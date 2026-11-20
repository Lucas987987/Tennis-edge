#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
odds_dynamics.py — Anatomie du mouvement des cotes.

LA QUESTION
Une cote à 1,50 bouge-t-elle autant qu'une cote à 1,80 ? Et si elle bouge
plus, est-ce exploitable ?

POURQUOI CE N'EST PAS TRIVIAL — LE PIÈGE DE L'UNITÉ
Une cote et une probabilité ne bougent pas à la même échelle.
    1,50 -> 1,55  =  +3,3 % de cote, mais -2,2 points de probabilité
    5,00 -> 5,17  =  +3,3 % de cote, mais -0,7 point de probabilité
Le même mouvement RELATIF correspond à trois fois moins d'information sur un
outsider. Mesurer la variation en pourcentage de cote fait donc paraître les
outsiders plus volatils qu'ils ne le sont — c'est un artefact d'unité, pas un
phénomène de marché.
On rapporte donc SYSTÉMATIQUEMENT les deux : variation de cote (ce que voit le
parieur) et variation de probabilité (ce que pense le marché).

CE QUE LE SCRIPT MESURE, PAR TRANCHE DE COTE D'OUVERTURE
  1. AMPLITUDE — de combien la cote bouge entre ouverture et clôture.
  2. VOLATILITÉ — l'agitation totale du parcours (somme des variations
     absolues), qui distingue une dérive régulière d'un aller-retour.
  3. DIRECTION — la cote monte-t-elle ou descend-elle plus souvent ?
  4. ROI — parier systématiquement chaque tranche, réglé au résultat.
  5. ROI en pariant le SENS du mouvement, pour séparer « ça bouge » de
     « ça bouge de façon prévisible ».

GARDE-FOUS
  • Coupe pré-match stricte : le dernier point est in-play et connaît le match.
  • Une observation par match ET par côté, jamais par opérateur — sinon un
    match coté par 19 books pèse 19 fois.
  • Cotes Pinnacle uniquement pour la dynamique : c'est la référence, et
    mélanger des books à marges différentes brouillerait les variations.
  • Test de permutation sur le ROI entre tranches.

Env : SHARP_BOOK, N_PERMUT, OUT.
Usage : python scripts/odds_dynamics.py
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
import alert_control_test as act      # noqa: E402
from results_join import ResultIndex  # noqa: E402

SHARP = os.environ.get('SHARP_BOOK', 'pinnacle')
N_PERMUT = int(os.environ.get('N_PERMUT', '2000'))
OUT = os.environ.get('OUT', 'odds_dynamics_report.json')

TRANCHES = [(1.0, 1.35, '1,00 – 1,35'), (1.35, 1.60, '1,35 – 1,60'),
            (1.60, 1.90, '1,60 – 1,90'), (1.90, 2.30, '1,90 – 2,30'),
            (2.30, 3.00, '2,30 – 3,00'), (3.00, 4.50, '3,00 – 4,50'),
            (4.50, 99, '4,50 et +')]


def ic(v):
    n = len(v)
    if n < 2:
        return None, None, None
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se


