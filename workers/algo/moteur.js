// 27/11/2026 (paquet 511, Lucas : « ok pour le % dans les notifications de fin de set, en reprenant le moteur du
// direct ») — LE MOTEUR DU % EN DIRECT DE LA PAGE, recopié À L'IDENTIQUE depuis algo/index.html (Moteur, calibre,
// etatLive, sigmaLive, formesLive, pointsServiceLive, pctLive, GH9, PT_LIVE) : le test workers/algo/test_moteur.mjs
// vérifie que chaque fonction est mot pour mot celle de la page et donne le même %. Seuls changent les « réservoirs »
// de la page (LIVE, D), remplis ici par pctDirect() avec ce que le worker connaît : le match du site (simulation, %
// publié), le direct (score, serveur), la feuille de stats déjà gardée au coffre (aucune requête TennisApi en plus) et
// σ (live_reevaluation de site.json).
const logit = p => Math.log(p/(1-p)), sig = z => 1/(1+Math.exp(-z));
const setFini = (g, o) => (Math.max(g, o) >= 6 && Math.abs(g - o) >= 2) || (Math.max(g, o) === 7 && Math.min(g, o) >= 5);
const PT_LIVE = {'0':0,'15':1,'30':2,'40':3,'A':4,'AD':4};
const GH9 = [[-4.5127458633997,2.23458440077e-05],[-3.2054290028565,0.00278914132123],[-2.0768479786779,0.0499164067652],
  [-1.0232556637891,0.244097502895],[0,0.406349206349],[1.0232556637891,0.244097502895],[2.0768479786779,0.0499164067652],
  [3.2054290028565,0.00278914132123],[4.5127458633997,2.23458440077e-05]];
const LIVE = { moteurs: {}, formes: {}, reeval: {}, stats: {} };
let D = null;

