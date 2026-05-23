"""Script one-shot : remplit les credentials dans le .env local.
Lancer une seule fois depuis le dossier marketing_agent/ :
    python setup_credentials.py
"""
from pathlib import Path

ENV_PATH = Path(__file__).parent / ".env"

CREDENTIALS = {
    "META_USER_TOKEN":      "EAALieVtYyqwBRbpFE9WuUAWLNnZASlYH50eGNfIkSUSCIVKhXlXyOu5vQPkue0o1WFPTNFLeQQviir32ZAwS8dj20p6N7ZCxQtzffM6NTI2ip9PEPBAomQSj8ZAwwdlLxbbQlZAkL2ZAsuoiD13Rps1VlLkL6NjdncsnS67MCrdbU2jSVUjs038lgU6SgGYSrw8ng6MHpXCXxt",
    "META_PAGE_TOKEN":      "EAALieVtYyqwBRXsSOFTWCrbjnYEzhc2PQOYa9bVfZAndH4co8M6slpL3YhZB0BUZAlyM5EKAGWCJbkXnr1TQrbYrARR7gzAZBdOehdf3RM14j7eTORypOtL7bQdWjmJVJsRTqdiYnWmHqMULIh0uphBrjuiCyZBOvxfrDtba1xwon7flGtwcZBo06PwvrFNVeW00p83HaKzfAe7EnBXN4BmKkV",
    "META_PAGE_ID":         "687765537757887",
    "META_APP_ID":          "811960804887212",
    "META_APP_SECRET":      "a240251d18c3fb27af45d5235efff5bf",
    "META_IG_ACCOUNT_ID":   "17841470045036166",
    "CLOUDINARY_CLOUD_NAME":"djr0kwlp1",
    "CLOUDINARY_API_KEY":   "661499473845151",
    "CLOUDINARY_API_SECRET":"Fbpu3dafYNvLe7GT8qwvutVqUb0",
    "ELEVENLABS_API_KEY":   "sk_44bd929e5414db3717e20beb3808bce14e5e10c76935d794",
    "ELEVENLABS_VOICE_ID":  "RC120K9RdCgexZFEp08N",
    "TIKTOK_CLIENT_KEY":    "aw91fs67kcgibcq0",
    "TIKTOK_CLIENT_SECRET": "S4I4SGeZOnOn3WGY83uBnLaVc9swuaar",
}

# Lit le .env existant ligne par ligne
lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []

updated = set()
new_lines = []
for line in lines:
    stripped = line.strip()
    if stripped and not stripped.startswith("#") and "=" in stripped:
        key = stripped.split("=", 1)[0].strip()
        if key in CREDENTIALS:
            new_lines.append(f"{key}={CREDENTIALS[key]}")
            updated.add(key)
            continue
    new_lines.append(line)

# Ajoute les clés absentes du fichier
for key, val in CREDENTIALS.items():
    if key not in updated:
        new_lines.append(f"{key}={val}")

ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

print("✅ .env mis à jour :")
for key, val in CREDENTIALS.items():
    status = "mis à jour" if key in updated else "ajouté"
    print(f"  {key[:30]:<30} [{status}]")
print("\nRedémarre le serveur pour appliquer les changements.")
