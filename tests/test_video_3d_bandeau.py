"""Vidéo 3D, paquet 287 (19/11/2026, Lucas : « il manque le bandeau en bas… reprendre les informations de ces stats…
le scénario doit coller à la réalité »). Comme la vidéo 2D : ligne de commentaire après chaque point, les 4 lignes
de l'algo (sans cote) cochées dès que le match simulé les atteint, et le pied « une parmi 20 000 » ; l'écran de fin
reprend ces lignes, ✓ ou ✗ selon le score final."""
import unittest
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / 'algo' / 'index.html').read_text(encoding='utf-8')
FILM = HTML[HTML.index('async function filmDuJour('):HTML.index('/* ───────────── carte de stats (?carte=1)')]


class Bandeau(unittest.TestCase):
    def test_memes_lignes_que_la_2d(self):
        self.assertIn("const k = m.lignes_algo; if (!k || RESUME) return [];", FILM)   # paquet 308 : pas de lignes dans le résumé d'un vrai match
        for cle in ("'total_plus_'", "'handicap_favori_'", "k.tie_break", "k.set_decisif"):
            self.assertIn(cle, FILM)

    def test_coherence_score_et_lignes(self):
        self.assertIn('etatLignes(x.apres, x.apres.fini)', FILM)                 # cochées au fil du match simulé
        self.assertIn("lignesFaites(F.final, true)", FILM)                        # bilan ✓ / ✗ à la fin
        self.assertIn("x.cle === 'hand' && fin", FILM)

    def test_commentaires_et_pied(self):
        for k in ("t('lg_set'", "t('lg_break'", "t('lg_sauve'", "t('lg_ace'", "t('lg_df'", "t('lg_ech'", "t('a_pied', nSim)"):
            self.assertIn(k, FILM)
        self.assertIn('FILM.dernier = { fin, frappes:', HTML)

    def test_rien_d_interdit(self):
        bas = FILM.lower()
        for mot in ('cote', 'pinnacle', 'march', 'value', 'adresse'):
            self.assertNotIn(mot, bas)


if __name__ == '__main__':
    unittest.main()
