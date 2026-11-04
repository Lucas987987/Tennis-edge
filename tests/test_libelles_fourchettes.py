import os
import re
import sys

ICI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import apres_match as AM  # noqa: E402


def test_penche_haut_signifie_reel_en_dessous():
    # 04/11/2026 : pos −1 = réel SOUS la fourchette → « penche_haut » (l'annonce penche haut). Le site affichait
    # l'inverse (« réel souvent au-dessus »).
    r = AM.fiabilite_stat([-1] * 20 + [0] * 80, [1.0] * 100)
    assert r['fiabilite'] == 'penche_haut'
    html = open(os.path.join(ICI, '..', 'algo', 'index.html'), encoding='utf-8').read()
    assert re.search(r"penche_haut:'réel souvent au-dessous'", html)
    assert re.search(r"penche_bas:'réel souvent au-dessus'", html)
    assert re.search(r"penche_haut:'actual often below'", html)
