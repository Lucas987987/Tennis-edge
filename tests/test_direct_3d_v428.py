# -*- coding: utf-8 -*-
"""25/11/2026 (paquet 428, Lucas : « il faut améliorer la 3D » — rendu, joueurs, jeu des points) : éclairage linéaire,
caméra TV plus serrée, caméra du ralenti hors de la chaise de l'arbitre."""
import pathlib

HTML = (pathlib.Path(__file__).resolve().parents[1] / 'algo' / 'index.html').read_text(encoding='utf-8')
BLOC = HTML[HTML.index('const G3D = (() => {'):HTML.index('// Vue du direct choisie par le visiteur')]


def test_eclairage_lineaire():
    assert 'vec3 lin = pow(max(base, vec3(0.0)), vec3(2.2));' in BLOC
    assert 'col = pow(col, vec3(2.2)) * 1.08;' not in BLOC                     # plus de double correction gamma
    assert 'col *= 1.25;' in BLOC and "Hard: { in: '#2d5f9a', out: '#46705f'" in BLOC and "Grass: { in: '#4b8443'" in BLOC


def test_cameras():
    assert 'tv: { yaw: 0, pitch: 0.31, dist: 21.5, fov: 0.58' in BLOC
    assert 'Object.assign(VUES.tv, { pitch: 0.27, dist: 22.5 })' in BLOC        # vidéo verticale : inchangée
    assert 'if (cam.cote < 0 && Math.abs(ez) < 2.2) ez = ez < 0 ? -2.2 : 2.2;' in BLOC
    assert 'if (ex * ex + ez * ez < 1.7) return true;' in BLOC
