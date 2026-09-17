import base64
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from app import storage as store
from app import importers
from app import providers
from app import public_web
from app.core import area_parse,normalize

class LocalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=store.DATA;store.DATA=Path(self.tmp.name);store.init()
    def tearDown(self):store.DATA=self.old;self.tmp.cleanup()
    def test_osm_url(self):
        a=area_parse('https://www.openstreetmap.org/#map=10/50.8/16.4',20)
        self.assertEqual(a['center'],[50.8,16.4])
    def test_csv_quoted_and_zero_coordinates(self):
        p=importers.parse_file('test.csv',b'name,latitude,longitude,description\n"Lake, test",0,0,"a,b"')[0]
        self.assertEqual(p['name'],'Lake, test');self.assertEqual(p['lat'],0)
    def test_ioverlander_restricted_to_local(self):
        p=importers.parse_file('ioverlander-poland.json',json.dumps([dict(name='Example',latitude=50,longitude=16)]).encode())[0]
        self.assertTrue(p['local_only']);self.assertEqual(p['source'],'ioverlander')
    def test_geojson(self):
        d=dict(type='FeatureCollection',features=[dict(type='Feature',geometry=dict(type='Point',coordinates=[16,50]),properties=dict(name='Test'))])
        p=importers.parse_file('x.geojson',json.dumps(d).encode())[0];self.assertEqual((p['lat'],p['lon']),(50,16))
        d['features'][0]['geometry']['type']='Polygon'
        with self.assertRaises(ValueError):importers.parse_file('x.geojson',json.dumps(d).encode())
    def test_gpx_and_entities(self):
        gpx=b'<gpx xmlns="http://www.topografix.com/GPX/1/1"><wpt lat="50" lon="16"><name>A &amp; B</name></wpt></gpx>'
        self.assertEqual(importers.parse_file('a.gpx',gpx)[0]['name'],'A & B')
        with self.assertRaises(ValueError):importers.parse_file('a.gpx',b'<!DOCTYPE gpx><gpx/>')
    def test_zip_no_extraction(self):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('../../escape.csv','name,lat,lon\nA,50,16')
        self.assertEqual(len(importers.parse_file('export.zip',buf.getvalue())),1)
        self.assertFalse((store.DATA/'escape.csv').exists())
    def test_upsert_preserves_user_note(self):
        p=importers.parse_file('x.csv',b'name,lat,lon\nA,50,16')[0];store.upsert([p]);key=store.key_for(p)
        store.save_note(key,'A','Dojazd sprawdzony');p['description']='Updated';store.upsert([p])
        row=store.all_places()[0];self.assertEqual(row['choice'],'A');self.assertEqual(row['user_note'],'Dojazd sprawdzony')
    def test_cache(self):
        store.cache_put('x',{'a':1});self.assertEqual(store.cache_get('x'),{'a':1});self.assertIsNone(store.cache_get('x',-1))
    def test_restart_job_marked_interrupted(self):
        store.save_job(dict(id='1',status='running'));store.init();self.assertEqual(store.jobs()[0]['status'],'interrupted')
    def test_osm_does_not_grant_official_permission(self):
        p=providers.osm_spot(dict(type='node',id=1,lat=50,lon=16,tags=dict(tourism='camp_site',motorcycle='yes',tents='yes')),'2026-09-18')
        self.assertTrue(all(e['authority']=='community' and e['date'] is None for e in p['evidence']))
    def test_bdl_dates_and_no_fake_motorcycle_permission(self):
        p=providers.bdl_spot(dict(attributes=dict(objectid=1,nzw_ob='Biwak',nocleg='T',edit_time=1700000000000),geometry=dict(x=16,y=50)),6,'2026-09-18')
        self.assertEqual(p['evidence'],[]);self.assertTrue(p['source_date'].startswith('2023'))
    def test_geometry_distance(self):
        d=providers.distance_segment(50,16,dict(lat=49.99,lon=16.001),dict(lat=50.01,lon=16.001))
        self.assertAlmostEqual(d,71.475,delta=1)
    def test_p4n_hidden_categories_never_imported(self):
        base=dict(id=1,lat=50,lng=16,name='Example',type=dict(code='PN'),nature_protect=0)
        self.assertIsNone(public_web.public_spot(base,public_web.PUBLIC_TYPES,'2026-09-18'))
        base['type']['code']='C';base['nature_protect']=1
        self.assertIsNone(public_web.public_spot(base,public_web.PUBLIC_TYPES,'2026-09-18'))
        base['nature_protect']=0;base['description']='word '*100
        p=public_web.public_spot(base,public_web.PUBLIC_TYPES,'2026-09-18');self.assertTrue(p['local_only']);self.assertEqual(len(p['description'].split()),20)
    def test_public_grid_bounded(self):
        self.assertLessEqual(len(public_web.map_centers(area_parse('15.7,50.5,16.9,51.3'))),10)
    def test_oversize_area(self):
        with self.assertRaises(ValueError):providers.check_area(area_parse('10,40,25,55'))
    def test_daily_web_budget(self):
        for _ in range(36):store.allowance('park4night')
        with self.assertRaises(ValueError):store.allowance('park4night')
    def test_overpass_remark_not_success(self):
        class R:
            def __enter__(self):return self
            def __exit__(self,*a):pass
            def read(self,*a):return b'{"remark":"timeout","elements":[]}'
        with patch('urllib.request.urlopen',return_value=R()),patch('time.sleep'):
            with self.assertRaises(ValueError):providers.request_json(providers.OVERPASS,{'data':'mock'},provider='osm')
    def test_bdl_pagination_and_errors_reported(self):
        feature=dict(attributes=dict(objectid=1,nzw_ob='Test'),geometry=dict(x=16,y=50))
        def fake(url,params):
            if '/query' not in url:return {'fields':[{'name':'objectid'},{'name':'nzw_ob'}]},True
            if params['resultOffset']==0:return {'features':[feature],'exceededTransferLimit':True},True
            return {'features':[],'exceededTransferLimit':False},True
        with patch.dict(providers.LAYERS,{6:('Test','camp_site')},clear=True),patch.object(providers,'request_json',side_effect=fake):
            places,report=providers.fetch_bdl(area_parse('15.9,49.9,16.1,50.1'),lambda m:None)
            self.assertEqual(len(places),1);self.assertEqual(report['status'],'ok')
        def bad(url,params):raise ValueError('Down')
        with patch.dict(providers.LAYERS,{6:('Test','camp_site')},clear=True),patch.object(providers,'request_json',side_effect=bad):
            _,report=providers.fetch_bdl(area_parse('15.9,49.9,16.1,50.1'),lambda m:None)
            self.assertEqual(report['status'],'partial')

if __name__=='__main__':unittest.main()
