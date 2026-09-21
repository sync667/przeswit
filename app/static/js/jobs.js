// Źródła danych, import automatyczny (sync) i cykliczne odpytywanie stanu zadań oraz folderu inbox.
import {$,el,link,notify} from './dom.js';
import {state,providerName} from './state.js';
import {api,getJSON} from './api.js';
import {loadLibrary} from './library.js';
import {t} from './i18n.js';

const POLL_INTERVAL_MS=2500;

export function renderSources(){const catalog=$('source-catalog');catalog.replaceChildren();for(const s of state.config.sources){const card=el('div',undefined,'source-card');card.append(el('h3',s.name),el('span',s.status,'source-status'),el('p',s.note));if(s.url)card.append(link(t('Dokumentacja / serwis ↗'),s.url));catalog.append(card);}}

function renderJobs(jobs){
 const list=$('jobs-list');list.replaceChildren();for(const j of jobs){const card=el('div',undefined,'job-card');card.append(el('strong',t('{time} UTC · {status}',{time:j.started?.slice(0,16).replace('T',' '),status:j.status})),el('p',j.message));for(const r of j.reports)card.append(el('p',t('{provider}: {count} rekordów · {status}',{provider:providerName(r.provider),count:r.count??0,status:r.status})+(r.message?' · '+r.message:'')));const det=el('details');det.append(el('summary',t('Szczegóły pokrycia, błędy i zakres')),el('pre',JSON.stringify(j.reports,null,2)));card.append(det);list.append(card);}if(!jobs.length)list.append(el('p',t('Nie wykonano importu automatycznego.')));
}

function renderInbox(files){
 const inbox=$('inbox-list');inbox.replaceChildren();for(const f of files)inbox.append(el('p',`${f.name} · ${f.status} · ${f.message}`));if(!files.length)inbox.append(el('p',t('Folder jest pusty.')));
}

export async function poll(){try{const s=await getJSON('/api/status');const running=s.jobs.find(j=>j.status==='running');$('job-banner').hidden=!running;$('sync').disabled=!!running;if(running){$('job-progress').max=running.total;$('job-progress').value=running.progress;$('job-message').textContent=running.message;}
 renderJobs(s.jobs);
 renderInbox(s.inbox);
 const signature=JSON.stringify(s.jobs.map(j=>[j.id,j.status]));const isign=JSON.stringify(s.inbox);if(state.lastJobSignature&&signature!==state.lastJobSignature&&!running){await loadLibrary();const latest=s.jobs[0];if(latest&&latest.status!=='complete')notify(t('Import zakończony z brakami. Otwórz „Źródła i importy”, aby zobaczyć błędy. Dostępne rekordy zapisano.'),true);}if(state.lastInboxSignature&&isign!==state.lastInboxSignature)await loadLibrary();state.lastJobSignature=signature;state.lastInboxSignature=isign;
 }catch(e){if(state.busy)notify(t('Utracono połączenie z lokalnym serwerem.'),true);}finally{clearTimeout(state.statusTimer);state.statusTimer=setTimeout(poll,POLL_INTERVAL_MS);}}

export async function startSync(){try{$('sync').disabled=true;const sources=['osm','bdl','p4n'].filter(s=>$('source-'+s).checked);await api('/api/sync',{areas:$('areas').value,radius:$('radius').value,sources});state.allLibrary=false;notify(t('Import uruchomiony. Możesz przeglądać wcześniej zapisane miejsca.'));await poll();}catch(e){$('sync').disabled=false;notify(e.message,true);}}
