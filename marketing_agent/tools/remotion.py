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


# Composant React et constante de durée par type — doit correspondre aux noms dans Root.tsx
_TYPE_TO_COMPONENT = {
    "VersusVideoProps":   "VersusVideo as React.ComponentType",
    "EducatifVideoProps": "EducatifVideo as React.ComponentType",
    "PromoVideoProps":    "PromoVideo as React.ComponentType",
}

_TYPE_DURATION_CONST = {
    "VersusVideoProps":   "VERSUS_TOTAL_FRAMES",
    "EducatifVideoProps": "EDUCATIF_TOTAL_FRAMES",
    "PromoVideoProps":    "PROMO_TOTAL_FRAMES",
}


def create_post_composition(composition_id: str, project_path: str, props: dict) -> dict:
    """Crée une nouvelle composition dans Root.tsx (const block + tag single-line)."""
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

        # ── 2. Insérer le tag <Composition> en format single-line ─────────────────
        if not has_tag:
            component = _TYPE_TO_COMPONENT.get(
                template_type, template_type.replace("Props", "") + " as React.ComponentType"
            )
            duration_const = _TYPE_DURATION_CONST.get(template_type, "EDUCATIF_TOTAL_FRAMES")

            # Format identique aux compositions manuelles (single-line, constantes TS)
            new_tag = (
                f'      <Composition'
                f' id="{composition_id}"'
                f' component={{{component}}}'
                f' durationInFrames={{{duration_const}}}'
                f' fps={{TIKTOK_FPS}}'
                f' width={{TIKTOK_W}}'
                f' height={{TIKTOK_H}}'
                f' defaultProps={{post{composition_id}}}'
                f' />'
            )

            # Chercher le dernier tag <Composition ... /> single-line et insérer après
            # (cherche les tags single-line sur une seule ligne)
            single_line_tags = list(re.finditer(
                r'^(\s*<Composition\s[^\n]*/>\s*)$', content, re.MULTILINE
            ))
            if single_line_tags:
                # Trier par ID pour insertion en ordre chronologique
                last_before = None
                for m in single_line_tags:
                    tag_id_m = re.search(r'id="(\d{8})"', m.group(0))
                    if tag_id_m and tag_id_m.group(1) <= composition_id:
                        last_before = m
                    elif tag_id_m and last_before is None:
                        # Tous les IDs sont supérieurs → insérer avant le premier
                        pos = m.start()
                        content = content[:pos] + new_tag + "\n" + content[pos:]
                        tsx.write_text(content, encoding="utf-8")
                        logger.info("Composition '%s' créée dans Root.tsx", composition_id)
                        return {"status": "created", "composition_id": composition_id,
                                "message": f"Composition '{composition_id}' créée dans Root.tsx"}

                if last_before:
                    pos = last_before.end()
                    content = content[:pos] + new_tag + "\n" + content[pos:]
            else:
                # Aucun tag single-line — insérer avant </> ou </RemotionRoot>
                close_m = re.search(r'(\s*</>|\s*</\w*Root>)', content)
                if close_m:
                    pos = close_m.start()
                    content = content[:pos] + "\n" + new_tag + "\n" + content[pos:]
                else:
                    content += "\n" + new_tag + "\n"

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


