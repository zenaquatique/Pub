import sqlite3
import json
from datetime import date

DB_PATH = "email_assistant.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            gmail_id TEXT UNIQUE NOT NULL,
            thread_id TEXT,
            message_id_header TEXT,
            from_email TEXT,
            from_name TEXT,
            to_email TEXT,
            subject TEXT,
            body TEXT,
            date TEXT,
            is_client INTEGER DEFAULT 0,
            category TEXT DEFAULT 'other',
            priority TEXT DEFAULT 'normal',
            summary TEXT,
            has_unsubscribe INTEGER DEFAULT 0,
            unsubscribe_link TEXT,
            unsubscribed INTEGER DEFAULT 0,
            synced_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id INTEGER REFERENCES emails(id),
            draft TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            sent_at TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS daily_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            summary TEXT,
            generated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def get_emails(client_only=False, limit=100):
    conn = get_db()
    c = conn.cursor()
    if client_only:
        c.execute('SELECT * FROM emails WHERE is_client = 1 ORDER BY date DESC LIMIT ?', (limit,))
    else:
        c.execute('SELECT * FROM emails ORDER BY date DESC LIMIT ?', (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows


def get_email(email_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM emails WHERE id = ?', (email_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_email_by_gmail_id(gmail_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM emails WHERE gmail_id = ?', (gmail_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def save_email(data):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT OR IGNORE INTO emails
        (gmail_id, thread_id, message_id_header, from_email, from_name, to_email,
         subject, body, date, is_client, category, priority, summary,
         has_unsubscribe, unsubscribe_link)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    ''', (
        data['gmail_id'], data.get('thread_id'), data.get('message_id_header'),
        data.get('from_email'), data.get('from_name'), data.get('to_email'),
        data.get('subject'), data.get('body'), data.get('date'),
        1 if data.get('is_client') else 0,
        data.get('category', 'other'), data.get('priority', 'normal'),
        data.get('summary', ''),
        1 if data.get('has_unsubscribe') else 0,
        data.get('unsubscribe_link'),
    ))
    conn.commit()
    email_id = c.lastrowid
    conn.close()
    return email_id


def update_email(email_id, updates):
    conn = get_db()
    c = conn.cursor()
    clause = ', '.join(f'{k} = ?' for k in updates)
    c.execute(f'UPDATE emails SET {clause} WHERE id = ?', [*updates.values(), email_id])
    conn.commit()
    conn.close()


def save_response(email_id, draft):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT id FROM responses WHERE email_id = ?', (email_id,))
    row = c.fetchone()
    if row:
        c.execute('UPDATE responses SET draft = ?, status = ? WHERE id = ?',
                  (draft, 'pending', row[0]))
        rid = row[0]
    else:
        c.execute('INSERT INTO responses (email_id, draft) VALUES (?, ?)', (email_id, draft))
        rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def get_response(email_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM responses WHERE email_id = ?', (email_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def get_response_by_id(response_id):
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT r.*, e.from_email, e.subject, e.thread_id, e.message_id_header
        FROM responses r JOIN emails e ON r.email_id = e.id
        WHERE r.id = ?
    ''', (response_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_response(response_id, updates):
    conn = get_db()
    c = conn.cursor()
    clause = ', '.join(f'{k} = ?' for k in updates)
    c.execute(f'UPDATE responses SET {clause} WHERE id = ?', [*updates.values(), response_id])
    conn.commit()
    conn.close()


def get_daily_summary(d):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM daily_summaries WHERE date = ?', (d,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def save_daily_summary(d, summary):
    conn = get_db()
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO daily_summaries (date, summary) VALUES (?, ?)', (d, summary))
    conn.commit()
    conn.close()
