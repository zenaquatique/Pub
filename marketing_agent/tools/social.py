"""Publication sur les réseaux sociaux (Instagram, Facebook, TikTok)."""
import hashlib
import os
import time
import requests
from datetime import datetime, timezone
from config import (
    META_PAGE_TOKEN, META_IG_ACCOUNT_ID, FACEBOOK_PAGE_ID,
    TIKTOK_ACCESS_TOKEN,
    CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET,
)

# backward compat aliases
META_ACCESS_TOKEN     = META_PAGE_TOKEN
INSTAGRAM_BUSINESS_ID = META_IG_ACCOUNT_ID


# ── Cloudinary ────────────────────────────────────────────────────────────────

def upload_to_cloudinary(video_path: str) -> str:
    """Upload une vidéo sur Cloudinary (requête signée) et retourne l'URL publique."""
    if not CLOUDINARY_CLOUD_NAME or not CLOUDINARY_API_KEY:
        raise ValueError("Cloudinary non configuré — vérifiez CLOUDINARY_* dans .env")

    ts       = int(time.time())
    sig_str  = f"timestamp={ts}{CLOUDINARY_API_SECRET}"
    signature = hashlib.sha1(sig_str.encode()).hexdigest()

    url = f"https://api.cloudinary.com/v1_1/{CLOUDINARY_CLOUD_NAME}/video/upload"
    with open(video_path, "rb") as f:
        r = requests.post(
            url,
            files={"file": (os.path.basename(video_path), f, "video/mp4")},
            data={"api_key": CLOUDINARY_API_KEY, "timestamp": ts, "signature": signature},
            timeout=600,
        )
    r.raise_for_status()
    return r.json()["secure_url"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _unix_ts(dt: datetime) -> int:
    return int(dt.timestamp())


def _http_error_message(exc: requests.HTTPError) -> str:
    try:
        return exc.response.json().get("error", {}).get("message", exc.response.text)
    except Exception:
        return exc.response.text if exc.response else str(exc)


# ── Facebook ──────────────────────────────────────────────────────────────────

def post_video_to_facebook(
    video_path: str,
    description: str,
    title: str = "",
    scheduled_at: datetime = None,
) -> dict:
    """Upload et publie (ou programme) une vidéo MP4 sur la Page Facebook."""
    if not META_PAGE_TOKEN or not FACEBOOK_PAGE_ID:
        return {"status": "skipped", "reason": "Facebook non configuré — vérifiez META_PAGE_TOKEN et META_PAGE_ID dans .env"}
    if not os.path.exists(video_path):
        return {"status": "error", "error": f"Fichier introuvable : {video_path}"}

    now = datetime.now(timezone.utc)
    is_scheduled = scheduled_at is not None and (scheduled_at - now).total_seconds() > 600

    payload = {
        "description": description,
        "title": title or "",
        "access_token": META_PAGE_TOKEN,
        "published": "false" if is_scheduled else "true",
    }
    if is_scheduled:
        payload["scheduled_publish_time"] = str(_unix_ts(scheduled_at))

    try:
        url = f"https://graph-video.facebook.com/v19.0/{FACEBOOK_PAGE_ID}/videos"
        with open(video_path, "rb") as f:
            resp = requests.post(
                url,
                files={"source": (os.path.basename(video_path), f, "video/mp4")},
                data=payload,
                timeout=600,
            )
        resp.raise_for_status()
        video_id = resp.json().get("id", "")
        return {
            "status": "scheduled" if is_scheduled else "published",
            "platform": "facebook",
            "video_id": video_id,
            "scheduled_at": scheduled_at.isoformat() if is_scheduled else None,
            "url": f"https://www.facebook.com/{FACEBOOK_PAGE_ID}/videos/{video_id}" if video_id else "",
        }
    except requests.HTTPError as exc:
        return {"status": "error", "error": _http_error_message(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ── Instagram Reels ───────────────────────────────────────────────────────────

def post_reels_to_instagram(
    video_path: str,
    caption: str,
    scheduled_at: datetime = None,
) -> dict:
    """Upload sur Cloudinary puis publie (ou programme) un Reel Instagram."""
    if not META_PAGE_TOKEN or not META_IG_ACCOUNT_ID:
        return {"status": "skipped", "reason": "Instagram non configuré — vérifiez META_PAGE_TOKEN et META_IG_ACCOUNT_ID dans .env"}
    if not os.path.exists(video_path):
        return {"status": "error", "error": f"Fichier introuvable : {video_path}"}

    # 1. Upload Cloudinary → URL publique
    try:
        video_url = upload_to_cloudinary(video_path)
    except Exception as exc:
        return {"status": "error", "error": f"Cloudinary upload échoué : {exc}"}

    now = datetime.now(timezone.utc)
    is_scheduled = scheduled_at is not None and (scheduled_at - now).total_seconds() > 600
    base  = "https://graph.facebook.com/v19.0"
    token = META_PAGE_TOKEN

    try:
        # 2. Créer le conteneur média
        container_payload = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": token,
        }
        if is_scheduled:
            container_payload["published"] = "false"
            container_payload["scheduled_publish_time"] = str(_unix_ts(scheduled_at))

        r = requests.post(f"{base}/{META_IG_ACCOUNT_ID}/media", data=container_payload, timeout=60)
        r.raise_for_status()
        container_id = r.json().get("id")

        # 3. Poll status FINISHED (max 5 min)
        for _ in range(30):
            time.sleep(10)
            status_r = requests.get(
                f"{base}/{container_id}",
                params={"fields": "status_code", "access_token": token},
                timeout=15,
            )
            code = status_r.json().get("status_code", "")
            if code == "FINISHED":
                break
            if code == "ERROR":
                return {"status": "error", "error": "Traitement vidéo Instagram échoué (status ERROR)"}

        # 4. Publier / programmer
        pub_payload = {"creation_id": container_id, "access_token": token}
        if is_scheduled:
            pub_payload["scheduled_publish_time"] = str(_unix_ts(scheduled_at))

        pub_r = requests.post(f"{base}/{META_IG_ACCOUNT_ID}/media_publish", data=pub_payload, timeout=30)
        pub_r.raise_for_status()
        post_id = pub_r.json().get("id", "")

        return {
            "status": "scheduled" if is_scheduled else "published",
            "platform": "instagram",
            "post_id": post_id,
            "scheduled_at": scheduled_at.isoformat() if is_scheduled else None,
            "video_url": video_url,
        }

    except requests.HTTPError as exc:
        return {"status": "error", "error": _http_error_message(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ── TikTok ────────────────────────────────────────────────────────────────────

def post_video_to_tiktok(video_path: str, caption: str) -> dict:
    """Upload sur Cloudinary puis publie via TikTok Content Posting API."""
    if not TIKTOK_ACCESS_TOKEN:
        return {"status": "skipped", "reason": "TikTok non configuré — vérifiez TIKTOK_ACCESS_TOKEN dans .env"}
    if not os.path.exists(video_path):
        return {"status": "error", "error": f"Fichier introuvable : {video_path}"}

    # Upload Cloudinary → URL publique
    try:
        video_url = upload_to_cloudinary(video_path)
    except Exception as exc:
        return {"status": "error", "error": f"Cloudinary upload échoué : {exc}"}

    url = "https://open.tiktokapis.com/v2/post/publish/video/init/"
    headers = {
        "Authorization": f"Bearer {TIKTOK_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "post_info": {
            "title": caption[:150],
            "privacy_level": "PUBLIC_TO_EVERYONE",
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "PULL_FROM_URL",
            "video_url": video_url,
        },
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        r.raise_for_status()
        publish_id = r.json().get("data", {}).get("publish_id", "")
        return {
            "status": "published",
            "platform": "tiktok",
            "publish_id": publish_id,
            "video_url": video_url,
        }
    except requests.HTTPError as exc:
        return {"status": "error", "error": _http_error_message(exc)}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


# ── Helpers image/texte (anciens) ─────────────────────────────────────────────

def post_to_instagram(caption: str, image_url: str) -> dict:
    if not META_PAGE_TOKEN or not META_IG_ACCOUNT_ID:
        return {"status": "skipped", "reason": "Instagram non configuré"}
    create_url = f"https://graph.facebook.com/v19.0/{META_IG_ACCOUNT_ID}/media"
    r = requests.post(create_url, data={"image_url": image_url, "caption": caption, "access_token": META_PAGE_TOKEN}, timeout=20)
    r.raise_for_status()
    container_id = r.json()["id"]
    time.sleep(3)
    r2 = requests.post(f"https://graph.facebook.com/v19.0/{META_IG_ACCOUNT_ID}/media_publish",
                       data={"creation_id": container_id, "access_token": META_PAGE_TOKEN}, timeout=20)
    r2.raise_for_status()
    return {"status": "published", "platform": "instagram", "post_id": r2.json().get("id")}


def post_to_facebook(message: str, link: str = None, image_url: str = None) -> dict:
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


def simulate_post(platform: str, content: str, image_url: str = None) -> dict:
    print(f"\n[SIMULATION] Publication {platform.upper()}")
    print(f"Content: {content[:200]}...")
    return {"status": "simulated", "platform": platform}
