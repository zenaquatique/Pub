"""Tableau de bord web — contrôle complet de l'agent marketing."""
import asyncio
import hashlib
import hmac
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from agent import execute_pending_action, _load_pending_actions, PENDING_ACTIONS_FILE
from config import (
    META_APP_SECRET, META_WEBHOOK_VERIFY_TOKEN, STORE_NAME,
    POSTING_HOUR, POSTING_MINUTE, POSTING_TIMEZONE,
    OBSIDIAN_VAULT_PATH, VIDEO_ASSETS_PATH,
    STORE_NICHE, BRAND_VOICE, TARGET_AUDIENCE,
    ANTHROPIC_API_KEY, CLAUDE_SCRIPT_MODEL,
    GROQ_API_KEY, GROQ_MODEL, CONTENT_RULES,
    OPENAI_API_KEY, OPENAI_MODEL,
)
from tools.customer import (
    get_pending_messages,
    log_customer_message,
    mark_replied,
    send_facebook_reply,
    send_instagram_reply,
)
from tools.knowledge import find_calendar_files, read_obsidian_vault, list_video_assets, read_agent_memory, append_agent_memory, read_local_context
from tools.remotion import (
    render_video, list_rendered_videos,
    extract_post_props, generate_voiceover, date_to_composition_id,
    update_post_props, create_post_composition, repair_root_tsx,
    delete_composition, list_src_files, read_project_file, scan_register_root,
    normalize_root_tsx,
)
from tools.shopify import get_products, get_store_analytics
from tools.social import post_video_to_facebook, post_reels_to_instagram, post_video_to_tiktok

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
_executor = ThreadPoolExecutor(max_workers=4)

