#!/usr/bin/env python3
"""
value_journal.py — Journalise un SCORE DE VALUE pour chaque match capturé, puis le
confronte au CLV réalisé (clv_history.jsonl).

  value = edge × fiabilité
  edge  = proba Elo calibrée  −  proba implicite marché (dévigée)
  fiabilité = n/(n+15) × pénalité_edge_extrême      (n = min des matchs Elo des 2 joueurs)

⚠️  CE SCORE EST UN CANDIDAT À VALIDER, PAS UN SIGNAL DE PARI.
    L'Elo est moins calibré que Pinnacle (log-loss ATP 0.659 vs 0.598). Ce script sert
    UNIQUEMENT à tester si le score prédit le CLV :
      - CLV moyen positif sur les candidats flaggés  -> le score a de la valeur prédictive
      - CLV nul ou négatif                           -> à jeter (comme form residuals)

Réplique EXACTE des fonctions JS de l'outil (toEloFormat / eloCombined / getEloProb / valueScore).
Lecture seule des données, AUCUN appel API (gratuit, hors quota).

Entrées : closing_lines.json, clv_history.jsonl, elo_ratings_atp.json, elo_ratings_wta.json
Sorties : value_candidates.jsonl (1 ligne/match), value_clv_report.json (agrégats)
"""
import json, os, math, datetime

CLOSING_FILE = 'closing_lines.json'
CLV_LOG      = 'clv_history.jsonl'
ELO_FILES    = {'ATP': 'elo_ratings_atp.json', 'WTA': 'elo_ratings_wta.json'}
OUT_JOURNAL  = 'value_candidates.jsonl'
OUT_REPORT   = 'value_clv_report.json'
# Closing rétroactif jugé fiable si son dernier point est ≤ ce délai avant le match.
CLV_CLOSE_MAX_MINS = int(os.environ.get('CLV_CLOSE_MAX_MINS', '60'))

VS_MIN_EV    = 0.05   # mêmes seuils que l'outil HTML
VS_MIN_SCORE = 0.03

# ── déduction surface / tour à partir du nom de tournoi ──────────────────────
GRASS = ('hertogenbosch','stuttgart','halle','queen','wimbledon','eastbourne',
         'mallorca','bad homburg','nottingham','birmingham','newport')
CLAY  = ('french open','roland','monte','madrid','rome','barcelona','hamburg','munich',
         'estoril','geneva','lyon','bucharest','gstaad','kitzbuhel','umag','bastad',
         'rabat','marrakech','houston','santiago','cordoba','buenos aires','rio',
         'sao paulo','clay','terre')
def infer_surface(tournament):
    t = (tournament or '').lower()
    if any(g in t for g in GRASS): return 'Grass'
    if any(c in t for c in CLAY):  return 'Clay'
    return 'Hard'  # défaut majoritaire

def infer_tour(tournament):
    t = (tournament or '').upper()
    if t.startswith('WTA') or ' WTA' in t or 'WOMEN' in t: return 'WTA'
    return 'ATP'

# ── réplique des fonctions Elo (identiques au JS de l'outil) ─────────────────
def to_elo_format(full):
    if not full: return ''
    parts = str(full).strip().split()
    if len(parts) < 2: return str(full).strip()
    return f"{parts[-1]} {parts[0][0].upper()}."

def elo_lookup(elo, name):
    pl = elo.get('players', {})
    if name in pl: return pl[name]
    nl = name.lower()
    for k, v in pl.items():
        if k.lower() == nl: return v
    return None

def elo_combined(p, surface, sw):
    g = p.get('elo'); s = g
    if   surface == 'Clay'  and p.get('elo_clay')  is not None: s = p['elo_clay']
    elif surface == 'Hard'  and p.get('elo_hard')  is not None: s = p['elo_hard']
    elif surface == 'Grass' and p.get('elo_grass') is not None: s = p['elo_grass']
    return (1 - sw) * g + sw * s

def get_elo_prob(nameA, nameB, surface, tour, elos):
    elo = elos.get(tour)
    if not elo: return {'pa': None, 'found': False}
    cfg = elo.get('config', {})
    sw  = cfg.get('surface_weight', 0.35 if tour == 'WTA' else 0.4)
    div = cfg.get('elo_div', 400) or 400
    A = elo_lookup(elo, to_elo_format(nameA))
    B = elo_lookup(elo, to_elo_format(nameB))
    if not A or not B:
        return {'pa': None, 'found': False, 'missA': not A, 'missB': not B}
    surf = surface if surface in ('Clay', 'Hard', 'Grass') else None
    ea = elo_combined(A, surf, sw); eb = elo_combined(B, surf, sw)
    pa = 1 / (1 + 10 ** ((eb - ea) / div))
    return {'pa': pa, 'found': True, 'elo': round(ea), 'eloOpp': round(eb),
            'n': A.get('n', 0), 'nOpp': B.get('n', 0), 'surf': bool(surf)}

