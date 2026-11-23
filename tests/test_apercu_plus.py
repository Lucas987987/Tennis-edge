"""Paquet 389 — aperçu Plus : un match terminé montré en entier aux visiteurs sans accès Plus (règle fixe)."""
import datetime as dt
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import vitrine as V  # noqa: E402
import site_leger as SL  # noqa: E402

NOW = dt.datetime(2026, 11, 23, 20, 0, tzinfo=dt.timezone.utc)
ETAT = {'joueurs': {'a': {'elo': 2000}, 'b': {'elo': 1900}, 'c': {'elo': 2300}, 'd': {'elo': 2200},
                    'e': {'elo': 2500}, 'f': {'elo': 2500}, 'g': {'elo': 1500}, 'h': {'elo': 1500}}}


def ligne(uid, debut, home, away, circuit='ATP', sim=True):
    return {'uid': uid, 'debut': debut, 'home': home, 'away': away, 'circuit': circuit, 'simulation': {'n': 1} if sim else None}


def test_regle_fixe_sans_resultat():
    L = [ligne('ab', '2026-11-23T10:00', 'A', 'B'), ligne('cd', '2026-11-23T12:00', 'C', 'D'),
         ligne('ef_a_venir', '2026-11-23T21:00', 'E', 'F'),          # pas commencé
         ligne('ef_trop_recent', '2026-11-23T18:30', 'E', 'F'),      # commencé il y a moins de 3 h
         ligne('gh', '2026-11-23T11:00', 'G', 'H', 'CH')]
    a = V.choisir_apercu(L, ETAT, {}, NOW)
    assert a == {'uid': 'cd', 'jour': '2026-11-23'}
    assert V.choisir_apercu(L, ETAT, {}, NOW, exclus={'cd'})['uid'] == 'ab'        # hors match du jour
    assert V.choisir_apercu(L, ETAT, {}, NOW, precedent={'uid': 'ab', 'jour': 'x'})['uid'] == 'ab'   # stable
    assert V.choisir_apercu([L[4]], ETAT, {}, NOW)['uid'] == 'gh'                   # Challenger à défaut
    assert V.choisir_apercu([ligne('vieux', '2026-11-22T10:00', 'E', 'F')], ETAT, {}, NOW) is None


def test_version_libre_garde_l_apercu_complet():
    site = {'match_du_jour': {'uid': 'mdj'}, 'apercu_plus': {'uid': 'cd'},
            'matchs': [{'uid': 'mdj', 'p_home': 0.6}, {'uid': 'cd', 'p_home': 0.7, 'home': 'C'}, {'uid': 'x', 'p_home': 0.5, 'home': 'X'}]}
    out = SL.libre(site)
    assert out['matchs'][1]['p_home'] == 0.7 and 'verrou' not in out['matchs'][1]
    assert out['matchs'][2] == {'uid': 'x', 'home': 'X', 'verrou': True}
    site['apercu_plus'] = None
    assert SL.libre(site)['matchs'][1].get('verrou') is True


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
