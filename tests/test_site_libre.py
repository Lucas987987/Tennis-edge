"""Paquet 377 — version libre du site : le match du jour complet, les autres matchs sans aucun pronostic."""
import json
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import site_leger as SL  # noqa: E402


def _site():   # 24/11/2026 : matchs dans le futur (le test cassait une fois l'heure passée : match « commencé »)
    m = lambda u, p: {'uid': u, 'debut': '2099-11-24T10:00', 'tournoi': 'T', 'circuit': 'CH', 'surface': 'Hard',
                      'home': 'A ' + u, 'away': 'B ' + u, 'p_home': p, 'sets': {'2-0': .4}, 'simulation': {'n': 20000},
                      'cotes_justes': [1.5, 3.0], 'fiabilite': {'note': 80}, 'scenarios': [1]}
    return {'match_du_jour': {'uid': 'u1'}, 'matchs': [m('u1', .61), m('u2', .73), m('u3', .55)], 'bilan': {'n': 3}}


def test_libre_ne_garde_que_l_affiche():
    L = SL.libre(_site())
    par = {m['uid']: m for m in L['matchs']}
    assert par['u1']['p_home'] == .61 and 'verrou' not in par['u1']             # le match offert, complet
    for u in ('u2', 'u3'):
        assert par[u]['verrou'] is True
        assert set(par[u]) <= set(SL.AFFICHE) | {'verrou'}
    txt = json.dumps([par['u2'], par['u3']])
    for interdit in ('p_home', 'sets', 'simulation', 'cotes_justes', 'fiabilite', 'scenarios', '0.73', '0.55'):
        assert interdit not in txt, interdit
    assert L['acces'] == 'libre' and L['bilan'] == {'n': 3}


def test_ecrit_les_trois_fichiers(tmp_path):
    src = tmp_path / 'd.json'
    src.write_text(json.dumps(_site()), encoding='utf-8')
    assert SL.main(['x', str(src), str(tmp_path / 'out')]) == 0
    assert sorted(os.listdir(tmp_path / 'out')) == ['site.json', 'site_admin.json', 'site_libre.json', 'site_plus.json']
    libre = json.load(open(tmp_path / 'out' / 'site_libre.json'))
    assert sum(1 for m in libre['matchs'] if not m.get('verrou')) == 1


def test_pages_ne_publie_pas_les_donnees_completes():
    w = open(os.path.join(RACINE, '.github', 'workflows', 'pages.yml'), encoding='utf-8').read()
    assert 'rm -f _pages/algo/site.json _pages/algo/donnees.json _pages/algo/site_admin.json' in w


def test_sections_internes_reservees_a_l_admin():
    """380 : journal, suivi de fiabilité, désaccords, données de service, calibration : site_admin.json seulement."""
    doc = dict(_site(), journal_changements={'changements': [1]}, validation_fiabilite={'g': 1}, desaccords={'d': 1},
               qualite_donnees={'q': 1}, rejoue={'r': 1}, fiabilite_stats={'f': 1}, bilan={'n': 3, 'calibration': [{'a': 1}]})
    site, plus = SL.decouper(doc)
    for k in SL.INTERNES:
        assert k not in site and k not in plus and k not in SL.libre(site), k
    assert 'calibration' not in plus['bilan'] and plus['bilan']['n'] == 3
    assert site['fiabilite_stats'] == {'f': 1}                      # « Statistiques annoncées » reste publique
    adm = SL.interne(doc)
    assert set(adm) == set(SL.INTERNES) | {'bilan_calibration'} and adm['bilan_calibration'] == [{'a': 1}]


def test_page_cache_les_sections_internes():
    html = open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8').read()
    for ident in ('journal-h', 'suivi-h', 'qualite-h', 'calib-h'):
        assert f'<section aria-labelledby="{ident}" class="interne" hidden>' in html
    for ident in ('bilan-h', 'fs-h'):
        assert f'<section aria-labelledby="{ident}">' in html
