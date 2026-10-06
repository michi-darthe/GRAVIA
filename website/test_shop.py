import http.cookiejar
import json
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.error import HTTPError
import unittest
import test_server
import server


class ShopTests(unittest.TestCase):
    setUp = test_server.InquiryTests.setUp
    tearDown = test_server.InquiryTests.tearDown

    def client(self):
        return build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, client, path, data=None, origin=None):
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        request = Request(self.url + '/api/' + path, data=None if data is None else json.dumps(data).encode(), headers=headers)
        try:
            response = client.open(request)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response), response.headers

    def register(self, client, email='one@example.com'):
        return self.call(client, 'register', {'name': 'Test Person', 'email': email, 'password': 'A long password 123!'})

    def test_account_cart_isolation_and_persistence(self):
        a, b = self.client(), self.client()
        code, _, headers = self.register(a)
        self.assertEqual(code, 200)
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Lax', headers['Set-Cookie'])
        self.assertEqual(self.call(a, 'account')[1]['user']['name'], 'Test Person')
        self.assertEqual(self.register(b, 'two@example.com')[0], 200)
        item = {'product': 'jewelry', 'design': 'Gravur: Anna\nForm: Herz\nKette: mit\nSymbole: ♡', 'quantity': 2}
        self.assertEqual(self.call(a, 'cart/add', item)[0], 200)
        saved = self.call(a, 'cart')[1]['items'][0]
        self.assertEqual(saved['design'], item['design'])
        self.assertEqual(self.call(b, 'cart')[1]['items'], [])
        self.assertEqual(self.call(b, 'cart/update', {'id': saved['id'], 'quantity': 8})[0], 404)
        self.assertEqual(self.call(b, 'cart/remove', {'id': saved['id']})[0], 404)
        self.assertEqual(self.call(a, 'cart/update', {'id': saved['id'], 'quantity': 3})[0], 200)
        self.call(a, 'logout', {})
        self.assertEqual(self.call(a, 'cart')[0], 401)
        self.assertEqual(self.call(a, 'login', {'email': 'ONE@example.com', 'password': 'A long password 123!'})[0], 200)
        server.initialize()
        self.assertEqual(self.call(a, 'cart')[1]['items'][0]['quantity'], 3)
        self.call(a, 'cart/remove', {'id': saved['id']})
        self.assertEqual(self.call(a, 'cart')[1]['items'], [])
        with server.connect() as db:
            row = db.execute('SELECT * FROM customers LIMIT 1').fetchone()
            self.assertNotEqual(row['password'], 'A long password 123!')

    def test_validation_csrf_expiry_and_throttle(self):
        a = self.client()
        self.assertEqual(self.register(a)[0], 200)
        self.assertEqual(self.register(a)[0], 400)
        self.assertEqual(self.call(a, 'logout', {}, 'https://evil.example')[0], 403)
        for quantity in [0, -1, 1001, True, '2']:
            self.assertEqual(self.call(a, 'cart/add', {'product': 'wood', 'design': 'Name', 'quantity': quantity})[0], 400)
        self.assertEqual(self.call(a, 'cart/add', {'product': [], 'design': 'Name', 'quantity': 1})[0], 400)
        with server.connect() as db:
            db.execute('UPDATE sessions SET expires=0')
        self.assertEqual(self.call(a, 'cart')[0], 401)
        for _ in range(13):
            self.assertEqual(self.call(a, 'login', {'email': 'one@example.com', 'password': 'wrong'})[0], 400)
        self.assertEqual(self.call(a, 'login', {'email': 'one@example.com', 'password': 'wrong'})[0], 429)

    def test_shop_pages_and_private_module(self):
        for path in ['/konto.html', '/warenkorb.html', '/shop.js']:
            with self.client().open(self.url + path) as response:
                self.assertEqual(response.status, 200)
        with self.assertRaises(HTTPError) as error:
            self.client().open(self.url + '/shop.py')
        self.assertEqual(error.exception.code, 404)
        error.exception.close()