# Jobs Instagram en arrière-plan { job_id -> résultat }
_publish_jobs: dict = {}

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
  "hookText": "10-14 mots — 2 phrases : contexte accrocheur + bénéfice clé ZenAquatique. Ex: 'Ces plantes vont transformer ton aquarium. Cultivées en France, livrées vivantes chez toi.'",
  "hookEmoji": "1 emoji aquatique pertinent",
  "tips": [
    {
      "num": "01",
      "title": "2-4 mots CONCRETS (ex: 'Dès 0,99€', 'Made in France', 'Boutures garanties')",
      "desc": "14-18 mots — 2 phrases : argument principal avec chiffre ou fait + détail engageant. Ex: 'Des boutures françaises à partir de 0,99€, fraîches et garanties vivantes à réception. L'aquarium de tes rêves à petit prix.'"
    },
    {
      "num": "02",
      "title": "2-4 mots CONCRETS",
      "desc": "14-18 mots — 2 phrases avec argument ZenAquatique précis (origine, livraison, qualité…)"
    },
    {
      "num": "03",
      "title": "2-4 mots CONCRETS",
      "desc": "14-18 mots — 2 phrases avec argument ZenAquatique précis"
    }
  ],
  "ctaText": "10-14 mots — 2 phrases : appel à l'action fort + zen-aquatique.fr. Ex: 'Crée l'aquarium de tes rêves dès aujourd'hui. Le lien est en bio, sur zen-aquatique.fr.'"
}""",
    "PromoVideoProps": """{
  "hookText": "10-14 mots — 2 phrases : accroche + angle de la sélection. Ex: 'Ces 3 plantes font le sol de ton aquarium. L'avant-plan qui change tout dans un aquascape.'",
  "plants": [
    {"emoji": "🌿", "name": "Nom précis (latin + commun si possible)", "description": "12-15 mots — 2 phrases : effet visuel ou bénéfice principal + usage. Ex: 'Un tapis dense et vert éclatant, incontournable en aquascape. Idéal pour couvrir l'avant-plan.'", "price": "X,XX€"},
    {"emoji": "🌿", "name": "Nom précis (latin + commun si possible)", "description": "12-15 mots — 2 phrases : effet visuel ou bénéfice + usage", "price": "X,XX€"},
    {"emoji": "🌿", "name": "Nom précis (latin + commun si possible)", "description": "12-15 mots — 2 phrases : effet visuel ou bénéfice + usage", "price": "X,XX€"}
  ],
  "ctaText": "10-14 mots — 2 phrases : appel à l'action + zen-aquatique.fr. Ex: 'Crée l'avant-plan parfait dès aujourd'hui. Le lien est en bio, sur zen-aquatique.fr.'"
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


def _llm_chat_json(messages: list, temperature: float = 0.7, max_tokens: int = 2048) -> str:
    """Appelle Groq en JSON; bascule automatiquement sur OpenAI si rate-limitée (429)."""
    if GROQ_API_KEY:
        try:
            from groq import Groq
            resp = Groq(api_key=GROQ_API_KEY).chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content
        except Exception as exc:
            is_429 = "429" in str(exc) or getattr(exc, "status_code", None) == 429
            if not is_429:
                raise
            logger.warning("Groq rate-limitée (429) → bascule sur OpenAI")

    if not OPENAI_API_KEY:
        raise RuntimeError(
            "Limite quotidienne Groq atteinte et OPENAI_API_KEY absent du .env — "
            "attends ~24h ou ajoute ta clé OpenAI dans le fichier .env"
        )

    import requests as _req
    r = _req.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": OPENAI_MODEL,
            "messages": messages,
            "response_format": {"type": "json_object"},
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    r.raise_for_status()
    logger.info("Fallback OpenAI utilisé (Groq rate-limited)")
    return r.json()["choices"][0]["message"]["content"]


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

        vault     = read_obsidian_vault(OBSIDIAN_VAULT_PATH)
        memory    = read_agent_memory(OBSIDIAN_VAULT_PATH)
        local_ctx = read_local_context()
        combined  = (local_ctx + "\n" + vault).strip()

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

{f"CONNAISSANCES MARQUE :{chr(10)}{combined[:8000]}" if combined else ""}

{f"CONTRAINTES MÉMOIRE — OBLIGATOIRES :{chr(10)}{memory}" if memory else ""}

MISSION : Tu génères des scripts vidéo qui vendent et engagent. Tes scripts doivent :
- Mettre en avant les vrais bénéfices des produits ZenAquatique (plantes, crevettes, équipements…)
- Utiliser un langage naturel, dynamique, proche du client — pas du jargon marketing creux
- Contenir de vraies phrases complètes pour la voix off (pas juste des mots-clés)
- Donner envie d'acheter ou de suivre la boutique
- Respecter TOUTES les contraintes mémoire et les interdits listés en début de prompt"""

        user_msg = (
            f"Sujet : {cal_entry or f'Post ZenAquatique du {composition_id}'}\n"
            f"Template : {template_type}\n"
            f"{f'FEEDBACK : {feedback}' if feedback else ''}\n\n"
            f"Génère les overlays visuels selon ce schéma exact :\n{schema}\n\n"
            f"⏱ RYTHME VOIX OFF = 3,5 mots/seconde (respecter absolument) :\n"
            f"  • hookText : 10-14 MOTS — 2 phrases courtes\n"
            f"  • chaque tip title : 2-4 mots concrets (affiché à l'écran, pas lu)\n"
            f"  • chaque tip desc : 14-18 MOTS — 2 phrases vendeuses\n"
            f"  • ctaText : 10-14 MOTS — 2 phrases (action + zen-aquatique.fr)\n\n"
            f"RÈGLES QUALITÉ — OBLIGATOIRES :\n"
            f"  1. hookText = 2 vraies phrases avec verbe fort\n"
            f"     ✅ 'Ces plantes vont transformer ton aquarium. Cultivées en France, livrées vivantes chez toi.'\n"
            f"     ❌ 'Paysage aquatique' / 'Découvrez nos plantes !'\n"
            f"  2. tip title = SPÉCIFIQUE AU SUJET — nom de plante, conseil précis, caractéristique unique\n"
            f"     ✅ (sujet plantes) : 'Micranthemum Monte Carlo' / 'Rotala H'ra' / 'Bucephalandra'\n"
            f"     ✅ (sujet conseil) : 'Sans CO2' / '8h de lumière max' / 'Substrat nutritif'\n"
            f"     ❌ JAMAIS : 'Dès 0,99€' / 'Made in France' / 'Livrées fraîches' en titre\n"
            f"        (ces arguments vont dans les descriptions ou le CTA)\n"
            f"  3. tip desc = 2 phrases avec fait concret + 1 argument ZenAquatique\n"
            f"     ✅ 'Tapis vert dense, idéal pour l'avant-plan en aquascape. Cultivée en France, dès 2,99€.'\n"
            f"     ❌ 'Des boutures de qualité à partir de 0,99€, fraîches garanties vivantes.'\n"
            f"  4. ctaText = impératif + zen-aquatique.fr en 2 phrases"
        )

        ai_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        def _call_claude(messages_list):
            with ai_client.messages.stream(
                model=CLAUDE_SCRIPT_MODEL,
                max_tokens=2000,
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

        msg      = _call_claude([{"role": "user", "content": user_msg}])
        raw_text = next((b.text for b in msg.content if getattr(b, "type", "") == "text"), "").strip()
        props    = _parse_raw(raw_text)
        if not isinstance(props, dict):
            props = {}
        t_type   = props.pop("template_type", template_type)

        # Filtre : retry si mots interdits dans les props
        props_text = json.dumps(props, ensure_ascii=False)
        for _attempt in range(3):
            violations = _check_voiceover(props_text)
            if not violations:
                break
            logger.warning("[Claude] Mots interdits dans props (%s) — retry %d/3", violations, _attempt + 1)
            msg2 = _call_claude([{"role": "user", "content": _retry_prompt(user_msg, violations)}])
            raw2 = next((b.text for b in msg2.content if getattr(b, "type", "") == "text"), "").strip()
            try:
                props2 = _parse_raw(raw2)
                if isinstance(props2, dict) and props2:
                    props      = props2
                    props_text = json.dumps(props, ensure_ascii=False)
            except Exception:
                pass

        props["template_type"]  = t_type
        props["composition_id"] = composition_id

        # Voiceover = lecture synchronisée des props (toujours en accord avec la vidéo)
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
        if feedback or force_reset or context:
            existing_props = {}
        else:
            existing_props = extract_post_props(composition_id, VIDEO_ASSETS_PATH)
        is_new = not existing_props

        vault        = read_obsidian_vault(OBSIDIAN_VAULT_PATH)
        memory       = read_agent_memory(OBSIDIAN_VAULT_PATH)
        local_ctx    = read_local_context()
        combined     = (local_ctx + "\n" + vault).strip()
        vault_block  = f"\nCONNAISSANCES MARQUE :\n{combined[:8000]}\n" if combined else ""
        memory_block = f"\nCONTRAINTES MÉMOIRE (obligatoires) :\n{memory}\n" if memory else ""
        fb_block     = f"\nRETOUR UTILISATEUR : {feedback}\n" if feedback else ""

        if is_new:
            cal_entry, template_type = _build_cal_entry(composition_id, context)
        else:
            template_type = existing_props.get("template_type", "EducatifVideoProps")
            cal_entry = ""

        subject = cal_entry or f"Post ZenAquatique du {composition_id}"
        schema  = _VOICEOVER_SCHEMAS.get(template_type, _VOICEOVER_SCHEMAS["EducatifVideoProps"])

        sys_base = (
            f"Tu travailles pour ZenAquatique (zen-aquatique.fr), boutique française de plantes aquatiques.\n"
            f"Ton : {BRAND_VOICE} | Audience : {TARGET_AUDIENCE}\n"
            f"{memory_block}{vault_block}"
            f"\n{CONTENT_RULES}\n"
        )

        # ── Appel unique : génère les props visuels (contenu de la vidéo) ──────────
        props_prompt = (
            f"Sujet : {subject}\nTemplate : {template_type}\n{fb_block}\n"
            f"Génère les overlays visuels selon ce schéma exact.\n\n"
            f"⏱ RYTHME VOIX OFF = 3,5 mots/seconde :\n"
            f"  • hookText : 10-14 mots — 2 phrases courtes\n"
            f"  • tip title : 2-4 mots SPÉCIFIQUES AU SUJET (affiché à l'écran)\n"
            f"  • tip desc  : 14-18 mots — 2 phrases précises\n"
            f"  • ctaText   : 10-14 mots — action + zen-aquatique.fr\n\n"
            f"RÈGLES QUALITÉ — OBLIGATOIRES :\n"
            f"  1. hookText = 2 phrases avec verbe fort, liées au sujet\n"
            f"     ✅ 'Ces 3 plantes font le sol de ton aquarium. L'avant-plan qui change tout dans un aquascape.'\n"
            f"     ❌ 'Transforme ton aquarium avec des plantes fraîches. Cultivées en France pour toi.'\n\n"
            f"  2. tip title = SPÉCIFIQUE AU SUJET — nom de plante, conseil précis, caractéristique unique\n"
            f"     ✅ (sujet plantes) : 'Micranthemum Monte Carlo' / 'Rotala H'ra' / 'Bucephalandra'\n"
            f"     ✅ (sujet conseil) : 'Sans CO2' / '8h de lumière max' / 'Substrat nutritif'\n"
            f"     ❌ JAMAIS ces titres génériques : 'Dès 0,99€' / 'Made in France' / 'Livrées fraîches'\n"
            f"        (ces arguments vont dans la desc ou le CTA, PAS dans les titres)\n\n"
            f"  3. tip desc = 2 phrases avec fait concret lié au sujet + 1 argument ZenAquatique\n"
            f"     ✅ 'Tapis vert dense, idéal pour couvrir le sol en aquascape. Cultivée en France, dès 2,99€.'\n"
            f"     ❌ 'Des boutures de qualité à partir de 0,99€, fraîches garanties vivantes.'\n\n"
            f"  4. ctaText = impératif + zen-aquatique.fr en 2 phrases\n\n"
            f"Schéma :\n{schema}"
        )

        try:
            props = json.loads(_llm_chat_json(
                messages=[
                    {"role": "system", "content": sys_base + "\nRéponds UNIQUEMENT en JSON valide selon le schéma."},
                    {"role": "user",   "content": props_prompt},
                ],
                temperature=0.7, max_tokens=2048,
            ))
            if not isinstance(props, dict):
                props = {}
        except Exception:
            props = {}

        # ── Filtre : retry si mots interdits dans les props ───────────────────────
        props_text = json.dumps(props, ensure_ascii=False)
        for _attempt in range(3):
            violations = _check_voiceover(props_text)
            if not violations:
                break
            logger.warning("[LLM] Mots interdits dans props (%s) — retry %d/3", violations, _attempt + 1)
            try:
                props2 = json.loads(_llm_chat_json(
                    messages=[
                        {"role": "system", "content": sys_base + "\nRéponds UNIQUEMENT en JSON valide."},
                        {"role": "user",   "content": _retry_prompt(props_prompt, violations)},
                    ],
                    temperature=0.5, max_tokens=2048,
                ))
                if isinstance(props2, dict) and props2:
                    props      = props2
                    props_text = json.dumps(props, ensure_ascii=False)
            except Exception:
                break

        props["template_type"]  = template_type
        props["composition_id"] = composition_id

        voiceover = generate_voiceover(props)

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
def _write_props_to_roots(composition_id: str, props: dict) -> None:
    """Écrit les props dans Root.tsx (crée la composition si absente). Silencieux en cas d'erreur."""
    try:
        res = update_post_props(composition_id, VIDEO_ASSETS_PATH, props)
        if res.get("status") == "error" and "introuvable" in res.get("error", ""):
            create_post_composition(composition_id, VIDEO_ASSETS_PATH, props)
    except Exception:
        logger.exception("Erreur écriture Root.tsx pour %s", composition_id)


@app.post("/api/script")
async def api_script(request: Request):
    body = await request.json()
    composition_id = body.get("composition_id", "").strip()
    feedback = body.get("feedback", "").strip()
    context  = body.get("context", "").strip()
    if not composition_id:
        raise HTTPException(400, "composition_id manquant")
    (SCRIPTS_DIR / f"{composition_id}.json").unlink(missing_ok=True)
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        _executor, _generate_voiceover_ai_sync, composition_id, feedback, True, context
    )
    if result.get("status") == "error":
        raise HTTPException(500, result["error"])
    # Écrit immédiatement dans Root.tsx — ce que l'utilisateur voit = ce qui est dans Root.tsx
    props = result.get("props")
    if props:
        await loop.run_in_executor(_executor, _write_props_to_roots, composition_id, props)
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

    try:
        props = json.loads(_llm_chat_json(
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
            temperature=0.3,
            max_tokens=2048,
        ))
        props["template_type"] = template_type
        props["composition_id"] = composition_id
        return {"status": "success", "props": props}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def _voiceover_to_props_sync(composition_id: str, voiceover: str, template_type: str) -> dict:
    """Génère les props visuels depuis le texte voix off affiché dans l'UI."""
    schema = _VOICEOVER_SCHEMAS.get(template_type, _VOICEOVER_SCHEMAS["EducatifVideoProps"])
    prompt_sys = (
        f"Tu extrais les overlays visuels d'une vidéo ZenAquatique depuis un script voix off.\n"
        f"{CONTENT_RULES}\n"
        "Réponds UNIQUEMENT en JSON valide selon le schéma. Textes courts (hookText max 7 mots tirés du script)."
    )
    prompt_user = (
        f"Script voix off :\n\"\"\"\n{voiceover}\n\"\"\"\n\n"
        f"Template : {template_type}\n"
        "Génère les props visuels qui illustrent EXACTEMENT ce script "
        "(mêmes plantes, même accroche, même CTA).\n"
        f"Schéma :\n{schema}"
    )
    try:
        if ANTHROPIC_API_KEY:
            import anthropic
            msg = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY).messages.create(
                model=CLAUDE_SCRIPT_MODEL, max_tokens=2000,
                system=prompt_sys,
                messages=[{"role": "user", "content": prompt_user}],
            )
            raw = next((b.text for b in msg.content if getattr(b, "type", "") == "text"), "").strip()
            if "```" in raw:
                for part in raw.split("```"):
                    s = part.strip().lstrip("json").strip()
                    if s.startswith("{"):
                        raw = s; break
            props = json.loads(raw)
        else:
            props = json.loads(_llm_chat_json(
                messages=[
                    {"role": "system", "content": prompt_sys},
                    {"role": "user",   "content": prompt_user},
                ],
                temperature=0.3, max_tokens=2048,
            ))
        props["template_type"]  = template_type
        props["composition_id"] = composition_id
        return {"status": "success", "props": props}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@app.post("/api/approve-voiceover")
