#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book_asymmetry.py — Asymetrie des books mous face aux moves Pinnacle.

PRE-ENREGISTREMENT (2026-06-12) : seuils fixes avant lecture des chiffres.

Intuition observee (Cirstea, Dart, Sonmez...) : les books mous SUIVENT VITE les
raccourcissements (steam) et TRAINENT sur les allongements (drift) — monter une
cote augmente leur exposition, la baisser ne coute rien. Consequence attendue :
le cote qui DERIVE est tres en-dessous du juste prix chez le book mou, le cote
STEAME est "presque correct".

Etude 100% MECANIQUE (pas besoin de resultats de matchs => n solide vite) :
pour chaque COTE de match dont le move Pinnacle open->close est >= MOVE_MIN
(3%), dans chaque book mou disponible :

  B1 EDGE RESIDUEL A LA CLOTURE : cote du book a sa cloture vs juste prix
     Pinnacle devige. Moyenne par sens du move (steam vs drift).
     -> chiffre exactement "ou la porte est la moins fermee".

  B2 TAUX DE SUIVI : move du book / move de Pinnacle (meme cote, open->close).
     ~1 = suit entierement, ~0 = ignore. Par sens du move.
     -> asymetrie de mise a jour confirmee si suivi(steam) >> suivi(drift).

  B3 RETARD TEMPOREL (matchs avec courbes des deux cotes) : minutes entre le
     moment ou Pinnacle a fait 50% de son move et celui ou le book l'a fait.
     Mediane par sens.

Garde-fou n >= MIN_N (30) par case ; [DIR] en dessous.
Sources (lecture seule, AUCUNE API) :
  CLV_FILE=clv_history.jsonl (Pinnacle)   BOOK_FILE=book_curves.jsonl (mous)
"""
import json, os, sys, datetime, statistics as st

CLV_FILE  = os.environ.get('CLV_FILE', 'clv_history.jsonl')
BOOK_FILE = os.environ.get('BOOK_FILE', 'book_curves.jsonl')
MIN_N     = int(os.environ.get('MIN_N', '30'))
MOVE_MIN  = float(os.environ.get('MOVE_MIN', '3.0'))   # % move Pinnacle minimal


def parse_dt(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None


def load_jsonl(path, key):
    """Charge un jsonl en dict key->entry (la DERNIERE occurrence fait foi :
    courbe la plus complete)."""
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            k = key(e)
            if k:
                out[k] = e
    return out


def t50(curve_raw, start, open_p, close_p):
    """Premier instant ou la courbe a parcouru 50% du chemin open->close
    (points pre-match uniquement). None si introuvable."""
    if not curve_raw or open_p is None or close_p is None:
        return None
    total = close_p - open_p
    if total == 0:
        return None
    mid = open_p + total / 2.0
    for t, p in curve_raw:
        dt = parse_dt(t)
        if dt is None or (start is not None and dt > start):
            continue
        if (total > 0 and p >= mid) or (total < 0 and p <= mid):
            return dt
    return None


def main():
    pinn = load_jsonl(CLV_FILE, lambda e: str(e.get('fixture_id') or ''))
    books_raw = {}
    if os.path.exists(BOOK_FILE):
        with open(BOOK_FILE, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                fid, book = str(e.get('fixture_id') or ''), e.get('book')
                if fid and book:
                    books_raw[(fid, book)] = e
    if not pinn or not books_raw:
        print(f"❌ donnees manquantes ({CLV_FILE}: {len(pinn)} | {BOOK_FILE}: {len(books_raw)})")
        sys.exit(0)

    book_names = sorted(set(b for _, b in books_raw.keys()))
    print(f"=== book_asymmetry — {len(pinn)} matchs Pinnacle, books: {', '.join(book_names)} ===")
    print(f"(exploration pre-enregistree 2026-06-12 — mecanique, [DIR] = n<{MIN_N})")
    print(f"unite = un COTE de match avec |move Pinnacle| >= {MOVE_MIN:.0f}%\n")

    for book in book_names:
        rows = []   # un par côté éligible
        for (fid, b), be in books_raw.items():
            if b != book:
                continue
            pe = pinn.get(fid)
            if not pe:
                continue
            start = parse_dt(pe.get('commence_time'))
            for side, other in (('home', 'away'), ('away', 'home')):
                pm = pe.get(f'{side}_metrics') or {}
                po = pe.get(f'{other}_metrics') or {}
                bm = be.get(f'{side}_metrics') or {}
                if pm.get('move_pct') is None or pm.get('open') is None or pm.get('close') is None:
                    continue
                if abs(pm['move_pct']) < MOVE_MIN:
                    continue
                direction = 'steam' if pm['move_pct'] < 0 else 'drift'
                # B1 : edge résiduel du book à SA clôture vs juste prix Pinnacle
                edge = None
                try:
                    a = 1.0 / float(pm['close']); c = 1.0 / float(po['close'])
                    p_fair = a / (a + c)                      # proba dévigée du côté
                    fair_odds = 1.0 / p_fair
                    if bm.get('close'):
                        edge = float(bm['close']) / fair_odds - 1.0
                except (TypeError, ValueError, ZeroDivisionError, KeyError):
                    pass
                # B2 : taux de suivi (move book / move Pinnacle, même côté)
                follow = None
                if bm.get('move_pct') is not None and pm['move_pct'] != 0:
                    follow = bm['move_pct'] / pm['move_pct']
                    follow = max(-1.0, min(2.0, follow))      # bornes anti-aberration
                # B3 : retard temporel à 50% du move
                lag_min = None
                tp = t50(pe.get(f'{side}_curve'), start, pm['open'], pm['close'])
                tb = t50(be.get(f'{side}_curve'), start, bm.get('open'), bm.get('close')) \
                    if bm.get('open') and bm.get('close') else None
                if tp and tb:
                    lag_min = (tb - tp).total_seconds() / 60.0
                rows.append({'dir': direction, 'edge': edge, 'follow': follow, 'lag': lag_min})

        print(f"── {book} " + '─' * max(0, 58 - len(book)))
        if not rows:
            print("  aucun côté éligible (pas de recouvrement de matchs ?)\n")
            continue
        for d in ('steam', 'drift'):
            g = [r for r in rows if r['dir'] == d]
            n = len(g)
            if n == 0:
                print(f"  {d:<6} n=0")
                continue
            edges = [r['edge'] for r in g if r['edge'] is not None]
            follows = [r['follow'] for r in g if r['follow'] is not None]
            lags = [r['lag'] for r in g if r['lag'] is not None]
            tag = '' if n >= MIN_N else ' [DIR]'
            e_s = f"{st.mean(edges):+.1%} (med {st.median(edges):+.1%}, n={len(edges)})" if edges else '-'
            f_s = f"{st.mean(follows):.0%} (med {st.median(follows):.0%}, n={len(follows)})" if follows else '-'
            l_s = f"{st.median(lags):+.0f} min (n={len(lags)})" if lags else '-'
            print(f"  {d:<6} n={n:<4} edge vs juste prix: {e_s}{tag}")
            print(f"         suivi du move: {f_s} | retard median a 50%: {l_s}")
        print()

    print("Lecture :")
    print(" - edge(steam) >> edge(drift) (moins negatif) = l'asymetrie observee est structurelle.")
    print(" - suivi(steam) > suivi(drift) = le book met a jour plus vite vers le bas.")
    print(" - un edge moyen steam proche de 0 dirait OU regarder pendant les gros moves —")
    print("   mais seul un edge POSITIF persistant sur du frais justifierait d'aller plus loin.")


if __name__ == '__main__':
    main()
