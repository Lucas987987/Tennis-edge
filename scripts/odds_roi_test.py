#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
odds_roi_test.py — Le ROI par tranche de COTE, réglé au résultat.

CE QUI A DÉJÀ ÉTÉ ÉTABLI
odds_cap_test.py a montré que la refermeture NETTE de l'écart monte avec la
cote : corrélation de rang +0,204 contre un seuil de bruit de ±0,095. Tout
plafond dégrade le CLV net, et le « meilleur plafond » ne bat pas ce que
produit la sélection du meilleur découpage sur du bruit.

CE QUE CE SCRIPT AJOUTE
Le CLV n'est pas de l'argent. On règle donc au RÉSULTAT réel, par tranche de
cote, pour savoir si l'edge mesuré en CLV se retrouve en ROI — et à quel prix
en variance.

POURQUOI C'EST LE TEST DIFFICILE
À cote 5,00, l'écart-type du gain par pari vaut 2,00 unités contre 0,77 à cote
1,60. Sur quelques dizaines de paris, l'intervalle de confiance d'une tranche
haute est mécaniquement énorme. Un ROI de +40 % y est parfaitement compatible
avec un edge nul. On rapporte donc systématiquement :
  • l'IC95, et le nombre de paris qu'il faudrait pour trancher ;
  • le ROI ATTENDU depuis le CLV net, comme point de comparaison ;
  • un test de permutation sur l'étiquette de tranche.

LE PIÈGE ÉVITÉ
Comparer les ROI de 5 tranches et retenir la meilleure, c'est se garantir un
faux positif. La permutation mesure exactement ça : quel écart maximum entre
tranches obtient-on en attribuant les cotes AU HASARD ?

