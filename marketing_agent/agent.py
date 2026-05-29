"""Agent marketing autonome — alimenté par Groq (llama-3.3-70b-versatile)."""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from config import (
    GROQ_API_KEY, GROQ_MODEL, STORE_NAME,
    STORE_NICHE, BRAND_VOICE, TARGET_AUDIENCE,
    SHOPIFY_SHOP_URL, OBSIDIAN_VAULT_PATH, VIDEO_ASSETS_PATH,
    CONTENT_RULES, ANTHROPIC_API_KEY, CLAUDE_SCRIPT_MODEL,
    OPENAI_API_KEY, OPENAI_MODEL,
)
from tools import shopify, social, email_campaigns, customer
from tools.knowledge import (
    read_obsidian_vault, list_video_assets, write_calendar_file,
    read_agent_memory, append_agent_memory,
)
from tools.remotion import render_video, list_rendered_videos, update_post_props, extract_post_props, create_post_composition

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

# ─── Définitions des outils (format OpenAI/Groq) ─────────────────────────────

TOOLS_GROQ = [
    {
        "type": "function",
        "function": {
            "name": "get_store_analytics",
            "description": "Récupère les statistiques actuelles de la boutique Shopify : commandes, chiffre d'affaires, produits populaires, stock faible.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_products",
            "description": "Récupère la liste des produits actifs de la boutique avec prix, stock et images.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Nombre de produits à récupérer (défaut 20)"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_product_description",
            "description": "Met à jour la description HTML d'un produit Shopify pour améliorer le SEO et la conversion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer", "description": "ID Shopify du produit"},
                    "new_description": {"type": "string", "description": "Nouvelle description en HTML"},
                },
                "required": ["product_id", "new_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "post_to_instagram",
            "description": "Publie un post sur Instagram avec une image et une légende.",
            "parameters": {
                "type": "object",
                "properties": {
                    "caption": {"type": "string", "description": "Légende du post (avec hashtags)"},
                    "image_url": {"type": "string", "description": "URL publique de l'image"},
                },
                "required": ["caption", "image_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "post_to_facebook",
            "description": "Publie un post sur la Page Facebook de la boutique.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Texte du post"},
                    "link": {"type": "string", "description": "URL à partager (optionnel)"},
                    "image_url": {"type": "string", "description": "URL de l'image (optionnel)"},
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_newsletter",
            "description": "Envoie une newsletter à tous les abonnés email de la boutique.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Objet de l'email"},
                    "html_body": {"type": "string", "description": "Corps de l'email en HTML"},
                    "plain_body": {"type": "string", "description": "Version texte brut (optionnel)"},
                },
                "required": ["subject", "html_body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_customer_messages",
            "description": "Récupère les messages et commentaires clients en attente de réponse.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reply_to_customer",
            "description": "Répond à un message ou commentaire client sur Instagram ou Facebook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "ID du message client"},
                    "platform": {"type": "string", "description": "Plateforme (instagram ou facebook)"},
                    "reply_text": {"type": "string", "description": "Réponse à envoyer"},
                },
                "required": ["message_id", "platform", "reply_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_abandoned_cart_email",
            "description": "Envoie un email de relance à un client qui a abandonné son panier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_email": {"type": "string"},
                    "customer_name": {"type": "string"},
                    "cart_items": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Liste des articles du panier",
                    },
                    "cart_url": {"type": "string", "description": "URL du panier"},
                },
                "required": ["customer_email", "customer_name", "cart_items", "cart_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_brand_knowledge",
            "description": "Relit la vault Obsidian et le dossier d'assets vidéo pour rafraîchir le contexte de marque, les instructions et les ressources disponibles.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "render_video",
            "description": (
                "Lance le rendu d'une vidéo Remotion. "
                "L'ID de composition suit le format YYYYMMDD (ex: '20260519'). "
                "La composition DOIT exister dans Root.tsx — utilise create_post_composition d'abord si elle n'existe pas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "composition_id": {"type": "string", "description": "ID Remotion au format YYYYMMDD"},
                    "output_filename": {"type": "string", "description": "Nom du fichier MP4 (optionnel)"},
                },
                "required": ["composition_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_rendered_videos",
            "description": "Liste les vidéos MP4 déjà rendues dans le dossier out/ du projet Remotion.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "save_to_memory",
            "description": (
                "Enregistre une note importante dans la mémoire persistante (vault Obsidian). "
                "Utilise dès que l'utilisateur exprime une préférence, une instruction récurrente, "
                "un retour sur un contenu, ou toute information à retenir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "note": {"type": "string", "description": "Note claire et concise à mémoriser"},
                },
                "required": ["note"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_post_props",
            "description": "Lit les props actuelles d'un post Remotion dans Root.tsx. À appeler avant toute modification.",
            "parameters": {
                "type": "object",
                "properties": {
                    "composition_id": {"type": "string", "description": "ID du post au format YYYYMMDD"},
                },
                "required": ["composition_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_post_props",
            "description": (
                "Écrit directement les nouvelles valeurs d'un post dans Root.tsx. "
                "Champs modifiables : hookText, verdict, leftItems, rightItems, ctaText, tips, plants, musicTrack. "
                "Appelle toujours render_video juste après."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "composition_id": {"type": "string", "description": "ID du post au format YYYYMMDD"},
                    "updates": {
                        "type": "object",
                        "description": "Champs à modifier. Ex: {\"hookText\": \"Nouveau texte\"}",
                    },
                },
                "required": ["composition_id", "updates"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_post_composition",
            "description": (
                "Crée une NOUVELLE composition dans Root.tsx quand elle n'existe pas encore. "
                "Ajoute automatiquement le bloc const ET l'enregistrement <Composition>. "
                "Appelle render_video ensuite."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "composition_id": {"type": "string", "description": "ID du post au format YYYYMMDD"},
                    "props": {
                        "type": "object",
                        "description": "Props complètes incluant template_type et tous les champs du template.",
                    },
                },
                "required": ["composition_id", "props"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_calendar_file",
            "description": "Crée ou met à jour un fichier markdown de calendrier éditorial dans la vault Obsidian.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Nom du fichier (ex: 'juin-2026.md')"},
                    "content": {"type": "string", "description": "Contenu markdown complet du calendrier"},
                },
                "required": ["filename", "content"],
            },
        },
    },
]

# Outils ultra-compacts pour Groq (TPM très limité — descriptions courtes)
TOOLS_COMPACT = [
    {"type": "function", "function": {"name": "get_store_analytics", "description": "Stats boutique Shopify.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "get_products", "description": "Liste produits actifs.", "parameters": {"type": "object", "properties": {"limit": {"type": "integer"}}, "required": []}}},
    {"type": "function", "function": {"name": "update_product_description", "description": "Met à jour description produit.", "parameters": {"type": "object", "properties": {"product_id": {"type": "integer"}, "new_description": {"type": "string"}}, "required": ["product_id", "new_description"]}}},
    {"type": "function", "function": {"name": "post_to_instagram", "description": "Post Instagram.", "parameters": {"type": "object", "properties": {"caption": {"type": "string"}, "image_url": {"type": "string"}}, "required": ["caption", "image_url"]}}},
    {"type": "function", "function": {"name": "post_to_facebook", "description": "Post Facebook.", "parameters": {"type": "object", "properties": {"message": {"type": "string"}, "link": {"type": "string"}, "image_url": {"type": "string"}}, "required": ["message"]}}},
    {"type": "function", "function": {"name": "send_newsletter", "description": "Envoie newsletter.", "parameters": {"type": "object", "properties": {"subject": {"type": "string"}, "html_body": {"type": "string"}, "plain_body": {"type": "string"}}, "required": ["subject", "html_body"]}}},
    {"type": "function", "function": {"name": "get_pending_customer_messages", "description": "Messages clients en attente.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "reply_to_customer", "description": "Répond client.", "parameters": {"type": "object", "properties": {"message_id": {"type": "string"}, "platform": {"type": "string"}, "reply_text": {"type": "string"}}, "required": ["message_id", "platform", "reply_text"]}}},
    {"type": "function", "function": {"name": "send_abandoned_cart_email", "description": "Email panier abandonné.", "parameters": {"type": "object", "properties": {"customer_email": {"type": "string"}, "customer_name": {"type": "string"}, "cart_items": {"type": "array", "items": {"type": "string"}}, "cart_url": {"type": "string"}}, "required": ["customer_email", "customer_name", "cart_items", "cart_url"]}}},
    {"type": "function", "function": {"name": "get_brand_knowledge", "description": "Charge vault Obsidian et assets vidéo.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "render_video", "description": "Rend vidéo Remotion. ID format YYYYMMDD.", "parameters": {"type": "object", "properties": {"composition_id": {"type": "string"}, "output_filename": {"type": "string"}}, "required": ["composition_id"]}}},
    {"type": "function", "function": {"name": "list_rendered_videos", "description": "Liste MP4 rendus.", "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {"name": "save_to_memory", "description": "Sauvegarde note persistante.", "parameters": {"type": "object", "properties": {"note": {"type": "string"}}, "required": ["note"]}}},
    {"type": "function", "function": {"name": "get_post_props", "description": "Lit props d'un post Remotion.", "parameters": {"type": "object", "properties": {"composition_id": {"type": "string"}}, "required": ["composition_id"]}}},
    {"type": "function", "function": {"name": "update_post_props", "description": "Modifie props d'un post Remotion. Appelle render_video après.", "parameters": {"type": "object", "properties": {"composition_id": {"type": "string"}, "updates": {"type": "object"}}, "required": ["composition_id", "updates"]}}},
    {"type": "function", "function": {"name": "create_post_composition", "description": "Crée nouvelle composition Remotion dans Root.tsx.", "parameters": {"type": "object", "properties": {"composition_id": {"type": "string"}, "props": {"type": "object"}}, "required": ["composition_id", "props"]}}},
    {"type": "function", "function": {"name": "write_calendar_file", "description": "Crée fichier calendrier markdown dans Obsidian.", "parameters": {"type": "object", "properties": {"filename": {"type": "string"}, "content": {"type": "string"}}, "required": ["filename", "content"]}}},
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

    if name == "create_post_composition":
        return create_post_composition(inputs["composition_id"], VIDEO_ASSETS_PATH, inputs["props"])

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

def build_system_prompt(compact: bool = False) -> str:
    today = datetime.now().strftime("%A %d %B %Y")

    memory = read_agent_memory(OBSIDIAN_VAULT_PATH)
    # En mode compact (Groq TPM), on tronque agressivement la mémoire
    _mem_max = 800 if compact else 4000
    if memory:
        mem_trimmed = memory[:_mem_max] + ("\n[... tronqué ...]" if len(memory) > _mem_max else "")
        memory_section = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️  MÉMOIRE PERSISTANTE — CONTRAINTES ABSOLUES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{mem_trimmed}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLE CRITIQUE : relis ci-dessus et ne viole AUCUNE contrainte.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    else:
        memory_section = "\n(mémoire vide — utilise save_to_memory pour enregistrer des préférences)\n"

    # Vault et assets : inclus uniquement hors mode compact (Claude/OpenAI)
    vault_section = ""
    assets_section = ""
    if not compact:
        vault_content = read_obsidian_vault(OBSIDIAN_VAULT_PATH)
        assets = list_video_assets(VIDEO_ASSETS_PATH)
        if vault_content:
            vault_trimmed = vault_content[:6000] + ("\n[... tronqué ...]" if len(vault_content) > 6000 else "")
            vault_section = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VAULT OBSIDIAN — CONNAISSANCES DE LA MARQUE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{vault_trimmed}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        if assets:
            lines = "\n".join(
                f"  - [{a['type'].upper()}] {a['name']}  ({a['size_kb']} KB)  → {a['path']}"
                for a in assets[:20]
            )
            extra = f"\n  (+ {len(assets) - 20} autres...)" if len(assets) > 20 else ""
            assets_section = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ASSETS VIDÉO / IMAGES DISPONIBLES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{lines}{extra}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    if compact:
        # Prompt minimal pour Groq (TPM 12k) — pas de dividers, pas de vault/assets
        mem_line = f"MEMOIRE: {mem_trimmed}" if memory else ""
        return f"""Agent marketing "{STORE_NAME}" ({STORE_NICHE}). Aujourd'hui: {today}.
Voix: {BRAND_VOICE} | Cible: {TARGET_AUDIENCE} | Boutique: https://{SHOPIFY_SHOP_URL}
{mem_line}
CONTENU INTERDIT: animaleries, plantes qui meurent, pesticides, concurrents.
CONTENU OK: beaute plantes, prix 0.99EUR+, cultivees France/Europe, livraison rapide, facilite entretien.
REGLES: reponds en "tu", sois court (1-3 phrases), fais les actions directement sans demander confirmation.
TACHE PRECISE: si instruction specifique, fais-la directement. ROUTINE: si message vide, lance routine complete.
REMOTION: projet={VIDEO_ASSETS_PATH}, ID=YYYYMMDD. Post existant: get_post_props->update_post_props->render_video. Post absent: create_post_composition->render_video.
CALENDRIER: get_brand_knowledge puis write_calendar_file. Format: | Jour | Date | Template | Plateformes | Sujet | ID |
MEMOIRE: save_to_memory avant toute action si correction/preference.
PUBLICATIONS: Instagram/Facebook/newsletter -> file d'attente. Vidéo/Root.tsx/calendrier -> direct."""

    return f"""Tu es l'agent marketing IA de "{STORE_NAME}" ({STORE_NICHE}).
Voix de marque : {BRAND_VOICE} | Cible : {TARGET_AUDIENCE}
Boutique : https://{SHOPIFY_SHOP_URL} | Aujourd'hui : {today}
{memory_section}{vault_section}{assets_section}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{CONTENT_RULES}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLES DE COMPORTEMENT — OBLIGATOIRES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Réponds TOUJOURS en "tu" — JAMAIS "vous", JAMAIS "votre", JAMAIS "Souhaitez-vous"
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
• ID composition : YYYYMMDD (ex: "20260520" = 20 mai 2026)

CAS 1 — Post existant dans Root.tsx (get_post_props retourne des données) :
  1. get_post_props(id)            ← lire le contenu actuel
  2. update_post_props(id, champs) ← écrire les nouvelles valeurs
  3. render_video(id)              ← générer le MP4

CAS 2 — Post ABSENT de Root.tsx (get_post_props retourne vide ou erreur) :
  1. create_post_composition(id, props_complets) ← CRÉE la composition dans Root.tsx
  2. render_video(id)                            ← générer le MP4

RÈGLES :
• Relis toujours la MÉMOIRE avant de générer du contenu — aucune contrainte ne doit être violée
• Ne génère JAMAIS un script texte dans le chat — écris dans Root.tsx et rends la vidéo
• Fais toutes les étapes d'affilée SANS t'arrêter ni demander confirmation

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CALENDRIER ÉDITORIAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Créer un mois : get_brand_knowledge pour voir le format, puis write_calendar_file
• Format : | Jour | Date | Template | Plateformes | Sujet | ID |
• ID = YYYYMMDD | lundi→samedi | formats : VersusVideo, EducatifVideo, PromoVideo, TikTokOrganic, ConceptVideo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MÉMOIRE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Dès que l'utilisateur exprime une correction ou préférence → appelle save_to_memory EN PREMIER, avant toute autre action
• Format de la note : commence par ce qui est interdit/obligatoire, puis le contexte
  Exemples : "INTERDIT : dire que les plantes meurent en 2 semaines — c'est faux"
             "PRIX : un pot en animalerie coûte 5€, pas 10€"
             "TON : toujours utiliser 'tu' avec les clients"
• La mémoire s'applique à TOUT le contenu généré dans toutes les sessions suivantes

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PUBLICATIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Instagram, Facebook, newsletter, descriptions produits → mis en attente d'approbation humaine
• Rendu vidéo, modification Root.tsx, calendrier → exécution directe immédiate"""


# ─── Boucle agent principale ──────────────────────────────────────────────────

def run_marketing_session(task: str = None) -> str:
    """Lance une session marketing. Priorité : Claude → OpenAI → Groq."""
    if ANTHROPIC_API_KEY:
        return _run_session_claude(task)
    if OPENAI_API_KEY:
        return _run_session_openai(task)
    return _run_session_groq(task)


def _run_session_groq(task: str = None) -> str:
    from groq import Groq

    groq_client = Groq(api_key=GROQ_API_KEY)
    system_prompt = build_system_prompt(compact=True)
    user_message = task or "Lance la routine marketing quotidienne complète."

    logger.info("=== Session Groq | %s ===", datetime.now().isoformat())

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    iteration = 0
    max_iterations = 20

    while iteration < max_iterations:
        iteration += 1
        logger.info("Tour %d", iteration)

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            tools=TOOLS_COMPACT,
            tool_choice="auto",
            temperature=0.6,
            max_tokens=4096,
        )

        msg = response.choices[0].message
        tool_calls = msg.tool_calls or []

        assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
        if tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ]
        messages.append(assistant_entry)

        if not tool_calls:
            logger.info("=== Session Groq terminée après %d tours ===", iteration)
            return msg.content or "(aucune réponse)"

        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                tool_result = execute_tool(tc.function.name, args)
            except Exception as exc:
                logger.warning("Outil %s échoué : %s", tc.function.name, exc)
                tool_result = {"status": "error", "reason": str(exc)}

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(tool_result, ensure_ascii=False, default=str),
            })

    logger.warning("Limite d'itérations atteinte (%d)", max_iterations)
    return "Session interrompue : limite d'itérations atteinte."


def _run_session_openai(task: str = None) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)
    system_prompt = build_system_prompt()
    user_message = task or "Lance la routine marketing quotidienne complète."

    logger.info("=== Session OpenAI | %s ===", datetime.now().isoformat())

    # Convertit TOOLS_GROQ en format OpenAI (identique, c'est déjà le même format)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]
    iteration = 0
    max_iterations = 20

    while iteration < max_iterations:
        iteration += 1
        logger.info("Tour OpenAI %d", iteration)

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            tools=TOOLS_GROQ,
            tool_choice="auto",
            temperature=0.6,
            max_tokens=4096,
        )

        msg = response.choices[0].message
        tool_calls = msg.tool_calls or []

        assistant_entry: dict = {"role": "assistant", "content": msg.content or ""}
        if tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in tool_calls
            ]
        messages.append(assistant_entry)

        if not tool_calls:
            logger.info("=== Session OpenAI terminée après %d tours ===", iteration)
            return msg.content or "(aucune réponse)"

        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                tool_result = execute_tool(tc.function.name, args)
            except Exception as exc:
                logger.warning("Outil %s échoué : %s", tc.function.name, exc)
                tool_result = {"status": "error", "reason": str(exc)}

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(tool_result, ensure_ascii=False, default=str),
            })

    logger.warning("Limite d'itérations atteinte (%d)", max_iterations)
    return "Session interrompue : limite d'itérations atteinte."


def _run_session_claude(task: str = None) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    system_prompt = build_system_prompt()
    user_message = task or "Lance la routine marketing quotidienne complète."

    logger.info("=== Session Claude | %s ===", datetime.now().isoformat())

    # Convertit TOOLS_GROQ (format OpenAI) en format Anthropic
    tools_anthropic = [
        {
            "name": t["function"]["name"],
            "description": t["function"].get("description", ""),
            "input_schema": t["function"].get("parameters", {"type": "object", "properties": {}}),
        }
        for t in TOOLS_GROQ
    ]

    messages: list[dict] = [{"role": "user", "content": user_message}]
    iteration = 0
    max_iterations = 20

    while iteration < max_iterations:
        iteration += 1
        logger.info("Tour Claude %d", iteration)

        response = client.messages.create(
            model=CLAUDE_SCRIPT_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            tools=tools_anthropic,
        )

        # Construire l'entrée assistant (texte + éventuels tool_use)
        assistant_content = response.content  # liste de blocs
        messages.append({"role": "assistant", "content": assistant_content})

        tool_use_blocks = [b for b in assistant_content if b.type == "tool_use"]

        if not tool_use_blocks:
            text_blocks = [b for b in assistant_content if b.type == "text"]
            text = " ".join(b.text for b in text_blocks)
            logger.info("=== Session Claude terminée après %d tours ===", iteration)
            return text or "(aucune réponse)"

        # Exécuter les outils et renvoyer les résultats
        tool_results = []
        for b in tool_use_blocks:
            try:
                tool_result = execute_tool(b.name, b.input or {})
            except Exception as exc:
                logger.warning("Outil %s échoué : %s", b.name, exc)
                tool_result = {"status": "error", "reason": str(exc)}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": b.id,
                "content": json.dumps(tool_result, ensure_ascii=False, default=str),
            })

        messages.append({"role": "user", "content": tool_results})

    logger.warning("Limite d'itérations atteinte (%d)", max_iterations)
    return "Session interrompue : limite d'itérations atteinte."
