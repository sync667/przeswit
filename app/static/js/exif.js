// Minimalny odczyt współrzędnych GPS z EXIF (JPEG): APP1 → TIFF → IFD0 → GPS IFD (tagi 1–4). Bez bibliotek.
export async function exifCoordinates(file){
 if(!/image\/jpe?g/i.test(file.type)&&!/\.jpe?g$/i.test(file.name))return null;
 const buf=await file.slice(0,262144).arrayBuffer();const v=new DataView(buf);
 if(v.byteLength<4||v.getUint16(0)!==0xFFD8)return null;
 let off=2;
 while(off+4<=v.byteLength){
  const marker=v.getUint16(off);if(marker===0xFFDA)break;const size=v.getUint16(off+2);
  if(marker===0xFFE1&&off+10<=v.byteLength&&v.getUint32(off+4)===0x45786966){const tiff=off+10;return readTiff(v,tiff);}
  off+=2+size;
 }
 return null;
}

function readTiff(v,tiff){
 if(tiff+8>v.byteLength)return null;
 const le=v.getUint16(tiff)===0x4949;const u16=o=>v.getUint16(o,le),u32=o=>v.getUint32(o,le);
 if(u16(tiff+2)!==42)return null;
 const ifd0=tiff+u32(tiff+4);let gpsIfd=null;
 const entries=u16(ifd0);
 for(let i=0;i<entries;i++){const e=ifd0+2+i*12;if(e+12>v.byteLength)return null;if(u16(e)===0x8825){gpsIfd=tiff+u32(e+8);break;}}
 if(!gpsIfd||gpsIfd+2>v.byteLength)return null;
 const tags={};const n=u16(gpsIfd);
 for(let i=0;i<n;i++){const e=gpsIfd+2+i*12;if(e+12>v.byteLength)break;const tag=u16(e),type=u16(e+2),count=u32(e+4);
  if(type===2&&count<=4){tags[tag]=String.fromCharCode(v.getUint8(e+8));}
  else if(type===5&&count===3){const p=tiff+u32(e+8);if(p+24>v.byteLength)continue;const r=[];for(let k=0;k<3;k++){const num=u32(p+k*8),den=u32(p+k*8+4);r.push(den?num/den:0);}tags[tag]=r;}}
 const lat=tags[2],lon=tags[4];if(!lat||!lon)return null;
 const toDeg=a=>a[0]+a[1]/60+a[2]/3600;
 let la=toDeg(lat),lo=toDeg(lon);if((tags[1]||'N')==='S')la=-la;if((tags[3]||'E')==='W')lo=-lo;
 if(!Number.isFinite(la)||!Number.isFinite(lo)||(la===0&&lo===0))return null;
 return {lat:la,lon:lo};
}
