"""Adoption directe des signaux combinés (04/11/2026) : en place d'emblée, retrait après deux semaines de perte."""
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import fantomes_circuits as FC  # noqa: E402
import pronostics_du_jour as PD  # noqa: E402


def racine(adopte_atp=True):
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, 'simulateur', 'journal_pronostics', 'apres_match'))
    doc = {'circuits': {'ATP': {'adopte': adopte_atp, 'betas': {'age_vieux': -0.04, 'favori_outsider': 1.5}},
                        'WTA': {'adopte': False, 'betas': {'age_vieux': -0.03}}}}
    json.dump(doc, open(os.path.join(d, 'simulateur', 'rapport_signaux_combines.json'), 'w'))
    return d


def bilans(d, jour, n, ll_sans, ll_affiche):
    B = {str(i): {'circuit': 'ATP', 'debut': jour, 'ecarts': {'signaux_circuit': {
        'appliques': ['age', 'favori_outsider', 'changement_surface', 'retour_absence'], 'll_sans': ll_sans, 'll_affiche': ll_affiche}}}
        for i in range(n)}
    with gzip.open(os.path.join(d, 'simulateur', 'journal_pronostics', 'apres_match', f'{jour}.json.gz'), 'wt') as f:
        json.dump(B, f)


class Adoption(unittest.TestCase):
    def test_en_place_d_emblee_sur_le_circuit_adopte(self):
        d = racine()
        L = FC.lire(d)
        for s in ('age', 'favori_outsider', 'changement_surface', 'retour_absence'):
            self.assertEqual(L.get(s), ['ATP'])

    def test_betas_combines(self):
        d = racine()
        B = PD.charger_betas_combines(d)
        self.assertEqual(set(B), {'ATP'})
        ancien = PD.BETAS_COMBINES
        PD.BETAS_COMBINES = B
        try:
            self.assertEqual(PD._beta('ATP', 'favori_outsider', 2.0), 1.5)
            self.assertEqual(PD._beta('WTA', 'favori_outsider', 2.0), 2.0)
        finally:
            PD.BETAS_COMBINES = ancien

    def test_retrait_apres_deux_semaines_de_perte(self):
        d = racine()
        bilans(d, '2026-11-03', 40, 0.60, 0.62)               # semaine 1 : pire de 0,02
        os.environ['FANTOMES_JOUR'] = '2026-11-10'
        FC.main(['x', d])
        self.assertIn('ATP', FC.lire(d).get('age', []))       # 1 semaine : toujours en place
        bilans(d, '2026-11-12', 40, 0.60, 0.62)
        os.environ['FANTOMES_JOUR'] = '2026-11-17'
        FC.main(['x', d])
        self.assertNotIn('ATP', FC.lire(d).get('age', []))    # 2 semaines de perte : retiré
        os.environ.pop('FANTOMES_JOUR')

    def test_semaine_pauvre_ne_compte_pas(self):
        d = racine()
        bilans(d, '2026-11-03', 5, 0.60, 0.70)
        os.environ['FANTOMES_JOUR'] = '2026-11-10'
        FC.main(['x', d])
        os.environ['FANTOMES_JOUR'] = '2026-11-17'
        FC.main(['x', d])
        os.environ.pop('FANTOMES_JOUR')
        self.assertIn('ATP', FC.lire(d).get('age', []))


if __name__ == '__main__':
    unittest.main()
