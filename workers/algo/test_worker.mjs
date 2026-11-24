// Worker « algo » (23/10/2026) : coffre fermé sans la clé, site public servi, liste alignée sur coffre.py.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import worker, { PRIVES } from './worker.js';

const CLE = 'k'.repeat(40);
const coffre = { 'prive/h19_signal_log.jsonl': '{"a":1}\n' };
const env = { CLE_PRIVEE: CLE, COFFRE: { get: async (k) => (k in coffre ? { body: coffre[k] } : null) } };
const req = (chemin, h = {}, method = 'GET') => new Request('https://algo.tennis-edge.workers.dev' + chemin, { method, headers: h });

test('coffre : sans clé ou mauvaise clé → 401, rien ne sort', async () => {
  for (const h of [{}, { 'X-Cle': 'mauvaise' }, { 'X-Cle': CLE + 'x' }]) {
    const r = await worker.fetch(req('/prive/h19_signal_log.jsonl', h), env);
    assert.equal(r.status, 401);
    assert.ok(!(await r.text()).includes('"a"'));
  }
});

test('coffre : bonne clé → fichier, jamais en cache public', async () => {
  const r = await worker.fetch(req('/prive/h19_signal_log.jsonl', { 'X-Cle': CLE, Origin: 'https://lucas987987.github.io' }), env);
  assert.equal(r.status, 200);
  assert.equal(await r.text(), '{"a":1}\n');
  assert.match(r.headers.get('Cache-Control'), /no-store/);
  assert.equal(r.headers.get('Access-Control-Allow-Origin'), 'https://lucas987987.github.io');
});

test('coffre : autre origine que le Lab → pas d’autorisation CORS ; nom hors liste → 404 ; clé courte → fermé', async () => {
  const r = await worker.fetch(req('/prive/h19_signal_log.jsonl', { 'X-Cle': CLE, Origin: 'https://exemple.com' }), env);
  assert.equal(r.headers.get('Access-Control-Allow-Origin'), null);
  assert.equal((await worker.fetch(req('/prive/..%2F.env', { 'X-Cle': CLE }), env)).status, 404);
  assert.equal((await worker.fetch(req('/prive/h19_signal_log.jsonl', { 'X-Cle': 'court' }), { ...env, CLE_PRIVEE: 'court' })).status, 503);
});

test('site public : page et données relues sur GitHub Pages, le reste → 404', async () => {
  const vus = [];
  globalThis.fetch = async (u) => { vus.push(u); return new Response('<!doctype html>ok', { status: 200 }); };
  const r = await worker.fetch(req('/'), env);
  assert.equal(r.status, 200);
  assert.match(r.headers.get('Content-Security-Policy'), /frame-ancestors 'none'/);
  // 377 : données complètes réservées — sans accès et sans copie R2, jamais de secours GitHub (503) ; avec la clé : servies
  assert.equal((await worker.fetch(req('/donnees.json'), env)).status, 503);
  const plein = await worker.fetch(req('/donnees.json', { 'X-Cle': CLE }), env);
  assert.equal(plein.headers.get('Content-Type'), 'application/json; charset=utf-8');
  assert.match(plein.headers.get('Cache-Control'), /no-store/);
  assert.equal((await worker.fetch(req('/Tennis_Edge_Lab/live/pronostics.json'), env)).status, 404);
  assert.deepEqual(vus, ['https://lucas987987.github.io/Tennis-edge/algo/index.html', 'https://lucas987987.github.io/Tennis-edge/algo/donnees.json']);
});

test('liste du coffre identique à scripts/coffre.py', () => {
  const py = fs.readFileSync(new URL('../../scripts/coffre.py', import.meta.url), 'utf8');
  const bloc = py.slice(py.indexOf('GROUPES = {'), py.indexOf("GROUPES['lab_entrees']"));
  const noms = [...bloc.matchAll(/'([^']+\.(?:jsonl|json))'/g)].map((m) => m[1].split('/').pop());
  assert.deepEqual([...new Set(noms)].sort(), [...PRIVES].sort());
});

// 04/11/2026 — vidéo à la demande
const post = (corps, h = {}) => new Request('https://algo.tennis-edge.workers.dev/video',
  { method: 'POST', headers: { 'Content-Type': 'application/json', ...h }, body: JSON.stringify(corps) });
const UID = '2026-11-04_tommy_paul_daniel_merida';

test('vidéo : sans clé → 401 ; sans jeton → 503 ; uid douteux → 400 ; GET → 405', async () => {
  globalThis.fetch = async () => { throw new Error('GitHub ne doit pas être appelé'); };
  assert.equal((await worker.fetch(post({ uid: UID }), { ...env, GH_TOKEN: 't' })).status, 401);
  assert.equal((await worker.fetch(post({ uid: UID }, { 'X-Cle': CLE }), env)).status, 503);
  for (const u of ['../x', '', '2026-11-04_A B', 'rien']) {
    assert.equal((await worker.fetch(post({ uid: u }, { 'X-Cle': CLE }), { ...env, GH_TOKEN: 't' })).status, 400);
  }
  assert.equal((await worker.fetch(req('/video', { 'X-Cle': CLE }), { ...env, GH_TOKEN: 't' })).status, 405);
});

