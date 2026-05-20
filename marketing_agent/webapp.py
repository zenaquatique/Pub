"""Tableau de bord web — contrôle complet de l'agent marketing."""
import asyncio
import hashlib
import hmac
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from agent import execute_pending_action, _load_pending_actions, PENDING_ACTIONS_FILE
from config import (
    META_APP_SECRET, META_WEBHOOK_VERIFY_TOKEN, STORE_NAME, POSTING_HOUR, POSTING_MINUTE,
    OBSIDIAN_VAULT_PATH, VIDEO_ASSETS_PATH, GOOGLE_API_KEY, GEMINI_MODEL,
    STORE_NICHE, BRAND_VOICE, TARGET_AUDIENCE,
)
from tools.customer import (
    get_pending_messages,
    log_customer_message,
    mark_replied,
    send_facebook_reply,
    send_instagram_reply,
)
from tools.knowledge import find_calendar_files, read_obsidian_vault, list_video_assets, read_agent_memory, append_agent_memory
from tools.remotion import (
    render_video, list_rendered_videos,
    extract_post_props, generate_voiceover, date_to_composition_id,
    update_post_props, create_post_composition,
)
from tools.shopify import get_products, get_store_analytics

logger = logging.getLogger(__name__)

REPORTS_FILE = Path(__file__).parent / "data" / "reports.json"

# ─── État de l'agent ─────────────────────────────────────────────────────────

_agent_state: dict = {
    "status": "idle",   # idle | running | done | error
    "started_at": None,
    "finished_at": None,
    "report": "",
    "error": "",
    "task": "",
}
_executor = ThreadPoolExecutor(max_workers=1)

# ─── Persistance des rapports ─────────────────────────────────────────────────

def _load_reports() -> list:
    REPORTS_FILE.parent.mkdir(exist_ok=True)
    if REPORTS_FILE.exists():
        try:
            return json.loads(REPORTS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            REPORTS_FILE.unlink(missing_ok=True)
    return []


def _save_report(report: str, task: str = "") -> None:
    reports = _load_reports()
    reports.insert(0, {
        "id": str(datetime.now().timestamp()),
        "date": datetime.now().isoformat(),
        "task": task or "Routine quotidienne",
        "report": report,
    })
    REPORTS_FILE.write_text(json.dumps(reports[:50], ensure_ascii=False, indent=2), encoding="utf-8")


# ─── Exécution de l'agent dans un thread ─────────────────────────────────────

def _run_agent_sync(task: str) -> None:
    from agent import run_marketing_session
    _agent_state.update(status="running", started_at=datetime.now().isoformat(),
                        finished_at=None, report="", error="", task=task)
    try:
        report = run_marketing_session(task or None)
        _agent_state.update(status="done", report=report, finished_at=datetime.now().isoformat())
        _save_report(report, task)
    except Exception as exc:
        logger.exception("Erreur agent")
        _agent_state.update(status="error", error=str(exc), finished_at=datetime.now().isoformat())


# ─── Application ──────────────────────────────────────────────────────────────

app = FastAPI(title=f"{STORE_NAME} — Marketing Agent")
app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "static")), name="static")

_HTML_FILE = Path(__file__).parent / "templates" / "index.html"


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    html = _HTML_FILE.read_text(encoding="utf-8").replace("{{ store_name }}", STORE_NAME)
    return HTMLResponse(content=html)


# ─── API — Agent ──────────────────────────────────────────────────────────────

@app.post("/api/run")
async def api_run(request: Request):
    if _agent_state["status"] == "running":
        raise HTTPException(409, "L'agent est déjà en cours d'exécution.")
    body = await request.json()
    task = body.get("task", "")
    loop = asyncio.get_event_loop()
    loop.run_in_executor(_executor, _run_agent_sync, task)
    return {"status": "started"}


@app.get("/api/status")
async def api_status():
    return _agent_state


# ─── API — Données boutique ───────────────────────────────────────────────────

