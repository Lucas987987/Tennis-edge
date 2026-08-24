#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
limit_lead_test.py — Une hausse de LIMITE précède-t-elle un mouvement de PRIX ?

L'HYPOTHÈSE
Pinnacle expose le montant maximum qu'il accepte sur un prix. Cette limite
monte par paliers à mesure que le marché mûrit (25 → 50 → 125 → 162...).
Elle mesure la CONFIANCE du book dans son propre prix, et non le prix lui-même.
Si le book gagne confiance AVANT d'ajuster sa cote, une hausse de limite
devrait précéder un mouvement — et donnerait enfin un signal en avance.

POURQUOI C'EST LA DERNIÈRE PISTE SÉRIEUSE
Tout le reste a été testé et écarté :
    Polymarket, Kalshi   écart médian 0,56 pt avec Pinnacle, lead/lag non concluant
    Elo                  57,9 % contre 65,9 % pour Pinnacle
    Fatigue, forme       aucun résidu significatif face au marché
    Momentum Pinnacle    50,0 % de continuation — pile ou face
La limite est le seul signal disponible qui ne soit PAS un prix, donc le seul
qui ne soit pas déjà une redite du marché.

CE QU'ON MESURE, DANS L'ORDRE
  1. Une hausse de limite est-elle suivie d'un mouvement de prix plus ample
     que d'ordinaire, dans les minutes qui suivent ?
  2. Le SENS du mouvement est-il prévisible, ou seulement son ampleur ?
     Une hausse de limite peut annoncer « ça va bouger » sans dire dans quel
     sens — ce qui serait déjà utile pour prioriser la surveillance, mais
     inutilisable pour parier.
  3. L'effet survit-il à une permutation ?

GARDE-FOU PRINCIPAL : LA CAUSALITÉ INVERSE
Une limite et un prix bougent souvent ENSEMBLE quand une information arrive.
Mesurer « limite et prix ont bougé dans la même fenêtre » ne prouverait rien.
On exige donc une SÉPARATION TEMPORELLE STRICTE : la hausse de limite est
observée jusqu'à t, le mouvement de prix mesuré APRÈS t seulement. Tout point
antérieur ou simultané est écarté.

Env : SHARP_BOOK, FENETRE_MIN, HAUSSE_MIN, N_PERMUT, OUT.
Usage : python scripts/limit_lead_test.py
"""
import os
import sys
import json
import math
import random
import datetime
import statistics as st
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402

SHARP = os.environ.get('SHARP_BOOK', 'pinnacle')
FENETRE = float(os.environ.get('FENETRE_MIN', '30'))     # horizon de mesure
HAUSSE_MIN = float(os.environ.get('HAUSSE_MIN', '1.5'))  # facteur de hausse
MIN_LEAD = float(os.environ.get('MIN_LEAD_MIN', '45'))
N_PERMUT = int(os.environ.get('N_PERMUT', '2000'))
OUT = os.environ.get('OUT', 'limit_lead_report.json')


def _dt(x):
    try:
        return datetime.datetime.fromisoformat(
            str(x).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def point(c):
    """(t, prix, limite|None). Les points valent [ts, prix] OU
    [ts, prix, limite] : déballer en deux valeurs planterait sur les 74 % de
    courbes d'août qui portent la limite."""
    if not c or len(c) < 2:
        return None
    t = _dt(c[0])
    if t is None or not c[1]:
        return None
    try:
        p = float(c[1])
    except (TypeError, ValueError):
        return None
    if p <= 1:
        return None
    lim = None
    if len(c) > 2 and c[2] is not None:
        try:
            lim = float(c[2])
        except (TypeError, ValueError):
            lim = None
    return t, p, lim


def shin_ph(oh, oa):
    try:
        ih, ia = 1.0 / float(oh), 1.0 / float(oa)
    except Exception:
        return None
    s = ih + ia
    if s <= 0:
        return None
    if s <= 1:
        return ih / s
    z, ph, pa = 0.02, None, None
    for _ in range(50):
        ph = (math.sqrt(z * z + 4 * (1 - z) * ih * ih / s) - z) / (2 * (1 - z))
        pa = (math.sqrt(z * z + 4 * (1 - z) * ia * ia / s) - z) / (2 * (1 - z))
        t = ph + pa
        if abs(t - 1) < 1e-9:
            break
        z = min(max(z + (t - 1), 0.0), 0.3)
    return ph / (ph + pa) if (ph and pa) else None


