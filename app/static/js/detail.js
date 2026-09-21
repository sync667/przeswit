// Okno szczegółów miejsca: nagłówek z akcjami, galeria, oceny, profil AI, mapa, komentarze, notatka, dowody.
import {$,el,link,notify,googleMapLink,distance,keyChip,placeLink} from './dom.js';
import {state,labels,featureLabels,featureGroups,negativeFeatures,providerName,photoURL,SAVED_CHOICES,factsLine,geoFlags} from './state.js';
import {api} from './api.js';
import {loadLibrary,currentMatch} from './library.js';
import {render,choose} from './cards.js';
import {FOREST_WMS,FOREST_OPTIONS,attachBasemaps,earth3dLink,googleSatelliteLink} from './map.js';
import {formatDistance} from './routes.js';
import {OWN_SOURCE,OWN_STATUS,openOwnDialog} from './own.js';
import {t} from './i18n.js';

let detailMap=null;

function section(title,cls){const s=el('section',undefined,'detail-section'+(cls?' '+cls:''));s.append(el('h3',title,'detail-section-title'));return s;}

// Szybkie decyzje w nagłówku karty — te same co na kafelku; etykiety odświeżają się po zapisie.
function quickActions(p){
 const row=el('div',undefined,'detail-actions');
 const save=el('button',undefined,'save-place'),reject=el('button');
 function refresh(){const saved=SAVED_CHOICES.includes(p.choice);save.textContent=saved?t('✓ Zachowane do oceny'):t('＋ Zachowaj do oceny');save.classList.toggle('chosen',saved);reject.textContent=p.choice==='rejected'?t('↶ Przywróć do przeglądania'):t('× Odrzuć');reject.classList.toggle('chosen',p.choice==='rejected');const sel=$('detail-choice');if(sel)sel.value=saved?'shortlist':p.choice||'';}
 save.onclick=async()=>{save.disabled=true;await choose(p,SAVED_CHOICES.includes(p.choice)?'':'shortlist');save.disabled=false;refresh();};
 reject.onclick=async()=>{reject.disabled=true;await choose(p,p.choice==='rejected'?'':'rejected');reject.disabled=false;refresh();};
 row.append(save,reject);if(p.source===OWN_SOURCE){const edit=el('button',t('✎ Edytuj punkt'));edit.onclick=()=>openOwnDialog(p);row.append(edit);}refresh();row.refresh=refresh;
 return row;
}

function scoreGrid(p){
 const scores=el('div',undefined,'score-grid');
 for(const [label,value] of [['ADV',p.scores.adv_access],[t('Widok'),p.scores.scenic],[t('Woda'),p.scores.water],[t('Spokój'),p.scores.solitude],[t('Dowody zgód'),p.legal_confidence]]){const box=el('div',undefined,'score-box');box.append(el('strong',value??'—'),el('span',label));scores.append(box);}
 return scores;
}

function detailGallery(p,availablePhotos,startPhoto){
 const photos=el('div',undefined,'detail-gallery');
 if(!availablePhotos.length)return photos;
 let index=Math.min(startPhoto,availablePhotos.length-1);const stage=el('div',undefined,'gallery-stage'),img=el('img'),caption=el('div',undefined,'gallery-caption'),counter=el('span',undefined,'gallery-counter'),thumbs=el('div',undefined,'gallery-thumbs');img.referrerPolicy='no-referrer';const failure=el('span',t('Nie udało się wczytać tego zdjęcia. Przejdź do następnego.'),'gallery-failure');failure.hidden=true;img.onerror=()=>{img.hidden=true;failure.hidden=false;};stage.append(img,failure,counter);
 function display(delta=0){index=(index+delta+availablePhotos.length)%availablePhotos.length;const ph=availablePhotos[index];img.hidden=false;failure.hidden=true;img.src=photoURL(ph.url);img.alt=ph.caption||p.name;counter.textContent=`${index+1} / ${availablePhotos.length}`;caption.replaceChildren(el('span',[ph.caption,ph.author,ph.license].filter(Boolean).join(' · ')));if(ph.source_url)caption.append(' ',link(t('Źródło zdjęcia ↗'),ph.source_url));for(const [i,b] of [...thumbs.children].entries()){b.classList.toggle('active',i===index);b.setAttribute('aria-pressed',String(i===index));}}
 if(availablePhotos.length>1){stage.tabIndex=0;stage.setAttribute('aria-label',t('Galeria zdjęć. Użyj strzałek w lewo i w prawo.'));for(const [label,delta,cls] of [['‹',-1,'previous'],['›',1,'next']]){const button=el('button',label,'gallery-arrow '+cls);button.setAttribute('aria-label',delta<0?t('Poprzednie zdjęcie'):t('Następne zdjęcie'));button.onclick=()=>display(delta);stage.append(button);}stage.onkeydown=e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();display(e.key==='ArrowLeft'?-1:1);}};let touchStart=null;stage.addEventListener('touchstart',e=>{touchStart=e.touches[0].clientX;},{passive:true});stage.addEventListener('touchend',e=>{if(touchStart!==null){const dx=e.changedTouches[0].clientX-touchStart;if(Math.abs(dx)>45)display(dx<0?1:-1);touchStart=null;}},{passive:true});
 for(const [i,ph] of availablePhotos.entries()){const button=el('button'),thumb=el('img');button.setAttribute('aria-label',t('Pokaż zdjęcie {n}',{n:i+1}));thumb.src=photoURL(ph.url);thumb.alt='';thumb.loading='lazy';thumb.referrerPolicy='no-referrer';button.append(thumb);button.onclick=()=>{index=i;display();};thumbs.append(button);}}
 photos.append(stage,caption,thumbs);display();
 return photos;
}

