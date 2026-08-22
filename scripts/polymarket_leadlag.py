#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
polymarket_leadlag.py — Polymarket est-il en avance sur Pinnacle ?

QUESTION POSÉE
Quand la probabilité d'un joueur bouge, qui bouge en premier : le marché de
prédiction (Polymarket, ordres réels d'un public non professionnel) ou le
bookmaker sharp (Pinnacle) ? Un décalage systématique et exploitable serait un
signal avancé pour la détection de steam.

MÉTHODE
  1. Ticks Polymarket -> probabilité du joueur home, par (uid, market_type).
     Le prix Polymarket EST une probabilité (0-1) : aucun dévigage à faire.
  2. Courbes Pinnacle -> probabilité du home, dévigée (Shin 2 voies).
  3. Les deux séries sont ramenées sur une grille temporelle commune, PRÉ-MATCH
     uniquement (un point in-play ferait entrer le résultat dans la mesure).
  4. Corrélation croisée des VARIATIONS (différences premières) à chaque
     décalage. Le décalage qui maximise la corrélation indique qui mène.
     décalage < 0 : Polymarket bouge AVANT Pinnacle.

TROIS GARDE-FOUS, tirés des faux positifs de ce projet
  • VARIATIONS, jamais les niveaux. Deux séries qui suivent le même match sont
    corrélées à 0,99 en niveau, quel que soit le décalage : cette corrélation-là
    ne dit rien. Seules les variations informent sur l'ordre d'arrivée.
  • Résolution limitée par Pinnacle. Les courbes Pinnacle sont échantillonnées
    toutes les 5-10 min : un décalage inférieur au pas de grille est INVISIBLE,
    et un décalage détecté à ce pas n'est pas significatif. Le script refuse
    d'interpréter en dessous de GRID_MIN.
  • Distribution nulle par permutation. On rejoue l'analyse en appariant chaque
    série Polymarket à un AUTRE match. Si le décalage trouvé sort aussi souvent
    sur ces paires factices, c'est du bruit. C'est le test qui manquait aux
    quatre faux positifs de la semaine (calibration, opening_value, cote >= 3,
    drift fort steam).

Env : PM_TICKS_GLOB (parts/pm_ticks_*.jsonl), CURVES, MARKET_TYPE (match),
      GRID_MIN (5), MAX_LAG_MIN (60), MIN_POINTS (12), N_PERMUT (200), OUT.

Sortie : polymarket_leadlag_report.json + tableau lisible.
"""
import os
import sys
import json
import glob
import gzip
import math
import random
import datetime
import statistics as st
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402

# Kalshi d'abord si des ticks existent : couverture plus large (Challengers,
# ITF) et 40x moins de volume. PM_TICKS_GLOB force une source précise.
PM_GLOB      = os.environ.get(
    'PM_TICKS_GLOB',
    'parts/kx_ticks_*.jsonl' if glob.glob('parts/kx_ticks_*.jsonl')
    else 'parts/pm_ticks_*.jsonl')
CURVES      = os.environ.get('CURVES', 'book_curves_live.jsonl')
MARKET_TYPE = os.environ.get('MARKET_TYPE', 'match')
GRID_MIN    = float(os.environ.get('GRID_MIN', '5'))
MAX_LAG_MIN = float(os.environ.get('MAX_LAG_MIN', '60'))
MIN_POINTS  = int(os.environ.get('MIN_POINTS', '12'))
N_PERMUT    = int(os.environ.get('N_PERMUT', '200'))
SHARP       = os.environ.get('SHARP_BOOK', 'pinnacle')
OUT         = os.environ.get('OUT', 'polymarket_leadlag_report.json')


def _dt(x):
    try:
        return datetime.datetime.fromisoformat(
            str(x).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def _open(path):
    if path.endswith('.gz'):
        return gzip.open(path, 'rt', encoding='utf-8')
    return open(path, encoding='utf-8')


def load_pm():
    """{uid: [(t, proba_home)]} depuis les ticks Polymarket."""
    series = collections.defaultdict(list)
    paths = ov.load_partitions(PM_GLOB)
    n_lignes = 0
    for p in paths:
        try:
            f = _open(p)
        except Exception:
            continue
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            n_lignes += 1
            # Kalshi n'écrit PAS market_type : son collecteur ne suit que les
            # séries « vainqueur du match », donc tout tick est déjà du bon
            # type. Exiger le champ rejetait 100 % des ticks Kalshi — et en
            # silence, ce qui est le pire cas.
            mt = r.get('market_type')
            if mt is not None and mt != MARKET_TYPE:
                continue
            if mt is None and MARKET_TYPE != 'match':
                continue
            uid = r.get('local_uid')
            side = r.get('local_side')
            if not uid or side not in ('home', 'away'):
                continue
            t = _dt(r.get('ts'))
            # mid = milieu de fourchette ; à défaut, dernier échange
            p = r.get('mid')
            if p is None:
                p = r.get('last_trade')
            if t is None or p is None:
                continue
            try:
                p = float(p)
            except Exception:
                continue
            if not (0.0 < p < 1.0):
                continue
            # tout est ramené à la probabilité du HOME
            series[uid].append((t, p if side == 'home' else 1.0 - p))
    for uid in series:
        series[uid].sort()
    print(f"Polymarket : {len(paths)} partition(s), {n_lignes} ticks lus, "
          f"{len(series)} match(s) avec série '{MARKET_TYPE}'")
    return series


def _shin(oh, oa):
    """Probabilité du home, marge retirée (dévigage 2 voies)."""
    try:
        ih, ia = 1.0 / float(oh), 1.0 / float(oa)
    except Exception:
        return None
    s = ih + ia
    if s <= 0:
        return None
    return ih / s


def load_pinnacle(uids):
    """{uid: [(t, proba_home)]} depuis les courbes du book sharp, PRÉ-MATCH."""
    out = {}
    for src in (CURVES, 'book_curves.jsonl'):
        # open_curves lève FileNotFoundError À L'ITÉRATION (générateur), pas à
        # l'appel : le try doit donc englober la boucle, sinon un historique
        # absent fait planter tout le script au lieu de passer à la source
        # suivante. Les ticks sont récents, l'historique est souvent inutile.
        try:
            lines = list(ov.open_curves(src, verbose=False))
        except FileNotFoundError:
            continue
        except Exception as exc:
            print(f"⚠️ {src} : {exc}")
            continue
        for line in lines:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get('book') != SHARP or r.get('uid') not in uids:
                continue
            ct = _dt(r.get('commence_time'))
            if not ct:
                continue

            def pre(seq):
                pts = [(_dt(q[0]), q[1]) for q in (seq or [])
                       if _dt(q[0]) and q[1] and float(q[1]) > 1]
                return sorted(q for q in pts if q[0] < ct)

            h, a = pre(r.get('home_curve')), pre(r.get('away_curve'))
            if len(h) < 2 or len(a) < 2:
                continue
            ah = {t: p for t, p in a}
            serie = []
            last_a = None
            for t, ph in h:
                last_a = ah.get(t, last_a)
                if last_a is None:
                    continue
                pr = _shin(ph, last_a)
                if pr is not None:
                    serie.append((t, pr))
            if len(serie) >= 2 and r['uid'] not in out:
                out[r['uid']] = (serie, ct)
    print(f"Pinnacle   : {len(out)} match(s) avec courbe exploitable")
    return out


def grille(serie, t0, t1, pas_min):
    """Rééchantillonne en escalier (dernière valeur connue) sur une grille."""
    if not serie:
        return []
    out, i, cur = [], 0, None
    t = t0
    while t <= t1:
        while i < len(serie) and serie[i][0] <= t:
            cur = serie[i][1]
            i += 1
        out.append(cur)
        t += datetime.timedelta(minutes=pas_min)
    return out


def diffs(v):
    return [(b - a) for a, b in zip(v, v[1:])
            if a is not None and b is not None]


def correl(x, y):
    n = min(len(x), len(y))
    if n < 3:
        return None
    x, y = x[:n], y[:n]
    mx, my = st.mean(x), st.mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = sum((a - mx) ** 2 for a in x)
    dy = sum((b - my) ** 2 for b in y)
    if dx <= 0 or dy <= 0:
        return None
    return num / math.sqrt(dx * dy)


def paire_alignee(pm, pin, ct):
    """Deux séries sur la même grille, bornées au pré-match et à l'intersection."""
    t0 = max(pm[0][0], pin[0][0])
    t1 = min(pm[-1][0], pin[-1][0], ct)
    if t1 <= t0:
        return None, None
    span = (t1 - t0).total_seconds() / 60.0
    if span < GRID_MIN * MIN_POINTS:
        return None, None
    return grille(pm, t0, t1, GRID_MIN), grille(pin, t0, t1, GRID_MIN)


def profil_lag(series_pm, series_pin, apparier_a=None):
    """Corrélation des variations pour chaque décalage. apparier_a permet de
    brancher la série Polymarket d'un AUTRE match (distribution nulle)."""
    kmax = int(MAX_LAG_MIN / GRID_MIN)
    acc = {k: [] for k in range(-kmax, kmax + 1)}
    n_paires = 0
    for uid, (pin, ct) in series_pin.items():
        src = apparier_a.get(uid) if apparier_a else series_pm.get(uid)
        if not src:
            continue
        gp, gq = paire_alignee(src, pin, ct)
        if gp is None:
            continue
        dp, dq = diffs(gp), diffs(gq)
        if len(dp) < MIN_POINTS or len(dq) < MIN_POINTS:
            continue
        n_paires += 1
        for k in acc:
            if k < 0:      # Polymarket AVANCÉ de |k| pas -> il mène
                a, b = dp[:len(dp) + k], dq[-k:]
            elif k > 0:
                a, b = dp[k:], dq[:len(dq) - k]
            else:
                a, b = dp, dq
            c = correl(a, b)
            if c is not None:
                acc[k].append(c)
    return {k: st.mean(v) for k, v in acc.items() if v}, n_paires


def main():
    pm = load_pm()
    if not pm:
        print("\n❌ aucune série Polymarket exploitable.")
        print("   Causes possibles : collecteur pas encore lancé, market_type "
              "absent des ticks (version antérieure du collecteur), ou "
              "local_uid non résolu.")
        return
    pin = load_pinnacle(set(pm))
    if not pin:
        print("\n❌ aucun match commun entre les ticks Polymarket et les courbes.")
        return

    profil, n = profil_lag(pm, pin)
    if not profil or n == 0:
        print(f"\n⏳ {n} paire(s) exploitable(s) — il faut au moins "
              f"{GRID_MIN * MIN_POINTS:.0f} min de recouvrement par match.")
        print("   Laisser le collecteur accumuler puis relancer.")
        return

    best = max(profil, key=lambda k: profil[k])
    lag_min = best * GRID_MIN

    # ── Distribution nulle : Polymarket apparié à un AUTRE match ──────────
    uids = list(pin)
    nul = []
    rng = random.Random(12345)
    for _ in range(max(20, N_PERMUT)):
        melange = uids[:]
        rng.shuffle(melange)
        faux = {u: pm.get(v) for u, v in zip(uids, melange) if u != v and pm.get(v)}
        if not faux:
            continue
        pr, _ = profil_lag(pm, pin, apparier_a=faux)
        if pr:
            nul.append(max(pr.values()))
    seuil = None
    if nul:
        nul.sort()
        seuil = nul[int(0.95 * (len(nul) - 1))]

    print()
    print("=" * 72)
    print(f"LEAD/LAG POLYMARKET vs {SHARP.upper()} — marché '{MARKET_TYPE}'")
    print(f"{n} match(s) · grille {GRID_MIN:.0f} min · variations, pas niveaux")
    print("=" * 72)
    print(f"{'décalage':>10} | {'corrélation':>12} | qui mène")
    print("-" * 72)
    for k in sorted(profil):
        m = k * GRID_MIN
        qui = "Polymarket devant" if m < 0 else ("Pinnacle devant" if m > 0 else "simultané")
        mark = "  <<<" if k == best else ""
        print(f"{m:>+7.0f}min | {profil[k]:>+12.3f} | {qui}{mark}")

    print()
    print(f"Maximum à {lag_min:+.0f} min (corrélation {profil[best]:+.3f})")
    if seuil is not None:
        print(f"Seuil de bruit (95e centile sur {len(nul)} appariements factices) : {seuil:+.3f}")
        if profil[best] <= seuil:
            print("→ NON CONCLUANT : le maximum ne dépasse pas ce que produisent")
            print("  des paires de matchs sans rapport. Aucun lead/lag démontré.")
        else:
            print("→ Le maximum dépasse la distribution nulle. Signal à confirmer")
            print("  sur davantage de matchs avant toute conclusion.")
    if abs(lag_min) <= GRID_MIN:
        print(f"⚠️ |décalage| <= {GRID_MIN:.0f} min = pas de la grille. Les courbes "
              f"{SHARP} sont échantillonnées toutes les 5-10 min : un décalage")
        print("  de cet ordre est INDISCERNABLE de zéro, quelle que soit la corrélation.")

    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec='seconds'),
        'market_type': MARKET_TYPE, 'sharp': SHARP,
        'grille_min': GRID_MIN, 'n_matchs': n,
        'profil': {str(k * GRID_MIN): round(v, 4) for k, v in profil.items()},
        'lag_optimal_min': lag_min,
        'correlation_max': round(profil[best], 4),
        'seuil_bruit_95': None if seuil is None else round(seuil, 4),
        'concluant': bool(seuil is not None and profil[best] > seuil
                          and abs(lag_min) > GRID_MIN),
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f"\nRapport écrit dans {OUT}")


if __name__ == '__main__':
    main()
