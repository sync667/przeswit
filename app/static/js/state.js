// Wspólny stan aplikacji i stałe. Moduły modyfikują pola `state`, nie kopiują ich.
export const PAGE=24;

export const labels={camp_site:'Biwak / kemping',camp_pitch:'Stanowisko namiotowe',caravan_site:'Miejsce dla kamperów',viewpoint:'Punkt widokowy',picnic_site:'Piknik',beach:'Plaża',water_access:'Punkt wodowania',parking:'Parking',wilderness_hut:'Schron terenowy',import:'Punkt z importu'};

export const featureLabels={"panorama": "rozległa panorama", "mountains": "widok gór", "elevated": "położenie wysoko / zbocze", "forest": "las", "meadow": "łąka / polana", "wild_nature": "naturalne otoczenie", "river": "rzeka lub potok", "lake": "jezioro", "waterfront": "bezpośrednio przy wodzie", "water_access": "możliwość dojścia do wody", "beach": "plaża", "shade": "cień", "sun_exposure": "nasłonecznienie", "sunset": "potwierdzony widok zachodu", "sunrise": "potwierdzony widok wschodu", "flat_ground": "płaski teren", "tent_space": "miejsce fizyczne na namiot", "moto_adjacent": "miejsce na motocykl obok namiotu", "road_access": "dowody fizycznego dojazdu", "gravel": "szuter", "easy_offroad": "lekki teren", "difficult_terrain": "trudny teren", "mud": "błoto / grząski grunt", "privacy": "osłonięcie od innych", "low_crowds": "mało ludzi", "quiet": "cisza", "low_buildings": "mało zabudowy", "low_traffic": "mały ruch drogowy", "facilities": "udogodnienia", "toilet": "toaleta", "drinking_water": "woda pitna", "free_cost": "bezpłatność", "fireplace": "wyznaczone palenisko", "flood_risk": "ryzyko zalania", "steep_ground": "stromy teren", "litter": "śmieci", "barriers": "szlabany / ogrodzenia"};

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
  ['Krajobraz',['panorama','mountains','elevated','forest','meadow','wild_nature','shade','sun_exposure','sunset','sunrise']],
  ['Woda',['waterfront','river','lake','water_access','beach']],
  ['Teren i dojazd',['road_access','gravel','easy_offroad','flat_ground','tent_space','moto_adjacent','difficult_terrain','mud']],
  ['Spokój',['privacy','quiet','low_crowds','low_buildings','low_traffic']],
  ['Udogodnienia',['free_cost','toilet','drinking_water','facilities','fireplace']],
  ['Ryzyka',['flood_risk','steep_ground','barriers','litter']],
];
// Cechy, których wysoki wynik jest niekorzystny (czerwony pasek).
export const negativeFeatures=new Set(['difficult_terrain','mud','flood_risk','steep_ground','barriers','litter']);

export const SAVED_CHOICES=['shortlist','A','B'];

// Ocena źródła i liczba komentarzy jako krótki opis pod nazwą miejsca.
export function factsLine(p){
  const parts=[];
  if(typeof p.source_rating==='number')parts.push(`★ ${p.source_rating.toFixed(1)}`);
  const comments=p.review_count??p.comments.length;
  parts.push(comments?`${comments} ${comments===1?'komentarz':comments<5?'komentarze':'komentarzy'}`:'bez komentarzy');
  if(p.photos.length)parts.push(`${p.photos.length} ${p.photos.length===1?'zdjęcie':p.photos.length<5?'zdjęcia':'zdjęć'}`);
  return parts.join(' · ');
}

// Flagi P4N z geo → krótkie etykiety na kaflu i w karcie.
export const geoFlagLabels=[['viewpoint','widok'],['p4n_baignade','kąpiel'],['p4n_peche','wędkowanie'],['p4n_eaux_vives','rzeka górska'],['p4n_rando','szlaki'],['p4n_vtt','MTB'],['p4n_escalade','wspinaczka'],['p4n_moto','moto'],['p4n_point_eau','woda pitna'],['p4n_wc_public','WC'],['p4n_poubelle','śmietnik'],['p4n_donnees_mobile','zasięg'],['p4n_animaux','zwierzęta']];
export function geoFlags(p){return geoFlagLabels.filter(([k])=>p.geo&&p.geo[k]).map(([,label])=>label);}
