"""Paquet 339 — une image X par tiroir de la fiche : bouton dans chaque tiroir, image toujours sombre, sans adresse
du site ni lien, sous-tiroirs repliés exclus, rien chargé d'ailleurs (polices du site intégrées)."""
import os
import re

PAGE = open(os.path.join(os.path.dirname(__file__), '..', 'algo', 'index.html'), encoding='utf-8').read()


def bloc():
    i = PAGE.index('// 22/11/2026 (paquet 339')
    return PAGE[i:PAGE.index('function rendMdj(){', i)]


def test_un_bouton_par_tiroir():
    assert 'boutonXTiroir(d);' in PAGE[PAGE.index('function tiroirsFiche(m){'):]
    assert "xt_bouton:'Image pour X'" in PAGE and "xt_bouton:'Image for X'" in PAGE


def test_jamais_d_adresse_ni_de_lien():
    b = bloc()
    assert ".replace(/gamesetalgo\\.[a-z]+/gi, '')" in b
    assert "copie.querySelectorAll('a').forEach" in b
    assert 'location.host' not in b and 'location.origin' not in b


def test_image_sombre_et_sous_tiroirs_replies_exclus():
    b = bloc()
    assert '--bg:#0E0A24' in b and '--ink:#F4F1FF' in b
    assert "if (x !== copie && !x.open) x.remove()" in b


def test_rien_charge_d_ailleurs():
    b = bloc()
    assert re.search(r"fetch\(new URL\(u, location\.href\)\)", b)
    assert 'http' not in b.replace('http://www.w3.org', '')
