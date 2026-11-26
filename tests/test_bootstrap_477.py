"""26/11/2026 (paquet 477) : IC bootstrap de validation_report plus rapide (rng.choices), toujours reproductible, et
limite du workflow portée à 150 min."""
import os
import random
import sys
import unittest

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(R, 'scripts'))


class Bootstrap(unittest.TestCase):
    def test_reproductible_et_coherent(self):
        import validation_report as V
        rnd = random.Random(7)
        xs = [rnd.choice([-1.0, 1.9]) for _ in range(500)]
        a, b = V.mean_ci(xs), V.mean_ci(xs)
        self.assertEqual(a, b)                                   # graine fixe : même IC à chaque lecture
        m, lo, hi, s = a
        self.assertLess(lo, m)
        self.assertLess(m, hi)
        half = 1.96 * s / len(xs) ** 0.5                         # proche de l'approximation normale à n = 500
        self.assertAlmostEqual(hi - lo, 2 * half, delta=0.25 * half)

    def test_limite_workflow(self):
        y = open(os.path.join(R, '.github', 'workflows', 'steam_pipeline.yml'), encoding='utf-8').read()
        self.assertIn('timeout-minutes: 150', y)


if __name__ == '__main__':
    unittest.main()
