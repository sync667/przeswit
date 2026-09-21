// Lasso wielopunktowe na mapie: klikasz wierzchołki wielokąta, kończysz dwuklikiem / przyciskiem,
// a zaznaczone (widoczne po filtrach) miejsca można masowo zachować lub odrzucić — z jednym „Cofnij”.
import {$,el,notify} from './dom.js';
import {state,SAVED_CHOICES} from './state.js';
import {filtered} from './library.js';
import {render,bulkChoose} from './cards.js';
import {t} from './i18n.js';

let active=false,vertices=[],preview=null,polygon=null,selectionLayer=null,bar=null;

function pointInPolygon(lat,lon,poly){
 let inside=false;
 for(let i=0,j=poly.length-1;i<poly.length;j=i++){const [yi,xi]=poly[i],[yj,xj]=poly[j];const hit=((yi>lat)!==(yj>lat))&&(lon<(xj-xi)*(lat-yi)/(yj-yi)+xi);if(hit)inside=!inside;}
 return inside;
}

function setActive(on){
 active=on;const container=state.map.getContainer();container.classList.toggle('lasso-active',on);
 $('lasso-start').textContent=on?t('Zakończ zaznaczanie'):t('Zaznacz obszar (lasso)');$('lasso-start').classList.toggle('chosen',on);
 $('lasso-hint').hidden=!on;
 if(on){state.map.doubleClickZoom.disable();state.map.closePopup();}else state.map.doubleClickZoom.enable();
}

function redrawPreview(){
 if(preview)preview.remove();
 if(vertices.length>1)preview=L.polyline(vertices,{color:'#e5aa61',weight:2,dashArray:'6 4'}).addTo(state.map);
 else preview=null;
}

function onMapClick(e){
 if(!active)return;
 vertices.push([e.latlng.lat,e.latlng.lng]);redrawPreview();
}

function onMapDblClick(e){
 if(!active)return;
 L.DomEvent.stop(e);
 finish();
}

function onKey(e){if(e.key==='Escape'&&active)cancel();}

export function startLasso(){
 if(active){finish();return;}
 clearSelection();vertices=[];setActive(true);
 notify(t('Lasso: klikaj wierzchołki na mapie, zakończ dwuklikiem albo przyciskiem. Esc anuluje.'));
}

function cancel(){vertices=[];redrawPreview();setActive(false);}

function finish(){
 if(vertices.length<3){notify(t('Zaznacz co najmniej 3 punkty.'),true);cancel();return;}
 const poly=vertices.slice();
 if(preview)preview.remove();preview=null;
 polygon=L.polygon(poly,{color:'#e5aa61',weight:2,fillOpacity:.08}).addTo(state.map);
 const selected=filtered().filter(p=>pointInPolygon(p.lat,p.lon,poly));
 state.selection=new Set(selected.map(p=>p.key));
 vertices=[];setActive(false);
 highlightSelection();renderBar();
 if(!selected.length)notify(t('W zaznaczonym obszarze nie ma widocznych miejsc (sprawdź filtry).'),true);
}

function highlightSelection(){
 if(selectionLayer)selectionLayer.remove();
 selectionLayer=L.layerGroup().addTo(state.map);
 for(const p of state.places)if(state.selection.has(p.key))L.circleMarker([p.lat,p.lon],{radius:9,color:'#e5aa61',weight:3,fill:false}).addTo(selectionLayer);
}

export function clearSelection(){
 state.selection=new Set();
 if(polygon){polygon.remove();polygon=null;}
 if(selectionLayer){selectionLayer.remove();selectionLayer=null;}
 renderBar();
}

function renderBar(){
 if(!bar)return;
 const n=state.selection.size;bar.hidden=!n;
 if(!n)return;
 const places=state.places.filter(p=>state.selection.has(p.key));
 const saved=places.filter(p=>SAVED_CHOICES.includes(p.choice)).length,rejected=places.filter(p=>p.choice==='rejected').length;
 $('lasso-count').textContent=t('Zaznaczono {n} {word}',{n,word:n===1?t('miejsce'):n<5?t('miejsca'):t('miejsc')})+(saved?t(' · zachowane {saved}',{saved}):'')+(rejected?t(' · odrzucone {rejected}',{rejected}):'');
}

async function applyAll(choice){
 const places=state.places.filter(p=>state.selection.has(p.key)&&p.choice!==choice);
 if(!places.length){notify(t('Wszystkie zaznaczone miejsca mają już ten stan.'));return;}
 for(const b of bar.querySelectorAll('button'))b.disabled=true;
 const done=await bulkChoose(places,choice);
 for(const b of bar.querySelectorAll('button'))b.disabled=false;
 renderBar();highlightSelection();
 notify(t('{verb} {done} z {total} zaznaczonych miejsc.',{verb:choice==='rejected'?t('Odrzucono'):choice?t('Zachowano'):t('Przywrócono'),done,total:places.length}),done<places.length);
}

export function initLasso(){
 const shell=document.querySelector('.map-shell');
 bar=el('div',undefined,'lasso-bar');bar.id='lasso-bar';bar.hidden=true;
 const count=el('span',undefined,'lasso-count');count.id='lasso-count';
 const save=el('button',t('＋ Zachowaj wszystkie'),'save-place'),reject=el('button',t('× Odrzuć wszystkie')),restore=el('button',t('↶ Przywróć wszystkie'),'ghost'),clear=el('button',t('Wyczyść zaznaczenie'),'ghost');
 save.onclick=()=>applyAll('shortlist');reject.onclick=()=>applyAll('rejected');restore.onclick=()=>applyAll('');clear.onclick=clearSelection;
 bar.append(count,save,reject,restore,clear);
 const tools=el('div',undefined,'lasso-tools');
 const start=el('button',t('Zaznacz obszar (lasso)'));start.id='lasso-start';start.onclick=startLasso;
 const hint=el('span',t('Klikaj wierzchołki, dwuklik kończy, Esc anuluje.'),'hint');hint.id='lasso-hint';hint.hidden=true;
 tools.append(start,hint);
 const legend=shell.querySelector('.map-legend');(legend||shell).after(tools);tools.after(bar);
 state.selection=new Set();
 state.map.on('click',onMapClick);state.map.on('dblclick',onMapDblClick);document.addEventListener('keydown',onKey);
}

// Po każdym renderze lista może się zmienić (filtry) — obwódki zaznaczenia rysujemy ponownie.
export function refreshLasso(){if(state.selection?.size)highlightSelection();}
