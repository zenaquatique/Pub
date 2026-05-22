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
    ANTHROPIC_API_KEY, CLAUDE_SCRIPT_MODEL,
    GROQ_API_KEY, GROQ_MODEL, CONTENT_RULES,
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
SCRIPTS_DIR  = Path(__file__).parent / "data" / "scripts"

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


# ─── Cache de scripts générés ─────────────────────────────────────────────────

def _save_script(composition_id: str, data: dict) -> None:
    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    (SCRIPTS_DIR / f"{composition_id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_script(composition_id: str) -> dict:
    p = SCRIPTS_DIR / f"{composition_id}.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


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

# Purge les entrées de cache générées depuis Root.tsx (sans IA) au démarrage
def _purge_root_tsx_cache() -> None:
    if not SCRIPTS_DIR.exists():
        return
    for f in SCRIPTS_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if data.get("source") == "root_tsx":
                f.unlink()
        except Exception:
            pass

_purge_root_tsx_cache()

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

# ── Filtre post-génération partagé ────────────────────────────────────────────

_BANNED_WORDS = [
    "pesticide", "traitement", "traitée", "traitées", "traité", "traités",
    "2 semaines", "deux semaines",
    "meurent", "mourir", "condamné", "dépéri",
    "animalerie", "animaleries",
    "importées d'asie", "importé d'asie", "importées d'asie",
    "concurrent", "concurrente",
]

def _check_voiceover(text: str) -> list[str]:
    """Retourne la liste des mots interdits trouvés dans le texte."""
    low = text.lower()
    return [w for w in _BANNED_WORDS if w in low]

def _retry_prompt(original_user_msg: str, violations: list[str]) -> str:
    return (
        f"{original_user_msg}\n\n"
        f"⛔ SCRIPT REFUSÉ — mots interdits détectés : {', '.join(violations)}\n"
        f"Ces mots sont BANNIS même en contexte positif (même 'sans pesticides' est interdit).\n\n"
        f"NOUVELLE TENTATIVE — Structure imposée :\n"
        f"1. Accroche sur la beauté visuelle des plantes ZenAquatique\n"
        f"2. Argument prix (à partir de 0,99€)\n"
        f"3. Cultivées en France, livraison rapide\n"
        f"4. Facilité d'entretien / passion aquariophile\n"
        f"5. CTA : commande sur zen-aquatique.fr\n\n"
        f"N'écris QUE ces 5 points. Zéro comparaison, zéro mention de concurrents, "
        f"zéro mention de plantes qui meurent ou de traitements chimiques."
    )

def _detect_template(text: str) -> str:
    """Déduit le template Remotion depuis un texte (ligne calendrier ou context)."""
    tl = text.lower()
    if "⚔" in text or "versus" in tl:
        return "VersusVideoProps"
    if "🔥" in text or "promo" in tl or "%" in text:
        return "PromoVideoProps"
    return "EducatifVideoProps"


def _generate_voiceover_ai_sync(
    composition_id: str,
    feedback: str = "",
    force_reset: bool = False,
    context: str = "",
) -> dict:
    if ANTHROPIC_API_KEY:
        return _generate_with_claude(composition_id, feedback, force_reset, context)
    if GROQ_API_KEY:
        return _generate_with_groq(composition_id, feedback, force_reset, context)
    return {"status": "error", "error": "Aucune clé API configurée. Ajoutez GROQ_API_KEY dans le fichier .env"}


def _build_cal_entry(composition_id: str, context: str) -> tuple[str, str]:
    """Retourne (cal_entry, detected_template). Utilise context si fourni, sinon cherche dans la vault."""
    if context:
        return context, _detect_template(context)
    calendar_files = find_calendar_files(OBSIDIAN_VAULT_PATH)
    _FR = {1:"jan",2:"fév",3:"mar",4:"avr",5:"mai",6:"jun",
           7:"jul",8:"aoû",9:"sep",10:"oct",11:"nov",12:"déc"}
    day_i   = int(composition_id[6:8])
    month_s = _FR.get(int(composition_id[4:6]), "")
    for cf in calendar_files[:3]:
        for line in cf["content"].split("\n"):
            if str(day_i) in line and month_s in line.lower():
                return line.strip(), _detect_template(line)
    return "", "EducatifVideoProps"


def _generate_with_claude(
    composition_id: str,
    feedback: str,
    force_reset: bool,
    context: str,
) -> dict:
    try:
        import anthropic

        if feedback or force_reset or context:
            existing_props = {}
        else:
            existing_props = extract_post_props(composition_id, VIDEO_ASSETS_PATH)
        is_new = not existing_props

        vault  = read_obsidian_vault(OBSIDIAN_VAULT_PATH)
        memory = read_agent_memory(OBSIDIAN_VAULT_PATH)

        if is_new:
            cal_entry, template_type = _build_cal_entry(composition_id, context)
        else:
            template_type = existing_props.get("template_type", "EducatifVideoProps")
            cal_entry = ""

        schema = _VOICEOVER_SCHEMAS.get(template_type, _VOICEOVER_SCHEMAS["EducatifVideoProps"])

        system_prompt = f"""{CONTENT_RULES}

---
Tu es le créateur de contenu vidéo de ZenAquatique, boutique en ligne spécialisée dans les plantes aquatiques, crevettes et équipements d'aquariophilie.

MARQUE : {STORE_NAME} | NICHE : {STORE_NICHE}
VOIX : {BRAND_VOICE}
AUDIENCE : {TARGET_AUDIENCE}

{f"CONNAISSANCES MARQUE (vault Obsidian) :{chr(10)}{vault[:8000]}" if vault else ""}

{f"CONTRAINTES MÉMOIRE — OBLIGATOIRES :{chr(10)}{memory}" if memory else ""}

MISSION : Tu génères des scripts vidéo qui vendent et engagent. Tes scripts doivent :
- Mettre en avant les vrais bénéfices des produits ZenAquatique (plantes, crevettes, équipements…)
- Utiliser un langage naturel, dynamique, proche du client — pas du jargon marketing creux
- Contenir de vraies phrases complètes pour la voix off (pas juste des mots-clés)
- Donner envie d'acheter ou de suivre la boutique
- Respecter TOUTES les contraintes mémoire et les interdits listés en début de prompt"""

        if is_new:
            user_msg = f"""Crée le script vidéo pour le post {composition_id}.

POST DU CALENDRIER : {cal_entry or f"Post ZenAquatique du {composition_id}"}
TEMPLATE : {template_type}
{f"FEEDBACK : {feedback}" if feedback else ""}

Génère un JSON avec cette structure exacte :
{{
  "template_type": "{template_type}",
  "props": {schema},
  "voiceover": "Script voix off COMPLET en vraies phrases commerciales.\\nStructuré par section : [ACCROCHE] ... [CORPS] ... [CTA] ...\\nPhrases entières, bénéfices concrets, ton dynamique."
}}

RÈGLES props :
- hookText : accroche percutante max 8 mots qui stoppe le scroll
- Tous les champs remplis avec du vrai contenu ZenAquatique (plantes, crevettes, aquarium)
- items/tips/desc : phrases courtes mais complètes (sujet + verbe + bénéfice)

RÈGLES voiceover :
- Vraies phrases, pas juste des mots-clés
- Minimum 5-8 phrases en tout
- Arguments de vente concrets : prix, facilité d'entretien, beauté, livraison, etc.
- RAPPEL : respecte les INTERDITS ABSOLUS du system prompt — aucune mention de pesticides, aucune allégation sur la durée de vie des plantes concurrentes"""
        else:
            current_vo = generate_voiceover(existing_props)
            user_msg = f"""Améliore le script du post {composition_id} (template : {template_type}).

SCRIPT ACTUEL :
{current_vo}

{f"FEEDBACK : {feedback}" if feedback else "Génère une nouvelle version plus percutante."}

Génère un JSON avec cette structure :
{{
  "template_type": "{template_type}",
  "props": {schema},
  "voiceover": "Nouveau script voix off COMPLET avec vraies phrases commerciales."
}}"""

        ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        def _call_claude(messages_list):
            with ai_client.messages.stream(
                model=CLAUDE_SCRIPT_MODEL,
                max_tokens=3000,
                system=system_prompt,
                messages=messages_list,
            ) as stream:
                return stream.get_final_message()

        def _parse_raw(raw: str):
            if "```" in raw:
                for part in raw.split("```"):
                    s = part.strip()
                    if s.startswith("json"):
                        s = s[4:].strip()
                    if s.startswith("{"):
                        raw = s
                        break
            return json.loads(raw)

        msg = _call_claude([{"role": "user", "content": user_msg}])
        raw_text = next(
            (b.text for b in msg.content if getattr(b, "type", "") == "text"), ""
        ).strip()

        data      = _parse_raw(raw_text)
        props     = data.get("props", data)
        voiceover = data.get("voiceover", "")
        t_type    = data.get("template_type", template_type)

        # ── Filtre : retry si mots interdits détectés (jusqu'à 3 fois) ──
        for _attempt in range(3):
            violations = _check_voiceover(voiceover)
            if not violations:
                break
            logger.warning("[Claude] Mots interdits (%s) — retry %d/3", violations, _attempt + 1)
            retry_msg = _retry_prompt(user_msg, violations)
            msg2 = _call_claude([{"role": "user", "content": retry_msg}])
            raw2 = next(
                (b.text for b in msg2.content if getattr(b, "type", "") == "text"), ""
            ).strip()
            try:
                data2     = _parse_raw(raw2)
                props     = data2.get("props", props)
                voiceover = data2.get("voiceover", voiceover)
                t_type    = data2.get("template_type", t_type)
            except Exception:
                pass

        props["template_type"]  = t_type
        props["composition_id"] = composition_id

        if not voiceover:
            voiceover = generate_voiceover(props)

        result = {
            "status": "success",
            "composition_id": composition_id,
            "props": props,
            "voiceover": voiceover,
            "is_new": is_new,
            "model": "claude",
        }
        _save_script(composition_id, result)
        return result

    except Exception as exc:
        logger.exception("Erreur génération Claude — fallback Groq")
        return _generate_with_groq(composition_id, feedback, force_reset, context)


def _generate_with_groq(
    composition_id: str,
    feedback: str,
    force_reset: bool,
    context: str,
) -> dict:
    try:
        from groq import Groq

        if feedback or force_reset or context:
            existing_props = {}
        else:
            existing_props = extract_post_props(composition_id, VIDEO_ASSETS_PATH)
        is_new = not existing_props

        vault  = read_obsidian_vault(OBSIDIAN_VAULT_PATH)
        memory = read_agent_memory(OBSIDIAN_VAULT_PATH)
        vault_block  = f"\nCONNAISSANCES MARQUE :\n{vault[:6000]}\n" if vault else ""
        memory_block = f"\nCONTRAINTES MÉMOIRE (obligatoires) :\n{memory}\n" if memory else ""
        fb_block     = f"\nRETOUR UTILISATEUR : {feedback}\n" if feedback else ""

        if is_new:
            cal_entry, template_type = _build_cal_entry(composition_id, context)
        else:
            template_type = existing_props.get("template_type", "EducatifVideoProps")
            cal_entry = ""

        subject = cal_entry or f"Post ZenAquatique du {composition_id}"
        schema  = _VOICEOVER_SCHEMAS.get(template_type, _VOICEOVER_SCHEMAS["EducatifVideoProps"])
        client  = Groq(api_key=GROQ_API_KEY)

        # ── Appel 1 : props JSON (overlays visuels courts) ──
        resp_props = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": (
                    f"Tu es le créateur de contenu vidéo de ZenAquatique, boutique spécialisée plantes aquatiques et crevettes.\n"
                    f"Voix : {BRAND_VOICE} | Audience : {TARGET_AUDIENCE}\n"
                    f"{memory_block}{vault_block}"
                    f"\n{CONTENT_RULES}\n\n"
                    "Réponds UNIQUEMENT en JSON valide selon le schéma fourni. "
                    "Textes courts (hookText max 7 mots), accrocheurs, tous les champs remplis avec du contenu ZenAquatique réel."
                )},
                {"role": "user", "content": (
                    f"Crée les textes d'overlay vidéo pour : {subject}\n"
                    f"Template : {template_type}\n"
                    f"{fb_block}\n"
                    f"Schéma JSON exact :\n{schema}"
                )},
            ],
            response_format={"type": "json_object"},
            temperature=0.75,
            max_tokens=2048,
        )
        try:
            props = json.loads(resp_props.choices[0].message.content)
            if not isinstance(props, dict):
                props = {}
        except Exception:
            props = {}

        # ── Appel 2 : voiceover texte libre (monologue commercial continu) ──
        resp_vo = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": (
                    f"Tu es la voix off de ZenAquatique (zen-aquatique.fr), boutique française de plantes aquatiques et crevettes.\n"
                    f"Ton : {BRAND_VOICE} | Audience : {TARGET_AUDIENCE}\n"
                    f"{memory_block}{vault_block}"
                    f"\n{CONTENT_RULES}\n\n"
                    "RÈGLES DE FORMAT :\n"
                    "• Monologue CONTINU — aucun titre, aucun timestamp, aucun 'Titre affiché'\n"
                    "• Vraies phrases complètes (sujet + verbe + bénéfice concret)\n"
                    "• Minimum 10 phrases, 80 mots minimum\n"
                    "• Mentionne : beauté visuelle, facilité d'entretien, qualité française, livraison rapide\n"
                    "• Ton enthousiaste et naturel\n"
                    "• Termine par un CTA : 'Commande sur zen-aquatique.fr'\n"
                    "Écris UNIQUEMENT le texte à lire, sans titre ni explication."
                )},
                {"role": "user", "content": (
                    f"Écris le script voix off pour : {subject}\n"
                    f"Type : {template_type}\n"
                    f"{fb_block}"
                )},
            ],
            temperature=0.9,
            max_tokens=2048,
        )
        vo_user_msg = (
            f"Écris le script voix off pour : {subject}\n"
            f"Type : {template_type}\n"
            f"{fb_block}"
        )
        vo_messages = [
            {"role": "system", "content": (
                f"Tu es la voix off de ZenAquatique (zen-aquatique.fr), boutique française de plantes aquatiques et crevettes.\n"
                f"Ton : {BRAND_VOICE} | Audience : {TARGET_AUDIENCE}\n"
                f"{memory_block}{vault_block}"
                f"\n{CONTENT_RULES}\n\n"
                "RÈGLES DE FORMAT :\n"
                "• Monologue CONTINU — aucun titre, aucun timestamp\n"
                "• Vraies phrases complètes, minimum 10 phrases, 80 mots minimum\n"
                "• Ton enthousiaste et naturel\n"
                "• Termine par un CTA : 'Commande sur zen-aquatique.fr'\n"
                "Écris UNIQUEMENT le texte à lire, sans titre ni explication."
            )},
            {"role": "user", "content": vo_user_msg},
        ]

        resp_vo = client.chat.completions.create(
            model=GROQ_MODEL, messages=vo_messages, temperature=0.9, max_tokens=2048,
        )
        voiceover = resp_vo.choices[0].message.content.strip() if resp_vo.choices else ""

        # ── Filtre : retry si mots interdits détectés ──
        for _attempt in range(3):
            violations = _check_voiceover(voiceover)
            if not violations:
                break
            logger.warning("[Groq] Mots interdits détectés (%s) — retry %d/3", violations, _attempt + 1)
            retry_messages = vo_messages + [
                {"role": "assistant", "content": voiceover},
                {"role": "user", "content": _retry_prompt(vo_user_msg, violations)},
            ]
            resp_retry = client.chat.completions.create(
                model=GROQ_MODEL, messages=retry_messages, temperature=0.7, max_tokens=2048,
            )
            voiceover = resp_retry.choices[0].message.content.strip() if resp_retry.choices else voiceover

        if voiceover.startswith('"') and voiceover.endswith('"'):
            voiceover = voiceover[1:-1]
        if not voiceover:
            voiceover = generate_voiceover(props) if props else ""

        props["template_type"]  = template_type
        props["composition_id"] = composition_id

        result = {
            "status": "success",
            "composition_id": composition_id,
            "props": props,
            "voiceover": voiceover,
            "is_new": is_new,
            "model": "groq",
        }
        _save_script(composition_id, result)
        return result

    except Exception as exc:
        logger.exception("Erreur _generate_with_groq")
        return {"status": "error", "error": str(exc)}


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


