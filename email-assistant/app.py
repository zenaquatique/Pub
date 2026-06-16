import os
from datetime import date, datetime

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

    business_context = os.environ.get('BUSINESS_CONTEXT', '')
    new_count = 0
    for e in emails:
        if not database.get_email_by_gmail_id(e['gmail_id']):
            classification = ai_service.classify_email(
                e['from_email'], e['from_name'], e['subject'], e['body']
            )
            e.update(classification)
            database.save_email(e)
            new_count += 1

    return jsonify({'synced': new_count, 'total': len(emails)})


@app.route('/api/emails')
def get_emails():
    client_only = request.args.get('client_only') == 'true'
    limit = int(request.args.get('limit', 100))
    emails = database.get_emails(client_only=client_only, limit=limit)
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
    business_context = os.environ.get('BUSINESS_CONTEXT', '')
    draft = ai_service.generate_response(e, business_context)
    rid = database.save_response(eid, draft)
    return jsonify({'response_id': rid, 'draft': draft})


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
