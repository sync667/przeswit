"""Two direct public-data connectors with bounded, serial, cached requests."""
import datetime as dt
import hashlib
import html
import json
import math
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from .core import normalize, inside, haversine, valid_url
from . import storage as store

UA='ADVScoutLocal/2.0 (personal local camping research; cached serial requests)'
OVERPASS='https://overpass-api.de/api/interpreter'
BDL='https://mapserver.bdl.lasy.gov.pl/arcgis/rest/services/Czas_w_las/WFS_BDL_czas_w_las/MapServer'
LOCK=threading.Lock()
LAST={}
LAYERS={6:('Miejsce biwakowania','camp_site'),7:('Miejsce biwakowania','camp_site'),
        8:('Pole biwakowe','camp_site'),9:('Pole biwakowe','camp_site'),10:('Kemping','camp_site'),11:('Kemping','camp_site'),
        17:('Parking leśny','parking'),18:('Parking leśny','parking'),19:('Miejsce postoju','parking'),20:('Miejsce postoju','parking'),
        25:('Punkt widokowy','viewpoint'),26:('Punkt wodowania','water_access')}
SOURCES=[
 dict(id='osm',name='OpenStreetMap',mode='automatic',status='Automatyczny import',url='https://www.openstreetmap.org/copyright',
      note='Biwaki, kempingi, punkty widokowe, plaże, pikniki i parkingi oznaczone jako biwakowe. ODbL; nie obejmuje każdego parkingu.'),
 dict(id='bdl',name='Lasy Państwowe / Czas w Las',mode='automatic',status='Automatyczny import',url='https://www.bdl.lasy.gov.pl/portal/uslugi-ogc',
      note='12 warstw: biwaki, pola, kempingi, parkingi, punkty widokowe i wodowania. Dane poglądowe, nie zgoda na wjazd.'),
 dict(id='ioverlander',name='iOverlander',mode='file',status='Oficjalny eksport + folder importu',url='https://ioverlander.com/countries',
      note='Eksport kraju wymaga Unlimited i zalogowania; link przychodzi e-mailem. GPX/CSV/JSON → inbox. Użytek osobisty; AI w chmurze wyłączone.'),
 dict(id='park4night',name='Park4Night',mode='public_web',status='Publiczna mapa · import próbki',url='https://park4night.com/en/cgu',
      note='Nieoficjalny adapter strony: tylko karty dostępne bez logowania. Kategorie za kontem/premium pomijane. Limit 36 żądań/dzień, cache 24 h. Brak gwarancji kompletności; warunki serwisu nadal obowiązują.'),
 dict(id='campercontact',name='Campercontact',mode='external',status='Dostęp partnerski do ustalenia',url='https://www.campercontact.com/en/content/partner-with-campercontact',
      note='Opisane integracje partnerskie i rezerwacyjne nie oznaczają otwartego eksportu wszystkich miejsc. Brak podłączonego API.'),
 dict(id='campinginfo',name='camping.info',mode='external',status='Brak potwierdzonego otwartego feedu',url='https://www.camping.info/en/info/partner-program',
      note='Program afiliacyjny nie jest licencją na bazę. Możliwy import pliku uzyskanego od operatora.'),
 dict(id='opencampingmap',name='OpenCampingMap',mode='shared',status='Miejsca przez OpenStreetMap',url='https://opencampingmap.org/',
      note='Wspólna baza OSM, nie drugie niezależne źródło miejsc. Opinie OpenCampingMap nie są pobierane.'),
 dict(id='files',name='Inne serwisy / własne punkty',mode='file',status='GPX · CSV · GeoJSON · JSON · ZIP',url='',
      note='Folder inbox jest monitorowany podczas działania aplikacji. Pliki muszą pochodzić z uprawnionego eksportu.')]

def now():return dt.datetime.now(dt.timezone.utc).isoformat()

def clean(value):return html.unescape(re.sub('<[^>]+>',' ',str(value or ''))).strip()

