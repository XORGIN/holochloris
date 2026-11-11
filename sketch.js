/* HOLOCHLORIS — PROJECTION P5
 * C1 gauche : 450/550/680 nm en boucle (1.2s par image), mises à jour atomiques.
 * C2 droite : dernière vidéo h264 MP4 de ComfyUI en boucle, rechargée si un nouveau MP4 est prêt.
 * BioCLIP bas : emplacement réservé, aucune donnée latente inventée.
 * F plein écran / I diagnostic / ESPACE titres.
 */
let bands=[], bandVersion=null, bandRequest=null, bandStarted=0;
let video=null, videoVersion=null, pendingVideo=null;
let status={c1:{ready:false}, c2:{ready:false}};
let showLabels=true, diagnostics=false, refreshing=false;
let biome='boreal';
const BIOME_C1={
  tropical:{order:[550,450,680],interval:850},
  desert:{order:[680,550,450],interval:1800},
  boreal:{order:[450,550,680],interval:1200},
  taiga:{order:[550,680,450],interval:1600},
  tundra:{order:[450,680,550],interval:2200}
};
const BAND_LABELS=['450 nm','550 nm','680 nm'];
const BAND_INTERVAL=1200;
const REF_W=1600, REF_H=900;

function setup(){
  const c=createCanvas(windowWidth,windowHeight);
  c.parent('stage');
  pixelDensity(Math.min(2, window.devicePixelRatio||1));
  textFont('Courier New');
  textAlign(CENTER,CENTER);
  poll(); setInterval(poll,2000);
}
function windowResized(){resizeCanvas(windowWidth,windowHeight)}
function keyPressed(){
  if(key==='f'||key==='F')fullscreen(!fullscreen());
  if(key==='i'||key==='I'){ diagnostics=!diagnostics;document.getElementById('status').style.display=diagnostics?'block':'none';document.getElementById('help').style.display=diagnostics?'block':'none';}
  if(key===' '){showLabels=!showLabels;return false;}
}
async function poll(){
  if(refreshing)return;
  refreshing=true;
  try{
    const response=await fetch('/api/status?time='+Date.now(),{cache:'no-store'});
    if(!response.ok)throw Error('API indisponible');
    status=await response.json();
    if(status.biome && BIOME_C1[status.biome.biome]) biome=status.biome.biome;
    document.getElementById('status').textContent=`C1 : ${status.c1.ready?'série '+status.c1.version:'en attente'} | C2 : ${status.c2.ready?status.c2.filename:'en attente'} | BioCLIP : réservé`;
    if(status.c1.ready && status.c1.version!==bandVersion && status.c1.version!==bandRequest){loadBands(status.c1.version)}
    if(status.c2.ready && status.c2.version!==videoVersion && status.c2.version!==pendingVideo){loadVideo(status.c2.version)}
  } catch(err){document.getElementById('status').textContent='Serveur déconnecté : '+err.message;}
  finally{refreshing=false;}
}
async function loadBands(version){
  bandRequest=version;
  try{
    const response=await fetch('/api/c1/sequence?time='+Date.now(),{cache:'no-store'});
    if(!response.ok)throw Error('Série C1 absente');
    const data=await response.json();
    if(data.version!==version || !Array.isArray(data.frames) || data.frames.length!==3)throw Error('Série C1 remplacée');
    const images=await Promise.all(data.frames.map(src=>new Promise((resolve,reject)=>loadImage(src,resolve,reject))));
    if(bandRequest!==version)return;
    bands=images; bandVersion=version; bandStarted=millis();
  }catch(err){console.warn('MST++',err)}
  finally{if(bandRequest===version)bandRequest=null}
}
function loadVideo(version){
  pendingVideo=version;
  const el=document.createElement('video');
  el.muted=true;el.defaultMuted=true;el.loop=true;el.autoplay=true;
  el.playsInline=true;el.preload='auto';el.crossOrigin='anonymous';
  el.style.display='none';
  el.src='/api/c2/video?v='+encodeURIComponent(version);
  document.body.appendChild(el);
  function cleanup(){el.pause();el.removeAttribute('src');el.load();el.remove()}
  el.addEventListener('loadeddata',()=>{
    if(pendingVideo!==version){cleanup();return;}
    const previous=video;
    video=el;videoVersion=version;pendingVideo=null;
    const play=el.play();if(play&&play.catch)play.catch(e=>console.warn('Vidéo :',e));
    if(previous){previous.pause();previous.removeAttribute('src');previous.load();previous.remove()}
  },{once:true});
  el.addEventListener('error',()=>{
    console.warn('Impossible de lire le MP4 C2',el.error);
    if(pendingVideo===version)pendingVideo=null;
    cleanup();
  },{once:true});
  el.load();
}
function draw(){
  background(0);
  const s=Math.min(width/REF_W,height/REF_H);
  push();translate((width-REF_W*s)*0.5,(height-REF_H*s)*0.5);scale(s);
  // Wide top strip containing two lenses, lower third intentionally reserved for BioCLIP.
  const leftX=410,rightX=1190,y=232,d=385;
  const setting=BIOME_C1[biome]||BIOME_C1.boreal;
  const idx=bands.length===3?Math.floor((millis()-bandStarted)/setting.interval)%3:0;
  const bandIdx=setting.order[idx];
  const bandPos=BAND_LABELS.findIndex(label=>label===bandIdx+' nm');
  drawCircleSource(leftX,y,d,bands.length===3?bands[bandPos]:null);
  drawCircleVideo(rightX,y,d,video);
  if(showLabels){
    // Echelle nominale : le diamètre utile de chaque rond représente 5 mm.
    // Validité physique à confirmer avec une lame micrométrique.
    drawScaleBar(leftX,449,d,5);
    drawScaleBar(rightX,449,d,5);
    noStroke();fill(219,225,227);textFont("Courier New");textSize(21);textStyle(NORMAL);
    text('PERCEPTION SPECTRALE',leftX,511);
    text('PERCEPTION SPÉCULATIVE',rightX,511);
    fill(150,160,164);textSize(13);
    if(bands.length===3)text(BAND_LABELS[bandPos]+'  /  CHAMP 5 × 5 mm*',leftX,540);
    else text('CHAMP 5 × 5 mm*',leftX,540);
    text('ÉCHELLE DE LA SOURCE*',rightX,540);
  }
  // La carte externe occupe la partie basse via un iframe DOM (port 8766).
  noStroke();fill(90,96,101);textSize(11);
  text('* ÉCHELLE NOMINALE — CALIBRATION MICROSCOPIQUE REQUISE',800,567);
  pop();
}
function emptyDisc(cx,cy,d,message){
  noStroke();fill(9,12,15);circle(cx,cy,d);
  noFill();stroke(37,44,49);strokeWeight(1);circle(cx,cy,d-4);
  noStroke();fill(114,129,138);textSize(16);text(message,cx,cy);
}
function drawCircleSource(cx,cy,d,img){
  if(!img){emptyDisc(cx,cy,d,'EN ATTENTE DE MST++');return;}
  const ctx=drawingContext;ctx.save();ctx.beginPath();ctx.arc(cx,cy,d/2,0,Math.PI*2);ctx.clip();
  const a=Math.max(d/img.width,d/img.height);
  image(img,cx-img.width*a/2,cy-img.height*a/2,img.width*a,img.height*a);
  ctx.restore();
}
function drawCircleVideo(cx,cy,d,el){
  if(!el || el.readyState<2 || !el.videoWidth){emptyDisc(cx,cy,d,'EN ATTENTE DE COMFYUI');return;}
  const ctx=drawingContext;ctx.save();ctx.beginPath();ctx.arc(cx,cy,d/2,0,Math.PI*2);ctx.clip();
  const a=Math.max(d/el.videoWidth,d/el.videoHeight);
  ctx.drawImage(el,cx-el.videoWidth*a/2,cy-el.videoHeight*a/2,el.videoWidth*a,el.videoHeight*a);
  ctx.restore();
}

// Regle de 5 mm (graduations tous les 1 mm).
// Le champ de 5 mm doit etre confirme avec une lame micrometrique.
// La regle de C2 indique l'echelle nominale de l'image source, PAS une mesure
// scientifique des elements generes ou deformes par IA.
function drawScaleBar(cx, y, diameter, fieldMm=5){
  const totalMm=5;
  const pxPerMm=diameter/fieldMm;
  const length=pxPerMm*totalMm;
  const x0=cx-length/2;
  push();
  textFont('Courier New');
  textStyle(NORMAL);
  stroke(218,224,226);
  strokeWeight(1.5);
  line(x0,y,x0+length,y);
  for(let i=0;i<=totalMm;i++){
    const tickX=x0+i*pxPerMm;
    const major=i===0||i===totalMm;
    line(tickX,y-(major?10:6),tickX,y+(major?10:6));
  }
  noStroke();
  fill(200,210,213);
  textSize(13);
  textAlign(CENTER,CENTER);
  for(let i=0;i<=totalMm;i++){
    text(String(i),x0+i*pxPerMm,y+23);
  }
  textSize(12);
  text('5 mm — champ nominal',cx,y-27);
  pop();
}
