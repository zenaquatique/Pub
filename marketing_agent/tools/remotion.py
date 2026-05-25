"""Rendu de vidéos via Remotion (npx remotion render)."""
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_FRENCH_MONTHS = {
    "jan": 1, "fév": 2, "feb": 2, "mar": 3, "avr": 4, "apr": 4,
    "mai": 5, "may": 5, "jun": 6, "juin": 6, "jul": 7, "juil": 7,
    "aoû": 8, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "déc": 12, "dec": 12,
}


def date_to_composition_id(date_str: str, year: int = 2026) -> str:
    """Convertit '19 mai', 'Lun 19 mai' ou '30 avr' en '20260519'."""
    tokens = re.sub(r"[^\w\s]", "", date_str.lower()).split()
    day = None
    month = None
    for tok in tokens:
        if tok.isdigit():
            day = int(tok)
        elif tok[:3] in _FRENCH_MONTHS:
            month = _FRENCH_MONTHS[tok[:3]]
    if day and month:
        return f"{year}{month:02d}{day:02d}"
    return ""


def extract_post_props(composition_id: str, project_path: str) -> dict:
    """Extrait les props d'un post depuis src/Root.tsx."""
    tsx = Path(project_path) / "src" / "Root.tsx"
    if not tsx.exists():
        return {}

    content = tsx.read_text(encoding="utf-8", errors="ignore")

    # Find `const post<ID>: <Type>Props = {`
    m = re.search(rf"const post{composition_id}:\s*(\w+Props)\s*=\s*\{{", content)
    if not m:
        return {}

    template_type = m.group(1)
    start = m.end() - 1

    # Walk forward to find matching closing brace
    depth, end = 0, start
    for i, ch in enumerate(content[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    block = content[start:end]

    def get_str(key: str) -> str:
        mm = re.search(rf'{key}\s*:\s*"([^"]*)"', block)
        return mm.group(1) if mm else ""

    def get_list(key: str) -> list[str]:
        mm = re.search(rf'{key}\s*:\s*\[([^\]]*)\]', block, re.DOTALL)
        if not mm:
            return []
        return re.findall(r'"([^"]*)"', mm.group(1))

    props: dict = {"template_type": template_type, "composition_id": composition_id}

    for key in ["hookText", "hookEmoji", "verdict", "musicTrack", "ctaText",
                "leftLabel", "rightLabel"]:
        v = get_str(key)
        if v:
            props[key] = v

    for key in ["leftItems", "rightItems"]:
        v = get_list(key)
        if v:
            props[key] = v

    # Tips (EducatifVideo)
    tips = re.findall(
        r'\{\s*num\s*:\s*"([^"]*)"\s*,\s*title\s*:\s*"([^"]*)"\s*,\s*desc\s*:\s*"([^"]*)"\s*\}',
        block,
    )
    if tips:
        props["tips"] = [{"num": t[0], "title": t[1], "desc": t[2]} for t in tips]

    # Plants (PromoVideo)
    plants = re.findall(
        r'\{\s*emoji\s*:\s*"([^"]*)"\s*,\s*name\s*:\s*"([^"]*)"\s*,\s*description\s*:\s*"([^"]*)"\s*,\s*price\s*:\s*"([^"]*)"\s*[,}]',
        block,
    )
    if plants:
        props["plants"] = [
            {"emoji": p[0], "name": p[1], "description": p[2], "price": p[3]}
            for p in plants
        ]

    return props


def generate_voiceover(props: dict) -> str:
    """Génère le script voix off structuré depuis les props Remotion.
    Rythme cible : 3,5 mots/seconde → hook 10-14 mots (3 s), tip desc 14-18 mots (5 s), CTA 10-14 mots (3 s).
    """
    t = props.get("template_type", "")
    lines: list[str] = []

    if "VersusVideoProps" in t:
        hook       = props.get("hookText", "")
        l_label    = props.get("leftLabel", "Option A")
        r_label    = props.get("rightLabel", "Option B")
        l_items    = props.get("leftItems", [])
        r_items    = props.get("rightItems", [])
        verdict    = props.get("verdict", "")

        lines = [
            "🎬 SCRIPT VOIX OFF — Versus",
            "",
            "[HOOK — 0 à 3 s]",
            f'« {hook} »',
            "",
            f"[{l_label.upper()} — 3 à 10 s]",
        ] + [f"  · {item}" for item in l_items] + [
            "",
            f"[{r_label.upper()} — 10 à 17 s]",
        ] + [f"  · {item}" for item in r_items] + [
            "",
            "[VERDICT — 17 à 20 s]",
            f'« {verdict} »',
            "",
            "[CTA — 20 à 23 s]",
            '« Clique sur le lien en bio ! »',
        ]

    elif "EducatifVideoProps" in t:
        emoji = props.get("hookEmoji", "")
        hook  = props.get("hookText", "")
        tips  = props.get("tips", [])
        cta   = props.get("ctaText", "Lien en bio !")

        lines = [
            "🎬 SCRIPT VOIX OFF — Éducatif",
            "",
            "[HOOK — 0 à 3 s]",
            f'« {emoji} {hook} »',
            "",
        ]
        for i, tip in enumerate(tips):
            s = 3 + i * 5
            lines += [
                f"[CONSEIL {tip['num']} — {s} à {s+5} s]",
                f"  Titre affiché : « {tip['title']} »",
                f"  Voix off      : « {tip['desc']} »",
                "",
            ]
        end_s = 3 + len(tips) * 5
        lines += [
            f"[CTA — {end_s} à {end_s+3} s]",
            f'« {cta} »',
        ]

    elif "PromoVideoProps" in t:
        hook   = props.get("hookText", "")
        plants = props.get("plants", [])
        cta    = props.get("ctaText", "Commande avant dimanche soir !")

        lines = [
            "🎬 SCRIPT VOIX OFF — Promo",
            "",
            "[HOOK — 0 à 3 s]",
            f'« {hook} »',
            "",
        ]
        for i, p in enumerate(plants):
            s = 3 + i * 4
            lines += [
                f"[PLANTE {i+1} — {s} à {s+4} s]",
                f'  « {p["emoji"]} {p["name"]} — {p["description"]} — {p["price"]} »',
                "",
            ]
        lines += ["[CTA]", f'« {cta} »']

    else:
        lines = [f"Type '{t}' non pris en charge pour la voix off."]

    return "\n".join(lines)


def _escape_ts(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _props_to_ts_block(composition_id: str, template_type: str, props: dict) -> str:
    """Reconstruit le bloc TypeScript complet pour un post."""
    lines: list[str] = []
    for key, value in props.items():
        if key in ("template_type", "composition_id"):
            continue
        if isinstance(value, str):
            lines.append(f'  {key}: "{_escape_ts(value)}",')
        elif isinstance(value, list):
            if not value:
                lines.append(f'  {key}: [],')
            elif isinstance(value[0], str):
                items = ", ".join(f'"{_escape_ts(x)}"' for x in value)
                lines.append(f'  {key}: [{items}],')
            elif isinstance(value[0], dict):
                inner = []
                for obj in value:
                    fields = ", ".join(f'{k}: "{_escape_ts(str(v))}"' for k, v in obj.items())
                    inner.append(f"    {{ {fields} }}")
                lines.append(f'  {key}: [\n' + ",\n".join(inner) + "\n  ],")
    return f"const post{composition_id}: {template_type} = {{\n" + "\n".join(lines) + "\n};"


_TYPE_TO_COMPONENT = {
    "VersusVideoProps":   "VersusVideo",
    "EducatifVideoProps": "EducatifVideo",
    "PromoVideoProps":    "PromoVideo",
}

_TYPE_DURATION = {
    "VersusVideoProps":   690,   # 23 s × 30 fps
    "EducatifVideoProps": 690,
    "PromoVideoProps":    480,   # 16 s × 30 fps
}


def create_post_composition(composition_id: str, project_path: str, props: dict) -> dict:
    """Crée une nouvelle composition dans Root.tsx (const block + enregistrement)."""
    try:
        tsx = Path(project_path) / "src" / "Root.tsx"
        if not tsx.exists():
            return {"status": "error", "error": "Root.tsx introuvable"}

        template_type = props.get("template_type", "")
        if not template_type:
            return {"status": "error", "error": "template_type manquant"}

        content = tsx.read_text(encoding="utf-8", errors="ignore")

        has_const = bool(re.search(rf"const post{composition_id}:", content))
        has_tag   = bool(re.search(rf'id="{composition_id}"', content))

        # Bloc const existant → mise à jour des props uniquement
        if has_const:
            return update_post_props(composition_id, project_path, props)

        # ── 1. Ajouter le bloc const avant le premier export ──────────────────────
        clean = {k: v for k, v in props.items() if k not in ("template_type", "composition_id")}
        const_block = _props_to_ts_block(composition_id, template_type, clean)

        export_m = re.search(r'\nexport ', content)
        if export_m:
            pos = export_m.start()
            content = content[:pos] + "\n\n" + const_block + "\n" + content[pos:]
        else:
            content += "\n\n" + const_block + "\n"

        # ── 2. Insérer le tag <Composition> seulement s'il n'existe pas déjà ─────
        if not has_tag:
            comp_m = re.search(
                r'<Composition[^>]*?fps=\{(\d+)\}[^>]*?width=\{(\d+)\}[^>]*?height=\{(\d+)\}',
                content, re.DOTALL,
            )
            fps    = int(comp_m.group(1)) if comp_m else 30
            width  = int(comp_m.group(2)) if comp_m else 1080
            height = int(comp_m.group(3)) if comp_m else 1920
            duration = _TYPE_DURATION.get(template_type, 600)
            component = _TYPE_TO_COMPONENT.get(template_type, template_type.replace("Props", ""))

            new_comp = (
                f'      <Composition\n'
                f'        id="{composition_id}"\n'
                f'        component={{{component}}}\n'
                f'        durationInFrames={{{duration}}}\n'
                f'        fps={{{fps}}}\n'
                f'        width={{{width}}}\n'
                f'        height={{{height}}}\n'
                f'        defaultProps={{post{composition_id}}}\n'
                f'      />'
            )

            all_ends = list(re.finditer(r'/>[ \t]*\n(\s*(?=<Composition|\s*</))', content))
            if all_ends:
                m = all_ends[-1]
                pos = m.start() + 2   # après />
                content = content[:pos] + "\n" + new_comp + content[pos:]
            else:
                close_m = re.search(r'(</>|</\w*Root>)', content)
                if close_m:
                    pos = close_m.start()
                    content = content[:pos] + new_comp + "\n      " + content[pos:]

        tsx.write_text(content, encoding="utf-8")
        logger.info("Composition '%s' créée dans Root.tsx", composition_id)
        return {
            "status": "created",
            "composition_id": composition_id,
            "message": f"Composition '{composition_id}' créée dans Root.tsx",
        }
    except Exception as exc:
        logger.exception("Erreur create_post_composition pour '%s'", composition_id)
        return {"status": "error", "error": str(exc)}


def repair_root_tsx(project_path: str) -> dict:
    """Supprime les balises <Composition> dupliquées dans Root.tsx (single-line ou multi-line)."""
    try:
        tsx = Path(project_path) / "src" / "Root.tsx"
        if not tsx.exists():
            return {"status": "error", "error": "Root.tsx introuvable"}

        content = tsx.read_text(encoding="utf-8", errors="ignore")

        # Capture <Composition ... /> (single ou multi-line ; pas de > dans les attributs JSX)
        pattern = re.compile(r'\n?[ \t]*<Composition\b[^>]*/>', re.DOTALL)

        seen_ids: list = []
        removed: list = []

        def _dedup(m: re.Match) -> str:
            tag = m.group(0)
            id_m = re.search(r'id="([^"]+)"', tag)
            if id_m:
                cid = id_m.group(1)
                if cid in seen_ids:
                    removed.append(cid)
                    return ""
                seen_ids.append(cid)
            return tag

        new_content = pattern.sub(_dedup, content)

        if removed:
            tsx.write_text(new_content, encoding="utf-8")
            logger.info("repair_root_tsx : supprimé %s", removed)
            return {"status": "fixed", "removed": removed,
                    "message": f"{len(removed)} doublon(s) supprimé(s) : {', '.join(removed)}"}

        return {"status": "ok", "removed": [], "message": "Aucun doublon trouvé dans Root.tsx"}
    except Exception as exc:
        logger.exception("Erreur repair_root_tsx")
        return {"status": "error", "error": str(exc)}


def update_post_props(composition_id: str, project_path: str, updates: dict) -> dict:
    """Remplace entièrement le bloc props d'un post dans Root.tsx."""
    try:
        tsx = Path(project_path) / "src" / "Root.tsx"
        if not tsx.exists():
            return {"status": "error", "error": "Root.tsx introuvable"}

        content = tsx.read_text(encoding="utf-8", errors="ignore")

        m = re.search(rf"const post{composition_id}:\s*(\w+Props)\s*=\s*\{{", content)
        if not m:
            return {"status": "error", "error": f"Composition '{composition_id}' introuvable dans Root.tsx"}

        template_type = m.group(1)
        block_start = m.start()
        brace_start = m.end() - 1
        depth, end = 0, brace_start
        for i, ch in enumerate(content[brace_start:], brace_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        # skip trailing semicolon
        if content[end:end+1] == ";":
            end += 1

        # Merge existing props with updates
        current = extract_post_props(composition_id, project_path)
        merged = {k: v for k, v in current.items() if k not in ("template_type", "composition_id")}
        merged.update({k: v for k, v in updates.items() if k not in ("template_type", "composition_id")})

        new_block = _props_to_ts_block(composition_id, template_type, merged)
        new_content = content[:block_start] + new_block + content[end:]
        tsx.write_text(new_content, encoding="utf-8")
        return {
            "status": "success",
            "composition_id": composition_id,
            "updated_fields": list(updates.keys()),
            "message": f"Root.tsx mis à jour — relance render_video pour regénérer la vidéo.",
        }
    except Exception as exc:
        logger.exception("Erreur update_post_props pour '%s'", composition_id)
        return {"status": "error", "error": str(exc)}


def _find_npx() -> str:
    """Trouve npx dans PATH ou dans les emplacements Node.js courants."""
    found = shutil.which("npx")
    if found:
        return found
    # Emplacements Windows courants
    candidates = [
        r"C:\Program Files\nodejs\npx.cmd",
        r"C:\Program Files (x86)\nodejs\npx.cmd",
        os.path.expandvars(r"%APPDATA%\npm\npx.cmd"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\nodejs\npx.cmd"),
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return "npx"  # fallback — laisse le shell le trouver


def render_video(composition_id: str, project_path: str, output_filename: str = "") -> dict:
    """Lance npx remotion render <composition_id> dans le dossier du projet."""
    project = Path(project_path)
    if not project.exists():
        return {"status": "error", "error": f"Dossier projet introuvable : {project_path}"}

    out_dir = project / "out"
    out_dir.mkdir(exist_ok=True)

    filename = output_filename or f"{composition_id}.mp4"
    output_path = out_dir / filename

    npx = _find_npx()
    cmd = f'"{npx}" remotion render "{composition_id}" "{output_path}"'
    logger.info("Remotion render : %s (cwd=%s)", cmd, project)

    # Enrichit PATH avec les dossiers Node.js courants pour que npx trouve ses modules
    env = os.environ.copy()
    extra_paths = [
        r"C:\Program Files\nodejs",
        os.path.expandvars(r"%APPDATA%\npm"),
    ]
    env["PATH"] = os.pathsep.join(extra_paths) + os.pathsep + env.get("PATH", "")

    try:
        result = subprocess.run(
            cmd, cwd=str(project), shell=True, env=env,
            capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace",
        )
        if result.returncode == 0:
            return {
                "status": "success",
                "composition_id": composition_id,
                "output_path": str(output_path),
                "message": f"Vidéo rendue → {output_path}",
            }
        error_output = (result.stderr or result.stdout or "Aucune sortie")[-3000:]
        logger.error("Remotion render failed (code %d): %s", result.returncode, error_output)
        return {"status": "error", "error": f"Exit code {result.returncode}\n\n{error_output}"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Timeout — rendu >10 min"}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def list_rendered_videos(project_path: str) -> list[dict]:
    """Liste les MP4 déjà rendus dans out/."""
    out = Path(project_path) / "out"
    if not out.exists():
        return []
    videos = []
    for f in sorted(out.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True):
        videos.append({
            "filename": f.name,
            "path": str(f),
            "size_mb": round(f.stat().st_size / 1_048_576, 1),
        })
    return videos[:20]
