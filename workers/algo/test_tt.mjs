// Paquet 499 — tennis de table : page servie, /tt.json complet pour un abonné Plus, version libre pour les autres
// (jamais le fichier complet, même en secours), page dans le plan du site.
import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { PUBLICS, RESERVES, LIBRES, PAGES_SITEMAP } from './worker.js';

const CLE = 'k'.repeat(40);
function monde() {
  const m = new Map(), v = new Map();
  m.set('site/algo/tennis-de-table.html', '<!doctype html><h1>tt</h1>');
  m.set('site/algo/tt.json', '{"acces":"plus"}');
  m.set('site/algo/tt_libre.json', '{"acces":"libre"}');
  m.set('site/algo/site_libre.json', '{"libre":true}');
  const C = {
    m,
    get: async (k) => (m.has(k) ? { body: m.get(k), size: m.get(k).length, etag: 'e' + (v.get(k) || 0), text: async () => m.get(k) } : null),
    put: async (k, x) => { m.set(k, String(x)); v.set(k, (v.get(k) || 0) + 1); return { key: k }; },
    delete: async (k) => { m.delete(k); },
    list: async ({ prefix }) => ({ objects: [...m.keys()].filter((k) => k.startsWith(prefix)).map((key) => ({ key })), truncated: false }),
  };
  globalThis.fetch = async () => new Response('{"acces":"plus","depuis_pages":true}', { status: 200 });
  return { CLE_PRIVEE: CLE, COFFRE: C };
}
const SITE = 'https://gamesetalgo.com', DEV = 'https://algo.tennis-edge.workers.dev';

test('499 : routes de la page et fichier réservé déclarés', () => {
  for (const p of ['/tennis-de-table', '/tennis-de-table.html', '/table-tennis']) assert.equal(PUBLICS[p], 'tennis-de-table.html', p);
  assert.equal(RESERVES['/tt.json'], 'tt.json');
  assert.equal(LIBRES['/tt.json'], 'tt_libre.json');
  assert.ok(PAGES_SITEMAP.includes('/tennis-de-table'));
  assert.ok(!('/tt_libre.json' in PUBLICS) && !('/tt.json' in PUBLICS));
});

test('499 : la page est servie depuis R2 sur gamesetalgo.com', async () => {
  const env = monde();
  const r = await worker.fetch(new Request(SITE + '/tennis-de-table', { headers: { Accept: 'text/html' } }), env);
  assert.equal(r.status, 200);
  assert.match(r.headers.get('Content-Type'), /text\/html/);
  assert.match(await r.text(), /<h1>tt<\/h1>/);
});

test('499 : sans accès Plus → tt_libre.json (jamais tt.json, ni la version libre du tennis)', async () => {
  const env = monde();
  const r = await worker.fetch(new Request(SITE + '/tt.json'), env);
  assert.equal(r.status, 200);
  assert.equal(await r.text(), '{"acces":"libre"}');
  assert.equal(r.headers.get('Cache-Control'), 'private, no-store');
  assert.equal(r.headers.get('X-Acces'), 'libre');
  // version libre absente de R2 : 503, jamais le secours GitHub Pages ni le fichier complet
  env.COFFRE.m.delete('site/algo/tt_libre.json');
  const r2 = await worker.fetch(new Request(SITE + '/tt.json'), env);
  assert.equal(r2.status, 503);
  assert.ok(!(await r2.text()).includes('plus'));
});

test('499 : avec la clé privée (administrateur) → tt.json complet', async () => {
  const env = monde();
  const r = await worker.fetch(new Request(DEV + '/tt.json', { headers: { 'X-Cle': CLE } }), env);
  assert.equal(await r.text(), '{"acces":"plus"}');
  assert.equal(r.headers.get('X-Acces'), 'plus');
});

test('499 : sitemap de secours avec la page du tennis de table', async () => {
  const env = { CLE_PRIVEE: CLE, COFFRE: { get: async () => null } };
  const t = await (await worker.fetch(new Request(SITE + '/sitemap.xml'), env)).text();
  assert.ok(t.includes('<loc>https://gamesetalgo.com/tennis-de-table</loc>'));
});
