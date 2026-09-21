// Wspólny stan aplikacji i stałe. Moduły modyfikują pola `state`, nie kopiują ich.
import {t} from './i18n.js';
export const PAGE=24;

export const labels={camp_site:t('Biwak / kemping'),camp_pitch:t('Stanowisko namiotowe'),caravan_site:t('Miejsce dla kamperów'),viewpoint:t('Punkt widokowy'),picnic_site:t('Piknik'),beach:t('Plaża'),water_access:t('Punkt wodowania'),parking:t('Parking'),wilderness_hut:t('Schron terenowy'),import:t('Punkt z importu')};

export const featureLabels={"panorama": t("rozległa panorama"), "mountains": t("widok gór"), "elevated": t("położenie wysoko / zbocze"), "forest": t("las"), "meadow": t("łąka / polana"), "wild_nature": t("naturalne otoczenie"), "river": t("rzeka lub potok"), "lake": t("jezioro"), "waterfront": t("bezpośrednio przy wodzie"), "water_access": t("możliwość dojścia do wody"), "beach": t("plaża"), "shade": t("cień"), "sun_exposure": t("nasłonecznienie"), "sunset": t("potwierdzony widok zachodu"), "sunrise": t("potwierdzony widok wschodu"), "flat_ground": t("płaski teren"), "tent_space": t("miejsce fizyczne na namiot"), "moto_adjacent": t("miejsce na motocykl obok namiotu"), "road_access": t("dowody fizycznego dojazdu"), "gravel": t("szuter"), "easy_offroad": t("lekki teren"), "difficult_terrain": t("trudny teren"), "mud": t("błoto / grząski grunt"), "privacy": t("osłonięcie od innych"), "low_crowds": t("mało ludzi"), "quiet": t("cisza"), "low_buildings": t("mało zabudowy"), "low_traffic": t("mały ruch drogowy"), "facilities": t("udogodnienia"), "toilet": t("toaleta"), "drinking_water": t("woda pitna"), "free_cost": t("bezpłatność"), "fireplace": t("wyznaczone palenisko"), "flood_risk": t("ryzyko zalania"), "steep_ground": t("stromy teren"), "litter": t("śmieci"), "barriers": t("szlabany / ogrodzenia")};

export const state={
  // konfiguracja i dane
  config:{},
  places:[],
  photoCache:{},
  photosPaused:false,
  // widok listy
  page:0,
  shown:0,
  selected:null,
  allLibrary:true,
  collection:'new',
  undoAction:null,
  undoTimer:null,
  // mapa
  map:null,
  layer:null,
  tiles:null,
  forestLayer:null,
  mapView:false,
  highlight:null,
  // planowane trasy GPX i odległości miejsc od nich
  routes:[],
  routeLayer:null,
  routeDistance:new Map(),
  // zaznaczenie lasso na mapie (klucze miejsc)
  selection:new Set(),
  markers:new Map(),
  // odpytywanie stanu zadań
  busy:false,
  statusTimer:null,
  lastJobSignature:'',
  lastInboxSignature:'',
  // wyszukiwanie AI i kolejka profili
  searchRunning:false,
  searchResults:new Map(),
  searchCriteria:'',
  queuePaused:false,
  profileTimer:null,
  profileSignature:'',
  queuePolls:0,
};

export const providerName=s=>state.config.sources?.find(x=>x.id===s)?.name||s;
export const photoURL=url=>state.photoCache[url]||url;

// Grupy cech profilu AI do czytelnej prezentacji w karcie miejsca.
export const featureGroups=[
  [t('Krajobraz'),['panorama','mountains','elevated','forest','meadow','wild_nature','shade','sun_exposure','sunset','sunrise']],
  [t('Woda'),['waterfront','river','lake','water_access','beach']],
  [t('Teren i dojazd'),['road_access','gravel','easy_offroad','flat_ground','tent_space','moto_adjacent','difficult_terrain','mud']],
  [t('Spokój'),['privacy','quiet','low_crowds','low_buildings','low_traffic']],
  [t('Udogodnienia'),['free_cost','toilet','drinking_water','facilities','fireplace']],
  [t('Ryzyka'),['flood_risk','steep_ground','barriers','litter']],
];
// Cechy, których wysoki wynik jest niekorzystny (czerwony pasek).
export const negativeFeatures=new Set(['difficult_terrain','mud','flood_risk','steep_ground','barriers','litter']);

export const SAVED_CHOICES=['shortlist','A','B'];

// Ocena źródła i liczba komentarzy jako krótki opis pod nazwą miejsca.
export function factsLine(p){
  const parts=[];
  if(typeof p.source_rating==='number')parts.push(`★ ${p.source_rating.toFixed(1)}`);
  const comments=p.review_count??p.comments.length;
  parts.push(comments?t('{n} {word}',{n:comments,word:comments===1?t('komentarz'):comments<5?t('komentarze'):t('komentarzy')}):t('bez komentarzy'));
  if(p.photos.length)parts.push(t('{n} {word}',{n:p.photos.length,word:p.photos.length===1?t('zdjęcie'):p.photos.length<5?t('zdjęcia'):t('zdjęć')}));
  return parts.join(' · ');
}

// Flagi P4N z geo → krótkie etykiety na kaflu i w karcie.
export const geoFlagLabels=[['viewpoint',t('widok')],['p4n_baignade',t('kąpiel')],['p4n_peche',t('wędkowanie')],['p4n_eaux_vives',t('rzeka górska')],['p4n_rando',t('szlaki')],['p4n_vtt',t('MTB')],['p4n_escalade',t('wspinaczka')],['p4n_moto',t('moto')],['p4n_point_eau',t('woda pitna')],['p4n_wc_public',t('WC')],['p4n_poubelle',t('śmietnik')],['p4n_donnees_mobile',t('zasięg')],['p4n_animaux',t('zwierzęta')]];
export function geoFlags(p){return geoFlagLabels.filter(([k])=>p.geo&&p.geo[k]).map(([,label])=>label);}
