// Worker « algo » (23/10/2026) — deux rôles, sur une adresse qui ne mène pas au dépôt GitHub :
//
// 1. SITE PUBLIC : https://algo.tennis-edge.workers.dev sert la page publique de l'algorithme (algo/index.html et
//    algo/donnees.json, relus sur GitHub Pages et gardés 60 s en cache). C'est l'adresse affichée dans les vidéos.
//
// 2. COFFRE PRIVÉ : /prive/<fichier> renvoie un fichier du coffre (R2, préfixe prive/ : journaux H18/H19/H20,
//    verdicts H19/H20, pronostic complet du jour) — SEULEMENT avec la clé privée (en-tête X-Cle = secret
//    CLE_PRIVEE du worker). Le Lab la lit via Tennis_Edge_Lab/prive.js. Sans clé : 401, et rien ne fuit.
//
// 4. SCORES EN DIRECT : /live (voir plus bas).
// 5. STATISTIQUES EN DIRECT : /live/stats?id= (voir plus bas).
// 6. DÉROULÉ POINT PAR POINT EN DIRECT : /live/points?id= (voir plus bas).
//
// Déployé par .github/workflows/deploy_algo.yml (secrets CLE_PRIVEE, GH_TOKEN et RAPIDAPI_KEY posés depuis les
// secrets GitHub).

const ORIGINE = 'https://lucas987987.github.io/Tennis-edge/algo/';
const LAB = 'https://lucas987987.github.io';
export const PUBLICS = { '/': 'index.html', '/index.html': 'index.html', '/donnees.json': 'donnees.json' };
// DOIT correspondre à scripts/coffre.py (SERVIS)
export const PRIVES = new Set(['h18_signal_log.jsonl', 'h18_signal_state.json', 'h19_signal_log.jsonl',
  'h19_signal_state.json', 'h20_signal_log.jsonl', 'h20_signal_state.json', 'h20.json', 'pronostics.json',
  'valeur.json']);

const SECURITE = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'X-Frame-Options': 'DENY',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
};
const CSP = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
  + "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";

function egal(a, b) {
  // comparaison à temps constant (ne révèle pas, par la durée, combien de caractères sont justes)
  const x = new TextEncoder().encode(String(a || '')), y = new TextEncoder().encode(String(b || ''));
  let d = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) d |= (x[i] || 0) ^ (y[i] || 0);
  return d === 0;
}

function cors(req) {
  const o = req.headers.get('Origin');
  return o === LAB ? { 'Access-Control-Allow-Origin': LAB, 'Access-Control-Allow-Headers': 'X-Cle',
    'Access-Control-Allow-Methods': 'GET, OPTIONS', 'Access-Control-Max-Age': '86400', Vary: 'Origin' } : { Vary: 'Origin' };
}

export async function prive(req, env, nom) {
  const h = { ...SECURITE, ...cors(req), 'Cache-Control': 'private, no-store' };
  if (req.method === 'OPTIONS') return new Response(null, { status: 204, headers: h });
  if (!env.CLE_PRIVEE || String(env.CLE_PRIVEE).length < 24) return new Response('Coffre fermé (clé non configurée).', { status: 503, headers: h });
  if (!egal(req.headers.get('X-Cle'), env.CLE_PRIVEE)) return new Response('Clé requise.', { status: 401, headers: h });
  if (!PRIVES.has(nom)) return new Response('Inconnu.', { status: 404, headers: h });
  const obj = await env.COFFRE.get('prive/' + nom);
  if (!obj) return new Response('Absent du coffre.', { status: 404, headers: h });
  return new Response(obj.body, { headers: { ...h, 'Content-Type': 'application/json; charset=utf-8' } });
}