test('vidéo : bonne clé → workflow vidéo lancé pour ce match, puis 3 minutes d’attente', async () => {
  const appels = [], store = {};
  const env2 = { ...env, GH_TOKEN: 'jeton', COFFRE: { get: async (k) => (k in store ? { text: async () => store[k] } : null),
                                                     put: async (k, v) => { store[k] = v; } } };
  globalThis.fetch = async (u, o) => { appels.push([u, JSON.parse(o.body), o.headers.Authorization]); return new Response(null, { status: 204 }); };
  const r = await worker.fetch(post({ uid: UID }, { 'X-Cle': CLE }), env2);
  assert.equal(r.status, 202);
  assert.match(appels[0][0], /actions\/workflows\/video_simulation\.yml\/dispatches$/);
  assert.deepEqual(appels[0][1], { ref: 'main', inputs: { uid: UID, adresse: 'false', seed: '' } });
  assert.equal(appels[0][2], 'Bearer jeton');
  assert.ok(!JSON.stringify(await r.clone().json()).includes('jeton'));
  assert.equal((await worker.fetch(post({ uid: UID }, { 'X-Cle': CLE }), env2)).status, 429);
  assert.equal(appels.length, 1);
});

test('vidéo : mode « resume » → workflow du résumé 3D, seulement l’uid', async () => {
  const appels = [], store = {};
  const env2 = { ...env, GH_TOKEN: 'jeton', COFFRE: { get: async (k) => (k in store ? { text: async () => store[k] } : null),
                                                     put: async (k, v) => { store[k] = v; } } };
  globalThis.fetch = async (u, o) => { appels.push([u, JSON.parse(o.body)]); return new Response(null, { status: 204 }); };
  const r = await worker.fetch(post({ uid: UID, mode: 'resume' }, { 'X-Cle': CLE }), env2);
  assert.equal(r.status, 202);
  assert.match(appels[0][0], /actions\/workflows\/video_resume\.yml\/dispatches$/);
  assert.deepEqual(appels[0][1], { ref: 'main', inputs: { uid: UID } });
  assert.match((await r.json()).message, /Résumé lancé/);
});

// 06/11/2026 — scores en direct
import { compacterLive, live } from './worker.js';
const EV = { id: 7, startTimestamp: 1793990000, tournament: { name: 'Paris', category: { name: 'ATP' } },
  homeTeam: { name: 'Taylor Fritz' }, awayTeam: { name: 'Carlos Alcaraz' }, status: { type: 'inprogress', description: '2nd set' },
  firstToServe: 2, homeScore: { current: 1, period1: 6, period2: 3, point: '30' },
  awayScore: { current: 0, period1: 4, period2: 2, point: '15' } };
const DOUBLE = { ...EV, id: 8, homeTeam: { name: 'A / B', subTeams: [{}] }, awayTeam: { name: 'C / D' } };

test('live : un simple avec « subTeams: [] » (format réel de TennisApi) est gardé', () => {
  const simple = { ...EV, id: 9, homeTeam: { name: 'Kimmer Coppejans', subTeams: [] }, awayTeam: { name: 'Jurij Rodionov', subTeams: [] } };
  const double = { ...EV, id: 10, homeTeam: { name: 'A / B', subTeams: [{ name: 'A' }, { name: 'B' }] }, awayTeam: { name: 'C / D', subTeams: [{}, {}] } };
  assert.deepEqual(compacterLive([simple, double]).map(m => m.id), [9]);
});

test('live : simples seulement, score compacté, serveur', () => {
  const [m, ...reste] = compacterLive([EV, DOUBLE]);
  assert.equal(reste.length, 0);
  assert.deepEqual(m.score_home, { sets: [6, 3], tb: [null, null], gagnes: 1, point: '30' });
  assert.equal(m.serveur, 'away');
  assert.equal(m.statut.type, 'inprogress');
});

test('live : une requête TennisApi pour plusieurs visiteurs, clé jamais renvoyée', async () => {
  let appels = 0;
  const stock = {};
  const envL = { RAPIDAPI_KEY: 'secret-tennis', COFFRE: { get: async k => (k in stock ? { text: async () => stock[k] } : null),
                                                         put: async (k, v) => { stock[k] = v; } } };
  globalThis.fetch = async (u, o) => { appels++; assert.equal(o.headers['X-RapidAPI-Key'], 'secret-tennis');
    return new Response(JSON.stringify({ events: [EV] }), { status: 200 }); };
  const r1 = await worker.fetch(req('/live'), envL);
  const r2 = await worker.fetch(req('/live'), envL);
  const t = await r2.text();
  assert.equal(appels, 1);
  assert.ok(!t.includes('secret-tennis'));
  assert.equal(JSON.parse(t).matchs[0].home, 'Taylor Fritz');
  assert.equal(r1.status, 200);
});

