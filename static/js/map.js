// Mapa Leaflet: podkład OSM, warstwa BDL „Zanocuj w lesie”, podświetlanie miejsca z karty.
import {$,el,link,notify} from './dom.js';
import {state} from './state.js';
import {render} from './cards.js';

export function highlightPlace(p){if(!state.mapView||!state.map)return;if(state.highlight)state.highlight.remove();state.highlight=L.circleMarker([p.lat,p.lon],{radius:15,color:'#fff',weight:4,fillColor:'#ed8d32',fillOpacity:1}).addTo(state.map);state.highlight.bringToFront();const label=el('strong',p.name);state.highlight.bindTooltip(label,{permanent:true,direction:'top',offset:[0,-15],className:'highlight-label'}).openTooltip();if(!state.map.getBounds().contains([p.lat,p.lon]))state.map.panTo([p.lat,p.lon],{animate:false});}

export function clearHighlight(){if(state.highlight){state.highlight.remove();state.highlight=null;}}

function initForestLayer(){
 const shell=document.querySelector('.map-shell'),bar=el('div',undefined,'forest-toolbar'),label=el('label',undefined,'check'),toggle=el('input');toggle.type='checkbox';toggle.id='forest-overlay';toggle.checked=true;label.append(toggle,document.createTextNode('Zanocuj w lesie'));const status=el('span','Warstwa BDL · online','forest-status');status.id='forest-status';status.setAttribute('role','status');bar.append(label,status);shell.prepend(bar);
 const note=el('div',undefined,'forest-note');note.append(el('span','▧ Obszary programu · '),link('Źródło: Bank Danych o Lasach ↗','https://www.bdl.lasy.gov.pl/portal/mapy'),el('div','Sprawdź regulamin nadleśnictwa i aktualne zakazy. Obszar programu nie oznacza zgody na wjazd motocyklem.'));shell.append(note);
 // Both official scale-dependent representations, names verified in GetCapabilities.
 state.forestLayer=L.tileLayer.wms('https://mapserver.bdl.lasy.gov.pl/arcgis/services/WMS_BDL_Mapa_turystyczna/MapServer/WMSServer',{layers:'0,5',format:'image/png',transparent:true,version:'1.1.1',opacity:.8,zIndex:250,maxZoom:19,attribution:'Obszary: <a href="https://www.bdl.lasy.gov.pl/portal/mapy" target="_blank" rel="noopener">BDL / Lasy Państwowe</a>'});
 let failed=false;state.forestLayer.on('loading',()=>{failed=false;status.textContent='Wczytuję obszary BDL…';});state.forestLayer.on('tileerror',()=>{failed=true;status.textContent='BDL niedostępne — granice mogą być niepełne';});state.forestLayer.on('load',()=>{if(!failed)status.textContent='Obszary BDL · warstwa online';});toggle.onchange=()=>{if(toggle.checked&&state.mapView)state.forestLayer.addTo(state.map);else state.forestLayer.remove();status.textContent=toggle.checked?'Obszary BDL · warstwa online':'Warstwa wyłączona';};
}

export function initMap(){if(!window.L){notify('Mapa niedostępna. Tabela nadal działa.',true);return;}state.map=L.map('map',{preferCanvas:true}).setView([50.9247,16.2726],9);state.layer=L.layerGroup().addTo(state.map);initForestLayer();state.tiles=L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'});if($('tiles').checked)state.tiles.addTo(state.map);state.map.on('moveend',()=>{if($('only-map').checked){state.page=0;render(false);}});}
