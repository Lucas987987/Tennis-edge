/* Suivi transparent des sélections et validations prospectives V6.3. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
  const nf = value => value === null || value === undefined
    ? '—' : new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(value);
  const pct = value => value === null || value === undefined
    ? '—' : `${value > 0 ? '+' : ''}${nf(value)} %`;
  const formatInterval = value => Array.isArray(value) && value.length === 2
    ? `${pct(value[0])} à ${pct(value[1])}` : '—';
  const formatDate = value => value ? esc(String(value).slice(0, 10)) : '—';
  let loading = false;
  let loaded = false;

  async function loadReport() {
    if (loading || loaded) return;
    loading = true;
    try {
      const response = await fetch('./live/candidate_watch_v62_prospective.json?t=' + Date.now(), {
        cache: 'no-store',
      });
      if (!response.ok) throw new Error(`Rapport V6.3 : HTTP ${response.status}`);
      const report = await response.json();
      if (['not_published', 'missing', 'pending', 'error'].includes(report.status)) {
        $('v63Notice').textContent = 'Suivi V6.3 non publié : aucune hypothèse officielle n\'est affichée.';
        return;
      }
      if (!Array.isArray(report.candidates) || !report.active_by_market) {
        throw new Error('Schéma de suivi V6.3 invalide');
      }
      render(report);
      loaded = true;
    } catch (error) {
      $('v63Notice').textContent = `Suivi V6.3 indisponible : ${String(error?.message || error)}`;
    } finally {
      loading = false;
    }
  }

  function render(report) {
    const candidates = report.candidates;
    const active = candidates.filter(item => item.lifecycle_state === 'active').length;
    const archived = candidates.filter(item => item.lifecycle_state === 'archivée').length;
    const duplicateTotal = (report.redundant_exploratory_count || 0)
      + (report.candidate_redundant_count || 0);
    $('v63Metrics').innerHTML = [
      ['Pistes découvertes', report.exploratory_inventory_count],
      ['Redondances écartées', duplicateTotal],
      ['Actives · match', report.active_by_market.match || 0],
      ['Actives · set 1', report.active_by_market.set1 || 0],
      ['Actives · set 2', report.active_by_market.set2 || 0],
      ['Terminées · archivées', report.completed_and_archived ?? archived],
    ].map(([label, value]) =>
      `<div class="kpi"><small>${esc(label)}</small><b>${nf(value)}</b></div>`,
    ).join('');

    const ordered = [...candidates].sort((a, b) =>
      (a.lifecycle_state === 'active' ? 0 : 1) - (b.lifecycle_state === 'active' ? 0 : 1)
      || String(a.market).localeCompare(String(b.market))
      || String(b.freeze_date_utc).localeCompare(String(a.freeze_date_utc))
      || String(a.candidate_id).localeCompare(String(b.candidate_id)));
    $('v63Rows').innerHTML = ordered.map(item => {
      const checks = item.checkpoints || [];
      const check = checks.length ? checks[checks.length - 1] : null;
      const criteria = (item.criteria || []).map(rule =>
        `${rule.dimension} ${rule.operator || 'eq'} ${rule.value}`,
      ).join(' · ');
      const evaluatedEnd = check?.cutoff_exclusive_utc || report.evaluated_future_period?.latest_cutoff_utc;
      const source = item.source_commit
        ? `${String(item.source_commit).slice(0, 12)} · SHA ${String(item.source_snapshot_sha256 || '').slice(0, 12)}`
        : String(item.source_snapshot_sha256 || '');
      return `<tr>
        <td>${esc(item.market)}<div class="detail">${esc(item.book)} · ${esc(item.horizon)} · ${esc(item.selection)}</div></td>
        <td>${esc(criteria || '—')}</td>
        <td>${esc(item.lifecycle_state || '—')}<div class="detail">${esc(item.state || '—')}</div></td>
        <td>${formatDate(item.freeze_date_utc)}<div class="detail">données ${formatDate(item.discovery_period?.start)} – ${formatDate(item.discovery_period?.end)}</div></td>
        <td>${formatDate(item.eligible_after_utc)} – ${formatDate(evaluatedEnd)}</td>
        <td class="num">${pct(check?.roi_pct)}<div class="detail">IC95 ${formatInterval(check?.roi_ci95)}</div></td>
        <td class="num">${pct(check?.clv_mean_pct)}<div class="detail">IC95 ${formatInterval(check?.clv_ci95)} · N ${nf(check?.clv_n)}</div></td>
        <td>${esc(source)}</td>
      </tr>`;
    }).join('');
    $('v63Notice').textContent = [
      `Sélection V6.3 · ${active} hypothèses actives / ${report.active_limit || 60}`,
      `${archived} terminées archivées`,
      `inventaire ${report.source_snapshot_sha256 || 'source non renseignée'}`,
      `évaluation jusqu’au ${formatDate(report.evaluated_future_period?.latest_cutoff_utc)}`,
      report.warning || '',
    ].filter(Boolean).join(' · ');
  }

  document.querySelectorAll('.tab[data-tab="v63Hypotheses"]')
    .forEach(button => button.addEventListener('click', loadReport));
})();
