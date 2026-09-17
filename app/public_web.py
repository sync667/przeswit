"""Read-only, anonymous public Park4Night map adapter; no auth or greyed categories.

Uses the request and response format emitted by the site's public JS, observed
2026-09-18. Not an official API. Encoding is decoded exactly as the public page.
"""
import base64
import hashlib
import json
import math
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from .core import inside,normalize,haversine,valid_url
from .providers import clean,now,UA,check_area
from . import storage as store

HOST='https://park4night.com'
PUBLIC_TYPES={'ACC_G','ACC_P','ACC_PR','PSS','P','AR','C','F','DS','EP','ASS','SIL','COU','VER','SHO'}
LOCK=threading.Lock()
LAST=0

def get_public(url):
    global LAST
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!='https' or parsed.hostname not in ('park4night.com','www.park4night.com','cdn6.park4night.com'):
        raise ValueError('Niedozwolony adres adaptera publicznego.')
    key='p4n:'+hashlib.sha256(url.encode()).hexdigest()
    with LOCK:
        cached=store.cache_get(key,86400)
        if cached is not None:return cached,True
        wait=store.get_setting('backoff:park4night',0)-time.time()
        if wait>0:raise ValueError(f'Park4Night: przerwa po ograniczeniu dostępu, pozostało {math.ceil(wait)} s.')
        time.sleep(max(0,4-(time.monotonic()-LAST)))
        store.allowance('park4night')
        try:
            req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,text/html,text/plain'})
            with urllib.request.urlopen(req,timeout=30) as r:
                target=urllib.parse.urlparse(r.url)
                if target.hostname not in ('park4night.com','www.park4night.com','cdn6.park4night.com'):raise ValueError('Park4Night przekierował do innej domeny. Import zatrzymany.')
                raw=r.read(2_000_001)
            store.account_bytes('park4night',len(raw))
            if len(raw)>2_000_000:raise ValueError('Park4Night: zbyt duża odpowiedź; import zatrzymany.')
            text=raw.decode('utf-8')
            if any(x in text.lower() for x in ('cf-chl-','verify you are human','challenge-platform','access denied')):
                store.set_setting('backoff:park4night',time.time()+3600)
                raise ValueError('Park4Night: wykryto blokadę/challenge; wymagana zwykła wizyta w serwisie. Brak obchodzenia.')
            store.cache_put(key,text);return text,False
        except urllib.error.HTTPError as e:
            if e.code in (401,403,429):store.set_setting('backoff:park4night',time.time()+3600)
            raise ValueError(f'Park4Night: HTTP {e.code}. Import zatrzymany bez ponawiania z inną tożsamością.')
        except (urllib.error.URLError,TimeoutError):raise ValueError('Park4Night nie odpowiedział. Zapisane dane pozostają lokalnie.')
        finally:LAST=time.monotonic()

def verify_public_contract():
    robots,_=get_public(HOST+'/robots.txt');rp=urllib.robotparser.RobotFileParser();rp.parse(robots.splitlines())
    if not rp.can_fetch(UA,HOST+'/api/places/around'):raise ValueError('robots.txt wyklucza adres mapy. Import zatrzymany.')
    page,_=get_public(HOST+'/en/search')
    urls=re.findall(r'<script[^>]+src="([^"]*app\.min\.js[^\"]*)"',page)
    if not urls:raise ValueError('Zmieniła się strona Park4Night; adapter wymaga aktualizacji.')
    script,_=get_public(urls[-1].replace('&amp;','&'))
    match=re.search(r'"PUBLIC_TYPES",(\[[^\]]+\])',script)
    if not match or '/api/places/around' not in script or 'nature_protect' not in script:
        raise ValueError('Nie można potwierdzić zakresu dostępu anonimowego. Import zatrzymany.')
    # Fail closed: newly advertised categories require a reviewed adapter update.
    return PUBLIC_TYPES.intersection(json.loads(match[1]))

