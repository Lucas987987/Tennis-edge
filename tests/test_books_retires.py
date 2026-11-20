"""Books retirés et flux « données seules » (22/10/2026) : leovegas, 4casters, sbobet, sharpbet ne
sont plus jamais proposés comme prix — canal public, journal du canal, entrée des hypothèses H13–H18,
H19, early open — et le journal du canal règle ses paris avec set_results.json quand l'index de
résultats ne les trouve pas ; le journal steam règle un pari abandonné dont le résultat est arrivé."""
import datetime as dt
import importlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
sys.path.insert(0, os.path.join(ICI, '..', 'Tennis_Edge_Lab'))
import books  # noqa: E402


class Drapeaux(unittest.TestCase):
    def test_non_jouables(self):
        for b in ('leovegas', '4casters', 'sbobet', 'sharpbet', 'LeoVegas'):
            self.assertFalse(books.flags(b)['jouable'], b)
        for b in ('bet365', 'unibet', 'betfair-ex', 'winamax.fr'):
            self.assertTrue(books.flags(b)['jouable'], b)
        self.assertTrue(books.flags('leovegas')['retire'])

    def test_books_d_entree_des_hypotheses(self):
        import validation_report as vr
        self.assertNotIn('leovegas', vr.H14_SOFTS)
        self.assertFalse([b for b in vr.H14_SOFTS if not books.flags(b)['jouable']])


def serie(t0, cotes):
    return [(t0 + dt.timedelta(minutes=10 * k), c) for k, c in enumerate(cotes)]


class CanalPublic(unittest.TestCase):
    def test_ligne_des_operateurs_sans_books_retires(self):
        with tempfile.TemporaryDirectory() as d:
            os.environ.update(STATE=os.path.join(d, 's.json'), LOG=os.path.join(d, 'log.jsonl'), DRY_RUN='1')
            import canal_public as CP
            CP = importlib.reload(CP)
            now = dt.datetime.utcnow()
            t0 = now - dt.timedelta(hours=2)
            g = {'_home': 'Diego Dedura', '_away': 'Felipe Meligeni Alves', '_tour': 'ATP Challenger Cali',
                 '_lead': 295.0, '_ct': now + dt.timedelta(minutes=295),
                 'pinnacle': {'h': serie(t0, [1.85, 2.15]), 'a': serie(t0, [1.97, 1.81])},
                 'leovegas': {'h': serie(t0, [1.75]), 'a': serie(t0, [2.07])},
                 '4casters': {'h': serie(t0, [1.8]), 'a': serie(t0, [2.02])},
                 'bet365': {'h': serie(t0, [1.8]), 'a': serie(t0, [1.97])}}
            CP.load_games = lambda now_: {'2026-10-22_diego_dedura_felipe_meligeni_alves': g}
            out = io.StringIO()
            with redirect_stdout(out):
                CP.main()
            txt = out.getvalue()
            self.assertIn('bet365 1.97', txt)
            self.assertNotIn('leovegas', txt)
            self.assertNotIn('4casters', txt)
            log = [json.loads(l) for l in open(os.environ['LOG'])]
            self.assertEqual([x[0] for x in log[0]['retards_tous']], ['bet365'])
            self.assertEqual(log[0]['n_books'], 1)
        for k in ('STATE', 'LOG', 'DRY_RUN'):
            os.environ.pop(k, None)


class JournalCanal(unittest.TestCase):
    def test_prix_d_entree_jouable_et_reglement_par_set_results(self):
        with tempfile.TemporaryDirectory() as d:
            log, out, rap, sr = (os.path.join(d, n) for n in ('log.jsonl', 'out.jsonl', 'rap.json', 'sr.json'))
            os.environ.update(LOG=log, OUT=out, RAPPORT=rap, SET_RESULTS=sr)
            import paper_journal_canal as PJ
            PJ = importlib.reload(PJ)
            with open(log, 'w') as f:
                f.write(json.dumps({'t': '2026-10-20T10:00:00', 'uid': '2026-10-20_diego_dedura_felipe_meligeni_alves',
                                    'commence': '2026-10-20T15:00:00', 'joueur': 'Felipe Meligeni Alves', 'palier': 0.05,
                                    'retards_tous': [['4casters', 2.10, 9.0], ['leovegas', 2.07, 8.0], ['bet365', 1.97, 4.0]]}) + '\n')
                f.write(json.dumps({'t': '2026-10-20T11:00:00', 'uid': '2026-10-20_a_b_c_d', 'commence': '2026-10-20T15:00:00',
                                    'joueur': 'C D', 'palier': 0.05, 'retards_tous': [['sbobet', 2.5, 9.0]]}) + '\n')
            json.dump({'2026-10-20_diego_dedura_felipe_meligeni_alves': {'match': 'away', 'set1': 'away', 'set2': 'away'}},
                      open(sr, 'w'))
            with redirect_stdout(io.StringIO()):
                PJ.main()
            T = [json.loads(l) for l in open(out)]
            self.assertEqual(len(T), 1)                                  # l'alerte « sbobet seul » : rien de jouable
            self.assertEqual(T[0]['book'], 'bet365')
            self.assertEqual(T[0]['cote'], 1.97)
            self.assertEqual(T[0]['statut'], 'REGLE')                     # réglé grâce à set_results.json
            self.assertTrue(T[0]['gagne'])
            self.assertAlmostEqual(T[0]['pnl'], 0.97)
            self.assertEqual(PJ.cote_du_joueur_par_uid('2026-10-20_diego_dedura_felipe_meligeni_alves', 'Diego Dedura'), 'home')
        for k in ('LOG', 'OUT', 'RAPPORT', 'SET_RESULTS'):
            os.environ.pop(k, None)


class EarlyOpen(unittest.TestCase):
    def test_filtre(self):
        import early_open_signal as EO
        self.assertFalse(EO._jouable('4casters'))
        self.assertFalse(EO._jouable('leovegas'))
        self.assertTrue(EO._jouable('bet365'))


if __name__ == '__main__':
    unittest.main()
