// Drobne pomocniki DOM i formatowania używane przez pozostałe moduły.
export const $=id=>document.getElementById(id);
export const el=(tag,text,cls)=>{const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x;};

export function notify(message,error=false){$('notice').textContent=message;$('notice').classList.toggle('error',error);}

export function safeURL(url){try{const u=new URL(url);return u.protocol==='https:'&&!u.username&&!u.password;}catch{return false;}}

export function link(text,url){const a=el('a',text);if(safeURL(url)){a.href=url;a.target='_blank';a.rel='noopener noreferrer';}return a;}

export function googleMapLink(p){const a=link('Google Maps ↗',`https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(p.lat+','+p.lon)}`);a.className='google-map-link';a.setAttribute('aria-label','Otwórz '+p.name+' w Google Maps w nowej karcie');return a;}

export function download(text,type,name){const a=el('a');a.href=URL.createObjectURL(new Blob([text],{type}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}

export function csvCell(v){let s=String(v??'');if(/^\s*[=+@-]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';}

// Odległość w metrach między dwoma punktami (haversine).
export function distance(a,b){const rad=x=>x*Math.PI/180;const y=Math.sin(rad(b.lat-a.lat)/2)**2+Math.cos(rad(a.lat))*Math.cos(rad(b.lat))*Math.sin(rad(b.lon-a.lon)/2)**2;return 6371000*2*Math.asin(Math.min(1,Math.sqrt(y)));}