test('live : sans clé → réponse vide expliquée, pas d’erreur', async () => {
  const o = await (await live(req('/live'), {})).json();
  assert.ok(Array.isArray(o.matchs));
});

// 06/11/2026 — statistiques en direct
import { compacterStats } from './worker.js';
const DOC_STATS = { statistics: [
  { period: 'ALL', groups: [{ statisticsItems: [{ key: 'aces', homeValue: 3, awayValue: 1 }, { key: 'firstServeAccuracy', homeValue: 20, homeTotal: 30, awayValue: 18, awayTotal: 25 }] }] },
  { period: '1ST', groups: [{ statisticsItems: [{ key: 'aces', homeValue: 2, awayValue: 0 }] }] }] };

test('stats : période ALL seulement, valeurs et totaux', () => {
  const s = compacterStats(DOC_STATS);
  assert.deepEqual(s.aces, [3, null, 1, null]);
  assert.deepEqual(s.firstServeAccuracy, [20, 30, 18, 25]);
  assert.equal(compacterStats({}), null);
});

test('stats : id douteux → 400 ; une requête par minute et par match ; plafond respecté', async () => {
  let appels = 0; const stock = {};
  const envS = { RAPIDAPI_KEY: 'k', LIVE_STATS_PLAFOND: '2', COFFRE: { get: async k => (k in stock ? { text: async () => stock[k] } : null), put: async (k, v) => { stock[k] = v; } } };
  globalThis.fetch = async (u) => { appels++; assert.match(u, /\/api\/tennis\/event\/\d+\/statistics$/); return new Response(JSON.stringify(DOC_STATS), { status: 200 }); };
  assert.equal((await worker.fetch(req('/live/stats?id=../x'), envS)).status, 400);
  const a = await (await worker.fetch(req('/live/stats?id=11'), envS)).json();
  await worker.fetch(req('/live/stats?id=11'), envS);
  assert.equal(appels, 1);
  assert.equal(a.stats.aces[0], 3);
  await worker.fetch(req('/live/stats?id=12'), envS);
  const c = await (await worker.fetch(req('/live/stats?id=13'), envS)).json();
  assert.equal(appels, 2);
  assert.equal(c.plafond, true);
});

// 06/11/2026 (paquet 210) — point par point en direct
import { compacterPoints } from './worker.js';
test('points : suite des points comme points_match.py, jeu en cours sans vainqueur', () => {
  const doc = { pointByPoint: [{ set: 1, games: [
    { game: 1, score: { serving: 1, scoring: 1 }, points: [{ homePoint: '15', awayPoint: '0' }, { homePoint: '30', awayPoint: '0' }, { homePoint: '40', awayPoint: '0' }] },
    { game: 2, score: { serving: 2, scoring: -1 }, points: [{ homePoint: '0', awayPoint: '15' }, { homePoint: '15', awayPoint: '15' }] }] }] };
  assert.deepEqual(compacterPoints(doc), [[1, 1, 1, 'HHHH', 1], [1, 2, 2, 'AH', null]]);
  assert.equal(compacterPoints({}), null);
});

test('points : /live/points passe par le même cache et le même plafond', async () => {
  let appels = 0; const stock = {};
  const envP = { RAPIDAPI_KEY: 'k', COFFRE: { get: async k => (k in stock ? { text: async () => stock[k] } : null), put: async (k, v) => { stock[k] = v; } } };
  globalThis.fetch = async (u) => { appels++; assert.match(u, /\/point-by-point$/); return new Response(JSON.stringify({ pointByPoint: [] }), { status: 200 }); };
  const o = await (await worker.fetch(req('/live/points?id=77'), envP)).json();
  await worker.fetch(req('/live/points?id=77'), envP);
  assert.equal(appels, 1);
  assert.equal(o.ok, true);
  assert.equal(o.jeux, null);
});

// 13/11/2026 (paquet 256) — fraîcheur du direct adaptée au quota TennisApi du jour
import { fraicheurLive, LIVE_TTL_MS, LIVE_TTL_MIN_MS, LIVE_TTL_MAX_MS } from './worker.js';

