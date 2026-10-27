import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import recap_apprentissage as RA


def donnees():
    return {
        'facteurs': {
            'genere_le': '2026-10-26T08:00:00+00:00', 'apprentissage': 1000, 'jugement': 300,
            'groupes': {
                'styles': {'adopte': True, 'adopte_brut': True, 'stabilite': 'en place'},
                'matchup': {'adopte': False, 'adopte_brut': True, 'stabilite': 'candidat (1/2)'},
                'pression': {'adopte': False, 'adopte_brut': False, 'stabilite': 'pas adopté'},
            },
            'ensemble_sur_le_jugement': {
                'base': {'log_loss': .7, 'reussite_pct': 60.},
                'avec': {'log_loss': .68, 'reussite_pct': 61.5},
            },
        },
        'choix': {'combinaison_continue': {
            'n': 140, 'min': 400, 'adopte': False, 'raison': 'en attente',
            'genere_le': '2026-10-26T09:00:00+00:00',
        }},
        'stabilite': {},
        'evaluation': {'global': {'combinaison': {
            'matchs': 150,
            'victoire': {'log_loss': {'valeur': .63}, 'brier': {'valeur': .22}, 'exact': {'valeur': .633333}},
            'scores': {'exact': {'valeur': .034}}, 'jeux': {'mae': {'valeur': 4.9}},
        }}},
        'recalibrage': {
            'populations_separees': True,
            'direct': {'n': 159, 'semaines': 2, 'champion_actif_modifie': False,
                       'decisions': {'logistique': {'adopte': False, 'statut': 'accumulation',
                                                    'gain_log_loss_pondere': None, 'fenetres_positives': 0, 'fenetres': 0}}},
            'rejoue': {'n': 4821, 'semaines': 13,
                       'decisions': {'logistique': {'adopte': False, 'statut': 'confirmation',
                                                    'gain_log_loss_pondere': -.003, 'fenetres_positives': 1, 'fenetres': 6}}},
        },
        'derive': {'statut': 'accumulation', 'n': 150, 'fenetres': {}, 'groupes_12_semaines': {}},
        'gouvernance': {
            'semaine': '2026-W44', 'statut': 'ok', 'initialisation': True,
            'champion_avant': None, 'champion_apres': 'abc',
            'promotions_demande_es': [], 'promotions_retenues': [], 'promotions_differees': [],
        },
    }


class RecapTests(unittest.TestCase):
    def test_synthese_conserve_populations_et_avant_apres(self):
        source = donnees()
        avant = copy.deepcopy(source)
        r = RA.construire(source, genere_le='2026-10-28T00:00:00+00:00')
        self.assertEqual(source, avant)
        self.assertEqual(r['statut'], 'ok')
        self.assertEqual(r['facteurs']['avant_apres_jugement']['gain_log_loss'], .02)
        self.assertEqual(r['facteurs']['avant_apres_jugement']['gain_exactitude_points'], 1.5)
        self.assertEqual(r['facteurs']['adoptes'], ['styles'])
        self.assertEqual(r['facteurs']['candidats_en_attente'], ['matchup'])
        self.assertEqual(r['apprentissage_continu']['statut'], 'accumulation')
        self.assertEqual(r['recalibrage']['direct']['n'], 159)
        self.assertEqual(r['recalibrage']['rejoue']['n'], 4821)
        self.assertFalse(r['modifie_apprentissage'])
        self.assertFalse(r['marche_utilise'])
        self.assertIsNone(r['champion']['modifie_cette_semaine'])

    def test_markdown_est_lisible_et_ne_transforme_pas_absence_en_zero(self):
        r = RA.construire(donnees(), genere_le='2026-10-28T00:00:00+00:00')
        texte = RA.markdown(r)
        self.assertIn('2026-W44', texte)
        self.assertIn('0.68', texte)
        self.assertIn('140/400 matchs documentés', texte)
        self.assertIn('Les deux populations ne sont jamais agrégées', texte)
        self.assertIn('| direct | Régression logistique | accumulation | — | 0/0 | non |', texte)
        self.assertIn('initialisation du suivi', texte)
        self.assertIn('aucun gain de ROI', texte)

    def test_sources_manquantes_donnent_un_recap_partiel(self):
        r = RA.construire({}, genere_le='2026-10-28T00:00:00+00:00')
        self.assertEqual(r['statut'], 'partiel')
        self.assertEqual(len(r['sources_manquantes']), len(RA.FICHIERS))
        self.assertIsNone(r['performance_recente']['exactitude'])
        self.assertIsNone(r['facteurs']['avant_apres_jugement']['gain_log_loss'])
        self.assertIn('—', RA.markdown(r))

    def test_alerte_de_derive_et_champion_reellement_modifie(self):
        d = donnees()
        d['derive'] = {'statut': 'alerte', 'n': 100,
                       'fenetres': {'4_semaines': {'alertes': ['degradation_log_loss_et_brier']}},
                       'groupes_12_semaines': {}}
        d['gouvernance'].update(initialisation=False, champion_avant='abc', champion_apres='def')
        r = RA.construire(d)
        self.assertEqual(r['statut'], 'alerte')
        self.assertEqual(r['derive']['alertes'], ['4_semaines:degradation_log_loss_et_brier'])
        self.assertTrue(r['champion']['modifie_cette_semaine'])

    def test_main_ecrit_json_et_markdown_sans_modifier_les_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            dossier = os.path.join(tmp, 'simulateur')
            os.makedirs(dossier)
            for nom, doc in donnees().items():
                with open(os.path.join(dossier, RA.FICHIERS[nom]), 'w', encoding='utf-8') as fh:
                    json.dump(doc, fh)
            avant = {nom: Path(dossier, f).read_text(encoding='utf-8')
                     for nom, f in RA.FICHIERS.items()}
            r = RA.main(tmp)
            self.assertEqual(r['schema'], 'recap_apprentissage_v1')
            self.assertEqual(avant, {nom: Path(dossier, f).read_text(encoding='utf-8')
                                     for nom, f in RA.FICHIERS.items()})
            with open(os.path.join(dossier, 'recap_apprentissage.json'), encoding='utf-8') as fh:
                self.assertEqual(json.load(fh)['semaine'], '2026-W44')
            self.assertTrue(os.path.getsize(os.path.join(dossier, 'recap_apprentissage.md')) > 500)


if __name__ == '__main__':
    unittest.main()
