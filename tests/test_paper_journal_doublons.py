"""Journaux de suivi : plus de position en double quand l'horaire d'un match bouge (paquet 306, 20/11/2026)."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'scripts'))
import paper_journal as PJ  # noqa: E402

SRC = (RACINE / 'scripts' / 'paper_journal.py').read_text(encoding='utf-8')


def pos(i, uid, book='bet365', palier=5, status='SETTLED', pnl=-1.0, won=False, clv=5.0):
    return {'id': f'{uid}@{i}|{book}|{palier}', 'uid': uid, 'book': book, 'palier': palier, 'status': status,
            'pnl': pnl, 'won': won, 'clv_pin': clv, 'clv_book': clv}


class Doublons(unittest.TestCase):
    def test_garde_la_premiere(self):
        T = {}
        for i, t in enumerate([pos(1, 'm1'), pos(2, 'm1'), pos(3, 'm1', book='bwin'), pos(4, 'm2', status='OPEN'),
                               pos(5, 'm2', status='OPEN'), pos(6, 'm1', palier=8)]):
            T[t['id']] = t
        self.assertEqual(PJ.marquer_doublons(T), 2)
        st = [t['status'] for t in T.values()]
        self.assertEqual(st, ['SETTLED', 'DOUBLON', 'SETTLED', 'OPEN', 'DOUBLON', 'SETTLED'])
        self.assertEqual(T['m1@2|bet365|5']['statut_avant_doublon'], 'SETTLED')
        self.assertEqual(PJ.marquer_doublons(T), 0)                       # idempotent

    def test_bilan_une_position_par_match(self):
        T = {t['id']: t for t in [pos(1, 'm1', pnl=2.0, won=True), pos(2, 'm1', book='bwin', pnl=2.1, won=True),
                                  pos(3, 'm2', pnl=-1.0)]}
        f = io.StringIO()
        with redirect_stdout(f):
            PJ.summary(T)
        self.assertIn('UNE POSITION PAR MATCH : 2 matchs | ROI +50.00% / mise', f.getvalue())

    def test_forward_ne_rouvre_pas(self):
        self.assertIn("n_doublons = marquer_doublons(trades)", SRC)
        self.assertIn("deja = {cle_position(t) for t in trades.values() if t.get('status') != 'DOUBLON'}", SRC)
        self.assertIn("(uid, sig['book'], int(sig['thr'] * 100)) in deja", SRC)
        self.assertLess(SRC.index('n_doublons = marquer_doublons(trades)'), SRC.index('SEUIL_ABANDON_JOURS = 7'))


if __name__ == '__main__':
    unittest.main()
