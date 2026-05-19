"""Agent marketing autonome — cerveau central alimenté par Gemini."""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from config import (
    GOOGLE_API_KEY, GEMINI_MODEL, STORE_NAME,
    STORE_NICHE, BRAND_VOICE, TARGET_AUDIENCE,
    SHOPIFY_SHOP_URL, OBSIDIAN_VAULT_PATH, VIDEO_ASSETS_PATH,
)
from tools import shopify, social, email_campaigns, customer
from tools.knowledge import (
    read_obsidian_vault, list_video_assets, write_calendar_file,
    read_agent_memory, append_agent_memory,
)
from tools.remotion import render_video, list_rendered_videos, update_post_props, extract_post_props

logger = logging.getLogger(__name__)

PENDING_ACTIONS_FILE = Path(__file__).parent / "data" / "pending_actions.json"

WRITE_TOOLS = {
    "post_to_instagram",
    "post_to_facebook",
    "send_newsletter",
    "update_product_description",
    "reply_to_customer",
    "send_abandoned_cart_email",
}

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
            types.FunctionDeclaration(
                name="get_brand_knowledge",
                description=(
                    "Relit la vault Obsidian et le dossier d'assets vidéo pour rafraîchir "
                    "le contexte de marque, les instructions et les ressources disponibles."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="render_video",
                description=(
                    "Lance le rendu d'une vidéo Remotion. "
                    "L'ID de composition suit le format YYYYMMDD (ex: '20260519' pour le 19 mai 2026). "
                    "Tous les posts du mois sont déjà définis dans Root.tsx avec leur contenu. "
                    "Cette commande génère le fichier MP4 directement dans le dossier out/ du projet."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "composition_id": types.Schema(
                            type=types.Type.STRING,
                            description="ID Remotion de la composition (format YYYYMMDD, ex: '20260519')",
                        ),
                        "output_filename": types.Schema(
                            type=types.Type.STRING,
                            description="Nom du fichier MP4 de sortie (optionnel, défaut: <composition_id>.mp4)",
                        ),
                    },
                    required=["composition_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="list_rendered_videos",
                description="Liste les vidéos MP4 déjà rendues dans le dossier out/ du projet Remotion.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={},
                ),
            ),
            types.FunctionDeclaration(
                name="save_to_memory",
                description=(
                    "Enregistre une note importante dans ta mémoire persistante (vault Obsidian). "
                    "Utilise dès que l'utilisateur exprime une préférence, une instruction récurrente, "
                    "un retour sur un contenu, ou toute information à retenir pour les prochaines sessions. "
                    "Exemples : préférences de format, sujets à éviter, ton souhaité, feedback sur des vidéos."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "note": types.Schema(
                            type=types.Type.STRING,
                            description="Note claire et concise à mémoriser (instruction, préférence, feedback)",
                        ),
                    },
                    required=["note"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_post_props",
                description=(
                    "Lit les props actuelles d'un post Remotion dans Root.tsx "
                    "(hookText, leftItems, rightItems, verdict, tips, plants, etc.). "
                    "À appeler avant de modifier un post pour voir son contenu actuel."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "composition_id": types.Schema(
                            type=types.Type.STRING,
                            description="ID du post au format YYYYMMDD (ex: '20260519')",
                        ),
                    },
                    required=["composition_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="update_post_props",
                description=(
                    "Modifie des champs d'un post Remotion dans Root.tsx. "
                    "Permet de corriger hookText, verdict, leftItems, rightItems, tips, plants, ctaText, etc. "
                    "Appelle render_video ensuite pour regénérer la vidéo avec le nouveau contenu."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "composition_id": types.Schema(
                            type=types.Type.STRING,
                            description="ID du post au format YYYYMMDD (ex: '20260519')",
                        ),
                        "updates": types.Schema(
                            type=types.Type.OBJECT,
                            description=(
                                "Champs à modifier. Clés = noms des props TypeScript. "
                                "Ex: {\"hookText\": \"Nouveau texte\", \"verdict\": \"Nouveau verdict\"} "
                                "ou {\"leftItems\": [\"item1\", \"item2\", \"item3\"]}"
                            ),
                        ),
                    },
                    required=["composition_id", "updates"],
                ),
            ),
            types.FunctionDeclaration(
                name="write_calendar_file",
                description=(
                    "Crée ou met à jour un fichier markdown de calendrier éditorial dans la vault Obsidian. "
                    "Utilise pour planifier un nouveau mois de contenu. "
                    "Le fichier est écrit directement dans le dossier Calendrier Publication."
                ),
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "filename": types.Schema(
                            type=types.Type.STRING,
                            description="Nom du fichier (ex: 'juin-2026.md')",
                        ),
                        "content": types.Schema(
                            type=types.Type.STRING,
                            description="Contenu markdown complet du calendrier éditorial",
                        ),
                    },
                    required=["filename", "content"],
                ),
            ),
        ]
    )
]

