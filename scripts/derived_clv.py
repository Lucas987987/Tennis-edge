#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
derived_clv.py — Mesure le CLV des SIGNAUX DÉRIVÉS (book mou vs fair Pinnacle).

Sur les marchés totals (total jeux) et spreads (handicap jeux), pour chaque book
mou qui offre une cote supérieure au "fair" Pinnacle dévigé : est-ce que ce prix
bat la clôture Pinnacle du MÊME marché/MÊME ligne ? (CLV = la seule preuve d'edge.)

Pourquoi ce marché est plus propre que le moneyline :
  - Chaque point de games_markets.json['history'] est un snapshot MULTI-BOOKS
    SYNCHRONE -> comparer book mou vs Pinnacle au même instant n'a pas l'artefact
    d'asynchronisme qui faussait les courbes moneyline.

Définitions :
  - fair Pinnacle(outcome) = dévigage des 2 issues du marché à la même ligne L.
  - signal = à l'instant t, cote book mou * P_fair_Pinnacle_t(outcome) - 1 > EV_MIN.
  - CLV%   = (cote book mou * P_fair_Pinnacle_CLÔTURE(outcome, ligne L) - 1) * 100.
             > 0 = le prix pris battait la clôture sharp.

Comparaison ligne IDENTIQUE obligatoire (Over 21.5 != Over 22.5). Les paires de
lignes différentes sont comptées à part (à interpoler dans une v2 si besoin).

PRÉREQUIS : games_markets.json avec le champ 'books' par point (patch multi-books).
Tant qu'aucun book mou n'y figure (capture Pinnacle seule), le script le signale.

Réglages env : EV_MIN (def 0.02), DERIVED_FILE (def games_markets.json),
               SHARP (def pinnacle), CLOSE_MAX_MIN (def 45 : fenêtre clôture fiable).
Lecture seule. Aucun appel API.
"""
import json, os, statistics as st
from datetime import datetime

DERIVED_FILE = os.environ.get('DERIVED_FILE', 'games_markets.json')
SHARP = os.environ.get('SHARP_BOOK', 'pinnacle')
EV_MIN = float(os.environ.get('EV_MIN', '0.02'))
CLOSE_MAX_MIN = float(os.environ.get('CLOSE_MAX_MIN', '45'))

MARKETS = {'totals': ('over', 'under'), 'spreads': ('home', 'away')}


def _dt(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).timestamp()
    except Exception:
        return None


def _mins_before(point, commence_ts):
    """Minutes avant match pour un point (recalcul depuis t si possible)."""
    if commence_ts is not None:
        t = _dt(point.get('t'))
        if t is not None:
            return (commence_ts - t) / 60.0
    return point.get('mins_before')


def _book_market(point, book, market):
    """Renvoie le dict du marché (ex {'over':{price,point},'under':{...}}) pour
    un book donné dans un point d'history. Gère le champ 'books' + repli Pinnacle."""
    books = point.get('books') or {}
    if book in books and books[book].get(market):
        return books[book][market]
    # repli rétro-compat : champ Pinnacle au niveau du point
    if book == SHARP and point.get(market):
        return point.get(market)
    return None


def _line(mkt, outcome):
    """Ligne (point) d'une issue, ex Over 21.5 -> 21.5 ; handicap home -1.5 -> -1.5."""
    o = (mkt or {}).get(outcome)
    return o.get('point') if o else None


def _price(mkt, outcome):
    o = (mkt or {}).get(outcome)
    return o.get('price') if o else None


def _fair(mkt, outcome, outcomes):
    """P dévigée d'une issue à partir des 2 cotes du marché (même ligne supposée)."""
    o1, o2 = outcomes
    p1, p2 = _price(mkt, o1), _price(mkt, o2)
    if not (p1 and p2 and p1 > 1 and p2 > 1):
        return None
    # lignes cohérentes entre les 2 issues ?
    l1, l2 = _line(mkt, o1), _line(mkt, o2)
    if l1 is not None and l2 is not None:
        if (o1, o2) == ('over', 'under') and l1 != l2:
            return None                      # over/under doivent partager la ligne
    inv1, inv2 = 1 / p1, 1 / p2
    fair = inv1 / (inv1 + inv2)
    return fair if outcome == o1 else (1 - fair)


def analyze():
    try:
        data = json.load(open(DERIVED_FILE, encoding='utf-8'))
    except Exception as e:
        print(f"Impossible de lire {DERIVED_FILE} : {e}")
        return
    print(f"{DERIVED_FILE} : {len(data)} matchs | EV_min={EV_MIN} | clôture<= {CLOSE_MAX_MIN:.0f}min\n")

    # books mous présents ?
    soft_seen = set()
    for m in data.values():
        for p in m.get('history', []):
            for b in (p.get('books') or {}):
                if b != SHARP:
                    soft_seen.add(b)
    if not soft_seen:
        print("⚠️  Aucun book mou dans 'books' — capture encore Pinnacle seule.")
        print("    Laisse tourner la capture élargie (games_markets patché), puis relance.")
        return
    print(f"books mous détectés : {sorted(soft_seen)}\n")

    sig_clv = []          # CLV des signaux (EV>EV_MIN à l'entrée)
    all_clv = []          # CLV de TOUTES les comparaisons valides (baseline)
    n_line_mismatch = 0
    n_no_close = 0

    for uid, m in data.items():
        hist = m.get('history', [])
        if len(hist) < 2:
            continue
        cts = _dt(m.get('commence_time'))

        # point de clôture = dernier point fiable avant match (mins_before in [0, CLOSE_MAX_MIN])
        close_pt = None
        for p in hist:
            mb = _mins_before(p, cts)
            if mb is None:
                continue
            if -2 <= mb <= CLOSE_MAX_MIN:
                close_pt = p          # le dernier qui satisfait = le plus tardif
        if close_pt is None:
            # repli : dernier point disponible
            close_pt = hist[-1]

        for p in hist:
            if p is close_pt:
                continue
            for market, outcomes in MARKETS.items():
                pin_t = _book_market(p, SHARP, market)
                pin_c = _book_market(close_pt, SHARP, market)
                if not pin_t or not pin_c:
                    continue
                for sb in (p.get('books') or {}):
                    if sb == SHARP:
                        continue
                    soft = _book_market(p, sb, market)
                    if not soft:
                        continue
                    for oc in outcomes:
                        p_soft = _price(soft, oc)
                        L = _line(soft, oc)
                        if not p_soft or p_soft <= 1 or L is None:
                            continue
                        # ligne identique chez Pinnacle à l'instant t ?
                        if _line(pin_t, oc) != L:
                            n_line_mismatch += 1
                            continue
                        fair_t = _fair(pin_t, oc, outcomes)
                        if fair_t is None:
                            continue
                        # clôture Pinnacle : même ligne ?
                        if _line(pin_c, oc) != L:
                            n_no_close += 1
                            continue
                        fair_c = _fair(pin_c, oc, outcomes)
                        if fair_c is None:
                            n_no_close += 1
                            continue
                        ev_entry = p_soft * fair_t - 1
                        clv = (p_soft * fair_c - 1) * 100
                        all_clv.append(clv)
                        if ev_entry > EV_MIN:
                            sig_clv.append(clv)

    def rep(name, lst):
        if not lst:
            print(f"  {name:28}: (aucune donnée)")
            return
        pos = 100 * sum(1 for x in lst if x > 0) / len(lst)
        print(f"  {name:28}: n={len(lst):4d} | CLV moyen {st.mean(lst):+.2f}% | "
              f"médian {st.median(lst):+.2f}% | %positif {pos:.0f}%")

    print("=== CLV vs clôture Pinnacle (même marché, même ligne) ===")
    rep("SIGNAUX (EV>seuil à l'entrée)", sig_clv)
    rep("baseline (toutes compar.)", all_clv)
    print(f"\n  lignes différentes ignorées : {n_line_mismatch} | clôture absente : {n_no_close}")

    if sig_clv and all_clv:
        edge = st.mean(sig_clv) - st.mean(all_clv)
        print(f"\n  Écart signal vs baseline : {edge:+.2f} pts de CLV")
        if st.mean(sig_clv) > 0.5 and edge > 0.3:
            print("  => Les signaux dérivés battent la clôture. Piste à creuser (volume, exécution).")
        else:
            print("  => Pas d'edge : les signaux ne battent pas la clôture (comme le moneyline).")
    print("\n  Rappel : conclure demande du volume. Quelques dizaines de matchs multi-books minimum.")


if __name__ == '__main__':
    analyze()
