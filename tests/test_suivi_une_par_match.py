"""Lecture gelée « une position par match » (paquet 307, 20/11/2026)."""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'scripts'))
import suivi_une_par_match as S  # noqa: E402

SRC = (RACINE / 'scripts' / 'suivi_une_par_match.py').read_text(encoding='utf-8')
YML = (RACINE / '.github' / 'workflows' / 'suivi_une_par_match.yml').read_text(encoding='utf-8')
APRES = S.GEL.timestamp() + 86400


def journal(lignes):
    p = Path(tempfile.mkdtemp()) / 'j.jsonl'
    p.write_text(''.join(json.dumps(x) + '\n' for x in lignes), encoding='utf-8')
    return str(p)


def pos(uid, commence=APRES, status='SETTLED', pnl=1.0, clv=5.0, book='bet365'):
    return {'uid': uid, 'commence': commence, 'status': status, 'pnl': pnl, 'won': pnl > 0, 'clv_pin': clv, 'book': book}


class Gel(unittest.TestCase):
    def test_regle_figee(self):
        self.assertEqual(S.GEL, dt.datetime(2026, 11, 20, 15, 30, tzinfo=dt.timezone.utc))
        self.assertEqual((S.MIN_MATCHS, S.TIRAGES), (30, 4000))
        self.assertIn('RÈGLE ÉCRITE LE 20/11/2026 À 15 h 30 UTC, AVANT TOUT MATCH JUGÉ', SRC)
        self.assertIn('la CLV contre la clôture de référence est la SEULE validation', SRC)

    def test_premiere_position_apres_le_gel(self):
        j = journal([pos('avant', commence=S.GEL.timestamp() - 60), pos('m1', pnl=2.0), pos('m1', pnl=-1.0, book='bwin'),
                     pos('m2', status='OPEN'), pos('m2', pnl=-1.0), pos('m3', status='DOUBLON'), pos('m3', pnl=-1.0)])
        T = S.premieres(j)
        self.assertEqual([t['uid'] for t in T], ['m1', 'm3'])               # m2 : la 1re n'est pas réglée
        self.assertEqual(T[0]['pnl'], 2.0)

    def test_verdicts(self):
        self.assertIn('trop tôt', S.bilan([pos(f'm{i}') for i in range(29)])['verdict'])
        self.assertIn('CLV positive', S.bilan([pos(f'm{i}', clv=4 + i % 3) for i in range(30)])['verdict'])
        self.assertIn('non démontrée', S.bilan([pos(f'm{i}', clv=(-1) ** i * 3) for i in range(40)])['verdict'])
        self.assertEqual(S.bilan([])['matchs'], 0)

    def test_prive_et_hebdomadaire(self):
        self.assertIn("cron: '23 8 * * 1'", YML)
        self.assertIn('contents: read', YML)
        self.assertNotIn('git push', YML)
        self.assertIn('${{ secrets.TELEGRAM_CHAT_ID }}', YML)
        self.assertNotIn('TELEGRAM_PUBLIC', YML)


if __name__ == '__main__':
    unittest.main()
