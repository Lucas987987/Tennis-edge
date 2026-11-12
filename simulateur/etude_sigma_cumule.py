#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_sigma_cumule.py — la forme du jour σ du lundi passe à la règle cumulée, circuit par circuit (12/11/2026, paquet 245)

LE DÉFAUT. sigma_circuit.py choisit chaque lundi un σ par circuit (grille 0,15 · 0,18 · 0,22 · 0,26) et le juge contre
0,15 sur les six dernières semaines, dont cinq déjà vues la semaine d'avant : entrer si le gain total dépasse 0,001
deux semaines de suite (et aucun circuit sous −0,001), sortir après deux semaines moins bien. C'est la règle que le
paquet 241 a remplacée ailleurs (9,4 % de semaines dans le mauvais état pour la règle cumulée contre 12,7 %). Le
paquet 243 a montré sur l'archive que le gain de σ est petit et instable, et que 0,22 ou plus dégrade l'écart de jeux :
un seuil de 0,001 sur quelques centaines de matchs est trop permissif.

CE QUI CHANGE (pas de nouvelle règle : celle du paquet 241, écrite avant) :
  - chaque match jugé fournit sa paire (perte avec 0,15, perte avec le σ choisi) ;
  - décision CIRCUIT PAR CIRCUIT (sigma_circuit.decider) : entrer si, depuis le dernier changement, sur au moins 300
    matchs, le gain dépasse 2 erreurs types ; sortir s'il est négatif de plus de 2 erreurs types ; chaque match compté
    une fois ; un circuit en place garde son σ d'avant tant que la semaine ne trouve pas mieux que 0,15.
CE SCRIPT : aucun rejeu possible ici (les profils des matchs jugés ne sont pas gardés) ; il lit le dernier jugement
(facteurs.json) et écrit ce que la règle fera au premier lundi. Aucune décision n'est prise sur ce contrôle.
Le % de victoire ne change pas : σ ne règle que la forme du match.

Usage : python simulateur/etude_sigma_cumule.py
"""
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import sigma_circuit as SGC  # noqa: E402
import stabilite as ST  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_sigma_cumule.json')


def main():
    try:
        with open(os.path.join(ICI, 'facteurs.json'), encoding='utf-8') as f:
            rs = json.load(f).get('sigma_circuit') or {}
    except (OSError, ValueError):
        rs = {}
    avant = (rs.get('sigmas') or SGC.DECISION) if rs.get('adopte', True) else {}
    circuits = {}
    for c in SGC.CIRCUITS:
        p = (rs.get('par_circuit') or {}).get(c) or {}
        en_place = SGC.sigma_de(avant, c) != SGC.BASE
        circuits[c] = {'sigma_en_place': SGC.sigma_de(avant, c), 'en_place': en_place,
                       'dernier_jugement': {'n': p.get('n'), 'sigma_choisi': p.get('sigma'), 'gain': p.get('gain')},
                       'au_premier_lundi': ("reste en place : il ne sort que si le gain cumulé devient négatif de plus de "
                                            f"{ST.CUMUL_ET:g} erreurs types sur au moins {ST.CUMUL_MIN} matchs") if en_place else
                                           ("reste à 0,15 : le σ choisi est 0,15, aucun gain possible" if p.get('sigma') == SGC.BASE
                                            else f"entre seulement si le gain dépasse {ST.CUMUL_ET:g} erreurs types sur au moins "
                                                 f"{ST.CUMUL_MIN} matchs")}
    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 245, 'statut': 'controle',
           'regle': ("règle cumulée du paquet 241 appliquée à σ, circuit par circuit (≥ 300 matchs, 2 erreurs types, chaque "
                     "match compté une fois) ; aucune décision sur ce contrôle"),
           'regle_d_avant': "gain total ≥ 0,001 deux semaines de suite, aucun circuit sous −0,001 ; sortie après deux semaines moins bien",
           'circuits': circuits,
           'a_surveiller': "à relire quand chaque circuit aura cumulé 1 000 matchs ; l'archive (paquet 243) dit que σ ≥ 0,22 dégrade l'écart de jeux"}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    print(json.dumps(circuits, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main())
