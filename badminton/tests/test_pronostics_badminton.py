"""520 : pronostics du badminton — données factices (aucun accès réseau, aucun script de scripts/)."""
import datetime as dt
import json
import os
import shutil
import sys
import tempfile
import unittest

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..'))
sys.path.insert(0, ICI)
import elo_badminton as EB  # noqa: E402
import etude_etape4_badminton as S4  # noqa: E402
import pronostics_badminton as P  # noqa: E402
from test_etude_elo_badminton import ecrire_monde  # noqa: E402

P.ligne_api = lambda e: e                    # le faux client renvoie déjà des lignes au format de l'historique
T0 = dt.datetime(2023, 9, 1, 9, tzinfo=dt.timezone.utc)


def ligne(i, t, h, a, tournoi='Open Factice (SS), MS', statut='notstarted', g=0, manches=None, detail=None):
    r = {'id': i, 't': int(t.timestamp()), 'ligue': 'International', 'tournoi': tournoi, 'tournoi_id': 1,
         'h': list(h), 'a': list(a), 'g': g, 'manches': manches or [], 'statut': statut}
    if detail:
        r['detail'] = detail
    return r


class Client:
    def __init__(self, L):
        self.L, self.n = L, 0

    def get(self, chemin):
        self.n += 1
        return 200, {'events': [dict(r, startTimestamp=r['t']) for r in self.L]}


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp()
        ecrire_monde(cls.dir, jours=420, debut=dt.date(2022, 7, 1))
        cls.H, _ = EB.lire(cls.dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir)

    def setUp(self):
        self.coffre = tempfile.mkdtemp()
        self.cf = P.CoffreLocal(self.coffre)

    def tearDown(self):
        shutil.rmtree(self.coffre)

    def lire(self, cle):
        return json.loads(self.cf.get(cle))

    def test_meme_elo_que_l_etude(self):
        M = self.H[:3000]
        attendu = S4.rejouer(M, *P.REGLAGE)
        mod = P.Modele([])
        for m, p in zip(M, attendu):
            ch, cb = P.camps(m)
            self.assertAlmostEqual(mod.predire(ch, cb)['p_h'], round(p, 4), places=6)
            mod.ajouter([m])

    def test_passages(self):
        J = [ligne(1, T0 + dt.timedelta(hours=3), (1, 'Joueur 1'), (2, 'Joueur 2')),
             ligne(2, T0 + dt.timedelta(hours=4), (201, 'Joueur 201 / Joueur 201b'), (202, 'Joueur 202 / Joueur 202b'),
                   tournoi='Open Factice (SS), MD'),
             ligne(3, T0 + dt.timedelta(hours=5), (3, 'Joueur 3'), (4, 'Joueur 4')),
             ligne(4, T0 - dt.timedelta(minutes=5), (5, 'Joueur 5'), (6, 'Joueur 6'), statut='inprogress')]
        c = Client(J)
        r = P.passage(self.dir, c, self.cf, maintenant=T0, journal=lambda x: None)
        self.assertTrue(r['publie'])
        self.assertEqual(c.n, 3)                                    # veille non collectée, jour, lendemain
        plein, libre = self.lire(P.CLE_SITE), self.lire(P.CLE_LIBRE)
        self.assertEqual(sorted(m['id'] for m in plein['matchs']), [1, 2, 3])
        self.assertEqual(sum(m['offert'] for m in plein['matchs']), 1)
        self.assertEqual({m['epreuve'] for m in plein['matchs']}, {'simple messieurs', 'double messieurs'})
        for m in libre['matchs']:
            if not m.get('offert'):
                self.assertTrue(m['verrou'])
                self.assertNotIn('p_h', m)
        p1 = self.lire(P.CLE_ETAT)['matchs']['1']['p_h']
        # 2e passage : 1 commencé (figé), 2 terminé (jugé), 3 abandon (ni bilan ni verdict)
        T1 = T0 + dt.timedelta(hours=6)
        J[0] = dict(J[0], statut='inprogress', manches=[[21, 15]])
        J[1] = dict(J[1], statut='finished', g=2, manches=[[15, 21], [21, 19], [18, 21]])
        J[2] = dict(J[2], statut='finished', g=1, manches=[[21, 3], [5, 2]], detail='Retired')
        P.passage(self.dir, Client(J), self.cf, maintenant=T1, journal=lambda x: None)
        e = self.lire(P.CLE_ETAT)
        self.assertEqual(e['matchs']['1']['p_h'], p1)
        x2 = e['matchs']['2']
        self.assertTrue(x2['juge'])
        self.assertEqual(x2['bon'], x2['p_h'] < 0.5)
        self.assertEqual(e['matchs']['3']['statut'], 'annule')
        self.assertEqual(e['bilan']['tout']['matchs'], 1)
        self.assertEqual(e['bilan']['double messieurs']['matchs'], 1)
        arch = self.cf.get(P.CLE_ARCHIVE.format(mois='2023-09')).decode().splitlines()
        self.assertEqual([json.loads(l)['id'] for l in arch], [2])
        libre = self.lire(P.CLE_LIBRE)
        un = next(m for m in libre['matchs'] if m['id'] == 1)
        self.assertIn('p_h', un)                                    # commencé : le % est public
        self.assertNotIn(3, [m['id'] for m in libre['matchs']])
        # 3e passage : rien compté deux fois
        P.passage(self.dir, Client(J), self.cf, maintenant=T1 + dt.timedelta(hours=1), journal=lambda x: None)
        self.assertEqual(self.lire(P.CLE_ETAT)['bilan']['tout']['matchs'], 1)

    def test_ecritures_seulement_au_coffre(self):
        avant = sorted(os.listdir(os.path.join(ICI, '..')))
        P.passage(self.dir, Client([ligne(1, T0 + dt.timedelta(hours=2), (1, 'Joueur 1'), (2, 'Joueur 2'))]), self.cf,
                  maintenant=T0, journal=lambda x: None)
        self.assertEqual(sorted(os.listdir(os.path.join(ICI, '..'))), avant)
        cles = sorted(os.path.relpath(os.path.join(d, f), self.coffre) for d, _, fs in os.walk(self.coffre) for f in fs)
        self.assertEqual(cles, sorted([P.CLE_ETAT, P.CLE_SITE, P.CLE_LIBRE]))
        self.assertTrue(P.CLE_ETAT.startswith('prive/'))

    def test_journal_sans_nom(self):
        L = []
        P.passage(self.dir, Client([ligne(1, T0 + dt.timedelta(hours=2), (1, 'Joueur 1'), (2, 'Joueur 2'))]), self.cf,
                  maintenant=T0, journal=L.append)
        self.assertNotIn('Joueur', '\n'.join(L))

    def test_reponse_manquante(self):
        class Panne:
            def get(self, chemin):
                return 500, None
        self.assertFalse(P.passage(self.dir, Panne(), self.cf, maintenant=T0, journal=lambda x: None)['publie'])
        self.assertIsNone(self.cf.get(P.CLE_SITE))


if __name__ == '__main__':
    unittest.main()
