/* Tennis Edge Lab V7.0 — Explorateur v2 : filtres cumulatifs, plages numériques, 4 jeux (dont Détections du suivi officiel). Lecture seule. */
(() => {
  'use strict';
  const hasDoc = typeof document !== 'undefined';
  const $ = id => (hasDoc ? document.getElementById(id) : null);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const nf = (v, d = 2) => v === null || v === undefined || !Number.isFinite(v) ? '—'
    : new Intl.NumberFormat('fr-FR', { maximumFractionDigits: d }).format(v);
  const pct = v => {
    if (v === null || v === undefined || !Number.isFinite(v)) return '—';
    const r = Math.round(v * 10) / 10 || 0; // évite « -0 % »
    return `${r > 0 ? '+' : ''}${nf(r, 1)} %`;
  };
  const pval = v => v === null || v === undefined || !Number.isFinite(v) ? '—' : v < 0.001 ? '< 0,001' : nf(v, 3);
  const ciTxt = ci => ci ? `${pct(ci[0])} à ${pct(ci[1])}` : '—';
  const excludesZero = ci => !!ci && (ci[0] > 0 || ci[1] < 0);

  // ---------- Statistiques (pures, testées sous Node) ----------
  /** Moyenne, IC95 et p unilatérale (H0 : moyenne ≤ 0), erreur-type robuste par grappes (jour). */
  function clusterSummary(values, clusters) {
    let n = 0, sum = 0;
    for (let i = 0; i < values.length; i++) if (Number.isFinite(values[i])) { n++; sum += values[i]; }
    if (!n) return { n: 0, mean: null, ci: null, p: null };
    const mean = sum / n;
    if (n < 2) return { n, mean, ci: null, p: null };
    const groups = new Map();
    let sq = 0;
    for (let i = 0; i < values.length; i++) {
      const v = values[i];
      if (!Number.isFinite(v)) continue;
      const k = clusters ? clusters[i] : i;
      groups.set(k, (groups.get(k) || 0) + v - mean);
      sq += (v - mean) ** 2;
    }
    const g = groups.size;
    let variance;
    if (g >= 4) { let s = 0; for (const x of groups.values()) s += x * x; variance = (g / (g - 1)) * s / (n * n); }
    else variance = sq / (n - 1) / n;
    const se = Math.sqrt(Math.max(variance, 0));
    if (!se) return { n, mean, ci: [mean, mean], p: mean > 0 ? 0 : 1 };
    const z = mean / se;
    return { n, mean, ci: [mean - 1.96 * se, mean + 1.96 * se], p: 0.5 * erfc(z / Math.SQRT2) };
  }
  function erfc(x) { // Numerical Recipes, précision ~1e-7
    const z = Math.abs(x), t = 1 / (1 + 0.5 * z);
    const r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))));
    return x >= 0 ? r : 2 - r;
  }
  /** Somme de cellules du cube (n, gagnés, Σpnl, Σpnl²) -> ROI et IC95 (indépendance). */
  function cubeStats(cells) {
    let n = 0, w = 0, s = 0, s2 = 0;
    for (const c of cells) { n += c.n; w += c.w; s += c.s; s2 += c.s2; }
    if (!n) return { n: 0, wins: 0, roi: null, ci: null };
    const mean = s / n;
    const variance = n > 1 ? (s2 - s * s / n) / (n - 1) : 0;
    const se = Math.sqrt(Math.max(variance, 0) / n);
    return { n, wins: w, roi: 100 * mean, ci: n > 1 ? [100 * (mean - 1.96 * se), 100 * (mean + 1.96 * se)] : null };
  }

  // ---------- Modèle de données commun ----------
  // D = { kind, n, cat: {champ: {codes, dict, label, apres}}, num: {champ: {vals, label}},
  //       date[], month[], won Int8Array, clv(entry) -> Float64Array, pnl(entry) -> Float64Array }
  function emptyModel(kind, n) { return { kind, n, cat: {}, num: {}, order: [] }; }
  function addCat(D, name, label, values, apres = false) {
    const dict = [], map = new Map(), codes = new Uint16Array(D.n);
    for (let i = 0; i < D.n; i++) {
      const v = values[i] === null || values[i] === undefined ? 'inconnu' : String(values[i]);
      let c = map.get(v);
      if (c === undefined) { c = dict.length; map.set(v, c); dict.push(v); }
      codes[i] = c;
    }
    D.cat[name] = { codes, dict, label, apres }; D.order.push(name);
  }
  function addCatCoded(D, name, label, codes, dict) {
    D.cat[name] = { codes: Uint16Array.from(codes), dict: dict.map(String), label, apres: false }; D.order.push(name);
  }
  function numArray(values) {
    const a = new Float64Array(values.length);
    for (let i = 0; i < values.length; i++) a[i] = values[i] === null || values[i] === undefined ? NaN : +values[i];
    return a;
  }
  function addNum(D, name, label, values) { D.num[name] = { vals: numArray(values), label }; D.order.push(name); }

  /** Jeu « alertes » (lignes + rôles) : filtre, filtre_num, filtre_apres_alerte. */
  function prepareAlerts(doc, kind = 'alertes') {
    const D = emptyModel(kind, doc.rows.length);
    const col = name => doc.columns.indexOf(name);
    const column = name => { const j = col(name); return doc.rows.map(r => r[j]); };
    for (const f of doc.fields) {
      if (f.role === 'filtre' || f.role === 'filtre_apres_alerte') addCat(D, f.name, f.label + (f.role === 'filtre_apres_alerte' ? ' (connu après l’alerte H)' : ''), column(f.name), f.role !== 'filtre');
      else if (f.role === 'filtre_num') addNum(D, f.name, f.label, column(f.name));
    }
    const clv = numArray(column('clv_pin')), pnl = numArray(column('pnl'));
    D.clv = () => clv; D.pnl = () => pnl;
    D.won = Int8Array.from(column('gagne').map(v => (v === null ? -1 : v)));
    D.date = column('date'); D.month = column('mois'); D.time = column('_at');
    return D;
  }
  /** Jeu « matchs » (colonnes codées) : filtres catégoriels et numériques, trois prix d'entrée. */
  function prepareMatchs(doc) {
    const D = emptyModel('matchs', doc.n);
    for (const c of doc.columns) {
      if (c.role !== 'filtre') continue;
      if (c.type === 'cat') addCatCoded(D, c.name, c.label, doc.data[c.name], doc.dicts[c.name]);
      else addNum(D, c.name, c.label, doc.data[c.name]);
    }
    const cache = {};
    const get = name => (cache[name] = cache[name] || numArray(doc.data[name]));
    D.clv = entry => get(`clv_${entry}`); D.pnl = entry => get(`pnl_${entry}`);
    D.won = Int8Array.from(doc.data.gagne.map(v => (v === null ? -1 : v)));
    const dd = doc.dicts.date; D.date = doc.data.date.map(c => dd[c]); D.month = doc.data.mois.map(c => doc.dicts.mois[c]);
    D.time = doc.data.decision_ts.map(c => doc.dicts.decision_ts[c]);
    D.entrees = doc.entrees;
    // 21/10/2026 : clé (jour, joueur) et horizon, pour « un pari par joueur et par match ».
    if (doc.data.joueur && doc.data.horizon) {
      const dj = doc.dicts.joueur || [], dh = doc.dicts.horizon || [];
      D.cle = doc.data.joueur.map((c, i) => `${D.date[i]}|${dj[c] ?? c}`);
      D.hz = doc.data.horizon.map(c => dh[c] ?? c);
    }
    return D;
  }
  /** Lignes simples (jeu d'essai de parité) : fields = [{name, type:'cat'|'num'}]. */
  function prepareRows(rows, fields, kind = 'alertes') {
    const D = emptyModel(kind, rows.length);
    for (const f of fields) {
      const values = rows.map(r => r[f.name]);
      if (f.type === 'num') addNum(D, f.name, f.name, values); else addCat(D, f.name, f.name, values);
    }
    D.clv = () => numArray(rows.map(r => r.clv)); D.pnl = () => numArray(rows.map(r => r.pnl));
    D.won = Int8Array.from(rows.map(r => (r.gagne === undefined || r.gagne === null ? -1 : r.gagne)));
    D.date = rows.map(r => r.date); D.month = rows.map(r => String(r.date || '').slice(0, 7));
    return D;
  }
  function prepareHisto(doc) {
    const D = emptyModel('histo', doc.cells.length);
    doc.keys.forEach((k, j) => addCat(D, k, doc.labels[k], doc.cells.map(c => c[j])));
    const off = doc.keys.length;
    D.cells = doc.cells.map(c => ({ n: c[off], w: c[off + 1], s: c[off + 2], s2: c[off + 3] }));
    D.year = doc.cells.map(c => c[0]);
    return D;
  }

  // ---------- Filtres : OU dans un critère, ET entre critères, bornes incluses ----------
  /** filters = { cats: {champ: [valeurs]}, ranges: {champ: [min|null, max|null]} } */
  function filterIndices(D, filters, except) {
    const cats = [], ranges = [];
    for (const [field, values] of Object.entries(filters.cats || {})) {
      if (field === except || !D.cat[field]) continue;
      const allowed = new Uint8Array(D.cat[field].dict.length + 1);
      for (const v of values) { const c = D.cat[field].dict.indexOf(String(v)); if (c >= 0) allowed[c] = 1; }
      cats.push([D.cat[field].codes, allowed]);
    }
    for (const [field, [lo, hi]] of Object.entries(filters.ranges || {})) {
      if (field === except || !D.num[field]) continue;
      ranges.push([D.num[field].vals, lo === null || lo === undefined ? -Infinity : lo, hi === null || hi === undefined ? Infinity : hi]);
    }
    const out = [];
    outer: for (let i = 0; i < D.n; i++) {
      for (let c = 0; c < cats.length; c++) if (!cats[c][1][cats[c][0][i]]) continue outer;
      for (let r = 0; r < ranges.length; r++) {
        const v = ranges[r][0][i];
        if (!(v >= ranges[r][1] && v <= ranges[r][2])) continue outer; // NaN exclu
      }
      out.push(i);
    }
    return out;
  }

  /** Un pari par (jour, joueur) : le premier horizon (24 h, 6 h, 1 h, 10 min) parmi les lignes retenues. */
  const ORDRE_HZ = { '24h': 0, '6h': 1, '1h': 2, '10m': 3 };
  function premierHorizon(D, idx) {
    if (!D.cle || !D.hz) return idx;
    const best = new Map();
    for (const i of idx) {
      const o = ORDRE_HZ[D.hz[i]] ?? 9, b = best.get(D.cle[i]);
      if (b === undefined || o < b[0]) best.set(D.cle[i], [o, i]);
    }
    return [...best.values()].map(b => b[1]).sort((a, b) => a - b);
  }

  function stats(D, idx, entry) {
    if (D.kind === 'histo') {
      const s = cubeStats(idx.map(i => D.cells[i]));
      const years = new Map();
      for (const i of idx) { const y = D.year[i]; const e = years.get(y) || [0, 0]; e[0] += D.cells[i].s; e[1] += D.cells[i].n; years.set(y, e); }
      let pos = 0, tot = 0; for (const [, e] of years) if (e[1] >= 20) { tot++; if (e[0] > 0) pos++; }
      return { n: s.n, settled: s.n, wins: s.wins, roi: s.roi, roiCi: s.ci, clv: null, clvCi: null, p: null, monthsPos: tot ? pos / tot : null };
    }
    const P = D.pnl(entry), C = D.clv(entry);
    const pnl = [], pDates = [], clv = [], cDates = [];
    let wins = 0, settled = 0;
    const months = new Map();
    for (const i of idx) {
      if (Number.isFinite(P[i])) { pnl.push(100 * P[i]); pDates.push(D.date[i]); settled++; if (D.won[i] === 1) wins++; }
      if (Number.isFinite(C[i])) {
        clv.push(C[i]); cDates.push(D.date[i]);
        const e = months.get(D.month[i]) || [0, 0]; e[0] += C[i]; e[1]++; months.set(D.month[i], e);
      }
    }
    const roi = clusterSummary(pnl, pDates), c = clusterSummary(clv, cDates);
    let mPos = 0, mTot = 0;
    for (const [, e] of months) if (e[1] >= 5) { mTot++; if (e[0] > 0) mPos++; }
    return { n: idx.length, settled, wins, roi: roi.mean, roiCi: roi.ci, clv: c.mean, clvCi: c.ci, p: c.p, clvN: c.n, monthsPos: mTot ? mPos / mTot : null };
  }
  // Compatibilité V6.7 (tests existants).
  const alertStats = (D, idx) => stats(D, idx, 'alerte');

  // ---------- Données ----------
  async function fetchJsonGz(base) {
    if (typeof DecompressionStream !== 'undefined') {
      try {
        const r = await fetch(`${base}.json.gz?t=${Date.now()}`, { cache: 'no-store' });
        if (r.ok) return JSON.parse(await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text());
      } catch { /* repli JSON simple */ }
    }
    const r = await fetch(`${base}.json?t=${Date.now()}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`${base} : HTTP ${r.status}`);
    return r.json();
  }

  // ---------- État ----------
  // V7.0 : les verdicts se lisent sur « Détections (suivi officiel) » (jeu par défaut).
  const state = { kind: 'detections', data: {}, reco: null, filters: { cats: {}, ranges: {} }, entry: 'jouable', splitBy: null,
    unParJoueur: true,
    sort: 'n', compare: false,
    // V7.2 : compteur de découpes PARTAGÉ avec l'onglet « Matchs en direct » (α/k commun à la session).
    seen: (hasDoc && typeof window !== 'undefined' ? (window.TELab = window.TELab || { seen: new Set() }).seen : new Set()), frozen: null, panelOpen: true, openCrit: new Set() };
  const PRESETS = {
    detections: [
      { label: 'Détections non envoyées, par hypothèse', cats: { envoyee: ['non'] }, ranges: {}, split: 'type' },
      { label: 'Envoyées ou non : comparer, par hypothèse', cats: {}, ranges: {}, split: 'envoyee' },
    ],
    alertes: [
      { label: 'Alerte publique · ATP · cote 1,80–2,40 · ampleur ≥ 3 pts', cats: { type: ['PUBLIC'], circuit: ['ATP'] }, ranges: { cote: [1.8, 2.4], ampleur_pts: [3, null] }, split: 'tranche_delai' },
      { label: 'Exemple : alertes H suivies d’une alerte publique', cats: { type: ['H13', 'H16', 'H16B', 'H17', 'H18'], suivie_public: ['oui'] }, ranges: {}, split: 'circuit' },
      { label: 'Exemple : alertes publiques précédées d’une alerte H', cats: { type: ['PUBLIC'], precede_par_H: ['oui'] }, ranges: {}, split: 'circuit' },
    ],
    matchs: [
      { label: 'Alerte publique avant · ATP · cote Pinnacle 1,80–2,40 · cote raccourcie d’au moins 3 %', cats: { alerte_avant: '*PUBLIC*', circuit: ['ATP'] }, ranges: { cote_pin: [1.8, 2.4], move_pin_pct: [null, -3] }, split: 'horizon' },
      { label: 'Meilleur jouable ≥ 2 % au-dessus du prix juste Pinnacle', cats: {}, ranges: { ecart_jouable_pct: [2, null] }, split: 'circuit', entry: 'jouable' },
      { label: 'Favoris Pinnacle · 1 h avant · cote raccourcie d’au moins 3 %', cats: { horizon: ['1h'], cote_pinnacle: ['favori'] }, ranges: { move_pin_pct: [null, -3] }, split: 'circuit' },
    ],
    histo: [],
  };
  const D = () => state.data[state.kind];
  const k = () => Math.max(1, state.seen.size);
  const entryKey = () => (state.kind === 'matchs' ? state.entry : 'alerte');
  const unPar = () => state.kind === 'matchs' && state.unParJoueur;
  const selection = data => (unPar() ? premierHorizon(data, filterIndices(data, state.filters)) : filterIndices(data, state.filters));
  const activeCount = () => Object.keys(state.filters.cats).length + Object.keys(state.filters.ranges).length;

  /** n par hypothèse : suivi officiel (EN DIRECT), envoyées, reconstruction (contrôle), Worker — reconciliation_hypotheses.json. */
  function populationCounts(reco) {
    const out = [];
    for (const [code, h] of Object.entries((reco && reco.hypotheses) || {})) {
      const o = h.suivi_officiel || {}, e = h.entonnoir || {};
      out.push({ code, detectees: o.n_detectees ?? null, denouees: o.n ?? null, envoyees: e.direct_envoyees ?? null,
        reconstruction: h.reconstruction?.n ?? null, worker: h.worker?.n ?? null, communes: e.communes ?? null });
    }
    return out;
  }
  function populationLine() {
    if (!['detections', 'alertes'].includes(state.kind)) return '';
    const rows = populationCounts(state.reco);
    if (!rows.length) return '';
    return `<details class="xp-pop"><summary><b>H* : suivi officiel (direct) / envoyées / contrôle</b> (n)</summary><div class="table-wrap"><table class="xp-mini"><thead><tr><th>Hyp.</th><th class="num">Détectées</th><th class="num">Dénouées</th><th class="num">Envoyées</th><th class="num">Reconstruction</th><th class="num">Worker</th></tr></thead><tbody>${rows.map(r => `<tr><td>${esc(r.code)}</td><td class="num">${nf(r.detectees, 0)}</td><td class="num">${nf(r.denouees, 0)}</td><td class="num">${nf(r.envoyees, 0)}</td><td class="num">${nf(r.reconstruction, 0)}</td><td class="num">${nf(r.worker, 0)}</td></tr>`).join('')}</tbody></table></div><p class="mini">Verdicts : alertes en direct uniquement. Reconstruction = contrôle. Détail : onglet « Réconciliation ».</p></details>`;
  }
  function otherPopulation(value) {
    const r = populationCounts(state.reco).find(x => x.code === value);
    if (!r) return '';
    if (state.kind === 'detections') return `envoyées ${nf(r.envoyees, 0)} · reconstruction ${nf(r.reconstruction, 0)}`;
    return `suivi officiel ${nf(r.detectees, 0)} détectées`;
  }

  function render() {
    const host = $('explorerBody');
    if (!host) return;
    const data = D();
    if (!data) { host.innerHTML = '<p class="mini">Chargement des données…</p>'; return; }
    const idx = selection(data);
    const s = stats(data, idx, entryKey());
    const candidates = data.order.filter(n => !(n in state.filters.cats) && !(n in state.filters.ranges));
    if (!state.splitBy || !candidates.includes(state.splitBy)) state.splitBy = candidates.find(n => data.cat[n]) || candidates[0] || null;
    if (state.splitBy) state.seen.add(JSON.stringify([state.kind, state.filters, state.splitBy, state.entry, unPar()]));
    const alpha = 0.05 / k();
    host.innerHTML = `${toolbar()}${filterPanel(data)}${chips(data)}${summaryCard(data, idx, s)}${state.compare ? compareCard(data, idx, s) : ''}${splitTable(data, idx, alpha)}${freezeBlock(data)}`;
    bind();
  }

  function toolbar() {
    const kinds = [['detections', 'Détections (suivi officiel)'], ['alertes', 'Alertes envoyées'], ['matchs', 'Tous les matchs'], ['histo', 'Historique 2010–2026']];
    const note = {
      detections: '<b>Suivi officiel = alertes EN DIRECT</b> (h*_signal_log.jsonl, données figées à la détection, résultat ajouté ensuite), y compris doublons non envoyés : mêmes n que verdicts_direct.json. <b>Référence pour les verdicts.</b>',
      alertes: 'Messages réellement envoyés (H*, sans doublon), alertes publiques et mouvements, surtout de <b>juin à octobre 2026</b> : échantillons courts. Mesure principale : CLV Pinnacle.',
      matchs: 'Chaque match suivi depuis juin, côté par côté, à 24 h, 6 h, 1 h et 10 min. Mesure principale : CLV Pinnacle du prix d’entrée choisi.',
      histo: 'tennis-data, clôture Pinnacle (marge incluse) : ROI au prix de clôture, pas de CLV.',
    }[state.kind];
    const entries = state.kind === 'matchs' ? `<label class="xp-entry">Prix d’entrée <select id="xpEntry">${[['pinnacle', 'Pinnacle'], ['jouable', 'Meilleur jouable'], ['fr', 'Meilleur FR']].map(([v, l]) => `<option value="${v}" ${state.entry === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label>
      <label class="xp-entry"><input type="checkbox" id="xpUnPar" ${state.unParJoueur ? 'checked' : ''}> Un pari par joueur et par match (premier horizon qui remplit les filtres)</label>` : '';
    const presets = PRESETS[state.kind] || [];
    return `<div class="xp-switch" role="group" aria-label="Jeu de données">${kinds.map(([v, l]) => `<button type="button" data-kind="${v}" class="${state.kind === v ? 'selected' : ''}">${l}</button>`).join('')}</div>
      <p class="mini">${note} · <b>Découpes consultées : ${k()}</b> · seuil corrigé α/k = ${pval(0.05 / k())}</p>${populationLine()}${entries}
      ${presets.length ? `<div class="xp-presets">${presets.map((p, i) => `<button type="button" data-preset="${i}">${esc(p.label)}</button>`).join('')}</div>` : ''}`;
  }

  function numBounds(field) {
    const vals = D().num[field].vals; let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < vals.length; i++) { const v = vals[i]; if (v < lo) lo = v; if (v > hi) hi = v; }
    return [lo, hi];
  }
  function filterPanel(data) {
    const cats = data.order.filter(n => data.cat[n]).map(n => {
      const c = data.cat[n], active = new Set(state.filters.cats[n] || []);
      const values = c.dict.map((v, j) => [v, j]).sort((a, b) => a[0].localeCompare(b[0], 'fr'));
      return `<details class="xp-crit" data-crit="${esc(n)}" ${state.openCrit.has(n) ? 'open' : ''}><summary>${esc(c.label)}${active.size ? ` <b>(${active.size})</b>` : ''}</summary><div class="xp-values">${values.map(([v]) => `<label><input type="checkbox" data-cat="${esc(n)}" value="${esc(v)}" ${active.has(v) ? 'checked' : ''}> ${esc(v)}</label>`).join('')}</div></details>`;
    }).join('');
    const nums = data.order.filter(n => data.num[n]).map(n => {
      const [lo, hi] = numBounds(n), r = state.filters.ranges[n] || [null, null];
      return `<div class="xp-range"><span>${esc(data.num[n].label)}</span><input type="number" step="any" inputmode="decimal" data-num="${esc(n)}" data-end="0" placeholder="min ${nf(lo)}" value="${r[0] ?? ''}"><input type="number" step="any" inputmode="decimal" data-num="${esc(n)}" data-end="1" placeholder="max ${nf(hi)}" value="${r[1] ?? ''}"></div>`;
    }).join('');
    return `<details class="xp-panel" ${state.panelOpen ? 'open' : ''}><summary><b>Filtres</b> — cocher plusieurs valeurs = OU ; plusieurs critères = ET</summary>${cats}${nums ? `<div class="xp-ranges">${nums}</div>` : ''}</details>`;
  }

  function chips(data) {
    const items = [];
    for (const [f, values] of Object.entries(state.filters.cats)) items.push(`<button type="button" class="xp-chip" data-remove-cat="${esc(f)}">${esc(data.cat[f]?.label || f)} : ${esc(values.join(' ou '))} ✕</button>`);
    for (const [f, [lo, hi]] of Object.entries(state.filters.ranges)) items.push(`<button type="button" class="xp-chip" data-remove-num="${esc(f)}">${esc(data.num[f]?.label || f)} : ${lo === null ? '…' : nf(lo)} à ${hi === null ? '…' : nf(hi)} ✕</button>`);
    if (!items.length) return '<p class="mini">Aucun critère : toute la base. Cochez des valeurs, saisissez une plage ou touchez une ligne du tableau.</p>';
    return `<div class="xp-chips" aria-label="Critères actifs">${items.join('')}<button type="button" class="xp-chip clear" data-clear="1">Tout effacer</button></div>`;
  }

  function badges(s) {
    const out = [];
    if (state.kind === 'matchs' && !state.unParJoueur && (state.filters.cats.horizon || []).length !== 1) out.push('<span class="xp-warn">un match compte jusqu’à 4 fois (horizons) : choisir un seul horizon</span>');
    if (s.n < 30) out.push('<span class="xp-warn">n &lt; 30</span>');
    if (excludesZero(s.roiCi) && s.roiCi[0] > 0 && s.clvCi && !excludesZero(s.clvCi)) out.push('<span class="xp-luck">ROI seul, CLV Pinnacle compatible avec 0 : probablement de la chance</span>');
    return out.join(' ');
  }

  function periodTable(data, idx) {
    const groups = new Map();
    for (const i of idx) { const key = data.kind === 'histo' ? data.year[i] : data.month[i]; if (!groups.has(key)) groups.set(key, []); groups.get(key).push(i); }
    const isH = data.kind === 'histo';
    return `<div class="table-wrap"><table class="xp-mini"><thead><tr><th>${isH ? 'Année' : 'Mois'}</th><th class="num">n</th><th class="num">ROI</th>${isH ? '' : '<th class="num">CLV Pinnacle</th>'}</tr></thead><tbody>${[...groups.keys()].sort().map(key => {
      const s = stats(data, groups.get(key), entryKey());
      return `<tr><td>${esc(key)}</td><td class="num">${nf(s.n, 0)}</td><td class="num">${pct(s.roi)}</td>${isH ? '' : `<td class="num">${pct(s.clv)}</td>`}</tr>`;
    }).join('')}</tbody></table></div>`;
  }

  function summaryCard(data, idx, s) {
    let period = '';
    if (idx.length) { const ds = idx.map(i => (data.kind === 'histo' ? data.year[i] : data.date[i])).sort(); period = `${ds[0]} → ${ds[ds.length - 1]}`; }
    const isH = data.kind === 'histo';
    const unit = { detections: 'Détections', alertes: 'Alertes', matchs: 'Décisions', histo: 'Paris' }[data.kind];
    return `<article class="candidate xp-summary"><h3>Sélection actuelle ${badges(s)}</h3>
      <div class="stats"><div><small>${unit}</small><strong>${nf(s.n, 0)}</strong><small>${isH ? '' : `${nf(s.settled, 0)} réglées`}</small></div>
      ${isH ? '' : `<div><small>CLV Pinnacle · IC95</small><strong class="${excludesZero(s.clvCi) ? (s.clv > 0 ? 'good' : 'bad') : ''}">${pct(s.clv)}</strong><small>${ciTxt(s.clvCi)}</small></div>`}
      <div><small>ROI · IC95${isH ? '' : ' (secondaire)'}</small><strong>${pct(s.roi)}</strong><small>${ciTxt(s.roiCi)}</small></div></div>
      <p class="detail">Période : ${esc(period || '—')} · gagnés ${s.settled ? nf(100 * s.wins / s.settled, 1) + ' %' : '—'}${isH ? '' : ` · mois CLV+ ${s.monthsPos === null ? '—' : nf(100 * s.monthsPos, 0) + ' %'}`}</p>
      <details><summary>Détail par ${isH ? 'année' : 'mois'}</summary>${periodTable(data, idx)}</details>
      <label class="xp-compare"><input type="checkbox" id="xpCompare" ${state.compare ? 'checked' : ''}> Comparer avec le reste</label></article>`;
  }

  function compareCard(data, idx, s) {
    const inSel = new Uint8Array(data.n); for (const i of idx) inSel[i] = 1;
    let rest = []; for (let i = 0; i < data.n; i++) if (!inSel[i]) rest.push(i);
    if (unPar()) rest = premierHorizon(data, rest);
    const r = stats(data, rest, entryKey());
    const overlap = (a, b) => a && b ? !(a[0] > b[1] || b[0] > a[1]) : null;
    const line = (name, a, b, ca, cb) => `<tr><td>${name}</td><td class="num">${pct(a)}</td><td class="num">${pct(b)}</td><td class="num">${pct(a !== null && b !== null ? a - b : null)}</td><td>${overlap(ca, cb) === null ? '—' : overlap(ca, cb) ? 'IC qui se chevauchent : différence non établie' : '<b>IC disjoints</b>'}</td></tr>`;
    return `<article class="candidate xp-cmp"><h3>Sélection contre le reste (${nf(r.n, 0)})</h3><div class="table-wrap"><table class="xp-mini"><thead><tr><th>Mesure</th><th class="num">Sélection</th><th class="num">Reste</th><th class="num">Écart</th><th>Lecture</th></tr></thead><tbody>
      ${data.kind === 'histo' ? '' : line('CLV Pinnacle', s.clv, r.clv, s.clvCi, r.clvCi)}${line('ROI', s.roi, r.roi, s.roiCi, r.roiCi)}</tbody></table></div></article>`;
  }

  /** Groupes de découpe : valeurs d'un critère catégoriel, ou 5 tranches (quantiles) d'un critère numérique. */
  function splitGroups(data, idx, field) {
    if (data.cat[field]) {
      const { codes, dict } = data.cat[field];
      const groups = dict.map(() => []);
      for (const i of idx) groups[codes[i]].push(i);
      return dict.map((value, j) => ({ label: value, value, members: groups[j] })).filter(g => g.members.length);
    }
    const vals = data.num[field].vals;
    const finite = idx.filter(i => Number.isFinite(vals[i])).sort((a, b) => vals[a] - vals[b]);
    if (!finite.length) return [];
    const edges = [];
    for (let q = 1; q < 5; q++) edges.push(vals[finite[Math.floor(q * finite.length / 5)]]);
    const cuts = [...new Set(edges)];
    const bounds = [];
    let lo = vals[finite[0]];
    for (const c of cuts) { if (c > lo) { bounds.push([lo, c]); lo = c; } }
    bounds.push([lo, vals[finite[finite.length - 1]]]);
    return bounds.map(([a, b], j) => {
      const last = j === bounds.length - 1;
      const members = finite.filter(i => vals[i] >= a && (last ? vals[i] <= b : vals[i] < b));
      return { label: `${nf(a)} à ${nf(b)}${last ? '' : ' (exclu)'}`, range: [a, last ? b : b - 1e-9], members };
    }).filter(g => g.members.length);
  }

  function splitTable(data, idx, alpha) {
    if (!state.splitBy) return '<p class="mini">Tous les critères sont utilisés.</p>';
    let rows = splitGroups(data, idx, state.splitBy).map(g => ({ ...g, s: stats(data, g.members, entryKey()) }));
    const isH = data.kind === 'histo';
    if (state.sort === 'clv' && !isH) rows.sort((a, b) => ((b.s.clvCi?.[0] ?? -1e9) - (a.s.clvCi?.[0] ?? -1e9)));
    else if (state.sort === 'valeur') rows = rows; // ordre naturel (tranches croissantes / dictionnaire)
    else rows.sort((a, b) => b.s.n - a.s.n);
    const maxN = Math.max(1, ...rows.map(r => r.s.n));
    const label = f => (data.cat[f] || data.num[f]).label;
    const options = data.order.filter(n => !(n in state.filters.cats) && !(n in state.filters.ranges))
      .map(n => `<option value="${esc(n)}" ${n === state.splitBy ? 'selected' : ''}>${esc(label(n))}</option>`).join('');
    return `<div class="xp-controls"><label>Découper par <select id="xpSplit">${options}</select></label>
      <label>Trier <select id="xpSort"><option value="n" ${state.sort === 'n' ? 'selected' : ''}>par effectif</option>${isH ? '' : `<option value="clv" ${state.sort === 'clv' ? 'selected' : ''}>par borne basse CLV Pinnacle</option>`}<option value="valeur" ${state.sort === 'valeur' ? 'selected' : ''}>par valeur</option></select></label></div>
      ${data.cat[state.splitBy]?.apres ? '<p class="xp-luck">Ce critère est connu après l’alerte H : utile pour comprendre, pas pour décider au moment de l’alerte H.</p>' : ''}
      <div class="table-wrap"><table class="xp-split"><thead><tr><th>${esc(label(state.splitBy))}</th><th class="num">n</th><th class="num">Gagnés</th><th class="num">ROI · IC95</th>${isH ? '' : '<th class="num">CLV Pinnacle · IC95</th><th class="num">p (seuil)</th>'}<th class="num">${isH ? 'Années ROI+' : 'Mois CLV+'}</th><th></th></tr></thead><tbody>
      ${rows.map((r, j) => {
        const s = r.s;
        const other = state.splitBy === 'type' && ['detections', 'alertes'].includes(data.kind) ? otherPopulation(r.value) : '';
        return `<tr class="xp-row" data-row="${j}" tabindex="0"><td><b>${esc(r.label)}</b>${other ? `<div class="detail">${esc(other)}</div>` : ''} ${s.n < 30 ? '<span class="xp-warn">n &lt; 30</span>' : ''}${!isH && excludesZero(s.roiCi) && s.roiCi[0] > 0 && !excludesZero(s.clvCi) ? ' <span class="xp-luck">probablement de la chance</span>' : ''}</td>
          <td class="num">${nf(s.n, 0)}</td><td class="num">${s.settled ? nf(100 * s.wins / s.settled, 0) + ' %' : '—'}</td>
          <td class="num">${pct(s.roi)}<div class="detail">${ciTxt(s.roiCi)}</div></td>
          ${isH ? '' : `<td class="num ${excludesZero(s.clvCi) ? 'xp-sig' : ''}">${pct(s.clv)}<div class="detail">${ciTxt(s.clvCi)}</div></td><td class="num">${pval(s.p)}<div class="detail">${s.p !== null && s.p < alpha ? '<b>&lt; α/k</b>' : `α/k ${pval(alpha)}`}</div></td>`}
          <td class="num">${s.monthsPos === null ? '—' : nf(100 * s.monthsPos, 0) + ' %'}</td>
          <td><span class="xp-bar" style="width:${Math.round(60 * s.n / maxN)}px"></span></td></tr>`;
      }).join('')}</tbody></table></div><p class="mini">Touchez une ligne pour l’ajouter aux filtres. Gras = IC95 du CLV Pinnacle qui exclut 0. Chaque découpe consultée augmente k (correction de Bonferroni).</p>`;
  }

  function freezeSpec(data, s) {
    const spec = {
      jeu: data.kind,
      criteres: Object.fromEntries(Object.entries(state.filters.cats).map(([f, v]) => [f, [...v]])),
      date: new Date().toISOString().slice(0, 10),
      stats: { n: s.n, clv_pin: s.clv === null ? null : +s.clv.toFixed(3), clv_ic95: s.clvCi ? s.clvCi.map(x => +x.toFixed(3)) : null,
        roi: s.roi === null ? null : +s.roi.toFixed(2), decoupes_consultees: k() },
    };
    if (Object.keys(state.filters.ranges).length) spec.plages = Object.fromEntries(Object.entries(state.filters.ranges).map(([f, r]) => [f, [r[0], r[1]]]));
    if (data.kind === 'matchs') spec.entree = state.entry;
    if (data.kind === 'matchs' && state.unParJoueur) spec.un_par_joueur = true;
    return spec;
  }
  function freezeBlock(data) {
    if (data.kind === 'histo') return '<p class="mini">Le gel ne concerne que « Alertes envoyées » et « Tous les matchs » (l’historique est déjà passé).</p>';
    if (data.kind === 'detections') return '<p class="mini">Les hypothèses H* sont déjà gelées : rien à geler ici. Pour une nouvelle piste, utilisez « Alertes envoyées » ou « Tous les matchs ».</p>';
    return '<div class="xp-freeze"><button type="button" id="xpFreeze">Préparer le gel</button><div id="xpFreezeOut"></div></div>';
  }
  function showFreeze() {
    const data = D(); const idx = selection(data); const s = stats(data, idx, entryKey());
    const out = $('xpFreezeOut'); if (!out) return;
    const bad = Object.keys(state.filters.cats).filter(f => f === 'mois' || data.cat[f]?.apres);
    if (!activeCount()) { out.innerHTML = '<p class="xp-luck">Ajoutez au moins un critère avant de geler.</p>'; return; }
    if (bad.length) { out.innerHTML = '<p class="xp-luck">Retirez « Mois » et « Suivie d’une alerte publique » : ils ne sont pas connus à l’avance pour des matchs futurs.</p>'; return; }
    out.innerHTML = `<p class="detail">Copier ce bloc dans l’entrée <b>explorateur</b> du workflow <b>« Lab - gel (V6.6 et explorateur) »</b> (GitHub → Actions → Run workflow). Seules les décisions à partir du lendemain du gel compteront.</p>
      <textarea readonly rows="6" class="xp-json" aria-label="Spécification du gel">${esc(JSON.stringify(freezeSpec(data, s)))}</textarea>`;
  }

  function renderFrozen() {
    const host = $('explorerFrozen'); if (!host) return;
    const f = state.frozen;
    if (!f || !Array.isArray(f.candidates) || !f.candidates.length) { host.innerHTML = '<p class="mini">Aucune sélection de l’Explorateur gelée pour l’instant.</p>'; return; }
    const desc = c => [...Object.entries(c.criteres || {}).map(([a, b]) => `${a} : ${b.join(' ou ')}`),
      ...Object.entries(c.plages || {}).map(([a, [lo, hi]]) => `${a} : ${lo ?? '…'} à ${hi ?? '…'}`)].join(' · ');
    host.innerHTML = `<p class="mini">${esc(f.rule)} ${esc(f.multiple_testing)}</p><div class="table-wrap"><table class="xp-mini"><thead><tr><th>Sélection</th><th>Gel</th><th class="num">Futures</th><th class="num">CLV Pinnacle · IC95</th><th class="num">p Holm</th><th class="num">ROI</th><th>État</th></tr></thead><tbody>${f.candidates.map(c => `<tr><td><code>${esc(c.candidate_id)}</code><div class="detail">${esc(c.jeu || 'alertes')}${c.entree ? ` · entrée ${esc(c.entree)}` : ''}${c.un_par_joueur ? ' · un pari par joueur' : ''} · ${esc(desc(c))}</div></td><td>${esc(String(c.created_at).slice(0, 10))}</td><td class="num">${nf(c.n, 0)}</td><td class="num">${pct(c.clv_pin_mean_pct)}<div class="detail">${ciTxt(c.clv_pin_ci95)}</div></td><td class="num">${pval(c.p_holm_clv_pin)}</td><td class="num">${pct(c.roi_pct)}</td><td>${esc(c.state)}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function applyPreset(p) {
    const data = D();
    const cats = {};
    for (const [f, v] of Object.entries(p.cats || {})) {
      if (!data.cat[f]) continue;
      const values = v === '*PUBLIC*' ? data.cat[f].dict.filter(x => x.split('+').includes('PUBLIC')) : v.filter(x => data.cat[f].dict.includes(x));
      if (values.length) cats[f] = values;
    }
    const ranges = {};
    for (const [f, r] of Object.entries(p.ranges || {})) if (data.num[f]) ranges[f] = r;
    state.filters = { cats, ranges };
    if (p.entry) state.entry = p.entry;
    state.splitBy = p.split;
    render();
  }

  function bind() {
    const host = $('explorerBody');
    // Garder ouverts le panneau et les critères dépliés d'un rendu à l'autre (cases multiples sur mobile).
    const panel = host.querySelector('.xp-panel');
    if (panel) panel.addEventListener('toggle', () => { state.panelOpen = panel.open; });
    host.querySelectorAll('.xp-crit').forEach(d => d.addEventListener('toggle', () => {
      if (d.open) state.openCrit.add(d.dataset.crit); else state.openCrit.delete(d.dataset.crit);
    }));
    host.querySelectorAll('[data-kind]').forEach(b => b.addEventListener('click', async () => {
      state.kind = b.dataset.kind; state.filters = { cats: {}, ranges: {} }; state.splitBy = null;
      try { await ensure(state.kind); } catch { return; }
      render();
    }));
    host.querySelectorAll('[data-preset]').forEach(b => b.addEventListener('click', () => applyPreset(PRESETS[state.kind][+b.dataset.preset])));
    host.querySelectorAll('[data-cat]').forEach(cb => cb.addEventListener('change', () => {
      const f = cb.dataset.cat, cur = new Set(state.filters.cats[f] || []);
      if (cb.checked) cur.add(cb.value); else cur.delete(cb.value);
      if (cur.size) state.filters.cats[f] = [...cur]; else delete state.filters.cats[f];
      render();
    }));
    host.querySelectorAll('[data-num]').forEach(inp => inp.addEventListener('change', () => {
      const f = inp.dataset.num, r = state.filters.ranges[f] ? [...state.filters.ranges[f]] : [null, null];
      const v = inp.value.trim() === '' ? null : Number(inp.value.replace(',', '.'));
      r[+inp.dataset.end] = Number.isFinite(v) ? v : null;
      if (r[0] === null && r[1] === null) delete state.filters.ranges[f]; else state.filters.ranges[f] = r;
      render();
    }));
    host.querySelectorAll('[data-remove-cat]').forEach(b => b.addEventListener('click', () => { delete state.filters.cats[b.dataset.removeCat]; render(); }));
    host.querySelectorAll('[data-remove-num]').forEach(b => b.addEventListener('click', () => { delete state.filters.ranges[b.dataset.removeNum]; render(); }));
    host.querySelectorAll('[data-clear]').forEach(b => b.addEventListener('click', () => { state.filters = { cats: {}, ranges: {} }; render(); }));
    const data = D();
    const groups = state.splitBy ? splitGroups(data, selection(data), state.splitBy) : [];
    const sorted = (() => {
      const rows = groups.map(g => ({ ...g, s: stats(data, g.members, entryKey()) }));
      if (state.sort === 'clv' && data.kind !== 'histo') rows.sort((a, b) => ((b.s.clvCi?.[0] ?? -1e9) - (a.s.clvCi?.[0] ?? -1e9)));
      else if (state.sort !== 'valeur') rows.sort((a, b) => b.s.n - a.s.n);
      return rows;
    })();
    host.querySelectorAll('.xp-row').forEach(tr => {
      const go = () => {
        const g = sorted[+tr.dataset.row]; if (!g) return;
        if (g.range) state.filters.ranges[state.splitBy] = g.range; else state.filters.cats[state.splitBy] = [g.value];
        render();
      };
      tr.addEventListener('click', go);
      tr.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
    });
    const split = $('xpSplit'); if (split) split.addEventListener('change', () => { state.splitBy = split.value; render(); });
    const sort = $('xpSort'); if (sort) sort.addEventListener('change', () => { state.sort = sort.value; render(); });
    const entry = $('xpEntry'); if (entry) entry.addEventListener('change', () => { state.entry = entry.value; render(); });
    const up = $('xpUnPar'); if (up) up.addEventListener('change', () => { state.unParJoueur = up.checked; render(); });
    const cmp = $('xpCompare'); if (cmp) cmp.addEventListener('change', () => { state.compare = cmp.checked; render(); });
    const fr = $('xpFreeze'); if (fr) fr.addEventListener('click', showFreeze);
  }

  async function ensure(kind) {
    if (state.data[kind]) return;
    const host = $('explorerBody');
    try {
      if (kind === 'detections') state.data.detections = prepareAlerts(await fetchJsonGz('./live/explorateur_detections'), 'detections');
      else if (kind === 'alertes') state.data.alertes = prepareAlerts(await fetchJsonGz('./live/explorateur_alertes'));
      else if (kind === 'matchs') state.data.matchs = prepareMatchs(await fetchJsonGz('./live/explorateur_matchs'));
      else state.data.histo = prepareHisto(await fetchJsonGz('./live/explorateur_histo'));
    } catch (e) {
      if (host) host.innerHTML = `<p class="notice warn">Données de l’Explorateur indisponibles : ${esc(e.message)}</p>`;
      throw e;
    }
  }

  async function start() {
    if (!$('explorerBody')) return;
    try {
      const r = await fetch(`./live/reconciliation_hypotheses.json?t=${Date.now()}`, { cache: 'no-store' });
      state.reco = r.ok ? await r.json() : null;
    } catch { state.reco = null; }
    try { await ensure(state.kind); } catch {
      state.kind = 'alertes'; // repli : jeu Détections pas encore publié
      try { await ensure('alertes'); } catch { return; }
    }
    render();
    try {
      const r = await fetch(`./live/gel_explorateur_prospective.json?t=${Date.now()}`, { cache: 'no-store' });
      state.frozen = r.ok ? await r.json() : null;
    } catch { state.frozen = null; }
    renderFrozen();
  }

  if (hasDoc && typeof module === 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  }
  if (typeof module !== 'undefined') {
    module.exports = { clusterSummary, cubeStats, alertStats, stats, prepareAlerts, prepareMatchs, prepareRows, prepareHisto,
      filterIndices, premierHorizon, splitGroups, freezeSpec, populationCounts, _state: state };
  }
})();
