// V7.3 « Base des matchs » : décodage du registre, meilleurs prix, filtres, cohérence CLV → gains.
const test = require('node:test');
const assert = require('node:assert/strict');
const R = require('../research_registre.js');
const R_ = R;
const D = require('../research_direct.js');

const doc = {
  points: ['open', '24h', '6h', '1h', '10m', 'close'],
  books: [{ nom: 'pinnacle', jouable: true, fr: false, commission: 0 }, { nom: 'betfair-ex', jouable: true, fr: false, commission: 0.05 },
    { nom: 'winamax.fr', jouable: true, fr: true, commission: 0 }],
  colonnes_horizons: ['horizon', 'cote_pin', 'proba_juste', 'book_jouable', 'cote_jouable', 'book_fr', 'cote_fr', 'ecart_jouable_pct',
    'move_pin_pct', 'alerte_avant', 'clv_pinnacle', 'clv_jouable', 'clv_fr', 'pnl_pinnacle', 'pnl_jouable', 'pnl_fr',
    'lecture_verdict', 'lecture_n', 'lecture_relaches', 'lecture_exces', 'lecture_exces_lo', 'lecture_exces_hi', 'lecture_base'],
  colonnes_alertes: ['type', 'cote_de', 'minutes_avant', 'book', 'cote', 'ampleur_pts', 'envoyee', 'clv_pin', 'pnl'],
  matchs: [
    { uid: 'm1', debut: '2026-10-02T12:00+00:00', mois: '2026-10', tournoi: 'ATP Metz', circuit: 'ATP', surface: 'Hard', joueurs: ['Alpha Un', 'Beta Deux'], vainqueur: 0,
      cotes: [[0, [[1800, 1.8], null, [360, 1.75], [60, 1.7], [10, 1.68], [5, 1.68]], [[1800, 2.1], null, [360, 2.15], [60, 2.2], [10, 2.25], [5, 2.25]]],
        [1, [[1700, 1.9], null, [360, 1.82], null, null, [5, 1.74]], [[1700, 2.2], null, [360, 2.3], null, null, [5, 2.4]]],
        [2, [[1600, 1.85], null, [360, 1.78], null, null, null], [[1600, 2.0], null, [360, 2.1], null, null, null]]],
      pinnacle: [[[1800, 1.8], [360, 1.75], [5, 1.68]], [[1800, 2.1], [5, 2.25]]],
      alertes: [['H13', 1, 300, 'betfair-ex', 2.3, 2.1, 1, 3.5, -1]],
      horizons: [[0, '6h', 1.75, 0.55, 'betfair-ex', 1.779, 'winamax.fr', 1.78, -2.1, -2.8, 'aucune', 1.2, 0.9, 1.1, 0.75, 0.779, 0.78, 'sur-coté', 40, 2, -1.1, -2, -0.2, -3.4]] },
    { uid: 'm2', debut: '2026-10-03T12:00+00:00', mois: '2026-10', tournoi: 'ATP Challenger Roanne', circuit: 'Challenger', surface: 'Hard', joueurs: ['Gamma', 'Delta'], vainqueur: null,
      sans_courbe: true, cotes: [], pinnacle: [[], []], alertes: [['PUBLIC', 0, 120, 'unibet', 2.5, 3, 0, null, null]], horizons: [] },
  ],
};

test('décodage : colonnes nommées, côté conservé', () => {
  const list = R.decodeMonth(doc);
  assert.equal(list.length, 2);
  assert.equal(list[0].horizons[0].side, 0);
  assert.equal(list[0].horizons[0].lecture_verdict, 'sur-coté');
  assert.equal(list[0].alertes[0].type, 'H13');
  assert.equal(list[0].alertes[0].cote_de, 1);
  assert.equal(R.lectureOf(list[0]), 'sur-coté');
});

