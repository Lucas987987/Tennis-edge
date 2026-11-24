# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 423) — historique de l'algo par tranche de % : bilan public et fiche du match."""
import pathlib
import re
import sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'simulateur'))
sys.path.insert(0, str(R / 'tests'))
import vitrine as V  # noqa: E402
from test_etude_projections_tranches import _monter  # noqa: E402

P = (R / 'algo' / 'index.html').read_text(encoding='utf-8')


def test_tranches_lues_du_cote_le_plus_probable():
    T = V._tranches([(.7, 1)] * 7 + [(.7, 0)] * 3 + [(.3, 0)] * 10 + [(.52, 0)] * 4)
    assert T['70-75'] == {'n': 20, 'annonce_pct': 70.0, 'bon': 17, 'bon_pct': 85.0}   # 0,3 « non » = 0,7 de confiance
    assert T['50-55']['bon'] == 0 and list(T) == ['50-55', '70-75']


def test_bilan_et_fiche(tmp_path):
    _monter(tmp_path)
    import json
    res = json.loads((tmp_path / 'Tennis_Edge_Lab' / 'live' / 'pronostics_resultats.json').read_text())
    for m in res['matchs']:
        m.setdefault('debut', '2026-11-10T10:00')
        m.update(home=f"A {m['uid']}", away='B Bb', premier={'combinaison': {'p_home': .7, 'vainqueur_juste': True}})
    B = V.bilan(res)
    assert B['tranches']['70-75']['n'] == 240 and B['par_circuit']['CH']['tranches']['70-75']['bon'] == 168
    RT = V.reussite_tranches(str(tmp_path), B)
    assert RT['min_n'] == 100 and RT['vainqueur']['TOUS']['70-75'] == [240, 70.0, 168]
    assert set(RT) >= {'set1_favori', 'sets_secs_favori', 'set_decisif', 'tie_break', 'handicap_favori_1.5'}
    assert not any(k.startswith('total_plus_') for k in RT)          # totaux : pas avant la correction du biais Challenger


def test_page():
    assert 'function reussiteA(proj, circ, p)' in P and 'function rendReussite(m)' in P and 'id="bilan-tranches"' in P
    assert '${rendReussite(m)}' in P and "ligneVu('tie_break', m.circuit, k.tie_break)" in P and '${ligneSetsSecs(m)}' in P
    assert "ligneVu(x, m.circuit, k[x])" in P and 'total_plus' not in P[P.index('function reussiteA'):P.index('function rendBilanTranches')]
    for cle in ('rt_titre', 'rt_ligne', 'rt_note', 'bt_titre', 'bt_sous'):
        assert len(re.findall(r'\b' + cle + ':', P)) == 2, cle
    assert 'if (x && x[0] >= min)' in P and 'if (n >= min)' in P                  # règle des 100 matchs, repli
