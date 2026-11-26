"""26/11/2026 (paquet 463) : la pastille « Match fiable / standard / fragile » est retirée (elle contredisait la note de
fiabilité mesurée match par match, qui intègre déjà les mêmes critères avec leur poids réel)."""
import datetime as dt
import os
import sys
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
import desaccords_du_jour as D  # noqa: E402
import vitrine as V  # noqa: E402


class PastilleRetiree(unittest.TestCase):
    def test_vitrine_sans_type_match(self):
        self.assertFalse(hasattr(V, 'type_de_match'))
        src = open(os.path.join(ICI, '..', 'simulateur', 'vitrine.py'), encoding='utf-8').read()
        self.assertNotIn("'type_match'", src)

    def test_page_sans_pastille(self):
        page = open(os.path.join(ICI, '..', 'algo', 'index.html'), encoding='utf-8').read()
        for mot in ('rendType', 'typem', 'type_match', 'Match fragile', 'Match fiable'):
            self.assertNotIn(mot, page)

    def test_desaccords_niveau_de_la_note(self):
        self.assertEqual(D.niveau_fiabilite({'fiabilite': {'niveau': 'solide', 'note': 95}}), 'solide')
        self.assertEqual(D.niveau_fiabilite({}), 'inconnu')
        x = {'heure': '12:00', 'circuit': 'CH', 'tournoi': 'T', 'home': 'A Un', 'away': 'B Deux', 'p_algo': .6,
             'p_pin': .45, 'oppose': True, 'niveau': 'fragile'}
        txt = D.message([x], dt.datetime(2026, 11, 26, 8, tzinfo=dt.timezone.utc))
        self.assertIn('🟠', txt)
        self.assertIn('fiabilité fragile', txt)
        self.assertNotIn('match fragile', txt)


if __name__ == '__main__':
    unittest.main()