test('direct : 3 s quand le quota est large, plus long quand il se resserre, 60 s sous la réserve', () => {
  assert.equal(fraicheurLive(14000, 4 * 3600, 3000), LIVE_TTL_MIN_MS);             // 11 000 dispo sur 4 h → 1,3 s, borné à 3
  assert.equal(fraicheurLive(4000, 20 * 3600, 3000), 60000);                       // 1 000 dispo sur 20 h → 72 s, borné à 60
  assert.equal(fraicheurLive(13000, 24 * 3600, 3000), 8640);                        // 10 000 dispo sur 24 h → 8,64 s
  assert.equal(fraicheurLive(13000, 2 * 3600, 3000), LIVE_TTL_MIN_MS);              // renouvellement proche → 3 s
  assert.equal(fraicheurLive(2500, 3600, 3000), LIVE_TTL_MAX_MS);                   // sous la réserve
  assert.equal(fraicheurLive(NaN, 3600, 3000), LIVE_TTL_MS);                        // en-têtes absents → 10 s
  for (const r of [0, 3001, 5000, 9000, 15000]) for (const s of [0, 60, 3600, 86400]) {
    const t = fraicheurLive(r, s, 3000);
    assert.ok(t >= LIVE_TTL_MIN_MS && t <= LIVE_TTL_MAX_MS);
  }
});

test('direct : le quota ne peut pas descendre sous la réserve à cause du direct', () => {
  // simulation d'une journée de 24 h regardée sans interruption, collecte à part : 1 000 requêtes réparties
  let restant = 15000, t = 0, collecte = 0;
  const FIN = 24 * 3600 * 1000;
  while (t < FIN) {
    restant--;                                                                     // une requête /live
    const pas = fraicheurLive(restant, (FIN - t) / 1000, 3000);
    const c = Math.floor((t + pas) / 86400) - Math.floor(t / 86400);              // ≈ 1 000 par jour
    restant -= c; collecte += c; t += pas;
  }
  assert.ok(collecte >= 990);
  assert.ok(restant >= 1500, `restant ${restant}`);                                // la réserve des feuilles de match tient
});

test('direct : la fraîcheur vient des en-têtes de TennisApi, jamais la clé ni le quota dans la réponse', async () => {
  const stock = {};
  const envL = { RAPIDAPI_KEY: 'secret-tennis', COFFRE: { get: async k => (k in stock ? { text: async () => stock[k] } : null),
                                                         put: async (k, v) => { stock[k] = v; } } };
  const vrai = Date.now; let decal = 0;
  Date.now = () => vrai() + decal;
  try {
    let appels = 0;
    globalThis.fetch = async () => { appels++; return new Response(JSON.stringify({ events: [EV] }), { status: 200,
      headers: { 'x-ratelimit-requests-remaining': '12345', 'x-ratelimit-requests-reset': '3600' } }); };
    decal = 10 * 60 * 1000;                                                        // copie précédente périmée
    const o = await (await worker.fetch(req('/live'), envL)).json();
    assert.equal(appels, 1);
    assert.equal(o.ttl, LIVE_TTL_MIN_MS);
    assert.ok(!JSON.stringify(o).includes('12345') && !JSON.stringify(o).includes('secret-tennis'));
    decal += 2000; await worker.fetch(req('/live'), envL); assert.equal(appels, 1); // 2 s plus tard : même copie
    decal += 1500; await worker.fetch(req('/live'), envL); assert.equal(appels, 2); // 3,5 s : nouvelle requête
  } finally { Date.now = vrai; }
});

test('direct : la page redemande les scores toutes les 3 s', () => {
  const page = fs.readFileSync(new URL('../../algo/index.html', import.meta.url), 'utf-8');
  assert.match(page, /setInterval\(chargerLive, 3000\)/);
});

test('direct : statistiques et point par point s’arrêtent quand le quota lu passe sous la réserve', async () => {
  const { QUOTA_VU } = await import('./worker.js');
  const stock = {};
  const envS = { RAPIDAPI_KEY: 'k', COFFRE: { get: async k => (k in stock ? { text: async () => stock[k] } : null), put: async (k, v) => { stock[k] = v; } } };
  let appels = 0;
  globalThis.fetch = async () => { appels++; return new Response(JSON.stringify(DOC_STATS), { status: 200,
    headers: { 'x-ratelimit-requests-remaining': '2999' } }); };
  const avant = QUOTA_VU.restant;
  try {
    QUOTA_VU.restant = 9000;
    await worker.fetch(req('/live/stats?id=9001'), envS);
    assert.equal(appels, 1);
    assert.equal(QUOTA_VU.restant, 2999);                                          // relu dans la réponse
    const o = await (await worker.fetch(req('/live/stats?id=9002'), envS)).json();
    assert.equal(appels, 1);
    assert.equal(o.plafond, true);
  } finally { QUOTA_VU.restant = avant; }
});


