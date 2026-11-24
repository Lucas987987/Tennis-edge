// Worker tennis-edge-closing (22/10/2026) : garde API avec plafond par workflow,
// décision jour / nuit.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import worker, { decide, runsBloquants, plafondMin, decisionPeriodique } from './worker.js';

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

test('périodique : pronostics et feuilles toutes les 2 h, sans doublon avec les crons GitHub', () => {
  const fini = (ilYa) => ({ status: 'completed', created_at: new Date(now - ilYa * MIN).toISOString() });
  assert.equal(decisionPeriodique([fini(130)], 'pronostics_quotidien.yml', 120, now).fire, true);
  assert.equal(decisionPeriodique([fini(50)], 'pronostics_quotidien.yml', 120, now).fire, false);   // cron passé il y a 50 min
  assert.equal(decisionPeriodique([], 'feuilles_match.yml', 120, now).fire, true);
  assert.equal(decisionPeriodique([run('in_progress', 200)], 'feuilles_match.yml', 120, now).fire, false);  // vraie collecte longue
  assert.equal(decisionPeriodique([run('in_progress', 400), fini(400)], 'feuilles_match.yml', 120, now).fire, true);  // fantôme
  assert.equal(plafondMin('pronostics_quotidien.yml'), 100);
});

// 24/11/2026 (paquet 400) — fenêtres juste après le renouvellement du quota TennisApi
import { decisionFenetres, minutesUTC } from './worker.js';
test('fenêtres : ITF à 07:50 et 08:50 UTC, une seule fois par fenêtre, jamais en double', () => {
  assert.equal(minutesUTC('07:50'), 470);
  assert.equal(minutesUTC('x'), null);
  const t = (h, m) => Date.UTC(2026, 10, 24, h, m);
  const run = (h, m, status = 'completed') => ({ name: 'itf_points.yml', path: '.github/workflows/itf_points.yml',
    status, created_at: new Date(t(h, m)).toISOString(), updated_at: new Date(t(h, m)).toISOString() });
  const F = ['07:50', '08:50'];
  assert.equal(decisionFenetres([run(4, 6)], 'itf_points.yml', F, t(7, 40)).fire, false);   // avant la fenêtre
  assert.equal(decisionFenetres([run(4, 6)], 'itf_points.yml', F, t(7, 51)).fire, true);
  assert.equal(decisionFenetres([run(7, 51)], 'itf_points.yml', F, t(7, 54)).fire, false);  // déjà servie
  assert.equal(decisionFenetres([run(7, 51)], 'itf_points.yml', F, t(8, 52)).fire, true);   // 2e fenêtre
  assert.equal(decisionFenetres([run(7, 51)], 'itf_points.yml', F, t(10, 0)).fire, false);  // passée depuis 70 min
  assert.equal(decisionFenetres([run(8, 50, 'in_progress')], 'itf_points.yml', F, t(8, 52)).fire, false);
});

test('410 : pronostics enchaînés — relancés dès la fin du passage, au plus toutes les 20 min', async () => {
  const W = await import('./worker.js');
  const now = Date.parse('2026-11-24T14:00:00Z');
  const run = (minAgo, status = 'completed') => ({ status, created_at: new Date(now - minAgo * 60000).toISOString() });
  assert.equal(W.periodePronostics({}), 20);
  assert.equal(W.periodePronostics({ PRONOSTICS_PERIODE_MIN: '5' }), 15);          // jamais plus serré que 15 min
  assert.equal(W.periodePronostics({ PRONOSTICS_PERIODE_MIN: '45' }), 45);
  assert.equal(W.decisionPeriodique([run(35)], 'pronostics_quotidien.yml', 20, now).fire, true);   // fini il y a peu : on relance
  assert.equal(W.decisionPeriodique([run(10)], 'pronostics_quotidien.yml', 20, now).fire, false);
  assert.equal(W.decisionPeriodique([run(70, 'in_progress')], 'pronostics_quotidien.yml', 20, now).fire, false);  // passage long : on attend
});

test('413 : feuilles de match toutes les heures par défaut, jamais plus serré que 30 min', async () => {
  const W = await import('./worker.js');
  assert.equal(W.periodeFeuilles({}), 60);
  assert.equal(W.periodeFeuilles({ FEUILLES_PERIODE_MIN: '10' }), 30);
  assert.equal(W.periodeFeuilles({ FEUILLES_PERIODE_MIN: '120' }), 120);
});
