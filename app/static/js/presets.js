// Presety filtrów (wbudowane + własne w localStorage), skróty klawiszowe, motyw ciemny, rejestracja PWA.
import {$,el,notify} from './dom.js';
import {state} from './state.js';
import {render,choose} from './cards.js';
import {showDetail} from './detail.js';

const PRESET_KEY='przeswit-presets';
const FIELDS=['search','source-filter','type-filter','photos-only','ai-only','only-map','route-only','route-range'];
const BUILTIN={
 'Weekend przy trasie':{'photos-only':true,'route-only':true,'route-range':'3'},
 'Widoki i woda':{'photos-only':true,'type-filter':'water'},
 'Punkty widokowe':{'photos-only':true,'type-filter':'viewpoint'},
 'Tylko wyniki AI':{'ai-only':true},
 'Wszystko':{'photos-only':false,'type-filter':'','source-filter':'','search':'','route-only':false,'ai-only':false},
};

function snapshot(){const s={};for(const id of FIELDS){const n=$(id);if(!n)continue;s[id]=n.type==='checkbox'?n.checked:n.value;}return s;}
function apply(s){for(const [id,v] of Object.entries(s)){const n=$(id);if(!n)continue;if(n.type==='checkbox')n.checked=!!v;else n.value=v;}state.page=0;render();document.dispatchEvent(new Event('przeswit:filters'));}
function custom(){try{return JSON.parse(localStorage.getItem(PRESET_KEY)||'{}');}catch{return {};}}
function saveCustom(all){try{localStorage.setItem(PRESET_KEY,JSON.stringify(all));}catch{}}

export function initPresets(){
 const bar=document.querySelector('.filterbar');if(!bar)return;
 const sel=el('select');sel.id='preset';sel.setAttribute('aria-label','Preset filtrów');
 const save=el('button','Zapisz preset','ghost');save.title='Zapisz bieżące filtry jako własny preset';
 const del=el('button','✕','ghost');del.title='Usuń wybrany własny preset';del.hidden=true;
 const nameBox=el('span',undefined,'preset-name');nameBox.hidden=true;const nameInput=el('input');nameInput.type='text';nameInput.placeholder='nazwa presetu';nameInput.maxLength=40;const ok=el('button','OK');nameBox.append(nameInput,ok);
 function fill(){const cur=custom();sel.replaceChildren(new Option('Presety…',''));for(const n of Object.keys(BUILTIN))sel.append(new Option(n,'b:'+n));for(const n of Object.keys(cur))sel.append(new Option(n+' (własny)','c:'+n));}
 sel.onchange=()=>{const v=sel.value;del.hidden=!v.startsWith('c:');if(!v)return;const s=v.startsWith('b:')?BUILTIN[v.slice(2)]:custom()[v.slice(2)];if(s){apply(s);notify(`Preset: ${v.slice(2)}`);}};
 save.onclick=()=>{nameBox.hidden=false;nameInput.focus();};
 ok.onclick=()=>{const n=nameInput.value.trim();if(!n)return;const all=custom();all[n]=snapshot();saveCustom(all);fill();sel.value='c:'+n;del.hidden=false;nameBox.hidden=true;nameInput.value='';notify(`Zapisano preset „${n}”.`);};
 nameInput.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();ok.click();}if(e.key==='Escape')nameBox.hidden=true;};
 del.onclick=()=>{const v=sel.value;if(!v.startsWith('c:'))return;const all=custom();delete all[v.slice(2)];saveCustom(all);fill();del.hidden=true;};
 fill();bar.append(sel,save,del,nameBox);
}

// Skróty: J/K następny/poprzedni kafel, S zachowaj, X odrzuć, Enter karta, M mapa, / szukaj, ? pomoc.
let current=-1;
function cards(){return [...document.querySelectorAll('#cards .place-card')];}
function focusCard(i){const list=cards();if(!list.length)return;current=Math.max(0,Math.min(list.length-1,i));list.forEach((c,k)=>c.classList.toggle('kbd-current',k===current));list[current].scrollIntoView({block:'center',behavior:'smooth'});}
function currentPlace(){const c=cards()[current];return c?state.places.find(p=>p.key===c.dataset.key):null;}
export function initShortcuts(){
 document.addEventListener('keydown',e=>{
  const tag=(e.target.tagName||'').toLowerCase();
  if(tag==='input'||tag==='textarea'||tag==='select'||e.ctrlKey||e.metaKey||e.altKey)return;
  if(document.querySelector('dialog[open]')&&e.key!=='Escape')return;
  const p=currentPlace();
  switch(e.key){
   case 'j':case 'ArrowDown':focusCard(current+1);e.preventDefault();break;
   case 'k':case 'ArrowUp':focusCard(current-1);e.preventDefault();break;
   case 's':if(p&&!state.config.read_only)choose(p,['shortlist','A','B'].includes(p.choice)?'':'shortlist');break;
   case 'x':if(p&&!state.config.read_only)choose(p,p.choice==='rejected'?'':'rejected');break;
   case 'Enter':if(p)showDetail(p.key);break;
   case 'm':$('toggle-map').click();break;
   case '/':$('search').focus();e.preventDefault();break;
   case 'd':toggleTheme();break;
   case '?':notify('Skróty: J/K kafle · S zachowaj · X odrzuć · Enter karta · M mapa · / szukaj · D motyw');break;
  }
 });
 document.addEventListener('przeswit:filters',()=>{current=-1;});
}

// Motyw ciemny: zapamiętany w localStorage, domyślnie wg systemu.
const THEME_KEY='przeswit-theme';
export function applyTheme(){let t=null;try{t=localStorage.getItem(THEME_KEY);}catch{}if(!t)t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';document.documentElement.dataset.theme=t;const b=$('theme-toggle');if(b)b.textContent=t==='dark'?'☀':'☾';}
export function toggleTheme(){const t=document.documentElement.dataset.theme==='dark'?'light':'dark';try{localStorage.setItem(THEME_KEY,t);}catch{}applyTheme();}
export function initTheme(){const b=el('button','☾','ghost');b.id='theme-toggle';b.title='Motyw jasny/ciemny (D)';b.onclick=toggleTheme;document.querySelector('.header-right')?.prepend(b);applyTheme();}

export function registerPWA(){if('serviceWorker' in navigator&&location.protocol==='https:')navigator.serviceWorker.register('/sw.js').catch(()=>{});}
