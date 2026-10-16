// V7.2 « Matchs en direct » : parité Python/JS de la similarité, relâchements, fraîcheur, aucun champ post-décision.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const zlib = require('node:zlib');
const D = require('../research_direct.js');
const fx = JSON.parse(fs.readFileSync(path.join(__dirname, 'fixtures', 'direct_parity.json'), 'utf8'));

test('parité Python/JS : indices, relâchements, statistiques, verdict', () => {
  fx.profiles.forEach((p, j) => {
    const e = fx.expected[j];
    const r = D.similar(fx.rows, p);
    assert.deepEqual(r.idx, e.indices, `profil ${j}`);
    assert.deepEqual(r.relaxed, e.relaxed);
    assert.equal(r.ok, e.ok);
    const base = D.baseline(fx.rows, r.crit);
    assert.ok(Math.abs(base - e.base) < 1e-9);
    const s = D.stats(fx.rows, r.idx, base);
    assert.ok(Math.abs(s.clv.mean - e.clv_mean) < 1e-9);
    assert.ok(Math.abs(s.exces.mean - e.exces_mean) < 1e-9);
    assert.ok(Math.abs(s.roi.mean - e.roi_mean) < 1e-9);
    assert.equal(s.wins, e.wins); assert.equal(s.settled, e.settled);
    assert.equal(D.verdict(s, 0.05), e.verdict);
  });
  for (const [a, b, f] of fx.fair) assert.ok(Math.abs(D.powerFair(a, b) - f) < 1e-9);
  for (const [m, h] of fx.horizons) assert.equal(D.nearestHorizon(m), h);
});

test('ordre des relâchements : horizon jamais relâché, alerte en premier', () => {
  assert.deepEqual(D.RELAX.slice(0, 3), ['alerte', 'ecart', 'move_band']);
  const p = { horizon: '6h', circuit: 'ATP', surface: 'Hard', cote_pin: 2, move_dir: 'raccourcie', move_band: '−5 à −2 %', ecart_band: null, alerte: 'non' };
  const all = D.criteria(p, D.RELAX);
  assert.deepEqual(Object.keys(all).sort(), ['cote', 'horizon']);
  assert.ok(Math.abs(all.cote[1] - 2.7) < 1e-12);
  assert.equal(D.criteria(p, []).ecart_band, 'sans jouable');
  const r = D.similar([], p);
  assert.equal(r.ok, false); assert.equal(r.relaxed.length, D.RELAX.length);
});

test('aucun champ post-décision dans la similarité (rôles du jeu « Tous les matchs »)', () => {
  const forbidden = ['gagne', 'clv_pinnacle', 'clv_jouable', 'clv_fr', 'pnl_pinnacle', 'pnl_jouable', 'pnl_fr', 'cloture_pin', 'move_cloture_pct', 'proba_juste'];
  for (const f of D.SIMILARITY_FIELDS) assert.ok(!forbidden.includes(f), f);
  const gz = path.join(__dirname, '..', 'live', 'explorateur_matchs.json.gz');
  if (fs.existsSync(gz)) {
    const doc = JSON.parse(zlib.gunzipSync(fs.readFileSync(gz)).toString('utf8'));
    const roles = Object.fromEntries(doc.columns.map(c => [c.name, c.role]));
    for (const f of D.SIMILARITY_FIELDS) assert.equal(roles[f], 'filtre', f);
  }
  // rowMatches n'ouvre jamais un champ de mesure : une ligne sans mesures est jugée pareil.
  const row = { horizon: '6h', circuit: 'ATP', surface: 'Hard', cote_pin: 2, move_pin_pct: -3, ecart_jouable_pct: -1, alerte_avant: 'aucune' };
  const c = D.criteria({ horizon: '6h', circuit: 'ATP', surface: 'Hard', cote_pin: 2, move_dir: 'raccourcie', move_band: '−5 à −2 %', ecart_band: '−2 à 0 %', alerte: 'non' }, []);
  assert.equal(D.rowMatches(row, c), true);
  assert.equal(D.rowMatches({ ...row, gagne: 1, clv_pinnacle: 50, cloture_pin: 1.01 }, c), true);
});