// Jedna cecha profilu: nazwa, wskaźnik pewności (3 słupki + podpowiedź), wynik jako liczba, pasek natężenia
// (blednie przy niskiej pewności); uzasadnienie w dwóch wierszach, pełne po najechaniu.
function featureRow(o){
 const row=el('div',undefined,'ai-feature'+(negativeFeatures.has(o.feature)?' negative':''));
 const score=Math.max(0,Math.min(100,Number(o.score)||0)),conf=Math.max(0,Math.min(100,Number(o.confidence)||0));
 row.style.setProperty('--conf',String(conf/100));
 const confidence=el('span',undefined,'ai-conf');confidence.dataset.level=conf>=70?'high':conf>=40?'mid':'low';confidence.title=t('Pewność modelu: {conf}%',{conf});confidence.setAttribute('role','img');confidence.setAttribute('aria-label',t('pewność {conf}%',{conf}));for(let i=0;i<3;i++)confidence.append(el('i'));
 const bar=el('span',undefined,'ai-bar'),fill=el('i');fill.style.width=`${score}%`;bar.append(fill);bar.setAttribute('aria-hidden','true');
 const head=el('div',undefined,'ai-feature-head');head.append(el('span',featureLabels[o.feature]||o.feature,'ai-feature-name'),confidence,el('span',String(o.score),'ai-score'));
 const reason=el('p',o.reason||'','ai-reason');reason.title=o.reason||'';
 row.append(head,bar,reason);
 return row;
}

