"""Lecture de la vault Obsidian et du dossier d'assets vidéo."""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_MD_EXTS = {".md", ".txt"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


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
