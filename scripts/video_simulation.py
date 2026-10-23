#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video_simulation.py — vidéo verticale (1080×1920, MP4) d'une simulation du match du jour, prête à poster sur X
(23/10/2026).

Ouvre la page publique algo/index.html en « mode vidéo » (?video=1) dans Chromium, enregistre l'écran pendant
que le match simulé se joue point par point, puis convertit l'enregistrement en MP4 (H.264, lisible partout).
La page signale la fin (window.__fini) ; la vidéo dure ~25 à 40 s selon la longueur du match simulé.

Usage : python scripts/video_simulation.py [--lang fr|en] [--uid UID] [--seed N] [--sortie dossier]
La page est servie en local depuis algo/ (algo/donnees.json doit exister : simulateur/vitrine.py).
"""
import argparse
import functools
import http.server
import os
import shutil
import subprocess
import sys
import threading

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
LARGEUR, HAUTEUR = 1080, 1920


def servir(dossier):
    class Silencieux(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = functools.partial(Silencieux, directory=dossier)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def enregistrer(url, dossier_tmp, max_s=90):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(viewport={'width': LARGEUR, 'height': HAUTEUR}, device_scale_factor=1,
                              record_video_dir=dossier_tmp, record_video_size={'width': LARGEUR, 'height': HAUTEUR})
        page = ctx.new_page()
        page.goto(url)
        page.wait_for_function('window.__fini === true', timeout=max_s * 1000, polling=250)
        chemin = page.video.path()
        ctx.close()
        nav.close()
    return chemin


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', default='fr', choices=['fr', 'en'])
    ap.add_argument('--uid', default='')
    ap.add_argument('--seed', default='7')
    ap.add_argument('--vitesse', default='1.6')
    ap.add_argument('--sortie', default=os.path.join(RACINE, 'videos'))
    a = ap.parse_args(argv[1:])
    algo = os.path.join(RACINE, 'algo')
    if not os.path.exists(os.path.join(algo, 'donnees.json')):
        print('algo/donnees.json absent : lancer simulateur/vitrine.py d\'abord.')
        return 1
    srv = servir(algo)
    q = f"video=1&lang={a.lang}&seed={a.seed}&vitesse={a.vitesse}" + (f"&uid={a.uid}" if a.uid else '')
    url = f"http://127.0.0.1:{srv.server_address[1]}/index.html?{q}"
    tmp = os.path.join(a.sortie, '_brut')
    os.makedirs(tmp, exist_ok=True)
    try:
        webm = enregistrer(url, tmp)
    finally:
        srv.shutdown()
    nom = f"simulation_{a.lang}.mp4"
    mp4 = os.path.join(a.sortie, nom)
    # recadre le premier quart de seconde (page blanche avant le rendu) ; H.264 + yuv420p : lisible sur X/Android/iOS
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '0.4', '-i', webm, '-c:v', 'libx264', '-preset', 'medium',
                    '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '30', '-movflags', '+faststart', '-an', mp4], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Vidéo : {mp4} ({os.path.getsize(mp4) / 1e6:.1f} Mo)")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
