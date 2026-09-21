// Planowane trasy GPX na mapie: wiele plików naraz (ślady z segmentami, trasy <rte>, punkty <wpt>),
// odległość każdego miejsca od najbliższej trasy, filtr „w pobliżu trasy”. Trasy są pamiętane w localStorage.
import {$,el,notify,download} from './dom.js';
import {state,SAVED_CHOICES} from './state.js';
import {render} from './cards.js';
import {t} from './i18n.js';

const STORAGE_KEY='przeswit-routes';
const STORAGE_LIMIT=4_000_000;              // localStorage ma zwykle ~5 MB; powyżej tego trasy żyją tylko do odświeżenia
const COLORS=['#d9480f','#1c7ed6','#7048e8','#e8590c','#0b7285','#c2255c','#5c940d','#862e9c'];
const DEFAULT_RANGE_KM=5;
let colorIndex=0;

function haversineM(aLat,aLon,bLat,bLon){const rad=x=>x*Math.PI/180;const y=Math.sin(rad(bLat-aLat)/2)**2+Math.cos(rad(aLat))*Math.cos(rad(bLat))*Math.sin(rad(bLon-aLon)/2)**2;return 6371000*2*Math.asin(Math.min(1,Math.sqrt(y)));}

// Odległość punktu od odcinka w metrach (rzut równoodległościowy — wystarczający dla odległości do kilkudziesięciu km).
function segmentDistanceM(lat,lon,a,b){
 const kx=111320*Math.cos(lat*Math.PI/180),ky=110540;
 const px=(lon-a[1])*kx,py=(lat-a[0])*ky,vx=(b[1]-a[1])*kx,vy=(b[0]-a[0])*ky;
 const len2=vx*vx+vy*vy;const t=len2?Math.max(0,Math.min(1,(px*vx+py*vy)/len2)):0;
 const dx=px-t*vx,dy=py-t*vy;return Math.sqrt(dx*dx+dy*dy);
}

function pointsOf(nodes){const out=[];for(const n of nodes){const lat=parseFloat(n.getAttribute('lat')),lon=parseFloat(n.getAttribute('lon'));if(Number.isFinite(lat)&&Number.isFinite(lon))out.push([+lat.toFixed(5),+lon.toFixed(5)]);}return out;}

// GPX 1.0/1.1: <trk><trkseg><trkpt>, <rte><rtept>, <wpt>. Każdy segment to osobna linia, więc przerwy w śladzie zostają przerwami.
export function parseGPX(text,fileName){
 const doc=new DOMParser().parseFromString(text,'application/xml');
 if(doc.querySelector('parsererror'))throw Error(t('{file}: to nie jest poprawny plik GPX/XML.',{file:fileName}));
 const q=sel=>[...doc.getElementsByTagNameNS('*',sel)];
 const lines=[];
 for(const trk of q('trk')){const name=trk.getElementsByTagNameNS('*','name')[0]?.textContent?.trim()||'';for(const seg of [...trk.getElementsByTagNameNS('*','trkseg')]){const pts=pointsOf([...seg.getElementsByTagNameNS('*','trkpt')]);if(pts.length>1)lines.push({name,points:pts,kind:'track'});}}
 for(const rte of q('rte')){const name=rte.getElementsByTagNameNS('*','name')[0]?.textContent?.trim()||'';const pts=pointsOf([...rte.getElementsByTagNameNS('*','rtept')]);if(pts.length>1)lines.push({name,points:pts,kind:'route'});}
 const waypoints=q('wpt').map(w=>{const [p]=pointsOf([w]);return p?{lat:p[0],lon:p[1],name:w.getElementsByTagNameNS('*','name')[0]?.textContent?.trim()||''}:null;}).filter(Boolean);
 if(!lines.length&&!waypoints.length)throw Error(t('{file}: brak śladów, tras ani punktów.',{file:fileName}));
 const meta=doc.getElementsByTagNameNS('*','metadata')[0];
 const name=meta?.getElementsByTagNameNS('*','name')[0]?.textContent?.trim()||lines[0]?.name||fileName.replace(/\.gpx$/i,'');
 let lengthM=0;for(const l of lines)for(let i=1;i<l.points.length;i++)lengthM+=haversineM(...l.points[i-1],...l.points[i]);
 return {id:`${Date.now().toString(36)}-${Math.random().toString(36).slice(2,7)}`,name,file:fileName,lines,waypoints,lengthM,color:COLORS[colorIndex++%COLORS.length]};
}