async def api_approve_voiceover(request: Request):
    """Dérive les props depuis le voiceover affiché, écrit Root.tsx et rend la vidéo."""
    body = await request.json()
    composition_id = body.get("composition_id", "").strip()
    voiceover_text = body.get("voiceover", "").strip()
    if not composition_id:
        raise HTTPException(400, "composition_id manquant")

    cached = _load_script(composition_id)

    # Si le voiceover est fourni (texte affiché dans l'UI), on re-dérive les props depuis lui
    if voiceover_text:
        template_type = (cached.get("props") or {}).get("template_type", "EducatifVideoProps")
        loop = asyncio.get_event_loop()
        pres = await loop.run_in_executor(
            _executor, _voiceover_to_props_sync, composition_id, voiceover_text, template_type
        )
        if pres.get("status") == "error":
            raise HTTPException(500, f"Erreur génération props : {pres['error']}")
        props = pres["props"]
        # Met à jour le cache avec les nouveaux props + voiceover
        _save_script(composition_id, {**cached, "props": props, "voiceover": voiceover_text, "status": "success"})
    else:
        props = cached.get("props")
        if not props:
            props = extract_post_props(composition_id, VIDEO_ASSETS_PATH)
        if not props:
            raise HTTPException(400, f"Aucun script pour '{composition_id}'. Clique d'abord sur 'Script IA'.")

    # Écriture Root.tsx
    result = update_post_props(composition_id, VIDEO_ASSETS_PATH, props)
    if result.get("status") == "error" and "introuvable" in result.get("error", ""):
        result = create_post_composition(composition_id, VIDEO_ASSETS_PATH, props)
    if result.get("status") not in ("success", "created"):
        raise HTTPException(500, result.get("error", "Erreur écriture Root.tsx"))

    # Rendu vidéo
    loop = asyncio.get_event_loop()
    render_result = await loop.run_in_executor(_executor, _render_sync, composition_id)
    if render_result.get("status") == "error":
        raise HTTPException(500, render_result["error"])

    return {**render_result, "root_tsx_updated": True}


