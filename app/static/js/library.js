// Ładowanie biblioteki z backendu, filtrowanie i sortowanie listy, dopasowanie do wyszukiwania AI.
import {$,notify} from './dom.js';
import {state,providerName} from './state.js';
import {api} from './api.js';
import {render} from './cards.js';
import {showDetail} from './detail.js';
import {syncRoutes,nearRouteActive,isNearRoute} from './routes.js';

// Filtr „cechy miejsca”: łączy typ obiektu (OSM/import) z flagami P4N zapisanymi w geo (p4n_*, viewpoint).
const TYPE_RULES={
 viewpoint:p=>p.type==='viewpoint'||!!p.geo.viewpoint||!!p.geo.p4n_point_de_vue,
 water:p=>['beach','water_access'].includes(p.type)||p.geo.water_distance_m<300||!!p.geo.p4n_baignade||!!p.geo.p4n_eaux_vives||!!p.geo.p4n_windsurf||!!p.geo.p4n_peche_pied,
 swimming:p=>!!p.geo.p4n_baignade||!!p.geo.p4n_piscine,
 fishing:p=>!!p.geo.p4n_peche||!!p.geo.p4n_peche_pied,
 whitewater:p=>!!p.geo.p4n_eaux_vives,
 hiking:p=>!!p.geo.p4n_rando,
 mtb:p=>!!p.geo.p4n_vtt,
 climbing:p=>!!p.geo.p4n_escalade,
 moto:p=>!!p.geo.p4n_moto,
 drinking_water:p=>!!p.geo.p4n_point_eau,
 toilet:p=>!!p.geo.p4n_wc_public,
 bins:p=>!!p.geo.p4n_poubelle,
 mobile:p=>!!p.geo.p4n_donnees_mobile,
 pets:p=>!!p.geo.p4n_animaux,
 overnight:p=>['camp_site','camp_pitch','caravan_site','wilderness_hut'].includes(p.type),
};
export function matchesType(p,type){const rule=TYPE_RULES[type];return rule?rule(p):p.type===type;}

export function areaRequest(){return {areas:state.allLibrary?'':$('areas').value,radius:$('radius').value};}

// Wynik wyszukiwania AI dla miejsca, o ile dotyczy aktualnego opisu i aktualnego profilu.
export function currentMatch(p){const r=state.searchResults.get(p.key);return state.searchCriteria===$('wish').value.trim()&&r&&r.fingerprint===p.profile_info?.fingerprint?r:null;}

export async function loadLibrary(fit=false){try{const r=await api('/api/library',{...areaRequest(),save_area:!state.allLibrary});state.photoCache=r.photo_cache||{};state.places=r.spots;state.page=0;syncRoutes();$('total').textContent=`${r.total} rekordów w lokalnej bazie`;const selectedSource=$('source-filter').value;$('source-filter').replaceChildren(new Option('Wszystkie źródła',''));for(const s of [...new Set(state.places.map(p=>p.source))].sort())$('source-filter').append(new Option(providerName(s),s));$('source-filter').value=selectedSource;render();if(fit&&state.map){if(r.areas.length){const b=r.areas.map(a=>a.bbox);state.map.fitBounds([[Math.min(...b.map(x=>x[1])),Math.min(...b.map(x=>x[0]))],[Math.max(...b.map(x=>x[3])),Math.max(...b.map(x=>x[2]))]]);}else if(state.places.length)state.map.fitBounds(state.places.map(p=>[p.lat,p.lon]),{maxZoom:11});}if(state.selected&&$('detail').open)showDetail(state.selected);notify(`${r.spots.length} rekordów ${state.allLibrary?'w całej bazie':'w wybranym obszarze'} · ${r.outside} poza obszarem. Dane zachowane lokalnie. Kompletność dotyczy raportu importu, nie wszystkich miejsc w terenie.`);}catch(e){notify(e.message,true);}}

export function filtered(){const q=$('search').value.toLocaleLowerCase('pl'),src=$('source-filter').value,type=$('type-filter').value;return state.places.filter(p=>{
 if(state.collection==='new'&&p.choice)return false;
 if(state.collection==='saved'&&!['shortlist','A','B'].includes(p.choice))return false;
 if(state.collection==='rejected'&&p.choice!=='rejected')return false;
 if($('photos-only').checked&&!p.photos.length)return false;
 if($('ai-only').checked&&!currentMatch(p))return false;
 if(src&&p.source!==src)return false;
 if(q&&!`${p.name} ${p.description} ${p.user_note||''}`.toLocaleLowerCase('pl').includes(q))return false;
 if(type&&!matchesType(p,type))return false;
 if($('only-map').checked&&state.map&&!state.map.getBounds().contains([p.lat,p.lon]))return false;
 if(nearRouteActive()&&!isNearRoute(p))return false;
 return true;
}).sort((a,b)=>(a.status==='excluded')-(b.status==='excluded')||Number(currentMatch(b)?.requirements_met??false)-Number(currentMatch(a)?.requirements_met??false)||(currentMatch(b)?.match??-1)-(currentMatch(a)?.match??-1)||(state.routes.length?(state.routeDistance.get(a.key)??Infinity)-(state.routeDistance.get(b.key)??Infinity):0)||a.name.localeCompare(b.name,'pl'));}
