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
        old = fb.MAX_ESSAIS
        fb.MAX_ESSAIS = 2                     # mode « une seconde chance » (CURVES_MAX_ESSAIS=2)
        try:
            self.assertNotIn('bet365', books(recent))
            self.assertIn('bet365', books(vieux))
            self.assertNotIn('bet365', books(epuise))
        finally:
            fb.MAX_ESSAIS = old


class Quota(unittest.TestCase):
    def tearDown(self):
        fb.ov.QUOTA.clear()

    def test_marge_reserve_la_capture(self):
        fb.ov.QUOTA.update({'remaining': 20000, 'reset_s': 10 * 86400})
        self.assertEqual(fb.marge_quota(1100, plancher=0), 20000 - 11000)
        self.assertEqual(fb.marge_quota(1100, plancher=2000), 20000 - 11000 - 2000)
        fb.ov.QUOTA.update({'remaining': 5000})
        self.assertLess(fb.marge_quota(1100), 0)

    def test_quota_inconnu_avant_le_premier_appel(self):
        self.assertIsNone(fb.marge_quota(1100))


if __name__ == '__main__':
    unittest.main()


class Apprentissage(unittest.TestCase):
    def test_categories(self):
        self.assertEqual(fb.categorie('ATP Challenger Roanne'), 'Challenger')
        self.assertEqual(fb.categorie('WTA Beijing'), 'WTA')
        self.assertEqual(fb.categorie('WTA 125 Mumbai'), 'WTA 125')
        self.assertEqual(fb.categorie('ATP Tokyo'), 'ATP')

    def test_book_qui_ne_cote_jamais_un_type_est_saute(self):
        stats = {'winamax.fr|Challenger': [120, 0], 'winamax.fr|ATP': [100, 83], 'pinnacle|Challenger': [200, 0]}
        self.assertTrue(fb.exclu(stats, 'winamax.fr', 'Challenger'))
        self.assertFalse(fb.exclu(stats, 'winamax.fr', 'ATP'))
        self.assertFalse(fb.exclu(stats, 'pinnacle', 'Challenger'))        # Pinnacle jamais exclu
        self.assertFalse(fb.exclu({'x|ATP': [10, 0]}, 'x', 'ATP'))           # trop peu d'essais
        s = [("2026-10-20_a_b", {'tournament': 'ATP Challenger X'}, 'f', dt.datetime(2026, 10, 20, 12))]
        books = [x[4] for x in fb.plan(s, set(), {}, ['pinnacle', 'winamax.fr'], NOW, niveau1=['pinnacle'], stats=stats)]
        self.assertEqual(books, ['pinnacle'])

    def test_une_seule_tentative_par_defaut(self):
        s = started(1)
        a = {f"{s[0][0]}|bet365": {'essais': 1, 'dernier': (NOW - dt.timedelta(days=3)).isoformat()}}
        self.assertNotIn('bet365', [x[4] for x in fb.plan(s, set(), a, ['pinnacle', 'bet365'], NOW, niveau1=['pinnacle', 'bet365'])])


class ReserveMesuree(unittest.TestCase):
    def test_mesure_la_consommation_du_reste_du_projet(self):
        prec = {'quota_fin': {'remaining': 40000, 'a': '2026-10-22T02:00:00'}}
        r, c = fb.reserve_mesuree(prec, 39000, dt.datetime(2026, 10, 23, 2, 0), plancher=600)
        self.assertEqual(c, 1000)
        self.assertEqual(r, 1300)

    def test_plancher_et_renouvellement(self):
        prec = {'quota_fin': {'remaining': 800, 'a': '2026-10-19T02:00:00'}}
        self.assertEqual(fb.reserve_mesuree(prec, 49000, dt.datetime(2026, 10, 20, 2), plancher=600), (600, None))
        self.assertEqual(fb.reserve_mesuree({}, 49000, NOW, plancher=600), (600, None))
        low = {'quota_fin': {'remaining': 40000, 'a': '2026-10-22T02:00:00'}}
        self.assertEqual(fb.reserve_mesuree(low, 39900, dt.datetime(2026, 10, 23, 2), plancher=600)[0], 600)
