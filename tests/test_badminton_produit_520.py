"""520 : le produit badminton — page publique, workflow sans commit, clés R2 privées, routes du worker."""
import os
import re
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'badminton'))
import pronostics_badminton as PB  # noqa: E402


def lire(*p):
    with open(os.path.join(R, *p), encoding='utf-8') as f:
        return f.read()


def test_page_publique():
    h = lire('algo', 'badminton.html')
    bas = h.lower()
    for mot in ('marché', 'marche ', 'pinnacle', 'cote', 'odds', 'leovegas', '4casters', 'value', 'workers.dev', 'github',
                'clôture', 'closing', 'bookmaker', 'scénario', 'fiabilit'):
        assert mot not in bas, mot
    assert "fetch('/bad.json'" in h and "credentials:'same-origin'" in h
    assert 'href="#plus"' in h and 'href="/?compte=inscription"' in h
    assert 'Ce site ne donne pas de conseil de pari' in h and '09 74 75 13 13' in h
    assert '<link rel="canonical" href="https://gamesetalgo.com/badminton">' in h
    assert 'innerHTML' in h and 'const esc=' in h


def test_workflow_ne_commite_rien():
    y = lire('.github', 'workflows', 'pronostics_badminton.yml')
    assert "cron: '27 * * * *'" in y and 'contents: read' in y
    for interdit in ('git commit', 'git push', 'git add'):
        assert interdit not in y, interdit
    for f in ('/badminton/', '/historique/badminton/', '/tennis_de_table/elo_tt.py', '/scripts/allsports.py',
              '/scripts/collecte_tennis_de_table.py', '/scripts/r2_io.py'):
        assert f in y, f
    for s in ('RAPIDAPI_KEY', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_ENDPOINT'):
        assert '${{ secrets.%s }}' % s in y, s
    assert 'python badminton/pronostics_badminton.py .' in y
    assert 'unittest discover -s badminton/tests' in y


def test_cles_r2_et_modele():
    assert PB.CLE_ETAT.startswith('prive/') and PB.CLE_ARCHIVE.startswith('prive/')
    assert PB.CLE_SITE == 'site/algo/bad.json' and PB.CLE_LIBRE == 'site/algo/bad_libre.json'
    assert PB.REGLAGE == (400, 0.3, 1.0, 32)


def test_page_publiee_routes_et_plan():
    p = lire('.github', 'workflows', 'pages.yml')
    assert 'cp algo/badminton.html _site/algo/' in p
    assert not re.search(r'bad(_libre)?\.json', p)
    assert "('/badminton', jour)" in lire('scripts', 'pages_seo.py')
    w = lire('workers', 'algo', 'worker.js')
    assert "'/bad.json': 'bad.json'" in w and "'/bad.json': 'bad_libre.json'" in w
    assert "'/badminton': 'badminton.html'" in w
