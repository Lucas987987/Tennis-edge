"""Rattrapage des marchés dérivés (21/10/2026) : 1 requête par match manquant,
plus récent d'abord, jamais deux fois, garde-fous de quota et d'historique."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
sys.path.insert(0, ICI)
import oddspapi_v5 as ov  # noqa: E402
import rattrapage_derives as R  # noqa: E402
import test_marches_derives as TD  # noqa: E402


class Rattrapage(unittest.TestCase):
    def setUp(self):
        self.cwd = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)
        self.now = dt.datetime.utcnow().replace(microsecond=0)
        closing, self.book = {}, []
        for i in range(120):                       # 120 matchs passés, Pinnacle connu
            d = self.now - dt.timedelta(hours=6 + 10 * i)
            closing[f"m{i}"] = {'fixture_id': f"f{i}", 'commence_time': d.isoformat() + 'Z',
                                'home': f"Alpha {i}", 'away': f"Beta {i}", 'tournament': 'ATP Test'}
            self.book.append(json.dumps({'uid': f"{d.date()}_alpha_{i}_beta_{i}", 'book': 'pinnacle'}))
        json.dump(closing, open('closing_lines.json', 'w'))
        json.dump({k: {'marketName': v['marketName'], 'handicap': v['handicap'], 'outcomes': v['outcomes']}
                   for k, v in TD.TABLE.items()}, open('marches_oddspapi.json', 'w'))
        self.appels = []
        self.sauve = (ov.KEY, ov.historical, ov.iter_hist_lines, ov.api_get, R.F.COOLDOWN, dict(ov.QUOTA), ov.QUOTA_HIT)
        self.max = R.MAX
        ov.KEY = 'x'
        R.F.COOLDOWN = 0
        ov.QUOTA.clear()
        ov.QUOTA_HIT = False

        def hist(fid, book='pinnacle'):
            self.appels.append(fid)
            ov.QUOTA.update({'remaining': 45000, 'limit': 50000, 'reset_s': 25 * 86400})
            return TD.DATA if int(fid[1:]) % 10 else {'odds': {'pinnacle': {}}}   # 1 sur 10 : plus servi
        ov.historical = hist
        ov.api_get = lambda *a, **k: (_ for _ in ()).throw(AssertionError('table déjà là : aucune requête /markets'))
        ov.iter_hist_lines = lambda m='book': iter(self.book if m == 'book' else
                                                   (open(p).read().splitlines() if os.path.exists(p := 'parts/x') else []))

    def tearDown(self):
        ov.KEY, ov.historical, ov.iter_hist_lines, ov.api_get, R.F.COOLDOWN, q, ov.QUOTA_HIT = self.sauve
        ov.QUOTA.clear(); ov.QUOTA.update(q)
        R.MAX = self.max
        os.chdir(self.cwd)
        self.tmp.cleanup()

    def lignes(self):
        import glob
        return [json.loads(l) for f in glob.glob('parts/hist_derives_*') for l in open(f)]

    def test_un_appel_par_match_recent_d_abord(self):
        R.MAX = 50
        R.main()
        self.assertEqual(len(self.appels), 50)
        self.assertEqual(self.appels[:3], ['f0', 'f1', 'f2'])        # du plus récent au plus ancien
        L = self.lignes()
        self.assertEqual(len(L), 45)                                  # 5 « plus servis » notés à part
        self.assertIn('total_sets 2.5', L[0]['marches'])
        self.assertEqual(len(json.load(open('derives_absences.json'))), 5)
        rap = json.load(open('derives_rattrapage.json'))
        self.assertEqual((rap['demandes'], rap['gardes'], rap['sans_marche'], rap['arret']), (50, 45, 5, 'plafond du run (50)'))

    def test_jamais_deux_fois(self):
        R.MAX = 50
        R.main()
        deja = list(self.appels)
        import glob
        derives = [l for f in glob.glob('parts/hist_derives_*') for l in open(f).read().splitlines()]
        ov.iter_hist_lines = lambda m='book': iter(self.book if m == 'book' else derives)
        self.appels.clear()
        R.main()
        self.assertFalse(set(self.appels) & set(deja))

    def test_quota_protege(self):
        R.MAX = 1000
        ov.historical = lambda fid, book='pinnacle': (self.appels.append(fid), ov.QUOTA.update(
            {'remaining': 28000, 'limit': 50000, 'reset_s': 25 * 86400}))[0] or TD.DATA
        R.main()
        self.assertEqual(len(self.appels), 1)                         # 28 000 < 25 j × 1 100 + 2 000 = 29 500 : on s'arrête
        self.assertIn('quota', json.load(open('derives_rattrapage.json'))['arret'])

    def test_historique_vide_rien_demande(self):
        self.book = self.book[:10]
        self.assertEqual(R.main(), 1)
        self.assertEqual(self.appels, [])


if __name__ == '__main__':
    unittest.main()
