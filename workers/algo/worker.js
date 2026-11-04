// Worker « algo » (23/10/2026) — deux rôles, sur une adresse qui ne mène pas au dépôt GitHub :
//
// 1. SITE PUBLIC : https://algo.tennis-edge.workers.dev sert la page publique de l'algorithme (algo/index.html et
//    algo/donnees.json, relus sur GitHub Pages et gardés 60 s en cache). C'est l'adresse affichée dans les vidéos.
//
// 2. COFFRE PRIVÉ : /prive/<fichier> renvoie un fichier du coffre (R2, préfixe prive/ : journaux H18/H19/H20,
//    verdicts H19/H20, pronostic complet du jour) — SEULEMENT avec la clé privée (en-tête X-Cle = secret
//    CLE_PRIVEE du worker). Le Lab la lit via Tennis_Edge_Lab/prive.js. Sans clé : 401, et rien ne fuit.
//
// Déployé par .github/workflows/deploy_algo.yml (secrets CLE_PRIVEE et GH_TOKEN posés depuis les secrets GitHub).

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

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname === '/video') return video(req, env);
    if (url.pathname.startsWith('/prive/')) return prive(req, env, decodeURIComponent(url.pathname.slice(7)));
    if (req.method !== 'GET' && req.method !== 'HEAD') return new Response(null, { status: 405, headers: SECURITE });
    return publique(req, url.pathname);
  },
};