def value_score(edge, ev, n_min):
    n = max(0, n_min or 0)
    rN = n / (n + 15)
    aE = abs(edge)
    rExt = 1 if aE <= 0.20 else max(0.3, 1 - (aE - 0.20) / 0.30)
    R = rN * rExt
    return {'edge': edge, 'ev': ev, 'R': R, 'score': edge * R, 'nMin': n}

# ── cotes d'entrée : prix le plus précoce dispo (= prix qu'on aurait pu prendre) ──
def entry_odds(m):
    ch, ca = m.get('clv_home'), m.get('clv_away')
    if ch and ca and ch.get('open') and ca.get('open'):
        return ch['open'], ca['open'], 'curve_open'   # vrai open de la courbe complète
    for lbl in ('pinnacle_t25', 'pinnacle_t15', 'pinnacle_t7', 'pinnacle_t3',
                'pinnacle_15min', 'closing'):
        s = m.get(lbl)
        if s and s.get('home') and s.get('away'):
            return s['home'], s['away'], lbl
    for h in (m.get('history') or []):
        if h.get('home') and h.get('away'):
            return h['home'], h['away'], 'history0'
    return None, None, None

def load_json(path, default=None):
    if not os.path.exists(path): return default
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def pearson(xs, ys):
    n = len(xs)
    if n < 2: return None
    mx, my = sum(xs)/n, sum(ys)/n
    sxx = sum((x-mx)**2 for x in xs); syy = sum((y-my)**2 for y in ys)
    sxy = sum((x-mx)*(y-my) for x, y in zip(xs, ys))
    if sxx == 0 or syy == 0: return None
    return sxy / math.sqrt(sxx * syy)

