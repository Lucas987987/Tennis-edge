"""Exhaustivité, incertitude et gouvernance de la matrice des styles."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import etude_matrice_styles as EM


def ligne(i):
    jour = (dt.date(2024, 1, 1) + dt.timedelta(days=i) if i < 240
            else dt.date(2025, 1, 1) + dt.timedelta(days=i-240))
    pair = ('contreur', 'equilibre') if i % 2 else ('grand_serveur', 'retourneur_pressant')
    return {
        'date': jour, 'semaine': f'{jour.isocalendar().year}-S{jour.isocalendar().week:02d}',
        'y': i % 2, 'bilan_global': (-1)**i * .12,
        'paire_styles': '|'.join(sorted(pair)),
    }


class MatriceStyles(unittest.TestCase):
    def test_21_paires_et_wilson(self):
        self.assertEqual(len(EM.paires()), 21)
        bas, haut = EM.wilson(5, 10)
        self.assertLess(bas, 50)
        self.assertGreater(haut, 50)
        self.assertEqual(EM.wilson(0, 0), [None, None])

    def test_effectifs_complets_metriques_et_incertitude(self):
        rows = [ligne(i) for i in range(480)]
        out = EM.evaluer(rows, bootstrap=30)
        self.assertEqual(len(out['matrices']['confirmation']), 21)
        self.assertEqual(sum(b['n'] for b in out['matrices']['confirmation'].values()), 240)
        bloc = out['matrices']['confirmation']['contreur|equilibre']
        self.assertEqual(bloc['n'], 120)
        self.assertIn('log_loss', bloc['profils_global'])
        self.assertIn('brier', bloc['profils_global'])
        self.assertIn('reussite_pct', bloc['profils_global'])
        self.assertEqual(len(bloc['profils_global']['ic95_exactitude_wilson']), 2)
        for nom in ('log_loss', 'brier', 'gain_log_loss', 'gain_brier'):
            self.assertIn(nom, bloc['ic95_bootstrap_semaine'])
        self.assertFalse(out['selection_sous_groupe'])
        self.assertFalse(out['activation'])
        self.assertFalse(out['champion_actif_modifie'])
        self.assertFalse(out['marche_utilise'])

    def test_markdown_conserve_les_paires_et_signale_la_fragilite(self):
        rows = [ligne(i) for i in range(480)]
        out = EM.evaluer(rows, bootstrap=0)
        texte = EM.markdown(out)
        self.assertIn('Contreur × Équilibré', texte)
        self.assertIn('Grand serveur × Retourneur pressant', texte)
        self.assertIn('Serveur attaquant × Contreur', texte)
        self.assertIn('Aucune paire n’est sélectionnée ou activée', texte)
        self.assertIn('⚠', texte)  # les 19 paires sans observation restent visibles ou fragiles


if __name__ == '__main__':
    unittest.main()