def request_json(url,params=None,post=False,provider='bdl',ttl=86400):
    encoded=urllib.parse.urlencode(params or {}).encode()
    key=hashlib.sha256(url.encode()+encoded).hexdigest()
    with LOCK:
        cached=store.cache_get(key,ttl)
        if cached is not None:return cached,True
        pause=store.get_setting('backoff:'+provider,0)-time.time()
        if pause>0:raise ValueError(f'Źródło ograniczyło ruch. Ponów za {math.ceil(pause)} s; nie obchodzimy limitu.')
        time.sleep(max(0,(5 if provider=='osm' else .25)-(time.monotonic()-LAST.get(provider,0))))
        store.allowance(provider)
        req=urllib.request.Request(url if post else url+('?' +encoded.decode() if encoded else ''),
              data=encoded if post else None,headers={'User-Agent':UA,'Accept':'application/json','Content-Type':'application/x-www-form-urlencoded'})
        try:
            with urllib.request.urlopen(req,timeout=50) as r:
                data=r.read(8_000_001)
                if len(data)>8_000_000:raise ValueError('Odpowiedź przekracza 8 MB; zmniejsz obszar.')
            store.account_bytes(provider,len(data))
            result=json.loads(data)
            if result.get('error'):raise ValueError('Źródło zwróciło błąd: '+str(result['error'].get('message',result['error'])))
            if result.get('remark'):raise ValueError('Niepełna odpowiedź Overpass: '+result['remark'])
            store.cache_put(key,result)
            return result,False
        except urllib.error.HTTPError as e:
            if e.code in (429,406,503,504):
                try:delay=max(60,min(3600,int(e.headers.get('Retry-After','60'))))
                except ValueError:delay=60
                store.set_setting('backoff:'+provider,time.time()+delay)
            raise ValueError(f'{provider}: HTTP {e.code}; zapisane wcześniej miejsca pozostają dostępne.')
        except (urllib.error.URLError,TimeoutError):raise ValueError(f'{provider}: brak odpowiedzi. Spróbuj później; cache i lokalna baza są zachowane.')
        finally:LAST[provider]=time.monotonic()

def check_area(a):
    w,s,e,n=a['bbox']
    size=haversine(s,w,s,e)*haversine(s,w,n,w)
    if size>30000 or e-w>6 or n-s>4:
        raise ValueError('Pojedynczy obszar importu: maks. 30 000 km², 6° szerokości i 4° wysokości. Podziel region na mniejsze bbox.')

def osm_query(a):
    w,s,e,n=a['bbox'];box=f'{s:.6f},{w:.6f},{n:.6f},{e:.6f}'
    return f'''[out:json][timeout:35];(
      nwr["tourism"~"^(camp_site|camp_pitch|caravan_site|viewpoint|picnic_site|wilderness_hut)$"]({box});
      nwr["natural"="beach"]({box});nwr["amenity"="parking"]["camping"="yes"]({box});
    );out center tags;'''

def osm_spot(e,stamp):
    t=e.get('tags',{});c=e if 'lat' in e else e.get('center',{})
    if 'lat' not in c or 'lon' not in c:return None
    kind=t.get('tourism') or ('beach' if t.get('natural')=='beach' else 'parking')
    labels={'camp_site':'Biwak / kemping','camp_pitch':'Stanowisko namiotowe','caravan_site':'Miejsce dla kamperów','viewpoint':'Punkt widokowy','picnic_site':'Miejsce piknikowe','wilderness_hut':'Schron terenowy','beach':'Plaża','parking':'Parking'}
    ident=f"{e['type']}/{e['id']}";url='https://www.openstreetmap.org/'+ident
    details=[t.get('description:pl') or t.get('description') or '',t.get('note','')]
    for k in ('access','motorcycle','motor_vehicle','tents','camping','surface','smoothness','opening_hours','fee','operator'):
        if k in t:details.append(f'{k}: {t[k]}')
    geo={'source_url':url,'date':stamp[:10]}
    if 'surface' in t:geo['surface']=t['surface']
    try:
        if 'ele' in t:geo['elevation_m']=float(t['ele'].replace(' m','').replace(',','.'))
    except ValueError:pass
    if kind=='viewpoint':geo['viewpoint']=True
    ev=[]
    motor=t.get('motorcycle',t.get('motor_vehicle',t.get('vehicle',t.get('access'))))
    for topic,value in [('motorcycle',motor),('tent',t.get('tents',t.get('camping')))]:
        if value in ('yes','designated','no','private'):
            ev.append(dict(topic=topic,value='forbidden' if value=='no' else 'unknown' if value=='private' else 'allowed',
                           authority='community',date=None,source_url=url,text=f'OSM {topic}={value}. Tag społeczności; data pobrania nie jest datą potwierdzenia.'))
    photos=[]
    if valid_url(t.get('image','')):photos.append(dict(url=t['image'],caption='Zdjęcie wskazane w OSM; prawa i autor na stronie źródłowej',source_url=url))
    commons=t.get('wikimedia_commons','')
    p=dict(id=ident,source='osm',name=t.get('name:pl') or t.get('name') or labels.get(kind,kind)+' · OSM '+str(e['id']),
           lat=c['lat'],lon=c['lon'],type=kind,description='\n'.join(x for x in details if x),comments=[],photos=photos,evidence=ev,geo=geo,
           source_url=url,license='© OpenStreetMap contributors · ODbL 1.0',fetched_at=stamp,source_date=None,raw=e,
           extra_flags=['Punkt widokowy/piknik/plaża nie jest potwierdzonym noclegiem'] if kind in ('viewpoint','picnic_site','beach','wilderness_hut') else [],
           commons_file=commons if commons.startswith('File:') else '')
    if e['type']!='node':p['extra_flags'].append('Współrzędne środka obiektu OSM — nie zweryfikowanego wjazdu')
    return p

