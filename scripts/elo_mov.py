#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
elo_mov.py — Elo tennis avec marge de victoire (MOV) + K dynamique,
             ET comparaison du log-loss vs Pinnacle dévigé.

OBJECTIF (étape 2 du plan) : trancher si améliorer l'Elo referme l'écart au
marché sharp. Le script fait passer plusieurs variantes sur TES données, en
ordre chronologique (zéro fuite : la proba est calculée AVANT de connaître le
résultat, puis la note est mise à jour), et imprime pour chaque variante :
  - log-loss et Brier de l'Elo
  - log-loss et Brier de Pinnacle dévigé, SUR LE MÊME jeu de matchs
  - l'écart Elo - Pinnacle (négatif = l'Elo fait mieux que Pinnacle ; quasi
    toujours positif → l'Elo NE bat PAS le marché, c'est attendu)

VARIANTES comparées :
  1. Elo std            : K fixe, pas de MOV
  2. Elo +Kdyn          : K dynamique 250/((parties+5)^0.4)  [FiveThirtyEight]
  3. Elo +Kdyn +MOV     : en plus, mise à jour pondérée par la marge en jeux
Toutes partagent le même blend surface/global et le même set d'évaluation.

VERDICT : si la meilleure variante ne referme pas l'écart à Pinnacle de façon
nette, l'angle « meilleure estimation de force » est mort → on s'arrête là
(cf. discipline : prédictif ≠ rentable).

ENTRÉE : un ou plusieurs CSV. Deux formats auto-détectés :
  A) tennis-data.co.uk  (colonnes Winner, Loser, PSW, PSL, W1..L5, Best of,
     Surface, Date) → permet la comparaison Pinnacle (colonnes PSW/PSL).
  B) Sackmann          (winner_name, loser_name, score, surface, tourney_date,
     best_of) → calcule l'Elo, MAIS pas de cotes Pinnacle dans ce format :
     le script le signale et n'imprime pas le verdict marché.

USAGE (sur GitHub Actions ou en local) :
    python scripts/elo_mov.py data/2021.csv data/2022.csv data/2023.csv ...
    python scripts/elo_mov.py            # cherche ./data/*.csv puis ./*.csv
    python scripts/elo_mov.py --selftest # test synthétique (pas de réseau)

