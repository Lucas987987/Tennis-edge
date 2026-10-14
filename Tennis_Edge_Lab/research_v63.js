/* Suivi V6.3 : ROI/CLV de découverte (descriptifs) versus vérification prospective. */
(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
  const nf = value => value === null || value === undefined || !Number.isFinite(Number(value))
    ? '—' : new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(Number(value));
  const pct = value => value === null || value === undefined || !Number.isFinite(Number(value))
    ? '—' : `${Number(value) > 0 ? '+' : ''}${nf(value)} %`;
  const formatInterval = value => Array.isArray(value) && value.length === 2
    ? `${pct(value[0])} à ${pct(value[1])}` : '—';
  const formatDate = value => value ? esc(String(value).slice(0, 10)) : '—';
  const metricClass = value => !Number.isFinite(Number(value)) || value === null || value === undefined
    ? 'neutral' : Number(value) >= 0 ? 'historical-positive' : 'historical-negative';
  let loading = false;
  let loaded = false;

  function latestCheckpoint(item) {
    const checks = item.checkpoints || [];
    return checks.length ? checks[checks.length - 1] : null;
  }

  function timeline(item, check) {
    if (check) return `${formatDate(item.eligible_after_utc)} – ${formatDate(check.cutoff_exclusive_utc)}`;
    const first = (item.scheduled_checkpoints_utc || [])[0];
    return `Début ${formatDate(item.eligible_after_utc)}<div class="detail">Premier contrôle ${formatDate(first)} · en attente</div>`;
  }

  function historicalROI(item) {
    const h = item.historical_context || {};
    return `<div class="v63-metric-caption">Historique · descriptif</div>
      <strong class="${metricClass(h.roi_pct)}">${pct(h.roi_pct)}</strong>
      <div class="detail">IC95 ${formatInterval(h.roi_ci95)}</div>`;
  }

  function historicalCLV(item) {
    const h = item.historical_context || {};
    return `<div class="v63-metric-caption">Historique · descriptif</div>
      <strong class="${metricClass(h.clv_mean_pct)}">${pct(h.clv_mean_pct)}</strong>
      <div class="detail">N CLV ${nf(h.clv_n)} · IC95 non fourni</div>`;
  }

  function futureROI(item, check) {
    return `<div class="v63-metric-caption">Prospectif · contrôle préenregistré</div>
      <strong>${check ? pct(check.roi_pct) : 'En attente'}</strong>
      <div class="detail">${check ? `IC95 ${formatInterval(check.roi_ci95)}` : `J+30 : ${formatDate(item.scheduled_checkpoints_utc?.[0])}`}</div>`;
  }

  function futureCLV(item, check) {
    return `<div class="v63-metric-caption">Prospectif · contrôle préenregistré</div>
      <strong>${check ? pct(check.clv_mean_pct) : 'En attente'}</strong>
      <div class="detail">${check ? `IC95 ${formatInterval(check.clv_ci95)} · N ${nf(check.clv_n)}` : `J+30 : ${formatDate(item.scheduled_checkpoints_utc?.[0])}`}</div>`;
  }

  function orderedCandidates(report) {
    return [...report.candidates].sort((a, b) =>
      (a.lifecycle_state === 'active' ? 0 : 1) - (b.lifecycle_state === 'active' ? 0 : 1)
      || String(a.market).localeCompare(String(b.market))
      || String(b.freeze_date_utc).localeCompare(String(a.freeze_date_utc))
      || String(a.candidate_id).localeCompare(String(b.candidate_id)));
  }

  function render(report) {
    const candidates = report.candidates;
    const active = candidates.filter(item => item.lifecycle_state === 'active').length;
    const archived = candidates.filter(item => item.lifecycle_state === 'archivée').length;
    const duplicateTotal = (report.redundant_exploratory_count || 0)
      + (report.candidate_redundant_count || 0);
    const historicalROIAvailable = candidates.filter(item => Number.isFinite(item.historical_context?.roi_pct)).length;
    const historicalCLVAvailable = candidates.filter(item => Number.isFinite(item.historical_context?.clv_mean_pct)).length;
    $('v63Metrics').innerHTML = [
      ['Pistes découvertes', report.exploratory_inventory_count],
      ['Redondances écartées', duplicateTotal],
      ['Actives · match', report.active_by_market.match || 0],
      ['Actives · set 1', report.active_by_market.set1 || 0],
      ['Actives · set 2', report.active_by_market.set2 || 0],
      ['Terminées · archivées', report.completed_and_archived ?? archived],
      ['ROI historiques disponibles', historicalROIAvailable],
      ['CLV historiques disponibles', historicalCLVAvailable],
    ].map(([label, value]) =>
      `<div class="kpi"><small>${esc(label)}</small><b>${nf(value)}</b></div>`,
    ).join('');

    const ordered = orderedCandidates(report);
    $('v63Rows').innerHTML = ordered.map(item => {
      const check = latestCheckpoint(item);
      const criteria = (item.criteria || []).map(rule =>
        `${rule.dimension} ${rule.operator || 'eq'} ${rule.value}`,
      ).join(' · ');
      const source = item.source_commit
        ? `${String(item.source_commit).slice(0, 12)} · SHA ${String(item.source_snapshot_sha256 || '').slice(0, 12)}`
        : String(item.source_snapshot_sha256 || '');
      return `<tr>
        <td>${esc(item.market)}<div class="detail">${esc(item.book)} · ${esc(item.horizon)} · ${esc(item.selection)}</div></td>
        <td>${esc(criteria || '—')}</td>
        <td>${esc(item.lifecycle_state || '—')}<div class="detail">${esc(item.state || '—')}</div></td>
        <td>${formatDate(item.freeze_date_utc)}<div class="detail">données ${formatDate(item.discovery_period?.start)} – ${formatDate(item.discovery_period?.end)}</div></td>
        <td>${timeline(item, check)}</td>
        <td class="num">${historicalROI(item)}<div class="v63-prospective">${futureROI(item, check)}</div></td>
        <td class="num">${historicalCLV(item)}<div class="v63-prospective">${futureCLV(item, check)}</div></td>
        <td>${esc(source)}</td>
      </tr>`;
    }).join('');

    const mobile = $('v63Cards');
    if (mobile) mobile.innerHTML = ordered.map(item => {
      const check = latestCheckpoint(item);
      const criteria = (item.criteria || []).map(rule =>
        `${rule.dimension} ${rule.operator || 'eq'} ${rule.value}`).join(' · ');
      return `<article class="v63-card">
        <div class="v63-card-title"><b>${esc(item.market)} · ${esc(item.book)}</b><span>${esc(item.lifecycle_state || '—')}</span></div>
        <p class="detail">${esc(item.horizon)} · ${esc(item.selection)} · ${esc(criteria || '—')}</p>
        <p class="detail">Gel ${formatDate(item.freeze_date_utc)} · ${timeline(item, check)}</p>
        <div class="v63-card-metrics"><div>${historicalROI(item)}</div><div>${historicalCLV(item)}</div></div>
        <div class="v63-card-metrics v63-prospective"><div>${futureROI(item, check)}</div><div>${futureCLV(item, check)}</div></div>
        <p class="detail">Identifiant ${esc(String(item.candidate_id || '').slice(0, 16))}</p>
      </article>`;
    }).join('');

    $('v63Notice').textContent = [
      `Sélection V6.3 · ${active} hypothèses actives / ${report.active_limit || 60}`,
      `${archived} terminées archivées`,
      `ROI historiques ${historicalROIAvailable}/${candidates.length} · CLV historiques ${historicalCLVAvailable}/${candidates.length}`,
      `inventaire ${report.source_snapshot_sha256 || 'source non renseignée'}`,
      `évaluation mise à jour ${formatDate(report.evaluated_future_period?.latest_cutoff_utc)}`,
      report.warning || '',
    ].filter(Boolean).join(' · ');
  }

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

  document.querySelectorAll('.tab[data-tab="v63Hypotheses"]')
    .forEach(button => button.addEventListener('click', loadReport));
})();
