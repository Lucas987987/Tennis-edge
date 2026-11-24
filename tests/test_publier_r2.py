"""Paquet 334 — le site servi par Cloudflare : _site part dans R2 (algo/ et arena/ publics, tout le reste privé),
seuls les fichiers modifiés partent, et GitHub Pages ne garde que le site public si l'envoi a réussi."""
import hashlib
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import publier_r2 as P  # noqa: E402


class FauxR2:
    def __init__(self):
        self.o, self.puts = {}, []

    def get(self, k):
        return self.o.get(k)

    def put(self, k, data, content_type='application/octet-stream', **_):
        self.o[k] = bytes(data)
        self.puts.append((k, content_type))
        return hashlib.md5(data).hexdigest()

    def list(self, prefixe):
        return [(k, len(v)) for k, v in sorted(self.o.items()) if k.startswith(prefixe)]


def site(d, fichiers):
    for rel, txt in fichiers.items():
        p = os.path.join(d, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8') as f:
            f.write(txt)


class Envoi(unittest.TestCase):
    def test_repartition_public_prive(self):
        self.assertEqual(P.cle_de('algo/index.html'), 'site/algo/index.html')
        self.assertEqual(P.cle_de('arena/arena.js'), 'site/arena/arena.js')
        for rel in ('Tennis_Edge_Lab/live/data.json', 'index.html', 'matches_oddspapi.json', 'division10.html',
                    'algorithme/x.html', 'algo.json'):
            self.assertTrue(P.cle_de(rel).startswith('prive/site/'), rel)

    def test_seuls_les_fichiers_modifies_partent(self):
        r2 = FauxR2()
        with tempfile.TemporaryDirectory() as d:
            site(d, {'algo/index.html': 'a', 'Tennis_Edge_Lab/live/x.json': '{}', '.nojekyll': ''})
            n = P.envoyer(r2, d, journal=lambda *_: None)
            self.assertEqual((n['public'][0], n['prive'][0]), (1, 1))
            self.assertEqual(r2.o['site/algo/index.html'], b'a')
            self.assertIn(('site/algo/index.html', 'text/html; charset=utf-8'), r2.puts)
            self.assertNotIn('site/.nojekyll', r2.o)
            r2.puts.clear()
            n = P.envoyer(r2, d, journal=lambda *_: None)
            self.assertEqual(r2.puts, [], 'rien de modifié, rien n’est renvoyé')
            site(d, {'Tennis_Edge_Lab/live/x.json': '{"n":2}'})
            P.envoyer(r2, d, journal=lambda *_: None)
            self.assertEqual([k for k, _ in r2.puts], ['prive/site/Tennis_Edge_Lab/live/x.json', 'prive/site/manifeste.json'])
            self.assertEqual(json.loads(r2.o['prive/site/manifeste.json'])['Tennis_Edge_Lab/live/x.json'],
                             hashlib.md5(b'{"n":2}').hexdigest())

    def test_telecharger_un_dossier_sans_ses_sous_dossiers(self):
        r2 = FauxR2()
        r2.o.update({'prive/site/Tennis_Edge_Lab/live/a.json': b'1', 'prive/site/Tennis_Edge_Lab/live/registre/b.json': b'2'})
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(P.telecharger(r2, 'prive/site/Tennis_Edge_Lab/live/', d, journal=lambda *_: None), 1)
            self.assertEqual(os.listdir(d), ['a.json'])


class Workflow(unittest.TestCase):
    W = open(os.path.join(RACINE, '.github/workflows/pages.yml'), encoding='utf-8').read()

    def test_pages_ne_garde_que_le_public_si_r2_a_reussi(self):
        self.assertIn('python scripts/publier_r2.py envoyer --site _site', self.W)
        self.assertIn("if: steps.r2.outcome == 'success'", self.W)
        self.assertIn("path: ${{ steps.r2.outcome == 'success' && '_pages' || '_site' }}", self.W)
        bloc = self.W.split('Ne garder sur GitHub Pages')[1].split('- name:')[0]
        self.assertIn('cp -R _site/algo _pages/', bloc)
        self.assertIn('cp -R _site/arena _pages/', bloc)
        self.assertNotIn('Tennis_Edge_Lab', bloc)

    def test_garde_du_lab_compare_a_la_version_r2(self):
        self.assertIn('--previous-base "${LAB_PRECEDENT}"', self.W)
        self.assertIn('base=file:///tmp/lab_precedent', self.W)
        for s in ('scripts/publier_r2.py', 'scripts/r2_io.py'):
            self.assertIn(s, self.W.split('sparse-checkout: |')[1].split('- name:')[0])


if __name__ == '__main__':
    unittest.main()


class OrdreEnvoi(unittest.TestCase):
    """424 : une page ne part qu'après ce qu'elle charge (sinon : page sans style pendant l'envoi)."""

    def test_pages_en_dernier(self):
        with tempfile.TemporaryDirectory() as d:
            site(d, {'algo/index.html': '<link href="style-0123456789ab.css">', 'algo/style-0123456789ab.css': 'a{}',
                     'algo/app-0123456789ab.js': '1', 'algo/joueur/x.html': 'j', 'algo/site.json': '{}',
                     'arena/index.html': 'a', 'algo/zz.png': 'p'})
            r2 = FauxR2()
            P.envoyer(r2, d, journal=lambda *_: None)
            ordre = [k for k, _ in r2.puts if not k.endswith(P.MANIFESTE)]
            pos = {k.split('/', 1)[1]: i for i, k in enumerate(ordre)}
            self.assertLess(pos['algo/style-0123456789ab.css'], pos['algo/index.html'])
            self.assertLess(pos['algo/app-0123456789ab.js'], pos['algo/joueur/x.html'])
            self.assertLess(pos['algo/zz.png'], pos['algo/joueur/x.html'])
            self.assertEqual({ordre[-1].split('/', 1)[1], ordre[-2].split('/', 1)[1]}, {'algo/index.html', 'arena/index.html'})


class Reprise(unittest.TestCase):
    """424 : un envoi interrompu ne fait pas tout repartir (manifeste réécrit en cours de route)."""

    def test_reprise_apres_coupure(self):
        class Coupe(FauxR2):
            def __init__(self, apres):
                super().__init__()
                self.reste = apres

            def put(self, k, data, **kw):
                if not k.endswith(P.MANIFESTE):
                    if self.reste <= 0:
                        raise RuntimeError('annulé')
                    self.reste -= 1
                return super().put(k, data, **kw)

        with tempfile.TemporaryDirectory() as d:
            site(d, dict({f'algo/match/m{i:03d}.html': str(i) for i in range(30)}, **{'algo/index.html': 'i'}))
            r2 = Coupe(apres=12)
            with self.assertRaises(RuntimeError):
                P.envoyer(r2, d, journal=lambda *_: None, taches=1, point=5)
            deja = json.loads(r2.o['site/' + P.MANIFESTE])
            self.assertGreaterEqual(len(deja), 10)                      # au moins deux points d'étape écrits
            self.assertNotIn('algo/index.html', deja)                   # la page d'accueil n'est pas partie
            r2.reste = 10 ** 6
            n = P.envoyer(r2, d, journal=lambda *_: None)
            self.assertEqual(n['public'][0], 31 - len(deja))            # seuls les fichiers manquants repartent
            self.assertEqual(len(json.loads(r2.o['site/' + P.MANIFESTE])), 31)

    def test_pages_yml_sans_annulation(self):
        y = open(os.path.join(RACINE, '.github', 'workflows', 'pages.yml'), encoding='utf-8').read()
        self.assertIn('group: pages\n  cancel-in-progress: false', y)
