/* Tennis Edge Lab V6.7 — Explorateur : découper pas à pas, en lecture seule. */
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
  /** Statistiques d'un ensemble d'alertes (indices). */
  function alertStats(D, idx) {
    const pnl = [], pDates = [], clv = [], cDates = [];
    let wins = 0, settled = 0;
    const months = new Map();
    for (const i of idx) {
      if (Number.isFinite(D.pnl[i])) { pnl.push(100 * D.pnl[i]); pDates.push(D.date[i]); settled++; if (D.won[i] === 1) wins++; }
      if (Number.isFinite(D.clv[i])) {
        clv.push(D.clv[i]); cDates.push(D.date[i]);
        const m = D.month[i]; const e = months.get(m) || [0, 0]; e[0] += D.clv[i]; e[1]++; months.set(m, e);
      }
    }
    const roi = clusterSummary(pnl, pDates), c = clusterSummary(clv, cDates);
    let mPos = 0, mTot = 0;
    for (const [, e] of months) if (e[1] >= 5) { mTot++; if (e[0] > 0) mPos++; }
    return { n: idx.length, settled, wins, roi: roi.mean, roiCi: roi.ci, clv: c.mean, clvCi: c.ci, p: c.p,
      clvN: c.n, monthsPos: mTot ? mPos / mTot : null };
  }

  // ---------- Données ----------
  async function fetchJsonGz(base) {
    if (typeof DecompressionStream !== 'undefined') {
      try {
        const r = await fetch(`${base}.json.gz?t=${Date.now()}`, { cache: 'no-store' });
        if (r.ok) {
          const text = await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text();
          return JSON.parse(text);
        }
      } catch { /* repli JSON simple */ }
    }
    const r = await fetch(`${base}.json?t=${Date.now()}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`${base} : HTTP ${r.status}`);
    return r.json();
  }

  function prepareAlerts(doc) {
    const col = name => doc.columns.indexOf(name);
    const fields = doc.fields.filter(f => f.role === 'filtre' || f.role === 'filtre_apres_alerte');
    const D = { kind: 'alertes', n: doc.rows.length, fields, codes: {}, dicts: {}, labels: {}, summary: doc.summary };
    for (const f of fields) {
      const j = col(f.name), dict = [], map = new Map(), arr = new Uint16Array(D.n);
      doc.rows.forEach((r, i) => { const v = String(r[j]); if (!map.has(v)) { map.set(v, dict.length); dict.push(v); } arr[i] = map.get(v); });
      D.codes[f.name] = arr; D.dicts[f.name] = dict; D.labels[f.name] = f.label + (f.role === 'filtre_apres_alerte' ? ' (connu après l’alerte H)' : '');
    }
    const num = name => { const j = col(name); const a = new Float64Array(D.n); doc.rows.forEach((r, i) => { a[i] = r[j] === null ? NaN : r[j]; }); return a; };
    D.pnl = num('pnl'); D.clv = num('clv_pin');
    const jw = col('gagne'); D.won = new Int8Array(D.n); doc.rows.forEach((r, i) => { D.won[i] = r[jw] === null ? -1 : r[jw]; });
    const jd = col('date'), jm = col('mois');
    D.date = doc.rows.map(r => r[jd]); D.month = doc.rows.map(r => r[jm]);
    D.byPeriod = D.month; D.periodLabel = 'Mois';
    return D;
  }
  function prepareHisto(doc) {
    const D = { kind: 'histo', n: doc.cells.length, fields: doc.keys.map(k => ({ name: k, label: doc.labels[k] })), codes: {}, dicts: {}, labels: doc.labels };
    doc.keys.forEach((k, j) => {
      const dict = [], map = new Map(), arr = new Uint16Array(D.n);
      doc.cells.forEach((c, i) => { const v = String(c[j]); if (!map.has(v)) { map.set(v, dict.length); dict.push(v); } arr[i] = map.get(v); });
      D.codes[k] = arr; D.dicts[k] = dict;
    });
    const off = doc.keys.length;
    D.cells = doc.cells.map(c => ({ n: c[off], w: c[off + 1], s: c[off + 2], s2: c[off + 3] }));
    D.year = doc.cells.map(c => c[0]);
    return D;
  }

  function filterIndices(D, filters, except) {
    const out = [];
    const active = filters.filter(f => f.field !== except).map(f => [D.codes[f.field], new Set(f.values.map(v => D.dicts[f.field].indexOf(v)))]);
    for (let i = 0; i < D.n; i++) {
      let ok = true;
      for (const [codes, set] of active) if (!set.has(codes[i])) { ok = false; break; }
      if (ok) out.push(i);
    }
    return out;
  }
  function stats(D, idx) {
    if (D.kind === 'histo') {
      const s = cubeStats(idx.map(i => D.cells[i]));
      const years = new Map();
      for (const i of idx) { const y = D.year[i]; const e = years.get(y) || [0, 0]; e[0] += D.cells[i].s; e[1] += D.cells[i].n; years.set(y, e); }
      let pos = 0, tot = 0; for (const [, e] of years) if (e[1] >= 20) { tot++; if (e[0] > 0) pos++; }
      return { n: s.n, settled: s.n, wins: s.wins, roi: s.roi, roiCi: s.ci, clv: null, clvCi: null, p: null, monthsPos: tot ? pos / tot : null };
    }
    return alertStats(D, idx);
  }

  // ---------- État de l'interface ----------
  const state = { kind: 'alertes', data: {}, filters: [], splitBy: null, sort: 'n', compare: false, seen: new Set(), frozen: null };
  const PRESETS = {
    h_public: { label: 'Exemple : alertes H suivies d’une alerte publique', filters: [{ field: 'type', values: ['H13', 'H16', 'H16B', 'H17', 'H18'] }, { field: 'suivie_public', values: ['oui'] }], split: 'circuit' },
    public_h: { label: 'Exemple : alertes publiques précédées d’une alerte H', filters: [{ field: 'type', values: ['PUBLIC'] }, { field: 'precede_par_H', values: ['oui'] }], split: 'circuit' },
  };

  function D() { return state.data[state.kind]; }
  function k() { return Math.max(1, state.seen.size); }

  function render() {
    const host = $('explorerBody');
    if (!host) return;
    const data = D();
    if (!data) { host.innerHTML = '<p class="mini">Chargement des données…</p>'; return; }
    const idx = filterIndices(data, state.filters);
    const s = stats(data, idx);
    const candidates = data.fields.map(f => f.name).filter(n => !state.filters.some(f => f.field === n));
    if (!state.splitBy || !candidates.includes(state.splitBy)) state.splitBy = candidates[0] || null;
    const seenKey = JSON.stringify([state.kind, state.filters, state.splitBy]);
    if (state.splitBy) state.seen.add(seenKey);
    const alpha = 0.05 / k();
    host.innerHTML = `
      ${toolbar()}
      ${chips(data)}
      ${summaryCard(data, idx, s)}
      ${state.compare ? compareCard(data, idx, s) : ''}
      ${splitTable(data, idx, alpha)}
      ${freezeBlock(data, s)}`;
    bind();
  }

  function toolbar() {
    const isA = state.kind === 'alertes';
    return `<div class="xp-switch" role="group" aria-label="Jeu de données">
        <button type="button" data-kind="alertes" class="${isA ? 'selected' : ''}">Nos alertes</button>
        <button type="button" data-kind="histo" class="${!isA ? 'selected' : ''}">Historique 2010–2026</button></div>
      <p class="mini">${isA ? 'Alertes surtout de <b>juin à octobre 2026</b> : échantillons courts. Mesure principale : CLV Pinnacle.' : 'tennis-data, clôture Pinnacle (marge incluse) : ROI au prix de clôture, pas de CLV.'}
      · <b>Découpes consultées : ${k()}</b> · seuil corrigé α/k = ${pval(0.05 / k())}</p>
      ${isA ? `<div class="xp-presets">${Object.entries(PRESETS).map(([id, p]) => `<button type="button" data-preset="${id}">${esc(p.label)}</button>`).join('')}</div>` : ''}`;
  }

  function chips(data) {
    if (!state.filters.length) return '<p class="mini">Aucun critère : toute la base. Touchez une ligne du tableau pour découper.</p>';
    return `<div class="xp-chips" aria-label="Critères actifs">${state.filters.map((f, i) =>
      `<button type="button" class="xp-chip" data-remove="${i}" title="Retirer">${esc(data.labels[f.field] || f.field)} : ${esc(f.values.join(', '))} ✕</button>`).join('')}
      <button type="button" class="xp-chip clear" data-clear="1">Tout effacer</button></div>`;
  }

  function badges(s) {
    const out = [];
    if (s.n < 30) out.push('<span class="xp-warn">n &lt; 30</span>');
    if (excludesZero(s.roiCi) && s.roiCi[0] > 0 && s.clvCi && !excludesZero(s.clvCi)) out.push('<span class="xp-luck">ROI seul, CLV Pinnacle compatible avec 0 : probablement de la chance</span>');
    return out.join(' ');
  }

  function periodTable(data, idx) {
    const groups = new Map();
    for (const i of idx) {
      const key = data.kind === 'histo' ? data.year[i] : data.month[i];
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(i);
    }
    const keys = [...groups.keys()].sort();
    return `<div class="table-wrap"><table class="xp-mini"><thead><tr><th>${data.kind === 'histo' ? 'Année' : 'Mois'}</th><th class="num">n</th><th class="num">ROI</th>${data.kind === 'alertes' ? '<th class="num">CLV Pinnacle</th>' : ''}</tr></thead><tbody>${keys.map(key => {
      const s = stats(data, groups.get(key));
      return `<tr><td>${esc(key)}</td><td class="num">${nf(s.n, 0)}</td><td class="num">${pct(s.roi)}</td>${data.kind === 'alertes' ? `<td class="num">${pct(s.clv)}</td>` : ''}</tr>`;
    }).join('')}</tbody></table></div>`;
  }

  function summaryCard(data, idx, s) {
    let period = '';
    if (data.kind === 'alertes' && idx.length) { const ds = idx.map(i => data.date[i]).sort(); period = `${ds[0]} → ${ds[ds.length - 1]}`; }
    if (data.kind === 'histo' && idx.length) { const ys = idx.map(i => data.year[i]).sort(); period = `${ys[0]} → ${ys[ys.length - 1]}`; }
    return `<article class="candidate xp-summary"><h3>Sélection actuelle ${badges(s)}</h3>
      <div class="stats"><div><small>${data.kind === 'histo' ? 'Paris' : 'Alertes'}</small><strong>${nf(s.n, 0)}</strong><small>${data.kind === 'alertes' ? `${nf(s.settled, 0)} réglées` : ''}</small></div>
      ${data.kind === 'alertes' ? `<div><small>CLV Pinnacle · IC95</small><strong class="${excludesZero(s.clvCi) ? (s.clv > 0 ? 'good' : 'bad') : ''}">${pct(s.clv)}</strong><small>${ciTxt(s.clvCi)}</small></div>` : ''}
      <div><small>ROI · IC95${data.kind === 'alertes' ? ' (secondaire)' : ''}</small><strong>${pct(s.roi)}</strong><small>${ciTxt(s.roiCi)}</small></div></div>
      <p class="detail">Période : ${esc(period || '—')} · gagnés ${s.settled ? nf(100 * s.wins / s.settled, 1) + ' %' : '—'}</p>
      <details><summary>Détail par ${data.kind === 'histo' ? 'année' : 'mois'}</summary>${periodTable(data, idx)}</details>
      <label class="xp-compare"><input type="checkbox" id="xpCompare" ${state.compare ? 'checked' : ''}> Comparer avec le reste</label></article>`;
  }

  function compareCard(data, idx, s) {
    const inSel = new Set(idx); const rest = [];
    for (let i = 0; i < data.n; i++) if (!inSel.has(i)) rest.push(i);
    const r = stats(data, rest);
    const overlap = (a, b) => a && b ? !(a[0] > b[1] || b[0] > a[1]) : null;
    const line = (name, a, b, ca, cb) => `<tr><td>${name}</td><td class="num">${pct(a)}</td><td class="num">${pct(b)}</td><td class="num">${pct(a !== null && b !== null ? a - b : null)}</td><td>${overlap(ca, cb) === null ? '—' : overlap(ca, cb) ? 'IC qui se chevauchent : différence non établie' : '<b>IC disjoints</b>'}</td></tr>`;
    return `<article class="candidate xp-cmp"><h3>Sélection contre le reste (${nf(r.n, 0)})</h3><div class="table-wrap"><table class="xp-mini"><thead><tr><th>Mesure</th><th class="num">Sélection</th><th class="num">Reste</th><th class="num">Écart</th><th>Lecture</th></tr></thead><tbody>
      ${data.kind === 'alertes' ? line('CLV Pinnacle', s.clv, r.clv, s.clvCi, r.clvCi) : ''}${line('ROI', s.roi, r.roi, s.roiCi, r.roiCi)}</tbody></table></div></article>`;
  }

  function splitTable(data, idx, alpha) {
    if (!state.splitBy) return '<p class="mini">Tous les critères sont utilisés.</p>';
    const codes = data.codes[state.splitBy], dict = data.dicts[state.splitBy];
    const groups = dict.map(() => []);
    for (const i of idx) groups[codes[i]].push(i);
    let rows = dict.map((value, j) => ({ value, s: stats(data, groups[j]) })).filter(r => r.s.n > 0);
    if (state.sort === 'clv' && data.kind === 'alertes') rows.sort((a, b) => ((b.s.clvCi?.[0] ?? -1e9) - (a.s.clvCi?.[0] ?? -1e9)));
    else if (state.sort === 'valeur') rows.sort((a, b) => a.value.localeCompare(b.value, 'fr'));
    else rows.sort((a, b) => b.s.n - a.s.n);
    const maxN = Math.max(1, ...rows.map(r => r.s.n));
    const isA = data.kind === 'alertes';
    const options = data.fields.filter(f => !state.filters.some(x => x.field === f.name))
      .map(f => `<option value="${esc(f.name)}" ${f.name === state.splitBy ? 'selected' : ''}>${esc(data.labels[f.name] || f.label)}</option>`).join('');
    return `<div class="xp-controls"><label>Découper par <select id="xpSplit">${options}</select></label>
      <label>Trier <select id="xpSort"><option value="n" ${state.sort === 'n' ? 'selected' : ''}>par effectif</option>${isA ? `<option value="clv" ${state.sort === 'clv' ? 'selected' : ''}>par borne basse CLV Pinnacle</option>` : ''}<option value="valeur" ${state.sort === 'valeur' ? 'selected' : ''}>par valeur</option></select></label></div>
      ${state.splitBy === 'suivie_public' ? '<p class="xp-luck">Ce critère est connu après l’alerte H : utile pour comprendre, pas pour décider au moment de l’alerte H.</p>' : ''}
      <div class="table-wrap"><table class="xp-split"><thead><tr><th>${esc(data.labels[state.splitBy] || state.splitBy)}</th><th class="num">n</th><th class="num">Gagnés</th><th class="num">ROI · IC95</th>${isA ? '<th class="num">CLV Pinnacle · IC95</th><th class="num">p (seuil)</th>' : ''}<th class="num">${isA ? 'Mois CLV+' : 'Années ROI+'}</th><th></th></tr></thead><tbody>
      ${rows.map(r => {
        const s = r.s;
        return `<tr class="xp-row" data-value="${esc(r.value)}" tabindex="0"><td><b>${esc(r.value)}</b> ${s.n < 30 ? '<span class="xp-warn">n &lt; 30</span>' : ''}${isA && excludesZero(s.roiCi) && s.roiCi[0] > 0 && !excludesZero(s.clvCi) ? ' <span class="xp-luck">probablement de la chance</span>' : ''}</td>
          <td class="num">${nf(s.n, 0)}</td><td class="num">${s.settled ? nf(100 * s.wins / s.settled, 0) + ' %' : '—'}</td>
          <td class="num">${pct(s.roi)}<div class="detail">${ciTxt(s.roiCi)}</div></td>
          ${isA ? `<td class="num ${excludesZero(s.clvCi) ? 'xp-sig' : ''}">${pct(s.clv)}<div class="detail">${ciTxt(s.clvCi)}</div></td><td class="num">${pval(s.p)}<div class="detail">${s.p !== null && s.p < alpha ? '<b>&lt; α/k</b>' : `α/k ${pval(alpha)}`}</div></td>` : ''}
          <td class="num">${s.monthsPos === null ? '—' : nf(100 * s.monthsPos, 0) + ' %'}</td>
          <td><span class="xp-bar" style="width:${Math.round(60 * s.n / maxN)}px"></span></td></tr>`;
      }).join('')}</tbody></table></div><p class="mini">Touchez une ligne pour l’ajouter comme critère. Gras = IC95 du CLV Pinnacle qui exclut 0. Chaque découpe consultée augmente k (correction de Bonferroni).</p>`;
  }

  function freezeSpec(data, s) {
    return {
      jeu: 'alertes',
      criteres: Object.fromEntries(state.filters.map(f => [f.field, f.values])),
      date: new Date().toISOString().slice(0, 10),
      stats: { n: s.n, clv_pin: s.clv === null ? null : +s.clv.toFixed(3), clv_ic95: s.clvCi ? s.clvCi.map(x => +x.toFixed(3)) : null,
        roi: s.roi === null ? null : +s.roi.toFixed(2), decoupes_consultees: k() },
    };
  }
  function freezeBlock(data, s) {
    if (data.kind !== 'alertes') return '<p class="mini">Le gel ne concerne que « Nos alertes » (l’historique est déjà passé).</p>';
    return `<div class="xp-freeze"><button type="button" id="xpFreeze">Préparer le gel</button><div id="xpFreezeOut"></div></div>`;
  }
  function showFreeze() {
    const data = D(); const idx = filterIndices(data, state.filters); const s = stats(data, idx);
    const out = $('xpFreezeOut'); if (!out) return;
    const bad = state.filters.filter(f => f.field === 'suivie_public' || f.field === 'mois');
    if (!state.filters.length) { out.innerHTML = '<p class="xp-luck">Ajoutez au moins un critère avant de geler.</p>'; return; }
    if (bad.length) { out.innerHTML = '<p class="xp-luck">Retirez « Mois » et « Suivie d’une alerte publique » : ils ne sont pas connus à l’avance pour des matchs futurs.</p>'; return; }
    const json = JSON.stringify(freezeSpec(data, s));
    out.innerHTML = `<p class="detail">Copier ce bloc dans l’entrée <b>explorateur</b> du workflow <b>« Lab - gel (V6.6 et explorateur) »</b> (GitHub → Actions → Run workflow). Seules les alertes à partir du lendemain du gel compteront.</p>
      <textarea readonly rows="5" class="xp-json" aria-label="Spécification du gel">${esc(json)}</textarea>`;
  }

  function renderFrozen() {
    const host = $('explorerFrozen'); if (!host) return;
    const f = state.frozen;
    if (!f || !Array.isArray(f.candidates) || !f.candidates.length) { host.innerHTML = '<p class="mini">Aucune sélection de l’Explorateur gelée pour l’instant.</p>'; return; }
    host.innerHTML = `<p class="mini">${esc(f.rule)} ${esc(f.multiple_testing)}</p><div class="table-wrap"><table class="xp-mini"><thead><tr><th>Sélection</th><th>Gel</th><th class="num">Alertes futures</th><th class="num">CLV Pinnacle · IC95</th><th class="num">p Holm</th><th class="num">ROI</th><th>État</th></tr></thead><tbody>${f.candidates.map(c => `<tr><td><code>${esc(c.candidate_id)}</code><div class="detail">${esc(Object.entries(c.criteres).map(([a, b]) => `${a} : ${b.join(', ')}`).join(' · '))}</div></td><td>${esc(String(c.created_at).slice(0, 10))}</td><td class="num">${nf(c.n, 0)}</td><td class="num">${pct(c.clv_pin_mean_pct)}<div class="detail">${ciTxt(c.clv_pin_ci95)}</div></td><td class="num">${pval(c.p_holm_clv_pin)}</td><td class="num">${pct(c.roi_pct)}</td><td>${esc(c.state)}</td></tr>`).join('')}</tbody></table></div>`;
  }

  function addFilter(field, value) {
    const existing = state.filters.find(f => f.field === field);
    if (existing) existing.values = [value]; else state.filters.push({ field, values: [value] });
    render();
  }

  function bind() {
    const host = $('explorerBody');
    host.querySelectorAll('[data-kind]').forEach(b => b.addEventListener('click', async () => {
      state.kind = b.dataset.kind; state.filters = []; state.splitBy = null;
      await ensure(state.kind); render();
    }));
    host.querySelectorAll('[data-preset]').forEach(b => b.addEventListener('click', () => {
      const p = PRESETS[b.dataset.preset];
      state.filters = p.filters.map(f => ({ field: f.field, values: f.values.filter(v => D().dicts[f.field]?.includes(v)) })).filter(f => f.values.length);
      state.splitBy = p.split; render();
    }));
    host.querySelectorAll('[data-remove]').forEach(b => b.addEventListener('click', () => { state.filters.splice(+b.dataset.remove, 1); render(); }));
    host.querySelectorAll('[data-clear]').forEach(b => b.addEventListener('click', () => { state.filters = []; render(); }));
    host.querySelectorAll('.xp-row').forEach(tr => {
      const go = () => addFilter(state.splitBy, tr.dataset.value);
      tr.addEventListener('click', go);
      tr.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
    });
    const split = $('xpSplit'); if (split) split.addEventListener('change', () => { state.splitBy = split.value; render(); });
    const sort = $('xpSort'); if (sort) sort.addEventListener('change', () => { state.sort = sort.value; render(); });
    const cmp = $('xpCompare'); if (cmp) cmp.addEventListener('change', () => { state.compare = cmp.checked; render(); });
    const fr = $('xpFreeze'); if (fr) fr.addEventListener('click', showFreeze);
  }

  async function ensure(kind) {
    if (state.data[kind]) return;
    const host = $('explorerBody');
    try {
      if (kind === 'alertes') state.data.alertes = prepareAlerts(await fetchJsonGz('./live/explorateur_alertes'));
      else state.data.histo = prepareHisto(await fetchJsonGz('./live/explorateur_histo'));
    } catch (e) {
      if (host) host.innerHTML = `<p class="notice warn">Données de l’Explorateur indisponibles : ${esc(e.message)}</p>`;
      throw e;
    }
  }

  async function start() {
    if (!$('explorerBody')) return;
    try { await ensure('alertes'); render(); } catch { return; }
    try {
      const r = await fetch(`./live/gel_explorateur_prospective.json?t=${Date.now()}`, { cache: 'no-store' });
      state.frozen = r.ok ? await r.json() : null;
    } catch { state.frozen = null; }
    renderFrozen();
  }

  if (hasDoc && typeof module === 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  }
  if (typeof module !== 'undefined') module.exports = { clusterSummary, cubeStats, alertStats, prepareAlerts, prepareHisto, filterIndices, stats, freezeSpec, _state: state };
})();
