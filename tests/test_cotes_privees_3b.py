"""Paquet 351 — cotes en privé, étape 3b : moves_detail*.csv, suivi_direct/resultats.json, resultats_oddspapi.json."""
import os
import subprocess
import sys
import tempfile

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import coffre as C  # noqa: E402
import cotes_privees as CP  # noqa: E402

WF = os.path.join(RACINE, '.github', 'workflows')
ENTIERS = ['moves_detail.csv', 'moves_detail_hist.csv', 'moves_detail_live.csv', 'suivi_direct/resultats.json',
           'resultats_oddspapi.json']
LECTEURS = ['arena_results_auto', 'audit_qa', 'book_index', 'calibration_buckets', 'courbes_alertes', 'drift_outcome',
            'elo', 'etudes_move', 'fetch_book_curves', 'fetch_results_settlement', 'freeze_thresholds',
            'kalshi_collector', 'lab_quotidien', 'lab_v651_source_audit', 'move_vs_outcome', 'opening_value', 'pages',
            'player_profiles', 'polymarket_collector', 'pronostic', 'pronostics_quotidien', 'rattrapage_derives',
            'soft_open_detector', 'steam_pipeline']


class FauxR2:
    def __init__(self, o=None):
        self.o = dict(o or {})

    def get_with_etag(self, k):
        return (self.o[k], 'e%d' % len(self.o[k])) if k in self.o else None

    def list(self, pre):
        return [(k, len(v)) for k, v in self.o.items() if k.startswith(pre)]

    def put(self, k, data, create_only=False, if_match=None, content_type=None):
        self.o[k] = data


def _wf(n):
    return open(os.path.join(WF, n + '.yml'), encoding='utf-8').read()


def test_groupes_cles_et_exclusions():
    assert sorted(CP.entiers()) == sorted(ENTIERS)
    assert C.cle('suivi_direct/resultats.json') == 'prive/suivi_direct/resultats.json'   # jamais confondu
    assert C.cle('moves_detail_hist.csv') == 'prive/moves_detail_hist.csv'
    for f in ENTIERS:
        assert '/' + f in CP.EXCLUSIONS
    assert 'mouvements' not in C.PROTEGES and 'resultats_reglement' not in C.PROTEGES      # un seul rédacteur


def _dans_depot(fn):
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['git', 'init', '-q', d], check=True)
        ici = os.getcwd()
        os.chdir(d)
        try:
            fn()
        finally:
            os.chdir(ici)


def test_prive_rapatrie_tout_hors_prive_jamais_par_dessus_le_depot():
    def corps():
        open('moves_detail_hist.csv', 'w').write('git')
        subprocess.run(['git', 'add', 'moves_detail_hist.csv'], check=True)
        r2 = FauxR2({'prive/moves_detail_hist.csv': b'coffre', 'prive/suivi_direct/resultats.json': b'{}',
                     'prive/resultats_oddspapi.json': b'{"x":1}'})
        os.remove('moves_detail_hist.csv')                  # suivi par git mais absent (checkout partiel)
        assert CP.pull_entiers(r2, 'on') == 2               # pas celui que git suit : retour arrière seulement
        assert not os.path.exists('moves_detail_hist.csv') and open('suivi_direct/resultats.json').read() == '{}'
        assert CP.pull_entiers(r2, 'prive') == 3
        assert open('moves_detail_hist.csv').read() == 'coffre'
    _dans_depot(corps)


def test_push_et_retirer_du_redacteur():
    def corps():
        open('moves_detail.csv', 'w').write('a')
        os.makedirs('suivi_direct')
        open('suivi_direct/resultats.json', 'w').write('{}')
        subprocess.run(['git', 'add', '.'], check=True)
        r2 = FauxR2()
        n, echecs = CP.push_entiers(r2, 'mouvements')
        assert (n, echecs) == (2, 0) and r2.o['prive/suivi_direct/resultats.json'] == b'{}'
        assert 'prive/resultats_oddspapi.json' not in r2.o                 # autre groupe, autre rédacteur
        assert CP.retirer_entiers(r2, 'mouvements') == 2
        assert CP.suivis(['moves_detail.csv', 'suivi_direct/resultats.json']) == set()
        assert os.path.exists('moves_detail.csv')                           # sorti de git, gardé sur le disque
    _dans_depot(corps)


def test_arguments():
    assert CP.main(['x', 'push', '--groupe', 'inconnu']) == 2
    assert CP.main(['x', 'age']) == 2


def test_lecteurs_rapatrient_avant_de_lire():
    for n in LECTEURS:
        s = _wf(n)
        assert 'cotes_privees.py pull' in s, n
        i = s.index('cotes_privees.py pull')
        assert "ETAT_CHAUD: ${{ vars.ETAT_CHAUD || 'double' }}" in s[:i + 1] or "ETAT_CHAUD:" in s, n


def test_redacteurs():
    s = _wf('steam_pipeline')
    assert 'cotes_privees.py push --groupe mouvements' in s and 'cotes_privees.py retirer --groupe mouvements' in s
    assert s.index('push --groupe mouvements') < s.index('- name: Commit résultats + journaux')
    assert 'if [ -f "$f" ] && ! git check-ignore -q -- "$f"; then git add -- "$f"; fi' in s
    s = _wf('fetch_results_settlement')
    assert s.index('cotes_privees.py pull') < s.index('python scripts/fetch_results_settlement.py')
    assert s.index('push --groupe resultats_reglement') < s.index('- name: Commit')
    assert '! git check-ignore -q -- "$f"' in s
    for n in LECTEURS:
        assert 'push --force' not in _wf(n)


def test_observateur_lit_l_age_du_coffre():
    s = _wf('observateur_externe')
    assert 'cotes_privees.py age moves_detail_hist.csv' in s and 'git ls-files --error-unmatch moves_detail_hist.csv' in s
