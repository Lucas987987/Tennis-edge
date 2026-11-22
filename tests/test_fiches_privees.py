"""Paquet 348 — fiches joueurs privées : rien ne s'ouvre sans la clé, aucun lien dans les messages."""
import os
import subprocess

RACINE = os.path.join(os.path.dirname(__file__), '..')


def test_porte_avant_toute_route():
    w = open(os.path.join(RACINE, 'workers', 'joueurs', 'worker-joueurs.js'), encoding='utf-8').read()
    i = w.index('export default {')
    bloc = w[i:]
    assert bloc.index('await porte(request, env, url)') < bloc.index('FICHES.route(url, env)')
    assert "'acces-site-prive-v1'" in w and 'X-Robots-Tag' in w
    assert "Accès privé fermé (clé non configurée)." in w


def test_porte_js():
    r = subprocess.run(['node', '--input-type=module', '-e', r"""
import { porte } from './workers/joueurs/worker-joueurs.js';
const env = { CLE_PRIVEE: 'x'.repeat(30) };
const u = (p) => new URL('https://j.dev' + p);
let r = await porte(new Request('https://j.dev/j/abc'), env, u('/j/abc'));
if (r.status !== 303 || !r.headers.get('Location').startsWith('/connexion')) throw new Error('pas de redirection');
r = await porte(new Request('https://j.dev/j'), {}, u('/j'));
if (r.status !== 503) throw new Error('clé absente : doit rester fermé');
r = await porte(new Request('https://j.dev/j', { headers: { 'X-Cle': env.CLE_PRIVEE } }), env, u('/j'));
if (r !== null) throw new Error('la clé doit ouvrir');
const f = new FormData(); f.set('cle', env.CLE_PRIVEE); f.set('suite', '/j/abc');
r = await porte(new Request('https://j.dev/connexion', { method: 'POST', body: f }), env, u('/connexion'));
if (r.status !== 303 || !/te_acces=/.test(r.headers.get('Set-Cookie'))) throw new Error('connexion');
const cookie = r.headers.get('Set-Cookie').split(';')[0];
r = await porte(new Request('https://j.dev/j/abc', { headers: { Cookie: cookie } }), env, u('/j/abc'));
if (r !== null) throw new Error('le jeton doit ouvrir');
console.log('ok');
"""], cwd=RACINE, capture_output=True, text=True)
    assert r.returncode == 0 and 'ok' in r.stdout, r.stderr[-800:]


def test_aucun_lien_par_defaut():
    env = {k: v for k, v in os.environ.items() if k != 'FICHES_BASE'}
    r = subprocess.run(['python3', '-c', 'import sys; sys.path.insert(0, "scripts"); import lien_joueur as L; '
                        'print(repr(L.ligne_texte("A B", "C D")))'], cwd=RACINE, capture_output=True, text=True, env=env)
    assert r.stdout.strip() == "''", r.stdout
    w = open(os.path.join(RACINE, '.github', 'workflows', 'courbes_alertes.yml'), encoding='utf-8').read()
    assert "FICHES_BASE: ''" in w


def test_fiches_au_coffre():
    import sys
    sys.path.insert(0, os.path.join(RACINE, 'scripts'))
    import coffre as C
    assert C.GROUPES['profils'] == ['players_profile.json']
    w = open(os.path.join(RACINE, '.github', 'workflows', 'player_profiles.yml'), encoding='utf-8').read()
    assert w.index('push --groupe profils') < w.index('git add player_form.json')
    assert 'git add players_profile.json player_form.json' not in w
    j = open(os.path.join(RACINE, 'workers', 'joueurs', 'worker-joueurs.js'), encoding='utf-8').read()
    assert "env.COFFRE.get('prive/players_profile.json')" in j
