"""Public du stade (paquet 300 ; vrais sons enregistrés au paquet 302, 19/11/2026, Lucas : « le bruit du public, ce n'est pas du tout clair »). L'ancien
public était du bruit filtré ; il est maintenant fait de voix synthétiques (hauteur, voyelles, syllabes) et
d'applaudissements au rythme de chaque spectateur. Toujours rien d'enregistré."""
import json
import sys
import time
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
try:
    import numpy as np
    import scipy  # noqa: F401
    SCIPY = True
except ImportError:
    SCIPY = False


@unittest.skipUnless(SCIPY, 'scipy absent')
class PublicStade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(RACINE / 'scripts'))
        import sons_stade
        cls.S = sons_stade

    def test_des_voix_et_pas_du_souffle(self):
        S = self.S
        r = S._rng(3)
        x = S._bouche(S._source(int(0.4 * S.TAUX), 120.0, r), S.VOYELLES['a'])
        x = x - x.mean()
        ac = np.correlate(x[:8000], x[:8000], 'full')[7999:]
        periode = int(S.TAUX / 120)
        self.assertGreater(ac[periode - 5:periode + 5].max() / ac[0], 0.5)       # une hauteur nette (voix), pas un bruit

    def test_applaudissements_rythmes(self):
        S = self.S
        x = S._applaudir_synth(2.0, 40, 0.5, S._rng(1))                                  # 10 spectateurs
        self.assertEqual(x.shape, (2 * S.TAUX, 2))
        self.assertTrue(np.isfinite(x).all())
        self.assertLessEqual(np.abs(x).max(), 0.5 + 1e-9)
        env = np.abs(x[:, 0]).reshape(-1, 480).max(axis=1)                         # 10 ms par case
        self.assertGreater((env > 0.05 * env.max()).mean(), 0.2)

    def test_brouhaha_et_ovation(self):
        S = self.S
        t = time.time()
        b = S._brouhaha_synth(20, S._rng(5))
        self.assertLess(time.time() - t, 30)                                      # 75 s de vidéo : quelques secondes
        self.assertEqual(b.shape, (20 * S.TAUX, 2))
        self.assertLess(np.corrcoef(b[S.TAUX:-S.TAUX, 0], b[S.TAUX:-S.TAUX, 1])[0, 1], 0.5)   # vraie stéréo
        o = S._ovation_synth(3.8, S._rng(9))
        self.assertTrue(np.isfinite(o).all())
        self.assertGreater(len(o), 3.5 * S.TAUX)
        h = S.houle(S._rng(8))
        self.assertEqual(h.shape[1], 2)

    def test_frappe_breve_et_creuse(self):                                       # paquet 301
        S = self.S
        for fort in (1.0, 1.25):
            x = S._pock_synth(fort, S._rng(1))
            w = int(0.002 * S.TAUX)
            e = np.sqrt((x[:len(x) // w * w].reshape(-1, w) ** 2).mean(axis=1))
            db = 20 * np.log10(e / e.max() + 1e-12)
            self.assertLess(db[10:].max(), -20)                                    # −20 dB passé 20 ms : un « pock », pas un « bip »
            f = np.fft.rfftfreq(len(x), 1 / S.TAUX)
            sp = np.abs(np.fft.rfft(x))
            self.assertGreater(sp[(f > 900) & (f < 3500)].sum(), sp[f < 400].sum())   # creux et clair, pas un « boum »
        self.assertLessEqual(np.abs(S._rebond_synth(S._rng(2))).max(), 0.26 + 1e-9)

    def test_synthese_sans_enregistrement(self):
        src = (RACINE / 'scripts' / 'sons_stade.py').read_text(encoding='utf-8')
        self.assertIn('paquet 300', src)
        self.assertIn("os.path.join(DOSSIER_SONS, nom + '.wav')", src)               # seuls les vrais sons du dossier sons/

    # ── paquet 302 : vrais sons enregistrés (CC0) ───────────────────────────────────────────────────────────
    def test_banque_chargee(self):
        B = self.S.banque()
        for k, n in (('frappes', 20), ('services', 15), ('rebonds', 15)):
            self.assertGreaterEqual(len(B.get(k, [])), n, k)
        for k in ('public_murmure', 'public_applaudissements', 'public_ovation', 'public_ovation2'):
            self.assertEqual(B[k].shape[1], 2, k)

    def test_niveaux_comme_avant(self):
        S, r = self.S, self.S._rng(4)
        self.assertAlmostEqual(float(np.abs(S.pock(1.0, r)).max()), 0.9, places=6)
        self.assertAlmostEqual(float(np.abs(S.pock(1.25, r)).max()), 1.125, places=6)
        self.assertAlmostEqual(float(np.abs(S.rebond(r)).max()), 0.26, places=6)
        b = S.brouhaha(30, r)
        self.assertAlmostEqual(float(np.sqrt((b ** 2).mean())), 0.06 * 0.42, delta=0.004)
        self.assertEqual(S.applaudir(2.6, 1000, 0.42, r).shape, (int(2.6 * S.TAUX), 2))
        self.assertTrue(np.isfinite(S.ovation(4.5, r)).all())

    def test_repli_sans_fichiers(self):
        S = self.S
        garde, dossier = S._BANQUE, S.DOSSIER_SONS
        try:
            S._BANQUE, S.DOSSIER_SONS = None, '/dossier/absent'
            self.assertEqual(S.banque(), {})
            self.assertEqual(S.pock(1.0, S._rng(1)).ndim, 1)
            self.assertEqual(S.brouhaha(5, S._rng(1)).shape, (5 * S.TAUX, 2))
        finally:
            S._BANQUE, S.DOSSIER_SONS = garde, dossier

    def test_licences(self):
        src = (RACINE / 'sons' / 'SOURCES.md').read_text(encoding='utf-8')
        self.assertIn('Creative Commons 0', src)
        for num in ('662256', '662258', '662264', '141250', '17737'):
            self.assertIn(num, src)
        meta = json.loads((RACINE / 'sons' / 'banque.json').read_text(encoding='utf-8'))
        for nom in meta:
            self.assertTrue((RACINE / 'sons' / (nom + '.wav')).exists(), nom)
        taille = sum(f.stat().st_size for f in (RACINE / 'sons').glob('*.wav'))
        self.assertLess(taille, 15_000_000)

    def test_video_recupere_les_sons(self):
        yml = (RACINE / '.github' / 'workflows' / 'video_simulation.yml').read_text(encoding='utf-8')
        self.assertIn('            /sons/\n', yml)


if __name__ == '__main__':
    unittest.main()
