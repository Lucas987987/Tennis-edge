"""Paquet 338 — sorties du Lab (cotes, CLV Pinnacle, explorateur, registre) et instantané data.js au coffre privé."""
import os
import subprocess
import sys
import tempfile
import unittest

RACINE = os.path.join(os.path.dirname(__file__), '..')
sys.path.insert(0, os.path.join(RACINE, 'scripts'))
import coffre as C  # noqa: E402

WF = os.path.join(RACINE, '.github', 'workflows')


def lire(nom):
    return open(os.path.join(WF, nom), encoding='utf-8').read()


class FauxR2:
    def __init__(self, o=None):
        self.o = dict(o or {})

    def list(self, pre):
        return [(k, len(v)) for k, v in self.o.items() if k.startswith(pre)]

    def get_with_etag(self, k):
        return (self.o[k], 'e' + str(len(self.o[k]))) if k in self.o else None

    def put(self, k, data, create_only=False, if_match=None, content_type=None):
        self.o[k] = data


class Groupes(unittest.TestCase):
    def test_cles_sans_collision(self):
        vus = {}
        for g, L in C.GROUPES.items():
            for f in L:
                k = C.cle(f)
                self.assertEqual(vus.setdefault(k, f), f, f'{f} et {vus[k]} → même clé {k}')

    def test_registre_cle_a_part(self):
        self.assertEqual(C.cle('Tennis_Edge_Lab/live/registre/index.json'), 'prive/registre/index.json')
        self.assertEqual(C.cle('Tennis_Edge_Lab/data.js'), 'prive/data.js')

    def test_groupes_proteges(self):
        self.assertTrue({'lab_sorties', 'lab_donnees'} <= C.PROTEGES)

    def test_developper_coffre_et_local(self):
        with tempfile.TemporaryDirectory() as d:
            ici = os.getcwd()
            os.chdir(d)
            try:
                os.makedirs('Tennis_Edge_Lab/live/registre')
                open('Tennis_Edge_Lab/live/registre/registre_2026-11.json.gz', 'wb').write(b'x')
                r2 = FauxR2({'prive/registre/index.json': b'{}', 'prive/registre/registre_2026-10.json.gz': b'y'})
                L = C.developper(['a.json', 'Tennis_Edge_Lab/live/registre/*'], r2)
                self.assertEqual(L, ['a.json'] + ['Tennis_Edge_Lab/live/registre/' + n for n in
                                 ('index.json', 'registre_2026-10.json.gz', 'registre_2026-11.json.gz')])
                C.pull_protege(L[1:], r2, base='.b')
                self.assertEqual(open('Tennis_Edge_Lab/live/registre/index.json', 'rb').read(), b'{}')
                self.assertTrue(os.path.exists('.b/registre__index.json'))
            finally:
                os.chdir(ici)

    def test_fichier_non_rapatrie_jamais_envoye(self):
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, 'data.js')
            open(f, 'wb').write(b'nouveau')
            r2 = FauxR2({C.cle(f): b'ancien'})
            C.push_protege([f], r2, base=os.path.join(d, '.b'))
            self.assertEqual(r2.o[C.cle(f)], b'ancien')

    def test_gitignore(self):
        for f in C.developper(C.GROUPES['lab_sorties'] + C.GROUPES['lab_donnees']) + [
                'Tennis_Edge_Lab/live/registre/registre_2027-01.json.gz', 'Tennis_Edge_Lab/data.json']:
            r = subprocess.run(['git', 'check-ignore', '--no-index', '-q', f], cwd=RACINE)
            self.assertEqual(r.returncode, 0, f)


class Workflows(unittest.TestCase):
    def test_lab_quotidien(self):
        w = lire('lab_quotidien.yml')
        tirer = w.index('pull --groupe lab_sorties')
        self.assertLess(tirer, w.index('source_features.py'))
        self.assertIn('push --groupe lab_sorties', w)
        self.assertIn('retirer --groupe lab_sorties', w)
        self.assertIn('retirer --groupe lab_donnees --si-present', w)
        publier = w[w.index('Publier si un contenu'):]
        for f in C.GROUPES['lab_sorties']:
            if not f.endswith('/*'):
                self.assertNotIn(f, publier.split('python scripts/coffre.py push --groupe lab_sorties')[1], f)
        self.assertNotIn('live/registre/*', publier)
        self.assertNotIn('push --force', w)
        self.assertNotIn('push -f', w)

    def test_pages(self):
        w = lire('pages.yml')
        self.assertIn('pull --groupe lab_sorties', w)
        self.assertLess(w.index('pull --groupe lab_donnees'), w.index('build_from_repo.py .'))
        self.assertLess(w.index('build_from_repo.py .'), w.index('push --groupe lab_donnees'))
        self.assertNotIn('git add', w)

    def test_lab_gel(self):
        w = lire('lab_gel.yml')
        self.assertLess(w.index('pull --groupe lab_sorties'), w.index('freeze'))
        self.assertLess(w.index('rendre --groupe lab_sorties'), w.index('git status --porcelain'))

    def test_aucun_autre_workflow_n_ajoute_ces_fichiers(self):
        for nom in os.listdir(WF):
            w = lire(nom)
            for l in w.splitlines():
                if 'git add' in l and not l.strip().startswith('#'):
                    for f in C.GROUPES['lab_sorties'] + C.GROUPES['lab_donnees']:
                        self.assertNotIn(f.rstrip('*'), l, f'{nom} : {l.strip()}')


if __name__ == '__main__':
    unittest.main()
