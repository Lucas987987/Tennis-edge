const assert = require('node:assert/strict');
const test = require('node:test');
const X = require('../research_explorer.js');

const close = (a, b, eps = 1e-9) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);

test('cube : ROI et IC95 obtenus en sommant les cellules = calcul direct sur les paris', () => {
  // Paris unitaires bruts (cote, gagné), répartis en 3 cellules.
  const bets = [[1.5, 1], [1.5, 0], [2.2, 1], [3.0, 0], [1.3, 1], [4.5, 1], [1.8, 0], [2.0, 1]];
  const pnl = bets.map(([o, w]) => (w ? o - 1 : -1));
  const groups = [[0, 1, 2], [3, 4], [5, 6, 7]];
  const cells = groups.map(g => ({ n: g.length, w: g.reduce((s, i) => s + bets[i][1], 0),
    s: g.reduce((s, i) => s + pnl[i], 0), s2: g.reduce((s, i) => s + pnl[i] ** 2, 0) }));
  const c = X.cubeStats(cells);
  const n = pnl.length, mean = pnl.reduce((a, b) => a + b, 0) / n;
  const variance = pnl.reduce((s, v) => s + (v - mean) ** 2, 0) / (n - 1);
  const se = Math.sqrt(variance / n);
  assert.equal(c.n, n);
  assert.equal(c.wins, 5);
  close(c.roi, 100 * mean);
  close(c.ci[0], 100 * (mean - 1.96 * se));
  close(c.ci[1], 100 * (mean + 1.96 * se));
});

test('IC par grappes identique à clv_stats.summary (Python)', () => {
  const s = X.clusterSummary([1, 2, 3, NaN, 4, 5, 6], ['a', 'a', 'b', 'b', 'c', 'c', 'd']);
  assert.equal(s.n, 6);
  close(s.mean, 3.5);
  // Valeurs de clv_stats.summary([1,2,3,None,4,5,6], list('aabbccd')) en Python.
  close(s.ci[0], 1.558, 1e-3);
  close(s.ci[1], 5.442, 1e-3);
  close(s.p, 0.000205541, 1e-6);
});

test('filtres, statistiques des alertes et bloc de gel', () => {
  const doc = {
    fields: [{ name: 'type', label: 'Type', role: 'filtre' }, { name: 'circuit', label: 'Circuit', role: 'filtre' },
      { name: 'suivie_public', label: 'Suivie', role: 'filtre_apres_alerte' }, { name: 'pin_move_entree_cloture', label: 'Après', role: 'post_entree' }],
    columns: ['type', 'circuit', 'suivie_public', 'date', 'mois', 'gagne', 'pnl', 'clv_pin', 'pin_move_entree_cloture'],
    rows: [
      ['H17', 'ATP', 'oui', '2026-10-01', '2026-10', 1, 1.1, 2.0, -3],
      ['H17', 'WTA', 'non', '2026-10-02', '2026-10', 0, -1, -1.0, 1],
      ['PUBLIC', 'ATP', 'sans objet', '2026-10-03', '2026-10', null, null, 4.0, null],
    ],
  };
  const D = X.prepareAlerts(doc);
  assert.deepEqual(D.fields.map(f => f.name), ['type', 'circuit', 'suivie_public']); // jamais post_entree
  const idx = X.filterIndices(D, [{ field: 'type', values: ['H17'] }]);
  assert.deepEqual(idx, [0, 1]);
  const s = X.stats(D, idx);
  assert.equal(s.n, 2); assert.equal(s.settled, 2); assert.equal(s.wins, 1);
  close(s.roi, 5); close(s.clv, 0.5);
  const all = X.stats(D, X.filterIndices(D, []));
  assert.equal(all.clvN, 3);
  X._state.filters = [{ field: 'type', values: ['H17'] }, { field: 'circuit', values: ['ATP'] }];
  const spec = X.freezeSpec(D, s);
  assert.equal(spec.jeu, 'alertes');
  assert.deepEqual(spec.criteres, { type: ['H17'], circuit: ['ATP'] });
});