test('Pinnacle juste et meilleur prix net de commission, Pinnacle exclu', () => {
  const m = { ...R.decodeMonth(doc)[0], _pinIx: 0 };
  const fair = R.fairRow(m, 0, 6);
  assert.ok(Math.abs(fair[0] - R.powerFair(1.8, 2.1)) < 1e-12);
  assert.equal(fair[1], null);
  const best = R.bestRow(m, 0, 6, doc.books);
  // ouverture : betfair 1.9 net = 1 + 0.9 × 0.95 = 1.855 > winamax 1.85
  assert.equal(best[0].book, 'betfair-ex');
  assert.ok(Math.abs(best[0].odds - 1.855) < 1e-12);
  // 6 h : betfair 1.82 net = 1.779 < winamax 1.78
  assert.equal(best[2].book, 'winamax.fr');
  const fr = R.bestRow(m, 0, 6, doc.books, true);
  assert.equal(fr[0].book, 'winamax.fr');
  assert.equal(fr[5], null);
});

test('filtres cumulables', () => {
  const list = R.decodeMonth(doc);
  assert.equal(R.filterMatches(list, { q: 'roanne' }).length, 1);
  assert.equal(R.filterMatches(list, { alerte: 'H' }).length, 1);
  assert.equal(R.filterMatches(list, { alerte: 'PUBLIC', circuit: 'Challenger' }).length, 1);
  assert.equal(R.filterMatches(list, { lecture: 'sur-coté' }).length, 1);
  assert.equal(R.filterMatches(list, { courbe: 'sans' })[0].uid, 'm2');
  assert.equal(R.filterMatches(list, { resultat: 'avec' })[0].uid, 'm1');
});

test('cohérence CLV → gains : mêmes règles que Python (cas du tipster)', () => {
  const ok = R.coherence(Array.from({ length: 200 }, (_, i) => [2.0, 0.0, i % 2 ? 1 : -1]));
  assert.equal(ok.etat, 'cohérent');
  const tip = R.coherence(Array.from({ length: 1000 }, (_, i) => [2.0, 2.0, i % 5 < 2 ? 1 : -1]));
  assert.ok(tip.z < -2);
  assert.equal(tip.etat, 'la CLV ne se transforme pas en gains');
  assert.equal(R.coherence([[2, 1, 1]]).etat, 'trop peu de paris');
  // même fonction dans « Matchs en direct »
  assert.deepEqual(D.coherence(Array.from({ length: 1000 }, (_, i) => [2.0, 2.0, i % 5 < 2 ? 1 : -1])), tip);
});

