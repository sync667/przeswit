// Lokalne AI: stan modelu, wyszukiwanie według opisu, kolejka profili, cache zdjęć i informacje o bazie.
import {$,el,notify} from './dom.js';
import {state,featureLabels} from './state.js';
import {api,getJSON} from './api.js';
import {loadLibrary,areaRequest} from './library.js';
import {render} from './cards.js';
import {t} from './i18n.js';

const PROFILE_POLL_MS=5000;
const LOCAL_STATUS_EVERY_N_POLLS=6;
const WISH_STORAGE_KEY='przeswit-wish';

export function restoreWish(){try{$('wish').value=localStorage.getItem(WISH_STORAGE_KEY)||$('wish').value;}catch{}}

export function onWishInput(){try{localStorage.setItem(WISH_STORAGE_KEY,$('wish').value);}catch{}$('ai-only').checked=false;state.page=0;render();if(state.searchResults.size)$('review-progress').textContent=t('Opis zmieniony. Kliknij „Szukaj według opisu”, aby odświeżyć wyniki.');}

export async function localStatus(){try{const s=await getJSON('/api/local-ai');$('local-ai-status').textContent=s.message;$('review-page').disabled=!s.ready||state.searchRunning;return s.ready;}catch{$('local-ai-status').textContent=t('Brak połączenia z lokalnym modelem');return false;}}

function renderQueryPlan(plan){
 const box=$('query-plan');box.replaceChildren(el('p',plan.interpretation));for(const c of plan.conditions)box.append(el('p',t('„{quote}” → {feature} · oczekiwany poziom {target}/100 · waga {weight}/5{required}',{quote:c.quote||'',feature:featureLabels[c.feature],target:c.target,weight:c.weight,required:c.required?t(' · wymagane'):''})));for(const x of plan.unsupported)box.append(el('p',t('Nieobsługiwane wymaganie: {x}',{x}),'card-warning'));
}

export async function searchByDescription(){if(state.searchRunning)return;state.searchRunning=true;$('review-page').disabled=true;$('wish').disabled=true;$('review-progress').textContent=t('AI interpretuje opis; w razie potrzeby czeka na zakończenie bieżącego profilu…');try{const result=await api('/api/profile-search',{criteria:$('wish').value.trim()});state.searchCriteria=result.criteria;state.searchResults=new Map(result.results.map(r=>[r.key,r]));await loadLibrary();$('ai-only').checked=true;state.page=0;render();$('query-details').hidden=false;renderQueryPlan(result.plan);$('review-progress').textContent=t('Przeszukano {profiled} z {total} profili w bazie; {pending} oczekuje lub wymaga ponowienia. Na liście obowiązują też Twoje filtry. Wyszukaj ponownie, aby uwzględnić nowe profile.',{profiled:result.profiled,total:result.total,pending:result.pending});}catch(e){$('review-progress').textContent=e.message;}finally{state.searchRunning=false;$('wish').disabled=false;await localStatus();}}

export async function toggleProfilePause(){try{await api('/api/profiles/pause',{paused:!state.queuePaused});await profileStatus();}catch(e){notify(e.message,true);}}

export async function retryProfiles(){try{await api('/api/profiles/retry',{});await profileStatus();}catch(e){notify(e.message,true);}}

export async function setParallelMode(){try{await api('/api/profiles/parallel',{mode:$('parallel-mode').value});await profileStatus();}catch(e){notify(e.message,true);}}

// Odświeża rekordy w miejscu, gdy przybyły nowe gotowe profile, bez resetowania strony i filtrów.
async function refreshProfiles(){const fresh=await api('/api/library',areaRequest());state.photoCache=fresh.photo_cache||{};const byKey=new Map(fresh.spots.map(p=>[p.key,p]));state.places=state.places.map(p=>byKey.get(p.key)||p);render();}

export async function profileStatus(){try{const r=await getJSON('/api/profiles');state.queuePaused=r.paused;$('parallel-mode').value=r.parallel_requested||'auto';const free=r.resources?.gpu_free_mb;$('resource-status').textContent=t('Aktywne {active}/{limit}{gpu}',{active:r.active||0,limit:r.parallel_limit??1,gpu:free!=null?t(' · wolne GPU {gb} GB',{gb:(free/1024).toFixed(1)}):''});const c=r.counts;$('profile-progress').textContent=t('Profile: {ready} gotowych · {pending} w kolejce · {running} w trakcie · {error} błędów. {tail}',{ready:c.ready||0,pending:c.pending||0,running:c.running||0,error:c.error||0,tail:state.queuePaused?t('Wstrzymane po bieżącym miejscu.'):r.current?t('Teraz: {current}',{current:r.current}):r.message});$('profile-pause').textContent=state.queuePaused?t('Wznów profilowanie'):t('Wstrzymaj profilowanie');$('profile-retry').hidden=!c.error;const signature=String(c.ready||0);if(state.profileSignature&&signature!==state.profileSignature&&!$('detail').open&&!state.searchRunning){try{await refreshProfiles();}catch(e){notify(t('Nie udało się odświeżyć listy po nowych profilach: {msg}',{msg:e.message}),true);}}state.profileSignature=signature;if(++state.queuePolls%LOCAL_STATUS_EVERY_N_POLLS===0)await localStatus();await photosStatus();}catch(e){$('profile-progress').textContent=t('Nie można odczytać kolejki profili: {msg}',{msg:e.message||e});}finally{clearTimeout(state.profileTimer);state.profileTimer=setTimeout(profileStatus,PROFILE_POLL_MS);}}

export async function databaseInfo(){try{const d=await getJSON('/api/database');$('database-info').textContent=t('{engine} · {journal} · {n} miejsc. Plik: {path}. Kopie: {backups}. Ostatnia: {latest}',{engine:d.engine,journal:d.journal.toUpperCase(),n:d.counts.places,path:d.path,backups:d.backups,latest:d.latest_backup||t('brak')});}catch{}}

export async function databaseBackup(){const b=$('database-backup');b.disabled=true;try{const r=await api('/api/database/backup',{});$('database-backup-status').textContent=t('Zapisano: {path}',{path:r.path});await databaseInfo();}catch(e){$('database-backup-status').textContent=e.message;}finally{b.disabled=false;}}

export async function photosStatus(){try{const r=await getJSON('/api/photos');state.photosPaused=r.paused;$('photo-progress').textContent=t('Zdjęcia lokalne: {ready} · {mb} MB / {gb} GB · błędy {error}. Pobieranie w tle: {status}',{ready:r.counts.ready||0,mb:(r.bytes/1048576).toFixed(1),gb:(r.limit/1024**3).toFixed(0),error:r.counts.error||0,status:r.paused?t('wstrzymane'):t('do {n} równolegle',{n:r.parallel||1})});$('photos-pause').textContent=r.paused?t('Wznów zdjęcia'):t('Wstrzymaj zdjęcia');}catch{}}

export async function togglePhotosPause(){try{await api('/api/photos/pause',{paused:!state.photosPaused});await photosStatus();}catch(e){notify(e.message,true);}}
