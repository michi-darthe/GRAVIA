"""Canonical board-set validation and pricing. All monetary amounts are cents."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RULES = json.loads((ROOT / 'set_catalog.json').read_text())
BOARDS = {p['id']: p for p in json.loads((ROOT / 'svg_products.json').read_text()) if p['id'].startswith('wood-')}
SET_IDS = {'set-custom', *(p['id'] for p in RULES['presets'])}


def engraving(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 28 or any(ord(c) < 32 for c in value):
        raise ValueError('Bitte gib für jedes Brett einen Gravurtext mit 1–28 Zeichen ein.')
    return value.strip()


def quote(items):
    if not isinstance(items, list) or not 1 <= len(items) <= 4:
        raise ValueError('Bitte wähle ein bis vier unterschiedliche Bretter aus.')
    selected = {}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError('Ungültiges Set-Produkt.')
        product = item.get('product')
        if not isinstance(product, str) or product not in BOARDS or product in selected:
            raise ValueError('Jedes verfügbare Brett darf einmal im Set enthalten sein.')
        selected[product] = engraving(item.get('engraving'))
    # Canonical order ensures identical combinations, regardless of selection order.
    normalized = [{'product': key, 'engraving': selected[key], 'title': p['name'], 'price': p['price_cents']}
                  for key, p in BOARDS.items() if key in selected]
    subtotal = sum(item['price'] for item in normalized)
    preset = next((p for p in RULES['presets'] if set(p['products']) == set(selected)), None)
    rate = None if preset else RULES['discounts'][str(len(normalized))]
    # Round the discount half-up once, at the set level; no binary floating-point money.
    discount = subtotal - preset['price'] if preset else (subtotal * rate + 50) // 100
    return {'id': preset['id'] if preset else 'set-custom', 'title': preset['title'] if preset else 'Dein individuelles Gravia Set',
            'items': normalized, 'subtotal': subtotal, 'discount_rate': rate, 'discount': discount,
            'total': subtotal - discount, 'preset': bool(preset)}


def stored_design(value):
    return json.dumps({'items': [{'product': i['product'], 'engraving': i['engraving']} for i in value['items']]}, ensure_ascii=False, sort_keys=True)


def money(cents):
    return f'{cents / 100:.2f}'.replace('.', ',') + ' €'


def summary(value, quantity=1):
    lines = [value['title']]
    for item in value['items']:
        p = BOARDS[item['product']]
        lines.append(f"{item['title']} ({p['width'] / 10:g} × {p['height'] / 10:g} × 1,5 cm): {item['engraving']}")
    lines += [f"Einzelpreise zusammen: {money(value['subtotal'])}",
              (f"Set-Ersparnis: {money(value['discount'])}" if value['preset'] else f"Rabatt {value['discount_rate']} %: {money(value['discount'])}"),
              f"Preis pro Set: {money(value['total'])} inkl. 20 % USt.", f"Anzahl Sets: {quantity}",
              f"Gesamt: {money(value['total'] * quantity)} inkl. 20 % USt.", 'Individuelle Gravur je Brett enthalten.']
    return '\n'.join(lines)


def cart_item(row):
    item = dict(row)
    if item['product'] in SET_IDS:
        value = quote(json.loads(item['design'])['items'])
        item.update(product=value['id'], title=value['title'], set=value, design=summary(value, item['quantity']))
    return item
