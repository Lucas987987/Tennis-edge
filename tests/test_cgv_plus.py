# -*- coding: utf-8 -*-
"""24/11/2026 (paquet 405) — conditions générales de vente, section Plus (gratuit contre Plus), paiement des fondateurs."""
import pathlib
import re

RACINE = pathlib.Path(__file__).resolve().parent.parent
PAGE = (RACINE / 'algo/index.html').read_text(encoding='utf-8')


def _seg(debut, fin):
    i = PAGE.index(debut)
    return PAGE[i:PAGE.index(fin, i)]


def test_cgv_lien_et_contenu():
    assert 'href="#cgv"' in PAGE and "'cgv'].includes(page)" in PAGE
    assert PAGE.count('lg_cgv') >= 3
    seg = _seg('function texteCgv', 'function ouvrirLegal')
    for mot in ('Conditions générales de vente', 'Terms of sale', 'L221-28', 'L224-25-12', 'sans renouvellement automatique',
                'médiateur de la consommation', 'consumer mediator', 'ni un conseil de pari', '9,99 €', '€9.99',
                'remboursé en totalité', 'ITF', 'FONDATEUR_DELAI_J', "e.mediateur"):
        assert mot in seg, mot
    for mot in ('marché', 'cote', 'Pinnacle', 'market', 'odds', 'value'):
        assert mot not in seg, mot
    assert 'x(md.nom)' in seg and 'x(md.site' in seg            # champs d'editeur.json échappés


def test_section_plus_tableau_et_preuve():
    assert 'id="plus-comp"' in PAGE and 'id="plus-preuve"' in PAGE and '<section id="plus"' in PAGE
    assert 'plus_items' not in PAGE
    seg = _seg('function rendPlus', '// 405 — fondateur')
    assert "m.circuit !== 'ITF'" in seg and 'g.n >= 30' in seg      # bilan des 30 jours : au moins 30 matchs
    for mot in ('marché', 'cote', 'Pinnacle', 'gain'):
        assert mot not in seg, mot
    for cle in ('plus_comp', 'plus_preuve', 'plus_exemple', 'fd_place', 'fd_pay_titre'):
        assert PAGE.count(cle + ':') == 2, cle                       # français et anglais


def test_paiement_seulement_pour_le_fondateur_prevenu():
    seg = _seg('function blocPaiement', '// 23/11/2026 (paquet 384')
    assert 'COMPTE.fondateur_place' in seg and 'PAIEMENT' in seg and 'map(esc)' in seg
    assert re.search(r"PAIEMENT = o\.paiement \|\| null", PAGE)


def test_demande_abonnement_prix_du_serveur():
    seg = _seg('function blocAbonnement', 'function abonnementAction')
    assert 'TARIFS_SITE[f]' in seg and '14,99' not in seg and '14.99' not in seg     # prix envoyés par le serveur
    assert "COMPTE.verifie" in seg and 'COMPTE.demande' in seg
    assert "apiCompte('abonnement'" in PAGE and 'TARIFS_SITE = o.tarifs' in PAGE
    for cle in ('ab_titre', 'ab_texte', 'ab_lib', 'ab_par', 'ab_go', 'ab_ok', 'ab_annuler', 'ab_sans_iban'):
        assert PAGE.count(cle + ':') == 2, cle
    seg_cgv = _seg('function texteCgv', 'function ouvrirLegal')
    assert "demande d'abonnement" in seg_cgv and 'subscription request' in seg_cgv
