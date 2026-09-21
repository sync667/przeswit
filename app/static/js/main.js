// Punkt wejścia: układ strony, podpięcie zdarzeń i start aplikacji.
import {$,el,notify} from './dom.js';
import {state} from './state.js';
import {getJSON} from './api.js';
import {initMap,clearHighlight} from './map.js';
import {initRoutes} from './routes.js';
import {initOwn,initOwnOnMap} from './own.js';
import {initPresets,initShortcuts,initTheme,registerPWA} from './presets.js';
import {loadLibrary,filtered} from './library.js';
import {render,undo,hideUndoToast} from './cards.js';
import {showDetail} from './detail.js';
import {renderSources,poll,startSync} from './jobs.js';
import {importFile,exportJSON,exportCSV,exportGPX} from './transfer.js';
import {restoreWish,onWishInput,localStatus,searchByDescription,toggleProfilePause,retryProfiles,setParallelMode,profileStatus,databaseInfo,databaseBackup,togglePhotosPause} from './ai.js';

// Zapamiętany widok (galeria/mapa, zakładka, filtry, ustawienia) — przywracany po odświeżeniu strony.
const VIEW_KEY='przeswit-view';
const VIEW_CHECKS=['photos-only','ai-only','only-map','remote-photos','tiles','shortlist-only','show-rejected'];
const VIEW_SELECTS=['source-filter','type-filter'];
function saveView(){try{const v={mapView:state.mapView,collection:state.collection,search:$('search').value,checks:{},selects:{}};for(const id of VIEW_CHECKS)if($(id))v.checks[id]=$(id).checked;for(const id of VIEW_SELECTS)v.selects[id]=$(id).value;localStorage.setItem(VIEW_KEY,JSON.stringify(v));}catch{}}
function loadView(){try{return JSON.parse(localStorage.getItem(VIEW_KEY)||'null')||{};}catch{return {};}}
function restoreControls(v){for(const [id,val] of Object.entries(v.checks||{}))if($(id))$(id).checked=val;if(v.selects?.['type-filter'])$('type-filter').value=v.selects['type-filter'];if(typeof v.search==='string')$('search').value=v.search;if(v.collection)state.collection=v.collection;}

function setupLayout(){
 const browseLayout=el('div',undefined,'browse-layout');const cards=$('cards'),mapShell=document.querySelector('.map-shell');cards.before(browseLayout);browseLayout.append(cards,mapShell);
 $('toggle-map').textContent='Mapa + lista';
 $('toggle-map').onclick=()=>{state.mapView=!state.mapView;saveView();mapShell.hidden=!state.mapView;browseLayout.classList.toggle('map-view',state.mapView);$('toggle-map').textContent=state.mapView?'Galeria zdjęć':'Mapa + lista';$('toggle-map').setAttribute('aria-pressed',String(state.mapView));clearHighlight();if(state.mapView){state.map?.invalidateSize();if($('forest-overlay')?.checked)state.forestLayer?.addTo(state.map);const points=filtered();if(points.length)state.map?.fitBounds(points.map(p=>[p.lat,p.lon]),{maxZoom:13,padding:[35,35]});}else {state.forestLayer?.remove();if($('only-map').checked){$('only-map').checked=false;render();}}};
}

function bindBrowsing(){
 $('undo').onclick=undo;
 $('undo-close').onclick=hideUndoToast;
 for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>{state.collection=b.dataset.view;state.page=0;render();saveView();};
 $('photos-only').onchange=()=>{state.page=0;render();saveView();};
 for(const id of ['source-filter','type-filter','shortlist-only','show-rejected','only-map'])$(id).onchange=()=>{state.page=0;render();saveView();};
 $('search').oninput=()=>{state.page=0;render();saveView();};
 $('tiles').onchange=()=>{saveView();if(state.map&&state.tiles){if($('tiles').checked)state.tiles.addTo(state.map);else state.tiles.remove();}};
 $('remote-photos').onchange=()=>{saveView();render();if(state.selected&&$('detail').open)showDetail(state.selected);};
}

