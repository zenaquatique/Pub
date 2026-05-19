"""Tableau de bord web — contrôle complet de l'agent marketing."""
import asyncio
import hashlib
import hmac
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import META_APP_SECRET, META_WEBHOOK_VERIFY_TOKEN, STORE_NAME
from tools.customer import (
    get_pending_messages,
    log_customer_message,
    mark_replied,
    send_facebook_reply,
    send_instagram_reply,
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
        return json.loads(REPORTS_FILE.read_text())
    return []


def _save_report(report: str, task: str = "") -> None:
    reports = _load_reports()
    reports.insert(0, {
        "id": str(datetime.now().timestamp()),
        "date": datetime.now().isoformat(),
        "task": task or "Routine quotidienne",
        "report": report,
    })
    REPORTS_FILE.write_text(json.dumps(reports[:50], ensure_ascii=False, indent=2))


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
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "store_name": STORE_NAME,
    })


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
async def api_analytics():
    try:
        return get_store_analytics()
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
    REPORTS_FILE.write_text(json.dumps(reports, ensure_ascii=False, indent=2))
    return {"status": "deleted"}


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


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "store": STORE_NAME}


# ─── Entrée ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
