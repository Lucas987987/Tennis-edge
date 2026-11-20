// V7.1 Réconciliation (verdicts en direct) : chiffres Worker recopiés, synthèse, filtres d'écarts, populations de l'Explorateur.
const test = require('node:test');
const assert = require('node:assert/strict');
const R = require('../research_reconciliation.js');
const X = require('../research_explorer.js');

const snap = { schema_version: 1, status: 'ok', fetched_at: '2026-10-16T09:09:00Z',
  hypotheses: [{ code: 'H13', gele_le: '2026-09-06', out_of_sample: { n: 132, roi: 3.6, clv_moyen: 0.8 } },
    { code: 'H16-B', out_of_sample: { n: 135, roi: 0.1 } }] };
const doc = {
  sources: { worker: { status: 'ok', fetched_at: '2026-10-16T04:30:00Z' } },
  hypotheses: {
    H13: { canal: 'h13', worker: { n: 130, roi: 3.0, out_of_sample: { n: 130, roi: 3.0 } },
      suivi_officiel: { n: 109, roi: 1.8, pts: -0.3, n_detectees: 207, n_envoyees: 207 },
      reconstruction: { n: 135, roi: 3.3 },
      entonnoir: { direct_detectees: 207, direct_envoyees: 207, communes: 66, inexpliques: 1 },
      ecarts: [{ sens: 'reconstruction seule', raison: 'apres_coup', explique: true, date: '2026-10-01' },
        { sens: 'direct seule', raison: 'inexplique', explique: false, date: '2026-10-02' }] },
    H14: { canal: 'h14', worker: null, suivi_officiel: { n: 0, n_detectees: 0 }, reconstruction: { n: 91 },
      entonnoir: { direct_detectees: 0, direct_envoyees: 0, communes: 0, inexpliques: 0 }, ecarts: [] },
  },
};

test('les chiffres du Worker sont recopiés tels quels', () => {
  const w = R.workerFromSnapshot(snap);
  assert.deepEqual(w.H13, { gele_le: '2026-09-06', out_of_sample: { n: 132, roi: 3.6, clv_moyen: 0.8 }, n: 132, roi: 3.6 });
  assert.equal(w.H16B.n, 135);
  assert.deepEqual(R.workerFromSnapshot({ status: 'unavailable', hypotheses: [] }), {});
  assert.deepEqual(R.workerExtras(w.H13), ['clv_moyen 0,8']);
});

test('la capture horaire plus récente remplace la capture quotidienne', () => {
  assert.equal(R.pickWorker(doc, snap).by.H13.n, 132);
  assert.equal(R.pickWorker(doc, null).by.H13.n, 130);
  assert.equal(R.pickWorker(doc, { ...snap, fetched_at: '2026-10-15T00:00:00Z' }).by.H13.n, 130);
});

test('synthèse : officiel en direct, contrôle reconstruction, écart Worker', () => {
  const rows = R.summaryRows(doc, R.pickWorker(doc, snap));
  assert.equal(rows[0].ecartWorker, 132 - 109);
  assert.equal(rows[0].reconstruction.n, 135);
  assert.equal(rows[1].ecartWorker, null);
});

test('filtres de la liste des écarts', () => {
  const list = doc.hypotheses.H13.ecarts;
  assert.equal(R.filterEcarts(list, 'inexpliques').length, 1);
  assert.equal(R.filterEcarts(list, 'reco')[0].raison, 'apres_coup');
  assert.equal(R.filterEcarts(list, 'direct').length, 1);
  assert.equal(R.filterEcarts(list, 'apres_coup').length, 1);
  assert.equal(R.filterEcarts(list, 'tous').length, 2);
});

test('Explorateur : jeu Détections par défaut et n des deux populations', () => {
  assert.equal(X._state.kind, 'detections');
  const D = X.prepareAlerts({ fields: [{ name: 'type', label: 'Hypothèse', role: 'filtre' }], columns: ['type', 'clv_pin', 'pnl', 'gagne', 'date', 'mois', '_at'],
    rows: [['H13', 1, 0.5, 1, '2026-10-01', '2026-10', '2026-10-01']] }, 'detections');
  assert.equal(D.kind, 'detections');
  const counts = X.populationCounts(doc);
  assert.deepEqual(counts.find(r => r.code === 'H13'), { code: 'H13', detectees: 207, denouees: 109, envoyees: 207, reconstruction: 135, worker: 130, communes: 66 });
  assert.equal(counts.find(r => r.code === 'H14').reconstruction, 91);
});