// Pozycja miejsca wzdłuż trasy: km od startu najbliższej linii (rzut na najbliższy odcinek) + odległość od trasy.
export function routePosition(p){
 let best=null;
 for(const r of state.routes){let base=0;for(const l of r.lines){const pts=l.points;let cum=0;for(let i=1;i<pts.length;i++){const segLen=haversineM(...pts[i-1],...pts[i]);const d=segmentDistanceM(p.lat,p.lon,pts[i-1],pts[i]);if(!best||d<best.offM){const t=projectT(p.lat,p.lon,pts[i-1],pts[i]);best={route:r,offM:d,alongM:base+cum+segLen*t};}cum+=segLen;}base+=cum;}}
 return best;
}
function projectT(lat,lon,a,b){const kx=111320*Math.cos(lat*Math.PI/180),ky=110540;const px=(lon-a[1])*kx,py=(lat-a[0])*ky,vx=(b[1]-a[1])*kx,vy=(b[0]-a[0])*ky;const len2=vx*vx+vy*vy;return len2?Math.max(0,Math.min(1,(px*vx+py*vy)/len2)):0;}

// Plan: zachowane miejsca w zasięgu trasy, uszeregowane wg km od startu i podzielone na dni.
export function buildPlan(kmPerDay){
 const items=state.places.filter(p=>SAVED_CHOICES.includes(p.choice)||p.source==='own-notes'&&p.own_status==='planned').map(p=>({p,pos:routePosition(p)})).filter(x=>x.pos&&x.pos.offM<=nearRouteRange()*1000).sort((a,b)=>a.pos.alongM-b.pos.alongM);
 const days=[];for(const it of items){const day=Math.floor(it.pos.alongM/1000/kmPerDay)+1;(days[day]=days[day]||[]).push(it);}
 return {items,days};
}

export function exportPlanGPX(){
 const {items}=buildPlan(planKmPerDay());
 const doc=document.implementation.createDocument('http://www.topografix.com/GPX/1/1','gpx');const root=doc.documentElement;root.setAttribute('version','1.1');root.setAttribute('creator','Prześwit');
 const ns=root.namespaceURI;const add=(parent,tag,text)=>{const e=doc.createElementNS(ns,tag);if(text!=null)e.textContent=text;parent.append(e);return e;};
 for(const [i,{p,pos}] of items.entries()){const w=doc.createElementNS(ns,'wpt');w.setAttribute('lat',p.lat);w.setAttribute('lon',p.lon);add(w,'name',`${i+1}. ${p.name}`);add(w,'desc',t('km {km} · {dist}{note}',{km:(pos.alongM/1000).toFixed(0),dist:formatDistance(pos.offM),note:p.user_note?' · '+p.user_note:''}));add(w,'sym','Campground');root.append(w);}
 for(const r of state.routes)for(const l of r.lines){const trk=add(root,'trk');add(trk,'name',r.name);const seg=add(trk,'trkseg');for(const [la,lo] of l.points){const pt=doc.createElementNS(ns,'trkpt');pt.setAttribute('lat',la);pt.setAttribute('lon',lo);seg.append(pt);}}
 download('<?xml version="1.0" encoding="UTF-8"?>\n'+new XMLSerializer().serializeToString(doc),'application/gpx+xml','przeswit-plan.gpx');
}
function planKmPerDay(){return Math.max(20,parseFloat($('plan-km')?.value)||250);}

