#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
odds_cap_test.py — Faut-il plafonner la cote signalée ?

L'OBSERVATION DE DÉPART
Le CLV monte avec la cote (+2,9 % sous 1,60, +17,2 % au-delà de 5,00). Mais
l'écart initial monte AUSSI, et la refermeture NETTE (CLV − écart) s'effondre
sur les très grosses cotes :
    < 1,60      +2,1 pts
    1,60-2,20   +3,9
    2,20-3,20   +5,2
    3,20-5,00   +7,1
    > 5,00      +0,8   <- l'écart ne se referme quasiment pas
Autrement dit, le CLV apparent des longshots vient de l'écart de départ, pas
d'une meilleure convergence.

POURQUOI ÇA COMPTE
L'écart-type du gain par pari passe de 0,77 u à cote 1,60 à 2,00 u à cote 5,00.
À edge égal, il faut ~3x plus de paris pour le même intervalle de confiance.
C'est ce qui produit des IC de 112 points sur 48 paris à cote moyenne 3,26.

CE QUE CE SCRIPT TESTE, ET DANS CET ORDRE
  1. La refermeture nette dépend-elle vraiment de la cote, ou est-ce du bruit ?
     -> corrélation continue + permutation, PAS un seuil choisi après coup.
  2. Un plafond améliore-t-il le CLV net moyen ? Et de combien ?
  3. Combien d'alertes perd-on, et quel resserrement d'IC gagne-t-on ?

LE PIÈGE QU'ON ÉVITE
Balayer 20 plafonds et garder le meilleur, c'est du sur-ajustement garanti.
On teste donc d'abord la relation CONTINUE : si elle n'existe pas, aucun
plafond n'est justifié, quel que soit le chiffre qu'affiche le meilleur
découpage. Quatre faux positifs de ce projet venaient exactement de là.

Env : CURVES, SHARP_BOOK, PALIERS, MIN_LEAD_MIN, MAX_MAG_PTS, N_PERMUT, OUT.
Usage : python scripts/odds_cap_test.py
"""
import os
import sys
import json
import math
import random
import datetime
import statistics as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alert_control_test as act  # noqa: E402

N_PERMUT = int(os.environ.get('N_PERMUT', '2000'))
OUT = os.environ.get('OUT', 'odds_cap_report.json')
PLAFONDS = [float(x) for x in os.environ.get(
    'PLAFONDS', '2.5,3.0,3.5,4.0,4.5,5.0,6.0').split(',')]


def ic(v):
    n = len(v)
    if n < 2:
        return None, None, None
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se


def spearman(xs, ys):
    """Corrélation de rang. Insensible à la forme de la relation, donc
    adaptée quand on ignore si l'effet est linéaire."""
    n = len(xs)
    if n < 10:
        return None

    def rangs(v):
        ordre = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[ordre[j + 1]] == v[ordre[i]]:
                j += 1
            moy = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                r[ordre[k]] = moy
            i = j + 1
        return r
    rx, ry = rangs(xs), rangs(ys)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx)
    dy = sum((b - my) ** 2 for b in ry)
    return num / math.sqrt(dx * dy) if dx > 0 and dy > 0 else None


def collecter():
    """(cote, CLV brut, écart, CLV net) pour chaque match à mouvement."""
    matchs = act.charger()
    obs = []
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
                best = (g, (cur / close - 1) * 100, cur, bk)
        if best:
            ecart, clv, cote, bk = best
            obs.append({'cote': cote, 'clv': clv, 'ecart': ecart,
                        'net': clv - ecart, 'book': bk, 'uid': uid})
    return obs


