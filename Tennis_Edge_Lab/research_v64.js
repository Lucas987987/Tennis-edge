/* V6.4 : sélection économique historique indépendante des gels V6.3. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = v => typeof v === 'number' && Number.isFinite(v)
    ? new Intl.NumberFormat('fr-FR',{maximumFractionDigits:2}).format(v):'—';
  const pct = v => typeof v === 'number' && Number.isFinite(v)
    ? (v > 0 ? '+' : '') + fmt(v) + ' %' : '—';
  const interval = v => Array.isArray(v) && v.length === 2
    ? pct(v[0]) + ' à ' + pct(v[1]) : 'Non disponible';
  let data = null;
  let loading = false;
  let page = 0;
  const PAGE_SIZE = 30;

  function currentRows() {
    if (!data) return [];
    const mode = $('v64Top').value;
    const market = $('v64Market').value;
    const byId = new Map(data.candidates.map(x => [x.id,x]));
    const ids = mode === 'all' ? data.candidates.map(x => x.id) : (data.tops?.[mode] || []);
    return ids.map(id => byId.get(id)).filter(x => x && (!market || x.market === market));
  }

  function metricClass(v) {return v > 0 ? 'v64-positive' : 'v64-muted';}
  function card(x, i) {
    const rules = (x.criteria || []).map(c => `${c.dimension} : ${c.value}`).join(' · ');
    return `<article class="v64-card"><header><strong>#${i + 1} · ${esc(x.market)} · ${esc(x.book)}</strong><span>${esc(x.horizon)} · ${esc(x.selection)}</span></header>
      <p>${esc(rules)}</p>
      <div class="v64-stats"><div><small>ROI historique</small><b class="${metricClass(x.roi_pct)}">${pct(x.roi_pct)}</b><small>IC95 ${interval(x.roi_ci95)}</small></div>
      <div><small>CLV historique</small><b class="${metricClass(x.clv_mean_pct)}">${pct(x.clv_mean_pct)}</b><small>N CLV ${fmt(x.clv_n)}</small></div>
      <div><small>Matchs / jours</small><b>${fmt(x.unique_matches)} / ${fmt(x.distinct_days)}</b><small>Moitié 1 : ${pct(x.first_half_roi_pct)} · moitié 2 : ${pct(x.second_half_roi_pct)}</small></div>
      <div><small>Score économique</small><b>${fmt(x.score)} / 100</b><small>Score robustesse : ${fmt(x.robustness_score)}</small></div></div>
      <small>Découverte ${esc(x.historical_start)} → ${esc(x.historical_end)} · IC, CLV et ROI historiques non prospectifs</small></article>`;
  }

  function render() {
    if (!data) return;
    const rows = currentRows();
    const maxPage = Math.max(0, Math.ceil(rows.length / PAGE_SIZE) - 1);
    page = Math.min(page, maxPage);
    const start = page * PAGE_SIZE;
    $('v64Count').textContent = `${fmt(rows.length)} hypothèses · ${fmt(data.selected_count)} dans la sélection complète · instantané ${esc(data.as_of_utc)} · pas une validation prospective`;
    $('v64List').innerHTML = rows.slice(start, start + PAGE_SIZE).map((x,i)=>card(x,start+i)).join('')
      || '<p>Aucune hypothèse pour ce filtre.</p>';
    $('v64Page').textContent = `${page + 1} / ${maxPage + 1}`;
    $('v64Prev').disabled = page === 0;
    $('v64Next').disabled = page >= maxPage;
  }

  async function load() {
    if (loading || data) return;
    loading = true;
    try {
      const response = await fetch('./live/economic_v64.json?t=' + Date.now(), {cache:'no-store'});
      if (!response.ok) {
        if (response.status === 404) throw new Error('Sélection non encore publiée. Lancer le workflow V6.4 en prévisualisation, puis publier après vérification.');
        throw new Error(`HTTP ${response.status}`);
      }
      const x = await response.json();
      if (x.policy_version !== 'tennis-edge-economic-v64-1' || !Array.isArray(x.candidates) || !x.tops) {
        throw new Error('Rapport V6.4 incomplet ou de version incorrecte');
      }
      data = x;
      $('v64Notice').textContent = `Sélection V6.4 · ${fmt(x.selected_count)} ROI+ ET CLV+ · ${fmt(x.source_market_count)} segments explorés · match ${fmt(x.by_market?.match || 0)}, set 1 ${fmt(x.by_market?.set1 || 0)}, set 2 ${fmt(x.by_market?.set2 || 0)}. Source ${String(x.source_snapshot_sha256||'').slice(0,14)}. Critères : ≥80 matchs, ≥20 jours, ≥50 observations CLV.`;
      $('v64Metrics').innerHTML = [
        ['Éligibles sélectionnées',x.selected_count],
        ['Match',x.by_market?.match || 0],
        ['Set 1',x.by_market?.set1 || 0],
        ['Set 2',x.by_market?.set2 || 0]
      ].map(([label,val])=>`<div class="kpi"><small>${esc(label)}</small><b>${fmt(val)}</b></div>`).join('');
      render();
    } catch(e) {
      $('v64Notice').textContent = `V6.4 : ${String(e.message || e)}`;
    } finally { loading = false; }
  }

  if (typeof document !== 'undefined') {
    document.querySelectorAll('.tab[data-tab="v64Economic"]').forEach(tab => tab.addEventListener('click', load));
    for (const id of ['v64Top','v64Market']) $(id)?.addEventListener('change',()=>{page=0;render();});
    $('v64Prev')?.addEventListener('click',()=>{page=Math.max(0,page-1);render();});
    $('v64Next')?.addEventListener('click',()=>{page++;render();});
  }
  if (typeof module !== 'undefined') module.exports = {renderTopIds: (report,mode) => mode==='all' ? report.candidates.map(x=>x.id) : report.tops[mode]};
})();
