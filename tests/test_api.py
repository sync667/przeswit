"""Testy warstwy HTTP (FastAPI) na tymczasowej bazie, bez Ollamy i procesów w tle."""

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app import storage as s
from app.security import TOKEN, TOKEN_HEADER
from app.web import create_app

BASE = 'http://127.0.0.1:8765'
AUTH = {TOKEN_HEADER: TOKEN, 'Origin': BASE}


def dataset(**kw):
    spot = dict(
        id='t-1',
        source='own-notes',
        name='Polana testowa',
        lat=50.9,
        lon=16.3,
        type='nature',
        description='Widok na dolinę i las.',
        comments=[],
        photos=[],
        geo={},
        evidence=[],
    )
    spot.update(kw)
    return json.dumps({'label': 'test', 'spots': [spot]}, ensure_ascii=False).encode()


class ApiCase(unittest.TestCase):
    """Wspólna konfiguracja: świeża baza w katalogu tymczasowym i klient testowy bez procesów w tle."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.patch = patch.object(s, 'DATA', Path(self.folder.name))
        self.patch.start()
        from app import web

        self.seed = patch.object(
            web, 'SEED', Path(self.folder.name) / 'no-seed.pack'
        )  # testy nie wczytują zbioru startowego
        self.seed.start()
        self.client = TestClient(create_app(), base_url=BASE, raise_server_exceptions=False)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.seed.stop()
        self.patch.stop()
        self.folder.cleanup()

    def import_sample(self, **kw):
        r = self.client.post(
            '/api/import',
            json=dict(name='test.json', content=base64.b64encode(dataset(**kw)).decode(), source='own-notes'),
            headers=AUTH,
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()


class ApiTests(ApiCase):
    def test_config_and_security_headers(self):
        r = self.client.get('/api/config')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['token'], TOKEN)
        self.assertEqual(r.headers['Cache-Control'], 'no-store')
        self.assertIn("script-src 'self'", r.headers['Content-Security-Policy'])
        self.assertEqual(r.headers['X-Content-Type-Options'], 'nosniff')

    def test_static_files_served_from_new_layout(self):
        for path, kind in [
            ('/', 'text/html'),
            ('/static/js/main.js', 'text/javascript'),
            ('/static/style.css', 'text/css'),
            ('/static/logo.svg', 'image/svg+xml'),
            ('/static/vendor/leaflet.js', 'text/javascript'),
            ('/examples/template.json', 'application/json'),
        ]:
            with self.subTest(path=path):
                r = self.client.get(path)
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.headers['Content-Type'].startswith(kind), r.headers['Content-Type'])
        self.assertEqual(self.client.get('/nope').status_code, 404)
        self.assertEqual(self.client.get('/nope').json()['error'], 'Not found')

    def test_host_rejected(self):
        r = self.client.get('/api/config', headers={'Host': 'evil.example:8765'})
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['error'], 'Host rejected')

    def test_post_requires_token_and_same_origin(self):
        self.assertEqual(self.client.post('/api/note', json={'key': 'x'}).status_code, 403)
        self.assertEqual(
            self.client.post('/api/note', json={'key': 'x'}, headers={TOKEN_HEADER: 'wrong'}).status_code, 403
        )
        r = self.client.post(
            '/api/note', json={'key': 'x'}, headers={TOKEN_HEADER: TOKEN, 'Origin': 'https://evil.example'}
        )
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()['error'], 'Origin rejected')

    def test_body_limit_and_empty_body(self):
        r = self.client.post('/api/profiles/retry', content=b'', headers={**AUTH, 'Content-Length': '0'})
        self.assertEqual(r.status_code, 400)
        self.assertIn('28 MB', r.json()['error'])
        r = self.client.post('/api/profiles/retry', content=b'{}', headers={**AUTH, 'Content-Length': '30000000'})
        self.assertEqual(r.status_code, 400)

    def test_validation_errors_are_400_with_error_field(self):
        r = self.client.post('/api/photos/pause', json={'paused': 'yes'}, headers=AUTH)
        self.assertEqual(r.status_code, 400)
        self.assertIn('paused', r.json()['error'])
        r = self.client.post('/api/profiles/parallel', json={'mode': '3'}, headers=AUTH)
        self.assertEqual(r.status_code, 400)
        r = self.client.post('/api/note', content=b'[1,2]', headers={**AUTH, 'Content-Type': 'application/json'})
        self.assertEqual(r.status_code, 400)

    def test_domain_value_error_is_400(self):
        r = self.client.post('/api/note', json={'key': 'missing'}, headers=AUTH)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['error'], 'Nie znaleziono miejsca.')
        r = self.client.post('/api/sync', json={'areas': '', 'radius': 40, 'sources': ['osm']}, headers=AUTH)
        self.assertEqual(r.status_code, 400)

    def test_import_library_note_flow(self):
        result = self.import_sample()
        self.assertEqual(result['imported'], 1)
        r = self.client.post('/api/library', json={'areas': '', 'radius': '40'}, headers=AUTH)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body['total'], 1)
        spot = body['spots'][0]
        self.assertEqual(spot['name'], 'Polana testowa')
        self.assertEqual(spot['profile_info']['status'], 'pending')
        r = self.client.post(
            '/api/note', json={'key': spot['key'], 'choice': 'shortlist', 'note': 'dojazd szutrem'}, headers=AUTH
        )
        self.assertEqual(r.status_code, 200)
        spot = self.client.post('/api/library', json={}, headers=AUTH).json()['spots'][0]
        self.assertEqual(spot['choice'], 'shortlist')
        self.assertEqual(spot['user_note'], 'dojazd szutrem')
        r = self.client.post(
            '/api/library', json={'areas': '16.0,50.0,16.1,50.1', 'radius': 40, 'save_area': True}, headers=AUTH
        )
        self.assertEqual(r.json()['outside'], 1)
        self.assertEqual(self.client.get('/api/config').json()['last_area']['areas'], '16.0,50.0,16.1,50.1')

    def test_settings_endpoints(self):
        r = self.client.post('/api/photos/pause', json={'paused': True}, headers=AUTH)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['paused'])
        self.assertTrue(self.client.get('/api/photos').json()['paused'])
        r = self.client.post('/api/profiles/pause', json={'paused': True}, headers=AUTH)
        self.assertTrue(r.json()['paused'])
        r = self.client.post('/api/profiles/parallel', json={'mode': '2'}, headers=AUTH)
        self.assertEqual(r.json(), {'ok': True})
        self.assertEqual(s.get_setting('profile_parallel'), '2')
        self.assertIn('counts', self.client.get('/api/profiles').json())
        r = self.client.post('/api/database/backup', json={}, headers=AUTH)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(Path(r.json()['path']).exists())
        self.assertEqual(self.client.get('/api/database').json()['counts']['places'], 0)
        self.assertEqual(self.client.get('/api/status').json(), {'jobs': [], 'inbox': []})

    def test_cloud_ai_refuses_local_only_records(self):
        self.import_sample(source='ioverlander')
        key = self.client.post('/api/library', json={}, headers=AUTH).json()['spots'][0]['key']
        with (
            patch.dict('os.environ', {'OPENAI_API_KEY': 'x', 'OPENAI_MODEL': 'm'}),
            patch('urllib.request.urlopen', side_effect=AssertionError('no network')),
        ):
            r = self.client.post('/api/ai', json={'key': key, 'photos': False}, headers=AUTH)
        self.assertEqual(r.status_code, 400)
        self.assertIn('lokalnego', r.json()['error'])

    def test_rank_endpoint(self):
        payload = json.loads(dataset())
        r = self.client.post(
            '/api/rank', json={'dataset': payload, 'areas': '16.0,50.5,16.5,51.0', 'radius': 10}, headers=AUTH
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['imported'], 1)
        self.assertEqual(len(r.json()['spots']), 1)

    def test_photo_not_found(self):
        r = self.client.get('/photos/' + 'a' * 64)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()['error'], 'Zdjęcie niedostępne')

    def test_unexpected_error_is_500_with_message(self):
        with patch('app.api.store.jobs', side_effect=RuntimeError('boom')), self.assertLogs(level='ERROR'):
            r = self.client.get('/api/status')
        self.assertEqual(r.status_code, 500)
        self.assertIn('Błąd aplikacji', r.json()['error'])
        self.assertEqual(r.headers['Cache-Control'], 'no-store')


class PublicHostTests(unittest.TestCase):
    """Dostęp przez publiczny host wymaga nagłówka Cloudflare Access z właściwym e-mailem."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.patch = patch.object(s, 'DATA', Path(self.folder.name))
        self.patch.start()
        from app import security

        self.sec = patch.multiple(
            security,
            PUBLIC_HOST='przeswit.example.com',
            ACCESS_TEAM='',
            ACCESS_AUD='',
            OWNER_EMAILS=frozenset({'ja@example.com'}),
            ACCESS_EMAILS=frozenset({'ja@example.com', 'gosc@example.com'}),
            ALLOWED_HOSTS=frozenset({'127.0.0.1:8765', 'localhost:8765', 'przeswit.example.com'}),
            ALLOWED_ORIGINS=frozenset(
                {'http://127.0.0.1:8765', 'http://localhost:8765', 'https://przeswit.example.com'}
            ),
        )
        self.sec.start()
        from app import web

        self.seed = patch.object(web, 'SEED', Path(self.folder.name) / 'no-seed.pack')
        self.seed.start()
        self.client = TestClient(create_app(), base_url='https://przeswit.example.com', raise_server_exceptions=False)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.seed.stop()
        self.sec.stop()
        self.patch.stop()
        self.folder.cleanup()

    def test_requires_access_email(self):
        self.assertEqual(self.client.get('/api/config').status_code, 403)
        self.assertEqual(
            self.client.get(
                '/api/config', headers={'Cf-Access-Authenticated-User-Email': 'ktos@example.com'}
            ).status_code,
            403,
        )
        r = self.client.get('/api/config', headers={'Cf-Access-Authenticated-User-Email': 'Ja@Example.com'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            self.client.get(
                '/api/config', headers={'Cf-Access-Authenticated-User-Email': 'gosc@example.com'}
            ).status_code,
            200,
        )
        headers = {
            'Cf-Access-Authenticated-User-Email': 'ja@example.com',
            TOKEN_HEADER: TOKEN,
            'Origin': 'https://przeswit.example.com',
        }
        self.assertEqual(self.client.post('/api/profiles/retry', json={}, headers=headers).status_code, 200)

    def test_local_host_still_works_without_access_header(self):
        r = self.client.get('/api/config', headers={'Host': '127.0.0.1:8765'})
        self.assertEqual(r.status_code, 200)


class OwnPlaceTests(ApiCase):
    def test_create_edit_delete_own_place(self):
        r = self.client.post(
            '/api/places/own',
            json=dict(
                name='Polana nad Bobrem',
                lat=50.9,
                lon=15.7,
                status='planned',
                note='sprawdzić dojazd od zachodu',
                url='https://example.com/x',
            ),
            headers=AUTH,
        )
        self.assertEqual(r.status_code, 200, r.text)
        key = r.json()['key']
        self.assertTrue(key.startswith('own-notes:'))
        spot = next(
            s for s in self.client.post('/api/library', json={}, headers=AUTH).json()['spots'] if s['key'] == key
        )
        self.assertEqual(spot['own_status'], 'planned')
        self.assertEqual(spot['choice'], 'shortlist')
        self.assertEqual(spot['user_note'], 'sprawdzić dojazd od zachodu')
        r = self.client.post(
            '/api/places/own',
            json=dict(key=key, name='Polana nad Bobrem', lat=50.9, lon=15.7, status='visited', note='byłem w lipcu'),
            headers=AUTH,
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['key'], key)
        spot = next(
            s for s in self.client.post('/api/library', json={}, headers=AUTH).json()['spots'] if s['key'] == key
        )
        self.assertEqual((spot['own_status'], spot['choice'], spot['user_note']), ('visited', '', 'byłem w lipcu'))
        self.assertEqual(
            self.client.post('/api/places/own', json=dict(name='', lat=1, lon=1), headers=AUTH).status_code, 400
        )
        self.assertEqual(self.client.post('/api/places/own/delete', json={'key': key}, headers=AUTH).status_code, 200)
        self.assertEqual(self.client.post('/api/library', json={}, headers=AUTH).json()['total'], 0)

    def test_cannot_delete_imported_place(self):
        self.import_sample(source='osm')
        key = self.client.post('/api/library', json={}, headers=AUTH).json()['spots'][0]['key']
        self.assertEqual(self.client.post('/api/places/own/delete', json={'key': key}, headers=AUTH).status_code, 400)


class OwnPhotoTests(ApiCase):
    PNG = base64.b64decode(
        'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='
    )

    def test_add_serve_and_delete_own_photo(self):
        key = self.client.post('/api/places/own', json=dict(name='Foto test', lat=50.0, lon=16.0), headers=AUTH).json()[
            'key'
        ]
        r = self.client.post(
            '/api/places/own/photos',
            json=dict(key=key, content=base64.b64encode(self.PNG).decode(), caption='moje'),
            headers=AUTH,
        )
        self.assertEqual(r.status_code, 200, r.text)
        url = r.json()['url']
        self.assertTrue(url.startswith('own://'))
        lib = self.client.post('/api/library', json={'areas': ''}, headers=AUTH).json()
        spot = next(s for s in lib['spots'] if s['key'] == key)
        self.assertEqual(spot['photos'][0]['url'], url)
        self.assertIn(url, lib['photo_cache'])
        served = self.client.get(lib['photo_cache'][url])
        self.assertEqual(served.status_code, 200)
        self.assertEqual(served.content, self.PNG)
        self.assertEqual(
            self.client.post(
                '/api/places/own/photos',
                json=dict(key=key, content=base64.b64encode(b'not an image').decode()),
                headers=AUTH,
            ).status_code,
            400,
        )
        r = self.client.post('/api/places/own/photos/delete', json=dict(key=key, url=url), headers=AUTH)
        self.assertEqual(r.json()['photos'], 0)
        self.assertEqual(self.client.get(lib['photo_cache'][url]).status_code, 404)


class ReadOnlyGuestTests(PublicHostTests):
    def test_guest_can_read_but_not_write(self):
        guest = {'Cf-Access-Authenticated-User-Email': 'gosc@example.com'}
        r = self.client.get('/api/config', headers=guest)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['read_only'])
        self.assertEqual(r.json()['user'], 'gosc@example.com')
        owner = self.client.get('/api/config', headers={'Cf-Access-Authenticated-User-Email': 'ja@example.com'}).json()
        self.assertFalse(owner['read_only'])
        headers = {**guest, TOKEN_HEADER: TOKEN, 'Origin': 'https://przeswit.example.com'}
        r = self.client.post('/api/profiles/retry', json={}, headers=headers)
        self.assertEqual(r.status_code, 403)
        self.assertIn('tylko do odczytu', r.json()['error'])
        r = self.client.post('/api/library', json={}, headers=headers)
        self.assertEqual(r.status_code, 403)


