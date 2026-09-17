// Galeria kart miejsc: stronicowanie, liczniki zakładek, znaczniki na mapie, decyzje zachowaj/odrzuć.
import {$,el,notify,googleMapLink} from './dom.js';
import {state,PAGE,labels,providerName,photoURL,SAVED_CHOICES,factsLine} from './state.js';
import {api} from './api.js';
import {filtered,currentMatch} from './library.js';
import {highlightPlace,clearHighlight} from './map.js';
import {showDetail} from './detail.js';


function updateCollectionTabs(){
 for(const button of document.querySelectorAll('[data-view]')){const v=button.dataset.view;button.classList.toggle('active',v===state.collection);button.setAttribute('aria-pressed',String(v===state.collection));button.querySelector('span').textContent=state.places.filter(p=>v==='all'||v==='new'&&!p.choice||v==='saved'&&SAVED_CHOICES.includes(p.choice)||v==='rejected'&&p.choice==='rejected').length;}
}

function placeCard(p){
 const card=el('article',undefined,'place-card'),media=el('div',undefined,'card-media');let photoIndex=0;card.onmouseenter=()=>highlightPlace(p);card.onmouseleave=clearHighlight;card.onfocusin=()=>highlightPlace(p);card.onfocusout=e=>{if(!card.contains(e.relatedTarget))clearHighlight();};
 const imageButton=el('button',undefined,'image-open');imageButton.setAttribute('aria-label','Otwórz zdjęcia: '+p.name);
 const img=el('img');img.loading='lazy';img.alt=p.name;img.referrerPolicy='no-referrer';
 const fallback=el('span','Brak dostępnego zdjęcia','photo-fallback');
 function setPhoto(){const ph=p.photos[photoIndex];img.hidden=!ph||(!$('remote-photos').checked&&!state.photoCache[ph.url]&&!ph.url.startsWith('data:'));fallback.hidden=!img.hidden;if(ph&&!img.hidden){img.src=photoURL(ph.url);img.alt=ph.caption||p.name;}}img.onerror=()=>{img.hidden=true;fallback.hidden=false;};imageButton.append(img,fallback);imageButton.onclick=()=>showDetail(p.key,photoIndex);media.append(imageButton);setPhoto();
 const badge=el('span',providerName(p.source),'photo-source');media.append(badge);
 if(p.photos.length>1){const controls=el('div',undefined,'photo-controls'),count=el('span');function step(delta){photoIndex=(photoIndex+delta+p.photos.length)%p.photos.length;setPhoto();count.textContent=`${photoIndex+1} / ${p.photos.length}`;}for(const [label,delta] of [['‹',-1],['›',1]]){const b=el('button',label);b.setAttribute('aria-label',(delta<0?'Poprzednie':'Następne')+' zdjęcie: '+p.name);b.onclick=()=>step(delta);controls.append(b);}controls.prepend(count);media.append(controls);step(0);}
 const body=el('div',undefined,'card-body'),title=el('button',p.name,'place-name');title.onclick=()=>showDetail(p.key);const meta=el('div',undefined,'card-meta-row'),maps=googleMapLink(p);maps.classList.add('card-map-link');const icon=document.createElementNS('http://www.w3.org/2000/svg','svg');icon.setAttribute('viewBox','0 0 24 24');icon.setAttribute('aria-hidden','true');const pin=document.createElementNS(icon.namespaceURI,'path');pin.setAttribute('d','M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z M15 10a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z');icon.append(pin);maps.prepend(icon);meta.append(el('div',labels[p.type]||p.type,'place-meta'),maps);body.append(meta,title,el('p',factsLine(p),'card-facts'));
 const scores=el('div',undefined,'card-scores'),fromProfile=p.ai?.source==='profile';for(const [label,val] of [['Widok',p.scores.scenic],['Woda',p.scores.water],['ADV',p.scores.adv_access]])scores.append(el('span',`${label} ${val??'—'}`,fromProfile&&val!=null?'ai':undefined));if(fromProfile){const tag=el('span','AI','ai');tag.title='Oceny z lokalnego profilu AI';scores.append(tag);}body.append(scores,el('p',p.status==='excluded'?'⚑ '+(p.red_flags[0]||'Ograniczenia w źródle'):'Dojazd i biwak do sprawdzenia','card-warning'));
 const actions=el('div',undefined,'card-actions'),reject=el('button',p.choice==='rejected'?'↶ Przywróć':'× Odrzuć'),save=el('button',SAVED_CHOICES.includes(p.choice)?'✓ Zachowane':'＋ Zachowaj do oceny','save-place');reject.onclick=()=>choose(p,p.choice==='rejected'?'':'rejected');save.onclick=()=>choose(p,SAVED_CHOICES.includes(p.choice)?'':'shortlist');actions.append(reject,save);const match=currentMatch(p);if(match){body.append(el('div',`✦ Dopasowanie ${match.match}/100 · pokrycie ${match.coverage}%`,'match-score'));if(match.conflicts.length)body.append(el('p',match.conflicts[0],'card-warning'));}const prof=p.profile_info?.profile;body.append(el('p',prof?`Profil AI · ${prof.photos_analyzed} zdjęć · ${prof.observations.length} cech`:'Profil AI: '+(p.profile_info?.status==='error'?'błąd — do ponowienia':'w kolejce'),'hint'));body.append(actions);card.append(media,body);
 return card;
}

