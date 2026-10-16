/* Tennis Edge Lab V7.1 — Réconciliation : verdicts EN DIRECT ↔ reconstruction (contrôle) ↔ Worker. Lecture seule. */
(() => {
  'use strict';
  const hasDoc = typeof document !== 'undefined';
  const $ = id => (hasDoc ? document.getElementById(id) : null);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const nf = (v, d = 1) => v === null || v === undefined || !Number.isFinite(+v) ? '—'
    : new Intl.NumberFormat('fr-FR', { maximumFractionDigits: d }).format(+v);
  const signed = (v, unit) => {
    if (v === null || v === undefined || !Number.isFinite(+v)) return '—';
    const r = Math.round(+v * 10) / 10 || 0;
    return `${r > 0 ? '+' : ''}${nf(r, 1)}${unit}`;
  };
  const pct = v => signed(v, ' %');
  const pts = v => signed(v, ' pts');
  const CODES = ['H13', 'H14', 'H15', 'H16', 'H16B', 'H17', 'H18'];

  // ---------- Fonctions pures (testées sous Node) ----------
  /** Agrégats Worker recopiés tels quels depuis une capture /api/hypotheses (même règle que reconciliation.py). */
  function workerFromSnapshot(snap) {
    const out = {};
    if (!snap || snap.status !== 'ok' || !Array.isArray(snap.hypotheses)) return out;
    for (const h of snap.hypotheses) {
      if (!h || typeof h !== 'object' || !h.out_of_sample || typeof h.out_of_sample !== 'object') continue;
      const code = String(h.code || '').toUpperCase().replace('-', '');
      const oos = {};
      for (const [k, v] of Object.entries(h.out_of_sample)) if (v === null || ['number', 'string'].includes(typeof v)) oos[k] = v;
      out[code] = { gele_le: h.gele_le ?? null, out_of_sample: oos, n: h.out_of_sample.n ?? null, roi: h.out_of_sample.roi ?? null };
    }
    return out;
  }
  /** Capture horaire de Pages si plus récente que celle embarquée dans le calcul quotidien. */
  function pickWorker(doc, hourly) {
    const embedded = { at: doc?.sources?.worker?.fetched_at || null, status: doc?.sources?.worker?.status || 'absent',
      by: Object.fromEntries(CODES.map(c => [c, doc?.hypotheses?.[c]?.worker || null])), origine: 'capture du calcul quotidien' };
    const h = workerFromSnapshot(hourly);
    if (hourly && hourly.status === 'ok' && Object.keys(h).length && (!embedded.at || String(hourly.fetched_at) > String(embedded.at)))
      return { at: hourly.fetched_at, status: 'ok', by: Object.fromEntries(CODES.map(c => [c, h[c] || null])), origine: 'capture horaire (Pages)' };
    return embedded;
  }
  /** Lignes du tableau de synthèse : une par hypothèse. */
  function summaryRows(doc, worker) {
    return CODES.filter(c => doc?.hypotheses?.[c]).map(c => {
      const h = doc.hypotheses[c], w = worker.by[c], o = h.suivi_officiel, e = h.entonnoir;
      return { code: c, worker: w, officiel: o, detectees: e.direct_detectees, envoyees: e.direct_envoyees,
        reconstruction: h.reconstruction, communes: e.communes, inexpliques: e.inexpliques,
        ecartWorker: w && Number.isFinite(w.n) ? w.n - o.n : null };
    });
  }
  /** Filtre de la liste des écarts : 'tous' | 'inexpliques' | 'reco' | 'direct' | code de raison. */
  function filterEcarts(list, mode) {
    if (!Array.isArray(list)) return [];
    if (mode === 'inexpliques') return list.filter(e => !e.explique);
    if (mode === 'reco') return list.filter(e => e.sens === 'reconstruction seule');
    if (mode === 'direct') return list.filter(e => e.sens === 'direct seule');
    if (mode && mode !== 'tous') return list.filter(e => e.raison === mode);
    return list.slice();
  }
  /** Autres champs numériques publiés par le Worker (pts, CLV…), sans interprétation. */
  function workerExtras(w) {
    if (!w || !w.out_of_sample) return [];
    return Object.entries(w.out_of_sample).filter(([k, v]) => !['n', 'roi'].includes(k) && typeof v === 'number').map(([k, v]) => `${k} ${nf(v, 2)}`);
  }

  // ---------- Rendu ----------
  const state = { doc: null, hourly: null, code: 'H13', mode: 'tous', all: false };

  function renderSummary(rows, worker) {
    return `<div class="table-wrap"><table class="rc-table"><thead><tr><th>Hyp.</th><th class="num">Officiel (direct)<div class="detail">dénouées · ROI · pts</div></th><th class="num">Dét.<div class="detail">env.</div></th><th class="num">Contrôle<div class="detail">reco.</div></th><th class="num">Worker</th><th class="num">⚠</th></tr></thead><tbody>${rows.map(r => `<tr class="rc-row ${r.code === state.code ? 'rc-selected' : ''}" data-code="${r.code}" tabindex="0">
      <td><b>${r.code}</b></td>
      <td class="num">${nf(r.officiel.n, 0)}<div class="detail">${pct(r.officiel.roi)} · ${pts(r.officiel.pts)}</div></td>
      <td class="num">${nf(r.detectees, 0)}<div class="detail">${nf(r.envoyees, 0)}</div></td>
      <td class="num">${nf(r.reconstruction.n, 0)}<div class="detail">${pct(r.reconstruction.roi)}</div></td>
      <td class="num">${r.worker ? `${nf(r.worker.n, 0)}<div class="detail">${pct(r.worker.roi)}</div>` : '—'}</td>
      <td class="num">${r.inexpliques ? `<span class="rc-flag">⚠ ${r.inexpliques}</span>` : '0'}</td></tr>`).join('')}</tbody></table></div>
      <p class="mini">Officiel = alertes <b>en direct</b> (verdicts_direct.json), seule base des verdicts. Contrôle = reconstruction moves_detail_hist (ne juge pas). ${worker.status === 'ok' ? `Worker : ${esc(worker.origine)} du ${esc(worker.at || '—')}, recopié.` : `Worker : aucune capture disponible (statut ${esc(worker.status)}).`} Touchez une ligne pour le détail.</p>`;
  }

  function funnel(h) {
    const e = h.entonnoir, labels = state.doc.raisons || {};
    const reasons = obj => Object.entries(obj || {}).sort((a, b) => b[1] - a[1]).map(([k, n]) => `<li><span class="${labels[k]?.explique === false ? 'rc-flag' : ''}">${esc(labels[k]?.libelle || k)}</span> <b>${nf(n, 0)}</b></li>`).join('') || '<li>aucune</li>';
    return `<div class="rc-funnel">
      <div class="rc-step"><small>En direct (officiel)</small><strong>${nf(e.direct_detectees, 0)}</strong><small>${nf(e.direct_envoyees, 0)} envoyées · ${nf(e.direct_doublons, 0)} doublons${e.direct_non_envoyees_autres ? ` · ${nf(e.direct_non_envoyees_autres, 0)} non envoyées` : ''} · ${nf(e.direct_denouees, 0)} dénouées</small></div>
      <div class="rc-step"><small>Reconstruction (contrôle)</small><strong>${nf(e.reconstruction_detectees, 0)}</strong><small>${nf(e.reconstruction_reglees, 0)} réglées</small></div>
      <div class="rc-step"><small>Communes</small><strong>${nf(e.communes, 0)}</strong><small>même match, même joueur</small></div></div>
      <div class="rc-reasons"><div><h4>En direct, absentes de la reconstruction : ${nf(e.direct_seule, 0)}</h4><ul>${reasons(e.direct_seule_raisons)}</ul></div>
      <div><h4>Reconstruction seule (pas en direct) : ${nf(e.reconstruction_seule, 0)}</h4><ul>${reasons(e.reconstruction_seule_raisons)}</ul></div></div>`;
  }

  function measures(h) {
    const m = h.mesures;
    const rows = [['Suivi officiel (direct, verdict)', m.suivi_officiel], ['· dont envoyées', m.envoyees], ['· dont détectées non envoyées', m.detectees_non_envoyees],
      ['Reconstruction (contrôle)', m.reconstruction], ['Communes · prix direct', m.communes_direct], ['Communes · prix reconstruit', m.communes_reconstruction],
      ['Direct seule', m.direct_seule], ['Reconstruction seule', m.reconstruction_seule]];
    return `<div class="table-wrap"><table class="rc-table rc-measures"><thead><tr><th>Population (dénouées)</th><th class="num">n</th><th class="num">ROI</th><th class="num">pts</th><th class="num">CLV Pinnacle</th></tr></thead><tbody>${rows.map(([l, s]) => `<tr><td>${esc(l)}${s.n && s.n < 30 ? ' <span class="rc-warn">n &lt; 30</span>' : ''}</td><td class="num">${nf(s.n, 0)}</td><td class="num">${pct(s.roi)}</td><td class="num">${pts(s.pts)}</td><td class="num">${pct(s.clv_pin)}</td></tr>`).join('')}</tbody></table></div>
      <p class="mini">pts = taux de gain − seuil de rentabilité (moyenne de 1/cote nette). Mesure principale : CLV Pinnacle (clôture sans marge, méthode puissance). Petits effectifs : prudence.</p>`;
  }

  function ecartsList(h) {
    const labels = state.doc.raisons || {};
    const present = [...new Set((h.ecarts || []).map(e => e.raison))];
    const list = filterEcarts(h.ecarts, state.mode).sort((a, b) => (a.explique - b.explique) || String(b.date).localeCompare(String(a.date)));
    const shown = state.all ? list : list.slice(0, 15);
    const opts = [['tous', 'Tous les écarts'], ['inexpliques', '⚠ Inexpliqués'], ['direct', 'En direct, absentes de la reconstruction'], ['reco', 'Reconstruction seule'],
      ...present.map(k => [k, labels[k]?.libelle || k])];
    return `<label class="rc-filter">Afficher <select id="rcMode">${opts.map(([v, l]) => `<option value="${esc(v)}" ${state.mode === v ? 'selected' : ''}>${esc(l)}</option>`).join('')}</select></label>
      <ul class="rc-list">${shown.map(e => `<li class="${e.explique ? '' : 'rc-unexplained'}"><div><b>${esc(e.date)}</b> · ${esc(e.match)}${e.explique ? '' : ' <span class="rc-flag">⚠ inexpliqué</span>'}</div>
        <div class="detail">${esc(e.sens)} · <b>${esc(e.joueur)}</b>${e.cote ? ` à ${nf(e.cote, 2)}` : ''}${e.book ? ` (${esc(e.book)})` : ''} · ${esc(e.statut)}</div>
        <div class="detail">${esc(e.libelle)}${e.detail ? ` — ${esc(e.detail)}` : ''}</div></li>`).join('') || '<li class="detail">Aucun écart dans ce filtre.</li>'}</ul>
      ${list.length > shown.length ? `<button type="button" id="rcAll" class="rc-more">Afficher les ${nf(list.length, 0)} écarts</button>` : ''}`;
  }

  function render() {
    const host = $('reconciliationBody');
    if (!host) return;
    const doc = state.doc;
    if (!doc || !doc.hypotheses) { host.innerHTML = '<p class="notice warn">Réconciliation pas encore calculée (tâche quotidienne).</p>'; return; }
    const worker = pickWorker(doc, state.hourly);
    const rows = summaryRows(doc, worker);
    const h = doc.hypotheses[state.code] || doc.hypotheses[rows[0]?.code];
    const w = worker.by[state.code];
    const gap = w && Number.isFinite(w.n) ? w.n - h.suivi_officiel.n : null;
    const o = h.suivi_officiel, k = h.reconstruction;
    host.innerHTML = `${renderSummary(rows, worker)}
      <article class="candidate rc-card"><h3>${esc(state.code)} · ${esc(h.regle)}</h3>
      <p class="detail">Gel ${esc(h.gel)} · canal ${esc(h.canal)}_signal_log.jsonl, première détection ${esc(h.mise_en_service || '—')}</p>
      <p class="detail"><b>Officiel (direct)</b> : ${nf(o.n_detectees, 0)} détectées · ${nf(o.n_envoyees, 0)} envoyées · ${nf(o.n, 0)} dénouées · ROI ${pct(o.roi)} · ${pts(o.pts)} · CLV Pinnacle ${pct(o.clv_pin)}${o.clv_pin_ic95 ? ` [${pct(o.clv_pin_ic95[0])} ; ${pct(o.clv_pin_ic95[1])}]` : ''}${o.statut ? ` · <b class="${o.verrouillable === false ? 'bad' : ''}">${esc(o.statut)}</b>` : ''}</p>
      <p class="detail">Contrôle reconstruction : ${nf(k.n, 0)} réglées · ROI ${pct(k.roi)} · ${pts(k.pts)} — identique à validation_report.py : ${k.egal_validation_report === true ? '<b class="good">oui</b>' : k.egal_validation_report === false ? '<b class="bad">non</b>' : 'non vérifié'}</p>
      <p class="detail">Worker : ${w ? `n ${nf(w.n, 0)} · ROI ${pct(w.roi)}${workerExtras(w).length ? ' · ' + esc(workerExtras(w).join(' · ')) : ''}` : 'pas de chiffre publié'}${gap !== null ? ` — écart avec l'officiel : <b>${gap > 0 ? '+' : ''}${nf(gap, 0)}</b>` : ''}</p>
      ${funnel(h)}${measures(h)}<h4>Liste des écarts direct ↔ reconstruction</h4>${ecartsList(h)}</article>
      <p class="mini">Sources : ${esc(doc.sources?.suivi_officiel || '')} · ${esc(doc.sources?.reconstruction || '')} · rapprochement ${esc(doc.sources?.rapprochement || '')} · calcul ${esc(doc.generated_at || '—')}.</p>`;
    bind();
  }

  function bind() {
    const host = $('reconciliationBody');
    host.querySelectorAll('.rc-row').forEach(tr => {
      const go = () => { state.code = tr.dataset.code; state.mode = 'tous'; state.all = false; render(); };
      tr.addEventListener('click', go);
      tr.addEventListener('keydown', e => { if (e.key === 'Enter') go(); });
    });
    const mode = $('rcMode'); if (mode) mode.addEventListener('change', () => { state.mode = mode.value; state.all = false; render(); });
    const all = $('rcAll'); if (all) all.addEventListener('click', () => { state.all = true; render(); });
  }

  async function getJson(url) {
    const r = await fetch(`${url}?t=${Date.now()}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  async function start() {
    if (!$('reconciliationBody')) return;
    try { state.doc = await getJson('./live/reconciliation_hypotheses.json'); } catch { state.doc = null; }
    try { state.hourly = await getJson('./live/worker_hypotheses.json'); } catch { state.hourly = null; }
    render();
  }

  if (hasDoc && typeof module === 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  }
  if (typeof module !== 'undefined') module.exports = { workerFromSnapshot, pickWorker, summaryRows, filterEcarts, workerExtras };
})();