class AccessJwtTests(unittest.TestCase):
    """Przy skonfigurowanym zespole i aud nagłówek e-mail bez poprawnego JWT nie wystarcza."""

    def test_signature_and_claims_are_checked(self):
        import jwt
        from cryptography.hazmat.primitives.asymmetric import rsa

        from app import security

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
        jwk['kid'] = 'k1'
        good = jwt.encode({'email': 'ja@example.com', 'aud': 'aud-1'}, key, algorithm='RS256', headers={'kid': 'k1'})
        other = jwt.encode({'email': 'ktos@example.com', 'aud': 'aud-1'}, key, algorithm='RS256', headers={'kid': 'k1'})
        wrong_aud = jwt.encode(
            {'email': 'ja@example.com', 'aud': 'aud-2'}, key, algorithm='RS256', headers={'kid': 'k1'}
        )

        class Headers(dict):
            def get(self, key, default=None):
                return super().get(key.lower(), default)

        class Req:
            def __init__(self, **h):
                self.headers = Headers({k.lower(): v for k, v in h.items()})

        with patch.multiple(
            security,
            PUBLIC_HOST='przeswit.example.com',
            ACCESS_TEAM='team',
            ACCESS_AUD='aud-1',
            _JWKS={'at': 9e12, 'keys': [jwk]},
        ):
            self.assertEqual(
                security.access_email(
                    Req(**{'Cf-Access-Authenticated-User-Email': 'ja@example.com', 'Cf-Access-Jwt-Assertion': good})
                ),
                'ja@example.com',
            )
            self.assertIsNone(security.access_email(Req(**{'Cf-Access-Authenticated-User-Email': 'ja@example.com'})))
            self.assertIsNone(
                security.access_email(
                    Req(**{'Cf-Access-Authenticated-User-Email': 'ja@example.com', 'Cf-Access-Jwt-Assertion': other})
                )
            )
            self.assertIsNone(
                security.access_email(
                    Req(
                        **{'Cf-Access-Authenticated-User-Email': 'ja@example.com', 'Cf-Access-Jwt-Assertion': wrong_aud}
                    )
                )
            )
            self.assertIsNone(
                security.access_email(
                    Req(
                        **{'Cf-Access-Authenticated-User-Email': 'ja@example.com', 'Cf-Access-Jwt-Assertion': 'garbage'}
                    )
                )
            )
