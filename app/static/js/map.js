// Mapa Leaflet: podkład OSM, warstwa BDL „Zanocuj w lesie”, podświetlanie miejsca z karty.
import {$,el,link,notify} from './dom.js';
import {state} from './state.js';
import {render} from './cards.js';
import {initLasso} from './lasso.js';

// Obszary „Zanocuj w lesie” (WMS BDL) są rysowane dopiero po przybliżeniu — z daleka to tylko szum.
export const FOREST_MIN_ZOOM=12;
export const FOREST_WMS='https://mapserver.bdl.lasy.gov.pl/arcgis/services/WMS_BDL_Mapa_turystyczna/MapServer/WMSServer';
export const FOREST_OPTIONS={layers:'0,5',format:'image/png',transparent:true,version:'1.1.1',opacity:.8,zIndex:250,minZoom:FOREST_MIN_ZOOM,maxZoom:19,attribution:'Obszary: <a href="https://www.bdl.lasy.gov.pl/portal/mapy" target="_blank" rel="noopener">BDL / Lasy Państwowe</a>'};

// Podkłady: OSM, zdjęcia satelitarne (Esri World Imagery) i satelita z cieniowaniem rzeźby terenu (wrażenie 3D).
// Wybór jest pamiętany osobno dla listy i karty miejsca (localStorage).
const OSM_ATTR='© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors';
const ESRI_ATTR='Zdjęcia: Esri, Maxar, Earthstar Geographics, GIS User Community';
export const BASEMAPS={
  osm:{label:'Mapa OSM',make:()=>L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:OSM_ATTR})},
  satellite:{label:'Satelita',make:()=>L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{maxNativeZoom:19,maxZoom:20,attribution:ESRI_ATTR})},
  relief:{label:'Satelita + rzeźba terenu (3D)',make:()=>L.layerGroup([
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',{maxNativeZoom:19,maxZoom:20,attribution:ESRI_ATTR}),
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}',{maxNativeZoom:16,maxZoom:20,opacity:.55,className:'hillshade-tiles',attribution:'Rzeźba: Esri World Hillshade'}),
  ])},
};
export function rememberedBasemap(scope,fallback){try{const v=localStorage.getItem('przeswit-basemap:'+scope);return v in BASEMAPS?v:fallback;}catch{return fallback;}}
// Dodaje przełącznik podkładów (+ opcjonalną warstwę BDL) i zwraca aktywny podkład; `onChange` dostaje klucz podkładu.
export function attachBasemaps(map,scope,fallback,overlays={},onChange){
 const layers={};for(const [key,b] of Object.entries(BASEMAPS))layers[b.label]=layers[key]=b.make();
 const bases=Object.fromEntries(Object.entries(BASEMAPS).map(([key,b])=>[b.label,layers[key]]));
 const current=rememberedBasemap(scope,fallback);layers[current].addTo(map);
 L.control.layers(bases,overlays,{position:'topright',collapsed:true}).addTo(map);
 map.on('baselayerchange',e=>{const key=Object.keys(BASEMAPS).find(k=>layers[k]===e.layer);if(!key)return;try{localStorage.setItem('przeswit-basemap:'+scope,key);}catch{}onChange?.(key,layers[key]);});
 return layers[current];
}
// Google Earth (prawdziwy widok 3D z nachyleniem) i Google Maps satelita dla dokładnego podglądu miejscówki.
export function earth3dLink(p){return `https://earth.google.com/web/@${p.lat},${p.lon},0a,600d,35y,0h,60t,0r`;}
export function googleSatelliteLink(p){return `https://www.google.com/maps/@${p.lat},${p.lon},400m/data=!3m1!1e3`;}

export function highlightPlace(p){if(!state.mapView||!state.map)return;if(state.highlight)state.highlight.remove();state.highlight=L.circleMarker([p.lat,p.lon],{radius:15,color:'#fff',weight:4,fillColor:'#ed8d32',fillOpacity:1}).addTo(state.map);state.highlight.bringToFront();const label=el('strong',p.name);state.highlight.bindTooltip(label,{permanent:true,direction:'top',offset:[0,-15],className:'highlight-label'}).openTooltip();if(!state.map.getBounds().contains([p.lat,p.lon]))state.map.panTo([p.lat,p.lon],{animate:false});}

export function clearHighlight(){if(state.highlight){state.highlight.remove();state.highlight=null;}}

function initForestLayer(){
 const shell=document.querySelector('.map-shell'),bar=el('div',undefined,'forest-toolbar'),label=el('label',undefined,'check'),toggle=el('input');toggle.type='checkbox';toggle.id='forest-overlay';toggle.checked=true;label.append(toggle,document.createTextNode('Zanocuj w lesie'));const status=el('span',`Obszary BDL od zoomu ${FOREST_MIN_ZOOM}`,'forest-status');status.id='forest-status';status.setAttribute('role','status');bar.append(label,status);shell.prepend(bar);
 const note=el('div',undefined,'forest-note');note.append(el('span','▧ Obszary programu · '),link('Źródło: Bank Danych o Lasach ↗','https://www.bdl.lasy.gov.pl/portal/mapy'),el('div','Sprawdź regulamin nadleśnictwa i aktualne zakazy. Obszar programu nie oznacza zgody na wjazd motocyklem.'));shell.append(note);
 // Both official scale-dependent representations, names verified in GetCapabilities.
 state.forestLayer=L.tileLayer.wms(FOREST_WMS,FOREST_OPTIONS);
 let failed=false;state.forestLayer.on('loading',()=>{failed=false;status.textContent='Wczytuję obszary BDL…';});state.forestLayer.on('tileerror',()=>{failed=true;status.textContent='BDL niedostępne — granice mogą być niepełne';});state.forestLayer.on('load',()=>{if(!failed)status.textContent='Obszary BDL · warstwa online';});toggle.onchange=()=>{if(toggle.checked&&state.mapView)state.forestLayer.addTo(state.map);else state.forestLayer.remove();status.textContent=toggle.checked?`Obszary BDL od zoomu ${FOREST_MIN_ZOOM}`:'Warstwa wyłączona';};
}

export function initMap(){if(!window.L){notify('Mapa niedostępna. Tabela nadal działa.',true);return;}state.map=L.map('map',{preferCanvas:true}).setView([50.9247,16.2726],9);state.layer=L.layerGroup().addTo(state.map);initForestLayer();state.tiles=attachBasemaps(state.map,'list','osm',{'Zanocuj w lesie (BDL)':state.forestLayer},(key,layer)=>{state.tiles=layer;});if(!$('tiles').checked)state.tiles.remove();state.map.on('moveend',()=>{if($('only-map').checked){state.page=0;render(false);}});initLasso();}
