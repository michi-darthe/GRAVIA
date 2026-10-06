import itertools
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import board_sets
import server
import test_shop

IDS = ['wood-compact', 'wood-classic', 'wood-grand', 'wood-serving']
TEXTS = ['Max', 'Familie Müller', 'Guten Appetit', '2026']


def items(ids=IDS):
    return [{'product': product, 'engraving': TEXTS[IDS.index(product)]} for product in ids]


class SetPricingTests(unittest.TestCase):
    def test_all_combinations_and_every_order(self):
        expected = {
            (0,): 790, (1,): 1090, (2,): 1290, (3,): 1490,
            (0, 1): 1786, (0, 2): 1976, (0, 3): 2166, (1, 2): 2261, (1, 3): 2451, (2, 3): 2641,
            (0, 1, 2): 2890, (0, 1, 3): 3033, (0, 2, 3): 3213, (1, 2, 3): 3483, (0, 1, 2, 3): 4190,
        }
        for indices, total in expected.items():
            reference = board_sets.quote(items([IDS[i] for i in indices]))
            self.assertEqual(reference['total'], total)
            self.assertEqual(reference['subtotal'] - reference['discount'], total)
            self.assertEqual(reference['preset'], indices in [(0, 1, 2), (0, 1, 2, 3)])
            for order in itertools.permutations(indices):
                self.assertEqual(board_sets.quote(items([IDS[i] for i in order])), reference)

    def test_required_engraving_and_unique_known_ids(self):
        invalid = [None, {}, [], 'wood-compact', items() + items(IDS[:1]), items(IDS[:1]) * 2,
                   [{'product': 'jewelry', 'engraving': 'Max'}], [{'product': [], 'engraving': 'Max'}], [None]]
        invalid += [[{'product': IDS[0], 'engraving': text}] for text in [None, '', '   ', '\t', 'x' * 29, 42, 'Name\nOther']]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                board_sets.quote(value)
        self.assertEqual(board_sets.quote([{'product': IDS[0], 'engraving': '  Max  '}])['items'][0]['engraving'], 'Max')

    def test_public_and_server_catalog_prices_match(self):
        text = Path('boards.js').read_text()
        boards = json.loads(text.split('=', 1)[1].strip().removesuffix(';'))
        self.assertEqual(set(boards), set(board_sets.BOARDS))
        for id, value in boards.items():
            self.assertEqual(value['price'], board_sets.BOARDS[id]['price_cents'])
            self.assertEqual(value['title'], board_sets.BOARDS[id]['name'])


