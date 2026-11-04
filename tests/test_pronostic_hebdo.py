import os
import subprocess
import sys

ICI = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import bilan_algo as B  # noqa: E402


def _aide(script, *args):
    return subprocess.run([sys.executable, os.path.join(ICI, '..', 'simulateur', script), *args, '-h'],
                          capture_output=True, text=True)


def test_racine_en_argument_positionnel():
    # 02/11/2026 : « profils_robustes.py /tmp/sackmann . --max 2000 » → « unrecognized arguments: . »
    for script in ('profils_robustes.py', 'styles_joueurs.py'):
        r = _aide(script, '/tmp/sackmann', '.', '--max', '2000')
        assert r.returncode == 0, r.stderr
        assert 'racine_pos' in r.stdout


def test_texte_telegram_echappe_hors_balises():
    t = B.texte_telegram('<b>Bilan</b>\n+0.0003 < 0.001 & 5 > 3 <i>ok</i> &amp; <a href="https://x.y">lien</a>')
    assert t == ['<b>Bilan</b>\n+0.0003 &lt; 0.001 &amp; 5 &gt; 3 <i>ok</i> &amp; <a href="https://x.y">lien</a>']


def test_texte_telegram_decoupe():
    morceaux = B.texte_telegram('\n'.join(['x' * 100] * 100))
    assert len(morceaux) == 3 and all(len(m) < 4096 for m in morceaux)
    assert ''.join(morceaux).count('x') == 10000


def test_checkout_quotidien_contient_le_coffre():
    # 04/11/2026 : « coffre.py push --groupe pronostics » sans le script dans le checkout partiel = échec silencieux
    wf = open(os.path.join(ICI, '..', '.github', 'workflows', 'pronostics_quotidien.yml'), encoding='utf-8').read()
    if 'coffre.py push' in wf:
        assert '/scripts/coffre.py\n' in wf and '/scripts/r2_io.py\n' in wf


def test_tout_workflow_du_coffre_a_le_script():
    # 04/11/2026 : un checkout partiel sans scripts/coffre.py faisait échouer en silence push et retrait du coffre
    import glob
    for chemin in glob.glob(os.path.join(ICI, '..', '.github', 'workflows', '*.yml')):
        wf = open(chemin, encoding='utf-8').read()
        if 'coffre.py' not in wf.replace('# ', '') or 'sparse-checkout: |' not in wf:
            continue
        motifs = [l.strip() for l in wf.split('sparse-checkout: |', 1)[1].split('\n') if l.strip() and not l.strip().startswith('#')]
        bloc = motifs[:motifs.index(next(m for m in motifs if m.endswith(':') or ': ' in m))] if any(
            m.endswith(':') or ': ' in m for m in motifs) else motifs
        if 'python scripts/coffre.py' in wf and '/*' not in bloc:
            assert {'scripts/coffre.py', '/scripts/coffre.py'} & set(bloc), os.path.basename(chemin)
            assert {'scripts/r2_io.py', '/scripts/r2_io.py'} & set(bloc), os.path.basename(chemin)
