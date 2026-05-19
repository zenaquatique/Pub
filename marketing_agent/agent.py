"""Agent marketing autonome — cerveau central alimenté par Claude."""
import json
import logging
from datetime import datetime
from typing import Any

import anthropic

from config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL, STORE_NAME,
    STORE_NICHE, BRAND_VOICE, TARGET_AUDIENCE,
    SHOPIFY_SHOP_URL,
)
from tools import shopify, social, email_campaigns, customer

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ─── Définitions des outils ───────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "get_store_analytics",
        "description": "Récupère les statistiques actuelles de la boutique Shopify : commandes, chiffre d'affaires, produits populaires, stock faible.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_products",
        "description": "Récupère la liste des produits actifs de la boutique avec prix, stock et images.",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "description": "Nombre de produits à récupérer (défaut 20)"}},
            "required": [],
        },
    },
    {
        "name": "update_product_description",
        "description": "Met à jour la description HTML d'un produit Shopify pour améliorer le SEO et la conversion.",
        "input_schema": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer", "description": "ID Shopify du produit"},
                "new_description": {"type": "string", "description": "Nouvelle description en HTML"},
            },
            "required": ["product_id", "new_description"],
        },
    },
    {
        "name": "post_to_instagram",
        "description": "Publie un post sur Instagram avec une image et une légende.",
        "input_schema": {
            "type": "object",
            "properties": {
                "caption": {"type": "string", "description": "Légende du post (avec hashtags)"},
                "image_url": {"type": "string", "description": "URL publique de l'image"},
            },
            "required": ["caption", "image_url"],
        },
    },
    {
        "name": "post_to_facebook",
        "description": "Publie un post sur la Page Facebook de la boutique.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Texte du post"},
                "link": {"type": "string", "description": "URL à partager (optionnel)"},
                "image_url": {"type": "string", "description": "URL de l'image (optionnel)"},
            },
            "required": ["message"],
        },
    },
    {
        "name": "send_newsletter",
        "description": "Envoie une newsletter à tous les abonnés email de la boutique.",
        "input_schema": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "Objet de l'email"},
                "html_body": {"type": "string", "description": "Corps de l'email en HTML"},
                "plain_body": {"type": "string", "description": "Version texte brut (optionnel)"},
            },
            "required": ["subject", "html_body"],
        },
    },
    {
        "name": "get_pending_customer_messages",
        "description": "Récupère les messages et commentaires clients en attente de réponse.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "reply_to_customer",
        "description": "Répond à un message ou commentaire client sur Instagram ou Facebook.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "ID du message client"},
                "platform": {"type": "string", "enum": ["instagram", "facebook"], "description": "Plateforme"},
                "reply_text": {"type": "string", "description": "Réponse à envoyer"},
            },
            "required": ["message_id", "platform", "reply_text"],
        },
    },
    {
        "name": "send_abandoned_cart_email",
        "description": "Envoie un email de relance à un client qui a abandonné son panier.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_email": {"type": "string"},
                "customer_name": {"type": "string"},
                "cart_items": {"type": "array", "items": {"type": "string"}, "description": "Liste des articles du panier"},
                "cart_url": {"type": "string", "description": "URL du panier"},
            },
            "required": ["customer_email", "customer_name", "cart_items", "cart_url"],
        },
    },
]

# ─── Exécution des outils ─────────────────────────────────────────────────────