@app.get("/api/analytics")
async def api_analytics(period: str = "month", start_date: str = None, end_date: str = None):
    try:
        return get_store_analytics(period=period, start_date=start_date, end_date=end_date)
    except Exception as exc:
        raise HTTPException(502, f"Erreur Shopify : {exc}")


@app.get("/api/products")
async def api_products():
    try:
        return get_products(limit=20)
    except Exception as exc:
        raise HTTPException(502, f"Erreur Shopify : {exc}")


# ─── API — Rapports ───────────────────────────────────────────────────────────

@app.get("/api/reports")
async def api_reports():
    return _load_reports()


@app.delete("/api/reports/{report_id}")
async def delete_report(report_id: str):
    reports = [r for r in _load_reports() if r["id"] != report_id]
    REPORTS_FILE.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "deleted"}


# ─── API — Approbation des actions ───────────────────────────────────────────

@app.get("/api/pending-actions")
async def api_pending_actions():
    actions = _load_pending_actions()
    return [a for a in actions if a.get("status") == "pending"]


@app.get("/api/pending-actions/count")
async def api_pending_actions_count():
    actions = _load_pending_actions()
    count = sum(1 for a in actions if a.get("status") == "pending")
    return {"count": count}


@app.post("/api/pending-actions/{action_id}/approve")
async def api_approve_action(action_id: str):
    try:
        result = execute_pending_action(action_id)
        return {"status": "approved", "result": result}
    except Exception as exc:
        raise HTTPException(500, f"Erreur exécution : {exc}")


@app.post("/api/pending-actions/{action_id}/reject")
async def api_reject_action(action_id: str):
    actions = _load_pending_actions()
    found = False
    for action in actions:
        if action["id"] == action_id:
            action["status"] = "rejected"
            action["rejected_at"] = datetime.now().isoformat()
            found = True
            break
    if not found:
        raise HTTPException(404, f"Action introuvable : {action_id}")
    PENDING_ACTIONS_FILE.write_text(
        json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"status": "rejected"}


# ─── API — Messages clients ───────────────────────────────────────────────────

@app.get("/api/messages")
async def api_messages():
    return get_pending_messages()


@app.post("/api/messages/{message_id}/reply")
async def api_reply(message_id: str, request: Request):
    body = await request.json()
    platform = body.get("platform", "instagram")
    reply_text = body.get("reply_text", "")
    if not reply_text:
        raise HTTPException(400, "reply_text manquant")
    if platform == "instagram":
        result = send_instagram_reply(message_id, reply_text)
    else:
        result = send_facebook_reply(message_id, reply_text)
    mark_replied(message_id, reply_text)
    return result


# ─── Webhooks Meta ────────────────────────────────────────────────────────────

