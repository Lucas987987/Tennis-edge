#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
steam_backtest.py — Backtest FORWARD-ONLY du steam-following.

Hypothèse testée : quand Pinnacle bouge tôt, suivre ce côté sur un book mou
donne un prix qui bat la clôture (CLV positif). Le mouvement lent (heures)
est capturable à 5-15 min, donc pas besoin de sub-minute.

RÈGLE FORWARD-ONLY (anti-look-ahead) :
  - On parcourt la courbe Pinnacle dans l'ordre du temps.
  - Le "drift" est calculé de l'OUVERTURE jusqu'à l'instant courant uniquement.
  - Dès que |drift de la proba dévigée| >= MOVE_MIN pour la 1re fois, on ENTRE,
    du côté qui se raccourcit, au prix du book mou DISPONIBLE à cet instant.
  - Une seule entrée par (match, book). On tient jusqu'à la clôture.
  - Contrainte : l'entrée doit être >= MIN_LEAD min avant le match (sinon trop
    tard pour que la suite du mouvement existe).

MESURES (le CLV est la seule preuve d'edge) :
  - CLV vs clôture du MÊME book mou  = (cote_entrée / cote_clôture_book - 1)*100
        -> le CLV réellement encaissable.
  - CLV vs fair Pinnacle clôture     = (cote_entrée * P_fair_pinnacle_close - 1)*100
        -> CLV vs la "vérité" sharp.
  - Contrôle : on rejoue en pariant le côté OPPOSÉ (doit être négatif).
  - Option : si backtest_tennis.csv est présent, taux de victoire réel du côté
    suivi vs proba implicite de clôture (le CLV bat-il aussi le résultat ?).

Réglages env : MOVE_MIN (def 0.02), MIN_LEAD (def 15 min), SHARP (def pinnacle),
               CURVES (def book_curves.jsonl), CAP_FAIR_JUMP (def 0.4 anti-artefact).
Lecture seule. Aucun appel API.
"""
import json, os, csv, unicodedata, re, statistics as st
from datetime import datetime

CURVES = os.environ.get('CURVES', 'book_curves.jsonl')
RESULTS_CSV = os.environ.get('RESULTS_CSV', 'backtest_tennis.csv')
SHARP = os.environ.get('SHARP_BOOK', 'pinnacle')
MOVE_MIN = float(os.environ.get('MOVE_MIN', '0.02'))
MIN_LEAD = float(os.environ.get('MIN_LEAD', '15'))
CAP_FAIR_JUMP = float(os.environ.get('CAP_FAIR_JUMP', '0.4'))


def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).timestamp()
    except Exception:
        return None


def _norm(s):
    s = unicodedata.normalize('NFD', str(s).lower().strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[.\s]+', ' ', s).strip()


def _ln(s):
    t = [x for x in _norm(s).split() if x not in ('jr', 'sr', 'ii', 'iii', 'iv')]
    return t[-1] if t else ''


def load_curves():
    """{uid: {book: {'h':[(t,o)], 'a':[(t,o)]}, '_commence': ts, '_home':, '_away':}}"""
    data = {}
    for line in open(CURVES, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        h = [(_dt(t), o) for t, o in r.get('home_curve', []) if _dt(t) and o]
        a = [(_dt(t), o) for t, o in r.get('away_curve', []) if _dt(t) and o]
        if len(h) < 3 or len(a) < 3:
            continue
        d = data.setdefault(r['uid'], {})
        d[r['book']] = {'h': sorted(h), 'a': sorted(a)}
        d['_commence'] = _dt(r.get('commence_time'))
        d['_home'] = r.get('home_team') or r.get('home') or ''
        d['_away'] = r.get('away_team') or r.get('away') or ''
    return data


def _at(series, t):
    v = None
    for tt, o in series:
        if tt <= t:
            v = o
        else:
            break
    return v


def _fair(bk, t):
    oh, oa = _at(bk['h'], t), _at(bk['a'], t)
    if oh and oa and oh > 1.01 and oa > 1.01:
        ih, ia = 1 / oh, 1 / oa
        return ih / (ih + ia)
    return None


def load_results():
    """{uid: home_won(bool)} si dispo, sinon {}."""
    if not os.path.exists(RESULTS_CSV):
        return {}
    out = {}
    try:
        rows = list(csv.DictReader(open(RESULTS_CSV, encoding='utf-8', errors='replace'), delimiter=';'))
        for r in rows:
            res = (r.get('resultat') or '').strip()
            if res not in ('0', '1'):
                continue
            uid = r.get('uid')
            # joueurA == home ?
            out[uid] = {'a_won': res == '1', 'ja': r.get('joueurA', '')}
    except Exception:
        return {}
    return out


def detect_entry(pin):
    """Forward-only : 1er instant où |drift de la proba dévigée| >= MOVE_MIN.
    Renvoie (t_entry, side, fair_open, fair_entry) ou None."""
    times = sorted(set(t for t, _ in pin['h']))
    if len(times) < 3:
        return None
    f0 = _fair(pin, times[0])
    if f0 is None:
        return None
    for t in times[1:]:
        f = _fair(pin, t)
        if f is None:
            continue
        if abs(f - f0) > CAP_FAIR_JUMP:        # saut impossible -> artefact, on ignore ce point
            continue
        if abs(f - f0) >= MOVE_MIN:
            return (t, 'home' if f > f0 else 'away', f0, f)
    return None


def backtest():
    data = load_curves()
    results = load_results()
    softbooks = sorted({b for m in data.values() for b in m
                        if not b.startswith('_') and b != SHARP})
    print(f"{CURVES} : {len(data)} matchs | books mous : {softbooks or '(aucun)'}")
    print(f"règles : move>={MOVE_MIN} (forward-only) | entrée >= {MIN_LEAD:.0f}min avant match\n")
    if not softbooks:
        print("Aucun book mou dans les courbes — rien à backtester.")
        return

    follow_own, follow_pin, opp_own = [], [], []
    win_follow, imp_close = [], []     # validation résultat (optionnelle)
    n_entries = 0

    for uid, bk in data.items():
        if SHARP not in bk:
            continue
        pin = bk[SHARP]
        commence = bk.get('_commence')
        ent = detect_entry(pin)
        if not ent:
            continue
        t_e, side, f0, f_e = ent
        # contrainte de timing : assez tôt avant le match
        if commence is not None:
            lead = (commence - t_e) / 60.0
            if lead < MIN_LEAD:
                continue
        n_entries += 1

        # fair Pinnacle à la clôture (dernier point)
        t_close = sorted(set(t for t, _ in pin['h']))[-1]
        fc = _fair(pin, t_close)
        pclose_side = None
        if fc is not None:
            pclose_side = fc if side == 'home' else (1 - fc)

        for sb in softbooks:
            if sb not in bk:
                continue
            ser = bk[sb]['h'] if side == 'home' else bk[sb]['a']
            oser = bk[sb]['a'] if side == 'home' else bk[sb]['h']
            entry = _at(ser, t_e)
            if not entry or entry <= 1 or not ser:
                continue
            close = ser[-1][1]
            if close and close > 1:
                follow_own.append((entry / close - 1) * 100)
            if pclose_side and pclose_side > 0:
                follow_pin.append((entry * pclose_side - 1) * 100)
            # contrôle côté opposé
            e2 = _at(oser, t_e); c2 = oser[-1][1] if oser else None
            if e2 and c2 and e2 > 1 and c2 > 1:
                opp_own.append((e2 / c2 - 1) * 100)

        # validation résultat (côté suivi)
        r = results.get(uid)
        if r and pclose_side is not None:
            a_is_home = _ln(r['ja']) == _ln(bk.get('_home', ''))
            home_won = r['a_won'] if a_is_home else (not r['a_won'])
            side_won = home_won if side == 'home' else (not home_won)
            win_follow.append(1 if side_won else 0)
            imp_close.append(pclose_side)

    def rep(name, lst, unit='%'):
        if not lst:
            print(f"  {name:34}: (vide)")
            return
        pos = 100 * sum(1 for x in lst if x > 0) / len(lst)
        print(f"  {name:34}: n={len(lst):3d} | moyen {st.mean(lst):+.2f}{unit} | "
              f"médian {st.median(lst):+.2f}{unit} | %positif {pos:.0f}%")

    print(f"=== {n_entries} entrées déclenchées (1/match) ===\n")
    print("CLV (le seul juge) :")
    rep("Suivre le move vs clôture book", follow_own)
    rep("Suivre le move vs fair Pinnacle", follow_pin)
    rep("Contrôle: opposé vs clôture book", opp_own)

    if win_follow:
        wr = 100 * st.mean(win_follow)
        impc = 100 * st.mean(imp_close)
        print(f"\nValidation résultat (côté suivi) : gagne {wr:.0f}% | "
              f"implicite clôture {impc:.0f}% | n={len(win_follow)}")
        print("  (gagne ≈ implicite clôture = normal ; le gain vient du CLV, pas de battre Pinnacle)")

    print("\n  Rappel : CLV positif = prix battu. EV net dépend de la marge encaissée et")
    print("  du gubbing. Conclure demande du volume multi-books — laisse la capture tourner.")


if __name__ == '__main__':
    backtest()