Env : CURVES, SHARP_BOOK, N_PERMUT, OUT.
Usage : python scripts/odds_roi_test.py
"""
import os
import sys
import json
import math
import random
import datetime
import statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alert_control_test as act      # noqa: E402
from results_join import ResultIndex  # noqa: E402

N_PERMUT = int(os.environ.get('N_PERMUT', '2000'))
OUT = os.environ.get('OUT', 'odds_roi_report.json')
TRANCHES = [(1.0, 1.6, '< 1,60'), (1.6, 2.2, '1,60 - 2,20'),
            (2.2, 3.2, '2,20 - 3,20'), (3.2, 5.0, '3,20 - 5,00'),
            (5.0, 99, '> 5,00')]


def ic(v):
    n = len(v)
    if n < 2:
        return None, None, None
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se


def n_requis(cote, edge_pct):
    """Paris nécessaires pour que l'IC95 exclue zéro, à edge donné.

    Rend visible le vrai coût des grosses cotes : ce n'est pas l'edge qui
    manque, c'est le nombre d'observations pour le prouver.
    """
    if edge_pct <= 0:
        return None
    p = 1.0 / cote
    var = (cote - 1) ** 2 * p + (1 - p) - (p * cote - 1) ** 2
    if var <= 0:
        return None
    return int(math.ceil((1.96 ** 2) * var / ((edge_pct / 100.0) ** 2)))


def main():
    idx = ResultIndex()
    if not idx.n:
        print("❌ resultats_derived.json absent — lancer results_bridge.py.")
        return

    matchs = act.charger()
    obs, sans_res = [], 0
    for uid, d in matchs.items():
        pin = d.get(act.SHARP)
        ct = d.get('_ct')
        if not pin or not ct:
            continue
        decl = act.declenchement(pin, ct)
        if not decl:
            continue
        t, shift, p_now = decl
        side = 'h' if shift > 0 else 'a'
        ps = p_now if side == 'h' else 1 - p_now
        if ps <= 0:
            continue
        juste = 1.0 / ps
        best = None
        for bk, s in d.items():
            if bk.startswith('_') or bk == act.SHARP:
                continue
            seq = s[side]
            cur = act.valeur_a(seq, t)
            close = seq[-1][1]
            if not cur or close <= 1:
                continue
            g = (cur / juste - 1) * 100
            if best is None or g > best[0]:
                # Clôture dévigée du MÊME book : le CLV net retire la marge.
                ch, ca = s['h'][-1][1], s['a'][-1][1]
                pf = act.shin_ph(ch, ca)
                pcs = (pf if side == 'h' else 1 - pf) if pf else None
                best = (g, cur, close, pcs)
        if not best:
            continue
        ecart, cote, close, p_close = best

        # charger() renvoie une clé CANONIQUE (match_key), pas les noms :
        #   'agustin-thiago-tirante_vs_arthur-fils@2026-08-21'
        # Les jetons y sont normalisés et triés, donc directement utilisables
        # par ResultIndex, qui applique la même normalisation. On sépare sur
        # '_vs_' plutôt que de deviner où s'arrête un nom.
        # NOMS RÉELS de la courbe, jamais la clé canonique : celle-ci trie les
        # joueurs alphabétiquement, donc son premier nom n'est pas le 'home'
        # des courbes. Utiliser la clé donnait une orientation aléatoire, d'où
        # des ROI aberrants (+446 % et 83 % de réussite au-delà de cote 5).
        home, away = d.get('_home'), d.get('_away')
        gagnant = idx.winner(home, away, ct) if (home and away) else None
        if gagnant is None:
            sans_res += 1
            continue
        gagne = (gagnant == 'home') if side == 'h' else (gagnant == 'away')
        obs.append({
            'cote': cote, 'ecart': ecart,
            'clv_brut': (cote / close - 1) * 100,
            'clv_net': (cote * p_close - 1) * 100 if p_close else None,
            'pnl': (cote - 1) if gagne else -1.0, 'gagne': gagne,
        })

    print(f"\n{len(obs)} pari(s) réglé(s) · {sans_res} sans résultat connu")
    if len(obs) < 40:
        print("⏳ trop peu pour conclure.")
        return

    print()
    print("=" * 92)
    print("ROI PAR TRANCHE DE COTE — mise plate, 1 pari par match")
    print("=" * 92)
    print(f"  {'tranche':<14}{'n':>5}{'ROI':>9}{'IC95 ROI':>20}"
          f"{'CLV net':>10}{'ROI attendu':>13}{'réussite':>10}")
    print("-" * 92)

    rapport = {}
    for lo, hi, lab in TRANCHES:
        g = [o for o in obs if lo <= o['cote'] < hi]
        if len(g) < 10:
            print(f"  {lab:<14}{len(g):>5}   trop peu")
            continue
        pnl = [o['pnl'] for o in g]
        roi, l, h = ic(pnl)
        nets = [o['clv_net'] for o in g if o['clv_net'] is not None]
        net = st.median(nets) if nets else None
        hit = 100 * sum(1 for o in g if o['gagne']) / len(g)
        rapport[lab] = {'n': len(g), 'roi_pct': round(roi * 100, 2),
                        'ic': [round(l * 100, 2), round(h * 100, 2)],
                        'clv_net_median': round(net, 2) if net else None,
                        'hit_pct': round(hit, 1),
                        'significatif': bool(l > 0)}
        marque = '  ✅' if l > 0 else ''
        print(f"  {lab:<14}{len(g):>5}{roi*100:>+8.1f}%"
              f"  [{l*100:>+7.1f} ; {h*100:>+7.1f}]"
              f"{net if net else 0:>+9.1f}%{net if net else 0:>+12.1f}%"
              f"{hit:>9.1f}%{marque}")

    print()
    print("  Le « ROI attendu » est le CLV net : si la clôture est efficiente,")
    print("  les deux doivent converger à long terme. Un écart important sur")
    print("  quelques dizaines de paris est de la variance, pas un edge.")

    # ── Combien de paris faudrait-il ? ───────────────────────────────────
    print()
    print("=" * 92)
    print("COMBIEN DE PARIS POUR TRANCHER ? (IC95 excluant zéro)")
    print("=" * 92)
    print(f"  {'tranche':<14}{'cote type':>11}{'edge visé':>12}{'n requis':>11}"
          f"{'n actuel':>11}{'il manque':>12}")
    print("-" * 92)
    for lo, hi, lab in TRANCHES:
        g = [o for o in obs if lo <= o['cote'] < hi]
        if len(g) < 10:
            continue
        cote = st.median(o['cote'] for o in g)
        nets = [o['clv_net'] for o in g if o['clv_net'] is not None]
        edge = st.median(nets) if nets else 0
        req = n_requis(cote, edge)
        if req is None:
            print(f"  {lab:<14}{cote:>11.2f}{edge:>+11.1f}%      edge nul ou négatif")
            continue
        rapport.setdefault(lab, {})['n_requis'] = req
        print(f"  {lab:<14}{cote:>11.2f}{edge:>+11.1f}%{req:>11}{len(g):>11}"
              f"{max(0, req-len(g)):>12}")

    # ── Permutation sur l'étiquette de tranche ───────────────────────────
    print()
    print("=" * 92)
    print("L'ÉCART ENTRE TRANCHES EXCÈDE-T-IL LE HASARD ?")
    print("=" * 92)
    rois = {}
    for lo, hi, lab in TRANCHES:
        g = [o['pnl'] for o in obs if lo <= o['cote'] < hi]
        if len(g) >= 10:
            rois[lab] = st.mean(g)
    if len(rois) >= 2:
        etendue = max(rois.values()) - min(rois.values())
        tailles = [len([o for o in obs if lo <= o['cote'] < hi])
                   for lo, hi, lab in TRANCHES if lab in rois]
        tous = [o['pnl'] for o in obs]
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
        print(f"  étendue observée entre tranches : {etendue*100:+.1f} pts de ROI")
        print(f"  seuil de bruit ({N_PERMUT} permutations) : {seuil*100:.1f} pts")
        if etendue <= seuil:
            print("  → l'écart entre tranches N'EXCÈDE PAS le hasard. Aucune")
            print("    tranche n'est démontrée meilleure qu'une autre.")
        else:
            print("  → l'écart dépasse le hasard. À geler et valider hors")
            print("    échantillon avant toute exploitation.")
        rapport['_permutation'] = {'etendue_pts': round(etendue * 100, 2),
                                   'seuil_pts': round(seuil * 100, 2),
                                   'depasse': bool(etendue > seuil)}

    print()
    print("  ⚠️ ROI THÉORIQUE : prix affichés, ni limite ni liquidité connues.")

    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc)
                     .replace(tzinfo=None).isoformat(timespec='seconds'),
        'n_paris': len(obs), 'sans_resultat': sans_res, 'tranches': rapport,
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nRapport écrit dans {OUT}")


if __name__ == '__main__':
    main()
