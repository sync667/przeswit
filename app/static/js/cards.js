// Galeria kart miejsc: stronicowanie, liczniki zakładek, znaczniki na mapie, decyzje zachowaj/odrzuć.
import {$,el,notify,googleMapLink,keyChip} from './dom.js';
import {refreshLasso} from './lasso.js';
import {OWN_SOURCE,OWN_STATUS} from './own.js';
import {state,PAGE,labels,providerName,photoURL,SAVED_CHOICES,factsLine,geoFlags} from './state.js';
import {api} from './api.js';
import {filtered,currentMatch} from './library.js';
import {highlightPlace,clearHighlight} from './map.js';
import {showDetail} from './detail.js';
import {formatDistance} from './routes.js';
import {t} from './i18n.js';


function updateCollectionTabs(){
 for(const button of document.querySelectorAll('[data-view]')){const v=button.dataset.view;button.classList.toggle('active',v===state.collection);button.setAttribute('aria-pressed',String(v===state.collection));button.querySelector('.tab-count').textContent=state.places.filter(p=>v==='all'||v==='new'&&!p.choice||v==='saved'&&SAVED_CHOICES.includes(p.choice)||v==='rejected'&&p.choice==='rejected').length;}
}

function placeCard(p){
 const card=el('article',undefined,'place-card'),media=el('div',undefined,'card-media');card.dataset.key=p.key;let photoIndex=0;card.onmouseenter=()=>highlightPlace(p);card.onmouseleave=clearHighlight;card.onfocusin=()=>highlightPlace(p);card.onfocusout=e=>{if(!card.contains(e.relatedTarget))clearHighlight();};
 const imageButton=el('button',undefined,'image-open');imageButton.setAttribute('aria-label',t('Otwórz zdjęcia: {name}',{name:p.name}));
 const img=el('img');img.loading='lazy';img.alt=p.name;img.referrerPolicy='no-referrer';
 const fallback=el('span',t('Brak dostępnego zdjęcia'),'photo-fallback');
 function setPhoto(){const ph=p.photos[photoIndex];img.hidden=!ph||(!$('remote-photos').checked&&!state.photoCache[ph.url]&&!ph.url.startsWith('data:'));fallback.hidden=!img.hidden;if(ph&&!img.hidden){img.src=photoURL(ph.url);img.alt=ph.caption||p.name;}}img.onerror=()=>{img.hidden=true;fallback.hidden=false;};imageButton.append(img,fallback);imageButton.onclick=()=>showDetail(p.key,photoIndex);media.append(imageButton);setPhoto();
 const badge=el('span',providerName(p.source),'photo-source');media.append(badge);
 if(p.photos.length>1){const controls=el('div',undefined,'photo-controls'),count=el('span');function step(delta){photoIndex=(photoIndex+delta+p.photos.length)%p.photos.length;setPhoto();count.textContent=`${photoIndex+1} / ${p.photos.length}`;}for(const [label,delta] of [['‹',-1],['›',1]]){const b=el('button',label);b.setAttribute('aria-label',t('{dir} zdjęcie: {name}',{dir:delta<0?t('Poprzednie'):t('Następne'),name:p.name}));b.onclick=()=>step(delta);controls.append(b);}controls.prepend(count);media.append(controls);step(0);}
 const body=el('div',undefined,'card-body'),title=el('button',p.name,'place-name');title.onclick=()=>showDetail(p.key);const meta=el('div',undefined,'card-meta-row'),maps=googleMapLink(p);maps.classList.add('card-map-link');const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');icon.setAttribute('viewBox','0 0 24 24');icon.setAttribute('aria-hidden','true');const pin=document.createElementNS(icon.namespaceURI,'path');pin.setAttribute('d','M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z');icon.append(pin);maps.prepend(icon);meta.append(el('div',labels[p.type]||p.type,'place-meta'),maps);const facts=el('p',factsLine(p),'card-facts');if(state.routeDistance.has(p.key))facts.append(' ',el('span','↔ '+formatDistance(state.routeDistance.get(p.key)),'route-distance'));facts.append(' ',keyChip(p.key));body.append(meta,title,facts);if(p.source===OWN_SOURCE)body.append(el('div',t('Własny punkt · {status}',{status:OWN_STATUS[p.own_status]||t('Na kiedyś')}),'own-badge'));const flags=geoFlags(p);if(flags.length){const row=el('div',undefined,'card-flags');for(const f of flags)row.append(el('span',f));body.append(row);}
 const scores=el('div',undefined,'card-scores'),fromProfile=p.ai?.source==='profile';for(const [label,val] of [[t('Widok'),p.scores.scenic],[t('Woda'),p.scores.water],['ADV',p.scores.adv_access]])scores.append(el('span',`${label} ${val??'—'}`,fromProfile&&val!=null?'ai':undefined));if(fromProfile){const tag=el('span','AI','ai');tag.title=t('Oceny z lokalnego profilu AI');scores.append(tag);}body.append(scores,el('p',p.status==='excluded'?'⚑ '+(p.red_flags[0]||t('Ograniczenia w źródle')):t('Dojazd i biwak do sprawdzenia'),'card-warning'));
 const actions=el('div',undefined,'card-actions'),reject=el('button',p.choice==='rejected'?t('↶ Przywróć'):t('× Odrzuć')),save=el('button',SAVED_CHOICES.includes(p.choice)?t('✓ Zachowane'):t('＋ Zachowaj do oceny'),'save-place');reject.onclick=()=>choose(p,p.choice==='rejected'?'':'rejected');save.onclick=()=>choose(p,SAVED_CHOICES.includes(p.choice)?'':'shortlist');actions.append(reject,save);const match=currentMatch(p);if(match){body.append(el('div',t('✦ Dopasowanie {match}/100 · pokrycie {coverage}%',{match:match.match,coverage:match.coverage}),'match-score'));if(match.conflicts.length)body.append(el('p',match.conflicts[0],'card-warning'));}const prof=p.profile_info?.profile;body.append(el('p',prof?t('Profil AI · {photos} zdjęć · {count} cech',{photos:prof.photos_analyzed,count:prof.observations.length}):t('Profil AI: {status}',{status:p.profile_info?.status==='error'?t('błąd — do ponowienia'):t('w kolejce')}),'hint card-profile'));body.append(actions);card.append(media,body);
 return card;
}

