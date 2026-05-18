import os
import re
import base64
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from bs4 import BeautifulSoup

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify',
]
CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'
REDIRECT_URI = 'http://localhost:5000/auth/callback'


def get_service():
    if not os.path.exists(TOKEN_FILE):
        return None
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'w') as f:
                f.write(creds.to_json())
        else:
            return None
    return build('gmail', 'v1', credentials=creds)


def create_flow():
    flow = Flow.from_client_secrets_file(CREDENTIALS_FILE, scopes=SCOPES, redirect_uri=REDIRECT_URI)
    return flow


def get_auth_url(flow):
    url, state = flow.authorization_url(access_type='offline', prompt='consent')
    return url, state


def exchange_code(flow, code):
    flow.fetch_token(code=code)
    with open(TOKEN_FILE, 'w') as f:
        f.write(flow.credentials.to_json())


def get_user_email():
    svc = get_service()
    if not svc:
        return None
    try:
        return svc.users().getProfile(userId='me').execute().get('emailAddress')
    except Exception:
        return None


def _decode_payload(payload):
    text, html = '', ''
    mime = payload.get('mimeType', '')
    if mime == 'text/plain':
        data = payload.get('body', {}).get('data', '')
        if data:
            text = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
    elif mime == 'text/html':
        data = payload.get('body', {}).get('data', '')
        if data:
            html = base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
            text = BeautifulSoup(html, 'html.parser').get_text('\n', strip=True)
    elif 'parts' in payload:
        for part in payload['parts']:
            t, h = _decode_payload(part)
            text = text or t
            html = html or h
    return text, html


def _find_unsubscribe(headers, body):
    for h in headers:
        if h['name'].lower() == 'list-unsubscribe':
            urls = re.findall(r'<(https?://[^>]+)>', h['value'])
            if urls:
                return urls[0]
            mailto = re.findall(r'<(mailto:[^>]+)>', h['value'])
            if mailto:
                return mailto[0]
    m = re.search(r'https?://\S*(?:unsubscribe|optout|opt-out|se-d%C3%A9sabonner)\S*',
                  body, re.IGNORECASE)
    return m.group(0) if m else None


def fetch_emails(max_results=50):
    svc = get_service()
    if not svc:
        return None, 'Non authentifié'
    try:
        result = svc.users().messages().list(
            userId='me', maxResults=max_results, labelIds=['INBOX']
        ).execute()
        messages = result.get('messages', [])
        emails = []
        for ref in messages:
            msg = svc.users().messages().get(
                userId='me', id=ref['id'], format='full'
            ).execute()
            headers = msg.get('payload', {}).get('headers', [])
            hmap = {h['name'].lower(): h['value'] for h in headers}

            raw_from = hmap.get('from', '')
            m = re.match(r'^"?([^"<]+?)"?\s*<([^>]+)>', raw_from)
            if m:
                from_name, from_email = m.group(1).strip(), m.group(2).strip()
            else:
                from_name = from_email = raw_from.strip()

            try:
                dt = parsedate_to_datetime(hmap.get('date', ''))
                date_iso = dt.isoformat()
            except Exception:
                date_iso = hmap.get('date', '')

            text, _ = _decode_payload(msg.get('payload', {}))
            text = text[:5000]
            unsub = _find_unsubscribe(headers, text)

            emails.append({
                'gmail_id': msg['id'],
                'thread_id': msg.get('threadId'),
                'message_id_header': hmap.get('message-id', ''),
                'from_email': from_email,
                'from_name': from_name,
                'to_email': hmap.get('to', ''),
                'subject': hmap.get('subject', '(sans objet)'),
                'body': text,
                'date': date_iso,
                'has_unsubscribe': unsub is not None,
                'unsubscribe_link': unsub,
            })
        return emails, None
    except HttpError as e:
        return None, str(e)


def send_email(to, subject, body, thread_id=None, in_reply_to=None):
    svc = get_service()
    if not svc:
        return False, 'Non authentifié'
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['to'] = to
        msg['subject'] = subject if subject.startswith('Re:') else f'Re: {subject}'
        if in_reply_to:
            msg['In-Reply-To'] = in_reply_to
            msg['References'] = in_reply_to
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        payload = {'raw': raw}
        if thread_id:
            payload['threadId'] = thread_id
        sent = svc.users().messages().send(userId='me', body=payload).execute()
        return True, sent
    except HttpError as e:
        return False, str(e)
