// Configure API_URL to your dedicated Arena Worker endpoint after deployment.
const API_URL=globalThis.ARENA_API_URL||'';
if(!API_URL||API_URL.includes('YOUR-SUBDOMAIN')){document.addEventListener('DOMContentLoaded',()=>{document.querySelector('#challenges').textContent='Arena en attente de configuration Cloudflare (arena/config.js).';});}
const token=()=>sessionStorage.getItem('arena_session')||'';
const el=id=>document.getElementById(id);
const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const publicMemo=new Map();
async function api(path,options={}){
 if(!options.method&&['/api/arena/challenges','/api/arena/leaderboard','/api/arena/rankings','/api/arena/rewards'].includes(path)){const item=publicMemo.get(path);if(item&&Date.now()-item.at<30000)return item.data;}
 const method=(options.method||'GET').toUpperCase();
 const headers={...(method==='GET'?{}:{'content-type':'application/json'}),...(method==='GET'?{}:token()?{authorization:'Bearer '+token()}:{})};
 if(method!=='GET')publicMemo.clear();
 const response=await fetch(API_URL+path,{...options,headers:{...headers,...(options.headers||{})}});
 const data=await response.json();if(!response.ok){if(response.status===500)throw Error('Service temporairement indisponible (quota Cloudflare possible).');throw Error(data.error||'Erreur');}if(method==='GET'&&['/api/arena/challenges','/api/arena/leaderboard','/api/arena/rankings','/api/arena/rewards'].includes(path))publicMemo.set(path,{at:Date.now(),data});return data;
}
const rarityFor=name=>{const n=String(name||'');if(/Gamma/i.test(n))return 'rare';if(/Epsilon|Zêta/i.test(n))return 'epique';return 'commune';};
const rarityLabels={commune:'COMMUNE',rare:'RARE',epique:'ÉPIQUE',legendaire:'LÉGENDAIRE'};
const cardMarkup=(name,{unlocked=false,rarity}={})=>{
 const r=['commune','rare','epique','legendaire'].includes(rarity)?rarity:rarityFor(name);
 const label=rarityLabels[r];
 return `<article class="player-card rarity-${r} ${unlocked?'is-unlocked':'is-preview'}" aria-label="Carte ${safe(name)} ${label}">
  <div class="player-card-head"><span>🎾 TENNIS EDGE</span><span class="rarity-pill">${label}</span></div>
  <div class="player-card-art" aria-hidden="true"><svg viewBox="0 0 240 190" xmlns="http://www.w3.org/2000/svg" role="img"><defs><linearGradient id="court-${r}" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#183e53"/><stop offset="1" stop-color="#092033"/></linearGradient></defs><rect x="9" y="9" width="222" height="172" rx="15" fill="url(#court-${r})"/><path d="M22 55h196M22 140h196M120 22v145" stroke="#a7f6cc" stroke-width="2" opacity=".35"/><circle cx="120" cy="88" r="57" fill="#a9f36b" opacity=".12"/><path d="M91 65c0-18 14-32 31-32s31 14 31 32-14 30-31 30-31-12-31-30ZM62 160c3-34 23-54 60-54s57 20 60 54" fill="#d8f4ff" opacity=".9"/><circle cx="185" cy="53" r="19" fill="#c4f96e"/><path d="M171 40c16 7 21 19 24 26M197 41c-17 6-23 17-25 26" fill="none" stroke="#fff" stroke-width="2"/></svg></div>
  <div class="player-card-footer"><strong>${safe(name)}</strong><span>${unlocked?'✓ DÉBLOQUÉE':'APERÇU · À GAGNER'}</span></div></article>`;
};
async function load(){for(const [path,id,draw] of [['/api/arena/challenges','challenges',d=>{el('challenges').innerHTML=d.challenges.map(c=>`<article class="card"><h3>${safe(c.title)}</h3><p>${safe(c.player_a)} ⚔️ ${safe(c.player_b)}</p><small>Fermeture : ${safe(c.closes_at)}</small><p><button data-id="${safe(c.id)}" data-pick="a">${safe(c.player_a)}</button> <button data-id="${safe(c.id)}" data-pick="b">${safe(c.player_b)}</button></p></article>`).join('')||'Aucun défi ouvert.';el('cards').innerHTML=d.challenges.flatMap(c=>[c.player_a,c.player_b]).filter((v,i,a)=>a.indexOf(v)===i).map(n=>cardMarkup(n)).join('')||'Aucune carte à découvrir pour le moment.';}],['/api/arena/leaderboard','leaders',d=>{el('leaders').innerHTML=d.leaders.map((u,i)=>`<p>${i+1}. ${safe(u.display_name)} — ${Number(u.xp)} XP</p>`).join('')||'Pas encore de participants.';}],['/api/arena/rewards','rewards',d=>{el('rewards').innerHTML=d.rewards.map(r=>`<div class="card"><h3>${safe(r.title)}</h3><p>${Number(r.cost)} points · Stock ${Number(r.stock)}</p><button data-reward="${safe(r.id)}">Échanger</button></div>`).join('')||'Boutique en préparation.';}]]){try{draw(await api(path));}catch(e){el(id).textContent='Données indisponibles : '+e.message;}}}
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;try{if(b.dataset.id){await api('/api/arena/predict',{method:'POST',body:JSON.stringify({challenge_id:b.dataset.id,pick:b.dataset.pick})});alert('Prédiction enregistrée !');}else if(b.dataset.reward){await api('/api/arena/redeem',{method:'POST',body:JSON.stringify({reward_id:b.dataset.reward})});alert('Récompense réservée !');load();}}catch(err){alert(err.message);}});
el('join').addEventListener('click',async()=>{try{await api('/api/arena/join',{method:'POST',body:JSON.stringify({display_name:el('name').value})});el('me').textContent='Inscription confirmée';await refreshMyCollection();}catch(e){el('me').textContent=e.message;}});load();

