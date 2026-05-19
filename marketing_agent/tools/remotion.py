"""Rendu de vidéos via Remotion (npx remotion render)."""
import logging
import re
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
    """Génère le script voix off structuré depuis les props Remotion."""
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


def update_post_props(composition_id: str, project_path: str, updates: dict) -> dict:
    """Met à jour des champs du post dans Root.tsx (hookText, verdict, items, etc.)."""
    tsx = Path(project_path) / "src" / "Root.tsx"
    if not tsx.exists():
        return {"status": "error", "error": "Root.tsx introuvable"}

    content = tsx.read_text(encoding="utf-8", errors="ignore")

    m = re.search(rf"const post{composition_id}:\s*\w+Props\s*=\s*\{{", content)
    if not m:
        return {"status": "error", "error": f"Composition '{composition_id}' introuvable dans Root.tsx"}

    block_start = m.end() - 1
    depth, end = 0, block_start
    for i, ch in enumerate(content[block_start:], block_start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    block = content[block_start:end]

    for key, value in updates.items():
        if isinstance(value, str):
            block = re.sub(
                rf'({re.escape(key)}\s*:\s*)"[^"]*"',
                lambda mo, v=value: f'{mo.group(1)}"{v}"',
                block,
            )
        elif isinstance(value, list) and all(isinstance(x, str) for x in value):
            items_str = ", ".join(f'"{x}"' for x in value)
            block = re.sub(
                rf'({re.escape(key)}\s*:\s*)\[[^\]]*\]',
                lambda mo, s=items_str: f'{mo.group(1)}[{s}]',
                block,
                flags=re.DOTALL,
            )

    new_content = content[:block_start] + block + content[end:]
    tsx.write_text(new_content, encoding="utf-8")
    return {
        "status": "success",
        "composition_id": composition_id,
        "updated_fields": list(updates.keys()),
        "message": f"Root.tsx mis à jour — {len(updates)} champ(s) modifié(s). Lance render_video pour regénérer.",
    }


def render_video(composition_id: str, project_path: str, output_filename: str = "") -> dict:
    """Lance npx remotion render <composition_id> dans le dossier du projet."""
    project = Path(project_path)
    if not project.exists():
        return {"status": "error", "error": f"Dossier projet introuvable : {project_path}"}

    out_dir = project / "out"
    out_dir.mkdir(exist_ok=True)

    filename = output_filename or f"{composition_id}.mp4"
    output_path = out_dir / filename

    cmd = f'npx remotion render "{composition_id}" "{output_path}"'
    logger.info("Remotion render : %s (cwd=%s)", cmd, project)

    try:
        result = subprocess.run(
            cmd, cwd=str(project), shell=True,
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
        return {"status": "error", "error": (result.stderr or result.stdout or "")[-3000:]}
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