def collecter():
    idx = ResultIndex()
    matchs = act.charger()
    obs = []
    for uid, d in matchs.items():
        pin = d.get(SHARP)
        ct = d.get('_ct')
        home, away = d.get('_home'), d.get('_away')
        if not pin or not ct or not home or not away:
            continue
        gagnant = idx.winner(home, away, ct)
        h, a = pin['h'], pin['a']
        if len(h) < 4 or len(a) < 4:
            continue
        for side, seq, autre in (('h', h, a), ('a', a, h)):
            o0, o1 = seq[0][1], seq[-1][1]
            if o0 <= 1 or o1 <= 1:
                continue
            # Probabilité dévigée aux deux bouts : la variation de cote seule
            # confondrait un ajustement de marge avec un changement d'avis.
            p0 = act.shin_ph(seq[0][1], autre[0][1]) if side == 'h' \
                else act.shin_ph(autre[0][1], seq[0][1])
            p1 = act.shin_ph(seq[-1][1], autre[-1][1]) if side == 'h' \
                else act.shin_ph(autre[-1][1], seq[-1][1])
            if p0 is None or p1 is None:
                continue
            # Volatilité : somme des variations absolues sur tout le parcours.
            # Distingue une dérive régulière d'un aller-retour de même amplitude.
            agit = sum(abs(seq[i][1] - seq[i - 1][1]) / seq[i - 1][1] * 100
                       for i in range(1, len(seq)))
            gagne = None
            if gagnant is not None:
                gagne = (gagnant == 'home') if side == 'h' else (gagnant == 'away')
            obs.append({
                'cote0': o0, 'cote1': o1,
                'var_cote': (o1 / o0 - 1) * 100,
                'var_proba': (p1 - p0) * 100,
                'agitation': agit, 'n_points': len(seq),
                'gagne': gagne,
            })
    return obs


