import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path
from przeswit import profiles as p
from przeswit import storage as s
class ProfileTests(unittest.TestCase):
    def test_unknown_does_not_match_required(self):
        q={'conditions':[dict(feature='river',target=100,weight=5,required=True)]}
        r=p.score_profile({'observations':[]},q)
        self.assertEqual(r['match'],0);self.assertFalse(r['requirements_met']);self.assertEqual(r['coverage'],0)
    def test_negative_preference(self):
        q={'conditions':[dict(feature='mud',target=0,weight=1,required=True)]}
        r=p.score_profile({'observations':[dict(feature='mud',score=100,confidence=100,reason='błoto')]},q)
        self.assertEqual(r['match'],0);self.assertFalse(r['requirements_met'])
    def test_query_unknown_feature(self):
        with self.assertRaises(ValueError):p.validate_query(dict(interpretation='x',unsupported=[],conditions=[dict(feature='legal',target=100,weight=1,required=True)]))
    def test_photo_reference_must_exist(self):
        a=dict(summary='x',scenes=[],unknown=[],warnings=[],observations=[dict(feature='river',score=90,confidence=90,reason='rzeka',evidence=['photo:0'])])
        with self.assertRaises(ValueError):p.validate_profile(a,{'description'})
    def test_queue_survives_restart_and_invalidates_changed_source(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(s,'DATA',Path(folder)):
            s.init();p.init();place=dict(source='test',id='1',name='Pierwsze',photos=[])
            s.upsert([place]);p.sync_queue()
            with s.connect() as db:db.execute("update profiles set status='running'")
            p.init();self.assertEqual(p.profiles_map()['test:1']['status'],'pending')
            with s.connect() as db:db.execute("update profiles set status='ready',body='{}'")
            p.sync_queue();self.assertEqual(p.profiles_map()['test:1']['status'],'ready')
            place['name']='Zmienione';s.upsert([place]);p.sync_queue();self.assertEqual(p.profiles_map()['test:1']['status'],'pending')
    def test_query_confidence_reduces_score(self):
        r=p.score_profile({'observations':[dict(feature='river',score=100,confidence=20,reason='wzmianka')]},{'conditions':[dict(feature='river',target=100,weight=1,required=False)]})
        self.assertEqual(r['match'],20)

    def test_query_discards_invented_preference(self):
        q=dict(interpretation='polana',unsupported=['pogoda'],conditions=[dict(feature='meadow',target=100,weight=5,required=True,quote='polany'),dict(feature='river',target=0,weight=1,required=False,quote='bez rzeki')])
        result=p.validate_query(q,'Szukam polany')
        self.assertEqual(len(result['conditions']),1)
        self.assertFalse(result['conditions'][0]['required'])
        self.assertEqual(result['unsupported'],[])
    def test_explicit_required_preference(self):
        q=dict(interpretation='bez zabudowy',unsupported=[],conditions=[dict(feature='low_buildings',target=100,weight=5,required=True,quote='Koniecznie bez zabudowy')])
        self.assertTrue(p.validate_query(q,'Koniecznie bez zabudowy')['conditions'][0]['required'])

    def test_text_and_latest_comments_are_sent_with_metadata(self):
        place=dict(description='Rzeka 300 m, bez toalety',type='camp_site',geo={},fee='30 PLN',comments=[dict(text='stara relacja',date='2020-01-01'),dict(text='nowy szlaban',date='2026-09-01')],evidence=[])
        sources,coverage=p.source_material(place)
        self.assertEqual(sources[0]['text'],place['description'])
        comments=[x for x in sources if x['id'].startswith('comment:')]
        self.assertEqual(comments[0]['id'],'comment:1')
        self.assertEqual(comments[0]['data']['text'],'nowy szlaban')
        self.assertEqual(coverage['comments_used'],2)
        self.assertEqual(next(x for x in sources if x['id']=='metadata')['data']['fee'],'30 PLN')

    def test_comment_change_invalidates_profile(self):
        place=dict(name='Test',description='Opis',comments=[dict(text='Cicho',date='2020-01-01')])
        before=p.digest(place)
        place['comments']=[dict(text='Nowy szlaban',date='2026-09-18')]
        self.assertNotEqual(before,p.digest(place))
    def test_comment_limit_is_explicit(self):
        place=dict(description='x',comments=[dict(text=str(i),date=f'2026-09-{i+1:02d}') for i in range(20)])
        sources,c=p.source_material(place)
        self.assertEqual(c['comments_total'],20)
        self.assertEqual(c['comments_used'],15)
        self.assertEqual(next(x for x in sources if x['id'].startswith('comment:'))['data']['text'],'19')
