import os
from dotenv import load_dotenv

load_dotenv()

# Anthropic
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
CLAUDE_MODEL = "claude-opus-4-7"

# Shopify
SHOPIFY_SHOP_URL = os.environ["SHOPIFY_SHOP_URL"]        # ex: monshop.myshopify.com
SHOPIFY_ACCESS_TOKEN = os.environ["SHOPIFY_ACCESS_TOKEN"]

# Meta (Instagram / Facebook)
META_ACCESS_TOKEN = os.environ.get("META_ACCESS_TOKEN", "")
INSTAGRAM_BUSINESS_ID = os.environ.get("INSTAGRAM_BUSINESS_ID", "")
FACEBOOK_PAGE_ID = os.environ.get("FACEBOOK_PAGE_ID", "")

# TikTok
TIKTOK_ACCESS_TOKEN = os.environ.get("TIKTOK_ACCESS_TOKEN", "")

# Email (SendGrid)
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
EMAIL_FROM = os.environ.get("EMAIL_FROM", "")
EMAIL_LIST_ID = os.environ.get("EMAIL_LIST_ID", "")

# Store identity
STORE_NAME = os.environ.get("STORE_NAME", "Ma Boutique")
STORE_NICHE = os.environ.get("STORE_NICHE", "e-commerce")
BRAND_VOICE = os.environ.get("BRAND_VOICE", "dynamique, authentique, proche du client")
TARGET_AUDIENCE = os.environ.get("TARGET_AUDIENCE", "adultes 25-45 ans")

# Meta webhooks
META_APP_SECRET = os.environ.get("META_APP_SECRET", "")
META_WEBHOOK_VERIFY_TOKEN = os.environ.get("META_WEBHOOK_VERIFY_TOKEN", "mon_token_secret_webhook")

# Scheduler
POSTING_HOUR = int(os.environ.get("POSTING_HOUR", "9"))
POSTING_MINUTE = int(os.environ.get("POSTING_MINUTE", "0"))
POSTING_TIMEZONE = os.environ.get("POSTING_TIMEZONE", "Europe/Paris")
