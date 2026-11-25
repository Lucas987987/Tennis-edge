#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sons_site.py — 25/11/2026 (paquet 428 bis, Lucas : « améliorer le bruit de frappe en prenant un vrai bruit de frappe,
améliorer le public »). Prépare pour le SITE les vrais sons enregistrés (CC0) déjà utilisés par la vidéo du jour
(dossier sons/, paquet 302 : frappes, services, rebonds, tribune, applaudissements, clameurs) : MP3 légers, lus par
la 3D du direct seulement quand le son est activé.

  sons/frappes.wav, services.wav, rebonds.wav → algo/sons/<nom>.mp3 (mono, 96 kb/s ; mêmes cases de 0,3 s / 0,2 s)
  sons/public_murmure.wav → algo/sons/murmure.mp3 (30 s, BOUCLE sans couture : la fin est fondue dans le début)
  sons/public_applaudissements.wav, public_ovation(2).wav → algo/sons/<nom>.mp3 (stéréo, 80 kb/s)
  algo/sons/sons.json : nombre d'extraits et durée de chaque case ; algo/sons/SOURCES.md : auteurs et licences.

Rien n'est inventé : découpe, fondus, conversion. Usage : python3 scripts/sons_site.py [racine]   (ffmpeg requis)
"""
import json
import os
import shutil
import subprocess
import sys
import wave

import numpy as np


def lire(chemin):
    with wave.open(chemin, 'rb') as w:
        n, ch, sr, sw = w.getnframes(), w.getnchannels(), w.getframerate(), w.getsampwidth()
        x = np.frombuffer(w.readframes(n), dtype={2: np.int16, 4: np.int32}[sw]).astype(np.float64)
    x = x.reshape(-1, ch) / float(2 ** (8 * sw - 1))
    return x, sr


def ecrire(chemin, x, sr):
    y = np.clip(x, -1, 1)
    with wave.open(chemin, 'wb') as w:
        w.setnchannels(y.shape[1]); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((y * 32767).astype('<i2').tobytes())


def boucle(x, sr, duree=30.0, fondu=1.5):
    """Les `duree` premières secondes, la fin fondue dans le début : rejouée en boucle, aucune couture audible."""
    n, f = int(duree * sr), int(fondu * sr)
    x = x[:n + f]
    a = np.linspace(0, 1, f)[:, None]
    y = x[:n].copy()
    y[:f] = x[n:n + f] * (1 - a) + x[:f] * a
    return y


def mp3(src, dst, debit, mono=False):
    cmd = ['ffmpeg', '-v', 'error', '-y', '-i', src] + (['-ac', '1'] if mono else []) + ['-codec:a', 'libmp3lame', '-b:a', debit, dst]
    subprocess.run(cmd, check=True)


def main(argv):
    racine = argv[1] if len(argv) > 1 else '.'
    src, out = os.path.join(racine, 'sons'), os.path.join(racine, 'algo', 'sons')
    os.makedirs(out, exist_ok=True)
    meta = json.load(open(os.path.join(src, 'banque.json'), encoding='utf-8'))
    tmp = os.path.join(out, '_tmp.wav')
    infos = {}
    for nom in ('frappes', 'services', 'rebonds'):
        mp3(os.path.join(src, nom + '.wav'), os.path.join(out, nom + '.mp3'), '96k', mono=True)
        infos[nom] = {'n': meta[nom]['n'], 'case_s': meta[nom]['case_s']}
    x, sr = lire(os.path.join(src, 'public_murmure.wav'))
    ecrire(tmp, boucle(x, sr), sr)
    mp3(tmp, os.path.join(out, 'murmure.mp3'), '64k')
    infos['murmure'] = {'duree_s': 30.0, 'boucle': True}
    for nom, cible in (('public_applaudissements', 'applaudissements'), ('public_ovation', 'ovation'), ('public_ovation2', 'ovation2')):
        mp3(os.path.join(src, nom + '.wav'), os.path.join(out, cible + '.mp3'), '80k')
        infos[cible] = {'duree_s': meta[nom]['duree_s']}
    os.remove(tmp)
    shutil.copy(os.path.join(src, 'SOURCES.md'), os.path.join(out, 'SOURCES.md'))
    with open(os.path.join(out, 'sons.json'), 'w', encoding='utf-8') as f:
        json.dump(infos, f, ensure_ascii=False, indent=1)
    tot = sum(os.path.getsize(os.path.join(out, k)) for k in os.listdir(out))
    print(f'sons du site : {len(infos)} fichiers, {tot // 1024} Ko au total')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
