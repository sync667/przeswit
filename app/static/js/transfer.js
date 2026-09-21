// Import pliku z dysku oraz eksport widocznych rekordów do JSON / CSV / GPX.
import {$,notify,download,csvCell,safeURL} from './dom.js';
import {api} from './api.js';
import {loadLibrary,filtered,currentMatch} from './library.js';

const MAX_UPLOAD_BYTES=20_000_000;

function readAsBase64(file){return new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(',')[1]);r.onerror=()=>reject(Error('Błąd odczytu pliku.'));r.readAsDataURL(file);});}

export async function importFile(e){const f=e.target.files[0];if(!f)return;try{if(f.size>MAX_UPLOAD_BYTES)throw Error('Plik przekracza 20 MB.');const data=await readAsBase64(f);const result=await api('/api/import',{name:f.name,content:data,source:$('file-source').value});await loadLibrary();notify(`Import: ${result.imported} rekordów, ${result.saved} zapisanych/odświeżonych. Zachowano notatki.`);}catch(err){notify(err.message,true);}finally{e.target.value='';}}

export function exportJSON(){download(JSON.stringify({label:'Prześwit · osobisty eksport wybranych rekordów',exported_at:new Date().toISOString(),scope:'visible_filters',spots:filtered()},null,2),'application/json','przeswit-miejsca.json');}

export function exportCSV(){const rows=[['name','latitude','longitude','source','url','type','match','criteria','ADV','scenic','water','solitude','legal_confidence','choice','note','license','fetched_at','flags'],...filtered().map(p=>[p.name,p.lat,p.lon,p.source,p.source_url||p.p4n_url,p.type,currentMatch(p)?.match,$('wish').value.trim(),p.scores.adv_access,p.scores.scenic,p.scores.water,p.scores.solitude,p.legal_confidence,p.choice,p.user_note,p.license,p.fetched_at,p.red_flags.join(' | ')])];download('\uFEFF'+rows.map(r=>r.map(csvCell).join(';')).join('\r\n'),'text/csv;charset=utf-8','przeswit-miejsca.csv');}

export function exportGPX(){const doc=document.implementation.createDocument('http://www.topografix.com/GPX/1/1','gpx');const root=doc.documentElement;root.setAttribute('version','1.1');root.setAttribute('creator','Prześwit Local');for(const p of filtered()){const n=doc.createElementNS(root.namespaceURI,'wpt');n.setAttribute('lat',p.lat);n.setAttribute('lon',p.lon);for(const [tag,text] of [['name',p.name],['desc',[p.description,p.user_note,p.license].filter(Boolean).join('\n')]]){const e=doc.createElementNS(root.namespaceURI,tag);e.textContent=text;n.append(e);}if(safeURL(p.source_url)){const a=doc.createElementNS(root.namespaceURI,'link');a.setAttribute('href',p.source_url);n.append(a);}root.append(n);}download('<?xml version="1.0" encoding="UTF-8"?>\n'+new XMLSerializer().serializeToString(doc),'application/gpx+xml','przeswit-miejsca.gpx');}
