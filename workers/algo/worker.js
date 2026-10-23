// Worker « algo » (23/10/2026) — deux rôles, sur une adresse qui ne mène pas au dépôt GitHub :
//
// 1. SITE PUBLIC : https://algo.tennis-edge.workers.dev sert la page publique de l'algorithme (algo/index.html et
//    algo/donnees.json, relus sur GitHub Pages et gardés 60 s en cache). C'est l'adresse affichée dans les vidéos.
//
// 2. COFFRE PRIVÉ : /prive/<fichier> renvoie un fichier du coffre (R2, préfixe prive/ : journaux H18/H19/H20,
//    verdicts H19/H20, pronostic complet du jour) — SEULEMENT avec la clé privée (en-tête X-Cle = secret
//    CLE_PRIVEE du worker). Le Lab la lit via Tennis_Edge_Lab/prive.js. Sans clé : 401, et rien ne fuit.
//
// Déployé par .github/workflows/deploy_algo.yml (secret CLE_PRIVEE posé depuis le secret GitHub du même nom).

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

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname.startsWith('/prive/')) return prive(req, env, decodeURIComponent(url.pathname.slice(7)));
    if (req.method !== 'GET' && req.method !== 'HEAD') return new Response(null, { status: 405, headers: SECURITE });
    return publique(req, url.pathname);
  },
};
