# -*- coding: utf-8 -*-
"""12/11/2026 (paquet 238) — en salle, plus de 1res balles : la table, l'étude, le décalage en production (avant le
recalage appris en direct, à l'affichage comme à l'apprentissage) et son suivi."""
import datetime as dt
import json
import os
import random
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import etude_premieres_balles_salle as EP  # noqa: E402
import pronostics_du_jour as PJ  # noqa: E402
import recalage_stats as RS  # noqa: E402
import tournois_en_salle as TS  # noqa: E402
import vitrine as VI  # noqa: E402

DEC = {'ATP': {'premiere_pct': {'salle': 1.22, 'plein_air': 0.02}, 'doubles_fautes': {'salle': -0.485, 'plein_air': -0.08}}}


class Table(unittest.TestCase):
    def test_trois_reponses(self):
        self.assertIs(TS.en_salle('ATP', 'Paris Masters', 'Hard'), True)
        self.assertIs(TS.en_salle('ATP', 'Miami Masters', 'Hard'), False)
        self.assertIs(TS.en_salle('ATP', 'Belgrade', 'Clay'), False)          # tranché par la surface
        self.assertIs(TS.en_salle('ATP', 'Belgrade', 'Hard'), True)
        self.assertIs(TS.en_salle('WTA', 'Stuttgart', 'Clay'), True)          # terre battue en salle
        self.assertIs(TS.en_salle('ATP', 'Stuttgart', 'Grass'), False)
        for c, t in (('CH', 'Paris Masters'), ('ATP', 'Tokyo'), ('ATP', None), ('ITF', 'x')):
            self.assertIsNone(TS.en_salle(c, t, 'Hard'), (c, t))

    def test_la_table_dit_comment_elle_a_ete_ecrite(self):
        self.assertIn('SANS regarder un seul résultat', TS.__doc__)
        self.assertGreater(len(TS.SALLE['ATP']), 25)
        self.assertFalse(set(TS.SALLE['ATP']) & set(TS.INCERTAINS['ATP']))


def cas(n, annees, salle, biais, k='premiere_pct', c='ATP', graine=1):
    rnd, out = random.Random(graine), []
    for an in annees:
        for i in range(n):
            out.append({'jour': f'{an}-{1 + i % 12:02d}-10', 'c': c, 'k': k, 'moy': 62.0, 'p10': 54.0, 'p90': 70.0,
                        'reel': 62.0 + biais + rnd.gauss(0, 6), 'tournoi': 'Paris Masters' if salle else 'Miami Masters', 'surface': 'Hard'})
    return out


