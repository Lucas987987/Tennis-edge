"""Livraison 104 (29/10/2026) : poids propres ATP / WTA (même règle que les Challenger) et sauvegarde du dépôt dans R2."""
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import os
import random
import sys
import tarfile
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', 'simulateur'))
sys.path.insert(0, os.path.join(ICI, '..', 'scripts'))
sys.path.insert(0, ICI)

import entrainement_progressif as EP  # noqa: E402
import backtest_match_simule as BMS  # noqa: E402

J0, LIM = dt.date(2026, 6, 1), dt.date(2026, 9, 1)
sg = lambda z: 1 / (1 + math.exp(-z))


def hors(circuit_sim_meilleure, n=2400, graine=3):
    rnd, H = random.Random(graine), []
    for k in range(n):
        c = ('ATP', 'WTA', 'CH')[k % 3]
        z = rnd.gauss(0, 1.2)
        bs, be = (0.2, 1.2) if c == circuit_sim_meilleure else (0.9, 0.6)
        zs, ze = z + rnd.gauss(0, bs), z + rnd.gauss(0, be)
        y = rnd.random() < sg(z)
        f = (lambda p: p) if y else (lambda p: 1 - p)
        H.append(({'circuit': c, 'jour': J0 + dt.timedelta(days=k * 140 // n)}, f(sg(zs)), f(sg(ze))))
    return H


class PoidsCircuit(unittest.TestCase):
    def test_atp_adoptes_quand_la_simulation_y_voit_mieux(self):
        r = EP.poids_circuit(hors('ATP'), {'elo': 0.7, 'simulation': 0.3}, LIM, BMS.ajuster_poids, 'ATP')
        self.assertTrue(r['adopte'], r['raison'])
        self.assertGreater(r['poids']['simulation'], r['poids']['elo'])
        self.assertIn('ATP des 6 dernières semaines', r['raison'])

    def test_challenger_inchange(self):
        H = hors('CH')
        a = EP.poids_challenger(H, {'elo': 0.7, 'simulation': 0.3}, LIM, BMS.ajuster_poids)
        b = EP.poids_circuit(H, {'elo': 0.7, 'simulation': 0.3}, LIM, BMS.ajuster_poids, 'CH')
        self.assertEqual(a, b)
        self.assertIn('Challenger des 6 dernières semaines', a['raison'])

    def test_pas_assez(self):
        r = EP.poids_circuit(hors('ATP', n=300), {'elo': 0.7, 'simulation': 0.3}, LIM, BMS.ajuster_poids, 'WTA')
        self.assertFalse(r['adopte'])
        self.assertIn('pas assez de matchs WTA', r['raison'])

    def test_application_et_chargement(self):
        import pronostics_du_jour as PJ
        PJ.AJUSTEMENTS.clear()
        PJ.AJUSTEMENTS.update({'poids_WTA': {'elo': 0.2, 'simulation': 0.8}})
        try:
            self.assertAlmostEqual(PJ.ajuster_combinaison(0.6, 'WTA', 0.7, 0.5, 200, 200), sg(0.2 * math.log(0.7 / 0.3)), places=6)
            self.assertEqual(PJ.ajuster_combinaison(0.6, 'ATP', 0.7, 0.5, 200, 200), 0.6)      # ATP non adopté
        finally:
            PJ.AJUSTEMENTS.clear()
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'simulateur'))
            with open(os.path.join(d, 'simulateur', 'choix_simulation.json'), 'w') as f:
                json.dump({'poids_ATP': {'adopte': True, 'poids': {'elo': 0.5, 'simulation': 0.5}},
                           'poids_WTA': {'adopte': False, 'poids': {'elo': 1, 'simulation': 0}}}, f)
            self.assertEqual(PJ.charger_ajustements(d), {'poids_ATP': {'elo': 0.5, 'simulation': 0.5}})


class FauxR2:
    def __init__(self):
        self.o, self.puts = {}, []

    def put(self, key, data, **_):
        self.o[key] = bytes(data)
        self.puts.append(key)
        return 'e'

    def get(self, key):
        return self.o.get(key)


class Sauvegarde(unittest.TestCase):
    def setUp(self):
        import sauvegarde_depot as SD
        self.SD = SD

    def test_emplacements(self):
        j = dt.date(2026, 10, 29)                  # semaine ISO 44 → hebdo-0 ; octobre → mensuel-1
        self.assertEqual(self.SD.emplacements(j, {}), ['hebdo-0', 'mensuel-1'])
        self.assertEqual(self.SD.emplacements(j, {'mensuel-1': {'date': '2026-10-04'}}), ['hebdo-0'])
        self.assertEqual(self.SD.emplacements(j, {'mensuel-1': {'date': '2026-07-05'}}), ['hebdo-0', 'mensuel-1'])
        semaines = {self.SD.emplacements(j + dt.timedelta(days=7 * k), {})[0] for k in range(12)}
        self.assertEqual(semaines, {'hebdo-0', 'hebdo-1', 'hebdo-2', 'hebdo-3'})   # place bornée

    def _depot(self, d):
        for rel, txt in (('a.json', '{}'), ('simulateur/x.py', 'x'), ('parts/kx_ticks_2026-10-28.jsonl.gz', 'gros'),
                         ('.git/config', 'secret?'), ('simulateur/__pycache__/x.pyc', 'c'), ('feuilles/parts/y.json', 'y')):
            os.makedirs(os.path.dirname(os.path.join(d, rel)) or d, exist_ok=True)
            with open(os.path.join(d, rel), 'w') as f:
                f.write(txt)

    def test_archive_sans_git_parts_ni_caches_et_stable(self):
        with tempfile.TemporaryDirectory() as d:
            self._depot(d)
            data, n = self.SD.archiver(d)
            with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as t:
                noms = sorted(t.getnames())
            self.assertEqual(noms, ['a.json', 'feuilles/parts/y.json', 'simulateur/x.py'])
            self.assertEqual(n, 3)
            self.assertEqual(hashlib.sha256(self.SD.archiver(d)[0]).digest(), hashlib.sha256(data).digest())

    def test_sauvegarder_relit_et_indexe(self):
        r2 = FauxR2()
        with tempfile.TemporaryDirectory() as d:
            self._depot(d)
            self.assertEqual(self.SD.sauvegarder(d, r2=r2, jour=dt.date(2026, 10, 29), commit='abc123'), 0)
            idx = json.loads(r2.o['sauvegardes/depot/index.json'])
            self.assertEqual(set(idx), {'hebdo-0', 'mensuel-1'})
            self.assertEqual(idx['hebdo-0']['sha256'], hashlib.sha256(r2.o['sauvegardes/depot/hebdo-0.tar.gz']).hexdigest())
            self.assertEqual(self.SD.sauvegarder(d, r2=r2, jour=dt.date(2026, 11, 5), commit='def'), 0)
            self.assertEqual(set(json.loads(r2.o['sauvegardes/depot/index.json'])), {'hebdo-0', 'hebdo-1', 'mensuel-1', 'mensuel-2'})
            sortie = os.path.join(d, 'r.tar.gz')
            self.assertEqual(self.SD.telecharger('hebdo-1', sortie, r2=r2), 0)
            r2.o['sauvegardes/depot/hebdo-1.tar.gz'] = b'abime'
            self.assertEqual(self.SD.telecharger('hebdo-1', sortie, r2=r2), 1)

    def test_relecture_differente_echoue(self):
        class Abime(FauxR2):
            def get(self, key):
                return b'x' if key.endswith('.tar.gz') else super().get(key)
        with tempfile.TemporaryDirectory() as d:
            self._depot(d)
            self.assertEqual(self.SD.sauvegarder(d, r2=Abime(), jour=dt.date(2026, 10, 29)), 1)

    def test_workflow(self):
        with open(os.path.join(ICI, '..', '.github', 'workflows', 'sauvegarde_depot.yml'), encoding='utf-8') as f:
            w = f.read()
        self.assertIn('scripts/sauvegarde_depot.py', w)
        self.assertIn('secrets.R2_SECRET_ACCESS_KEY', w)
        self.assertNotIn('echo "$R2', w)


if __name__ == '__main__':
    unittest.main()
