"""Workflows vidéo et cartes (05/11/2026, paquet 194) : plus d'apt, image figée, script d'installation présent."""
import os
import unittest

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
FLUX = ('video_simulation', 'bilan_match_du_jour', 'bilan_semaine')


class InstallerVideo(unittest.TestCase):
    def test_workflows_sans_apt(self):
        for f in FLUX:
            s = open(os.path.join(RACINE, '.github', 'workflows', f + '.yml'), encoding='utf-8').read()
            self.assertNotIn('apt-get', s, f)
            self.assertNotIn('--with-deps', s, f)
            self.assertIn('bash scripts/installer_video.sh', s, f)
            self.assertIn('/scripts/installer_video.sh', s, f)            # présent dans le checkout partiel
            self.assertIn('runs-on: ubuntu-24.04', s, f)

    def test_script(self):
        s = open(os.path.join(RACINE, 'scripts', 'installer_video.sh'), encoding='utf-8').read()
        self.assertIn('imageio-ffmpeg', s)
        self.assertIn('GITHUB_PATH', s)
        self.assertIn('timeout 360', s)                                   # apt seulement en secours, borné
        code = '\n'.join(l for l in s.splitlines() if not l.lstrip().startswith('#'))
        self.assertNotIn('--with-deps', code)
        self.assertNotIn('apt-get', code)


if __name__ == '__main__':
    unittest.main()
