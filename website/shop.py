"""Customer accounts and per-customer carts, using the existing SQLite database."""
import supabase_auth
import board_sets
import hashlib
import hmac
import json
from pathlib import Path
import os
import re
import secrets
import sqlite3
import time
from http.cookies import SimpleCookie
from urllib.parse import urlsplit

TITLES = {'wood': 'Gravia Wood One', 'jewelry': 'Gravia Mark', 'cards': '3D-gedruckte Kartenhalterung', 'custom': 'Individuelles 3D-Druck-Produkt'}
TITLES.update({p['id']: p['name'] for p in json.loads(Path(__file__).with_name('svg_products.json').read_text()) if p['id'].startswith('wood-')})
COOKIE = 'gravia_session'


def initialize(db):
    db.executescript('''
    CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, password TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS supabase_customers (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, customer TEXT NOT NULL, expires REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS cart (id TEXT PRIMARY KEY, customer TEXT NOT NULL, product TEXT NOT NULL, design TEXT NOT NULL, quantity INTEGER NOT NULL);
    CREATE INDEX IF NOT EXISTS cart_customer ON cart(customer);
    CREATE TABLE IF NOT EXISTS auth_attempts (client TEXT NOT NULL, created REAL NOT NULL);
    ''')


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


def token_for(handler):
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get('Cookie', ''))
        value = cookie[COOKIE].value if COOKIE in cookie else ''
    except Exception:
        value = ''
    return hashlib.sha256(value.encode()).hexdigest()


def customer(db, handler):
    table = 'supabase_customers' if supabase_auth.enabled() else 'customers'
    return db.execute(f'SELECT c.id,c.name,c.email FROM {table} c JOIN sessions s ON s.customer=c.id WHERE s.token=? AND s.expires>?', (token_for(handler), time.time())).fetchone()


def set_session(db, handler, customer_id):
    token = secrets.token_urlsafe(32)
    db.execute('DELETE FROM sessions WHERE token=? OR expires<?', (token_for(handler), time.time()))
    db.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), customer_id, time.time() + 604800))
    secure = '; Secure' if os.environ.get('GRAVIA_COOKIE_SECURE') == '1' else ''
    handler.shop_cookie = f'{COOKIE}={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age=604800{secure}'


