"""Gestion des réponses clients (messages, commentaires)."""
import json
from datetime import datetime
from pathlib import Path

# Stockage local simple des interactions
INTERACTIONS_FILE = Path(__file__).parent.parent / "data" / "interactions.json"


def _load_interactions() -> list:
    INTERACTIONS_FILE.parent.mkdir(exist_ok=True)
    if INTERACTIONS_FILE.exists():
        return json.loads(INTERACTIONS_FILE.read_text())
    return []


def _save_interactions(data: list) -> None:
    INTERACTIONS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def get_pending_messages() -> list[dict]:
    """Retourne les messages clients en attente de réponse."""
    interactions = _load_interactions()
    return [i for i in interactions if i.get("status") == "pending"]


def log_customer_message(platform: str, sender_name: str, message: str, message_id: str = None) -> dict:
    """Enregistre un nouveau message client."""
    interactions = _load_interactions()
    entry = {
        "id": message_id or f"{platform}_{datetime.now().timestamp()}",
        "platform": platform,
        "sender": sender_name,
        "message": message,
        "received_at": datetime.now().isoformat(),
        "status": "pending",
        "response": None,
    }
    interactions.append(entry)
    _save_interactions(interactions)
    return entry


def mark_replied(message_id: str, response_text: str) -> None:
    """Marque un message comme traité avec la réponse envoyée."""
    interactions = _load_interactions()
    for item in interactions:
        if item["id"] == message_id:
            item["status"] = "replied"
            item["response"] = response_text
            item["replied_at"] = datetime.now().isoformat()
            break
    _save_interactions(interactions)


def send_instagram_reply(comment_id: str, reply_text: str) -> dict:
    """Répond à un commentaire Instagram via l'API Meta."""
    from config import META_ACCESS_TOKEN
    import requests

    if not META_ACCESS_TOKEN:
        print(f"[SIMULATION REPLY Instagram] {reply_text}")
        return {"status": "simulated"}

    url = f"https://graph.facebook.com/v19.0/{comment_id}/replies"
    r = requests.post(url, data={"message": reply_text, "access_token": META_ACCESS_TOKEN}, timeout=15)
    r.raise_for_status()
    return {"status": "sent", "reply_id": r.json().get("id")}


def send_facebook_reply(comment_id: str, reply_text: str) -> dict:
    """Répond à un commentaire Facebook."""
    from config import META_ACCESS_TOKEN
    import requests

    if not META_ACCESS_TOKEN:
        print(f"[SIMULATION REPLY Facebook] {reply_text}")
        return {"status": "simulated"}

    url = f"https://graph.facebook.com/v19.0/{comment_id}/comments"
    r = requests.post(url, data={"message": reply_text, "access_token": META_ACCESS_TOKEN}, timeout=15)
    r.raise_for_status()
    return {"status": "sent", "reply_id": r.json().get("id")}