def ic(v):
    n = len(v)
    if n < 2:
        return None, None, None
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se


def main():
    # ── Charger les courbes Pinnacle avec limite ─────────────────────────
    matchs = {}
    for ligne in ov.iter_hist_lines('book'):
        try:
            r = json.loads(ligne)
        except Exception:
            continue
        if r.get('book') != SHARP:
            continue
        ct = _dt(r.get('commence_time'))
        if not ct:
            continue
        h = sorted(x for x in (point(c) for c in (r.get('home_curve') or []))
                   if x and x[0] < ct)
        a = sorted(x for x in (point(c) for c in (r.get('away_curve') or []))
                   if x and x[0] < ct)
        if len(h) < 6 or len(a) < 6:
            continue
        if not any(x[2] is not None for x in h):
            continue                       # pas de limite : inutilisable ici
        k = (str(r.get('home') or r.get('home_team')),
             str(r.get('away') or r.get('away_team')), str(ct)[:10])
        if k not in matchs:
            matchs[k] = {'h': h, 'a': a, 'ct': ct}

    print(f"\n{len(matchs)} match(s) Pinnacle avec limite exploitable")
    if len(matchs) < 40:
        print("⏳ trop peu. La limite n'est présente que sur une partie des")
        print("   courbes ; laisser l'historique grossir.")
        return

    # ── Construire les observations ──────────────────────────────────────
    # À chaque point où la limite est connue, on compare la limite à celle du
    # point précédent, puis on mesure le mouvement de prix APRÈS ce point.
    hausses, temoins = [], []
    for k, d in matchs.items():
        h, a, ct = d['h'], d['a'], d['ct']
        lim_par_t = {x[0]: x[2] for x in h if x[2] is not None}
        instants = sorted(lim_par_t)
        if len(instants) < 3:
            continue
        ad = {x[0]: x[1] for x in a}
        last_a = None

        def prix_a(t):
            v = None
            for ts, p in ((x[0], x[1]) for x in a):
                if ts > t:
                    break
                v = p
            return v

        def prix_h(t):
            v = None
            for ts, p in ((x[0], x[1]) for x in h):
                if ts > t:
                    break
                v = p
            return v

        for i in range(1, len(instants)):
            t = instants[i]
            if (ct - t).total_seconds() / 60 < MIN_LEAD:
                break
            lim_av, lim_ap = lim_par_t[instants[i - 1]], lim_par_t[t]
            if not lim_av or lim_av <= 0:
                continue
            oh, oa = prix_h(t), prix_a(t)
            if not oh or not oa:
                continue
            p_t = shin_ph(oh, oa)
            if p_t is None:
                continue
            # SÉPARATION TEMPORELLE STRICTE : uniquement des points > t.
            t_fin = t + datetime.timedelta(minutes=FENETRE)
            oh2 = oa2 = None
            for x in h:
                if t < x[0] <= t_fin:
                    oh2 = x[1]
            for x in a:
                if t < x[0] <= t_fin:
                    oa2 = x[1]
            if oh2 is None or oa2 is None:
                continue
            p_ap = shin_ph(oh2, oa2)
            if p_ap is None:
                continue
            delta = (p_ap - p_t) * 100
            obs = {'ampleur': abs(delta), 'signe': 1 if delta > 0 else -1,
                   'ratio': lim_ap / lim_av, 'match': k}
            (hausses if lim_ap >= lim_av * HAUSSE_MIN else temoins).append(obs)

    print(f"{len(hausses)} hausse(s) de limite (facteur >= {HAUSSE_MIN}) · "
          f"{len(temoins)} témoin(s)")
    if len(hausses) < 25 or len(temoins) < 25:
        print("⏳ pas assez d'observations dans les deux groupes.")
        return

    # ── 1. Le prix bouge-t-il PLUS après une hausse de limite ? ──────────
    print()
    print("=" * 74)
    print(f"1. AMPLEUR DU MOUVEMENT DANS LES {FENETRE:.0f} MIN QUI SUIVENT")
    print("   (mesure strictement postérieure : aucun point simultané)")
    print("=" * 74)
    ha = [o['ampleur'] for o in hausses]
    ta = [o['ampleur'] for o in temoins]
    m1, l1, h1 = ic(ha)
    m2, l2, h2 = ic(ta)
    print(f"  {'groupe':<28}{'n':>6}{'ampleur moy':>14}{'IC95':>20}")
    print("-" * 74)
    print(f"  {'hausse de limite':<28}{len(ha):>6}{m1:>13.3f}  [{l1:>6.3f} ; {h1:>6.3f}]")
    print(f"  {'témoin (limite stable)':<28}{len(ta):>6}{m2:>13.3f}  [{l2:>6.3f} ; {h2:>6.3f}]")
    ecart = m1 - m2
    print(f"\n  écart : {ecart:+.3f} pt")

    # Permutation sur l'étiquette hausse/témoin.
    tous = ha + ta
    rng = random.Random(20260824)
    nul = []
    for _ in range(N_PERMUT):
        rng.shuffle(tous)
        nul.append(st.mean(tous[:len(ha)]) - st.mean(tous[len(ha):]))
    nul.sort()
    seuil = nul[int(0.975 * (len(nul) - 1))]
    print(f"  seuil de bruit ({N_PERMUT} rebattages) : ±{seuil:.3f}")
    ampleur_ok = abs(ecart) > seuil
    print("  → " + ("l'ampleur diffère significativement."
                    if ampleur_ok else
                    "aucune différence d'ampleur. La limite n'annonce pas"
                    " un mouvement plus fort."))

    # ── 2. Le SENS est-il prévisible ? ───────────────────────────────────
    # Une hausse de limite pourrait annoncer « ça va bouger » sans dire dans
    # quel sens : utile pour prioriser la surveillance, inutile pour parier.
    print()
    print("=" * 74)
    print("2. LE SENS DU MOUVEMENT EST-IL PRÉVISIBLE ?")
    print("=" * 74)
    # On regarde si le prix monte plus souvent côté home après une hausse.
    signes = [1 if o['signe'] > 0 else 0 for o in hausses]
    p = st.mean(signes)
    se = math.sqrt(max(p * (1 - p), 1e-9) / len(signes))
    print(f"  part de mouvements vers le HOME : {100*p:.1f} % "
          f"IC95 [{100*(p-1.96*se):.1f} ; {100*(p+1.96*se):.1f}]")
    sens_ok = not (p - 1.96 * se <= 0.5 <= p + 1.96 * se)
    print("  → " + ("le sens est prévisible." if sens_ok else
                    "50 % : le sens n'est PAS prévisible. Même si l'ampleur"
                    " l'était,\n    on ne saurait pas de quel côté parier."))

    print()
    print("=" * 74)
    if ampleur_ok and sens_ok:
        print("PISTE OUVERTE — à geler et valider hors échantillon.")
    elif ampleur_ok:
        print("SIGNAL PARTIEL — la limite annonce un mouvement, pas sa direction.")
        print("Utilisable pour PRIORISER la surveillance, pas pour parier.")
    else:
        print("PISTE FERMÉE — la limite n'annonce rien de mesurable.")
    print("=" * 74)

    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc)
                     .replace(tzinfo=None).isoformat(timespec='seconds'),
        'n_matchs': len(matchs), 'n_hausses': len(ha), 'n_temoins': len(ta),
        'fenetre_min': FENETRE, 'hausse_min': HAUSSE_MIN,
        'ampleur_hausse': round(m1, 4), 'ampleur_temoin': round(m2, 4),
        'ecart': round(ecart, 4), 'seuil_bruit': round(seuil, 4),
        'ampleur_significative': bool(ampleur_ok),
        'part_home': round(p, 4), 'sens_previsible': bool(sens_ok),
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nRapport écrit dans {OUT}")


if __name__ == '__main__':
    main()
