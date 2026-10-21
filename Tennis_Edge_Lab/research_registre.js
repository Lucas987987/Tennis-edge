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
  const state = { index: null, months: {}, mois: null, list: null, f: {}, page: 0, open: new Set(), evalDoc: null, err: null };
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
    host.innerHTML = `${valeurBlock(state.valeurDoc)}${delaiBlock(state.delaiDoc)}${evaluation(state.evalDoc)}${booksBlock(state.valeurDoc)}
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
    render();
  }
  if (hasDoc && typeof module === 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  }
  if (typeof module !== 'undefined') {
    module.exports = { delaiBlock, booksBlock, valeurBlock, victoires, powerFair, decodeMonth, fairRow, bestRow, filterMatches, coherence, lectureOf, effective, evaluation, fiche, row };
  }
})();
