import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import vitesse_courts as V  # noqa: E402


def test_noms_archive_et_tennisapi_se_rejoignent():
    assert V.norme('Paris Masters') == V.norme('Paris, France') == V.norme('ATP Paris') == 'paris'
    assert V.norme('Mouilleron-Le-Captif CH') == V.norme('Mouilleron-le-Captif, France') == V.norme('ATP Challenger Mouilleron-le-Captif')
    assert V.cle_officielle('Tour Finals') == 'atp finals' and V.cle_officielle('Montreal, Canada') == 'canada'
    assert V.cle_officielle('Paris Olympics') is None and V.cle_officielle('Ningbo CH') is None


def test_cpi_officiel_lisible():
    racine = os.path.join(os.path.dirname(__file__), '..')
    cpi = V.lire_cpi(racine)
    assert cpi[('paris', 2026)] == 47.9 and cpi[('paris', 2025)] == 35.1 and len(cpi) >= 100


def test_etalonnage_retrouve_une_relation_connue():
    I, cpi = {}, {}
    for i in range(40):
        t = ['paris', 'miami', 'madrid', 'rome', 'shanghai'][i % 5]
        an = 2010 + i
        s, a = (i % 7) / 100, (i % 5) / 200
        I[('ATP', t, an)] = {'pts': 8000, 'service': s, 'aces': a, 'nom': t}
        cpi[(t, an)] = 30 + 100 * s + 200 * a
    et, rows = V.etalonner(I, cpi)
    assert len(rows) == 40 and et['erreur_moyenne_tournoi_de_cote'] < 0.01
    assert abs(et['coefs'][1] - 100) < 0.5 and abs(et['coefs'][2] - 200) < 1


def test_vitesse_du_match_edition_en_cours_sinon_precedente():
    doc = {'tournois': {'ATP|paris': {'2025': {'cpi_estime': 35.0, 'cpi_officiel': 35.1, 'classe': 'moyenne'}},
                        'CH|ningbo': {'2026': {'cpi_estime': 36.0, 'cpi_officiel': None, 'classe': 'moyenne'}}}}
    assert V.vitesse_du_match(doc, 'ATP', 'ATP Paris', dt.date(2026, 11, 4))['annee'] == 2025
    assert V.vitesse_du_match(doc, 'CH', 'ATP Challenger Ningbo', dt.date(2026, 11, 4))['cpi_estime'] == 36.0
    assert V.vitesse_du_match(doc, 'WTA', 'WTA Ningbo', dt.date(2026, 11, 4)) is None
    assert V.classe(47.9) == 'rapide' and V.classe(25) == 'lente'