def main():
    obs = collecter()
    print(f"\n{len(obs)} observation(s) (1 par match et par côté)")
    regles = [o for o in obs if o['gagne'] is not None]
    print(f"{len(regles)} avec résultat connu")
    if len(obs) < 200:
        print("⏳ trop peu.")
        return

    # ── 1. Amplitude et volatilité par tranche ───────────────────────────
    print()
    print("=" * 92)
    print("1. DE COMBIEN BOUGE UNE COTE, SELON SON NIVEAU D'OUVERTURE ?")
    print("=" * 92)
    print(f"  {'cote ouverture':<16}{'n':>6}{'|Δ cote|':>11}{'|Δ proba|':>12}"
          f"{'agitation':>12}{'% qui montent':>15}")
    print("-" * 92)
    rap = {}
    for lo, hi, lab in TRANCHES:
        g = [o for o in obs if lo <= o['cote0'] < hi]
        if len(g) < 25:
            print(f"  {lab:<16}{len(g):>6}   trop peu")
            continue
        dc = st.median(abs(o['var_cote']) for o in g)
        dp = st.median(abs(o['var_proba']) for o in g)
        ag = st.median(o['agitation'] for o in g)
        monte = 100 * sum(1 for o in g if o['var_cote'] > 0) / len(g)
        rap[lab] = {'n': len(g), 'd_cote_pct': round(dc, 2),
                    'd_proba_pts': round(dp, 2), 'agitation': round(ag, 2),
                    'pct_montent': round(monte, 1)}
        print(f"  {lab:<16}{len(g):>6}{dc:>10.2f}%{dp:>11.2f}{ag:>11.2f}%"
              f"{monte:>14.1f}%")

    print()
    print("  |Δ cote| et |Δ proba| ne disent PAS la même chose : à variation de")
    print("  cote égale, un outsider bouge beaucoup moins en probabilité.")
    print("  L'agitation cumule tout le parcours : élevée avec une amplitude")
    print("  faible = aller-retours, donc bruit plutôt qu'information.")

    # ── 2. ROI par tranche de cote d'ouverture ───────────────────────────
    if len(regles) >= 100:
        print()
        print("=" * 92)
        print("2. ROI EN PARIANT SYSTÉMATIQUEMENT CHAQUE TRANCHE")
        print("   (cote de CLÔTURE Pinnacle, mise plate — mesure l'efficience)")
        print("=" * 92)
        print(f"  {'cote ouverture':<16}{'n':>6}{'ROI':>9}{'IC95':>20}"
              f"{'réussite':>11}{'attendu':>10}")
        print("-" * 92)
        for lo, hi, lab in TRANCHES:
            g = [o for o in regles if lo <= o['cote0'] < hi]
            if len(g) < 25:
                continue
            pnl = [(o['cote1'] - 1) if o['gagne'] else -1.0 for o in g]
            roi, l, h = ic(pnl)
            hit = 100 * sum(1 for o in g if o['gagne']) / len(g)
            att = 100 * st.mean(1 / o['cote1'] for o in g)
            rap.setdefault(lab, {}).update({
                'roi_pct': round(roi * 100, 2),
                'roi_ic': [round(l * 100, 2), round(h * 100, 2)],
                'hit_pct': round(hit, 1), 'attendu_pct': round(att, 1)})
            marque = '  ⚠️' if l > 0 or h < 0 else ''
            print(f"  {lab:<16}{len(g):>6}{roi*100:>+8.1f}%"
                  f"  [{l*100:>+7.1f} ; {h*100:>+7.1f}]{hit:>10.1f}%"
                  f"{att:>9.1f}%{marque}")
        print()
        print("  « attendu » = ce que la cote implique. Si réussite ≈ attendu,")
        print("  le marché est efficient sur cette tranche et le ROI ≈ −marge.")

        # ── 3. Parier le SENS du mouvement ───────────────────────────────
        print()
        print("=" * 92)
        print("3. PARIER LE SENS DU MOUVEMENT (le côté dont la cote BAISSE)")
        print("=" * 92)
        steam = [o for o in regles if o['var_proba'] > 0]
        contre = [o for o in regles if o['var_proba'] < 0]
        for lab, lot in (('côté qui MONTE en proba', steam),
                         ('côté qui BAISSE en proba', contre)):
            if len(lot) < 25:
                print(f"  {lab:<28}{len(lot):>6}   trop peu")
                continue
            pnl = [(o['cote1'] - 1) if o['gagne'] else -1.0 for o in lot]
            roi, l, h = ic(pnl)
            hit = 100 * sum(1 for o in lot if o['gagne']) / len(lot)
            rap[lab] = {'n': len(lot), 'roi_pct': round(roi * 100, 2),
                        'roi_ic': [round(l * 100, 2), round(h * 100, 2)],
                        'hit_pct': round(hit, 1)}
            print(f"  {lab:<28}{len(lot):>6}{roi*100:>+8.1f}%"
                  f"  [{l*100:>+7.1f} ; {h*100:>+7.1f}]{hit:>10.1f}%")

        # Permutation : l'écart de ROI entre tranches excède-t-il le hasard ?
        rois, tailles = [], []
        for lo, hi, lab in TRANCHES:
            g = [o for o in regles if lo <= o['cote0'] < hi]
            if len(g) >= 25:
                rois.append(st.mean((o['cote1'] - 1) if o['gagne'] else -1.0
                                    for o in g))
                tailles.append(len(g))
        if len(rois) >= 3:
            etendue = max(rois) - min(rois)
            tous = [(o['cote1'] - 1) if o['gagne'] else -1.0 for o in regles]
            rng = random.Random(20260824)
            nul = []
            for _ in range(N_PERMUT):
                rng.shuffle(tous)
                i, moys = 0, []
                for n in tailles:
                    moys.append(st.mean(tous[i:i + n]))
                    i += n
                nul.append(max(moys) - min(moys))
            nul.sort()
            seuil = nul[int(0.95 * (len(nul) - 1))]
            print()
            print(f"  étendue de ROI entre tranches : {etendue*100:+.1f} pts")
            print(f"  seuil de bruit ({N_PERMUT} permutations) : {seuil*100:.1f} pts")
            print("  → " + ("dépasse le hasard, à geler et valider hors échantillon."
                            if etendue > seuil else
                            "n'excède PAS le hasard. Aucune tranche n'est"
                            " meilleure qu'une autre."))
            rap['_permutation'] = {'etendue_pts': round(etendue * 100, 2),
                                   'seuil_pts': round(seuil * 100, 2),
                                   'depasse': bool(etendue > seuil)}

    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc)
                     .replace(tzinfo=None).isoformat(timespec='seconds'),
        'n_obs': len(obs), 'n_regles': len(regles), 'tranches': rap,
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nRapport écrit dans {OUT}")


if __name__ == '__main__':
    main()
