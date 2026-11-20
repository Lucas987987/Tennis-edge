"""Résumé 3D d'un vrai match terminé (paquet 308, 20/11/2026)."""
import datetime as dt
import gzip
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'scripts'))
import resume_match as R  # noqa: E402

T0 = dt.datetime(2026, 11, 1, 18, 30, tzinfo=dt.timezone.utc)
UID = '2026-11-01_ana_bo_cia_do'


def jeu(set_, n, srv, pts):
    return [set_, n, srv, pts]


def match_6_0_6_0(gagnant='H'):
    """Deux sets 6-0 du joueur de la feuille « gagnant », service alterné, chaque jeu blanc."""
    jeux = []
    for s in (1, 2):
        for n in range(1, 7):
            jeux.append(jeu(s, n, 1 if (n + s) % 2 == 0 else 2, gagnant * 4))
    return jeux


class Construire(unittest.TestCase):
    def preparer(self, feuille, points, circuit='ATP', home='Ana Bo', away='Cia Do'):
        d = Path(tempfile.mkdtemp())
        for x in ('feuilles', 'feuilles_points', 'algo'):
            (d / x).mkdir()
        with gzip.open(d / 'feuilles' / '2026-11-01.jsonl.gz', 'wt', encoding='utf-8') as f:
            f.write(json.dumps(feuille) + '\n')
        if points is not None:
            with gzip.open(d / 'feuilles_points' / '2026-11-01.jsonl.gz', 'wt', encoding='utf-8') as f:
                f.write(json.dumps({'id': 7, 'jeux': points}) + '\n')
        D = {'matchs': [{'uid': UID, 'debut_utc': T0.isoformat(), 'home': home, 'away': away, 'circuit': circuit}]}
        (d / 'algo' / 'donnees.json').write_text(json.dumps(D), encoding='utf-8')
        return d

    def feuille(self, h='Ana Bo', a='Cia Do', sh=(6, 6), sa=(0, 0), v=1, texte='Ended'):
        return {'id': 7, 'jour': '2026-11-01', 'debut': T0.timestamp(), 'home': {'nom': h}, 'away': {'nom': a},
                'score_home': {'sets': list(sh)}, 'score_away': {'sets': list(sa)}, 'vainqueur': v,
                'statut': {'texte': texte, 'type': 'finished'}}

    def test_meme_sens(self):
        d = self.preparer(self.feuille(), match_6_0_6_0('H'))
        r = R.construire(str(d), UID)
        self.assertEqual(r['trace'], '0' * 48)
        self.assertEqual((r['sets'], r['vainqueur'], r['score'], r['points']), ([[6, 0], [6, 0]], 0, '6-0 6-0', 48))
        self.assertEqual(r['premier'], 0)          # 1er jeu servi par le joueur à domicile de la feuille (= Ana Bo)

    def test_sens_inverse(self):
        # la feuille met Cia Do à domicile ; Cia Do gagne 6-0 6-0 → sur le site (Ana Bo d'abord) : 0-6 0-6, vainqueur 1
        d = self.preparer(self.feuille(h='Cia Do', a='Ana Bo'), match_6_0_6_0('H'))
        r = R.construire(str(d), UID)
        self.assertEqual(r['trace'], '1' * 48)
        self.assertEqual((r['sets'], r['vainqueur'], r['score']), ([[0, 6], [0, 6]], 1, '6-0 6-0'))
        self.assertEqual(r['premier'], 1)          # Cia Do (domicile sur la feuille) sert d'abord ; 2e sur le site

    def test_refus(self):
        cas = [
            (dict(circuit='ITF'), self.feuille(), match_6_0_6_0(), 'ITF'),
            ({}, self.feuille(texte='Retired', v=1), match_6_0_6_0(), 'non terminé'),
            ({}, self.feuille(), None, 'point par point'),
            ({}, self.feuille(), match_6_0_6_0()[:-1], 'incomplet'),
            ({}, self.feuille(h='Eve Fa', a='Gil Ha'), match_6_0_6_0(), 'feuille'),
        ]
        for opts, fe, pts, motif in cas:
            with self.subTest(motif=motif):
                d = self.preparer(fe, pts, **opts)
                with self.assertRaises(ValueError) as e:
                    R.construire(str(d), UID)
                self.assertIn(motif, str(e.exception))

    def test_jeux_complets(self):
        J = R._jeu_complet
        self.assertTrue(J(list('HHHH'), False)); self.assertTrue(J(list('HHHAAAHAHH'), False))
        self.assertFalse(J(list('HHHHA'), False)); self.assertFalse(J(list('HHH'), False))
        self.assertTrue(J(list('HHHHAAHAAAHH'), True))            # 7-5
        self.assertTrue(J(list('HHHHHHAAAAAAHAHHH'), True))       # 10-7 (jeu décisif en 10 points)
        self.assertFalse(J(list('HHHHAAHAAAHHH'), True))          # 8-5 : un point de trop

    def test_jeu_decisif_point_en_double(self):
        # 6-6 puis jeu décisif 7-5 noté avec le dernier point en double (format TennisApi) : on l'enlève
        jeux = []
        for n in range(1, 13):
            jeux.append(jeu(1, n, 1 if n % 2 else 2, ('H' if n % 2 else 'A') * 4))
        jeux.append(jeu(1, 13, 1, 'HHHHAAHAAAHHH'))
        jeux += [jeu(2, n, 1 if n % 2 else 2, 'HHHH') for n in range(1, 7)]
        d = self.preparer(self.feuille(sh=(7, 6), sa=(6, 0)), jeux)
        r = R.construire(str(d), UID)
        self.assertEqual(r['points'], 12 * 4 + 12 + 6 * 4)
        self.assertEqual((r['sets'], r['score']), ([[7, 6], [6, 0]], '7-6 6-0'))
        # un jeu ordinaire trop long reste refusé
        jeux[0] = jeu(1, 1, 1, 'HHHHH')
        with self.assertRaises(ValueError):
            R.construire(str(self.preparer(self.feuille(sh=(7, 6), sa=(6, 0)), jeux)), UID)

    def test_vraies_stats(self):
        fe = self.feuille()
        fe['stats'] = {'ALL': {'aces': [5, None, 1, None], 'doubleFaults': [2, None, 4, None], 'pointsTotal': [60, None, 40, None],
                               'firstServeAccuracy': [30, 50, 27, 45], 'breakPointsScored': [3, None, 1, None],
                               'breakPointsSaved': [2, 3, 4, 7]}}
        r = R.construire(str(self.preparer(fe, match_6_0_6_0('H'))), UID)
        self.assertEqual(r['stats'], {'aces': [5, 1], 'df': [2, 4], 'pts': [60, 40], 'prem': [60, 60], 'bb': [[3, 7], [1, 3]]})
        fe2 = dict(fe, home={'nom': 'Cia Do'}, away={'nom': 'Ana Bo'})          # feuille dans l'autre sens
        r2 = R.construire(str(self.preparer(fe2, match_6_0_6_0('H'))), UID)
        self.assertEqual(r2['stats']['aces'], [1, 5])
        self.assertEqual(r2['stats']['bb'], [[1, 3], [3, 7]])
        self.assertIsNone(R.stats_reelles({}, 1))

    def test_main_ecrit_le_fichier(self):
        d = self.preparer(self.feuille(), match_6_0_6_0('H'))
        self.assertEqual(R.main(['x', UID, str(d)]), 0)
        self.assertEqual(json.loads((d / 'algo' / 'resume_match.json').read_text())['uid'], UID)
        self.assertEqual(R.main(['x', 'inconnu', str(d)]), 1)