export async function publique(req, chemin) {
  const f = PUBLICS[chemin];
  if (!f) return new Response('Page introuvable.', { status: 404, headers: SECURITE });
  const r = await fetch(ORIGINE + f, { cf: { cacheTtl: 60, cacheEverything: true } });
  if (!r.ok) return new Response('Indisponible, réessayer dans un instant.', { status: 502, headers: SECURITE });
  const type = f.endsWith('.json') ? 'application/json; charset=utf-8' : 'text/html; charset=utf-8';
  const h = { ...SECURITE, 'Content-Type': type, 'Cache-Control': 'public, max-age=60' };
  if (type.startsWith('text/html')) h['Content-Security-Policy'] = CSP;
  return new Response(r.body, { headers: h });
}

// 3. VIDÉO À LA DEMANDE (04/11/2026, demande de Lucas) : POST /video {uid} lance le workflow « Vidéo — simulation du
//    match du jour » (video_simulation.yml) pour ce match ; la vidéo arrive sur le Telegram PRIVÉ, comme chaque matin.
//    Même clé privée que le coffre (en-tête X-Cle) ; jeton GitHub (secret GH_TOKEN du worker, droit « Actions » en
//    écriture) jamais exposé à la page ; une demande toutes les 3 minutes au plus (horodatage gardé au coffre).
export const UID_VIDEO = /^\d{4}-\d{2}-\d{2}_[a-z0-9_]{3,120}$/;
const DEPOT = 'Lucas987987/Tennis-edge';
const ECART_VIDEO_MS = 3 * 60 * 1000;