test('fraîcheur affichée', () => {
  const now = Date.parse('2026-10-16T12:00:00Z');
  assert.equal(D.freshness('2026-10-16T11:59:40Z', now).text, 'mis à jour à l’instant');
  assert.deepEqual(D.freshness('2026-10-16T11:53:00Z', now), { text: 'mis à jour il y a 7 min', stale: false, minutes: 7 });
  assert.equal(D.freshness('2026-10-16T10:35:00Z', now).text, 'mis à jour il y a 1 h 25');
  assert.equal(D.freshness('2026-10-16T11:30:00Z', now).stale, true);
  assert.equal(D.freshness(null, now).stale, true);
});

test('profil du moment : prix récents seulement, écart vs Pinnacle juste, alerte passée', () => {
  const now = Date.parse('2026-10-16T12:00:00Z');
  const flags = { unibet: { jouable: true, fr: false, commission: 0 }, 'winamax.fr': { jouable: true, fr: true, commission: 0 },
    'betfair-ex': { jouable: true, fr: false, commission: 0.05 }, sbobet: { jouable: false } };
  const m = { uid: 'u', home: 'Ann B', away: 'Bob C', circuit: 'ATP', surface: 'Hard', commence: '2026-10-16T18:00:00Z',
    pin: { ouverture: { h: 2.0, a: 1.9, t: '2026-10-15T08:00:00Z' }, courant: { h: 1.8, a: 2.1, t: '2026-10-16T11:58:00Z' } },
    cotes: { unibet: [1.85, 2.0, '2026-10-16T11:50:00Z'], 'winamax.fr': [1.9, 1.95, '2026-10-16T10:00:00Z'], 'betfair-ex': [1.92, 2.1, '2026-10-16T11:59:00Z'], sbobet: [2.5, 1.5, '2026-10-16T11:59:00Z'] },
    alertes: [{ type: 'H16', joueur: 'Ann B', t: '2026-10-16T09:00:00' }] };
  const px = D.sidePrices(m, 'home', now, flags);
  assert.equal(px.best.jouable.book, 'betfair-ex');                 // 1 + 0,92 × 0,95 = 1,874 > 1,85
  assert.ok(Math.abs(px.best.jouable.eff - 1.874) < 1e-9);
  assert.equal(px.best.fr, null);                                   // winamax.fr : prix de plus de 30 min
  assert.ok(Math.abs(px.move - (-10)) < 1e-9);
  const p = D.profileFor(m, 'home', now, flags);
  assert.deepEqual([p.horizon, p.move_dir, p.move_band, p.alerte], ['6h', 'raccourcie', '≤ −5 %', 'oui']);
  assert.equal(D.profileFor(m, 'away', now, flags).alerte, 'non');
  assert.equal(D.profileFor({ ...m, commence: '2026-10-16T11:00:00Z' }, 'home', now, flags), null);  // en cours
});

test('cotes de live_odds.json plus récentes appliquées (côtés inversés gérés)', () => {
  const doc = { matchs: [{ home: 'Ann B', away: 'Bob C', commence: '2026-10-16T18:00:00Z', pin: { courant: { h: 1.8, a: 2.1, t: '2026-10-16T11:00:00Z' } }, cotes: {} }] };
  const live = [{ home_team: 'Bob C', away_team: 'Ann B', commence_time: '2026-10-16T18:00:00Z', books_match: { pinnacle: { home: 2.2, away: 1.75 }, unibet: { home: 2.1, away: 1.7 } } }];
  D.mergeLiveOdds(doc, live, '2026-10-16T11:55:00');
  assert.deepEqual(doc.matchs[0].pin.courant, { h: 1.75, a: 2.2, t: '2026-10-16T11:55:00Z' });
  assert.deepEqual(doc.matchs[0].cotes.unibet, [1.7, 2.1, '2026-10-16T11:55:00Z']);
  const enCours = { matchs: [{ home: 'Ann B', away: 'Bob C', commence: '2026-10-16T11:00:00Z', pin: { courant: { h: 1.8, a: 2.1, t: '2026-10-16T10:59:00Z' } }, cotes: {} }] };
  D.mergeLiveOdds(enCours, [{ ...live[0], commence_time: '2026-10-16T11:00:00Z' }], '2026-10-16T11:55:00');
  assert.equal(enCours.matchs[0].pin.courant.h, 1.8);            // pas de cote en jeu
});

test('lien fiche joueur : même slug que worker-joueurs.js', () => {
  assert.equal(D.slug('Félix Auger-Aliassime'), 'aliassime-auger-felix');
});
