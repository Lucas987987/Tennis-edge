# -*- coding: utf-8 -*-
"""27/11/2026 (paquet 499) — produit tennis de table : format lu dans l'événement, page publique sans mot interdit,
workflow qui ne commite rien (les pronostics à venir ne passent jamais par le dépôt public), page publiée et dans le
plan du site."""
import os
import re
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'tennis_de_table'))
import pronostics_tt as PT  # noqa: E402


def lire(*p):
    with open(os.path.join(R, *p), encoding='utf-8') as f:
        return f.read()


def test_ligne_api_format_et_tour():
    e = {'id': 5, 'startTimestamp': 1795561200, 'tournament': {'name': 'WTT Champions X, MS', 'uniqueTournament': {'id': 3, 'name': 'WTT Champions X, MS'}},
         'homeTeam': {'id': 1, 'name': 'A'}, 'awayTeam': {'id': 2, 'name': 'B'}, 'status': {'type': 'notstarted', 'description': 'Not started'},
         'defaultPeriodCount': 7, 'roundInfo': {'name': 'Final'}}
    r = PT.ligne_api(e, 'International')
    assert (r['id'], r['t'], r['ligue'], r['h'], r['a'], r['format'], r['tour']) == (5, 1795561200, 'International', [1, 'A'], [2, 'B'], 4, 'Final')
    e.pop('defaultPeriodCount')
    assert 'format' not in PT.ligne_api(e, 'International')


def test_equipes_ecartees():
    for t in ('ETTU Champions League', 'European Team Championships, Women', 'ETTU Europe Cup'):
        assert PT.equipe({'tournoi': t}), t
    for t in ('Feeder Dusseldorf II, MS', 'TT Elite Series', 'WTT Star Contender Doha, XD'):
        assert not PT.equipe({'tournoi': t}), t


def test_page_publique():
    h = lire('algo', 'tennis-de-table.html')
    bas = h.lower()
    for mot in ('marché', 'marche ', 'pinnacle', 'cote', 'odds', 'leovegas', '4casters', 'value', 'workers.dev', 'github',
                'clôture', 'closing', 'bookmaker'):
        assert mot not in bas, mot
    assert "fetch('/tt.json'" in h and "credentials:'same-origin'" in h
    assert 'href="#plus"' in h and 'href="/?compte=inscription"' in h     # 509 : l'accès Plus sur la page
    assert 'Ce site ne donne pas de conseil de pari' in h and '09 74 75 13 13' in h
    assert '<link rel="canonical" href="https://gamesetalgo.com/tennis-de-table">' in h
    assert 'innerHTML' in h and 'const esc=' in h            # noms des joueurs échappés


def test_workflow_ne_commite_rien():
    y = lire('.github', 'workflows', 'pronostics_tennis_de_table.yml')
    assert "cron: '41 * * * *'" in y
    assert 'contents: read' in y
    for interdit in ('git push', 'git commit', 'git add'):
        assert interdit not in y, interdit
    for f in ('/tennis_de_table/', '/historique/tennis_de_table/', '/scripts/allsports.py', '/scripts/collecte_tennis_de_table.py',
              '/scripts/r2_io.py'):
        assert f in y, f
    for s in ('RAPIDAPI_KEY', 'R2_ACCESS_KEY_ID', 'R2_SECRET_ACCESS_KEY', 'R2_ENDPOINT'):
        assert '${{ secrets.%s }}' % s in y, s
    assert 'python tennis_de_table/pronostics_tt.py .' in y
    assert 'unittest discover -s tennis_de_table/tests' in y


def test_cles_r2():
    assert PT.CLE_ETAT.startswith('prive/') and PT.CLE_ARCHIVE.startswith('prive/')
    assert PT.CLE_SITE == 'site/algo/tt.json' and PT.CLE_LIBRE == 'site/algo/tt_libre.json'


def test_page_publiee_et_dans_le_plan():
    p = lire('.github', 'workflows', 'pages.yml')
    assert 'cp algo/tennis-de-table.html _site/algo/' in p
    assert not re.search(r'tt(_libre)?\.json', p)            # les données ne passent pas par la publication du site
    assert "('/tennis-de-table', jour)" in lire('scripts', 'pages_seo.py')
    w = lire('workers', 'algo', 'worker.js')
    assert "'/tt.json': 'tt.json'" in w and "'/tt.json': 'tt_libre.json'" in w
    assert 'workers/algo/test_tt.mjs' in lire('.github', 'workflows', 'deploy_algo.yml')
