"""Upheld file imports; ZIP is read in memory, never extracted to filesystem."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from .core import normalize, valid_url
from . import storage as store
from .providers import clean,now

INBOX=Path(__file__).resolve().parent.parent/'inbox'
EXTENSIONS={'.json','.geojson','.csv','.gpx','.zip'}

def make_spot(row,source,ident=None):
    def first(*keys):return next((row[k] for k in keys if row.get(k) not in (None,'')),None)
    lat=first('lat','latitude','Latitude','LAT');lon=first('lon','lng','longitude','Longitude','LON')
    loc=row.get('location')
    if isinstance(loc,dict):lat=lat if lat is not None else loc.get('lat',loc.get('latitude'));lon=lon if lon is not None else loc.get('lon',loc.get('lng',loc.get('longitude')))
    name=clean(first('name','Name','title','Title'))
    desc=clean(first('description','Description','desc','comments'))
    link=first('source_url','url','URL','link','Link','park4night_url') or ''
    if isinstance(link,dict):link=link.get('href','')
    actual='ioverlander' if 'ioverlander' in str(link).lower() or source=='ioverlander' else source
    ident=str(ident or first('id','ID','place_id') or hashlib.sha256(f'{name}:{lat}:{lon}'.encode()).hexdigest()[:20])
    kind=first('type','category','Type','Category') or 'import'
    if isinstance(kind,dict):kind=kind.get('name','import')
    p=dict(id=ident,source=actual,name=name or 'Punkt '+ident,lat=lat,lon=lon,type=str(kind),description=desc,
      source_url=link if valid_url(link) else '',comments=[],photos=[],geo={},evidence=[],fetched_at=now(),
      license='Import użytkownika; zachowaj warunki oryginalnego źródła',raw=row,local_only=actual=='ioverlander')
    if valid_url(link,True):p['park4night_url']=link
    return p

def parse_file(name,content,source='files'):
    suffix=Path(name).suffix.lower()
    if len(content)>20_000_000:raise ValueError('Limit importu: 20 MB.')
    if source not in ('files','ioverlander','park4night','campercontact','campinginfo','own-notes'):raise ValueError('Nieprawidłowe źródło pliku.')
    if 'ioverlander' in name.lower():source='ioverlander'
    raw=[]
    if suffix=='.zip':
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            infos=[i for i in z.infolist() if not i.is_dir() and Path(i.filename).suffix.lower() in EXTENSIONS- {'.zip'}]
            if sum(i.file_size for i in infos)>20_000_000 or len(infos)>50:raise ValueError('ZIP: za dużo plików lub rozmiar po rozpakowaniu >20 MB.')
            if not infos:raise ValueError('ZIP nie zawiera obsługiwanego pliku.')
            for i in infos:raw.extend(parse_file(i.filename,z.read(i),source))
    elif suffix in ('.json','.geojson'):
        d=json.loads(content.decode('utf-8-sig'))
        if isinstance(d,dict) and 'spots' in d:
            raw=d['spots']
            if not isinstance(raw,list):raise ValueError('spots musi być listą.')
            for p in raw:
                p.setdefault('source',source)
                if source=='ioverlander' or p.get('source')=='ioverlander':p['local_only']=True
        elif isinstance(d,dict) and d.get('type')=='FeatureCollection':
            for f in d.get('features',[]):
                g=f.get('geometry') or {}
                if g.get('type')!='Point':raise ValueError('GeoJSON importuje punkty. Zmień geometrię na Point lub użyj dostawcy obszarów.')
                c=g.get('coordinates',[])
                if len(c)<2:raise ValueError('GeoJSON: brak współrzędnych.')
                props=dict(f.get('properties') or {},lat=c[1],lon=c[0]);raw.append(make_spot(props,source,f.get('id')))
        else:
            rows=d if isinstance(d,list) else d.get('places',d.get('data')) if isinstance(d,dict) else None
            if not isinstance(rows,list):raise ValueError('JSON: oczekiwano spots, listy places/data lub GeoJSON FeatureCollection.')
            for r in rows:
                if not isinstance(r,dict):raise ValueError('Rekord JSON musi być obiektem.')
                raw.append(make_spot(r,source))
    elif suffix=='.csv':
        text=content.decode('utf-8-sig')
        try:dialect=csv.Sniffer().sniff(text[:8000],delimiters=',;\t')
        except csv.Error:dialect=csv.excel
        reader=csv.DictReader(io.StringIO(text),dialect=dialect)
        for row in reader:raw.append(make_spot({k.strip():v for k,v in row.items() if k is not None},source))
    elif suffix=='.gpx':
        if b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():raise ValueError('GPX z DTD/ENTITY nie jest obsługiwany.')
        tree=ET.fromstring(content)
        for node in tree.iter():
            if node.tag.split('}')[-1]!='wpt':continue
            row=dict(lat=node.attrib.get('lat'),lon=node.attrib.get('lon'))
            for child in node:
                tag=child.tag.split('}')[-1]
                if tag in ('name','desc','type','cmt'):row['description' if tag in ('desc','cmt') else tag]=child.text or ''
                if tag=='link':row['url']=child.attrib.get('href','')
            raw.append(make_spot(row,source))
        if not raw:raise ValueError('GPX nie zawiera waypointów wpt. Ślady trasy nie są miejscami noclegu.')
    else:raise ValueError('Obsługiwane: JSON, GeoJSON, CSV, GPX, ZIP. KML/KMZ nie są jeszcze obsługiwane.')
    normalized,_=normalize({'spots':raw})
    return normalized

def poll_inbox():
    INBOX.mkdir(exist_ok=True)
    for path in INBOX.iterdir():
        if not path.is_file() or path.suffix.lower() not in EXTENSIONS:continue
        if time.time()-path.stat().st_mtime<3:continue
        if path.stat().st_size>20_000_000:continue
        data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
        with store.connect() as db:old=db.execute('select digest from inbox where name=?',(path.name,)).fetchone()
        if old and old['digest']==digest:continue
        try:
            places=parse_file(path.name,data)
            changed=store.upsert(places);status='ok';message=f'{len(places)} miejsc, {changed} zapisanych/odświeżonych'
        except Exception as e:status='error';message=str(e)[:500]
        with store.connect() as db:db.execute('insert or replace into inbox values(?,?,?,?,?)',(path.name,digest,status,message,time.time()))

def watch(stop):
    while not stop.wait(6):
        try:poll_inbox()
        except OSError:pass
