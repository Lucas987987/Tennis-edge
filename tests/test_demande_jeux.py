# -*- coding: utf-8 -*-
"""25/11/2026 (paquet 430) — « Demande à l'algo » mise en valeur ; jeux du match par nombre de sets."""
import pathlib
import re
import sys

R = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / 'simulateur'))
import scenarios_match as SM  # noqa: E402

P = (R / 'algo' / 'index.html').read_text(encoding='utf-8')


def test_jeux_par_sets():
    D = [{'score': [[6, 4], [6, 4]], 'probabilite': .3, 'vainqueur': 0}, {'score': [[6, 3], [7, 5]], 'probabilite': .2, 'vainqueur': 0},
         {'score': [[4, 6], [6, 3], [6, 4]], 'probabilite': .25, 'vainqueur': 0}, {'score': [[6, 4], [3, 6], [7, 6]], 'probabilite': .25, 'vainqueur': 1}]
    J = SM.scenarios(D)['jeux']
    assert (J['p10'], J['mediane'], J['p90']) == (20, 21, 32)                     # la fourchette d'ensemble ne change pas
    assert J['par_sets']['2'] == {'p': 0.5, 'p10': 20, 'mediane': 20, 'p90': 21, 'mode': 20}
    assert J['par_sets']['3']['p'] == 0.5 and J['par_sets']['3']['p10'] == 29 and J['par_sets']['3']['p90'] == 32


def test_page():
    assert 'function jeuxParSets(J, fr)' in P and 'jeuxParSets(J, fr)] : null' in P
    assert "if (el.classList.contains('qa')) { faits.qa = el; return; }" in P
    assert '[document.getElementById(\'post-zone\'), faits.qa, barre, faits.match, faits.stats]' in P
    assert '.panel.qa{border:1.5px solid' in P
