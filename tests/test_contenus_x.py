"""Paquet 363 — contenus X : image du résultat, vidéo courte et lisible sans le son, relance par le worker."""
import os
import re

RACINE = os.path.join(os.path.dirname(__file__), '..')
HTML = open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8').read()
WF = os.path.join(RACINE, '.github', 'workflows')


def test_image_resultat():
    assert 'function carteResultat(b, tournoi)' in HTML and 'data-xres=' in HTML and 'async function imageResultat(uid)' in HTML
    corps = HTML[HTML.index('function carteResultat('):HTML.index('async function imageResultat(')]
    for interdit in ('cote', 'marché', 'Pinnacle', 'value', 'gamesetalgo', 'http'):
        assert interdit not in corps, interdit
    assert "replace(/gamesetalgo\\.[a-z]+/gi, '')" in HTML[HTML.index('async function imageResultat('):]


def test_video_courte_et_bandeau():
    assert "const COURT = Q.get('court') === '1';" in HTML
    assert "(RESUME ? 4 : COURT ? 3 : 5)" in HTML and 'rejouer: dernier && !RESUME && !COURT' in HTML
    assert '<div class="f3-algo">' in HTML and "f3_algo:(n,v)=>" in HTML
    v = open(os.path.join(RACINE, 'scripts', 'video_simulation.py'), encoding='utf-8').read()
    assert "'--court'" in v and "&court=1" in v and "_courte" in v
    y = open(os.path.join(WF, 'video_simulation.yml'), encoding='utf-8').read()
    assert 'duree: [longue, courte]' in y and "--court" in y and 'types: [video_simulation]' in y


def test_relance_par_le_worker():
    w = open(os.path.join(RACINE, 'workers', 'tennis-edge-closing', 'worker.js'), encoding='utf-8').read()
    for wf, ev in (('video_simulation.yml', 'video_simulation'), ('bilan_match_du_jour.yml', 'bilan_match_du_jour'),
                   ('video_resume.yml', 'video_resume'), ('bilan_semaine.yml', 'bilan_semaine')):
        assert f"'{wf}', '{ev}'" in w, wf
        assert f'types: [{ev}]' in open(os.path.join(WF, wf), encoding='utf-8').read(), wf
    assert re.search(r"CONTENUS_X_ENABLED", w)