# ─── API — Rendu Remotion ────────────────────────────────────────────────────

def _render_sync(composition_id: str) -> dict:
    return render_video(composition_id, VIDEO_ASSETS_PATH, f"{composition_id}.mp4")


def _get_post_schedule(composition_id: str):
    """Retourne la datetime UTC planifiée (si > 10 min dans le futur), sinon None."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo  # Python < 3.9
    try:
        year  = int(composition_id[0:4])
        month = int(composition_id[4:6])
        day   = int(composition_id[6:8])
        tz    = ZoneInfo(POSTING_TIMEZONE)
        local_dt = datetime(year, month, day, POSTING_HOUR, POSTING_MINUTE, tzinfo=tz)
        utc_dt   = local_dt.astimezone(timezone.utc)
        now      = datetime.now(timezone.utc)
        return utc_dt if (utc_dt - now).total_seconds() > 600 else None
    except Exception:
        return None


def _generate_social_captions_sync(composition_id: str) -> dict:
    """Génère des légendes IA pour Facebook, Instagram et TikTok depuis les props."""
    try:
        cached = _load_script(composition_id)
        props  = cached.get("props") or {}
        if not props:
            try:
                props = extract_post_props(composition_id, VIDEO_ASSETS_PATH) or {}
            except Exception:
                props = {}
    except Exception:
        cached = {}
        props  = {}

    voiceover = cached.get("voiceover", "").strip()
    hook      = props.get("hookText", "")
    tips      = props.get("tips", [])
    plants    = props.get("plants", [])
    cta       = props.get("ctaText", "")

    # Construit un résumé structuré de la vidéo
    content_parts = []
    if voiceover:
        content_parts.append(f"=== NARRATION COMPLÈTE DE LA VIDÉO ===\n{voiceover}\n=== FIN NARRATION ===")
    if hook:
        content_parts.append(f"Accroche visuelle : {hook}")
    for t in tips:
        content_parts.append(f"Conseil {t.get('num','')} — {t.get('title','')} : {t.get('desc','')}")
    for p in plants:
        content_parts.append(f"Plante mise en avant : {p.get('name','')} — {p.get('description','')} — {p.get('price','')}")
    if cta:
        content_parts.append(f"Appel à l'action : {cta}")

    if not content_parts:
        content_parts.append("Plantes aquatiques ZenAquatique — cultivées en France, dès 0,99€")

    content_summary = "\n\n".join(content_parts)

    prompt = f"""Tu es le social media manager de ZenAquatique (zen-aquatique.fr).
{CONTENT_RULES}

