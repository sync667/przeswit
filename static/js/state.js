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
  selected:null,
  allLibrary:true,
  collection:'new',
  undoAction:null,
  // mapa
  map:null,
  layer:null,
  tiles:null,
  forestLayer:null,
  mapView:false,
  highlight:null,
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
