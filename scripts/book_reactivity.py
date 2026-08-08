#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book_reactivity.py — Compare la RÉACTIVITÉ des books mous face à Pinnacle (sharp).

QUESTION : après un mouvement de Pinnacle, combien de temps un book mou met-il à
suivre ? Un book qui suit lentement = prix périmé exploitable (beat-the-close).

MÉTHODE (rigoureuse, vu l'échantillonnage 5-15 min) :
  1. Pour chaque match/book, on reconstruit le "fair" dévigé P(home) = (1/oh)/((1/oh)+(1/oa))
     à chaque instant où home ET away sont connus (step-hold), pour éviter l'artefact
     d'une jambe périmée.
  2. On détecte les ÉVÉNEMENTS Pinnacle : variation du fair >= MOVE_MIN qui PERSISTE
     (ne revient pas sous le seuil au point suivant) — pas les blips d'un seul tick.
  3. Pour chaque book mou et chaque événement, on mesure le LAG = délai avant que le
     book bouge d'au moins FOLLOW_FRAC du mouvement Pinnacle, dans la même direction,
     dans une fenêtre <= MAX_WAIT min. Sinon "non suivi".
  4. BASELINE ALÉATOIRE : même mesure depuis des instants tirés au hasard. Si le lag
     "après événement" ne bat pas le hasard, il n'y a pas de signal — on le dit.
  5. On reporte aussi l'écart résiduel de fair à la CLÔTURE (book mou vs Pinnacle).

SORTIE : tableau par book (n, follow-rate, lag médian, écart close) + baseline + verdict.
Lecture seule de book_curves.jsonl. Aucun appel API.

Réglages via env : MOVE_MIN (def 0.010 = 1 pt de proba), FOLLOW_FRAC (0.5),
                   MAX_WAIT (120 min), SHARP (pinnacle), MIN_PTS (6).
"""
import json, os, random, statistics as st
from datetime import datetime

CURVES   = os.environ.get('BOOK_CURVES_FILE', 'book_curves.jsonl')
SHARP    = os.environ.get('SHARP_BOOK', 'pinnacle')
MOVE_MIN = float(os.environ.get('MOVE_MIN', '0.030'))    # mouvement fair "significatif" (3 pts)
FOLLOW_FRAC = float(os.environ.get('FOLLOW_FRAC', '0.5'))# fraction du move à reproduire
MAX_WAIT = float(os.environ.get('MAX_WAIT', '120'))      # minutes de recherche du suivi
MIN_PTS  = int(os.environ.get('MIN_PTS', '6'))           # points mini pour un match exploitable
random.seed(42)


def _ts(s):
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00')).timestamp()
    except Exception:
        return None


def load_curves(path=CURVES):
    """{uid: {book: {'h':[(t,o)...], 'a':[(t,o)...]}}}"""
    data = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            h = [(_ts(p[0]), p[1]) for p in r.get('home_curve', []) if _ts(p[0]) and p[1]]
            a = [(_ts(p[0]), p[1]) for p in r.get('away_curve', []) if _ts(p[0]) and p[1]]
            if len(h) >= 2 and len(a) >= 2:
                data.setdefault(r['uid'], {})[r['book']] = {'h': sorted(h), 'a': sorted(a)}
    return data


def _at(series, t):
    """Dernière valeur <= t (step-hold)."""
    v = None
    for tt, o in series:
        if tt <= t:
            v = o
        else:
            break
    return v


def fair_series(bk):
    """[(t, P_home_devigé)] à chaque instant home où away est aussi connu."""
    out = []
    for t, oh in bk['h']:
        oa = _at(bk['a'], t)
        if oh and oa:
            ih, ia = 1 / oh, 1 / oa
            out.append((t, ih / (ih + ia)))
    return out


def pinnacle_events(fs):
    """Instants (t, direction, ampleur) de mouvements significatifs ET persistants."""
    ev = []
    for i in range(1, len(fs) - 1):
        d = fs[i][1] - fs[i - 1][1]
        if abs(d) >= MOVE_MIN:
            # persistance : le point suivant ne revient pas en deçà du départ
            if (d > 0 and fs[i + 1][1] >= fs[i - 1][1] + MOVE_MIN / 2) or \
               (d < 0 and fs[i + 1][1] <= fs[i - 1][1] - MOVE_MIN / 2):
                ev.append((fs[i][0], 1 if d > 0 else -1, abs(d)))
    return ev


def measure_lag(soft_fs, t0, direction, amp):
    """Délai (min) avant que le book bouge de FOLLOW_FRAC*amp dans la bonne direction
    après t0. None si non suivi dans MAX_WAIT."""
    base = None
    for t, p in soft_fs:
        if t <= t0:
            base = p
        else:
            break
    if base is None:
        return None
    need = FOLLOW_FRAC * amp
    for t, p in soft_fs:
        if t <= t0:
            continue
        if (t - t0) / 60.0 > MAX_WAIT:
            break
        if (p - base) * direction >= need:
            return (t - t0) / 60.0
    return None


def analyze():
    data = load_curves()
    books = sorted({b for m in data.values() for b in m})
    soft = [b for b in books if b != SHARP]
    print(f"book_curves : {len(data)} matchs | books : {books}")
    print(f"réglages : move_min={MOVE_MIN} persistant | follow={FOLLOW_FRAC} | fenêtre={MAX_WAIT:.0f}min\n")

    # collecte lag par book (réel) + baseline (instants aléatoires)
    real = {b: [] for b in soft}     # lags suivis
    nofollow = {b: 0 for b in soft}  # événements non suivis
    base = {b: [] for b in soft}
    close_gap = {b: [] for b in soft}
    n_events = 0

    for uid, bk in data.items():
        if SHARP not in bk:
            continue
        pfs = fair_series(bk[SHARP])
        if len(pfs) < MIN_PTS:
            continue
        events = pinnacle_events(pfs)
        # instants aléatoires (même nombre) pour le baseline
        rand_t = [random.uniform(pfs[0][0], pfs[-1][0]) for _ in events] if events else []
        n_events += len(events)
        for sb in soft:
            if sb not in bk:
                continue
            sfs = fair_series(bk[sb])
            if len(sfs) < 2:
                continue
            for (t0, d, amp) in events:
                lag = measure_lag(sfs, t0, d, amp)
                if lag is None:
                    nofollow[sb] += 1
                else:
                    real[sb].append(lag)
            for rt in rand_t:
                lag = measure_lag(sfs, rt, 1, MOVE_MIN)   # direction/ampleur de réf neutre
                if lag is not None:
                    base[sb].append(lag)
            # écart de fair à la clôture
            if pfs and sfs:
                close_gap[sb].append(abs(sfs[-1][1] - pfs[-1][1]) * 100)

    print(f"événements Pinnacle détectés (significatifs+persistants) : {n_events}")
    n_matches_used = sum(1 for uid, bk in data.items()
                         if SHARP in bk and len(fair_series(bk[SHARP])) >= MIN_PTS)
    if n_matches_used:
        ratio = n_events / n_matches_used
        print(f"  soit ~{ratio:.1f} événements/match sur {n_matches_used} matchs exploitables")
        if ratio > 8:
            print("  ⚠️ ratio élevé = seuil trop sensible (jitter capté). Monte MOVE_MIN.")
    print()
    if n_events == 0:
        print("Pas assez de mouvements nets pour conclure. Reviens quand il y a plus de volume.")
        return

    header = f"  {'book':<12} {'suivis':>7} {'follow%':>8} {'lag médian':>11} {'lag moyen':>10} {'écart close':>12}"
    print(header); print("  " + "-" * (len(header) - 2))
    rows = []
    for sb in soft:
        nfollow = len(real[sb]); ntot = nfollow + nofollow[sb]
        if ntot == 0:
            continue
        fr = 100 * nfollow / ntot
        lmed = st.median(real[sb]) if real[sb] else float('nan')
        lmean = st.mean(real[sb]) if real[sb] else float('nan')
        gap = st.mean(close_gap[sb]) if close_gap[sb] else float('nan')
        rows.append((sb, ntot, fr, lmed, lmean, gap))
        print(f"  {sb:<12} {ntot:>7} {fr:>7.0f}% {lmed:>9.0f}min {lmean:>8.0f}min {gap:>10.2f}pt")

    # baseline aléatoire (référence anti-bruit)
    print("\n  Baseline aléatoire (lag médian depuis des instants au hasard) :")
    for sb in soft:
        if base[sb]:
            print(f"    {sb:<12} lag médian aléatoire {st.median(base[sb]):.0f}min  (n={len(base[sb])})")

    # verdict : un book est "exploitable" si lag médian >> cadence ET follow-rate notable
    print("\n  VERDICT (lag réel vs aléatoire) :")
    for sb, ntot, fr, lmed, lmean, gap in sorted(rows, key=lambda r: -(r[3] if r[3] == r[3] else -1)):
        b = st.median(base[sb]) if base[sb] else float('nan')
        if lmed != lmed:
            verdict = "jamais suivi → inerte ou pas assez de data"
        elif b == b and lmed <= b + 2:
            verdict = "lag ≈ hasard → pas de retard exploitable"
        elif fr < 30:
            verdict = "suit rarement → peu fiable comme signal"
        else:
            verdict = f"RETARD RÉEL ~{lmed:.0f}min → candidat à exploiter (poll plus vite)"
        print(f"    {sb:<12}: {verdict}")
    print("\n  Rappel : un lag n'est exploitable que s'il dépasse ta cadence de capture.")


if __name__ == '__main__':
    analyze()
