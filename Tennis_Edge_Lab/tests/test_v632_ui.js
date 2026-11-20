const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const lab = path.join(__dirname, '..');
const script = fs.readFileSync(path.join(lab, 'research_v63.js'), 'utf8');

function makeReport(checkpoints = []) {
  return {
    active_limit: 60,
    exploratory_inventory_count: 160313,
    redundant_exploratory_count: 10,
    candidate_redundant_count: 3,
    active_by_market: { match: 20, set1: 20, set2: 20 },
    completed_and_archived: 0,
    evaluated_future_period: { latest_cutoff_utc: '2026-10-14T16:00:00Z' },
    candidates: [{
      candidate_id: 'candidate-1', market: 'match', book: '<script>alert(1)</script>',
      horizon: '6h', selection: 'favori', freeze_date_utc: '2026-10-14',
      eligible_after_utc: '2026-10-15', scheduled_checkpoints_utc: ['2026-11-13'],
      source_commit: 'abcdef1234567890', source_snapshot_sha256: 'testsha',
      criteria: [{ dimension: 'marge', operator: 'eq', value: '<span>marge < 2%</span>' }],
      lifecycle_state: 'active', state: 'observation exploratoire',
      discovery_period: { start: '2026-08-01', end: '2026-10-14' },
      historical_context: { roi_pct: -2.25, roi_ci95: [-8.3, 3.8], clv_mean_pct: 0.1, clv_n: 1522 },
      checkpoints,
    }],
  };
}

async function render(report) {
  const elements = new Map();
  const el = id => { if (!elements.has(id)) elements.set(id, { innerHTML: '', textContent: '' }); return elements.get(id); };
  let click;
  const ctx = {
    document: { getElementById: el, querySelectorAll: () => [{ addEventListener: (_ev, fn) => { click = fn; } }] },
    fetch: async () => ({ ok: true, json: async () => report }),
  };
  vm.runInNewContext(script, ctx);
  click();
  await new Promise(resolve => setTimeout(resolve, 0));
  return { rows: el('v63Rows').innerHTML, cards: el('v63Cards').innerHTML, notice: el('v63Notice').textContent };
}

test('ROI/CLV historiques visibles et suivi futur toujours en attente avant checkpoint', async () => {
  const { rows, cards } = await render(makeReport());
  assert.match(rows, /-2,25 %/);
  assert.match(rows, /\+0,1 %/);
  assert.match(rows, /-8,3 % à \+3,8 %/);
  assert.match(rows, /1 522|1.522/);
  assert.match(rows, /En attente/);
  assert.match(rows, /2026-10-15/);
  assert.match(rows, /2026-11-13/);
  assert.doesNotMatch(rows, /2026-10-15 – 2026-10-14/);
  assert.match(cards, /Historique · descriptif/);
  assert.match(cards, /Prospectif · contrôle préenregistré/);
  assert.match(cards, /-2,25 %/);
  assert.match(cards, /En attente/);
  assert.doesNotMatch(rows, /<script>alert/);
  assert.match(rows, /&lt;script&gt;/);
  assert.doesNotMatch(cards, /<span>marge/);
});

test('Le calcul prospectif affiché séparément à une échéance, sans remplacer le descriptif', async () => {
  const { rows } = await render(makeReport([{cutoff_exclusive_utc:'2026-11-13T00:00:00Z',roi_pct:5,roi_ci95:[1,9],clv_mean_pct:2,clv_ci95:[-1,4],clv_n:70}]));
  assert.match(rows, /-2,25 %/); assert.match(rows, /\+0,1 %/);
  assert.match(rows, /\+5 %/); assert.match(rows, /\+2 %/);
  assert.match(rows, /2026-10-15 – 2026-11-13/);
});
