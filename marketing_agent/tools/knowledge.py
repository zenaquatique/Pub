"""Lecture de la vault Obsidian et du dossier d'assets vidéo."""
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_MD_EXTS = {".md", ".txt"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

_MEMORY_FOLDER = "Mémoire Agent"
_MEMORY_FILE   = "memoire.md"

# Dossier de contexte local (commité dans le repo, toujours disponible)
_LOCAL_CONTEXT_DIR  = Path(__file__).parent.parent / "data" / "context"

# Dossier calendrier local (commité dans le repo, sync via git — pas besoin d'Obsidian)
_LOCAL_CALENDAR_DIR = Path(__file__).parent.parent / "data" / "calendrier"

_MONTH_NUM = {
    "jan": 1, "fév": 2, "feb": 2, "mar": 3, "avr": 4, "apr": 4,
    "mai": 5, "may": 5, "jun": 6, "juin": 6, "jul": 7,
    "aoû": 8, "aug": 8, "sep": 9, "oct": 10, "nov": 11,
    "déc": 12, "dec": 12,
}

def _calendar_sort_key(entry: dict) -> tuple:
    """Extrait (année, mois) depuis un nom de fichier comme 'juin-2026.md'."""
    stem = Path(entry["file"]).stem.lower()
    year = month = 0
    for part in stem.replace("_", "-").split("-"):
        if part.isdigit() and len(part) == 4:
            year = int(part)
        elif part[:3] in _MONTH_NUM:
            month = _MONTH_NUM[part[:3]]
    return (year, month)


def read_local_context() -> str:
    """Lit tous les fichiers .md du dossier data/context/ du projet."""
    if not _LOCAL_CONTEXT_DIR.exists():
        return ""
    parts = []
    for f in sorted(_LOCAL_CONTEXT_DIR.glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="ignore").strip()
        if text:
            parts.append(f"\n---\n## [contexte local] {f.name}\n{text}")
    return "\n".join(parts)


def read_agent_memory(vault_path: str) -> str:
    """Lit le fichier mémoire de l'agent dans la vault Obsidian."""
    p = Path(vault_path) / _MEMORY_FOLDER / _MEMORY_FILE
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore").strip()


def append_agent_memory(vault_path: str, note: str) -> dict:
    """Ajoute une note datée dans la mémoire persistante de l'agent."""
    folder = Path(vault_path) / _MEMORY_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / _MEMORY_FILE
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n## {timestamp}\n{note.strip()}\n"
    with f.open("a", encoding="utf-8") as fp:
        fp.write(entry)
    logger.info("Mémoire agent mise à jour : %s", f)
    return {"status": "success", "path": str(f), "note_saved": note[:120]}


def read_obsidian_vault(vault_path: str, max_chars: int = 80_000) -> str:
    """Retourne le contenu de tous les fichiers .md/.txt de la vault Obsidian."""
    p = Path(vault_path)
    if not vault_path or not p.exists():
        return ""

    parts: list[str] = []
    total = 0

    for f in sorted(p.rglob("*")):
        if f.suffix.lower() not in _MD_EXTS or not f.is_file():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                continue
            relative = f.relative_to(p)
            header = f"\n---\n## {relative}\n"
            chunk = header + text
            parts.append(chunk)
            total += len(chunk)
            if total >= max_chars:
                parts.append("\n[... vault tronquée — limite atteinte ...]")
                break
        except Exception as exc:
            logger.warning("Lecture vault ignorée %s : %s", f, exc)

    return "\n".join(parts)


# Mots-clés précis — on évite les termes trop génériques ("contenu", "plan")
_CALENDAR_FOLDER_KEYWORDS = {"calendrier", "calendar", "planning", "editorial", "éditorial", "schedule"}
_CALENDAR_FILE_KEYWORDS   = {"calendrier", "calendar", "planning", "editorial", "éditorial", "schedule", "publication"}


def find_calendar_files(vault_path: str) -> list[dict]:
    """Retourne les fichiers liés au calendrier éditorial.

    Sources (fusionnées, dédupliquées par nom de fichier) :
    1. data/calendrier/ du repo Git  ← toujours disponible, sync via git
    2. Vault Obsidian (si vault_path existe)  ← optionnel, PC principal
    """
    results: dict[str, dict] = {}  # filename → entry (déduplique)

    # ── Source 1 : dossier local Git (priorité) ───────────────────────────────
    if _LOCAL_CALENDAR_DIR.exists():
        for f in sorted(_LOCAL_CALENDAR_DIR.rglob("*.md")):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore").strip()
                if content:
                    results[f.name] = {
                        "file": f"calendrier/{f.name}",
                        "path": str(f),
                        "content": content,
                        "source": "git",
                    }
            except Exception as exc:
                logger.warning("Lecture calendrier local ignorée %s : %s", f, exc)

    # ── Source 2 : vault Obsidian (optionnelle) ───────────────────────────────
    p = Path(vault_path) if vault_path else None
    if p and p.exists():
        priority: list[dict] = []
        fallback: list[dict] = []
        for f in sorted(p.rglob("*.md")):
            try:
                rel = f.relative_to(p)
                parts_list = list(rel.parts)
                folder_parts_lower = [pt.lower() for pt in parts_list[:-1]]
                file_name_lower    = rel.stem.lower()
                content = f.read_text(encoding="utf-8", errors="ignore").strip()
                if not content:
                    continue
                entry = {"file": str(rel), "path": str(f), "content": content, "source": "obsidian"}
                if any(kw in fp for kw in _CALENDAR_FOLDER_KEYWORDS for fp in folder_parts_lower):
                    priority.append(entry)
                elif any(kw in file_name_lower for kw in _CALENDAR_FILE_KEYWORDS):
                    fallback.append(entry)
            except Exception as exc:
                logger.warning("Lecture calendrier Obsidian ignorée %s : %s", f, exc)
        priority.sort(key=lambda x: x["file"], reverse=True)
        fallback.sort(key=lambda x: x["file"], reverse=True)
        for entry in priority + fallback:
            fname = Path(entry["file"]).name
            if fname not in results:  # git a la priorité
                results[fname] = entry

    combined = sorted(results.values(), key=_calendar_sort_key, reverse=True)
    if not combined:
        logger.warning("Aucun fichier calendrier trouvé (ni git ni Obsidian).")
    return combined


def write_calendar_file(vault_path: str, filename: str, content: str) -> dict:
    """Crée ou met à jour un fichier markdown calendrier.

    Écrit dans data/calendrier/ du repo Git (sync via git, disponible partout).
    Si la vault Obsidian est aussi disponible, écrit en miroir dedans.
    """
    # ── Toujours écrire dans le dossier Git ──────────────────────────────────
    _LOCAL_CALENDAR_DIR.mkdir(parents=True, exist_ok=True)
    git_target = _LOCAL_CALENDAR_DIR / filename
    git_target.write_text(content, encoding="utf-8")
    logger.info("Calendrier écrit (git) : %s", git_target)

    # ── Miroir dans Obsidian si disponible ───────────────────────────────────
    p = Path(vault_path) if vault_path else None
    if p and p.exists():
        cal_folder = None
        for folder in sorted(p.rglob("*")):
            if folder.is_dir() and any(kw in folder.name.lower() for kw in _CALENDAR_FOLDER_KEYWORDS):
                cal_folder = folder
                break
        if cal_folder is None:
            cal_folder = p / "Calendrier Publication"
            cal_folder.mkdir(parents=True, exist_ok=True)
        obs_target = cal_folder / filename
        obs_target.write_text(content, encoding="utf-8")
        logger.info("Calendrier écrit (Obsidian miroir) : %s", obs_target)

    return {"status": "success", "path": str(git_target), "file": filename}


def sync_calendars_to_obsidian(vault_path: str) -> dict:
    """Copie tous les fichiers de data/calendrier/ vers la vault Obsidian.

    Utile quand un calendrier est créé directement dans le repo Git
    (sans passer par write_calendar_file) et doit apparaître dans Obsidian.
    """
    if not _LOCAL_CALENDAR_DIR.exists():
        return {"status": "error", "error": "data/calendrier/ introuvable"}

    p = Path(vault_path) if vault_path else None
    if not p or not p.exists():
        return {"status": "error", "error": f"Vault Obsidian introuvable : {vault_path}"}

    cal_folder = None
    for folder in sorted(p.rglob("*")):
        if folder.is_dir() and any(kw in folder.name.lower() for kw in _CALENDAR_FOLDER_KEYWORDS):
            cal_folder = folder
            break
    if cal_folder is None:
        cal_folder = p / "Calendrier Publication"
        cal_folder.mkdir(parents=True, exist_ok=True)

    synced = []
    for f in sorted(_LOCAL_CALENDAR_DIR.glob("*.md")):
        try:
            dest = cal_folder / f.name
            dest.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            synced.append(f.name)
            logger.info("Sync Obsidian : %s → %s", f.name, dest)
        except Exception as exc:
            logger.warning("Sync Obsidian échoué pour %s : %s", f.name, exc)

    return {"status": "success", "synced": synced, "obsidian_folder": str(cal_folder)}


def list_video_assets(assets_path: str) -> list[dict]:
    """Liste les vidéos, images et docs du dossier d'assets."""
    p = Path(assets_path)
    if not assets_path or not p.exists():
        return []

    assets: list[dict] = []
    for f in sorted(p.rglob("*")):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        if ext in _VIDEO_EXTS | _IMAGE_EXTS | _MD_EXTS:
            assets.append({
                "name": f.name,
                "path": str(f),
                "type": "video" if ext in _VIDEO_EXTS
                        else "image" if ext in _IMAGE_EXTS
                        else "document",
                "size_kb": round(f.stat().st_size / 1024, 1),
            })
    return assets[:100]
