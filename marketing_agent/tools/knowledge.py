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
    """Retourne les fichiers Obsidian liés au calendrier éditorial.

    Priorité :
    1. Fichiers dont un dossier parent contient un mot-clé calendrier (ex: 'Calendrier Publication/mai-2026.md')
    2. Fichiers dont le nom contient un mot-clé calendrier
    """
    p = Path(vault_path)
    if not vault_path or not p.exists():
        return []

    priority: list[dict] = []   # dossier parent calendrier
    fallback: list[dict] = []   # nom de fichier calendrier

    for f in sorted(p.rglob("*.md")):
        try:
            rel = f.relative_to(p)
            parts = list(rel.parts)
            folder_parts_lower = [pt.lower() for pt in parts[:-1]]  # dossiers seulement
            file_name_lower    = rel.stem.lower()

            content = f.read_text(encoding="utf-8", errors="ignore").strip()
            if not content:
                continue

            entry = {"file": str(rel), "path": str(f), "content": content}

            if any(kw in fp for kw in _CALENDAR_FOLDER_KEYWORDS for fp in folder_parts_lower):
                priority.append(entry)
            elif any(kw in file_name_lower for kw in _CALENDAR_FILE_KEYWORDS):
                fallback.append(entry)
        except Exception as exc:
            logger.warning("Lecture calendrier ignorée %s : %s", f, exc)

    # Dans chaque groupe, les plus récents (année/mois dans le nom) en premier
    priority.sort(key=lambda x: x["file"], reverse=True)
    fallback.sort(key=lambda x: x["file"], reverse=True)
    return priority + fallback


def write_calendar_file(vault_path: str, filename: str, content: str) -> dict:
    """Crée ou met à jour un fichier markdown dans le dossier Calendrier Publication."""
    p = Path(vault_path)
    if not vault_path or not p.exists():
        return {"status": "error", "error": f"Vault introuvable : {vault_path}"}

    # Cherche le dossier calendrier existant
    cal_folder = None
    for folder in sorted(p.rglob("*")):
        if folder.is_dir() and any(kw in folder.name.lower() for kw in _CALENDAR_FOLDER_KEYWORDS):
            cal_folder = folder
            break

    if cal_folder is None:
        cal_folder = p / "Calendrier Publication"
        cal_folder.mkdir(parents=True, exist_ok=True)

    target = cal_folder / filename
    target.write_text(content, encoding="utf-8")
    logger.info("Calendrier écrit : %s", target)
    return {"status": "success", "path": str(target), "file": filename}


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
