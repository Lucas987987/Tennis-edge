const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

test('Bookmakers & Sets rendert couverture et pistes sans HTML injecté', async () => {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) {
      elements.set(id, {
        innerHTML: '',
        textContent: '',
        value: '',
        addEventListener() {},
      });
    }
    return elements.get(id);
  };
  const responses = {
    './live/prospective.json': {
      schema_version: 1, total_frozen: 0, ledger_tip: 'none',
      validation_minimum: 'validation requise', models: [],
    },
    './live/source_catalog.json': {
      total_data_files: 3, total_bytes: 1000, indexed_partition_files: 3,
      warning: 'inventaire', families: [],
    },
    './live/archive/index.json': null,
    './live/bookmakers_sets.json': {
      schema_version: 1, generated_at: '2026-10-12T00:00:00Z',
      coverage: {
        set2: {
          bookmaker_count: 1,
          bookmakers: {
            'unsafe<script>alert(1)</script>': {
              partition_records: 20, matched_results: 18,
              snapshots: { '24h': 2, '6h': 4, '1h': 8, '10m': 10 },
            },
          },
        },
      },
      summary: {
        unique_market_book_matches: 20, settled_snapshots: 24,
        tested_segments: 40, signals: 0,
      },
      discoveries: [],
      unconfirmed: [{
        market: 'set2', book: 'test-book', horizon: '1h', selection: 'favori',
        criteria: [{ dimension: 'amplitude', value: '3–5 %' }],
        unique_matches: 12, roi_pct: 4, roi_ci95: [-10, 18],
        clv_mean_pct: 1, clv_n: 8, p_holm: 1,
        first_half: { roi_pct: -2 }, second_half: { roi_pct: 10 },
        status: 'piste non confirmée', freeze_automatic: false,
      }],
      methodology: {
        temporal_rule: 'Strictement avant le match.',
        set2_rule: 'Jamais après le set 1.',
        clv: 'CLV descriptive.',
        inference: 'Tests corrigés.',
        warnings: ['Exploratoire.'],
      },
    },
  };
  const fetch = async (url) => {
    const key = Object.keys(responses).find((item) => url.startsWith(item));
    if (!key || responses[key] === null) return { ok: false, status: 404 };
    return { ok: true, json: async () => responses[key] };
  };
  const context = {
    document: { getElementById: element },
    fetch,
    console,
  };
  const script = fs.readFileSync(path.join(__dirname, '..', 'v4.js'), 'utf8');
  vm.runInNewContext(script, context);
  await new Promise((resolve) => setTimeout(resolve, 0));

  assert.match(element('v5Notice').textContent || element('v5Notice').innerHTML, /tests corrigés/);
  assert.match(element('v5Coverage').innerHTML, /18/);
  assert.match(element('v5Coverage').innerHTML, /&lt;script&gt;/);
  assert.doesNotMatch(element('v5Coverage').innerHTML, /<script>alert/);
  assert.match(element('v5Unconfirmed').innerHTML, /Vainqueur du set 2/);
  assert.match(element('v5Unconfirmed').innerHTML, /gel automatique désactivé/);
});
