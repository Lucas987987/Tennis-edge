#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
book_index.py — Indice comparatif des opérateurs sur le tennis.

CE QUE C'EST, ET POURQUOI
Un produit qui ne repose sur AUCUN edge. Les tests ont établi que le CLV net
est proche de zéro une fois la marge retirée, et que cinq pistes d'anticipation
sont fermées. Mais les mêmes données répondent à une autre question, bien plus
utile au lecteur : OÙ placer son pari, plutôt que QUEL pari placer.

Trois mesures, toutes vérifiables et sans promesse de rendement :
  • MARGE — ce que l'opérateur prélève, mesuré sur ses clôtures pré-match.
    C'est le coût réel du pari, et il varie du simple au double.
  • RÉACTIVITÉ — écart moyen au juste prix Pinnacle à l'instant où le marché
    bouge. Positif = l'opérateur traîne, donc offre encore un prix généreux.
    Négatif = il a déjà ajusté, voire sur-ajusté.
  • MEILLEUR PRIX — combien de fois l'opérateur affiche la meilleure cote du
    panel, sur les matchs où le marché a bougé.

CE QU'IL NE FAUT PAS EN CONCLURE
Qu'un opérateur « lent » est rentable. L'écart mesuré se referme, mais la marge
l'absorbe : c'est précisément ce qu'ont montré les tests de ROI. Un opérateur à
marge basse ET souvent meilleur prix coûte simplement MOINS CHER au parieur.
C'est une information de coût, pas de rendement.

CONFORMITÉ
Information consommateur comparative, sans incitation ni promesse de gain.
Aucun lien d'affiliation, aucun classement « recommandé ». Les opérateurs sont
présentés par marge croissante, un critère objectif et vérifiable.

GARDE-FOUS
  • Coupe pré-match stricte : un point in-play encoderait le déroulement.
  • Un opérateur n'apparaît qu'au-delà de MIN_OBS observations — sinon un
    book vu trois fois occuperait la première place par hasard.
  • Les exchanges sont exclus : sans marge à prélever, ils ne sont pas
    comparables à un bookmaker (commission, carnet, back/lay).
  • Intervalles de confiance sur la marge : deux opérateurs séparés de 0,2
    point ne sont pas distinguables.

