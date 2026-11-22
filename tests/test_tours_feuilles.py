"""Paquet 349 — noms de tours TennisApi traduits en codes d'archive (ordre des matchs d'un même jour)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import feuilles as FE  # noqa: E402


def test_traduction():
    O = FE.donnees.ORDRE_TOURS
    assert FE.ordre_tour('Qualification Round 1') == O['Q1'] == 0
    assert FE.ordre_tour('Qualification Final') == O['Q2']
    assert FE.ordre_tour('Round of 32') == O['R32'] and FE.ordre_tour('Round of 16') == O['R16']
    assert FE.ordre_tour('Quarterfinals') == O['QF'] and FE.ordre_tour('Semifinals') == O['SF'] and FE.ordre_tour('Final') == O['F']
    assert FE.ordre_tour('R32') == O['R32']             # codes d'archive inchangés
    assert FE.ordre_tour('Inconnu') == 6 and FE.ordre_tour(None) == 6
    assert FE.ordre_tour('Qualification Round 1') < FE.ordre_tour('Qualification Final') < FE.ordre_tour('Round of 32')
