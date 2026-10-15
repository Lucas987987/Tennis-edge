const assert = require('node:assert/strict');
const test = require('node:test');

const elements = new Map();
const element = id => {
  if (!elements.has(id)) elements.set(id, { innerHTML: '', textContent: '', querySelectorAll: () => [] });
  return elements.get(id);
};
globalThis.document = { getElementById: element, readyState: 'complete' };
const ui = require('../research_v66.js');

test('stabilité 16 ans : cellules retenues et échappement HTML', () => {
  ui.renderHistory({
    matches: 10, cells_tested: 2, cells_passing: 1, period: { start: '2010-01-04', end: '2026-01-10' },
    bands: ['1,01–1,30'], rules: { null_model: 'modèle', levels: 'niveaux' },
    passing: [{ cell: 'côté favori · <b>x</b>', n: 900, roi_pct: 1.3, roi_ci95: [-1, 3], roi_vs_peers_pct: 0.8,
      years_positive: 10, years_tested: 16, p_permutation: 0.005, p_holm: 0.048 }],
    cells: [{ depth: 2, side: 'favori', band: '1,01–1,30', n: 9000, roi_pct: -2, roi_ci95: [-3, -1], years_positive: 3, years_tested: 16 }],
  });
  const html = element('history16Body').innerHTML;
  assert.match(html, /Cellules retenues/);
  assert.match(html, /&lt;b&gt;x&lt;\/b&gt;/);
  assert.match(html, /0,048/);
  assert.match(html, /biais favori-outsider/);
});

test('propositions : filtre « Jouables en France » et badge FR', () => {
  globalThis.dispatchEvent = () => true;
  ui._set({
    iso_week: '2026-W42', eligible_pool: 30, max_per_week: 10,
    proposals: [
      { id: 'aaaaaaaaaaaaaaaa', market: 'match', book: 'winamax.fr', jouable: true, jouable_fr: true, horizon: '1h', selection: 'favori', criteria: [{ value: 'marge < 4 %' }], clv_pin_mean_pct: 2.1, clv_pin_ci95: [0.3, 3.9], p_holm_clv_pin: 0.2, n: 120, stabilite_16_ans: { label: 'stable 16 ans' }, note_mecanisme: 'mécanisme' },
      { id: 'bbbbbbbbbbbbbbbb', market: 'set1', book: 'pinnacle', jouable: true, jouable_fr: false, horizon: '6h', selection: 'outsider', criteria: [], clv_pin_mean_pct: 1, clv_pin_ci95: [0.1, 2], n: 90 },
    ],
  }, { total_frozen: 0, candidates: [], rule: 'règle', multiple_testing: 'Holm' });
  ui.setFilter('jouable');
  let html = element('v66Proposals').innerHTML;
  assert.match(html, /aaaaaaaaaaaaaaaa/);
  assert.match(html, /bbbbbbbbbbbbbbbb/);
  assert.match(html, />FR</);
  assert.match(html, /non gelée/);
  ui.setFilter('fr');
  html = element('v66Proposals').innerHTML;
  assert.match(html, /aaaaaaaaaaaaaaaa/);
  assert.doesNotMatch(html, /bbbbbbbbbbbbbbbb/);
  assert.match(element('bookFilter').innerHTML, /Jouables en France/);
  assert.match(element('v66Frozen').innerHTML, /Aucune piste gelée/);
});
