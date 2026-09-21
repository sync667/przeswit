// Własne punkty: szybkie dodanie miejsca (planowane / byłem / na kiedyś) z notatką, edycja i usuwanie.
// Współrzędne: wpisane ręcznie, wklejone z linku Google Maps / tekstu „lat, lon” albo wskazane kliknięciem na mapie.
import {$,el,notify} from './dom.js';
import {state} from './state.js';
import {api} from './api.js';
import {loadLibrary} from './library.js';
import {showDetail} from './detail.js';
import {exifCoordinates} from './exif.js';
import {t} from './i18n.js';

export const OWN_SOURCE='own-notes';
export const OWN_STATUS={planned:t('Planowane'),visited:t('Byłem'),someday:t('Na kiedyś')};
let editingKey='',pickHandler=null,editingPhotos=[];
const MAX_EDGE=2048;

// Zmniejsza zdjęcie w przeglądarce (telefon daje 5–10 MB), zwraca base64 JPEG; małe pliki idą bez zmian.
async function prepareImage(file){
 if(file.size<1_500_000&&/image\/(jpeg|png|webp)/.test(file.type))return {content:await toBase64(file),caption:file.name};
 const bitmap=await createImageBitmap(file);const scale=Math.min(1,MAX_EDGE/Math.max(bitmap.width,bitmap.height));
 const canvas=document.createElement('canvas');canvas.width=Math.round(bitmap.width*scale);canvas.height=Math.round(bitmap.height*scale);
 canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);
 const blob=await new Promise(r=>canvas.toBlob(r,'image/jpeg',.86));
 return {content:await toBase64(blob),caption:file.name};
}
function toBase64(blob){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=()=>reject(Error(t('Błąd odczytu pliku.')));r.readAsDataURL(blob);});}

function renderPhotos(){
 const box=$('own-photos');box.replaceChildren();
 for(const ph of editingPhotos){const item=el('figure',undefined,'own-photo');const img=el('img');img.src=state.photoCache[ph.url]||ph.url;img.alt=ph.caption||'';const del=el('button','✕','ghost');del.type='button';del.title=t('Usuń zdjęcie');del.onclick=async()=>{try{await api('/api/places/own/photos/delete',{key:editingKey,url:ph.url});editingPhotos=editingPhotos.filter(x=>x.url!==ph.url);renderPhotos();}catch(e){$('own-error').textContent=e.message;}};item.append(img,del);box.append(item);}
 const pending=[...($('own-files').files||[])];if(pending.length)box.append(el('p',t('Do wysłania po zapisie: {names}',{names:pending.map(f=>f.name).join(', ')}),'hint'));
}

async function uploadPending(key){
 const files=[...($('own-files').files||[])];let done=0;
 for(const f of files){try{const img=await prepareImage(f);await api('/api/places/own/photos',{key,...img});done++;}catch(e){notify(`${f.name}: ${e.message}`,true);}}
 $('own-files').value='';return done;
}