def _parse_t(t):
    try:
        return datetime.datetime.fromisoformat(str(t).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None

def close_mins_before(c, side):
    """Minutes entre le dernier point AVANT le coup d'envoi et le coup d'envoi.
    Lit le champ pré-calculé (fetch_clv récent) sinon le recalcule depuis la courbe
    stockée (entrées anciennes). None si indéterminable."""
    mk = c.get('home_metrics' if side == 'home' else 'away_metrics') or {}
    if mk.get('close_mins_before') is not None:
        return mk['close_mins_before']
    start = _parse_t(c.get('commence_time'))
    cur = c.get('home_curve' if side == 'home' else 'away_curve') or []
    if not start or not cur:
        return None
    before = [p for p in (_parse_t(t) for t, _ in cur) if p and p <= start]
    if not before:
        return None
    return round((start - max(before)).total_seconds() / 60)

def main():
    elos = {t: load_json(f) for t, f in ELO_FILES.items()}
    closing = load_json(CLOSING_FILE, {}) or {}

    # CLV réalisé indexé par uid (dernière entrée gagne)
    clv = {}
    if os.path.exists(CLV_LOG):
        with open(CLV_LOG, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                try: c = json.loads(line)
                except Exception: continue
                if c.get('uid'): clv[c['uid']] = c

    records = []
    for uid, m in closing.items():
        oh, oa, src = entry_odds(m)
        home, away = m.get('home', ''), m.get('away', '')
        tour = infer_tour(m.get('tournament', ''))
        surf = infer_surface(m.get('tournament', ''))
        rec = {'uid': uid, 'home': home, 'away': away, 'tour': tour, 'surface': surf,
               'tournament': m.get('tournament', ''), 'fixture_id': m.get('fixture_id', ''),
               'odds_src': src, 'odds_home': oh, 'odds_away': oa}
        if not oh or not oa:
            rec.update({'found': False, 'reason': 'no_odds'}); records.append(rec); continue
        e = get_elo_prob(home, away, surf, tour, elos)
        if not e.get('found'):
            rec.update({'found': False, 'reason': 'elo_missing',
                        'missA': e.get('missA'), 'missB': e.get('missB')})
            records.append(rec); continue
        # dévigage marché
        ih, ia = 1/oh, 1/oa; vig = ih + ia
        pnH, pnA = ih/vig, ia/vig
        pa_home = e['pa']
        n_min = min(e.get('n', 0), e.get('nOpp', 0))
        edgeH = pa_home - pnH
        # edge one-sided : on score le côté à edge positif
        if edgeH >= 0:
            side, pa_side, odd_side, pn_side = 'home', pa_home, oh, pnH
        else:
            side, pa_side, odd_side, pn_side = 'away', 1 - pa_home, oa, pnA
        edge = pa_side - pn_side
        ev   = pa_side * odd_side - 1
        vs   = value_score(edge, ev, n_min)
        cand = bool(vs['edge'] > 0 and vs['ev'] > VS_MIN_EV and vs['score'] > VS_MIN_SCORE)
        rec.update({'found': True, 'side': side, 'pa_elo': round(pa_side, 4),
                    'p_market': round(pn_side, 4), 'edge': round(edge, 4),
                    'ev': round(ev, 4), 'R': round(vs['R'], 3),
                    'score': round(vs['score'], 4), 'n_min': n_min,
                    'elo': e['elo'], 'elo_opp': e['eloOpp'], 'surf_used': e['surf'],
                    'candidate': cand})
        # jointure CLV (si dispo) : CLV = -move_pct du côté parié (prix raccourci = +)
        c = clv.get(uid)
        if c:
            mk = c.get('home_metrics' if side == 'home' else 'away_metrics') or {}
            mv = mk.get('move_pct')
            cmb = close_mins_before(c, side)
            rec['clv_close_mins_before'] = cmb
            reliable = (cmb is not None and cmb <= CLV_CLOSE_MAX_MINS)
            rec['clv_close_reliable'] = reliable
            if mv is not None and reliable:
                rec['clv_pct'] = round(-mv, 2)            # closing fiable -> compte pour la validation
                rec['clv_amplitude'] = mk.get('amplitude_pct')
            elif mv is not None:
                rec['clv_pct_stale'] = round(-mv, 2)      # closing périmé -> gardé pour info, EXCLU
        records.append(rec)

    # écrire le journal (réécrit intégralement, idempotent)
    with open(OUT_JOURNAL, 'w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    # ── agrégats de validation ──────────────────────────────────────────────
    scored = [r for r in records if r.get('found')]
    with_clv = [r for r in scored if 'clv_pct' in r]
    cands = [r for r in scored if r.get('candidate')]
    cands_clv = [r for r in cands if 'clv_pct' in r]

    n_stale = sum(1 for r in scored if 'clv_pct_stale' in r)
    report = {
        'n_matchs_closing': len(closing),
        'n_scorables': len(scored),
        'n_candidats': len(cands),
        'n_avec_clv': len(with_clv),
        'n_candidats_avec_clv': len(cands_clv),
        'n_clv_stale_exclus': n_stale,
        'clv_close_max_mins': CLV_CLOSE_MAX_MINS,
    }
    # corrélation score <-> CLV sur TOUS les matchs scorés avec CLV (signal le + large)
    if len(with_clv) >= 2:
        report['corr_score_clv'] = round(pearson([r['score'] for r in with_clv],
                                                  [r['clv_pct'] for r in with_clv]) or 0, 3)
    # CLV des candidats flaggés (le test qui compte)
    if cands_clv:
        clvs = [r['clv_pct'] for r in cands_clv]
        report['candidats_clv_moyen'] = round(sum(clvs)/len(clvs), 2)
        report['candidats_clv_pct_positif'] = round(100*sum(1 for x in clvs if x > 0)/len(clvs), 1)
    # référence : CLV moyen des NON-candidats (pour comparer)
    noncand_clv = [r['clv_pct'] for r in with_clv if not r.get('candidate')]
    if noncand_clv:
        report['non_candidats_clv_moyen'] = round(sum(noncand_clv)/len(noncand_clv), 2)

    with open(OUT_REPORT, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # ── affichage ─────────────────────────────────────────────────────────────
    print(f"📊 {len(scored)} matchs scorés / {len(closing)} | {len(cands)} candidats value "
          f"(EV>{VS_MIN_EV*100:.0f}% & score>{VS_MIN_SCORE*100:.0f})")
    for r in sorted(cands, key=lambda x: -x['score'])[:15]:
        clv_txt = f" | CLV {r['clv_pct']:+.1f}%" if 'clv_pct' in r else " | CLV n/a"
        print(f"  🎯 {r['home']} vs {r['away']} [{r['surface']}] -> {r['side']} "
              f"edge {r['edge']*100:+.1f}% EV {r['ev']*100:+.1f}% score {r['score']*100:.1f} "
              f"(n={r['n_min']}){clv_txt}")
    print("\n── Validation CLV ──")
    print(f"  closings fiables ≤{CLV_CLOSE_MAX_MINS}min : {len(with_clv)} retenus | {n_stale} périmés exclus")
    if 'corr_score_clv' in report:
        print(f"  corrélation score↔CLV (n={report['n_avec_clv']}) : {report['corr_score_clv']:+.3f}")
    if 'candidats_clv_moyen' in report:
        print(f"  CLV moyen CANDIDATS : {report['candidats_clv_moyen']:+.2f}% "
              f"({report['candidats_clv_pct_positif']:.0f}% positifs, n={report['n_candidats_avec_clv']})")
    if 'non_candidats_clv_moyen' in report:
        print(f"  CLV moyen non-candidats : {report['non_candidats_clv_moyen']:+.2f}%")
    if report.get('n_candidats_avec_clv', 0) < 30:
        print("  ⚠️ Échantillon trop faible pour conclure — accumuler quelques semaines.")
    print(f"\n✅ Journal: {OUT_JOURNAL} | Rapport: {OUT_REPORT}")

if __name__ == '__main__':
    main()
