/* Tennis Edge Lab V6.6 : filtre des books, stabilité 16 ans, propositions et gels V6.6. Lecture seule. */
(() => {
  'use strict';
  const $ = id => (typeof document !== 'undefined' ? document.getElementById(id) : null);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const nf = (v, d = 2) => v === null || v === undefined || Number.isNaN(v) ? '—'
    : new Intl.NumberFormat('fr-FR', { maximumFractionDigits: d }).format(v);
  const pct = v => v === null || v === undefined ? '—' : `${v > 0 ? '+' : ''}${nf(v)} %`;
  const pval = v => v === null || v === undefined ? '—' : v < 0.001 ? '< 0,001' : nf(v, 3);
  const ci = a => Array.isArray(a) && a.length === 2 ? `${pct(a[0])} à ${pct(a[1])}` : '—';
  const cls = v => v > 0 ? 'good' : v < 0 ? 'bad' : 'neutral';
  const KEY = 'tel-book-filter';
  const MARKETS = { match: 'Match', set1: 'Set 1', set2: 'Set 2' };

  function getFilter() {
    try { return localStorage.getItem(KEY) === 'fr' ? 'fr' : 'jouable'; } catch { return 'jouable'; }
  }
  function setFilter(value) {
    globalThis.TEL_BOOK_FILTER = value;
    try { localStorage.setItem(KEY, value); } catch { /* stockage indisponible : filtre de session */ }
    renderFilter();
    try { globalThis.dispatchEvent(new Event('tel-book-filter')); } catch { /* environnement de test */ }
    renderProposals();
    renderFrozen();
  }
  const keep = item => (globalThis.TEL_BOOK_FILTER === 'fr' ? !!item.jouable_fr : item.jouable !== false);
  const frBadge = item => item.jouable_fr ? ' <span class="badge fr" title="Opérateur agréé ANJ">FR</span>'
    : item.fr_incertain ? ' <span class="badge unsure" title="Statut ANJ à vérifier">FR ?</span>' : '';

  function renderFilter() {
    const host = $('bookFilter');
    if (!host) return;
    const current = globalThis.TEL_BOOK_FILTER;
    host.innerHTML = `<span class="mini">Books :</span>
      <button type="button" data-filter="jouable" class="${current === 'jouable' ? 'selected' : ''}" aria-pressed="${current === 'jouable'}">Tous les books jouables</button>
      <button type="button" data-filter="fr" class="${current === 'fr' ? 'selected' : ''}" aria-pressed="${current === 'fr'}">Jouables en France</button>`;
    host.querySelectorAll('button').forEach(b => b.addEventListener('click', () => setFilter(b.dataset.filter)));
  }

  async function load(url) {
    const r = await fetch(`${url}?t=${Date.now()}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`${url} : HTTP ${r.status}`);
    return r.json();
  }

  // ---------- Stabilité 16 ans ----------
  function renderHistory(doc) {
    const host = $('history16Body');
    if (!host) return;
    if (!doc || !Array.isArray(doc.cells)) { host.innerHTML = '<p class="mini">Rapport indisponible.</p>'; return; }
    const kp = (l, v, d) => `<div class="kpi"><small>${esc(l)}</small><b>${esc(v)}</b><small>${esc(d)}</small></div>`;
    const period = doc.period || {};
    const bands = doc.cells.filter(c => c.depth === 2)
      .sort((a, b) => (a.side === b.side ? doc.bands.indexOf(a.band) - doc.bands.indexOf(b.band) : a.side < b.side ? -1 : 1));
    const passing = doc.passing || [];
    host.innerHTML = `<div class="kpis">${kp('Matchs', nf(doc.matches, 0), `${esc(period.start)} → ${esc(period.end)}`)}
      ${kp('Cellules testées', nf(doc.cells_tested, 0), '≥ 5 années avec n ≥ 20')}
      ${kp('Cellules retenues', nf(doc.cells_passing, 0), 'Holm < 0,05 ou ≥ 70 % d’années + permutation')}</div>
      <p class="notice"><b>Descriptif.</b> Prix de clôture Pinnacle (marge incluse), pas d’ouverture. Le biais favori-outsider est attendu. Une cellule « stable » donne du contexte ; ce n’est pas une stratégie.</p>
      <h3>Cellules retenues</h3>
      ${passing.length ? `<div class="table-wrap"><table><thead><tr><th>Cellule</th><th class="num">n</th><th class="num">ROI · IC95</th><th class="num">vs pairs</th><th class="num">Années +</th><th class="num">p permutation</th><th class="num">p Holm</th></tr></thead><tbody>${passing.map(c => `<tr><td>${esc(c.cell)}</td><td class="num">${nf(c.n, 0)}</td><td class="num"><span class="${cls(c.roi_pct)}">${pct(c.roi_pct)}</span><div class="detail">${ci(c.roi_ci95)}</div></td><td class="num">${pct(c.roi_vs_peers_pct)}</td><td class="num">${nf(c.years_positive, 0)}/${nf(c.years_tested, 0)}</td><td class="num">${pval(c.p_permutation)}</td><td class="num"><b>${pval(c.p_holm)}</b></td></tr>`).join('')}</tbody></table></div>`
        : '<p class="mini">Aucune cellule ne passe les seuils.</p>'}
      <h3>Toutes années — par côté et tranche de cote</h3>
      <div class="table-wrap"><table><thead><tr><th>Côté · cote</th><th class="num">n</th><th class="num">ROI · IC95</th><th class="num">Années +</th></tr></thead><tbody>${bands.map(c => `<tr><td>${esc(c.side)} · ${esc(c.band)}</td><td class="num">${nf(c.n, 0)}</td><td class="num"><span class="${cls(c.roi_pct)}">${pct(c.roi_pct)}</span><div class="detail">${ci(c.roi_ci95)}</div></td><td class="num">${nf(c.years_positive, 0)}/${nf(c.years_tested, 0)}</td></tr>`).join('')}</tbody></table></div>
      <p class="mini">${esc(doc.rules?.null_model)} ${esc(doc.rules?.levels)} <a href="./live/history_stability.json" download>Exporter (JSON)</a></p>`;
  }

  // ---------- Propositions de la semaine ----------
  let proposals = null;
  let frozen = null;
  function renderProposals() {
    const host = $('v66Proposals');
    if (!host) return;
    if (!proposals) return;
    const list = (proposals.proposals || []).filter(keep);
    const head = `<p class="mini">Semaine ${esc(proposals.iso_week)} · ${nf(proposals.eligible_pool, 0)} segments éligibles · au plus ${nf(proposals.max_per_week, 0)} propositions · <b>non gelées</b>.</p>`;
    host.innerHTML = head + (list.length ? `<div class="cards">${list.map(p => `<article class="candidate">
      <h3><code>${esc(p.id)}</code> · ${esc(MARKETS[p.market] || p.market)} · ${esc(p.book)}${frBadge(p)} · ${esc(p.horizon)} · ${esc(p.selection)}</h3>
      <p class="small-rule">${(p.criteria || []).map(c => esc(c.value)).join(' · ')}</p>
      <div class="stats"><div><small>CLV Pinnacle · IC95</small><strong class="${cls(p.clv_pin_mean_pct)}">${pct(p.clv_pin_mean_pct)}</strong><small>${ci(p.clv_pin_ci95)}</small></div>
      <div><small>p Holm CLV</small><strong>${pval(p.p_holm_clv_pin)}</strong></div><div><small>Matchs</small><strong>${nf(p.n, 0)}</strong></div></div>
      <p class="detail">ROI (secondaire) ${pct(p.roi_pct)} · IC95 ${ci(p.roi_ci95)} · CLV book (secondaire) ${pct(p.clv_book_mean_pct)} · sans clôture Pinnacle : ${nf(p.sans_cloture_pinnacle, 0)}</p>
      <p class="detail"><b>16 ans :</b> ${esc(p.stabilite_16_ans?.label || '—')}</p>
      <p class="detail"><b>Mécanisme :</b> ${esc(p.note_mecanisme)}</p>
      ${p.alerte_grosse_cote ? '<p class="detail bad"><b>Attention :</b> grosse cote — le CLV Pinnacle est probablement gonflé (la marge retirée proportionnellement est trop faible sur les outsiders).</p>' : ''}
      <span class="chip">Proposition · non gelée</span></article>`).join('')}</div>`
      : '<p class="mini">Aucune proposition pour ce filtre de books.</p>') +
      '<p class="explain">Pour geler : GitHub → Actions → « Lab — geler des pistes V6.6 » → Run workflow, coller les identifiants choisis séparés par des virgules. Le suivi ne compte que les matchs à partir du lendemain du gel.</p>';
  }

  function renderFrozen() {
    const host = $('v66Frozen');
    if (!host || !frozen) return;
    const list = (frozen.candidates || []).filter(keep);
    host.innerHTML = `<p class="mini">${nf(frozen.total_frozen, 0)} piste(s) gelée(s) · ${esc(frozen.rule)} ${esc(frozen.multiple_testing)}</p>` +
      (list.length ? `<div class="table-wrap"><table><thead><tr><th>Piste</th><th>Gel · dès le</th><th class="num">Matchs futurs</th><th class="num">CLV Pinnacle · IC95</th><th class="num">p Holm</th><th class="num">ROI (secondaire)</th><th>État</th></tr></thead><tbody>${list.map(c => `<tr>
        <td><code>${esc(c.candidate_id)}</code><div class="detail">${esc(MARKETS[c.market] || c.market)} · ${esc(c.book)}${frBadge(c)} · ${esc(c.horizon)} · ${esc(c.selection)} · ${(c.criteria || []).map(x => esc(x.value)).join(' · ')}</div></td>
        <td>${esc(String(c.created_at).slice(0, 10))}<div class="detail">dès le ${esc(c.eligible_after_utc)}</div></td>
        <td class="num">${nf(c.n, 0)}<div class="detail">sans clôture Pinnacle : ${nf(c.sans_cloture_pinnacle, 0)}</div></td>
        <td class="num"><span class="${cls(c.clv_pin_mean_pct)}">${pct(c.clv_pin_mean_pct)}</span><div class="detail">${ci(c.clv_pin_ci95)}</div></td>
        <td class="num"><b>${pval(c.p_holm_clv_pin)}</b></td><td class="num">${pct(c.roi_pct)}</td><td>${esc(c.state)}</td></tr>`).join('')}</tbody></table></div>`
        : '<p class="mini">Aucune piste gelée pour ce filtre. Les propositions ci-dessus ne deviennent des gels que sur décision de Lucas.</p>');
  }

  async function start() {
    globalThis.TEL_BOOK_FILTER = getFilter();
    renderFilter();
    const [h, p, g] = await Promise.allSettled([
      load('./live/history_stability.json'), load('./live/propositions_v66.json'), load('./live/gel_v66_prospective.json'),
    ]);
    if (h.status === 'fulfilled') renderHistory(h.value);
    else if ($('history16Body')) $('history16Body').innerHTML = `<p class="notice warn">Stabilité 16 ans indisponible : ${esc(h.reason?.message)}</p>`;
    if (p.status === 'fulfilled' && Array.isArray(p.value.proposals)) { proposals = p.value; renderProposals(); }
    else if ($('v66Proposals')) $('v66Proposals').innerHTML = '<p class="notice warn">Propositions pas encore publiées par la tâche quotidienne.</p>';
    if (g.status === 'fulfilled' && Array.isArray(g.value.candidates)) { frozen = g.value; renderFrozen(); }
    else if ($('v66Frozen')) $('v66Frozen').innerHTML = '<p class="mini">Aucune piste V6.6 gelée pour l’instant.</p>';
  }

  if (typeof document !== 'undefined' && typeof module === 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
  }
  if (typeof module !== 'undefined') module.exports = { renderHistory, start, _set: (p, g) => { proposals = p; frozen = g; }, renderProposals, renderFrozen, setFilter };
})();
