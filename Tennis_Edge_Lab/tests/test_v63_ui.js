const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const lab = path.join(__dirname, '..');
const script = fs.readFileSync(path.join(lab, 'research_v63.js'), 'utf8');

test('Le tableau V6.3 expose la sélection, les échéances et les métriques', async () => {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, { innerHTML: '', textContent: '' });
    return elements.get(id);
  };
  let click;
  const tab = {
    addEventListener(name, callback) {
      if (name === 'click') click = callback;
    },
  };
  const report = {
    active_limit: 60,
    exploratory_inventory_count: 17023,
    redundant_exploratory_count: 17,
    candidate_redundant_count: 4,
    active_by_market: { match: 20, set1: 20, set2: 20 },
    completed_and_archived: 3,
    source_snapshot_sha256: 'snapshot-hash',
    evaluated_future_period: { latest_cutoff_utc: '2026-10-13T08:00:00Z' },
    candidates: [{
      candidate_id: 'candidate-1',
      market: 'match',
      book: '<script>alert(1)</script>',
      horizon: '24h',
      selection: 'favori',
      criteria: [{ dimension: 'circuit', operator: 'eq', value: 'ATP' }],
      lifecycle_state: 'active',
      state: 'signal prospectif à auditer',
      freeze_date_utc: '2026-10-01',
      eligible_after_utc: '2026-10-02',
      discovery_period: { start: '2026-08-01', end: '2026-09-30' },
      source_commit: 'abcdef0123456789',
      source_snapshot_sha256: '1234567890abcdef',
      checkpoints: [{
        cutoff_exclusive_utc: '2026-11-01T00:00:00Z',
        roi_pct: 5,
        roi_ci95: [1, 9],
        clv_mean_pct: 2,
        clv_ci95: [-1, 4],
        clv_n: 65,
      }],
    }],
  };
  const context = {
    document: { getElementById: element, querySelectorAll: () => [tab] },
    fetch: async () => ({ ok: true, json: async () => report }),
  };
  vm.runInNewContext(script, context);
  click();
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.match(element('v63Metrics').innerHTML, /17 023|17.023/);
  assert.match(element('v63Metrics').innerHTML, /20/);
  assert.match(element('v63Metrics').innerHTML, /3/);
  assert.match(element('v63Rows').innerHTML, /signal prospectif à auditer/);
  assert.match(element('v63Rows').innerHTML, /IC95/);
  assert.match(element('v63Rows').innerHTML, /-1/);
  assert.match(element('v63Rows').innerHTML, /2026-10-02 – 2026-11-01/);
  assert.match(element('v63Rows').innerHTML, /&lt;script&gt;/);
  assert.doesNotMatch(element('v63Rows').innerHTML, /<script>alert/);
});

test('Le HTML V6.3 relie le rapport et le manifeste préenregistré', () => {
  const html = fs.readFileSync(path.join(lab, 'research.html'), 'utf8');
  assert.match(html, /data-tab="v63Hypotheses"/);
  assert.match(html, /id="v63Rows"/);
  assert.match(html, /candidate_selection_v63\.jsonl/);
  assert.match(html, /research_v63\.js/);
});