// Wyciąga współrzędne z tekstu: „50.123, 16.456”, link Google Maps (@lat,lon / q=lat,lon / !3dlat!4dlon), OSM (#map=z/lat/lon, mlat/mlon).
export function parseCoordinates(text){
 const s=String(text||'').trim();if(!s)return null;
 const patterns=[/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/,/[?&](?:q|query|ll)=(-?\d+(?:\.\d+)?)(?:,|%2C)(-?\d+(?:\.\d+)?)/i,/!3d(-?\d+(?:\.\d+)?)!4d(-?\d+(?:\.\d+)?)/,/mlat=(-?\d+(?:\.\d+)?)&mlon=(-?\d+(?:\.\d+)?)/,/#map=\d+\/(-?\d+(?:\.\d+)?)\/(-?\d+(?:\.\d+)?)/,/^\s*(-?\d+(?:[.,]\d+)?)\s*[,; ]\s*(-?\d+(?:[.,]\d+)?)\s*$/];
 for(const re of patterns){const m=s.match(re);if(m){const lat=parseFloat(m[1].replace(',','.')),lon=parseFloat(m[2].replace(',','.'));if(Math.abs(lat)<=90&&Math.abs(lon)<=180)return {lat,lon};}}
 return null;
}

function fill(p,coords){
 editingKey=p?.key||'';editingPhotos=p?[...p.photos]:[];
 $('own-title').textContent=p?t('Edytuj własny punkt'):t('Dodaj własny punkt');
 $('own-name').value=p?.name||'';const c=coords||p;$('own-lat').value=c?c.lat.toFixed(6):'';$('own-lon').value=c?c.lon.toFixed(6):'';$('own-coords').value='';$('own-files').value='';
 $('own-description').value=p?.description||'';$('own-note').value=p?.user_note||'';$('own-url').value=p?.source_url||'';
 const status=p?.own_status||'someday';for(const r of document.querySelectorAll('input[name="own-status"]'))r.checked=r.value===status;
 $('own-delete').hidden=!p;$('own-error').textContent='';renderPhotos();
}

export function openOwnDialog(p=null,coords=null){fill(p,coords);$('own-dialog').showModal();$('own-name').focus();}

function stopPick(){if(pickHandler&&state.map){state.map.off('click',pickHandler);state.map.getContainer().classList.remove('pick-active');}pickHandler=null;$('own-pick').textContent=t('Wskaż na mapie');}

function startPick(){
 if(!state.map){notify(t('Najpierw przełącz na widok „Mapa + lista”.'),true);return;}
 if(pickHandler){stopPick();return;}
 $('own-dialog').close();
 if(!state.mapView)$('toggle-map').click();
 notify(t('Kliknij na mapie miejsce, które chcesz zapisać (Esc anuluje).'));
 state.map.getContainer().classList.add('pick-active');$('own-pick').textContent=t('Anuluj wskazywanie');
 pickHandler=e=>{$('own-lat').value=e.latlng.lat.toFixed(6);$('own-lon').value=e.latlng.lng.toFixed(6);stopPick();$('own-dialog').showModal();};
 state.map.once('click',pickHandler);
 const esc=ev=>{if(ev.key==='Escape'){stopPick();$('own-dialog').showModal();document.removeEventListener('keydown',esc);}};document.addEventListener('keydown',esc);
}

async function save(){
 const lat=parseFloat($('own-lat').value),lon=parseFloat($('own-lon').value);
 const status=document.querySelector('input[name="own-status"]:checked')?.value||'someday';
 if(!$('own-name').value.trim()){$('own-error').textContent=t('Podaj nazwę.');return;}
 if(!Number.isFinite(lat)||!Number.isFinite(lon)){$('own-error').textContent=t('Podaj współrzędne: wpisz, wklej link albo wskaż na mapie.');return;}
 $('own-save').disabled=true;
 try{
  const r=await api('/api/places/own',{key:editingKey,name:$('own-name').value.trim(),lat,lon,status,description:$('own-description').value,note:$('own-note').value,url:$('own-url').value.trim()});
  const uploaded=await uploadPending(r.key);
  $('own-dialog').close();await loadLibrary();if(uploaded)notify(t('Zapisano punkt i {n} {word}.',{n:uploaded,word:uploaded===1?t('zdjęcie'):uploaded<5?t('zdjęcia'):t('zdjęć')}));
  if(!state.places.some(p=>p.key===r.key))notify(t('Punkt zapisany, ale jest poza bieżącymi filtrami (np. „Tylko ze zdjęciami”).'));
  else showDetail(r.key);
 }catch(e){$('own-error').textContent=e.message;}
 finally{$('own-save').disabled=false;}
}

async function remove(){
 if(!editingKey)return;
 try{await api('/api/places/own/delete',{key:editingKey});$('own-dialog').close();if($('detail').open)$('detail').close();await loadLibrary();notify(t('Własny punkt usunięty.'));}
 catch(e){$('own-error').textContent=e.message;}
}

export function initOwn(){
 $('open-own').onclick=()=>openOwnDialog();
 $('close-own').onclick=()=>{stopPick();$('own-dialog').close();};
 $('own-save').onclick=save;$('own-delete').onclick=remove;$('own-pick').onclick=startPick;
 $('own-coords').oninput=()=>{const c=parseCoordinates($('own-coords').value);if(c){$('own-lat').value=c.lat.toFixed(6);$('own-lon').value=c.lon.toFixed(6);$('own-error').textContent='';}else if($('own-coords').value.trim())$('own-error').textContent=t('Nie rozpoznaję współrzędnych w tym tekście.');};
 $('own-form').onsubmit=e=>{e.preventDefault();save();};
 $('own-files').onchange=async()=>{renderPhotos();if(!$('own-lat').value&&!$('own-lon').value){for(const f of [...($('own-files').files||[])]){const c=await exifCoordinates(f).catch(()=>null);if(c){$('own-lat').value=c.lat.toFixed(6);$('own-lon').value=c.lon.toFixed(6);$('own-error').textContent='';notify(t('Współrzędne pobrane z EXIF zdjęcia {name}.',{name:f.name}));break;}}}};
}

// Z mapy: prawy klik / długie przytrzymanie → popup „Własny punkt tutaj”; przycisk w pasku mapy → wskazanie klikiem.
export function initOwnOnMap(){
 if(!state.map)return;
 state.map.on('contextmenu',e=>{if(state.map.getContainer().classList.contains('lasso-active'))return;const box=el('div',undefined,'marker-popup');box.append(el('div',`${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}`,'hint'));const b=el('button',t('＋ Własny punkt tutaj'),'save-place');b.onclick=()=>{state.map.closePopup();openOwnDialog(null,{lat:e.latlng.lat,lon:e.latlng.lng});};box.append(b);L.popup().setLatLng(e.latlng).setContent(box).openOn(state.map);});
 const tools=document.querySelector('.lasso-tools');if(tools){const b=el('button',t('＋ Punkt na mapie'));b.title=t('Kliknij, potem wskaż miejsce na mapie');b.onclick=()=>{openOwnDialog();startPick();};tools.append(b);}
}