# POST /api/script — génère TOUJOURS un nouveau script (vide le cache d'abord)
@app.post("/api/script")
async def api_script(request: Request):
    body = await request.json()
    composition_id = body.get("composition_id", "").strip()
    feedback = body.get("feedback", "").strip()
    context  = body.get("context", "").strip()   # ligne calendrier envoyée par le frontend
    if not composition_id:
        raise HTTPException(400, "composition_id manquant")
    # Vider le cache
    (SCRIPTS_DIR / f"{composition_id}.json").unlink(missing_ok=True)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor, _generate_voiceover_ai_sync, composition_id, feedback, True, context
    )
    if result.get("status") == "error":
        raise HTTPException(500, result["error"])
    return result


@app.get("/api/script/{composition_id}")
async def api_get_script(composition_id: str):
    """Charge le script depuis le cache ou génère via IA."""
    cached = _load_script(composition_id)
    if cached.get("status") == "success":
        return cached
    # Aucun cache → génération IA
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor, _generate_voiceover_ai_sync, composition_id, "", False
    )
    if result.get("status") == "error":
        raise HTTPException(500, result["error"])
    return result


@app.delete("/api/script/{composition_id}")
async def api_delete_script(composition_id: str):
    """Vide le cache pour un post (forcer une regénération)."""
    cache_file = SCRIPTS_DIR / f"{composition_id}.json"
    if cache_file.exists():
        cache_file.unlink(missing_ok=True)
    return {"status": "cleared", "composition_id": composition_id}