// 13/11/2026 (paquet 264) — modèles des joueurs 3D : servis depuis la copie du site, jamais d'ailleurs
test('modèles 3D : relus sur la copie GitHub Pages du site, binaire, sinon 502', async () => {
  const vus = [];
  globalThis.fetch = async (u) => { vus.push(String(u)); return new Response(new Uint8Array(200000), { status: 200, headers: { 'content-length': '200000', 'content-type': 'application/octet-stream' } }); };
  const r = await worker.fetch(req('/modeles/joueurs3d.bin'), {});
  assert.equal(r.status, 200);
  assert.equal(r.headers.get('content-type'), 'application/octet-stream');
  assert.equal(vus.length, 1);
  assert.ok(vus[0].startsWith('https://lucas987987.github.io/Tennis-edge/algo/modeles/joueurs3d.bin'));
  globalThis.fetch = async () => new Response('<html>404</html>', { status: 404, headers: { 'content-type': 'text/html' } });
  assert.equal((await worker.fetch(req('/modeles/joueurs3d.bin'), {})).status, 502);
  assert.equal((await worker.fetch(req('/modeles/autre.bin'), {})).status, 404);
});

// 21/11/2026 (paquet 328) — site « pro » : données allégées, mentions légales, aperçu, polices locales
test('site léger : site.json, site_plus.json, editeur.json, partage.png et polices servis avec le bon type', async () => {
  const vus = [];
  globalThis.fetch = async (u) => { vus.push(String(u)); return new Response('x', { status: 200 }); };
  assert.equal((await worker.fetch(req('/site.json', { 'X-Cle': CLE }), env)).headers.get('Content-Type'), 'application/json; charset=utf-8');
  const types = { '/site_plus.json': 'application/json; charset=utf-8',
    '/editeur.json': 'application/json; charset=utf-8', '/partage.png': 'image/png', '/polices/barlow-400.woff2': 'font/woff2' };
  for (const [c, t] of Object.entries(types)) {
    const r = await worker.fetch(req(c), env);
    assert.equal(r.status, 200, c);
    assert.equal(r.headers.get('Content-Type'), t, c);
  }
  assert.ok(vus.includes('https://lucas987987.github.io/Tennis-edge/algo/polices/barlow-400.woff2'));
  assert.match((await worker.fetch(req('/polices/barlow-400.woff2'), env)).headers.get('Cache-Control'), /max-age=604800/);
  for (const c of ['/polices/a%2Fb.woff2', '/polices/x.ttf', '/polices/', '/algo/site.json']) assert.equal((await worker.fetch(req(c), env)).status, 404, c);
});

test('CSP : plus aucune police chez Google', async () => {
  globalThis.fetch = async () => new Response('<!doctype html>ok', { status: 200 });
  const csp = (await worker.fetch(req('/'), env)).headers.get('Content-Security-Policy');
  assert.ok(!csp.includes('googleapis') && !csp.includes('gstatic'));
  assert.match(csp, /font-src 'self'/);
});

test('modèles 3D : la version demandée par la page sert de clé de cache', async () => {
  const vus = [];
  globalThis.fetch = async (u) => { vus.push(String(u)); return new Response(new Uint8Array(200000), { status: 200, headers: { 'content-length': '200000', 'content-type': 'application/octet-stream' } }); };
  await worker.fetch(req('/modeles/joueurs3d.bin?v=326'), {});
  await worker.fetch(req('/modeles/joueurs3d.bin?v=abc'), {});
  assert.ok(vus[0].endsWith('joueurs3d.bin?v=326'));
  assert.ok(vus[1].endsWith('joueurs3d.bin?v=283'));
});

// 22/11/2026 (paquet 334) — site servi par R2 d'abord ; Lab et tableau privés, seulement sur workers.dev
const R2 = { 'site/algo/index.html': '<!doctype html>depuis-r2', 'prive/site/Tennis_Edge_Lab/index.html': '<!doctype html>lab-prive',
  'prive/site/Tennis_Edge_Lab/live/data.json': '{"clv":1}', 'prive/site/index.html': '<!doctype html>tableau',
  'site/algo/modeles/joueurs3d.bin': 'x'.repeat(200000) };
const envR2 = { CLE_PRIVEE: CLE, COFFRE: { get: async (k) => (k in R2 ? { body: R2[k], size: R2[k].length } : null) } };
const surMarque = (chemin, h = {}, method = 'GET', body) => new Request('https://gamesetalgo.com' + chemin, { method, headers: h, body });
const surDev = (chemin, h = {}, method = 'GET', body) => new Request('https://algo.tennis-edge.workers.dev' + chemin, { method, headers: h, body });

test('334 : la page publique vient de R2, GitHub Pages seulement en secours', async () => {
  let appels = 0;
  globalThis.fetch = async () => { appels++; return new Response('<!doctype html>pages', { status: 200 }); };
  const r = await worker.fetch(surMarque('/'), envR2);
  assert.equal(await r.text(), '<!doctype html>depuis-r2');
  assert.equal(appels, 0);
  assert.match(r.headers.get('Content-Security-Policy'), /default-src 'self'/);
  const s = await worker.fetch(surMarque('/methode.html'), envR2);
  assert.equal(await s.text(), '<!doctype html>pages');
  assert.equal(appels, 1);
  const m = await worker.fetch(surMarque('/modeles/joueurs3d.bin?v=326'), envR2);
  assert.equal(m.status, 200);
  assert.equal(appels, 1, 'modèle 3D lu dans R2');
});