function Moteur(sim){
  const A = sim.a, B = sim.b, N = sim.sets_gagnants, TBF = sim.tb_final || 7;
  const pServ = s => s===0 ? A : 1-B;          // P(home gagne le point) selon le serveur
  const memo = new Map();
  function pGame(p,a,b){                        // P(serveur gagne le jeu) depuis a-b points
    if (a>=4 && a-b>=2) return 1; if (b>=4 && b-a>=2) return 0;
    if (a>=3 && b>=3){ const d = p*p/(p*p+(1-p)*(1-p)); return a===b ? d : (a>b ? p+(1-p)*d : p*d); }
    return p*pGame(p,a+1,b)+(1-p)*pGame(p,a,b+1);
  }
  const tbServ = (k,s0) => k===0 ? s0 : ((((k-1)>>1)%2)===0 ? 1-s0 : s0);
  function pTB(i,j,s0,cible){                    // P(home gagne le jeu décisif) depuis i-j
    if (i>=cible && i-j>=2) return 1; if (j>=cible && j-i>=2) return 0;
    if (i===j && i>=cible-1){ const k=i+j, p1=pServ(tbServ(k,s0)), p2=pServ(tbServ(k+1,s0)); const w=p1*p2, l=(1-p1)*(1-p2); return w/(w+l); }
    const key='t'+i+','+j+','+s0+','+cible; if (memo.has(key)) return memo.get(key);
    const p=pServ(tbServ(i+j,s0)); const v=p*pTB(i+1,j,s0,cible)+(1-p)*pTB(i,j+1,s0,cible); memo.set(key,v); return v;
  }
  // distribution de fin de set : [home gagne & sert ensuite 0, home gagne & 1, away gagne & 0, away gagne & 1]
  function setDist(gh,ga,srv,fin){
    if ((gh>=6 && gh-ga>=2) || gh===7) return [srv===0?1:0, srv===1?1:0, 0,0];
    if ((ga>=6 && ga-gh>=2) || ga===7) return [0,0, srv===0?1:0, srv===1?1:0];
    const key='s'+gh+','+ga+','+srv+','+fin; if (memo.has(key)) return memo.get(key);
    let v;
    if (gh===6 && ga===6){ const p=pTB(0,0,srv,fin?TBF:7); v = srv===0 ? [0,p,0,1-p] : [p,0,1-p,0]; }
    else { const pg = srv===0 ? pGame(A,0,0) : 1-pGame(B,0,0);
      const x=setDist(gh+1,ga,1-srv,fin), y=setDist(gh,ga+1,1-srv,fin); v=x.map((e,i)=>pg*e+(1-pg)*y[i]); }
    memo.set(key,v); return v;
  }
  function pMatch(sh,sa,srv){
    if (sh>=N) return 1; if (sa>=N) return 0;
    const key='m'+sh+','+sa+','+srv; if (memo.has(key)) return memo.get(key);
    const d=setDist(0,0,srv,sh===N-1&&sa===N-1);
    const v=d[0]*pMatch(sh+1,sa,0)+d[1]*pMatch(sh+1,sa,1)+d[2]*pMatch(sh,sa+1,0)+d[3]*pMatch(sh,sa+1,1);
    memo.set(key,v); return v;
  }
  function pLive(S){                             // P(home gagne le match) depuis l'état S
    if (S.fini) return S.vainqueur===0 ? 1 : 0;
    const sh=S.sets[0], sa=S.sets[1], fin = sh===N-1 && sa===N-1, gh=S.jeux[0], ga=S.jeux[1];
    let d;
    if (S.tb){ const p=pTB(S.pts[0],S.pts[1],S.tbS0,S.tbCible); const nx=1-S.tbS0; d = nx===0 ? [p,0,1-p,0] : [0,p,0,1-p]; }
    else {
      const ps = S.srv===0 ? pGame(A,S.pts[0],S.pts[1]) : 1-pGame(B,S.pts[1],S.pts[0]);
      const x=setDist(gh+1,ga,1-S.srv,fin), y=setDist(gh,ga+1,1-S.srv,fin); d=x.map((e,i)=>ps*e+(1-ps)*y[i]);
    }
    return d[0]*pMatch(sh+1,sa,0)+d[1]*pMatch(sh+1,sa,1)+d[2]*pMatch(sh,sa+1,0)+d[3]*pMatch(sh,sa+1,1);
  }
  function etat(premier){ return {sets:[0,0], jeux:[0,0], pts:[0,0], srv:premier, tb:false, tbS0:0, tbCible:7, histo:[], fini:false, vainqueur:null}; }
  function point(S, r){                          // joue un point ; r ∈ [0,1)
    const serveur = S.tb ? tbServ(S.pts[0]+S.pts[1], S.tbS0) : S.srv;
    const h = r < pServ(serveur) ? 0 : 1;
    S.pts[h]++;
    const [a,b]=S.pts;
    if (S.tb){
      if ((a>=S.tbCible || b>=S.tbCible) && Math.abs(a-b)>=2){ S.jeux[h]++; finSet(S,h); S.srv = 1-S.tbS0; }
      return h;
    }
    if ((a>=4 || b>=4) && Math.abs(a-b)>=2){
      S.jeux[h]++; S.pts=[0,0]; S.srv=1-S.srv;
      const [gh,ga]=S.jeux, fin = S.sets[0]===N-1 && S.sets[1]===N-1;
      if ((gh>=6||ga>=6) && Math.abs(gh-ga)>=2) finSet(S, gh>ga?0:1);
      else if (gh===6 && ga===6){ S.tb=true; S.tbS0=S.srv; S.tbCible = fin ? TBF : 7; }
    }
    return h;
  }
  function finSet(S,h){ S.histo.push([...S.jeux]); S.sets[h]++; S.jeux=[0,0]; S.pts=[0,0]; S.tb=false;
    if (S.sets[h]>=N){ S.fini=true; S.vainqueur=h; } }
  const serveur = S => S.tb ? tbServ(S.pts[0]+S.pts[1], S.tbS0) : S.srv;
  return {etat, point, pLive, serveur};
}

function calibre(sim, p){
  const f = d => Moteur({...sim, a: sim.a + d, b: sim.b - d}).pLive(Moteur(sim).etat(0)) - p;
  let lo = -0.2, hi = 0.2;
  if (f(lo) > 0 || f(hi) < 0) return sim;
  for (let k=0;k<40;k++){ const mid=(lo+hi)/2; if (f(mid) < 0) lo = mid; else hi = mid; }
  const d=(lo+hi)/2; return {...sim, a: sim.a + d, b: sim.b - d};
}

