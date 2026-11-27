# -*- coding: utf-8 -*-
"""27/11/2026 (paquet 512) — l'étoile « suivre ce joueur » sur les pages /joueur (mêmes favoris que la page du tennis)."""
import os
import sys

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(R, 'scripts'))
import pages_seo as PS  # noqa: E402


def test_script_et_bouton():
    assert "fetch('/compte/api/favoris'" in PS.FAV_JOUEUR and "type:'joueur',cle:n" in PS.FAV_JOUEUR
    assert '/?compte=inscription' in PS.FAV_JOUEUR
    h = PS.page('fr', 'T', 'D', '/joueur/x', '<h1>A</h1>', script=PS.FAV_JOUEUR)
    assert PS.FAV_JOUEUR in h
    assert PS.FAV_JOUEUR not in PS.page('fr', 'T', 'D', '/match/x', '<h1>A</h1>')      # seulement les pages joueur
    src = open(os.path.join(R, 'scripts', 'pages_seo.py'), encoding='utf-8').read()
    assert 'data-fav-joueur="{e(nom)}"' in src and "script=FAV_JOUEUR)" in src
