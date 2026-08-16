#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
player_key.py — Appariement FIABLE de noms de joueurs.

BUG CORRIGÉ (16/08/2026)
Trois scripts (calibration_buckets.py, opening_value.py, move_vs_outcome.py)
embarquaient chacun leur copie de la même règle permissive :

    return bool(sh) and (len(sh) >= 2 or any(len(t) >= 4 for t in sh))

Un SEUL jeton commun d'au moins 4 lettres suffisait. Or un prénom fait presque
toujours 4 lettres ou plus. Conséquence : deux joueurs différents partageant un
prénom étaient considérés comme le même joueur.
    Tallon Griekspoor    ≡ Tallon Tien
    Alexander Zverev     ≡ Alexander Bublik
    Daniel Altmaier      ≡ Daniel Merida
Ce n'est pas anecdotique : 6 joueurs du jeu se prénomment « alex », 4 « arthur »,
4 « lorenzo », 4 « federico », 4 « anna », 4 « maria ».
Combiné à une tolérance de date de ±3 jours et au retour du PREMIER résultat
trouvé, la jointure attrapait régulièrement le match d'un homonyme partiel joué
la veille ou le lendemain.

MESURE : sur 1286 matchs, la règle permissive et une règle stricte donnent un
vainqueur DIFFÉRENT dans 133 cas (10,3 %), plus 27 matchs appariés à tort par la
seule version permissive.

EFFET SUR LES CONCLUSIONS : le résidu de calibration de juin passait de +12,2 pts
(permissif) à -0,8 pt (strict) sur la tranche 3,00-5,00. Autrement dit, l'« été à
surprises » qui fondait l'hypothèse gelée n°1 était en bonne partie un artefact
d'appariement de noms, pas un phénomène de marché.

RÈGLE RETENUE : au moins DEUX jetons communs.
Vérifié sans risque sur ces données : sur 530 noms distincts, 527 comportent au
moins 2 jetons (aucune forme abrégée type « A. Zverev »), les 3 restants étant
des libellés techniques (WQF2, WQF3, WQF4). La règle stricte ne fait donc perdre
aucun appariement légitime.
"""
import re
import unicodedata


def norm_tokens(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return set(t for t in re.split(r'[^a-z0-9]+', s.lower()) if len(t) >= 2)


def player_match(a, b):
    """Deux ensembles de jetons désignent-ils le MÊME joueur ?

    Deux jetons communs minimum. Un seul jeton commun — même long — ne suffit
    pas : c'est presque toujours un prénom partagé.
    """
    return len(a & b) >= 2


def pair_match(H1, A1, H2, A2):
    """Deux rencontres opposent-elles les mêmes joueurs ?

    Renvoie 'direct' (même ordre), 'swap' (ordre inversé) ou None.
    L'ordre home/away n'est pas fiable d'une source à l'autre : il faut donc
    tester les deux sens, mais sans jamais accepter un appariement partiel.
    """
    if player_match(H1, H2) and player_match(A1, A2):
        return 'direct'
    if player_match(H1, A2) and player_match(A1, H2):
        return 'swap'
    return None