function profileSection(p){
 const profile=p.profile_info?.profile;
 const box=section(t('Profil AI'),'ai-profile');
 if(!profile){box.append(el('p',p.profile_info?.status==='error'?t('Profil nie powstał — błąd analizy; ponów z panelu profilowania.'):t('Profil AI powstanie automatycznie w tle. Oceny poniżej pochodzą na razie z reguł i danych źródła.'),'hint'));return box;}
 const meta=el('p',[`${profile.model}`,t('{a} / {b} zdjęć',{a:profile.photos_analyzed,b:profile.photos_total}),profile.coverage==='text_only'?t('tylko opis i kontekst — bez analizy obrazu'):t('zdjęcia i opis'),profile.date?.slice(0,10)].filter(Boolean).join(' · '),'ai-meta');
 box.append(meta);
 if(profile.summary)box.append(el('p',profile.summary,'ai-summary'));
 if(profile.scenes?.length){const scenes=el('ul',undefined,'ai-scenes');for(const s of profile.scenes)scenes.append(el('li',s));box.append(scenes);}
 const byFeature=new Map();for(const o of profile.observations){const prev=byFeature.get(o.feature);if(!prev||o.score>prev.score)byFeature.set(o.feature,o);}
 const groups=el('div',undefined,'ai-groups');let placed=0;
 for(const [title,features] of featureGroups){const rows=features.filter(f=>byFeature.has(f)).map(f=>byFeature.get(f)).sort((a,b)=>b.score-a.score);if(!rows.length)continue;const g=el('div',undefined,'ai-group');g.append(el('h4',title));for(const o of rows){g.append(featureRow(o));placed++;}groups.append(g);}
 const rest=[...byFeature.values()].filter(o=>!featureGroups.some(([,f])=>f.includes(o.feature)));
 if(rest.length){const g=el('div',undefined,'ai-group');g.append(el('h4',t('Inne')));for(const o of rest)g.append(featureRow(o));groups.append(g);}
 box.append(placed||rest.length?groups:el('p',t('Model nie rozpoznał żadnej cechy z katalogu.'),'hint'));
 if(profile.warnings?.length){const w=el('div',undefined,'ai-warnings');w.append(el('h4',t('Ostrzeżenia')));const ul=el('ul');for(const item of profile.warnings)ul.append(el('li',item));w.append(ul);box.append(w);}
 if(profile.unknown?.length){const u=el('div',undefined,'ai-unknown');u.append(el('h4',t('Bez danych w źródle')));const chips=el('div',undefined,'ai-chips');for(const item of profile.unknown)chips.append(el('span',item.replace(/\.$/,'')));u.append(chips);box.append(u);}
 if(profile.skipped_photos?.length)box.append(el('p',t('Pominięte zdjęcia: {list}',{list:profile.skipped_photos.join('; ')}),'hint'));
 const c=profile.source_coverage;if(c)box.append(el('p',t('Materiał: opis {dc}/{dt} znaków · komentarze {cu}/{ct} · dowody {eu}/{et} · typ i metadane źródła',{dc:c.description_chars,dt:c.description_total_chars,cu:c.comments_used,ct:c.comments_total,eu:c.evidence_used,et:c.evidence_total}),'hint'));
 const m=currentMatch(p);
 if(m){const match=el('div',undefined,'ai-match');match.append(el('h4',t('Dopasowanie do wyszukiwania: {match}/100 · pokrycie {coverage}%',{match:m.match,coverage:m.coverage})));const ul=el('ul');for(const t2 of m.reasons)ul.append(el('li',t2));for(const t2 of m.conflicts)ul.append(el('li',t2,'conflict'));if(m.missing.length)ul.append(el('li',t('Brak danych: {list}',{list:m.missing.join(', ')}),'missing'));match.append(ul);box.append(match);}
 return box;
}

function mapSection(p){
 const box=section(t('Lokalizacja'),'detail-map-section');
 const holder=el('div',undefined,'detail-map');holder.id='detail-map';
 const tools=el('div',undefined,'detail-map-tools');
 tools.append(link(t('Google Earth 3D ↗'),earth3dLink(p)),link(t('Google Maps satelita ↗'),googleSatelliteLink(p)),el('span',`${p.lat.toFixed(6)}, ${p.lon.toFixed(6)}`,'hint'));
 box.append(holder,tools,el('p',t('Podkład przełączysz ikoną warstw w rogu mapy (OSM · satelita · satelita + rzeźba terenu). Prawdziwy widok 3D z nachyleniem otwiera Google Earth.'),'hint'));
 return box;
}

// Mapa tworzona po otwarciu okna (Leaflet potrzebuje widocznego kontenera o znanych wymiarach).
function mountMap(p){
 if(detailMap){detailMap.remove();detailMap=null;}
 const holder=$('detail-map');if(!holder||!window.L)return;
 if(!$('tiles').checked){holder.replaceWith(el('p',t('Podkład mapy wyłączony — włącz „Podkłady map online” w ustawieniach.'),'hint'));return;}
 detailMap=L.map(holder,{scrollWheelZoom:false}).setView([p.lat,p.lon],16);
 const forest=L.tileLayer.wms(FOREST_WMS,FOREST_OPTIONS);
 attachBasemaps(detailMap,'detail','relief',{[t('Zanocuj w lesie (BDL)')]:forest});
 if($('forest-overlay')?.checked??true)forest.addTo(detailMap);
 for(const r of state.routes)for(const l of r.lines)L.polyline(l.points,{color:r.color,weight:4,opacity:.9,dashArray:l.kind==='route'?'8 6':null}).addTo(detailMap).bindTooltip(r.name,{sticky:true});
 L.circleMarker([p.lat,p.lon],{radius:9,color:'#fff',weight:3,fillColor:'#ed8d32',fillOpacity:1}).addTo(detailMap).bindTooltip(p.name,{permanent:true,direction:'top',offset:[0,-9]});
 setTimeout(()=>detailMap?.invalidateSize(),50);
}

