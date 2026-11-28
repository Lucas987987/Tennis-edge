"""534 : on arrive sur le thème CLAIR (un choix déjà fait sur l'appareil reste) ; boutons Tennis de table / Badminton lisibles
en sombre (le texte sombre du bouton Arena ne doit plus l'emporter)."""
import os
import re

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lire = lambda p: open(os.path.join(R, p), encoding='utf-8').read()  # noqa: E731


def test_clair_par_defaut_partout():
    for p in ('algo/index.html', 'algo/tennis-de-table.html', 'algo/badminton.html', 'algo/apropos.html', 'scripts/pages_seo.py'):
        t = lire(p)
        assert not re.search(r"""getItem\(["']te_theme["']\)\s*\|\|\s*["']dark["']""", t), p
        assert re.search(r"""getItem\(["']te_theme["']\)\s*\|\|\s*["']light["']""", t), p
    i = lire('algo/index.html')
    assert "let TH = 'light';" in i
    assert 'data-theme-v="light" data-t="th_clair" aria-pressed="true"' in i


def test_boutons_sports_lisibles_en_sombre():
    i = lire('algo/index.html')
    assert '.arena-nav.tt-nav{background:var(--panel)!important;color:var(--ink)!important' in i
    assert not re.search(r'(?<![\w.-])\.tt-nav\{', i)          # plus de règle .tt-nav seule, moins forte que .arena-nav
    assert i.count('class="arena-nav tt-nav"') == 2
