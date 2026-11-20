import os
import re

HTML = open(os.path.join(os.path.dirname(__file__), '..', 'algo', 'index.html'), encoding='utf-8').read()


def _fonction(nom):
    i = HTML.index(f'function {nom}(')
    return HTML[i:HTML.index('\nfunction ', i + 10)]


def test_bouton_post_x_present_et_branche():
    assert 'id="b-post"' in HTML and 'id="post-zone"' in HTML and 'ouvrirPost(m)' in HTML


def test_post_x_sans_adresse_ni_cote_ni_marche():
    # règles : jamais d'adresse de site dans un post, aucune cote de bookmaker, pas le mot « marché »
    f = _fonction('postX')
    assert not re.search(r'https?://|workers\.dev|github\.io|\.com', f)
    assert 'cotes_justes' not in f and 'odds(' not in f
    assert not re.search(r'march[ée]', f, re.I)
    assert "L = 'fr'" in f and 'finally { L = Ls; }' in f      # toujours en français, langue du site rendue


def test_desaccord_des_deux_modeles_explique():
    # 04/11/2026 : Elo et simulation ne désignent pas le même favori (ou 10 points d'écart) → une ligne l'explique
    f = _fonction('essentielListe')
    assert "t('es_modeles'" in f and 'mo.p_elo' in f and '.10' in f
    assert 'es_modeles:' in HTML.split("es_titre:'Key points'")[0]          # version française
    assert 'Taux BRUTS' in HTML                                                # le duel dit qu'il est brut


def test_post_resultat_regles():
    # 08/11/2026 (paquet 218) : post du résultat — mêmes interdits que le post d'avant match, titre neutre si le favori perd
    f = _fonction('postResultat')
    assert not re.search(r'https?://|workers\.dev|github\.io|\.com', f)
    assert not re.search(r'march[ée]', f, re.I)
    assert "L = 'fr'" in f and 'finally { L = Ls; }' in f
    assert 'LE BILAN DU MATCH' in f and 'NOUVELLE VICTOIRE' in f
    assert 'id="b-post-res"' in HTML and "ouvrirPost(m, 'resultat')" in HTML


def test_post_avant_match_suit_le_modele():
    f = _fonction('postX')
    for ligne in ('Surface :', 'PROBABILITÉS DE VICTOIRE', 'Fiabilité de l', 'CE QUE L'):
        assert ligne not in f


def test_tiroirs_et_video_conserves():
    assert 'function tiroirsFiche(' in HTML and 'tiroirsFiche(m);' in HTML
    assert 'id="b-video"' in HTML and 'function lancerVideo(' in HTML
    assert 'data-live-stats' in HTML and 'rendApresMatch(bil)' in HTML
