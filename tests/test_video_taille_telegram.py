"""Vidéo du jour, paquet 291 (19/11/2026) : run rouge, « Telegram fr : HTTP 413 » — la vidéo 3D faisait 73,6 Mo, Telegram
refuse au-delà de 50 Mo. Au-dessus de 48 Mo elle est réencodée au débit qui la fait tenir ; le paquet 288 (échelle 1)
est retiré pour la définition comme le prévoyait sa règle (run de 65 min, au-delà de 60)."""
import importlib.util
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
SCRIPT = RACINE / 'scripts' / 'video_simulation.py'
SRC = SCRIPT.read_text(encoding='utf-8')


def module():
    spec = importlib.util.spec_from_file_location('video_simulation_t', SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TailleTelegram(unittest.TestCase):
    def test_plafond_appele(self):
        self.assertIn('TAILLE_MAX = 48_000_000', SRC)
        self.assertIn('        plafonner(mp4, duree)\n', SRC)
        self.assertLess(SRC.index('        plafonner(mp4, duree)\n'), SRC.index('print(f"Vidéo : {mp4} ({os.path.getsize(mp4) / 1e6:.1f} Mo, {duree:.1f} s'))

    def test_petite_video_intacte(self):
        m = module()
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            f.write(b'0' * 1000)
        try:
            self.assertFalse(m.plafonner(f.name, 10.0))
        finally:
            os.remove(f.name)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'ffmpeg absent')
    def test_reencodage_sous_la_limite(self):
        m = module()
        d = tempfile.mkdtemp()
        try:
            v = os.path.join(d, 'v.mp4')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=320x568:rate=25:duration=4',
                            '-f', 'lavfi', '-i', 'sine=frequency=440:duration=4', '-c:v', 'libx264', '-crf', '0', '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac', '-shortest', v], check=True)
            limite = 400_000
            self.assertGreater(os.path.getsize(v), limite)
            self.assertTrue(m.plafonner(v, 4.0, limite=limite, son_kbps=130))
            self.assertLessEqual(os.path.getsize(v), limite)
            sortie = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', v],
                                    capture_output=True, text=True).stdout.split()
            self.assertEqual(sorted(sortie), ['audio', 'video'])
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
