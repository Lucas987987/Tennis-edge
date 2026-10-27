"""Tranches d'échange, orientation service-retour et moyennes de jeux."""
import csv
import datetime as dt
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import charting_echanges as CE
import evolution_statistiques as EV


def match():
    return {
        'date': dt.date(2024, 1, 1), 'fin': dt.date(2024, 1, 3), 'circuit': 'ATP', 'surface': 'Hard',
        'bo': 3, 'gagnant': 'atp:1', 'perdant': 'atp:2', 'nom_g': 'Player A', 'nom_p': 'Player B',
        'sets': [(7, 6), (6, 4)], 'complet': True, 'abandon': False,
        'detail': {'w': (100, 60, 42, 18, 10, 2, 4, 2, 10),
                   'l': (100, 60, 42, 18, 10, 2, 6, 3, 10)},
        'tour': 1, 'num': 0, 'niveau': 'M', 'tournoi': 'Test',
    }


def ecrire_mcp(dossier):
    champs = ['match_id', 'Date', 'Player 1', 'Player 2', 'Surface', 'Tournament']
    with open(os.path.join(dossier, 'charting-m-matches.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=champs, extrasaction='ignore')
        w.writeheader()
        w.writerow({'match_id': 'm1', 'Date': '20240101', 'Player 1': 'Player A',
                    'Player 2': 'Player B', 'Surface': 'Hard', 'Tournament': 'Test'})
    colonnes = ['match_id', 'server', 'returner', 'row', 'pts', 'pl1_won', 'pl2_won']
    with open(os.path.join(dossier, 'charting-m-stats-Rally.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=colonnes, extrasaction='ignore')
        w.writeheader()
        for row, pts, p1, p2 in [('1-3', 100, 60, 40), ('1-3-1', 60, 40, 20), ('1-3-2', 40, 20, 20)]:
            w.writerow({'match_id': 'm1', 'server': 'Player A', 'returner': 'Player B',
                        'row': row, 'pts': pts, 'pl1_won': p1, 'pl2_won': p2})


class EchangesTests(unittest.TestCase):
    def test_frequence_reussite_et_orientation(self):
        with tempfile.TemporaryDirectory() as d:
            ecrire_mcp(d)
            data = CE.charger(d)
        a = [x for x in data['aplayer'] if x[3] == 'total' and x[4] == '1-3'][0]
        service = [x for x in data['aplayer'] if x[3] == 'service'][0]
        retour = [x for x in data['aplayer'] if x[3] == 'retour'][0]
        self.assertEqual((a[5], a[6]), (100, 60))
        self.assertEqual((service[5], service[6]), (60, 40))
        self.assertEqual((retour[5], retour[6]), (40, 20))
        e = CE.Echanges(data)
        self.assertEqual(e.documentation('aplayer', dt.date(2024, 1, 1)), 0)
        self.assertEqual(e.documentation('aplayer', dt.date(2024, 1, 2)), 100)
        x = e.variables_match('aplayer', 'bplayer', 'ATP', 'Hard', dt.date(2024, 1, 2))
        y = e.variables_match('bplayer', 'aplayer', 'ATP', 'Hard', dt.date(2024, 1, 2))
        for nom in CE.VARIABLES:
            self.assertAlmostEqual(x[nom], -y[nom])
        self.assertGreater(x['echange_reussite_1_3_ecart'], 0)

    def test_comparaison_conserve_points_et_taux(self):
        lignes = [(dt.date(2024, 1, 1), 'Hard', 'ATP', 'total', '1-3', 100, 60),
                  (dt.date(2024, 1, 1), 'Hard', 'ATP', 'service', '1-3', 60, 40),
                  (dt.date(2024, 1, 1), 'Hard', 'ATP', 'retour', '1-3', 40, 20)]
        out = CE.comparaison(lignes, dt.date(2024, 6, 1), 180)
        bloc = out['periode_recente']['scopes']['total']['tranches']['1-3']
        self.assertEqual(bloc['points'], 100)
        self.assertEqual(bloc['points_gagnes'], 60)
        self.assertEqual(bloc['reussite_pct'], 60)
        self.assertEqual(bloc['frequence_pct'], 100)


class JeuxTests(unittest.TestCase):
    def test_moyennes_exactes_total_gagnes_perdus(self):
        m = match()
        out = EV.construire([m], dt.date(2024, 6, 1), joueurs=['Player A'], points_trajectoire=1)
        bloc = out['joueurs']['atp:1']['global']['periode_recente']
        self.assertEqual(bloc['moyennes']['jeux_totaux_par_match']['moyenne'], 23)
        self.assertEqual(bloc['moyennes']['jeux_gagnes_par_match']['moyenne'], 13)
        self.assertEqual(bloc['moyennes']['jeux_perdus_par_match']['moyenne'], 10)

    def test_rapport_joint_echanges_et_archive(self):
        m = match()
        data = {'aplayer': [(dt.date(2024, 1, 1), 'Hard', 'ATP', 'total', '1-3', 100, 60)]}
        out = EV.construire([m], dt.date(2024, 6, 1), joueurs=['Player A'],
                            points_trajectoire=1, donnees_echanges=data)
        bloc = out['joueurs']['atp:1']['echanges']['global']['periode_recente']
        self.assertEqual(bloc['scopes']['total']['tranches']['1-3']['reussite_pct'], 60)


if __name__ == '__main__':
    unittest.main()
