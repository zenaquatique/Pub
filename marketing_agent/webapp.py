"""Tableau de bord web — contrôle complet de l'agent marketing."""
import asyncio
import hashlib
import hmac
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from agent import execute_pending_action, _load_pending_actions, PENDING_ACTIONS_FILE
from config import (
    META_APP_SECRET, META_WEBHOOK_VERIFY_TOKEN, STORE_NAME, POSTING_HOUR, POSTING_MINUTE,
    OBSIDIAN_VAULT_PATH, VIDEO_ASSETS_PATH, GOOGLE_API_KEY, GEMINI_MODEL,
    STORE_NICHE, BRAND_VOICE, TARGET_AUDIENCE,
)
from tools.customer import (
    get_pending_messages,
    log_customer_message,
    mark_replied,
    send_facebook_reply,
    send_instagram_reply,
)
from tools.knowledge import find_calendar_files, read_obsidian_vault, list_video_assets
from tools.remotion import (
    render_video, list_rendered_videos,
    extract_post_props, generate_voiceover, date_to_composition_id,
)
from tools.shopify import get_products, get_store_analytics

logger = logging.getLogger(__name__)

REPORTS_FILE = Path(__file__).parent / "data" / "reports.json"

# ─── État de l'agent ─────────────────────────────────────────────────────────

_agent_state: dict = {
    "status": "idle",   # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "report": "",
    "error": "",
    "task": "",
}
_executor = ThreadPoolExecutor(max_workers=1)

# ─── Persistance des rapports ─────────────────────────────────────────────────

def _load_reports() -> list:
    REPORTS_FILE.parent.mkdir(exist_ok=True)
    if REPORTS_FILE.exists():
        try:
            return json.loads(REPORTS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            REPORTS_FILE.unlink(missing_ok=True)
    return []


def _save_report(report: str, task: str = "") -> None:
    reports = _load_reports()
    reports.insert(0, {
        "id": str(datetime.now().timestamp()),
        "date": datetime.now().isoformat(),
        "task": task or "Routine quotidienne",
        "report": report,
    })
    REPORTS_FILE.write_text(json.dumps(reports[:50], ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Exécution de l'agent dans un thread ─────────────────────────────────────

def _run_agent_sync(task: str) -> None:
    from agent import run_marketing_session
    _agent_state.update(status="running", started_at=datetime.now().isoformat(),
                        finished_at=None, report="", error="", task=task)
    try:
        report = run_marketing_session(task or None)
        _agent_state.update(status="done", report=report, finished_at=datetime.now().isoformat())
        _save_report(report, task)
    except Exception as exc:
        logger.exception("Erreur agent")
        _agent_state.update(status="error", error=str(exc), finished_at=datetime.now().isoformat())


# ─── Application ──────────────────────────────────────────────────────────────

app = FastAPI(title=f"{STORE_NAME} — Marketing Agent")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

_HTML_FILE = Path(__file__).parent / "templates" / "index.html"


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    html = _HTML_FILE.read_text(encoding="utf-8").replace("{{ store_name }}", STORE_NAME)
    return HTMLResponse(content=html)


# ─── API — Agent ──────────────────────────────────────────────────────────────

@app.post("/api/run")
async def api_run(request: Request):
    if _agent_state["status"] == "running":
        raise HTTPException(409, "L'agent est déjà en cours d'exécution.")
    body = await request.json()
    task = body.get("task", "")
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_agent_sync, task)
    return {"status": "started"}


@app.get("/api/status")
async def api_status():
    return _agent_state


# ─── API — Données boutique ───────────────────────────────────────────────────

@app.get("/api/analytics")
async def api_analytics(period: str = "month", start_date: str = None, end_date: str = None):
    try:
        return get_store_analytics(period=period, start_date=start_date, end_date=end_date)
    except Exception as exc:
        raise HTTPException(502, f"Erreur Shopify : {exc}")


@app.get("/api/products")
async def api_products():
    try:
        return get_products(limit=20)
    except Exception as exc:
        raise HTTPException(502, f"Erreur Shopify : {exc}")


# ─── API — Rapports ───────────────────────────────────────────────────────────

@app.get("/api/reports")
async def api_reports():
    return _load_reports()


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: str):
    reports = [r for r in _load_reports() if r["id"] != report_id]
    REPORTS_FILE.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "deleted"}


# ─── API — Approbation des actions ───────────────────────────────────────────

@app.get("/api/pending-actions")
async def api_pending_actions():
    actions = _load_pending_actions()
    return [a for a in actions if a.get("status") == "pending"]


@app.get("/api/pending-actions/count")
async def api_pending_actions_count():
    actions = _load_pending_actions()
    count = sum(1 for a in actions if a.get("status") == "pending")
    return {"count": count}


