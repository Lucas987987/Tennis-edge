#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
move_vs_outcome.py
------------------
Repond a : un favori qui a RACCOURCI gagne-t-il PLUS, AUTANT ou MOINS que ne
le dit sa cote de cloture ? (le mouvement sur-corrige-t-il ?)

- "autant"  -> marche efficient, pas d'edge.
- "moins"   -> sur-correction : l'outsider est sous-cote a la cloture -> jouable.
- "plus"    -> la cloture sous-estime le favori.

Joint clv_history.jsonl (courbes/metriques Pinnacle) a resultats.json (vainqueur,
source Sackmann) par appariement de noms. Lecture seule, aucune API.

Metrique cle : (taux de victoire reel du favori) - (proba de cloture devigee).
Negatif et significatif sur les favoris qui ont raccourci = sur-correction.
"""
import json, os, sys, math, re, unicodedata, datetime

HIST    = os.environ.get('CLV_HISTORY', 'clv_history.jsonl')
RESULTS = os.environ.get('RESULTS', 'resultats.json')
OUT     = os.environ.get('MOVE_OUTCOME_REPORT', 'move_outcome_report.json')
DATE_TOL_DAYS = 3

def norm_tokens(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return set(t for t in re.split(r'[^a-z0-9]+', s.lower()) if len(t) >= 2)

def player_match(a, b):
    shared = a & b
    if not shared:
        return False
    # un vrai token de nom partage (>=4) ou >=2 tokens communs
    return len(shared) >= 2 or any(len(t) >= 4 for t in shared)

def parse_date(s):
    if not s: return None
    s = str(s)[:10]
    try: return datetime.date.fromisoformat(s)
    except Exception: return None

RESULTS_FAST = os.environ.get('RESULTS_FAST', 'resultats_fast.json')

def _load_results_file(path, provisional):
    if not os.path.exists(path): return []
    try:
        d = json.load(open(path, encoding='utf-8'))
    except Exception:
        return []
    res = d.get('results', d) if isinstance(d, dict) else d
    out = []
    for r in res:
        if not isinstance(r, dict): continue
        r['_H'] = norm_tokens(r.get('home_team', ''))
        r['_A'] = norm_tokens(r.get('away_team', ''))
        r['_d'] = parse_date(r.get('date'))
        r['_prov'] = provisional
        out.append(r)
    return out

def _same_match(p, a):
    direct = player_match(p['_H'], a['_H']) and player_match(p['_A'], a['_A'])
    swap   = player_match(p['_H'], a['_A']) and player_match(p['_A'], a['_H'])
    if not (direct or swap): return False
    if p['_d'] and a['_d'] and abs((p['_d'] - a['_d']).days) > DATE_TOL_DAYS: return False
    return True

def load_results():
    """Sackmann (officiel) prioritaire ; provisoire rapide seulement pour les matchs absents."""
    auth = _load_results_file(RESULTS, False)
    prov = _load_results_file(RESULTS_FAST, True)
    kept = [p for p in prov if not any(_same_match(p, a) for a in auth)]
    return auth + kept

def load_hist():
    rows = []
    if not os.path.exists(HIST): return rows
    for line in open(HIST, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        try: rows.append(json.loads(line))
        except json.JSONDecodeError: pass
    return rows

def find_result(H, A, mdate, results):
    Ht, At = norm_tokens(H), norm_tokens(A)
    for r in results:
        direct = player_match(Ht, r['_H']) and player_match(At, r['_A'])
        swap   = player_match(Ht, r['_A']) and player_match(At, r['_H'])
        if not (direct or swap): continue
        if mdate and r['_d']:
            if abs((mdate - r['_d']).days) > DATE_TOL_DAYS: continue
        return r, direct   # direct => clv-home == result home_team
    return None, None

def close_open(m, side):
    """(open, close) du cote 'home'/'away' depuis les metriques ou la courbe."""
    met = m.get(side + '_metrics')
    if isinstance(met, dict) and met.get('open') and met.get('close'):
        return float(met['open']), float(met['close'])
    cur = m.get(side + '_curve')
    if isinstance(cur, list) and len(cur) >= 2:
        return float(cur[0][1]), float(cur[-1][1])
    return None, None

def zscore(wins, n, p):
    if n == 0 or p <= 0 or p >= 1: return 0.0
    return (wins/n - p) / math.sqrt(p*(1-p)/n)

def block(items):
    """items = liste de (fav_won_bool, prob_close). Renvoie stats du gap."""
    n = len(items)
    if n == 0: return {'n': 0}
    wins = sum(1 for w, _ in items if w)
    wr = wins/n
    mp = sum(p for _, p in items)/n
    gap = wr - mp
    se = math.sqrt(wr*(1-wr)/n) if 0 < wr < 1 else 0.0
    return {'n': n, 'victoires_favori': wins, 'taux_victoire': round(wr, 4),
            'proba_cloture_moy': round(mp, 4), 'gap': round(gap, 4),
            'gap_ic95_bas': round(gap-1.96*se, 4), 'gap_ic95_haut': round(gap+1.96*se, 4),
            'z': round(zscore(wins, n, mp), 2)}

def main():
    rows = load_hist()
    results = load_results()
    if not rows:
        print("MOVE/OUTCOME — clv_history.jsonl vide. Declenche fetch_clv.")
        json.dump({'status': 'empty'}, open(OUT, 'w')); return 0
    if not results:
        print(f"MOVE/OUTCOME — {RESULTS} introuvable ou vide.")
        json.dump({'status': 'no_results'}, open(OUT, 'w')); return 0

    matched = 0; unmatched = []
    short_items, drift_items, flat_items, all_items = [], [], [], []
    detail = []
    for m in rows:
        H, A = m.get('home'), m.get('away')
        ho = close_open(m, 'home'); ao = close_open(m, 'away')
        if not ho or not ao or not ho[1] or not ao[1]:
            continue
        h_open, h_close = ho; a_open, a_close = ao
        r, H_is_home = find_result(H, A, parse_date(m.get('commence_time')), results)
        if not r:
            unmatched.append(f"{H} vs {A}"); continue
        wc = r.get('winner_code')
        if wc not in (1, 2):
            wn = norm_tokens(r.get('winner', ''))
            wc = 1 if player_match(wn, r['_H']) else (2 if player_match(wn, r['_A']) else None)
        if wc not in (1, 2):
            unmatched.append(f"{H} vs {A} (winner?)"); continue
        result_home_won = (wc == 1)
        clvH_won = result_home_won if H_is_home else (not result_home_won)
        matched += 1

        # favori = cote de cloture la plus basse
        if h_close <= a_close:
            fav_side, fav_open, fav_close, dog_close = 'home', h_open, h_close, a_close
        else:
            fav_side, fav_open, fav_close, dog_close = 'away', a_open, a_close, h_close
        ip_f, ip_d = 1/fav_close, 1/dog_close
        fav_prob = ip_f/(ip_f+ip_d)               # proba favori devigee a la cloture
        fav_won = clvH_won if fav_side == 'home' else (not clvH_won)
        drift = (fav_close/fav_open - 1)*100 if fav_open else 0.0   # <0 = raccourci

        item = (fav_won, fav_prob)
        all_items.append(item)
        if drift <= -1.0:   short_items.append(item)
        elif drift >= 1.0:  drift_items.append(item)
        else:               flat_items.append(item)
        detail.append({'match': f"{H} vs {A}", 'fav_side': fav_side,
                       'fav_open': round(fav_open, 3), 'fav_close': round(fav_close, 3),
                       'drift_pct': round(drift, 2), 'fav_prob_close': round(fav_prob, 4),
                       'fav_won': fav_won})

    report = {'status': 'ok', 'n_clv': len(rows), 'n_resultats': len(results),
              'apparies': matched, 'non_apparies': len(unmatched),
              'global': block(all_items),
              'favoris_qui_ont_raccourci': block(short_items),
              'favoris_qui_ont_derive': block(drift_items),
              'favoris_stables': block(flat_items),
              'detail': detail}
    json.dump(report, open(OUT, 'w'), ensure_ascii=False, indent=2)

    print("="*64)
    print(f"MOVE vs OUTCOME — {matched}/{len(rows)} matchs apparies "
          f"({len(unmatched)} non apparies)")
    print("="*64)
    def show(title, b):
        if b.get('n', 0) == 0:
            print(f"{title}: 0 match"); return
        print(f"{title} (n={b['n']})")
        print(f"   victoire favori : {b['taux_victoire']*100:.1f}%  "
              f"vs proba cloture {b['proba_cloture_moy']*100:.1f}%")
        print(f"   gap (reel-cloture) : {b['gap']*100:+.1f} pts "
              f"[IC95 {b['gap_ic95_bas']*100:+.1f};{b['gap_ic95_haut']*100:+.1f}]  z={b['z']:+.2f}")
    show("GLOBAL", report['global'])
    print()
    show(">>> FAVORIS QUI ONT RACCOURCI", report['favoris_qui_ont_raccourci'])
    show("    favoris qui ont derive", report['favoris_qui_ont_derive'])
    show("    favoris stables", report['favoris_stables'])
    print()
    b = report['favoris_qui_ont_raccourci']
    if b.get('n', 0) < 30:
        print(f"VERDICT : trop peu de favoris-raccourcis (n={b.get('n',0)}<30) pour conclure.")
    elif b['gap_ic95_haut'] < 0:
        print("VERDICT : SUR-CORRECTION significative -> l'outsider est sous-cote a la "
              "cloture. Piste jouable A LA CLOTURE (pas de course de vitesse). A creuser.")
    elif b['gap_ic95_bas'] > 0:
        print("VERDICT : les favoris-raccourcis gagnent PLUS que la cloture -> "
              "la cloture les sous-estime (rare).")
    else:
        print("VERDICT : gap ~0 -> mouvement bien calibre, marche efficient, pas d'edge.")
    print("="*64)
    if unmatched[:8]:
        print("Non apparies (extrait) :", "; ".join(unmatched[:8]))
    return 0

if __name__ == '__main__':
    sys.exit(main())
