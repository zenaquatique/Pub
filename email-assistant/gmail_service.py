import base64
import os
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parsedate_to_datetime

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


def _parse_date(date_str):
    try:
        return parsedate_to_datetime(date_str).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return date_str


SHOPIFY_SENDERS = {'mailer@shopify.com', 'no-reply@shopify.com', 'notifications@shopify.com'}


def extract_shopify_customer_email(body):
    """Extract customer email from Shopify contact form email body."""
    # Shopify format: "E-mail:\nowengury24@gmail.com" or "E-mail: owengury24@gmail.com"
    match = re.search(r'E-mail\s*:\s*[\r\n]+\s*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', body)
    if not match:
        match = re.search(r'E-mail\s*:\s*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', body)
    return match.group(1).strip() if match else None


def extract_shopify_customer_name(body):
    """Extract customer name from Shopify contact form email body."""
    match = re.search(r'Nom\s*:\s*[\r\n]+\s*(.+)', body)
    if not match:
        match = re.search(r'Name\s*:\s*[\r\n]+\s*(.+)', body)
    return match.group(1).strip() if match else None


def get_reply_to(gmail_id):
    """Return the Reply-To email address for a Gmail message, or None."""
    service = _get_service()
    if not service:
        return None
    try:
        m = service.users().messages().get(userId='me', id=gmail_id, format='metadata',
                                           metadataHeaders=['Reply-To']).execute()
        for h in m.get('payload', {}).get('headers', []):
            if h['name'].lower() == 'reply-to':
                val = h['value'].strip()
                rt_match = re.match(r'^"?([^"<]+)"?\s*<(.+)>$', val)
                return rt_match.group(2).strip() if rt_match else val
    except Exception:
        pass
    return None


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

            if from_email.lower() in SHOPIFY_SENDERS:
                customer_email = extract_shopify_customer_email(body)
                if customer_email:
                    from_email = customer_email
                    customer_name = extract_shopify_customer_name(body)
                    if customer_name:
                        from_name = customer_name
                else:
                    reply_to_raw = h('Reply-To')
                    if reply_to_raw:
                        rt_match = re.match(r'^"?([^"<]+)"?\s*<(.+)>$', reply_to_raw)
                        if rt_match:
                            from_name = rt_match.group(1).strip()
                            from_email = rt_match.group(2).strip()
                        elif '@' in reply_to_raw:
                            from_email = reply_to_raw.strip()
                            from_name = reply_to_raw.strip()
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
                'date': _parse_date(h('Date')),
                'has_unsubscribe': has_unsub,
                'unsubscribe_link': unsub_link,
            })
        return emails, None
    except Exception as e:
        return [], str(e)


def fetch_thread(thread_id):
    service = _get_service()
    if not service:
        return []
    try:
        thread = service.users().threads().get(userId='me', id=thread_id, format='full').execute()
        result = []
        for m in thread.get('messages', []):
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
            is_sent = 'SENT' in m.get('labelIds', [])
            result.append({
                'gmail_id': m['id'],
                'from_name': from_name,
                'from_email': from_email,
                'subject': h('Subject'),
                'body': body,
                'date': _parse_date(h('Date')),
                'is_sent': is_sent,
            })
        return result
    except Exception:
        return []


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
