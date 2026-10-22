/* Tennis Edge Lab V7.3 — « Base des matchs » : tous les matchs collectés, de l'ouverture à la clôture,
   les lectures « matchs similaires passés » rejouées dans le temps, et leur vérification après coup.
   Lecture seule. */
(() => {
  'use strict';
  const hasDoc = typeof document !== 'undefined';
  const $ = id => (hasDoc ? document.getElementById(id) : null);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const fin = v => v !== null && v !== undefined && Number.isFinite(+v);
  const nf = (v, d = 2) => (fin(v) ? new Intl.NumberFormat('fr-FR', { maximumFractionDigits: d, minimumFractionDigits: 0 }).format(+v) : '—');
  const sg = (v, d = 1, u = ' %') => {
    if (!fin(v)) return '—';
    const r = Math.round(+v * 10 ** d) / 10 ** d || 0;
    return `${r > 0 ? '+' : ''}${nf(r, d)}${u}`;
  };
  const ic = c => (c && fin(c[0]) ? `[${sg(c[0])} ; ${sg(c[1])}]` : '—');
  const PAGE = 25;
  const CP_LABEL = { open: 'Ouv.', '24h': '24 h', '6h': '6 h', '1h': '1 h', '10m': '10 min', close: 'Clôt.' };

  // ---------- Fonctions pures (testées) ----------
  function powerFair(side, other, tol = 1e-12) {
    if (!side || !other || side <= 1 || other <= 1) return null;
    const a = 1 / side, b = 1 / other, f = k => a ** k + b ** k - 1;
    let lo = 0, hi = 1;
    while (f(hi) > 0) { hi *= 2; if (hi > 1e6) return null; }
    for (let i = 0; i < 200; i++) { const mid = (lo + hi) / 2; if (f(mid) > 0) lo = mid; else hi = mid; if (hi - lo < tol) break; }
    return 1 / (a ** ((lo + hi) / 2));
  }
  const effective = (book, odds) => (fin(odds) ? 1 + (odds - 1) * (1 - ((book && book.commission) || 0)) : null);

  /** Décode un mois : lignes « horizons » et « alertes » en objets. */
  function decodeMonth(doc) {
    const hc = doc.colonnes_horizons || [], ac = doc.colonnes_alertes || [];
    return (doc.matchs || []).map(m => ({
      ...m,
      horizons: (m.horizons || []).map(r => { const o = { side: r[0] }; hc.forEach((c, i) => { o[c] = r[i + 1]; }); return o; }),
      alertes: (m.alertes || []).map(r => { const o = {}; ac.forEach((c, i) => { o[c] = r[i]; }); return o; }),
    }));
  }

  /** Cote d'un book à un point (index dans doc.points) pour un côté : [minutes avant, cote] ou null. */
  const at = (line, side, k) => (line && line[1 + side] ? line[1 + side][k] : null);

  /** Pinnacle juste à chaque point, pour le côté donné. */
  function fairRow(m, side, npts) {
    const pin = m.cotes.find(c => c[0] === m._pinIx);
    return Array.from({ length: npts }, (_, k) => {
      const a = at(pin, side, k), b = at(pin, 1 - side, k);
      return a && b ? powerFair(a[1], b[1]) : null;
    });
  }

  /** Meilleur prix jouable (net de commission, hors Pinnacle) à chaque point. */
  function bestRow(m, side, npts, books, onlyFr = false) {
    return Array.from({ length: npts }, (_, k) => {
      let best = null;
      for (const line of m.cotes) {
        const b = books[line[0]];
        if (!b || b.nom === 'pinnacle' || !b.jouable || (onlyFr && !b.fr)) continue;
        const p = at(line, side, k);
        if (!p) continue;
        const eff = effective(b, p[1]);
        if (!best || eff > best.odds) best = { book: b.nom, odds: eff };
      }
      return best;
    });
  }

  function lectureOf(m) {
    const v = new Set(m.horizons.map(h => h.lecture_verdict).filter(Boolean));
    return v.has('sous-coté') ? 'sous-coté' : v.has('sur-coté') ? 'sur-coté' : v.size ? 'le marché a raison' : null;
  }

  function filterMatches(list, f) {
    const q = (f.q || '').trim().toLowerCase();
    return list.filter(m => {
      if (q && !`${m.joueurs.join(' ')} ${m.tournoi}`.toLowerCase().includes(q)) return false;
      if (f.circuit && m.circuit !== f.circuit) return false;
      if (f.alerte === 'avec' && !m.alertes.length) return false;
      if (f.alerte === 'sans' && m.alertes.length) return false;
      if (f.alerte && !['avec', 'sans'].includes(f.alerte) && !m.alertes.some(a => String(a.type).startsWith(f.alerte))) return false;
      if (f.lecture) {
        const vs = new Set(m.horizons.map(h => h.lecture_verdict));
        if (!vs.has(f.lecture)) return false;
      }
      if (f.courbe === 'avec' && m.sans_courbe) return false;
      if (f.courbe === 'sans' && !m.sans_courbe) return false;
      if (f.resultat === 'avec' && m.vainqueur === null) return false;
      if (f.resultat === 'sans' && m.vainqueur !== null) return false;
      return true;
    });
  }

  /** Cohérence CLV → ROI (miroir de lectures_profils.coherence). items : [[cote nette, clv %, pnl]]. */
  function coherence(items) {
    const ok = items.filter(([c, v, g]) => fin(c) && c > 1 && fin(v) && fin(g));
    const n = ok.length;
    if (!n) return { n: 0, roi_attendu: null, roi_reel: null, z: null, etat: 'aucun pari réglé' };
    let exp = 0, real = 0, vr = 0;
    for (const [c, v, g] of ok) {
      exp += v / 100; real += g;
      const p = Math.min(Math.max((1 + v / 100) / c, 1e-6), 1 - 1e-6);
      vr += c * c * p * (1 - p);
    }
    const z = vr ? (real - exp) / Math.sqrt(vr) : null;
    const etat = n < 30 ? 'trop peu de paris' : z === null || Math.abs(z) < 2 ? 'cohérent'
      : z > 0 ? 'gains au-dessus de la CLV' : 'la CLV ne se transforme pas en gains';
    return { n, roi_attendu: 100 * exp / n, roi_reel: 100 * real / n, z, etat };
  }

  const ago = min => (!fin(min) ? '—' : min >= 1440 ? `${nf(min / 1440, 1)} j avant` : min >= 60 ? `${nf(min / 60, 1)} h avant` : `${nf(min, 0)} min avant`);

  // ---------- Rendu ----------
  const state = { index: null, months: {}, mois: null, list: null, f: {}, page: 0, open: new Set(), simOpen: new Set(), evalDoc: null, err: null,
    servDoc: null, servQ: '', servKey: null, servOpen: false };
  async function chargerService() {
    if (state.servDoc) return;
    try { state.servDoc = await gz('./live/joueurs_service.json.gz'); } catch (e) { state.servDoc = { joueurs: {}, erreur: e.message }; }
  }
  function bindService() {
    const q = $('rgServQ');
    if (q) q.addEventListener('input', () => {
      state.servQ = q.value;
      const body = $('rgServBody');
      if (body) { body.innerHTML = serviceInner(state.servDoc, state.servQ, state.servKey); bindService(); const q2 = $('rgServQ'); if (q2) { q2.focus(); q2.setSelectionRange(q2.value.length, q2.value.length); } }
    });
    document.querySelectorAll('#registreBody [data-serv-key]').forEach(b => b.addEventListener('click', async () => {
      state.servKey = b.dataset.servKey; state.servOpen = true;
      await chargerService();
      render();
      const d = $('rgServ'); if (d && d.scrollIntoView) d.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }));
  }
  async function gz(url) {
    if (typeof DecompressionStream === 'undefined') throw new Error('navigateur sans décompression gzip');
    const r = await fetch(`${url}?t=${Date.now()}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`${url} : ${r.status}`);
    return JSON.parse(await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text());
  }
  async function json(url) {
    const r = await fetch(`${url}?t=${Date.now()}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`${url} : ${r.status}`);
    return r.json();
  }
  async function loadMonth(mois) {
    if (!state.months[mois]) {
      const entry = state.index.mois.find(x => x.mois === mois);
      const doc = await gz(`./live/registre/${entry.fichier}`);
      const pinIx = doc.books.findIndex(b => b.nom === 'pinnacle');
      // Plus récents d'abord.
      state.months[mois] = { doc, list: decodeMonth(doc).map(m => ({ ...m, _pinIx: pinIx })).reverse() };
    }
    state.mois = mois;
    state.page = 0;
    state.open.clear();
  }

  function spark(m) {
    const series = m.pinnacle || [[], []];
    const all = series.flat();
    if (all.length < 2) return '<p class="mini">Courbe Pinnacle indisponible.</p>';
    const xs = all.map(p => p[0]), ys = all.map(p => Math.log(p[1]));
    const x0 = Math.max(...xs), x1 = Math.min(...xs, 0), y0 = Math.min(...ys), y1 = Math.max(...ys);
    const W = 320, H = 110, P = 6;
    const X = v => P + (W - 2 * P) * (x0 === x1 ? 1 : (x0 - v) / (x0 - x1));
    const Y = v => P + (H - 2 * P) * (y1 === y0 ? 0.5 : (y1 - Math.log(v)) / (y1 - y0));
    const line = (s, cls) => (s.length ? `<polyline class="${cls}" points="${s.map(p => `${X(p[0]).toFixed(1)},${Y(p[1]).toFixed(1)}`).join(' ')}"/>` : '');
    const marks = (m.alertes || []).filter(a => fin(a.minutes_avant)).map(a => `<line class="rg-alert" x1="${X(a.minutes_avant).toFixed(1)}" x2="${X(a.minutes_avant).toFixed(1)}" y1="${P}" y2="${H - P}"><title>${esc(a.type)}</title></line>`).join('');
    return `<svg class="rg-spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="Cote Pinnacle de l'ouverture au début du match">${marks}${line(series[0], 'rg-l0')}${line(series[1], 'rg-l1')}</svg>
      <p class="mini rg-legend"><span class="rg-k0"></span>${esc(m.joueurs[0])} <span class="rg-k1"></span>${esc(m.joueurs[1])} · ouverture à gauche (${ago(x0)}), début à droite${(m.alertes || []).length ? ' · traits = alertes' : ''}</p>`;
  }

  function priceTable(m, side, doc) {
    const pts = doc.points, books = doc.books;
    const fair = fairRow(m, side, pts.length), best = bestRow(m, side, pts.length, books), fr = bestRow(m, side, pts.length, books, true);
    const head = `<tr><th>Book</th>${pts.map(p => `<th>${CP_LABEL[p] || esc(p)}</th>`).join('')}</tr>`;
    const cell = (p, hl) => (p ? `<td class="${hl ? 'rg-best' : ''}">${nf(p[1], 2)}</td>` : '<td>—</td>');
    const rows = m.cotes.map(line => {
      const b = books[line[0]];
      const isPin = b.nom === 'pinnacle';
      return `<tr class="${isPin ? 'rg-pin' : ''}"><th>${esc(b.nom)}${b.fr ? ' 🇫🇷' : ''}${b.jouable ? '' : ' ·'}</th>${pts.map((_, k) => {
        const p = at(line, side, k);
        const hl = !isPin && p && best[k] && best[k].book === b.nom;
        return cell(p, hl);
      }).join('')}</tr>`;
    });
    const fairTr = `<tr class="rg-fair"><th>Pinnacle juste</th>${fair.map(v => `<td>${nf(v, 2)}</td>`).join('')}</tr>`;
    const bestTr = `<tr class="rg-fair"><th>Meilleur jouable (net)</th>${best.map(v => `<td>${v ? nf(v.odds, 2) : '—'}</td>`).join('')}</tr>`;
    const frTr = `<tr class="rg-fair"><th>Meilleur FR</th>${fr.map(v => `<td>${v ? nf(v.odds, 2) : '—'}</td>`).join('')}</tr>`;
    const pinLine = m.cotes.find(c => c[0] === m._pinIx);
    const when = pts.map((_, k) => { const p = at(pinLine, side, k); return `<td>${p ? esc(ago(p[0]).replace(' avant', '')) : '—'}</td>`; }).join('');
    return `<div class="table-wrap rg-table"><table><thead>${head}</thead><tbody>${rows[0] || ''}${fairTr}<tr class="rg-when"><th>(heure Pinnacle)</th>${when}</tr>${bestTr}${frTr}${rows.slice(1).join('')}</tbody></table></div>`;
  }

  function horizonsTable(m) {
    if (!m.horizons.length) return '<p class="mini">Pinnacle ne cotait pas les deux joueurs aux horizons 24 h / 6 h / 1 h / 10 min.</p>';
    const tr = m.horizons.map(h => {
      const v = h.lecture_verdict;
      const cls = v === 'sous-coté' ? 'good' : v === 'sur-coté' ? 'bad' : '';
      return `<tr><td>${esc(h.horizon)}</td><td>${esc(m.joueurs[h.side] || '?')}</td><td>${nf(h.cote_pin, 2)}<span class="detail">${fin(h.proba_juste) ? nf(100 * h.proba_juste, 1) + ' %' : ''}</span></td>
        <td>${h.cote_jouable ? `${nf(h.cote_jouable, 2)}<span class="detail">${esc(h.book_jouable)} · ${sg(h.ecart_jouable_pct)}</span>` : '—'}</td>
        <td>${h.cote_fr ? `${nf(h.cote_fr, 2)}<span class="detail">${esc(h.book_fr)}</span>` : '—'}</td>
        <td>${sg(h.clv_pinnacle)}<span class="detail">jouable ${sg(h.clv_jouable)}${fin(h.clv_fr) ? ` · FR ${sg(h.clv_fr)}` : ''}</span></td>
        <td>${fin(h.pnl_jouable) ? sg(100 * h.pnl_jouable, 0) : fin(h.pnl_pinnacle) ? sg(100 * h.pnl_pinnacle, 0) : '—'}</td>
        <td class="${cls}">${v ? esc(v) : '—'}<span class="detail">${fin(h.lecture_exces) ? `excès ${sg(h.lecture_exces)} [${sg(h.lecture_exces_lo)} ; ${sg(h.lecture_exces_hi)}] · n=${nf(h.lecture_n, 0)}` : ''}</span></td></tr>`;
    }).join('');
    return `<div class="table-wrap rg-table"><table><thead><tr><th>Horizon</th><th>Joueur</th><th>Pinnacle · juste</th><th>Meilleur jouable · écart</th><th>Meilleur FR</th><th>CLV</th><th>P&amp;L</th><th>Lecture « matchs similaires » à ce moment</th></tr></thead><tbody>${tr}</tbody></table></div>
      <p class="mini">La lecture n'utilise que les matchs commencés au moins 4 h avant l'horizon : c'est ce que l'onglet « Matchs en direct » aurait affiché à ce moment-là.</p>`;
  }

  function alertsList(m) {
    if (!m.alertes.length) return '<p class="mini">Aucune alerte sur ce match.</p>';
    return `<ul class="rg-alerts">${m.alertes.map(a => `<li><b>${esc(a.type)}</b> · ${esc(m.joueurs[a.cote_de] || '?')} · ${esc(ago(a.minutes_avant))}${a.book ? ` · ${esc(a.book)}` : ''}${fin(a.cote) ? ` à ${nf(a.cote, 2)}` : ''}${fin(a.ampleur_pts) ? ` · ${nf(a.ampleur_pts, 1)} pts` : ''}${a.envoyee ? '' : ' · <i>non envoyée</i>'}${fin(a.clv_pin) ? ` · CLV ${sg(a.clv_pin)}` : ''}${fin(a.pnl) ? ` · P&amp;L ${sg(100 * a.pnl, 0)}` : ''}</li>`).join('')}</ul>`;
  }

  function fiche(m, doc) {
    if (m.sans_courbe) {
      return `<div class="rg-fiche"><p class="notice">Courbes de cotes non collectées pour ce match (la collecte des courbes ne couvre pas tous les matchs, et elle est en pause jusqu'au 27/10). Seules ses alertes sont connues, avec leur CLV et leur résultat. Heure de début estimée d'après les alertes.</p>
        <h4>Alertes</h4>${alertsList(m)}</div>`;
    }
    return `<div class="rg-fiche">${spark(m)}
      <h4>Cotes de l'ouverture à la clôture — ${esc(m.joueurs[0])}</h4>${priceTable(m, 0, doc)}
      <h4>Cotes de l'ouverture à la clôture — ${esc(m.joueurs[1])}</h4>${priceTable(m, 1, doc)}
      <p class="mini">Surligné : meilleur prix jouable hors Pinnacle à ce point (net de commission). « · » après un nom : book non jouable (donnée seule).</p>
      <h4>Alertes</h4>${alertsList(m)}
      <h4>Aux horizons de décision</h4>${horizonsTable(m)}</div>`;
  }

  function row(m, doc) {
    const pin = m.cotes.find(c => c[0] === m._pinIx);
    const oc = side => { const o = at(pin, side, 0), c = at(pin, side, doc.points.length - 1); return `${o ? nf(o[1], 2) : '—'} → ${c ? nf(c[1], 2) : '—'}`; };
    const d = new Date(m.debut);
    const when = `${String(d.getUTCDate()).padStart(2, '0')}/${String(d.getUTCMonth() + 1).padStart(2, '0')} ${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}`;
    const types = [...new Set(m.alertes.map(a => String(a.type).startsWith('H') ? a.type : a.type))];
    const lec = lectureOf(m);
    const open = state.open.has(m.uid);
    const name = i => `<span class="${m.vainqueur === i ? 'rg-win' : ''}">${esc(m.joueurs[i])}</span>`;
    return `<article class="rg-card"><button type="button" class="rg-head" data-uid="${esc(m.uid)}" aria-expanded="${open}">
      <span class="detail">${m.debut_estime ? '≈ ' : ''}${esc(when)} UTC · ${esc(m.tournoi)} · ${esc(m.circuit)} · ${esc(m.surface)}</span>
      <span class="rg-players">${name(0)} <span class="detail">${oc(0)}</span><br>${name(1)} <span class="detail">${oc(1)}</span></span>
      <span class="rg-badges">${m.vainqueur === null ? '<i>sans résultat</i>' : ''}${m.sans_courbe ? '<span class="rg-badge">sans courbe</span>' : ''}${types.map(t => `<span class="rg-badge">${esc(t)}</span>`).join('')}${lec && lec !== 'le marché a raison' ? `<span class="rg-badge ${lec === 'sous-coté' ? 'good' : 'bad'}">${esc(lec)}</span>` : ''}</span></button>
      ${open ? fiche(m, doc) : ''}</article>`;
  }

  const summaryCell = s => (s && fin(s.moyenne) ? `${sg(s.moyenne)}<span class="detail">${ic(s.ic95)} · n=${nf(s.n, 0)}</span>` : '—');
  /** Écart de victoires des profils (ex. 24/25 gagnés pour 72 % attendus) et ce qu'a fait le match suivant. */
  function victoires(V) {
    if (!V || !V.lignes) return '';
    const corr = V.correlation;
    const msg = !fin(corr) ? '' : Math.abs(corr) < 0.05
      ? `Corrélation écart du profil / écart du match suivant : <b>${nf(corr, 3)}</b>. Un profil qui gagnait beaucoup plus (ou moins) que prévu <b>ne dit rien</b> du match suivant : l'écart venait du hasard.`
      : `Corrélation écart du profil / écart du match suivant : <b>${nf(corr, 3)}</b> — à examiner tranche par tranche.`;
    const tab = (rows, head) => `<div class="table-wrap rg-table"><table><thead><tr><th>${head}</th><th>Matchs suivants</th><th>Gagné</th><th>Attendu (juste)</th><th>Écart · IC95</th><th>ROI Pinnacle</th></tr></thead><tbody>${rows.filter(g => g.n).map(g => `<tr><td>${esc(g.groupe)}</td><td>${nf(g.n, 0)}</td><td>${nf(100 * g.gagne, 1)} %</td><td>${nf(100 * g.attendu, 1)} %</td><td>${sg(g.ecart_pts, 1, ' pts')}<span class="detail">[${sg(g.ic95_pts[0], 1, '')} ; ${sg(g.ic95_pts[1], 1, '')}]</span></td><td>${sg(g.roi_pinnacle)}</td></tr>`).join('')}</tbody></table></div>`;
    return `<h4>Écart de victoires des profils, vérifié après coup</h4>
      <p class="mini">${nf(V.lignes, 0)} matchs dont le profil avait au moins ${V.min_regles} matchs réglés. On classe chaque match selon l'écart de son profil (victoires − probabilité juste), puis on regarde si le match lui-même a gagné plus ou moins que prévu.</p>
      <p>${msg}</p>
      <h5>Selon l'écart du profil</h5>${tab(V.par_ecart, 'Le profil gagnait…')}
      <h5>Selon la rareté de l'écart (z binomial)</h5>${tab(V.par_z, 'Écart du profil')}`;
  }

  /** Le prix tient-il après l'alerte ? (delai_alertes.json) */
  function delaiBlock(D) {
    if (!D || !D.resume || !D.resume.length) return '';
    const by = {};
    for (const r of D.resume) (by[r.hypothese] = by[r.hypothese] || {})[r.delai_min] = r;
    const delais = D.delais_min || [0, 2, 5, 10, 30];
    const codes = Object.keys(by).sort((a, b) => (a === 'toutes') - (b === 'toutes') || a.localeCompare(b));
    const cell = r => (r ? `${nf(100 * r.prix_tenu, 0)} %<span class="detail">CLV ${sg(r.clv_au_prix_disponible, 2)}</span>` : '—');
    const rows = codes.map(c => {
      const r0 = by[c][delais[0]] || {};
      return `<tr><td>${esc(c)}</td><td>${nf(r0.n, 0)}</td><td>${sg(r0.clv_au_prix_alerte, 2)}</td>${delais.map(d => `<td>${cell(by[c][d])}</td>`).join('')}<td>${sg((by[c][5] || {}).clv_meilleur_book, 2)}</td></tr>`;
    }).join('');
    return `<details class="rg-eval"><summary>Le prix tient-il après l'alerte ?</summary>
      <p class="mini">${nf(D.alertes_envoyees, 0)} alertes envoyées (H13 à H19) ; ${nf(D.sans_courbe_du_book, 0)} sans courbe du book alerté (matchs pas encore récupérés). Pour chaque délai après l'envoi : part des alertes où le book paie encore au moins le prix du message, et CLV au prix alors disponible (clôture Pinnacle sans marge). Dernière colonne : CLV au meilleur prix tous books confondus, 5 min après.</p>
      <div class="table-wrap rg-table"><table><thead><tr><th>Hypothèse</th><th>Alertes</th><th>CLV message</th>${delais.map(d => `<th>+${d} min</th>`).join('')}<th>Meilleur book à +5 min</th></tr></thead><tbody>${rows}</tbody></table></div>
    </details>`;
  }

  /** Chaque book collecté : couverture, part du meilleur prix, écart médian à la cote juste. */
  function booksBlock(V) {
    const B = V && V.books;
    if (!B || !B.books || !B.books.length) return '';
    return `<details class="rg-eval"><summary>Les books collectés : couverture et prix</summary>
      <p class="mini">${nf(B.matchs, 0)} matchs, ${nf(B.decisions, 0)} décisions (joueur × horizon). Écart = prix net (commission déduite) contre la cote Pinnacle juste au même moment ; une cote de plus de 30 min n'est pas comptée.</p>
      <div class="table-wrap rg-table"><table><thead><tr><th>Book</th><th>Matchs cotés</th><th>Meilleur prix</th><th>Écart médian</th><th>Cotes ≥ +2 %</th></tr></thead><tbody>${B.books.map(b => `<tr><td>${esc(b.book)}${b.fr ? ' 🇫🇷' : ''}${b.bourse ? ' (bourse)' : ''}</td><td>${nf(100 * b.couverture, 0)} %<span class="detail">${nf(b.matchs, 0)}</span></td><td>${nf(100 * b.meilleur_prix, 1)} %</td><td>${sg(b.ecart_median)}</td><td>${nf(b.au_dessus_2pct, 0)}</td></tr>`).join('')}</tbody></table></div>
    </details>`;
  }

  /** Croisements : réel − attendu de l'issue selon les circonstances (croisements.json). */
  function croisementsBlock(C) {
    if (!C || !C.lignes || !C.lignes.length) return '';
    const iss = C.issues || [];
    const by = {};
    for (const L of C.lignes) ((by[L.famille] = by[L.famille] || {})[L.circonstance] = by[L.famille][L.circonstance] || {})[L.issue] = L;
    const pts = s => (s && s.n ? `${sg(s.ecart, 1, '')}` : '—');
    const cell = L => {
      if (!L || !L.decouverte || !L.decouverte.n) return '<td>—</td>';
      const cls = L.statut === 'confirmé' ? 'good' : L.statut === 'à suivre' ? 'rg-suivre' : '';
      return `<td class="${cls}">${pts(L.decouverte)} / ${pts(L.confirmation)}<span class="detail">z ${nf(L.decouverte.z, 1)} / ${nf(L.confirmation && L.confirmation.z, 1)}</span></td>`;
    };
    const fams = Object.keys(by);
    const conf = C.lignes.filter(L => L.statut === 'confirmé');
    const suiv = C.lignes.filter(L => L.statut === 'à suivre');
    const lab = k => ((iss.find(i => i.cle === k) || {}).libelle || k);
    const tables = fams.map(f => {
      const rows = Object.entries(by[f]).filter(([, v]) => Object.values(v).some(L => L.decouverte && L.decouverte.n >= 20));
      if (!rows.length) return '';
      return `<h5>${esc(f)}</h5><div class="table-wrap rg-table"><table><thead><tr><th>Circonstance</th><th>Matchs</th>${iss.map(i => `<th>${esc(i.libelle)}</th>`).join('')}</tr></thead><tbody>${rows.map(([lib, v]) => {
        const any = Object.values(v)[0] || {};
        return `<tr><td>${esc(lib)}</td><td>${nf((any.decouverte || {}).n, 0)} + ${nf((any.confirmation || {}).n, 0)}</td>${iss.map(i => cell(v[i.cle])).join('')}</tr>`;
      }).join('')}</tbody></table></div>`;
    }).join('');
    const liste = (arr, t) => (arr.length ? `<p><b>${t}</b> : ${arr.map(L => `${esc(L.circonstance)} — ${esc(lab(L.issue))} (${pts(L.decouverte)} / ${pts(L.confirmation)} pts)`).join(' · ')}</p>` : '');
    return `<details class="rg-eval"><summary>Croisements : l'issue selon les circonstances</summary>
      <p class="mini">${nf(C.matchs, 0)} matchs joués (${esc((C.periode || [])[0] || '')} → ${esc((C.periode || [])[1] || '')}). Chaque case : écart <b>réel − attendu</b> en points, sur la 1re moitié des matchs de la circonstance (découverte) / sur la 2de (confirmation). Attendu : victoire = cote Pinnacle juste à la clôture ; 2-0, 3 sets et set 1 = moteur du simulateur (forme du jour). Un écart proche de 0 : la circonstance est déjà dans la cote.</p>
      ${conf.length ? liste(conf, 'Confirmé (Holm en découverte, même sens z ≥ 1,96 en confirmation)') : `<p>Aucun croisement confirmé pour l'instant (${nf(C.tests_holm, 0)} tests, correction de Holm).</p>`}
      ${liste(suiv, 'À suivre (|z| ≥ 2 en découverte seulement — souvent du hasard)')}
      ${tables}
      <p class="mini">Un croisement confirmé n'est pas un pari : il devient une hypothèse à geler, puis à juger sur la CLV des matchs suivants.</p>
    </details>`;
  }

  /** Pronostics du jour : deux versions côte à côte + compteur de réussite (pronostics.json, pronostics_bilan.json). */
  /** 22/10/2026 — le match joué avant l'heure : feuille de stats prévue (moyenne + fourchette 80 %),
   *  scores les plus fréquents, match type set par set avec les breaks. Version marché si Pinnacle cote. */
  /** 22/10/2026 — la même probabilité lue en cote JUSTE (1 / p, sans marge) : 2 décimales sous 10,
   *  1 jusqu'à 100, entière au-delà. Ce n'est pas un prix à jouer : un book ajoute sa marge. */
  const coteJuste = p => {
    if (!fin(p) || p <= 0 || p >= 1) return '—';
    const c = 1 / p;
    return c.toFixed(c < 10 ? 2 : c < 100 ? 1 : 0).replace('.', ',');
  };
  const pcCote = p => (fin(p) ? `${nf(100 * p, p < 0.1 ? 1 : 0)} % <span class="rg-cote">· ${coteJuste(p)}</span>` : '—');
  const SIM_LIGNES = [['aces', 'Aces', 1], ['doubles_fautes', 'Doubles fautes', 1], ['premiere_pct', '1re balle', 0, ' %'],
    ['gagnes_1re_pct', 'Points gagnés 1re balle', 0, ' %'], ['gagnes_2e_pct', 'Points gagnés 2e balle', 0, ' %'],
    ['balles_break_obtenues', 'Balles de break obtenues', 1], ['breaks', 'Breaks', 1],
    ['jeux_service_gagnes_pct', 'Jeux de service gagnés', 0, ' %'], ['points_gagnes', 'Points gagnés', 0]];
  function simuleBlock(m, ouverts) {
    const v = [m.simulation, m.marche, m.stats].find(x => x && x.match_simule);
    const S = v && v.match_simule;
    if (!S || !S.feuille) return '';
    const court = n => esc(String(n || '').split(' ').slice(-1)[0]);
    const H = court(m.home), A = court(m.away);
    const pl = (n, un, plus = `${un}s`) => (fin(n) ? `${n} ${n > 1 ? plus : un}` : '—');
    const val = (x, dec, unit = '') => (x && fin(x.moy) ? `<b>${nf(x.moy, dec)}${unit}</b><span class="detail">${nf(x.p10, 0)}–${nf(x.p90, 0)}${unit}</span>` : '—');
    const rows = SIM_LIGNES.map(([k, lab, dec, unit]) => `<tr><td>${val(S.feuille[0][k], dec, unit)}</td><th scope="row">${lab}</th><td>${val(S.feuille[1][k], dec, unit)}</td></tr>`).join('');
    const scores = (S.scores || []).map(([sc, p]) => `${esc(sc)} <small>${pcCote(p)}</small>`).join(' · ');
    const T = S.match_type;
    let recit = '';
    if (T && T.sets) {
      recit = T.sets.map(([a, b], i) => {
        const br = (T.breaks || []).filter(x => x[0] === i).map(([, ga, gb, qui]) => `${qui === 0 ? H : A} (${ga + (qui === 0)}-${gb + (qui === 1)})`);
        return `<li><b>Set ${i + 1} · ${a}-${b}</b>${a + b === 13 ? ' (tie-break)' : ''}${br.length ? ` — break${br.length > 1 ? 's' : ''} : ${br.join(', ')}` : ' — aucun break'}</li>`;
      }).join('');
      const f = T.feuille || [{}, {}];
      recit = `<h5>Match type</h5><p class="mini">Une simulation réelle, la plus proche de la médiane parmi celles du score le plus fréquent (${esc(T.score)}).</p>
        <ol class="rg-sim-sets">${recit}</ol><p class="mini">${H} : ${pl(f[0].aces, "ace")}, ${pl(f[0].doubles_fautes, "double faute", "doubles fautes")}, ${nf(f[0].premiere_pct, 0)} % de 1re balle · ${A} : ${pl(f[1].aces, "ace")}, ${pl(f[1].doubles_fautes, "double faute", "doubles fautes")}, ${nf(f[1].premiere_pct, 0)} % de 1re balle.</p>`;
    }
    const inconnus = [[m.home, 0], [m.away, 1]].filter(([, i]) => S.profil_connu && !S.profil_connu[i]).map(([n]) => esc(n));
    const ouvert = ouverts && ouverts.has(m.uid) ? ' open' : '';
    return `<details class="rg-sim" data-sim="${esc(m.uid || '')}"${ouvert}><summary>Match simulé ${nf(S.n, 0)} fois</summary>
      <p class="mini">${v === m.simulation ? '<b>Match joué avec les seules statistiques des deux joueurs</b> (1re balle, aces, doubles fautes, points gagnés derrière la 1re et la 2e, retour), sans classement ni cote' : v === m.marche ? 'Niveau : cote Pinnacle (stats + marché)' : 'Niveau : classement Elo (stats seules)'}. ${H} gagne ${nf(100 * S.victoire_A, 0)} % des simulations. Sous chaque valeur : fourchette à 80 % (8 simulations sur 10 dedans).${inconnus.length ? ` Profil de service inconnu pour ${inconnus.join(' et ')} : moyenne du circuit.` : ''}</p>
      <div class="table-wrap rg-table rg-sim-feuille"><table><thead><tr><th>${H}</th><th></th><th>${A}</th></tr></thead><tbody>${rows}</tbody></table></div>
      <p class="mini">Jeux : <b>${nf(S.jeux && S.jeux.moy, 1)}</b> (${nf(S.jeux && S.jeux.p10, 0)}–${nf(S.jeux && S.jeux.p90, 0)}) · au moins un tie-break : <b>${pcCote(S.tiebreak)}</b></p>
      <p class="mini">Scores les plus fréquents : ${scores}</p>${recit}</details>`;
  }

  /** 22/10/2026 — fiche « service et retour » d'un joueur (joueurs_service.json.gz, profils du match simulé). */
  const SERV_LIGNES = [['f', '% de 1re balle'], ['a', 'Aces par 1re balle dans le court'], ['d', 'Doubles fautes par 2e balle'],
    ['w1', 'Points gagnés derrière la 1re'], ['w2j', 'Points gagnés derrière la 2e jouée'], ['serv', 'Points de service gagnés'],
    ['ra', 'Aces concédés au retour'], ['ret1', 'Points gagnés en retour sur 1re'], ['ret2', 'Points gagnés en retour sur 2e'],
    ['ret', 'Points gagnés en retour']];
  const SURF_FR = { all: 'Tous terrains', Hard: 'Dur', Clay: 'Terre', Grass: 'Gazon' };
  const sansAccent = t => String(t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  function chercherJoueurs(doc, q, n = 8) {
    const t = sansAccent(q).trim();
    if (!doc || !doc.joueurs || t.length < 2) return [];
    const mots = t.split(/\s+/);
    return Object.entries(doc.joueurs).filter(([, j]) => mots.every(m => sansAccent(j.nom).includes(m)))
      .sort((a, b) => b[1].balles - a[1].balles).slice(0, n);
  }
  function ficheService(doc, key) {
    const j = doc && doc.joueurs && doc.joueurs[key];
    if (!j) return '<p class="mini">Pas de profil pour ce joueur (moins de 300 balles de service, ou aucun match depuis 2025).</p>';
    const S = j.surfaces || {}, M = (doc.moyennes || {})[j.circuit] || {};
    const surfs = ['all', 'Hard', 'Clay', 'Grass'].filter(s => S[s]);
    const v = x => (fin(x) ? `${nf(100 * x, 1)} %` : '—');
    const cent = c => (fin(c) ? `<span class="rg-cent ${c >= 75 ? 'good' : c <= 25 ? 'bad' : ''}">${c}<sup>e</sup> centile</span>` : '');
    const lignes = SERV_LIGNES.map(([k, lab]) => `<tr><td>${lab}</td>${surfs.map(s => `<td><b>${v(S[s].joueur[k])}</b>${s === 'all' ? cent((S.all.centiles || {})[k]) : ''}<span class="detail">circuit ${v((M[s] || {})[k])}</span></td>`).join('')}</tr>`).join('');
    const evo = j.evolution && j.evolution.length ? `<h5>Mois par mois (feuilles collectées depuis la fin de l'archive)</h5><div class="table-wrap rg-table"><table><thead><tr><th>Mois</th><th>Matchs</th><th>Aces / match</th><th>1re balle</th><th>Gagnés 1re</th><th>Gagnés 2e</th><th>Service</th><th>Retour</th></tr></thead><tbody>${j.evolution.map(r => `<tr><td>${esc(r[0])}</td><td>${r[1]}</td><td>${nf(r[2], 1)}</td><td>${nf(r[3], 1)} %</td><td>${nf(r[4], 1)} %</td><td>${nf(r[5], 1)} %</td><td>${nf(r[6], 1)} %</td><td>${nf(r[7], 1)} %</td></tr>`).join('')}</tbody></table></div>` : '';
    return `<div class="rg-serv-fiche"><div class="rg-pron-j"><b>${esc(j.nom)}</b> <span class="mini">${esc(j.circuit)} · ${nf(j.balles, 0)} balles de service (pondérées) · dernier match ${esc(j.dernier_match)}</span></div>
      <div class="table-wrap rg-table"><table><thead><tr><th></th>${surfs.map(s => `<th>${SURF_FR[s]}<span class="detail">${nf(S[s].balles, 0)} balles</span></th>`).join('')}</tr></thead><tbody>${lignes}</tbody></table></div>
      <p class="mini">Centile parmi les joueurs actifs du même circuit (100 = le meilleur ; pour les doubles fautes et les aces concédés, moins = mieux). Profil ramené vers la moyenne quand il y a peu de balles : c'est celui qu'utilise le match simulé. Une description du jeu, pas un signal de pari.</p>${evo}</div>`;
  }
  function serviceInner(doc, q, key) {
    if (!doc) return '<p class="mini">Chargement…</p>';
    const res = chercherJoueurs(doc, q);
    return `<label class="rg-q">Joueur<input id="rgServQ" type="search" value="${esc(q || '')}" placeholder="ex. Fils, Swiatek…" autocomplete="off"></label>
      ${res.length ? `<div class="rg-serv-res">${res.map(([k, j]) => `<button type="button" data-serv-key="${esc(k)}">${esc(j.nom)} <small>${esc(j.circuit)}</small></button>`).join('')}</div>` : ''}
      ${key ? ficheService(doc, key) : '<p class="mini">Tapez au moins deux lettres du nom, ou touchez « Profil » sous un pronostic.</p>'}`;
  }
  function serviceBlock(doc, q, key, ouvert) {
    return `<details class="rg-eval" id="rgServ"${ouvert ? ' open' : ''}><summary>Profils de service et de retour${doc && doc.joueurs ? ` (${nf(Object.keys(doc.joueurs).length, 0)} joueurs)` : ''}</summary>
      <div id="rgServBody">${ouvert ? serviceInner(doc, q, key) : ''}</div></details>`;
  }

  // 22/10/2026 — facteurs du match adoptés par l'étude : ce qu'ils changent au % de la simulation.
  const FACTEURS_LIB = { forme_fatigue: 'Forme récente et fatigue', vitesse_court: 'Vitesse du court', morphologie: 'Gaucher ou droitier, taille', points_importants: 'Points importants', styles: 'Duel de styles', face_a_face: 'Face-à-face', conditions: 'Conditions du jour', contexte_tournoi: 'Contexte du tournoi', charting: 'Façon de jouer (Match Charting)', blessure: 'Blessure (abandon, forfait récents)' };
  function facteursBlock(m) {
    const f = m && m.simulation && m.simulation.facteurs;
    if (!f || !f.groupes || !Object.keys(f.groupes).length) return '';
    const nom = String(m.home || '').split(' ').slice(-1)[0];
    const pts = x => `${x > 0 ? '+' : x < 0 ? '−' : ''}${nf(Math.abs(x), 1)} pt`;
    const items = Object.entries(f.groupes).map(([g, x]) => `${esc(FACTEURS_LIB[g] || g)} <b>${pts(x)}</b>`).join(' · ');
    return `<div class="rg-facteurs mini">Ce qui pèse pour ${esc(nom)} : ${items} <span class="rg-cote">(${nf(100 * f.sans, 0)} % sans, ${nf(100 * f.avec, 0)} % avec)</span></div>`;
  }

  // 22/10/2026 — point 8 : EN DIRECT. Même calcul exact que simulateur/direct.py : la forme du jour est
  // mise à jour d'après le score (règle de Bayes sur les 13 nœuds), puis la suite du match est calculée
  // depuis le point exact (sets, jeux, points ou tie-break, serveur).
  const lgD = p => { const q = Math.min(Math.max(p, 1e-9), 1 - 1e-9); return Math.log(q / (1 - q)); };
  const sgD = z => 1 / (1 + Math.exp(-z));
  function pJeu(p) { const q = 1 - p; const d = p * p / (1 - 2 * p * q); return p ** 4 * (1 + 4 * q + 10 * q * q) + 20 * p ** 3 * q ** 3 * d; }
  function jeuDepuis(p, a, b) {
    if (a >= 4 && a - b >= 2) return 1; if (b >= 4 && b - a >= 2) return 0;
    if (a >= 3 && b >= 3) { const d = p * p / (1 - 2 * p * (1 - p)); return a === b ? d : (a > b ? p + (1 - p) * d : p * d); }
    return p * jeuDepuis(p, a + 1, b) + (1 - p) * jeuDepuis(p, a, b + 1);
  }
  function tbDepuis(pA, pB, a, b, aPremier, cible) {
    const memo = new Map();
    const f = (x, y) => {
      if (x >= cible && x - y >= 2) return 1; if (y >= cible && y - x >= 2) return 0;
      if (x >= cible - 1 && y >= cible - 1 && x === y) { const u = pA * (1 - pB), v = (1 - pA) * pB; return u + v > 0 ? u / (u + v) : 0.5; }
      const k = `${x},${y}`; if (memo.has(k)) return memo.get(k);
      const n = x + y; const sertA = ((Math.floor((n + 1) / 2) % 2) === 0) === aPremier;
      const q = sertA ? pA : 1 - pB;
      const r = q * f(x + 1, y) + (1 - q) * f(x, y + 1); memo.set(k, r); return r;
    };
    return f(a, b);
  }
  function matchDepuis(pA, pB, sa, sb, ga, gb, aPremier, pts, sg, tbFinal, memo = new Map()) {
    if (sa === sg) return 1; if (sb === sg) return 0;
    const key = `${sa},${sb},${ga},${gb},${aPremier},${pts[0]},${pts[1]}`;
    if (memo.has(key)) return memo.get(key);
    const cible = (sa === sg - 1 && sb === sg - 1) ? tbFinal : 7;
    const fin = new Map(); let etats = new Map([[`${ga},${gb},${pts[0]},${pts[1]}`, 1]]);
    const add = (m, k, v) => m.set(k, (m.get(k) || 0) + v);
    while (etats.size) {
      const nouv = new Map();
      for (const [k, pr] of etats) {
        const [x, y, p0, p1] = k.split(',').map(Number);
        if (x === 6 && y === 6) { const t = tbDepuis(pA, pB, p0, p1, aPremier, cible); add(fin, 'A,13', pr * t); add(fin, 'B,13', pr * (1 - t)); continue; }
        const sertA = ((x + y) % 2 === 0) === aPremier;
        const h = sertA ? jeuDepuis(pA, p0, p1) : 1 - jeuDepuis(pB, p1, p0);
        for (const [nx, ny, w] of [[x + 1, y, h], [x, y + 1, 1 - h]]) {
          if ((nx >= 6 && nx - ny >= 2) || (ny >= 6 && ny - nx >= 2)) add(fin, `${nx > ny ? 'A' : 'B'},${nx + ny}`, pr * w);
          else add(nouv, `${nx},${ny},0,0`, pr * w);
        }
      }
      etats = nouv;
    }
    let tot = 0;
    for (const [k, pr] of fin) {
      const [g, n] = k.split(','); const aG = g === 'A';
      const prochain = Number(n) % 2 === 0 ? aPremier : !aPremier;
      tot += pr * matchDepuis(pA, pB, sa + (aG ? 1 : 0), sb + (aG ? 0 : 1), 0, 0, prochain, [0, 0], sg, tbFinal, memo);
    }
    memo.set(key, tot); return tot;
  }
  function setIssues(pA, pB, aPremier, cible) {
    const hA = pJeu(pA), hB = pJeu(pB); let etats = new Map([['0,0', 1]]); const fin = new Map();
    while (etats.size) {
      const nouv = new Map();
      for (const [k, pr] of etats) {
        const [a, b] = k.split(',').map(Number);
        const sertA = ((a + b) % 2 === 0) === aPremier;
        if (a === 6 && b === 6) { const t = tbDepuis(pA, pB, 0, 0, sertA, cible); fin.set('7,6', (fin.get('7,6') || 0) + pr * t); fin.set('6,7', (fin.get('6,7') || 0) + pr * (1 - t)); continue; }
        const w = sertA ? hA : 1 - hB;
        for (const [na, nb, x] of [[a + 1, b, w], [a, b + 1, 1 - w]]) {
          const m = ((na >= 6 && na - nb >= 2) || (nb >= 6 && nb - na >= 2)) ? fin : nouv;
          m.set(`${na},${nb}`, (m.get(`${na},${nb}`) || 0) + pr * x);
        }
      }
      etats = nouv;
    }
    return fin;
  }
  function atteindre(pA, pB, ga, gb, aPremier) {
    let etats = new Map([['0,0', 1]]);
    for (let i = 0; i < ga + gb; i++) {
      const nouv = new Map();
      for (const [k, pr] of etats) {
        const [x, y] = k.split(',').map(Number);
        if ((x >= 6 && x - y >= 2) || (y >= 6 && y - x >= 2) || (x === 6 && y === 6)) continue;
        const sertA = ((x + y) % 2 === 0) === aPremier; const h = sertA ? pJeu(pA) : 1 - pJeu(pB);
        nouv.set(`${x + 1},${y}`, (nouv.get(`${x + 1},${y}`) || 0) + pr * h);
        nouv.set(`${x},${y + 1}`, (nouv.get(`${x},${y + 1}`) || 0) + pr * (1 - h));
      }
      etats = nouv;
    }
    return etats.get(`${ga},${gb}`) || 0;
  }
  function enDirect(d, noeuds, setsJoues, ga, gb, homeSert, pts) {
    const sg = d.sets_gagnants || 2, tbF = d.tb_final || (sg === 3 ? 10 : 7), sigma = d.sigma == null ? 0.15 : d.sigma;
    let premierSet;
    if (ga === 6 && gb === 6) { const n = pts[0] + pts[1]; premierSet = (Math.floor((n + 1) / 2) % 2 === 0) ? homeSert : !homeSert; }
    else premierSet = (ga + gb) % 2 === 0 ? homeSert : !homeSert;
    const premiers = []; let p = premierSet;
    for (let i = setsJoues.length - 1; i >= 0; i--) { const [x, y] = setsJoues[i]; p = (x + y) % 2 === 0 ? p : !p; premiers.unshift(p); }
    const sa = setsJoues.filter(([x, y]) => x > y).length, sb = setsJoues.filter(([x, y]) => y > x).length;
    const N = sigma > 0 ? (noeuds || [[0, 1]]) : [[0, 1]];
    const la = lgD(d.a), lb = lgD(d.b);
    let num = 0, den = 0, num0 = 0;
    for (const [z, w] of N) {
      const dz = sigma * z, pa = sgD(la + dz), pb = sgD(lb - dz);
      let L = 1;
      setsJoues.forEach(([x, y], k) => {
        const s_a = setsJoues.slice(0, k).filter(([u, v]) => u > v).length, s_b = k - s_a;
        const cible = (s_a === sg - 1 && s_b === sg - 1) ? tbF : 7;
        L *= setIssues(pa, pb, premiers[k], cible).get(`${x},${y}`) || 0;
      });
      L *= atteindre(pa, pb, ga, gb, premierSet);
      const v = matchDepuis(pa, pb, sa, sb, ga, gb, premierSet, pts, sg, tbF);
      num += w * L * v; den += w * L; num0 += w * v;
    }
    return { p: den > 0 ? num / den : num0, p0: num0 };
  }
  // « 6-4 3-6 », jeux « 2-1 », points « 30-15 » / « 40-AV » / tie-break « 5-4 »
  function lireScore(sets, jeux, points) {
    const paire = t => { const m = String(t || '').trim().match(/^(\d+)\s*[-–]\s*(\d+)$/); return m ? [Number(m[1]), Number(m[2])] : null; };
    const S = String(sets || '').trim() ? String(sets).trim().split(/\s+/).map(paire) : [];
    if (S.some(x => !x)) return { erreur: 'Sets terminés : écrivez par exemple « 6-4 3-6 ».' };
    const J = String(jeux || '').trim() ? paire(jeux) : [0, 0];
    if (!J) return { erreur: 'Jeux du set en cours : écrivez par exemple « 2-1 ».' };
    let P = [0, 0];
    const t = String(points || '').trim().toUpperCase();
    if (t) {
      if (J[0] === 6 && J[1] === 6) { P = paire(t); if (!P) return { erreur: 'Tie-break : points, par exemple « 5-4 ».' }; }
      else {
        const V = { 0: 0, 15: 1, 30: 2, 40: 3, AV: 4, A: 4, AD: 4 };
        const m = t.match(/^(\w+)\s*[-–]\s*(\w+)$/);
        if (!m || !(m[1] in V) || !(m[2] in V)) return { erreur: 'Points : écrivez par exemple « 30-15 » ou « 40-AV ».' };
        P = [V[m[1]], V[m[2]]];
        if (P[0] === 4) P = [4, 3]; if (P[1] === 4) P = [3, 4];
      }
    }
    return { sets: S, jeux: J, points: P };
  }
  function directBlock(m, noeuds, ouverts) {
    if (!m || !m.direct) return '';
    const id = `${m.uid}|direct`;
    const nc = n => esc(String(n || '').split(' ').slice(-1)[0]);
    return `<details class="rg-eval rg-sim rg-direct" data-sim="${esc(id)}"${ouverts && ouverts.has(id) ? ' open' : ''}><summary>En direct : le % depuis le score</summary>
      <div class="rg-direct-form" data-uid="${esc(m.uid)}">
        <label>Sets terminés <small>(${nc(m.home)} d'abord)</small><input type="text" inputmode="numeric" data-d="sets" placeholder="ex. 6-4 3-6"></label>
        <label>Jeux du set en cours<input type="text" inputmode="numeric" data-d="jeux" placeholder="ex. 2-1"></label>
        <label>Points du jeu en cours<input type="text" data-d="points" placeholder="ex. 30-15, 40-AV ; tie-break : 5-4"></label>
        <fieldset><legend>Au service</legend><label><input type="radio" name="srv-${esc(m.uid)}" value="home" checked> ${nc(m.home)}</label><label><input type="radio" name="srv-${esc(m.uid)}" value="away"> ${nc(m.away)}</label></fieldset>
        <button type="button" data-direct="${esc(m.uid)}">Calculer</button>
        <div class="rg-direct-res mini" aria-live="polite"></div>
      </div>
      <p class="mini">Calcul exact, sans tirage au hasard : la forme du jour est revue d'après le score (un joueur qui mène nettement est sans doute dans un bon jour), puis la suite du match est jouée depuis le point exact. Version : ${m.direct.version === 'combinaison' ? 'simulation + Elo' : 'simulation'}.</p></details>`;
  }
  function directResultat(m, noeuds, form) {
    const r = lireScore(form.sets, form.jeux, form.points);
    if (r.erreur) return `<span class="bad">${esc(r.erreur)}</span>`;
    const x = enDirect(m.direct, noeuds, r.sets, r.jeux[0], r.jeux[1], form.homeSert, r.points);
    const nc = n => esc(String(n || '').split(' ').slice(-1)[0]);
    const fav = x.p >= 0.5;
    const pv = fav ? x.p : 1 - x.p;
    return `<b>${fav ? nc(m.home) : nc(m.away)}</b> ${pcCote(pv)} <span class="detail">sans revoir la forme du jour : ${nc(m.home)} ${pcCote(x.p0)}</span>`;
  }

  // 22/10/2026 — point 9 : le modèle se trompe-t-il de confiance ? (favori annoncé à X %, gagne combien ?)
  const VERSIONS_LIB = [['combinaison', 'Simulation + Elo'], ['simulation', 'Simulation'], ['stats_seules', 'Classement Elo'], ['stats_plus_marche', 'Cote Pinnacle']];
  function calibrationBlock(B) {
    const C = B && B.calibration;
    if (!C) return '';
    const vers = VERSIONS_LIB.filter(([k]) => (C[k] || []).length);
    if (!vers.length) return '';
    const tranches = [...new Set(vers.flatMap(([k]) => C[k].map(x => x.tranche)))];
    const cell = (k, t) => { const x = (C[k] || []).find(y => y.tranche === t); return x ? `${nf(x.reel, 0)} % <small>(${nf(x.n, 0)})</small>` : '—'; };
    const PC = B.par_circuit || {};
    const circ = Object.keys(PC);
    const pcell = b => (b && b.n ? `${nf(b.reussite_pct, 1)} % <small>(${nf(b.n, 0)})</small>` : '—');
    return `<details class="rg-eval"><summary>Le % annoncé tient-il ? (calibration sur les matchs joués)</summary>
      <div class="table-wrap rg-table"><table><thead><tr><th>Favori annoncé à</th>${vers.map(([, l]) => `<th>${l} : gagne</th>`).join('')}</tr></thead>
      <tbody>${tranches.map(t => `<tr><td>${esc(t)}</td>${vers.map(([k]) => `<td>${cell(k, t)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
      <p class="mini">Bien réglé : un favori annoncé entre 60 et 70 % gagne environ 65 fois sur 100. Plus bas, le modèle est trop sûr de lui ; plus haut, pas assez. Entre parenthèses : nombre de matchs.</p>
      ${circ.length ? `<div class="table-wrap rg-table"><table><thead><tr><th>Circuit</th>${vers.map(([, l]) => `<th>${l}</th>`).join('')}</tr></thead>
      <tbody>${circ.map(c => `<tr><td>${esc(c)}</td>${vers.map(([k]) => `<td>${pcell(PC[c][k])}</td>`).join('')}</tr>`).join('')}</tbody></table></div><p class="mini">Vainqueurs trouvés par circuit.</p>` : ''}</details>`;
  }

  // 22/10/2026 — PRÉDIT / RÉEL : chaque match joué, ce qu'on avait annoncé (1re prédiction) contre
  // ce qui s'est passé. Tout est aussi gardé dans simulateur/journal_pronostics (chaque passage).
  const VERSION_LIB = { combinaison: 'Simulation + Elo', simulation: 'Simulation', stats: 'Classement Elo', marche: 'Cote Pinnacle' };
  function resultatsBlock(R, ouvert) {
    if (!R || !R.matchs) return '';
    const L = R.matchs;
    if (!L.length) return '<details class="rg-eval"><summary>Prédit / réel</summary><p class="mini">Aucun match joué avec son résultat pour l\'instant.</p></details>';
    const nc = n => esc(String(n || '').split(' ').slice(-1)[0]);
    const ok = v => (v === true ? '<span class="good">✓</span>' : v === false ? '<span class="bad">✗</span>' : '·');
    const principal = m => ['combinaison', 'simulation', 'stats'].find(k => m.premier && m.premier[k]);
    const resume = Object.keys(VERSION_LIB).map(k => {
      const g = L.filter(m => m.premier && m.premier[k] && m.premier[k].vainqueur_juste != null);
      if (!g.length) return '';
      const j = g.filter(m => m.premier[k].vainqueur_juste).length;
      return `<div><small>${VERSION_LIB[k]}</small><b>${nf(j, 0)}/${nf(g.length, 0)}</b><small>vainqueurs trouvés</small></div>`;
    }).join('');
    const lignes = L.slice(0, 60).map(m => {
      const k = principal(m); const v = k ? m.premier[k] : null; const r = m.reel || {};
      const pin = m.premier && m.premier.marche;
      const fav = v ? (v.p_home >= 0.5 ? m.home : m.away) : null;
      const pf = v ? Math.max(v.p_home, 1 - v.p_home) : null;
      const prevu = v ? `<b>${nc(fav)}</b> ${pcCote(pf)}${v.score_prevu ? `<span class="detail">score : ${esc(v.score_prevu)}</span>` : (v.sets_prevus ? `<span class="detail">sets : ${esc(v.sets_prevus)}</span>` : '')}<span class="detail">${esc(VERSION_LIB[k])}</span>` : '—';
      const reel = `<b>${nc(r.gagnant === 'home' ? m.home : m.away)}</b>${r.score ? `<span class="detail">${esc(r.score)}</span>` : (r.sets ? `<span class="detail">sets : ${esc(r.sets)}</span>` : '')}`;
      const juste = v ? `${ok(v.vainqueur_juste)} vainqueur${v.sets_justes != null ? `<br>${ok(v.sets_justes)} sets` : ''}${v.score_juste != null ? `<br>${ok(v.score_juste)} score` : ''}` : '—';
      return `<tr><td>${esc(String(m.debut).slice(5, 10).split('-').reverse().join('/'))} · ${esc(m.home)} – ${esc(m.away)}<span class="detail">${esc(m.tournoi || '')}</span></td><td>${prevu}</td><td>${pin ? `${nc(pin.p_home >= 0.5 ? m.home : m.away)} ${pcCote(Math.max(pin.p_home, 1 - pin.p_home))}` : '—'}</td><td>${reel}</td><td>${juste}</td></tr>`;
    }).join('');
    return `<details class="rg-eval" id="rgResultats"${ouvert ? ' open' : ''}><summary>Prédit / réel (${nf(L.length, 0)} matchs joués)</summary>
      <div class="rg-kpis">${resume}</div>
      <div class="table-wrap rg-table"><table><thead><tr><th>Match</th><th>Prédit avant le match</th><th>Pinnacle</th><th>Résultat</th><th>Juste ?</th></tr></thead><tbody>${lignes}</tbody></table></div>
      <p class="mini">Première prédiction de chaque match, jamais retouchée. Version affichée : Simulation + Elo quand elle existait, sinon la simulation, sinon le classement Elo. Le score en jeux arrive avec la feuille de match (collecte de 4 h 41 et 16 h 41 UTC). Tout est enregistré : chaque passage dans simulateur/journal_pronostics, chaque match joué dans live/pronostics_resultats.json.</p></details>`;
  }

  // 22/10/2026 — EXPLORATEUR DES PRONOSTICS : croiser les résultats de l'algorithme avec les critères
  // (circuit, surface, format, niveau, tour, expérience, confiance, accord simulation / Elo, période)
  // sur les ~9 000 matchs ATP/WTA 2024 → 2026 rejoués avant l'heure. Une piste trouvée ici n'est qu'une
  // CANDIDATE : elle se gèle, puis se juge sur les matchs suivants.
  const XP_VERSIONS = [['simulation', 'Simulation'], ['combinaison', 'Simulation + Elo'], ['elo', 'Classement Elo'], ['pinnacle', 'Cote Pinnacle']];
  const XP_NIVEAU = n => (n === 'G' ? 'Grand Chelem' : n === 'M' || n === 'PM' ? 'Masters / 1000' : n === 'F' ? 'Finales' : n === 'D' ? 'Coupe Davis / BJK' : 'Autres tournois');
  const XP_TOUR = t => (t >= 9 ? 'Demi / finale' : t >= 7 ? '8es / quarts' : t >= 5 ? '1er–2e tour (64, 32)' : '1er tour (128)');
  const XP_EXP = n => (n < 30 ? 'moins de 30 matchs' : n < 100 ? '30 à 100 matchs' : 'plus de 100 matchs');
  const XP_CRITERES = {
    circuit: ['Circuit', x => x.circuit],
    surface: ['Surface', x => x.surface],
    format: ['Format', x => (x.bo === 5 ? '5 sets' : '3 sets')],
    niveau: ['Niveau', x => XP_NIVEAU(x.niveau)],
    tour: ['Tour', x => XP_TOUR(x.tour)],
    experience: ['Expérience du moins rodé', x => XP_EXP(x.matchs_min)],
    confiance: ['Confiance de la simulation', x => { const c = Math.max(x.simulation, 1 - x.simulation); return c < 0.6 ? '50–60 %' : c < 0.7 ? '60–70 %' : c < 0.8 ? '70–80 %' : '80 % et plus'; }],
    accord: ['Simulation et Elo', x => ((x.simulation > 0.5) === (x.elo > 0.5) ? "d'accord sur le vainqueur" : 'en désaccord')],
    periode: ['Période', (x, d) => (x.date < d ? 'apprentissage (2024)' : 'jugement (2025 →)')],
  };
  function xpLignes(doc) {
    if (!doc || !doc.lignes) return [];
    if (doc._L) return doc._L;
    const c = doc.colonnes;
    doc._L = doc.lignes.map(r => Object.fromEntries(c.map((k, i) => [k, r[i]])));
    return doc._L;
  }
  function xpStats(L, v) {
    const g = L.filter(x => fin(x[v]));
    const n = g.length;
    if (!n) return { n: 0 };
    const ok = g.reduce((a, x) => a + (x[v] > 0.5 ? 1 : x[v] === 0.5 ? 0.5 : 0), 0) / n;
    const ll = -g.reduce((a, x) => a + Math.log(Math.min(Math.max(x[v], 1e-6), 1 - 1e-6)), 0) / n;
    const se = Math.sqrt(ok * (1 - ok) / n);
    return { n, ok, lo: ok - 1.96 * se, hi: ok + 1.96 * se, ll };
  }
  function xpFiltrer(doc, f) {
    const d = doc.debut_jugement || '2025-01-01';
    return xpLignes(doc).filter(x => Object.entries(f || {}).every(([k, val]) => !val || XP_CRITERES[k][1](x, d) === val));
  }
  function xpScan(doc, f, nMin = 150) {
    // chaque valeur de chaque critère (dans le filtre courant) : la simulation y trouve-t-elle le vainqueur
    // plus ou moins souvent que l'Elo, et que d'habitude ? Trié par écart à la moyenne de la simulation.
    const d = doc.debut_jugement || '2025-01-01';
    const base = xpFiltrer(doc, f);
    const ref = xpStats(base, 'simulation');
    const out = [];
    for (const [k, [lab, fn]] of Object.entries(XP_CRITERES)) {
      if (f && f[k]) continue;
      const groupes = {};
      base.forEach(x => { const v = fn(x, d); (groupes[v] = groupes[v] || []).push(x); });
      for (const [val, g] of Object.entries(groupes)) {
        if (g.length < nMin) continue;
        const s = xpStats(g, 'simulation'), e = xpStats(g, 'elo');
        out.push({ critere: lab, valeur: val, n: g.length, sim: s, elo: e, ecart: s.ok - ref.ok, vsElo: s.ok - e.ok });
      }
    }
    return out.sort((a, b) => Math.abs(b.vsElo) - Math.abs(a.vsElo)).slice(0, 12);
  }
  function explorateurBlock(doc, f, ouvert) {
    const head = `<details class="rg-eval" id="rgXp"${ouvert ? ' open' : ''}><summary>Explorateur des pronostics : croiser les résultats avec les critères${doc && doc.lignes ? ` (${nf(doc.lignes.length, 0)} matchs rejoués)` : ''}</summary>`;
    if (!ouvert) return `${head}</details>`;
    if (!doc) return `${head}<p class="mini">Chargement…</p></details>`;
    if (!doc.lignes) return `${head}<p class="mini">Données pas encore produites : lancer « Pronostic - test du modèle ».</p></details>`;
    const d = doc.debut_jugement || '2025-01-01';
    const L = xpLignes(doc);
    const sel = Object.entries(XP_CRITERES).map(([k, [lab, fn]]) => {
      const vals = [...new Set(L.map(x => fn(x, d)))].filter(v => v != null).sort();
      return `<label>${esc(lab)}<select data-xp="${k}"><option value="">tous</option>${vals.map(v => `<option${f && f[k] === v ? ' selected' : ''}>${esc(v)}</option>`).join('')}</select></label>`;
    }).join('');
    const G = xpFiltrer(doc, f);
    const pct = x => `${nf(100 * x, 1)} %`;
    const rows = XP_VERSIONS.map(([v, lab]) => { const s = xpStats(G, v); return s.n ? `<tr><td>${lab}</td><td>${pct(s.ok)} <small>[${nf(100 * s.lo, 1)} ; ${nf(100 * s.hi, 1)}]</small></td><td>${nf(s.ll, 3)}</td><td>${nf(s.n, 0)}</td></tr>` : ''; }).join('');
    const scan = xpScan(doc, f);
    const sc = scan.map(z => `<tr><td>${esc(z.critere)} : <b>${esc(z.valeur)}</b></td><td>${pct(z.sim.ok)}</td><td>${pct(z.elo.ok)}</td><td class="${z.vsElo > 0 ? 'good' : 'bad'}">${z.vsElo > 0 ? '+' : '−'}${nf(Math.abs(100 * z.vsElo), 1)} pt</td><td>${nf(z.n, 0)}</td></tr>`).join('');
    return `${head}<div class="rg-xp-filtres">${sel}</div>
      <p class="mini">${nf(G.length, 0)} matchs dans ce filtre · vainqueur trouvé quand la version donne plus de 50 % au vrai vainqueur.</p>
      <div class="table-wrap rg-table"><table><thead><tr><th>Version</th><th>Vainqueurs trouvés <small>(IC 95 %)</small></th><th>Log loss</th><th>Matchs</th></tr></thead><tbody>${rows}</tbody></table></div>
      ${sc ? `<h5>Où la simulation fait mieux ou moins bien que l'Elo (dans ce filtre, 150 matchs au moins)</h5>
      <div class="table-wrap rg-table"><table><thead><tr><th>Critère</th><th>Simulation</th><th>Elo</th><th>Écart</th><th>Matchs</th></tr></thead><tbody>${sc}</tbody></table></div>` : ''}
      <p class="mini">Exploration : en regardant beaucoup de cases, certaines sortent du lot par hasard. Une piste n'est qu'une candidate tant qu'elle n'a pas été gelée puis confirmée sur des matchs joués APRÈS le gel (comme H13–H20). Le filtre « Période » permet de vérifier qu'un écart vu en 2024 tient en 2025 →.</p></details>`;
  }

  function pronosticsBlock(P, B, ouverts) {
    if (!P || !P.matchs) return '';
    const pc = v => (fin(v) ? `${nf(100 * v, 0)} %` : '—');
    const heure = d => { try { return new Date(`${d}Z`).toLocaleString('fr-FR', { weekday: 'short', hour: '2-digit', minute: '2-digit' }); } catch { return esc(d); } };
    const nomCourt = n => esc(String(n || '').split(' ').slice(-1)[0]);
    const ligne = (lab, v, m) => {
      if (!v) return `<tr><td>${lab}</td><td colspan="3" class="mini">Pinnacle ne cote pas encore ce match</td></tr>`;
      const fav = v.p_home >= 0.5;
      const sets = Object.entries(v.sets || {}).map(([k, x]) => `${esc(k)} ${pcCote(x)}`).join('<br>');
      const scores = (v.scores_probables || []).map(([s, p]) => `${esc(s)} <small>${pcCote(p)}</small>`).join('<br>');
      const rem = v.remontee ? `<span class="detail">gagne après avoir perdu le 1er set : ${nomCourt(m.home)} ${pcCote(v.remontee.home)} · ${nomCourt(m.away)} ${pcCote(v.remontee.away)}</span>` : '';
      const pv = fav ? v.p_home : 1 - v.p_home;
      return `<tr><td>${lab}</td><td><b>${fav ? nomCourt(m.home) : nomCourt(m.away)}</b> ${pcCote(pv)}<span class="detail">adversaire : ${coteJuste(1 - pv)}</span><span class="detail">${sets}</span></td><td>${scores}${rem}</td><td>${nf(v.jeux_moyen, 1)}</td></tr>`;
    };
    const kpi = (lab, b) => `<div><small>${lab}</small><b>${b && b.n ? `${nf(b.reussite_pct, 1)} %` : '—'}</b><small>${b && b.n ? `${nf(b.n, 0)} matchs joués` : 'pas encore de match joué'}</small></div>`;
    const T = (B && B.tous) || {}, S = (B && B['7_derniers_jours']) || {};
    const F = B && B.match_simule_contre_feuille;
    const LIB = { aces: 'Aces', doubles_fautes: 'Doubles fautes', premiere_pct: '% de 1re balle', gagnes_1re_pct: '% gagnés 1re', gagnes_2e_pct: '% gagnés 2e', breaks: 'Breaks', jeux: 'Jeux gagnés', total_jeux: 'Total de jeux' };
    const suiviF = F && F.n ? `<h5>Match simulé contre la vraie feuille (${nf(F.n, 0)} matchs joués)</h5><div class="table-wrap rg-table"><table><thead><tr><th>Statistique</th><th>Prévu</th><th>Réel</th><th>Écart moyen</th><th>Dans la fourchette 80 %</th></tr></thead><tbody>${Object.entries(F.stats || {}).map(([k, x]) => `<tr><td>${LIB[k] || esc(k)}</td><td>${nf(x.prevu, 1)}</td><td>${nf(x.reel, 1)}</td><td>${nf(x.ecart_moyen, 1)}</td><td>${nf(x.dans_fourchette_pct, 0)} %</td></tr>`).join('')}</tbody></table></div><p class="mini">Feuille prévue avant le match (premier pronostic, jamais retouché) contre la feuille réelle collectée après. Une fourchette bien réglée contient le réel environ 8 fois sur 10.</p>`
      : (P.simulations ? '<p class="mini">Match simulé contre la vraie feuille : en attente des premiers matchs joués avec leur feuille.</p>' : '');
    const cartes = P.matchs.map(m => `<div class="rg-pron"><div class="mini">${heure(m.debut)} · ${esc(m.tournoi)} · ${esc(m.surface)}${m.meilleur_des === 5 ? ' · 5 sets' : ''}</div>
        <div class="rg-pron-j"><b>${esc(m.home)}</b> – <b>${esc(m.away)}</b></div>
        <div class="table-wrap rg-table"><table><thead><tr><th></th><th>Vainqueur · sets <small>(% · cote juste)</small></th><th>Scores les plus probables (sur ~1 500 possibles)</th><th>Jeux</th></tr></thead>
        <tbody>${m.combinaison ? ligne(`<b>Simulation + Elo</b><span class="detail">les deux % mélangés, puis le match joué à ce niveau</span>`, m.combinaison, m) : ''}${m.simulation ? ligne(`<b>Simulation</b><span class="detail">${nf((P.simulations || 0), 0)} matchs joués</span>`, m.simulation, m) : ''}${ligne('Classement Elo', m.stats, m)}${ligne('Cote Pinnacle', m.marche, m)}</tbody></table></div>${facteursBlock(m)}${directBlock(m, P.noeuds_forme, ouverts)}${simuleBlock(m, ouverts)}${m.cles ? `<div class="rg-serv-liens">Profil de service : <button type="button" data-serv-key="${esc(m.cles[0])}">${nomCourt(m.home)}</button> <button type="button" data-serv-key="${esc(m.cles[1])}">${nomCourt(m.away)}</button></div>` : ''}</div>`).join('');
    return `<details class="rg-eval" open><summary>Pronostics du jour (${nf(P.matchs.length, 0)} matchs dans les ${nf(P.horizon_h, 0)} h)</summary>
      <p class="mini"><b>Simulation</b> : chaque match est joué ${nf(P.simulations || 5000, 0)} fois point par point avec les seules statistiques des deux joueurs — 1re balle, aces, doubles fautes, points gagnés derrière la 1re et la 2e, qualité de retour (profils au ${esc(P.profils_au || '—')}) — et la part des simulations gagnées donne le pourcentage. Pour comparaison : <b>classement Elo</b> (résultats seuls) et <b>cote Pinnacle</b> (marge retirée), joués dans le même moteur. Le premier pronostic de chaque match est gardé tel quel : les compteurs portent sur lui. Chaque pourcentage est aussi lu en <b>cote juste</b> (1 / probabilité, sans marge).${(P.facteurs_adoptes || []).length ? ` Facteurs du match retenus par le test : ${P.facteurs_adoptes.map(g => esc(FACTEURS_LIB[g] || g)).join(', ')}.` : ''}${P.combinaison && fin(P.combinaison.simulation) ? ` <b>Simulation + Elo</b> : poids ${nf(100 * P.combinaison.simulation / (P.combinaison.simulation + P.combinaison.elo), 0)} % simulation, appris sur ${esc(P.combinaison.source || 'l\'archive 2024–2026')} ; ré-appris chaque lundi.` : ''}${P.reglage_simulation && P.reglage_simulation.jeux > 0 ? ' La simulation apprend aussi des scores des matchs sans statistiques détaillées (ITF, Challenger…).' : ''}${P.reglage_simulation && P.reglage_simulation.resultats > 0 ? ' Elle apprend aussi de qui a gagné, match après match (une surprise corrige plus qu\'une victoire attendue).' : ''}</p>
      <div class="rg-kpis">${(P.combinaison || (T.combinaison && T.combinaison.n)) ? kpi('Réussite simulation + Elo', T.combinaison) : ''}${kpi('Réussite simulation', T.simulation)}${kpi('Réussite Elo', T.stats_seules)}${kpi('Réussite Pinnacle', T.stats_plus_marche)}${(P.combinaison || (T.combinaison && T.combinaison.n)) ? kpi('7 jours, simulation + Elo', S.combinaison) : ''}${kpi('7 jours, simulation', S.simulation)}${kpi('7 jours, Elo', S.stats_seules)}${kpi('7 jours, Pinnacle', S.stats_plus_marche)}</div>
      ${calibrationBlock(B)}
      ${suiviF}
      ${cartes || '<p class="mini">Aucun match dans les prochaines heures.</p>'}
    </details>`;
  }

  /** H19 « valeur contre Pinnacle juste » : suivi gelé + grille rétrospective (valeur.json). */
  function valeurBlock(V) {
    if (!V || !V.h19) return '';
    const H = V.h19, P = H.prospectif, R = H.retrospectif;
    const cl = s => (s && s.clv && fin(s.clv.mean) ? `${sg(s.clv.mean, 2)}<span class="detail">${ic(s.clv.ci)}</span>` : '—');
    const roi = s => (s && s.roi && fin(s.roi.mean) ? `${sg(s.roi.mean)}<span class="detail">${ic(s.roi.ci)}</span>` : '—');
    const pers = s => (s && fin(s.persistance) ? `${nf(100 * s.persistance, 0)} %` : '—');
    const tab = (rows, first) => `<div class="table-wrap rg-table"><table><thead><tr><th>${first}</th><th>Paris</th><th>CLV · IC95</th><th>ROI · IC95</th><th>Prix encore là à la clôture</th></tr></thead><tbody>${rows.map(g => `<tr><td>${esc(g.groupe ?? g.case)}</td><td>${nf(g.n, 0)}</td><td>${cl(g)}</td><td>${roi(g)}</td><td>${pers(g)}</td></tr>`).join('')}</tbody></table></div>`;
    const D = H.decoupes_retrospectives || {};
    const cases = ((V.grille || {}).cases || []).filter(c => c.n >= 30);
    const gtab = `<div class="table-wrap rg-table"><table><thead><tr><th>Case</th><th>Paris</th><th>CLV · IC95</th><th>p Holm</th><th>Mois CLV+</th><th>ROI</th></tr></thead><tbody>${cases.map(c => `<tr><td>${esc(c.case)}</td><td>${nf(c.n, 0)}</td><td>${cl(c)}</td><td class="${fin(c.p_holm) && c.p_holm < 0.05 ? 'good' : ''}">${fin(c.p_holm) ? nf(c.p_holm, 4) : '—'}</td><td>${esc(c.mois_clv_positif || '—')}</td><td>${roi(c)}</td></tr>`).join('')}</tbody></table></div>`;
    const gelOk = H.gel && H.gel.etat === 'intact';
    return `<details class="rg-eval" open><summary>H19 — valeur contre Pinnacle juste (gelée le ${esc(H.regle.gele_le)})</summary>
      <p class="mini">Règle : meilleur book jouable (hors Pinnacle, cote de moins de ${H.regle.age_max_min} min, commission déduite) qui paie de +${nf(H.regle.ecart_min_pct, 0)} % à +${nf(H.regle.ecart_max_pct, 0)} % au-dessus de la cote Pinnacle juste, à 24 h, 6 h, 1 h ou 10 min ; un pari par joueur et par match. Jugée sur la CLV, matchs commençant après le gel, cible ${nf(H.regle.cible_n, 0)}. Gel ${gelOk ? '<b class="good">intact</b>' : '<b class="bad">' + esc(H.gel && H.gel.etat) + '</b>'}.</p>
      <div class="rg-kpis"><div><small>Suivi prospectif</small><b>${nf(P.n, 0)} / ${nf(H.regle.cible_n, 0)}</b><small>${esc(P.verdict)}</small></div>
        <div><small>CLV prospective</small><b>${P.clv && fin(P.clv.mean) ? sg(P.clv.mean, 2) : '—'}</b><small>${ic(P.clv && P.clv.ci)}</small></div>
        <div><small>ROI prospectif</small><b>${P.roi && fin(P.roi.mean) ? sg(P.roi.mean) : '—'}</b><small>${nf(P.regles, 0)} réglés</small></div></div>
      ${H.alertes_direct && H.alertes_direct.lignes ? `<p class="mini">Alertes en direct : ${nf(H.alertes_direct.envoyees, 0)} envoyées sur ${nf(H.alertes_direct.lignes, 0)} détections ; ${nf(H.alertes_direct.communes_avec_le_lab, 0)} correspondent à un pari du suivi du Lab (${nf(H.alertes_direct.paris_lab_meme_periode, 0)} sur la même période). Le suivi officiel reste celui des courbes de tous les matchs.</p>` : ''}
      <h5>Avant le gel (a servi à choisir la règle : ne compte pas)</h5>
      <p class="mini">${nf(R.n, 0)} paris · CLV ${sg(R.clv && R.clv.mean, 2)} ${ic(R.clv && R.clv.ci)} · ROI ${sg(R.roi && R.roi.mean)} · mois à CLV positive ${esc(R.mois_clv_positif || '—')} · prix encore là à la clôture ${pers(R)}</p>
      ${D.persistance ? `<h5>Le book a-t-il corrigé son prix ?</h5>${tab(D.persistance, 'Prix à la clôture du book')}<p class="mini">Un prix qui disparaît avant la clôture = le book s'est aligné : l'écart était une vraie erreur de prix. Un prix encore là à la clôture = souvent Pinnacle qui s'est rapproché du book.</p>` : ''}
      ${D.age_cote ? `<h5>Âge de la cote au moment de la décision</h5>${tab(D.age_cote, 'Âge')}` : ''}
      ${D.ecart ? `<h5>Taille de l'écart</h5>${tab(D.ecart, 'Écart')}` : ''}
      ${D.horizon ? `<h5>Horizon</h5>${tab(D.horizon, 'Horizon')}` : ''}
      ${D.book ? `<h5>Book</h5>${tab(D.book.filter(g => g.n >= 5), 'Book')}` : ''}
      <h5>Grille d'étude (exploratoire, corrigée de Holm sur ${nf(V.grille && V.grille.cases_testees, 0)} cases)</h5>${gtab}
      <p class="mini">La grille sert à comprendre H19, jamais à la modifier : une case qui brille ici devra être gelée à son tour et jugée sur les matchs suivants.</p>
    </details>`;
  }

  function evaluation(ev) {
    if (!ev) return '';
    const L = ev.lectures || {};
    const tous = (L.par_verdict || []).filter(v => v.horizon === 'tous');
    const corr = L.correlation;
    const lecture = !fin(corr) ? 'Pas encore assez de lectures.'
      : Math.abs(corr) < 0.1 ? `Corrélation excès prédit / excès réalisé : <b>${nf(corr, 3)}</b>. Les lectures décrivent le passé mais <b>ne prédisent presque rien</b> du match suivant.`
        : corr > 0 ? `Corrélation <b>${nf(corr, 3)}</b> : les lectures portent une information, à confirmer par tranche ci-dessous.`
          : `Corrélation <b>${nf(corr, 3)}</b> : les lectures vont à l'envers — à examiner.`;
    const tv = tous.map(v => `<tr><td>${esc(v.verdict)}</td><td>${nf(v.lignes, 0)}</td><td>${summaryCell(v.exces_realise)}</td><td>${summaryCell(v.clv_realisee)}</td><td>${summaryCell(v.roi_jouable)}</td></tr>`).join('');
    const tq = (L.par_quintile || []).map(q => `<tr><td>${q.quintile}</td><td>${sg(q.exces_predit_moyen)}</td><td>${summaryCell(q.exces_realise)}</td><td>${summaryCell(q.roi_jouable)}</td></tr>`).join('');
    const F = ev.fiabilite_cloture || {};
    const ft = (rows, title) => (rows && rows.length ? `<h5>${esc(title)}</h5><div class="table-wrap rg-table"><table><thead><tr><th>Groupe</th><th>n</th><th>Annoncé (juste)</th><th>Annoncé brut</th><th>Gagné</th><th>Écart · IC95</th><th>État</th></tr></thead><tbody>${rows.map(g => `<tr><td>${esc(g.groupe)}</td><td>${nf(g.n, 0)}</td><td>${nf(100 * g.proba_juste, 1)} %</td><td>${nf(100 * g.proba_brute, 1)} %</td><td>${nf(100 * g.victoires, 1)} %</td><td>${sg(g.ecart_pts, 1, ' pts')}<span class="detail">[${sg(g.ic95_pts[0], 1, '')} ; ${sg(g.ic95_pts[1], 1, '')}]</span></td><td class="${g.etat === 'conforme' ? '' : 'bad'}">${esc(g.etat)}</td></tr>`).join('')}</tbody></table></div>` : '');
    const coh = (rows, key) => `<div class="table-wrap rg-table"><table><thead><tr><th>${key === 'hypothese' ? 'Hypothèse' : 'Entrée'}</th><th>Paris réglés</th><th>ROI attendu (CLV)</th><th>ROI réel</th><th>z</th><th>État</th></tr></thead><tbody>${rows.map(c => `<tr><td>${esc(c[key])}</td><td>${nf(c.n, 0)}</td><td>${sg(c.roi_attendu)}</td><td>${sg(c.roi_reel)}</td><td>${nf(c.z, 2)}</td><td class="${c.etat === 'la CLV ne se transforme pas en gains' ? 'bad' : c.etat === 'cohérent' ? 'good' : ''}">${esc(c.etat)}</td></tr>`).join('')}</tbody></table></div>`;
    const cm = (ev.coherence_matchs || []).filter(c => c.horizon === 'tous');
    return `<details class="rg-eval"><summary>Évaluation de tous les matchs : lectures, clôture Pinnacle, CLV → gains</summary>
      <h4>Les lectures « matchs similaires passés », vérifiées après coup</h4>
      <p class="mini">${nf(L.lignes_lues, 0)} lectures rejouées (chaque match, chaque joueur, chaque horizon), avec seulement les matchs connus à ce moment-là. « Excès réalisé » = CLV du match moins celle des matchs de même horizon et même cote.</p>
      <p>${lecture}</p>
      <div class="table-wrap rg-table"><table><thead><tr><th>Lecture</th><th>Lignes</th><th>Excès réalisé</th><th>CLV réalisée</th><th>ROI jouable</th></tr></thead><tbody>${tv}</tbody></table></div>
      ${tq ? `<h5>Par quintile de l'excès prédit (1 = le plus « sur-coté », 5 = le plus « sous-coté »)</h5><div class="table-wrap rg-table"><table><thead><tr><th>Quintile</th><th>Excès prédit</th><th>Excès réalisé</th><th>ROI jouable</th></tr></thead><tbody>${tq}</tbody></table></div><p class="mini">Si les lectures servaient, l'excès réalisé monterait régulièrement du quintile 1 au quintile 5.</p>` : ''}
      ${victoires(L.victoires)}
      <h4>La clôture Pinnacle est-elle juste ?</h4>
      <p class="mini">Notre CLV suppose que la clôture Pinnacle sans marge donne la vraie probabilité. Ici on le vérifie sur ${nf(F.cotes_jugees, 0)} matchs (le favori à la clôture). « Annoncé brut » = 1/cote, marge incluse : c'est ce qu'utilise une « CLV brute ».</p>
      ${ft(F.par_tranche, 'Par probabilité annoncée')}${ft(F.par_circuit, 'Par circuit')}${ft(F.par_surface, 'Par surface')}
      <h4>La CLV se transforme-t-elle en gains ?</h4>
      <p class="mini">Avec une clôture juste, le gain attendu d'un pari = sa CLV (sans marge). On compare au P&amp;L réel ; |z| &lt; 2 = l'écart est du bruit. Une « CLV brute » (marge incluse) peut monter pendant que le bankroll baisse : la marge n'est jamais retirée.</p>
      <h5>Tous les matchs collectés, tous horizons</h5>${coh(cm, 'entree')}
      <h5>Détections du suivi officiel</h5>${coh(ev.coherence_hypotheses || [], 'hypothese')}
    </details>`;
  }

  function render() {
    const host = $('registreBody');
    if (!host) return;
    if (state.err) { host.innerHTML = `<p class="notice warn">${esc(state.err)}</p>`; return; }
    if (!state.index) { host.innerHTML = '<p class="mini">Chargement du registre…</p>'; return; }
    const cur = state.months[state.mois];
    const doc = cur.doc;
    const list = filterMatches(cur.list, state.f);
    const pages = Math.max(1, Math.ceil(list.length / PAGE));
    state.page = Math.min(state.page, pages - 1);
    const shown = list.slice(state.page * PAGE, (state.page + 1) * PAGE);
    const opt = (vals, v) => vals.map(([k, l]) => `<option value="${esc(k)}" ${k === (v || '') ? 'selected' : ''}>${esc(l)}</option>`).join('');
    const circuits = [...new Set(cur.list.map(m => m.circuit))].sort();
    host.innerHTML = `${pronosticsBlock(state.pronoDoc, state.pronoBilan, state.simOpen)}${resultatsBlock(state.pronoResultats, state.simOpen.has('resultats'))}${explorateurBlock(state.xpDoc, state.xpF, state.xpOpen)}${serviceBlock(state.servDoc, state.servQ, state.servKey, state.servOpen)}${valeurBlock(state.valeurDoc)}${croisementsBlock(state.croisDoc)}${delaiBlock(state.delaiDoc)}${evaluation(state.evalDoc)}${booksBlock(state.valeurDoc)}
      <div class="rg-filters">
        <label>Mois<select id="rgMois">${opt([...state.index.mois].reverse().map(x => [x.mois, `${x.mois} (${x.matchs})`]), state.mois)}</select></label>
        <label>Circuit<select id="rgCircuit">${opt([['', 'tous'], ...circuits.map(c => [c, c])], state.f.circuit)}</select></label>
        <label>Alertes<select id="rgAlerte">${opt([['', 'toutes'], ['avec', 'avec alerte'], ['sans', 'sans alerte'], ['H', 'H13–H18'], ['PUBLIC', 'publique'], ['MOUVEMENT', 'mouvement'], ['COURBES', 'courbes']], state.f.alerte)}</select></label>
        <label>Lecture<select id="rgLecture">${opt([['', 'toutes'], ['sous-coté', 'sous-coté'], ['sur-coté', 'sur-coté']], state.f.lecture)}</select></label>
        <label>Courbes<select id="rgCourbe">${opt([['', 'tous'], ['avec', 'avec courbes'], ['sans', 'alertes seules']], state.f.courbe)}</select></label>
        <label>Résultat<select id="rgResultat">${opt([['', 'tous'], ['avec', 'avec résultat'], ['sans', 'sans résultat']], state.f.resultat)}</select></label>
        <label class="rg-q">Joueur ou tournoi<input id="rgQ" type="search" value="${esc(state.f.q || '')}" placeholder="ex. Sinner, Roanne…"></label>
      </div>
      <p class="mini">${nf(list.length, 0)} match(s) sur ${nf(cur.list.length, 0)} en ${esc(state.mois)} · ${nf(state.index.matchs, 0)} au total depuis juin. Touchez un match pour sa fiche complète.</p>
      ${shown.map(m => row(m, doc)).join('') || '<p class="mini">Aucun match dans ce filtre.</p>'}
      <div class="buttons"><button type="button" id="rgPrev" ${state.page ? '' : 'disabled'}>← Précédent</button><span>${state.page + 1} / ${pages}</span><button type="button" id="rgNext" ${state.page + 1 < pages ? '' : 'disabled'}>Suivant →</button></div>`;
    bind();
  }

  function bind() {
    const set = (id, key, ev = 'change') => { const el = $(id); if (el) el.addEventListener(ev, () => { state.f[key] = el.value; state.page = 0; render(); if (ev === 'input') { const e2 = $(id); if (e2) { e2.focus(); e2.setSelectionRange(e2.value.length, e2.value.length); } } }); };
    set('rgCircuit', 'circuit'); set('rgAlerte', 'alerte'); set('rgLecture', 'lecture'); set('rgResultat', 'resultat'); set('rgCourbe', 'courbe'); set('rgQ', 'q', 'input');
    const mois = $('rgMois');
    if (mois) mois.addEventListener('change', async () => { $('registreBody').insertAdjacentHTML('afterbegin', '<p class="mini">Chargement…</p>'); try { await loadMonth(mois.value); } catch (e) { state.err = e.message; } render(); });
    document.querySelectorAll('#registreBody .rg-sim').forEach(d => d.addEventListener('toggle', () => {
      if (d.open) state.simOpen.add(d.dataset.sim); else state.simOpen.delete(d.dataset.sim);
    }));
    const xp = $('rgXp');
    if (xp) xp.addEventListener('toggle', async () => {
      state.xpOpen = xp.open;
      if (xp.open && !state.xpDoc) { render(); try { state.xpDoc = await gz('./live/explorateur_pronostics.json.gz'); } catch (e) { state.xpDoc = { erreur: e.message }; } render(); }
    });
    document.querySelectorAll('#registreBody [data-xp]').forEach(el => el.addEventListener('change', () => {
      state.xpF = Object.assign({}, state.xpF, { [el.dataset.xp]: el.value }); render();
      const d2 = $('rgXp'); if (d2 && d2.scrollIntoView) d2.scrollIntoView({ block: 'start' });
    }));
    const resD = $('rgResultats');
    if (resD) resD.addEventListener('toggle', () => { if (resD.open) state.simOpen.add('resultats'); else state.simOpen.delete('resultats'); });
    const serv = $('rgServ');
    if (serv) serv.addEventListener('toggle', async () => {
      state.servOpen = serv.open;
      if (serv.open && !state.servDoc) { await chargerService(); render(); }
    });
    bindService();
    document.querySelectorAll('#registreBody [data-direct]').forEach(b => b.addEventListener('click', () => {
      const P = state.pronoDoc || {};
      const m = (P.matchs || []).find(x => x.uid === b.dataset.direct);
      const f = b.closest('.rg-direct-form');
      if (!m || !f) return;
      const v = k => (f.querySelector(`[data-d="${k}"]`) || {}).value || '';
      const srv = f.querySelector('input[type="radio"]:checked');
      f.querySelector('.rg-direct-res').innerHTML = directResultat(m, P.noeuds_forme, { sets: v('sets'), jeux: v('jeux'), points: v('points'), homeSert: !srv || srv.value === 'home' });
    }));
    const prev = $('rgPrev'), next = $('rgNext');
    if (prev) prev.addEventListener('click', () => { state.page--; render(); });
    if (next) next.addEventListener('click', () => { state.page++; render(); });
    document.querySelectorAll('#registreBody .rg-head').forEach(b => b.addEventListener('click', () => {
      const u = b.dataset.uid;
      if (state.open.has(u)) state.open.delete(u); else state.open.add(u);
      render();
    }));
  }

  async function start() {
    if (!$('registreBody')) return;
    render();
    try {
      state.index = await json('./live/registre/index.json');
      if (!state.index.mois || !state.index.mois.length) throw new Error('registre vide');
      await loadMonth(state.index.mois[state.index.mois.length - 1].mois);
    } catch (e) { state.err = `Registre indisponible (${e.message}).`; }
    try { state.evalDoc = await json('./live/lectures_profils.json'); } catch { /* évaluation absente : le registre reste lisible */ }
    try { state.valeurDoc = await json('./live/valeur.json'); } catch { /* H19 absente */ }
    try { state.delaiDoc = await json('./live/delai_alertes.json'); } catch { /* étude absente */ }
    try { state.croisDoc = await json('./live/croisements.json'); } catch { /* croisements absents */ }
    try { state.pronoDoc = await json('./live/pronostics.json'); } catch { /* pronostics absents */ }
    try { state.pronoBilan = await json('./live/pronostics_bilan.json'); } catch { /* bilan absent */ }
    try { state.pronoResultats = await json('./live/pronostics_resultats.json'); } catch { /* prédit / réel absent */ }
    render();
  }
  if (hasDoc && typeof module === 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  }
  if (typeof module !== 'undefined') {
    module.exports = { explorateurBlock, xpScan, xpStats, xpFiltrer, resultatsBlock, pronosticsBlock, calibrationBlock, directBlock, directResultat, enDirect, lireScore, facteursBlock, simuleBlock, serviceBlock, serviceInner, ficheService, chercherJoueurs, croisementsBlock, delaiBlock, booksBlock, valeurBlock, victoires, powerFair, decodeMonth, fairRow, bestRow, filterMatches, coherence, lectureOf, effective, evaluation, fiche, row };
  }
})();