function commentsSection(p){
 if(!p.comments.length)return null;
 const box=section(t('Komentarze ({n})',{n:p.comments.length}),'detail-comments');
 const list=el('div',undefined,'comment-list');
 for(const c of p.comments){const item=el('article',undefined,'comment');const head=el('div',undefined,'comment-head');head.append(el('span',c.date?.slice(0,10)||t('bez daty')));if(c.author)head.append(el('span',String(c.author)));if(typeof c.rating==='number')head.append(el('span',`★ ${c.rating}`));item.append(head,el('p',c.text));list.append(item);}
 box.append(list);
 return box;
}

function notesSection(p){
 const box=section(t('Twój wybór i notatka'),'detail-notes');
 if(p.note_author&&(p.choice||p.user_note))box.append(el('p',t('Ostatnia zmiana: {who}{when}',{who:p.note_author==='local'?t('ten komputer'):p.note_author,when:p.note_updated?' · '+new Date(p.note_updated*1000).toLocaleString('pl-PL'):''}),'hint'));
 const notes=el('div',undefined,'note-grid'),choiceGroup=el('div'),noteGroup=el('div'),choice=el('select');choice.id='detail-choice';for(const [v,text] of [['',t('Jeszcze nie wybrane')],['shortlist',t('Na mojej liście')],['rejected',t('Odrzucone przeze mnie')]])choice.append(new Option(text,v));choice.value=['A','B'].includes(p.choice)?'shortlist':p.choice||'';const cl=el('label',t('Twój wybór'));cl.htmlFor=choice.id;choiceGroup.append(cl,choice);const text=el('textarea');text.id='detail-note';text.value=p.user_note||'';text.placeholder=t('Dojazd, kontakt, rzeczy do sprawdzenia…');const nl=el('label',t('Prywatna notatka'));nl.htmlFor=text.id;noteGroup.append(nl,text);notes.append(choiceGroup,noteGroup);box.append(notes);const save=el('button',t('Zapisz wybór i notatkę'),'note-save');save.onclick=async()=>{try{await api('/api/note',{key:p.key,choice:choice.value,note:text.value});p.choice=choice.value;p.user_note=text.value;render();save.textContent=t('Zapisano lokalnie ✓');document.querySelector('.detail-actions')?.refresh?.();}catch(e){notify(e.message,true);}};box.append(save);
 return box;
}

function evidenceSection(p){
 const evidence=el('details',undefined,'detail-evidence');evidence.append(el('summary',t('Uzasadnienie ocen, dowody i kontekst geograficzny')));
 const reasons=el('ul');for(const r of p.reasons)reasons.append(el('li',r));evidence.append(reasons);
 for(const e of p.evidence)evidence.append(el('p',`${e.topic} · ${e.value} · ${e.authority} · ${e.date||t('bez daty')} · ${e.text}`));
 if(Object.keys(p.geo||{}).length)evidence.append(el('pre',JSON.stringify(p.geo,null,2),'source-raw'));
 if(p.ai&&p.ai.source!=='profile')evidence.append(el('pre',JSON.stringify(p.ai,null,2),'source-raw'));
 return evidence;
}

