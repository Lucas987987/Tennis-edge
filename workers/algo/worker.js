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
// 7. SITE PRIVÉ (22/11/2026, paquet 334) : le Lab (/lab/…) et l'ancien tableau de bord (/tableau/…), autrefois publics
//    sur GitHub Pages, sont lus dans R2 (prive/site/, envoyés par scripts/publier_r2.py) et servis SEULEMENT sur
//    l'adresse workers.dev, jamais sur gamesetalgo.com, après connexion (/connexion, clé CLE_PRIVEE ; cookie de
//    session signé, valable un an). Le site public est lui aussi lu dans R2 d'abord (site/algo/), GitHub Pages ne
//    servant plus que de secours.
//
// Déployé par .github/workflows/deploy_algo.yml (secrets CLE_PRIVEE, GH_TOKEN et RAPIDAPI_KEY posés depuis les
// secrets GitHub).

// 8. COMPTES DES ABONNÉS (23/11/2026, paquet 377) : /compte/api/… (inscription, connexion, e-mails par Brevo) et
//    /compte/admin (workers.dev + clé privée : donner un accès Plus à la main). Données réservées : /site.json et
//    /donnees.json ne sont servis complets qu'à un abonné (ou avec la clé privée) ; les autres reçoivent
//    site_libre.json (le match du jour complet, les autres matchs sans aucun pronostic). Voir comptes.js.
import { apiCompte, adminComptes, utilisateur, abonne, estAdmin } from './comptes.js';
import { compterVisite, quotidien } from './ventes.js';

const ORIGINE = 'https://lucas987987.github.io/Tennis-edge/algo/';
const LAB = 'https://lucas987987.github.io';
export const PUBLICS = { '/': 'index.html', '/index.html': 'index.html', '/donnees.json': 'donnees.json',
  // 21/11/2026 (paquet 328) : site plus léger (site.json d'abord, site_plus.json ensuite), éditeur des mentions
  // légales, image d'aperçu des liens partagés et polices servies par le site lui-même (plus aucun appel à Google)
  '/site.json': 'site.json', '/site_plus.json': 'site_plus.json', '/editeur.json': 'editeur.json', '/partage.png': 'partage.png',
  // 22/11/2026 (paquet 329) : la page « Comment ça marche »
  '/methode.html': 'methode.html', '/comment-ca-marche': 'methode.html',
  // 22/11/2026 (paquet 330) : la page « Qui sommes-nous »
  '/apropos.html': 'apropos.html', '/qui-sommes-nous': 'apropos.html',
  // 23/11/2026 (paquet 391) : le site s'installe comme une appli (manifeste, service worker, icônes)
  '/manifest.webmanifest': 'manifest.webmanifest', '/sw.js': 'sw.js', '/icone-192.png': 'icone-192.png',
  '/icone-512.png': 'icone-512.png', '/icone-maskable-512.png': 'icone-maskable-512.png', '/apple-touch-icon.png': 'apple-touch-icon.png' };
export const POLICES = /^\/polices\/[a-z0-9-]{3,40}\.woff2$/;
// 391 : le script et la feuille de style de la page, sortis à la publication (scripts/decouper_page.py) ; leur nom
// contient l'empreinte de leur contenu : gardés un an par le navigateur
export const EMPREINTES = /^\/(app-[0-9a-f]{12}\.js|style-[0-9a-f]{12}\.css)$/;
const TYPES = { json: 'application/json; charset=utf-8', html: 'text/html; charset=utf-8', png: 'image/png', woff2: 'font/woff2',
  js: 'text/javascript; charset=utf-8', css: 'text/css; charset=utf-8', webmanifest: 'application/manifest+json' };
// DOIT correspondre à scripts/coffre.py (SERVIS)
export const PRIVES = new Set(['h18_signal_log.jsonl', 'h18_signal_state.json', 'h19_signal_log.jsonl',
  'h19_signal_state.json', 'h20_signal_log.jsonl', 'h20_signal_state.json', 'h20.json', 'pronostics.json',
  'valeur.json', 'delai_alertes.json']);

const SECURITE = {
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'no-referrer',
  'X-Frame-Options': 'DENY',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
};
// 382 : Cloudflare Turnstile (anti-robots des comptes) — son script et son cadre, rien d'autre
const CSP = "default-src 'self'; script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline'; "
  + "font-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src https://challenges.cloudflare.com; "
  + "base-uri 'none'; form-action 'none'; frame-ancestors 'none'";

// 334 : lecture dans R2 (bucket du coffre) ; null si absent, vide ou en erreur (le secours GitHub Pages prend le relais)
async function depuisR2(env, cle, min = 1) {
  if (!env || !env.COFFRE) return null;
  try {
    const o = await env.COFFRE.get(cle);
    if (!o) return null;
    if (o.size !== undefined && o.size < min) { if (o.body && o.body.cancel) await o.body.cancel(); return null; }
    return o;
  } catch (e) { return null; }
}

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

