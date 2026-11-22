"""Paquet 352 — cotes en privé, étape 4 : un groupe par rédacteur, pulls restreints, onglet Direct du Lab."""
import os
import subprocess
import sys
import tempfile

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import coffre as C  # noqa: E402
import cotes_privees as CP  # noqa: E402

WF = os.path.join(RACINE, '.github', 'workflows')
REDACTEURS = {'kalshi': 'polymarket_studies', 'courbes_absences': 'fetch_book_curves', 'value': 'value_journal',
              'book_lag': 'book_lag', 'calibration': 'calibration_buckets', 'direct': 'courbes_alertes',
              'figes': 'lab_quotidien'}


def _wf(n):
    return open(os.path.join(WF, n + '.yml'), encoding='utf-8').read()


class FauxR2:
    def __init__(self, o=None):
        self.o = dict(o or {})

    def get_with_etag(self, k):
        return (self.o[k], 'e') if k in self.o else None

    def put(self, k, data, create_only=False, if_match=None, content_type=None):
        self.o[k] = data


def test_groupes():
    for g in REDACTEURS:
        assert g in CP.GROUPES_ENTIERS and C.GROUPES[g] and g not in C.PROTEGES
    tous = CP.entiers()
    assert len(tous) == len(set(tous))
    assert len({C.cle(f) for f in tous}) == len(tous)                     # aucune clé du coffre partagée
    for f in tous:
        assert '/' + f in CP.exclusions()
    # les registres de gels du Lab restent publics (preuve de date avant les résultats)
    assert not any('registry/' in f for f in tous)


def test_entiers_argument():
    assert CP._groupes_arg(['x', 'pull']) is None
    assert CP._groupes_arg(['x', 'pull', '--entiers', 'aucun']) == ()
    assert CP._groupes_arg(['x', 'pull', '--entiers', 'mouvements,direct']) == ('mouvements', 'direct')
    assert CP.main(['x', 'pull', '--entiers', 'inconnu']) == 2
    assert CP.entiers(groupes=()) == []


def test_site_direct():
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, 'direct_matchs.json'), 'w').write('{"m":1}')
        open(os.path.join(d, 'live_odds.json'), 'w').write('{}')
        r2 = FauxR2()
        assert CP.site_direct(r2, d) == (2, 0)
        assert r2.o['prive/site/Tennis_Edge_Lab/direct/direct_matchs.json'] == b'{"m":1}'
        assert CP.site_direct(r2, d) == (0, 2)                             # inchangé : rien de réécrit


def test_redacteurs_envoient_et_retirent():
    for g, w in REDACTEURS.items():
        s = _wf(w)
        assert f'cotes_privees.py push --groupe {g}' in s, w
        assert f'cotes_privees.py retirer --groupe {g}' in s, w
        assert 'push --force' not in s
    s = _wf('lab_quotidien')
    assert s.index('push --groupe figes') < s.index('- name: R2 — rapatrier les partitions (all)')   # avant le calcul
    for f in ('games_markets.json', 'simulateur/rapport_ecart_pinnacle.json', 'simulateur/rapport_ecart_cloture.json'):
        assert '            ' + f + '\n' in s                              # dans le checkout partiel
    s = _wf('courbes_alertes')
    assert 'cotes_privees.py site' in s
    assert s.index('push --groupe direct') < s.index('- name: Commit (robuste')
    for w in ('polymarket_studies', 'fetch_book_curves', 'value_journal', 'book_lag', 'calibration_buckets'):
        assert '! git check-ignore -q --' in _wf(w), w


def test_pulls():
    attendus = {'capture_closing': 'aucun', 'courbes_alertes': 'mouvements,resultats_reglement,direct',
                'pages': 'mouvements,resultats_reglement,kalshi,direct', 'arena_results_auto': 'resultats_reglement',
                'polymarket_studies': 'kalshi', 'book_lag': 'book_lag', 'lab_v655_ingestion': 'figes'}
    for w, g in attendus.items():
        assert f'cotes_privees.py pull --entiers {g} ' in _wf(w), w
    for w in ('polymarket_studies', 'book_lag', 'lab_v652_compatibility', 'lab_v653_source_mapping', 'lab_v654_matcher'):
        s = _wf(w)
        assert s.index('cotes_privees.py pull') < s.index('python', s.index('cotes_privees.py pull') + 40), w


def test_lab_direct_lit_le_site_prive_d_abord():
    js = open(os.path.join(RACINE, 'Tennis_Edge_Lab', 'research_direct.js'), encoding='utf-8').read()
    assert "const PRIV = f => `./direct/${f}`;" in js
    for n in CP.SITE_DIRECT:
        assert f"getJson([PRIV('{n}'), RAW('{n}')" in js


def test_pull_entiers_restreint():
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['git', 'init', '-q', d], check=True)
        ici = os.getcwd()
        os.chdir(d)
        try:
            r2 = FauxR2({'prive/kalshi_lead_obs.jsonl': b'{"a":1}\n', 'prive/moves_detail_hist.csv': b'x'})
            assert CP.pull_entiers(r2, 'prive', groupes=('kalshi',)) == 1
            assert os.path.exists('kalshi_lead_obs.jsonl') and not os.path.exists('moves_detail_hist.csv')
            assert CP.pull_entiers(r2, 'prive', groupes=()) == 0
        finally:
            os.chdir(ici)