class Etude(unittest.TestCase):
    def test_un_biais_en_salle_qui_tient_est_retenu(self):
        rows = cas(400, (2019, 2020, 2021, 2022, 2023, 2024, 2025), True, 1.8) + cas(1500, (2019, 2020, 2021, 2022, 2023, 2024, 2025), False, 0.0, graine=2)
        x = EP.etudier(rows)['ATP']['premiere_pct']
        self.assertAlmostEqual(x['decalages']['salle'], 1.8, delta=0.4)
        self.assertAlmostEqual(x['decalages']['plein_air'], 0.0, delta=0.3)
        self.assertTrue(x['retenu'], x['raisons'])
        self.assertLess(abs(x['jugement_apres']['biais_en_salle']), abs(x['jugement_avant']['biais_en_salle']) / 2)

    def test_pas_assez_de_cas_en_salle_ou_biais_qui_ne_tient_pas(self):
        peu = cas(400, (2019, 2020, 2021, 2022), True, 1.8) + cas(300, (2023, 2024), True, 1.8) + cas(1500, (2019, 2020, 2021, 2022, 2023, 2024), False, 0.0, graine=2)
        self.assertIn('moins de 1000 cas en salle jugés', EP.etudier(peu)['ATP']['premiere_pct']['raisons'])
        tient_pas = cas(400, (2019, 2020, 2021, 2022), True, 1.8) + cas(600, (2023, 2024), True, -0.5, graine=5) + cas(1500, (2019, 2020, 2021, 2022, 2023, 2024), False, 0.0, graine=2)
        self.assertFalse(EP.etudier(tient_pas)['ATP']['premiere_pct']['retenu'])

    def test_regle_ecrite_avant(self):
        with open(os.path.join(RACINE, 'simulateur', 'etude_premieres_balles_salle.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn('AVANT DE LANCER', src)
        self.assertEqual((EP.MIN_CAS_SALLE, EP.REDUCTION, EP.COUPURE), (1000, 0.5, '2023-01-01'))


class Rapport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(os.path.join(RACINE, 'simulateur', 'rapport_premieres_balles_salle.json'), encoding='utf-8') as f:
            cls.R = json.load(f)
        with open(os.path.join(RACINE, 'simulateur', 'salle_stats.json'), encoding='utf-8') as f:
            cls.C = json.load(f)

    def test_public(self):
        for doc in (self.R, self.C):
            txt = json.dumps(doc, ensure_ascii=False).lower()
            for mot in ('marché', 'pinnacle', 'clôture', 'cote'):
                self.assertNotIn(mot, txt)

    def test_les_verdicts_suivent_la_regle(self):
        for c, v in self.R['circuits'].items():
            for k, x in v.items():
                a, b = x['jugement_avant'], x['jugement_apres']
                passe = (a['cas_en_salle'] >= 1000 and abs(b['biais_en_salle']) <= abs(a['biais_en_salle']) / 2
                         and b['ecart_moyen'] <= a['ecart_moyen'])
                self.assertEqual(x['retenu'], passe, (c, k))
        self.assertIn('ATP|premiere_pct', self.R['retenus'])

    def test_seul_ce_qui_a_passe_est_en_production(self):
        attendu = {}
        for cle in self.R['retenus']:
            c, k = cle.split('|')
            attendu.setdefault(c, {})[k] = self.R['circuits'][c][k]['decalages']
        self.assertEqual(self.C['decalages'], attendu)
        self.assertEqual(RS.decalages_salle(RACINE), attendu)
        self.assertIn('300', self.C['retrait'])


class Production(unittest.TestCase):
    def test_decalage_d_une_statistique(self):
        self.assertEqual(RS.decaler_salle(DEC, 'ATP', 'premiere_pct', True, 62.0, 54.0, 70.0), (63.2, 55.2, 71.2))
        self.assertEqual(RS.decaler_salle(DEC, 'ATP', 'premiere_pct', False, 62.0, 54.0, 70.0), (62.0, 54.0, 70.0))
        self.assertEqual(RS.decaler_salle(DEC, 'ATP', 'premiere_pct', None, 62.0, 54.0, 70.0), (62.0, 54.0, 70.0))   # on ne sait pas
        self.assertEqual(RS.decaler_salle(DEC, 'ATP', 'premiere_pct', True, 99.5, 98.0, 99.9), (100.0, 99.2, 100.0))  # borné
        self.assertEqual(RS.decaler_salle(DEC, 'ATP', 'doubles_fautes', True, 2.8, 0.0, 5.0), (2.31, 0.0, 5.0))       # comptes : bornes entières
        self.assertEqual(RS.decaler_salle(DEC, 'WTA', 'premiere_pct', True, 62.0, 54.0, 70.0), (62.0, 54.0, 70.0))    # rien de réglé en WTA
        self.assertEqual(RS.decaler_salle(DEC, 'ATP', 'aces', True, 6.0, 2.0, 10.0), (6.0, 2.0, 10.0))

    def test_le_site_decale_avant_le_recalage_et_garde_les_valeurs_d_avant(self):
        fp = [{'premiere_pct': 62.0, 'aces': 6.0}, {'premiere_pct': 58.0, 'aces': 3.0}]
        fq = [{'premiere_pct': [54.0, 70.0], 'aces': [2.0, 10.0]}, {'premiere_pct': [50.0, 66.0], 'aces': [1.0, 6.0]}]
        fp2, fq2, ok, avant = VI.decaler_salle('ATP', True, fp, fq, dec=DEC)
        self.assertTrue(ok)
        self.assertEqual((fp2[0]['premiere_pct'], fq2[0]['premiere_pct'], fp2[0]['aces']), (63.2, [55.2, 71.2], 6.0))
        self.assertEqual(avant[1]['premiere_pct'], [58.0, 50.0, 66.0])
        self.assertEqual(fp[0]['premiere_pct'], 62.0)                              # l'entrée n'est pas modifiée
        for c, salle in (('ATP', None), ('WTA', True)):
            self.assertEqual(VI.decaler_salle(c, salle, fp, fq, dec=DEC), (fp, fq, False, None))
        with open(os.path.join(RACINE, 'simulateur', 'vitrine.py'), encoding='utf-8') as f:
            src = f.read()
        self.assertIn("recaler_feuille(m.get('circuit'), fp0, fq0)[0]", src)
        self.assertIn("'feuille_prevue_brute': fp0", src)                          # le recalage en direct apprend sur les valeurs décalées

    def fiche(self, **dernier):
        d = {'feuille': [{'premiere_pct': 62.0}, {'premiere_pct': 58.0}], 'fourchette': [{'premiere_pct': [54.0, 70.0]}, {'premiere_pct': [50.0, 66.0]}]}
        d.update(dernier)
        return {'circuit': 'ATP', 'debut': '2026-11-03T18:00:00+00:00', 'home': 'Ana Un', 'away': 'Bea Deux', 'dernier': d}

    REEL = {'u': {'feuille': [{'premiere_pct': 66.0}, {'premiere_pct': 60.0}]}}

    def test_l_apprentissage_ajoute_le_decalage_aux_fiches_qui_ne_l_ont_pas(self):
        import elo as E
        salles = {('2026-11-03', *sorted((E.cle('Ana Un'), E.cle('Bea Deux')))): True}
        vieux = RS.lignes({'u': self.fiche()}, self.REEL, salles, DEC)             # fiche d'avant : pas de décalage dedans
        self.assertEqual([(r['moy'], r['p10'], r['p90'], r['salle']) for r in vieux], [(63.2, 55.2, 71.2, True), (59.2, 51.2, 67.2, True)])
        neuf = RS.lignes({'u': self.fiche(en_salle=True, salle_appliquee=True)}, self.REEL, None, DEC)
        self.assertEqual([r['moy'] for r in neuf], [62.0, 58.0])                   # déjà décalée au pronostic : pas deux fois
        inconnu = RS.lignes({'u': self.fiche()}, self.REEL, {}, DEC)
        self.assertEqual([(r['moy'], r['salle']) for r in inconnu], [(62.0, None), (58.0, None)])

    def test_en_salle_lu_dans_la_fiche_puis_dans_la_feuille_du_match(self):
        import elo as E
        cles = sorted((E.cle('Ana Un'), E.cle('Bea Deux')))
        self.assertIs(RS.salle_de_la_fiche(self.fiche(en_salle=False), {('2026-11-03', *cles): True}), False)   # la fiche d'abord
        self.assertIs(RS.salle_de_la_fiche(self.fiche(), {('2026-11-04', *cles): True}), True)                # lendemain (heure UTC)
        self.assertIsNone(RS.salle_de_la_fiche(self.fiche(), {('2026-11-08', *cles): True}))

    def test_suivi_sans_decalage_reprend_les_valeurs_d_avant(self):
        f = self.fiche(en_salle=True, salle_appliquee=True, salle_brut=[{'premiere_pct': [60.8, 52.8, 68.8]}, {'premiere_pct': [56.8, 48.8, 64.8]}])
        self.assertEqual([r['moy'] for r in RS.lignes({'u': f}, self.REEL, None, None, sans_decalage=True)], [60.8, 56.8])

    def test_un_decalage_retire_n_est_plus_lu(self):
        self.assertNotIn('premiere_pct', RS.decalages_salle(RACINE, {'ATP|premiere_pct'}).get('ATP', {}))
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(RS.decalages_salle(d), {})
            self.assertEqual(RS.salle_retiree(d), set())

    def test_le_pronostic_note_si_le_match_est_en_salle(self):
        avant = (PJ.PROGRAMME, dict(PJ.SALLES))
        try:
            PJ.PROGRAMME = {('2026-11-12', 'a', 'b'): {'tournoi': 'Metz, France, Qualifying', 'tour': 'Qualification Final'},
                            ('2026-11-12', 'c', 'd'): {'tournoi': 'Inconnu, Nulle Part', 'tour': 'Final'}}
            PJ.SALLES.clear()
            PJ.SALLES.update({'Metz, France': True, 'Montevideo, Uruguay': False})
            self.assertIs(PJ.salle_du_match('b', 'a', dt.date(2026, 11, 12)), True)       # « Qualifying » retiré du nom
            self.assertIsNone(PJ.salle_du_match('c', 'd', dt.date(2026, 11, 12)))         # tournoi sans feuille encore
            self.assertIsNone(PJ.salle_du_match('x', 'y', dt.date(2026, 11, 12)))         # match absent du programme
        finally:
            PJ.PROGRAMME = avant[0]
            PJ.SALLES.clear()
            PJ.SALLES.update(avant[1])
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'feuilles'))
            json.dump({'1': {'nom': 'Metz, France, Qualifying', 'interieur': False}, '2': {'nom': 'Metz, France', 'interieur': True},
                       '3': {'nom': 'Lima, Peru', 'interieur': False}, '4': {'nom': 'Sans drapeau'}}, open(os.path.join(d, 'feuilles', 'tournois.json'), 'w'))
            self.assertEqual(PJ.charger_salles(d), {'Metz, France': True, 'Lima, Peru': False})


if __name__ == '__main__':
    unittest.main()