Sorties : book_index.json (données) et book_index.md (publiable tel quel).
Env : MIN_OBS, OUT, OUT_MD.
Usage : python scripts/book_index.py
"""
import os
import sys
import json
import math
import datetime
import statistics as st
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alert_control_test as act  # noqa: E402

MIN_OBS = int(os.environ.get('MIN_OBS', '100'))
MIN_MOVE = int(os.environ.get('MIN_MOVE_OBS', '30'))
OUT = os.environ.get('OUT', 'book_index.json')
OUT_MD = os.environ.get('OUT_MD', 'book_index.md')

# Opérateurs disposant d'une licence ANJ, donc légaux en France. Signalé pour
# information : le lecteur français ne peut pas jouer chez les autres.
FR = {'winamax.fr', 'unibet.fr', 'bet365.fr', 'pmu', 'netbet.fr', 'bwin.fr',
      'zebet.fr', 'genybet.fr', 'vbet.fr', 'circusbet.fr', 'feelingbet.fr'}


def ic(v):
    n = len(v)
    if n < 2:
        return None, None, None
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se


def main():
    matchs = act.charger()
    marge = collections.defaultdict(list)
    retard = collections.defaultdict(list)
    meilleur = collections.Counter()
    n_moves = 0

    for uid, d in matchs.items():
        pin = d.get(act.SHARP)
        ct = d.get('_ct')
        if not ct:
            continue

        # ── Marge : sur la clôture pré-match de chaque opérateur ─────────
        for bk, s in d.items():
            if bk.startswith('_'):
                continue
            try:
                oh, oa = s['h'][-1][1], s['a'][-1][1]
            except (IndexError, KeyError, TypeError):
                continue
            if oh > 1 and oa > 1:
                marge[bk].append((1 / oh + 1 / oa - 1) * 100)

        # ── Réactivité : à l'instant où Pinnacle bouge ───────────────────
        if not pin:
            continue
        decl = act.declenchement(pin, ct)
        if not decl:
            continue
        t, shift, p_now = decl
        side = 'h' if shift > 0 else 'a'
        ps = p_now if side == 'h' else 1 - p_now
        if ps <= 0:
            continue
        n_moves += 1
        juste = 1.0 / ps
        cands = []
        for bk, s in d.items():
            if bk.startswith('_') or bk == act.SHARP:
                continue
            cur = act.valeur_a(s[side], t)
            if not cur:
                continue
            retard[bk].append((cur / juste - 1) * 100)
            cands.append((cur, bk))
        if cands:
            meilleur[max(cands)[1]] += 1

    lignes = []
    for bk, v in marge.items():
        if len(v) < MIN_OBS or len(retard.get(bk, [])) < MIN_MOVE:
            continue
        m, lo, hi = ic(v)
        r = st.mean(retard[bk])
        lignes.append({
            'book': bk, 'n_cotes': len(v), 'n_moves': len(retard[bk]),
            'marge_mediane': round(st.median(v), 2),
            'marge_moyenne': round(m, 2),
            'marge_ic': [round(lo, 2), round(hi, 2)],
            'retard_moyen': round(r, 2),
            'meilleur_prix': meilleur.get(bk, 0),
            'licence_fr': bk in FR,
        })
    lignes.sort(key=lambda x: x['marge_moyenne'])

    if not lignes:
        print("❌ pas assez de données.")
        return

    print()
    print("=" * 82)
    print(f"INDICE DES OPÉRATEURS — TENNIS · {len(matchs)} matchs · "
          f"{n_moves} mouvements de marché")
    print("=" * 82)
    print(f"  {'opérateur':<16}{'marge':>9}{'IC95':>16}{'réactivité':>13}"
          f"{'meilleur prix':>15}{'FR':>5}")
    print("-" * 82)
    for x in lignes:
        fr = 'oui' if x['licence_fr'] else '—'
        # On affiche la MOYENNE à côté de son IC : mettre une médiane en
        # regard d'un IC de moyenne donne des lignes incohérentes du type
        # « 4,96 % [4,61 ; 4,89] », où l'intervalle ne contient pas la valeur.
        # La médiane reste dans le JSON, elle est plus robuste aux valeurs
        # extrêmes, mais elle ne se compare pas à cet intervalle.
        print(f"  {x['book']:<16}{x['marge_moyenne']:>8.2f}%"
              f"  [{x['marge_ic'][0]:>5.2f} ; {x['marge_ic'][1]:>5.2f}]"
              f"{x['retard_moyen']:>+12.2f}%{x['meilleur_prix']:>15}{fr:>5}")

    # ── Rendu publiable ──────────────────────────────────────────────────
    md = _markdown(lignes, len(matchs), n_moves)
    open(OUT_MD, 'w', encoding='utf-8').write(md)
    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc)
                     .replace(tzinfo=None).isoformat(timespec='seconds'),
        'n_matchs': len(matchs), 'n_mouvements': n_moves,
        'min_obs': MIN_OBS, 'operateurs': lignes,
    }, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

    # Le fait le plus parlant : l'écart entre versions d'un même opérateur.
    paires = [('bet365', 'bet365.fr'), ('unibet', 'unibet.fr'),
              ('bwin', 'bwin.fr'), ('netbet', 'netbet.fr')]
    par_nom = {x['book']: x for x in lignes}
    ecarts = []
    for inter, fr in paires:
        if inter in par_nom and fr in par_nom:
            ecarts.append((inter, par_nom[inter]['marge_moyenne'],
                           fr, par_nom[fr]['marge_moyenne']))
    if ecarts:
        print()
        print("  MÊME OPÉRATEUR, VERSION FRANÇAISE vs INTERNATIONALE")
        print("  " + "-" * 60)
        for a, ma, b, mb in ecarts:
            print(f"  {a:<14}{ma:>6.2f}%   {b:<14}{mb:>6.2f}%   "
                  f"écart {mb-ma:+.2f} pt")

    print(f"\n{OUT} · rendu publiable dans {OUT_MD}")


def _markdown(lignes, n_matchs, n_moves):
    d = datetime.date.today().isoformat()
    out = [f"# Indice des opérateurs — tennis", "",
           f"*Mesuré sur {n_matchs} matchs et {n_moves} mouvements de marché. "
           f"Mise à jour du {d}.*", "",
           "| Opérateur | Marge | Réactivité | Meilleur prix | Licence FR |",
           "|---|---:|---:|---:|:---:|"]
    for x in lignes:
        fr = '✅' if x['licence_fr'] else '—'
        out.append(f"| {x['book']} | {x['marge_moyenne']:.2f} % | "
                   f"{x['retard_moyen']:+.2f} % | {x['meilleur_prix']} | {fr} |")
    out += ["",
            "**Marge** — ce que l'opérateur prélève, mesuré sur ses cotes de "
            "clôture avant match. C'est le coût réel du pari.", "",
            "**Réactivité** — écart au juste prix estimé à l'instant où le "
            "marché bouge. Un chiffre positif signifie que l'opérateur n'a pas "
            "encore ajusté.", "",
            "**Meilleur prix** — nombre de fois où l'opérateur affiche la "
            "meilleure cote du panel.", "",
            "---", "",
            "Ces chiffres décrivent le **coût** d'un pari, pas son rendement. "
            "Un opérateur lent à ajuster n'est pas pour autant rentable : "
            "l'écart observé se referme, mais la marge l'absorbe.", "",
            "Aucun lien d'affiliation. Classement par marge croissante, "
            "critère objectif et vérifiable.", "",
            "18+ · Jouer comporte des risques · joueurs-info-service.fr"]
    return "\n".join(out)


if __name__ == '__main__':
    main()
