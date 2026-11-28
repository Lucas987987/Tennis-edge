"""533 : comptage des doublons de fin d'archive (rien n'est modifié) et étude du drapeau Grand Chelem des feuilles."""
import datetime as dt
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'simulateur'))
import controle_doublons_fin_archive as CD  # noqa: E402
import etude_grand_chelem_feuilles as GC  # noqa: E402

D = dt.date


def s(g, p, jour, niveau='A', circuit='ATP'):
    return {'nom_g': g, 'nom_p': p, 'date': jour, 'niveau': niveau, 'circuit': circuit, 'surface': 'Clay',
            'sets': [(6, 3), (6, 4)], 'complet': True, 'tournoi': 'T'}


def test_jumeaux_fenetre_de_16_jours():
    S = [s('A', 'B', D(2026, 5, 24))]
    L = [{'g': 'B', 'p': 'A', 'd': D(2026, 6, 5)}, {'g': 'A', 'p': 'B', 'd': D(2026, 6, 20)}, {'g': 'A', 'p': 'C', 'd': D(2026, 6, 2)}]
    J = CD.jumeaux(S, L, lambda x: [frozenset((x['nom_g'], x['nom_p']))], lambda x: [frozenset((x['g'], x['p']))],
                   lambda x: x['d'])
    assert list(J) == [0]


def test_comptage_seul():
    t = open(os.path.join(R, 'simulateur', 'controle_doublons_fin_archive.py'), encoding='utf-8').read()
    assert 'COMPTAGE SEUL' in t
    assert t.count("open(SORTIE, 'w'") == 1 and t.count("'w'") == 1     # n'écrit que son rapport


def test_regle_gc_ecrite_avant():
    t = open(os.path.join(R, 'simulateur', 'etude_grand_chelem_feuilles.py'), encoding='utf-8').read()
    assert 'RÈGLE ÉCRITE LE 28/11/2026, AVANT TOUT CALCUL' in t
    assert (GC.SEUIL, GC.N_MIN, GC.ACCORD_MIN, GC.QUALIF_MIN, GC.POINTS_GC) == (0.001, 1000, 0.99, 0.90, 2000)


def test_detecteur():
    r = {'points_tournoi': 2000, 'tournoi': 'Wimbledon, London, Great Britain'}
    q = {'points_tournoi': 2000, 'tournoi': 'Wimbledon, London, GB, Qualifying, 3rd Round'}
    assert GC.detecte(r, False) and not GC.detecte(q, False) and GC.detecte(q, True)
    assert not GC.detecte({'points_tournoi': 1000, 'tournoi': 'Madrid'}, True)


def test_controle_accord():
    S = [s('A', 'B', D(2025, 6, 30), 'G'), s('C', 'D', D(2025, 6, 23), 'A'), s('E', 'F', D(2025, 5, 5), 'A')]
    A = [({'nom_g': 'A', 'nom_p': 'B', 'date': D(2025, 7, 2)}, {'points_tournoi': 2000, 'tournoi': 'Wimbledon'}),
         ({'nom_g': 'C', 'nom_p': 'D', 'date': D(2025, 6, 24)}, {'points_tournoi': 2000, 'tournoi': 'Wimbledon, Qualifying'}),
         ({'nom_g': 'E', 'nom_p': 'F', 'date': D(2025, 5, 6)}, {'points_tournoi': 1000, 'tournoi': 'Madrid'})]
    c = GC.controler(S, A, lambda n: n)
    assert c['tableau_detecte_vers_G'] == 1.0 and c['tableau_G_vers_detecte'] == 1.0 and c['qualifs_G'] == 0.0


def test_fenetres_et_decision():
    f = GC.fenetres_gc([D(2026, 6, 22), D(2026, 6, 29), D(2026, 8, 24)])
    assert f == [(D(2026, 6, 22), D(2026, 8, 17)), (D(2026, 8, 24), D(2026, 10, 19))]
    x = lambda g, n=1500: {'n': n, 'gain': g}  # noqa: E731
    bon = {f'{p} {c}': x(0.0012) for p in ('periode_1', 'periode_2') for c in ('ATP', 'WTA')}
    assert GC.decider(bon).startswith('retenu')
    assert GC.decider(dict(bon, **{'periode_2 WTA': x(0.0004)})) == 'non retenu : rien ne change'
    assert 'même sur l' in GC.decider(dict(bon, **{'periode_1 ATP': x(0.0)}))
    assert GC.decider(dict(bon, **{'periode_2 ATP': x(0.01, 300)})).startswith('pas assez')


def test_le_moteur_n_est_pas_touche():
    t = open(os.path.join(R, 'simulateur', 'backtest_pronostic.py'), encoding='utf-8').read()
    assert "elo.maj(w_, l_, x['surface'], False," in t                # la production reste sans drapeau tant que rien n'est retenu
