# -*- coding: utf-8 -*-
"""Paquet 328 (21/11/2026, Lucas : « 1 et vitesse ») — site « pro » : mentions légales, confidentialité, conditions
d'utilisation, données allégées pour le visiteur, polices servies par le site, aperçu des liens partagés."""
import json
import re
import struct
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'scripts'))
import site_leger  # noqa: E402

PAGE = (RACINE / 'algo/index.html').read_text(encoding='utf-8')
WORKER = (RACINE / 'workers/algo/worker.js').read_text(encoding='utf-8')
PAGES = (RACINE / '.github/workflows/pages.yml').read_text(encoding='utf-8')
POLICES = (RACINE / '.github/workflows/polices.yml').read_text(encoding='utf-8')


def test_decoupage_garde_l_essentiel_et_renvoie_le_reste_a_plus_tard():
    doc = {'matchs': [{'id': 1, 'p1': 'A', 'distribution_scores': [1] * 99, 'horodatage': 'x'}],
           'bilan': {'n': 3}, 'journal_changements': [1], 'validation_fiabilite': {}, 'qualite_horodatages': {}, 'maj': 'h'}
    site, plus = site_leger.decouper(doc)
    assert site['matchs'] == [{'id': 1, 'p1': 'A'}] and site['maj'] == 'h' and site['_plus'] == 'site_plus.json'
    assert set(plus) == {'bilan'}         # 380 : journal et suivi de fiabilité → site_admin.json (administrateur)
    assert 'bilan' not in site and 'qualite_horodatages' not in site
    assert doc['matchs'][0]['distribution_scores'], 'le fichier complet ne doit pas être modifié'


def test_les_champs_retires_ne_sont_jamais_lus_par_la_page():
    for k in site_leger.INUTILES_MATCH + site_leger.INUTILES_HAUT:
        assert not re.search(r'\.' + k + r'\b|\[[\'"]' + k + r'[\'"]\]', PAGE), k


def test_la_page_lit_site_json_puis_le_reste_et_garde_donnees_json_en_secours():
    assert "lireJson('site.json').catch(() => lireJson('donnees.json'))" in PAGE
    assert 'function chargerPlus()' in PAGE and 'chargerPlus();' in PAGE
    # les images et vidéos (cartes, bilan, projections) gardent le fichier complet
    assert re.search(r"MODE_IMAGE \? lireJson\('donnees.json'\)", PAGE)


def test_aucune_requete_vers_google_et_polices_alignees_sur_le_workflow():
    assert 'fonts.googleapis' not in PAGE and 'fonts.gstatic' not in PAGE
    assert 'googleapis' not in WORKER and "font-src 'self'" in WORKER
    pages = set(re.findall(r'url\(polices/([a-z0-9-]+\.woff2)\)', PAGE))
    assert len(pages) == 7
    assert pages == set(re.findall(r'\s(\S+\.woff2)\n', POLICES))
    assert 'font-display:swap' in PAGE


def test_liens_legaux_et_trois_pages():
    for h in ('#mentions', '#confidentialite', '#cgu'):
        assert f'href="{h}"' in PAGE
    for cle in ('lg_mentions', 'lg_confid', 'lg_cgu'):
        assert PAGE.count(cle) >= 3, cle  # lien + FR + EN
    i = PAGE.index('function texteLegal')
    seg = PAGE[i:PAGE.index('function ouvrirLegal')]
    for mot in ('Mentions légales', 'Confidentialité', "Conditions d'utilisation", '6-III-2', 'GitHub, Inc.', 'Cloudflare, Inc.',
                'CNIL', '09 74 75 13 13', 'aucun conseil de pari', 'conditions générales de vente'):
        assert mot in seg, mot
    # règles du site public : ni « marché », ni cotes, ni Pinnacle
    for mot in ('marché', 'cote', 'Pinnacle', 'market', 'odds'):
        assert mot not in seg, mot
    assert 'esc(' in seg or 'x(e.' in seg  # les champs de editeur.json sont échappés