def main():
    obs = collecter()
    print(f"\n{len(obs)} match(s) avec mouvement Pinnacle exploitable")
    if len(obs) < 60:
        print("⏳ trop peu pour conclure.")
        return

    cotes = [o['cote'] for o in obs]
    nets = [o['net'] for o in obs]
    clvs = [o['clv'] for o in obs]

    # ── 1. RELATION CONTINUE ─────────────────────────────────────────────
    # Avant tout seuil : la refermeture nette varie-t-elle avec la cote ?
    print()
    print("=" * 76)
    print("1. LA REFERMETURE NETTE DÉPEND-ELLE DE LA COTE ?")
    print("   (net = CLV − écart initial : ce qui se referme VRAIMENT)")
    print("=" * 76)
    rho_net = spearman(cotes, nets)
    rho_clv = spearman(cotes, clvs)
    print(f"  corrélation de rang cote / CLV brut : {rho_clv:+.3f}")
    print(f"  corrélation de rang cote / net      : {rho_net:+.3f}")

    rng = random.Random(20260824)
    melange = nets[:]
    nul = []
    for _ in range(N_PERMUT):
        rng.shuffle(melange)
        r = spearman(cotes, melange)
        if r is not None:
            nul.append(abs(r))
    nul.sort()
    seuil = nul[int(0.95 * (len(nul) - 1))]
    print(f"  seuil de bruit (95e centile, {N_PERMUT} permutations) : ±{seuil:.3f}")
    significatif = abs(rho_net) > seuil
    if not significatif:
        print("  → la relation cote/net N'EXCÈDE PAS le bruit.")
        print("    Aucun plafond n'est justifié : le découpage par tranche")
        print("    montrait une tendance, la corrélation continue la dément.")
    else:
        print(f"  → relation {'positive' if rho_net > 0 else 'NÉGATIVE'} significative.")
        if rho_net < 0:
            print("    Les grosses cotes se referment MOINS : un plafond a du sens.")

    # ── 2. EFFET D'UN PLAFOND ────────────────────────────────────────────
    print()
    print("=" * 76)
    print("2. EFFET D'UN PLAFOND SUR LE CLV NET")
    print("=" * 76)
    print(f"  {'plafond':>9}{'gardés':>8}{'perdus':>8}{'net moyen':>12}"
          f"{'IC95':>18}{'largeur IC':>12}")
    print("-" * 76)
    base = [o['net'] for o in obs]
    m0, l0, h0 = ic(base)
    print(f"  {'aucun':>9}{len(base):>8}{0:>8}{m0:>+11.2f}"
          f"  [{l0:>+6.2f} ; {h0:>+6.2f}]{h0-l0:>11.2f}")
    tableau = {}
    for p in PLAFONDS:
        g = [o['net'] for o in obs if o['cote'] <= p]
        if len(g) < 30:
            continue
        m, lo, hi = ic(g)
        tableau[str(p)] = {'n': len(g), 'perdus': len(obs) - len(g),
                           'net_moyen': round(m, 3),
                           'ic': [round(lo, 3), round(hi, 3)],
                           'largeur_ic': round(hi - lo, 3)}
        print(f"  {p:>9.1f}{len(g):>8}{len(obs)-len(g):>8}{m:>+11.2f}"
              f"  [{lo:>+6.2f} ; {hi:>+6.2f}]{hi-lo:>11.2f}")

    # ── 3. LE PLAFOND EST-IL UN VRAI SEUIL ? ─────────────────────────────
    # Si la relation est continue et monotone, un « plafond » n'est qu'un
    # point arbitraire sur une pente. On compare l'amélioration réelle à
    # celle qu'obtiendrait un plafond posé au hasard.
    print()
    print("=" * 76)
    print("3. LE MEILLEUR PLAFOND BAT-IL UN PLAFOND TIRÉ AU HASARD ?")
    print("=" * 76)
    if tableau:
        best_p = max(tableau, key=lambda k: tableau[k]['net_moyen'])
        gain = tableau[best_p]['net_moyen'] - m0
        print(f"  meilleur plafond observé : {best_p} "
              f"(net {tableau[best_p]['net_moyen']:+.2f} vs {m0:+.2f} sans plafond)")
        print(f"  gain apparent : {gain:+.2f} pts")

        # Distribution nulle : on rebat les 'net' au hasard entre les matchs,
        # en gardant la structure des cotes. Un plafond sur des données sans
        # relation produit tout de même un gain, par simple sélection du max.
        rng2 = random.Random(4242)
        mel = [o['net'] for o in obs]
        gains_nuls = []
        for _ in range(max(200, N_PERMUT // 4)):
            rng2.shuffle(mel)
            faux = [{'cote': o['cote'], 'net': v} for o, v in zip(obs, mel)]
            meilleurs = []
            for p in PLAFONDS:
                g = [x['net'] for x in faux if x['cote'] <= p]
                if len(g) >= 30:
                    meilleurs.append(st.mean(g))
            if meilleurs:
                gains_nuls.append(max(meilleurs) - st.mean(mel))
        gains_nuls.sort()
        s2 = gains_nuls[int(0.95 * (len(gains_nuls) - 1))]
        print(f"  gain d'un plafond sur données SANS relation : {s2:+.2f} pts (95e centile)")
        if gain <= s2:
            print("  → le gain n'excède PAS ce que produit la simple sélection du")
            print("    meilleur découpage sur du bruit. Ne rien changer.")
        else:
            print("  → le gain dépasse la sélection sur bruit. Piste à GELER et")
            print("    valider hors échantillon avant toute mise en production.")
    else:
        best_p, gain, s2 = None, None, None

    print()
    print("  Rappel : même un plafond justifié ne se déploie qu'après validation")
    print("  hors échantillon. Le tableau ci-dessus est de l'IN-échantillon.")

    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc)
                     .replace(tzinfo=None).isoformat(timespec='seconds'),
        'n': len(obs),
        'rho_cote_clv': round(rho_clv, 4) if rho_clv else None,
        'rho_cote_net': round(rho_net, 4) if rho_net else None,
        'seuil_bruit_rho': round(seuil, 4),
        'relation_significative': bool(significatif),
        'net_sans_plafond': round(m0, 3),
        'plafonds': tableau,
        'meilleur_plafond': best_p,
        'gain_apparent': round(gain, 3) if gain is not None else None,
        'gain_seuil_bruit': round(s2, 3) if s2 is not None else None,
        'conclut': bool(significatif and gain is not None and s2 is not None
                        and gain > s2),
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f"\nRapport écrit dans {OUT}")


if __name__ == '__main__':
    main()