export function renderPlan(){
 const box=$('route-plan');if(!box)return;
 if(!state.routes.length){box.hidden=true;return;}
 box.hidden=false;const list=$('plan-list');list.replaceChildren();
 const {items,days}=buildPlan(planKmPerDay());
 if(!items.length){list.append(el('p',t('Brak zachowanych miejsc w zasięgu {range} km od trasy. Zachowaj miejsca (＋), a pojawią się tu w kolejności jazdy.',{range:nearRouteRange()}),'hint'));return;}
 days.forEach((day,n)=>{if(!day)return;const h=el('h4',t('Dzień {n} · km {from}–{to}',{n,from:(n-1)*planKmPerDay(),to:n*planKmPerDay()}));list.append(h);for(const {p,pos} of day){const row=el('div',undefined,'plan-item');const open=el('button',p.name,'route-name');open.onclick=()=>import('./detail.js').then(m=>m.showDetail(p.key));row.append(el('span',t('km {km}',{km:(pos.alongM/1000).toFixed(0)}),'plan-km'),open,el('span',formatDistance(pos.offM),'route-distance'));list.append(row);}});
}

export function routeDistanceM(p){
 let best=Infinity;
 for(const r of state.routes){for(const l of r.lines){const pts=l.points;for(let i=1;i<pts.length;i++){const d=segmentDistanceM(p.lat,p.lon,pts[i-1],pts[i]);if(d<best)best=d;}}for(const w of r.waypoints){const d=haversineM(p.lat,p.lon,w.lat,w.lon);if(d<best)best=d;}}
 return best;
}

export function recomputeDistances(){
 state.routeDistance=new Map();
 if(!state.routes.length)return;
 for(const p of state.places)state.routeDistance.set(p.key,routeDistanceM(p));
}

export function formatDistance(m){if(!Number.isFinite(m))return '';return m<1000?t('{m} m od trasy',{m:Math.round(m)}):t('{km} km od trasy',{km:(m/1000).toFixed(m<10000?1:0)});}

export function nearRouteRange(){return Math.max(0.1,parseFloat($('route-range')?.value)||DEFAULT_RANGE_KM);}
export function nearRouteActive(){return state.routes.length>0&&!!$('route-only')?.checked;}
export function isNearRoute(p){const d=state.routeDistance.get(p.key);return d!==undefined&&d<=nearRouteRange()*1000;}

function persist(){
 try{const data=JSON.stringify(state.routes.map(r=>({...r})));if(data.length>STORAGE_LIMIT){notify(t('Trasy GPX są zbyt duże, by je zapamiętać między odświeżeniami (limit ~4 MB); zostaną do zamknięcia strony.'),true);localStorage.removeItem(STORAGE_KEY);return;}localStorage.setItem(STORAGE_KEY,data);}catch{}
}

function restore(){
 try{const raw=localStorage.getItem(STORAGE_KEY);if(!raw)return;const list=JSON.parse(raw);if(Array.isArray(list))state.routes=list.filter(r=>r&&Array.isArray(r.lines));colorIndex=state.routes.length;}catch{}
}

function drawRoutes(){
 if(!state.map)return;
 if(!state.routeLayer)state.routeLayer=L.layerGroup().addTo(state.map);
 state.routeLayer.clearLayers();
 for(const r of state.routes){
  for(const l of r.lines){L.polyline(l.points,{color:'#fff',weight:7,opacity:.7}).addTo(state.routeLayer);L.polyline(l.points,{color:r.color,weight:4,opacity:.95,dashArray:l.kind==='route'?'8 6':null}).addTo(state.routeLayer).bindTooltip(`${r.name}${l.name&&l.name!==r.name?' · '+l.name:''}`,{sticky:true});}
  for(const w of r.waypoints)L.circleMarker([w.lat,w.lon],{radius:5,color:'#fff',weight:2,fillColor:r.color,fillOpacity:1}).addTo(state.routeLayer).bindTooltip(w.name||r.name);
 }
}

function fitRoute(r){
 if(!state.map||!state.mapView)return;
 const pts=[...r.lines.flatMap(l=>l.points),...r.waypoints.map(w=>[w.lat,w.lon])];
 if(pts.length)state.map.fitBounds(pts,{padding:[30,30]});
}

