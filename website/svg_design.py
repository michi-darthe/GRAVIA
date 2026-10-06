"""Validated, code-free SVG generation and authenticated inquiry administration."""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, parse_qs
import shop

NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
CATALOG = Path(__file__).with_name('svg_products.json')
FONTS = ['sans-serif', 'serif', 'monospace', 'cursive']
LIMIT = 6_000_000


def products():
    return json.loads(CATALOG.read_text())


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS inquiry_designs (
        inquiry TEXT PRIMARY KEY REFERENCES inquiries(id), product TEXT NOT NULL,
        design TEXT NOT NULL, svg TEXT NOT NULL, quantity INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'Neu')''')


def number(value, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError('Ungültige Größe oder Position im Design.')
    return round(value, 4)


def sanitize_svg(source):
    """Accept static SVG geometry only; never preserve scripts or external resources."""
    if not isinstance(source, str) or len(source) > 500_000 or '<!' in source:
        raise ValueError('SVG zu groß oder enthält nicht unterstützte XML-Inhalte.')
    try:
        root = ET.fromstring(source)
    except ET.ParseError:
        raise ValueError('Ungültige SVG-Datei.')
    if root.tag not in ['svg', f'{{{NS}}}svg']:
        raise ValueError('SVG-Wurzelelement fehlt.')
    tags = {'svg', 'g', 'defs', 'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'text', 'tspan', 'title', 'desc', 'clipPath', 'linearGradient', 'radialGradient', 'stop'}
    attrs = {'id', 'x', 'y', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry', 'width', 'height', 'viewBox', 'preserveAspectRatio', 'd', 'points', 'transform', 'fill', 'stroke', 'stroke-width', 'fill-rule', 'clip-rule', 'fill-opacity', 'stroke-opacity', 'opacity', 'stroke-linecap', 'stroke-linejoin', 'stroke-miterlimit', 'stroke-dasharray', 'stroke-dashoffset', 'font-family', 'font-size', 'font-weight', 'font-style', 'text-anchor', 'dominant-baseline', 'dx', 'dy', 'letter-spacing', 'word-spacing', 'clip-path', 'clipPathUnits', 'offset', 'stop-color', 'stop-opacity', 'gradientUnits', 'gradientTransform', 'spreadMethod', 'fx', 'fy', 'fr'}
    count = 0
    prefix = 'import' + hashlib.sha256(source.encode()).hexdigest()[:12] + '-'
    def clean(element, depth=0):
        nonlocal count
        count += 1
        if count > 4000 or depth > 40:
            raise ValueError('SVG ist zu komplex.')
        tag = element.tag.rsplit('}', 1)[-1]
        if tag not in tags:
            raise ValueError('SVG enthält nicht unterstützte Elemente. Als einfache SVG mit Pfaden exportieren.')
        element.tag = f'{{{NS}}}{tag}'
        style = element.attrib.pop('style', '')
        for declaration in style.split(';'):
            if not declaration.strip():
                continue
            key, sep, value = declaration.partition(':')
            if not sep or key.strip() not in attrs:
                raise ValueError('SVG-Stil wird nicht unterstützt. In Inkscape in einfache Pfade umwandeln.')
            element.set(key.strip(), value.strip())
        for key, value in list(element.attrib.items()):
            if key.startswith('{') and not key.startswith('{' + NS + '}'):
                if key.endswith('}href'):
                    raise ValueError('Externe SVG-Verweise werden nicht unterstützt.')
                del element.attrib[key]
                continue
            if key not in attrs or len(value) > 200_000:
                raise ValueError('Nicht unterstütztes SVG-Attribut.')
            if 'url' in value.lower():
                match = re.fullmatch(r'url\(#([A-Za-z_][\w.-]*)\)', value)
                if not match:
                    raise ValueError('Externe SVG-Ressourcen werden nicht unterstützt.')
                element.set(key, 'url(#' + prefix + match[1] + ')')
            if key == 'id':
                if not re.fullmatch(r'[A-Za-z_][\w.-]*', value):
                    raise ValueError('Ungültige SVG-ID.')
                element.set(key, prefix + value)
        for child in list(element):
            if child.tag.rsplit('}', 1)[-1] in ['metadata', 'namedview']:
                element.remove(child)
            else:
                clean(child, depth + 1)
    clean(root)
    view = root.get('viewBox', '').replace(',', ' ').split()
    if len(view) != 4:
        raise ValueError('SVG benötigt eine viewBox mit vier Zahlen.')
    try:
        bounds = [float(v) for v in view]
    except ValueError:
        raise ValueError('Ungültige SVG-viewBox.')
    if not all(math.isfinite(v) and abs(v) <= 100000 for v in bounds) or min(bounds[2:]) <= 0:
        raise ValueError('Ungültige SVG-viewBox.')
    return ET.tostring(root, encoding='unicode')


def validate(data):
    if not isinstance(data, dict):
        raise ValueError('Ungültiges Design.')
    product = next((p for p in products() if p['id'] == data.get('product')), None)
    if not product:
        raise ValueError('Unbekanntes SVG-Produkt.')
    quantity = data.get('quantity', 1)
    if type(quantity) is not int or not 1 <= quantity <= 1000:
        raise ValueError('Stückzahl muss zwischen 1 und 1000 liegen.')
    objects = data.get('objects')
    if not isinstance(objects, list) or not 1 <= len(objects) <= 80:
        raise ValueError('Bitte gestalte 1 bis 80 Objekte.')
    result = []
    for obj in objects:
        if not isinstance(obj, dict) or obj.get('type') not in ['text', 'rect', 'ellipse', 'image', 'path', 'svg']:
            raise ValueError('Nicht unterstütztes Objekt.')
        item = {'type': obj['type']}
        for key, lo, hi in [('x', 0, product['width']), ('y', 0, product['height']), ('width', .1, product['width']), ('height', .1, product['height']), ('rotation', -360, 360), ('strokeWidth', 0, 10)]:
            item[key] = number(obj.get(key, 0 if key in ['rotation', 'strokeWidth'] else None), lo, hi)
        for key in ['fill', 'stroke']:
            value = obj.get(key, '#000000' if key == 'fill' else 'none')
            if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}|none', value):
                raise ValueError('Ungültige Farbe.')
            item[key] = value
        if item['type'] == 'text':
            text = obj.get('text')
            if not isinstance(text, str) or not text.strip() or len(text) > 500 or any(ord(c) < 32 and c != '\n' for c in text):
                raise ValueError('Bitte gib einen Text mit maximal 500 Zeichen ein.')
            item.update(text=text, font=obj.get('font', 'sans-serif'), fontSize=number(obj.get('fontSize'), .5, 150), align=obj.get('align', 'middle'))
            if item['font'] not in FONTS or item['align'] not in ['start', 'middle', 'end']:
                raise ValueError('Ungültige Schrift oder Ausrichtung.')
        if item['type'] == 'image':
            src = obj.get('src', '')
            if not isinstance(src, str) or len(src) > 2_800_000 or not re.fullmatch(r'data:image/(png|jpeg);base64,[A-Za-z0-9+/=]+', src):
                raise ValueError('Nur eingebettete PNG- und JPEG-Fotos bis 2 MB sind erlaubt.')
            try:
                raw = base64.b64decode(src.split(',')[1], validate=True)
            except ValueError:
                raise ValueError('Ungültiges Foto.')
            if not ((src.startswith('data:image/png;') and raw.startswith(b'\x89PNG\r\n\x1a\n')) or (src.startswith('data:image/jpeg;') and raw.startswith(b'\xff\xd8\xff'))):
                raise ValueError('Ungültiges Bildformat.')
            item['src'] = src
        if item['type'] == 'svg':
            item['source'] = sanitize_svg(obj.get('source'))
        if item['type'] == 'path':
            points = obj.get('points')
            if not isinstance(points, list) or not 2 <= len(points) <= 2000:
                raise ValueError('Ungültiger Freihandpfad.')
            item['points'] = [[number(p[0], 0, 1), number(p[1], 0, 1)] for p in points if isinstance(p, list) and len(p) == 2]
            if len(item['points']) != len(points):
                raise ValueError('Ungültiger Pfadpunkt.')
        result.append(item)
    return {'product': product['id'], 'quantity': quantity, 'objects': result, 'product_snapshot': product}


def from_simple(data):
    """Turn the existing customer controls into a stored, reproducible SVG draft."""
    if not isinstance(data, dict) or not isinstance(data.get('product'), str) or data['product'] not in shop.TITLES:
        raise ValueError('Ungültiges Produktdesign.')
    product_id = data['product']
    text, second = data.get('text'), data.get('second', '')
    if not isinstance(text, str) or not text.strip() or len(text) > 28 or not isinstance(second, str) or len(second) > 28:
        raise ValueError('Bitte prüfe deinen Wunschtext (maximal 28 Zeichen pro Zeile).')
    styles = {
        'classic': ('Georgia, serif', 'normal', '400'),
        'modern': ('DM Sans, sans-serif', 'normal', '600'),
        'script': ('Georgia, serif', 'italic', '400'),
        'book': ('Palatino, Palatino Linotype, Book Antiqua, serif', 'normal', '400'),
        'mono': ('Courier New, Courier, monospace', 'normal', '400'),
        'bold': ('Arial, Helvetica, sans-serif', 'normal', '900'),
        'rounded': ('Trebuchet MS, Arial Rounded MT Bold, sans-serif', 'normal', '400'),
    }
    font, position, align = data.get('font'), data.get('position'), data.get('align')
    if not isinstance(font, str) or font not in styles or position not in ['upper', 'center', 'lower'] or align not in ['left', 'center', 'right']:
        raise ValueError('Ungültige Schrift oder Position.')
    size = number(data.get('size'), 75, 115) / 100
    shape, chain = data.get('shape', ''), data.get('chain', 'without')
    if product_id == 'jewelry' and (shape not in ['heart', 'rectangle', 'round'] or chain not in ['with', 'without']):
        raise ValueError('Bitte wähle eine gültige Anhängerform und Ausführung.')
    p = next((dict(p) for p in products() if p['id'] == product_id), None)
    if p is None:
        p = {'id': product_id, 'name': shop.TITLES[product_id], 'inquiry': shop.TITLES[product_id],
             'width': 100, 'height': 100, 'area': [10, 10, 80, 80], 'confirmed': False}
    if product_id == 'jewelry':
        p['name'] = 'Gravia Mark · ' + {'heart': 'Herz', 'rectangle': 'Rechteck', 'round': 'Rund'}[shape]
        # Other shapes have no confirmed production template yet.
        if shape != 'rectangle':
            p['confirmed'] = False
    x, y, w, h = p['area']
    lines = [text.strip()] + ([second.strip()] if second.strip() else [])
    font_size = min(w / max(len(line) for line in lines) / .7, h / (len(lines) * 1.4), w / 12) * size
    obj = {'type': 'text', 'x': x + {'left': 0, 'center': w/2, 'right': w}[align],
           'y': y + h * {'upper': .3, 'center': .5, 'lower': .7}[position],
           'width': min(w, 100), 'height': min(h, 30), 'font': 'serif', 'fontSize': max(.5, font_size),
           'text': '\n'.join(lines), 'align': {'left': 'start', 'center': 'middle', 'right': 'end'}[align]}
    result = validate({'product': product_id if any(p['id'] == product_id for p in products()) else 'wood', 'quantity': data.get('quantity'), 'objects': [obj]})
    result.update(product=product_id, product_snapshot=p, simple_design=data)
    result['objects'][0].update(font=styles[font][0], fontStyle=styles[font][1], fontWeight=styles[font][2])
    return result


def render(design):
    p = design['product_snapshot']
    def node(parent, name, attrs):
        return ET.SubElement(parent, f'{{{NS}}}{name}', {k: str(v) for k, v in attrs.items()})
    root = ET.Element(f'{{{NS}}}svg', {'width': f"{p['width']}mm", 'height': f"{p['height']}mm", 'viewBox': f"0 0 {p['width']} {p['height']}"})
    node(root, 'title', {}).text = p['name']
    node(root, 'desc', {}).text = 'Gravurentwurf; Maße, Schrift und Fertigung vor Produktion prüfen.' + (' Beispielmaße, nicht zur direkten Produktion freigegeben.' if not p.get('confirmed') and not p.get('dimensions_confirmed') else '')
    defs = node(root, 'defs', {})
    clip = node(defs, 'clipPath', {'id': 'engraving-area'})
    node(clip, 'rect', dict(zip(['x', 'y', 'width', 'height'], p['area'])))
    content = node(root, 'g', {'clip-path': 'url(#engraving-area)'})
    for o in design['objects']:
        group = node(content, 'g', {'transform': f"translate({o['x']} {o['y']}) rotate({o['rotation']})", 'fill': o['fill'], 'stroke': o['stroke'], 'stroke-width': o['strokeWidth']})
        w, h = o['width'], o['height']
        if o['type'] == 'text':
            text = node(group, 'text', {'font-family': o['font'], 'font-size': o['fontSize'], 'text-anchor': o['align'], 'font-style': o.get('fontStyle', 'normal'), 'font-weight': o.get('fontWeight', '400')})
            for i, line in enumerate(o['text'].split('\n')):
                node(text, 'tspan', {'x': 0, 'dy': 0 if i == 0 else o['fontSize'] * 1.2}).text = line
        elif o['type'] == 'rect':
            node(group, 'rect', {'x': -w/2, 'y': -h/2, 'width': w, 'height': h})
        elif o['type'] == 'ellipse':
            node(group, 'ellipse', {'cx': 0, 'cy': 0, 'rx': w/2, 'ry': h/2})
        elif o['type'] == 'image':
            node(group, 'image', {'x': -w/2, 'y': -h/2, 'width': w, 'height': h, 'href': o['src'], 'preserveAspectRatio': 'xMidYMid meet'})
        elif o['type'] == 'svg':
            imported = ET.fromstring(o['source'])
            # Standalone SVG defaults must not inherit the editor object's paint.
            for key, value in {'fill': 'black', 'stroke': 'none', 'stroke-width': '1'}.items():
                if key not in imported.attrib:
                    imported.set(key, value)
            for key, value in {'x': -w/2, 'y': -h/2, 'width': w, 'height': h, 'preserveAspectRatio': 'xMidYMid meet'}.items():
                imported.set(key, str(value))
            group.append(imported)
        else:
            d = ' '.join(('M' if i == 0 else 'L') + f'{(x-.5)*w} {(y-.5)*h}' for i, (x,y) in enumerate(o['points']))
            node(group, 'path', {'d': d, 'fill': 'none', 'stroke-linecap': 'round', 'stroke-linejoin': 'round'})
    return ET.tostring(root, encoding='unicode')


def handle(handler, connect):
    path = urlsplit(handler.path).path
    if path not in ['/api/svg/products', '/api/svg/render', '/api/svg/import', '/api/admin/inquiries', '/api/admin/svg', '/api/admin/status']:
        return False
    try:
        if path == '/api/svg/products' and handler.command == 'GET':
            handler.respond(200, {'products': [p for p in products() if not p.get('legacy')], 'fonts': FONTS})
            return True
        admin = path.startswith('/api/admin/')
        if admin:
            with connect() as db:
                user = shop.customer(db, handler)
            allowed = {v.strip() for v in os.environ.get('GRAVIA_ADMIN_IDS', '').split(',') if v.strip()}
            if not user or user['id'] not in allowed:
                handler.respond(403, {'error': 'Bitte mit einem freigeschalteten Admin-Konto anmelden.'})
                return True
        if path in ['/api/svg/render', '/api/svg/import', '/api/admin/status']:
            if handler.command != 'POST':
                handler.respond(405, {'error': 'POST erforderlich.'})
                return True
            origin = handler.headers.get('Origin')
            if (origin and (urlsplit(origin).netloc != handler.headers.get('Host') or urlsplit(origin).scheme not in ['http', 'https'])) or handler.headers.get('Sec-Fetch-Site') == 'cross-site':
                handler.respond(403, {'error': 'Unzulässiger Ursprung.'})
                return True
            size = int(handler.headers.get('Content-Length', '0'))
            if not 0 < size <= LIMIT or handler.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Ungültige Anfragegröße oder Format.')
            handler.connection.settimeout(10)
            data = json.loads(handler.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Ungültige Anfrage.')
            if path == '/api/svg/import':
                handler.respond(200, {'source': sanitize_svg(data.get('source'))})
                return True
            if not admin:
                design = validate(data)
                handler.respond(200, {'svg': render(design), 'filename': design['product'] + '.svg'})
            else:
                if data.get('status') not in ['Neu', 'In Prüfung', 'In Produktion', 'Erledigt'] or not isinstance(data.get('id'), str):
                    raise ValueError('Ungültiger Status.')
                with connect() as db:
                    cursor = db.execute('UPDATE inquiry_designs SET status=? WHERE inquiry=?', (data['status'], data['id']))
                handler.respond(200 if cursor.rowcount else 404, {'ok': bool(cursor.rowcount)})
            return True
        if handler.command != 'GET':
            handler.respond(405, {'error': 'GET erforderlich.'})
            return True
        with connect() as db:
            if path == '/api/admin/inquiries':
                rows = db.execute('SELECT i.id,i.created,i.payload,d.product,d.quantity,d.status FROM inquiries i JOIN inquiry_designs d ON d.inquiry=i.id ORDER BY i.created DESC LIMIT 200').fetchall()
                handler.respond(200, {'items': [dict(row) | {'payload': json.loads(row['payload'])} for row in rows]})
            else:
                uid = parse_qs(urlsplit(handler.path).query).get('id', [''])[0]
                row = db.execute('SELECT svg,product FROM inquiry_designs WHERE inquiry=?', (uid,)).fetchone()
                if not row:
                    handler.respond(404, {'error': 'Datei nicht gefunden.'})
                else:
                    body = row['svg'].encode()
                    handler.send_response(200)
                    handler.send_header('Content-Type', 'image/svg+xml')
                    handler.send_header('Content-Disposition', f'attachment; filename="{row["product"]}_{uid[:8]}.svg"')
                    handler.send_header('Content-Length', str(len(body)))
                    handler.send_header('Cache-Control', 'no-store')
                    handler.send_header('X-Content-Type-Options', 'nosniff')
                    handler.send_header('Content-Security-Policy', "default-src 'none'; sandbox")
                    handler.end_headers()
                    handler.wfile.write(body)
    except (ValueError, TypeError, UnicodeError):
        handler.respond(400, {'error': 'Bitte prüfe dein Design, Dateiformat und die Eingaben.'})
    except (OSError, sqlite3.Error):
        handler.respond(503, {'error': 'Speicherung derzeit nicht erreichbar.'})
    return True
