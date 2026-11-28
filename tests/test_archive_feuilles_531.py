"""531 : les feuilles anciennes (historique/archive_feuilles) lues au même format que nos feuilles ; l'algo ne les lit pas
tant que l'étude « nos données à la place de Sackmann depuis 2023 » (etude_nos_donnees_2023.py) n'a pas conclu."""
import datetime as dt
import gzip
import json
import os
import shutil
import sys
import tempfile

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'simulateur'))
import feuilles as FE  # noqa: E402


def fiche(i, jour):
    st = {'ALL': {}}
    return {'id': i, 'jour': jour, 'vainqueur': 1, 'home': {'nom': f'Joueur A{i}'}, 'away': {'nom': f'Joueur B{i}'},
            'score_home': {'sets': [6, 6]}, 'score_away': {'sets': [3, 4]}, 'stats': st, 'tournoi': 'Open', 'categorie': 'atp',
            'surface': 'Hardcourt outdoor', 'meilleur_des': 3}


def ecrire(p, L):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with gzip.open(p, 'wt', encoding='utf-8') as f:
        f.write(''.join(json.dumps(x) + '\n' for x in L))


def test_archive_seulement_sur_demande():
    d = tempfile.mkdtemp()
    try:
        ecrire(os.path.join(d, 'feuilles', '2026-06-02.jsonl.gz'), [fiche(1, '2026-06-02')])
        ecrire(os.path.join(d, 'historique', 'archive_feuilles', '2025', '2025-03-01.jsonl.gz'),
               [fiche(2, '2025-03-01'), fiche(1, '2026-06-02')])          # le même id qu'une feuille récente : ignoré
        ancien = os.environ.pop('FE_ARCHIVE', None)
        try:
            assert [m['id'] for m in FE.charger(d)] == [1]                  # l'algo : sans les feuilles anciennes
            assert [m['id'] for m in FE.charger(d, archive=True)] == [2, 1]
            os.environ['FE_ARCHIVE'] = '1'                                   # l'étude : avec
            assert [m['id'] for m in FE.charger(d)] == [2, 1]
            assert [m['id'] for m in FE.charger(d, archive=False)] == [1]
        finally:
            os.environ.pop('FE_ARCHIVE', None)
            if ancien is not None:
                os.environ['FE_ARCHIVE'] = ancien
    finally:
        shutil.rmtree(d)


def test_aucun_fichier_de_l_algo_ne_les_lit():
    import glob
    for f in glob.glob(os.path.join(R, 'simulateur', '*.py')):
        if os.path.basename(f) in ('feuilles.py', 'etude_nos_donnees_2023.py'):
            continue
        t = open(f, encoding='utf-8').read()
        assert 'archive=True' not in t and 'lire_archive' not in t, f


import etude_nos_donnees_2023 as ND  # noqa: E402

D = dt.date


def m(nom_g, nom_p, jour, circuit='ATP', fin=None, i=None):
    return {'date': jour, 'fin': fin or jour, 'circuit': circuit, 'surface': 'Hard', 'bo': 3, 'nom_g': nom_g, 'nom_p': nom_p,
            'stats': {'w': (60, 40), 'l': (60, 32)}, 'sets': [(6, 3), (6, 4)], 'complet': True, 'tour': 1, 'num': 0,
            'id': i, 'niveau': ''}


def test_regle_ecrite_avant():
    t = open(os.path.join(R, 'simulateur', 'etude_nos_donnees_2023.py'), encoding='utf-8').read()
    assert 'RÈGLE ÉCRITE LE 28/11/2026, AVANT TOUT CALCUL' in t
    assert ND.SEUIL == 0.001 and ND.N_MIN == 1000 and ND.JUGEMENT == (D(2025, 1, 1), D(2026, 6, 1))
    assert ND.DEBUT_B == {'ATP': D(2023, 1, 1), 'WTA': D(2023, 1, 1), 'CH': D(2024, 1, 1)}


def test_sources_a_et_b():
    cle = lambda n: n.lower()  # noqa: E731
    S = [m('A', 'B', D(2022, 5, 2)),                                 # avant 2023 : dans les deux
         m('C', 'D', D(2025, 3, 3), fin=D(2025, 3, 11)),             # retrouvé : A à la date de la feuille, B = la feuille
         m('E', 'F', D(2025, 3, 3), fin=D(2025, 3, 11)),             # pas retrouvé : A seulement, à la fin du tournoi
         m('G', 'H', D(2023, 6, 5), 'ITF', fin=D(2023, 6, 13)),      # ITF : Sackmann dans les deux
         m('I', 'J', D(2023, 6, 5), 'CH', fin=D(2023, 6, 13))]       # Challenger 2023 : Sackmann dans les deux
    F = [m('C', 'D', D(2025, 3, 6), i=1), m('K', 'L', D(2025, 4, 1), i=2)]
    lien = ND.apparier(S, F, cle)
    assert lien == {1: 0}
    A, B = ND.sources(S, F, lien, cle)
    jours = lambda L: sorted((e[2], e[0]) for e in L)  # noqa: E731
    assert jours(A) == [('a', D(2022, 5, 2)), ('c', D(2025, 3, 6)), ('e', D(2025, 3, 11)),
                        ('g', D(2023, 6, 13)), ('i', D(2023, 6, 13)), ('k', D(2025, 4, 1))]   # K : après Sackmann
    assert jours(B) == [('a', D(2022, 5, 2)), ('c', D(2025, 3, 6)), ('g', D(2023, 6, 13)),
                        ('i', D(2023, 6, 13)), ('k', D(2025, 4, 1))]
    Q, des = ND.requetes(S, F, lien, cle)
    assert [(q[2], q[7]) for q in Q] == [('c', 'jugement')] and des == 0


def test_notes_d_avant_le_jour():
    vus = []
    evts = [(D(2025, 1, 1), 0, 'a', 'b'), (D(2025, 1, 2), 0, 'a', 'b')]
    Q = [('q', D(2025, 1, 2), 'a', 'b')]
    ND.rejouer(evts, Q, lambda q: len(vus), lambda e: vus.append(e), lambda k: 0)
    assert len(vus) == 1                                             # le match du jour même n'est pas encore compté


def test_decision():
    x = lambda e, n=2000: {'n': n, 'ecart': e}  # noqa: E731
    bon = {'apprentissage': {c: x(0.0005) for c in ND.CIRCUITS}, 'jugement': {c: x(-0.0002) for c in ND.CIRCUITS}}
    assert ND.decider({'Elo': bon})[0].startswith('remplacer')
    pire = {'apprentissage': dict(bon['apprentissage']), 'jugement': dict(bon['jugement'], WTA=x(0.0015))}
    assert ND.decider({'Elo': pire})[0].startswith('garder Sackmann')
    peu = {'apprentissage': {c: x(0.01) for c in ND.CIRCUITS}, 'jugement': {c: x(0.01, 500) for c in ND.CIRCUITS}}
    assert ND.decider({'Elo': peu})[0].startswith('pas assez')


def test_pas_de_jugement_avant_la_fin_de_la_collecte():
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, 'historique', 'archive_feuilles', 'etat.json')
        os.makedirs(os.path.dirname(p))
        json.dump({'jours': {'2025-03-01': {}}}, open(p, 'w'))
        assert ND.collecte_finie(d) == (1, 1247)
        assert ND.main(['x', '/rien', d]) == 0
        assert not os.path.exists(ND.SORTIE) or os.path.getmtime(ND.SORTIE) < os.path.getmtime(p)
    finally:
        shutil.rmtree(d)
