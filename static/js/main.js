// Punkt wejścia: układ strony, podpięcie zdarzeń i start aplikacji.
import {$,el,notify} from './dom.js';
import {state} from './state.js';
import {getJSON} from './api.js';
import {initMap,clearHighlight} from './map.js';
import {loadLibrary,filtered} from './library.js';
import {render,undo} from './cards.js';
import {showDetail} from './detail.js';
import {renderSources,poll,startSync} from './jobs.js';
import {importFile,exportJSON,exportCSV,exportGPX} from './transfer.js';
import {restoreWish,onWishInput,localStatus,searchByDescription,toggleProfilePause,retryProfiles,setParallelMode,profileStatus,databaseInfo,databaseBackup,togglePhotosPause} from './ai.js';

function setupLayout(){
 const browseLayout=el('div',undefined,'browse-layout');const cards=$('cards'),mapShell=document.querySelector('.map-shell');cards.before(browseLayout);browseLayout.append(cards,mapShell);
 $('toggle-map').textContent='Mapa + lista';
 $('toggle-map').onclick=()=>{state.mapView=!state.mapView;mapShell.hidden=!state.mapView;browseLayout.classList.toggle('map-view',state.mapView);$('toggle-map').textContent=state.mapView?'Galeria zdjęć':'Mapa + lista';$('toggle-map').setAttribute('aria-pressed',String(state.mapView));clearHighlight();if(state.mapView){state.map?.invalidateSize();if($('forest-overlay')?.checked)state.forestLayer?.addTo(state.map);const points=filtered();if(points.length)state.map?.fitBounds(points.map(p=>[p.lat,p.lon]),{maxZoom:13,padding:[35,35]});}else {state.forestLayer?.remove();if($('only-map').checked){$('only-map').checked=false;render();}}};
}

function bindBrowsing(){
 $('undo').onclick=undo;
 for(const b of document.querySelectorAll('[data-view]'))b.onclick=()=>{state.collection=b.dataset.view;state.page=0;render();};
 $('photos-only').onchange=()=>{state.page=0;render();};
 for(const id of ['source-filter','type-filter','shortlist-only','show-rejected','only-map'])$(id).onchange=()=>{state.page=0;render();};
 $('search').oninput=()=>{state.page=0;render();};
 $('prev').onclick=()=>{state.page--;render(false);};
 $('next').onclick=()=>{state.page++;render(false);};
 $('tiles').onchange=()=>{if(state.map&&state.tiles){if($('tiles').checked)state.tiles.addTo(state.map);else state.tiles.remove();}};
 $('remote-photos').onchange=()=>{render();if(state.selected&&$('detail').open)showDetail(state.selected);};
}

function bindDialogs(){
 $('open-import').onclick=()=>$('import-dialog').showModal();
 $('close-import').onclick=()=>$('import-dialog').close();
 $('sources-button').onclick=()=>{$('sources').showModal();};
 $('close-sources').onclick=()=>$('sources').close();
 $('close-detail').onclick=()=>$('detail').close();
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
 $('ai-only').onchange=()=>{state.page=0;render();};
 $('review-page').onclick=searchByDescription;
 $('profile-pause').onclick=toggleProfilePause;
 $('profile-retry').onclick=retryProfiles;
 $('parallel-mode').onchange=setParallelMode;
 $('database-backup').onclick=databaseBackup;
 $('photos-pause').onclick=togglePhotosPause;
}

async function boot(){
 try{state.config=await getJSON('/api/config');if(state.config.last_area){$('areas').value=state.config.last_area.areas;$('radius').value=state.config.last_area.radius;}$('inbox-path').textContent=state.config.inbox;$('ai-state').textContent='Analiza zdjęć: lokalna Ollama / Gemma 3. Bez klucza API.';renderSources();initMap();await loadLibrary(true);await poll();}catch(e){notify(e.message,true);}
}

setupLayout();
bindBrowsing();
bindDialogs();
bindAreas();
bindTransfer();
bindAI();
databaseInfo();
localStatus();
profileStatus();
boot();
