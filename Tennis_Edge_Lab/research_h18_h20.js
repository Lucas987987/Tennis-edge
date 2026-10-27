/* Tennis Edge Lab — résultats H18, H19 et H20, lecture seule.
 * H18 : données publiques de réconciliation. H19/H20 : coffre privé via prive.js.
 * Les populations et les périodes de découverte ne sont jamais additionnées au prospectif.
 */
(() => {
  'use strict';
  const $ = id => (typeof document !== 'undefined' ? document.getElementById(id) : null);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const nf = (v, d = 2) => v === null || v === undefined || Number.isNaN(Number(v)) ? '—'
    : new Intl.NumberFormat('fr-FR', { maximumFractionDigits: d }).format(Number(v));
  const pct = v => v === null || v === undefined ? '—' : `${Number(v) > 0 ? '+' : ''}${nf(v)} %`;
  const cls = v => Number(v) > 0 ? 'good' : Number(v) < 0 ? 'bad' : 'neutral';
  const ci = a => Array.isArray(a) && a.length === 2 ? `${pct(a[0])} à ${pct(a[1])}` : '—';

  function stats(items) {
    return `<div class="stats">${items.map(([label, value, detail, valueClass]) => `<div><small>${esc(label)}</small><strong class="${esc(valueClass || '')}">${value}</strong>${detail ? `<small>${detail}</small>` : ''}</div>`).join('')}</div>`;
  }

  function blocH18(titre, m, worker = false) {
    m = m || {};
    const clv = worker ? m.clv_pin_moyen : m.clv_pin;
    return `<section class="h1820-source"><h4>${esc(titre)}</h4>${stats([
      ['Paris réglés', nf(m.n, 0), m.gagnes !== undefined ? `${nf(m.gagnes, 0)} gagnés` : ''],
      ['CLV Pinnacle', pct(clv), m.clv_n !== undefined ? `n = ${nf(m.clv_n, 0)}` : '', cls(clv)],
      ['ROI (secondaire)', pct(m.roi), m.taux !== undefined ? `${nf(m.taux, 1)} % gagnés` : '', cls(m.roi)],
    ])}${m.verdict ? `<p class="detail">${esc(m.verdict)}</p>` : ''}</section>`;
  }

  function renderH18(doc) {
    const h = doc?.hypotheses?.H18;
    if (!h) return '<p class="notice warn">H18 n’est pas présente dans la réconciliation publiée.</p>';
    return `<article class="candidate h1820-card"><div class="h1820-head"><div><h3>H18 — ${esc(h.regle || 'Intersection H16 et H17')}</h3><p class="detail">Gelée le ${esc(h.gel || '—')} · source publique</p></div><span class="chip">Lecture seule</span></div>
      <p class="notice"><b>Populations distinctes.</b> Le suivi direct, le Worker et la reconstruction ne s’additionnent pas. La reconstruction est un contrôle, pas le verdict officiel.</p>
      ${blocH18('Suivi officiel direct', h.suivi_officiel)}
      ${blocH18('Worker — hors échantillon', h.worker?.out_of_sample, true)}
      ${blocH18('Reconstruction — contrôle historique', h.reconstruction)}
      <p class="mini"><a href="./live/reconciliation_hypotheses.json" download>Exporter la réconciliation H18</a></p></article>`;
  }

  function statsProspectifH19(p) {
    p = p || {};
    return stats([
      ['Décisions', nf(p.n, 0), `${nf(p.regles, 0)} réglées`],
      ['CLV Pinnacle', pct(p.clv?.mean), `${ci(p.clv?.ci)} · n = ${nf(p.clv?.n, 0)}`, cls(p.clv?.mean)],
      ['ROI (secondaire)', pct(p.roi?.mean), ci(p.roi?.ci), cls(p.roi?.mean)],
    ]);
  }

  function statsProspectifH20(p) {
    p = p || {};
    return stats([
      ['Décisions', nf(p.n, 0), `${nf(p.regles, 0)} réglées`],
      ['CLV Pinnacle', pct(p.clv_moy_pct), `${ci(p.clv_ic95)} · n = ${nf(p.clv_n, 0)}`, cls(p.clv_moy_pct)],
      ['ROI (secondaire)', pct(p.roi_pct), `${nf(p.gagnes, 0)} gagnés`, cls(p.roi_pct)],
    ]);
  }

  function derniers(rows, code) {
    rows = Array.isArray(rows) ? rows.slice(-10).reverse() : [];
    if (!rows.length) return '<p class="mini">Aucune décision prospective détaillée pour le moment.</p>';
    return `<details class="h1820-details"><summary>Voir ${rows.length === 1 ? 'la dernière décision' : `les ${rows.length} dernières décisions`}</summary><div class="table-wrap"><table><thead><tr><th>Date · joueur</th><th>Horizon · book</th><th class="num">CLV</th><th class="num">Résultat</th></tr></thead><tbody>${rows.map(r => {
      const clv = code === 'H19' && Number.isFinite(Number(r.clv)) ? 100 * Number(r.clv) : r.clv_jouable;
      const roi = code === 'H19' && Number.isFinite(Number(r.pnl)) ? 100 * Number(r.pnl) : null;
      const resultat = r.gagne === 1 || r.gagne === true ? 'Gagné' : r.gagne === 0 || r.gagne === false ? 'Perdu' : roi !== null ? pct(roi) : '—';
      return `<tr><td>${esc(r.date || '—')}<div class="detail">${esc(r.joueur || r.match || r.uid || '—')}</div></td><td>${esc(r.horizon || '—')}<div class="detail">${esc(r.book || r.book_jouable || '—')}</div></td><td class="num">${pct(clv)}</td><td class="num">${esc(resultat)}</td></tr>`;
    }).join('')}</tbody></table></div></details>`;
  }

  function renderH19(doc) {
    const h = doc?.h19, p = h?.prospectif, r = h?.regle || {};
    if (!p) throw new Error('structure H19 absente');
    return `<article class="candidate h1820-card"><div class="h1820-head"><div><h3>H19 — ${esc(r.nom || 'Valeur contre Pinnacle juste')}</h3><p class="detail">Gelée le ${esc(r.gele_le || '—')} · coffre privé</p></div><span class="chip">Prospectif</span></div>
      <p class="notice"><b>${esc(p.verdict || 'En cours')}</b><br>Mesure principale : CLV Pinnacle. Le ROI reste secondaire et ne valide pas l’hypothèse.</p>
      ${statsProspectifH19(p)}${derniers(p.derniers, 'H19')}
      <details class="h1820-details"><summary>Période de découverte (aucune valeur de preuve)</summary>${statsProspectifH19(h.retrospectif)}<p class="detail">${esc(h.retrospectif?.avertissement || '')}</p></details></article>`;
  }

  function renderH20(doc) {
    const p = doc?.prospectif, r = doc?.regle || {};
    if (!p) throw new Error('structure H20 absente');
    const d = doc?.decouverte_avant_gel;
    return `<article class="candidate h1820-card"><div class="h1820-head"><div><h3>H20 — Outsider WTA soutenu par Pinnacle</h3><p class="detail">Gelée le ${esc(r.gele_le || '—')} · coffre privé</p></div><span class="chip">Prospectif</span></div>
      <p class="notice"><b>${esc(p.verdict || 'En cours')}</b><br>Un pari par match et joueur, au premier horizon admissible. La CLV Pinnacle reste la mesure principale.</p>
      ${statsProspectifH20(p)}${derniers(p.derniers, 'H20')}
      <details class="h1820-details"><summary>Période de découverte (aucune valeur de preuve)</summary>${statsProspectifH20(d)}<p class="detail">${esc(d?.note || '')}</p></details></article>`;
  }

  function verrouille(code, raison) {
    const prive = code !== 'H18';
    return `<article class="candidate h1820-card"><h3>${esc(code)} — résultats indisponibles</h3><p class="notice warn">${prive ? 'Coffre privé verrouillé ou rapport absent. Ouvrez une fois le Lab avec votre clé (<code>?cle=VOTRE_CLE</code>), puis revenez sur cet onglet. Aucune clé n’est incluse dans la page.' : 'Le rapport public n’a pas pu être chargé.'}</p><p class="detail">${esc(raison || '')}</p></article>`;
  }

  async function load(url) {
    const r = await fetch(`${url}?t=${Date.now()}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  async function start() {
    const host = $('h1820Body');
    if (!host) return;
    host.innerHTML = '<p class="mini">Chargement des résultats H18, H19 et H20…</p>';
    const [h18, h19, h20] = await Promise.allSettled([
      load('./live/reconciliation_hypotheses.json'), load('./live/valeur.json'), load('./live/h20.json'),
    ]);
    const rendus = [];
    try { rendus.push(h18.status === 'fulfilled' ? renderH18(h18.value) : verrouille('H18', h18.reason?.message)); }
    catch (e) { rendus.push(verrouille('H18', e.message)); }
    for (const [code, result, render] of [['H19', h19, renderH19], ['H20', h20, renderH20]]) {
      try { rendus.push(result.status === 'fulfilled' ? render(result.value) : verrouille(code, result.reason?.message)); }
      catch (e) { rendus.push(verrouille(code, e.message)); }
    }
    host.innerHTML = rendus.join('');
    const stamp = $('h1820Updated');
    if (stamp) stamp.textContent = `Actualisé à ${new Intl.DateTimeFormat('fr-FR', { hour: '2-digit', minute: '2-digit' }).format(new Date())}`;
  }

  if (typeof document !== 'undefined' && typeof module === 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
    else start();
    document.getElementById('h1820Refresh')?.addEventListener('click', start);
  }
  if (typeof module !== 'undefined') module.exports = { renderH18, renderH19, renderH20, statsProspectifH19, statsProspectifH20, start };
})();
