import os
import re
import glob
from datetime import date, datetime

import requests as http_requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()

from flask import Flask, jsonify, redirect, render_template, request, session

import ai_service
import database
import gmail_service

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
os.environ.setdefault('OAUTHLIB_INSECURE_TRANSPORT', '1')

database.init_db()

_oauth_flow = None


# ── Pages ──────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    setup_needed = not os.path.exists('credentials.json')
    authenticated = os.path.exists('token.json')
    return render_template('index.html', setup_needed=setup_needed, authenticated=authenticated)


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.route('/auth/start')
def auth_start():
    if not os.path.exists('credentials.json'):
        return 'credentials.json manquant', 400
    global _oauth_flow
    _oauth_flow = gmail_service.create_flow()
    url, state = gmail_service.get_auth_url(_oauth_flow)
    session['oauth_state'] = state
    return redirect(url)


@app.route('/auth/callback')
def auth_callback():
    global _oauth_flow
    if _oauth_flow is None:
        return redirect('/')
    gmail_service.exchange_code(_oauth_flow, request.args.get('code'))
    _oauth_flow = None
    return redirect('/')


@app.route('/auth/status')
def auth_status():
    authenticated = os.path.exists('token.json')
    email = gmail_service.get_user_email() if authenticated else None
    return jsonify({'authenticated': authenticated, 'email': email})


@app.route('/auth/disconnect', methods=['POST'])
def auth_disconnect():
    if os.path.exists('token.json'):
        os.remove('token.json')
    return jsonify({'ok': True})


# ── Emails ─────────────────────────────────────────────────────────────────────

@app.route('/api/emails/sync', methods=['POST'])
def sync_emails():
    data = request.get_json(silent=True) or {}
    emails, error = gmail_service.fetch_emails(max_results=data.get('max_results', 50))
    if error:
        return jsonify({'error': error}), 400

    new_emails = [e for e in emails if not database.get_email_by_gmail_id(e['gmail_id'])]
    if new_emails:
        classifications = ai_service.classify_emails_batch(new_emails)
        for e, c in zip(new_emails, classifications):
            e.update(c)
            database.save_email(e)
    new_count = len(new_emails)

    return jsonify({'synced': new_count, 'total': len(emails)})


@app.route('/api/emails')
def get_emails():
    client_only = request.args.get('client_only') == 'true'
    important_only = request.args.get('important_only') == 'true'
    limit = int(request.args.get('limit', 100))
    emails = database.get_emails(client_only=client_only, important_only=important_only, limit=limit)
    for e in emails:
        e['response'] = database.get_response(e['id'])
    return jsonify(emails)


@app.route('/api/emails/<int:eid>')
def get_email(eid):
    e = database.get_email(eid)
    if not e:
        return jsonify({'error': 'Email introuvable'}), 404
    e['response'] = database.get_response(eid)
    return jsonify(e)


@app.route('/api/emails/<int:eid>/generate-response', methods=['POST'])
def generate_response(eid):
    e = database.get_email(eid)
    if not e:
        return jsonify({'error': 'Email introuvable'}), 404
    data = request.get_json(silent=True) or {}
    business_context = os.environ.get('BUSINESS_CONTEXT', '')
    knowledge_base = database.get_setting('knowledge_base')
    instructions = data.get('instructions', '')
    try:
        draft = ai_service.generate_response(e, business_context, knowledge_base=knowledge_base, instructions=instructions)
    except Exception as ex:
        return jsonify({'error': str(ex)}), 500
    rid = database.save_response(eid, draft)
    return jsonify({'response_id': rid, 'draft': draft})


@app.route('/api/emails/<int:eid>/read', methods=['POST'])
def mark_read(eid):
    database.update_email(eid, {'is_read': 1})
    return jsonify({'ok': True})


@app.route('/api/emails/<int:eid>/unread', methods=['POST'])
def mark_unread(eid):
    database.update_email(eid, {'is_read': 0})
    return jsonify({'ok': True})


@app.route('/api/emails/<int:eid>/toggle-important', methods=['POST'])
def toggle_important(eid):
    e = database.get_email(eid)
    if not e:
        return jsonify({'error': 'Email introuvable'}), 404
    database.update_email(eid, {'is_important': 0 if e['is_important'] else 1})
    return jsonify({'is_important': not e['is_important']})


@app.route('/api/emails/<int:eid>/toggle-client', methods=['POST'])
def toggle_client(eid):
    e = database.get_email(eid)
    if not e:
        return jsonify({'error': 'Email introuvable'}), 404
    database.update_email(eid, {'is_client': 0 if e['is_client'] else 1})
    return jsonify({'is_client': not e['is_client']})


@app.route('/api/emails/<int:eid>', methods=['DELETE'])
def delete_email(eid):
    database.delete_email(eid)
    return jsonify({'ok': True})


@app.route('/api/emails/<int:eid>/draft', methods=['POST'])
def save_draft(eid):
    data = request.get_json(silent=True) or {}
    draft = data.get('draft', '')
    rid = database.save_response(eid, draft)
    return jsonify({'response_id': rid})


