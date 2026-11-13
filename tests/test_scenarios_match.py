"""Scénarios du match (11/11/2026, paquet 221) : 6 issues regroupées, après le 1er set, historique contre circuit."""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'simulateur'))
import infos_avant_match as I  # noqa: E402
import vitrine as V  # noqa: E402


def _r(score, v, p):
    return {'score': score, 'vainqueur': v, 'probabilite': p}


class Scenarios(unittest.TestCase):
    D = [_r([[6, 2], [6, 3]], 0, 0.2), _r([[7, 5], [6, 1]], 0, 0.2), _r([[3, 6], [6, 4], [6, 4]], 0, 0.1),
         _r([[6, 4], [3, 6], [7, 6]], 0, 0.1), _r([[2, 6], [3, 6]], 1, 0.25), _r([[6, 3], [4, 6], [4, 6]], 1, 0.15)]

    def test_six_issues_somme_un(self):
        s = V.scenarios(self.D)
        h, a = s['j']
        # paquet 267 : 6-3 et 7-5 = « accrochés » (un seul break a pu suffire) ; « sans trembler » = 6-2 ou mieux
        self.assertAlmostEqual(h['net'], 0.0)
        self.assertAlmostEqual(h['accroche'], 0.4)
        self.assertAlmostEqual(h['long'], 0.2)
        self.assertAlmostEqual(h['remontee'], 0.1)
        self.assertAlmostEqual(a['net'], 0.0)
        self.assertAlmostEqual(a['accroche'], 0.25)
        self.assertAlmostEqual(a['long'], 0.15)
        self.assertAlmostEqual(sum(o[k] for o in s['j'] for k in ('net', 'accroche', 'long')), 1.0)
        self.assertAlmostEqual(s['tiebreak'], 0.1)
        self.assertAlmostEqual(s['set_sec'], 0.2)

    def test_apres_premier_set(self):
        h, a = V.scenarios(self.D)['j']
        # home gagne le 1er set : 0,2 + 0,2 + 0,1 (gagnés) + 0,15 (perdu ensuite) → 0,5 / 0,65
        self.assertAlmostEqual(h['si_set1_gagne'], round(0.5 / 0.65, 4))
        # home perd le 1er set : 0,1 (remontée) sur 0,1 + 0,25
        self.assertAlmostEqual(h['si_set1_perdu'], round(0.1 / 0.35, 4))
        self.assertAlmostEqual(a['si_set1_gagne'], round(0.25 / 0.35, 4))

    def test_historique_et_moyenne_du_circuit(self):
        j = dt.date(2026, 11, 11)
        L = [(j - dt.timedelta(days=10), 1, 0.6, 2, 0, 'x', False, (1, 1), 'ATP'),
             (j - dt.timedelta(days=20), 0, 0.5, 1, 2, 'y', False, (1, 0, 0), 'ATP'),
             (j - dt.timedelta(days=30), 1, 0.5, 2, 1, 'z', False, (0, 1, 1), 'ATP'),
             (j - dt.timedelta(days=40), 0, 0.5, 0, 1, 'w', True, (0,), 'ATP'),          # abandon : exclu
             (j - dt.timedelta(days=900), 1, 0.5, 2, 0, 'v', False, (1, 1), 'ATP')]      # trop ancien
        self.assertEqual(I.apres_set1(L, j), {'gagne': [1, 2], 'perdu': [1, 1]})



