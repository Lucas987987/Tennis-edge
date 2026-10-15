/* Fraîcheur et état de publication de chaque rapport du Lab. */
(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
  const LABELS = {
    ok: 'OK', ok_sans_date: 'OK (sans date)', ancien: 'Ancien', ancien_conserve: 'Ancien conservé',
    missing: 'Absent', pending: 'En attente', error: 'Erreur', not_published: 'Non publié',
  };
  const GOOD = new Set(['ok', 'ok_sans_date']);
  const HISTORICAL = new Set(['economic_v64.json', 'archive/bookmakers_sets_v61/current']);

  function age(stamp, now) {
    const time = Date.parse(stamp);
    if (Number.isNaN(time)) return '—';
    const hours = Math.max(0, (now - time) / 3600000);
    return hours < 48 ? `${hours.toFixed(1)} h` : `${(hours / 24).toFixed(1)} j`;
  }

  // L'état est recalculé avec l'heure du navigateur : une page restée ouverte ne paraît pas fraîche.
  function liveState(entry, now) {
    if (entry.state !== 'ok' || !entry.generated_at || !entry.max_age_hours) return entry.state;
    const time = Date.parse(entry.generated_at);
    return !Number.isNaN(time) && (now - time) / 3600000 > entry.max_age_hours ? 'ancien' : entry.state;
  }

  function render(host, status) {
    const now = Date.now();
    const rows = status.reports.map(entry => ({ ...entry, live: liveState(entry, now) }));
    const bad = rows.filter(entry => !GOOD.has(entry.live) && !HISTORICAL.has(entry.file));
    const lines = rows.map(entry => `<tr class="${GOOD.has(entry.live) || HISTORICAL.has(entry.file) ? '' : 'stale'}">
      <td>${esc(entry.tab)}</td><td><code>${esc(entry.file)}</code></td>
      <td><b>${esc(LABELS[entry.live] || entry.live)}</b></td>
      <td>${esc(entry.generated_at || '—')}</td><td>${entry.generated_at ? esc(age(entry.generated_at, now)) : '—'}</td>
      <td>${esc(entry.data_through || '—')}</td></tr>`).join('');
    host.className = `notice${bad.length ? ' warn' : ''}`;
    host.innerHTML = `<details${bad.length ? ' open' : ''}><summary><strong>Fraîcheur des analyses :</strong>
      ${bad.length ? `${bad.length} rapport(s) sur ${rows.length} absent(s), anciens, en attente ou en erreur` : `${rows.length} rapports à jour`}
      · publication du ${esc(status.checked_at)}</summary>
      <div class="table-wrap"><table><thead><tr><th>Onglet</th><th>Rapport</th><th>État</th><th>Généré le</th><th>Âge</th><th>Dernière donnée</th></tr></thead>
      <tbody>${lines}</tbody></table></div>
      <p class="description">Un rapport « ancien conservé » est la dernière version valide ; il n'a pas été recalculé lors de cette publication.</p>
      <p class="description"><strong>Limites connues :</strong> le suivi V6 historique (sans gel strict enregistré) peut être ancien ; le suivi exploratoire V6.1 et l’archive exhaustive V6.1 ne sont pas hébergés dans GitHub Pages. Leur absence est réelle et reste signalée, sans affecter les 60 gels V6.3. Les archives complètes sont à consulter dans les <a href="https://github.com/Lucas987987/Tennis-edge/actions/workflows/lab_autonomous.yml" target="_blank" rel="noopener noreferrer">artifacts des exécutions du Lab</a> tant qu’ils sont conservés (90 jours).</p></details>`;
  }

  async function load() {
    const host = document.getElementById('freshness');
    if (!host) return;
    try {
      const response = await fetch('./live/publication_status.json?t=' + Date.now(), { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const status = await response.json();
      if (!Array.isArray(status.reports)) throw new Error('schéma invalide');
      render(host, status);
    } catch (error) {
      host.className = 'notice warn';
      host.textContent = `Fraîcheur non vérifiable (${String(error?.message || error)}). ` +
        'Sur un serveur local brut, générez le site avec python Tennis_Edge_Lab/publish_guard.py ; les analyses affichées ne doivent pas être considérées comme fraîches.';
    }
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', load);
    else load();
  }
  if (typeof module !== 'undefined') module.exports = { liveState, age };
})();
