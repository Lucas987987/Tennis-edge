"""Paquet 369 — un joueur écrit de deux façons = un classement ; un match à venir n'est affiché qu'une fois."""
import datetime as dt
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import elo as E  # noqa: E402
import identites as ID  # noqa: E402
import pronostics_du_jour as P  # noqa: E402

NAISS = dt.date(1999, 3, 2).toordinal()


def _fiches(*lignes):
    F = ID.Fiches()
    for nom, pays, nb, ht, n, tournois in lignes:
        for i in range(n):
            F.voir(nom, pays, nb, ht, tournoi=tournois[i % len(tournois)] if tournois else None)
    return F


def test_diminutif_manuel_relie():
    F = _fiches(('Menelaos Efstathiou', 'CYP', NAISS + 10, 183, 15, ['T1', 'T2']),
                ('Melios Efstathiou', 'CYP', NAISS, 183, 9, ['T3']))
    al, det = ID.liens(F)
    assert al == {E.cle('Melios Efstathiou'): E.cle('Menelaos Efstathiou')}
    assert det[0]['garde'] == 'Menelaos Efstathiou'


def test_diminutif_sans_liste_non_relie():
    F = _fiches(('Menelaos Testoulos', 'CYP', NAISS, 183, 15, ['T1']), ('Melios Testoulos', 'CYP', NAISS, 183, 9, ['T3']))
    assert ID.liens(F)[0] == {}


def test_jumelles_jamais_reliees():
    # même pays, même naissance, même taille, prénoms proches : vues dans le même tournoi → deux joueuses
    F = _fiches(('Karolina Pliskova', 'CZE', NAISS, 184, 20, ['T1', 'T2']),
                ('Karolin Pliskova', 'CZE', NAISS, 184, 5, ['T2']))
    assert ID.liens(F)[0] == {}
    # prénoms différents (Kristyna / Karolina) → pas relié même sans tournoi commun
    F = _fiches(('Karolina Pliskova', 'CZE', NAISS, 184, 20, ['T1']), ('Kristyna Pliskova', 'CZE', NAISS, 184, 5, ['T9']))
    assert ID.liens(F)[0] == {}


def test_orthographe_proche_et_garde_fous():
    base = ('Alexander Shevchenko', 'KAZ', NAISS, 185, 30, ['T1'])
    assert ID.liens(_fiches(base, ('Aleksandr Shevchenko', 'KAZ', NAISS + 20, 188, 5, ['T7'])))[0]
    assert not ID.liens(_fiches(base, ('Aleksandr Shevchenko', 'RUS', NAISS, 188, 5, ['T7'])))[0]      # pays
    assert not ID.liens(_fiches(base, ('Aleksandr Shevchenko', 'KAZ', NAISS + 90, 188, 5, ['T7'])))[0]  # naissance
    assert not ID.liens(_fiches(base, ('Aleksandr Shevchenko', 'KAZ', NAISS, 199, 5, ['T7'])))[0]       # taille
    # deux candidats possibles → on ne relie pas
    assert not ID.liens(_fiches(base, ('Aleksandr Shevchenko', 'KAZ', NAISS, 185, 5, ['T7']),
                                ('Alexandr Shevchenko', 'KAZ', NAISS, 185, 5, ['T8'])))[0]


def test_resoudre_suit_les_chaines():
    assert ID.resoudre({'a': 'b', 'b': 'c', 'x': 'x'}) == {'a': 'c', 'b': 'c'}


def _m(h, a, heure, tournoi='ATP Challenger Hersonissos 4'):
    return {'home': h, 'away': a, 'tournoi': tournoi, 'debut': dt.datetime(2026, 11, 23, heure)}


def test_doublon_a_venir_meme_joueur():
    cle_c = E.cle
    nb = {E.cle('Melios Efstathiou'): 127, E.cle('Menelaos Efstathiou'): 15}
    v = [_m('Gianluca Cadenasso', 'Menelaos Efstathiou', 12), _m('Gianluca Cadenasso', 'Melios Efstathiou', 12),
         _m('Felix Gill', 'Luca Potenza', 12)]
    g, r = P.doublons_a_venir(v, cle_c, nb)
    assert [x['away'] for x in g] == ['Melios Efstathiou', 'Luca Potenza']
    assert r[0]['away'] == 'Menelaos Efstathiou' and r[0]['raison'] == 'doublon_meme_match'


def test_doublon_a_venir_paire_reliee_et_cas_legitimes():
    al = {E.cle('Melios Efstathiou'): E.cle('Menelaos Efstathiou')}
    cle_c = lambda n: al.get(E.cle(n), E.cle(n))
    v = [_m('Menelaos Efstathiou', 'Gianluca Cadenasso', 12), _m('Gianluca Cadenasso', 'Melios Efstathiou', 14)]
    g, r = P.doublons_a_venir(v, cle_c, {})
    assert len(g) == 1 and len(r) == 1
    # adversaires différents (autre nom de famille), ou autre tournoi, ou le lendemain : deux matchs
    v = [_m('Gianluca Cadenasso', 'Melios Efstathiou', 12), _m('Gianluca Cadenasso', 'Luca Potenza', 12)]
    assert len(P.doublons_a_venir(v, E.cle, {})[0]) == 2
    v = [_m('A Bcd', 'Melios Efstathiou', 12), _m('A Bcd', 'Menelaos Efstathiou', 12, tournoi='Autre')]
    assert len(P.doublons_a_venir(v, E.cle, {})[0]) == 2
    v = [_m('A Bcd', 'Efg Hij', 1), {**_m('A Bcd', 'Efg Hij', 1), 'debut': dt.datetime(2026, 11, 24, 21)}]
    assert len(P.doublons_a_venir(v, E.cle, {})[0]) == 2


def test_396_meme_identifiant_tennisapi_relie_deux_ecritures(tmp_path):
    import gzip as _gz
    import json as _js
    (tmp_path / 'feuilles').mkdir()
    (tmp_path / 'resultats_itf').mkdir()
    with _gz.open(tmp_path / 'resultats_itf' / '2026-08.jsonl.gz', 'wt') as f:
        for i in range(5):
            f.write(_js.dumps({'home': {'id': 387395, 'nom': 'Zach Viiala'}, 'away': {'id': 10 + i, 'nom': f'Autre {i}'}}) + '\n')
    with _gz.open(tmp_path / 'feuilles' / '2026-11-16.jsonl.gz', 'wt') as f:
        f.write(_js.dumps({'home': {'id': 384145, 'nom': 'Sebastian Dominko'}, 'away': {'id': 387395, 'nom': 'Zachary Viiala'}}) + '\n')
        f.write(_js.dumps({'home': {'id': 1, 'nom': 'Karolina Pliskova'}, 'away': {'id': 2, 'nom': 'Kristyna Pliskova'}}) + '\n')
    import identites as I
    lid, det = I.liens_identifiant(str(tmp_path))
    assert lid == {I.E.cle('Zachary Viiala'): I.E.cle('Zach Viiala')}
    assert det[0]['source'] == 'meme_identifiant_tennisapi'