class Branchements(unittest.TestCase):
    page = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')
    wf = (RACINE / '.github' / 'workflows' / 'video_resume.yml').read_text(encoding='utf-8')
    worker = (RACINE / 'workers' / 'algo' / 'worker.js').read_text(encoding='utf-8')
    video = (RACINE / 'scripts' / 'video_simulation.py').read_text(encoding='utf-8')

    def test_page(self):
        self.assertIn("Q.get('resume') === '1'", self.page)
        self.assertIn("fetch('resume_match.json'", self.page)
        self.assertIn('JSON.stringify(F.final.histo) !== JSON.stringify(RESUME.sets)', self.page)   # jamais un faux score
        self.assertIn('b-resume', self.page)
        # le résumé refuse l'ITF et ne passe que par la 3D
        bloc = self.page[self.page.index("Q.get('resume') === '1'"):][:900]
        self.assertIn('ITF', bloc)
        self.assertIn('G3D.disponible()', bloc)

    def test_textes_publics_propres(self):
        for cle in ('r_haut', 'r_vs', 'r_pied', 'r_fin_p'):
            for m in re.finditer(cle + r":\s*(?:\([^)]*\)\s*=>\s*)?[`'](.*?)[`']\s*,", self.page):
                self.assertNotRegex(m.group(1).lower(), r'march[eé]|cote|pinnacle|value|pari|bet\b|odds|market')
        self.assertGreaterEqual(self.page.count("r_haut:"), 2)       # FR et EN

    def test_worker_et_workflow(self):
        self.assertIn("corps.mode === 'resume'", self.worker)
        self.assertIn('video_resume.yml', self.worker)
        self.assertIn('workflow_dispatch', self.wf)
        self.assertIn('scripts/resume_match.py', self.wf)
        self.assertIn('/scripts/resultats_feuilles.py', self.wf)
        self.assertIn('/feuilles_points/', self.wf)
        self.assertIn('--resume', self.wf)
        self.assertIn('TELEGRAM_CHAT_ID', self.wf)
        self.assertNotIn('--adresse', self.wf)                       # jamais l'adresse du site dans la vidéo
        self.assertNotIn('upload-artifact', self.wf)
        self.assertNotIn('git push', self.wf)
        self.assertIn("'&resume=1' if a.resume", self.video)
        self.assertIn("'resume' if a.resume else 'simulation'", self.video)

    def test_fin_et_matin(self):
        self.assertIn('${RESUME && RESUME.stats ? statsReelles(RESUME.stats) : \'\'}', self.page)
        self.assertGreaterEqual(self.page.count('r_st:{'), 2)
        self.assertIn("cron: '12 6 * * *'", self.wf)
        self.assertIn("match_du_jour_veille", self.wf)
        self.assertIn('--uid "${{ steps.r.outputs.uid }}"', self.wf)


if __name__ == '__main__':
    unittest.main()
