"""Paquet 456 : « au moins un tie-break » — une seule valeur (corrigée) sur toute la fiche ; heure du calcul de chaque match
sur les images et les textes pour X (texte et images d'un même post venaient de deux calculs : Kicker – Moller du 25/11)."""
import datetime as dt
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import vitrine as V  # noqa: E402

H = (RACINE / 'algo' / 'index.html').read_text(encoding='utf-8')


class TieBreak(unittest.TestCase):
    def test_une_seule_valeur(self):
        self.assertIn('function tbMatch(m)', H)
        self.assertIn("case 'tb': return tbMatch(m);", H)
        self.assertIn("pc0(tbMatch(m))", H)
        self.assertNotIn("pc0(S.tiebreak)", H)
        self.assertNotIn("() => ({ p: Z.tb })", H)


class HeureDuCalcul(unittest.TestCase):
    def test_images_et_textes(self):
        self.assertIn('function calculDe(m)', H)
        self.assertEqual(H.count("${calculDe(m) ? ` · ${esc(calculDe(m))}` : ''}"), 2)       # deux images pour X
        self.assertEqual(H.count("🕒 ${calculDe(m)}"), 2)                                      # deux textes pour X

    def test_match_garde_garde_son_heure(self):
        m = dt.datetime(2026, 11, 25, 18, 0, tzinfo=dt.timezone.utc)
        ancien = {'matchs': [{'uid': 'k', 'debut': '2026-11-25T16:05:00+00:00', 'calcule_le': '2026-11-25T08:00:00Z'}]}
        L = V.garder_commences([{'uid': 'a', 'debut': '2026-11-25T20:00', 'calcule_le': '2026-11-25T17:00:00Z'}], ancien, m)
        self.assertEqual({x['uid']: x['calcule_le'] for x in L}, {'a': '2026-11-25T17:00:00Z', 'k': '2026-11-25T08:00:00Z'})

    def test_vitrine_pose_l_heure(self):
        src = (RACINE / 'simulateur' / 'vitrine.py').read_text(encoding='utf-8')
        self.assertIn("l_.setdefault('calcule_le', pron.get('genere_le'))", src)
        self.assertLess(src.index("l_.setdefault('calcule_le'"), src.index("lignes = garder_commences(lignes, ancien_doc, maintenant, racine)"))


if __name__ == '__main__':
    unittest.main()
