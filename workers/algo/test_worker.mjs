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
