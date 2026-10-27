import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import ablation as AB
import dependances_points as DP
import evaluation_sorties as ES
import fiabilite as FI
import gouvernance as G
import match_simule as MS
import profils_robustes as PR
import profils_service as PS
import pronostics_du_jour as PDJ
import recherche_externe as RE
import validation_fiabilite as VF


def match_resultat(note=None):
    m = {
        'uid': 'u1', 'debut': '2026-10-20T10:00', 'home': 'A', 'away': 'B',
        'circuit': 'ATP', 'surface': 'Hard', 'reel': {'gagnant': 'home'},
        'premier': {
            'combinaison': {'p_home': .6, 'proba_des_sets_reels': .4, 'sets_justes': True,
                            'score_juste': False, 'rang_du_score_reel': 2, 'ecart_jeux': -2},
            'simulation': {'p_home': .55}, 'stats': {'p_home': .58},
        },
        'diagnostic_version': 'combinaison',
        'diagnostic': {'stats': {'aces': {'home': {'prevu': 5, 'reel': 7, 'dans': True}}}},
    }
    if note is not None:
        m['fiabilite'] = {'note': note}
    return m


class EvaluationSorties(unittest.TestCase):
    def test_toutes_les_sorties_et_rang_un_indexe(self):
        out = ES.evaluer({'matchs': [match_resultat(85)]})
        r = out['global']['combinaison']
        self.assertEqual(r['matchs'], 1)
        self.assertEqual(r['sets']['exact']['valeur'], 1)
        self.assertEqual(r['scores']['rang_reciproque']['valeur'], .5)
        self.assertEqual(r['scores']['dans_top3']['valeur'], 1)
        self.assertEqual(r['jeux']['mae']['valeur'], 2)
        self.assertEqual(r['statistiques']['aces']['mae']['valeur'], 2)
        self.assertEqual(r['statistiques']['aces']['couverture80']['valeur'], 1)
        self.assertEqual(out['global']['simulation']['statistiques'], {})
        self.assertEqual(out['par_fiabilite']['solide']['combinaison']['matchs'], 1)
        self.assertIn('tres_peu_documente', out['par_documentation'])

    def test_donnee_absente_ne_devient_pas_zero(self):
        m = match_resultat()
        m['diagnostic'] = None
        out = ES.evaluer({'matchs': [m]})
        self.assertEqual(out['global']['combinaison']['statistiques'], {})

    def test_filtre_interrompu(self):
        m = match_resultat()
        m['reel']['interrompu'] = 'abandon'
        ok, non = AB.utilisables({'matchs': [m]})
        self.assertEqual((len(ok), len(non)), (0, 1))


class Fiabilite(unittest.TestCase):
    def test_niveaux(self):
        self.assertEqual([FI.niveau(x) for x in (0, 45, 65, 80)], list(FI.NIVEAUX))

    def test_validation_des_notes_figees(self):
        matchs = []
        for i in range(40):
            m = match_resultat(85 if i % 2 else 30)
            m['uid'] = str(i)
            m['debut'] = f'2026-{9+i//16:02d}-{1+i%8:02d}T10:00'
            if i % 2:
                m['reel']['gagnant'] = 'home'
                m['premier']['combinaison']['p_home'] = .8
            else:
                m['reel']['gagnant'] = 'away'
                m['premier']['combinaison']['p_home'] = .8
            matchs.append(m)
        rows = VF.preparer({'matchs': matchs})
        self.assertEqual(len(rows), 40)
        out = VF.evaluer({'matchs': matchs})
        self.assertEqual(out['n_avec_note'], 40)
        self.assertLess(out['par_niveau']['solide']['log_loss'], out['par_niveau']['fragile']['log_loss'])

    def test_journal_conserve_la_note(self):
        with tempfile.TemporaryDirectory() as d:
            os.mkdir(os.path.join(d, 'simulateur'))
            v = {'p_home': .6, 'sets': {'2-0': .6, '2-1': .4}}
            m = {'uid': 'u', 'debut': '2030-01-01T10:00', 'home': 'A', 'away': 'B', 'tournoi': 'T',
                 'circuit': 'ATP', 'surface': 'Hard', 'meilleur_des': 3, 'stats': v,
                 'simulation': v, 'combinaison': v, 'fiabilite': {'note': 72}}
            PDJ.journaliser(d, {'genere_le': '2029-12-31T00:00:00Z', 'matchs': [m]})
            ligne = json.loads(open(os.path.join(d, PDJ.LOG), encoding='utf-8').read())
            self.assertEqual(ligne['fiabilite']['note'], 72)


