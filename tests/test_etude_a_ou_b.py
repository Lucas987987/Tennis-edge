"""Paquet 268 : A ou B par niveau de fiabilité (CLV privée) et anatomie des défaites (publique, sans cote ni nom)."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import etude_a_ou_b as AB  # noqa: E402


def _cas(clv_a, clv_b, n, niveau='correct', circuit='CH'):
    return [{'circuit': circuit, 'niveau': niveau, 'clv_a': clv_a, 'clv_b': clv_b, 'gain_a': 0.0, 'gain_b': 0.0,
             'prise': 'exacte'} for _ in range(n)]


def _match(p_home, gagnant, niveau='correct', jour=1, **k):
    m = {'uid': f'2026-11-{jour:02d}_a_b', 'circuit': 'CH', 'debut': f'2026-11-{jour:02d}T12:00',
         'pronostique_le': f'2026-11-{jour:02d}T06:00:00Z', 'fiabilite': {'niveau': niveau},
         'premier': {'combinaison': {'p_home': p_home}}, 'reel': {'gagnant': gagnant, 'interrompu': None}}
    m.update(k)
    return m


class Regle(unittest.TestCase):
    def test_trop_tot_sous_30(self):
        self.assertEqual(AB.verdict_case(_cas(0.05, -0.05, 29))['verdict'], 'trop tot')

    def test_a_positif_confirme(self):
        L = _cas(0.05, -0.08, 20) + _cas(0.03, -0.07, 20)
        L[0]['clv_a'] = 0.10
        self.assertEqual(AB.verdict_case(L)['verdict'], 'A positif — CONFIRMÉ')

    def test_a_confirmer_si_une_moitie_negative(self):
        L = _cas(-0.01, -0.05, 20) + _cas(0.08, -0.10, 20)
        L[0]['clv_a'] = -0.0                              # première moitié ≤ 0
        r = AB.verdict_case(L)
        self.assertTrue(r['verdict'].endswith('à confirmer') or r['verdict'] == 'indécis', r)

    def test_negatif(self):
        self.assertEqual(AB.verdict_case(_cas(-0.03, -0.03, 40))['verdict'], 'négatif')

    def test_prise_au_premier_pronostic(self):
        d = dt.datetime(2026, 11, 1, 6)
        e = {'history': [{'t': '2026-11-01T05:00:00', 'home': 1.5, 'away': 2.6},
                         {'t': '2026-11-01T09:00:00', 'home': 1.4, 'away': 2.9}]}
        self.assertEqual(AB.prise(e, d, dt.datetime(2026, 11, 1, 12)), (1.5, 2.6, 'exacte'))
        e2 = {'history': [{'t': '2026-11-01T09:00:00', 'home': 1.4, 'away': 2.9}]}
        self.assertEqual(AB.prise(e2, d, dt.datetime(2026, 11, 1, 12)), (1.4, 2.9, 'dans_6h'))
        e3 = {'history': [{'t': '2026-11-01T13:00:00', 'home': 1.4, 'away': 2.9}]}
        self.assertIsNone(AB.prise(e3, d, dt.datetime(2026, 11, 1, 14)))


class Public(unittest.TestCase):
    def test_rapport_sans_nom_ni_cote(self):
        import tempfile
        L = [_match(0.7, 'home' if k % 3 else 'away', 'fragile' if k % 2 else 'solide', 1 + k % 28,
                    home='Jean Dupont', away='Paul Martin', matchs_joues=[20, 100]) for k in range(80)]
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'Tennis_Edge_Lab', 'live').mkdir(parents=True)
            Path(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json').write_text(json.dumps({'matchs': L}))
            r = AB.public(d)
        self.assertEqual(r['matchs'], 80)
        t = json.dumps(r, ensure_ascii=False)
        for interdit in ('Dupont', 'Martin', 'cote', 'Pinnacle', 'march', 'CLV', 'roi_'):
            self.assertNotIn(interdit, t)
        g = r['anatomie']['CH']['criteres']['un joueur à moins de 30 matchs']
        self.assertEqual(g['n'], 80)
        self.assertNotIn('sous_prevu', t)

    def test_a_est_le_favori_du_premier_pronostic(self):
        import tempfile
        L = [_match(0.3, 'away'), _match(0.8, 'away', jour=2)]
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'Tennis_Edge_Lab', 'live').mkdir(parents=True)
            Path(d, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json').write_text(json.dumps({'matchs': L}))
            M = AB.matchs(d)
        self.assertEqual([(x['a'], x['a_gagne'], round(x['p_a'], 2)) for x in M], [(1, True, 0.7), (0, False, 0.8)])

    def test_prive_jamais_ecrit_dans_le_depot(self):
        src = (RACINE / 'simulateur' / 'etude_a_ou_b.py').read_text(encoding='utf-8')
        self.assertIn("P = prive(racine, M)                                   # jamais écrit dans le dépôt", src)
        self.assertEqual(src.count("open(os.path.join(racine, 'simulateur'"), 1)       # seul le rapport public est écrit
        wf = (RACINE / '.github' / 'workflows' / 'a_ou_b.yml').read_text(encoding='utf-8')
        self.assertIn('git add -- simulateur/rapport_anatomie_defaites.json', wf)
        self.assertNotIn('--force', wf)
        self.assertNotIn('-f origin', wf)

    def test_regle_dans_l_en_tete(self):
        self.assertIn('RÈGLE FIXÉE AVANT DE REGARDER LES RÉSULTATS', AB.__doc__)
        self.assertEqual((AB.N_MIN, AB.N_MOITIE, AB.N_MOITIE_ANAT), (30, 15, 30))


if __name__ == '__main__':
    unittest.main()