@app.post("/api/pending-actions/{action_id}/approve")
async def api_approve_action(action_id: str):
    try:
        result = execute_pending_action(action_id)
        return {"status": "approved", "result": result}
    except Exception as exc:
        raise HTTPException(500, f"Erreur exécution : {exc}")


@app.post("/api/pending-actions/{action_id}/reject")
async def api_reject_action(action_id: str):
    actions = _load_pending_actions()
    found = False
    for action in actions:
        if action["id"] == action_id:
            action["status"] = "rejected"
            action["rejected_at"] = datetime.now().isoformat()
            found = True
            break
    if not found:
        raise HTTPException(404, f"Action introuvable : {action_id}")
    PENDING_ACTIONS_FILE.write_text(
        json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"status": "rejected"}


# ─── API — Messages clients ───────────────────────────────────────────────────

@app.get("/api/messages")
async def api_messages():
    return get_pending_messages()


@app.post("/api/messages/{message_id}/reply")
async def api_reply(message_id: str, request: Request):
    body = await request.json()
    platform = body.get("platform", "instagram")
    reply_text = body.get("reply_text", "")
    if not reply_text:
        raise HTTPException(400, "reply_text manquant")
    if platform == "instagram":
        result = send_instagram_reply(message_id, reply_text)
    else:
        result = send_facebook_reply(message_id, reply_text)
    mark_replied(message_id, reply_text)
    return result


# ─── Webhooks Meta ────────────────────────────────────────────────────────────

def _verify_meta_signature(payload: bytes, header: str) -> bool:
    if not META_APP_SECRET:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(META_APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


@app.get("/webhook")
async def verify_webhook(request: Request) -> PlainTextResponse:
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == META_WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(403, "Vérification échouée")


@app.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.body()
    if not _verify_meta_signature(body, request.headers.get("X-Hub-Signature-256", "")):
        raise HTTPException(401, "Signature invalide")
    data = json.loads(body)
    object_type = data.get("object", "")
    for entry in data.get("entry", []):
        for msg in entry.get("messaging", []):
            text = msg.get("message", {}).get("text", "")
            mid = msg.get("message", {}).get("mid", "")
            if text:
                platform = "instagram" if object_type == "instagram" else "facebook"
                log_customer_message(platform, msg.get("sender", {}).get("id", "?"), text, mid)
        for change in entry.get("changes", []):
            v = change.get("value", {})
            if v.get("id") and v.get("text"):
                platform = "instagram" if object_type == "instagram" else "facebook"
                log_customer_message(platform, v.get("from", {}).get("name", "?"), v["text"], v["id"])
    return {"status": "ok"}


# ─── API — Calendrier éditorial ──────────────────────────────────────────────

@app.get("/api/calendar")
async def api_calendar(file_index: int = 0):
    files = find_calendar_files(OBSIDIAN_VAULT_PATH)
    if not files:
        return {"raw": "", "source": "", "all_files": []}
    idx  = max(0, min(file_index, len(files) - 1))
    main = files[idx]
    return {"raw": main["content"], "source": main["file"], "all_files": [f["file"] for f in files]}


# ─── API — Rendu Remotion ────────────────────────────────────────────────────

def _render_sync(composition_id: str) -> dict:
    return render_video(composition_id, VIDEO_ASSETS_PATH, f"{composition_id}.mp4")


@app.post("/api/render-video")
async def api_render_video(request: Request):
    body = await request.json()
    composition_id = body.get("composition_id", "").strip()
    if not composition_id:
        raise HTTPException(400, "composition_id manquant")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _render_sync, composition_id)
    if result.get("status") == "error":
        raise HTTPException(500, result["error"])
    return result


@app.get("/api/post-script/{composition_id}")
async def api_post_script(composition_id: str):
    props = extract_post_props(composition_id, VIDEO_ASSETS_PATH)
    if not props:
        raise HTTPException(404, f"Composition '{composition_id}' introuvable dans Root.tsx")
    voiceover = generate_voiceover(props)
    return {"composition_id": composition_id, "props": props, "voiceover": voiceover}


@app.get("/api/rendered-videos")
async def api_rendered_videos():
    return list_rendered_videos(VIDEO_ASSETS_PATH)


# ─── API — Script vidéo ───────────────────────────────────────────────────────

