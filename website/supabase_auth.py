"""Supabase password authentication; credentials and tokens stay on the server."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AuthError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def enabled():
    return bool(os.environ.get('SUPABASE_URL') or os.environ.get('SUPABASE_PUBLISHABLE_KEY'))


def request(path, data=None):
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_PUBLISHABLE_KEY', '')
    if not url.startswith('https://') or not key:
        raise AuthError('Die Anmeldung ist noch nicht vollständig eingerichtet.', 503)
    req = Request(url + '/auth/v1/' + path,
                  data=json.dumps(data).encode() if data is not None else None,
                  headers={'apikey': key, 'Content-Type': 'application/json'})
    try:
        with urlopen(req, timeout=15) as response:
            return json.load(response)
    except HTTPError as error:
        with error:
            try:
                code = json.load(error).get('error_code', '')
            except (ValueError, AttributeError):
                code = ''
        if error.code == 429:
            raise AuthError('Zu viele Versuche. Bitte versuche es später erneut.', 429) from None
        if error.code >= 500 or error.code in (401, 403):
            raise AuthError('Die Anmeldung ist gerade nicht verfügbar.', 503) from None
        if code == 'email_not_confirmed':
            raise AuthError('Bitte bestätige zuerst deine E-Mail-Adresse.') from None
        raise AuthError('Anmeldung oder Registrierung fehlgeschlagen. Bitte prüfe deine Angaben und gegebenenfalls deine Bestätigungs-E-Mail.') from None
    except (URLError, OSError, ValueError):
        raise AuthError('Die Anmeldung ist gerade nicht erreichbar. Bitte versuche es erneut.', 503) from None


def authenticate(action, email, password, name=''):
    payload = {'email': email, 'password': password}
    if action == 'register':
        payload['data'] = {'name': name}
    result = request('signup' if action == 'register' else 'token?grant_type=password', payload)
    if action == 'register' and not result.get('access_token'):
        return None
    user = result.get('user', {})
    if not result.get('access_token') or not user.get('id') or not user.get('email'):
        raise AuthError('Die Anmeldung konnte nicht abgeschlossen werden.', 503)
    return {'id': user['id'], 'email': user['email'],
            'name': str((user.get('user_metadata') or {}).get('name') or user['email'])[:100]}
