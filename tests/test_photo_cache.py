import tempfile
import unittest

from app.p4n.endpoints import CDN_HOSTS

CDN3, CDN6 = sorted(CDN_HOSTS)
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from app import photo_cache as c
from app import profiles as p
from app import storage as s


class PhotoCacheTests(unittest.TestCase):
    def test_concurrent_fetch_once_and_offline_reuse(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(s, 'DATA', Path(directory)),
            patch.object(c.time, 'sleep'),
        ):
            s.init()
            c.init()
            calls = []
            data = b'\xff\xd8\xfftest'

            def fetch():
                calls.append(1)
                return data

            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: c.get(f'https://{CDN3}/test.jpg', fetch), range(2)))
            self.assertEqual(results, [data, data])
            self.assertEqual(len(calls), 1)
            c.init()
            self.assertEqual(c.get(f'https://{CDN3}/test.jpg', lambda: 1 / 0), data)
            self.assertEqual(c.read(c.key(f'https://{CDN3}/test.jpg')), (data, 'image/jpeg'))
            self.assertEqual(len(c.url_map()), 1)
            self.assertIsNone(c.read('../scout.sqlite3'))

    def test_profile_schema_only_allows_actual_evidence(self):
        good = dict(summary='Opis', scenes=[], unknown=[], warnings=[], observations=[])
        seen = []

        def call(path, payload, timeout):
            seen.append(payload)
            return dict(done=True, message=dict(content=__import__('json').dumps(good)))

        with patch.object(p.vision, 'local_call', side_effect=call):
            result = p.make_profile(
                dict(name='Test', photos=[], description='Polana', comments=[], geo={}, type='picnic_site')
            )
        allowed = seen[0]['format']['properties']['observations']['items']['properties']['evidence']['items']['enum']
        self.assertIn('description', allowed)
        self.assertNotIn('comment:N', allowed)
        self.assertNotIn('photo:0', allowed)
        self.assertEqual(result['photos_analyzed'], 0)


class ParallelDownloadTests(unittest.TestCase):
    def test_different_urls_download_concurrently_same_url_once(self):
        import threading
        import time

        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(s, 'DATA', Path(directory)),
            patch.object(c, 'MIN_INTERVAL', 0),
        ):
            s.init()
            c.init()
            active = []
            peak = [0]
            lock = threading.Lock()
            calls = []

            def fetch_for(url):
                def fetch():
                    with lock:
                        active.append(url)
                        peak[0] = max(peak[0], len(active))
                        calls.append(url)
                    time.sleep(0.15)
                    with lock:
                        active.remove(url)
                    return b'\xff\xd8data'

                return fetch

            urls = [f'https://{CDN3}/{i}.jpg' for i in range(6)] + [f'https://{CDN3}/0.jpg'] * 3
            with ThreadPoolExecutor(9) as pool:
                list(pool.map(lambda u: c.get(u, fetch_for(u)), urls))
            self.assertGreaterEqual(peak[0], 2)
            self.assertLessEqual(peak[0], c.CONCURRENCY)
            self.assertEqual(calls.count(f'https://{CDN3}/0.jpg'), 1)
            self.assertEqual(c.status()['counts']['ready'], 6)
            self.assertEqual(c.status()['parallel'], c.CONCURRENCY)

    def test_pending_urls_skips_ready_and_unknown_hosts(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(s, 'DATA', Path(directory)),
            patch.object(c, 'MIN_INTERVAL', 0),
        ):
            s.init()
            c.init()
            ready = f'https://{CDN6}/ready.jpg'
            c.get(ready, lambda: b'\xff\xd8x')
            s.upsert(
                [
                    dict(
                        id='1',
                        source='own-notes',
                        name='a',
                        lat=50.0,
                        lon=16.0,
                        type='nature',
                        description='',
                        comments=[],
                        evidence=[],
                        geo={},
                        photos=[
                            dict(url=ready),
                            dict(url=f'https://{CDN3}/new.jpg'),
                            dict(url='https://example.com/x.jpg'),
                            dict(url=f'https://{CDN3}/new.jpg'),
                        ],
                    )
                ]
            )
            self.assertEqual(c.pending_urls(), [f'https://{CDN3}/new.jpg'])
