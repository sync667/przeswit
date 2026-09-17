// Lokalne AI: stan modelu, wyszukiwanie według opisu, kolejka profili, cache zdjęć i informacje o bazie.
import {$,el,notify} from './dom.js';
import {state,featureLabels} from './state.js';
import {api,getJSON} from './api.js';
import {loadLibrary,areaRequest} from './library.js';
import {render} from './cards.js';

const PROFILE_POLL_MS=5000;
const LOCAL_STATUS_EVERY_N_POLLS=6;
const WISH_STORAGE_KEY='przeswit-wish';

export function restoreWish(){try{$('wish').value=localStorage.getItem(WISH_STORAGE_KEY)||$('wish').value;}catch{}}

export function onWishInput(){try{localStorage.setItem(WISH_STORAGE_KEY,$('wish').value);}catch{}$('ai-only').checked=false;state.page=0;render();if(state.searchResults.size)$('review-progress').textContent='Opis zmieniony. Kliknij „Szukaj według opisu”, aby odświeżyć wyniki.';}

export async function localStatus(){try{const s=await getJSON('/api/local-ai');$('local-ai-status').textContent=s.message;$('review-page').disabled=!s.ready||state.searchRunning;return s.ready;}catch{$('local-ai-status').textContent='Brak połączenia z lokalnym modelem';return false;}}

function renderQueryPlan(plan){
 const box=$('query-plan');box.replaceChildren(el('p',plan.interpretation));for(const c of plan.conditions)box.append(el('p',`„${c.quote||''}” → ${featureLabels[c.feature]} · oczekiwany poziom ${c.target}/100 · waga ${c.weight}/5${c.required?' · wymagane':''}`));for(const x of plan.unsupported)box.append(el('p','Nieobsługiwane wymaganie: '+x,'card-warning'));
}

export async function searchByDescription(){if(state.searchRunning)return;state.searchRunning=true;$('review-page').disabled=true;$('wish').disabled=true;$('review-progress').textContent='AI interpretuje opis; w razie potrzeby czeka na zakończenie bieżącego profilu…';try{const result=await api('/api/profile-search',{criteria:$('wish').value.trim()});state.searchCriteria=result.criteria;state.searchResults=new Map(result.results.map(r=>[r.key,r]));await loadLibrary();$('ai-only').checked=true;state.page=0;render();$('query-details').hidden=false;renderQueryPlan(result.plan);$('review-progress').textContent=`Przeszukano ${result.profiled} z ${result.total} profili w bazie; ${result.pending} oczekuje lub wymaga ponowienia. Na liście obowiązują też Twoje filtry. Wyszukaj ponownie, aby uwzględnić nowe profile.`;}catch(e){$('review-progress').textContent=e.message;}finally{state.searchRunning=false;$('wish').disabled=false;await localStatus();}}

export async function toggleProfilePause(){try{await api('/api/profiles/pause',{paused:!state.queuePaused});await profileStatus();}catch(e){notify(e.message,true);}}

export async function retryProfiles(){try{await api('/api/profiles/retry',{});await profileStatus();}catch(e){notify(e.message,true);}}

export async function setParallelMode(){try{await api('/api/profiles/parallel',{mode:$('parallel-mode').value});await profileStatus();}catch(e){notify(e.message,true);}}

// Odświeża rekordy w miejscu, gdy przybyły nowe gotowe profile, bez resetowania strony i filtrów.
async function refreshProfiles(){const fresh=await api('/api/library',areaRequest());state.photoCache=fresh.photo_cache||{};const byKey=new Map(fresh.spots.map(p=>[p.key,p]));state.places=state.places.map(p=>byKey.get(p.key)||p);render();}

export async function profileStatus(){try{const r=await getJSON('/api/profiles');state.queuePaused=r.paused;$('parallel-mode').value=r.parallel_requested||'auto';const free=r.resources?.gpu_free_mb;$('resource-status').textContent=`Aktywne ${r.active||0}/${r.parallel_limit??1}${free!=null?' · wolne GPU '+(free/1024).toFixed(1)+' GB':''}`;const c=r.counts;$('profile-progress').textContent=`Profile: ${c.ready||0} gotowych · ${c.pending||0} w kolejce · ${c.running||0} w trakcie · ${c.error||0} błędów. ${state.queuePaused?'Wstrzymane po bieżącym miejscu.':r.current?'Teraz: '+r.current:r.message}`;$('profile-pause').textContent=state.queuePaused?'Wznów profilowanie':'Wstrzymaj profilowanie';$('profile-retry').hidden=!c.error;const signature=String(c.ready||0);if(state.profileSignature&&signature!==state.profileSignature&&!$('detail').open&&!state.searchRunning)await refreshProfiles();state.profileSignature=signature;if(++state.queuePolls%LOCAL_STATUS_EVERY_N_POLLS===0)await localStatus();await photosStatus();}catch(e){$('profile-progress').textContent='Nie można odczytać kolejki profili.';}finally{clearTimeout(state.profileTimer);state.profileTimer=setTimeout(profileStatus,PROFILE_POLL_MS);}}

export async function databaseInfo(){try{const d=await getJSON('/api/database');$('database-info').textContent=`${d.engine} · ${d.journal.toUpperCase()} · ${d.counts.places} miejsc. Plik: ${d.path}. Kopie: ${d.backups}. Ostatnia: ${d.latest_backup||'brak'}`;}catch{}}

export async function databaseBackup(){const b=$('database-backup');b.disabled=true;try{const r=await api('/api/database/backup',{});$('database-backup-status').textContent='Zapisano: '+r.path;await databaseInfo();}catch(e){$('database-backup-status').textContent=e.message;}finally{b.disabled=false;}}

export async function photosStatus(){try{const r=await getJSON('/api/photos');state.photosPaused=r.paused;$('photo-progress').textContent=`Zdjęcia lokalne: ${r.counts.ready||0} · ${(r.bytes/1048576).toFixed(1)} MB / ${(r.limit/1024**3).toFixed(0)} GB · błędy ${r.counts.error||0}. Pobieranie w tle: ${r.paused?'wstrzymane':`do ${r.parallel||1} równolegle`}`;$('photos-pause').textContent=r.paused?'Wznów zdjęcia':'Wstrzymaj zdjęcia';}catch{}}

export async function togglePhotosPause(){try{await api('/api/photos/pause',{paused:!state.photosPaused});await photosStatus();}catch(e){notify(e.message,true);}}