function bindDialogs(){
 $('open-import').onclick=()=>$('import-dialog').showModal();
 $('close-import').onclick=()=>$('import-dialog').close();
 $('sources-button').onclick=()=>{$('sources').showModal();};
 $('close-sources').onclick=()=>$('sources').close();
 $('close-detail').onclick=()=>$('detail').close();
 $('detail').addEventListener('close',()=>{if(location.hash.startsWith('#place='))history.replaceState(null,'',location.pathname);});
 window.addEventListener('hashchange',openFromHash);
}

function bindAreas(){
 $('sync').onclick=startSync;
 $('area-filter').onclick=()=>{state.allLibrary=false;loadLibrary(true);};
 $('all-library').onclick=()=>{state.allLibrary=true;loadLibrary(true);};
 $('map-area').onclick=()=>{if(!state.map)return;const b=state.map.getBounds();$('areas').value=[b.getWest(),b.getSouth(),b.getEast(),b.getNorth()].map(v=>v.toFixed(6)).join(',');state.allLibrary=false;loadLibrary();};
}

function bindTransfer(){
 $('file').onchange=importFile;
 $('export-json').onclick=exportJSON;
 $('export-csv').onclick=exportCSV;
 $('export-gpx').onclick=exportGPX;
}

function bindAI(){
 restoreWish();
 $('wish').oninput=onWishInput;
 $('ai-only').onchange=()=>{state.page=0;render();saveView();};
 $('review-page').onclick=searchByDescription;
 $('profile-pause').onclick=toggleProfilePause;
 $('profile-retry').onclick=retryProfiles;
 $('parallel-mode').onchange=setParallelMode;
 $('database-backup').onclick=databaseBackup;
 $('photos-pause').onclick=togglePhotosPause;
}

// #place=<klucz> w adresie otwiera kartę miejsca (link można wkleić lub przekazać dalej).
function openFromHash(){const m=location.hash.match(/^#place=(.+)$/);if(!m)return;const key=decodeURIComponent(m[1]);if(state.places.some(p=>p.key===key))showDetail(key);else notify(`Nie znaleziono miejsca ${key} w bieżącym widoku biblioteki.`,true);}

// Gość (Cloudflare Access, konto spoza właścicieli): przegląda, ale nie zapisuje — chowamy przyciski zapisu i pokazujemy baner.
function applyReadOnly(){
 if(!state.config.read_only)return;
 document.body.classList.add('read-only');
 const bar=el('div',`Tryb tylko do odczytu · zalogowano jako ${state.config.user||'gość'} — decyzje, notatki i importy są wyłączone.`,'read-only-banner');
 document.querySelector('header').after(bar);
 for(const id of ['open-import','open-own','sync','profile-pause','profile-retry','photos-pause','database-backup','review-page','parallel-mode'])if($(id))$(id).disabled=true;
}

async function boot(){
 const view=loadView();
 try{state.config=await getJSON('/api/config');if(state.config.last_area){$('areas').value=state.config.last_area.areas;$('radius').value=state.config.last_area.radius;}$('inbox-path').textContent=state.config.inbox;$('ai-state').textContent='Analiza zdjęć: lokalna Ollama / Gemma 3. Bez klucza API.';applyReadOnly();renderSources();initMap();initRoutes();initOwnOnMap();await loadLibrary(true);if(view.selects?.['source-filter']){$('source-filter').value=view.selects['source-filter'];render();}if(view.mapView)$('toggle-map').click();openFromHash();await poll();}catch(e){notify(e.message,true);}
}

restoreControls(loadView());
document.addEventListener('przeswit:filters',saveView);
setupLayout();
bindBrowsing();
bindDialogs();
bindAreas();
bindTransfer();
bindAI();
initOwn();
initTheme();
initPresets();
initShortcuts();
registerPWA();
databaseInfo();
localStatus();
profileStatus();
boot();
