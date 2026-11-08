// Configure API_URL to your dedicated Arena Worker endpoint after deployment.
const API_URL=globalThis.ARENA_API_URL||'';
if(!API_URL||API_URL.includes('YOUR-SUBDOMAIN')){document.addEventListener('DOMContentLoaded',()=>{document.querySelector('#challenges').textContent='Arena en attente de configuration Cloudflare (arena/config.js).';});}
const token=()=>sessionStorage.getItem('arena_session')||'';
const el=id=>document.getElementById(id);
const safe=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
async function api(path,options={}){const response=await fetch(API_URL+path,{...options,headers:{'content-type':'application/json',...(token()?{authorization:'Bearer '+token()}:{})}});const data=await response.json();if(!response.ok)throw Error(data.error||'Erreur');return data;}
async function load(){for(const [path,id,draw] of [['/api/arena/challenges','challenges',d=>{el('challenges').innerHTML=d.challenges.map(c=>`<article class="card"><h3>${safe(c.title)}</h3><p>${safe(c.player_a)} ⚔️ ${safe(c.player_b)}</p><small>Fermeture : ${safe(c.closes_at)}</small><p><button data-id="${safe(c.id)}" data-pick="a">${safe(c.player_a)}</button> <button data-id="${safe(c.id)}" data-pick="b">${safe(c.player_b)}</button></p></article>`).join('')||'Aucun défi ouvert.';el('cards').innerHTML=d.challenges.flatMap(c=>[c.player_a,c.player_b]).filter((v,i,a)=>a.indexOf(v)===i).map(n=>`<div class="card">🎾 <strong>${safe(n)}</strong><p>Carte joueur</p></div>`).join('');}],['/api/arena/leaderboard','leaders',d=>{el('leaders').innerHTML=d.leaders.map((u,i)=>`<p>${i+1}. ${safe(u.display_name)} — ${Number(u.xp)} XP</p>`).join('')||'Pas encore de participants.';}],['/api/arena/rewards','rewards',d=>{el('rewards').innerHTML=d.rewards.map(r=>`<div class="card"><h3>${safe(r.title)}</h3><p>${Number(r.cost)} points · Stock ${Number(r.stock)}</p><button data-reward="${safe(r.id)}">Échanger</button></div>`).join('')||'Boutique en préparation.';}]]){try{draw(await api(path));}catch(e){el(id).textContent='Données indisponibles : '+e.message;}}}
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;try{if(b.dataset.id){await api('/api/arena/predict',{method:'POST',body:JSON.stringify({challenge_id:b.dataset.id,pick:b.dataset.pick})});alert('Prédiction enregistrée !');}else if(b.dataset.reward){await api('/api/arena/redeem',{method:'POST',body:JSON.stringify({reward_id:b.dataset.reward})});alert('Récompense réservée !');load();}}catch(err){alert(err.message);}});
el('join').addEventListener('click',async()=>{try{await api('/api/arena/join',{method:'POST',body:JSON.stringify({display_name:el('name').value})});el('me').textContent='Inscription confirmée';}catch(e){el('me').textContent=e.message;}});load();

document.getElementById('test-login').addEventListener('click',async()=>{const field=document.getElementById('test-key'),state=document.getElementById('test-state');try{const result=await api('/api/arena/test-login',{method:'POST',body:JSON.stringify({access_key:field.value})});sessionStorage.setItem('arena_session',result.token);field.value='';state.textContent='Mode test activé pour une heure';await load();}catch(e){state.textContent=e.message;}});

const demoNames=[['arena-demo-1','Joueur Alpha','Joueur Bêta'],['arena-demo-2','Joueur Gamma','Joueur Delta'],['arena-demo-3','Joueur Epsilon','Joueur Zêta']];
async function refreshDemo(){
 const settled=await api('/api/arena/challenges');
 const openIds=new Set(settled.challenges.map(x=>x.id));
 el('demo-settle').innerHTML=demoNames.map(([id,a,b])=>`<article class="card"><strong>${safe(id.replace('arena-demo-','Duel '))}</strong><p>${openIds.has(id)?'En attente de validation':'Terminé ou indisponible'}</p>${openIds.has(id)?`<button data-demo-id="${id}" data-winner="a">🏆 ${safe(a)}</button> <button data-demo-id="${id}" data-winner="b">🏆 ${safe(b)}</button>`:''}</article>`).join('');
 if(!token())return;
 try{const [me,cards]=await Promise.all([api('/api/arena/me'),api('/api/arena/me/cards')]);
 el('profile').textContent=me.profile?`⭐ ${me.profile.xp} XP · 🪙 ${me.profile.points} points`:'Profil non trouvé';
 el('my-cards').innerHTML=cards.cards.map(c=>`<div class="card">🃏 <strong>${safe(c.player_name)}</strong><p>Carte gagnée</p></div>`).join('')||'Aucune carte débloquée pour le moment.';
 }catch(e){el('profile').textContent=e.message;}
}
document.addEventListener('click',async e=>{
 const b=e.target.closest('button[data-demo-id]');if(!b)return;
 if(!token()){el('demo-state').textContent='Active d’abord le mode test privé.';return;}
 if(!confirm('Valider définitivement ce résultat fictif ?'))return;
 b.disabled=true;
 try{await api('/api/arena/test/settle',{method:'POST',body:JSON.stringify({challenge_id:b.dataset.demoId,winner:b.dataset.winner})});el('demo-state').textContent='Résultat validé. Points et XP calculés.';await load();await refreshDemo();}
 catch(err){el('demo-state').textContent='Erreur : '+err.message;b.disabled=false;}
});
// Refresh after login, join, and on first page load.
el('test-login').addEventListener('click',()=>setTimeout(refreshDemo,350));
el('join').addEventListener('click',()=>setTimeout(async()=>{await load();await refreshDemo();},350));
refreshDemo();
