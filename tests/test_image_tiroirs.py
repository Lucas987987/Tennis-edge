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


def test_schemas_des_tiroirs_341():
    for f in ('function tuilesEssentiel(m)', 'function feuilleMiroir(f, m)', 'function visAvantMatch(A, m)',
              'function visVigilance(V, stat, lig)', 'function courbeTotaux(k)', 'function barreDuree(pv, m)'):
        assert f in PAGE, f
    assert '${tuilesEssentiel(m)}<ul>' in PAGE and '${feuilleMiroir(f, m)}' in PAGE and '${visAvantMatch(A,m)}' in PAGE
    assert '${courbeTotaux(k)}' in PAGE and '${barreDuree(pv, m)}' in PAGE and '${visVigilance(V, stat, lig)}' in PAGE


def test_pas_de_cote_dans_les_schemas():
    i = PAGE.index('function feuilleMiroir(f, m)')
    for f in ('function tuilesEssentiel(m)', 'function visVigilance', 'function courbeTotaux', 'function barreDuree',
              'function visAvantMatch'):
        j = PAGE.index(f)
        bloc = PAGE[j:PAGE.index('\nfunction ', j + 10)].lower()
        for mot in ('cote', 'odds', 'marché', 'pinnacle'):
            assert mot not in bloc, (f, mot)
    assert 'aucune cote utilisée' not in PAGE and 'no odds used' not in PAGE


def test_schemas_348():
    for f in ('function meteoTuiles(mt)', 'function duelVis(d, N)', 'function bandeStyles(sj, m)'):
        assert f in PAGE, f
    assert '${meteoTuiles(mt)}' in PAGE and '${duelVis(d,N)}' in PAGE and '${bandeStyles(sj,m)}' in PAGE
    for f in ('function meteoTuiles', 'function duelVis', 'function bandeStyles'):
        j = PAGE.index(f)
        bloc = PAGE[j:PAGE.index('\nfunction ', j + 10)].lower()
        for mot in ('cote', 'odds', 'marché', 'pinnacle'):
            assert mot not in bloc, (f, mot)
