/* confidence.js — Score de confiance calibré (Venn-Abers) côté outil.
 *
 * 1) Au démarrage :  await loadConfidenceCalib();   // charge confidence_calib.json
 * 2) Par match     :  const c = applyConfidence(match.probA_modele);
 *                     // c = { p, lo, hi, width, tier }  ou null si pas chargé
 *
 * Rien à recalculer : on lit la grille produite par confidence_v2.py.
 */
(function (global) {
  let _calib = null;

  async function loadConfidenceCalib(url = 'confidence_calib.json') {
    try {
      const r = await fetch(url, { cache: 'no-store' });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      _calib = await r.json();
      return _calib;
    } catch (e) {
      console.warn('confidence: calibration non chargée', e);
      _calib = null;
      return null;
    }
  }

  function applyConfidence(rawProb) {
    if (!_calib || rawProb == null || isNaN(rawProb)) return null;
    const g = _calib.grid;
    const s = Math.max(0, Math.min(1, +rawProb));
    const idx = Math.max(0, Math.min(g.length - 1, Math.round(s * (g.length - 1))));
    const e = g[idx];
    const width = +(e.p1 - e.p0).toFixed(4);
    const t = _calib.tiers || { haute: 0.06, moyenne: 0.12 };
    const tier = width <= t.haute ? 'haute' : (width <= t.moyenne ? 'moyenne' : 'faible');
    return { p: e.p, lo: e.p0, hi: e.p1, width, tier };
  }

  // Rend un petit badge HTML prêt à insérer (optionnel).
  function confidenceBadge(rawProb) {
    const c = applyConfidence(rawProb);
    if (!c) return '';
    const color = c.tier === 'haute' ? '#1a7f37' : (c.tier === 'moyenne' ? '#9a6700' : '#b35900');
    const pct = x => Math.round(x * 100);
    return '<span class="conf-badge" title="proba calibrée + intervalle Venn-Abers" '
      + 'style="border:1px solid ' + color + ';color:' + color
      + ';border-radius:6px;padding:2px 6px;font-size:12px;white-space:nowrap">'
      + pct(c.p) + '% [' + pct(c.lo) + '–' + pct(c.hi) + '] · conf. ' + c.tier
      + '</span>';
  }

  global.loadConfidenceCalib = loadConfidenceCalib;
  global.applyConfidence = applyConfidence;
  global.confidenceBadge = confidenceBadge;
})(window);
