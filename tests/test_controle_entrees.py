"""Paquet 371 — matchs écartés, identités vues en direct, joueurs réunis contrôlés."""
import datetime as dt
import json
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import controle_entrees as CE  # noqa: E402
import elo as E  # noqa: E402
import identites as ID  # noqa: E402
import pronostics_du_jour as P  # noqa: E402


def test_espaces_seuls_ne_sont_pas_une_collision():
    assert E.collisions_identite(['Soon Woo Kwon', 'Soonwoo Kwon']) == []
    assert E.collisions_identite(['Ab C', 'A Bc'])          # deux mots de chaque côté : vrai doute, on écarte


def _m(h, a):
    return {'home': h, 'away': a, 'tournoi': 'ATP Challenger Ankara', 'debut': dt.datetime(2026, 11, 22, 9, 10)}


def test_doublon_vu_en_direct_devient_un_lien(tmp_path):
    nb = {E.cle('Tugra Duran'): 33}
    g, r = P.doublons_a_venir([_m('Aaron Funk', 'Cemil Tugra Duran'), _m('Aaron Funk', 'Tugra Duran')], E.cle, nb)
    assert [x['away'] for x in g] == ['Tugra Duran'] and r[0]['meme_classement'] is False
    assert ID.noter_observes(str(tmp_path), r, '2026-11-22') == 1
    d = ID.charger_observes(str(tmp_path))
    assert d[E.cle('Cemil Tugra Duran')]['vers'] == 'Tugra Duran'
    assert ID.noter_observes(str(tmp_path), r, '2026-11-23') == 0
    assert ID.charger_observes(str(tmp_path))[E.cle('Cemil Tugra Duran')]['vu'] == 2
    # une autre cible pour le même nom : conflit, le lien n'est plus appliqué
    r2 = [dict(r[0], garde=['Aaron Funk', 'Cemil Duran'])]
    ID.noter_observes(str(tmp_path), r2, '2026-11-24')
    assert ID.charger_observes(str(tmp_path))[E.cle('Cemil Tugra Duran')]['conflit'] is True


def test_rien_a_ecrire_sans_doublon(tmp_path):
    assert ID.noter_observes(str(tmp_path), [{'raison': 'surface_inconnue'}], '2026-11-22') == 0
    assert not os.path.exists(os.path.join(tmp_path, ID.CHEMIN_OBSERVES))


def test_fiches_contradictoires_bloquent_un_lien_vu():
    F = ID.Fiches()
    F.voir('Tugra Duran', 'TUR', 730000, 180)
    F.voir('Cemil Tugra Duran', 'TUR', 730010, 181)
    assert not ID.contredit(F, E.cle('Tugra Duran'), E.cle('Cemil Tugra Duran'))
    F.voir('Ali Duran', 'GER', 731000, 180)
    assert ID.contredit(F, E.cle('Tugra Duran'), E.cle('Ali Duran'))


def _ecrire(racine, chemin, obj):
    p = os.path.join(racine, chemin)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f)


def test_rapport(tmp_path):
    r = str(tmp_path)
    _ecrire(r, 'Tennis_Edge_Lab/live/pronostics.json', {
        'genere_le': '2026-11-23T10:00:00Z',
        'matchs': [{'home': 'A Bcd', 'away': 'Nouveau Duran', 'tournoi': 'T', 'matchs_joues': [40, 0]}],
        'rejets_entrees': [{'home': 'X Y', 'away': 'Z W', 'tournoi': 'Inconnu', 'raison': 'surface_inconnue'},
                           {'home': 'A', 'away': 'B', 'raison': 'doublon_meme_match', 'garde': ['A', 'C'],
                            'meme_classement': True}]})
    _ecrire(r, 'simulateur/elo_etat.json', {
        'joueurs': {E.cle('Tugra Duran'): {'nom': 'Tugra Duran', 'matchs': 33},
                    E.cle('Melios Efstathiou'): {'nom': 'Melios Efstathiou', 'matchs': 145}},
        'alias': {E.cle('Menelaos Efstathiou'): E.cle('Melios Efstathiou')},
        'identites': [{'alias': 'Menelaos Efstathiou', 'garde': 'Melios Efstathiou'}]})
    rap = CE.controler(r)
    assert rap['statut'] == 'ok' and rap['rejets_par_raison'] == {'surface_inconnue': 1, 'doublon_meme_match': 1}
    assert rap['surfaces_inconnues'] == ['Inconnu']
    assert rap['fusions'] == {'n': 1, 'deux_classements': [], 'cible_sans_classement': []}
    assert rap['sans_historique']['suspects'][0]['meme_nom_de_famille'] == ['Tugra Duran']
    # un joueur réuni qui garde son propre classement → alerte
    _ecrire(r, 'simulateur/elo_etat.json', {
        'joueurs': {E.cle('Menelaos Efstathiou'): {'nom': 'Menelaos Efstathiou', 'matchs': 15},
                    E.cle('Melios Efstathiou'): {'nom': 'Melios Efstathiou', 'matchs': 145}},
        'alias': {E.cle('Menelaos Efstathiou'): E.cle('Melios Efstathiou')},
        'identites': [{'alias': 'Menelaos Efstathiou', 'garde': 'Melios Efstathiou'}]})
    assert CE.controler(r)['statut'] == 'alerte'
    assert CE.main(['x', r]) == 0
    assert len(json.load(open(os.path.join(r, CE.SORTIE)))['historique']) == 1
