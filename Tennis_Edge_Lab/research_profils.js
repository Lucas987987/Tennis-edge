/* Tennis Edge Lab V6.8 — Profils automatiques des hypothèses (lecture seule). */
(() => {
  'use strict';
  const hasDoc = typeof document !== 'undefined';
  const $ = id => (hasDoc ? document.getElementById(id) : null);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const nf = (v, d = 1) => v === null || v === undefined || !Number.isFinite(v) ? '—'
    : new Intl.NumberFormat('fr-FR', { maximumFractionDigits: d, minimumFractionDigits: d }).format(Math.round(v * 10 ** d) / 10 ** d || 0);
  const pct = v => (v === null || v === undefined || !Number.isFinite(v)) ? '—' : `${v > 0.05 ? '+' : ''}${nf(v)} %`;
  const ci = a => Array.isArray(a) ? `${pct(a[0])} à ${pct(a[1])}` : '—';
  const pval = v => v === null || v === undefined ? '—' : v < 0.001 ? '< 0,001' : nf(v, 3);
  const RANK = { prouve: 0, piste: 1, aucune: 2 };

  function sentencesOf(card) {
    const out = [];
    for (const crit of card.criteres || []) for (const p of crit.phrases || []) out.push({ p, crit });
    return out.sort((a, b) => RANK[a.p.force] - RANK[b.p.force] || a.crit.p - b.crit.p);
  }

  function levelTable(crit) {
    return `<div class="table-wrap"><table class="pf-table"><thead><tr><th>${esc(crit.libelle)}</th><th class="num">n</th><th class="num">CLV Pinnacle · IC95</th><th class="num">ROI · IC95</th><th class="num">Moitiés (écart)</th></tr></thead><tbody>${crit.modalites.map(lv => `<tr><td>${esc(lv.valeur)}</td><td class="num">${lv.n}</td><td class="num">${pct(lv.clv)}<div class="detail">${ci(lv.clv_ic95)}</div></td><td class="num">${pct(lv.roi)}<div class="detail">${ci(lv.roi_ic95)} · ${lv.regles} réglés</div></td><td class="num">${lv.moities.map(pct).join(' / ')}</td></tr>`).join('')}</tbody></table></div>
      <p class="mini">Test d’hétérogénéité : p brute ${pval(crit.p)} · p Holm ${pval(crit.p_holm)}</p>`;
  }

  function card(c, i) {
    const items = sentencesOf(c);
    const best = items.length ? items[0].p.force : 'aucune';
    return `<article class="candidate pf-card pf-${best}"><h3>${esc(c.sujet)} <span class="pf-source">${esc(c.source)}</span></h3>
      <p class="detail">${c.n} alertes · CLV Pinnacle <b>${pct(c.clv)}</b> (${ci(c.clv_ic95)}) sur ${c.n_clv} · ROI (secondaire) ${pct(c.roi)} (${ci(c.roi_ic95)}) sur ${c.regles} réglées${c.periode ? ` · ${esc(c.periode[0])} → ${esc(c.periode[1])}` : ''}</p>
      ${items.length ? items.map(({ p, crit }, j) => `<details class="pf-item pf-${p.force}"><summary>${esc(p.texte)}</summary>${levelTable(crit)}${p.variante ? `<button type="button" class="pf-freeze" data-card="${i}" data-item="${j}">Préparer le gel de la variante</button><div class="pf-out" id="pf-out-${i}-${j}"></div>` : ''}</details>`).join('')
        : '<p class="mini">Trop peu de données pour un profil (moins de 15 alertes par modalité).</p>'}</article>`;
  }

  let doc = null;
  function render() {
    const host = $('profilsBody'); if (!host || !doc) return;
    const c = doc.compte || {};
    host.innerHTML = `<p class="notice"><b>${doc.k_tests} tests</b> aujourd’hui (critère × sujet), corrigés par Holm · période ${esc(doc.periode?.[0])} → ${esc(doc.periode?.[1])} ·
      ✅ ${c.prouve || 0} · 🟡 ${c.piste || 0} · ⚪ ${c.aucune || 0}<br>${esc(doc.note)}</p>
      <p class="mini">${esc(doc.methode)}</p>
      ${doc.sujets.filter(s => s.n > 0).map(card).join('')}`;
    host.querySelectorAll('.pf-freeze').forEach(b => b.addEventListener('click', () => {
      const cardObj = doc.sujets.filter(s => s.n > 0)[+b.dataset.card];
      const item = sentencesOf(cardObj)[+b.dataset.item];
      const spec = { ...item.p.variante, date: new Date().toISOString().slice(0, 10) };
      const out = document.getElementById(`pf-out-${b.dataset.card}-${b.dataset.item}`);
      out.innerHTML = `<p class="detail">Copier ce bloc dans l’entrée <b>explorateur</b> du workflow <b>« Lab - gel (V6.6 et explorateur) »</b>. Seules les alertes à partir du lendemain du gel compteront.</p><textarea readonly rows="4" class="pf-json">${esc(JSON.stringify(spec))}</textarea>`;
    }));
  }

  async function start() {
    const host = $('profilsBody'); if (!host) return;
    try {
      const r = await fetch(`./live/profils_hypotheses.json?t=${Date.now()}`, { cache: 'no-store' });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      doc = await r.json(); render();
    } catch (e) { host.innerHTML = `<p class="notice warn">Profils indisponibles : ${esc(e.message)}</p>`; }
  }
  if (hasDoc && typeof module === 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  }
  if (typeof module !== 'undefined') module.exports = { sentencesOf, card };
})();
