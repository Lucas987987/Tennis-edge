// Paquet 511 — le moteur du % en direct du worker est MOT POUR MOT celui de la page (algo/index.html) et donne le même
// % ; la notification de fin de set l'affiche ; la feuille de stats n'est lue qu'au coffre (récente), jamais demandée.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import * as MO from './moteur.js';
import * as N from './notifs.js';

const page = fs.readFileSync(new URL('../../algo/index.html', import.meta.url), 'utf8');
const mod = fs.readFileSync(new URL('./moteur.js', import.meta.url), 'utf8');
function fonction(src, nom) {
  const i = src.indexOf(`function ${nom}(`); assert.ok(i >= 0, nom);
  let k = src.indexOf('{', i), d = 0;
  for (; k < src.length; k++) { if (src[k] === '{') d++; else if (src[k] === '}' && --d === 0) break; }
  return src.slice(i, k + 1);
}

test('511 : chaque fonction du moteur est celle de la page, mot pour mot', () => {
  for (const nom of MO.SOURCES) assert.equal(fonction(mod, nom), fonction(page, nom), nom);
  const ligne = (src, d) => src.slice(src.indexOf(d), src.indexOf('\n', src.indexOf(d)));
  assert.equal(ligne(mod, 'const PT_LIVE = '), ligne(page, 'const PT_LIVE = '));
  const gh = (src) => src.slice(src.indexOf('const GH9 = '), src.indexOf(']];', src.indexOf('const GH9 = ')) + 3);
  assert.equal(gh(mod), gh(page));
});

test('511 : même % que la page (sans et avec feuille de stats, serveur connu ou non, sens inversé)', () => {
  // la page, reconstituée avec ses propres fonctions et des réservoirs vides
  const corps = ['const logit = p => Math.log(p/(1-p)), sig = z => 1/(1+Math.exp(-z));',
    'const setFini = (g, o) => (Math.max(g, o) >= 6 && Math.abs(g - o) >= 2) || (Math.max(g, o) === 7 && Math.min(g, o) >= 5);',
    page.slice(page.indexOf('const PT_LIVE = '), page.indexOf('\n', page.indexOf('const PT_LIVE = '))),
    page.slice(page.indexOf('const GH9 = '), page.indexOf(']];', page.indexOf('const GH9 = ')) + 3),
    ...MO.SOURCES.map((n) => fonction(page, n)), 'return { pctLive, LIVE };'].join('\n');
  const fabrique = (sigma, stats, uid) => new Function('LIVE', 'D', corps)(
    { moteurs: {}, formes: {}, reeval: {}, stats: stats ? { [uid]: { o: { stats } } } : {} }, { live_reevaluation: { sigma } });
  const sigma = { ATP: 0.15, WTA: 0.15, CH: 0.225 };
  const stats = { firstServeAccuracy: [30, 41, 27, 44], servicePointsScored: [29, null, 24, null] };
  let n = 0;
  for (const [sh, sa, pt, srv] of [[[6, 0], [4, 0], ['0', '0'], 'home'], [[3, 6, 2], [6, 4, 1], ['30', '15'], 'away'],
    [[6, 6], [7, 6], ['3', '5'], null], [[7, 5], [6, 3], ['40', 'A'], 'home']]) {
    for (const inverse of [false, true]) for (const st of [null, stats]) {
      const m = { uid: 'u' + n++, circuit: 'ATP', p_home: 0.58, simulation: { a: 0.65, b: 0.62, sets_gagnants: 2, tb_final: 7 } };
      const x = { score_home: { sets: sh, point: pt[0] }, score_away: { sets: sa, point: pt[1] }, serveur: srv };
      const P = fabrique(sigma, st, m.uid).pctLive(m, { x, inverse });
      assert.ok(Number.isFinite(P) || P === null);
      assert.equal(MO.pctDirect(m, { x, inverse }, sigma, st), P);
    }
  }
});