export async function video(req, env) {
  const h = { ...SECURITE, 'Cache-Control': 'no-store', 'Content-Type': 'application/json; charset=utf-8' };
  const rep = (status, o) => new Response(JSON.stringify(o), { status, headers: h });
  if (req.method !== 'POST') return rep(405, { ok: false, message: 'POST attendu.' });
  if (!env.CLE_PRIVEE || String(env.CLE_PRIVEE).length < 24) return rep(503, { ok: false, message: 'Clé privée non configurée.' });
  if (!egal(req.headers.get('X-Cle'), env.CLE_PRIVEE)) return rep(401, { ok: false, message: 'Clé privée incorrecte.' });
  if (!env.GH_TOKEN) return rep(503, { ok: false, message: 'Jeton GitHub du worker absent (secret GH_TOKEN).' });
  let corps = {};
  try { corps = await req.json(); } catch (e) { corps = {}; }
  const uid = String(corps.uid || '');
  if (!UID_VIDEO.test(uid)) return rep(400, { ok: false, message: 'Match inconnu.' });
  const dernier = env.COFFRE ? await env.COFFRE.get('prive/video_derniere_demande.json') : null;
  if (dernier) {
    let t = 0;
    try { t = Number(JSON.parse(await dernier.text()).t) || 0; } catch (e) { t = 0; }
    const reste = ECART_VIDEO_MS - (Date.now() - t);
    if (reste > 0) return rep(429, { ok: false, message: `Une vidéo est déjà en route : réessayer dans ${Math.ceil(reste / 60000)} min.` });
  }
  const r = await fetch(`https://api.github.com/repos/${DEPOT}/actions/workflows/video_simulation.yml/dispatches`, {
    method: 'POST',
    headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${env.GH_TOKEN}`,
               'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'tennis-edge-algo', 'Content-Type': 'application/json' },
    body: JSON.stringify({ ref: 'main', inputs: { uid, adresse: 'false', seed: '' } }),
  });
  if (r.status !== 204) return rep(502, { ok: false, message: `GitHub a refusé (HTTP ${r.status}).` });
  if (env.COFFRE) await env.COFFRE.put('prive/video_derniere_demande.json', JSON.stringify({ t: Date.now(), uid }));
  return rep(202, { ok: true, message: 'Vidéo lancée : elle arrive sur ton Telegram privé dans 5 à 10 minutes.' });
}

// 4. SCORES EN DIRECT (06/11/2026, demande de Lucas) : GET /live → les matchs de simple en cours (TennisApi,
//    /api/tennis/events/live), compactés : score par set, points du jeu, serveur. Une requête TennisApi toutes les
//    30 s AU PLUS quel que soit le nombre de visiteurs (≈ 2 900 par jour pour un quota de 15 000) : réponse gardée en
//    mémoire et au coffre R2 (le cache HTTP de Cloudflare ne marche pas sur *.workers.dev). Clé : secret RAPIDAPI_KEY
//    du worker, jamais exposée. Aucune cote, aucun pronostic : la page relie elle-même les matchs à ses % figés.
const HOTE_TENNIS = 'tennisapi1.p.rapidapi.com';
export const LIVE_TTL_MS = 30 * 1000;
const LIVE_R2 = 'live/en_cours.json';
let LIVE_MEMOIRE = null;

function scoreSets(s) {
  s = s || {};
  const sets = [], tb = [];
  for (let i = 1; i <= 5; i++) {
    if (s['period' + i] == null) break;
    sets.push(s['period' + i]);
    tb.push(s['period' + i + 'TieBreak'] ?? null);
  }
  return { sets, tb, gagnes: s.current ?? null, point: s.point ?? null };
}

export function compacterLive(events) {
  return (events || []).filter(e => {
    const h = e.homeTeam || {}, a = e.awayTeam || {};
    // 06/11/2026 (soir) : en simple, TennisApi envoie « subTeams: [] » — un tableau vide est VRAI en JavaScript :
    // le premier filtre (!h.subTeams) écartait donc TOUS les matchs. On compte les éléments, comme est_simple() en Python.
    const equipes = t => Array.isArray(t.subTeams) ? t.subTeams.length > 0 : !!t.subTeams;
    return !equipes(h) && !equipes(a) && !String((h.name || '') + (a.name || '')).includes('/');
  }).map(e => ({
    id: e.id, debut: e.startTimestamp || null,
    categorie: ((e.tournament || {}).category || {}).name || null, tournoi: (e.tournament || {}).name || null,
    home: (e.homeTeam || {}).name || '', away: (e.awayTeam || {}).name || '',
    statut: { type: (e.status || {}).type || null, texte: (e.status || {}).description || null },
    // firstToServe = serveur du jeu en cours/dernier jeu (vérifié le 05/11/2026 sur 9 304 matchs : 93 %)
    serveur: e.firstToServe === 1 ? 'home' : e.firstToServe === 2 ? 'away' : null,
    score_home: scoreSets(e.homeScore), score_away: scoreSets(e.awayScore),
  }));
}

export async function live(req, env) {
  const h = { ...SECURITE, 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'public, max-age=15' };
  const rep = o => new Response(JSON.stringify(o), { headers: h });
  const frais = o => o && Date.now() - (o.maj || 0) < LIVE_TTL_MS;
  if (frais(LIVE_MEMOIRE)) return rep(LIVE_MEMOIRE);
  if (env.COFFRE) {
    try {
      const obj = await env.COFFRE.get(LIVE_R2);
      if (obj) { const o = JSON.parse(await obj.text()); if (frais(o)) { LIVE_MEMOIRE = o; return rep(o); } }
    } catch (e) { /* on interroge TennisApi */ }
  }
  let o;
  if (!env.RAPIDAPI_KEY) o = { ok: false, maj: Date.now(), message: 'Scores en direct : clé TennisApi du worker absente.', matchs: [] };
  else {
    try {
      const r = await fetch(`https://${HOTE_TENNIS}/api/tennis/events/live`, {
        headers: { 'X-RapidAPI-Key': env.RAPIDAPI_KEY, 'X-RapidAPI-Host': HOTE_TENNIS, Accept: 'application/json' } });
      // brut : nombre de matchs reçus de TennisApi avant le filtre (simples seulement) — pour vérifier d'un coup d'œil
      const doc = r.ok ? await r.json() : null;
      const ev = doc ? (doc.events || []) : [];
      o = r.ok ? { ok: true, maj: Date.now(), brut: ev.length, matchs: compacterLive(ev) }
               : { ok: false, maj: Date.now(), message: `TennisApi : HTTP ${r.status}`, matchs: [] };
    } catch (e) {
      o = { ok: false, maj: Date.now(), message: 'TennisApi injoignable.', matchs: [] };
    }
  }
  LIVE_MEMOIRE = o;
  if (env.COFFRE) { try { await env.COFFRE.put(LIVE_R2, JSON.stringify(o)); } catch (e) { /* mémoire seule */ } }
  return rep(o);
}