Voici le script de la vidéo :
---
{content_summary}
---

EXEMPLE de ce qu'on attend (pour une autre vidéo) :
Facebook  → "🌿 La Cryptocoryne, c'est la plante parfaite pour débuter. Elle pousse sans CO2, s'adapte à tous les aquariums et reste belle des années. Cultivée en France, livrée fraîche chez toi dès 1,49€. 👉 zen-aquatique.fr"
Instagram → "La plante des débutants qui ne meurt pas 🌿\nCryptocoryne française • sans CO2 • dès 1,49€\n🔗 Lien en bio — zen-aquatique.fr\n#aquarium #aquascape #plantesaquatiques #zenaquatique"
TikTok    → "Tu galères avec tes plantes aquatiques ? 🌿 La Cryptocoryne pousse toute seule, même sans CO2. Dès 1,49€ sur zen-aquatique.fr 👉\n#aquarium #zenaquatique #plantesaquatiques"

Maintenant écris les 3 légendes pour LA VIDÉO CI-DESSUS.
Même style : naturel, court, une idée forte, pas de copie du script.

Hashtags Instagram à inclure : #aquarium #aquascape #plantesaquatiques #aquariophilie #zenaquatique #aquariumfrance #boutures #aquascaping #aquascapefrance #aquariumplants #freshwateraquarium #plantedtank #aquariumhobby #aquaticplants #aquariumlife
Hashtags TikTok à inclure : #aquarium #aquascape #zenaquatique #plantesaquatiques #aquariumtiktok #aquascapefrance #aquariophilie #plantedtank