test('511 : la notification de fin de set dit le % en direct ; sans % calculé, rien de plus', async () => {
  const m = { uid: 'a_b', home: 'Jannik Sinner', away: 'Carlos Alcaraz', p_home: 0.6, circuit: 'ATP',
    simulation: { a: 0.66, b: 0.63, sets_gagnants: 2 } };
  const e = { type: 'set', qui: 'h', set: 1, sets: '1-0', score: '6-4', p_direct: 0.712 };
  assert.equal(N.message(e, m, 'fr').texte, 'Jannik Sinner – Carlos Alcaraz · 6-4 · Sets : 1-0 · L\'algo donne maintenant Jannik Sinner gagnant à 71 %');
  assert.match(N.message({ ...e, p_direct: 0.3 }, m, 'en').texte, /The algo now has Carlos Alcaraz winning at 70%$/);
  assert.equal(N.message({ ...e, p_direct: null }, m, 'fr').texte, 'Jannik Sinner – Carlos Alcaraz · 6-4 · Sets : 1-0');
  // feuille de stats : lue au coffre seulement si récente ; aucune requête réseau
  let reseau = 0; globalThis.fetch = async () => { reseau++; return new Response('', { status: 500 }); };
  const store = new Map();
  const env = { COFFRE: { get: async (k) => (store.has(k) ? { body: store.get(k), etag: 'e', text: async () => store.get(k) } : null) } };
  const x = { id: 77, score_home: { sets: [6, 0], point: '0' }, score_away: { sets: [4, 0], point: '0' }, serveur: 'home' };
  const sans = await N.pctApresSet(env, m, x, false, 1e12);
  store.set('live/stats/77.json', JSON.stringify({ maj: 1e12 - 60e3, stats: { firstServeAccuracy: [30, 41, 27, 44], servicePointsScored: [29, null, 24, null] } }));
  const avec = await N.pctApresSet(env, m, x, false, 1e12);
  const vieux = await N.pctApresSet(env, m, x, false, 1e12 + 3600e3);
  assert.ok(Number.isFinite(sans) && Number.isFinite(avec));
  assert.equal(vieux, sans);                                  // feuille trop vieille : comme sans feuille
  assert.equal(reseau, 0);
});

test('519 : set gagné par le second nommé → score dans l\'ordre des noms (4-6) ; % avec la feuille fraîche de la page', async () => {
  const m = { uid: 'a_b', home: 'Juan La Serna', away: 'Genaro Olivieri', p_home: 0.58, circuit: 'CH',
    simulation: { a: 0.64, b: 0.63, sets_gagnants: 2 } };
  const p = { h: [4], a: [5], srv: 'h' }, c = { h: [4, 0], a: [6, 0], srv: 'a' };
  const E = N.evenements(m, p, c, 3);
  assert.equal(E.length, 1);
  assert.deepEqual([E[0].type, E[0].qui, E[0].score, E[0].sets], ['set', 'a', '4-6', '0-1']);
  assert.match(N.message(E[0], m, 'fr').texte, /^Juan La Serna – Genaro Olivieri · 4-6 · Sets : 0-1$/);
  // la feuille fraîche (même source que la page) l'emporte sur l'absence de feuille au coffre
  const env = { COFFRE: { get: async () => null } };
  const x = { id: 5, score_home: { sets: [4, 0], point: '0' }, score_away: { sets: [6, 0], point: '0' }, serveur: 'home' };
  const feuille = { firstServeAccuracy: [20, 40, 30, 40], servicePointsScored: [18, null, 30, null] };
  let demandes = 0;
  const sans = await N.pctApresSet(env, m, x, false, 1e12);
  const avec = await N.pctApresSet(env, m, x, false, 1e12, async (id) => { demandes++; assert.equal(id, 5); return feuille; });
  const attendu = MO.pctDirect(m, { x, inverse: false }, {}, feuille);
  assert.equal(demandes, 1);
  assert.equal(avec, attendu);
  assert.ok(Number.isFinite(sans) && Number.isFinite(avec));
  const panne = await N.pctApresSet(env, m, x, false, 1e12, async () => { throw new Error('x'); });
  assert.equal(panne, sans);                                  // feuille indisponible : comme avant
});
