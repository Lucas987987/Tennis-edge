"""Paquet 372 — bilan « selon la documentation » classé avec la documentation du jour du match."""
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import qualite_donnees as Q  # noqa: E402
import vitrine as V  # noqa: E402

DOC = {'champs': ['svpt'], 'joueurs': {'1': {'nom': 'A Bcd', 'sommes': {'all': [5000]}},
                                       '2': {'nom': 'E Fgh', 'sommes': {'all': [4000]}}}}
M = [{'uid': 'u1', 'circuit': 'CH', 'home': 'A Bcd', 'away': 'E Fgh', 'debut': '2026-10-01T10:00', 'p': .7, 'y': 1,
      'balles_min': 300},
     {'uid': 'u2', 'circuit': 'CH', 'home': 'A Bcd', 'away': 'E Fgh', 'debut': '2026-11-01T10:00', 'p': .6, 'y': 0,
      'balles_min': 2000}]


def juge(m):
    return m['p'], m['y']


def _tr(o):
    return {t['tranche']: t['n'] for t in o['tranches']}


def test_classement_au_jour_du_match():
    aujourdhui = Q.couverture_pronostiques(DOC, M, juge)
    assert _tr(aujourdhui)['3 000 et plus'] == 2 and aujourdhui['mesure_tranches'] == 'aujourd_hui'
    f = V.documentation_au_jour(RACINE, M, archive='/inexistant')       # tout est noté : pas besoin d'archive
    o = Q.couverture_pronostiques(DOC, M, juge, f)
    assert _tr(o)['moins de 500'] == 1 and _tr(o)['1 500 à 3 000'] == 1
    assert o['mesure_tranches'] == 'au_jour_du_match' and dict(f.sources) == {'note_au_pronostic': 2}
    # le tableau des circuits (couverture d'aujourd'hui) ne change pas
    assert o['circuits'] == aujourdhui['circuits']


def test_sans_archive_ancienne_mesure():
    M2 = [dict(m) for m in M]
    del M2[0]['balles_min']
    assert V.documentation_au_jour(RACINE, M2, archive='/inexistant') is None
