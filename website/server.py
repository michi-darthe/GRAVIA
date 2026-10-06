"""GRAVIA inquiry server. Run: python3 server.py"""
from contextlib import contextmanager
import shop
import board_sets
import svg_design
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import smtplib
import sqlite3
import ssl
import threading
import time
import uuid
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('GRAVIA_DB', str(ROOT / 'data' / 'inquiries.sqlite3')))
PRODUCTS = {'Noch offen / Eigene Idee', 'Personalisiertes Schneidbrett', 'Personalisierter Schmuck', '3D-gedruckte Kartenhalterung', 'Individuelles 3D-Druck-Produkt', 'Firmenprojekt / Größere Stückzahl'}


@contextmanager
def connect():
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS inquiries (
            id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, payload TEXT NOT NULL,
            client TEXT NOT NULL, created REAL NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0)''')
        db.execute('CREATE INDEX IF NOT EXISTS inquiry_client_time ON inquiries(client, created)')
        shop.initialize(db)
        svg_design.initialize(db)
    DB.chmod(0o600)


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Ungültige Anfrage.')
    result = {}
    for field, minimum, maximum in [('name', 2, 100), ('email', 3, 254), ('product', 1, 100), ('message', 10, 4000)]:
        value = data.get(field)
        if not isinstance(value, str):
            raise ValueError('Bitte fülle alle Pflichtfelder aus.')
        value = value.strip()
        if not minimum <= len(value) <= maximum or any(ord(c) < 32 and c not in '\n\t' for c in value):
            raise ValueError('Bitte prüfe die Länge und Zeichen deiner Eingaben.')
        result[field] = value
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', result['email']):
        raise ValueError('Bitte gib eine gültige E-Mail-Adresse an.')
    if '\n' in result['name'] or result['product'] not in PRODUCTS:
        raise ValueError('Bitte prüfe Name und Produktauswahl.')
    if data.get('website', '') != '':
        raise ValueError('Die Anfrage konnte nicht angenommen werden.')
    try:
        result_id = str(uuid.UUID(data.get('request_id', '')))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Bitte lade die Seite neu und versuche es erneut.')
    return result_id, result


def configured():
    return all(os.environ.get(key) for key in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD', 'MAIL_FROM', 'MAIL_TO'))


def notify(row):
    data = json.loads(row['payload'])
    message = EmailMessage()
    message['Subject'] = f"GRAVIA Anfrage {row['id'][:8]} – {data['product']}"
    message['From'] = os.environ['MAIL_FROM']
    message['To'] = os.environ['MAIL_TO']
    message['Reply-To'] = data['email']
    message['Message-ID'] = f"<{row['id']}@gravia.local>"
    message.set_content(f"Neue Anfrage: {row['id']}\n\nName: {data['name']}\nE-Mail: {data['email']}\nProdukt: {data['product']}\n\n{data['message']}\n\nAntworte auf diese E-Mail, um die anfragende Person zu erreichen.")
    with connect() as db:
        attachment = db.execute('SELECT svg,product FROM inquiry_designs WHERE inquiry=?', (row['id'],)).fetchone()
    if attachment:
        message.set_content(message.get_content() + '\nDie automatisch erstellte SVG-Datei ist angehängt. Bitte Produktmaße, Schriftarten und Gravur vor der Fertigung prüfen. Noch nicht bestätigte Maße sind Beispielwerte.\n')
        message.add_attachment(attachment['svg'].encode('utf-8'), maintype='image', subtype='svg+xml',
                               filename=f"{attachment['product']}_{row['id'][:8]}.svg")
    if data.get('board_set'):
        for item in data['board_set']['items']:
            design = svg_design.from_simple({'product': item['product'], 'text': item['engraving'], 'second': '',
                'font': 'classic', 'size': 100, 'position': 'center', 'align': 'center', 'quantity': data['set_quantity']})
            message.add_attachment(svg_design.render(design).encode('utf-8'), maintype='image', subtype='svg+xml',
                filename=f"{item['product']}_{row['id'][:8]}.svg")
    port = int(os.environ.get('SMTP_PORT', '465'))
    context = ssl.create_default_context()
    if port == 465:
        client = smtplib.SMTP_SSL(os.environ['SMTP_HOST'], port, timeout=20, context=context)
    else:
        client = smtplib.SMTP(os.environ['SMTP_HOST'], port, timeout=20)
    with client:
        if port != 465:
            client.starttls(context=context)
        client.login(os.environ['SMTP_USER'], os.environ['SMTP_PASSWORD'])
        client.send_message(message)


def deliver_pending():
    with connect() as db:
        rows = db.execute("SELECT * FROM inquiries WHERE state='pending' AND next_attempt <= ? ORDER BY created LIMIT 10", (time.time(),)).fetchall()
    for row in rows:
        try:
            notify(row)
        except Exception as error:
            # Never log customer data, SMTP credentials or provider responses.
            delay = min(3600, 30 * 2 ** min(row['attempts'], 7))
            with connect() as db:
                db.execute('UPDATE inquiries SET attempts=attempts+1, next_attempt=? WHERE id=?', (time.time() + delay, row['id']))
            print(f"Benachrichtigung {row['id']}: erneuter Versuch in {delay}s ({type(error).__name__})", flush=True)
        else:
            with connect() as db:
                db.execute("UPDATE inquiries SET state='sent', attempts=attempts+1 WHERE id=?", (row['id'],))


def worker():
    while True:
        try:
            if configured():
                deliver_pending()
        except Exception as error:
            print(f'Warteschlange: {type(error).__name__}', flush=True)
        time.sleep(5)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def respond(self, code, body):
        content = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if getattr(self, 'shop_cookie', None):
            self.send_header('Set-Cookie', self.shop_cookie)
            self.shop_cookie = None
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if svg_design.handle(self, connect):
            return
        if shop.handle(self, connect):
            return
        path = urlsplit(self.path).path
        if path == '/api/status':
            self.respond(200, {'ready': configured()})
            return
        # Explicit public file list: database, source and secrets are never served.
        files = {'/': ('index.html', 'text/html; charset=utf-8'), '/index.html': ('index.html', 'text/html; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8'), '/script.js': ('script.js', 'text/javascript; charset=utf-8')}
        files['/produkt.html'] = ('produkt.html', 'text/html; charset=utf-8')
        for name, mime in [('sets.html', 'text/html'), ('sets.css', 'text/css'), ('sets-core.js', 'text/javascript'), ('sets.js', 'text/javascript'), ('set_catalog.json', 'application/json')]:
            files['/' + name] = (name, mime + '; charset=utf-8')
        files['/gestalten.html'] = ('gestalten.html', 'text/html; charset=utf-8')
        for name, mime in [('editor.css', 'text/css'), ('admin.html', 'text/html'), ('admin.js', 'text/javascript')]:
            files['/' + name] = (name, mime + '; charset=utf-8')
        files['/gestalten.js'] = ('gestalten.js', 'text/javascript; charset=utf-8')
        files['/boards.js'] = ('boards.js', 'text/javascript; charset=utf-8')
        files['/produkt.js'] = ('produkt.js', 'text/javascript; charset=utf-8')
        for name, mime in [('konto.html', 'text/html'), ('warenkorb.html', 'text/html'), ('shop.js', 'text/javascript')]:
            files['/' + name] = (name, mime + '; charset=utf-8')
        for asset in (ROOT / 'assets').glob('*.png'):
            files['/assets/' + asset.name] = ('assets/' + asset.name, 'image/png')
        if path not in files:
            self.respond(404, {'error': 'Nicht gefunden.'})
            return
        file, mime = files[path]
        content = (ROOT / file).read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'strict-origin-when-cross-origin')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        if svg_design.handle(self, connect):
            return
        if shop.handle(self, connect):
            return
        if self.path != '/api/inquiries':
            self.respond(404, {'error': 'Nicht gefunden.'})
            return
        origin = self.headers.get('Origin')
        if origin and (urlsplit(origin).netloc != self.headers.get('Host') or urlsplit(origin).scheme not in ('http', 'https')):
            self.respond(403, {'error': 'Unzulässiger Ursprung.'})
            return
        if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
            self.respond(415, {'error': 'JSON erwartet.'})
            return
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= svg_design.LIMIT:
                self.respond(413, {'error': 'Die Anfrage ist zu groß oder leer.'})
                return
            self.connection.settimeout(10)
            data = json.loads(self.rfile.read(size))
            request_id, payload = validate(data)
            selection = None
            if 'board_set' in data:
                if 'simple_design' in data or 'design' in data:
                    raise ValueError('Bitte frage ein Set oder ein einzelnes Design an.')
                selection = board_sets.quote(data['board_set'])
                quantity = data.get('set_quantity', 1)
                shop.check_quantity(quantity)
                payload['board_set'] = selection
                payload['set_quantity'] = quantity
                payload['product'] = selection['title']
                payload['message'] = board_sets.summary(selection, quantity) + '\n\nWeitere Wünsche:\n' + payload['message']
            design = svg_design.from_simple(data['simple_design']) if 'simple_design' in data else (svg_design.validate(data['design']) if 'design' in data else None)
            if design:
                payload['product'] = design['product_snapshot']['inquiry']
                payload['design_summary'] = {'product': design['product'], 'quantity': design['quantity'], 'texts': [o['text'] for o in design['objects'] if o['type'] == 'text']}
            svg = svg_design.render(design) if design else None
        except (ValueError, UnicodeError) as error:
            self.respond(400, {'error': str(error) if not isinstance(error, json.JSONDecodeError) else 'Ungültige Anfrage.'})
            return
        except (TimeoutError, OSError):
            self.respond(408, {'error': 'Zeitüberschreitung. Bitte erneut versuchen.'})
            return
        if not configured() and not design and not selection:
            self.respond(503, {'error': 'Der Anfrageversand wird gerade eingerichtet. Bitte versuche es später erneut.'})
            return
        serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        fingerprint = hashlib.sha256((serialized + (json.dumps(design, sort_keys=True) if design else '')).encode()).hexdigest()
        client = hashlib.sha256(self.client_address[0].encode()).hexdigest()
        try:
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT fingerprint FROM inquiries WHERE id=?', (request_id,)).fetchone()
                if existing:
                    if existing['fingerprint'] != fingerprint:
                        self.respond(409, {'error': 'Die Anfrage wurde geändert. Bitte lade die Seite neu.'})
                        return
                else:
                    count = db.execute('SELECT count(*) FROM inquiries WHERE client=? AND created>?', (client, time.time() - 3600)).fetchone()[0]
                    if count >= 5:
                        self.respond(429, {'error': 'Zu viele Anfragen. Bitte versuche es in einer Stunde erneut.'})
                        return
                    db.execute('INSERT INTO inquiries(id,fingerprint,payload,client,created) VALUES(?,?,?,?,?)', (request_id, fingerprint, serialized, client, time.time()))
                    if design:
                        db.execute('INSERT INTO inquiry_designs(inquiry,product,design,svg,quantity) VALUES(?,?,?,?,?)', (request_id, design['product'], json.dumps(design, ensure_ascii=False), svg, design['quantity']))
        except sqlite3.Error:
            self.respond(503, {'error': 'Deine Anfrage konnte nicht gespeichert werden. Bitte versuche es erneut.'})
            return
        self.respond(202, {'id': request_id, 'status': 'accepted'})


if __name__ == '__main__':
    # Read simple KEY=value entries without executing shell commands.
    env_file = ROOT / '.env'
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            key, separator, value = line.removeprefix('export ').partition('=')
            if separator and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', key.strip()):
                parts = shlex.split(value, comments=True)
                os.environ.setdefault(key.strip(), ' '.join(parts))
    DB = Path(os.environ.get('GRAVIA_DB', str(ROOT / 'data' / 'inquiries.sqlite3')))
    initialize()
    threading.Thread(target=worker, daemon=True).start()
    port = int(os.environ.get('PORT', '8000'))
    print(f'GRAVIA: http://localhost:{port} – Versand ' + ('bereit' if configured() else 'noch nicht eingerichtet'), flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), Handler).serve_forever()
