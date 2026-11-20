// Worker tennis-edge-db (16/10/2026) : lecture de verdicts_direct.json, forme de /api/hypotheses, page.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import worker, { adapter, sourceUrl, page } from './worker.js';

const source = fs.readFileSync(new URL('./worker.js', import.meta.url), 'utf8');
const fixture = {
  genere_le: '2026-10-16T11:20:55Z', regles_de_comptage: ['un pari par (hypothèse, uid, côté)'],
  hypotheses: [
    { code: 'H18', libelle: 'Favorite <Steam>', gele_le: '2026-09-27', cible: 150, avancement: 7, restant: 139,
      out_of_sample: { n: 11, gains: 10, taux: 90.9, seuil: 66.6, ecart: 24.3, ic95: [62.3, 98.4], roi: 37.1, pnl: 4.1,
        clv_moyen: 3.0, clv_pin_moyen: 3.0, clv_pin_ic95: [1.0, 5.0], n_detectees: 12, n_envoyees: 12, n_denouees: 11, verdict: 'ne tranche pas' },
      replication: [{ moitie: 1, n: 6, roi: 30, ecart: 20 }, { moitie: 2, n: 5, roi: 45, ecart: 29 }] },
    { code: 'H14', libelle: 'amplitude + timing', gele_le: '2026-10-02', cible: 166, out_of_sample: { n_detectees: 0 } },
  ],
};

test('aucun artefact d\'extraction (guillemets typographiques hors texte)', () => {
  for (const line of source.split('\n')) {
    const code = line.split('//')[0];
    assert.ok(!/[“”‘’]/.test(code), line);
  }
  assert.ok(!/archiverCourbes|env\.DB|filtre_sql/.test(source.replace(/\/\/.*$/gm, '')));
});

test('adapter garde la forme de /api/hypotheses et ajoute les champs du direct', () => {
  const d = adapter(fixture, 'x');
  assert.equal(d.genere_le, fixture.genere_le);
  assert.equal(d.hypotheses[0].out_of_sample.n, 11);
  assert.equal(d.hypotheses[0].out_of_sample.n_detectees, 12);
  assert.equal(d.hypotheses[1].out_of_sample.n, 0);           // n toujours présent (fetch_worker_snapshot l'exige)
  assert.deepEqual(d.hypotheses[1].in_sample_recalcule, { n: 0 });
});

test('source configurable, défaut dépôt principal', () => {
  assert.equal(sourceUrl({}), 'https://raw.githubusercontent.com/Lucas987987/Tennis-edge/main/verdicts_direct.json');
  assert.equal(sourceUrl({ GH_OWNER: 'a', GH_REPO: 'b', GH_BRANCH: 'c' }), 'https://raw.githubusercontent.com/a/b/c/verdicts_direct.json');
});

test('routes : /api/hypotheses lit GitHub avec cache 60 s ; page HTML ; 404', async () => {
  const calls = [];
  globalThis.fetch = async (url, init) => { calls.push([url, init]); return new Response(JSON.stringify(fixture), { status: 200 }); };
  const r = await worker.fetch(new Request('https://w.dev/api/hypotheses'), {}, {});
  assert.equal(r.status, 200);
  const body = await r.json();
  assert.equal(body.hypotheses[0].code, 'H18');
  assert.equal(calls[0][1].cf.cacheTtl, 60);
  const p = await worker.fetch(new Request('https://w.dev/'), {}, {});
  assert.match(p.headers.get('content-type'), /text\/html/);
  assert.match(await p.text(), /dénouées/);
  assert.equal((await worker.fetch(new Request('https://w.dev/ingest'), {}, {})).status, 404);
  globalThis.fetch = async () => new Response('x', { status: 500 });
  const e = await worker.fetch(new Request('https://w.dev/api/hypotheses'), {}, {});
  assert.equal(e.status, 502);
});

test('la page échappe les libellés', () => {
  assert.match(page(), /const esc = /);
  assert.ok(page().includes('esc(h.libelle)'));
});
