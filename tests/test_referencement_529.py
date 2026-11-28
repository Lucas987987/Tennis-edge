"""529 : référencement des pages du tennis de table et du badminton (IndexNow, plan du site)."""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
import indexnow as I  # noqa: E402


def test_pages_principales_signalees():
    assert I.url_de('algo/tennis-de-table.html') == 'https://gamesetalgo.com/tennis-de-table'
    assert I.url_de('algo/badminton.html') == 'https://gamesetalgo.com/badminton'
    assert I.url_de('algo/bad.json') is None


def test_workflows():
    for f in ('pronostics_tennis_de_table.yml', 'pronostics_badminton.yml'):
        y = open(os.path.join(R, '.github', 'workflows', f), encoding='utf-8').read()
        assert '/scripts/indexnow.py' in y and "INDEXNOW_ACTIF: '1'" in y
        i = y.index("INDEXNOW_ACTIF: '1'")
        assert 'python -m unittest' not in y[i:i + 400]            # seulement l'étape de production, jamais les tests