class Profils(unittest.TestCase):
    def _match(self, jour=None):
        return {'date': jour or dt.date(2025, 1, 1), 'fin': jour or dt.date(2025, 1, 2),
                'gagnant': 'J', 'perdant': 'O', 'nom_g': 'J', 'nom_p': 'O', 'circuit': 'ATP', 'surface': 'Hard',
                'detail': {'w': (20, 12, 12, 7, 5, 1, 2, 1, 2), 'l': (20, 12, 7, 4, 1, 2, 2, 1, 2)}}

    def test_prior_plus_fort_rapproche_de_la_moyenne(self):
        a, b = PS.Profils(prior_mult=1), PS.Profils(prior_mult=10)
        for p in (a, b):
            p.ajouter(self._match())
        pa, _ = a.profil('J', 'ATP', 'Clay', dt.date(2025, 1, 3))
        pb, _ = b.profil('J', 'ATP', 'Clay', dt.date(2025, 1, 3))
        mu = a.moyenne('ATP', 'Clay')
        self.assertLessEqual(abs(pb['w1']-mu['w1']), abs(pa['w1']-mu['w1']))

    def test_export_conserve_les_reglages(self):
        p = PS.Profils(180, 2)
        p.ajouter(self._match())
        doc = p.exporter(dt.date(2025, 1, 3), n_min=0)
        q = PS.Profils.importer(doc)
        self.assertEqual((q.hl, q.prior_mult), (180, 2))

    def test_challenger_ne_change_pas_la_selection(self):
        self.assertEqual(PR.CANDIDATS['champion'], {'demi_vie': 365, 'prior_mult': 1.0})

    def test_backtest_candidat_point_in_time(self):
        m1 = dict(self._match(dt.date(2025, 1, 1)), bo=3, sets=[(6, 4), (6, 4)], complet=True, abandon=False)
        m2 = dict(self._match(dt.date(2025, 1, 4)), bo=3, sets=[(6, 4), (6, 4)], complet=True, abandon=False)
        m2['fin'] = dt.date(2025, 1, 5)
        r = PR.evaluer_candidat([m1, m2], {id(m2)}, PR.CANDIDATS['champion'], dt.date(2026, 1, 1))
        self.assertEqual(r['decouverte']['global']['n'], 1)


class Dependances(unittest.TestCase):
    def test_variables_seulement_passees(self):
        tx = {'f': .6, 'w1': .65, 'w2j': .5, 'a': .05, 'bp': 0., 'd': .03}
        ligne = {'t': 1, 'bo': 5, 'pbp': [[1, 1, 0, 'HA'], [1, 13, 1, 'H']],
                 'srv': [{'tx': tx, 'p': .6}, {'tx': tx, 'p': .6}], 'var': [{}, {}]}
        rows, matchs = DP.extraire([ligne])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][3][0], 0)
        self.assertEqual(rows[1][3][0], 1)  # home vient de gagner le point précédent, toujours serveur
        self.assertEqual(rows[2][3][1], 1)  # tie-break
        self.assertEqual(rows[2][3][3], rows[2][3][2])  # interaction BO5


class Gouvernance(unittest.TestCase):
    def test_une_seule_promotion(self):
        choix = {'a': {'adopte': True, 'adopte_brut': True, 'stabilite': 'oui'},
                 'b': {'adopte': True, 'adopte_brut': True, 'stabilite': 'oui'}}
        stab = {'a': {'gain': .002, 'adopte': True}, 'b': {'gain': .004, 'adopte': True}}
        precedent = {'choix': {'a': {'adopte': False}, 'b': {'adopte': False}}}
        choix, stab, rapport = G.appliquer(choix, stab, precedent, '2026-W44')
        self.assertEqual(rapport['promotions_retenues'], ['b'])
        self.assertEqual(rapport['promotions_differees'], ['a'])
        self.assertFalse(choix['a']['adopte'])

    def test_chevauchement_detecte(self):
        precedent = {'choix': {'combinaison_continue': {'adopte': False, 'jugement': {'depuis': '2026-10-01', 'jusqua': '2026-10-10'}}}}
        choix = {'combinaison_continue': {'adopte': False, 'jugement': {'depuis': '2026-10-05', 'jusqua': '2026-10-15', 'n': 40}}}
        _, _, r = G.appliquer(choix, {}, precedent, '2026-W44')
        self.assertFalse(r['periodes']['ok'])


class RechercheExterne(unittest.TestCase):
    def setUp(self):
        self.debut = RE._date('2026-10-20T12:00:00Z')
        self.prono = RE._date('2026-10-20T10:00:00Z')

    def test_cotes_censurees_avant_debut(self):
        row = {'home_curve': [['2026-10-20T09:00:00Z', 2.0], ['2026-10-20T10:30:00Z', 2.0],
                              ['2026-10-20T11:30:00Z', 1.5], ['2026-10-20T12:30:00Z', 1.1]],
               'away_curve': [['2026-10-20T09:00:00Z', 2.0], ['2026-10-20T10:30:00Z', 2.0],
                              ['2026-10-20T11:30:00Z', 3.0], ['2026-10-20T12:30:00Z', 8.0]]}
        r = RE.mouvement(row, self.prono, self.debut)
        self.assertAlmostEqual(r['p_au_pronostic'], .5)
        self.assertAlmostEqual(r['p_avant_debut'], 2/3)
        self.assertNotIn('12:30', r['horodatage_avant_debut'])

    def test_signal_posterieur_au_pronostic_exclu(self):
        m = {'home': 'A', 'away': 'B', 'debut': '2026-10-20T12:00', 'pronostique_le': '2026-10-20T10:00'}
        index = {RE._paire('A', 'B'): [{'joueur': 'A', 'adversaire': 'B', 'detecte_le': '2026-10-20T11:00',
                                       'commence': '2026-10-20T12:00'}]}
        self.assertIsNone(RE.signal_avant(m, index))

    def test_logit_avec_offset(self):
        rows = [(RE._lg(.5), 1, 1) for _ in range(30)] + [(RE._lg(.5), 1, 0) for _ in range(10)]
        beta, _, _ = RE.ajuster(rows, ridge=.01)
        self.assertGreater(beta, 0)
        self.assertGreater(RE.metriques(rows, beta)['gain'], 0)


if __name__ == '__main__':
    unittest.main()
