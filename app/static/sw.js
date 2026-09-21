// Service worker PWA: statyki z cache (aktualizowane w tle), API zawsze z sieci; offline pokazuje ostatnią wersję aplikacji.
const CACHE='przeswit-static-v1';
const CORE=['/','/static/style.css','/static/js/main.js','/static/logo.svg','/static/vendor/leaflet.js','/static/vendor/leaflet.css','/static/manifest.webmanifest'];
self.addEventListener('install',e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(CORE)).then(()=>self.skipWaiting()));});
self.addEventListener('activate',e=>{e.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',e=>{
 const url=new URL(e.request.url);
 if(e.request.method!=='GET'||url.origin!==location.origin)return;
 if(url.pathname.startsWith('/api/')||url.pathname.startsWith('/photos/'))return;
 e.respondWith(caches.open(CACHE).then(async c=>{const cached=await c.match(e.request);const network=fetch(e.request).then(r=>{if(r.ok)c.put(e.request,r.clone());return r;}).catch(()=>cached);return cached||network;}));
});