def execute_tool(name: str, inputs: dict) -> Any:
    logger.info("Exécution de l'outil: %s | inputs: %s", name, inputs)

    if name == "get_store_analytics":
        return shopify.get_store_analytics()

    if name == "get_products":
        return shopify.get_products(limit=inputs.get("limit", 20))

    if name == "update_product_description":
        return shopify.update_product_description(
            inputs["product_id"], inputs["new_description"]
        )

    if name == "post_to_instagram":
        return social.post_to_instagram(inputs["caption"], inputs["image_url"])

    if name == "post_to_facebook":
        return social.post_to_facebook(
            inputs["message"],
            link=inputs.get("link"),
            image_url=inputs.get("image_url"),
        )

    if name == "send_newsletter":
        return email_campaigns.send_newsletter(
            inputs["subject"],
            inputs["html_body"],
            plain_body=inputs.get("plain_body", ""),
        )

    if name == "get_pending_customer_messages":
        return customer.get_pending_messages()

    if name == "reply_to_customer":
        message_id = inputs["message_id"]
        platform = inputs["platform"]
        reply = inputs["reply_text"]
        if platform == "instagram":
            result = customer.send_instagram_reply(message_id, reply)
        else:
            result = customer.send_facebook_reply(message_id, reply)
        customer.mark_replied(message_id, reply)
        return result

    if name == "send_abandoned_cart_email":
        return email_campaigns.send_abandoned_cart_email(
            inputs["customer_email"],
            inputs["customer_name"],
            inputs["cart_items"],
            inputs["cart_url"],
        )

    return {"error": f"Outil inconnu: {name}"}


# ─── Prompt système ───────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    today = datetime.now().strftime("%A %d %B %Y")
    return f"""Tu es l'agent marketing IA autonome de la boutique e-commerce "{STORE_NAME}".
Niche : {STORE_NICHE}
Voix de marque : {BRAND_VOICE}
Cible : {TARGET_AUDIENCE}
URL boutique : https://{SHOPIFY_SHOP_URL}
Date d'aujourd'hui : {today}

TON RÔLE : Gérer 99 % du marketing de façon autonome, sans intervention humaine.

PROCESSUS À SUIVRE À CHAQUE EXÉCUTION :
1. Récupère les analytics et les produits de la boutique
2. Analyse les données : qu'est-ce qui se vend bien ? Quoi mettre en avant ?
3. Publie 1 post Instagram et 1 post Facebook (produit star ou actualité boutique)
4. Vérifie les messages clients en attente → réponds-y avec empathie et professionnalisme
5. Si du stock est faible sur un produit populaire, crée un email de newsletter d'urgence
6. Améliore les descriptions des produits qui n'en ont pas ou peu
7. Propose un email newsletter hebdomadaire si c'est lundi

RÈGLES :
- Adapte le ton à la marque : {BRAND_VOICE}
- Les posts sociaux doivent être engageants, avec des emojis pertinents et des hashtags
- Les réponses clients sont chaleureuses, rapides, et orientées solution
- Ne publie JAMAIS de fausses informations sur les produits
- Si tu ne trouves pas d'image pour un post, utilise l'image du produit Shopify
- Fais toujours les actions dans l'ordre logique : données → contenu → publication

Commence maintenant par collecter les données de la boutique."""


# ─── Boucle agent principale ──────────────────────────────────────────────────

def run_marketing_session(task: str = None) -> str:
    """Lance une session marketing complète. Retourne le rapport final."""
    system_prompt = build_system_prompt()
    user_message = task or "Lance la routine marketing quotidienne complète."

    messages: list[dict] = [{"role": "user", "content": user_message}]

    logger.info("=== Démarrage session marketing | %s ===", datetime.now().isoformat())

    iteration = 0
    max_iterations = 20  # sécurité anti-boucle infinie

    while iteration < max_iterations:
        iteration += 1

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=8192,
            thinking={"type": "adaptive"},
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        logger.info("Tour %d | stop_reason: %s | blocs: %d", iteration, response.stop_reason, len(response.content))

        # Ajouter la réponse assistant à l'historique
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            # Extraire le texte final du rapport
            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text
            logger.info("=== Session terminée après %d tours ===", iteration)
            return final_text

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })
            messages.append({"role": "user", "content": tool_results})

        elif response.stop_reason == "pause_turn":
            # Continuer la session
            messages.append({"role": "user", "content": [{"type": "text", "text": "Continue."}]})

        else:
            logger.warning("stop_reason inattendu: %s", response.stop_reason)
            break

    logger.warning("Limite d'itérations atteinte (%d)", max_iterations)
    return "Session interrompue : limite d'itérations atteinte."


# ─── Point d'entrée direct ────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    rapport = run_marketing_session()
    print("\n" + "=" * 60)
    print("RAPPORT MARKETING")
    print("=" * 60)
    print(rapport)
