#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
voix.py — la voix de l'arbitre de chaise dans la vidéo 3D (paquet 277, 18/11/2026).

Synthèse vocale Piper (logiciel libre, hors ligne), voix « fr_FR-tom-medium » et « en_GB-alan-medium », installées
par scripts/installer_video.sh dans ~/.cache/te_voix (fr.onnx, en.onnx). Ce ne sont pas des voix de vraies
personnes connues : des voix de synthèse génériques. Si Piper ou la voix manque, dire() renvoie None et la vidéo
sort sans voix (le reste de la bande-son ne change pas).
"""
import io
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

DOSSIER = os.environ.get('TE_VOIX', os.path.join(os.path.expanduser('~'), '.cache', 'te_voix'))
_CACHE = {}


def modele(lang):
    m = os.path.join(DOSSIER, f'{lang}.onnx')
    return m if os.path.exists(m) and os.path.exists(m + '.json') else None


def _lire(octets):
    with wave.open(io.BytesIO(octets)) as w:
        sr, n, k = w.getframerate(), w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(float) / 32768
    if k > 1:
        x = x.reshape(-1, k).mean(axis=1)
    return x, sr


def _piper(texte, m):
    """Piper par son module Python (versions 1.2 et 1.3), sinon par sa ligne de commande."""
    try:
        from piper import PiperVoice
        v = _CACHE.get(m) or PiperVoice.load(m)
        _CACHE[m] = v
        tampon = io.BytesIO()
        with wave.open(tampon, 'wb') as w:
            if hasattr(v, 'synthesize_wav'):
                v.synthesize_wav(texte, w)
            else:
                v.synthesize(texte, w)
        return tampon.getvalue()
    except Exception:
        pass
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, 'v.wav')
        for cmd in ([sys.executable, '-m', 'piper', '--model', m, '--output_file', f],
                    [sys.executable, '-m', 'piper', '-m', m, '-f', f, '--', texte]):
            try:
                subprocess.run(cmd, input=texte.encode('utf-8'), capture_output=True, timeout=60, check=True)
                if os.path.exists(f) and os.path.getsize(f) > 1000:
                    return open(f, 'rb').read()
            except Exception:
                continue
    return None


def dire(texte, lang, taux=48000):
    """La phrase dite (tableau mono au taux voulu) ou None."""
    m = modele(lang)
    if not m or not texte:
        return None
    octets = _piper(texte, m)
    if not octets:
        return None
    try:
        x, sr = _lire(octets)
    except Exception:
        return None
    if sr != taux:
        from scipy.signal import resample_poly
        from math import gcd
        g = gcd(int(sr), int(taux))
        x = resample_poly(x, taux // g, int(sr) // g)
    return x


def disponible(lang):
    return modele(lang) is not None
