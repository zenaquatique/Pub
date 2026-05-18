import base64
import os
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
]
TOKEN_PATH = 'token.json'
CREDENTIALS_PATH = 'credentials.json'


def create_flow():
    return Flow.from_client_secrets_file(
        CREDENTIALS_PATH,
        scopes=SCOPES,
        redirect_uri='http://localhost:5000/auth/callback',
    )


def get_auth_url(flow):
    url, state = flow.authorization_url(access_type='offline', prompt='consent')
    return url, state


def exchange_code(flow, code):
    flow.fetch_token(code=code)
    creds = flow.credentials
    with open(TOKEN_PATH, 'w') as f:
        f.write(creds.to_json())


def _get_creds():
    if not os.path.exists(TOKEN_PATH):
        return None
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, 'w') as f:
            f.write(creds.to_json())
    return creds


def _get_service():
    creds = _get_creds()
    if not creds:
        return None
    return build('gmail', 'v1', credentials=creds)


def get_user_email():
    service = _get_service()
    if not service:
        return None
    try:
        profile = service.users().getProfile(userId='me').execute()
        return profile.get('emailAddress')
    except Exception:
        return None


def _decode_body(payload):
    body = ''
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                body = base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='replace')
                break
        if not body:
            for part in payload['parts']:
                if part['mimeType'] == 'text/html':
                    data = part['body'].get('data', '')
                    body = base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='replace')
                    body = re.sub(r'<[^>]+>', ' ', body)
                    break
    else:
        data = payload.get('body', {}).get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data + '==').decode('utf-8', errors='replace')
    return body.strip()


def _find_unsubscribe(headers, body):
    for h in headers:
        if h['name'].lower() == 'list-unsubscribe':
            match = re.search(r'<(https?://[^>]+)>', h['value'])
            if match:
                return True, match.group(1)
            match = re.search(r'<(mailto:[^>]+)>', h['value'])
            if match:
                return True, match.group(1)
    match = re.search(r'https?://\S+unsubscribe\S*', body, re.IGNORECASE)
    if match:
        return True, match.group(0)
    return False, None


def fetch_emails(max_results=50):
    service = _get_service()
    if not service:
        return [], 'Non authentifié'
    try:
        result = service.users().messages().list(
            userId='me', maxResults=max_results, labelIds=['INBOX']
        ).execute()
        messages = result.get('messages', [])
        emails = []
        for msg in messages:
            m = service.users().messages().get(
                userId='me', id=msg['id'], format='full'
            ).execute()
            headers = m['payload'].get('headers', [])

            def h(name):
                for hdr in headers:
                    if hdr['name'].lower() == name.lower():
                        return hdr['value']
                return ''

            from_raw = h('From')
            name_match = re.match(r'^"?([^"<]+)"?\s*<(.+)>$', from_raw)
            from_name = name_match.group(1).strip() if name_match else from_raw
            from_email = name_match.group(2).strip() if name_match else from_raw

            body = _decode_body(m['payload'])
            has_unsub, unsub_link = _find_unsubscribe(headers, body)

            emails.append({
                'gmail_id': m['id'],
                'thread_id': m.get('threadId'),
                'message_id_header': h('Message-ID'),
                'from_email': from_email,
                'from_name': from_name,
                'to_email': h('To'),
                'subject': h('Subject'),
                'body': body,
                'date': h('Date'),
                'has_unsubscribe': has_unsub,
                'unsubscribe_link': unsub_link,
            })
        return emails, None
    except Exception as e:
        return [], str(e)


def send_email(to, subject, body, thread_id=None, in_reply_to=None):
    service = _get_service()
    if not service:
        return False, 'Non authentifié'
    try:
        msg = MIMEMultipart()
        msg['To'] = to
        msg['Subject'] = subject
        if in_reply_to:
            msg['In-Reply-To'] = in_reply_to
            msg['References'] = in_reply_to
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        body_data = {'raw': raw}
        if thread_id:
            body_data['threadId'] = thread_id
        service.users().messages().send(userId='me', body=body_data).execute()
        return True, None
    except Exception as e:
        return False, str(e)
