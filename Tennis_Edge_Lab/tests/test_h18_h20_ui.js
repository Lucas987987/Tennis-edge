const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const lab = path.join(__dirname, '..');
const script = fs.readFileSync(path.join(lab, 'research_h18_h20.js'), 'utf8');

const publicH18 = {
  hypotheses: {
    H18: {
      regle: '<img src=x onerror=alert(1)>', gel: '2026-10-16',
      suivi_officiel: { n: 0, gagnes: 0, roi: null, clv_pin: null, clv_n: 0 },
      worker: { out_of_sample: { n: 17, roi: 32.3, clv_pin_moyen: 1.9, clv_n: 18, verdict: 'non concluant' } },
      reconstruction: { n: 39, gagnes: 31, roi: 11.82, clv_pin: 1.7, clv_n: 36 },
    },
  },
};
const privateH19 = {
  h19: {
    regle: { nom: 'Valeur test', gele_le: '2026-10-16' },
    prospectif: {
      n: 12, regles: 8, verdict: 'cible non atteinte',
      clv: { mean: 1.4, ci: [-0.2, 3], n: 12 }, roi: { mean: -2.1, ci: [-9, 5] },
      derniers: [{ date: '2026-10-27', joueur: '<script>alert(1)</script>', book: 'Book', horizon: '6h', clv: 0.014, gagne: 1 }],
    },
    retrospectif: { n: 100, clv: { mean: 4, ci: [2, 6], n: 100 }, roi: { mean: 5, ci: [1, 9] }, avertissement: 'découverte' },
  },
};
const privateH20 = {
  regle: { gele_le: '2026-10-17' },
  prospectif: { n: 9, regles: 5, gagnes: 3, clv_n: 9, clv_moy_pct: 2.2, clv_ic95: [-1, 5], roi_pct: -3.4, verdict: 'en cours', derniers: [] },
  decouverte_avant_gel: { n: 50, clv_n: 50, clv_moy_pct: 3, roi_pct: 4, note: 'aucune valeur de preuve' },
};

function contextWith(responses) {
  const elements = new Map();
  const element = id => {
    if (!elements.has(id)) elements.set(id, { innerHTML: '', textContent: '' });
    return elements.get(id);
  };
  const context = {
    document: { getElementById: element },
    fetch: async url => {
      const key = url.split('?')[0];
      const value = responses[key];
      if (value instanceof Error) return { ok: false, status: 401 };
      return { ok: true, json: async () => value };
    },
    Date, Intl, Promise, Error, module: { exports: {} },
  };
  vm.runInNewContext(script, context);
  return { context, element };
}

test('H18, H19 et H20 affichent leurs populations et le prospectif sans injection HTML', async () => {
  const { context, element } = contextWith({
    './live/reconciliation_hypotheses.json': publicH18,
    './live/valeur.json': privateH19,
    './live/h20.json': privateH20,
  });
  await context.module.exports.start();
  const html = element('h1820Body').innerHTML;
  assert.match(html, /Suivi officiel direct/);
  assert.match(html, /Worker — hors échantillon/);
  assert.match(html, /Reconstruction — contrôle historique/);
  assert.match(html, /32,3|32.3/);
  assert.match(html, /11,82|11.82/);
  assert.match(html, /cible non atteinte/);
  assert.match(html, /H20 — Outsider WTA/);
  assert.match(html, /Période de découverte \(aucune valeur de preuve\)/);
  assert.match(html, /&lt;img src=x onerror=alert\(1\)&gt;/);
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>alert|<img src=x/);
});

test('Un coffre verrouillé ne masque pas les résultats publics H18', async () => {
  const { context, element } = contextWith({
    './live/reconciliation_hypotheses.json': publicH18,
    './live/valeur.json': new Error('401'),
    './live/h20.json': new Error('401'),
  });
  await context.module.exports.start();
  const html = element('h1820Body').innerHTML;
  assert.match(html, /Reconstruction — contrôle historique/);
  assert.equal((html.match(/Coffre privé verrouillé/g) || []).length, 2);
  assert.match(html, /H19 — résultats indisponibles/);
  assert.match(html, /H20 — résultats indisponibles/);
  assert.doesNotMatch(html, /cible non atteinte/);
});

test('Le nouvel onglet et son script sont reliés au déploiement Pages', () => {
  const html = fs.readFileSync(path.join(lab, 'research.html'), 'utf8');
  const workflow = fs.readFileSync(path.join(lab, '..', '.github', 'workflows', 'pages.yml'), 'utf8');
  assert.match(html, /data-tab="h18h20"/);
  assert.match(html, /id="h1820Body"/);
  assert.match(html, /id="h1820Refresh"/);
  assert.match(html, /research_h18_h20\.js/);
  assert.match(workflow, /Tennis_Edge_Lab\/research_h18_h20\.js/);
  assert.match(workflow, /research_registre\.js research_h18_h20\.js freshness\.js/);
});
