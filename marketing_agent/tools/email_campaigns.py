"""Gestion des campagnes email via SendGrid."""
import json
import requests
from config import SENDGRID_API_KEY, EMAIL_FROM, EMAIL_LIST_ID, STORE_NAME


def _sendgrid_post(endpoint: str, payload: dict) -> dict:
    if not SENDGRID_API_KEY:
        return {"status": "skipped", "reason": "SendGrid non configuré"}
    url = f"https://api.sendgrid.com/v3/{endpoint}"
    headers = {"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"}
    r = requests.post(url, json=payload, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json() if r.content else {"status": "sent"}


def send_newsletter(subject: str, html_body: str, plain_body: str = "") -> dict:
    """Envoie une newsletter à toute la liste d'abonnés."""
    if not EMAIL_FROM or not EMAIL_LIST_ID:
        print(f"[SIMULATION EMAIL] Sujet: {subject}\n{plain_body or html_body[:300]}")
        return {"status": "simulated"}

    payload = {
        "name": f"Newsletter - {subject}",
        "subject": subject,
        "email_config": {
            "subject": subject,
            "html_content": html_body,
            "plain_content": plain_body or "",
            "generate_plain_content": not plain_body,
            "sender_id": EMAIL_FROM,
        },
        "list_ids": [EMAIL_LIST_ID],
        "status": "scheduled",
    }
    result = _sendgrid_post("marketing/singlesends", payload)
    # Envoyer immédiatement
    if result.get("id"):
        _sendgrid_post(f"marketing/singlesends/{result['id']}/schedule", {"send_at": "now"})
    return {"status": "sent", "newsletter_id": result.get("id")}


def send_abandoned_cart_email(customer_email: str, customer_name: str, cart_items: list, cart_url: str) -> dict:
    """Email de relance panier abandonné."""
    items_html = "".join(f"<li>{item}</li>" for item in cart_items)
    html = f"""
    <p>Bonjour {customer_name},</p>
    <p>Vous avez laissé des articles dans votre panier chez <strong>{STORE_NAME}</strong> !</p>
    <ul>{items_html}</ul>
    <p><a href="{cart_url}" style="background:#000;color:#fff;padding:12px 24px;text-decoration:none;border-radius:4px;">
       Finaliser ma commande
    </a></p>
    <p>À bientôt !</p>
    """
    payload = {
        "personalizations": [{"to": [{"email": customer_email, "name": customer_name}]}],
        "from": {"email": EMAIL_FROM, "name": STORE_NAME},
        "subject": f"{customer_name}, votre panier vous attend ! 🛒",
        "content": [{"type": "text/html", "value": html}],
    }
    return _sendgrid_post("mail/send", payload)


def send_promotional_email(customer_email: str, customer_name: str, subject: str, html_content: str) -> dict:
    """Email promotionnel personnalisé."""
    payload = {
        "personalizations": [{"to": [{"email": customer_email, "name": customer_name}]}],
        "from": {"email": EMAIL_FROM, "name": STORE_NAME},
        "subject": subject,
        "content": [{"type": "text/html", "value": html_content}],
    }
    return _sendgrid_post("mail/send", payload)
