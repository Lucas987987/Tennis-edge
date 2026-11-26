"""26/11/2026 (paquet 466) : fantôme « pente sous 500 points » en Challenger, suivi sur nos matchs publiés."""
import os
import random
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, os.path.join(RACINE, 'simulateur'))
import suivi_pente_sous_500 as SP  # noqa: E402


def matchs(n, pente_vraie, balles, circuit='CH', graine=7):
    rnd = random.Random(graine)
    out = []
    for i in range(n):
        p = rnd.uniform(.52, .85)
        vraie = SP._sg(pente_vraie * SP._lg(p))
        out.append({'circuit': circuit, 'p_affiche': p, 'balles_min': balles, 'debut': f'2026-12-{1 + i % 28:02d}T{i % 24:02d}',
                    'reel': {'gagnant': 'home' if rnd.random() < vraie else 'away', 'interrompu': None}})
    return {'matchs': out}


class Suivi(unittest.TestCase):
    def test_filtres(self):
        d = matchs(50, 1.0, 300)
        d['matchs'][0]['reel']['interrompu'] = 'abandon'
        d['matchs'][1]['balles_min'] = None
        d['matchs'][2]['circuit'] = 'ITF'
        self.assertEqual(len(SP.lignes(d)), 47)

    def test_jamais_propose_sous_1000(self):
        c = SP.candidat(SP.lignes(matchs(600, 1.6, 200)))
        self.assertEqual(c['matchs'], 600)
        self.assertFalse(c['a_proposer'])

    def test_propose_si_regle_remplie(self):
        c = SP.candidat(SP.lignes(matchs(3000, 1.6, 200)))
        self.assertGreater(c['gain_log_loss'], 0.001)
        self.assertTrue(c['a_proposer'])
        self.assertIn('jamais appliqué automatiquement', c['regle'])

    def test_pas_propose_si_bien_etalonne(self):
        self.assertFalse(SP.candidat(SP.lignes(matchs(3000, 1.0, 200)))['a_proposer'])

    def test_hors_tranche_ignores(self):
        self.assertEqual(SP.candidat(SP.lignes(matchs(200, 1.6, 800)))['matchs'], 0)
        t = SP.par_tranche(SP.lignes(matchs(200, 1.0, 800)))
        self.assertEqual(t['CH']['500 à 1 500']['matchs'], 200)

    def test_branche_en_production(self):
        src = open(os.path.join(RACINE, 'simulateur', 'pronostics_du_jour.py'), encoding='utf-8').read()
        self.assertIn("'balles_min': r.get('balles_min')", src)
        wf = open(os.path.join(RACINE, '.github', 'workflows', 'pronostic.yml'), encoding='utf-8').read()
        self.assertIn('simulateur/suivi_pente_sous_500.py . --telegram', wf)
        self.assertIn('git add -- simulateur/suivi_pente_sous_500.json', wf)


if __name__ == '__main__':
    unittest.main()
