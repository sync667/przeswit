import copy
import json
import unittest
from unittest.mock import patch
import datetime as dt
from app.core import area_parse,inside,normalize,rank,analyze_ai,TODAY

def spot(**kw):
    raw=dict(id='1',source='test',name='Test',lat=50.9,lon=16.3,description='',type='nature',comments=[],photos=[],geo={},evidence=[])
    raw.update(kw)
    return normalize({'spots':[raw]})[0][0]

def permission(topic,value='allowed',date=None,authority='owner'):
    return dict(topic=topic,value=value,date=date or str(TODAY()),authority=authority,source_url='https://example.org/rules',text='Warunki testowe')

class Tests(unittest.TestCase):
    def test_bbox_and_circle(self):
        self.assertTrue(inside(spot(),area_parse('16,50,17,51')))
        self.assertFalse(inside(spot(lat=51),area_parse('https://park4night.com/en/search?lat=50.9&lng=16.3&z=9',1)))
        self.assertTrue(inside(spot(),area_parse('https://park4night.com/en/search?lat=50.9&lng=16.3&z=9',1)))
    def test_bad_areas(self):
        for text in ['17,50,16,51','nan,50,17,51','https://evil.test/?lat=50&lng=16','1,2,3','1,-91,2,3']:
            with self.assertRaises(ValueError):area_parse(text)
    def test_unknown_is_not_permission(self):
        r=rank(spot(description='Kamper dojechał. Great view. Quiet river.'))
        self.assertEqual(r['status'],'verify')
        self.assertEqual(r['legal_confidence'],0)
        self.assertIsNone(r['scores']['adv_access'])
    def test_all_permissions_required(self):
        r=rank(spot(evidence=[permission(k) for k in ('motorcycle','tent','adjacent')]))
        self.assertEqual(r['status'],'candidate')
        self.assertEqual(r['legal_confidence'],90)
    def test_stale_and_community_do_not_authorize(self):
        for ev in [permission('tent',date='2020-01-01'),permission('tent',authority='community'),permission('tent',date='2999-01-01')]:
            self.assertEqual(rank(spot(evidence=[ev]))['permissions']['tent'],'unknown')
    def test_conflicting_ban_wins(self):
        p=spot(evidence=[permission('tent'),permission('tent','forbidden')])
        self.assertEqual(rank(p)['status'],'excluded')
    def test_ai_cannot_override_ban(self):
        p=spot(evidence=[permission('motorcycle','forbidden')])
        a=dict(scores={k:100 for k in ('adv_access','scenic','water','solitude')},reasons=[],red_flags=[])
        self.assertEqual(rank(p,a)['status'],'excluded')
    def test_ai_null_is_not_keyword_score(self):
        a=dict(scores={k:None for k in ('adv_access','scenic','water','solitude')},reasons=[],red_flags=[])
        self.assertIsNone(rank(spot(description='No view here'),a)['scores']['scenic'])
    def test_ai_cannot_override_difficult_surface(self):
        a=dict(scores={k:100 for k in ('adv_access','scenic','water','solitude')},reasons=[],red_flags=[])
        self.assertEqual(rank(spot(geo={'surface':'mud'}),a)['status'],'excluded')
    def test_dedup(self):
        p=spot();self.assertEqual(normalize({'spots':[p,copy.deepcopy(p)]})[1],1)
    def test_water_and_hard_surface(self):
        r=rank(spot(geo={'water_distance_m':20,'surface':'mud'}))
        self.assertEqual(r['scores']['water'],95);self.assertEqual(r['status'],'excluded')
    def test_link_validation(self):
        with self.assertRaises(ValueError):spot(park4night_url='https://park4night.com.evil.test/x')
        with self.assertRaises(ValueError):spot(photos=[{'url':'javascript:alert(1)'}])
    def test_bad_number(self):
        with self.assertRaises(ValueError):spot(lat=True)
        with self.assertRaises(ValueError):spot(geo={'water_distance_m':-1})
    def test_missing_scores_do_not_inflate(self):
        r=rank(spot());self.assertEqual(r['rank_a'],0);self.assertEqual(r['evidence_coverage'],0)
    def test_protected_requires_review(self):
        r=rank(spot(geo={'protected_area':True},evidence=[permission(k) for k in ('motorcycle','tent','adjacent')]))
        self.assertEqual(r['status'],'verify')
    def test_ai_request_and_validation(self):
        answer=dict(scores=dict(adv_access=None,scenic=70,water=None,solitude=None),reasons=['Opis wskazuje panoramę (description)'],red_flags=[],evidence_ids=['description'],photo_notes=[])
        class Response:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self):return json.dumps({'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps(answer)}]}]}).encode()
        with patch.dict('os.environ',{'OPENAI_API_KEY':'test','OPENAI_MODEL':'test-model'}),patch('urllib.request.urlopen',return_value=Response()) as call:
            a=analyze_ai(spot(description='Widok na góry'))
            self.assertEqual(a['scores']['scenic'],70)
            payload=json.loads(call.call_args.args[0].data)
            self.assertFalse(payload['store'])
            self.assertEqual(payload['text']['format']['type'],'json_schema')
            answer['evidence_ids']=['imaginary']
            with self.assertRaises(ValueError):analyze_ai(spot())

if __name__=='__main__':unittest.main()
