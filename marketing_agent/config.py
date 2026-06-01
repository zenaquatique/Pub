import os
from pathlib import Path
from dotenv import load_dotenv

_local_env = Path(__file__).parent / ".env"
load_dotenv(_local_env)

# Groq (génération scripts vidéo)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL   = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

# Règles de contenu — injectées dans TOUS les prompts de génération
CONTENT_RULES = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLES DE CONTENU — OBLIGATOIRES SANS EXCEPTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SUJET DU SCRIPT : Les points forts de ZenAquatique. RIEN D'AUTRE.

❌ INTERDIT — ne jamais écrire, insinuer, ni sous-entendre :
• Tout ce qui concerne les animaleries ou autres vendeurs (ne pas les nommer, ne pas les comparer, ne pas les critiquer)
• Les plantes qui meurent, dépérissent, ne survivent pas, durent 2 semaines, ou toute durée similaire
• Les pesticides, traitements chimiques, plantes traitées ou importées sous conditions douteuses
• Toute affirmation sur les pratiques des concurrents

✅ UNIQUEMENT ces angles positifs sur ZenAquatique :
• Beauté visuelle des plantes (couleurs, formes, effet aquascape)
• Prix accessibles à partir de 0,99€
• Cultivées en France / en Europe
• Livraison rapide, plantes fraîches à la réception
• Facilité d'entretien et d'adaptation
• Passion aquariophile, conseil, service client
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


# Shopify (optionnel — mode simulation si non configuré)
SHOPIFY_SHOP_URL     = os.environ.get("SHOPIFY_SHOP_URL", "")
SHOPIFY_ACCESS_TOKEN = os.environ.get("SHOPIFY_ACCESS_TOKEN", "")

# Meta — nommage exact du .env
META_USER_TOKEN    = os.environ.get("META_USER_TOKEN", "")
META_PAGE_ID       = os.environ.get("META_PAGE_ID", "")
META_APP_ID        = os.environ.get("META_APP_ID", "")
META_APP_SECRET    = os.environ.get("META_APP_SECRET", "")
META_IG_ACCOUNT_ID = os.environ.get("META_IG_ACCOUNT_ID", "")

# Accepte tous les noms possibles pour le token et l'ID de page
META_PAGE_TOKEN = (
    os.environ.get("META_PAGE_TOKEN")
    or os.environ.get("META_USER_TOKEN")
    or os.environ.get("META_ACCESS_TOKEN")
    or ""
)
META_ACCESS_TOKEN = META_PAGE_TOKEN

FACEBOOK_PAGE_ID = (
    os.environ.get("META_PAGE_ID")
    or os.environ.get("FACEBOOK_PAGE_ID")
    or ""
)

INSTAGRAM_BUSINESS_ID = META_IG_ACCOUNT_ID

# TikTok
TIKTOK_CLIENT_KEY    = os.environ.get("TIKTOK_CLIENT_KEY", "")
TIKTOK_CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
TIKTOK_ACCESS_TOKEN  = os.environ.get("TIKTOK_ACCESS_TOKEN", "")

# Cloudinary (hébergement temporaire pour Instagram Reels et TikTok)
CLOUDINARY_CLOUD_NAME = os.environ.get("CLOUDINARY_CLOUD_NAME", "")
CLOUDINARY_API_KEY    = os.environ.get("CLOUDINARY_API_KEY", "")
CLOUDINARY_API_SECRET = os.environ.get("CLOUDINARY_API_SECRET", "")

# Email (SendGrid)
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
EMAIL_FROM       = os.environ.get("EMAIL_FROM", "")
EMAIL_LIST_ID    = os.environ.get("EMAIL_LIST_ID", "")

# Identité boutique
STORE_NAME      = os.environ.get("STORE_NAME", "Ma Boutique")
STORE_NICHE     = os.environ.get("STORE_NICHE", "e-commerce")
BRAND_VOICE     = os.environ.get("BRAND_VOICE", "dynamique, authentique, proche du client")
TARGET_AUDIENCE = os.environ.get("TARGET_AUDIENCE", "adultes 25-45 ans")

# Meta webhooks
META_WEBHOOK_VERIFY_TOKEN = os.environ.get("META_WEBHOOK_VERIFY_TOKEN", "mon_token_secret_webhook")

# Planificateur — créneau semaine 18h30, weekend 10h00
POSTING_HOUR     = int(os.environ.get("POSTING_HOUR", "18"))
POSTING_MINUTE   = int(os.environ.get("POSTING_MINUTE", "30"))
POSTING_TIMEZONE = os.environ.get("POSTING_TIMEZONE", "Europe/Paris")

# Claude API (optionnel — priorité sur Groq si clé fournie)
ANTHROPIC_API_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_SCRIPT_MODEL = os.environ.get("CLAUDE_SCRIPT_MODEL", "claude-haiku-4-5-20251001")

# OpenAI (fallback quand Groq est rate-limitée)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

# Ressources locales
OBSIDIAN_VAULT_PATH = os.environ.get("OBSIDIAN_VAULT_PATH", r"C:\Users\ec\Desktop\Obsidian\Pub")
VIDEO_ASSETS_PATH   = os.environ.get("VIDEO_ASSETS_PATH",   r"C:\Users\ec\Desktop\zenaquatique-video")
