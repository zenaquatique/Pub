import os
import json
import google.generativeai as genai

_model = None


def _get_model():
    global _model
    if _model is None:
        genai.configure(api_key=os.environ.get('GEMINI_API_KEY'))
        _model = genai.GenerativeModel('gemini-1.5-flash')
    return _model


def _ask(prompt):
    return _get_model().generate_content(prompt).text.strip()


SHOPIFY_SENDERS = {'mailer@shopify.com', 'no-reply@shopify.com', 'notifications@shopify.com'}

_DEFAULT = {'is_client': False, 'category': 'other', 'priority': 'normal', 'summary': ''}


def classify_email(from_email, from_name, subject, body):
    if from_email and from_email.lower() in SHOPIFY_SENDERS:
        return {'is_client': True, 'category': 'order_inquiry', 'priority': 'normal', 'summary': subject or ''}

    results = classify_emails_batch([{
        'from_email': from_email, 'from_name': from_name,
        'subject': subject, 'body': body
    }])
    return results[0] if results else dict(_DEFAULT)


def classify_emails_batch(emails):
    if not emails:
        return []

    items = []
    for i, e in enumerate(emails):
        items.append(
            f"[{i}] De: {e.get('from_name','')} <{e.get('from_email','')}> | "
            f"Objet: {e.get('subject','')} | Corps: {e.get('body','')[:300]}"
        )

    prompt = f"""Analyse ces {len(emails)} emails reçus par une boutique Shopify.
Pour chacun, détermine:
- is_client: true si c'est un client ou notification Shopify liée à une commande/client
- category: "order_inquiry"|"support"|"complaint"|"return_request"|"shipping"|"product_question"|"newsletter"|"spam"|"other"
- priority: "high" si urgent/réclamation, "normal" sinon, "low" pour newsletters/spam
- summary: résumé 1 phrase courte (vide si pas client)

EMAILS:
{chr(10).join(items)}

Réponds UNIQUEMENT avec un tableau JSON valide de {len(emails)} objets dans l'ordre:
[{{"is_client": bool, "category": string, "priority": string, "summary": string}}, ...]"""

    try:
        text = _ask(prompt)
        text = text.replace('```json', '').replace('```', '').strip()
        results = json.loads(text)
        if isinstance(results, list) and len(results) == len(emails):
            return results
    except Exception:
        pass
    return [dict(_DEFAULT) for _ in emails]


def generate_response(email, business_context=''):
    context = business_context or 'une boutique Shopify'
    prompt = f"""Tu es un assistant SAV pour {context}. \
Génère une réponse professionnelle et chaleureuse pour cet email.

DE: {email.get('from_name', '')} <{email.get('from_email', '')}>
OBJET: {email.get('subject', '')}
MESSAGE: {email.get('body', '')[:2000]}
RÉSUMÉ: {email.get('summary', '')}
CATÉGORIE: {email.get('category', 'other')}

Règles:
- Réponds dans la langue du client
- Sois professionnel mais humain et chaleureux
- Réponds directement à sa demande
- Si besoin d'infos (numéro de commande, etc.), demande-les poliment
- Pas de placeholders comme [NOM], [DATE] — écris une réponse complète
- 3 à 5 paragraphes maximum
- Termine par une formule de politesse

Génère UNIQUEMENT le texte de la réponse, rien d'autre:"""

    return _ask(prompt)


def generate_daily_summary(emails):
    if not emails:
        return "Aucun email à résumer pour aujourd'hui."

    lines = []
    for e in emails[:60]:
        tag = 'CLIENT' if e.get('is_client') else 'autre'
        lines.append(
            f"- [{tag}] {e.get('from_name') or e.get('from_email', '?')} | "
            f"{e.get('subject', '?')} | {e.get('category', '?')} | "
            f"répondu: {'oui' if e.get('response') and e['response'].get('status') == 'sent' else 'non'}"
        )

    prompt = f"""Fais un récapitulatif journalier structuré de ces emails pour un gérant de boutique Shopify.

EMAILS DU JOUR:
{chr(10).join(lines)}

Structure le récap ainsi:
📊 **Statistiques**
(nombre total, nombre clients, nombre répondus)

🔴 **Priorités — à traiter aujourd'hui**
(emails clients urgents sans réponse)

📦 **Activité clients**
(résumé des types de demandes clients)

📰 **Autres emails**
(newsletters, divers)

✅ **Actions effectuées**
(réponses déjà envoyées)

Réponds en français, sois concis et actionnable."""

    return _ask(prompt)