test('334 : Lab et tableau introuvables sur gamesetalgo.com, même avec la clé', async () => {
  globalThis.fetch = async () => new Response('absent', { status: 404 });
  for (const c of ['/lab/', '/lab/index.html', '/tableau/', '/connexion']) {
    const r = await worker.fetch(surMarque(c, { 'X-Cle': CLE }), envR2);
    assert.equal(r.status, 404, c);
    assert.ok(!(await r.text()).includes('lab-prive'));
  }
});

test('334 : sans connexion, le Lab renvoie vers /connexion et ne livre rien', async () => {
  const r = await worker.fetch(surDev('/lab/', { Accept: 'text/html' }), envR2);
  assert.equal(r.status, 303);
  assert.equal(r.headers.get('Location'), '/connexion?suite=%2Flab%2F');
  const j = await worker.fetch(surDev('/lab/live/data.json'), envR2);
  assert.equal(j.status, 401);
  assert.ok(!(await j.text()).includes('clv'));
  const faux = await worker.fetch(surDev('/lab/', { Cookie: 'te_acces=faux' }), envR2);
  assert.equal(faux.status, 401);
});

test('334 : connexion avec la clé → cookie de session, puis Lab et tableau servis, jamais en cache', async () => {
  const mauvais = await worker.fetch(surDev('/connexion', { 'Content-Type': 'application/x-www-form-urlencoded' }, 'POST', 'cle=mauvaise&suite=%2Flab%2F'), envR2);
  assert.equal(mauvais.status, 401);
  assert.equal(mauvais.headers.get('Set-Cookie'), null);
  const ok = await worker.fetch(surDev('/connexion', { 'Content-Type': 'application/x-www-form-urlencoded' }, 'POST', `cle=${CLE}&suite=%2Flab%2F`), envR2);
  assert.equal(ok.status, 303);
  assert.equal(ok.headers.get('Location'), '/lab/');
  const cookie = ok.headers.get('Set-Cookie');
  assert.match(cookie, /^te_acces=[A-Za-z0-9_-]{20,}; Path=\/; HttpOnly; Secure; SameSite=Lax/);
  assert.ok(!cookie.includes(CLE), 'la clé elle-même ne part jamais dans le cookie');
  const c = { Cookie: cookie.split(';')[0] };
  const lab = await worker.fetch(surDev('/lab/', c), envR2);
  assert.equal(await lab.text(), '<!doctype html>lab-prive');
  assert.equal(lab.headers.get('Cache-Control'), 'private, no-store');
  assert.equal(lab.headers.get('X-Robots-Tag'), 'noindex, nofollow');
  const d = await worker.fetch(surDev('/lab/live/data.json', c), envR2);
  assert.equal(d.headers.get('Content-Type'), 'application/json; charset=utf-8');
  assert.equal(await (await worker.fetch(surDev('/tableau/', c), envR2)).text(), '<!doctype html>tableau');
  const autre = await worker.fetch(surDev('/connexion', { 'Content-Type': 'application/x-www-form-urlencoded' }, 'POST', `cle=${CLE}&suite=https%3A%2F%2Fexemple.com`), envR2);
  assert.equal(autre.headers.get('Location'), '/lab/', 'jamais de redirection vers un autre site');
  const sortie = await worker.fetch(surDev('/deconnexion', c), envR2);
  assert.match(sortie.headers.get('Set-Cookie'), /Max-Age=0/);
});

test('334 : pas de sortie du dossier privé', async () => {
  for (const c of ['/lab/%2e%2e/x', '/lab/a/%2E%2E/%2E%2E/prive/h19_signal_log.jsonl']) {
    const r = await worker.fetch(surDev(c, { 'X-Cle': CLE }), envR2);
    assert.ok([404, 400].includes(r.status), c + ' ' + r.status);
  }
});

