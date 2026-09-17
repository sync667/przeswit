"""Slow persistent cache of already imported image URLs, never a site crawler."""
import hashlib,json,re,shutil,threading,time
from urllib.parse import urlparse
from . import storage as store
LOCK=threading.Lock();LAST_FETCH=0;LIMIT=50*1024**3

def init():
    with store.connect() as db:db.execute('create table if not exists photo_cache (key text primary key,url text unique,status text,size integer,error text,retry_at real,updated real)')
def key(url):return hashlib.sha256(url.encode()).hexdigest()
def folder():
    p=store.DATA/'photos';p.mkdir(parents=True,exist_ok=True);return p

def get(url,fetch):
    global LAST_FETCH
    k=key(url)
    with LOCK:
        path=folder()/k
        with store.connect() as db:row=db.execute('select * from photo_cache where key=?',(k,)).fetchone()
        if row and row['status']=='ready' and path.exists():return path.read_bytes()
        host=urlparse(url).hostname or ''
        if store.get_setting('photo_backoff:'+host,0)>time.time():raise ValueError('Serwer zdjęć chwilowo niedostępny; pobieranie dla źródła odłożone.')
        if row and row['retry_at']>time.time():raise ValueError(row['error'] or 'Pobieranie zdjęcia odłożone.')
        with store.connect() as db:used=db.execute("select coalesce(sum(size),0) from photo_cache where status='ready'").fetchone()[0]
        if used>=LIMIT or shutil.disk_usage(folder()).free<2*1024**3:raise ValueError('Pamięć zdjęć pełna lub mniej niż 2 GB wolnego dysku.')
        time.sleep(max(0,2-(time.monotonic()-LAST_FETCH)))
        try:
            LAST_FETCH=time.monotonic();data=fetch()
            if used+len(data)>LIMIT:raise ValueError('Limit pamięci zdjęć: 50 GB.')
            partial=path.with_suffix('.partial');partial.write_bytes(data);partial.replace(path)
            with store.connect() as db:db.execute('insert or replace into photo_cache values(?,?,?,?,?,?,?)',(k,url,'ready',len(data),None,0,time.time()))
            return data
        except Exception as e:
            if getattr(e,'code',None) in (401,403,429):store.set_setting('photo_backoff:'+host,time.time()+86400)
            with store.connect() as db:db.execute('insert or replace into photo_cache values(?,?,?,?,?,?,?)',(k,url,'error',0,str(e)[:300],time.time()+86400,time.time()))
            raise

def url_map():
    with store.connect() as db:rows=db.execute("select key,url from photo_cache where status='ready'").fetchall()
    return {r['url']:'/photos/'+r['key'] for r in rows if (folder()/r['key']).exists()}
def read(k):
    if not re.fullmatch('[a-f0-9]{64}',k):return None
    path=folder()/k
    if not path.is_file():return None
    data=path.read_bytes();mime='image/jpeg' if data.startswith(b'\xff\xd8') else 'image/png' if data.startswith(b'\x89PNG') else 'image/webp'
    return data,mime

def status():
    with store.connect() as db:
        rows=db.execute('select status,count(*) n,coalesce(sum(size),0) bytes from photo_cache group by status').fetchall()
    return dict(counts={r['status']:r['n'] for r in rows},bytes=sum(r['bytes'] for r in rows),limit=LIMIT,path=str(folder()),paused=bool(store.get_setting('photos_paused',False)))
def worker(stop):
    from . import local_vision as vision
    from urllib.parse import urlparse
    while not stop.is_set():
        try:
            seen=set()
            for p in store.all_places():
                for ph in p.get('photos',[]):
                    if stop.is_set():return
                    if store.get_setting('photos_paused',False):break
                    url=ph.get('url','')
                    if url in seen or urlparse(url).hostname not in vision.HOSTS:continue
                    seen.add(url)
                    try:vision.image_bytes(url)
                    except Exception:pass
                    if stop.wait(.1):return
                if store.get_setting('photos_paused',False):break
        except Exception:pass
        stop.wait(30)
