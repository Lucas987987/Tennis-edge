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
  assert.equal((await worker.fetch(req('/donnees.json'), env)).headers.get('Content-Type'), 'application/json; charset=utf-8');
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
