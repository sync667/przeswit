"""Prześwit: stdlib HTTP, SQLite, source jobs, watched export folder."""
import base64
import json
import logging
import os
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from .core import normalize,inside,rank,analyze_ai
from . import storage as store
from . import providers
from . import importers
from . import sync
from . import local_vision
from . import profiles
from . import ai_runtime
from . import photo_cache

ROOT=Path(__file__).resolve().parent.parent
TOKEN=secrets.token_urlsafe(24)

def ranked(p):return rank(p,p.get('saved_ai'))

class Handler(BaseHTTPRequestHandler):
    def send(self,data,status=200,kind='application/json; charset=utf-8'):
        body=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False,allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','strict-origin-when-cross-origin')
        self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers();self.wfile.write(body)

    def host_ok(self):return self.headers.get('Host') in ('127.0.0.1:8765','localhost:8765')

    def do_GET(self):
        if not self.host_ok():return self.send({'error':'Host rejected'},403)
        path=urlparse(self.path).path
        if path=='/api/config':return self.send(dict(token=TOKEN,ai_ready=bool(os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_MODEL')),sources=providers.SOURCES,
            last_area=store.get_setting('last_area'),inbox=str(importers.INBOX),version='2.0-local'))
        if path.startswith('/photos/'):
            item=photo_cache.read(path[len('/photos/'):])
            return self.send(item[0],kind=item[1]) if item else self.send({'error':'Zdjęcie niedostępne'},404)
        if path=='/api/photos':return self.send(photo_cache.status())
        if path=='/api/database':return self.send(store.database_info())
        if path=='/api/profiles':return self.send(profiles.snapshot())
        if path=='/api/local-ai':return self.send(local_vision.status())
        if path=='/api/status':return self.send(dict(jobs=store.jobs(),inbox=store.inbox_rows()))
        files={'/logo.svg':'static/logo.svg','/':'static/index.html','/app.js':'static/app.js','/style.css':'static/style.css','/template.json':'examples/template.json','/demo.json':'examples/demo.json',
               '/vendor/leaflet.js':'static/vendor/leaflet.js','/vendor/leaflet.css':'static/vendor/leaflet.css'}
        if path not in files:return self.send({'error':'Not found'},404)
        file=ROOT/files[path]
        return self.send(file.read_bytes(),kind={'.svg':'image/svg+xml','.js':'text/javascript','.html':'text/html','.css':'text/css','.json':'application/json'}[file.suffix]+'; charset=utf-8')

    def do_POST(self):
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=28_000_000:raise ValueError('Limit żądania: 28 MB.')
            raw=self.rfile.read(size)
            if not self.host_ok() or self.headers.get('X-ADV-Token')!=TOKEN:return self.send({'error':'Unauthorized'},403)
            if self.headers.get('Origin') not in (None,'http://127.0.0.1:8765','http://localhost:8765'):return self.send({'error':'Origin rejected'},403)
            b=json.loads(raw)
            if not isinstance(b,dict):raise ValueError('Żądanie musi być obiektem JSON.')
            if self.path=='/api/photos/pause':
                if not isinstance(b.get('paused'),bool):raise ValueError('Nieprawidłowy stan.')
                store.set_setting('photos_paused',b['paused']);return self.send(photo_cache.status())
            if self.path=='/api/database/backup':return self.send(dict(path=store.daily_backup(force=True)))
            if self.path=='/api/profiles/parallel':
                choice=b.get('mode')
                if choice not in ('auto','1','2'):raise ValueError('Wybierz auto, 1 lub 2.')
                store.set_setting('profile_parallel',choice);return self.send(dict(ok=True))
            if self.path=='/api/profile-search':return self.send(profiles.search(b.get('criteria')))
            if self.path=='/api/profiles/pause':
                if not isinstance(b.get('paused'),bool):raise ValueError('Nieprawidłowy stan kolejki.')
                store.set_setting('profiles_paused',b['paused']);return self.send(profiles.snapshot())
            if self.path=='/api/profiles/retry':
                with store.connect() as db:db.execute("update profiles set status='pending',attempts=0,retry_at=0 where status='error'")
                return self.send(dict(ok=True))
            if self.path=='/api/local-ai':return self.send(dict(result=local_vision.analyze(b.get('key'),b.get('criteria'))))
            if self.path=='/api/sync':return self.send(sync.start(b.get('areas',''),b.get('radius',40),b.get('sources',[])))
            if self.path=='/api/library':
                areas=sync.parse_areas(b.get('areas',''),b.get('radius',40)) if b.get('areas') else []
                places=store.all_places();pm=profiles.profiles_map()
                for p in places:
                    info=pm.get(p['key'])
                    p['profile_info']=info if info and info['fingerprint']==profiles.digest(p) else {'status':'pending','profile':None}
                selected=[p for p in places if not areas or any(inside(p,a) for a in areas)]
                if b.get('save_area') and areas:store.set_setting('last_area',dict(areas=b['areas'],radius=b.get('radius',40)))
                return self.send(dict(photo_cache=photo_cache.url_map(),spots=[ranked(p) for p in selected],areas=areas,total=len(places),outside=len(places)-len(selected)))
            if self.path=='/api/import':
                content=base64.b64decode(b.get('content',''),validate=True)
                places=importers.parse_file(b.get('name',''),content,b.get('source','files'))
                return self.send(dict(imported=len(places),saved=store.upsert(places)))
            if self.path=='/api/note':
                store.save_note(b.get('key'),b.get('choice',''),b.get('note',''));return self.send(dict(ok=True))
            if self.path=='/api/enrich':
                p=providers.enrich(store.get_place(b.get('key')));store.upsert([p]);return self.send(dict(spot=ranked(p)))
            if self.path=='/api/ai':
                p=store.get_place(b.get('key'))
                if p.get('local_only') or p.get('source')=='ioverlander':raise ValueError('Ten rekord jest przeznaczony do użytku lokalnego; nie wysyłamy go do zewnętrznego AI.')
                a=analyze_ai(p,b.get('photos') is True);p['saved_ai']=a;store.upsert([p]);return self.send(dict(spot=ranked(p)))
            if self.path=='/api/commons':
                p=store.get_place(b.get('key'));file=p.get('commons_file','')
                if not isinstance(file,str) or not file.startswith('File:') or len(file)>400:raise ValueError('Brak odnośnika do pliku Wikimedia Commons.')
                data,_=providers.request_json('https://commons.wikimedia.org/w/api.php',dict(action='query',format='json',titles=file,prop='imageinfo',iiprop='url|extmetadata',iiurlwidth=600),provider='commons',ttl=604800)
                page=next(iter(data.get('query',{}).get('pages',{}).values()),{})
                info=(page.get('imageinfo') or [{}])[0];meta=info.get('extmetadata',{})
                url=info.get('thumburl') or info.get('url','')
                if not url.startswith('https://upload.wikimedia.org/'):raise ValueError('Brak zdjęcia Commons do wyświetlenia.')
                photo=dict(url=url,caption=file,source_url=info.get('descriptionurl',''),author=providers.clean(meta.get('Artist',{}).get('value')),
                    license=providers.clean(meta.get('LicenseShortName',{}).get('value')),license_url=meta.get('LicenseUrl',{}).get('value',''))
                p['photos']=[x for x in p['photos'] if x.get('caption')!=file]+[photo];p.pop('saved_ai',None);store.upsert([p]);return self.send(dict(spot=ranked(p)))
            if self.path=='/api/rank':
                places,dups=normalize(b.get('dataset'));areas=sync.parse_areas(b.get('areas',''),b.get('radius',40))
                selected=[p for p in places if any(inside(p,a) for a in areas)]
                return self.send(dict(spots=[rank(p) for p in selected],areas=areas,imported=len(places),duplicates=dups,outside=len(places)-len(selected)))
            return self.send({'error':'Not found'},404)
        except HTTPError as e:self.send({'error':f'Zewnętrzna usługa: HTTP {e.code}; dane lokalne zachowane.'},502)
        except (URLError,TimeoutError):self.send({'error':'Brak odpowiedzi zewnętrznej usługi. Dane lokalne zachowane.'},502)
        except (ValueError,TypeError,KeyError) as e:self.send({'error':str(e)},400)
        except Exception:
            logging.exception('Request failed');self.send({'error':'Błąd aplikacji; sprawdź log serwera. Dane lokalne zachowane.'},500)

def main():
    store.init();profiles.init();photo_cache.init();store.daily_backup();ai_runtime.ensure();stop=threading.Event();profile_worker=threading.Thread(target=profiles.worker,args=(stop,),daemon=True);profile_worker.start();threading.Thread(target=photo_cache.worker,args=(stop,),daemon=True).start();threading.Thread(target=importers.watch,args=(stop,),daemon=True).start()
    http=ThreadingHTTPServer(('127.0.0.1',8765),Handler)
    print('Prześwit: http://127.0.0.1:8765 · Ctrl+C kończy pracę',flush=True)
    try:http.serve_forever()
    except KeyboardInterrupt:pass
    finally:stop.set();http.server_close();profile_worker.join(timeout=250)

if __name__=='__main__':main()