def normalize_root_tsx(project_path: str) -> dict:
    """Convertit toutes les <Composition> multi-lignes en single-line dans Root.tsx.

    Les tags multi-lignes (créés par d'anciennes versions du code) provoquent
    "Multiple composition registered" dans Remotion. Cette fonction les aplatit
    en une seule ligne, identique au format des compositions manuelles.
    """
    try:
        tsx = Path(project_path) / "src" / "Root.tsx"
        if not tsx.exists():
            return {"status": "error", "error": "Root.tsx introuvable"}

        content = tsx.read_text(encoding="utf-8", errors="ignore")
        original = content

        # Capture chaque tag <Composition ... /> (single ou multi-line)
        tag_re = re.compile(r'[ \t]*<Composition\b[^>]*/>', re.DOTALL)
        converted = []

        def _to_single_line(m: re.Match) -> str:
            tag = m.group(0)
            # Déjà single-line ?
            if "\n" not in tag:
                return tag
            # Extrait les attributs et les compacte sur une ligne
            tag_id_m = re.search(r'id="([^"]+)"', tag)
            comp_id = tag_id_m.group(1) if tag_id_m else "?"

            # Extrait les paires attribut=valeur et les rejoint sur une ligne
            attrs = re.findall(r'(\w+)=\{([^{}]*)\}|(\w+)="([^"]*)"', tag)
            parts = []
            for a1, v1, a2, v2 in attrs:
                if a1:
                    parts.append(f'{a1}={{{v1}}}')
                elif a2:
                    parts.append(f'{a2}="{v2}"')

            indent = "      "  # 6 espaces = indentation standard
            new_tag = f'{indent}<Composition {" ".join(parts)} />'
            converted.append(comp_id)
            logger.info("normalize_root_tsx: aplatissement de %s", comp_id)
            return new_tag

        new_content = tag_re.sub(_to_single_line, content)

        if new_content != original:
            tsx.write_text(new_content, encoding="utf-8")
            return {
                "status": "fixed",
                "converted": converted,
                "message": f"{len(converted)} tag(s) multi-lignes aplati(s) : {', '.join(converted)}",
            }

        return {"status": "ok", "converted": [], "message": "Tous les tags déjà en single-line"}
    except Exception as exc:
        logger.exception("Erreur normalize_root_tsx")
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


def delete_composition(composition_id: str, project_path: str) -> dict:
    """Supprime complètement une composition de Root.tsx (const block + tag <Composition>)."""
    try:
        tsx = Path(project_path) / "src" / "Root.tsx"
        if not tsx.exists():
            return {"status": "error", "error": "Root.tsx introuvable"}

        content = tsx.read_text(encoding="utf-8", errors="ignore")

        # 1. Supprimer le bloc const (const postID: ... = { ... };)
        m = re.search(rf"const post{composition_id}:\s*\w+Props\s*=\s*\{{", content)
        if m:
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
            if content[end:end+1] == ";":
                end += 1
            # Inclure les newlines précédentes/suivantes pour ne pas laisser de lignes vides
            start = m.start()
            while start > 0 and content[start-1] == "\n":
                start -= 1
            content = content[:start] + content[end:]

        # 2. Supprimer le tag <Composition id="ID" ... />  (single ou multi-line)
        tag_pattern = re.compile(
            r'\n?[ \t]*<Composition\b[^>]*?' + rf'id="{composition_id}"' + r'[^>]*/>', re.DOTALL
        )
        content = tag_pattern.sub("", content)

        # Nettoie les lignes vides multiples
        content = re.sub(r'\n{3,}', '\n\n', content)

        tsx.write_text(content, encoding="utf-8")
        logger.info("Composition '%s' supprimée de Root.tsx", composition_id)
        return {"status": "deleted", "composition_id": composition_id,
                "message": f"Composition '{composition_id}' supprimée — régénère le script pour la recréer."}
    except Exception as exc:
        logger.exception("Erreur delete_composition pour '%s'", composition_id)
        return {"status": "error", "error": str(exc)}


def list_src_files(project_path: str) -> list[str]:
    """Liste tous les fichiers TypeScript/TSX du projet Remotion."""
    src = Path(project_path) / "src"
    if not src.exists():
        return []
    return [str(f.relative_to(src)) for f in sorted(src.rglob("*")) if f.is_file()]