document.getElementById('test-login').addEventListener('click',async()=>{const field=document.getElementById('test-key'),state=document.getElementById('test-state');try{const result=await api('/api/arena/test-login',{method:'POST',body:JSON.stringify({access_key:field.value})});sessionStorage.setItem('arena_session',result.token);field.value='';state.textContent='Mode test activé pour une heure';await refreshMyCollection();await load();}catch(e){state.textContent=e.message;}});

const demoNames=[['arena-demo-1','Joueur Alpha','Joueur Bêta'],['arena-demo-2','Joueur Gamma','Joueur Delta'],['arena-demo-3','Joueur Epsilon','Joueur Zêta']];
// Collection privée : indépendante du chargement des défis publics.
let collectionRequest=0;
async function refreshMyCollection(){
 const request=++collectionRequest;
 const album=el('my-cards');
 if(!token()){
  album.textContent='Active le mode test privé pour consulter tes cartes débloquées.';
  el('profile').textContent='';
  return;
 }
 album.textContent='Chargement de ta collection…';
 const [profileResult,cardsResult]=await Promise.allSettled([
  api('/api/arena/me'),api('/api/arena/me/cards')
 ]);
 if(request!==collectionRequest)return;
 if(profileResult.status==='fulfilled'){
  const profile=profileResult.value.profile;
  el('profile').textContent=profile?`⭐ ${Number(profile.xp)} XP · 🪙 ${Number(profile.points)} points`:'Profil non trouvé. Utilise « Rejoindre ».';
 }else{
  el('profile').textContent='Profil temporairement indisponible : '+profileResult.reason.message;
 }
 if(cardsResult.status==='fulfilled'){
  const cards=cardsResult.value.cards||[];
  album.innerHTML=cards.length?cards.map(c=>cardMarkup(c.player_name,{unlocked:true,rarity:c.rarity})).join(''):'Aucune carte débloquée pour ce compte.';
 }else{
  album.textContent='Impossible de charger les cartes : '+cardsResult.reason.message+' Réessaie après le renouvellement du quota D1.';
 }
}
async function refreshDemo(){
 // Les boutons de validation ne doivent pas bloquer la collection personnelle.
 try{
  const settled=await api('/api/arena/challenges');
  const openIds=new Set((settled.challenges||[]).map(x=>x.id));
  el('demo-settle').innerHTML=demoNames.map(([id,a,b])=>`<article class="card"><strong>${safe(id.replace('arena-demo-','Duel '))}</strong><p>${openIds.has(id)?'En attente de validation':'Terminé ou indisponible'}</p>${openIds.has(id)?`<button data-demo-id="${id}" data-winner="a">🏆 ${safe(a)}</button> <button data-demo-id="${id}" data-winner="b">🏆 ${safe(b)}</button>`:''}</article>`).join('');
 }catch(e){el('demo-state').textContent='Défis temporairement indisponibles : '+e.message;}
}
document.addEventListener('click',async e=>{
 const b=e.target.closest('button[data-demo-id]');if(!b)return;
 if(!token()){el('demo-state').textContent='Active d’abord le mode test privé.';return;}
 if(!confirm('Valider définitivement ce résultat fictif ?'))return;
 b.disabled=true;
 try{await api('/api/arena/test/settle',{method:'POST',body:JSON.stringify({challenge_id:b.dataset.demoId,winner:b.dataset.winner})});el('demo-state').textContent='Résultat validé. Points et XP calculés.';await load();await refreshDemo();await refreshMyCollection();}
 catch(err){el('demo-state').textContent='Erreur : '+err.message;b.disabled=false;}
});
// Au chargement, restituer une session déjà ouverte et son album.
refreshMyCollection();
refreshDemo();

async function loadRankings(){
 try{
  const data=await api('/api/arena/rankings');
  for(const key of ['weekly','monthly']){
   el(key).innerHTML=(data[key]||[]).map((u,i)=>`<p>${i+1}. ${safe(u.display_name)} — ${Number(u.xp)} XP</p>`).join('')||'Aucun XP sur cette période.';
  }
 }catch(e){el('weekly').textContent=e.message;el('monthly').textContent=e.message;}
}
loadRankings();
document.addEventListener('click',e=>{if(e.target.closest('button[data-demo-id]'))setTimeout(loadRankings,600);});