def _verify_meta_signature(payload: bytes, header: str) -> bool:
    if not META_APP_SECRET:
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(META_APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


@app.get("/webhook")
async def verify_webhook(request: Request) -> PlainTextResponse:
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == META_WEBHOOK_VERIFY_TOKEN:
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(403, "Vérification échouée")


@app.post("/webhook")
async def receive_webhook(request: Request):
    body = await request.body()
    if not _verify_meta_signature(body, request.headers.get("X-Hub-Signature-256", "")):
        raise HTTPException(401, "Signature invalide")
    data = json.loads(body)
    object_type = data.get("object", "")
    for entry in data.get("entry", []):
        for msg in entry.get("messaging", []):
            text = msg.get("message", {}).get("text", "")
            mid = msg.get("message", {}).get("mid", "")
            if text:
                platform = "instagram" if object_type == "instagram" else "facebook"
                log_customer_message(platform, msg.get("sender", {}).get("id", "?"), text, mid)
        for change in entry.get("changes", []):
            v = change.get("value", {})
            if v.get("id") and v.get("text"):
                platform = "instagram" if object_type == "instagram" else "facebook"
                log_customer_message(platform, v.get("from", {}).get("name", "?"), v["text"], v["id"])
    return {"status": "ok"}


# ─── API — Mémoire agent ─────────────────────────────────────────────────────

@app.get("/api/memory")
async def api_get_memory():
    content = read_agent_memory(OBSIDIAN_VAULT_PATH)
    return {"content": content}


@app.post("/api/memory")
async def api_add_memory(request: Request):
    body = await request.json()
    note = body.get("note", "").strip()
    if not note:
        raise HTTPException(400, "note manquante")
    result = append_agent_memory(OBSIDIAN_VAULT_PATH, note)
    return result


@app.delete("/api/memory")
async def api_clear_memory():
    from pathlib import Path
    p = Path(OBSIDIAN_VAULT_PATH) / "Mémoire Agent" / "memoire.md"
    if p.exists():
        p.unlink()
    return {"status": "cleared"}


# ─── API — Calendrier éditorial ──────────────────────────────────────────────

@app.get("/api/calendar")
async def api_calendar(file_index: int = 0):
    files = find_calendar_files(OBSIDIAN_VAULT_PATH)
    if not files:
        return {"raw": "", "source": "", "all_files": []}
    idx  = max(0, min(file_index, len(files) - 1))
    main = files[idx]
    return {"raw": main["content"], "source": main["file"], "all_files": [f["file"] for f in files]}


# ─── Génération IA de voix off ───────────────────────────────────────────────

_VOICEOVER_SCHEMAS = {
    "VersusVideoProps": """{
  "hookText": "accroche courte (max 8 mots)",
  "hookEmoji": "1 emoji",
  "leftLabel": "label option gauche",
  "leftItems": ["avantage 1", "avantage 2", "avantage 3"],
  "rightLabel": "label option droite",
  "rightItems": ["avantage 1", "avantage 2", "avantage 3"],
  "verdict": "verdict final court",
  "ctaText": "call-to-action"
}""",
    "EducatifVideoProps": """{
  "hookText": "question ou affirmation courte",
  "hookEmoji": "1 emoji",
  "tips": [
    {"num": "01", "title": "titre court", "desc": "description 1 phrase"},
    {"num": "02", "title": "titre court", "desc": "description 1 phrase"},
    {"num": "03", "title": "titre court", "desc": "description 1 phrase"}
  ],
  "ctaText": "call-to-action"
}""",
    "PromoVideoProps": """{
  "hookText": "accroche promo courte",
  "plants": [
    {"emoji": "🌿", "name": "Nom plante", "description": "1 bénéfice", "price": "X,XX€"},
    {"emoji": "🌿", "name": "Nom plante", "description": "1 bénéfice", "price": "X,XX€"},
    {"emoji": "🌿", "name": "Nom plante", "description": "1 bénéfice", "price": "X,XX€"}
  ],
  "ctaText": "call-to-action urgence"
}""",
}


def _generate_voiceover_ai_sync(composition_id: str, feedback: str = "") -> dict:
    from google import genai
    from google.genai import types as gtypes

    existing_props = extract_post_props(composition_id, VIDEO_ASSETS_PATH)
    is_new = not existing_props

    memory = read_agent_memory(OBSIDIAN_VAULT_PATH)
    memory_block   = f"\nCONTRAINTES MÉMOIRE (respecte-les à la lettre) :\n{memory}\n" if memory else ""
    feedback_block = f"\nFEEDBACK UTILISATEUR (applique ces corrections) :\n{feedback}\n" if feedback else ""

    if is_new:
        calendar_files = find_calendar_files(OBSIDIAN_VAULT_PATH)
        cal_ctx = "\n".join(f["content"] for f in calendar_files[:2])[:3000] if calendar_files else ""
        calendar_block = f"\nCALENDRIER ÉDITORIAL :\n{cal_ctx}\n" if cal_ctx else ""
        schemas_desc = "\n\n".join(f"{k} :\n{v}" for k, v in _VOICEOVER_SCHEMAS.items())
        prompt = f"""Tu es expert en contenu vidéo court pour ZenAquatique ({STORE_NICHE}).
Voix de marque : {BRAND_VOICE} | Cible : {TARGET_AUDIENCE}
{memory_block}{calendar_block}{feedback_block}
Génère un script pour la vidéo du {composition_id}. Choisis le template le plus adapté au calendrier.

Schemas disponibles :
{schemas_desc}

Réponds UNIQUEMENT en JSON valide :
{{
  "template_type": "VersusVideoProps|EducatifVideoProps|PromoVideoProps",
  "props": {{ ... props complets selon le template choisi ... }}
}}"""
    else:
        template_type = existing_props.get("template_type", "")
        schema = _VOICEOVER_SCHEMAS.get(template_type, "")
        vault = read_obsidian_vault(OBSIDIAN_VAULT_PATH)
        vault_block   = f"\nCONTEXTE MARQUE :\n{vault[:6000]}\n" if vault else ""
        current_block = f"\nSCRIPT ACTUEL :\n{generate_voiceover(existing_props)}\n"
        prompt = f"""Tu es expert en contenu vidéo court pour ZenAquatique ({STORE_NICHE}).
Voix de marque : {BRAND_VOICE} | Cible : {TARGET_AUDIENCE}
{vault_block}{memory_block}{current_block}{feedback_block}
Génère un NOUVEAU script pour la vidéo {composition_id} (template : {template_type}).
Textes COURTS : hookText max 8 mots, items max 6 mots. Respecte STRICTEMENT les contraintes mémoire.

Réponds UNIQUEMENT en JSON valide avec ce schéma exact :
{schema}"""

    client = genai.Client(api_key=GOOGLE_API_KEY)
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=gtypes.GenerateContentConfig(response_mime_type="application/json", temperature=0.85),
    )
    try:
        raw = json.loads(resp.text.strip())
        if is_new:
            template_type = raw.get("template_type", "")
            new_props = raw.get("props", {})
            if not template_type or not new_props:
                raise ValueError("Réponse incomplète")
            new_props["template_type"] = template_type
        else:
            new_props = raw
            new_props["template_type"] = template_type
        new_props["composition_id"] = composition_id
        return {
            "status": "success",
            "composition_id": composition_id,
            "props": new_props,
            "voiceover": generate_voiceover(new_props),
            "is_new": is_new,
        }
    except Exception as exc:
        return {"status": "error", "error": f"Réponse Gemini invalide : {exc}", "raw": resp.text[:500]}


