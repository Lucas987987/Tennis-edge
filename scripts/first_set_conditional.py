#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
first_set_conditional.py — P(favori gagne le match | il a PERDU le 1er set).

Étude DESCRIPTIVE (pas un signal de pari : c'est une quantité in-play, et le
marché live se recale après le set 1). Sert à comprendre la valeur prédictive
du 1er set, segmentée par cote du favori, format (BO3/BO5) et surface.

Données : CSV tennis-data.co.uk (les mêmes que le workflow Elo). Chaque ligne
donne le favori d'avant-match (cote la plus basse : PSW vs PSL, sinon AvgW/AvgL,
sinon B365W/B365L), le vainqueur du 1er set (W1 vs L1, du point de vue du
vainqueur du match) et le résultat final (Winner/Loser).

Sorties :
  - références : P(favori gagne), P(favori gagne | a GAGNÉ set1),
                 P(favori gagne | a PERDU set1)
  - tables P(favori gagne | a perdu set1) par tranche de cote du favori,
    séparées BO3 / BO5, avec n, taux, IC95 de Wilson, et l'implicite pré-match
    dévigé en référence (≠ proba live).
Garde-fou : ✅/chiffre fiable seulement si n >= MIN_N (défaut 30) ; sinon (n<MIN_N).

USAGE :
    python scripts/first_set_conditional.py data/*.csv
    python scripts/first_set_conditional.py --selftest
ENV : FS_MIN_N (défaut 30)
"""

import os, sys, math, glob
import pandas as pd

MIN_N = int(os.environ.get('FS_MIN_N', '30'))
FAV_BUCKETS = [(1.01, 1.30), (1.30, 1.50), (1.50, 1.70), (1.70, 2.00)]


# --------------------------------------------------------------------------- #
def _odds(row):
    """Renvoie (cote_vainqueur, cote_perdant) en privilégiant Pinnacle."""
    for w, l in (('PSW', 'PSL'), ('AvgW', 'AvgL'), ('B365W', 'B365L')):
        ow, ol = row.get(w), row.get(l)
        if pd.notna(ow) and pd.notna(ol) and float(ow) > 1 and float(ol) > 1:
            return float(ow), float(ol)
    return None, None


def load(paths):
    frames = []
    for p in paths:
        try:
            frames.append(pd.read_csv(p, encoding='utf-8', low_memory=False))
        except UnicodeDecodeError:
            frames.append(pd.read_csv(p, encoding='latin-1', low_memory=False))
    if not frames:
        return []
    df = pd.concat(frames, ignore_index=True)
    if not ({'Winner', 'Loser'} <= set(df.columns)):
        raise SystemExit("Format attendu : tennis-data.co.uk (colonnes Winner/Loser).")

    out = []
    for _, r in df.iterrows():
        ow, ol = _odds(r)
        if ow is None:
            continue
        try:
            w1, l1 = r.get('W1'), r.get('L1')
            if pd.isna(w1) or pd.isna(l1):
                continue
            w1, l1 = int(w1), int(l1)
        except (ValueError, TypeError):
            continue
        if w1 == l1:                       # set 1 ne peut pas être nul ; bruit -> skip
            continue

        winner_is_fav = ow < ol            # le favori est-il le vainqueur du match ?
        fav_odds = min(ow, ol)
        iw, il = 1.0 / ow, 1.0 / ol
        fav_implied = (iw if winner_is_fav else il) / (iw + il)   # dévigé
        winner_won_set1 = w1 > l1
        fav_won_set1 = winner_won_set1 if winner_is_fav else (not winner_won_set1)

        try:
            bo = int(r.get('Best of')) if pd.notna(r.get('Best of')) else None
        except (ValueError, TypeError):
            bo = None

        out.append({
            'fav_odds': fav_odds, 'fav_implied': fav_implied,
            'fav_won_set1': fav_won_set1, 'fav_won_match': winner_is_fav,
            'best_of': bo, 'surface': str(r.get('Surface', 'Unknown')),
        })
    return out


# --------------------------------------------------------------------------- #
def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def rate(matches, cond):
    sub = [m for m in matches if cond(m)]
    n = len(sub)
    k = sum(1 for m in sub if m['fav_won_match'])
    lo, hi = wilson(k, n)
    return n, (k / n if n else 0.0), lo, hi, sub


def line(label, n, p, lo, hi, implied=None):
    flag = "" if n >= MIN_N else f"  (n<{MIN_N})"
    imp = f"   impl.pré {implied*100:5.1f}%" if implied is not None else ""
    print(f"  {label:14s} {n:5d}   {p*100:5.1f}%   "
          f"[{lo*100:5.1f};{hi*100:5.1f}]{imp}{flag}")


def table_by_bucket(matches, bo, title):
    sub = [m for m in matches if (bo is None or m['best_of'] == bo)
           and not m['fav_won_set1']]              # favori a PERDU le set 1
    print(f"\n--- {title} : P(favori gagne | a perdu le set 1) par cote du favori ---")
    print(f"  {'cote favori':14s} {'n':>5s}   {'taux':>6s}   {'IC95(Wilson)':>14s}")
    if not sub:
        print("  (aucun match)"); return
    for lo_b, hi_b in FAV_BUCKETS:
        b = [m for m in sub if lo_b <= m['fav_odds'] < hi_b]
        n = len(b)
        k = sum(1 for m in b if m['fav_won_match'])
        impl = sum(m['fav_implied'] for m in b) / n if n else None
        lo, hi = wilson(k, n)
        line(f"{lo_b:.2f}-{hi_b:.2f}", n, (k / n if n else 0.0), lo, hi, impl)


def report(matches):
    print("=" * 74)
    print("FIRST-SET CONDITIONAL — P(favori gagne le match | a perdu le set 1)")
    print("=" * 74)
    n_lost = sum(1 for m in matches if not m['fav_won_set1'])
    print(f"matchs valides : {len(matches)} | dont favori a perdu le set 1 : {n_lost}")

    print("\nRéférences (tous matchs valides) :")
    n, p, lo, hi, _ = rate(matches, lambda m: True)
    line("fav gagne", n, p, lo, hi)
    n, p, lo, hi, _ = rate(matches, lambda m: m['fav_won_set1'])
    line("| a GAGNÉ s1", n, p, lo, hi)
    n, p, lo, hi, _ = rate(matches, lambda m: not m['fav_won_set1'])
    line("| a PERDU s1", n, p, lo, hi)
    print("   ^ c'est la question : un favori qui lâche le 1er set.")

    for bo, title in ((3, "Best-of-3"), (5, "Best-of-5")):
        if any(m['best_of'] == bo for m in matches):
            table_by_bucket(matches, bo, title)
    # surfaces (tous formats confondus)
    surfs = sorted({m['surface'] for m in matches if not m['fav_won_set1']})
    if len(surfs) > 1:
        print("\n--- Par surface (tous formats) : P(favori gagne | a perdu set 1) ---")
        print(f"  {'surface':14s} {'n':>5s}   {'taux':>6s}   {'IC95(Wilson)':>14s}")
        for s in surfs:
            n, p, lo, hi, _ = rate(matches,
                                   lambda m, s=s: (not m['fav_won_set1']) and m['surface'] == s)
            line(s, n, p, lo, hi)

    print(f"\n(n<{MIN_N}) = échantillon trop faible, à ignorer. "
          "Rappel : quantité in-play, descriptive — pas un signal de pari.")


# --------------------------------------------------------------------------- #
def selftest():
    import random
    random.seed(11)

    def sim_match(s, best_of):
        """s = proba du favori par set. Renvoie (fav_won_set1, fav_won_match)."""
        need = best_of // 2 + 1
        fav = dog = 0; first = None
        while fav < need and dog < need:
            fav_wins_set = random.random() < s
            if first is None:
                first = fav_wins_set
            if fav_wins_set: fav += 1
            else: dog += 1
        return first, (fav >= need)

    def p_match(s, best_of):                # proba match du favori (analytique BO3/BO5)
        if best_of == 3:
            return s**2 + 2 * s**2 * (1 - s)
        return s**3 + 3*s**3*(1-s) + 6*s**3*(1-s)**2

    rows = []
    for _ in range(20000):
        best_of = random.choice([3, 3, 3, 5])          # majorité BO3
        s = random.uniform(0.52, 0.80)                 # force par set du favori
        fav_s1, fav_win = sim_match(s, best_of)
        pm = p_match(s, best_of)
        fair_fav, fair_dog = pm, 1 - pm
        # cotes avec vig 4%, du point de vue Winner/Loser
        if fav_win:
            psw, psl = 1/(fair_fav*1.04), 1/(fair_dog*1.04)
            w1, l1 = (6, random.randint(0, 4)) if fav_s1 else (random.randint(0, 4), 6)
        else:
            psw, psl = 1/(fair_dog*1.04), 1/(fair_fav*1.04)
            # winner = dog ; fav_s1 True => fav a gagné s1 => winner(dog) a perdu s1
            w1, l1 = (random.randint(0, 4), 6) if fav_s1 else (6, random.randint(0, 4))
        rows.append({'Winner': 'W', 'Loser': 'L', 'PSW': round(psw, 3),
                     'PSL': round(psl, 3), 'W1': w1, 'L1': l1,
                     'Best of': best_of, 'Surface': random.choice(['Hard', 'Clay', 'Grass'])})
    path = '/home/claude/_synth_fs.csv'
    pd.DataFrame(rows).to_csv(path, index=False)
    report(load([path]))


def main():
    if '--selftest' in sys.argv:
        selftest(); return
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    paths = args or sorted(glob.glob('data/*.csv')) or sorted(glob.glob('*.csv'))
    if not paths:
        raise SystemExit("Aucun CSV. Donne des chemins, ou utilise --selftest.")
    m = load(paths)
    if not m:
        raise SystemExit("Aucun match valide (cotes + set 1 requis).")
    report(m)


if __name__ == '__main__':
    main()
