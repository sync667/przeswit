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
    spot = dict(id='t-1', source='own-notes', name='Polana testowa', lat=50.9, lon=16.3, type='nature', description='Widok na dolinę i las.',
                comments=[], photos=[], geo={}, evidence=[])
    spot.update(kw)
    return json.dumps({'label': 'test', 'spots': [spot]}, ensure_ascii=False).encode()


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.patch = patch.object(s, 'DATA', Path(self.folder.name))
        self.patch.start()
        self.client = TestClient(create_app(), base_url=BASE, raise_server_exceptions=False)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.patch.stop()
        self.folder.cleanup()

    def import_sample(self, **kw):
        r = self.client.post('/api/import', json=dict(name='test.json', content=base64.b64encode(dataset(**kw)).decode(), source='own-notes'), headers=AUTH)
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_config_and_security_headers(self):
        r = self.client.get('/api/config')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['token'], TOKEN)
        self.assertEqual(r.headers['Cache-Control'], 'no-store')
        self.assertIn("script-src 'self'", r.headers['Content-Security-Policy'])
        self.assertEqual(r.headers['X-Content-Type-Options'], 'nosniff')

    def test_static_files_served_from_new_layout(self):
        for path, kind in [('/', 'text/html'), ('/static/js/main.js', 'text/javascript'), ('/static/style.css', 'text/css'),
                           ('/static/logo.svg', 'image/svg+xml'), ('/static/vendor/leaflet.js', 'text/javascript'), ('/examples/template.json', 'application/json')]:
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
        self.assertEqual(self.client.post('/api/note', json={'key': 'x'}, headers={TOKEN_HEADER: 'wrong'}).status_code, 403)
        r = self.client.post('/api/note', json={'key': 'x'}, headers={TOKEN_HEADER: TOKEN, 'Origin': 'https://evil.example'})
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
        r = self.client.post('/api/note', json={'key': spot['key'], 'choice': 'shortlist', 'note': 'dojazd szutrem'}, headers=AUTH)
        self.assertEqual(r.status_code, 200)
        spot = self.client.post('/api/library', json={}, headers=AUTH).json()['spots'][0]
        self.assertEqual(spot['choice'], 'shortlist')
        self.assertEqual(spot['user_note'], 'dojazd szutrem')
        r = self.client.post('/api/library', json={'areas': '16.0,50.0,16.1,50.1', 'radius': 40, 'save_area': True}, headers=AUTH)
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
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'x', 'OPENAI_MODEL': 'm'}), patch('urllib.request.urlopen', side_effect=AssertionError('no network')):
            r = self.client.post('/api/ai', json={'key': key, 'photos': False}, headers=AUTH)
        self.assertEqual(r.status_code, 400)
        self.assertIn('lokalnego', r.json()['error'])

    def test_rank_endpoint(self):
        payload = json.loads(dataset())
        r = self.client.post('/api/rank', json={'dataset': payload, 'areas': '16.0,50.5,16.5,51.0', 'radius': 10}, headers=AUTH)
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
