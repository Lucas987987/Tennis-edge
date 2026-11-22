// Paquet 345 — l'ancienne page publique des hypothèses est fermée : aucune donnée, aucune lecture de GitHub.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import worker, { page } from './worker.js';

const source = fs.readFileSync(new URL('./worker.js', import.meta.url), 'utf8');

test('plus aucune lecture extérieure ni donnée de verdict', () => {
  assert.ok(!/fetch\(\s*['"`]?http/.test(source));
  assert.ok(!source.includes('raw.githubusercontent'));
  for (const mot of ['clv', 'pinnacle', 'roi', 'cote']) assert.ok(!page().toLowerCase().includes(mot), mot);
});

test('routes : API et page répondent « fermé » (410), le reste 404', async () => {
  const api = await worker.fetch(new Request('https://x.dev/api/hypotheses'));
  assert.equal(api.status, 410);
  const j = await api.json();
  assert.equal(j.status, 'prive');
  assert.deepEqual(j.hypotheses, []);
  const p = await worker.fetch(new Request('https://x.dev/'));
  assert.equal(p.status, 410);
  assert.match(await p.text(), /Page fermée/);
  assert.equal((await worker.fetch(new Request('https://x.dev/autre'))).status, 404);
});