@app.post("/api/generate-voiceover-ai")
async def api_generate_voiceover_ai(request: Request):
    body = await request.json()
    composition_id = body.get("composition_id", "").strip()
    feedback = body.get("feedback", "").strip()
    if not composition_id:
        raise HTTPException(400, "composition_id manquant")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor, _generate_voiceover_ai_sync, composition_id, feedback
    )
    if result.get("status") == "error":
        raise HTTPException(500, result["error"])
    return result


def _text_to_props_sync(script_text: str, composition_id: str, template_type: str) -> dict:
    """Convertit un script texte libre en props structurés via Gemini."""
    from google import genai
    from google.genai import types as gtypes

    schema = _VOICEOVER_SCHEMAS.get(template_type, "")
    if not schema:
        return {"status": "error", "error": f"Template '{template_type}' non supporté"}

    memory = read_agent_memory(OBSIDIAN_VAULT_PATH)
    memory_block = f"\nCONTRAINTES MÉMOIRE (respecte-les) :\n{memory}\n" if memory else ""

    prompt = f"""Tu es expert en contenu vidéo court pour ZenAquatique ({STORE_NICHE}).
{memory_block}
Voici un script rédigé par l'utilisateur pour la vidéo {composition_id} (template : {template_type}) :

---
{script_text}
---

Convertis ce script en JSON valide correspondant exactement à ce schéma :
{schema}

Respecte l'intention et le contenu du script. Textes courts (hookText max 8 mots, items max 6 mots).
Réponds UNIQUEMENT en JSON valide, sans markdown ni explication."""

    client = genai.Client(api_key=GOOGLE_API_KEY)
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=gtypes.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.3,
        ),
    )
    try:
        props = json.loads(resp.text.strip())
        props["template_type"] = template_type
        props["composition_id"] = composition_id
        return {"status": "success", "props": props}
    except Exception:
        return {"status": "error", "error": "Réponse Gemini invalide", "raw": resp.text[:500]}


