"""Paquet 451 : note de fiabilité mesurée match par match (0 à 100, sans plafond), son apprentissage et son garde-fou."""
import copy
import datetime as dt
import json
import math
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import fiabilite as FI  # noqa: E402
import note_par_match as NP  # noqa: E402
import pronostics_du_jour as P  # noqa: E402


def _sg(z):
    return 1 / (1 + math.exp(-z))


def modele():
    return {'pentes_base': {c: {'_circuit': 1.0, '0': 1.0, '1': 1.0, '2': 1.0, '3': 1.0} for c in NP.CIRCUITS},
            'effets': {'beta': {}, 'gamma': {}}}


class Note(unittest.TestCase):
    def test_note_continue_et_sens(self):
        M = modele()
        M['effets']['beta'] = {'favoris_opposes': math.log(0.6), 'gros_favori': math.log(1.3)}
        e = NP.evaluer_match(M, 'CH', 50, {'favoris_opposes': 1, 'gros_favori': 0})
        self.assertEqual(e['note'], 60)                              # pas de plafond : 60, pas 77
        self.assertEqual(e['sens'], 'tranches')
        e = NP.evaluer_match(M, 'CH', 50, {'favoris_opposes': 0, 'gros_favori': 1})
        self.assertEqual(e['note'], 77)
        self.assertEqual(e['sens'], 'prudents')
        self.assertEqual(NP.evaluer_match(M, 'CH', 50, {})['note'], 100)

    def test_gamma_ajuste_la_base(self):
        M = modele()
        M['effets']['gamma'] = {'CH|3': math.log(1.25)}
        self.assertEqual(NP.evaluer_match(M, 'CH', 400, {})['note'], 80)
        self.assertEqual(NP.evaluer_match(M, 'CH', 50, {})['note'], 100)

    def test_categories(self):
        self.assertEqual([NP.niveau(n) for n in (0, 77, 78, 84, 85, 92, 93, 100)],
                         ['fragile', 'fragile', 'prudent', 'prudent', 'correct', 'correct', 'solide', 'solide'])

    def test_pentes_base_challenger(self):
        pb = NP.pentes_base(str(RACINE))
        self.assertEqual(pb['CH']['3'], NP.CH_APPRIS['_circuit'])    # change de sens entre les périodes : circuit
        self.assertEqual(pb['CH']['1'], NP.CH_APPRIS['1'])
        self.assertIn('2', pb['ATP'])


class Apprentissage(unittest.TestCase):
    def test_retrouve_l_effet_d_un_critere(self):
        rnd = random.Random(3)
        L = []
        for _ in range(20000):
            crit = {k: 0 for k in NP_criteres()}
            crit['huitiemes'] = int(rnd.random() < 0.4)
            a = 0.6 if crit['huitiemes'] else 1.0
            z0 = rnd.gauss(0, 1.3)
            L.append({'c': 'CH', 'n': 150, 'z': z0 if rnd.random() < _sg(a * z0) else -z0, 'crit': crit})
        E = NP.apprendre_effets(L, modele())
        self.assertAlmostEqual(E['facteurs']['huitiemes'], 0.6, delta=0.06)
        self.assertAlmostEqual(E['facteurs']['gros_favori'], 1.0, delta=0.01)     # aucun match : reste à 1
        self.assertEqual(E["matchs"], 20000)

    def test_peu_de_matchs_ramene_vers_aucun_effet(self):
        rnd = random.Random(4)
        L = []
        for i in range(60):
            crit = {k: 0 for k in NP_criteres()}
            crit['huitiemes'] = 1
            z0 = rnd.gauss(0, 1.3)
            L.append({'c': 'CH', 'n': 150, 'z': z0 if rnd.random() < _sg(0.4 * z0) else -z0, 'crit': crit})
        E = NP.apprendre_effets(L, modele())
        self.assertGreater(E['facteurs']['huitiemes'], 0.45)       # rétréci vers 1


def NP_criteres():
    import surveillance_fragilite as SF
    return list(SF.CRITERES)


class GardeFou(unittest.TestCase):
    def _racine(self, nouvelle_juste, n=2000):
        d = tempfile.mkdtemp()
        os.makedirs(os.path.join(d, 'simulateur'))
        os.makedirs(os.path.join(d, 'Tennis_Edge_Lab', 'live'))
        dec = {'active_le': '2026-11-25', 'retire': False, 'pentes_base': modele()['pentes_base']}
        rnd = random.Random(7)
        M = []
        for i in range(n):
            a_vrai = 1.0 if i % 2 == 0 else 0.5
            z0 = rnd.gauss(0, 1.5)
            juste = rnd.random() < _sg(a_vrai * z0)
            bonne, mauvaise = (a_vrai, 100 * min(a_vrai, 1 / a_vrai)), (0.77, 77)
            (an, nn), (aa, na) = (bonne, mauvaise) if nouvelle_juste else (mauvaise, bonne)
            M.append({'circuit': 'CH', 'debut': '2026-11-30T10:00', 'p_affiche': _sg(z0),
                      'reel': {'gagnant': 'home' if juste else 'away', 'interrompu': None},
                      'fiabilite': {'note': nn, 'pente_du_match': an, 'note_ancienne': na, 'pente_ancienne': aa}})
        json.dump({'matchs': M}, open(os.path.join(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), 'w'))
        return d, dec

    def test_gardee(self):
        d, dec = self._racine(True)
        c = NP.garde_fou(d, dec, dt.date(2026, 12, 7))
        self.assertEqual(c['verdict'], 'gardée')
        self.assertFalse(dec['retire'])
        self.assertLess(c['log_loss_pente_nouvelle'], c['log_loss_pente_ancienne'])

    def test_retiree(self):
        d, dec = self._racine(False)
        c = NP.garde_fou(d, dec, dt.date(2026, 12, 7))
        self.assertTrue(c['verdict'].startswith('RETIRÉE'))
        self.assertTrue(dec['retire'])

    def test_trop_tot(self):
        d, dec = self._racine(False, n=150)
        c = NP.garde_fou(d, dec, dt.date(2026, 12, 7))
        self.assertTrue(c['verdict'].startswith('pas encore jugée'))
        self.assertFalse(dec['retire'])