def _text_to_props_sync(script_text: str, composition_id: str, template_type: str) -> dict:
    """Convertit un script texte libre en props structurés via Groq."""
    from groq import Groq

    schema = _VOICEOVER_SCHEMAS.get(template_type, "")
    if not schema:
        return {"status": "error", "error": f"Template '{template_type}' non supporté"}

    memory = read_agent_memory(OBSIDIAN_VAULT_PATH)
    memory_block = f"\nCONTRAINTES MÉMOIRE (respecte-les) :\n{memory}\n" if memory else ""

    client = Groq(api_key=GROQ_API_KEY)
    resp = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": (
                f"Tu es expert en contenu vidéo court pour ZenAquatique ({STORE_NICHE}).\n"
                f"{memory_block}"
                f"\n{CONTENT_RULES}\n\n"
                "Convertis les scripts en JSON selon le schéma exact. "
                "Textes courts : hookText max 8 mots, items max 6 mots. "
                "Réponds UNIQUEMENT en JSON valide."
            )},
            {"role": "user", "content": (
                f"Script pour la vidéo {composition_id} (template : {template_type}) :\n\n"
                f"---\n{script_text}\n---\n\n"
                f"Convertis en JSON selon ce schéma :\n{schema}"
            )},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=2048,
    )
    try:
        props = json.loads(resp.choices[0].message.content)
        props["template_type"] = template_type
        props["composition_id"] = composition_id
        return {"status": "success", "props": props}
    except Exception:
        raw = resp.choices[0].message.content if resp.choices else ""
        return {"status": "error", "error": "Réponse invalide", "raw": raw[:500]}