function etatLive(m, r){
  const sim = m.simulation; if (!sim || !sim.a || !sim.b) return null;
  const x = r.x, h = r.inverse ? x.score_away : x.score_home, a = r.inverse ? x.score_home : x.score_away;
  const N = sim.sets_gagnants || 2, TBF = sim.tb_final || 7;
  const SH = h.sets || [], SA = a.sets || [];
  const S = {sets:[0,0], jeux:[0,0], pts:[0,0], srv:0, tb:false, tbS0:0, tbCible:7, histo:[], fini:false, vainqueur:null};
  for (let i=0;i<SH.length;i++){
    const gh = +SH[i]||0, ga = +(SA[i]??0)||0;
    if (setFini(gh,ga) || setFini(ga,gh)) { S.sets[gh>ga?0:1]++; continue; }
    if (i < SH.length-1) return null;                // set non fini suivi d'un autre : score illisible
    S.jeux = [gh, ga];
  }
  if (S.sets[0]>=N || S.sets[1]>=N) return null;     // match fini (le dernier score reste affiché)
  const fin = S.sets[0]===N-1 && S.sets[1]===N-1;
  const sv = x.serveur ? ((x.serveur==='home') !== r.inverse ? 0 : 1) : null;
  if (S.jeux[0]===6 && S.jeux[1]===6){
    S.tb = true; S.tbCible = fin ? TBF : 7;
    S.pts = [parseInt(h.point,10)||0, parseInt(a.point,10)||0];
  } else {
    let ph = PT_LIVE[String(h.point??'0').toUpperCase()] ?? 0, pa = PT_LIVE[String(a.point??'0').toUpperCase()] ?? 0;
    if (ph===4 && pa<3) pa = 3; if (pa===4 && ph<3) ph = 3;
    S.pts = [ph, pa];
  }
  return {S, sv};
}
function sigmaLive(m){ const s = D && D.live_reevaluation && D.live_reevaluation.sigma; return (s && +s[m.circuit]) || 0; }
function formesLive(m, sigma){
  const cle = m.uid + '|' + sigma; if (LIVE.formes[cle]) return LIVE.formes[cle];
  const sim = m.simulation, la = logit(sim.a), lb = logit(sim.b), p = m.p_home;
  const avant = M => (M.pLive(M.etat(0)) + M.pLive(M.etat(1))) / 2;
  const v = d => GH9.reduce((t,[z,w]) => t + w*avant(Moteur({...sim, a: sig(la+d+sigma*z), b: sig(lb-d-sigma*z)})), 0);
  let lo = -4, hi = 4;
  for (let k=0;k<22;k++){ const mid=(lo+hi)/2; if (v(mid) < p) lo = mid; else hi = mid; }
  const d = (lo+hi)/2;
  return (LIVE.formes[cle] = GH9.map(([z,w]) => { const a = sig(la+d+sigma*z), b = sig(lb-d-sigma*z);
    return {w, a, b, M: Moteur({...sim, a, b})}; }));
}
function pointsServiceLive(uid, inverse){
  const st = LIVE.stats[uid], S = st && st.o && st.o.stats; if (!S) return null;
  const fs = S.firstServeAccuracy, sp = S.servicePointsScored; if (!fs || !sp || fs[1]==null || fs[3]==null) return null;
  const h = {n:+fs[1]||0, w:+sp[0]||0}, a = {n:+fs[3]||0, w:+sp[2]||0};
  return inverse ? [a, h] : [h, a];
}
function pctLive(m, r){
  const e = etatLive(m, r); if (!e) return null;
  try {
    const avec = M => { const unServeur = s => { const S = {...e.S, pts:[...e.S.pts], jeux:[...e.S.jeux], sets:[...e.S.sets]};
      S.srv = s; if (S.tb){ const k=S.pts[0]+S.pts[1]; S.tbS0 = k===0 ? s : ((((k-1)>>1)%2)===0 ? 1-s : s); } return M.pLive(S); };
      return e.sv==null ? (unServeur(0)+unServeur(1))/2 : unServeur(e.sv); };
    const sigma = sigmaLive(m), pts = sigma > 0 ? pointsServiceLive(m.uid, r.inverse) : null;
    let p;
    if (pts){
      const F = formesLive(m, sigma), [A, B] = pts;
      const lw = F.map(f => Math.log(f.w) + A.w*Math.log(f.a) + (A.n-A.w)*Math.log(1-f.a) + B.w*Math.log(f.b) + (B.n-B.w)*Math.log(1-f.b));
      const mx = Math.max(...lw); let tot = 0, v = 0;
      F.forEach((f,i) => { const x = Math.exp(lw[i]-mx); tot += x; v += x*avec(f.M); });
      p = v / tot; LIVE.reeval[m.uid] = true;
    } else {
      const M = LIVE.moteurs[m.uid] || (LIVE.moteurs[m.uid] = Moteur(calibre(m.simulation, m.p_home)));
      p = avec(M); LIVE.reeval[m.uid] = false;
    }
    return Number.isFinite(p) ? Math.min(0.99, Math.max(0.01, p)) : null;   // jamais « 100 % » tant que ça se joue
  } catch(err){ return null; }
}

// m : match du site (uid, circuit, simulation, p_home) ; r : { x: match du direct, inverse } ; sigma : {ATP, WTA, CH} ;
// stats : feuille du direct (compacterStats) ou null.
export function pctDirect(m, r, sigma, stats) {
  if (Object.keys(LIVE.moteurs).length > 300) { LIVE.moteurs = {}; LIVE.formes = {}; }
  D = { live_reevaluation: { sigma: sigma || {} } };
  if (stats) LIVE.stats[m.uid] = { o: { stats } }; else delete LIVE.stats[m.uid];
  try { return pctLive(m, r); } finally { delete LIVE.stats[m.uid]; }
}
export { Moteur, calibre, etatLive, pctLive };
export const SOURCES = ['Moteur', 'calibre', 'etatLive', 'sigmaLive', 'formesLive', 'pointsServiceLive', 'pctLive'];
