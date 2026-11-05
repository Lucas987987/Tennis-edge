import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'simulateur'))
import pronostics_du_jour as P  # noqa: E402
import tableau_adoptions as TA  # noqa: E402


def _r(uid, debut, score, home='Alexander Zverev', away='Lorenzo Musetti'):
    return {'uid': uid, 'debut': debut, 'home': home, 'away': away, 'reel': {'gagnant': 'away', 'score': score}}


class TestDoublons(unittest.TestCase):
    def test_meme_match_sous_deux_uid(self):
        R = [_r('a', '2026-11-03T19:00', '6-7 2-6'), _r('b', '2026-11-04T10:00', '6-7 2-6'),
             _r('c', '2026-11-04T12:00', '6-3 6-4', 'Tommy Paul', 'Quentin Halys')]
        self.assertEqual([x['uid'] for x in P.dedoublonner(R)], ['b', 'c'])

    def test_deux_vrais_matchs_gardes(self):
        R = [_r('a', '2026-10-01T10:00', '6-7 2-6'), _r('b', '2026-11-04T10:00', '6-7 2-6'),
             _r('c', '2026-11-05T10:00', '6-1 6-1')]
        self.assertEqual(len(P.dedoublonner(R)), 3)


class TestTableau(unittest.TestCase):
    def test_message(self):
        txt = TA.message([{'quoi': 'âge', 'circuit': 'ATP', 'etat': '✅ en place', 'detail': 'x'}])
        self.assertIn('ATP · âge', txt)


if __name__ == '__main__':
    unittest.main()
