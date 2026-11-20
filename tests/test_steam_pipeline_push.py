"""Paquet 286 (18/11/2026) : alerte Telegram « Verdicts en direct : pas de mise à jour depuis 36 h ». Le run du
18/11 avait bien calculé les verdicts, mais son unique push a été refusé (un autre workflow venait de pousser) et le
commit est parti avec la machine du run. Le push est maintenant retenté jusqu'à 6 fois."""
import unittest
from pathlib import Path

YML = (Path(__file__).resolve().parents[1] / '.github' / 'workflows' / 'steam_pipeline.yml').read_text(encoding='utf-8')


class PushRetente(unittest.TestCase):
    def test_six_essais_avec_synchro(self):
        bloc = YML[YML.index('- name: Commit résultats + journaux'):YML.index('- name: Verrou qualité')]
        self.assertIn('for essai in 1 2 3 4 5 6; do', bloc)
        self.assertIn('git fetch origin main', bloc)
        self.assertIn('git merge origin/main --no-edit', bloc)
        self.assertIn('sleep $((essai * 8))', bloc)
        self.assertNotIn('--force', bloc)
        self.assertNotIn('récupérable au prochain run', bloc)                  # c'était faux : la machine est effacée
        self.assertIn('ne sont PAS sur GitHub', bloc)
        self.assertIn('verdicts_direct.json', bloc)


if __name__ == '__main__':
    unittest.main()
