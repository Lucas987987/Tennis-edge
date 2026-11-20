"""Canal « 🎯 MISER » (21/10/2026) : une ligne par message envoyé, bilan sur la
première alerte de chaque match, ligne de suivi dans le message."""
import datetime as dt
import importlib.util
import json
import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import steam_alert as sa  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    try:
        spec.loader.exec_module(m)
    finally:
        sys.path.remove(str(path.parent))
    return m


sd = _load('tennis_edge_t_sd_miser', ROOT / 'scripts' / 'suivi_direct.py')

T0 = dt.datetime(2026, 10, 22, 8, 0, tzinfo=dt.timezone.utc).timestamp()
BK = {'_home': 'Terence Atmane', '_away': 'Mattia Bellucci', '_tour': 'ATP Almaty', '_commence': T0 + 15 * 3600}
BEST = {'side': 'home', 'sb': '1xbet', 'odds': 2.27, 'fair': 2.13, 'ev': 0.065, 'thr': 0.05}


class FauxAjouts:
    """Résultat connu pour u1 (gagné), u2 sans résultat ; clôture connue pour les deux."""
    def pour(self, r):
        won = {'u1': True}.get(r['uid'])
        pnl = None if won is None else (r['cote'] - 1 if won else -1.0)
        return {'gagne': None if won is None else int(won), 'pnl': pnl, 'pin_close': 2.0, 'pin_close_adv': 1.9,
                'clv_pin': {'u1': 6.0, 'u2': 2.0}[r['uid']], 'source_resultat': 'test', 'denoue': won is not None}


class Miser(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        self._dry = sa.DRY_RUN
        sa.DRY_RUN = False                 # module seulement : rien dans os.environ

    def tearDown(self):
        sa.DRY_RUN = self._dry
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def test_journal_une_ligne_par_message(self):
        sa.journaliser(BK, 'u1', BEST, 2.42, 2.06, 15 * 3600 + 780, 0, T0)
        sa.journaliser(BK, 'u1', dict(BEST, thr=0.08, odds=2.2), 2.42, 1.98, 14 * 3600, 0.05, T0 + 3600)
        L = [json.loads(x) for x in open(sa.MISER_LOG, encoding='utf-8')]
        self.assertEqual(len(L), 2)
        r = L[0]
        self.assertEqual((r['joueur'], r['adversaire'], r['book'], r['cote'], r['palier'], r['relance']),
                         ('Terence Atmane', 'Mattia Bellucci', '1xbet', 2.27, 5, False))
        self.assertEqual(r['commence'], '2026-10-22T23:00:00+00:00')
        self.assertEqual(r['ev_pct'], 6.5)
        self.assertTrue(L[1]['relance'])

    def test_dry_run_sans_journal(self):
        sa.DRY_RUN = True
        sa.journaliser(BK, 'u1', BEST, 2.42, 2.06, 3600, 0, T0)
        self.assertFalse(os.path.exists(sa.MISER_LOG))

    def test_bilan_premiere_alerte_par_match(self):
        sa.journaliser(BK, 'u1', BEST, 2.42, 2.06, 3600, 0, T0)
        sa.journaliser(BK, 'u1', dict(BEST, thr=0.08, odds=2.0), 2.42, 1.98, 3000, 0.05, T0 + 600)   # relance
        sa.journaliser(dict(BK, _home='A', _away='B'), 'u2', BEST, 2.42, 2.06, 3600, 0, T0 + 60)
        # ligne dupliquée par la fusion « union » : ignorée
        with open(sa.MISER_LOG, encoding='utf-8') as f:
            first = f.readline()
        with open(sa.MISER_LOG, 'a', encoding='utf-8') as f:
            f.write(first)
        doc = sd.canal_miser('.', FauxAjouts(), maintenant=dt.datetime(2026, 10, 24, tzinfo=dt.timezone.utc))
        m = doc['canaux']['MISER']
        self.assertEqual((m['n_alertes'], m['n_matchs'], m['n_relances'], m['n_denoues']), (3, 2, 1, 1))
        b = m['bilan']
        self.assertEqual(b['n'], 1)
        self.assertEqual(b['pnl'], 1.3)            # premier prix 2,27, pas celui de la relance
        self.assertEqual(b['clv_mediane'], 4.0)    # CLV sur toutes les alertes à clôture connue
        self.assertEqual(sorted(m['paris']), ['u1', 'u2'])

    def test_ligne_de_suivi(self):
        json.dump({'canaux': {'MISER': {'n_matchs': 2, 'bilan': {'n': 0}}}}, open(sa.SUIVI_CANAUX, 'w'))
        self.assertIn("aucun pari dénoué pour l'instant (2 alerte(s)", sa.suivi_line())
        json.dump({'canaux': {'MISER': {'n_matchs': 12, 'bilan': {
            'n': 10, 'gains': 6, 'taux': 60.0, 'seuil': 45.0, 'roi': 12.3, 'pnl': 1.2, 'clv_mediane': 5.5}}}},
            open(sa.SUIVI_CANAUX, 'w'))
        t = sa.suivi_line()
        self.assertIn('10 paris dénoués', t)
        self.assertIn('ROI +12.3 %', t)
        self.assertIn('CLV Pinnacle méd +5.5 %', t)
        self.assertIn('Avant ce suivi', t)
        os.remove(sa.SUIVI_CANAUX)
        self.assertIn('aucun pari dénoué', sa.suivi_line())   # fichier absent : pas d'erreur


if __name__ == '__main__':
    unittest.main()