Réponds UNIQUEMENT en JSON :
{{"facebook": "...", "instagram": "...", "tiktok": "..."}}"""

    _h = hook or "Plantes aquatiques cultivées en France"
    fallback_fb = f"🌿 {_h}\n\nDès 0,99€, livrées fraîches et garanties vivantes. Cultivées en France avec passion.\n\n👉 zen-aquatique.fr"
    fallback_ig = f"🌿 {_h}\nDès 0,99€ • Cultivées en France • Livrées fraîches\n🔗 Lien en bio — zen-aquatique.fr\n\n#aquarium #aquascape #plantesaquatiques #zenaquatique #aquariophilie"
    fallback_tt = f"🌿 {_h} — dès 0,99€, livrées fraîches ! 👉 zen-aquatique.fr\n#aquarium #aquascape #zenaquatique #plantesaquatiques"

    try:
        data = json.loads(_llm_chat_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=2000,
        ))
        if all(k in data for k in ("facebook", "instagram", "tiktok")):
            return data
    except Exception as exc:
        logger.error("Erreur génération légendes sociales: %s", exc)

    return {"facebook": fallback_fb, "instagram": fallback_ig, "tiktok": fallback_tt}


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


@app.get("/api/caption/{composition_id}")
async def api_caption(composition_id: str):
    """Génère les légendes IA pour Facebook, Instagram et TikTok."""
    loop      = asyncio.get_event_loop()
    captions  = await loop.run_in_executor(_executor, _generate_social_captions_sync, composition_id)
    scheduled = _get_post_schedule(composition_id)
    return {
        "captions": captions,
        "scheduled_at": scheduled.isoformat() if scheduled else None,
        "publishes_now": scheduled is None,
    }


@app.get("/api/debug-video/{composition_id}")
async def api_debug_video(composition_id: str):
    out_dir = Path(VIDEO_ASSETS_PATH) / "out"
    day, month = composition_id[6:8], composition_id[4:6]
    files_in_out = []
    if out_dir.exists():
        files_in_out = [f.name for f in out_dir.iterdir() if f.is_file()]
    selected = _find_video(composition_id)
    return {
        "VIDEO_ASSETS_PATH": VIDEO_ASSETS_PATH,
        "out_dir": str(out_dir),
        "out_dir_exists": out_dir.exists(),
        "files_in_out": sorted(files_in_out),
        "looking_for": [f"{day}-{month}.mp4", f"{day}-{month}.MP4", f"{day}-{month}.mov"],
        "selected_video": selected,
    }
async def api_caption(composition_id: str):
    """Génère les légendes IA pour Facebook, Instagram et TikTok."""
    loop       = asyncio.get_event_loop()
    captions   = await loop.run_in_executor(_executor, _generate_social_captions_sync, composition_id)
    scheduled  = _get_post_schedule(composition_id)
    return {
        "captions": captions,
        "scheduled_at": scheduled.isoformat() if scheduled else None,
        "publishes_now": scheduled is None,
    }


@app.get("/api/debug-env")
async def api_debug_env():
    """Vérifie quelles variables .env sont chargées (valeurs masquées)."""
    import os
    from pathlib import Path as _Path

    env_file = _Path(__file__).parent / ".env"
    vars_to_check = [
        "META_USER_TOKEN", "META_PAGE_TOKEN", "META_PAGE_ID",
        "META_IG_ACCOUNT_ID", "META_APP_ID", "META_APP_SECRET",
        "GROQ_API_KEY", "TIKTOK_ACCESS_TOKEN",
        "CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET",
    ]
    result = {}
    for v in vars_to_check:
        val = os.environ.get(v, "")
        if val:
            result[v] = f"✅ {val[:6]}…({len(val)} chars)"
        else:
            result[v] = "❌ VIDE"

    return {
        "env_file_exists": env_file.exists(),
        "env_file_path": str(env_file),
        "variables": result,
    }


@app.get("/api/repair-root-tsx")
async def api_repair_root_tsx():
    """Supprime les balises <Composition> dupliquées dans Root.tsx."""
    result = repair_root_tsx(VIDEO_ASSETS_PATH)
    return result


@app.get("/api/normalize-root-tsx")
async def api_normalize_root_tsx():
    """Convertit les <Composition> multi-lignes en single-line pour corriger le bug Remotion."""
    result = normalize_root_tsx(VIDEO_ASSETS_PATH)
    return result


@app.delete("/api/composition/{composition_id}")
async def api_delete_composition(composition_id: str):
    """Supprime une composition de Root.tsx (const + tag). Régénère ensuite le script."""
    result = delete_composition(composition_id, VIDEO_ASSETS_PATH)
    if result.get("status") == "error":
        raise HTTPException(500, result["error"])
    return result


@app.get("/api/delete-composition/{composition_id}")
async def api_delete_composition_get(composition_id: str):
    """Supprime une composition via GET (utilisable directement depuis le navigateur)."""
    result = delete_composition(composition_id, VIDEO_ASSETS_PATH)
    if result.get("status") == "error":
        raise HTTPException(500, result["error"])
    return result


@app.get("/api/debug-src-files")
async def api_debug_src_files():
    """Liste les fichiers TypeScript du projet Remotion pour détecter des compositions en doublon."""
    files = list_src_files(VIDEO_ASSETS_PATH)
    return {"src_files": files, "count": len(files)}


@app.get("/api/debug-src-search/{composition_id}")
async def api_debug_src_search(composition_id: str):
    """Cherche un ID de composition dans TOUS les fichiers src du projet Remotion."""
    import re as _re
    from pathlib import Path as _Path
    src = _Path(VIDEO_ASSETS_PATH) / "src"
    if not src.exists():
        return {"error": "Dossier src introuvable"}
    results = []
    for f in sorted(src.rglob("*")):
        if not f.is_file():
            continue
        try:
            content = f.read_text(encoding="utf-8", errors="ignore")
            if composition_id in content:
                hits = []
                for i, line in enumerate(content.splitlines(), 1):
                    if composition_id in line:
                        hits.append({"line": i, "content": line.strip()})
                results.append({"file": f.name, "hits": hits})
        except Exception:
            pass
    return {"composition_id": composition_id, "found_in": results}


@app.get("/api/debug-root-tsx")
async def api_debug_root_tsx():
    """Affiche tous les IDs de compositions trouvés dans Root.tsx."""
    import re as _re
    from pathlib import Path as _Path
    from collections import Counter
    tsx = _Path(VIDEO_ASSETS_PATH) / "src" / "Root.tsx"
    if not tsx.exists():
        return {"error": "Root.tsx introuvable", "path": str(tsx)}
    content = tsx.read_text(encoding="utf-8", errors="ignore")
    ids = _re.findall(r'id="(\d{8})"', content)
    counts = Counter(ids)
    duplicates = {k: v for k, v in counts.items() if v > 1}

    # Extrait les lignes contenant un ID pour inspection visuelle
    lines_with_id = []
    for i, line in enumerate(content.splitlines(), 1):
        if _re.search(r'\d{8}', line):
            lines_with_id.append({"line": i, "content": line.strip()})

    return {
        "all_ids": ids,
        "total_compositions": len(ids),
        "duplicates": duplicates,
        "has_duplicates": bool(duplicates),
        "lines_with_8digit_ids": lines_with_id,
    }


@app.get("/api/debug-read-src/{filepath:path}")
async def api_debug_read_src(filepath: str):
    """Lit le contenu brut d'un fichier dans le projet Remotion (chemin relatif à la racine)."""
    result = read_project_file(VIDEO_ASSETS_PATH, filepath)
    if result["status"] == "error":
        raise HTTPException(404, result["error"])
    return result


