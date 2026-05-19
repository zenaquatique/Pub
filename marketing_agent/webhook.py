"""Serveur FastAPI — reçoit les webhooks Meta (Instagram/Facebook) et les stocke."""
import hashlib
import hmac
import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from config import META_WEBHOOK_VERIFY_TOKEN, META_APP_SECRET
from tools.customer import log_customer_message

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Marketing Agent Webhook", version="1.0")


# ─── Vérification de la signature Meta ────────────────────────────────────────

def _verify_meta_signature(payload: bytes, signature_header: str) -> bool:
    """Vérifie la signature X-Hub-Signature-256 de Meta."""
    if not META_APP_SECRET:
        return True  # mode développement sans secret configuré
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(META_APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


# ─── Endpoint de vérification (challenge handshake) ───────────────────────────

@app.get("/webhook")
async def verify_webhook(request: Request) -> PlainTextResponse:
    """Meta envoie un GET pour vérifier le webhook lors de l'inscription."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == META_WEBHOOK_VERIFY_TOKEN:
        logger.info("Webhook vérifié avec succès.")
        return PlainTextResponse(challenge)

    raise HTTPException(status_code=403, detail="Vérification échouée")


# ─── Endpoint de réception des événements ────────────────────────────────────

@app.post("/webhook")
async def receive_webhook(request: Request) -> dict:
    """Reçoit les événements Meta (messages, commentaires) et les enregistre."""
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")

    if not _verify_meta_signature(body, signature):
        raise HTTPException(status_code=401, detail="Signature invalide")

    data: dict[str, Any] = await request.json()
    object_type = data.get("object", "")

    for entry in data.get("entry", []):
        entry_id = entry.get("id", "unknown")

        # — Messagerie Instagram / Facebook Messenger
        for messaging in entry.get("messaging", []):
            sender_id = messaging.get("sender", {}).get("id", "unknown")
            message_obj = messaging.get("message", {})
            text = message_obj.get("text", "")
            message_id = message_obj.get("mid", f"msg_{sender_id}_{entry_id}")

            if text:
                platform = "instagram" if object_type == "instagram" else "facebook"
                log_customer_message(
                    platform=platform,
                    sender_name=sender_id,
                    message=text,
                    message_id=message_id,
                )
                logger.info("Message %s enregistré depuis %s", message_id, platform)

        # — Commentaires Instagram
        for change in entry.get("changes", []):
            value = change.get("value", {})
            comment_id = value.get("id")
            text = value.get("text", "")
            sender = value.get("from", {}).get("name", "Utilisateur")

            if comment_id and text:
                platform = "instagram" if object_type == "instagram" else "facebook"
                log_customer_message(
                    platform=platform,
                    sender_name=sender,
                    message=text,
                    message_id=comment_id,
                )
                logger.info("Commentaire %s enregistré depuis %s", comment_id, platform)

    return {"status": "ok"}


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict:
    return {"status": "healthy"}


# ─── Point d'entrée ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
