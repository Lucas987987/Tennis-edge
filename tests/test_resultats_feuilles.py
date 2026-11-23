"""Résultats manquants complétés depuis les feuilles de match (paquet 305, 20/11/2026)."""
import datetime as dt
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'scripts'))
import resultats_feuilles as R  # noqa: E402

T0 = dt.datetime(2026, 11, 1, 18, 30, tzinfo=dt.timezone.utc).timestamp()
MAINTENANT = T0 + 5 * 86400


def feuille(h, a, sh, sa, v, texte='Ended', debut=T0, tb=None, tb_a=None):
    return {'id': 1, 'jour': '2026-11-01', 'debut': debut, 'home': {'nom': h}, 'away': {'nom': a},
            'score_home': {'sets': sh, 'tb': (tb or [None] * len(sh))}, 'score_away': {'sets': sa, 'tb': (tb_a or [None] * len(sa))},
            'vainqueur': v, 'statut': {'texte': texte, 'type': 'finished' if texte in ('Ended', 'Retired') else 'canceled'}}


class Completer(unittest.TestCase):
    def preparer(self, positions, feuilles, sr=None):
        d = Path(tempfile.mkdtemp())
        (d / 'feuilles').mkdir()
        with gzip.open(d / 'feuilles' / '2026-11-01.jsonl.gz', 'wt', encoding='utf-8') as f:
            for x in feuilles:
                f.write(json.dumps(x) + '\n')
        (d / 'set_results.json').write_text(json.dumps(sr or {}), encoding='utf-8')
        (d / 'paper_trades_match.jsonl').write_text(''.join(json.dumps(p) + '\n' for p in positions), encoding='utf-8')
        return d

    def test_sens_de_l_uid(self):
        uid = '2026-11-01_mitchell_krueger_marcel_latak'
        pos = [{'uid': uid, 'status': 'OPEN', 'commence': T0, 'home': 'Mitchell Krueger', 'away': 'Marcel Latak'}]
        # feuille dans l'autre sens : Latak à domicile, Krueger gagne 6-1 6-0
        d = self.preparer(pos, [feuille('Marcel Latak', 'Mitchell Krueger', [1, 0], [6, 6], 2)])
        aj = R.completer(str(d), MAINTENANT)
        self.assertEqual(aj[uid], {'match': 'home', 'set1': 'home', 'set2': 'home'})
        self.assertEqual(json.loads((d / 'set_results.json').read_text())[uid]['match'], 'home')
        self.assertIn(uid, json.loads((d / 'set_results_feuilles.json').read_text()))

    def test_sets_et_tie_break(self):
        uid = '2026-11-01_ana_bo_cia_do'
        pos = [{'uid': uid, 'status': 'ABANDONNED', 'commence': T0}]
        d = self.preparer(pos, [feuille('Ana Bo', 'Cia Do', [6, 3, 6], [6, 6, 2], 1, tb=[7, None, None], tb_a=[5, None, None])])
        self.assertEqual(R.completer(str(d), MAINTENANT)[uid], {'match': 'home', 'set1': 'home', 'set2': 'away'})

    def test_abandon_non_rempli_et_rien_par_dessus(self):
        u1, u2 = '2026-11-01_ana_bo_cia_do', '2026-11-01_eve_fa_gil_ha'
        pos = [{'uid': u1, 'status': 'OPEN', 'commence': T0}, {'uid': u2, 'status': 'OPEN', 'commence': T0}]
        d = self.preparer(pos, [feuille('Ana Bo', 'Cia Do', [6, 2], [3, 0], 1, texte='Retired'),
                                feuille('Eve Fa', 'Gil Ha', [6, 6], [1, 1], 1)],
                          sr={u2: {'match': 'away', 'set1': 'away', 'set2': 'away'}})
        self.assertEqual(R.completer(str(d), MAINTENANT), {})
        self.assertEqual(json.loads((d / 'set_results.json').read_text())[u2]['match'], 'away')

    def test_autre_rencontre_ignoree(self):
        uid = '2026-10-25_ana_bo_cia_do'                                    # uid d'une rencontre plus ancienne
        pos = [{'uid': uid, 'statut': 'OUVERT', 'commence': '2026-11-01T18:30:00'}]
        d = self.preparer(pos, [feuille('Ana Bo', 'Cia Do', [6, 6], [1, 1], 1)])
        self.assertEqual(R.completer(str(d), MAINTENANT), {})

    def test_trop_tot_ou_trop_loin(self):
        uid = '2026-11-01_ana_bo_cia_do'
        pos = [{'uid': uid, 'status': 'OPEN', 'commence': T0}]
        d = self.preparer(pos, [feuille('Ana Bo', 'Cia Do', [6, 6], [1, 1], 1, debut=T0 + 30 * 3600)])
        self.assertEqual(R.completer(str(d), MAINTENANT), {})
        d2 = self.preparer(pos, [feuille('Ana Bo', 'Cia Do', [6, 6], [1, 1], 1)])
        self.assertEqual(R.completer(str(d2), T0 + 3600), {})

    def test_pipeline(self):
        yml = (RACINE / '.github' / 'workflows' / 'steam_pipeline.yml').read_text(encoding='utf-8')
        i, j = yml.index('python scripts/fetch_set_results.py'), yml.index('python scripts/resultats_feuilles.py')
        self.assertLess(i, j)
        self.assertLess(j, yml.index('scripts/paper_journal.py'))      # 393 : lancé par scripts/discret.py
        self.assertIn('set_results.json set_results_feuilles.json', yml)


if __name__ == '__main__':
    unittest.main()