class EnProduction(unittest.TestCase):
    def test_fichier_de_decision(self):
        d = json.load(open(RACINE / 'simulateur' / 'note_par_match.json', encoding='utf-8'))
        self.assertEqual(d['paquet'], 451)
        self.assertIn('regle_retrait', d)
        self.assertTrue(d['effets'] and d['effets']['beta'])
        self.assertNotIn('marché', json.dumps(d, ensure_ascii=False))

    def test_evaluer_sans_plafond_et_ancienne_a_cote(self):
        FI._MODELE_PM.clear()
        if not FI.modele_par_match():
            self.skipTest('note par match retirée')
        base = {'circuit': 'CH', 'surface': 'Hard', 'matchs_joues': [20, 300], 'style_connu': [True, True], 'uid': 'x'}
        f = FI.evaluer(dict(base, combinaison={'p_home': .55}, stats={'p_home': .58}, simulation={'p_home': .45}), [])
        self.assertEqual(f['methode'], 'par_match_451')
        self.assertEqual(f['note'], f['note_par_match'])
        self.assertIn(f['sens'], ('prudents', 'tranches', 'justes'))
        self.assertIn('note_ancienne', f)
        self.assertEqual(f['niveau_correction'], f['niveau_ancien'])
        self.assertEqual(FI.VERSION_FIABILITE, 'par_match')

    def test_correction_suit_l_ancien_niveau(self):
        doc = {'matchs': [
            {'uid': 'a', 'circuit': 'CH', 'combinaison': {'p_home': .65},
             'fiabilite': {'niveau': 'solide', 'niveau_ancien': 'correct', 'niveau_correction': 'correct'}},
            {'uid': 'b', 'circuit': 'CH', 'combinaison': {'p_home': .6},
             'fiabilite': {'niveau': 'correct', 'niveau_ancien': 'solide', 'niveau_correction': 'solide'}}]}
        appels = []

        def faux(racine, maintenant, uids=None, pentes_forcees=None):
            appels.append((uids, pentes_forcees))
            return {'matchs': [{'uid': 'a', 'circuit': 'CH', 'combinaison': {'p_home': .666}, 'fiabilite': {}}]}
        self.assertEqual(P.appliquer_corrections_niveaux(str(RACINE), copy.deepcopy(doc), dt.datetime(2026, 11, 26), {}, faux), 1)
        self.assertEqual(appels, [({'a'}, {'a': 1.142})])

    def test_lundi(self):
        wf = (RACINE / '.github' / 'workflows' / 'pronostic.yml').read_text(encoding='utf-8')
        self.assertIn('python simulateur/note_par_match.py . --telegram', wf)
        self.assertIn('git add -- simulateur/note_par_match.json', wf)


if __name__ == '__main__':
    unittest.main()


class NoteDesJoueurs(unittest.TestCase):
    def test_seuls_les_matchs_d_avant_comptent(self):
        enreg = []
        for i in range(10):                                   # A annoncé à 80 %, perd tout : note basse
            enreg.append({'home': 'Joueur A', 'away': f'X{i}', 'debut': f'2026-11-{10 + i:02d}T10:00', 'p': 0.8, 'y': 0})
        idx = NP.index_joueurs(enreg)
        self.assertEqual(NP.x_joueur(idx, 'Joueur A', 'Inconnu', '2026-11-12'), 0.0)   # 2 matchs avant : pas de note
        x_tard = NP.x_joueur(idx, 'Joueur A', 'Inconnu', '2026-11-30')
        self.assertGreater(x_tard, 0.5)
        self.assertEqual(NP.x_joueur(idx, 'Joueur A', 'Inconnu', '2026-11-15'),
                         NP.x_joueur(NP.index_joueurs(enreg[:5]), 'Joueur A', 'Inconnu', '2026-11-15'))  # le futur n'entre pas

    def test_critere_continu(self):
        M = modele()
        M['effets']['beta'] = {NP.CRITERE_JOUEUR: math.log(0.5)}
        e = NP.evaluer_match(M, 'CH', 50, {NP.CRITERE_JOUEUR: 0.5})
        self.assertEqual(e['note'], round(100 * 0.5 ** 0.5))
        self.assertIn(NP.CRITERE_JOUEUR, NP.noms_criteres())

    def test_enregistrements_portent_les_noms(self):
        h = FI.enregistrements({'matchs': [{'uid': 'u', 'home': 'A', 'away': 'B', 'debut': '2026-11-20T10:00',
                                            'p_affiche': .6, 'reel': {'gagnant': 'home'}}]})
        self.assertEqual((h[0]['home'], h[0]['away'], h[0]['debut']), ('A', 'B', '2026-11-20T10:00'))