// 5. STATISTIQUES EN DIRECT (06/11/2026) : GET /live/stats?id=<id TennisApi> → la feuille du match en cours
//    (/api/tennis/event/{id}/statistics, période « ALL »), gardée 60 s par match en mémoire et au coffre : 100 visiteurs
//    sur la même fiche = 1 requête par minute. La page ne la demande que pour la fiche ouverte d'un match en cours.
//    Plafond de requêtes TennisApi par jour (UTC) : variable LIVE_STATS_PLAFOND du worker, 6 000 par défaut ;
//    au-delà, la dernière feuille connue est renvoyée avec plafond: true jusqu'au lendemain (les scores continuent).
export const STATS_TTL_MS = 60 * 1000;
const STATS_MEMOIRE = new Map();
const COMPTEUR = { jour: null, n: 0 };

export function compacterStats(doc) {
  for (const p of (doc && doc.statistics) || []) {
    if (String(p.period || 'ALL') !== 'ALL') continue;
    const out = {};
    for (const g of p.groups || []) for (const it of g.statisticsItems || []) {
      const k = it.key || it.name;
      if (k) out[k] = [it.homeValue ?? null, it.homeTotal ?? null, it.awayValue ?? null, it.awayTotal ?? null];
    }
    return Object.keys(out).length ? out : null;
  }
  return null;
}

async function compter(env) {
  const jour = new Date().toISOString().slice(0, 10), cle = `live/compteur/${jour}.json`;
  if (COMPTEUR.jour !== jour) {
    COMPTEUR.jour = jour; COMPTEUR.n = 0;
    if (env.COFFRE) { try { const o = await env.COFFRE.get(cle); if (o) COMPTEUR.n = JSON.parse(await o.text()).n || 0; } catch (e) { /* 0 */ } }
  }
  return { jour, cle };
}

// 6. DÉROULÉ POINT PAR POINT EN DIRECT (06/11/2026, paquet 210) : GET /live/points?id= → [[set, jeu, serveur, « HAHA… »,
//    vainqueur du jeu ou null]] (/api/tennis/event/{id}/point-by-point), même cache de 60 s et même plafond que les stats.
//    La page en tire la courbe du % jeu après jeu et les moments clés (breaks, sets).
const VALEURS_PT = { '0': 0, '15': 1, '30': 2, '40': 3, 'A': 4, 'AD': 4 };
function valeurPt(x) {
  const s = String(x ?? '').trim().toUpperCase();
  if (s in VALEURS_PT) return VALEURS_PT[s];
  const n = parseInt(s, 10);
  return Number.isFinite(n) ? n : null;
}
export function suiteDesPoints(points, gagnant) {
  // même lecture que scripts/points_match.py (suite_des_points)
  const out = [];
  let ph = 0, pa = 0;
  for (const pt of points || []) {
    const h = valeurPt(pt.homePoint), a = valeurPt(pt.awayPoint);
    if (h === null || a === null) return null;
    if (h > ph || (a < pa && h >= ph)) out.push('H');
    else if (a > pa || (h < ph && a >= pa)) out.push('A');
    else return null;
    ph = h; pa = a;
  }
  if ((gagnant === 1 || gagnant === 2) && out.length) out.push(gagnant === 1 ? 'H' : 'A');
  return out.join('');
}
export function compacterPoints(doc) {
  const sets = (doc || {}).pointByPoint;
  if (!Array.isArray(sets)) return null;
  const jeux = [];
  for (const s of sets) for (const g of s.games || []) {
    const sc = g.score || {};
    const seq = suiteDesPoints(g.points, sc.scoring);
    if (seq === null || (sc.serving !== 1 && sc.serving !== 2)) continue;
    jeux.push([s.set, g.game, sc.serving, seq, sc.scoring === 1 || sc.scoring === 2 ? sc.scoring : null]);
  }
  jeux.sort((x, y) => (x[0] - y[0]) || (x[1] - y[1]));
  return jeux.length ? jeux : null;
}