// Popup znacznika: nazwa, fakty, ID do skopiowania oraz te same decyzje co na kaflu (odświeżają się po zapisie).
function markerPopup(p,marker){
 const pop=el('div',undefined,'marker-popup');
 pop.append(el('strong',p.name),el('div',factsLine(p),'hint'),keyChip(p.key));
 const actions=el('div',undefined,'popup-actions'),save=el('button',undefined,'save-place'),reject=el('button');
 function refresh(){const saved=SAVED_CHOICES.includes(p.choice);save.textContent=saved?t('✓ Zachowane'):t('＋ Zachowaj');save.classList.toggle('chosen',saved);reject.textContent=p.choice==='rejected'?t('↶ Przywróć'):t('× Odrzuć');reject.classList.toggle('chosen',p.choice==='rejected');}
 save.onclick=async()=>{save.disabled=true;await choose(p,SAVED_CHOICES.includes(p.choice)?'':'shortlist');save.disabled=false;refresh();marker.setStyle(markerStyle(p));};
 reject.onclick=async()=>{reject.disabled=true;await choose(p,p.choice==='rejected'?'':'rejected');reject.disabled=false;refresh();marker.setStyle(markerStyle(p));};
 const open=el('button',t('Otwórz kartę →'),'ghost');open.onclick=()=>showDetail(p.key);
 actions.append(save,reject,open);pop.append(actions,googleMapLink(p));refresh();
 return pop;
}
function markerStyle(p){const color=p.source===OWN_SOURCE?'#1c7ed6':p.status==='excluded'||p.choice==='rejected'?'#b56752':p.choice?'#c6a032':'#467453';return {radius:p.choice?6:4,color:'#fff',weight:1,fillColor:color,fillOpacity:.9};}
function renderMarkers(all){
 state.layer.clearLayers();state.markers=new Map();for(const p of all){const marker=L.circleMarker([p.lat,p.lon],markerStyle(p));marker.bindPopup(()=>markerPopup(p,marker),{minWidth:220});state.layer.addLayer(marker);state.markers.set(p.key,marker);}
}

// Galeria bez stronicowania: pierwsza partia od razu, kolejne dokładane w miarę przewijania (IntersectionObserver).
let sentinelObserver=null,sentinelEl=null;
// Element-wartownik żyje poza DOM między renderami (replaceChildren go usuwa), dlatego trzymamy referencję.
function sentinel(){return sentinelEl||(sentinelEl=$('cards-sentinel')||el('div',undefined,'cards-sentinel'));}
function appendBatch(all,rows){
 const start=state.shown,end=Math.min(all.length,start+PAGE);
 for(const p of all.slice(start,end))rows.append(placeCard(p));
 state.shown=end;
 $('page-info').textContent=all.length?t('Pokazano {shown} z {total}',{shown:state.shown,total:all.length}):'';
 const s=sentinel();s.hidden=state.shown>=all.length;rows.append(s);
}
function watchSentinel(all,rows){
 if(sentinelObserver)sentinelObserver.disconnect();
 sentinelObserver=new IntersectionObserver(entries=>{if(entries.some(e=>e.isIntersecting)&&state.shown<all.length)appendBatch(all,rows);},{rootMargin:'600px 0px'});
 sentinelObserver.observe(sentinel());
}

export function render(updateMap=true){const all=filtered();state.page=0;state.shown=0;$('count').textContent=t('{shown} / {total} rekordów',{shown:all.length,total:state.places.length});const rows=$('cards');clearHighlight();rows.replaceChildren();
 updateCollectionTabs();
 appendBatch(all,rows);
 watchSentinel(all,rows);
 if(!all.length){const empty=el('div',undefined,'empty-state');empty.append(el('h2',t('Tutaj jest jeszcze spokojnie.')),el('p',t('Zmień filtry lub wczytaj miejsca. Wyłącz „Tylko ze zdjęciami”, żeby zobaczyć także pozostałe punkty.')));rows.append(empty);}
 if(updateMap&&state.map){renderMarkers(all);refreshLasso();}
}