// 377 : fichiers réservés à l'accès Plus ; sans accès, la version libre (jamais le fichier complet, même en secours)
export const RESERVES = Object.freeze({ '/site.json': 'site.json', '/donnees.json': 'donnees.json', '/site_admin.json': 'site_admin.json' });
export async function accesPlus(req, env) {
  if (await autorise(req, env)) return true;
  const u = await utilisateur(req, env);
  return !!u && abonne(u);
}
// 380 : administrateur = clé privée (Lab, workers.dev) ou compte « admin » : seul à voir les sections internes
export async function accesAdmin(req, env) {
  if (await autorise(req, env)) return true;
  return estAdmin(await utilisateur(req, env));
}
async function reserve(req, chemin, env) {
  const admin = chemin !== '/site.json' && await accesAdmin(req, env);
  const plus = admin || await accesPlus(req, env);
  // /donnees.json complet (avec les sections internes) : administrateur seulement ; un abonné reçoit site.json
  const f = chemin === '/site_admin.json' ? (admin ? 'site_admin.json' : null)
    : !plus ? 'site_libre.json' : (chemin === '/donnees.json' && !admin ? 'site.json' : RESERVES[chemin]);
  if (!f) return new Response('Page introuvable.', { status: 404, headers: SECURITE });
  const h = { ...SECURITE, 'Content-Type': TYPES.json, 'Cache-Control': 'private, no-store', Vary: 'Cookie', 'X-Acces': plus ? 'plus' : 'libre' };
  const o = await depuisR2(env, 'site/algo/' + f);
  if (o) return new Response(req.method === 'HEAD' ? null : o.body, { headers: h });
  if (plus) {
    const r = await fetch(ORIGINE + f, { cf: { cacheTtl: 60, cacheEverything: true } });
    if (r.ok) return new Response(r.body, { headers: h });
  }
  return new Response('Indisponible, réessayer dans un instant.', { status: 503, headers: SECURITE });
}

export async function publique(req, chemin, env) {
  if (chemin in RESERVES) return reserve(req, chemin, env);
  const f = PUBLICS[chemin] || (POLICES.test(chemin) || EMPREINTES.test(chemin) ? chemin.slice(1) : null);
  if (!f) return new Response('Page introuvable.', { status: 404, headers: SECURITE });
  const ext = f.split('.').pop(), fixe = ext === 'woff2' || ext === 'png', immuable = EMPREINTES.test(chemin);
  const type = TYPES[ext] || 'text/html; charset=utf-8';
  const h = { ...SECURITE, 'Content-Type': type,
    'Cache-Control': immuable ? 'public, max-age=31536000, immutable' : f === 'sw.js' ? 'no-cache' : fixe ? 'public, max-age=604800' : 'public, max-age=60' };
  if (type.startsWith('text/html')) h['Content-Security-Policy'] = CSP;
  // 334 : R2 d'abord (site/algo/, publié par pages.yml), GitHub Pages en secours
  const o = await depuisR2(env, 'site/algo/' + f);
  if (o) return new Response(req.method === 'HEAD' ? null : o.body, { headers: h });
  const r = await fetch(ORIGINE + f, { cf: { cacheTtl: immuable ? 31536000 : fixe ? 86400 : 60, cacheEverything: true } });
  if (!r.ok) return new Response('Indisponible, réessayer dans un instant.', { status: r.status === 404 ? 404 : 502, headers: SECURITE });
  return new Response(r.body, { headers: h });
}

// ------------------------------------------------------------------ 334 : site privé (Lab, tableau)
export const MARQUES = new Set(['gamesetalgo.com', 'www.gamesetalgo.com']);
const TYPES_PRIVES = { html: 'text/html; charset=utf-8', js: 'text/javascript; charset=utf-8', css: 'text/css; charset=utf-8',
  json: 'application/json; charset=utf-8', csv: 'text/csv; charset=utf-8', txt: 'text/plain; charset=utf-8',
  md: 'text/plain; charset=utf-8', svg: 'image/svg+xml', png: 'image/png', jpg: 'image/jpeg', ico: 'image/x-icon',
  gz: 'application/gzip', webmanifest: 'application/manifest+json', woff2: 'font/woff2' };
const ENTETES_PRIVES = { 'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer', 'X-Frame-Options': 'SAMEORIGIN',
  'X-Robots-Tag': 'noindex, nofollow', 'Cache-Control': 'private, no-store' };
const COOKIE = 'te_acces';

