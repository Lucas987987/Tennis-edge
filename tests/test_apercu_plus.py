"""Paquets 389-390 — version libre (match commencé : le % seulement ; l'aperçu complet du 389 est abandonné, le nom
du fichier reste pour remplacer celui du paquet 389) et bilan sur 30 jours."""
import datetime as dt
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import vitrine as V  # noqa: E402
import site_leger as SL  # noqa: E402

NOW = dt.datetime(2026, 11, 23, 20, 0, tzinfo=dt.timezone.utc)


def test_version_libre_match_commence_le_pourcentage_seulement():
    """Paquet 390 (Lucas) : un match commencé n'affiche que le % de l'algo, jamais le détail."""
    site = {'match_du_jour': {'uid': 'mdj'}, 'apercu_plus': {'uid': 'cd'},
            'matchs': [{'uid': 'mdj', 'p_home': 0.6, 'sets': {'2-0': 0.4}},
                       {'uid': 'cd', 'debut': '2026-11-23T12:00', 'p_home': 0.7, 'home': 'C', 'sets': {'2-0': 0.5},
                        'scores_probables': [['6-4 6-4', 0.03]], 'simulation': {'n': 20000}},
                       {'uid': 'x', 'debut': '2026-11-23T21:00', 'p_home': 0.5, 'home': 'X'}]}
    out = SL.libre(site, NOW)
    assert out['matchs'][0]['sets'] == {'2-0': 0.4}                        # le match du jour reste complet
    assert out['matchs'][1] == {'uid': 'cd', 'debut': '2026-11-23T12:00', 'home': 'C', 'verrou': True, 'p_home': 0.7}
    assert out['matchs'][2] == {'uid': 'x', 'debut': '2026-11-23T21:00', 'home': 'X', 'verrou': True}   # à venir : rien
    assert 'apercu_plus' not in out


def test_bilan_30_jours_dans_le_bas_de_page_sans_calibration():
    doc = {'matchs': [], 'bilan': {'depuis': '2026-10-21', 'calibration': [1]}, 'bilan_30j': {'depuis': '2026-10-25', 'calibration': [1], 'global': {}}}
    site, plus = SL.decouper(doc)
    assert 'bilan_30j' not in site and plus['bilan_30j'] == {'depuis': '2026-10-25', 'global': {}}


def test_bilan_30_jours_part_de_la_bonne_date():
    res = {'matchs': [{'uid': u, 'circuit': 'ATP', 'debut': d, 'home': 'A', 'away': 'B', 'reel': {'gagnant': 'home'},
                       'dernier': {'combinaison': {'p_home': 0.7, 'vainqueur_juste': True}}} for u, d in
                      (('vieux', '2026-10-22T10:00'), ('recent', '2026-11-20T10:00'))]}
    tout, recent = V.bilan(res), V.bilan(res, '2026-10-25')
    assert tout['global']['n'] == 2 and recent['global']['n'] == 1 and recent['depuis'] == '2026-10-25'