RÉGLAGES (variables d'environnement, tous optionnels) :
    ELO_SURFACE_W   poids du blend surface (0=global pur, 1=surface pur)  [0.5]
    ELO_K_FIXED     K de la variante standard                            [32]
    ELO_MIN_MATCHES n mini de matchs joués par CHAQUE joueur pour qu'un
                    match compte dans l'évaluation (burn-in)             [10]
    ELO_MOV_CAP     borne du multiplicateur MOV [0.5 .. ELO_MOV_CAP]     [2.0]
    ELO_INIT        note initiale                                       [1500]
"""

import os, sys, math, glob, json
import pandas as pd

SURFACE_W   = float(os.environ.get('ELO_SURFACE_W', '0.5'))
K_FIXED     = float(os.environ.get('ELO_K_FIXED', '32'))
MIN_MATCHES = int(os.environ.get('ELO_MIN_MATCHES', '10'))
MOV_CAP     = float(os.environ.get('ELO_MOV_CAP', '2.0'))
INIT        = float(os.environ.get('ELO_INIT', '1500'))
EPS         = 1e-12


# --------------------------------------------------------------------------- #
# Chargement & normalisation
# --------------------------------------------------------------------------- #
def _games_from_sets(row, n=5):
    """Somme des jeux gagnés par le vainqueur / le perdant (tennis-data W1..L5)."""
    w = l = 0
    for i in range(1, n + 1):
        try:
            wi = row.get(f'W{i}'); li = row.get(f'L{i}')
            if pd.notna(wi) and pd.notna(li):
                w += int(wi); l += int(li)
        except (ValueError, TypeError):
            pass
    return w, l


def _games_from_score(score):
    """Parse une chaîne Sackmann '6-4 7-6(5) 6-3' -> (jeux_gagnant, jeux_perdant)."""
    if not isinstance(score, str):
        return 0, 0
    w = l = 0
    for tok in score.replace(',', ' ').split():
        t = tok.split('(')[0]              # retire le tie-break (5)
        if '-' in t:
            a, _, b = t.partition('-')
            try:
                w += int(a); l += int(b)
            except ValueError:
                continue
    return w, l


def load_matches(paths):
    """Renvoie (liste de dicts triée par date, has_pinnacle:bool, fmt:str)."""
    frames = []
    for p in paths:
        try:
            frames.append(pd.read_csv(p, encoding='utf-8', low_memory=False))
        except UnicodeDecodeError:
            frames.append(pd.read_csv(p, encoding='latin-1', low_memory=False))
    if not frames:
        return [], False, 'none'
    df = pd.concat(frames, ignore_index=True)
    cols = set(df.columns)

    matches = []
    if {'Winner', 'Loser'} <= cols:                      # tennis-data.co.uk
        fmt = 'tennis-data'
        has_ps = {'PSW', 'PSL'} <= cols
        df['_d'] = pd.to_datetime(df.get('Date'), errors='coerce', dayfirst=True)
        df = df.sort_values('_d', kind='stable')
        for _, r in df.iterrows():
            wg, lg = _games_from_sets(r)
            psw = r.get('PSW'); psl = r.get('PSL')
            matches.append({
                'date': r['_d'], 'surface': str(r.get('Surface', 'Unknown')),
                'winner': str(r['Winner']).strip(), 'loser': str(r['Loser']).strip(),
                'wg': wg, 'lg': lg,
                'psw': float(psw) if has_ps and pd.notna(psw) else None,
                'psl': float(psl) if has_ps and pd.notna(psl) else None,
            })
    elif {'winner_name', 'loser_name'} <= cols:          # Sackmann
        fmt = 'sackmann'; has_ps = False
        dcol = 'tourney_date' if 'tourney_date' in cols else 'date'
        df['_d'] = pd.to_datetime(df.get(dcol).astype(str), errors='coerce',
                                  format='mixed')
        df = df.sort_values('_d', kind='stable')
        for _, r in df.iterrows():
            wg, lg = _games_from_score(r.get('score'))
            matches.append({
                'date': r['_d'], 'surface': str(r.get('surface', 'Unknown')),
                'winner': str(r['winner_name']).strip(),
                'loser': str(r['loser_name']).strip(),
                'wg': wg, 'lg': lg, 'psw': None, 'psl': None,
            })
    else:
        raise SystemExit("Format CSV non reconnu (ni tennis-data ni Sackmann).")

    return matches, (fmt == 'tennis-data' and {'PSW', 'PSL'} <= cols), fmt


# --------------------------------------------------------------------------- #
# Moteur Elo
# --------------------------------------------------------------------------- #
def expected(diff):
    return 1.0 / (1.0 + 10.0 ** (-diff / 400.0))


def dyn_k(n):
    """K dynamique FiveThirtyEight : grand pour les nouveaux, décroît ensuite."""
    return 250.0 / ((n + 5.0) ** 0.4)


def mov_mult(wg, lg, elo_diff_winner):
    """Multiplicateur de marge (style 538, corrige l'auto-corrélation).
    Borné dans [0.5, MOV_CAP] pour éviter l'emballement des notes."""
    if wg + lg == 0:
        return 1.0
    margin = abs(wg - lg)
    m = math.log(margin + 1.0) * (2.2 / (0.001 * elo_diff_winner + 2.2))
    return max(0.5, min(MOV_CAP, m))


def maturity_mask(matches):
    """True pour les matchs où CHAQUE joueur a déjà >= MIN_MATCHES matchs.
    Dépend uniquement de l'ordre -> identique pour toutes les variantes."""
    cnt = {}; mask = []
    for m in matches:
        ok = cnt.get(m['winner'], 0) >= MIN_MATCHES and cnt.get(m['loser'], 0) >= MIN_MATCHES
        mask.append(ok)
        cnt[m['winner']] = cnt.get(m['winner'], 0) + 1
        cnt[m['loser']]  = cnt.get(m['loser'], 0) + 1
    return mask


def run_config(matches, mask, use_dyn_k, use_mov):
    """Passe chronologique. Renvoie la liste des probas assignées au VRAI
    vainqueur, pour les matchs du masque d'évaluation (label = 1)."""
    ov, sf, cnt = {}, {}, {}                 # notes globales, par surface, compteur
    preds = []
    for m, ev in zip(matches, mask):
        w, l, s = m['winner'], m['loser'], m['surface']
        rw_o = ov.get(w, INIT); rl_o = ov.get(l, INIT)
        rw_s = sf.get((w, s), INIT); rl_s = sf.get((l, s), INIT)
        diff = (1 - SURFACE_W) * (rw_o - rl_o) + SURFACE_W * (rw_s - rl_s)
        p_w = expected(diff)                 # proba AVANT résultat (vainqueur réel)
        if ev:
            preds.append(p_w)

        # --- mise à jour ---
        kw = dyn_k(cnt.get(w, 0)) if use_dyn_k else K_FIXED
        kl = dyn_k(cnt.get(l, 0)) if use_dyn_k else K_FIXED
        mm = mov_mult(m['wg'], m['lg'], rw_o - rl_o) if use_mov else 1.0
        ov[w] = rw_o + kw * mm * (1 - p_w)
        ov[l] = rl_o + kl * mm * (0 - (1 - p_w))
        # surface : proba calculée sur le diff surface seul
        ps = expected(rw_s - rl_s)
        sf[(w, s)] = rw_s + kw * mm * (1 - ps)
        sf[(l, s)] = rl_s + kl * mm * (0 - (1 - ps))
        cnt[w] = cnt.get(w, 0) + 1
        cnt[l] = cnt.get(l, 0) + 1
    return preds


def pinnacle_preds(matches, mask):
    """Proba dévigée de Pinnacle pour le vainqueur réel, sur le masque."""
    out = []
    for m, ev in zip(matches, mask):
        if ev and m['psw'] and m['psl'] and m['psw'] > 1 and m['psl'] > 1:
            iw, il = 1.0 / m['psw'], 1.0 / m['psl']
            out.append(iw / (iw + il))       # devig 2 issues
        elif ev:
            out.append(None)                 # pas de cote Pinnacle sur ce match
    return out


# --------------------------------------------------------------------------- #
# Métriques
# --------------------------------------------------------------------------- #
def metrics(preds):
    """log-loss, Brier, accuracy (label = 1 partout : c'est le vainqueur réel)."""
    p = [x for x in preds if x is not None]
    if not p:
        return None
    ll = -sum(math.log(max(EPS, x)) for x in p) / len(p)
    br = sum((1 - x) ** 2 for x in p) / len(p)
    ac = sum(1 for x in p if x > 0.5) / len(p)
    return {'n': len(p), 'logloss': ll, 'brier': br, 'acc': ac}


def aligned_metrics(elo_preds, pin_preds):
    """Restreint l'Elo aux matchs où Pinnacle est dispo, pour une compa juste."""
    e = [ep for ep, pp in zip(elo_preds, pin_preds) if pp is not None]
    pr = [pp for pp in pin_preds if pp is not None]
    return metrics(e), metrics(pr)


# --------------------------------------------------------------------------- #
# Rapport
# --------------------------------------------------------------------------- #
def report(matches, has_pinnacle, fmt):
    mask = maturity_mask(matches)
    n_eval = sum(mask)
    configs = [
        ("Elo std",          dict(use_dyn_k=False, use_mov=False)),
        ("Elo +Kdyn",        dict(use_dyn_k=True,  use_mov=False)),
        ("Elo +Kdyn +MOV",   dict(use_dyn_k=True,  use_mov=True)),
    ]
    print("=" * 78)
    print("ELO MOV + K DYNAMIQUE  —  comparaison log-loss vs Pinnacle dévigé")
    print("=" * 78)
    print(f"Format: {fmt} | matchs chargés: {len(matches)} | "
          f"évalués (burn-in≥{MIN_MATCHES}): {n_eval} | "
          f"blend surface={SURFACE_W}")
    if not has_pinnacle:
        print("\n[!] Pas de colonnes Pinnacle (PSW/PSL) -> log-loss Elo seul, "
              "pas de verdict marché.\n    Fournis un CSV tennis-data.co.uk "
              "pour la comparaison.\n")

    pin = pinnacle_preds(matches, mask) if has_pinnacle else [None] * n_eval
    rows, best = [], None
    print(f"\n  {'variante':16s} {'n':>6s} {'logloss':>9s} {'Brier':>8s} {'acc':>7s}"
          f"   {'vs Pinnacle':>12s}")
    print("  " + "-" * 70)
    for name, cfg in configs:
        ep = run_config(matches, mask, **cfg)
        if has_pinnacle:
            me, mp = aligned_metrics(ep, pin)
        else:
            me, mp = metrics(ep), None
        gap = (me['logloss'] - mp['logloss']) if (me and mp) else None
        rows.append({'config': name, 'elo': me, 'pinnacle': mp,
                     'logloss_gap_vs_pinnacle': gap})
        gtxt = f"{gap:+.4f}" if gap is not None else "   —"
        if me:
            print(f"  {name:16s} {me['n']:6d} {me['logloss']:9.4f} "
                  f"{me['brier']:8.4f} {me['acc']*100:6.1f}%   {gtxt:>12s}")
        if gap is not None and (best is None or gap < best[1]):
            best = (name, gap)

    if has_pinnacle and rows and rows[0]['pinnacle']:
        mp = rows[0]['pinnacle']
        print("  " + "-" * 70)
        print(f"  {'Pinnacle (marché)':16s} {mp['n']:6d} {mp['logloss']:9.4f} "
              f"{mp['brier']:8.4f} {mp['acc']*100:6.1f}%   {'(référence)':>12s}")
        print("\n" + "=" * 78)
        name, gap = best
        if gap < 0:
            print(f"VERDICT : « {name} » BAT Pinnacle (écart {gap:+.4f}). "
                  "Surprenant — vérifie fuite/échantillon avant de t'emballer.")
        elif gap < 0.010:
            print(f"VERDICT : « {name} » referme presque l'écart "
                  f"(écart {gap:+.4f} < 0.010). Piste à creuser, prudemment.")
        else:
            print(f"VERDICT : meilleure variante « {name} », écart {gap:+.4f} "
                  "au-dessus de Pinnacle.\n          L'angle « meilleure force » "
                  "ne bat pas le marché -> on s'arrête là (prédictif ≠ rentable).")
        print("=" * 78)

    json.dump({'format': fmt, 'n_loaded': len(matches), 'n_eval': n_eval,
               'surface_w': SURFACE_W, 'min_matches': MIN_MATCHES,
               'configs': rows},
              open('elo_mov_report.json', 'w'), indent=2, default=str)
    print("\n-> elo_mov_report.json écrit.")


# --------------------------------------------------------------------------- #
# Test synthétique (réseau coupé) : vérifie que le pipeline tourne et que
# Pinnacle (≈ vérité) sort le plus bas log-loss. NE cherche PAS à prouver que
# le MOV gagne (ce serait tricher).
# --------------------------------------------------------------------------- #
def selftest():
    import random
    random.seed(7)
    P = [f"J{i}" for i in range(60)]
    skill = {p: random.gauss(0, 350) for p in P}     # force latente (échelle Elo)
    surfs = ['Hard', 'Clay', 'Grass']
    rows = []
    for d in range(4000):
        a, b = random.sample(P, 2)
        pa = expected(skill[a] - skill[b])
        win, lose = (a, b) if random.random() < pa else (b, a)
        pw = expected(skill[win] - skill[lose])
        # marge en jeux corrélée à l'écart de force
        gap_games = 2 + int(6 * (pw - 0.5) * 2)
        wgames = 12 + max(0, gap_games); lgames = max(0, 12 - gap_games)
        # Pinnacle ≈ vraie proba + bruit + vig 4%
        fair = min(0.97, max(0.03, pw + random.gauss(0, 0.03)))
        psw, psl = 1.0 / (fair * 1.04), 1.0 / ((1 - fair) * 1.04)
        rows.append({'Date': f'2023-01-{(d % 27)+1:02d}', 'Surface': random.choice(surfs),
                     'Winner': win, 'Loser': lose, 'Best of': 3,
                     'W1': wgames, 'L1': lgames, 'PSW': round(psw, 3), 'PSL': round(psl, 3)})
    path = '/home/claude/_synth_td.csv'
    pd.DataFrame(rows).to_csv(path, index=False)
    matches, has_ps, fmt = load_matches([path])
    report(matches, has_ps, fmt)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if '--selftest' in sys.argv:
        selftest(); return
    paths = args or sorted(glob.glob('data/*.csv')) or sorted(glob.glob('*.csv'))
    if not paths:
        raise SystemExit("Aucun CSV. Donne des chemins, ou place des .csv dans "
                         "./data/, ou lance --selftest.")
    matches, has_ps, fmt = load_matches(paths)
    if not matches:
        raise SystemExit("CSV vides ou illisibles.")
    report(matches, has_ps, fmt)


if __name__ == '__main__':
    main()
