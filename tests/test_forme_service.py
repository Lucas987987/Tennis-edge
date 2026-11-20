import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import forme_service as FSV  # noqa: E402


def _base():
    J = dt.date(2026, 10, 29)
    L = []
    # référence (60 à 120 jours avant) : 60 % au service, 38 % au retour, 400 points chacun
    for i in range(4):
        j = J - dt.timedelta(days=60 + 10 * i)
        L.append((j, 'Joueur A', 'Hard', 100, 60, 100, 38))
        L.append((j, 'Joueur B', 'Hard', 100, 70, 100, 30))
    # récent : A à 70 % au service (2 matchs, 200 points), B inchangé ; un match sur terre ignoré
    for i in range(2):
        j = J - dt.timedelta(days=5 + i)
        L.append((j, 'Joueur A', 'Hard', 100, 70, 100, 38))
        L.append((j, 'Joueur B', 'Hard', 100, 70, 100, 30))
    L.append((J - dt.timedelta(days=3), 'Joueur A', 'Clay', 100, 20, 100, 10))
    L.append((J, 'Joueur A', 'Hard', 100, 0, 100, 0))           # le jour même : exclu
    return FSV.FormeService(L, cle=lambda n: n), J


def test_variables_hausse_et_retrait():
    F, J = _base()
    v = F.variables('Joueur A', J, 'Hard')
    assert v['recent']['pts_service'] == 200 and abs(v['recent']['service'] - 0.70) < 1e-9
    assert abs(v['reference']['service'] - 0.60) < 1e-9
    assert v['sens_service'] == 'hausse' and v['sens_retour'] == 'stable'
    brut = FSV._lg(0.70) - FSV._lg(0.60)
    assert abs(v['d_service'] - round(brut * 200 / 500, 4)) < 1e-4       # retrait n / (n + 300)
    assert v['d_retour'] == 0.0


def test_surface_et_reference_minimale():
    F, J = _base()
    assert F.variables('Joueur A', J, 'Grass') is None
    v = F.variables('Joueur A', J, 'Clay')
    assert v['d_service'] == 0.0 and v['sens_service'] is None          # pas de référence sur terre


def test_decalages():
    F, J = _base()
    va, vb = F.variables('Joueur A', J, 'Hard'), F.variables('Joueur B', J, 'Hard')
    dh, da = FSV.decalages(va, vb)
    assert dh > 0 and abs(da) < 1e-9
    assert FSV.decalages(None, None) == (0.0, 0.0)


def test_surface_feuille():
    assert FSV.surface_feuille('Hardcourt indoor') == 'Hard'
    assert FSV.surface_feuille('Red clay') == 'Clay'
    assert FSV.surface_feuille('Grass') == 'Grass'
    assert FSV.surface_feuille(None) is None


def test_apres_match_fantome_forme_service():
    import apres_match as AM
    f = {'dernier': {'p_home': 0.53, 'controle': {'forme_service': {'p_home': 0.45}}}, 'debut': '2026-10-30T20:00'}
    b = AM.bilan_match('u', f, {'gagnant': 'away', 'score': '6-4 6-4'})
    fs = b['ecarts']['fantome_forme_service']
    assert fs['ll_reference'] < fs['ll_elo']            # le fantôme donnait plus de chances au vainqueur réel
