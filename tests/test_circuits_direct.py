"""Paquet 335 — verdicts en direct lus ATP / WTA / Challenger : les trois circuits toujours côte à côte, rien sous 30
clôtures, CLV corrigée de Holm sur toutes les cases lues ; ligne « par circuit » dans le récap privé."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import suivi_direct as S  # noqa: E402
import h13_recap as H  # noqa: E402


def paris(n, clv, circ, jour0=1):
    return [{'cote': 2.0, 'book': 'bet365', 'gagne': i % 2, 'pnl': 1.0 if i % 2 else -1.0, 'clv_pin': clv + (i % 3 - 1) * 0.5,
             'jour': f"2026-10-{(jour0 + i) % 28 + 1:02d}", 'lead_min': 60, 'circuit': circ} for i in range(n)]


class Circuits(unittest.TestCase):
    def test_circuit(self):
        self.assertEqual(S.circuit('ATP Challenger Cali'), 'Challenger')
        self.assertEqual(S.circuit('WTA Linz'), 'WTA')
        self.assertEqual(S.circuit('ATP Lyon'), 'ATP')
        self.assertEqual(S.circuit(''), 'inconnu')

    def test_trois_circuits_seuil_et_holm(self):
        p = paris(40, 3.0, 'Challenger') + paris(40, -3.0, 'WTA') + paris(10, 5.0, 'ATP')
        clv = [(x['clv_pin'], x['jour'], x['circuit']) for x in p]
        pc = S.par_circuit(p, clv)
        self.assertEqual(set(pc), {'ATP', 'WTA', 'Challenger'})
        S.holm_circuits([pc])
        self.assertEqual(pc['Challenger']['lecture'], 'CLV positive (Holm)')
        self.assertEqual(pc['WTA']['lecture'], 'CLV négative')
        self.assertTrue(pc['ATP']['lecture'].startswith('trop tôt'))           # +5 % mais 10 clôtures seulement
        self.assertNotIn('clv_p_holm', pc['ATP'])

    def test_holm_sur_toutes_les_cases(self):
        a = S.par_circuit(paris(40, 0.2, 'ATP'), [(x['clv_pin'], x['jour'], 'ATP') for x in paris(40, 0.2, 'ATP')])
        b = S.par_circuit(paris(40, 0.2, 'ATP'), [(x['clv_pin'], x['jour'], 'ATP') for x in paris(40, 0.2, 'ATP')])
        S.holm_circuits([a, b])
        self.assertGreaterEqual(a['ATP']['clv_p_holm'], a['ATP']['clv_pin_p'])

    def test_recap_prive(self):
        p = paris(40, 3.0, 'Challenger')
        o = S.bloc(p)
        o['par_circuit'] = S.par_circuit(p, [(x['clv_pin'], x['jour'], x['circuit']) for x in p])
        S.holm_circuits([o['par_circuit']])
        doc = {'genere_le': '2026-11-22T08:00', 'hypotheses': [{'code': 'H17', 'libelle': 'x', 'cible': 350,
                                                                 'out_of_sample': dict(o, n_detectees=40, n_envoyees=40)}]}
        txt = H.message_direct(doc)
        self.assertIn('par circuit (CLV) : CH +3.0 % (40) ✅', txt)
        self.assertIn('Ne pas diffuser', txt)


if __name__ == '__main__':
    unittest.main()