function renderList(){
 const list=$('route-list');if(!list)return;list.replaceChildren();
 for(const r of state.routes){
  const item=el('div',undefined,'route-item');const swatch=el('span',undefined,'route-swatch');swatch.style.background=r.color;
  const label=el('button',undefined,'route-name');label.append(el('strong',r.name),el('span',' · '+t('{km} km · {n} {word}',{km:(r.lengthM/1000).toFixed(1),n:r.lines.length,word:r.lines.length===1?t('segment'):r.lines.length<5?t('segmenty'):t('segmentów')})+(r.waypoints.length?t(' · {n} pkt',{n:r.waypoints.length}):'')));label.title=t('Pokaż trasę na mapie');label.onclick=()=>fitRoute(r);
  const remove=el('button','✕','ghost route-remove');remove.setAttribute('aria-label',t('Usuń trasę {name}',{name:r.name}));remove.onclick=()=>removeRoute(r.id);
  item.append(swatch,label,remove);list.append(item);
 }
 $('route-filter').hidden=!state.routes.length;
 if(!state.routes.length)list.append(el('p',t('Wczytaj jeden lub więcej plików GPX, aby zobaczyć trasę i odległość miejsc od niej.'),'hint'));
}

function afterChange(){persist();drawRoutes();recomputeDistances();renderList();render();renderPlan();}

export async function addRouteFiles(files){
 let added=0;
 for(const f of files){try{state.routes.push(parseGPX(await f.text(),f.name));added++;}catch(e){notify(e.message,true);}}
 if(!added)return;
 afterChange();
 fitRoute(state.routes[state.routes.length-1]);
 notify(t('Wczytano {n} {word} GPX. Miejsca pokazują odległość od najbliższej trasy.',{n:added,word:added===1?t('trasę'):t('tras')}));
}

export function removeRoute(id){state.routes=state.routes.filter(r=>r.id!==id);afterChange();}

export function initRoutes(){
 restore();
 const shell=document.querySelector('.map-shell');
 const panel=el('section',undefined,'route-panel');panel.id='route-panel';
 const head=el('div',undefined,'route-head');head.append(el('strong',t('Planowana trasa (GPX)')));
 const input=el('input');input.type='file';input.id='route-files';input.accept='.gpx';input.multiple=true;input.hidden=true;input.onchange=async e=>{await addRouteFiles([...e.target.files]);e.target.value='';};
 const pick=el('button',t('＋ Dodaj GPX'),'route-add');pick.onclick=()=>input.click();
 head.append(pick,input);
 const list=el('div',undefined,'route-list');list.id='route-list';
 const filter=el('label',undefined,'check route-filter');filter.id='route-filter';
 const only=el('input');only.type='checkbox';only.id='route-only';const range=el('input');range.type='number';range.id='route-range';range.min='0.1';range.step='0.5';range.value=String(DEFAULT_RANGE_KM);
 filter.append(only,document.createTextNode(t('Tylko miejsca do ')),range,document.createTextNode(t(' km od trasy')));
 only.onchange=()=>{render();saveRouteFilter();};range.onchange=()=>{render();saveRouteFilter();};
 const plan=el('section',undefined,'route-plan');plan.id='route-plan';plan.hidden=true;
 const planHead=el('div',undefined,'route-head');planHead.append(el('strong',t('Plan jazdy (zachowane miejsca wzdłuż trasy)')));
 const km=el('label',undefined,'check');const kmInput=el('input');kmInput.type='number';kmInput.id='plan-km';kmInput.min='20';kmInput.step='10';kmInput.value='250';km.append(document.createTextNode(t('km/dzień ')),kmInput);
 const exp=el('button',t('GPX planu ↓'),'ghost');exp.onclick=exportPlanGPX;planHead.append(km,exp);
 const planList=el('div',undefined,'plan-list');planList.id='plan-list';plan.append(planHead,planList);
 kmInput.onchange=renderPlan;
 panel.append(head,list,filter,plan);shell.append(panel);
 try{const f=JSON.parse(localStorage.getItem(STORAGE_KEY+':filter')||'null');if(f){only.checked=!!f.only;if(f.range)range.value=String(f.range);}}catch{}
 renderList();renderPlan();
}
function saveRouteFilter(){try{localStorage.setItem(STORAGE_KEY+':filter',JSON.stringify({only:$('route-only').checked,range:nearRouteRange()}));}catch{}}

// Wołane po initMap i po każdym loadLibrary — rysuje trasy i liczy odległości dla aktualnych miejsc.
export function syncRoutes(){drawRoutes();recomputeDistances();renderPlan();}
