"""Santé de la chaîne (23/10/2026) : alerte quand un maillon s'arrête, rappel toutes les 6 h, « reparti »."""
import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import sante_chaine as SC  # noqa: E402

T0 = dt.datetime(2026, 10, 23, 9, 0, tzinfo=dt.timezone.utc)


def ecrire(d, pron_h, feuil_h, verd_h):
    os.makedirs(os.path.join(d, 'algo'), exist_ok=True)
    os.makedirs(os.path.join(d, 'feuilles'), exist_ok=True)
    iso = lambda h: (T0 - dt.timedelta(hours=h)).isoformat()
    json.dump({'pronostics_du': iso(pron_h).replace('+00:00', 'Z')}, open(os.path.join(d, 'algo', 'donnees.json'), 'w'))
    json.dump({'dernier_passage': {'le': iso(feuil_h)}}, open(os.path.join(d, 'feuilles', 'etat.json'), 'w'))
    json.dump({'genere_le': iso(verd_h)}, open(os.path.join(d, 'verdicts_direct.json'), 'w'))


class Sante(unittest.TestCase):
    def test_cycle(self):
        with tempfile.TemporaryDirectory() as d:
            etat = {}
            ecrire(d, 1, 11, 5)
            m = SC.verifier(d, T0, etat)
            self.assertEqual(len(m), 1)
            self.assertIn('Feuilles de match', m[0])
            self.assertIn('11 h (seuil 6 h)', m[0])
            self.assertEqual(SC.verifier(d, T0 + dt.timedelta(hours=1), etat), [])          # pas de spam
            m = SC.verifier(d, T0 + dt.timedelta(hours=6), etat)                            # rappel 6 h plus tard
            self.assertTrue(any('Feuilles de match' in x for x in m))
            self.assertTrue(any('Pronostics du Lab' in x for x in m))                     # 7 h > 4 h : en retard aussi
            ecrire(d, -5.5, -5.5, 5)                                                       # tout frais à T0 + 6 h
            m = SC.verifier(d, T0 + dt.timedelta(hours=6), etat)
            self.assertEqual(sorted(x.split(' :')[0] for x in m),
                             ['✅ Feuilles de match (résultats, stats, point par point)', '✅ Pronostics du Lab'])
            self.assertEqual(SC.verifier(d, T0 + dt.timedelta(hours=6), etat), [])

    def test_fichier_absent(self):
        with tempfile.TemporaryDirectory() as d:
            m = SC.verifier(d, T0, {})
            self.assertEqual(len(m), 3)
            self.assertIn('inconnu', m[0])


if __name__ == '__main__':
    unittest.main()
