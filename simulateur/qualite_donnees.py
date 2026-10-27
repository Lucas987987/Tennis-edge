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


def main(argv):
    chemin = argv[1] if len(argv) > 1 else 'simulateur/profils_service.json'
    with open(chemin, encoding='utf-8') as f:
        print(json.dumps(auditer(json.load(f)), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