@app.get("/api/debug-scan-register-root")
async def api_debug_scan_register_root():
    """Scanne tous les fichiers JS/TS pour trouver registerRoot et les balises <Composition>."""
    return scan_register_root(VIDEO_ASSETS_PATH)


@app.get("/api/debug-root-tsx-content/{composition_id}")
async def api_debug_root_tsx_content(composition_id: str):
    """Retourne les 10 lignes autour d'un ID dans Root.tsx pour vérification visuelle."""
    from pathlib import Path as _Path
    tsx = _Path(VIDEO_ASSETS_PATH) / "src" / "Root.tsx"
    if not tsx.exists():
        return {"error": "Root.tsx introuvable"}
    content = tsx.read_text(encoding="utf-8", errors="ignore")
    lines = content.splitlines()
    results = []
    for i, line in enumerate(lines):
        if composition_id in line:
            start = max(0, i - 5)
            end = min(len(lines), i + 6)
            results.append({
                "match_line": i + 1,
                "context": [{"line": j + 1, "content": lines[j]} for j in range(start, end)],
            })
    return {"composition_id": composition_id, "occurrences": results, "count": len(results)}


def _find_video(composition_id: str) -> str | None:
    """Cherche uniquement la vidéo finale montée (DD-MM). Jamais le rendu Remotion brut."""
    out_dir = Path(VIDEO_ASSETS_PATH) / "out"
    day, month = composition_id[6:8], composition_id[4:6]
    for p in [
        out_dir / f"{day}-{month}.mp4",
        out_dir / f"{day}-{month}.MP4",
        out_dir / f"{day}-{month}.mov",
    ]:
        if p.exists():
            return str(p)
    return None


def _run_instagram_bg(job_id: str, video_path: str, caption: str, scheduled_at):
    """Tâche longue Instagram — poll côté Meta jusqu'à FINISHED (2-5 min)."""
    _publish_jobs[job_id] = {"status": "processing", "message": "Traitement vidéo côté Meta…"}
    result = post_reels_to_instagram(video_path, caption, scheduled_at)
    _publish_jobs[job_id] = result


