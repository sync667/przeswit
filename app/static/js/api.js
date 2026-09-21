// Komunikacja z lokalnym backendem. POST wymaga tokenu sesji z /api/config.
import {state} from './state.js';
import {t} from './i18n.js';

export async function api(path,body){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-ADV-Token':state.config.token},body:JSON.stringify(body)});
  const out=await r.json();
  if(!r.ok)throw Error(out.error||t('Nie udało się wykonać operacji.'));
  return out;
}

export async function getJSON(path){
  const r=await fetch(path);
  const out=await r.json();
  if(!r.ok)throw Error(out.error||t('Nie udało się pobrać danych.'));
  return out;
}
