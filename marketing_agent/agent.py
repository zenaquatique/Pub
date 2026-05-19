"""Agent marketing autonome — cerveau central alimenté par Gemini."""
import json
import logging
from datetime import datetime
from typing import Any

from google import genai
from google.genai import types

from config import (
    GOOGLE_API_KEY, GEMINI_MODEL, STORE_NAME,
    STORE_NICHE, BRAND_VOICE, TARGET_AUDIENCE,
    SHOPIFY_SHOP_URL,
)
from tools import shopify, social, email_campaigns, customer

logger = logging.getLogger(__name__)

client = genai.Client(api_key=GOOGLE_API_KEY)

# ─── Définitions des outils ───────────────────────────────────────────────────

TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_store_analytics",
                description="Récupère les statistiques actuelles de la boutique Shopify : commandes, chiffre d'affaires, produits populaires, stock faible.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="get_products",
                description="Récupère la liste des produits actifs de la boutique avec prix, stock et images.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "limit": types.Schema(
                            type=types.Type.INTEGER,
                            description="Nombre de produits à récupérer (défaut 20)",
                        ),
                    },
                ),
            ),
            types.FunctionDeclaration(
                name="update_product_description",
                description="Met à jour la description HTML d'un produit Shopify pour améliorer le SEO et la conversion.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "product_id": types.Schema(
                            type=types.Type.INTEGER,
                            description="ID Shopify du produit",
                        ),
                        "new_description": types.Schema(
                            type=types.Type.STRING,
                            description="Nouvelle description en HTML",
                        ),
                    },
                    required=["product_id", "new_description"],
                ),
            ),
            types.FunctionDeclaration(
                name="post_to_instagram",
                description="Publie un post sur Instagram avec une image et une légende.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "caption": types.Schema(
                            type=types.Type.STRING,
                            description="Légende du post (avec hashtags)",
                        ),
                        "image_url": types.Schema(
                            type=types.Type.STRING,
                            description="URL publique de l'image",
                        ),
                    },
                    required=["caption", "image_url"],
                ),
            ),
            types.FunctionDeclaration(
                name="post_to_facebook",
                description="Publie un post sur la Page Facebook de la boutique.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "message": types.Schema(
                            type=types.Type.STRING,
                            description="Texte du post",
                        ),
                        "link": types.Schema(
                            type=types.Type.STRING,
                            description="URL à partager (optionnel)",
                        ),
                        "image_url": types.Schema(
                            type=types.Type.STRING,
                            description="URL de l'image (optionnel)",
                        ),
                    },
                    required=["message"],
                ),
            ),
            types.FunctionDeclaration(
                name="send_newsletter",
                description="Envoie une newsletter à tous les abonnés email de la boutique.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "subject": types.Schema(
                            type=types.Type.STRING,
                            description="Objet de l'email",
                        ),
                        "html_body": types.Schema(
                            type=types.Type.STRING,
                            description="Corps de l'email en HTML",
                        ),
                        "plain_body": types.Schema(
                            type=types.Type.STRING,
                            description="Version texte brut (optionnel)",
                        ),
                    },
                    required=["subject", "html_body"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_pending_customer_messages",
                description="Récupère les messages et commentaires clients en attente de réponse.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="reply_to_customer",
                description="Répond à un message ou commentaire client sur Instagram ou Facebook.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "message_id": types.Schema(
                            type=types.Type.STRING,
                            description="ID du message client",
                        ),
                        "platform": types.Schema(
                            type=types.Type.STRING,
                            description="Plateforme (instagram ou facebook)",
                        ),
                        "reply_text": types.Schema(
                            type=types.Type.STRING,
                            description="Réponse à envoyer",
                        ),
                    },
                    required=["message_id", "platform", "reply_text"],
                ),
            ),
            types.FunctionDeclaration(
                name="send_abandoned_cart_email",
                description="Envoie un email de relance à un client qui a abandonné son panier.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "customer_email": types.Schema(
                            type=types.Type.STRING,
                        ),
                        "customer_name": types.Schema(
                            type=types.Type.STRING,
                        ),
                        "cart_items": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(type=types.Type.STRING),
                            description="Liste des articles du panier",
                        ),
                        "cart_url": types.Schema(
                            type=types.Type.STRING,
                            description="URL du panier",
                        ),
                    },
                    required=["customer_email", "customer_name", "cart_items", "cart_url"],
                ),
            ),
        ]
    )
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

    logger.info("=== Démarrage session marketing | %s ===", datetime.now().isoformat())

    chat = client.chats.create(
        model=GEMINI_MODEL,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            tools=TOOLS,
        ),
    )

    response = chat.send_message(user_message)

    iteration = 0
    max_iterations = 20  # sécurité anti-boucle infinie

    while iteration < max_iterations:
        iteration += 1
        logger.info("Tour %d", iteration)

        # Collect any function calls in this response
        function_calls = [
            part.function_call
            for part in response.candidates[0].content.parts
            if part.function_call
        ]

        if not function_calls:
            # No tool calls — the model is done; extract final text
            final_text = "".join(
                part.text
                for part in response.candidates[0].content.parts
                if hasattr(part, "text")
            )
            logger.info("=== Session terminée après %d tours ===", iteration)
            return final_text

        # Execute every tool called in this turn, one response per call
        for fc in function_calls:
            try:
                tool_result = execute_tool(fc.name, dict(fc.args))
            except Exception as exc:
                logger.warning("Outil %s échoué : %s", fc.name, exc)
                tool_result = {"status": "skipped", "reason": str(exc)}
            response = chat.send_message(
                types.Part.from_function_response(
                    name=fc.name,
                    response={"result": json.dumps(tool_result, ensure_ascii=False, default=str)},
                )
            )

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
