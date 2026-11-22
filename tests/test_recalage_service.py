"""Paquet 348 — recalage affiché du service : règle, jugement seulement après le 22/11/2026, rapport seulement."""
import glob
import os
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import etude_recalage_service as RS  # noqa: E402


def test_regle():
    assert (RS.COUPURE, RS.N_MIN, RS.PRIOR) == ('2026-11-23', 1000, 100.0)


def test_rien_conclu_sous_1000_et_bon_sens():
    R = [{'circuit': 'CH', 'debut': '2026-11-10', 'stat': 'service', 'annonce': 60.0, 'reel': 61.0}] * 200
    R += [{'circuit': 'CH', 'debut': '2026-11-25', 'stat': 'service', 'annonce': 60.0, 'reel': 61.0}] * 50
    e = RS.etudier(R)['CH|service']
    assert e['retenu'] is False and 'pas encore jugeable' in e['raison']
    assert abs(e['decalage_pts'] - 1.0 * 200 / 300) < 1e-3


def test_retenu_quand_tout_passe():
    import random
    random.seed(1)
    R = [{'circuit': 'CH', 'debut': '2026-11-10', 'stat': 'service', 'annonce': 60.0, 'reel': 61.0 + random.gauss(0, 3)} for _ in range(2000)]
    R += [{'circuit': 'CH', 'debut': '2026-11-30', 'stat': 'service', 'annonce': 60.0, 'reel': 61.0 + random.gauss(0, 3)} for _ in range(1500)]
    assert RS.etudier(R)['CH|service']['retenu'] is True


def test_rapport_seulement():
    for p in glob.glob(os.path.join(RACINE, 'simulateur', '*.py')) + glob.glob(os.path.join(RACINE, 'scripts', '*.py')):
        if os.path.basename(p) != 'etude_recalage_service.py':
            assert 'rapport_recalage_service' not in open(p, encoding='utf-8').read(), p