test('fiche : complète avec courbes, réduite sans courbe', () => {
  const [m1, m2] = R.decodeMonth(doc).map(m => ({ ...m, _pinIx: 0 }));
  const h1 = R.fiche(m1, doc);
  assert.match(h1, /Cotes de l'ouverture à la clôture — Alpha Un/);
  assert.match(h1, /Pinnacle juste/);
  assert.match(h1, /rg-best/);
  assert.match(h1, /sur-coté/);
  assert.match(h1, /<svg/);
  const h2 = R.fiche(m2, doc);
  assert.match(h2, /Courbes de cotes non collectées/);
  assert.match(h2, /PUBLIC/);
  assert.doesNotMatch(h2, /<svg/);
});

test('évaluation : tableaux rendus, aucune donnée inventée', () => {
  const html = R.evaluation({
    lectures: { lignes_lues: 10, correlation: 0.036, par_verdict: [{ verdict: 'sur-coté', horizon: 'tous', lignes: 5, exces_realise: { n: 5, moyenne: -0.5, ic95: [-0.8, -0.2] } }], par_quintile: [] },
    fiabilite_cloture: { cotes_jugees: 40, par_tranche: [{ groupe: '60–70 %', n: 40, proba_juste: 0.65, proba_brute: 0.67, victoires: 0.6, ecart_pts: -5, ic95_pts: [-10, 0], z: -1.2, etat: 'conforme' }] },
    coherence_matchs: [{ horizon: 'tous', entree: 'pinnacle', n: 100, roi_attendu: -4.5, roi_reel: -3.6, z: 1.06, etat: 'cohérent' }],
    coherence_hypotheses: [],
  });
  assert.match(html, /ne prédisent presque rien/);
  assert.match(html, /La clôture Pinnacle est-elle juste/);
  assert.match(html, /cohérent/);
  assert.equal(R.evaluation(null), '');
});

test('écart de victoires des profils : tableau et conclusion', () => {
  const g = (groupe, n) => ({ groupe, n, gagne: 0.433, attendu: 0.431, ecart_pts: 0.2, ic95_pts: [-5.5, 5.9], roi_pinnacle: -3.4 });
  const html = R.victoires({ lignes: 12859, min_regles: 20, correlation: 0.004, par_ecart: [g('≥ 15 pts en plus', 275), g('vide', 0)], par_z: [g('z ≥ 2,5', 235)] });
  assert.match(html, /ne dit rien/);
  assert.match(html, /≥ 15 pts en plus/);
  assert.doesNotMatch(html, /vide/);
  assert.equal(R.victoires(null), '');
});

test('H19 : suivi gelé, rétrospectif marqué « ne compte pas », grille', () => {
  const s = (n, m) => ({ n, clv: { n, mean: m, ci: [m - 1, m + 1] }, roi: { mean: 5, ci: [-20, 30] }, persistance: 0.4, regles: n, mois_clv_positif: '3/3' });
  const V = {
    h19: { regle: { gele_le: '2026-10-16', age_max_min: 30, ecart_min_pct: 2, ecart_max_pct: 8, cible_n: 300 }, gel: { etat: 'intact' },
      prospectif: { ...s(0, null), verdict: 'EN COURS — 0/300, aucun verdict avant la cible' }, retrospectif: s(227, 2.31),
      decoupes_retrospectives: { persistance: [{ groupe: 'prix disparu avant la clôture', ...s(136, 3.1) }] } },
    grille: { cases_testees: 20, cases: [{ case: 'écart ≥ 2 %', ...s(241, 2.33), p_holm: 0.0001 }, { case: 'petite', ...s(5, 9) }] },
  };
  const html = R.valeurBlock(V);
  assert.match(html, /gelée le 2026-10-16/);
  assert.match(html, /intact/);
  assert.match(html, /EN COURS/);
  assert.match(html, /ne compte pas/);
  assert.match(html, /prix disparu avant la clôture/);
  assert.match(html, /écart ≥ 2 %/);
  assert.doesNotMatch(html, /petite/);
  assert.equal(R.valeurBlock(null), '');
});

test('table des books collectés', () => {
  const html = R.booksBlock({ books: { matchs: 2744, decisions: 12039, books: [{ book: 'bet365', matchs: 1262, couverture: 0.46, meilleur_prix: 0.053, ecart_median: -6.7, au_dessus_2pct: 100, fr: false, bourse: false }, { book: 'winamax.fr', matchs: 439, couverture: 0.16, meilleur_prix: 0.003, ecart_median: -6.2, au_dessus_2pct: 0, fr: true, bourse: false }] } });
  assert.match(html, /Les books collectés/);
  assert.match(html, /bet365/);
  assert.match(html, /🇫🇷/);
  assert.equal(R.booksBlock(null), '');
});

test('délai alerte -> pari : tableau par hypothèse et par délai', () => {
  const r = (h, d, t) => ({ hypothese: h, delai_min: d, n: 17, prix_tenu: t, clv_au_prix_disponible: 0.5, clv_au_prix_alerte: 2.81, clv_meilleur_book: 5.8 });
  const html = R.delaiBlock({ alertes_envoyees: 581, sans_courbe_du_book: 250, delais_min: [0, 5], resume: [r('H17', 0, 0.65), r('H17', 5, 0.65), r('toutes', 0, 0.88), r('toutes', 5, 0.82)] });
  assert.match(html, /Le prix tient-il/);
  assert.match(html, /H17/);
  assert.match(html, /\+5 min/);
  assert.ok(html.indexOf('H17') < html.indexOf('toutes'));
  assert.equal(R.delaiBlock(null), '');
});

test('croisements : écarts découverte / confirmation, statut, rien d\'inventé', () => {
  const L = (c, i, d, k, st) => ({ famille: 'Marché', circonstance: c, issue: i, statut: st,
    decouverte: { n: 300, ecart: d, z: d / 2 }, confirmation: { n: 300, ecart: k, z: k / 2 } });
  const C = { matchs: 2706, periode: ['2026-06-07', '2026-10-21'], tests_holm: 92,
    issues: [{ cle: 'victoire', libelle: 'victoire du favori' }, { cle: '2-0', libelle: 'favori gagne 2-0' }],
    lignes: [L('cote stable', 'victoire', 1.2, 0.4, 'rien'), L('cote stable', '2-0', -4.4, 1.3, 'à suivre')] };
  const html = R.croisementsBlock(C);
  assert.match(html, /Croisements : l'issue selon les circonstances/);
  assert.match(html, /Aucun croisement confirmé/);
  assert.match(html, /À suivre/);
  assert.match(html, /rg-suivre/);
  assert.match(html, /cote stable/);
  const C2 = { ...C, lignes: [L('cote stable', 'victoire', -6, -5, 'confirmé')] };
  assert.match(R.croisementsBlock(C2), /Confirmé/);
  assert.equal(R.croisementsBlock(null), '');
});

test('pronostics du jour : deux versions côte à côte et compteur', () => {
  const v = (p, sc) => ({ p_home: p, sets: { '2-0': 0.4, '2-1': 0.2, '1-2': 0.2, '0-2': 0.2 }, scores_probables: [[sc, 0.034], ['4-6 6-3 6-4', 0.012]],
    remontee: { home: 0.11, away: 0.08 }, jeux_moyen: 22.6 });
  const P = { horizon_h: 36, matchs: [
    { debut: '2026-10-22T04:00', tournoi: 'ATP Challenger Guangzhou', surface: 'Hard', meilleur_des: 3, home: 'Liam Broady', away: 'Akira Santillan',
      stats: v(0.75, '6-3 6-3'), marche: v(0.31, '4-6 4-6') },
    { debut: '2026-10-22T05:00', tournoi: 'WTA Osaka', surface: 'Hard', meilleur_des: 3, home: 'A B', away: 'C D', stats: v(0.5, '6-4 6-4'), marche: null }] };
  const B = { tous: { stats_seules: { n: 120, reussite_pct: 64.2 }, stats_plus_marche: { n: 118, reussite_pct: 66.1 } }, '7_derniers_jours': {} };
  const html = R.pronosticsBlock(P, B);
  assert.match(html, /Pronostics du jour \(2 matchs dans les 36 h\)/);
  assert.match(html, /<b>Broady<\/b> 75 %/);
  assert.match(html, /<b>Santillan<\/b> 69 %/);
  assert.match(html, /6-3 6-3 <small>3,4 % <span class="rg-cote">· 29,4<\/span><\/small>/);
  assert.match(html, /<b>Broady<\/b> 75 % <span class="rg-cote">· 1,33<\/span><span class="detail">adversaire : 4,00<\/span>/);
  assert.match(html, /2-0 40 % <span class="rg-cote">· 2,50<\/span>/);
  assert.match(html, /4-6 6-3 6-4/);
  assert.match(html, /gagne après avoir perdu le 1er set : Broady 11 %/);
  assert.match(html, /Pinnacle ne cote pas encore ce match/);
  assert.match(html, /64,2 %/);
  assert.match(html, /pas encore de match joué/);
  assert.equal(R.pronosticsBlock(null), '');
});

test('match simulé : feuille prévue, fourchette, match type, version marché en priorité (22/10/2026)', () => {
  const x = (moy, p10, p90) => ({ moy, p10, p90 });
  const f = a => ({ aces: x(a, 3, 12), doubles_fautes: x(2.4, 0, 5), premiere_pct: x(61.2, 54, 68), gagnes_1re_pct: x(74, 64, 83),
    gagnes_2e_pct: x(51, 38, 64), balles_break_obtenues: x(6, 2, 11), breaks: x(2.1, 0, 4), jeux_service_gagnes_pct: x(80, 64, 94), points_gagnes: x(70, 50, 95) });
  const sim = (n, v) => ({ n, victoire_A: v, jeux: x(22.8, 17, 31), tiebreak: 0.34, scores: [['6-4 6-4', 0.031], ['6-3 6-4', 0.029]],
    feuille: [f(8.4), f(3.1)], profil_connu: [true, false],
    match_type: { score: '6-4 6-4', sets: [[6, 4], [7, 6]], breaks: [[0, 2, 2, 0]], feuille: [{ aces: 9, doubles_fautes: 1, premiere_pct: 62 }, { aces: 1, doubles_fautes: 3, premiere_pct: 58 }] } });
  const m = { uid: 'u1', home: 'Arthur Fils', away: 'Hugo Gaston', stats: { match_simule: sim(5000, 0.61) }, marche: { match_simule: sim(5000, 0.7) } };
  const html = R.simuleBlock(m, new Set(['u1']));
  assert.match(html, /<details class="rg-sim" data-sim="u1" open>/);
  assert.match(html, /Match simulé 5\s000 fois/);
  assert.match(html, /Niveau : cote Pinnacle/);
  assert.match(html, /Fils gagne 70 %/);
  assert.match(html, /<b>8,4<\/b><span class="detail">3–12<\/span>/);
  assert.match(html, /Profil de service inconnu pour Hugo Gaston/);
  assert.match(html, /Set 1 · 6-4<\/b> — break : Fils \(3-2\)/);
  assert.match(html, /Set 2 · 7-6<\/b> \(tie-break\) — aucun break/);
  assert.match(html, /Fils : 9 aces, 1 double faute/);
  assert.match(html, /Gaston : 1 ace, 3 doubles fautes/);
  assert.match(R.simuleBlock({ ...m, marche: null }), /Niveau : classement Elo/);
  assert.equal(R.simuleBlock({ stats: {}, marche: null }), '');
  assert.match(R.pronosticsBlock({ horizon_h: 36, simulations: 5000, profils_au: '2026-06-02', matchs: [{ ...m, debut: '2026-10-22T04:00', tournoi: 'ATP Brussels', surface: 'Hard', meilleur_des: 3,
    stats: { ...m.stats, p_home: 0.6, sets: {} }, marche: { ...m.marche, p_home: 0.7, sets: {} } }] }, null), /joué 5\s000 fois point par point avec les seules statistiques/);
});

test('pronostics : suivi du match simulé contre la vraie feuille (22/10/2026)', () => {
  const B = { tous: {}, '7_derniers_jours': {}, match_simule_contre_feuille: { n: 42, stats: {
    aces: { n: 84, prevu: 4.6, reel: 5.1, ecart_moyen: 2.2, dans_fourchette_pct: 81.0 },
    total_jeux: { n: 42, prevu: 23.4, reel: 24.0, ecart_moyen: 4.9, dans_fourchette_pct: 83.3 } } } };
  const html = R.pronosticsBlock({ horizon_h: 36, simulations: 5000, matchs: [] }, B);
  assert.match(html, /Match simulé contre la vraie feuille \(42 matchs joués\)/);
  assert.match(html, /<td>Aces<\/td><td>4,6<\/td><td>5,1<\/td><td>2,2<\/td><td>81 %<\/td>/);
  assert.match(html, /Total de jeux/);
  assert.match(R.pronosticsBlock({ horizon_h: 36, simulations: 5000, matchs: [] }, { tous: {}, match_simule_contre_feuille: { n: 0 } }), /en attente des premiers matchs/);
});

test('profils de service : recherche, fiche, centiles, évolution, liens depuis les pronostics (22/10/2026)', () => {
  const t = x => ({ f: 0.6, a: x, d: 0.08, w1: 0.74, w2j: 0.55, serv: 0.65, ra: 0.1, ret1: 0.27, ret2: 0.48, ret: 0.36 });
  const doc = { moyennes: { ATP: { all: t(0.12), Hard: t(0.13) } }, joueurs: {
    k1: { nom: 'Arthur Fils', circuit: 'ATP', balles: 4200, dernier_match: '2026-10-20', evolution: [['2026-09', 6, 8.2, 61.5, 75.1, 52.0, 66.3, 37.9]],
      surfaces: { all: { balles: 4200, joueur: t(0.18), centiles: { a: 88, d: 20 } }, Hard: { balles: 2500, joueur: t(0.2) } } },
    k2: { nom: 'Hugo Gaston', circuit: 'ATP', balles: 3000, dernier_match: '2026-10-19', surfaces: { all: { balles: 3000, joueur: t(0.05) } } } } };
  assert.deepEqual(R.chercherJoueurs(doc, 'fils').map(x => x[0]), ['k1']);
  assert.deepEqual(R.chercherJoueurs(doc, 'h'), []);                                     // au moins 2 lettres
  const f = R.ficheService(doc, 'k1');
  assert.match(f, /<b>Arthur Fils<\/b>/);
  assert.match(f, /Aces par 1re balle dans le court<\/td><td><b>18 %<\/b><span class="rg-cent good">88<sup>e<\/sup> centile<\/span><span class="detail">circuit 12 %<\/span>/);
  assert.match(f, /<th>Dur<span class="detail">2\s500 balles<\/span><\/th>/);
  assert.match(f, /rg-cent bad">20/);
  assert.match(f, /2026-09<\/td><td>6<\/td><td>8,2<\/td>/);
  assert.match(R.ficheService(doc, 'absent'), /Pas de profil/);
  assert.match(R.serviceInner(doc, 'gas', null), /data-serv-key="k2">Hugo Gaston/);
  const P = { horizon_h: 36, matchs: [{ uid: 'u', cles: ['k1', 'k2'], debut: '2026-10-22T04:00', tournoi: 'ATP Brussels', surface: 'Hard', meilleur_des: 3,
    home: 'Arthur Fils', away: 'Hugo Gaston', stats: { p_home: 0.6, sets: {} }, marche: null }] };
  assert.match(R.pronosticsBlock(P, null), /Profil de service : <button type="button" data-serv-key="k1">Fils<\/button>/);
});

test('simulation pure : ligne principale, compteur, match simulé joué sans classement ni cote (22/10/2026)', () => {
  const x = (moy, p10, p90) => ({ moy, p10, p90 });
  const f = { aces: x(5, 2, 9), doubles_fautes: x(3, 1, 5), premiere_pct: x(62, 55, 69), gagnes_1re_pct: x(72, 62, 81), gagnes_2e_pct: x(50, 38, 62),
    balles_break_obtenues: x(6, 2, 11), breaks: x(2, 0, 4), jeux_service_gagnes_pct: x(78, 60, 92), points_gagnes: x(70, 50, 95) };
  const sim = { n: 5000, victoire_A: 0.7, jeux: x(22, 17, 30), tiebreak: 0.3, scores: [['6-3 6-4', 0.03]], feuille: [f, f], profil_connu: [true, true] };
  const v = p => ({ p_home: p, sets: { '2-0': 0.45 }, scores_probables: [['6-3 6-4', 0.03]], jeux_moyen: 22 });
  const m = { uid: 'u', debut: '2026-10-22T04:00', tournoi: 'ATP Vienna', surface: 'Hard', meilleur_des: 3, home: 'Arthur Fils', away: 'Hugo Gaston',
    simulation: { ...v(0.7), match_simule: sim }, stats: v(0.62), marche: v(0.66) };
  const B = { tous: { simulation: { n: 40, reussite_pct: 66.5 }, stats_seules: { n: 40, reussite_pct: 64 }, stats_plus_marche: { n: 38, reussite_pct: 68 } }, '7_derniers_jours': {} };
  const html = R.pronosticsBlock({ horizon_h: 36, simulations: 5000, matchs: [m] }, B);
  assert.match(html, /<b>Simulation<\/b><span class="detail">5\s000 matchs joués<\/span><\/td><td><b>Fils<\/b> 70 %/);
  assert.match(html, /Classement Elo<\/td><td><b>Fils<\/b> 62 %/);
  assert.match(html, /Cote Pinnacle<\/td><td><b>Fils<\/b> 66 %/);
  assert.match(html, /Réussite simulation<\/small><b>66,5 %<\/b>/);
  assert.match(R.simuleBlock(m), /Match joué avec les seules statistiques des deux joueurs/);
});

test('facteurs du match : ce qui pèse, seulement les groupes adoptés (22/10/2026)', () => {
  const v = p => ({ p_home: p, sets: {}, scores_probables: [], jeux_moyen: 22 });
  const m = { uid: 'u', debut: '2026-10-22T04:00', tournoi: 'ATP Vienna', surface: 'Hard', meilleur_des: 3, home: 'Arthur Fils', away: 'Hugo Gaston',
    simulation: { ...v(0.55), facteurs: { sans: 0.6, avec: 0.55, groupes: { forme_fatigue: -4.2, vitesse_court: 0.3 } } }, stats: v(0.6), marche: null };
  const f = R.facteursBlock(m);
  assert.match(f, /Ce qui pèse pour Fils : Forme récente et fatigue <b>−4,2 pt<\/b> · Vitesse du court <b>\+0,3 pt<\/b>/);
  assert.match(f, /60 % sans, 55 % avec/);
  assert.equal(R.facteursBlock({ simulation: v(0.5) }), '');
  const html = R.pronosticsBlock({ horizon_h: 36, simulations: 5000, facteurs_adoptes: ['forme_fatigue'], matchs: [m] }, null);
  assert.match(html, /Facteurs du match retenus par le test : Forme récente et fatigue\./);
  assert.match(html, /rg-facteurs/);
});

test('simulation + Elo et calibration (22/10/2026)', () => {
  const v = p => ({ p_home: p, sets: {}, scores_probables: [], jeux_moyen: 22 });
  const m = { uid: 'u', debut: '2026-10-22T04:00', tournoi: 'ATP Vienna', surface: 'Hard', meilleur_des: 3, home: 'Arthur Fils', away: 'Hugo Gaston',
    combinaison: v(0.64), simulation: v(0.7), stats: v(0.6), marche: null };
  const B = { tous: { combinaison: { n: 12, reussite_pct: 70 } }, '7_derniers_jours': {},
    calibration: { combinaison: [{ tranche: '60–70 %', n: 12, prevu: 64, reel: 66.7 }], simulation: [{ tranche: '70–80 %', n: 5, prevu: 72, reel: 60 }] },
    par_circuit: { ATP: { combinaison: { n: 12, reussite_pct: 70 } } } };
  const html = R.pronosticsBlock({ horizon_h: 36, simulations: 5000, combinaison: { elo: 0.6, simulation: 0.5 }, matchs: [m] }, B);
  assert.match(html, /<b>Simulation \+ Elo<\/b>.*<b>Fils<\/b> 64 %/s);
  assert.match(html, /Réussite simulation \+ Elo<\/small><b>70 %<\/b>/);
  const c = R.calibrationBlock(B);
  assert.match(c, /<td>60–70 %<\/td><td>67 % <small>\(12\)<\/small><\/td><td>—<\/td>/);
  assert.match(c, /<td>ATP<\/td><td>70 % <small>\(12\)<\/small><\/td>/);
  assert.equal(R.calibrationBlock(null), '');
});

test('en direct : même calcul exact que simulateur/direct.py (22/10/2026)', () => {
  const N = [[-3.0, 0.0022182], [-2.5, 0.00877313], [-2.0, 0.02702316], [-1.5, 0.06482519], [-1.0, 0.12110939], [-0.5, 0.17621312], [0.0, 0.19967563], [0.5, 0.17621312], [1.0, 0.12110939], [1.5, 0.06482519], [2.0, 0.02702316], [2.5, 0.00877313], [3.0, 0.0022182]];
  const d = { a: 0.66, b: 0.62, sigma: 0.15, sets_gagnants: 2, tb_final: 7 };
  const cas = [[[], 0, 0, true, [0, 0], 0.647195616, 0.647195616], [[[6, 1]], 4, 0, true, [0, 0], 0.998594199, 0.986323688],
    [[[6, 4], [4, 6]], 6, 6, true, [5, 6], 0.342832449, 0.359979224], [[[3, 6]], 5, 4, false, [2, 3], 0.31393115, 0.403461101],
    [[[7, 6], [4, 6]], 2, 3, true, [4, 3], 0.503400832, 0.565048423]];
  for (const [S, ga, gb, hs, pts, p, p0] of cas) {
    const r = R.enDirect(d, N, S, ga, gb, hs, pts);
    assert.ok(Math.abs(r.p - p) < 1e-6, `${JSON.stringify(S)} ${ga}-${gb} : ${r.p} ≠ ${p}`);
    assert.ok(Math.abs(r.p0 - p0) < 1e-6);
  }
  assert.deepEqual(R.lireScore('6-4 3-6', '2-1', '40-AV'), { sets: [[6, 4], [3, 6]], jeux: [2, 1], points: [3, 4] });
  assert.deepEqual(R.lireScore('', '6-6', '5-4').points, [5, 4]);
  assert.match(R.lireScore('6/4', '', '').erreur, /Sets terminés/);
  const m = { uid: 'u', home: 'Arthur Fils', away: 'Hugo Gaston', direct: d };
  assert.match(R.directBlock(m, N), /En direct : le % depuis le score/);
  assert.equal(R.directBlock({ uid: 'x' }, N), '');
  assert.match(R.directResultat(m, N, { sets: '6-1', jeux: '4-0', points: '', homeSert: true }), /<b>Fils<\/b> 99,9 %|<b>Fils<\/b> 100 %/);
  assert.match(R.directResultat(m, N, { sets: 'x', jeux: '', points: '', homeSert: true }), /Sets terminés/);
});

test('prédit / réel (22/10/2026)', () => {
  const R = { n: 1, matchs: [{ uid: 'u', debut: '2026-10-21T14:00', home: 'Arthur Fils', away: 'Hugo Gaston', tournoi: 'ATP Vienna',
    reel: { gagnant: 'home', sets: '2-0', score: '6-4 6-4', jeux: 20 },
    premier: { combinaison: { p_home: 0.68, vainqueur_juste: true, sets_prevus: '2-0', sets_justes: true, score_prevu: '6-4 6-4', score_juste: true },
      simulation: { p_home: 0.45, vainqueur_juste: false }, stats: { p_home: 0.7, vainqueur_juste: true }, marche: { p_home: 0.66, vainqueur_juste: true } } }] };
  const h = R_.resultatsBlock(R);
  assert.match(h, /Prédit \/ réel \(1 matchs joués\)/);
  assert.match(h, /<small>Simulation \+ Elo<\/small><b>1\/1<\/b>/);
  assert.match(h, /<small>Simulation<\/small><b>0\/1<\/b>/);
  assert.match(h, /<b>Fils<\/b> 68 %.*score : 6-4 6-4/s);
  assert.match(h, /21\/10 · Arthur Fils – Hugo Gaston/);
  assert.match(h, /✓<\/span> vainqueur<br><span class="good">✓<\/span> sets<br><span class="good">✓<\/span> score/);
  assert.match(R_.resultatsBlock({ matchs: [] }), /Aucun match joué/);
  assert.equal(R_.resultatsBlock(null), '');
});

test('explorateur des pronostics (22/10/2026)', () => {
  const colonnes = ['date', 'circuit', 'surface', 'bo', 'tour', 'niveau', 'tournoi', 'gagnant', 'perdant', 'matchs_min', 'elo', 'simulation', 'combinaison', 'pinnacle'];
  const lignes = [];
  for (let i = 0; i < 400; i++) {
    const atp = i % 2 === 0;
    lignes.push([i < 200 ? '2024-05-01' : '2025-05-01', atp ? 'ATP' : 'WTA', 'Hard', 3, 6, 'A', 'T', 'g', 'p', 120,
      i % 4 === 0 ? 0.4 : 0.7, atp ? 0.7 : (i % 4 === 1 ? 0.4 : 0.65), 0.68, 0.72]);
  }
  const doc = { colonnes, lignes, debut_jugement: '2025-01-01' };
  const all = R.xpStats(R.xpFiltrer(doc, {}), 'simulation');
  assert.equal(all.n, 400);
  assert.ok(Math.abs(all.ok - 0.75) < 1e-9);
  const atp = R.xpStats(R.xpFiltrer(doc, { circuit: 'ATP' }), 'simulation');
  assert.equal(atp.ok, 1);
  const scan = R.xpScan(doc, {}, 150);
  const c = scan.find(z => z.critere === 'Circuit' && z.valeur === 'ATP');
  assert.ok(c && Math.abs(c.vsElo - 0.5) < 1e-9);                  // ATP : simulation 100 %, Elo 50 %
  const h = R.explorateurBlock(doc, { circuit: 'WTA' }, true);
  assert.match(h, /200 matchs dans ce filtre/);
  assert.match(h, /<option selected>WTA<\/option>/);
  assert.match(R.explorateurBlock(null, {}, true), /Chargement/);
  assert.doesNotMatch(R.explorateurBlock(doc, {}, false), /<table>/);
});
