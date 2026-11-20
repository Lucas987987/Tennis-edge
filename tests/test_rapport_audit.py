# -*- coding: utf-8 -*-
"""11/11/2026 (paquet 227) — le rapport d'audit est public et porte, pour chaque étude à venir, sa règle écrite à l'avance."""
import json
import os
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
CHEMIN = os.path.join(ICI, '..', 'simulateur', 'rapport_audit.json')
INTERDITS = ('marché', 'marche ', 'pinnacle', 'clôture', 'cloture', 'closing', 'oddspapi', 'cote')


class RapportAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CHEMIN, encoding='utf-8') as f:
            cls.doc = json.load(f)

    def test_public_sans_mot_interdit(self):
        txt = json.dumps(self.doc, ensure_ascii=False).lower()
        for mot in INTERDITS:
            self.assertNotIn(mot, txt, mot)

    def test_chaque_etude_prevue_a_sa_regle(self):
        prevus = [c for c in self.doc['constats'] if c.get('paquet_prevu')]
        self.assertGreaterEqual(len(prevus), 5)
        for c in prevus:
            self.assertIn('2018–2022', c['regle'] + self.doc['methode']['regle_generale'], c['id'])
            self.assertTrue(c['regle'].strip(), c['id'])
        self.assertEqual(sorted(c['paquet_prevu'] for c in prevus), sorted(set(c['paquet_prevu'] for c in prevus)))

    def test_la_periode_de_jugement_n_a_pas_ete_regardee(self):
        """Aucune mesure d'archive du rapport ne porte sur 2023 ou après (les clés de mesure disent leur période)."""
        for c in self.doc['constats']:
            for cle in c:
                if cle.startswith('mesure_') and any(a in cle for a in ('2016', '2018', '2019')):
                    self.assertFalse(any(a in cle for a in ('2023', '2024', '2025')), (c['id'], cle))
        self.assertIn('intacte', self.doc['methode']['archive'])

    def test_les_correctifs_du_paquet_sont_en_place(self):
        faits = {r['id'] for r in self.doc['risques_sans_etude'] if r.get('fait_dans_le_paquet') == 227}
        self.assertEqual(faits, {'journal_public', 'parite_elo'})
        with open(os.path.join(ICI, '..', 'simulateur', 'journal_changements.json'), encoding='utf-8') as f:
            J = json.load(f)['changements']
        self.assertTrue([c for c in J if c.get('paquet') == 227])
        self.assertTrue([c for c in J if c.get('prive')])


if __name__ == '__main__':
    unittest.main()
