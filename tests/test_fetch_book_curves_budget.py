"""27/10/2026 : courbes par budget — tous les matchs, plus anciens d'abord, niveau 1 avant niveau 2,
« book ne cote pas » mémorisé, arrêt quand le quota de la capture est menacé."""
import datetime as dt
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import fetch_book_curves as fb  # noqa: E402

NOW = dt.datetime(2026, 10, 28, 1, 0)


def started(n):
    return [(f"2026-10-{14 + i:02d}_a_b", {}, f"id{i}", dt.datetime(2026, 10, 14 + i, 12)) for i in range(n)]


class Plan(unittest.TestCase):
    BOOKS = ['pinnacle', 'bet365', 'tipico']

    def test_niveau1_pour_tous_les_matchs_avant_le_niveau2(self):
        p = fb.plan(started(3), set(), {}, self.BOOKS, NOW, niveau1=['pinnacle', 'bet365'])
        books = [x[4] for x in p]
        self.assertEqual(books[:6], ['pinnacle', 'bet365'] * 3)
        self.assertEqual(books[6:], ['tipico'] * 3)

    def test_plus_ancien_d_abord_pinnacle_en_tete(self):
        p = fb.plan(list(reversed(started(3))), set(), {}, self.BOOKS, NOW, niveau1=self.BOOKS)
        self.assertEqual([x[0] for x in p[:3]], ["2026-10-14_a_b"] * 3)
        self.assertEqual(p[0][4], 'pinnacle')

    def test_deja_recupere_jamais_redemande(self):
        s = started(1)
        p = fb.plan(s, {(s[0][0], 'pinnacle')}, {}, self.BOOKS, NOW, niveau1=self.BOOKS)
        self.assertNotIn('pinnacle', [x[4] for x in p])

    def test_absence_redemandee_une_fois_apres_24h(self):
        s = started(1)
        k = f"{s[0][0]}|bet365"
        recent = {k: {'essais': 1, 'dernier': (NOW - dt.timedelta(hours=3)).isoformat()}}
        vieux = {k: {'essais': 1, 'dernier': (NOW - dt.timedelta(hours=30)).isoformat()}}
        epuise = {k: {'essais': 2, 'dernier': (NOW - dt.timedelta(days=5)).isoformat()}}
        books = lambda a: [x[4] for x in fb.plan(s, set(), a, self.BOOKS, NOW, niveau1=self.BOOKS)]
        self.assertNotIn('bet365', books(recent))
        self.assertIn('bet365', books(vieux))
        self.assertNotIn('bet365', books(epuise))


class Quota(unittest.TestCase):
    def tearDown(self):
        fb.ov.QUOTA.clear()

    def test_marge_reserve_la_capture(self):
        fb.ov.QUOTA.update({'remaining': 20000, 'reset_s': 10 * 86400})
        self.assertEqual(fb.marge_quota(1100), 20000 - 11000)
        fb.ov.QUOTA.update({'remaining': 5000})
        self.assertLess(fb.marge_quota(1100), 0)

    def test_quota_inconnu_avant_le_premier_appel(self):
        self.assertIsNone(fb.marge_quota(1100))


if __name__ == '__main__':
    unittest.main()