@app.post("/api/approve-voiceover")
async def api_approve_voiceover(request: Request):
    body = await request.json()
    composition_id = body.get("composition_id", "").strip()
    script_text = body.get("script_text", "").strip()
    template_type = body.get("template_type", "").strip()

    if not composition_id:
        raise HTTPException(400, "composition_id manquant")

    if script_text and template_type:
        # Convert free-text script to structured props via Gemini
        loop = asyncio.get_event_loop()
        conversion = await loop.run_in_executor(
            _executor, _text_to_props_sync, script_text, composition_id, template_type
        )
        if conversion.get("status") == "error":
            raise HTTPException(500, conversion.get("error", "Conversion échouée"))
        props = conversion["props"]
    else:
        props = body.get("props", {})
        if not props:
            raise HTTPException(400, "script_text+template_type ou props requis")

    result = update_post_props(composition_id, VIDEO_ASSETS_PATH, props)
    if result.get("status") == "error" and "introuvable" in result.get("error", ""):
        result = create_post_composition(composition_id, VIDEO_ASSETS_PATH, props)
    return result


# ─── API — Rendu Remotion ────────────────────────────────────────────────────

def _render_sync(composition_id: str) -> dict:
    return render_video(composition_id, VIDEO_ASSETS_PATH, f"{composition_id}.mp4")


@app.post("/api/render-video")
async def api_render_video(request: Request):
    body = await request.json()
    composition_id = body.get("composition_id", "").strip()
    if not composition_id:
        raise HTTPException(400, "composition_id manquant")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _render_sync, composition_id)
    if result.get("status") == "error":
        raise HTTPException(500, result["error"])
    return result


@app.get("/api/post-script/{composition_id}")
async def api_post_script(composition_id: str):
    props = extract_post_props(composition_id, VIDEO_ASSETS_PATH)
    if not props:
        raise HTTPException(404, f"Composition '{composition_id}' introuvable dans Root.tsx")
    voiceover = generate_voiceover(props)
    return {"composition_id": composition_id, "props": props, "voiceover": voiceover}


@app.get("/api/rendered-videos")
async def api_rendered_videos():
    return list_rendered_videos(VIDEO_ASSETS_PATH)


# ─── API — Script vidéo ───────────────────────────────────────────────────────

_REMOTION_TEMPLATE_HINTS = {
    "Top3": (
        "Format Top3 (TikTokOrganic ~13s) : présente 3 plantes/produits en rafale. "
        "Chaque 'slot' = 1 produit avec son nom + bénéfice clé + prix. Rythme ultra-rapide. "
        "Script en 3 blocs : Slot1 / Slot2 / Slot3 + CTA final."
    ),
    "Concept": (
        "Format Concept (ConceptVideo-ZenAquatique 30s) : storytelling de marque. "
        "Accroche émotionnelle → problème du viewer → solution ZenAquatique → preuve → CTA. "
        "Ton chaleureux, voix off posée."
    ),
    "Educatif": (
        "Format Educatif (EducatifVideo-ZenAquatique 20s) : 3 conseils / erreurs / étapes. "
        "Structure : Intro question → Conseil 1 → Conseil 2 → Conseil 3 → CTA. "
        "Texte à l'écran court pour chaque conseil."
    ),
    "Versus": (
        "Format Versus (VersusVideo-ZenAquatique 20s) : comparaison bouture vs pot / boutique vs animalerie. "
        "Structure : Versus intro → Option A (avantages) → Option B (avantages) → Verdict ZenAquatique → CTA. "
        "Ton factuel et convaincant."
    ),
    "Promo": (
        "Format Promo (PromoVideo-ZenAquatique 16s) : 3 plantes en promotion week-end. "
        "Ultra direct : offre + prix barré + prix promo + urgence (weekend only). "
        "Chaque plante = 1 slide rapide. CTA : 'Commande avant dimanche'."
    ),
}