function renderMarkers(all){
 state.layer.clearLayers();for(const p of all){const color=p.status==='excluded'||p.choice==='rejected'?'#b56752':p.choice?'#c6a032':'#467453';const marker=L.circleMarker([p.lat,p.lon],{radius:p.choice?6:4,color:'#fff',weight:1,fillColor:color,fillOpacity:.9});const pop=el('div');pop.append(el('strong',p.name),el('div',labels[p.type]||p.type));const open=el('button','Otwórz kartę →');open.onclick=()=>showDetail(p.key);pop.append(open,googleMapLink(p));marker.bindPopup(pop);state.layer.addLayer(marker);}
}

export function render(updateMap=true){const all=filtered();state.page=Math.min(state.page,Math.max(0,Math.ceil(all.length/PAGE)-1));$('count').textContent=`${all.length} / ${state.places.length} rekordów`;$('page-info').textContent=`Strona ${state.page+1} / ${Math.max(1,Math.ceil(all.length/PAGE))}`;$('prev').disabled=state.page===0;$('next').disabled=(state.page+1)*PAGE>=all.length;const rows=$('cards');clearHighlight();rows.replaceChildren();
 updateCollectionTabs();
 for(const p of all.slice(state.page*PAGE,(state.page+1)*PAGE))rows.append(placeCard(p));
 if(!all.length){const empty=el('div',undefined,'empty-state');empty.append(el('h2','Tutaj jest jeszcze spokojnie.'),el('p','Zmień filtry lub wczytaj miejsca. Wyłącz „Tylko ze zdjęciami”, żeby zobaczyć także pozostałe punkty.'));rows.append(empty);}
 if(updateMap&&state.map)renderMarkers(all);
}

export async function choose(p,choice){const previous={key:p.key,choice:p.choice||'',note:p.user_note||''};try{await api('/api/note',{key:p.key,choice,note:p.user_note||''});p.choice=choice;state.undoAction=previous;$('undo-text').textContent=choice==='rejected'?'Miejsce odrzucone':choice?'Zachowano do oceny':'Przywrócono do przeglądania';$('undo-toast').hidden=false;render();return true;}catch(e){notify(e.message,true);return false;}}

export async function undo(){if(!state.undoAction)return;try{await api('/api/note',state.undoAction);const p=state.places.find(x=>x.key===state.undoAction.key);if(p)p.choice=state.undoAction.choice;state.undoAction=null;$('undo-toast').hidden=true;render();}catch(e){notify(e.message,true);}}
