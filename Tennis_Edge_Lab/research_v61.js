/* Affichage mobile paginé du registre exploratoire et de l'audit V6.1. */
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
  const interval = predicate => {
    if (predicate.interval) return predicate.value;
    return `${predicate.dimension} = ${predicate.value}`;
  };
  const statusClass = value => value === 'signal prospectif à auditer'
    ? 'prospective-signal' : value === 'non confirmé'
      ? 'prospective-unconfirmed' : 'exploratory-observation';
  const reasonList = segment => (segment.rejection_reasons || []).length
    ? segment.rejection_reasons : ['aucun'];
  let audit = null;
  let frozen = null;
  let manifest = null;
  let archivePage = null;
  let selectedPage = 0;
  let candidatePage = 0;
  const candidatePageSize = 20;
  let requestNumber = 0;
  let initialized = false;

  // Étape 4 stockage (16/10/2026) : le rapport V6.1 est publié compressé
  // (.json.gz, 2,8 Mo au lieu de 42 Mo). Lecture du .gz si le navigateur sait
  // décompresser, sinon repli sur le .json — même principe que l'Explorateur.
  async function fetchJSONGz(url) {
    if (typeof DecompressionStream !== 'undefined') {
      try {
        const r = await fetch(`${url}.gz?t=${Date.now()}`, { cache: 'no-store' });
        if (r.ok && r.body) {
          const text = await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text();
          return JSON.parse(text);
        }
      } catch { /* repli JSON simple */ }
    }
    return fetchJSON(url);
  }

  async function fetchJSON(url) {
    const response = await fetch(`${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}`, {
      cache: 'no-store',
    });
    if (!response.ok) throw new Error(`${url}: HTTP ${response.status}`);
    return response.json();
  }

  function fillSelect(id, values) {
    const select = $(id);
    if (!select) return;
    const first = select.options[0];
    select.replaceChildren(first);
    values.forEach(value => {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = value;
      select.append(option);
    });
  }

  function renderCounters() {
    const counts = audit.rejection_counts_multiple_causes || {};
    const labels = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    const max = Math.max(1, ...labels.map(([, count]) => count));
    $('v61AuditCharts').innerHTML = `<h3>Motifs cumulés — plusieurs causes par segment</h3><div class="audit-bars" role="img" aria-label="Répartition des motifs de rejet">${labels.map(([reason, count]) => `<div class="audit-bar"><span>${esc(reason)}</span><span class="audit-bar-track"><i style="width:${Math.max(2, count / max * 100)}%"></i></span><b>${nf(count)}</b></div>`).join('') || '<p class="mini">Aucun motif publié.</p>'}</div>`;
    $('v61AuditKpis').innerHTML = [
      ['Segments complets', audit.segment_count],
      ['Tests nominaux valides', audit.tested_segments],
      ['Motifs cumulés', Object.values(counts).reduce((sum, value) => sum + value, 0)],
      ['Empreinte des sources', (audit.source_hash_sha256 || '').slice(0, 16)],
    ].map(([label, value]) => `<div class="kpi"><small>${esc(label)}</small><b>${label === 'Empreinte des sources' ? esc(value) : nf(value)}</b></div>`).join('');
  }

  function renderExtremes(market) {
    const data = audit.markets?.[market];
    if (!data) {
      $('v61AuditExtremes').textContent = '';
      return;
    }
    const cards = (title, list, negative) => `<section class="v61-extreme"><h3>${title}</h3><ul>${(list || []).map(item => `<li><b>${esc(item.book)}</b> · ${esc(item.horizon)} · ${esc(item.circuit)} · N ${nf(item.n)} · <b>Holm CLV Pinnacle ${nf(item.p_holm_clv_pin)}</b> · CLV Pinnacle ${pct(item.clv_pin_mean_pct)} · ROI (secondaire) ${pct(item.roi_pct)} · ${negative ? 'lecture historique négative' : 'lecture historique, non validée'}</li>`).join('') || '<li>Aucun segment disponible</li>'}</ul></section>`;
    $('v61AuditExtremes').innerHTML = `<div class="v61-extremes">${cards('CLV Pinnacle positif — tri par p (descriptif)', data.best_positive, false)}${cards('CLV Pinnacle négatif (descriptif)', data.worst_negative, true)}</div>`;
  }

  function setFilterOptions() {
    fillSelect('v61MarketFilter', ['match', 'set1', 'set2']);
    fillSelect('v61BookFilter', Object.keys(audit.rejection_counts_by_bookmaker || {}).sort());
    fillSelect('v61CircuitFilter', Object.keys(audit.rejection_counts_by_circuit || {}).sort());
    fillSelect('v61HorizonFilter', Object.keys(audit.rejection_counts_by_horizon || {}).sort());
    fillSelect('v61ReasonFilter', Object.keys(audit.rejection_counts_by_primary_reason || {})
      .filter(value => value !== 'aucun').sort());
    $('v61MarketFilter').value = 'match';
  }

  function filteredRows() {
    if (!archivePage) return [];
    const market = $('v61MarketFilter').value;
    const book = $('v61BookFilter').value;
    const circuit = $('v61CircuitFilter').value;
    const horizon = $('v61HorizonFilter').value;
    const minimum = Number($('v61SampleFilter').value || 0);
    const reason = $('v61ReasonFilter').value;
    return archivePage.segments.filter(item =>
      item.market === market
      && (!book || item.book === book)
      && (!circuit || item.circuit === circuit)
      && (!horizon || item.horizon === horizon)
      && item.unique_matches >= minimum
      && (!reason || item.primary_rejection_reason === reason));
  }

  function renderTable() {
    const rows = filteredRows();
    $('v61AuditRows').innerHTML = rows.map(item => {
      const rules = (item.predicates || []).map(predicate => esc(interval(predicate))).join('<br>');
      const ci = item.roi_ci95 ? `${pct(item.roi_ci95[0])} à ${pct(item.roi_ci95[1])}` : '—';
      const reasons = reasonList(item).map(reason => `<span class="tag">${esc(reason)}</span>`).join(' ');
      return `<tr><td>${esc(item.market)}<div class="detail ${item.roi_pct > 0 ? 'historical-positive' : item.roi_pct < 0 ? 'historical-negative' : ''}">historique</div></td><td><b>${esc(item.book)}</b><div class="detail">${esc(item.circuit)} · ${esc(item.horizon)} · ${esc(item.selection)}</div></td><td class="small-rule">${rules || 'Tous segments'}</td><td class="num">${nf(item.unique_matches)} / ${nf(item.distinct_days)}</td><td class="num">${nf(item.wins)} · ${nf(item.mean_odds)}</td><td class="num">${pct(item.roi_pct)}<div class="detail">IC95 ${ci}</div></td><td class="num">${nf(item.pnl_units)}<div class="detail">CLV Pinnacle ${pct(item.clv_pin_mean_pct)} · CLV book (secondaire) ${pct(item.clv_mean_pct)}</div></td><td class="num"><b>Holm CLV Pinnacle ${nf(item.p_holm_clv_pin)}</b><div class="detail">p ROI ${nf(item.p_nominal)} · Holm ROI ${nf(item.p_holm)}</div></td><td>${item.primary_rejection_reason ? `<b>${esc(item.primary_rejection_reason)}</b><br>` : ''}${reasons}</td></tr>`;
    }).join('');
    const info = manifest?.markets?.[$('v61MarketFilter').value];
    $('v61PageIndicator').textContent = `Archive ${selectedPage + 1}/${Math.max(1, info?.pages?.length || 0)} · ${rows.length} lignes filtrées sur ${archivePage?.segments?.length || 0} dans cette page`;
    $('v61Previous').disabled = selectedPage <= 0;
    $('v61Next').disabled = !info || selectedPage + 1 >= info.pages.length;
  }

  async function loadArchivePage() {
    if (!manifest) return;
    const market = $('v61MarketFilter').value;
    const entry = manifest.markets?.[market];
    if (!entry) throw new Error(`Archive absente pour le marché ${market}`);
    if (entry.segment_count === 0 && Array.isArray(entry.pages) && entry.pages.length === 0) {
      const currentRequest = ++requestNumber;
      archivePage = { schema_version: 1, market, page: 1, segments: [] };
      $('v61CompressedArchive').href = entry.compressed_jsonl.replace(
        /^Tennis_Edge_Lab\//, './',
      );
      $('v61ArchiveInfo').textContent =
        `Empreinte sources ${manifest.source_snapshot_sha256} · 0 segment · export intégral compressé (${entry.compressed_sha256})`;
      if (currentRequest === requestNumber) {
        renderExtremes(market);
        renderTable();
      }
      return;
    }
    const pageUrl = entry.pages[selectedPage]?.replace(/^Tennis_Edge_Lab\//, './');
    if (!pageUrl) throw new Error(`Page ${selectedPage + 1} absente pour ${market}`);
    const currentRequest = ++requestNumber;
    const page = await fetchJSON(pageUrl);
    if (currentRequest !== requestNumber) return;
    if (page.schema_version !== 1 || page.market !== market || !Array.isArray(page.segments)) {
      throw new Error('Format de page d’archive incompatible');
    }
    archivePage = page;
    $('v61CompressedArchive').href = entry.compressed_jsonl.replace(
      /^Tennis_Edge_Lab\//, './',
    );
    $('v61ArchiveInfo').textContent = `Empreinte sources ${manifest.source_snapshot_sha256} · ${entry.segment_count} segments · export intégral compressé (${entry.compressed_sha256})`;
    renderExtremes(market);
    renderTable();
  }

  function renderCandidates() {
    if (!frozen) throw new Error('Rapport prospectif V6.1 absent');
    const all = frozen.candidates || [];
    const pages = Math.max(1, Math.ceil(all.length / candidatePageSize));
    candidatePage = Math.min(candidatePage, pages - 1);
    $('v61CandidatesNotice').textContent = `${nf(frozen.total_frozen)} pistes gelées · politique ${frozen.policy_version} · échéances J+${(frozen.planned_checkpoints_days || []).join(', J+')} · empreinte du registre ${frozen.ledger_tip || 'non disponible'}`;
    $('v61CandidateCards').innerHTML = all.slice(
      candidatePage * candidatePageSize, (candidatePage + 1) * candidatePageSize,
    ).map(item => {
      const checkpoints = (item.checkpoints || []).map(check => `<div class="prospective-check"><b>Échéance UTC ${esc(check.checkpoint_utc)}</b><span>${nf(check.unique_matches)} matchs · ${nf(check.distinct_days)} jours</span><span>ROI ${pct(check.roi_pct)} · IC95 ${check.roi_ci95 ? `${pct(check.roi_ci95[0])} à ${pct(check.roi_ci95[1])}` : '—'}</span><span>P&amp;L ${nf(check.pnl_units)} · CLV Pinnacle ${pct(check.clv_pin_mean_pct)} · CLV book (secondaire) ${pct(check.clv_mean_pct)} · Holm ${nf(check.p_holm)}</span><span class="${statusClass(check.state)}">${esc(check.state)}</span></div>`).join('');
      const rules = (item.predicates || []).map(predicate => `<li>${esc(interval(predicate))}</li>`).join('');
      const circuit = item.criteria?.find(predicate => predicate.dimension === 'circuit')?.value || 'tous circuits';
      const historical = item.historical_context || {};
      return `<article class="candidate v61-frozen-card"><div class="v61-state ${statusClass(item.state)}">${esc(item.state)}</div><h3>${esc(item.market)} · ${esc(item.book)} · ${esc(circuit)} · ${esc(item.horizon)} · ${esc(item.selection)}</h3><ul class="v61-rules">${rules}</ul><p class="detail">Gel UTC ${esc(item.freeze_date_utc)} · admissible à partir du ${esc(item.eligible_after_utc)} · période de découverte ${esc(item.discovery_period?.start)} → ${esc(item.discovery_period?.end)}</p><p class="detail">Signature ${esc(item.candidate_id)} · commit ${esc(item.source_commit)} · source ${esc(item.source_snapshot_sha256)}</p><div class="historical-context"><b>Observation historique — non prospective :</b> ROI ${pct(historical.roi_pct)} · IC95 ${historical.roi_ci95 ? `${pct(historical.roi_ci95[0])} à ${pct(historical.roi_ci95[1])}` : '—'} · CLV book (secondaire) ${pct(historical.clv_mean_pct)} · P&amp;L ${nf(historical.pnl_units)}. Cette observation n’entre jamais dans les résultats futurs.</div><h4>Validation prospective indépendante</h4>${checkpoints || '<p class="exploratory-observation">Observation exploratoire · première échéance préenregistrée en attente.</p>'}</article>`;
    }).join('') || '<p>Aucune piste exploratoire gelée admissible.</p>';
    $('v61CandidatePage').textContent = `${candidatePage + 1}/${pages}`;
    $('v61CandidatePrevious').disabled = candidatePage === 0;
    $('v61CandidateNext').disabled = candidatePage + 1 >= pages;
  }

  async function initialize() {
    if (initialized) return;
    initialized = true;
    try {
      [audit, frozen] = await Promise.all([
        fetchJSON('./live/bookmakers_sets_audit.json'),
        fetchJSONGz('./live/candidate_watch_v61_prospective.json'),
      ]);
      if (audit.schema_version !== 1 || !Number.isInteger(audit.segment_count)) {
        throw new Error('Rapport d’audit V6.1 invalide');
      }
      renderCounters();
      setFilterOptions();
      const manifestUrl = `./${audit.archive.manifest}`;
      manifest = await fetchJSON(manifestUrl);
      if (manifest.source_snapshot_sha256 !== audit.archive.source_snapshot_sha256) {
        throw new Error('Empreinte du manifeste différente du rapport synthétique');
      }
      $('v61ManifestLink').href = manifestUrl;
      $('v61AuditNotice').textContent = `Sources UTC · rapport ${audit.generated_at} · ${audit.segment_count} segments · SHA-256 ${audit.source_hash_sha256}`;
      renderCandidates();
      await loadArchivePage();
    } catch (error) {
      const message = String(error?.message || error);
      $('v61AuditNotice').textContent = `Audit V6.1 indisponible : ${message}`;
      $('v61CandidatesNotice').textContent = `Registre exploratoire V6.1 indisponible : ${message}`;
    }
  }

  document.querySelectorAll('.tab[data-tab="v61Audit"], .tab[data-tab="v61Candidates"]')
    .forEach(button => button.addEventListener('click', initialize));
  ['v61MarketFilter', 'v61BookFilter', 'v61CircuitFilter', 'v61HorizonFilter',
    'v61SampleFilter', 'v61ReasonFilter'].forEach(id => {
    $(id)?.addEventListener('change', () => {
      if (id === 'v61MarketFilter') {
        selectedPage = 0;
        archivePage = null;
        loadArchivePage().catch(error => {
          $('v61AuditNotice').textContent = `Page d’archive indisponible : ${String(error.message || error)}`;
        });
      } else if (archivePage) renderTable();
    });
  });
  $('v61Previous')?.addEventListener('click', () => {
    if (selectedPage > 0) {
      selectedPage -= 1;
      loadArchivePage().catch(error => {
        $('v61AuditNotice').textContent = `Page d’archive indisponible : ${String(error.message || error)}`;
      });
    }
  });
  $('v61Next')?.addEventListener('click', () => {
    const pages = manifest?.markets?.[$('v61MarketFilter').value]?.pages || [];
    if (selectedPage + 1 < pages.length) {
      selectedPage += 1;
      loadArchivePage().catch(error => {
        $('v61AuditNotice').textContent = `Page d’archive indisponible : ${String(error.message || error)}`;
      });
    }
  });
  $('v61CandidatePrevious')?.addEventListener('click', () => {
    if (candidatePage > 0) {
      candidatePage -= 1;
      renderCandidates();
    }
  });
  $('v61CandidateNext')?.addEventListener('click', () => {
    if (frozen && (candidatePage + 1) * candidatePageSize < (frozen.candidates || []).length) {
      candidatePage += 1;
      renderCandidates();
    }
  });
})();