const UNDO_TOAST_MS=7000;
// Toast z „Cofnij” znika sam po kilku sekundach; kolejna decyzja odświeża licznik.
function showUndoToast(text){$('undo-text').textContent=text;$('undo-toast').hidden=false;clearTimeout(state.undoTimer);state.undoTimer=setTimeout(hideUndoToast,UNDO_TOAST_MS);}
export function hideUndoToast(){clearTimeout(state.undoTimer);$('undo-toast').hidden=true;}

// Pojedyncza decyzja nie przebudowuje listy: kafel znika (albo odświeża się w miejscu), z dołu dojeżdża kolejny,
// scroll zostaje tam, gdzie był. Pełny render tylko przy zmianie filtrów, cofnięciu i akcjach masowych.
function updateAfterChoice(p){
 updateCollectionTabs();
 const rows=$('cards'),all=filtered(),card=rows.querySelector(`[data-key="${CSS.escape(p.key)}"]`);
 const stillListed=all.some(x=>x.key===p.key);
 if(card&&!stillListed){
  card.style.height=card.offsetHeight+'px';card.classList.add('leaving');
  requestAnimationFrame(()=>{card.style.height='0px';});
  setTimeout(()=>card.remove(),190);
  const shownKeys=new Set([...rows.querySelectorAll('.place-card')].map(c=>c.dataset.key));shownKeys.delete(p.key);
  const next=all.find(x=>!shownKeys.has(x.key));
  state.shown=Math.max(0,state.shown-1);
  if(next){const s=sentinel();rows.insertBefore(placeCard(next),s.parentElement===rows?s:null);state.shown++;}
  $('page-info').textContent=all.length?t('Pokazano {shown} z {total}',{shown:Math.min(state.shown,all.length),total:all.length}):'';
  $('count').textContent=t('{shown} / {total} rekordów',{shown:all.length,total:state.places.length});
  if(!all.length)render(false);
 }else if(card){card.replaceWith(placeCard(p));}
 else if(stillListed){
  // Cofnięcie decyzji: kafel wraca na swoje miejsce w kolejności listy (jeśli mieści się w załadowanej części).
  const order=new Map(all.map((x,i)=>[x.key,i])),mine=order.get(p.key);
  const after=[...rows.querySelectorAll('.place-card')].find(c=>(order.get(c.dataset.key)??Infinity)>mine);
  if(after){rows.insertBefore(placeCard(p),after);state.shown++;}
  else if(state.shown>=all.length-1){const s=sentinel();rows.insertBefore(placeCard(p),s.parentElement===rows?s:null);state.shown++;}
  $('page-info').textContent=t('Pokazano {shown} z {total}',{shown:Math.min(state.shown,all.length),total:all.length});$('count').textContent=t('{shown} / {total} rekordów',{shown:all.length,total:state.places.length});
 }
 state.markers?.get(p.key)?.setStyle(markerStyle(p));
 refreshLasso();
 import('./routes.js').then(m=>m.renderPlan());
}

export async function choose(p,choice){const previous={key:p.key,choice:p.choice||'',note:p.user_note||''};try{await api('/api/note',{key:p.key,choice,note:p.user_note||''});p.choice=choice;state.undoAction=[previous];showUndoToast(choice==='rejected'?t('Miejsce odrzucone'):choice?t('Zachowano do oceny'):t('Przywrócono do przeglądania'));updateAfterChoice(p);return true;}catch(e){notify(e.message,true);return false;}}

// Masowa decyzja (lasso): zapis po kolei, jedno „Cofnij” przywraca wszystkie zmienione rekordy.
export async function bulkChoose(places,choice){
 const previous=[];let done=0;
 for(const p of places){try{await api('/api/note',{key:p.key,choice,note:p.user_note||''});previous.push({key:p.key,choice:p.choice||'',note:p.user_note||''});p.choice=choice;done++;}catch(e){notify(`${p.name}: ${e.message}`,true);}}
 if(previous.length){state.undoAction=previous;const n=previous.length;showUndoToast(t('{verb} {n} {word}',{verb:choice==='rejected'?t('Odrzucono'):choice?t('Zachowano'):t('Przywrócono'),n,word:n===1?t('miejsce'):n<5?t('miejsca'):t('miejsc')}));}
 render();return done;
}

export async function undo(){if(!state.undoAction)return;const actions=[].concat(state.undoAction);try{const touched=[];for(const a of actions){await api('/api/note',a);const p=state.places.find(x=>x.key===a.key);if(p){p.choice=a.choice;touched.push(p);}}state.undoAction=null;hideUndoToast();if(touched.length===1)updateAfterChoice(touched[0]);else render();}catch(e){notify(e.message,true);}}