def handle(handler, connect):
    path = urlsplit(handler.path).path
    if path not in ['/api/account', '/api/register', '/api/login', '/api/logout', '/api/cart', '/api/cart/add', '/api/cart/update', '/api/cart/remove']:
        return False
    try:
        data = {}
        if handler.command == 'POST':
            origin = handler.headers.get('Origin')
            if (origin and (urlsplit(origin).netloc != handler.headers.get('Host') or urlsplit(origin).scheme not in ('http', 'https'))) or handler.headers.get('Sec-Fetch-Site') == 'cross-site':
                handler.respond(403, {'error': 'Unzulässiger Ursprung.'})
                return True
            if handler.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                handler.respond(415, {'error': 'JSON erwartet.'})
                return True
            length = int(handler.headers.get('Content-Length', '0'))
            if not 0 < length <= 16000:
                raise ValueError('Ungültige Anfragegröße.')
            handler.connection.settimeout(10)
            data = json.loads(handler.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Ungültige Anfrage.')
        elif path not in ['/api/account', '/api/cart']:
            handler.respond(405, {'error': 'POST erforderlich.'})
            return True
        with connect() as db:
            user = customer(db, handler)
            if path in ['/api/register', '/api/login']:
                client = hashlib.sha256(handler.client_address[0].encode()).hexdigest()
                db.execute('BEGIN IMMEDIATE')
                db.execute('DELETE FROM auth_attempts WHERE created<?', (time.time() - 900,))
                if db.execute('SELECT count(*) FROM auth_attempts WHERE client=?', (client,)).fetchone()[0] >= 15:
                    handler.respond(429, {'error': 'Zu viele Versuche. Bitte warte 15 Minuten.'})
                    return True
                db.execute('INSERT INTO auth_attempts VALUES(?,?)', (client, time.time()))
                db.commit()
                email = data.get('email', '')
                password = data.get('password', '')
                if not isinstance(email, str) or not isinstance(password, str) or not 1 <= len(password) <= 256:
                    raise ValueError('Bitte prüfe E-Mail und Passwort.')
                email = email.strip().lower()
                if len(email) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
                    raise ValueError('Bitte gib eine gültige E-Mail-Adresse ein.')
                if supabase_auth.enabled():
                    name = data.get('name', '')
                    if path == '/api/register' and (not isinstance(name, str) or not 2 <= len(name.strip()) <= 100 or len(password) < 12):
                        raise ValueError('Bitte prüfe Name und Passwort.')
                    profile = supabase_auth.authenticate(path.rsplit('/', 1)[1], email, password, name.strip() if isinstance(name, str) else '')
                    if profile is None:
                        handler.respond(200, {'ok': True, 'confirmation_required': True})
                        return True
                    uid = profile['id']
                    db.execute('INSERT INTO supabase_customers VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,email=excluded.email',
                               (uid, profile['name'], profile['email']))
                else:
                    if path == '/api/register':
                        name = data.get('name', '')
                        if not isinstance(name, str) or not 2 <= len(name.strip()) <= 100 or len(password) < 12:
                            raise ValueError('Name: 2–100 Zeichen. Passwort: mindestens 12 Zeichen.')
                        salt = secrets.token_hex(16)
                        uid = secrets.token_hex(16)
                        try:
                            db.execute('INSERT INTO customers VALUES(?,?,?,?,?)', (uid, name.strip(), email, salt, password_hash(password, salt)))
                        except sqlite3.IntegrityError:
                            raise ValueError('Konto konnte nicht erstellt werden. Nutze gegebenenfalls die Anmeldung.')
                    else:
                        row = db.execute('SELECT * FROM customers WHERE email=?', (email,)).fetchone()
                        computed = password_hash(password, row['salt'] if row else '00' * 16)
                        if not row or not hmac.compare_digest(computed, row['password']):
                            raise ValueError('E-Mail oder Passwort stimmt nicht.')
                        uid = row['id']
                set_session(db, handler, uid)
                result = {'ok': True}
            elif path == '/api/logout':
                db.execute('DELETE FROM sessions WHERE token=?', (token_for(handler),))
                handler.shop_cookie = f'{COOKIE}=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0'
                result = {'ok': True}
            elif path == '/api/account':
                result = {'user': dict(user) if user else None}
            elif not user:
                handler.respond(401, {'error': 'Bitte melde dich zuerst an.'})
                return True
            elif path == '/api/cart':
                result = {'items': [board_sets.cart_item(row) if row['product'] in board_sets.SET_IDS else dict(row) | {'title': TITLES[row['product']]} for row in db.execute('SELECT id,product,design,quantity FROM cart WHERE customer=? ORDER BY rowid', (user['id'],))]}
            elif path == '/api/cart/add':
                product, design, quantity = data.get('product'), data.get('design'), data.get('quantity')
                if isinstance(product, str) and (product == 'board-set' or product in board_sets.SET_IDS):
                    selection = board_sets.quote(data.get('items'))
                    product, design = selection['id'], board_sets.stored_design(selection)
                elif not isinstance(product, str) or product not in TITLES or not isinstance(design, str) or not 1 <= len(design) <= 5000:
                    raise ValueError('Bitte prüfe dein Produkt und deine Gestaltung.')
                elif product in board_sets.BOARDS:
                    text = board_sets.engraving(data.get('engraving'))
                    design = f'Gravur: {text}\n{design}'
                check_quantity(quantity)
                db.execute('BEGIN IMMEDIATE')
                if db.execute('SELECT count(*) FROM cart WHERE customer=?', (user['id'],)).fetchone()[0] >= 50:
                    raise ValueError('Dein Warenkorb enthält bereits 50 Positionen.')
                db.execute('INSERT INTO cart VALUES(?,?,?,?,?)', (secrets.token_hex(16), user['id'], product, design, quantity))
                result = {'ok': True}
            else:
                item_id = data.get('id')
                if not isinstance(item_id, str):
                    raise ValueError('Ungültige Position.')
                if path == '/api/cart/update':
                    check_quantity(data.get('quantity'))
                    cursor = db.execute('UPDATE cart SET quantity=? WHERE id=? AND customer=?', (data['quantity'], item_id, user['id']))
                else:
                    cursor = db.execute('DELETE FROM cart WHERE id=? AND customer=?', (item_id, user['id']))
                if not cursor.rowcount:
                    handler.respond(404, {'error': 'Position nicht gefunden.'})
                    return True
                result = {'ok': True}
        handler.respond(200, result)
    except supabase_auth.AuthError as error:
        handler.respond(error.status, {'error': str(error)})
    except (ValueError, UnicodeError):
        handler.respond(400, {'error': 'Bitte prüfe deine Eingaben. Name: 2–100 Zeichen, Passwort bei Registrierung: mindestens 12 Zeichen. E-Mail und Passwort müssen bei der Anmeldung übereinstimmen.'} if path in ['/api/register', '/api/login'] else {'error': 'Bitte prüfe deine Eingaben (Stückzahl: 1–1000).'} )
    except (sqlite3.Error, OSError):
        handler.respond(503, {'error': 'Der Dienst ist gerade nicht verfügbar. Bitte versuche es erneut.'})
    return True


def check_quantity(value):
    if type(value) is not int or not 1 <= value <= 1000:
        raise ValueError('Stückzahl: 1–1000.')
