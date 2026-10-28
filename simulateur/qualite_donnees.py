#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit descriptif et reproductible des profils service–retour exportés.

Cet audit mesure la couverture et la cohérence interne, pas la supériorité sur un
concurrent. Les balles sont des effectifs à la date d'export, après pondération
temporelle : elles ne correspondent donc pas au nombre brut de matchs joués.
"""
import json
import math
import sys


def _quantile(valeurs, q):
    if not valeurs:
        return None
    return valeurs[min(len(valeurs) - 1, round(q * (len(valeurs) - 1)))]


def auditer(doc):
    champs = list((doc or {}).get('champs') or [])
    if not champs:
        return None
    pos = {c: i for i, c in enumerate(champs)}
    joueurs = (doc or {}).get('joueurs') or {}
    effectifs, surfaces, anomalies = [], {}, {}
    controles = (('in1', 'svpt'), ('w1', 'in1'), ('ace', 'in1'), ('df', 'sec'), ('w2', 'sec'))
    for donnees in joueurs.values():
        sommes = donnees.get('sommes') or {}
        total = sommes.get('all')
        if not total:
            anomalies['profil_sans_total'] = anomalies.get('profil_sans_total', 0) + 1
            continue
        try:
            valeurs = [float(x) for x in total]
            effectifs.append(valeurs[pos['svpt']])
            for nom, valeur in zip(champs, valeurs):
                if not math.isfinite(valeur) or valeur < 0:
                    anomalies['valeur_invalide_' + nom] = anomalies.get('valeur_invalide_' + nom, 0) + 1
            for num, den in controles:
                if valeurs[pos[num]] > valeurs[pos[den]] + 1e-7:
                    cle = f'{num}_superieur_{den}'
                    anomalies[cle] = anomalies.get(cle, 0) + 1
        except (KeyError, IndexError, TypeError, ValueError):
            anomalies['profil_incomplet'] = anomalies.get('profil_incomplet', 0) + 1
        for surface in sommes:
            if surface != 'all':
                surfaces[surface] = surfaces.get(surface, 0) + 1
    effectifs.sort()
    n = len(effectifs)
    return {
        'jour': doc.get('jour'), 'genere_le': doc.get('genere_le'),
        'source': doc.get('source'), 'archive_jusqu_au': doc.get('archive_jusqu_au'),
        'profils': n, 'surfaces': surfaces,
        'balles_effectives': {
            'mediane': round(_quantile(effectifs, .5), 1) if n else None,
            'q1': round(_quantile(effectifs, .25), 1) if n else None,
            'q3': round(_quantile(effectifs, .75), 1) if n else None,
            'au_moins_200': sum(x >= 200 for x in effectifs),
            'au_moins_500': sum(x >= 500 for x in effectifs),
            'pct_au_moins_500': round(100 * sum(x >= 500 for x in effectifs) / n, 1) if n else None,
        },
        'anomalies': anomalies,
        'portee': "Couverture et cohérence interne ; ne mesure ni l'exactitude externe ni la supériorité sur une autre source.",
    }


# ------------------------------------------------------------------ couverture des joueurs PRONOSTIQUÉS (28/10/2026)
# Les 4 500 profils du fichier comptent des milliers de joueurs ITF jamais pronostiqués : leur part sous 500 balles
# ne dit rien de nos pronostics. Ici : chaque joueur de chaque match jugé, retrouvé comme le fait la production
# (clé du nom, puis même joueur écrit autrement : elo.unifier), et le bilan par tranche de documentation du joueur
# le MOINS documenté du match. Descriptif : rien n'est réglé sur ces chiffres.
TRANCHES = ((0, 500, 'moins de 500'), (500, 1500, '500 à 1 500'), (1500, 3000, '1 500 à 3 000'),
            (3000, float('inf'), '3 000 et plus'))


def couverture_pronostiques(doc, matchs, juge):
    """matchs : [{circuit, home, away, …}] jugés ; juge(m) -> (p_home, y) ou None (y = 1 si home gagne)."""
    import elo as E
    pos = {c: i for i, c in enumerate((doc or {}).get('champs') or [])}
    if 'svpt' not in pos or not matchs:
        return None
    balles, connus = {}, {}
    for d in ((doc or {}).get('joueurs') or {}).values():
        nom = d.get('nom') or ''
        k = E.cle(nom)
        try:
            b = float((d.get('sommes') or {}).get('all')[pos['svpt']])
        except (TypeError, IndexError, ValueError):
            continue
        if k and b > balles.get(k, -1):
            balles[k], connus[k] = b, nom
    alias = E.unifier(connus, [n for m in matchs for n in (m['home'], m['away'])])

    def b_de(nom):
        k = E.cle(nom)
        return balles.get(alias.get(k, k), 0.0)
    par_c, tr = {}, {lib: [] for _, _, lib in TRANCHES}
    for m in matchs:
        bh, ba = b_de(m['home']), b_de(m['away'])
        par_c.setdefault(m['circuit'], []).extend((bh, ba))
        j = juge(m)
        if j is None:
            continue
        lo = min(bh, ba)
        for a, z, lib in TRANCHES:
            if a <= lo < z:
                tr[lib].append(j)
    circuits = {}
    for c, L in sorted(par_c.items()):
        L.sort()
        n = len(L)
        circuits[c] = {'joueurs_matchs': n, 'mediane': round(_quantile(L, .5)),
                       'pct_moins_500': round(100 * sum(x < 500 for x in L) / n, 1),
                       'pct_moins_1500': round(100 * sum(x < 1500 for x in L) / n, 1)}
    tranches = []
    for _, _, lib in TRANCHES:
        X = tr[lib]
        n = len(X)
        tranches.append({'tranche': lib, 'n': n,
                         'vainqueurs_pct': round(100 * sum((p > .5) == (y == 1) for p, y in X) / n, 1) if n else None,
                         'confiance_pct': round(100 * sum(max(p, 1 - p) for p, _ in X) / n, 1) if n else None,
                         'brier': round(sum((p - y) ** 2 for p, y in X) / n, 4) if n else None,
                         'conclusion_possible': n >= 30})
    return {'circuits': circuits, 'tranches': tranches,
            'lecture': ("Balles effectives du joueur le moins documenté du match. « Confiance » = probabilité moyenne "
                        "donnée au favori : si les vainqueurs trouvés restent nettement en dessous, la tranche est "
                        "trop sûre d'elle. Moins de 30 matchs : aucune conclusion.")}


def main(argv):
    chemin = argv[1] if len(argv) > 1 else 'simulateur/profils_service.json'
    with open(chemin, encoding='utf-8') as f:
        print(json.dumps(auditer(json.load(f)), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