@app.post("/api/publish-video/{composition_id}")
async def api_publish_video(
    composition_id: str, request: Request, background_tasks: BackgroundTasks
):
    body     = await request.json()
    platform = body.get("platform", "facebook").lower()
    caption  = body.get("caption", "").strip()

    video_path = _find_video(composition_id)
    if not video_path:
        out_dir = Path(VIDEO_ASSETS_PATH) / "out"
        raise HTTPException(404, f"Aucune vidéo trouvée dans {out_dir}")

    if not caption:
        caption = "🌿 Plantes aquatiques cultivées en France, livrées fraîches. Dès 0,99€. 👉 zen-aquatique.fr"

    scheduled_at = _get_post_schedule(composition_id)
    loop = asyncio.get_event_loop()

    if platform == "facebook":
        result = await loop.run_in_executor(
            _executor, post_video_to_facebook, video_path, caption, "", scheduled_at
        )
        if result.get("status") == "error":
            raise HTTPException(500, result["error"])
        return result

    elif platform == "instagram":
        import uuid
        job_id = uuid.uuid4().hex
        _publish_jobs[job_id] = {"status": "processing", "message": "Upload Cloudinary en cours…"}
        background_tasks.add_task(_run_instagram_bg, job_id, video_path, caption, scheduled_at)
        return {"status": "processing", "job_id": job_id, "platform": "instagram"}

    elif platform == "tiktok":
        result = await loop.run_in_executor(
            _executor, post_video_to_tiktok, video_path, caption
        )
        if result.get("status") == "error":
            raise HTTPException(500, result["error"])
        return result

    else:
        raise HTTPException(400, f"Plateforme inconnue : {platform}")


@app.get("/api/publish-status/{job_id}")
async def api_publish_status(job_id: str):
    """Retourne l'état d'un job de publication en arrière-plan."""
    job = _publish_jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Job inconnu")
    return job


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


def _regen_props_sync(composition_id: str, feedback: str) -> dict:
    """Regénère uniquement les props visuels (overlays) en gardant le voiceover intact."""
    cached = _load_script(composition_id)
    if not cached.get("props"):
        return {"status": "error", "error": "Aucun script en cache — génère d'abord le script."}

    template_type = cached["props"].get("template_type", "EducatifVideoProps")
    schema = _VOICEOVER_SCHEMAS.get(template_type, _VOICEOVER_SCHEMAS["EducatifVideoProps"])
    memory = read_agent_memory(OBSIDIAN_VAULT_PATH)
    memory_block = f"\nCONTRAINTES MÉMOIRE :\n{memory}\n" if memory else ""

    prompt_sys = (
        f"Tu modifies les overlays visuels d'une vidéo ZenAquatique.\n"
        f"{memory_block}\n{CONTENT_RULES}\n"
        "Réponds UNIQUEMENT en JSON valide selon le schéma fourni. Textes courts (hookText max 7 mots)."
    )
    prompt_user = (
        f"Props actuelles :\n{json.dumps(cached['props'], ensure_ascii=False, indent=2)}\n\n"
        f"Instructions de modification : {feedback}\n\n"
        f"Schéma à respecter :\n{schema}\n\n"
        "Génère les nouvelles props en appliquant les modifications demandées."
    )

    try:
        if ANTHROPIC_API_KEY:
            import anthropic
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            msg = client.messages.create(
                model=CLAUDE_SCRIPT_MODEL, max_tokens=2000,
                system=prompt_sys,
                messages=[{"role": "user", "content": prompt_user}],
            )
            raw = next((b.text for b in msg.content if getattr(b, "type", "") == "text"), "").strip()
            if "```" in raw:
                for part in raw.split("```"):
                    s = part.strip().lstrip("json").strip()
                    if s.startswith("{"):
                        raw = s; break
            new_props = json.loads(raw)
        else:
            from groq import Groq
            resp = Groq(api_key=GROQ_API_KEY).chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": prompt_sys},
                    {"role": "user",   "content": prompt_user},
                ],
                response_format={"type": "json_object"},
                temperature=0.6, max_tokens=2000,
            )
            new_props = json.loads(resp.choices[0].message.content)
    except Exception as exc:
        return {"status": "error", "error": str(exc)}

    new_props["template_type"]  = template_type
    new_props["composition_id"] = composition_id

    updated = {**cached, "props": new_props}
    _save_script(composition_id, updated)
    return {"status": "success", "props": new_props, "voiceover": cached.get("voiceover", "")}


@app.post("/api/props/{composition_id}")
async def api_regen_props(composition_id: str, request: Request):
    """Regénère les overlays visuels sans toucher au voiceover."""
    body = await request.json()
    feedback = body.get("feedback", "").strip()
    if not feedback:
        raise HTTPException(400, "feedback manquant")
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(_executor, _regen_props_sync, composition_id, feedback)
    if result.get("status") == "error":
        raise HTTPException(500, result["error"])
    return result


@app.get("/api/video/{filename}")
async def api_serve_video(filename: str):
    """Sert un fichier MP4 depuis le dossier out/ du projet Remotion."""
    from fastapi.responses import FileResponse
    # Sécurité : nom de fichier seulement, pas de traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(400, "Nom de fichier invalide")
    video_path = Path(VIDEO_ASSETS_PATH) / "out" / filename
    if not video_path.exists():
        raise HTTPException(404, f"Vidéo introuvable : {video_path}")
    return FileResponse(str(video_path), media_type="video/mp4")


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
    logger.info("=== DÉMARRAGE v2.1 — endpoint props: /api/props/{id} ===")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