export function showDetail(key,startPhoto=0){const p=state.places.find(x=>x.key===key);if(!p)return;state.selected=key;const root=$('detail-content');root.replaceChildren();
 root.append(el('h2',p.name,'detail-title'));
 const badges=el('div',undefined,'detail-badges');badges.append(el('span',providerName(p.source),'badge'),el('span',labels[p.type]||p.type,'badge'),el('span',p.status==='excluded'?t('ODRZUCONE'):p.status==='candidate'?t('DOWODY ZGÓD W IMPORCIE'):t('DO SPRAWDZENIA'),'badge '+p.status),el('span',factsLine(p),'detail-facts'));if(state.routeDistance.has(p.key))badges.append(el('span','↔ '+formatDistance(state.routeDistance.get(p.key)),'route-distance'));badges.append(keyChip(p.key,'detail-key'));root.append(badges);
 history.replaceState(null,'',placeLink(p.key));
 if(p.source===OWN_SOURCE)root.append(el('div',t('Własny punkt · {status}',{status:OWN_STATUS[p.own_status]||t('Na kiedyś')}),'own-badge'));
 const flags=geoFlags(p);if(flags.length){const row=el('div',undefined,'card-flags detail-flags');for(const f of flags)row.append(el('span',f));root.append(row);}
 root.append(quickActions(p));
 const links=el('div',undefined,'detail-links');links.append(googleMapLink(p));if(p.source_url)links.append(link(t('Źródło miejsca ↗'),p.source_url));if(p.p4n_url&&p.p4n_url!==p.source_url)links.append(link('P4N ↗',p.p4n_url));if(p.website)links.append(link(t('Strona / regulamin ↗'),p.website));links.append(link(t('Pokaż w OSM ↗'),`https://www.openstreetmap.org/?mlat=${p.lat}&mlon=${p.lon}#map=16/${p.lat}/${p.lon}`));root.append(links,el('p',t('pobrano {fetched} · data źródła {sourceDate} · {mode} · pokrycie danych {coverage}%',{fetched:p.fetched_at?.slice(0,10)||t('brak daty'),sourceDate:p.source_date?.slice(0,10)||t('nieznana'),mode:p.analysis_mode,coverage:p.evidence_coverage}),'hint detail-meta'));
 const availablePhotos=p.photos.filter(ph=>ph.url.startsWith('data:image/')||state.photoCache[ph.url]||$('remote-photos').checked);
 root.append(detailGallery(p,availablePhotos,startPhoto));
 if(p.photos.length&&!$('remote-photos').checked)root.append(el('p',t('Zdjęcia dostępne: włącz „Wyświetlaj zdjęcia z internetu” w ustawieniach.'),'hint'));
 root.append(scoreGrid(p));
 if(p.description){const d=section(t('Opis ze źródła'));d.append(el('p',p.description,'description'));root.append(d);}
 if(p.red_flags.length){const f=section(t('Do sprawdzenia'));const flags=el('ul',undefined,'flag-list');for(const x of p.red_flags)flags.append(el('li',x));f.append(flags);root.append(f);}
 root.append(profileSection(p));
 const columns=el('div',undefined,'detail-columns');columns.append(mapSection(p));const comments=commentsSection(p);if(comments)columns.append(comments);else columns.classList.add('single');root.append(columns);
 const actions=el('div',undefined,'actions');function action(label,path,disabled=false,body={}){const b=el('button',label);b.disabled=disabled;b.onclick=async()=>{b.disabled=true;b.textContent=t('Pracuję…');try{await api(path,{key:p.key,...body});await loadLibrary();showDetail(p.key);}catch(e){b.disabled=false;b.textContent=label;notify(e.message,true);const err=el('p',e.message,'mini-flag');actions.after(err);}};actions.append(b);}
 action(t('Sprawdź wodę i drogę (OSM)'),'/api/enrich');if(p.commons_file)action(t('Pobierz zdjęcie z Commons'),'/api/commons');root.append(actions);
 if(p.local_only)root.append(el('p',t('Analiza zdjęć działa lokalnie na tym komputerze.'),'hint'));
 root.append(notesSection(p));
 root.append(evidenceSection(p));
 const nearby=state.places.filter(x=>x.key!==p.key&&x.source!==p.source&&distance(p,x)<150).sort((a,b)=>distance(p,a)-distance(p,b)).slice(0,6);if(nearby.length){const group=el('div',undefined,'nearby');group.append(el('h3',t('W pobliżu w innych źródłach')),el('p',t('Możliwy duplikat lub sąsiedni obiekt — rekordów nie scalamy bez sprawdzenia.')));for(const n of nearby){const b=el('button',t('{name} · {source} · {m} m',{name:n.name,source:providerName(n.source),m:Math.round(distance(p,n))}));b.onclick=()=>showDetail(n.key);group.append(b);}root.append(group);}
 root.append(el('p',p.license||t('Warunki oryginalnego źródła'),'hint'));const raw=el('details',undefined,'detail-raw');raw.append(el('summary',t('Oryginalny rekord źródłowy')),el('pre',JSON.stringify(p.raw||{},null,2),'source-raw'));root.append(raw);
 if(!$('detail').open)$('detail').showModal();
 mountMap(p);
}
