"""Paquet 450 → 451 : la note Challenger par classe (paquet 450) est remplacée avant sa mise en route par la note mesurée
match par match (simulateur/note_par_match.py, tests dans tests/test_note_par_match.py)."""
import json
import sys
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / 'simulateur'))
import fiabilite as FI  # noqa: E402


class Remplacee(unittest.TestCase):
    def test_fichier_marque_retire(self):
        d = json.load(open(RACINE / 'simulateur' / 'note_v3_challenger.json', encoding='utf-8'))
        self.assertTrue(d['retire'])
        self.assertIn('note_par_match.json', d['remplace_par'])

    def test_note_v3_reste_celle_de_l_archive(self):
        FI._MODELE_CH.clear()
        m = {'circuit': 'CH', 'matchs_joues': [50, 400]}
        self.assertEqual(FI.note_v3(m), FI.note_v3(m, ancienne=True))

    def test_plus_lance_le_lundi(self):
        wf = (RACINE / '.github' / 'workflows' / 'pronostic.yml').read_text(encoding='utf-8')
        self.assertNotIn('python simulateur/note_v3_challenger.py', wf)
        self.assertIn('python simulateur/note_par_match.py . --telegram', wf)


if __name__ == '__main__':
    unittest.main()
