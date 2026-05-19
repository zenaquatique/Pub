"""Rendu de vidéos via Remotion (npx remotion render)."""
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


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
            cmd,
            cwd=str(project),
            shell=True,
            capture_output=True,
            text=True,
            timeout=600,   # 10 minutes max
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            return {
                "status": "success",
                "composition_id": composition_id,
                "output_path": str(output_path),
                "message": f"Vidéo rendue avec succès → {output_path}",
            }
        stderr = (result.stderr or result.stdout or "")[-3000:]
        return {"status": "error", "error": stderr}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Timeout — rendu trop long (>10 min)"}
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
