"""Paquet 370 — le message ROI dépassait 4 096 caractères : HTTP 400 de Telegram, run pronostic rouge."""
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import roi_algo as R  # noqa: E402


def test_morceaux_sous_la_limite_et_rien_perdu():
    texte = '\n'.join(f"<b>Ligne {i}</b> " + 'x' * (i % 90) for i in range(300))
    M = R.morceaux(texte)
    assert len(M) > 1 and all(len(m) <= R.LIMITE_TELEGRAM for m in M)
    assert '\n'.join(M) == texte
    assert all(m.count('<b>') == m.count('</b>') for m in M)


def test_court_reste_un_seul_message_et_ligne_geante_coupee():
    assert R.morceaux('a\nb') == ['a\nb']
    M = R.morceaux('y' * 9000, limite=4000)
    assert [len(m) for m in M] == [4000, 4000, 1000]


def test_echec_envoi_ne_fait_pas_planter(monkeypatch):
    import urllib.request
    monkeypatch.setenv('TELEGRAM_TOKEN', 't')
    monkeypatch.setenv('TELEGRAM_CHAT_ID', 'c')

    def refuse(*a, **k):
        raise OSError('400')
    monkeypatch.setattr(urllib.request, 'urlopen', refuse)
    R.envoyer('z' * 5000)
