"""535 : « Demande à l'algo » sur les pages tennis de table et badminton (réponses tirées de ce que la page montre déjà) et
bilan en direct (lecture seule, règle écrite avant)."""
import json
import os
import subprocess
import sys
import tempfile

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
import bilan_direct_tt_badminton as BD  # noqa: E402

lire = lambda p: open(os.path.join(R, p), encoding='utf-8').read()  # noqa: E731
INTERDITS = ('marché', 'pinnacle', 'cote', 'odds', 'leovegas', '4casters', 'value', 'workers.dev', 'github', 'clôture',
             'closing', 'bookmaker')


def test_demande_a_l_algo_sur_les_deux_pages():
    for p in ('algo/tennis-de-table.html', 'algo/badminton.html'):
        h = lire(p)
        assert 'function qaListe(m)' in h and 'function qaBloc(m)' in h and 'if(qaClic(e))return;' in h
        assert "if(!('p_h' in m))return '';" in h                 # match verrouillé : pas de bouton, rien de plus
        assert '+qaBloc(m)+suivre+' in h
        assert '💬 Demande à l’algo' in h and '💬 Ask the algorithm' in h
        bas = h.lower()
        for mot in INTERDITS:
            assert mot not in bas, (p, mot)


def test_bilan_regle_ecrite_et_lecture_seule():
    t = lire('scripts/bilan_direct_tt_badminton.py')
    assert 'RÈGLE ÉCRITE LE 28/11/2026, AVANT D' in t and 'LECTURE SEULE' in t
    assert '.put(' not in t                                    # n'écrit jamais dans le coffre
    assert (BD.N_INDICATION, BD.N_CONSTAT, BD.N_TRANCHE) == (300, 1000, 100)
    w = lire('.github/workflows/bilan_direct_tt_badminton.yml')
    assert 'contents: read' in w and 'git push' not in w


def test_mesure_et_jugement():
    L = [{'id': i, 'ligue': 'Poland', 'p_h': 0.7, 'g': 1 if i % 10 < 7 else 2} for i in range(1000)]
    m = BD.mesurer(L)
    assert m['matchs'] == 1000 and m['bons_pct'] == 70.0 and abs(m['log_loss'] - 0.6109) < 0.001
    assert m['tranches']['70']['matchs'] == 1000 and not m['tranches']['70']['signalee']
    j = BD.juger(m, {'log_loss': 0.65, 'bons_vainqueurs_pct': 61.0})
    assert j['niveau'] == 'constat' and j['log_loss'] == 'conforme' and j['bons_vainqueurs'] == 'conforme'
    assert BD.juger(BD.mesurer(L[:100]), None)['niveau'] == 'trop tôt'
    assert BD.juger(m, {'log_loss': 0.55, 'bons_vainqueurs_pct': 80.0})['log_loss'] == 'à surveiller'


def test_bout_en_bout_coffre_local():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, 'prive', 'tennis_de_table', 'archive'))
    with open(os.path.join(d, 'prive', 'tennis_de_table', 'archive', '2026-11.jsonl'), 'w') as f:
        f.write('\n'.join(json.dumps({'id': i, 'ligue': 'International', 'p_h': 0.6, 'g': 1}) for i in range(5)))
    env = dict(os.environ, BILAN_COFFRE_LOCAL=d)
    r = subprocess.run([sys.executable, os.path.join(R, 'scripts', 'bilan_direct_tt_badminton.py'), d], env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert 'Tennis de table : 5 matchs jugés' in r.stdout and 'trop tôt' in r.stdout
