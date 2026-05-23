"""Publication sur les réseaux sociaux (Instagram, Facebook, TikTok)."""
import os
import time
import requests
from config import (
    META_PAGE_TOKEN, META_IG_ACCOUNT_ID, FACEBOOK_PAGE_ID,
    TIKTOK_ACCESS_TOKEN,
)

# backward compat
META_ACCESS_TOKEN     = META_PAGE_TOKEN
INSTAGRAM_BUSINESS_ID = META_IG_ACCOUNT_ID


def post_video_to_facebook(video_path: str, description: str, title: str = "") -> dict:
    """Upload et publie une vidéo MP4 sur la Page Facebook via graph-video."""
    if not META_PAGE_TOKEN or not FACEBOOK_PAGE_ID:
        return {"status": "skipped", "reason": "Facebook non configuré — vérifiez META_PAGE_TOKEN et META_PAGE_ID dans .env"}

    if not os.path.exists(video_path):
        return {"status": "error", "error": f"Fichier introuvable : {video_path}"}

    url = f"https://graph-video.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/videos"

    try:
        with open(video_path, "rb") as f:
            resp = requests.post(
                url,
                files={"source": (os.path.basename(video_path), f, "video/mp4")},
                data={
                    "description": description,
                    "title": title or "",
                    "access_token": META_PAGE_TOKEN,
                },
                timeout=600,
            )
        resp.raise_for_status()
        data = resp.json()
        video_id = data.get("id", "")
        page_url = f"https://www.facebook.com/{FACEBOOK_PAGE_ID}/videos/{video_id}" if video_id else ""
        return {
            "status": "published",
            "platform": "facebook",
            "video_id": video_id,
            "url": page_url,
        }
    except requests.HTTPError as exc:
        detail = ""
        try:
            detail = exc.response.json().get("error", {}).get("message", exc.response.text)
        except Exception:
            detail = exc.response.text if exc.response else str(exc)
        return {"status": "error", "error": detail}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def post_to_instagram(caption: str, image_url: str) -> dict:
    """Publie une image avec légende sur Instagram Business."""
    if not META_PAGE_TOKEN or not META_IG_ACCOUNT_ID:
        return {"status": "skipped", "reason": "Instagram non configuré"}

    create_url = f"https://graph.facebook.com/v19.0/{META_IG_ACCOUNT_ID}/media"
    payload = {"image_url": image_url, "caption": caption, "access_token": META_PAGE_TOKEN}
    r = requests.post(create_url, data=payload, timeout=20)
    r.raise_for_status()
    container_id = r.json()["id"]

    time.sleep(3)

    publish_url = f"https://graph.facebook.com/v19.0/{META_IG_ACCOUNT_ID}/media_publish"
    r2 = requests.post(publish_url, data={"creation_id": container_id, "access_token": META_PAGE_TOKEN}, timeout=20)
    r2.raise_for_status()
    return {"status": "published", "platform": "instagram", "post_id": r2.json().get("id")}


def post_to_facebook(message: str, link: str = None, image_url: str = None) -> dict:
    """Publie un texte/lien/image sur la Page Facebook."""
    if not META_PAGE_TOKEN or not FACEBOOK_PAGE_ID:
        return {"status": "skipped", "reason": "Facebook non configuré"}

    url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/feed"
    payload = {"message": message, "access_token": META_PAGE_TOKEN}
    if link:
        payload["link"] = link
    if image_url and not link:
        url = f"https://graph.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/photos"
        payload["url"] = image_url
        payload["caption"] = message

    r = requests.post(url, data=payload, timeout=20)
    r.raise_for_status()
    return {"status": "published", "platform": "facebook", "post_id": r.json().get("id")}


def post_to_tiktok(video_url: str, description: str) -> dict:
    """Publie une vidéo sur TikTok via l'API Content Posting."""
    if not TIKTOK_ACCESS_TOKEN:
        return {"status": "skipped", "reason": "TikTok non configuré"}

    url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {"Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "post_info": {"title": description[:150], "privacy_level": "PUBLIC_TO_EVERYONE"},
        "source_info": {"source": "PULL_FROM_URL", "video_url": video_url},
    }
    r = requests.post(url, json=payload, headers=headers, timeout=20)
    r.raise_for_status()
    return {"status": "published", "platform": "tiktok", "publish_id": r.json().get("data", {}).get("publish_id")}


def simulate_post(platform: str, content: str, image_url: str = None) -> dict:
    """Mode simulation — log uniquement, aucun appel API réel."""
    print(f"\n[SIMULATION] Publication {platform.upper()}")
    print(f"Content: {content[:200]}...")
    if image_url:
        print(f"Image: {image_url}")
    return {"status": "simulated", "platform": platform}
