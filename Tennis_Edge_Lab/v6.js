/* Tennis Edge Lab V6: suivi des validations prospectives multi-marchés */
(() => {
  'use strict';

  const el = (id) => document.getElementById(id);
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[character]);
  const number = (value) => value === null || value === undefined
    ? '—' : new Intl.NumberFormat('fr-FR', { maximumFractionDigits: 2 }).format(value);
  const percent = (value) => value === null || value === undefined
    ? '—' : `${value > 0 ? '+' : ''}${number(value)} %`;
  const marketLabels = {
    match: 'Vainqueur du match',
    set1: 'Vainqueur du set 1',
    set2: 'Vainqueur du set 2',
  };

  async function load() {
    const response = await fetch(`./live/bookmakers_sets_prospective.json?v=${Date.now()}`, {
      cache: 'no-store',
    });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const report = await response.json();
    if (report.schema_version !== 1 || !Array.isArray(report.hypotheses)) {
      throw new Error('Schéma de suivi V6 absent ou incompatible');
    }
    return report;
  }

  function render(report) {
    el('v6Notice').textContent =
      `Généré le ${new Date(report.generated_at).toLocaleString('fr-FR')} · ` +
      `${report.total_frozen} hypothèse(s) gelée(s) · ` +
      `${report.tested_hypotheses} test(s) prospectif(s) corrigé(s) par Holm. ` +
      report.warning;

    const rows = report.hypotheses.map((item) => {
      const metrics = item.metrics || {};
      const ci = metrics.roi_ci95
        ? `${percent(metrics.roi_ci95[0])} à ${percent(metrics.roi_ci95[1])}` : '—';
      const clvCi = metrics.clv_ci95
        ? `${percent(metrics.clv_ci95[0])} à ${percent(metrics.clv_ci95[1])}` : '—';
      const rule = (item.criteria || [])
        .map((criterion) => `${criterion.dimension} ${criterion.operator} ${criterion.value}`)
        .join(' · ') || '—';
      return `<tr>
        <td>${esc(marketLabels[item.market] || item.market)}</td>
        <td>${esc(item.book)}</td>
        <td>${esc(item.horizon)} · ${esc(item.selection)}</td>
        <td>${esc(rule)}</td>
        <td>${esc(item.freeze_date)}<br><small>Admissible après ${esc(item.eligible_after)}</small></td>
        <td>${number(item.discovery_matches)} découverte<br>${number(metrics.n)} prospectifs / ${number(item.distinct_days)} jours</td>
        <td class="${metrics.roi_pct === null || metrics.roi_pct === undefined
          ? 'neutral' : metrics.roi_pct > 0 ? 'good' : 'bad'}">${percent(metrics.roi_pct)}<br><small>IC95 ${ci}</small></td>
        <td>${percent(metrics.clv_mean_pct)}<br><small>IC95 ${clvCi} · n=${number(metrics.clv_n)}</small></td>
        <td>${esc(item.first_prospective_date || '—')}<br>${esc(item.last_prospective_date || '—')}</td>
        <td>${number(item.p_holm)}<br><small>${esc(item.status)}</small></td>
      </tr>`;
    });
    el('v6Metrics').innerHTML = [
      ['Hypothèses gelées', report.total_frozen, 'Registre V5/V6 distinct de V4'],
      ['Tests prospectifs', report.tested_hypotheses, 'Correction familiale de Holm'],
      ['Marchés', (report.markets || []).map((market) => marketLabels[market] || market).join(' · '), 'Match, set 1 et set 2'],
      ['Unité de corrélation', 'Match', 'Un pari au plus par fixture et hypothèse'],
    ].map(([title, value, detail]) => `<div class="kpi"><small>${esc(title)}</small><b>${esc(value)}</b><small>${esc(detail)}</small></div>`).join('');

    el('v6Hypotheses').innerHTML = rows.length
      ? `<div class="table-wrap"><table><thead><tr>
          <th>Marché</th><th>Bookmaker</th><th>Horizon / sélection</th><th>Règle gelée</th><th>Gel</th>
          <th>Effectifs</th><th>ROI / IC95</th><th>CLV book (secondaire) / IC95</th><th>Période prospective</th>
          <th>p Holm / statut</th>
        </tr></thead><tbody>${rows.join('')}</tbody></table></div>`
      : '<p class="mini">Aucune hypothèse V6 gelée. Le registre est prêt; aucune piste ne satisfait actuellement les critères historiques corrigés.</p>';
  }

  load().then(render).catch((error) => {
    el('v6Notice').textContent = `Suivi prospectif V6 indisponible : ${error.message}`;
    el('v6Metrics').textContent = '';
    el('v6Hypotheses').textContent = '';
  });
})();
