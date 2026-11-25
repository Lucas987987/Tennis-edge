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


# ── paquet 429 : vrais sons enregistrés, public plus vivant ──────────────────────────────────────────────────
import json  # noqa: E402

RACINE = pathlib.Path(__file__).resolve().parents[1]


def test_vrais_sons():
    assert "fetch('sons/sons.json?v=428')" in BLOC and 'function extrait(nom, gain, pan, rev, vitesse)' in BLOC
    assert "extrait(force >= 1 ? 'services' : 'frappes'" in BLOC and "extrait('rebonds'" in BLOC
    assert "REEL[Math.random() < 0.5 ? 'ovation' : 'ovation2']" in BLOC and 'function demarrerMurmure()' in BLOC
    assert 'function modes(sr, dur, M, clic, bruitT)' in BLOC                         # synthèse de secours
    meta = json.loads((RACINE / 'algo' / 'sons' / 'sons.json').read_text(encoding='utf-8'))
    assert meta['frappes'] == {'n': 24, 'case_s': 0.3} and meta['services']['n'] == 19 and meta['rebonds']['n'] == 20
    for n in ('frappes', 'services', 'rebonds', 'murmure', 'applaudissements', 'ovation', 'ovation2'):
        assert (RACINE / 'algo' / 'sons' / f'{n}.mp3').stat().st_size > 10000, n
    assert 'Creative Commons 0' in (RACINE / 'algo' / 'sons' / 'SOURCES.md').read_text(encoding='utf-8')
    w = (RACINE / 'workers' / 'algo' / 'worker.js').read_text(encoding='utf-8')
    assert "'/sons/sons.json': { type: 'application/json; charset=utf-8', min: 50 }" in w
    y = (RACINE / '.github' / 'workflows' / 'pages.yml').read_text(encoding='utf-8')
    assert 'cp algo/sons/*.mp3 algo/sons/sons.json algo/sons/SOURCES.md _site/algo/sons/' in y


def test_public():
    assert 'c = peau ? peauC : (chev ? chevC : (siege ? aC : aC * aIC));' in BLOC
    assert 'q.x += sin(uT * 0.6 + h * 40.0) * 0.018 * q.y;' in BLOC


def test_tension_public_431():
    assert 'if (nF >= 6) SON.tension(Math.min(1, (nF - 5) / 6));' in BLOC
    assert 'tension(niv) {' in BLOC and 'relacher() {' in BLOC and 'this.relacher(); this.applaudir(' in BLOC
    assert "(VIDEO_ICI || ADMIN) ? '<button type=\"button\" class=\"btn\" id=\"b-video\">" in HTML