def map_centers(a):
    w,s,e,n=a['bbox'];width=haversine(s,w,s,e);height=haversine(s,w,n,w)
    nx=min(3,max(1,math.ceil(width/40)));ny=min(3,max(1,math.ceil(height/40)))
    centers=[((s+n)/2,(w+e)/2)]
    centers.extend((s+(y+.5)*(n-s)/ny,w+(x+.5)*(e-w)/nx) for y in range(ny) for x in range(nx))
    return list(dict.fromkeys((round(lat,6),round(lon,6)) for lat,lon in centers))

def public_spot(p,allowed,stamp):
    code=p.get('type',{}).get('code')
    # Public JS explicitly replaces these cards with login/subscription prompts.
    if code not in allowed or p.get('nature_protect') not in (0,None,False):return None
    if p.get('waiting_validation'):return None
    if not isinstance(p.get('id'),int):raise ValueError('Zmiana schematu identyfikatora Park4Night.')
    url=HOST+'/en/place/'+str(p['id'])
    kind='camp_site' if code=='C' else 'caravan_site' if code in ('ACC_G','ACC_P','ACC_PR','PSS') else 'parking' if code in ('P','AR') else 'import'
    # Short excerpt only; original page remains the source of full descriptions/reviews.
    words=clean(p.get('description','')).split();excerpt=' '.join(words[:20])+('…' if len(words)>20 else '')
    photos=[]
    for image in (p.get('images') or [])[:3]:
        image_url=image.get('thumb') or image.get('url')
        if valid_url(image_url):photos.append(dict(url=image_url,caption='Miniatura wskazana przez publiczną kartę Park4Night',source_url=url))
    return dict(id=str(p['id']),source='park4night',name=clean(p.get('title') or p.get('name') or 'Park4Night '+str(p['id'])),
       lat=p.get('lat'),lon=p.get('lng'),type=kind,source_type=code,description=excerpt,park4night_url=url,source_url=url,
       comments=[],photos=photos,geo={},evidence=[],fetched_at=stamp,source_date=p.get('created_at'),
       source_rating=p.get('rating'),review_count=p.get('review'),license='Park4Night / autorzy treści · prywatny przegląd; prawa do treści zastrzeżone',
       local_only=True,extra_flags=['Publiczna karta Park4Night; opinie, zgoda na namiot i dojazd nie są automatycznie potwierdzone.'],
       raw={'id':p['id'],'type':code,'lat':p.get('lat'),'lng':p.get('lng'),'rating':p.get('rating'),'review_count':p.get('review')})

def fetch_park4night(a,progress):
    check_area(a);progress('Sprawdzam publiczny zakres Park4Night i robots.txt…');allowed=verify_public_contract()
    centers=map_centers(a);places={};restricted=set();queries=[];stamp=now()
    for i,(lat,lon) in enumerate(centers):
        progress(f'Park4Night: publiczna mapa {i+1}/{len(centers)}; cache i odstęp 4 s…')
        url=HOST+'/api/places/around?'+urllib.parse.urlencode(dict(lat=lat,lng=lon,radius=200,filter='{}',lang='en'))
        body,cached=get_public(url)
        try:
            try:raw=json.loads(body)
            except json.JSONDecodeError:raw=json.loads(base64.b64decode(body,validate=True))
        except (ValueError,UnicodeDecodeError):raise ValueError('Zmienił się format publicznej mapy Park4Night; nie zgadujemy nowego formatu.')
        items=raw.get('places') if isinstance(raw,dict) else raw
        if not isinstance(items,list):raise ValueError('Park4Night: nieoczekiwana odpowiedź mapy.')
        for p in items:
            out=public_spot(p,allowed,stamp)
            if out and inside(out,a):places[out['id']]=out
            elif out is None:restricted.add(p.get('id'))
        queries.append(dict(center=[lat,lon],returned=len(items),cached=cached,possibly_capped=len(items)>=200))
    normalized,_=normalize({'spots':list(places.values())})
    return normalized,dict(provider='park4night',count=len(normalized),status='sampled',queries=queries,omitted_gated_or_unvalidated=len(restricted),
       coverage='Próbkowanie publicznej mapy, NIE pełna baza. Pominięto kategorie wymagające konta/premium i miejsca oczekujące na zatwierdzenie. Lista może być obcięta przez serwis.')