def fetch_osm(a,progress):
    check_area(a);progress('Pobieram miejsca OpenStreetMap…')
    raw,cached=request_json(OVERPASS,{'data':osm_query(a)},post=True,provider='osm')
    stamp=now();places=[p for e in raw.get('elements',[]) if (p:=osm_spot(e,stamp)) and inside(p,a)]
    normalized,_=normalize({'spots':places})
    return normalized,dict(provider='osm',count=len(normalized),cached=cached,status='ok',
        coverage='Wszystkie rekordy odpowiedzi dla wybranych tagów i punktów reprezentatywnych w obszarze. Baza społeczności może mieć braki.',source_date=raw.get('osm3s',{}).get('timestamp_osm_base'))

def representative(g):
    if 'x' in g:return g['y'],g['x']
    pts=[p for ring in g.get('rings',[]) for p in ring]
    if not pts:return None
    return (min(p[1] for p in pts)+max(p[1] for p in pts))/2,(min(p[0] for p in pts)+max(p[0] for p in pts))/2

def bdl_spot(feature,layer,stamp):
    attrs=feature['attributes'];point=representative(feature.get('geometry',{}))
    if not point:return None
    title,kind=LAYERS[layer];ident=str(attrs.get('foreign_key') or f"{layer}/{attrs['objectid']}")
    source_url=BDL+f'/{layer}/query?'+urllib.parse.urlencode(dict(f='pjson',objectIds=attrs['objectid'],outFields='*',outSR=4326))
    fields={'adres':'Adres','rec_od_do':'Dostępność','metod_rez':'Rezerwacja','uwagi':'Uwagi','infr_tow':'Otoczenie','inne_atr':'Atrakcje','otw_od':'Otwarte od','otw_do':'Otwarte do','nocleg':'Nocleg (T/N)','koszt_mnam':'Koszt małego namiotu'}
    desc='\n'.join(f'{label}: {clean(attrs[k])}' for k,label in fields.items() if attrs.get(k) not in (None,'','brak'))
    source_date=None
    if attrs.get('edit_time'):
        try:source_date=dt.datetime.fromtimestamp(attrs['edit_time']/1000,dt.timezone.utc).isoformat()
        except (ValueError,OverflowError):pass
    geo={'forest':True,'source_url':source_url,'date':source_date[:10] if source_date else None}
    if kind=='viewpoint' or attrs.get('pkt_wid')=='T':geo['viewpoint']=True
    if kind=='water_access':geo['water_access_point']=True
    flags=['BDL: sprawdź regulamin obiektu i dojazd. Miejsce biwakowania nie oznacza prawa wjazdu motocyklem.']
    if 'rings' in feature.get('geometry',{}):flags.append('Środek obszaru BDL — sprawdź granice i rzeczywisty wjazd')
    p=dict(id=ident,source='bdl',name=clean(attrs.get('nzw_ob')) or title+' · '+str(attrs['objectid']),lat=point[0],lon=point[1],type=kind,
      description=desc,comments=[],photos=[],evidence=[],geo=geo,source_url=source_url,
      website=attrs.get('link','') if valid_url(attrs.get('link','')) else '',
      fetched_at=stamp,source_date=source_date,license='Bank Danych o Lasach / Lasy Państwowe · regulamin BDL, rozdział V',
      raw=feature,extra_flags=flags)
    # Listing in an official map is not a current official consent for this visitor.
    return p