@app.route('/api/emails/<int:eid>/unsubscribe', methods=['POST'])
def unsubscribe(eid):
    e = database.get_email(eid)
    if not e:
        return jsonify({'error': 'Email introuvable'}), 404
    link = e.get('unsubscribe_link')
    if not link:
        return jsonify({'error': 'Aucun lien de désabonnement trouvé'}), 400

    database.update_email(eid, {'unsubscribed': 1})

    # For mailto: unsubscribe, send an empty email via Gmail API
    if link.startswith('mailto:'):
        addr = link[7:].split('?')[0]
        gmail_service.send_email(addr, 'Unsubscribe', '')
        return jsonify({'ok': True, 'method': 'mailto', 'message': 'Email de désabonnement envoyé.'})

    return jsonify({'ok': True, 'method': 'link', 'url': link})


# ── Responses ──────────────────────────────────────────────────────────────────

@app.route('/api/responses/<int:rid>', methods=['PUT'])
def update_response(rid):
    data = request.get_json(silent=True) or {}
    updates = {k: data[k] for k in ('draft', 'status') if k in data}
    if updates:
        database.update_response(rid, updates)
    return jsonify({'ok': True})


@app.route('/api/responses/<int:rid>/send', methods=['POST'])
def send_response(rid):
    # Save latest draft if provided
    data = request.get_json(silent=True) or {}
    if 'draft' in data:
        database.update_response(rid, {'draft': data['draft']})

    row = database.get_response_by_id(rid)
    if not row:
        return jsonify({'error': 'Réponse introuvable'}), 404
    if row['status'] == 'sent':
        return jsonify({'error': 'Déjà envoyé'}), 400

    ok, result = gmail_service.send_email(
        to=row['from_email'],
        subject=row['subject'],
        body=row['draft'],
        thread_id=row['thread_id'],
        in_reply_to=row.get('message_id_header'),
    )
    if ok:
        database.update_response(rid, {'status': 'sent', 'sent_at': datetime.utcnow().isoformat()})
        return jsonify({'ok': True})
    return jsonify({'error': str(result)}), 500


# ── Import ─────────────────────────────────────────────────────────────────────

@app.route('/api/import/shopify', methods=['POST'])
def import_shopify():
    data = request.get_json(silent=True) or {}
    url = data.get('url', '').rstrip('/')
    if not url:
        return jsonify({'error': 'URL manquante'}), 400
    try:
        resp = http_requests.get(f'{url}/products.json?limit=250', timeout=15)
        products = resp.json().get('products', [])
        lines = []
        for p in products:
            title = p.get('title', '')
            body = BeautifulSoup(p.get('body_html', ''), 'html.parser').get_text(' ').strip()
            body = re.sub(r'\s+', ' ', body)[:300]
            variants = p.get('variants', [])
            prices = sorted(set(v.get('price', '') for v in variants if v.get('price')))
            price_str = f" — {prices[0]}€" if prices else ''
            lines.append(f"- {title}{price_str}: {body}")
        kb = '\n'.join(lines)
        existing = database.get_setting('knowledge_base', '')
        combined = (existing + '\n\n--- Produits Shopify ---\n' + kb).strip() if existing else kb
        database.save_setting('knowledge_base', combined)
        return jsonify({'ok': True, 'imported': len(products), 'preview': kb[:500]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/import/obsidian', methods=['POST'])
def import_obsidian():
    data = request.get_json(silent=True) or {}
    vault_path = data.get('path', '').strip()
    if not vault_path or not os.path.isdir(vault_path):
        return jsonify({'error': 'Dossier introuvable : ' + vault_path}), 400
    try:
        md_files = glob.glob(os.path.join(vault_path, '**', '*.md'), recursive=True)
        lines = []
        for f in md_files[:100]:
            try:
                with open(f, encoding='utf-8') as fh:
                    content = fh.read()[:1000]
                name = os.path.splitext(os.path.basename(f))[0]
                lines.append(f"### {name}\n{content}")
            except Exception:
                pass
        kb = '\n\n'.join(lines)
        existing = database.get_setting('knowledge_base', '')
        combined = (existing + '\n\n--- Vault Obsidian ---\n' + kb).strip() if existing else kb
        database.save_setting('knowledge_base', combined)
        return jsonify({'ok': True, 'imported': len(md_files), 'preview': kb[:500]})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Settings ───────────────────────────────────────────────────────────────────

@app.route('/api/settings/<key>')
def get_setting(key):
    value = database.get_setting(key)
    return jsonify({'value': value})


@app.route('/api/settings/<key>', methods=['POST'])
def save_setting(key):
    data = request.get_json(silent=True) or {}
    value = data.get('value', '')
    database.save_setting(key, value)
    return jsonify({'ok': True})


# ── Summary ────────────────────────────────────────────────────────────────────

@app.route('/api/summary/daily')
def daily_summary():
    today = date.today().isoformat()
    s = database.get_daily_summary(today)
    return jsonify({'date': today, 'summary': s['summary'] if s else None})


@app.route('/api/summary/generate', methods=['POST'])
def generate_summary():
    today = date.today().isoformat()
    emails = database.get_emails(limit=200)
    today_emails = [e for e in emails if (e.get('date') or '').startswith(today)] or emails[:30]
    for e in today_emails:
        e['response'] = database.get_response(e['id'])
    summary = ai_service.generate_daily_summary(today_emails)
    database.save_daily_summary(today, summary)
    return jsonify({'date': today, 'summary': summary})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
