import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import storage as s
from app.p4n import convert, pipeline
from app.p4n.endpoints import CDN_HOSTS

CDN3, CDN6 = sorted(CDN_HOSTS)
from app.p4n.dataset import Dataset

PAGE = """<html><section class="place-feedback"><div class="place-feedback-average"><strong>Average (2 Feedback) : </strong></div>
<ul><li><article class="place-feedback-article" data-review-id="11" data-review-rating="5"><header>
<a href="/en/user/Ola"><strong>Ola</strong></a><span class="caption text-gray">14/07/2026</span></header>
<p class="place-feedback-article-content">Cicho, &amp; ładny widok<br>na dolinę.</p></article></li>
<li class="d-none"><article class="place-feedback-article" data-review-id="12" data-review-rating="3"><header>
<a href="/en/user/Tom"><strong>Tom</strong></a><span class="caption text-gray">01/01/2025</span></header>
<p class="place-feedback-article-content">Szlaban zamknięty.</p></article></li></ul></section>
<div class="inner-page-carousel"><article class="place-feedback-article" data-review-id="99"></article></div></html>"""

BASIC = dict(
    id=123,
    title_short="<img src='x'>() - Polana",
    lat=50.5,
    lng=16.5,
    description='Quiet spot by the river',
    rating=4.5,
    review=2,
    photo=1,
    created_at='2021-05-01T10:00:00',
    address=dict(city='Kłodzko', country='Poland'),
    type=dict(code='PN'),
    activities=['point_de_vue', 'rando'],
    images=[dict(url=f'https://{CDN3}/lieu/123/1_gd.jpg')],
)
FULL = dict(
    description_en='Quiet spot by the river, free.',
    prix_stationnement='gratuit',
    date_fermeture='all_year',
    peche='1',
    wc_public=0,
    tel='123456',
    mail='x@y',
    photos=[dict(link_large=f'https://{CDN6}/lieu/123/2_gd.jpg'), 'https://evil.example/x.jpg'],
)


class ParseTests(unittest.TestCase):
    def test_parse_comments_reads_hidden_ones_and_ignores_carousel(self):
        items, declared = convert.parse_comments(PAGE)
        self.assertEqual(declared, 2)
        self.assertEqual([c['id'] for c in items], ['11', '12'])
        self.assertEqual(
            items[0], dict(id='11', rating=5, author='Ola', date='2026-07-14', text='Cicho, & ładny widok na dolinę.')
        )


class ConvertTests(unittest.TestCase):
    def test_convert_maps_fields_and_drops_contacts(self):
        comments, _ = convert.parse_comments(PAGE)
        spot = convert.convert(BASIC, FULL, comments, fetched_at='2026-09-18T00:00:00+00:00')
        self.assertEqual(spot['id'], '123')
        self.assertEqual(spot['name'], 'Polana')
        self.assertEqual((spot['lat'], spot['lon'], spot['source']), (50.5, 16.5, 'p4n'))
        self.assertEqual(
            [p['url'] for p in spot['photos']],
            [f'https://{CDN3}/lieu/123/1_gd.jpg', f'https://{CDN6}/lieu/123/2_gd.jpg'],
        )
        self.assertTrue(spot['geo']['viewpoint'])
        self.assertTrue(spot['geo']['p4n_peche'])
        self.assertNotIn('p4n_wc_public', spot['geo'])
        self.assertEqual(len(spot['comments']), 2)
        self.assertEqual(spot['comments'][0]['author'], 'Ola')
        self.assertNotIn('tel', spot['raw']['full'])
        self.assertNotIn('mail', json.dumps(spot))
        self.assertEqual(spot['raw']['full']['prix_stationnement'], 'gratuit')
        self.assertEqual(spot['country'], 'Poland')
        anonymous = convert.convert(BASIC, FULL, comments, with_authors=False)
        self.assertNotIn('author', anonymous['comments'][0])


class PipelineTests(unittest.TestCase):
    def test_grid_covers_bbox(self):
        cells = pipeline.grid((49.0, 14.1, 49.8, 14.9), step=0.35)
        self.assertEqual(cells[0], (49.0, 14.1))
        self.assertEqual(len(cells), 9)

    def test_ingest_and_seed_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(s, 'DATA', Path(folder)):
            s.init()
            ds = Dataset(Path(folder) / 'p4n')
            ds.places['123'] = BASIC
            ds.details['123'] = FULL
            ds.comments['123'], _ = convert.parse_comments(PAGE)
            ds.state['fetched_at'] = '2026-09-18T00:00:00+00:00'
            self.assertEqual(ds.missing_comments(), [])
            self.assertEqual(pipeline.ingest(ds, 'Poland'), (1, 1))
            self.assertEqual(pipeline.ingest(ds, 'Poland'), (1, 0))  # idempotentne
            self.assertEqual(s.all_places()[0]['key'], 'p4n:123')
            seed = Path(folder) / 'seed.pack'
            self.assertEqual(pipeline.export_seed(ds, seed), 1)
            self.assertNotIn(b'Polana', seed.read_bytes())
            data = pipeline.load_seed(seed)
            self.assertEqual(data['spots'][0]['name'], 'Polana')
            self.assertNotIn('author', data['spots'][0]['comments'][0])

    def test_seed_if_empty_imports_once(self):
        from app import photo_cache, profiles, web

        with tempfile.TemporaryDirectory() as folder, patch.object(s, 'DATA', Path(folder)):
            s.init()
            profiles.init()
            photo_cache.init()
            seed = Path(folder) / 'seed.pack'
            seed.write_bytes(
                pipeline.pack_seed(
                    dict(
                        spots=[
                            dict(
                                id='1',
                                source='p4n',
                                name='A',
                                lat=50.0,
                                lon=16.0,
                                type='nature',
                                description='',
                                comments=[],
                                photos=[],
                                geo={},
                                evidence=[],
                            )
                        ]
                    )
                )
            )
            with patch.object(web, 'SEED', seed):
                web.seed_if_empty()
                self.assertEqual(len(s.all_places()), 1)
                self.assertEqual(s.get_setting('seed_imported')['places'], 1)
                s.delete_place('p4n:1')
                web.seed_if_empty()  # już zaimportowany — nie wraca po usunięciu przez użytkownika
                self.assertEqual(len(s.all_places()), 0)


class MigrationTests(unittest.TestCase):
    def test_legacy_source_keys_are_renamed(self):
        import json as _json

        legacy = 'park4' + 'night'
        with tempfile.TemporaryDirectory() as folder, patch.object(s, 'DATA', Path(folder)):
            s.init()
            with s.connect() as db:
                db.execute(
                    'insert into places values(?,?,?,?)',
                    (
                        legacy + ':1',
                        legacy,
                        _json.dumps(dict(id='1', source=legacy, name='A', lat=1, lon=1, **{legacy + '_url': 'x'})),
                        0,
                    ),
                )
                db.execute('insert into notes(key,choice,note) values(?,?,?)', (legacy + ':1', 'shortlist', 'n'))
            s.init()
            p = s.all_places()[0]
            self.assertEqual(p['key'], 'p4n:1')
            self.assertEqual(p['source'], 'p4n')
            self.assertIn('p4n_url', p)
            self.assertEqual(p['choice'], 'shortlist')