// 23/11/2026 (paquet 388) — résultats dès la fin du match
import { suivreTermines, finDeMatch } from './worker.js';
test('388 : un match qui quitte le direct est vérifié une fois ; fini → score final et vainqueur gardés', async () => {
  const fini = { ...EV, status: { type: 'finished', description: 'Ended' }, winnerCode: 1,
    homeScore: { current: 2, period1: 6, period2: 6 }, awayScore: { current: 0, period1: 4, period2: 3 } };
  const demandes = [];
  const avant = { matchs: compacterLive([EV, { ...EV, id: 11 }]) };
  const apres = { matchs: compacterLive([{ ...EV, id: 11 }]) };
  const d = await suivreTermines({}, avant, apres, async (id) => { demandes.push(id); return fini; });
  assert.deepEqual(demandes, [7]);
  assert.equal(d.termines.length, 1);
  assert.equal(d.termines[0].gagnant, 'home');
  assert.deepEqual(d.termines[0].score_home.sets, [6, 6]);
  // au rafraîchissement suivant : plus de requête pour ce match
  const d2 = await suivreTermines({}, { ...apres, ...d }, apres, async (id) => { demandes.push(id); return fini; });
  assert.deepEqual(demandes, [7]);
  assert.equal(d2.termines.length, 1);
  // pas encore « finished » (coupure) : réessayé, 3 fois au plus
  let n = 0;
  let e = { termines: [], a_verifier: [] };
  for (let i = 0; i < 5; i++) e = await suivreTermines({}, i === 0 ? avant : { ...apres, ...e }, apres, async () => { n++; return { ...EV, status: { type: 'interrupted' } }; });
  assert.equal(n, 3);
  assert.equal(finDeMatch({ ...EV, status: { type: 'inprogress' } }), null);
});

test('388 : /live renvoie les matchs terminés (et les garde si TennisApi tombe)', async () => {
  const stock = {};
  const envL = { RAPIDAPI_KEY: 'k', COFFRE: { get: async k => (k in stock ? { text: async () => stock[k] } : null), put: async (k, v) => { stock[k] = v; } } };
  let etape = 0;
  globalThis.fetch = async (u) => {
    if (String(u).endsWith('/events/live')) return new Response(JSON.stringify({ events: etape === 0 ? [EV] : [] }), { status: 200 });
    if (String(u).endsWith('/event/7')) return new Response(JSON.stringify({ event: { ...EV, status: { type: 'finished' }, winnerCode: 2 } }), { status: 200 });
    return new Response('x', { status: 404 });
  };
  const { viderLiveMemoire } = await import('./worker.js');
  viderLiveMemoire();
  await worker.fetch(req('/live'), envL);
  etape = 1;
  viderLiveMemoire();
  stock['live/en_cours.json'] = JSON.stringify({ ...JSON.parse(stock['live/en_cours.json']), maj: 0 });
  const o = await (await worker.fetch(req('/live'), envL)).json();
  assert.equal(o.matchs.length, 0);
  assert.equal(o.termines, undefined);                         // le direct ne transporte pas la liste
  const t = await (await worker.fetch(req('/live/termines'), envL)).json();
  assert.equal(t.termines.length, 1);
  assert.equal(t.termines[0].gagnant, 'away');
  // TennisApi en panne : les terminés restent
  viderLiveMemoire();
  stock['live/en_cours.json'] = JSON.stringify({ ...JSON.parse(stock['live/en_cours.json']), maj: 0 });
  globalThis.fetch = async () => { throw new Error('panne'); };
  const t2 = await (await worker.fetch(req('/live/termines'), envL)).json();
  assert.equal(t2.termines.length, 1);
});

// 23/11/2026 (paquet 391) — appli installable et fichiers à empreinte
test('391 : fichiers à empreinte gardés un an, service worker jamais en cache, manifeste', async () => {
  const stock = { 'site/algo/app-0123456789ab.js': 'var x=1;', 'site/algo/sw.js': '//sw', 'site/algo/manifest.webmanifest': '{}' };
  const envP = { COFFRE: { get: async (k) => (k in stock ? { body: stock[k], size: stock[k].length, text: async () => stock[k] } : null) } };
  let r = await worker.fetch(req('/app-0123456789ab.js'), envP);
  assert.equal(r.status, 200);
  assert.match(r.headers.get('Cache-Control'), /max-age=31536000, immutable/);
  assert.match(r.headers.get('Content-Type'), /javascript/);
  r = await worker.fetch(req('/sw.js'), envP);
  assert.equal(r.headers.get('Cache-Control'), 'no-cache');
  r = await worker.fetch(new Request('https://gamesetalgo.com/manifest.webmanifest'), envP);   // 415 : seulement sur le site
  assert.match(r.headers.get('Content-Type'), /manifest\+json/);
  assert.equal((await worker.fetch(req('/app-zz.js'), envP)).status, 404);
  assert.equal((await worker.fetch(req('/app-0123456789ab.js.map'), envP)).status, 404);
});

