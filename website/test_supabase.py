import os
from unittest.mock import patch
import supabase_auth
import test_shop


class SupabaseTests(test_shop.ShopTests):
    def setUp(self):
        super().setUp()
        self.env = patch.dict(os.environ, {'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_PUBLISHABLE_KEY': 'test'})
        self.env.start()
        self.addCleanup(self.env.stop)
        remote_patch = patch('supabase_auth.request', side_effect=self.provider)
        self.remote = remote_patch.start()
        self.addCleanup(remote_patch.stop)

    def provider(self, path, data):
        if data['password'] == 'wrong':
            raise supabase_auth.AuthError('Ungültige Anmeldung.')
        return {'access_token': 'server-only-token', 'user': {'id': 'remote-' + data['email'], 'email': data['email'], 'user_metadata': {'name': 'Test Person'}}}

    def test_account_cart_isolation_and_persistence(self):
        a, b = self.client(), self.client()
        self.assertEqual(self.register(a)[0], 200)
        self.assertEqual(self.register(b, 'two@example.com')[0], 200)
        self.assertEqual(self.call(a, 'cart/add', {'product': 'wood', 'design': 'Anna', 'quantity': 2})[0], 200)
        item = self.call(a, 'cart')[1]['items'][0]
        self.assertEqual(self.call(b, 'cart')[1]['items'], [])
        self.assertEqual(self.call(b, 'cart/remove', {'id': item['id']})[0], 404)
        self.call(a, 'logout', {})
        self.assertEqual(self.call(a, 'cart')[0], 401)
        self.assertEqual(self.call(a, 'login', {'email': 'one@example.com', 'password': 'A long password 123!'})[0], 200)
        self.assertEqual(self.call(a, 'cart')[1]['items'][0]['id'], item['id'])
        with __import__('server').connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM customers').fetchone()[0], 0)

    def test_validation_csrf_expiry_and_throttle(self):
        a = self.client()
        self.assertEqual(self.call(a, 'register', {'email': 'one@example.com', 'name': 'OK', 'password': 'short'})[0], 400)
        self.remote.assert_not_called()
        self.assertEqual(self.call(a, 'login', {'email': 'one@example.com', 'password': 'wrong'})[0], 400)
        self.assertEqual(self.call(a, 'logout', {}, 'https://evil.example')[0], 403)

    def test_confirmation_does_not_create_session(self):
        self.remote.side_effect = None
        self.remote.return_value = {'user': {'id': 'unconfirmed'}}
        client = self.client()
        code, result, headers = self.register(client)
        self.assertEqual(code, 200)
        self.assertTrue(result['confirmation_required'])
        self.assertNotIn('Set-Cookie', headers)
        self.assertIsNone(self.call(client, 'account')[1]['user'])

    def test_provider_failure_has_no_local_fallback(self):
        self.remote.side_effect = supabase_auth.AuthError('Nicht erreichbar.', 503)
        client = self.client()
        self.assertEqual(self.register(client)[0], 503)
        self.assertIsNone(self.call(client, 'account')[1]['user'])