class SetApiTests(unittest.TestCase):
    setUp = test_shop.ShopTests.setUp
    tearDown = test_shop.ShopTests.tearDown
    client = test_shop.ShopTests.client
    call = test_shop.ShopTests.call
    register = test_shop.ShopTests.register

    def test_cart_canonicalizes_presets_and_ignores_client_prices(self):
        client = self.client()
        payload = {'product': 'set-custom', 'items': items(list(reversed(IDS[:3]))), 'quantity': 2, 'total': 1, 'discount_rate': 99}
        self.assertEqual(self.call(client, 'cart/add', payload)[0], 401)
        self.register(client)
        self.assertEqual(self.call(client, 'cart/add', payload)[0], 200)
        saved = self.call(client, 'cart')[1]['items'][0]
        self.assertEqual(saved['product'], 'set-kitchen')
        self.assertEqual(saved['set']['total'], 2890)
        self.assertEqual(saved['quantity'], 2)
        self.assertIn('57,80 €', saved['design'])
        self.assertEqual(saved['set']['items'][1]['engraving'], 'Familie Müller')
        server.initialize()
        self.assertEqual(self.call(client, 'cart')[1]['items'][0], saved)
        self.assertEqual(self.call(client, 'cart/update', {'id': saved['id'], 'quantity': 3})[0], 200)
        self.assertIn('86,70 €', self.call(client, 'cart')[1]['items'][0]['design'])
        other = self.client(); self.register(other, 'other@example.com')
        self.assertEqual(self.call(other, 'cart')[1]['items'], [])
        self.assertEqual(self.call(other, 'cart/update', {'id': saved['id'], 'quantity': 5})[0], 404)
        self.assertEqual(self.call(client, 'cart/remove', {'id': saved['id']})[0], 200)
        self.assertEqual(self.call(client, 'cart')[1]['items'], [])

    def test_invalid_cart_sets_and_single_board_engraving(self):
        client = self.client(); self.register(client)
        for selection in [[], items(IDS[:1]) * 2, [{'product': IDS[0], 'engraving': ' '}], None]:
            self.assertEqual(self.call(client, 'cart/add', {'product': 'board-set', 'items': selection, 'quantity': 1})[0], 400)
        for quantity in [0, True, 1.5, 1001]:
            self.assertEqual(self.call(client, 'cart/add', {'product': 'board-set', 'items': items(), 'quantity': quantity})[0], 400)
        self.assertEqual(self.call(client, 'cart/add', {'product': IDS[0], 'design': 'No engraving', 'quantity': 1})[0], 400)
        self.assertEqual(self.call(client, 'cart/add', {'product': IDS[0], 'design': 'Max', 'engraving': 'Max', 'quantity': 1})[0], 200)
        self.assertEqual(self.call(client, 'cart/add', {'product': 'board-set', 'items': items([IDS[0], IDS[3]]), 'quantity': 1})[0], 200)
        custom = self.call(client, 'cart')[1]['items'][1]['set']
        self.assertEqual((custom['id'], custom['discount_rate'], custom['total']), ('set-custom', 5, 2166))

    def test_set_inquiry_persists_once_and_sends_separate_svg_engraving_per_board(self):
        client = self.client()
        payload = dict(self.payload, board_set=items(), set_quantity=2)
        with patch.dict(os.environ, {'SMTP_HOST': ''}):
            self.assertEqual(self.call(client, 'inquiries', payload)[0], 202)
        self.assertEqual(self.call(client, 'inquiries', payload)[0], 202)
        with server.connect() as db:
            rows = db.execute('SELECT * FROM inquiries').fetchall()
        self.assertEqual(len(rows), 1)
        stored = json.loads(rows[0]['payload'])
        self.assertEqual(stored['board_set']['id'], 'set-complete')
        self.assertEqual(stored['board_set']['total'], 4190)
        self.assertIn('83,80 €', stored['message'])
        with patch.dict(os.environ, {'SMTP_PORT': '465'}), patch.object(server.smtplib, 'SMTP_SSL') as smtp:
            server.notify(rows[0])
            mail = smtp.return_value.send_message.call_args.args[0]
        attachments = list(mail.iter_attachments())
        self.assertEqual(len(attachments), 4)
        for item, attachment in zip(items(), attachments):
            self.assertTrue(attachment.get_filename().startswith(item['product']))
            self.assertIn(item['engraving'], attachment.get_payload(decode=True).decode())
        self.assertIn('Gravia Complete Set', mail.get_body(preferencelist=('plain',)).get_content())
        payload['board_set'][0]['engraving'] = 'Different'
        self.assertEqual(self.call(client, 'inquiries', payload)[0], 409)

    def test_invalid_inquiry_does_not_save_and_private_files_not_served(self):
        client = self.client()
        self.assertEqual(self.call(client, 'inquiries', dict(self.payload, board_set=[{'product': IDS[0], 'engraving': ''}]))[0], 400)
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM inquiries').fetchone()[0], 0)
        for path in ['sets.html', 'sets.js', 'sets-core.js', 'sets.css', 'set_catalog.json']:
            with client.open(self.url + '/' + path) as response:
                self.assertEqual(response.status, 200)
        with self.assertRaises(HTTPError) as error:
            client.open(self.url + '/board_sets.py')
        error.exception.close()
        self.assertEqual(error.exception.code, 404)


if __name__ == '__main__':
    unittest.main()