@app.post("/api/approve-voiceover")
async def api_approve_voiceover(request: Request):
    """Écrit Root.tsx depuis le cache de script et génère la vidéo."""
    body = await request.json()
    composition_id = body.get("composition_id", "").strip()
    if not composition_id:
        raise HTTPException(400, "composition_id manquant")

    # 1. Props depuis le cache
    cached = _load_script(composition_id)
    props = cached.get("props")

    # 2. Fallback : Root.tsx
    if not props:
        props = extract_post_props(composition_id, VIDEO_ASSETS_PATH)

    if not props:
        raise HTTPException(
            400,
            f"Aucun script pour '{composition_id}'. Clique d'abord sur 'Script IA'."
        )

    # 3. Écriture Root.tsx
    result = update_post_props(composition_id, VIDEO_ASSETS_PATH, props)
    if result.get("status") == "error" and "introuvable" in result.get("error", ""):
        result = create_post_composition(composition_id, VIDEO_ASSETS_PATH, props)
    if result.get("status") not in ("success", "created"):
        raise HTTPException(500, result.get("error", "Erreur écriture Root.tsx"))

    # 4. Rendu vidéo
    loop = asyncio.get_event_loop()
    render_result = await loop.run_in_executor(_executor, _render_sync, composition_id)
    if render_result.get("status") == "error":
        raise HTTPException(500, render_result["error"])

    return {**render_result, "root_tsx_updated": True}


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
    from groq import Groq

    vault_content = read_obsidian_vault(OBSIDIAN_VAULT_PATH)
    assets = list_video_assets(VIDEO_ASSETS_PATH)
    asset_list = "\n".join(f"  - [{a['type']}] {a['name']}" for a in assets) if assets else "  (aucun asset trouvé)"

    platform_tips = {
        "tiktok":    "TikTok : accroche dans les 3 premières secondes, rythme rapide, texte à l'écran très court",
        "instagram": "Instagram Reels : esthétique soignée, transitions fluides, CTA clair en fin",
        "facebook":  "Facebook : sous-titres obligatoires (60 % visionnés sans son), CTA avec lien boutique",
    }

    template_hint = _REMOTION_TEMPLATE_HINTS.get(template, "")

    client = Groq(api_key=GROQ_API_KEY)
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": (
                f"Tu es expert en création de contenu vidéo court pour {STORE_NAME} ({STORE_NICHE}).\n"
                f"Voix de marque : {BRAND_VOICE}\nCible : {TARGET_AUDIENCE}\n"
                f"{f'VAULT OBSIDIAN :{chr(10)}{vault_content[:6000]}' if vault_content else ''}\n"
                f"ASSETS DISPONIBLES :\n{asset_list}\n"
                f"\n{CONTENT_RULES}\n\n"
                "Réponds UNIQUEMENT en JSON valide avec les clés demandées."
            )},
            {"role": "user", "content": (
                f"Plateforme : {platform_tips.get(platform, platform.upper())}\n"
                f"{f'TEMPLATE — {template} ({remotion}) :{chr(10)}{template_hint}' if template_hint else ''}\n"
                f"Durée : {duration}\n"
                f"Sujet : {topic or 'Choisis le produit le plus pertinent depuis le calendrier éditorial'}\n\n"
                "Génère un script complet en JSON :\n"
                '{"hook":"accroche 3s","script":"script complet mot à mot",'
                '"subtitles":["ligne1","ligne2"],"visuals":"plans à filmer",'
                '"cta":"call-to-action","caption":"légende avec emojis",'
                '"hashtags":["#tag1"],"remotion_notes":"config Remotion"}'
            )},
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
        max_tokens=4096,
    )
    raw = response.choices[0].message.content if response.choices else ""
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
