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
sys.path.insert(0, ICI)
LARGEUR, HAUTEUR = 1080, 1920
DEBUT_COUPE = 0.4                    # secondes coupées au début (page blanche)


def servir(dossier):
    class Silencieux(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = functools.partial(Silencieux, directory=dossier)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def enregistrer(url, dossier_tmp, max_s=120):
    """Renvoie (chemin de la vidéo brute, événements sonores [(secondes depuis le début de la vidéo, nom)])."""
    import time
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(viewport={'width': LARGEUR, 'height': HAUTEUR}, device_scale_factor=1,
                              record_video_dir=dossier_tmp, record_video_size={'width': LARGEUR, 'height': HAUTEUR})
        page = ctx.new_page()
        t0 = time.time()                     # l'enregistrement commence avec la page
        page.goto(url)
        page.wait_for_function('window.__fini === true', timeout=max_s * 1000, polling=250)
        sons = page.evaluate('window.__sons || []')
        chemin = page.video.path()
        ctx.close()
        nav.close()
    return chemin, [(e['t'] / 1000 - t0, e['type']) for e in sons]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', default='fr', choices=['fr', 'en'])
    ap.add_argument('--uid', default='')
    ap.add_argument('--seed', default='', help='tirage précis ; vide = le scénario le plus fréquent des 5 000 (défaut)')
    ap.add_argument('--vitesse', default='1')
    ap.add_argument('--muet', action='store_true', help='sans bande-son')
    ap.add_argument('--adresse', action='store_true', help="afficher l'adresse du site en fin de vidéo (non par défaut)")
    ap.add_argument('--sortie', default=os.path.join(RACINE, 'videos'))
    a = ap.parse_args(argv[1:])
    algo = os.path.join(RACINE, 'algo')
    if not os.path.exists(os.path.join(algo, 'donnees.json')):
        print('algo/donnees.json absent : lancer simulateur/vitrine.py d\'abord.')
        return 1
    srv = servir(algo)
    q = (f"video=1&lang={a.lang}&vitesse={a.vitesse}" + (f"&seed={a.seed}" if str(a.seed).strip() else '')
         + (f"&uid={a.uid}" if a.uid else '')
         + ('&adresse=1' if a.adresse else ''))
    url = f"http://127.0.0.1:{srv.server_address[1]}/index.html?{q}"
    tmp = os.path.join(a.sortie, '_brut')
    os.makedirs(tmp, exist_ok=True)
    try:
        webm, sons = enregistrer(url, tmp)
    finally:
        srv.shutdown()
    nom = f"simulation_{a.lang}.mp4"
    mp4 = os.path.join(a.sortie, nom)
    brut = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', webm],
                          capture_output=True, text=True).stdout.strip()
    try:
        duree = float(brut) - DEBUT_COUPE
    except ValueError:                       # webm sans durée dans l'en-tête : le dernier son + la fin
        duree = max([t for t, _ in sons] or [30]) + 5 - DEBUT_COUPE
    entree_son = []
    if not a.muet and duree > 0:
        # bande-son synthétisée (scripts/sons.py), calée sur les événements de la page ; même coupe de début
        import sons as SN
        wav = os.path.join(tmp, 'son.wav')
        SN.piste([(t - DEBUT_COUPE, n) for t, n in sons], duree, wav)
        entree_son = ['-i', wav, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '160k', '-shortest']
    # coupe le début (page blanche avant le rendu) ; H.264 + yuv420p : lisible sur X/Android/iOS
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(DEBUT_COUPE), '-i', webm, *entree_son,
                    '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p', '-r', '30',
                    '-movflags', '+faststart', *([] if entree_son else ['-an']), mp4], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"Vidéo : {mp4} ({os.path.getsize(mp4) / 1e6:.1f} Mo)")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
