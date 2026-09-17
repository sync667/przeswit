import unittest,tempfile
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from app import storage as s,photo_cache as c,profiles as p
class PhotoCacheTests(unittest.TestCase):
    def test_concurrent_fetch_once_and_offline_reuse(self):
        with tempfile.TemporaryDirectory() as directory,patch.object(s,'DATA',Path(directory)),patch.object(c.time,'sleep'):
            s.init();c.init();calls=[];data=b'\xff\xd8\xfftest'
            def fetch():calls.append(1);return data
            with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:c.get('https://cdn3.park4night.com/test.jpg',fetch),range(2)))
            self.assertEqual(results,[data,data]);self.assertEqual(len(calls),1)
            c.init();self.assertEqual(c.get('https://cdn3.park4night.com/test.jpg',lambda:1/0),data)
            self.assertEqual(c.read(c.key('https://cdn3.park4night.com/test.jpg')),(data,'image/jpeg'))
            self.assertEqual(len(c.url_map()),1)
            self.assertIsNone(c.read('../scout.sqlite3'))
    def test_profile_schema_only_allows_actual_evidence(self):
        good=dict(summary='Opis',scenes=[],unknown=[],warnings=[],observations=[])
        seen=[]
        def call(path,payload,timeout):
            seen.append(payload);return dict(done=True,message=dict(content=__import__('json').dumps(good)))
        with patch.object(p.vision,'local_call',side_effect=call):
            result=p.make_profile(dict(name='Test',photos=[],description='Polana',comments=[],geo={},type='picnic_site'))
        allowed=seen[0]['format']['properties']['observations']['items']['properties']['evidence']['items']['enum']
        self.assertIn('description',allowed);self.assertNotIn('comment:N',allowed);self.assertNotIn('photo:0',allowed)
        self.assertEqual(result['photos_analyzed'],0)
