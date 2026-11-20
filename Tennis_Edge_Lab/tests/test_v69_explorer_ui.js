const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const X = require('../research_explorer.js');

const fixture = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'explorer_parity.json'), 'utf8'));

test('parité Python/JS : OU dans un critère, ET entre critères, plages incluses, valeurs absentes exclues', () => {
  const D = X.prepareRows(fixture.rows, fixture.fields);
  for (const spec of fixture.specs) {
    const got = X.filterIndices(D, { cats: spec.criteres, ranges: spec.plages });
    assert.deepEqual(got, spec.expected, JSON.stringify(spec));
  }
});

test('jeu « matchs » : colonnes codées, choix du prix d’entrée, découpe numérique', () => {
  const doc = {
    n: 4, entrees: {},
    columns: [
      { name: 'circuit', type: 'cat', role: 'filtre' }, { name: 'cote_pin', type: 'num', role: 'filtre' },
      { name: 'date', type: 'cat', role: 'descriptif' }, { name: 'mois', type: 'cat', role: 'filtre' },
      { name: 'decision_ts', type: 'cat', role: 'descriptif' }, { name: 'cloture_pin', type: 'num', role: 'post_entree' },
    ],
    dicts: { circuit: ['ATP', 'WTA'], date: ['2026-10-01', '2026-10-02'], mois: ['2026-10'], decision_ts: ['t'] },
    data: {
      circuit: [0, 1, 0, 0], cote_pin: [1.5, 2.1, null, 3.0], date: [0, 0, 1, 1], mois: [0, 0, 0, 0], decision_ts: [0, 0, 0, 0],
      cloture_pin: [1.4, 2, 2, 2.9], gagne: [1, 0, 1, null],
      clv_pinnacle: [1, -1, 2, 0], clv_jouable: [3, 1, 4, 2], clv_fr: [null, null, null, 5],
      pnl_pinnacle: [0.5, -1, 1.2, null], pnl_jouable: [0.6, -1, 1.3, null], pnl_fr: [null, null, null, null],
    },
  };
  const D = X.prepareMatchs(doc);
  assert.ok(!('cloture_pin' in D.num), 'la clôture (après coup) ne doit jamais être un filtre');
  const idx = X.filterIndices(D, { cats: { circuit: ['ATP'] }, ranges: { cote_pin: [1.4, 3.0] } });
  assert.deepEqual(idx, [0, 3]); // la ligne sans cote est exclue
  const p = X.stats(D, idx, 'pinnacle'), j = X.stats(D, idx, 'jouable'), f = X.stats(D, idx, 'fr');
  assert.equal(p.clv, 0.5); assert.equal(j.clv, 2.5); assert.equal(f.clv, 5); assert.equal(f.clvN, 1);
  const groups = X.splitGroups(D, [0, 1, 2, 3], 'cote_pin');
  assert.equal(groups.reduce((s, g) => s + g.members.length, 0), 3);
});

test('préparer le gel : critères multiples, plages et prix d’entrée sérialisés', () => {
  const D = X.prepareRows(fixture.rows, fixture.fields, 'matchs');
  X._state.kind = 'matchs';
  X._state.entry = 'fr';
  X._state.filters = { cats: { circuit: ['ATP', 'WTA'] }, ranges: { cote: [1.8, 2.4], move: [null, -3] } };
  const spec = X.freezeSpec(D, { n: 10, clv: 1.234, clvCi: [0.1, 2.3], roi: 4.5 });
  assert.equal(spec.jeu, 'matchs');
  assert.equal(spec.entree, 'fr');
  assert.deepEqual(spec.criteres, { circuit: ['ATP', 'WTA'] });
  assert.deepEqual(spec.plages, { cote: [1.8, 2.4], move: [null, -3] });
  assert.ok(JSON.stringify(spec).length < 4000);
});

test('rapide sur la taille réelle (≈ 20 000 lignes)', () => {
  const rows = [];
  for (let i = 0; i < 20000; i++) rows.push({ circuit: ['ATP', 'WTA', 'Challenger'][i % 3], type: i % 2 ? 'A' : 'B', cote: 1 + (i % 500) / 100, move: (i % 21) - 10, date: `2026-0${6 + (i % 4)}-01`, clv: (i % 7) - 3, pnl: i % 2 ? 1 : -1, gagne: i % 2 });
  const D = X.prepareRows(rows, fixture.fields);
  const t0 = Date.now();
  for (let r = 0; r < 20; r++) {
    const idx = X.filterIndices(D, { cats: { circuit: ['ATP', 'WTA'] }, ranges: { cote: [1.5, 3], move: [null, -3] } });
    X.stats(D, idx, 'alerte');
  }
  assert.ok((Date.now() - t0) / 20 < 100, 'filtrage + statistiques trop lents');
});

test('un pari par joueur et par match : premier horizon retenu, puis spécification du gel (21/10/2026)', () => {
  const doc = {
    n: 5, entrees: {},
    columns: [{ name: 'circuit', type: 'cat', role: 'filtre' }, { name: 'horizon', type: 'cat', role: 'filtre' },
      { name: 'date', type: 'cat', role: 'descriptif' }, { name: 'joueur', type: 'cat', role: 'descriptif' },
      { name: 'mois', type: 'cat', role: 'filtre' }, { name: 'decision_ts', type: 'cat', role: 'descriptif' }],
    dicts: { circuit: ['WTA'], horizon: ['24h', '6h', '1h', '10m'], date: ['2026-10-01', '2026-10-02'], joueur: ['A', 'B'],
      mois: ['2026-10'], decision_ts: ['t'] },
    data: { circuit: [0, 0, 0, 0, 0], horizon: [3, 1, 2, 3, 3], date: [0, 0, 0, 0, 1], joueur: [0, 0, 0, 1, 0],
      mois: [0, 0, 0, 0, 0], decision_ts: [0, 0, 0, 0, 0], gagne: [1, 1, 1, 0, 1],
      clv_pinnacle: [0, 0, 0, 0, 0], clv_jouable: [1, 2, 3, 4, 5], clv_fr: [null, null, null, null, null],
      pnl_pinnacle: [0, 0, 0, 0, 0], pnl_jouable: [1, 1, 1, -1, 1], pnl_fr: [null, null, null, null, null] },
  };
  const D = X.prepareMatchs(doc);
  // A le 01/10 : 10 min, 6 h, 1 h -> 6 h seulement ; B le 01/10 ; A le 02/10 (autre match)
  assert.deepEqual(X.premierHorizon(D, [0, 1, 2, 3, 4]), [1, 3, 4]);
  assert.deepEqual(X.premierHorizon(D, [0, 2]), [2]);
  X._state.kind = 'matchs'; X._state.entry = 'jouable'; X._state.unParJoueur = true;
  X._state.filters = { cats: { circuit: ['WTA'] }, ranges: {} };
  assert.equal(X.freezeSpec(D, { n: 3, clv: 1, clvCi: null, roi: 1 }).un_par_joueur, true);
  X._state.unParJoueur = false;
  assert.ok(!('un_par_joueur' in X.freezeSpec(D, { n: 3, clv: 1, clvCi: null, roi: 1 })));
  X._state.unParJoueur = true;
});
