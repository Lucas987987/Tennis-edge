"""Paquet 392 — les études privées n'écrivent aucun chiffre de comparaison aux cotes dans les journaux GitHub (publics)."""
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import telegram_envoi as TE  # noqa: E402


def test_journal_public(monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    assert TE.journal_public()
    monkeypatch.delenv('GITHUB_ACTIONS')
    assert not TE.journal_public()


def test_les_trois_etudes_privees_se_taisent_dans_actions():
    for f in ('etude_marches_derives.py', 'suivi_desaccords_pinnacle.py', 'etude_algo_cloture.py'):
        assert 'journal_public()' in open(os.path.join(RACINE, 'simulateur', f), encoding='utf-8').read(), f
