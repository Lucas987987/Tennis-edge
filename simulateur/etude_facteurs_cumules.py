#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_facteurs_cumules.py — les facteurs du lundi passent à la règle cumulée (12/11/2026, audit, paquet 246)

LE DÉFAUT (audit, paquet 234, « regles_hebdomadaires_des_poids_et_des_facteurs »). facteurs.py rejuge chaque lundi,
sur les six dernières semaines dont cinq déjà vues, les groupes de facteurs (global et circuit par circuit), le modèle
complet (arbres) et la forme des scores. Un groupe entrait si les points étaient mieux prédits — d'aussi peu que ce
soit — et si la log loss du vainqueur ne montait pas de plus de 0,001, deux semaines de suite. Des groupes sont en
place avec des gains de quelques millionièmes par point.

RÈGLE ÉCRITE LE 12/11/2026, AVANT TOUT RÉSULTAT (même famille que la règle cumulée du paquet 241, 300 matchs et
2 erreurs types ; deux mesures parce que la règle d'avant en avait deux) :
  - groupes (global et par circuit) : mesure principale = perte moyenne par point du match (service, aces, balles de
    break) sans et avec le groupe ; garde = log loss du vainqueur sans et avec ;
  - modèle complet : mesure principale = log loss du vainqueur (sa règle exigeait un gain) ; garde = points de service ;
  - ENTRER : au moins 300 matchs depuis le dernier changement, principale positive de plus de 2 erreurs types ET garde
    pas négative de plus de 2 erreurs types ; SORTIR : principale OU garde négative de plus de 2 erreurs types ;
  - forme des scores : règle cumulée simple du paquet 241 sur la vraisemblance de la forme réelle ;
  - chaque match compté une fois (le jour où il entre dans la fenêtre) ; ce qui est en place le reste au départ ;
  - les décisions directes de Lucas (voyage le 06/11, premier verdict par circuit) ne changent pas.
CE SCRIPT : aucun rejeu possible ici (la préparation des feuilles prend plus de 40 minutes) ; il lit le dernier
jugement (facteurs.json) et écrit, décision par décision, ce qui est en place et ce que la règle demandera.
Aucune décision n'est prise sur ce contrôle.

Usage : python simulateur/etude_facteurs_cumules.py
"""
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import stabilite as ST  # noqa: E402

SORTIE = os.path.join(ICI, 'rapport_facteurs_cumules.json')


def _gains(r):
    pts = {m: (round(v['base'] - v['avec'], 6) if v.get('base') and v.get('avec') else None)
           for m, v in (r.get('points') or {}).items()}
    vq = r.get('vainqueur') or {}
    b, a = (vq.get('base') or {}).get('log_loss'), (vq.get('avec') or {}).get('log_loss')
    return pts, (round(b - a, 5) if b is not None and a is not None else None)


def main():
    try:
        with open(os.path.join(ICI, 'facteurs.json'), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = {}
    attendu = lambda en: (f"reste en place : ne sort que si les points ou le vainqueur perdent plus de {ST.CUMUL_ET:g} "  # noqa: E731
                          f"erreurs types sur au moins {ST.CUMUL_MIN} matchs") if en else \
                         (f"entre seulement si les points gagnent plus de {ST.CUMUL_ET:g} erreurs types sur au moins "
                          f"{ST.CUMUL_MIN} matchs, sans que le vainqueur perde plus de {ST.CUMUL_ET:g} erreurs types")
    groupes = {}
    for g, r in (doc.get('groupes') or {}).items():
        pts, vq = _gains(r)
        groupes[g] = {'en_place': bool(r.get('adopte')), 'gain_points_par_modele': pts, 'gain_vainqueur': vq,
                      'au_premier_lundi': attendu(bool(r.get('adopte')))}
    par_circuit = {c: {'en_place': b.get('adoptes'), 'matchs': b.get('matchs')} for c, b in (doc.get('par_circuit') or {}).items()}
    mc = doc.get('modele_complet') or {}
    fs = doc.get('forme_scores') or {}
    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': 246, 'statut': 'controle',
           'regle': ("règle cumulée à deux mesures (≥ 300 matchs, 2 erreurs types, chaque match compté une fois) : groupes "
                     "— points pour entrer, vainqueur en garde ; modèle complet — vainqueur pour entrer, points en garde ; "
                     "forme des scores — règle cumulée simple ; aucune décision sur ce contrôle"),
           'regle_d_avant': ("points mieux prédits (sans seuil) et vainqueur pas plus de 0,001 moins bien, deux semaines de "
                             "suite, sur six semaines glissantes dont cinq déjà vues"),
           'dernier_jugement': {'apprentissage': doc.get('apprentissage'), 'jugement': doc.get('jugement')},
           'groupes': groupes,
           'en_place_aujourd_hui': {'global': doc.get('adoptes'), 'par_circuit': par_circuit,
                                    'modele_complet': bool(mc.get('adopte')), 'forme_des_scores': bool(fs.get('adopte'))},
           'ce_qui_peut_changer': ("en place : sortie seulement sur une perte nette (plus de 2 erreurs types) ; hors place "
                                   "(conditions, charting, blessure, densité de l'air, dotation en global) : entrée seulement "
                                   "sur un gain net des points sans perte nette sur le vainqueur. Les gains de quelques "
                                   "millionièmes par point ne suffisent plus pour entrer."),
           'a_surveiller': "premier lundi : noter les entrées et sorties ; à relire quand chaque décision aura 1 000 matchs cumulés"}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    print(json.dumps({g: (v['en_place'], v['gain_points_par_modele'], v['gain_vainqueur']) for g, v in groupes.items()},
                     ensure_ascii=False, indent=0))
    return 0


if __name__ == '__main__':
    sys.exit(main())
