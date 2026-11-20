"""Paquet 284 (18/11/2026) : le déploiement du worker échouait (test « direct : la page redemande les scores toutes
les 3 s » : algo/index.html absent de la copie partielle du dépôt). La page est maintenant dans la copie."""
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
YML = (RACINE / '.github' / 'workflows' / 'deploy_algo.yml').read_text(encoding='utf-8')
TEST = (RACINE / 'workers' / 'algo' / 'test_worker.mjs').read_text(encoding='utf-8')


class DeploiementWorker(unittest.TestCase):
    def test_les_fichiers_lus_par_les_tests_sont_dans_la_copie(self):
        bloc = YML[YML.index('sparse-checkout: |'):YML.index('- uses: actions/setup-node')]
        for f in ('workers/algo', 'scripts/coffre.py', 'algo/index.html'):
            self.assertIn(f, bloc)
        self.assertIn("'../../algo/index.html'", TEST)
        self.assertIn("'../../scripts/coffre.py'", TEST)


if __name__ == '__main__':
    unittest.main()
