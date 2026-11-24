# -*- coding: utf-8 -*-
"""24/11/2026 — repère des gros favoris dans le bilan, vainqueur peu documenté, nom au mot répété."""
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))

import bilan_algo as B  # noqa: E402
import pronostics_du_jour as P  # noqa: E402


def m(p_home, juste, gagnant='home', mj=(100, 100)):
    return {'premier': {'combinaison': {'p_home': p_home, 'vainqueur_juste': juste}}, 'reel': {'gagnant': gagnant},
            'matchs_joues': list(mj)}


def test_repere_compte_attendu_et_perdus():
    T = [m(0.95, True), m(0.95, False, 'away'), m(0.05, True, 'away'), m(0.80, False, 'away'), m(0.9, None)]
    r = B.repere_gros_favoris(T)
    assert '3 favoris annoncés' in r and '1 battu ' in r and '0,2 défaites attendues' in r
    assert 'ne pas conclure' in r


def test_repere_vide():
    assert B.repere_gros_favoris([m(0.6, True)]) is None


def test_vainqueur_peu_documente():
    assert 'aucun match classé' in B.vainqueur_peu_documente(m(0.99, False, 'away', (94, 0)))
    assert '11 matchs' in B.vainqueur_peu_documente(m(0.97, False, 'away', (29, 11)))
    assert B.vainqueur_peu_documente(m(0.96, False, 'away', (162, 117))) == ''
    assert B.vainqueur_peu_documente({'reel': {'gagnant': 'home'}}) == ''


def test_nom_sans_doublon():
    assert P.nom_sans_doublon('William Mroz Mroz', {'mrozwilliam'}) == 'William Mroz'
    assert P.nom_sans_doublon('Lu Lu', set()) == 'Lu Lu'                  # nom réel possible : jamais touché s'il est inconnu
    assert P.nom_sans_doublon('William Mroz', {'mrozwilliam'}) == 'William Mroz'
    assert P.nom_sans_doublon('Ab Ab', {'ab', 'abab'}) == 'Ab Ab'         # l'écriture d'origine est connue : on la garde