async function jeton(env) {
  const k = await crypto.subtle.importKey('raw', new TextEncoder().encode(String(env.CLE_PRIVEE)), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const sig = new Uint8Array(await crypto.subtle.sign('HMAC', k, new TextEncoder().encode('acces-site-prive-v1')));
  return btoa(String.fromCharCode(...sig)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function lireCookie(req, nom) {
  for (const p of (req.headers.get('Cookie') || '').split(';')) {
    const i = p.indexOf('=');
    if (i > 0 && p.slice(0, i).trim() === nom) return p.slice(i + 1).trim();
  }
  return '';
}
export async function autorise(req, env) {
  if (!env.CLE_PRIVEE || String(env.CLE_PRIVEE).length < 24) return false;
  if (egal(req.headers.get('X-Cle'), env.CLE_PRIVEE)) return true;
  const c = lireCookie(req, COOKIE);
  return !!c && egal(c, await jeton(env));
}
function suiteSure(s) {
  return /^\/(lab|tableau)\/[A-Za-z0-9_\-./]*$/.test(s || '') && !String(s).includes('..') ? s : '/lab/';
}
function pageConnexion(suite, erreur) {
  const e = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  return `<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex"><title>Accès privé</title><style>body{font:16px system-ui,sans-serif;background:#0e0a24;color:#f4f1ff;
display:grid;place-items:center;min-height:100vh;margin:0}form{background:#1b1342;padding:24px;border-radius:16px;width:min(340px,90vw)}
input,button{width:100%;box-sizing:border-box;font:inherit;padding:12px;border-radius:10px;border:1px solid #443a7a;margin-top:10px}
input{background:#0e0a24;color:#f4f1ff}button{background:#2ee6ff;color:#0e0a24;font-weight:700;border:0}p{color:#ff4fae;margin:10px 0 0}</style></head>
<body><form method="post" action="/connexion"><b>Accès privé</b><input type="hidden" name="suite" value="${e(suite)}">
<input type="password" name="cle" autocomplete="current-password" placeholder="Clé" required autofocus>
<button type="submit">Entrer</button>${erreur ? '<p>Clé refusée.</p>' : ''}</form></body></html>`;
}
export async function connexion(req, env, url) {
  const h = { ...ENTETES_PRIVES, 'Content-Type': 'text/html; charset=utf-8',
    'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'" };
  if (!env.CLE_PRIVEE || String(env.CLE_PRIVEE).length < 24) return new Response('Accès privé fermé (clé non configurée).', { status: 503, headers: h });
  if (req.method === 'POST') {
    let cle = '', suite = '/lab/';
    try { const f = await req.formData(); cle = String(f.get('cle') || ''); suite = suiteSure(String(f.get('suite') || '')); } catch (e) { /* vide */ }
    if (!egal(cle, env.CLE_PRIVEE)) return new Response(pageConnexion(suite, true), { status: 401, headers: h });
    return new Response(null, { status: 303, headers: { ...ENTETES_PRIVES, Location: suite,
      'Set-Cookie': `${COOKIE}=${await jeton(env)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=31536000` } });
  }
  return new Response(pageConnexion(suiteSure(url.searchParams.get('suite')), false), { headers: h });
}
export async function sitePrive(req, env, url) {
  const p = url.pathname;
  if (p === '/deconnexion') return new Response(null, { status: 303, headers: { ...ENTETES_PRIVES, Location: '/connexion',
    'Set-Cookie': `${COOKIE}=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0` } });
  if (p === '/lab' || p === '/tableau') return new Response(null, { status: 301, headers: { ...ENTETES_PRIVES, Location: p + '/' } });
  if (req.method !== 'GET' && req.method !== 'HEAD') return new Response(null, { status: 405, headers: ENTETES_PRIVES });
  if (!(await autorise(req, env))) {
    const nav = (req.headers.get('Accept') || '').includes('text/html');
    return nav ? new Response(null, { status: 303, headers: { ...ENTETES_PRIVES, Location: '/connexion?suite=' + encodeURIComponent(p) } })
      : new Response('Connexion requise.', { status: 401, headers: ENTETES_PRIVES });
  }
  let rel = p.startsWith('/lab/') ? 'Tennis_Edge_Lab/' + p.slice(5) : p.slice('/tableau/'.length);
  if (rel === '' || rel.endsWith('/')) rel += 'index.html';
  let nom;
  try { nom = decodeURIComponent(rel); } catch (e) { return new Response('Inconnu.', { status: 404, headers: ENTETES_PRIVES }); }
  if (nom.split('/').some(x => x === '..' || x === '.') || nom.includes('\\')) return new Response('Inconnu.', { status: 404, headers: ENTETES_PRIVES });
  const o = await depuisR2(env, 'prive/site/' + nom, 0);
  if (!o) return new Response('Absent.', { status: 404, headers: ENTETES_PRIVES });
  const ext = nom.includes('.') ? nom.split('.').pop().toLowerCase() : '';
  return new Response(req.method === 'HEAD' ? null : o.body,
    { headers: { ...ENTETES_PRIVES, 'Content-Type': TYPES_PRIVES[ext] || 'application/octet-stream' } });
}


// V9.3 : passerelle 3D résiliente. Les trois ressources sont publiques et explicitement autorisées.
// Les CDN ne sont contactés que côté Worker : aucune dépendance externe dans la CSP du navigateur.
export const VENDOR_3D = Object.freeze({
  '/vendor/babylon.js': { type: 'application/javascript; charset=utf-8', min: 100000,
    sources: ['https://cdn.jsdelivr.net/npm/babylonjs@7.54.3/babylon.js',
      'https://unpkg.com/babylonjs@7.54.3/babylon.js'] },
  '/vendor/babylonjs.loaders.min.js': { type: 'application/javascript; charset=utf-8', min: 10000,
    sources: ['https://cdn.jsdelivr.net/npm/babylonjs-loaders@7.54.3/babylonjs.loaders.min.js',
      'https://unpkg.com/babylonjs-loaders@7.54.3/babylonjs.loaders.min.js'] },
  '/vendor/Soldier.glb': { type: 'model/gltf-binary', min: 10000,
    sources: ['https://raw.githubusercontent.com/mrdoob/three.js/r164/examples/models/gltf/Soldier.glb'] },
});
// 13/11/2026 (paquet 264) : les modèles des joueurs 3D (CC0, préparés par scripts/modeles_joueurs.py), servis
// depuis la copie GitHub Pages du site et rien d'autre ; gardés 1 jour (le nom de fichier change avec la version).
export const MODELES = Object.freeze({ '/modeles/joueurs3d.bin': { type: 'application/octet-stream', min: 100000 } });
export async function modele(req, pathname, env) {
  const cfg = MODELES[pathname];
  if (req.method !== 'GET' && req.method !== 'HEAD') return new Response(null, { status: 405, headers: SECURITE });
  // 334 : R2 d'abord (site/algo/modeles/…, publié par pages.yml ; toujours la dernière version publiée)
  const o = await depuisR2(env, 'site/algo' + pathname, cfg.min);
  if (o) return new Response(req.method === 'HEAD' ? null : o.body, { headers: { ...SECURITE, 'Content-Type': cfg.type,
    'Cache-Control': 'public, max-age=86400', 'Cross-Origin-Resource-Policy': 'same-origin' } });
  try {
    // 18/11/2026 (paquet 282) : seules les réponses réussies sont gardées un jour ; une absence (404) n'est jamais
    // mise en cache, sinon le fichier enfin publié resterait invisible jusqu'au lendemain
    // 283 : « ?v=283 » change la clé du cache de Cloudflare, qui gardait l'ancienne réponse « absent » (404) jusqu'à un jour
    // 328 : la version demandée par la page (« ?v=326 ») devient la clé du cache ; sans version, l'ancienne clé 283
    const v = (new URL(req.url).search.match(/^\?v=(\d{1,6})$/) || [])[1] || '283';
    const r = await fetch(ORIGINE + pathname.slice(1) + '?v=' + v, { cf: { cacheTtlByStatus: { '200-299': 86400, '404': 0, '500-599': 0 }, cacheEverything: true } });
    const n = Number(r.headers.get('content-length')) || 0;
    if (r.ok && !(n && n < cfg.min) && !(r.headers.get('content-type') || '').includes('text/html'))
      return new Response(req.method === 'HEAD' ? null : r.body, { headers: { ...SECURITE, 'Content-Type': cfg.type,
        'Cache-Control': 'public, max-age=86400', 'Cross-Origin-Resource-Policy': 'same-origin' } });
    if (r.body) await r.body.cancel();
  } catch (e) { /* plus bas */ }
  return new Response('Modèle indisponible.', { status: 502, headers: { ...SECURITE, 'Cache-Control': 'no-store' } });
}
const VENDOR_CACHE_SECONDS = 300;
function vendorSources(pathname) {
  const name = pathname.slice('/vendor/'.length);
  return [ORIGINE + 'vendor/' + name, ...VENDOR_3D[pathname].sources];
}
async function vendorFetch(source, method = 'GET') {
  // Aucun cache forcé pour les erreurs Pages : un 404 ancien ne doit pas bloquer la correction.
  return fetch(source, { method, redirect: 'follow', headers: { Accept: '*/*' } });
}
export async function vendor3D(req, pathname, env) {
  const cfg = VENDOR_3D[pathname];
  if (!cfg) return new Response('Ressource inconnue.', { status: 404, headers: SECURITE });
  if (req.method !== 'GET' && req.method !== 'HEAD')
    return new Response(null, { status: 405, headers: SECURITE });
  // 334 : R2 d'abord (site/algo/vendor/…, publié par pages.yml)
  const o = await depuisR2(env, 'site/algo' + pathname, cfg.min);
  if (o) return new Response(req.method === 'HEAD' ? null : o.body, { status: 200, headers: { ...SECURITE, 'Content-Type': cfg.type,
    'Cache-Control': `public, max-age=${VENDOR_CACHE_SECONDS}`, 'Cross-Origin-Resource-Policy': 'same-origin',
    'X-Tennis-3D-Source': 'r2', 'X-Tennis-3D-Version': '9.3' } });
  const attempts = [];
  for (const [i, source] of vendorSources(pathname).entries()) {
    try {
      // GET même pour HEAD : certains hébergeurs ne gèrent pas HEAD comme GET.
      const upstream = await vendorFetch(source);
      const length = Number(upstream.headers.get('content-length')) || 0;
      const contentType = (upstream.headers.get('content-type') || '').toLowerCase();
      if (!upstream.ok || contentType.includes('text/html') || (length && length < cfg.min)) {
        attempts.push(`${i === 0 ? 'pages' : 'secours'+i}:${upstream.status}`);
        if (upstream.body) await upstream.body.cancel();
        continue;
      }
      const headers = { ...SECURITE, 'Content-Type': cfg.type,
        'Cache-Control': `public, max-age=${VENDOR_CACHE_SECONDS}`,
        'Cross-Origin-Resource-Policy': 'same-origin',
        'X-Tennis-3D-Source': i === 0 ? 'github-pages' : `fallback-${i}`,
        'X-Tennis-3D-Version': '9.3' };
      return new Response(req.method === 'HEAD' ? null : upstream.body,
        { status: 200, headers });
    } catch (err) { attempts.push(`${i === 0 ? 'pages' : 'secours'+i}:network`); }
  }
  return new Response('Ressource 3D indisponible. ' + attempts.join(', '), {
    status: 502, headers: { ...SECURITE, 'Content-Type': 'text/plain; charset=utf-8',
      'Cache-Control': 'no-store', 'X-Tennis-3D-Version': '9.3' },
  });
}
// Diagnostic léger : teste l'accessibilité des sources sans télécharger les modèles complets.
export async function vendorStatus(req) {
  if (req.method !== 'GET' && req.method !== 'HEAD')
    return new Response(null, { status: 405, headers: SECURITE });
  const results = {};
  for (const pathname of Object.keys(VENDOR_3D)) {
    const attempts = [];
    for (const [i, source] of vendorSources(pathname).entries()) {
      try {
        const r = await vendorFetch(source, 'HEAD');
        attempts.push({ source: i === 0 ? 'github-pages' : `fallback-${i}`,
          status: r.status, type: r.headers.get('content-type') || null,
          bytes: r.headers.get('content-length') || null });
        if (r.body) await r.body.cancel();
      } catch (_) { attempts.push({ source: i === 0 ? 'github-pages' : `fallback-${i}`, status: 'network-error' }); }
    }
    results[pathname] = attempts;
  }
  return new Response(req.method === 'HEAD' ? null : JSON.stringify({ ok: true, version: '9.3', files: results }), {
    headers: { ...SECURITE, 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' },
  });
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
  // 20/11/2026 (paquet 308) : mode « resume » → workflow « Vidéo — résumé 3D d'un match terminé » (video_resume.yml)
  const resume = corps.mode === 'resume';
  const r = await fetch(`https://api.github.com/repos/${DEPOT}/actions/workflows/${resume ? 'video_resume.yml' : 'video_simulation.yml'}/dispatches`, {
    method: 'POST',
    headers: { Accept: 'application/vnd.github+json', Authorization: `Bearer ${env.GH_TOKEN}`,
               'X-GitHub-Api-Version': '2022-11-28', 'User-Agent': 'tennis-edge-algo', 'Content-Type': 'application/json' },
    body: JSON.stringify({ ref: 'main', inputs: resume ? { uid } : { uid, adresse: 'false', seed: '' } }),
  });
  if (r.status !== 204) return rep(502, { ok: false, message: `GitHub a refusé (HTTP ${r.status}).` });
  if (env.COFFRE) await env.COFFRE.put('prive/video_derniere_demande.json', JSON.stringify({ t: Date.now(), uid }));
  return rep(202, { ok: true, message: resume ? 'Résumé lancé : il arrive sur ton Telegram privé dans 20 à 40 minutes.'
                                              : 'Vidéo lancée : elle arrive sur ton Telegram privé dans 5 à 10 minutes.' });
}

// 4. SCORES EN DIRECT (06/11/2026, demande de Lucas) : GET /live → les matchs de simple en cours (TennisApi,
//    /api/tennis/events/live), compactés : score par set, points du jeu, serveur. Une seule requête TennisApi par
//    période de fraîcheur, quel que soit le nombre de visiteurs : réponse gardée en mémoire et au coffre R2 (le cache
//    HTTP de Cloudflare ne marche pas sur *.workers.dev). Clé : secret RAPIDAPI_KEY du worker, jamais exposée.
//    Aucune cote, aucun pronostic : la page relie elle-même les matchs à ses % figés.
// 13/11/2026 (paquet 256, demande de Lucas : « en direct », 2 ou 3 s si ça rentre dans la limite) : fraîcheur
//    ADAPTÉE AU QUOTA au lieu de 30 s fixes. Chaque réponse TennisApi donne le quota restant du jour et le délai
//    avant renouvellement (en-têtes x-ratelimit-requests-remaining / -reset). On garde LIVE_RESERVE requêtes
//    (3 000 par défaut : collecte habituelle ≈ 1 000 par jour + réserve de 1 500 des feuilles de match) et on étale
//    le reste jusqu'au renouvellement : fraîcheur = délai restant ÷ (restant − réserve), bornée à [3 s ; 60 s].
//    Consommation relevée du 06 au 13/11 : 800 à 1 800 requêtes par jour sur 15 000 → 3 s presque toute la
//    journée ; si le direct est très regardé, la fraîcheur s'allonge seule et la collecte n'est jamais privée.
//    Statistiques et point par point : en plus de leur plafond, elles s'arrêtent dès que le quota lu passe sous la
//    réserve (le dernier relevé fait foi ; il se remet à jour à chaque réponse de TennisApi).
//    Retrait : remettre LIVE_TTL_MIN_MS à 30 s (ou LIVE_RESERVE très haut dans wrangler.toml).
const HOTE_TENNIS = 'tennisapi1.p.rapidapi.com';
export const LIVE_TTL_MS = 10 * 1000;          // quota inconnu (en-têtes absents) : 10 s
export const LIVE_TTL_MIN_MS = 3 * 1000;
export const LIVE_TTL_MAX_MS = 60 * 1000;
// Dernier quota TennisApi lu (scores ou fiches) : les statistiques et le point par point s'arrêtent aussi sous la réserve.
export const QUOTA_VU = { restant: NaN };
function lireQuota(r) {
  const v = r && r.headers && r.headers.get('x-ratelimit-requests-remaining');
  if (v != null && v !== '' && Number.isFinite(Number(v))) QUOTA_VU.restant = Number(v);
}
const reserveLive = env => { const x = parseInt(env.LIVE_RESERVE, 10); return Number.isFinite(x) ? x : 3000; };
export function fraicheurLive(restant, resetS, reserve = 3000) {
  if (!Number.isFinite(restant) || !Number.isFinite(resetS) || resetS < 0) return LIVE_TTL_MS;
  const dispo = restant - reserve;
  if (dispo <= 0) return LIVE_TTL_MAX_MS;
  return Math.min(LIVE_TTL_MAX_MS, Math.max(LIVE_TTL_MIN_MS, Math.round(resetS * 1000 / dispo)));
}
const LIVE_R2 = 'live/en_cours.json';
let LIVE_MEMOIRE = null;
export const viderLiveMemoire = () => { LIVE_MEMOIRE = null; };   // tests

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

// 23/11/2026 (paquet 388, Lucas : « trouver les résultats dès la fin du match ») — MATCHS TERMINÉS : un match qui
// disparaît du flux en direct est vérifié une fois (/api/tennis/event/{id}, 1 requête) ; s'il est fini, son score final
// et son vainqueur sont gardés 36 h et renvoyés avec le direct (« termines »). La page les affiche aussitôt, sans
// attendre la résolution des résultats de la chaîne (toutes les 2 h). 6 vérifications au plus par rafraîchissement ;
// les autres attendent le suivant (3 essais au plus par match).
export const TERMINES_H = 36, TERMINES_MAX = 800, VERIFS_MAX = 6;
export function finDeMatch(e) {
  if (!e || !e.id) return null;
  const st = e.status || {}, type = st.type || null;
  if (type !== 'finished') return null;
  const [x] = compacterLive([e]);
  if (!x) return null;
  return { ...x, gagnant: e.winnerCode === 1 ? 'home' : e.winnerCode === 2 ? 'away' : null, fin: Date.now() };
}
export async function suivreTermines(env, avant, apres, demander) {
  const maintenant = Date.now(), ids = new Set((apres.matchs || []).map(x => x.id));
  const doc = { termines: (avant && avant.termines) || [], a_verifier: (avant && avant.a_verifier) || [] };
  doc.termines = doc.termines.filter(x => maintenant - (x.fin || 0) < TERMINES_H * 3600e3).slice(-TERMINES_MAX);
  const connus = new Set(doc.termines.map(x => x.id));
  const attente = new Map((doc.a_verifier || []).filter(x => !ids.has(x.id) && !connus.has(x.id)).map(x => [x.id, x]));
  for (const x of (avant && avant.matchs) || []) if (!ids.has(x.id) && !connus.has(x.id) && !attente.has(x.id)) attente.set(x.id, { id: x.id, essais: 0 });
  let n = 0;
  for (const v of attente.values()) {
    if (n >= VERIFS_MAX) break;
    n++; v.essais = (v.essais || 0) + 1;
    try {
      const e = await demander(v.id);
      const f = finDeMatch(e);
      if (f) { doc.termines.push(f); attente.delete(v.id); }
      else if (e && e.status && ['canceled', 'postponed', 'notstarted'].includes(e.status.type)) attente.delete(v.id);
    } catch (err) { /* réessayé au rafraîchissement suivant */ }
    if (attente.has(v.id) && v.essais >= 3) attente.delete(v.id);
  }
  doc.a_verifier = [...attente.values()];
  return doc;
}

// /live : le direct seul (appelé toutes les 3 s) ; /live/termines : les matchs terminés seuls (la page les lit à
// l'ouverture puis toutes les 30 s) — la liste des terminés ne pèse pas sur chaque rafraîchissement du direct.
export async function live(req, env, vue = 'direct') {
  const h = { ...SECURITE, 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': `public, max-age=${vue === 'termines' ? 20 : 2}` };
  const rep = o => new Response(JSON.stringify(vue === 'termines' ? { ok: o.ok, maj: o.maj, termines: o.termines || [] }
    : { ...o, termines: undefined, a_verifier: undefined }), { headers: h });
  const frais = o => o && Date.now() - (o.maj || 0) < (o.ttl || LIVE_TTL_MS);
  if (frais(LIVE_MEMOIRE)) return rep(LIVE_MEMOIRE);
  if (vue === 'termines') {                       // jamais de requête TennisApi : la liste tenue par le direct
    let doc = LIVE_MEMOIRE;
    if (env.COFFRE) { try { const obj = await env.COFFRE.get(LIVE_R2); if (obj) { const o2 = JSON.parse(await obj.text()); if (!doc || (o2.maj || 0) > (doc.maj || 0)) doc = o2; } } catch (e) { /* mémoire */ } }
    return rep(doc || { ok: false, maj: Date.now(), termines: [] });
  }
  let avant = LIVE_MEMOIRE;
  if (env.COFFRE) {
    try {
      const obj = await env.COFFRE.get(LIVE_R2);
      if (obj) { const o = JSON.parse(await obj.text()); if (frais(o)) { LIVE_MEMOIRE = o; return rep(o); } if (!avant || (o.maj || 0) > (avant.maj || 0)) avant = o; }
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
      const en = k => { const v = r.headers && r.headers.get(k); return v == null || v === '' ? NaN : Number(v); };
      lireQuota(r);
      const ttl = fraicheurLive(en('x-ratelimit-requests-remaining'), en('x-ratelimit-requests-reset'), reserveLive(env));
      o = r.ok ? { ok: true, maj: Date.now(), ttl, brut: ev.length, matchs: compacterLive(ev) }
               : { ok: false, maj: Date.now(), ttl: LIVE_TTL_MAX_MS, message: `TennisApi : HTTP ${r.status}`, matchs: [] };
      if (o.ok) {
        const demander = async (id) => {
          const rr = await fetch(`https://${HOTE_TENNIS}/api/tennis/event/${id}`, {
            headers: { 'X-RapidAPI-Key': env.RAPIDAPI_KEY, 'X-RapidAPI-Host': HOTE_TENNIS, Accept: 'application/json' } });
          lireQuota(rr);
          return rr.ok ? ((await rr.json()) || {}).event || null : null;
        };
        Object.assign(o, await suivreTermines(env, avant, o, demander));
      }
    } catch (e) {
      o = { ok: false, maj: Date.now(), ttl: LIVE_TTL_MS, message: 'TennisApi injoignable.', matchs: [] };
    }
  }
  if (!o.termines && avant) { o.termines = avant.termines || []; o.a_verifier = avant.a_verifier || []; }   // panne : rien de perdu
  o.termines = o.termines || [];
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

// 24/11/2026 (paquet 411, Lucas : « toutes les statistiques après le match ») — un match TERMINÉ (dans la liste des
// terminés tenue par /live) a une feuille définitive : la première réponse complète est gardée 24 h (une seule requête
// TennisApi par match terminé, quel que soit le nombre de visiteurs), marquée final: true.
export const STATS_FINAL_TTL_MS = 24 * 3600 * 1000;
async function estTermine(env, id) {
  const dans = o => !!(o && Array.isArray(o.termines) && o.termines.some(x => String(x.id) === String(id)));
  if (dans(LIVE_MEMOIRE)) return true;
  if (!env.COFFRE) return false;
  try { const o = await env.COFFRE.get(LIVE_R2); return o ? dans(JSON.parse(await o.text())) : false; } catch (e) { return false; }
}
export const ttlDetail = (genre, connu) => connu && connu.final ? STATS_FINAL_TTL_MS : (genre === 'points' ? 30 * 1000 : STATS_TTL_MS);
async function liveDetail(req, env, url, genre) {
  const D = DETAILS[genre];
  const h = { ...SECURITE, 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'public, max-age=30' };
  const rep = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: h });
  const id = url.searchParams.get('id') || '';
  if (!/^\d{1,12}$/.test(id)) return rep({ ok: false, message: 'id invalide' }, 400);
  const cleR2 = `live/${genre}/${id}.json`, cleM = `${genre}:${id}`;
  // 06/11/2026 (paquet 215) : le point par point de la fiche ouverte se rafraîchit toutes les 30 s (stats : 60 s)
  let connu = STATS_MEMOIRE.get(cleM) || null;
  if (connu && Date.now() - connu.maj < ttlDetail(genre, connu)) return rep(connu);
  if (env.COFFRE) {
    try { const o = await env.COFFRE.get(cleR2); if (o) { const x = JSON.parse(await o.text()); if (!connu || x.maj > connu.maj) connu = x; } } catch (e) { /* rien */ }
    if (connu && Date.now() - connu.maj < ttlDetail(genre, connu)) { STATS_MEMOIRE.set(cleM, connu); return rep(connu); }
  }
  const plafond = parseInt(env.LIVE_STATS_PLAFOND, 10) || 6000;
  const { cle } = await compter(env);
  if (COMPTEUR.n >= plafond || QUOTA_VU.restant <= reserveLive(env))
    return rep({ ...(connu || { ok: false, [D.champ]: null }), plafond: true });
  if (!env.RAPIDAPI_KEY) return rep({ ok: false, message: 'clé TennisApi absente', [D.champ]: null });
  let o;
  try {
    COMPTEUR.n++;
    if (env.COFFRE) { try { await env.COFFRE.put(cle, JSON.stringify({ n: COMPTEUR.n })); } catch (e) { /* mémoire seule */ } }
    const r = await fetch(`https://${HOTE_TENNIS}${D.chemin(id)}`, {
      headers: { 'X-RapidAPI-Key': env.RAPIDAPI_KEY, 'X-RapidAPI-Host': HOTE_TENNIS, Accept: 'application/json' } });
    lireQuota(r);
    o = r.ok ? { ok: true, id: +id, maj: Date.now(), [D.champ]: D.compacter(await r.json()) }
      // 404 = pas encore de données (début de match) : on le garde 60 s comme une réponse normale
             : { ok: r.status === 404, id: +id, maj: Date.now(), [D.champ]: connu ? connu[D.champ] : null, message: `TennisApi : HTTP ${r.status}` };
  } catch (e) {
    o = { ok: false, id: +id, maj: Date.now(), [D.champ]: connu ? connu[D.champ] : null, message: 'TennisApi injoignable.' };
  }
  if (o.ok && o[D.champ] && await estTermine(env, id)) o.final = true;       // 411 : feuille définitive
  STATS_MEMOIRE.set(cleM, o);
  if (STATS_MEMOIRE.size > 300) STATS_MEMOIRE.delete(STATS_MEMOIRE.keys().next().value);
  if (env.COFFRE) { try { await env.COFFRE.put(cleR2, JSON.stringify(o)); } catch (e) { /* mémoire seule */ } }
  return rep(o);
}
export const liveStats = (req, env, url) => liveDetail(req, env, url, 'stats');
export const livePoints = (req, env, url) => liveDetail(req, env, url, 'points');

export default {
  // 386 : chaque jour (wrangler.toml, [triggers]) : rappels de fin d'accès payé, totaux des visites de la veille
  async scheduled(event, env, ctx) { ctx.waitUntil(quotidien(env)); },
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    // 386 : entonnoir privé — une ouverture de la page publique (site.json) sur gamesetalgo.com, sans cookie
    if (url.pathname === '/site.json' && req.method === 'GET' && MARQUES.has(url.hostname) && ctx && ctx.waitUntil)
      ctx.waitUntil(compterVisite(req, env).catch(() => {}));
    if (url.pathname === '/vendor/status') return vendorStatus(req);
    if (url.pathname in VENDOR_3D) return vendor3D(req, url.pathname, env);
    if (url.pathname in MODELES) return modele(req, url.pathname, env);
    if (url.pathname === '/live/stats') return liveStats(req, env, url);
    if (url.pathname === '/live/points') return livePoints(req, env, url);
    if (url.pathname === '/live') return live(req, env);
    if (url.pathname === '/live/termines') return live(req, env, 'termines');
    if (url.pathname === '/video') return video(req, env);
    if (url.pathname.startsWith('/prive/')) return prive(req, env, decodeURIComponent(url.pathname.slice(7)));
    if (url.pathname.startsWith('/compte/api/')) return apiCompte(req, env, url, await autorise(req, env));
    if (url.pathname === '/compte/admin' || url.pathname.startsWith('/compte/admin/')) {
      // 377 : jamais sur gamesetalgo.com ; clé privée exigée (cookie du Lab ou en-tête X-Cle)
      if (MARQUES.has(url.hostname)) return new Response('Page introuvable.', { status: 404, headers: SECURITE });
      if (!(await autorise(req, env))) return new Response(null, { status: 303, headers: { ...ENTETES_PRIVES, Location: '/connexion?suite=' + encodeURIComponent('/lab/') } });
      return adminComptes(req, env, url);
    }
    // 334 : site privé, seulement hors de gamesetalgo.com (adresse workers.dev)
    if (!MARQUES.has(url.hostname)) {
      if (url.pathname === '/connexion') return connexion(req, env, url);
      if (url.pathname === '/deconnexion' || url.pathname === '/lab' || url.pathname === '/tableau'
        || url.pathname.startsWith('/lab/') || url.pathname.startsWith('/tableau/')) return sitePrive(req, env, url);
    }
    if (req.method !== 'GET' && req.method !== 'HEAD') return new Response(null, { status: 405, headers: SECURITE });
    return publique(req, url.pathname, env);
  },
};