const DETAILS = {
  stats: { chemin: id => `/api/tennis/event/${id}/statistics`, compacter: compacterStats, champ: 'stats' },
  points: { chemin: id => `/api/tennis/event/${id}/point-by-point`, compacter: compacterPoints, champ: 'jeux' },
};

async function liveDetail(req, env, url, genre) {
  const D = DETAILS[genre];
  const h = { ...SECURITE, 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'public, max-age=30' };
  const rep = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: h });
  const id = url.searchParams.get('id') || '';
  if (!/^\d{1,12}$/.test(id)) return rep({ ok: false, message: 'id invalide' }, 400);
  const cleR2 = `live/${genre}/${id}.json`, cleM = `${genre}:${id}`;
  let connu = STATS_MEMOIRE.get(cleM) || null;
  if (connu && Date.now() - connu.maj < STATS_TTL_MS) return rep(connu);
  if (env.COFFRE) {
    try { const o = await env.COFFRE.get(cleR2); if (o) { const x = JSON.parse(await o.text()); if (!connu || x.maj > connu.maj) connu = x; } } catch (e) { /* rien */ }
    if (connu && Date.now() - connu.maj < STATS_TTL_MS) { STATS_MEMOIRE.set(cleM, connu); return rep(connu); }
  }
  const plafond = parseInt(env.LIVE_STATS_PLAFOND, 10) || 6000;
  const { cle } = await compter(env);
  if (COMPTEUR.n >= plafond) return rep({ ...(connu || { ok: false, [D.champ]: null }), plafond: true });
  if (!env.RAPIDAPI_KEY) return rep({ ok: false, message: 'clé TennisApi absente', [D.champ]: null });
  let o;
  try {
    COMPTEUR.n++;
    if (env.COFFRE) { try { await env.COFFRE.put(cle, JSON.stringify({ n: COMPTEUR.n })); } catch (e) { /* mémoire seule */ } }
    const r = await fetch(`https://${HOTE_TENNIS}${D.chemin(id)}`, {
      headers: { 'X-RapidAPI-Key': env.RAPIDAPI_KEY, 'X-RapidAPI-Host': HOTE_TENNIS, Accept: 'application/json' } });
    o = r.ok ? { ok: true, id: +id, maj: Date.now(), [D.champ]: D.compacter(await r.json()) }
      // 404 = pas encore de données (début de match) : on le garde 60 s comme une réponse normale
             : { ok: r.status === 404, id: +id, maj: Date.now(), [D.champ]: connu ? connu[D.champ] : null, message: `TennisApi : HTTP ${r.status}` };
  } catch (e) {
    o = { ok: false, id: +id, maj: Date.now(), [D.champ]: connu ? connu[D.champ] : null, message: 'TennisApi injoignable.' };
  }
  STATS_MEMOIRE.set(cleM, o);
  if (STATS_MEMOIRE.size > 300) STATS_MEMOIRE.delete(STATS_MEMOIRE.keys().next().value);
  if (env.COFFRE) { try { await env.COFFRE.put(cleR2, JSON.stringify(o)); } catch (e) { /* mémoire seule */ } }
  return rep(o);
}
export const liveStats = (req, env, url) => liveDetail(req, env, url, 'stats');
export const livePoints = (req, env, url) => liveDetail(req, env, url, 'points');

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname === '/live/stats') return liveStats(req, env, url);
    if (url.pathname === '/live/points') return livePoints(req, env, url);
    if (url.pathname === '/live') return live(req, env);
    if (url.pathname === '/video') return video(req, env);
    if (url.pathname.startsWith('/prive/')) return prive(req, env, decodeURIComponent(url.pathname.slice(7)));
    if (req.method !== 'GET' && req.method !== 'HEAD') return new Response(null, { status: 405, headers: SECURITE });
    return publique(req, url.pathname);
  },
};
