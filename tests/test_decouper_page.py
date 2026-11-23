"""Paquet 391 — page découpée à la publication (script et style à empreinte) et appli installable."""
import json
import os
import re
import subprocess
import sys

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import decouper_page as DP  # noqa: E402


def test_decoupe_au_meme_endroit_et_contenu_identique():
    gros_js, gros_css = 'var a = 1;\n' * 3000, '.x{color:red}\n' * 2000
    html = (f'<head><script>petit()</script><style>.p{{}}</style><style>{gros_css}</style><style id="x">{gros_css}</style>'
            f'</head><body><p>a</p><script>{gros_js}</script><p>b</p></body>')
    page, f = DP.decouper(html)
    js = [n for n in f if n.startswith('app-')][0]
    css = [n for n in f if n.startswith('style-')][0]
    assert f[js] == gros_js and f[css] == gros_css
    assert re.fullmatch(r'app-[0-9a-f]{12}\.js', js) and re.fullmatch(r'style-[0-9a-f]{12}\.css', css)
    assert page.index(f'<script src="{js}">') > page.index('<p>a</p>') and page.index(f'<script src="{js}">') < page.index('<p>b</p>')
    assert '<script>petit()</script>' in page and '<style id="x">' in page   # petits blocs et blocs nommés : inchangés
    assert DP.decouper(html.replace('var a', 'var b'))[1].keys() != f.keys()  # le contenu change → le nom change


def test_la_vraie_page_se_decoupe_et_son_script_est_valide(tmp_path):
    html = open(os.path.join(RACINE, 'algo', 'index.html'), encoding='utf-8').read()
    page, f = DP.decouper(html)
    assert len(page.encode()) < 200 * 1024
    js = [n for n in f if n.startswith('app-')]
    assert len(js) == 1
    p = tmp_path / js[0]
    p.write_text(f[js[0]], encoding='utf-8')
    r = subprocess.run(['node', '--check', str(p)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-500:]


def test_manifeste_et_icones():
    m = json.load(open(os.path.join(RACINE, 'algo', 'manifest.webmanifest'), encoding='utf-8'))
    assert m['display'] == 'standalone' and m['start_url'].startswith('./')
    for i in m['icons']:
        assert os.path.getsize(os.path.join(RACINE, 'algo', i['src'])) > 1000
    assert any(i.get('purpose') == 'maskable' for i in m['icons'])


def test_service_worker_ne_garde_ni_donnees_ni_comptes():
    sw = open(os.path.join(RACINE, 'algo', 'sw.js'), encoding='utf-8').read()
    fixes = re.search(r"const FIXES = (/.*/);", sw).group(1)
    for x in ('site.json', 'donnees.json', 'compte', 'live'):
        assert x not in fixes
    assert "req.method !== 'GET'" in sw and 'skipWaiting' in sw