# ─── Gestion des actions en attente ──────────────────────────────────────────

def _load_pending_actions() -> list:
    PENDING_ACTIONS_FILE.parent.mkdir(exist_ok=True)
    if PENDING_ACTIONS_FILE.exists():
        try:
            return json.loads(PENDING_ACTIONS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            PENDING_ACTIONS_FILE.unlink(missing_ok=True)
    return []


def _queue_action(name: str, inputs: dict) -> dict:
    actions = _load_pending_actions()
    action_id = str(uuid.uuid4())
    action = {
        "id": action_id,
        "tool": name,
        "inputs": inputs,
        "created_at": datetime.now().isoformat(),
        "status": "pending",
    }
    actions.append(action)
    PENDING_ACTIONS_FILE.write_text(
        json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Action mise en attente : %s | id=%s", name, action_id)
    return {
        "status": "queued",
        "message": "Action mise en attente pour approbation.",
        "id": action_id,
    }


def execute_pending_action(action_id: str) -> dict:
    actions = _load_pending_actions()
    for action in actions:
        if action["id"] == action_id:
            result = _execute_tool_directly(action["tool"], action["inputs"])
            action["status"] = "executed"
            action["executed_at"] = datetime.now().isoformat()
            PENDING_ACTIONS_FILE.write_text(
                json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return result
    return {"error": f"Action introuvable : {action_id}"}


# ─── Exécution des outils ─────────────────────────────────────────────────────

def _execute_tool_directly(name: str, inputs: dict) -> Any:
    """Execute a tool without going through the approval queue."""
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

    if name == "get_brand_knowledge":
        vault_content = read_obsidian_vault(OBSIDIAN_VAULT_PATH)
        assets = list_video_assets(VIDEO_ASSETS_PATH)
        return {
            "vault_content": vault_content or "Vault non trouvée ou vide.",
            "video_assets": assets,
            "vault_path": OBSIDIAN_VAULT_PATH,
            "assets_path": VIDEO_ASSETS_PATH,
        }

    if name == "render_video":
        return render_video(
            inputs["composition_id"],
            VIDEO_ASSETS_PATH,
            inputs.get("output_filename", ""),
        )

    if name == "list_rendered_videos":
        return list_rendered_videos(VIDEO_ASSETS_PATH)

    if name == "save_to_memory":
        return append_agent_memory(OBSIDIAN_VAULT_PATH, inputs["note"])

    if name == "get_post_props":
        return extract_post_props(inputs["composition_id"], VIDEO_ASSETS_PATH)

    if name == "update_post_props":
        return update_post_props(inputs["composition_id"], VIDEO_ASSETS_PATH, inputs["updates"])

    if name == "write_calendar_file":
        return write_calendar_file(
            OBSIDIAN_VAULT_PATH,
            inputs["filename"],
            inputs["content"],
        )

    return {"error": f"Outil inconnu: {name}"}


def execute_tool(name: str, inputs: dict) -> Any:
    logger.info("Exécution de l'outil: %s | inputs: %s", name, inputs)

    if name in WRITE_TOOLS:
        return _queue_action(name, inputs)

    return _execute_tool_directly(name, inputs)


# ─── Prompt système ───────────────────────────────────────────────────────────

def build_system_prompt() -> str:
    today = datetime.now().strftime("%A %d %B %Y")

    vault_content = read_obsidian_vault(OBSIDIAN_VAULT_PATH)
    assets = list_video_assets(VIDEO_ASSETS_PATH)
    memory = read_agent_memory(OBSIDIAN_VAULT_PATH)

    memory_section = ""
    if memory:
        memory_section = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MÉMOIRE PERSISTANTE — CE QUE TU AS APPRIS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{memory}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ces informations proviennent de tes sessions précédentes.
RESPECTE-LES EN PRIORITÉ dans toutes tes actions.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    vault_section = ""
    if vault_content:
        vault_section = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VAULT OBSIDIAN — CONNAISSANCES DE LA MARQUE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{vault_content}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    assets_section = ""
    if assets:
        lines = "\n".join(
            f"  - [{a['type'].upper()}] {a['name']}  ({a['size_kb']} KB)  → {a['path']}"
            for a in assets
        )
        assets_section = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASSETS VIDÉO / IMAGES DISPONIBLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{lines}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    return f"""Tu es l'agent marketing IA de "{STORE_NAME}" ({STORE_NICHE}).
Voix de marque : {BRAND_VOICE} | Cible : {TARGET_AUDIENCE}
Boutique : https://{SHOPIFY_SHOP_URL} | Aujourd'hui : {today}
{memory_section}{vault_section}{assets_section}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLES DE COMPORTEMENT — OBLIGATOIRES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Réponds TOUJOURS en "tu" — JAMAIS "vous"
• Sois COURT : 1 à 3 phrases après avoir agi, pas de listes inutiles
• N'affiche JAMAIS le script voix off dans le chat — modifie Root.tsx et rends la vidéo
• N'ATTENDS PAS de confirmation — si on te dit de faire quelque chose, FAIS-LE directement
• Ne reviens JAMAIS à la routine complète si l'utilisateur donne une tâche précise

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DEUX MODES — RESPECTE-LES À LA LETTRE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MODE TÂCHE PRÉCISE (priorité absolue) :
Si le message contient une instruction spécifique → fais UNIQUEMENT ça, puis réponds en 1-2 phrases.
Exemples :
  • "change X dans le post du 19 mai" → get_post_props → update_post_props → render_video → "✅ Fait !"
  • "les plantes ne meurent pas en 2 semaines" → update_post_props pour corriger → render_video → "✅ Corrigé et vidéo regénérée"
  • "prépare juin" → write_calendar_file → "✅ Calendrier juin créé dans la vault"
  • Toute correction de prix, ton, contenu → applique directement sans commenter le script

MODE ROUTINE (uniquement si le message est vide ou dit explicitement "lance la routine") :
  1. get_store_analytics + get_products
  2. post_to_instagram + post_to_facebook (1 post chacun)
  3. get_pending_customer_messages → reply si messages en attente
  4. render_video pour la vidéo du jour (ID = YYYYMMDD d'aujourd'hui)
  5. Rapport final en 5 lignes max

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VIDÉO REMOTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Projet : {VIDEO_ASSETS_PATH}
• ID composition : YYYYMMDD (ex: "20260519" = 19 mai 2026)
• Modification d'un post : get_post_props → update_post_props → render_video (dans cet ordre, sans pause)
• Ne génère pas de script texte — modifie Root.tsx et rends la vidéo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CALENDRIER ÉDITORIAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Créer un mois : get_brand_knowledge pour voir le format, puis write_calendar_file
• Format : | Jour | Date | Template | Plateformes | Sujet | ID |
• ID = YYYYMMDD | lundi→samedi | formats : VersusVideo, EducatifVideo, PromoVideo, TikTokOrganic, ConceptVideo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MÉMOIRE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Feedback, correction, préférence → save_to_memory IMMÉDIATEMENT (avant de répondre)
• Ne jamais répéter une erreur déjà mémorisée

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PUBLICATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Instagram, Facebook, newsletter, descriptions produits → mis en attente d'approbation humaine
• Rendu vidéo, modification Root.tsx, calendrier → exécution directe immédiate"""


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

        # Defensive access — Gemini can return None candidates or parts
        try:
            parts = response.candidates[0].content.parts or []
        except (AttributeError, IndexError, TypeError):
            logger.warning("Réponse invalide à l'itération %d", iteration)
            break

        function_calls = [
            part.function_call
            for part in parts
            if getattr(part, "function_call", None)
        ]

        if not function_calls:
            final_text = "".join(
                part.text
                for part in parts
                if getattr(part, "text", None)
            )
            logger.info("=== Session terminée après %d tours ===", iteration)
            return final_text or "(aucune réponse)"

        # Execute every tool called in this turn
        for fc in function_calls:
            try:
                args = dict(fc.args) if fc.args is not None else {}
                tool_result = execute_tool(fc.name, args)
            except Exception as exc:
                logger.warning("Outil %s échoué : %s", fc.name, exc)
                tool_result = {"status": "error", "reason": str(exc)}
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