def test_editeur_vide_par_defaut_et_publie():
    e = json.loads((RACINE / 'algo/editeur.json').read_text(encoding='utf-8'))
    assert {'nom', 'statut', 'adresse', 'siret', 'email'} <= set(e)
    assert not any(e[k] for k in ('nom', 'adresse', 'siret', 'email')), 'jamais de données personnelles livrées par un paquet'
    assert 'cp algo/editeur.json algo/partage.png algo/methode.html algo/apropos.html _site/algo/' in PAGES
    assert 'scripts/site_leger.py algo/donnees.json _site/algo' in PAGES
    assert re.search(r'^\s+scripts/site_leger\.py$', PAGES, re.M), 'le script doit être dans le sparse-checkout'


def test_apercu_des_liens_partages():
    b = (RACINE / 'algo/partage.png').read_bytes()
    assert b[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', b[16:24]) == (1200, 630)
    assert 'gamesetalgo' not in b.decode('latin-1').lower()
    assert '<meta property="og:image" content="https://gamesetalgo.com/partage.png">' in PAGE
    assert 'summary_large_image' in PAGE
    for m in re.findall(r'<meta (?:name|property)="(?:description|og:description)" content="([^"]+)"', PAGE):
        assert 'cote' not in m and 'marché' not in m


def test_worker_sert_les_nouveaux_fichiers():
    for c in ("'/site.json'", "'/site_plus.json'", "'/editeur.json'", "'/partage.png'", "woff2: 'font/woff2'", "png: 'image/png'"):
        assert c in WORKER, c


# 22/11/2026 (paquet 329) — page « Comment ça marche »
METHODE = (RACINE / 'algo/methode.html').read_text(encoding='utf-8')


def test_page_methode_publiee_servie_et_liee_depuis_l_accueil():
    assert "'/comment-ca-marche': 'methode.html'" in WORKER and "'/methode.html': 'methode.html'" in WORKER
    assert 'algo/methode.html algo/apropos.html _site/algo/' in PAGES
    assert PAGE.count('href="methode.html"') == 2 and "cm_lien:" in PAGE and PAGE.count('cm_court:') == 2


def test_page_methode_explique_la_regle_et_relit_seulement_le_bilan():
    for mot in ('20 000', '2018–2022', '1 000 matchs', 'Elo', 'service', 'aucun conseil de pari', 'ITF', 'règle fixe', '09 74 75 13 13'):
        assert mot in METHODE, mot
    for mot in ('marché', 'Pinnacle', 'cote', 'market', 'odds', 'value', 'gamesetalgo.com/"'):
        assert mot not in METHODE, mot
    assert "lire('site_plus.json').catch(() => lire('donnees.json'))" in METHODE
    assert 'fonts.googleapis' not in METHODE and METHODE.count('@font-face') == 7
    assert '@@POLICES@@' not in METHODE and "%23D4FF3A'" in METHODE


def test_editeur_professionnel_prevu():
    e = json.loads((RACINE / 'algo/editeur.json').read_text(encoding='utf-8'))
    assert e['tva_franchise'] is False and e['ape'] == '' and e['tva'] == ''
    assert 'article 293 B du Code général des impôts' in PAGE and 'Code APE' in PAGE


# 22/11/2026 (paquet 330) — page « Qui sommes-nous »
APROPOS = (RACINE / 'algo/apropos.html').read_text(encoding='utf-8')


def test_page_qui_sommes_nous():
    assert "'/qui-sommes-nous': 'apropos.html'" in WORKER and "'/apropos.html': 'apropos.html'" in WORKER
    assert 'href="apropos.html"' in PAGE and PAGE.count('qs_court:') == 2 and 'apropos.html${' in METHODE
    for mot in ('projet indépendant', 'Aucun conseil de pari', 'ticket sûr', 'ITF', '09 74 75 13 13', 'methode.html'):
        assert mot in APROPOS, mot
    for mot in ('marché', 'Pinnacle', 'cote', 'market', 'odds', 'value', 'Lucas'):
        assert mot not in APROPOS, mot
    assert not re.search(r'[\w.-]+@[\w-]+\.\w+', APROPOS), 'aucune adresse en dur : elle vient de editeur.json'
    assert "fetch('editeur.json" in APROPOS and 'esc(e.email)' in APROPOS
    assert 'fonts.googleapis' not in APROPOS and APROPOS.count('@font-face') == 7
