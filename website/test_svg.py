import json
import os
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch
from urllib.error import HTTPError
import server
import svg_design
import test_shop


def design():
    return {'product': 'wood', 'quantity': 2, 'objects': [{'type': 'text', 'x': 200, 'y': 125, 'width': 100, 'height': 30, 'text': 'Mama & <GANI>', 'fontSize': 20}]}


class SvgTests(unittest.TestCase):
    setUp = test_shop.ShopTests.setUp
    tearDown = test_shop.ShopTests.tearDown
    client = test_shop.ShopTests.client
    call = test_shop.ShopTests.call
    register = test_shop.ShopTests.register

    def test_dimensions_escaping_and_clip(self):
        value = svg_design.render(svg_design.validate(design()))
        root = ET.fromstring(value)
        self.assertEqual(root.get('width'), '400mm')
        self.assertEqual(root.get('height'), '250mm')
        self.assertEqual(root.get('viewBox'), '0 0 400 250')
        self.assertIn('Mama &amp; &lt;GANI&gt;', value)
        self.assertIn('clip-path="url(#engraving-area)"', value)
        self.assertNotIn('<script', value)

    def test_malicious_and_invalid_designs(self):
        client = self.client()
        for changes in [{'x': float('nan')}, {'font': 'url(https://evil.test)'}, {'fill': 'url(https://evil.test)'}, {'type': 'script'}, {'type': 'image', 'src': 'data:image/svg+xml;base64,AAAA'}, {'type': 'image', 'src': 'data:image/png;base64,AAAA'}, {'type':'text','text':'\x00'}]:
            data = design()
            data['objects'][0].update(changes)
            self.assertEqual(self.call(client, 'svg/render', data)[0], 400)
        self.assertEqual(self.call(client, 'svg/render', design(), origin='https://evil.test')[0], 403)
        data = design(); data['objects'] *= 81
        self.assertEqual(self.call(client, 'svg/render', data)[0], 400)

    def test_svg_import_is_static(self):
        safe = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0 L10 10" stroke="black"/></svg>'
        self.assertIn('<path', svg_design.sanitize_svg(safe))
        for source in [safe.replace('<path', '<script'), safe.replace('stroke="black"', 'onload="alert(1)"'), safe.replace('stroke="black"', 'fill="url(https://evil.test)"'), '<!DOCTYPE svg><svg/>', safe.replace('<path', '<image href="https://evil.test"')]:
            with self.assertRaises(ValueError):
                svg_design.sanitize_svg(source)
        data=design();data['objects'][0].update(type='svg',source=safe)
        self.assertIn('<path', svg_design.render(svg_design.validate(data)))

    def test_atomic_storage_idempotence_and_admin_access(self):
        client = self.client()
        data = dict(self.payload, design=design())
        with patch.dict(os.environ, {'SMTP_PASSWORD': ''}):
            self.assertEqual(self.call(client, 'inquiries', data)[0], 202)
            self.assertEqual(self.call(client, 'inquiries', data)[0], 202)
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM inquiry_designs').fetchone()[0], 1)
            saved = db.execute('SELECT svg FROM inquiry_designs').fetchone()[0]
        changed=json.loads(json.dumps(data));changed['design']['objects'][0]['x']=100
        self.assertEqual(self.call(client, 'inquiries', changed)[0], 409)
        self.assertEqual(self.call(client, 'admin/inquiries')[0], 403)
        self.assertEqual(self.call(client, 'admin/svg?id='+data['request_id'])[0], 403)
        self.assertEqual(self.register(client)[0], 200)
        uid=self.call(client, 'account')[1]['user']['id']
        self.assertEqual(self.call(client, 'admin/inquiries')[0], 403)
        with patch.dict(os.environ, {'GRAVIA_ADMIN_IDS': uid}):
            code, result, _ = self.call(client, 'admin/inquiries')
            self.assertEqual(code, 200)
            self.assertEqual(result['items'][0]['quantity'], 2)
            self.assertEqual(self.call(client, 'admin/status', {'id':data['request_id'],'status':'Erledigt'})[0], 200)
            self.assertEqual(self.call(client, 'admin/status', {'id':data['request_id'],'status':'Neu'}, origin='https://evil.test')[0], 403)
            with client.open(self.url+'/api/admin/svg?id='+data['request_id']) as response:
                self.assertIn('attachment',response.headers['Content-Disposition'])
                self.assertEqual(response.read().decode(),saved)
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT status FROM inquiry_designs').fetchone()[0],'Erledigt')

    def test_simple_design_becomes_email_attachment(self):
        simple = {'product':'jewelry', 'text':'Mama & Papa', 'second':'2026', 'font':'script',
                  'size':100, 'position':'center', 'align':'center', 'quantity':2,
                  'shape':'heart', 'chain':'with'}
        data = dict(self.payload, simple_design=simple)
        self.assertEqual(self.call(self.client(), 'inquiries', data)[0], 202)
        with server.connect() as db:
            row = db.execute('SELECT * FROM inquiries').fetchone()
            stored = db.execute('SELECT svg,design FROM inquiry_designs').fetchone()
        self.assertIn('Mama &amp; Papa', stored['svg'])
        self.assertIn('font-style="italic"', stored['svg'])
        self.assertEqual(json.loads(stored['design'])['simple_design']['shape'], 'heart')
        with patch.dict(os.environ, {'SMTP_PORT':'465'}), patch.object(server.smtplib, 'SMTP_SSL') as smtp:
            server.notify(row)
            message = smtp.return_value.send_message.call_args.args[0]
        attachments = list(message.iter_attachments())
        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0].get_content_type(), 'image/svg+xml')
        self.assertEqual(attachments[0].get_payload(decode=True).decode(), stored['svg'])
        self.assertEqual(message['To'], os.environ['MAIL_TO'])
        self.assertEqual(message['Reply-To'], self.payload['email'])

    def test_simple_products_and_validation(self):
        for product in ['wood', 'jewelry', 'cards', 'custom']:
            value = {'product': product, 'text': 'GANI', 'second': '', 'font': 'bold', 'size': 110,
                     'position': 'upper', 'align': 'right', 'quantity': 3, 'shape': 'round'}
            result = svg_design.from_simple(value)
            self.assertEqual(result['product'], product)
            self.assertIn('GANI', svg_design.render(result))
        with self.assertRaises(ValueError):
            svg_design.from_simple(dict(value, product=[]))

    def test_board_variants_keep_dimensions_in_inquiries_and_cart(self):
        import uuid
        client = self.client()
        self.assertEqual(self.register(client)[0], 200)
        catalog = self.call(client, 'svg/products')[1]['products']
        self.assertNotIn('wood', [p['id'] for p in catalog])
        for slug, width, height, price in [('compact', 220, 150, 790), ('classic', 280, 220, 1090), ('grand', 330, 220, 1290), ('serving', 580, 190, 1490)]:
            product = 'wood-' + slug
            with self.subTest(product=product):
                entry = next(p for p in catalog if p['id'] == product)
                self.assertEqual(entry['price_cents'], price)
                value = {'product': product, 'text': 'Familie Test', 'second': '', 'font': 'bold', 'size': 100,
                         'position': 'center', 'align': 'center', 'quantity': 2}
                result = svg_design.from_simple(value)
                root = ET.fromstring(svg_design.render(result))
                self.assertEqual(root.get('width'), f'{width}mm')
                self.assertEqual(root.get('height'), f'{height}mm')
                self.assertEqual(result['product_snapshot']['thickness'], 15)
                payload = dict(self.payload, request_id=str(uuid.uuid4()), product='Personalisiertes Schneidbrett', simple_design=value)
                code, response, _ = self.call(client, 'inquiries', payload)
                self.assertEqual(code, 202)
                with server.connect() as db:
                    row = db.execute('SELECT product, svg FROM inquiry_designs WHERE inquiry=?', (response['id'],)).fetchone()
                self.assertEqual(row['product'], product)
                self.assertIn(f'width="{width}mm"', row['svg'])
                self.assertEqual(self.call(client, 'cart/add', {'product': product, 'design': 'Familie Test', 'engraving': 'Familie Test', 'quantity': 2})[0], 200)
        items = self.call(client, 'cart')[1]['items']
        self.assertEqual(len(items), 4)
        self.assertEqual({i['title'] for i in items}, {'Gravia Compact Board', 'Gravia Classic Board', 'Gravia Grand Board', 'Gravia Serving Board'})

    def test_invalid_design_leaves_no_inquiry(self):
        data=dict(self.payload, design=design());data['design']['quantity']=0
        self.assertEqual(self.call(self.client(), 'inquiries', data)[0],400)
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM inquiries').fetchone()[0],0)


if __name__ == '__main__':
    unittest.main()