def fetch_bdl(a,progress):
    check_area(a);allspots=[];reports=[];stamp=now()
    fields='objectid,foreign_key,nzw_ob,adres,link,rec_od_do,metod_rez,uwagi,infr_tow,inne_atr,otw_od,otw_do,nocleg,koszt_mnam,edit_time,pkt_wid'
    for layer,(title,kind) in LAYERS.items():
        try:
            meta,_=request_json(BDL+f'/{layer}',{'f':'json'})
            available={f['name'] for f in meta.get('fields',[])}
            selected_fields=','.join(f for f in fields.split(',') if f in available)
            if 'objectid' not in available:raise ValueError('Zmienił się schemat warstwy BDL; wymagana aktualizacja adaptera.')
            total=0;offset=0;cached_all=True;seen=set()
            while True:
                progress(f'Lasy Państwowe: {title}, warstwa {layer}, od rekordu {offset}…')
                params=dict(f='json',where='1=1',geometry=','.join(str(x) for x in a['bbox']),geometryType='esriGeometryEnvelope',
                            inSR=4326,outSR=4326,spatialRel='esriSpatialRelIntersects',outFields=selected_fields,returnGeometry='true',
                            orderByFields='objectid ASC',resultOffset=offset,resultRecordCount=250)
                raw,cached=request_json(BDL+f'/{layer}/query',params)
                cached_all &= cached
                features=raw.get('features',[])
                ids=[f['attributes']['objectid'] for f in features]
                if any(i in seen for i in ids):raise ValueError('Powtórzona strona odpowiedzi; import warstwy niepełny.')
                seen.update(ids)
                for f in features:
                    p=bdl_spot(f,layer,stamp)
                    if p and inside(p,a):allspots.append(p);total+=1
                if not raw.get('exceededTransferLimit'):break
                if not features or offset>=4750:raise ValueError('Limit/niepełna paginacja. Zmniejsz obszar.')
                offset+=len(features)
            reports.append(dict(layer=layer,status='ok',count=total,cached=cached_all))
        except ValueError as e:reports.append(dict(layer=layer,status='error',message=str(e)))
    normalized,dups=normalize({'spots':allspots})
    return normalized,dict(provider='bdl',count=len(normalized),status='partial' if any(r['status']=='error' for r in reports) else 'ok',layers=reports,
        coverage='12 wybranych warstw BDL, w obszarze według punktów reprezentatywnych; poligony nie są trasą dojazdu.',duplicates=dups)

def distance_segment(lat,lon,a,b):
    scale=111195;cs=math.cos(math.radians(lat))
    ax=(a['lon']-lon)*scale*cs;ay=(a['lat']-lat)*scale
    bx=(b['lon']-lon)*scale*cs;by=(b['lat']-lat)*scale
    vx,vy=bx-ax,by-ay;t=max(0,min(1,-(ax*vx+ay*vy)/(vx*vx+vy*vy))) if vx or vy else 0
    return math.hypot(ax+t*vx,ay+t*vy)

def enrich(p):
    lat,lon=p['lat'],p['lon']
    query=f'''[out:json][timeout:30];(way(around:1200,{lat},{lon})["waterway"~"^(river|stream|canal)$"];way(around:1200,{lat},{lon})["natural"="water"];way(around:200,{lat},{lon})["highway"];);out tags geom;'''
    raw,cached=request_json(OVERPASS,{'data':query},post=True,provider='osm')
    nearest=[]
    for e in raw.get('elements',[]):
        geom=e.get('geometry',[])
        if len(geom)<2:continue
        d=min(distance_segment(lat,lon,a,b) for a,b in zip(geom,geom[1:]))
        nearest.append((d,e))
    water=sorted([(d,e) for d,e in nearest if e.get('tags',{}).get('waterway') or e.get('tags',{}).get('natural')=='water'],key=lambda x:x[0])
    roads=sorted([(d,e) for d,e in nearest if e.get('tags',{}).get('highway')],key=lambda x:x[0])
    p['geo']['context_fetched_at']=now();p['geo']['context_source']='OpenStreetMap / Overpass'
    if water:
        d,e=water[0];p['geo'].update(water_distance_m=round(d),water_kind=e['tags'].get('waterway',e['tags'].get('water','water')),
          water_source_url='https://www.openstreetmap.org/way/'+str(e['id']))
    if roads:
        d,e=roads[0];p['geo'].update(nearest_road_m=round(d),nearest_road_tags=e.get('tags',{}),nearest_road_url='https://www.openstreetmap.org/way/'+str(e['id']))
    p.setdefault('extra_flags',[])
    note='Kontekst OSM: odległość do geometrii wody/drogi, nie zweryfikowana trasa ani prawo dostępu.'
    if note not in p['extra_flags']:p['extra_flags'].append(note)
    if not water:p['geo']['water_search_note']='Nie znaleziono geometrii wody w zapytaniu 1,2 km. Nie dowodzi to braku wody.'
    p.pop('saved_ai',None)
    return p
