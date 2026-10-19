"""Regressions prematch : zero requete reseau, aucune cote in-play envoyee."""
import datetime as dt
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'scripts'))
import prematch_guard as pg

NOW = dt.datetime(2026, 10, 19, 10, 0, tzinfo=dt.timezone.utc)


def iso(minutes=0):
    return (NOW + dt.timedelta(minutes=minutes)).isoformat().replace('+00:00', 'Z')


def row(starts_in=120, last_quote=-5, uid='2026-10-19_ana_mila'):
    return {
        'uid': uid, 'book': 'pinnacle', 'home': 'Ana', 'away': 'Mila',
        'commence_time': iso(starts_in),
        'home_curve': [[iso(-80), 2.1], [iso(last_quote), 1.8]],
        'away_curve': [[iso(-80), 1.7], [iso(last_quote), 2.0]],
    }


def fixture(starts_in=120, status=None):
    obj = {'id': 'id_demo', 'home_team': 'Ana', 'away_team': 'Mila', 'commence_time': iso(starts_in)}
    if status:
        obj['status'] = status
    return obj


class GuardTest(unittest.TestCase):
    def test_match_sain_conserve(self):
        ok, reason, official = pg.safe_curve(row(), pg.make_index([fixture()]), set(), NOW)
        self.assertTrue(ok, reason)
        self.assertEqual(official, NOW + dt.timedelta(minutes=120))

    def test_debut_theorique_deja_passe(self):
        ok, *_ = pg.safe_curve(row(starts_in=-10), pg.make_index([fixture(-10)]), set(), NOW)
        self.assertFalse(ok)

    def test_aucune_marge_les_dernieres_minutes_sont_autorisees(self):
        for mins in [1, 2, 5, 20, 44]:
            with self.subTest(mins=mins):
                ok, reason, *_ = pg.safe_curve(row(starts_in=mins), pg.make_index([fixture(mins)]), set(), NOW)
                self.assertTrue(ok, reason)

    def test_debut_exact_bloque(self):
        ok, reason, *_ = pg.safe_curve(row(starts_in=0), pg.make_index([fixture(0)]), set(), NOW)
        self.assertFalse(ok)
        self.assertIn('debut', reason)

    def test_une_seconde_avant_reste_autorisee(self):
        just_before = NOW + dt.timedelta(seconds=1)
        f = fixture(starts_in=1)
        f['commence_time'] = just_before.isoformat().replace('+00:00', 'Z')
        ok, reason, *_ = pg.safe_curve(row(starts_in=1), pg.make_index([f]), set(), NOW)
        self.assertTrue(ok, reason)

    def test_statut_live_ou_annule_bloque(self):
        for status in ['live', 'in_play', 'finished', 'cancelled', 'walkover', 'postponed']:
            with self.subTest(status=status):
                ok, *_ = pg.safe_curve(row(), pg.make_index([fixture(status=status)]), set(), NOW)
                self.assertFalse(ok)

    def test_horaire_corrige_plus_tot_mais_toujours_a_venir(self):
        ok, reason, official = pg.safe_curve(row(starts_in=160), pg.make_index([fixture(starts_in=15)]), set(), NOW)
        self.assertTrue(ok, reason)
        self.assertEqual(official, NOW + dt.timedelta(minutes=15))

    def test_horaire_corrige_plus_tot_et_deja_commence(self):
        ok, *_ = pg.safe_curve(row(starts_in=160), pg.make_index([fixture(starts_in=-1)]), set(), NOW)
        self.assertFalse(ok)

    def test_horaire_reportee_valide_si_pas_de_cote_suspecte(self):
        ok, why, official = pg.safe_curve(row(starts_in=120), pg.make_index([fixture(180)]), set(), NOW)
        self.assertTrue(ok, why)
        self.assertEqual(official, NOW + dt.timedelta(minutes=180))

    def test_report_apres_ancien_debut_exclu(self):
        ok, *_ = pg.safe_curve(row(starts_in=-5), pg.make_index([fixture(240)]), set(), NOW)
        self.assertFalse(ok)

    def test_pari_regle_bloque(self):
        ok, *_ = pg.safe_curve(row(), pg.make_index([fixture()]), {'2026-10-19_ana_mila'}, NOW)
        self.assertFalse(ok)

    def test_pas_de_fixture_ou_ambiguite_bloque(self):
        for matches in ([], [fixture(), fixture(180)]):
            ok, *_ = pg.safe_curve(row(), pg.make_index(matches), set(), NOW)
            self.assertFalse(ok)

    def test_point_apres_debut_bloque(self):
        ok, *_ = pg.safe_curve(row(starts_in=60, last_quote=70), pg.make_index([fixture(60)]), set(), NOW)
        self.assertFalse(ok)

    def test_courbe_trop_vieille_bloque(self):
        ok, *_ = pg.safe_curve(row(last_quote=-60), pg.make_index([fixture()]), set(), NOW)
        self.assertFalse(ok)

    def test_pas_de_donnees_recentes_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'matches_oddspapi.json').write_text(json.dumps([fixture()]), encoding='utf-8')
            p = root / 'book_curves_live.jsonl'
            p.write_text(json.dumps(row()) + '\n', encoding='utf-8')
            summary = pg.filter_all(root, now=NOW, curve_paths=['book_curves_live.jsonl'])
            self.assertFalse(summary['snapshot_recent'])
            self.assertEqual(p.read_text(), '')

    def test_conserve_uniquement_valide_et_recalcule_horaire(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / 'matches_oddspapi.json').write_text(json.dumps([fixture(180)]), encoding='utf-8')
            (root / 'matches_oddspapi_meta.json').write_text(json.dumps({'last_write': iso(-5)}), encoding='utf-8')
            p = root / 'book_curves_live.jsonl'
            stranger = row(120, uid='2026-10-19_other_match')
            stranger['home'] = 'Other'
            p.write_text(json.dumps(row(120)) + '\n' + json.dumps(stranger) + '\n', encoding='utf-8')
            summary = pg.filter_all(root, now=NOW, curve_paths=['book_curves_live.jsonl'])
            self.assertTrue(summary['snapshot_recent'])
            lines = [json.loads(x) for x in p.read_text().splitlines()]
            self.assertEqual(len(lines), 1)  # fixture inconnue eliminee
            self.assertTrue(all(x['commence_time'] == iso(180) for x in lines))

    def test_source_stale_bloque(self):
        self.assertFalse(pg.source_fresh({'last_write': iso(-50)}, NOW))
        self.assertTrue(pg.source_fresh({'last_write': iso(-10)}, NOW))


if __name__ == '__main__':
    unittest.main()
