// Worker tennis-edge-closing (22/10/2026) : garde API avec plafond par workflow,
// décision jour / nuit.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import worker, { decide, runsBloquants, plafondMin } from './worker.js';

const source = fs.readFileSync(new URL('./worker.js', import.meta.url), 'utf8');
const MIN = 60000;
const now = Date.parse('2026-10-22T19:30:00Z');
const run = (status, ilYaMin) => ({ status, created_at: new Date(now - ilYaMin * MIN).toISOString() });

test('un seul runEnCours, plus de redéfinition collée en fin de fichier', () => {
  assert.equal((source.match(/function runEnCours\(/g) || []).length, 1);
  assert.ok(!/runEnCours\s*=\s*async/.test(source));
  assert.equal(typeof worker.scheduled, 'function');
});

test('cron du wrangler.toml = CRON_MIN', () => {
  const toml = fs.readFileSync(new URL('./wrangler.toml', import.meta.url), 'utf8');
  const cron = Number(source.match(/const CRON_MIN = (\d+)/)[1]);
  assert.ok(toml.includes(`"*/${cron} * * * *"`));
});

test('capture : un run « en cours » de plus de 6 min est un fantôme', () => {
  assert.equal(plafondMin('capture_closing.yml'), 6);
  assert.equal(runsBloquants([run('in_progress', 2)], 'capture_closing.yml', now).bloquant, true);
  const r = runsBloquants([run('in_progress', 13)], 'capture_closing.yml', now);   // cas du 22/10 (12 min 47)
  assert.deepEqual(r, { bloquant: false, fantomes: 1 });
  assert.equal(runsBloquants([run('queued', 44)], 'capture_closing.yml', now).bloquant, false);
  assert.equal(runsBloquants([run('completed', 1)], 'capture_closing.yml', now).bloquant, false);
});

test('Polymarket et Kalshi gardent 45 min : un vrai run de 20 min bloque toujours', () => {
  assert.equal(runsBloquants([run('in_progress', 20)], 'polymarket_collector.yml', now).bloquant, true);
  assert.equal(runsBloquants([run('in_progress', 50)], 'kalshi_collector.yml', now).bloquant, false);
  assert.equal(plafondMin('courbes_alertes.yml'), 10);
});

test('decide : de jour, la garde API seule ; repli temporel si l’API est muette', () => {
  const cfg = { DAY_CADENCE_MIN: 3, NIGHT_CADENCE_MIN: 15, NIGHT_START_UTC: 23, NIGHT_END_UTC: 6 };
  const st = { last_capture_at: new Date(now - 2 * MIN).toISOString() };
  assert.equal(decide(st, 10, now, cfg, false).fire, true);
  assert.equal(decide(st, 10, now, cfg, true).fire, false);
  assert.equal(decide(st, 10, now, cfg, null).fire, true);                 // 2 min >= 3 − 1,5
  const nuit = Date.parse('2026-10-22T23:30:00Z');
  assert.equal(decide({ last_capture_at: new Date(nuit - 5 * MIN).toISOString() }, 0, nuit, cfg, false).fire, false);
});