_REMOTION_TEMPLATE_HINTS = {
    "Top3": (
        "Format Top3 (TikTokOrganic ~13s) : présente 3 plantes/produits en rafale. "
        "Chaque 'slot' = 1 produit avec son nom + bénéfice clé + prix. Rythme ultra-rapide. "
        "Script en 3 blocs : Slot1 / Slot2 / Slot3 + CTA final."
    ),
    "Concept": (
        "Format Concept (ConceptVideo-ZenAquatique 30s) : storytelling de marque. "
        "Accroche émotionnelle → problème du viewer → solution ZenAquatique → preuve → CTA. "
        "Ton chaleureux, voix off posée."
    ),
    "Educatif": (
        "Format Educatif (EducatifVideo-ZenAquatique 20s) : 3 conseils / erreurs / étapes. "
        "Structure : Intro question → Conseil 1 → Conseil 2 → Conseil 3 → CTA. "
        "Texte à l'écran court pour chaque conseil."
    ),
    "Versus": (
        "Format Versus (VersusVideo-ZenAquatique 20s) : comparaison bouture vs pot / boutique vs animalerie. "
        "Structure : Versus intro → Option A (avantages) → Option B (avantages) → Verdict ZenAquatique → CTA. "
        "Ton factuel et convaincant."
    ),
    "Promo": (
        "Format Promo (PromoVideo-ZenAquatique 16s) : 3 plantes en promotion week-end. "
        "Ultra direct : offre + prix barré + prix promo + urgence (weekend only). "
        "Chaque plante = 1 slide rapide. CTA : 'Commande avant dimanche'."
    ),
}


def _generate_video_script_sync(topic: str, platform: str, duration: str,
                                 template: str = "", remotion: str = "") -> dict:
    from google import genai
    from google.genai import types as gtypes

    vault_content = read_obsidian_vault(OBSIDIAN_VAULT_PATH)
    assets = list_video_assets(VIDEO_ASSETS_PATH)
    asset_list = "\n".join(f"  - [{a['type']}] {a['name']}" for a in assets) if assets else "  (aucun asset trouvé)"

    platform_tips = {
        "tiktok":    "TikTok : accroche dans les 3 premières secondes, rythme rapide, texte à l'écran très court",
        "instagram": "Instagram Reels : esthétique soignée, transitions fluides, CTA clair en fin",
        "facebook":  "Facebook : sous-titres obligatoires (60 % visionnés sans son), CTA avec lien boutique",
    }

    template_hint = _REMOTION_TEMPLATE_HINTS.get(template, "")
    template_section = f"\n\nTEMPLATE REMOTION SÉLECTIONNÉ — {template} ({remotion}) :\n{template_hint}" if template_hint else ""
    vault_section = f"\n\nVAULT OBSIDIAN (connaissances marque et calendrier) :\n{vault_content}" if vault_content else ""
    assets_section = f"\n\nASSETS DISPONIBLES dans le dossier vidéo :\n{asset_list}"

    prompt = f"""Tu es expert en création de contenu vidéo courts pour {STORE_NAME} ({STORE_NICHE}).
Voix de marque : {BRAND_VOICE}
Cible : {TARGET_AUDIENCE}
Plateforme : {platform_tips.get(platform, platform.upper())}
{template_section}{vault_section}{assets_section}

Crée un script vidéo COMPLET adapté au template ci-dessus (durée : {duration}).
Sujet / brief : {topic or 'Choisis le produit le plus pertinent depuis le calendrier éditorial ou les analytics'}

Respecte STRICTEMENT la structure du template (nombre de slots, durée, rythme).
Réponds UNIQUEMENT en JSON valide avec cette structure :
{{
  "hook": "Accroche (3 premières secondes — ce qui stoppe le scroll)",
  "script": "Script complet structuré selon le template — mot à mot, slot par slot",
  "subtitles": ["sous-titre ligne 1", "sous-titre ligne 2", "..."],
  "visuals": "Description précise des plans / visuels à filmer ou à insérer dans Remotion",
  "cta": "Call-to-action final",
  "caption": "Légende complète du post avec emojis",
  "hashtags": ["#hashtag1", "#hashtag2"],
  "remotion_notes": "Notes spécifiques pour configurer le template Remotion (textes des slots, couleurs, musique suggérée…)"
}}"""

    client = genai.Client(api_key=GOOGLE_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=gtypes.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.8,
        ),
    )
    raw = response.text.strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


@app.post("/api/video-script")
async def api_video_script(request: Request):
    body = await request.json()
    topic    = body.get("topic", "")
    platform = body.get("platform", "facebook")
    duration = body.get("duration", "30-60 secondes")
    template = body.get("template", "")
    remotion = body.get("remotion", "")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor, _generate_video_script_sync, topic, platform, duration, template, remotion
    )
    return result


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "store": STORE_NAME}


# ─── Planificateur automatique ───────────────────────────────────────────────

def _scheduled_job():
    if _agent_state["status"] == "running":
        return
    logger.info("=== Routine automatique déclenchée ===")
    _executor.submit(_run_agent_sync, "Routine marketing quotidienne automatique")

_scheduler = BackgroundScheduler(timezone="Europe/Paris")
_scheduler.add_job(
    _scheduled_job,
    CronTrigger(hour=POSTING_HOUR, minute=POSTING_MINUTE, timezone="Europe/Paris"),
    id="routine_quotidienne",
    replace_existing=True,
)
_scheduler.start()
logger.info("Planificateur démarré — routine automatique à %02d:%02d", POSTING_HOUR, POSTING_MINUTE)


# ─── Entrée ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