// 24/11/2026 (paquet 411) — feuille d'un match terminé : définitive, gardée 24 h (une seule requête TennisApi)
test('411 : stats d’un match terminé marquées final et gardées 24 h ; match en cours : 60 s', async () => {
  const { ttlDetail, STATS_FINAL_TTL_MS, STATS_TTL_MS } = await import('./worker.js');
  assert.equal(ttlDetail('stats', { final: true }), STATS_FINAL_TTL_MS);
  assert.equal(ttlDetail('stats', { final: false }), STATS_TTL_MS);
  assert.equal(ttlDetail('points', null), 30000);
  let appels = 0; const stock = { 'live/en_cours.json': JSON.stringify({ maj: Date.now(), termines: [{ id: 987654, fin: Date.now() }] }) };
  const envF = { RAPIDAPI_KEY: 'k', LIVE_STATS_PLAFOND: '100000', COFFRE: { get: async k => (k in stock ? { text: async () => stock[k] } : null), put: async (k, v) => { stock[k] = v; } } };
  globalThis.fetch = async () => { appels++; return new Response(JSON.stringify(DOC_STATS), { status: 200 }); };
  const a = await (await worker.fetch(req('/live/stats?id=987654'), envF)).json();
  assert.equal(a.final, true);
  assert.equal(a.stats.aces[0], 3);
  const b = await (await worker.fetch(req('/live/stats?id=987655'), envF)).json();   // pas dans les terminés
  assert.equal(b.final, undefined);
  assert.equal(appels, 2);
  await worker.fetch(req('/live/stats?id=987654'), envF);
  assert.equal(appels, 2);                                                            // gardée
});

// 24/11/2026 (paquet 415) — l'appli ne s'installe que depuis gamesetalgo.com
test('415 : pas de manifeste hors de gamesetalgo.com', async () => {
  const r = await worker.fetch(new Request('https://algo.tennis-edge.workers.dev/manifest.webmanifest'), { CLE_PRIVEE: CLE });
  assert.equal(r.status, 404);
  const r2 = await worker.fetch(new Request('https://gamesetalgo.com/manifest.webmanifest'), { CLE_PRIVEE: CLE, COFFRE: { get: async () => null } });
  assert.notEqual(r2.status, 405);
});

// 24/11/2026 (paquet 417) — référencement
test('417 : robots.txt, sitemap.xml, www → gamesetalgo.com, adresse technique jamais indexée', async () => {
  const envS = { CLE_PRIVEE: CLE, COFFRE: { get: async () => null } };
  let r = await worker.fetch(new Request('https://gamesetalgo.com/robots.txt'), envS);
  let t = await r.text();
  assert.match(t, /Allow: \//); assert.match(t, /Disallow: \/compte\//); assert.match(t, /Sitemap: https:\/\/gamesetalgo\.com\/sitemap\.xml/);
  r = await worker.fetch(new Request('https://algo.tennis-edge.workers.dev/robots.txt'), envS);
  assert.equal(await r.text(), 'User-agent: *\nDisallow: /\n');
  r = await worker.fetch(new Request('https://gamesetalgo.com/sitemap.xml'), envS);
  t = await r.text();
  assert.match(r.headers.get('Content-Type'), /xml/);
  for (const p of ['/', '/methode.html', '/apropos.html']) assert.ok(t.includes(`<loc>https://gamesetalgo.com${p}</loc>`), p);
  r = await worker.fetch(new Request('https://www.gamesetalgo.com/methode.html?lang=en'), envS);
  assert.equal(r.status, 301);
  assert.equal(r.headers.get('Location'), 'https://gamesetalgo.com/methode.html?lang=en');
  globalThis.fetch = async () => new Response('<html></html>', { status: 200 });
  r = await worker.fetch(new Request('https://algo.tennis-edge.workers.dev/'), envS);
  assert.equal(r.headers.get('X-Robots-Tag'), 'noindex, nofollow');
  r = await worker.fetch(new Request('https://gamesetalgo.com/'), envS);
  assert.equal(r.headers.get('X-Robots-Tag'), null);
});

test('418 : pages des matchs et des joueurs servies depuis R2, plan du site publié', async () => {
  const stock = { 'site/algo/match/2026-11-20_aa_bb.html': '<h1>match</h1>', 'site/algo/joueur/aaa-bbb.html': '<h1>joueur</h1>',
    'site/algo/matchs.html': '<h1>matchs</h1>', 'site/algo/sitemap.xml': '<urlset>complet</urlset>' };
  const envS = { CLE_PRIVEE: CLE, COFFRE: { get: async (k) => (k in stock ? { body: stock[k], size: stock[k].length, text: async () => stock[k] } : null) } };
  for (const [u, t] of [['/match/2026-11-20_aa_bb', 'match'], ['/joueur/aaa-bbb', 'joueur'], ['/matchs', 'matchs']]) {
    const r = await worker.fetch(new Request('https://gamesetalgo.com' + u), envS);
    assert.equal(r.status, 200, u);
    assert.match(r.headers.get('Content-Type'), /text\/html/);
    assert.match(await r.text(), new RegExp(t));
  }
  globalThis.fetch = async () => new Response('x', { status: 404 });
  assert.equal((await worker.fetch(new Request('https://gamesetalgo.com/match/../secret'), envS)).status, 404);
  const s = await worker.fetch(new Request('https://gamesetalgo.com/sitemap.xml'), envS);
  assert.equal(await s.text(), '<urlset>complet</urlset>');
});
