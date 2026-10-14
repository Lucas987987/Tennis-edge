# -*- coding: utf-8 -*-
"""Tests du watchdog collecteurs : aucune relance si un run est actif/en
attente/récent ou si l'API est injoignable ; relance seulement si bloqué.
Aucun accès réseau : `gh` est remplacé par un faux GitHub en mémoire.

    pytest tests/test_watchdog_collecteurs.py
"""
import datetime as dt
import importlib.util
import json
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location(
    'watchdog_collecteurs',
    os.path.join(RACINE, 'scripts', 'watchdog_collecteurs.py'))
W = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(W)

NOW = dt.datetime(2026, 10, 14, 9, 0, tzinfo=dt.timezone.utc)


def il_y_a(minutes):
    return (NOW - dt.timedelta(minutes=minutes)).strftime('%Y-%m-%dT%H:%M:%SZ')


def run(status, conclusion='', cree=0, fin=None):
    return {'status': status, 'conclusion': conclusion, 'event': 'workflow_dispatch',
            'createdAt': il_y_a(cree), 'updatedAt': il_y_a(cree if fin is None else fin)}


def ok_succes(fin):
    return run('completed', 'success', cree=fin + 16, fin=fin)


def test_run_en_cours_pas_de_relance():
    r = [run('in_progress', cree=10), ok_succes(40)]
    assert W.decider(r, float('inf'), NOW)[0] is False


def test_run_en_attente_pas_de_relance():
    for st in ('queued', 'waiting', 'pending', 'requested'):
        assert W.decider([run(st, cree=30), ok_succes(60)], 90, NOW)[0] is False


def test_annulation_de_concurrence_ne_compte_ni_comme_actif_ni_comme_publication():
    # Runs annulés récents (créés il y a 1 min) : on attend, on ne relance pas.
    r = [run('completed', 'cancelled', cree=1), ok_succes(10)]
    assert W.decider(r, float('inf'), NOW)[0] is False
    # Annulé ancien + dernier succès trop vieux : l'annulation ne rajeunit pas l'âge.
    r = [run('completed', 'cancelled', cree=8, fin=8), ok_succes(45)]
    assert W.decider(r, float('inf'), NOW)[0] is True


def test_echec_reel_recent_sans_run_actif_attend_le_seuil():
    # Échec il y a 6 min, dernier succès il y a 22 min -> bloqué : relance.
    r = [run('completed', 'failure', cree=12, fin=6), ok_succes(22)]
    assert W.decider(r, float('inf'), NOW)[0] is True
    # Dernier succès il y a 12 min : pas encore bloqué.
    r = [run('completed', 'failure', cree=8, fin=6), ok_succes(12)]
    assert W.decider(r, float('inf'), NOW)[0] is False


def test_collecte_bloquee_relance():
    r = [ok_succes(55), ok_succes(75)]
    ok, raison = W.decider(r, 55, NOW)
    assert ok is True and 'relance' in raison


def test_etat_recent_suffit_a_eviter_la_relance():
    # API sans succès récent mais stopped_at publié il y a 3 min.
    assert W.decider([ok_succes(80)], 3, NOW)[0] is False


def test_api_inaccessible_fail_safe():
    ok, raison = W.decider(None, float('inf'), NOW)
    assert ok is False and 'fail-safe' in raison


def test_liste_vide_et_etat_inconnu_relance():
    assert W.decider([], float('inf'), NOW)[0] is True


def test_run_cree_avant_publication_ne_fausse_pas_l_age():
    # last_run_at (début) ancien de 16 min mais run publié il y a 1 min.
    assert W.decider([ok_succes(1)], float('inf'), NOW)[0] is False


class FauxGitHub:
    """Simule GitHub : un dispatch crée immédiatement un run queued."""
    def __init__(self, runs, panne=False):
        self.runs, self.panne, self.dispatches = list(runs), panne, 0

    def lister(self, wf):
        return None if self.panne else list(self.runs)

    def lancer(self, wf):
        self.dispatches += 1
        self.runs.insert(0, run('queued', cree=0))
        return True


def _etat(tmp_path, stopped_min):
    p = tmp_path / 'etat.json'
    p.write_text(json.dumps({'stopped_at': il_y_a(stopped_min).rstrip('Z'),
                             'last_run_at': il_y_a(stopped_min + 16)}))
    return str(p)


def test_deux_watchdogs_concurrents_un_seul_dispatch(tmp_path):
    gh = FauxGitHub([ok_succes(55)])
    etat = _etat(tmp_path, 55)
    for _ in range(2):  # deux capture_closing qui passent à la suite
        W.traiter('k.yml', etat, gh.lister, gh.lancer, horloge=lambda: NOW)
    assert gh.dispatches == 1


def test_revérification_juste_avant_envoi(tmp_path):
    # Un autre watchdog crée un run entre la 1re et la 2e lecture.
    gh = FauxGitHub([ok_succes(55)])
    appels = []

    def lister(wf):
        appels.append(1)
        if len(appels) == 2:
            gh.runs.insert(0, run('queued', cree=0))
        return list(gh.runs)
    W.traiter('k.yml', _etat(tmp_path, 55), lister, gh.lancer, horloge=lambda: NOW)
    assert gh.dispatches == 0


def test_api_en_panne_aucun_dispatch(tmp_path):
    gh = FauxGitHub([], panne=True)
    W.traiter('k.yml', _etat(tmp_path, 90), gh.lister, gh.lancer, horloge=lambda: NOW)
    assert gh.dispatches == 0


def test_etat_illisible_ne_declenche_pas_si_run_actif(tmp_path):
    gh = FauxGitHub([run('in_progress', cree=5)])
    bad = tmp_path / 'x.json'
    bad.write_text('{pas du json')
    W.traiter('k.yml', str(bad), gh.lister, gh.lancer, horloge=lambda: NOW)
    assert gh.dispatches == 0


def test_echec_de_relance_non_bloquant(tmp_path):
    gh = FauxGitHub([ok_succes(55)])
    assert W.traiter('k.yml', _etat(tmp_path, 55), gh.lister,
                     lambda wf: False, horloge=lambda: NOW) is True


if __name__ == '__main__':
    import pytest, sys
    sys.exit(pytest.main([__file__, '-v']))
