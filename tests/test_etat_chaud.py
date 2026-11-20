"""État chaud (scripts/etat_chaud.py) : R2 relaie les fichiers réécrits à chaque capture ; git n'en reçoit qu'une photo."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from r2_fakes import FakeS3, install, uninstall  # noqa: E402
import etat_chaud as EC  # noqa: E402
import r2_io  # noqa: E402


def git(*a):
    return subprocess.run(['git', '-c', 'user.email=t@t', '-c', 'user.name=t', *a], check=True,
                          capture_output=True, text=True).stdout


def ecrire(nom, obj):
    Path(nom).write_text(json.dumps(obj))


def lire(nom):
    return json.loads(Path(nom).read_text())


class EtatChaud(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.tmp.name)
        os.environ['RUNNER_TEMP'] = self.tmp.name
        EC.ETAGS = os.path.join(self.tmp.name, 'etags.json')
        self.fake = FakeS3()
        install(self.fake, 'double')
        self.r2 = r2_io.client()
        git('init', '-q')

    def tearDown(self):
        os.chdir(self.cwd)
        uninstall()
        os.environ.pop('ETAT_CHAUD', None)
        self.tmp.cleanup()

    def distant(self, nom):
        return json.loads(self.fake.raw(EC.PREFIXE + nom))

    def test_aller_retour_capture(self):
        ecrire('closing_lines.json', {'m1': {'p': 1}})
        git('add', '.'); git('commit', '-qm', 'base')
        self.assertEqual(EC.pull(self.r2), {})                     # R2 vide : copie git gardée
        ecrire('closing_lines.json', {'m1': {'p': 1}, 'm2': {'p': 2}})
        self.assertEqual(EC.push(self.r2), ['closing_lines.json'])
        self.assertEqual(self.distant('closing_lines.json'), {'m1': {'p': 1}, 'm2': {'p': 2}})
        # passage suivant : la copie git (vieille, mais connue ? non : la version de base n'est jamais passée par R2)
        git('checkout', '--', 'closing_lines.json')
        self.assertEqual(EC.pull(self.r2), {'closing_lines.json': 'fusion'})
        self.assertEqual(lire('closing_lines.json'), {'m1': {'p': 1}, 'm2': {'p': 2}})

    def test_copie_git_connue_prend_r2(self):
        ecrire('closing_lines.json', {'m1': {'p': 1}})
        EC.push(self.r2)
        git('add', '.'); git('commit', '-qm', 'photo')             # la photo git = une version passée par R2
        ecrire('closing_lines.json', {'m1': {'p': 9}})                # capture suivante (cote mise à jour)
        EC.pull(self.r2); ecrire('closing_lines.json', {'m1': {'p': 9}}); EC.push(self.r2)
        git('checkout', '--', 'closing_lines.json')                   # nouveau runner : copie git = {'p': 1}
        self.assertEqual(EC.pull(self.r2), {'closing_lines.json': 'r2'})
        self.assertEqual(lire('closing_lines.json'), {'m1': {'p': 9}})   # la valeur récente gagne

    def test_ecriture_hors_relais_gagne_les_egalites(self):
        ecrire('closing_lines.json', {'m1': {'p': 1}})
        EC.push(self.r2)
        ecrire('closing_lines.json', {'m1': {'p': 1, 'repare': True}})   # réparation manuelle commitée
        self.assertEqual(EC.pull(self.r2), {'closing_lines.json': 'fusion'})
        self.assertTrue(lire('closing_lines.json')['m1']['repare'])

    def test_photo_inconnue_garde_git(self):
        ecrire('live_odds.json', {'a': 1})
        EC.push(self.r2)
        ecrire('live_odds.json', {'b': 2})
        self.assertEqual(EC.pull(self.r2), {'live_odds.json': 'git'})
        self.assertEqual(lire('live_odds.json'), {'b': 2})

    def test_conflit_fusionne_accumulateur(self):
        ecrire('closing_lines.json', {'m1': 1})
        EC.push(self.r2)
        EC.pull(self.r2)                                              # ETag lu
        self.fake.put_raw(EC.PREFIXE + 'closing_lines.json', json.dumps({'m1': 1, 'autre': 5}).encode())
        ecrire('closing_lines.json', {'m1': 1, 'nous': 7})
        EC.push(self.r2)
        attendu = {'m1': 1, 'autre': 5, 'nous': 7}
        self.assertEqual(self.distant('closing_lines.json'), attendu)
        self.assertEqual(lire('closing_lines.json'), attendu)         # la photo git = version fusionnée

    def test_conflit_photo_la_notre_gagne(self):
        ecrire('live_odds.json', {'v': 1})
        EC.push(self.r2); EC.pull(self.r2)
        self.fake.put_raw(EC.PREFIXE + 'live_odds.json', b'{"v": 2}')
        ecrire('live_odds.json', {'v': 3})
        EC.push(self.r2)
        self.assertEqual(self.distant('live_odds.json'), {'v': 3})

    def test_double_ecrase_sans_condition(self):
        self.fake.put_raw(EC.PREFIXE + 'live_odds.json', b'{"v": 0}')
        ecrire('live_odds.json', {'v': 1})
        self.assertEqual(EC.push(self.r2, ecraser=True), ['live_odds.json'])
        self.assertEqual(self.distant('live_odds.json'), {'v': 1})

    def test_json_illisible_jamais_envoye(self):
        Path('live_odds.json').write_text('{tronqué')
        self.assertEqual(EC.push(self.r2), [])
        self.assertIsNone(self.fake.raw(EC.PREFIXE + 'live_odds.json'))

    def test_garde_photo_toutes_les_deux_heures(self):
        ecrire('closing_lines.json', {'a': 1}); ecrire('autre.json', {'x': 1})
        git('add', '.'); git('commit', '-qm', 'base')
        ecrire('closing_lines.json', {'a': 2}); ecrire('autre.json', {'x': 2})
        git('add', '-A')
        self.assertEqual(EC.garde(), ['closing_lines.json'])           # commit récent : retenu
        self.assertEqual(lire('closing_lines.json'), {'a': 1})
        self.assertIn('autre.json', git('diff', '--cached', '--name-only'))   # les autres fichiers partent
        ecrire('closing_lines.json', {'a': 3}); git('add', '-A')
        self.assertEqual(EC.garde(maintenant=time.time() + 3 * 3600), [])    # 3 h plus tard : photo publiée
        self.assertIn('closing_lines.json', git('diff', '--cached', '--name-only'))

    def test_garde_lecteur_ne_publie_jamais(self):
        ecrire('matches_oddspapi.json', {'a': 1})
        git('add', '.'); git('commit', '-qm', 'base')
        ecrire('matches_oddspapi.json', {'a': 2})
        self.assertEqual(EC.garde(lecteur=True, maintenant=time.time() + 10 * 3600), ['matches_oddspapi.json'])
        self.assertEqual(git('status', '--short'), '')

    def test_modes_et_sans_r2(self):
        self.assertEqual(EC.mode({}), 'double')
        self.assertEqual(EC.mode({'ETAT_CHAUD': 'ON'}), 'on')
        self.assertEqual(EC.mode({'ETAT_CHAUD': 'n_importe'}), 'double')
        os.environ['ETAT_CHAUD'] = 'double'
        ecrire('closing_lines.json', {'a': 1}); git('add', '.'); git('commit', '-qm', 'b')
        ecrire('closing_lines.json', {'a': 2}); git('add', '-A')
        self.assertEqual(EC.main(['x', 'garde']), 0)                  # double : garde inactive, git publie tout
        self.assertIn('closing_lines.json', git('diff', '--cached', '--name-only'))
        self.assertEqual(EC.main(['x', 'pull']), 0)                   # double : pas de pull
        self.assertEqual(lire('closing_lines.json'), {'a': 2})
        self.assertEqual(EC.main(['x', 'push', 'inconnu.json']), 2)
        r2_io.reset_cache(); r2_io._CLIENT_CACHE['client'] = None     # sans secrets R2
        os.environ['ETAT_CHAUD'] = 'on'
        self.assertEqual(EC.main(['x', 'garde']), 0)
        self.assertIn('closing_lines.json', git('diff', '--cached', '--name-only'))

    def test_empreinte_egale_git(self):
        Path('f.json').write_bytes(b'{"a":1}')
        h = subprocess.run(['git', 'hash-object', 'f.json'], capture_output=True, text=True).stdout.strip()
        self.assertEqual(EC.empreinte(b'{"a":1}'), h)


if __name__ == '__main__':
    unittest.main()
