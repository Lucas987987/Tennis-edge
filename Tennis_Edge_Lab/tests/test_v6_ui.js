const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

test('Le suivi V6 affiche chaque marché et échappe les données du rapport', async () => {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, { innerHTML: '', textContent: '' });
    return elements.get(id);
  };
  const report = {
    schema_version: 1,
    generated_at: '2026-10-12T00:00:00Z',
    total_frozen: 1,
    tested_hypotheses: 1,
    markets: ['match', 'set1', 'set2'],
    warning: 'Aucun succès déclaré.',
    hypotheses: [{
      candidate_id: 'abc',
      market: 'set2',
      book: '<script>alert(1)</script>',
      horizon: '1h',
      selection: 'favori',
      criteria: [{ dimension: 'circuit', operator: 'eq', value: 'ATP' }],
      freeze_date: '2026-10-01',
      eligible_after: '2026-10-02',
      discovery_matches: 60,
      metrics: {
        n: 60, unique_matches: 60, roi_pct: 5, roi_ci95: [1, 9],
        clv_mean_pct: 2, clv_ci95: [0, 4], clv_n: 55,
      },
      distinct_days: 12,
      first_prospective_date: '2026-10-02',
      last_prospective_date: '2026-10-12',
      p_holm: 0.03,
      status: 'signal prospectif à auditer',
    }],
  };
  const context = {
    document: { getElementById: element },
    fetch: async () => ({ ok: true, json: async () => report }),
  };
  const script = fs.readFileSync(path.join(__dirname, '..', 'v6.js'), 'utf8');
  vm.runInNewContext(script, context);
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.match(element('v6Hypotheses').innerHTML, /Vainqueur du set 2/);
  assert.match(element('v6Hypotheses').innerHTML, /circuit eq ATP/);
  assert.match(element('v6Hypotheses').innerHTML, /&lt;script&gt;/);
  assert.doesNotMatch(element('v6Hypotheses').innerHTML, /<script>alert/);
  assert.match(element('v6Hypotheses').innerHTML, /IC95/);
  assert.match(element('v6Hypotheses').innerHTML, /0,03/);
});
