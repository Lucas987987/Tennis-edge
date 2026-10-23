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
