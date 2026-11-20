/* Tennis Edge Lab V7.2 — onglet « Matchs en direct » : cotes du moment + matchs similaires passés. Lecture seule. */
(() => {
  'use strict';
  const hasDoc = typeof document !== 'undefined';
  const $ = id => (hasDoc ? document.getElementById(id) : null);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const nf = (v, d = 2) => v === null || v === undefined || !Number.isFinite(+v) ? '—'
    : new Intl.NumberFormat('fr-FR', { maximumFractionDigits: d }).format(+v);
  const sg = (v, d = 1, u = ' %') => {
    if (v === null || v === undefined || !Number.isFinite(+v)) return '—';
    const r = Math.round(+v * 10 ** d) / 10 ** d || 0;
    return `${r > 0 ? '+' : ''}${nf(r, d)}${u}`;
  };
  const ic = c => (c ? `[${sg(c[0])} ; ${sg(c[1])}]` : '—');

  // ---------- Règles (miroir EXACT de direct_profils.py, parité testée) ----------
  const HORIZONS = [['24h', 1440], ['6h', 360], ['1h', 60], ['10m', 10]];
  const MIN_N = 30;
  const MOVE_BANDS = [[-1e9, -5, '≤ −5 %'], [-5, -2, '−5 à −2 %'], [-2, 0, '−2 à 0 %'], [0, 2, '0 à 2 %'], [2, 5, '2 à 5 %'], [5, 1e9, '≥ 5 %']];
  const GAP_BANDS = [[-1e9, -5, '< −5 %'], [-5, -2, '−5 à −2 %'], [-2, 0, '−2 à 0 %'], [0, 2, '0 à 2 %'], [2, 1e9, '≥ 2 %']];
  // Seuls champs du jeu « matchs » lus pour la similarité : rôle « filtre » (connus à l'horizon).
  const SIMILARITY_FIELDS = ['horizon', 'circuit', 'surface', 'cote_pin', 'move_pin_pct', 'ecart_jouable_pct', 'alerte_avant'];
  const RELAX = ['alerte', 'ecart', 'move_band', 'surface', 'move_dir', 'cote20', 'circuit', 'cote35'];
  const RELAX_LABEL = { alerte: 'alerte avant', ecart: 'écart vs Pinnacle', move_band: 'ampleur du mouvement', surface: 'surface',
    move_dir: 'sens du mouvement', cote20: 'cote ±10 % → ±20 %', circuit: 'circuit', cote35: 'cote ±20 % → ±35 %' };
  const MAX_ENTRY_AGE_MIN = 30;

  const band = (v, bands) => { if (v === null || v === undefined || !Number.isFinite(v)) return null; for (const [lo, hi, l] of bands) if (v >= lo && v < hi) return l; return null; };
  const direction = m => (m === null || m === undefined || !Number.isFinite(m) ? null : m < 0 ? 'raccourcie' : m > 0 ? 'allongée' : 'stable');

  function powerFair(side, other, tol = 1e-12) {
    if (!side || !other || side <= 1 || other <= 1) return null;
    const a = 1 / side, b = 1 / other, f = k => a ** k + b ** k - 1;
    let lo = 0, hi = 1;
    while (f(hi) > 0) { hi *= 2; if (hi > 1e6) return null; }
    for (let i = 0; i < 200; i++) { const mid = (lo + hi) / 2; if (f(mid) > 0) lo = mid; else hi = mid; if (hi - lo < tol) break; }
    return 1 / (a ** ((lo + hi) / 2));
  }
  const nearestHorizon = minutes => HORIZONS.reduce((best, h) => (Math.abs(h[1] - minutes) < Math.abs(best[1] - minutes) ? h : best))[0];
  const effOdds = (flags, book, odds) => 1 + (odds - 1) * (1 - ((flags[book] || {}).commission || 0));

  function criteria(p, relaxed) {
    const r = new Set(relaxed);
    const c = { horizon: p.horizon };
    if (!r.has('circuit')) c.circuit = p.circuit;
    if (!r.has('surface') && p.surface && p.surface !== 'inconnue') c.surface = p.surface;
    const w = r.has('cote35') ? 0.35 : r.has('cote20') ? 0.20 : 0.10;
    c.cote = [p.cote_pin / (1 + w), p.cote_pin * (1 + w)];
    if (!r.has('move_dir') && p.move_dir) c.move_dir = p.move_dir;
    if (!r.has('move_band') && p.move_band) c.move_band = p.move_band;
    if (!r.has('ecart')) c.ecart_band = p.ecart_band || 'sans jouable';
    if (!r.has('alerte')) c.alerte = p.alerte;
    return c;
  }
  function rowMatches(row, c) {
    if (row.horizon !== c.horizon) return false;
    if ('circuit' in c && row.circuit !== c.circuit) return false;
    if ('surface' in c && row.surface !== c.surface) return false;
    const cp = row.cote_pin;
    if (cp === null || cp === undefined || !(cp >= c.cote[0] && cp <= c.cote[1])) return false;
    const mv = row.move_pin_pct;
    if ('move_dir' in c && direction(mv) !== c.move_dir) return false;
    if ('move_band' in c && band(mv, MOVE_BANDS) !== c.move_band) return false;
    if ('ecart_band' in c && (band(row.ecart_jouable_pct, GAP_BANDS) || 'sans jouable') !== c.ecart_band) return false;
    if ('alerte' in c && ((row.alerte_avant === null || row.alerte_avant === undefined || row.alerte_avant === 'aucune') ? 'non' : 'oui') !== c.alerte) return false;
    return true;
  }
  function similar(rows, p) {
    const relaxed = [];
    for (;;) {
      const c = criteria(p, relaxed);
      const idx = [];
      for (let i = 0; i < rows.length; i++) if (rowMatches(rows[i], c)) idx.push(i);
      const n = idx.reduce((a, i) => a + (rows[i].clv_pinnacle !== null && rows[i].clv_pinnacle !== undefined ? 1 : 0), 0);
      if (n >= MIN_N) return { idx, relaxed: relaxed.slice(), crit: c, ok: true };
      if (relaxed.length === RELAX.length) return { idx, relaxed: relaxed.slice(), crit: c, ok: false };
      relaxed.push(RELAX[relaxed.length]);
    }
  }
  function erfc(x) {
    const z = Math.abs(x), t = 1 / (1 + 0.5 * z);
    const r = t * Math.exp(-z * z - 1.26551223 + t * (1.00002368 + t * (0.37409196 + t * (0.09678418 + t * (-0.18628806 + t * (0.27886807 + t * (-1.13520398 + t * (1.48851587 + t * (-0.82215223 + t * 0.17087277)))))))));
    return x >= 0 ? r : 2 - r;
  }
  function clusterSummary(values, clusters) {
    const pairs = [];
    values.forEach((v, i) => { if (typeof v === 'number' && Number.isFinite(v)) pairs.push([v, clusters[i]]); });
    const n = pairs.length;
    if (!n) return { n: 0, mean: null, ci: null, p: null };
    const mean = pairs.reduce((a, [v]) => a + v, 0) / n;
    if (n < 2) return { n, mean, ci: null, p: null };
    const g = new Map();
    for (const [v, c] of pairs) g.set(c, (g.get(c) || 0) + v - mean);
    let variance;
    if (g.size >= 4) { let s = 0; for (const x of g.values()) s += x * x; variance = (g.size / (g.size - 1)) * s / (n * n); }
    else variance = pairs.reduce((a, [v]) => a + (v - mean) ** 2, 0) / (n - 1) / n;
    const se = Math.sqrt(Math.max(variance, 0));
    if (!se) return { n, mean, ci: [mean, mean], p: mean > 0 ? 0 : 1 };
    return { n, mean, ci: [mean - 1.96 * se, mean + 1.96 * se], p: 0.5 * erfc(mean / se / Math.SQRT2) };
  }
  /** CLV Pinnacle moyenne des matchs de même horizon ET même fenêtre de cote (la marge Pinnacle dépend du niveau de cote). */
  function baseline(rows, crit) {
    let s = 0, n = 0;
    for (const r of rows) {
      if (r.horizon !== crit.horizon || r.clv_pinnacle === null || r.clv_pinnacle === undefined) continue;
      if (r.cote_pin === null || r.cote_pin === undefined || !(r.cote_pin >= crit.cote[0] && r.cote_pin <= crit.cote[1])) continue;
      s += r.clv_pinnacle; n++;
    }
    return n ? s / n : 0;
  }
  function stats(rows, idx, base = 0) {
    const dates = idx.map(i => rows[i].date);
    const clv = clusterSummary(idx.map(i => rows[i].clv_pinnacle), dates);
    const exces = clusterSummary(idx.map(i => (rows[i].clv_pinnacle === null || rows[i].clv_pinnacle === undefined ? null : rows[i].clv_pinnacle - base)), dates);
    const clvJ = clusterSummary(idx.map(i => rows[i].clv_jouable), dates);
    const roi = clusterSummary(idx.map(i => (rows[i].pnl_jouable === null || rows[i].pnl_jouable === undefined ? null : 100 * rows[i].pnl_jouable)), dates);
    const settled = idx.filter(i => rows[i].gagne !== null && rows[i].gagne !== undefined);
    const wins = settled.reduce((a, i) => a + rows[i].gagne, 0);
    const implied = settled.map(i => rows[i].proba_juste || 1 / rows[i].cote_pin);
    const months = new Map();
    for (const i of idx) {
      const v = rows[i].clv_pinnacle;
      if (v === null || v === undefined) continue;
      const m = String(rows[i].date).slice(0, 7), e = months.get(m) || [0, 0];
      e[0] += v; e[1]++; months.set(m, e);
    }
    const tot = [...months.values()].filter(m => m[1] >= 5);
    return { n: idx.length, clv, exces, base, clvJ, roi, settled: settled.length, wins,
      implied: implied.length ? implied.reduce((a, b) => a + b, 0) / implied.length : null,
      impliedFair: settled.every(i => rows[i].proba_juste), monthsPos: tot.length ? tot.filter(m => m[0] > 0).length / tot.length : null };
  }
  // V7.3 : la CLV de ces matchs s'est-elle transformée en gains ? (miroir de lectures_profils.coherence)
  function coherence(items) {
    const ok = items.filter(([c, v, g]) => Number.isFinite(c) && c > 1 && Number.isFinite(v) && Number.isFinite(g));
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

  function verdict(s, alpha) {
    const c = s.exces;
    if (c.n < MIN_N) return 'trop peu de matchs (n<30)';
    if (c.ci && c.ci[0] > 0 && c.p !== null && c.p < alpha) return 'sous-coté';
    if (c.ci && c.ci[1] < 0 && c.p !== null && 1 - c.p < alpha) return 'sur-coté';
    return 'le marché a raison';
  }
  function verdictText(s, alpha) {
    const v = verdict(s, alpha), e = s.exces;
    if (v === 'sous-coté') return `profil historiquement sous-coté : CLV ${sg(e.mean)} ${ic(e.ci)} au-dessus des matchs de même horizon et même cote, sur ${e.n} matchs — information, pas un conseil`;
    if (v === 'sur-coté') return `profil historiquement sur-coté : CLV ${sg(e.mean)} ${ic(e.ci)} sous les matchs de même horizon et même cote, sur ${e.n} matchs — information, pas un conseil`;
    if (v === 'le marché a raison') return `le marché a raison sur ce profil (CLV ≈ 0 : écart aux matchs de même cote ${sg(e.mean)} ${ic(e.ci)}, n=${e.n})`;
    return `trop peu de matchs (n<30) : ${e.n} avec CLV`;
  }

  // ---------- Match du moment -> profil (champs connus MAINTENANT uniquement) ----------
  function sidePrices(m, side, now, flags) {
    const i = side === 'home' ? 0 : 1, o = 1 - i;
    const pinCur = m.pin.courant, pinOpen = m.pin.ouverture;
    const cur = side === 'home' ? pinCur.h : pinCur.a, opp = side === 'home' ? pinCur.a : pinCur.h;
    const open = side === 'home' ? pinOpen.h : pinOpen.a;
    const fair = powerFair(cur, opp);
    const best = { jouable: null, fr: null };
    let nBooks = 1;
    for (const [book, q] of Object.entries(m.cotes || {})) {
      if (!q || !q[i] || !q[o]) continue;
      nBooks++;
      const f = flags[book] || {};
      if (!f.jouable) continue;
      const age = (now - Date.parse(q[2])) / 60000;
      if (!(age <= MAX_ENTRY_AGE_MIN)) continue;
      const eff = effOdds(flags, book, q[i]);
      for (const [kind, ok] of [['jouable', true], ['fr', f.fr]]) {
        if (ok && (!best[kind] || eff > best[kind].eff)) best[kind] = { book, odds: q[i], eff, gap: fair ? 100 * (eff / fair - 1) : null };
      }
    }
    return { cur, opp, open, fair, move: open ? 100 * (cur / open - 1) : null, best, nBooks };
  }
  function profileFor(m, side, now, flags) {
    const mins = (Date.parse(m.commence) - now) / 60000;
    if (!(mins > 0) || !m.pin) return null;
    const px = sidePrices(m, side, now, flags);
    const player = side === 'home' ? m.home : m.away;
    const fired = (m.alertes || []).some(a => normName(a.joueur) === normName(player) && Date.parse(a.t + (/Z|[+-]\d\d:?\d\d$/.test(a.t) ? '' : 'Z')) < now);
    return { horizon: nearestHorizon(mins), circuit: m.circuit, surface: m.surface, cote_pin: px.cur,
      move_dir: direction(px.move), move_band: band(px.move, MOVE_BANDS),
      ecart_band: px.best.jouable ? band(px.best.jouable.gap, GAP_BANDS) : null, alerte: fired ? 'oui' : 'non' };
  }
  const normName = s => String(s || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '');
  const slug = nom => String(nom).normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().split(/[^a-z]+/).filter(t => t.length > 1).sort().join('-');

  /** Cotes courantes de live_odds.json (capture la plus récente) appliquées aux matchs de direct_matchs.json. */
  function mergeLiveOdds(doc, live, lastWrite) {
    if (!doc || !Array.isArray(live) || !lastWrite) return doc;
    const t = new Date(lastWrite.endsWith('Z') || /[+-]\d\d:\d\d$/.test(lastWrite) ? lastWrite : lastWrite + 'Z').toISOString().replace(/\.\d{3}Z$/, 'Z');
    const byPair = new Map();
    for (const e of live) byPair.set([normName(e.home_team), normName(e.away_team)].sort().join('|'), e);
    for (const m of doc.matchs || []) {
      const e = byPair.get([normName(m.home), normName(m.away)].sort().join('|'));
      if (!e || Math.abs(Date.parse(e.commence_time) - Date.parse(m.commence)) > 2 * 3600e3) continue;
      if (Date.parse(m.commence) <= Date.parse(t)) continue;   // match commencé : jamais de cotes en jeu
      const swap = normName(e.home_team) !== normName(m.home);
      for (const [book, q] of Object.entries(e.books_match || {})) {
        if (!q || !q.home || !q.away) continue;
        const h = swap ? q.away : q.home, a = swap ? q.home : q.away;
        if (book === 'pinnacle') { if (!m.pin.courant.t || t > m.pin.courant.t) m.pin.courant = { h, a, t }; }
        else if (!m.cotes[book] || t > m.cotes[book][2]) m.cotes[book] = [h, a, t];
      }
      m.live_odds = true;
    }
    return doc;
  }
  function freshness(iso, now) {
    if (!iso) return { text: 'date de mise à jour inconnue', stale: true, minutes: null };
    const min = Math.max(0, Math.round((now - Date.parse(iso)) / 60000));
    const text = min < 1 ? 'mis à jour à l’instant' : min < 60 ? `mis à jour il y a ${min} min` : `mis à jour il y a ${Math.floor(min / 60)} h ${String(min % 60).padStart(2, '0')}`;
    return { text, stale: min > 20, minutes: min };
  }
  function visible(matches, f, now) {
    return (matches || []).filter(m => {
      const mins = (Date.parse(m.commence) - now) / 60000;
      if (f.circuit && m.circuit !== f.circuit) return false;
      if (f.surface && m.surface !== f.surface) return false;
      if (f.fenetre === 'encours') return mins <= 0 && mins > -180;
      const max = { '1h': 60, '6h': 360, '24h': 1440 }[f.fenetre || '24h'];
      return mins > -180 && mins <= max;
    }).sort((a, b) => Date.parse(a.commence) - Date.parse(b.commence));
  }
  /** Colonnes de explorateur_matchs -> objets (seuls les champs utiles). */
  function rowsFromMatchs(doc) {
    const keep = [...SIMILARITY_FIELDS, 'date', 'gagne', 'clv_pinnacle', 'clv_jouable', 'pnl_jouable', 'proba_juste', 'cote_jouable'];
    const cols = Object.fromEntries(doc.columns.map(c => [c.name, c]));
    const rows = new Array(doc.n);
    for (let i = 0; i < doc.n; i++) rows[i] = {};
    for (const name of keep) {
      if (!cols[name]) continue;
      const data = doc.data[name], dict = doc.dicts[name];
      for (let i = 0; i < doc.n; i++) rows[i][name] = cols[name].type === 'cat' ? (data[i] === null ? null : dict[data[i]]) : data[i];
    }
    return rows;
  }

  // ---------- État et rendu ----------
  const shared = hasDoc && typeof window !== 'undefined' ? (window.TELab = window.TELab || { seen: new Set() }) : { seen: new Set() };
  const state = { doc: null, liveAt: null, rows: null, rowsErr: null, base: {}, f: { circuit: '', surface: '', fenetre: '24h' }, open: new Set(), panels: new Map() };
  const repo = () => {
    if (!hasDoc) return 'Lucas987987/Tennis-edge';
    const h = location.hostname.match(/^([^.]+)\.github\.io$/);
    const seg = location.pathname.split('/').filter(Boolean)[0];
    return h && seg ? `${h[1]}/${seg}` : 'Lucas987987/Tennis-edge';
  };
  const RAW = f => `https://raw.githubusercontent.com/${repo()}/main/${f}`;
  async function getJson(urls) {
    for (const u of urls) {
      try { const r = await fetch(`${u}?t=${Date.now()}`, { cache: 'no-store' }); if (r.ok) return await r.json(); } catch { /* suivant */ }
    }
    return null;
  }
  async function loadRows() {
    if (state.rows || state.rowsErr) return;
    try {
      let doc = null;
      if (typeof DecompressionStream !== 'undefined') {
        const r = await fetch(`./live/explorateur_matchs.json.gz?t=${Date.now()}`, { cache: 'no-store' });
        if (r.ok) doc = JSON.parse(await new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).text());
      }
      if (!doc) { const r = await fetch(`./live/explorateur_matchs.json?t=${Date.now()}`); if (r.ok) doc = await r.json(); }
      if (!doc) throw new Error('jeu « Tous les matchs » indisponible');
      state.rows = rowsFromMatchs(doc);
    } catch (e) { state.rowsErr = e.message; }
  }
  async function refresh() {
    const [doc, live, meta] = await Promise.all([
      getJson([RAW('direct_matchs.json'), '../direct_matchs.json']),
      getJson([RAW('live_odds.json'), '../live_odds.json']),
      getJson([RAW('matches_oddspapi_meta.json'), '../matches_oddspapi_meta.json'])]);
    if (doc) { state.doc = mergeLiveOdds(doc, live, meta && meta.last_write); state.liveAt = meta && meta.last_write ? meta.last_write + (/Z|[+-]\d\d:\d\d$/.test(meta.last_write) ? '' : 'Z') : null; state.panels.clear(); }
    render();
  }

  function oddsCell(px, kind) {
    const b = px.best[kind];
    return b ? `<b>${nf(b.odds, 2)}</b><span class="detail">${esc(b.book)} · écart ${sg(b.gap)}</span>` : '<b>—</b><span class="detail">aucun</span>';
  }
  function sideBlock(m, side, now, flags) {
    const px = sidePrices(m, side, now, flags);
    const player = side === 'home' ? m.home : m.away;
    const key = `${m.uid}|${side}`;
    const link = `https://joueurs.tennis-edge.workers.dev/j/${slug(player)}`;
    return `<div class="dm-side"><div class="dm-player"><a href="${esc(link)}" target="_blank" rel="noopener">${esc(player)}</a></div>
      <div class="dm-grid"><span>Pinnacle</span><b>${nf(px.cur, 2)}</b><span class="detail">juste ${nf(px.fair, 2)} · depuis l’ouverture ${sg(px.move)}</span>
      <span>Meilleur jouable</span>${oddsCell(px, 'jouable')}
      <span>Meilleur FR</span>${oddsCell(px, 'fr')}</div>
      ${Date.parse(m.commence) > now ? `<button type="button" class="dm-sim" data-sim="${esc(key)}">${state.panels.has(key) ? 'Masquer' : 'Matchs similaires passés'}</button>` : ''}
      ${state.panels.has(key) ? state.panels.get(key) : ''}</div>`;
  }
  function panel(m, side, now, flags) {
    if (state.rowsErr) return `<div class="dm-panel"><p class="notice warn">${esc(state.rowsErr)}</p></div>`;
    if (!state.rows) return '<div class="dm-panel"><p class="mini">Chargement de l’historique…</p></div>';
    const p = profileFor(m, side, now, flags);
    if (!p) return '<div class="dm-panel"><p class="mini">Match commencé : profils pré-match non applicables.</p></div>';
    const res = similar(state.rows, p);
    shared.seen.add(JSON.stringify(['direct', p]));
    const k = Math.max(1, shared.seen.size), alpha = 0.05 / k;
    const bkey = JSON.stringify([res.crit.horizon, res.crit.cote]);
    const base = state.base[bkey] ?? (state.base[bkey] = baseline(state.rows, res.crit));
    const s = stats(state.rows, res.idx, base);
    const v = verdict(s, alpha);
    const crit = [`horizon ${p.horizon}`, res.crit.circuit && `circuit ${res.crit.circuit}`, res.crit.surface && `surface ${res.crit.surface}`,
      `cote Pinnacle ${nf(res.crit.cote[0], 2)}–${nf(res.crit.cote[1], 2)}`, res.crit.move_dir && `cote ${res.crit.move_dir}`,
      res.crit.move_band && `mouvement ${res.crit.move_band}`, res.crit.ecart_band && `écart jouable ${res.crit.ecart_band}`,
      res.crit.alerte && `alerte avant : ${res.crit.alerte}`].filter(Boolean);
    return `<div class="dm-panel"><p class="detail"><b>Profil</b> : ${esc(crit.join(' · '))}</p>
      ${res.relaxed.length ? `<p class="detail">Relâché pour atteindre n ≥ 30 : ${esc(res.relaxed.map(r => RELAX_LABEL[r]).join(', '))}</p>` : '<p class="detail">Aucun critère relâché.</p>'}
      <div class="dm-stats"><div><small>Matchs</small><b>${nf(s.n, 0)}</b><small>${nf(s.settled, 0)} réglés</small></div>
      <div><small>Gagnés / implicite</small><b>${s.settled ? nf(100 * s.wins / s.settled, 1) + ' %' : '—'}</b><small>${s.implied ? nf(100 * s.implied, 1) + ' %' : '—'} ${s.impliedFair ? '(Pinnacle juste)' : '(1/cote, marge incluse)'}</small></div>
      <div><small>CLV Pinnacle · IC95</small><b>${sg(s.clv.mean)}</b><small>${ic(s.clv.ci)} · n=${nf(s.clv.n, 0)}</small></div>
      <div><small>Écart aux matchs de même horizon et même cote (${sg(s.base)})</small><b class="${v === 'sous-coté' ? 'good' : v === 'sur-coté' ? 'bad' : ''}">${sg(s.exces.mean)}</b><small>${ic(s.exces.ci)}</small></div>
      <div><small>ROI au meilleur jouable</small><b>${sg(s.roi.mean)}</b><small>${ic(s.roi.ci)}</small></div></div>
      <p class="detail">CLV entrée meilleur jouable ${sg(s.clvJ.mean)} · mois CLV+ ${s.monthsPos === null ? '—' : nf(100 * s.monthsPos, 0) + ' %'} · p ${s.exces.p === null ? '—' : nf(s.exces.p, 3)} (seuil α/k = ${nf(alpha, 4)}, k = ${k} profils et découpes consultés)</p>
      ${(() => {
        const c = coherence(res.idx.map(i => [state.rows[i].cote_jouable, state.rows[i].clv_jouable, state.rows[i].pnl_jouable]));
        return c.n ? `<p class="detail">CLV → gains (entrée meilleur jouable, ${nf(c.n, 0)} paris réglés) : ROI attendu d’après la CLV ${sg(c.roi_attendu)} · ROI réel ${sg(c.roi_reel)} · z ${c.z === null ? '—' : nf(c.z, 2)} → <b>${esc(c.etat)}</b></p>` : '';
      })()}
      <p class="dm-verdict ${v === 'sous-coté' ? 'good' : ''}">${esc(verdictText(s, alpha))}</p></div>`;
  }
  function card(m, now, flags) {
    const mins = Math.round((Date.parse(m.commence) - now) / 60000);
    const when = mins > 0 ? `dans ${mins >= 60 ? `${Math.floor(mins / 60)} h ${String(mins % 60).padStart(2, '0')}` : `${mins} min`}` : 'en cours · cotes d’avant le début';
    const nb = new Set(Object.keys(m.cotes || {})).size + 1;
    const duo = `https://joueurs.tennis-edge.workers.dev/j/${slug(m.home)}/${slug(m.away)}`;
    const al = (m.alertes || []).map(a => `<li><b>${esc(a.type)}</b> ${esc(String(a.t || '').slice(11, 16))} · ${esc(a.joueur)} à ${nf(a.cote, 2)}${a.book ? ` (${esc(a.book)})` : ''}${a.envoye ? '' : ' · non envoyée'}</li>`).join('');
    return `<article class="dm-card ${mins <= 0 ? 'dm-live' : ''}"><div class="dm-head"><b>${esc(when)}</b> · ${esc(m.tournoi)} <span class="detail">${esc(m.circuit)} · ${esc(m.surface)} · ${nb} books · <a href="${esc(duo)}" target="_blank" rel="noopener">face-à-face</a></span></div>
      ${sideBlock(m, 'home', now, flags)}${sideBlock(m, 'away', now, flags)}
      ${al ? `<ul class="dm-alerts">${al}</ul>` : '<p class="detail">Aucune alerte sur ce match.</p>'}</article>`;
  }
  function render() {
    const host = $('directBody');
    if (!host) return;
    const now = Date.now();
    const d = state.doc;
    if (!d) { host.innerHTML = '<p class="notice warn">Données en direct indisponibles (direct_matchs.json).</p>'; return; }
    const fr1 = freshness(d.genere_le, now), fr2 = freshness(state.liveAt, now);
    const list = visible(d.matchs, state.f, now);
    const opts = (vals, cur) => ['', ...vals].map(v => `<option value="${esc(v)}" ${v === cur ? 'selected' : ''}>${v ? esc(v) : 'tous'}</option>`).join('');
    const circuits = [...new Set(d.matchs.map(m => m.circuit))].sort(), surfaces = [...new Set(d.matchs.map(m => m.surface))].sort();
    host.innerHTML = `<p class="mini dm-fresh ${fr1.stale ? 'dm-stale' : ''}">Courbes et alertes : ${esc(fr1.text)} · cotes courantes : ${esc(fr2.text)} · actualisation toutes les 2 min 30.</p>
      <div class="dm-filters"><label>Circuit<select id="dmCircuit">${opts(circuits, state.f.circuit)}</select></label>
      <label>Surface<select id="dmSurface">${opts(surfaces, state.f.surface)}</select></label>
      <label>Début<select id="dmFenetre">${[['encours', 'en cours'], ['1h', '< 1 h'], ['6h', '< 6 h'], ['24h', '< 24 h']].map(([v, l]) => `<option value="${v}" ${state.f.fenetre === v ? 'selected' : ''}>${l}</option>`).join('')}</select></label></div>
      <p class="mini">${list.length} match(s). Écart = meilleure cote (nette de commission, &lt; 30 min) vs cote Pinnacle juste (méthode puissance). Profils consultés dans la session : <b>${Math.max(1, shared.seen.size)}</b>.</p>
      ${list.map(m => card(m, now, d.books || {})).join('') || '<p class="mini">Aucun match dans ce filtre.</p>'}`;
    bind();
  }
  function bind() {
    const host = $('directBody');
    for (const [id, key] of [['dmCircuit', 'circuit'], ['dmSurface', 'surface'], ['dmFenetre', 'fenetre']]) {
      const el = $(id); if (el) el.addEventListener('change', () => { state.f[key] = el.value; render(); });
    }
    host.querySelectorAll('[data-sim]').forEach(b => b.addEventListener('click', async () => {
      const key = b.dataset.sim;
      if (state.panels.has(key)) { state.panels.delete(key); render(); return; }
      state.panels.set(key, '<div class="dm-panel"><p class="mini">Chargement de l’historique…</p></div>');
      render();
      await loadRows();
      const [uid, side] = key.split('|');
      const m = state.doc.matchs.find(x => x.uid === uid);
      if (m) state.panels.set(key, panel(m, side, Date.now(), state.doc.books || {}));
      render();
    }));
  }
  async function start() {
    if (!$('directBody')) return;
    await refresh();
    setInterval(refresh, 150000);
    setInterval(() => { const el = document.querySelector('.dm-fresh'); if (el && state.doc) render(); }, 30000);
  }
  if (hasDoc && typeof module === 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
  }
  if (typeof module !== 'undefined') {
    module.exports = { HORIZONS, RELAX, SIMILARITY_FIELDS, MOVE_BANDS, GAP_BANDS, powerFair, nearestHorizon, criteria, rowMatches,
      similar, stats, baseline, verdict, verdictText, coherence, profileFor, sidePrices, mergeLiveOdds, freshness, visible, rowsFromMatchs, slug, clusterSummary };
  }
})();
