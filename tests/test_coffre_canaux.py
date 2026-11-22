"""Paquet 345 — cotes en privé, étape 2 : canaux d'alertes (canal public, MISER, H13 à H17, zone) et verdicts au coffre."""
import os
import subprocess
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import coffre as C  # noqa: E402

WF = os.path.join(RACINE, '.github', 'workflows')
lire = lambda n: open(os.path.join(WF, n), encoding='utf-8').read()


def test_groupes_et_protection():
    assert {'canaux', 'verdicts'} <= C.PROTEGES
    assert 'h13_signal_state.json' in C.GROUPES['canaux'] and 'canal_public_log.jsonl' in C.GROUPES['canaux']
    assert set(C.GROUPES['verdicts']) == {'verdicts_direct.json', 'suivi_canaux.json', 'verdicts_geles.json'}


def test_gitignore():
    for f in C.GROUPES['canaux'] + C.GROUPES['verdicts']:
        assert subprocess.run(['git', 'check-ignore', '--no-index', '-q', f], cwd=RACINE).returncode == 0, f


def test_redacteur_courbes_alertes():
    w = lire('courbes_alertes.yml')
    assert w.index('pull --groupe canaux') < w.index('- name: Courbes live + alertes forward (0 requête API)')
    for g in ('canaux', 'verdicts'):
        assert f'push --groupe {g}' in w and f'retirer --groupe {g}' in w
        assert w.index(f'push --groupe {g}') < w.index('git add -A')


def test_steam_pipeline():
    w = lire('steam_pipeline.yml')
    assert w.index('pull --groupe canaux') < w.index('scripts/suivi_direct.py')
    assert 'push --groupe verdicts' in w and 'rendre --groupe canaux' in w
    bloc = w[w.index('for f in set_results.json set_results_feuilles.json'):]
    bloc = bloc[:bloc.index('; do')]
    for f in C.GROUPES['verdicts']:
        assert f not in bloc, f


def test_lecteurs():
    assert lire('lab_quotidien.yml').count('--groupe canaux') == 2 and 'rendre --groupe verdicts' in lire('lab_quotidien.yml')
    assert 'pull --groupe canaux' in lire('pages.yml') and 'pull --groupe verdicts' in lire('pages.yml')
    p = lire('pronostic.yml')
    assert p.index('pull --groupe canaux') < p.index('recherche_externe.py') and 'rendre --groupe canaux' in p
    o = lire('observateur_externe.yml')
    assert o.index('pull --groupe verdicts') < o.index('verifier_existence "verdicts_geles.json"')


def test_aucun_workflow_n_ajoute_ces_fichiers():
    for nom in os.listdir(WF):
        for l in lire(nom).splitlines():
            if 'git add' in l and not l.strip().startswith('#'):
                for f in C.GROUPES['canaux'] + C.GROUPES['verdicts']:
                    assert f not in l, (nom, l)


def test_page_publique_fermee():
    w = open(os.path.join(RACINE, 'workers', 'tennis-edge-db', 'worker.js'), encoding='utf-8').read()
    assert 'raw.githubusercontent' not in w and "status: 410" in w
