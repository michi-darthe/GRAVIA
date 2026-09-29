import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import uuid
import server


class InquiryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        server.DB = Path(self.temp.name) / 'inquiries.sqlite3'
        server.initialize()
        self.config = patch.dict(os.environ, {key: 'test' for key in ('SMTP_HOST', 'SMTP_USER', 'SMTP_PASSWORD', 'MAIL_FROM', 'MAIL_TO')})
        self.config.start()
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        threading.Thread(target=self.http.serve_forever, daemon=True).start()
        self.url = f'http://127.0.0.1:{self.http.server_port}'
        self.payload = {'request_id': str(uuid.uuid4()), 'name': 'Test Person', 'email': 'test@example.com', 'product': 'Noch offen / Eigene Idee', 'message': 'Ein Brett mit Gravur bitte.', 'website': ''}

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.config.stop()
        self.temp.cleanup()

    def post(self, payload=None, origin=None):
        headers = {'Content-Type': 'application/json'}
        if origin:
            headers['Origin'] = origin
        request = Request(self.url + '/api/inquiries', data=json.dumps(payload or self.payload).encode(), headers=headers)
        try:
            response = urlopen(request)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def test_persistence_and_duplicate_retry(self):
        self.assertEqual(self.post()[0], 202)
        self.assertEqual(self.post()[0], 202)
        server.initialize()
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM inquiries').fetchone()[0], 1)
        self.payload['message'] = 'Eine andere Anfrage.'
        self.assertEqual(self.post()[0], 409)

    def test_validation_origin_and_honeypot(self):
        self.assertEqual(self.post(origin='https://other.example')[0], 403)
        for field, value in [('email', 'bad\nmail'), ('message', 'kurz'), ('website', 'spam'), ('product', 'unknown')]:
            with self.subTest(field=field):
                self.assertEqual(self.post(dict(self.payload, **{field: value}))[0], 400)

    def test_rate_limit(self):
        for _ in range(5):
            self.assertEqual(self.post(dict(self.payload, request_id=str(uuid.uuid4())))[0], 202)
        self.assertEqual(self.post(dict(self.payload, request_id=str(uuid.uuid4())))[0], 429)

    def test_unconfigured_does_not_accept(self):
        with patch.dict(os.environ, {'SMTP_PASSWORD': ''}):
            self.assertEqual(self.post()[0], 503)

    def test_failed_delivery_retries_then_succeeds(self):
        self.post()
        with patch.object(server, 'notify', side_effect=OSError):
            server.deliver_pending()
        with server.connect() as db:
            row = db.execute('SELECT * FROM inquiries').fetchone()
            self.assertEqual((row['state'], row['attempts']), ('pending', 1))
            db.execute('UPDATE inquiries SET next_attempt=0')
        with patch.object(server, 'notify') as deliver:
            server.deliver_pending()
            server.deliver_pending()
            self.assertEqual(deliver.call_count, 1)
        with server.connect() as db:
            self.assertEqual(db.execute('SELECT state FROM inquiries').fetchone()[0], 'sent')

    def test_private_files_are_not_public(self):
        for path in ['/server.py', '/.env', '/data/inquiries.sqlite3', '/../README.md']:
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                urlopen(self.url + path)
            self.assertEqual(error.exception.code, 404)
            error.exception.close()


if __name__ == '__main__':
    unittest.main()
