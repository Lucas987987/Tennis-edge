#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
drift_outcome.py — La loi « réalisé ≈ clôture » sur TES données.

Pour chaque fixture (book_curves.jsonl, book sharp = bwin dévigé) :
  - proba d'OUVERTURE et de CLÔTURE du favori (dévigées) ;
  - drift = proba_clôture - proba_ouverture (>0 = le favori s'est renforcé) ;
  - le favori a-t-il gagné ? (résultat lu dans resultats_fast.json / resultats.json).

Sortie : par tranche de drift, le taux RÉALISÉ vs implicite OUVERTURE vs implicite
CLÔTURE. Si la loi tient : réalisé ≈ clôture (résidu ≈ 0), et l'ouverture est
biaisée du montant du drift. Garde-fou n>=30 : aucune conclusion sous le seuil.

Sources de résultats (priorité) : RESULTS_FILE puis RESULTS_FALLBACK.
Format attendu : {"results":[{"home_team","away_team","winner"(nom) ou
"winner_code"(1=home,2=away),"date",...}, ...]}.

Config (env) : BOOK_CURVES, SHARP_BOOK(bwin), RESULTS_FILE(resultats_fast.json),
RESULTS_FALLBACK(resultats.json).
"""
import json, os, csv, math, statistics as st, unicodedata, re
from datetime import datetime

BOOK_CURVES = os.environ.get('BOOK_CURVES', 'book_curves.jsonl')
SHARP_BOOK  = os.environ.get('SHARP_BOOK', 'bwin')
RESULTS_FILE = os.environ.get('RESULTS_FILE', 'resultats_fast.json')
RESULTS_FALLBACK = os.environ.get('RESULTS_FALLBACK', 'resultats.json')
N_MIN = 30


def toks(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    return frozenset(w for w in re.sub(r'[^a-z]', ' ', s).split() if len(w) >= 3)


def same(a, b):
    ta, tb = toks(a), toks(b)
    return bool(ta and tb) and (ta <= tb or tb <= ta or len(ta & tb) >= 2)


def parse(t):
    t = str(t).replace('Z', '').replace('.000', '')
    for f in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S'):
        try:
            return datetime.strptime(t[:26], f)
        except ValueError:
            pass


def devig(oh, oa):
    ph, pa = 1 / oh, 1 / oa
    s = ph + pa
    return ph / s, pa / s


def load_results():
    """Liste de (home, away, winner_name)."""
    out = []
    for path in (RESULTS_FILE, RESULTS_FALLBACK):
        if not path or not os.path.exists(path):
            continue
        data = json.load(open(path, encoding='utf-8'))
        for r in data.get('results', []):
            h, a = r.get('home_team', ''), r.get('away_team', '')
            w = r.get('winner', '')
            if not w and r.get('winner_code') in (1, 2):
                w = h if r['winner_code'] == 1 else a
            if h and a and w:
                out.append((h, a, w))
        if out:
            print(f"✅ résultats lus depuis {path} : {len(out)}")
            break
    return out


def fav_won(fav, opp, results):
    for h, a, w in results:
        if (same(fav, h) and same(opp, a)) or (same(fav, a) and same(opp, h)):
            return 1 if same(w, fav) else 0
    return None


def main():
    results = load_results()
    if not results:
        print("❌ Aucun fichier de résultats trouvé (resultats_fast.json / resultats.json).")
        print("   Uploade resultats_fast.json à la racine et relance.")
        return

    rows = []
    for line in open(BOOK_CURVES, encoding='utf-8'):
        if not line.strip():
            continue
        x = json.loads(line)
        if x.get('book') != SHARP_BOOK:
            continue
        com = parse(x['commence_time'])
        H = [z for z in sorted((parse(t), p) for t, p in (x.get('home_curve') or []) if p and parse(t)) if z[0] <= com]
        A = [z for z in sorted((parse(t), p) for t, p in (x.get('away_curve') or []) if p and parse(t)) if z[0] <= com]
        if len(H) < 2 or len(A) < 2:
            continue
        foh, fao = devig(H[0][1], A[0][1])
        fhc, fac = devig(H[-1][1], A[-1][1])
        if fhc >= fac:
            fav, opp, p_open, p_close = x['home'], x['away'], foh, fhc
        else:
            fav, opp, p_open, p_close = x['away'], x['home'], fao, fac
        won = fav_won(fav, opp, results)
        if won is None:
            continue
        rows.append({'fav': fav, 'p_open': p_open, 'p_close': p_close,
                     'drift': p_close - p_open, 'won': won})

    out = ["## Calibration drift -> résultat (favori, bwin dévigé)", ""]
    out.append(f"matchs avec drift ET résultat : {len(rows)}")
    if not rows:
        print("\n".join(out)); return

    won = [r['won'] for r in rows]
    realized = st.mean(won)
    mclose = st.mean([r['p_close'] for r in rows])
    mopen = st.mean([r['p_open'] for r in rows])
    bo = st.mean([(r['p_open'] - r['won']) ** 2 for r in rows])
    bc = st.mean([(r['p_close'] - r['won']) ** 2 for r in rows])
    out += [
        "",
        f"GLOBAL (n={len(rows)}):",
        f"  favori gagne réellement : {realized*100:.1f}%",
        f"  implicite OUVERTURE moy : {mopen*100:.1f}%   (biais ouverture = {(mopen-realized)*100:+.1f} pts)",
        f"  implicite CLÔTURE  moy  : {mclose*100:.1f}%   (biais clôture  = {(mclose-realized)*100:+.1f} pts)",
        f"  Brier ouverture={bo:.4f}  clôture={bc:.4f}  ({'clôture meilleure' if bc<bo else 'ouverture meilleure'})",
        "",
        "Par tranche de drift (proba clôture - ouverture, en points) :",
        f"  {'tranche':14s} {'n':>3s}  {'réalisé':>8s} {'i.ouvert':>9s} {'i.clôt':>8s} {'réel-clôt':>10s}",
    ]
    bins = [(-99, -3, 'forte dérive'), (-3, -1, 'légère dérive'), (-1, 1, 'stable'),
            (1, 3, 'léger steam'), (3, 99, 'fort steam')]
    for lo, hi, lab in bins:
        sub = [r for r in rows if lo <= r['drift'] * 100 < hi]
        if not sub:
            continue
        n = len(sub)
        rz = st.mean([r['won'] for r in sub]) * 100
        io = st.mean([r['p_open'] for r in sub]) * 100
        ic = st.mean([r['p_close'] for r in sub]) * 100
        flag = '' if n >= N_MIN else ' [n<30]'
        out.append(f"  {lab:14s} {n:>3d}  {rz:>7.1f}% {io:>8.1f}% {ic:>7.1f}% {rz-ic:>+9.1f}{flag}")

    out += ["", f"Lecture : si la loi tient, 'réel-clôt' ≈ 0 partout, et 'i.ouvert' "
            f"dévie dans le sens du drift.", ]
    if len(rows) < N_MIN:
        out.append(f"⚠️ n={len(rows)} < {N_MIN} au global : tendance seulement, pas de conclusion.")

    report = "\n".join(out)
    print("\n" + report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8').write(report + "\n")


if __name__ == '__main__':
    main()