def read_project_file(project_path: str, relative_path: str) -> dict:
    """Lit le contenu d'un fichier du projet Remotion (relatif à la racine du projet)."""
    target = Path(project_path) / relative_path
    if not target.exists():
        return {"status": "error", "error": f"Fichier introuvable : {target}"}
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"status": "ok", "path": str(target), "content": content}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def scan_register_root(project_path: str) -> dict:
    """Scanne tous les fichiers du projet à la recherche de registerRoot et <Composition."""
    project = Path(project_path)
    register_hits = []
    composition_hits = []

    # Composition tag regex — handles single-line AND multi-line tags
    _comp_re = re.compile(
        r'<Composition\b[^>]*?id="(\d{8})"[^>]*/>', re.DOTALL
    )

    for f in sorted(project.rglob("*")):
        if not f.is_file():
            continue
        parts = f.parts
        if "node_modules" in parts or ".git" in parts:
            continue
        suffix = f.suffix.lower()
        if suffix not in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"):
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        rel = str(f.relative_to(project))
        lines = content.splitlines()

        for i, line in enumerate(lines, 1):
            if "registerRoot" in line:
                register_hits.append({"file": rel, "line": i, "content": line.strip()})

        # Find all <Composition> tags (single or multiline) and record line numbers
        for m in _comp_re.finditer(content):
            comp_id = m.group(1)
            line_no = content[:m.start()].count("\n") + 1
            snippet = m.group(0).replace("\n", " ")[:120]
            composition_hits.append({
                "file": rel,
                "line": line_no,
                "composition_id": comp_id,
                "content": snippet,
            })

    from collections import Counter
    id_counts = Counter(h["composition_id"] for h in composition_hits)
    duplicates = {k: v for k, v in id_counts.items() if v > 1}

    return {
        "registerRoot_occurrences": register_hits,
        "composition_tag_occurrences": composition_hits,
        "duplicates": duplicates,
        "has_duplicates": bool(duplicates),
        "summary": {
            "registerRoot_count": len(register_hits),
            "composition_tags_total": len(composition_hits),
            "unique_ids": len(id_counts),
        },
    }


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

    # Normalise Root.tsx avant le rendu : aplatit les tags multi-lignes qui
    # provoquent "Multiple composition registered" dans Remotion
    norm = normalize_root_tsx(project_path)
    if norm.get("converted"):
        logger.warning("render_video: tags normalisés avant rendu → %s", norm["converted"])

    out_dir = project / "out"
    out_dir.mkdir(exist_ok=True)

    filename = output_filename or f"{composition_id}.mp4"
    output_path = out_dir / filename

    npx = _find_npx()

    env = os.environ.copy()
    extra_paths = [
        r"C:\Program Files\nodejs",
        os.path.expandvars(r"%APPDATA%\npm"),
    ]
    env["PATH"] = os.pathsep.join(extra_paths) + os.pathsep + env.get("PATH", "")

    def _run(cmd: str) -> subprocess.CompletedProcess:
        logger.info("Remotion render : %s (cwd=%s)", cmd, project)
        return subprocess.run(
            cmd, cwd=str(project), shell=True, env=env,
            capture_output=True, text=True, timeout=600,
            encoding="utf-8", errors="replace",
        )

    try:
        cmd = f'"{npx}" remotion render "{composition_id}" "{output_path}"'
        result = _run(cmd)

        if result.returncode == 0:
            return {"status": "success", "composition_id": composition_id,
                    "output_path": str(output_path),
                    "message": f"Vidéo rendue → {output_path}"}

        error_output = (result.stderr or result.stdout or "")
        # "Multiple composition" → vide TOUS les caches connus et relance sans cache bundle
        if "Multiple composition" in error_output:
            # 1. Cache webpack local
            for cache_subdir in ["node_modules/.cache", ".remotion"]:
                cache_dir = project / cache_subdir
                if cache_dir.exists():
                    shutil.rmtree(cache_dir)
            # 2. Cache temp système (Windows)
            import tempfile as _tmp
            tmp = Path(_tmp.gettempdir())
            for entry in tmp.glob("remotion-*"):
                try:
                    shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
                except Exception:
                    pass
            logger.warning("Tous les caches Remotion vidés — retry avec --bundle-cache=false")
            # Relance sans cache bundle
            cmd_no_cache = (
                f'"{npx}" remotion render --bundle-cache=false '
                f'"{composition_id}" "{output_path}"'
            )
            result = _run(cmd_no_cache)
            if result.returncode == 0:
                return {"status": "success", "composition_id": composition_id,
                        "output_path": str(output_path),
                        "message": f"Vidéo rendue → {output_path} (cache vidé)"}
            error_output = (result.stderr or result.stdout or "")

        logger.error("Remotion render failed (code %d): %s", result.returncode, error_output[-3000:])
        return {"status": "error", "error": f"Exit code {result.returncode}\n\n{error_output[-3000:]}"}

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