def _generate_video_script_sync(topic: str, platform: str, duration: str,
                                 template: str = "", remotion: str = "") -> dict:
    from google import genai
    from google.genai import types as gtypes

    vault_content = read_obsidian_vault(OBSIDIAN_VAULT_PATH)
    assets = list_video_assets(VIDEO_ASSETS_PATH)
    asset_list = "\n".join(f"  - [{a['type']}] {a['name']}" for a in assets) if assets else "  (aucun asset trouvé)"

    platform_tips = {
        "tiktok":    "TikTok : accroche dans les 3 premières secondes, rythme rapide, texte à l'écran très court",
        "instagram": "Instagram Reels : esthétique soignée, transitions fluides, CTA clair en fin",
        "facebook":  "Facebook : sous-titres obligatoires (60 % visionnés sans son), CTA avec lien boutique",
    }

    template_hint = _REMOTION_TEMPLATE_HINTS.get(template, "")
    template_section = f"\n\nTEMPLATE REMOTION SÉLECTIONNÉ — {template} ({remotion}) :\n{template_hint}" if template_hint else ""
    vault_section = f"\n\nVAULT OBSIDIAN (connaissances marque et calendrier) :\n{vault_content}" if vault_content else ""
    assets_section = f"\n\nASSETS DISPONIBLES dans le dossier vidéo :\n{asset_list}"

    prompt = f"""Tu es expert en création de contenu vidéo courts pour {STORE_NAME} ({STORE_NICHE}).
Voix de marque : {BRAND_VOICE}
Cible : {TARGET_AUDIENCE}
Plateforme : {platform_tips.get(platform, platform.upper())}
{template_section}{vault_section}{assets_section}

Crée un script vidéo COMPLET adapté au template ci-dessus (durée : {duration}).
Sujet / brief : {topic or 'Choisis le produit le plus pertinent depuis le calendrier éditorial ou les analytics'}

Respecte STRICTEMENT la structure du template (nombre de slots, durée, rythme).
Réponds UNIQUEMENT en JSON valide avec cette structure :
{{
  "hook": "Accroche (3 premières secondes — ce qui stoppe le scroll)",
  "script": "Script complet structuré selon le template — mot à mot, slot par slot",
  "subtitles": ["sous-titre ligne 1", "sous-titre ligne 2", "..."],
  "visuals": "Description précise des plans / visuels à filmer ou à insérer dans Remotion",
  "cta": "Call-to-action final",
  "caption": "Légende complète du post avec emojis",
  "hashtags": ["#hashtag1", "#hashtag2"],
  "remotion_notes": "Notes spécifiques pour configurer le template Remotion (textes des slots, couleurs, musique suggérée…)"
}}"""

    client = genai.Client(api_key=GOOGLE_API_KEY)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=gtypes.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.8,
        ),
    )
    raw = response.text.strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


@app.post("/api/video-script")
async def api_video_script(request: Request):
    body = await request.json()
    topic    = body.get("topic", "")
    platform = body.get("platform", "facebook")
    duration = body.get("duration", "30-60 secondes")
    template = body.get("template", "")
    remotion = body.get("remotion", "")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor, _generate_video_script_sync, topic, platform, duration, template, remotion
    )
    return result


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "healthy", "store": STORE_NAME}


# ─── Planificateur automatique ───────────────────────────────────────────────

def _scheduled_job():
    if _agent_state["status"] == "running":
        return
    logger.info("=== Routine automatique déclenchée ===")
    _executor.submit(_run_agent_sync, "Routine marketing quotidienne automatique")

_scheduler = BackgroundScheduler(timezone="Europe/Paris")
_scheduler.add_job(
    _scheduled_job,
    CronTrigger(hour=POSTING_HOUR, minute=POSTING_MINUTE, timezone="Europe/Paris"),
    id="routine_quotidienne",
    replace_existing=True,
)
_scheduler.start()
logger.info("Planificateur démarré — routine automatique à %02d:%02d", POSTING_HOUR, POSTING_MINUTE)


# ─── Entrée ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