class Controle(unittest.TestCase):
    def test_reconstituer_respecte_les_sets(self):
        import scenarios_match as SM
        d = {'sets': {'2-0': 0.4, '2-1': 0.2, '1-2': 0.15, '0-2': 0.25},
             'scores': [['6-2 6-1', 0.1], ['7-5 6-4', 0.1], ['4-6 6-3 6-4', 0.05], ['6-4 3-6 6-2', 0.05],
                        ['6-3 4-6 4-6', 0.04], ['3-6 6-4 4-6', 0.04], ['2-6 3-6', 0.08], ['6-7 5-7', 0.08]]}
        r = SM.reconstituer(d)
        h, a = r['j']
        self.assertAlmostEqual(h['net'] + h['accroche'], 0.4)
        self.assertAlmostEqual(h['net'], 0.2)
        self.assertAlmostEqual(h['long'], 0.2)
        self.assertAlmostEqual(h['remontee'], 0.1)
        self.assertAlmostEqual(a['net'], 0.0)                                      # 2-6 3-6 : le 3-6 a pu ne compter qu'un break
        self.assertAlmostEqual(a['accroche'], 0.25)
        self.assertAlmostEqual(a['long'], 0.15)

    def test_verdict(self):
        import scenarios_match as SM
        self.assertEqual(SM._verdict([0.5] * 10, [1.0] * 10)['verdict'], 'trop tot')
        self.assertEqual(SM._verdict([0.5] * 100, [1.0] * 50 + [0.0] * 50)['verdict'], 'juste')
        self.assertEqual(SM._verdict([0.2] * 100, [1.0] * 50 + [0.0] * 50)['verdict'], 'trop bas')


class Definition267(unittest.TestCase):
    """13/11/2026 (paquet 267) : un set à 6-3 peut ne compter qu'un break (vainqueur au service en premier), comme 6-4."""

    def test_six_trois_est_accroche(self):
        import scenarios_match as SM
        self.assertEqual(SM.issue([(6, 3), (6, 1)], 0), ('accroche', False))
        self.assertEqual(SM.issue([(6, 2), (6, 0)], 0), ('net', False))
        self.assertEqual(SM.issue([(1, 6), (2, 6)], 1), ('net', False))
        self.assertEqual(SM.issue([(3, 6), (4, 6)], 1), ('accroche', False))
        self.assertEqual(SM.issue([(6, 4), (7, 6)], 0), ('accroche', False))

    def test_un_break_suffit_pour_six_trois(self):
        # vainqueur au service en premier : 5 jeux de service gardés + 1 break sur 4 jeux adverses = 6-3, un seul break
        sert = [0, 1] * 5
        jeux = [0 if s == 0 else (0 if k == 1 else 1) for k, s in enumerate(sert[:9])]
        self.assertEqual((jeux.count(0), jeux.count(1)), (6, 3))
        self.assertEqual(sum(1 for s, g in zip(sert, jeux) if s != g), 1)

    def test_figes_ancienne_definition_reconstitues(self):
        import scenarios_match as SM
        s = SM.scenarios([_r([[6, 3], [6, 3]], 0, 1.0)])
        self.assertEqual(s['definition'], SM.DEFINITION)
        self.assertAlmostEqual(s['j'][0]['accroche'], 1.0)
        src = Path(SM.__file__).read_text(encoding='utf-8')
        self.assertIn("prev.get('definition') != DEFINITION", src)

    def test_textes_de_la_page(self):
        html = (Path(__file__).resolve().parents[1] / 'algo' / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('6-3 ou mieux', html)
        self.assertIn('au moins un set à 6-3, 6-4, 7-5 ou 7-6', html)
        self.assertIn('every set 6-2 or better', html)



class Rapport267(unittest.TestCase):
    def test_rapport_public_sans_nom_ni_cote(self):
        import importlib.util
        racine = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location('r267', racine / 'scripts' / 'rapport_sets_accroches.py')
        R = importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
        import tempfile, json as js
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'Tennis_Edge_Lab', 'live').mkdir(parents=True)
            Path(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json').write_text(js.dumps({'matchs': [
                {'uid': 'a', 'circuit': 'ATP', 'home': 'X Y', 'away': 'Z W', 'reel': {'gagnant': 'home', 'score': '6-3 6-1'}},
                {'uid': 'b', 'circuit': 'ATP', 'home': 'X Y', 'away': 'Z W', 'reel': {'gagnant': 'away', 'score': '2-6 1-6'}}]}))
            r = R.rapport(d)
        o = r['par_circuit']['ATP']
        self.assertEqual(o['victoires_2_sets'], 2)
        self.assertEqual((o['pct_sans_trembler_ancienne'], o['pct_sans_trembler_nouvelle']), (100.0, 50.0))
        texte = js.dumps(r, ensure_ascii=False)
        for interdit in ('X Y', 'Z W', 'cote', 'pinnacle', 'march'):
            self.assertNotIn(interdit, texte.lower() if interdit.islower() else texte)


if __name__ == '__main__':
    unittest.main()
