#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
video_simulation.py — vidéo verticale (1080×1920, MP4) d'une simulation du match du jour, prête à poster sur X
(23/10/2026).

Ouvre la page publique algo/index.html en « mode vidéo » (?video=1) dans Chromium, enregistre l'écran pendant
que le match simulé se joue point par point, puis convertit l'enregistrement en MP4 (H.264, lisible partout).
La page signale la fin (window.__fini) ; la vidéo dure ~25 à 40 s selon la longueur du match simulé.

04/11/2026 — CAPTURE IMAGE PAR IMAGE (par défaut) : l'horloge de la page est remplacée par une horloge virtuelle
(minuteries, Date, performance, requestAnimationFrame, animations et transitions CSS). Le script avance le temps de
1/IPS seconde, prend une capture, et recommence : chaque image est exacte, sans saccade, quelle que soit la vitesse
de la machine. --capture ecran garde l'ancien enregistrement d'écran (repli).

Usage : python scripts/video_simulation.py [--lang fr|en] [--uid UID] [--seed N] [--carte] [--sortie dossier]
--carte : la carte de stats du match (PNG 1080×1350) au lieu de la vidéo.
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
# 05/11/2026 : format au choix — 9:16 (défaut, Reels / Shorts) ou 4:5 (1080×1350, le plus grand dans le fil de X)
FORMATS = {'9x16': (1080, 1920), '4x5': (1080, 1350)}
DEBUT_COUPE = 0.4                    # secondes coupées au début (page blanche)
IPS = 30                             # images par seconde de la capture image par image

# Horloge virtuelle injectée avant tout script de la page : le temps n'avance que quand le script le demande.
HORLOGE = r"""
(() => {
  const vraiST = window.setTimeout.bind(window), D0 = Date.now(), VraiDate = Date;
  let maint = 0, suiv = 1;
  const minut = new Map(), rafs = new Map();
  window.setTimeout = (fn, ms, ...a) => { const i = suiv++; minut.set(i, {at: maint + Math.max(0, +ms || 0), fn, a, ordre: i}); return i; };
  window.clearTimeout = i => { minut.delete(i); };
  window.setInterval = (fn, ms, ...a) => { const i = suiv++, pas = Math.max(1, +ms || 0);
    const tic = () => { minut.set(i, {at: maint + pas, fn: () => { tic(); fn(...a); }, a: [], ordre: suiv++}); }; tic(); return i; };
  window.clearInterval = window.clearTimeout;
  window.requestAnimationFrame = fn => { const i = suiv++; rafs.set(i, fn); return i; };
  window.cancelAnimationFrame = i => { rafs.delete(i); };
  performance.now = () => maint;
  Date.now = () => D0 + maint;
  window.Date = class extends VraiDate { constructor(...a){ if (a.length) super(...a); else super(D0 + maint); } static now(){ return D0 + maint; } };
  const vide = () => new Promise(r => vraiST(r, 0));         // laisse s'exécuter les suites (await) en attente
  const anims = () => { for (const an of document.getAnimations()){
      if (an.__v === undefined){ an.__v = maint - (an.currentTime || 0); an.pause(); }
      try { an.currentTime = maint - an.__v; } catch (e) {} } };
  window.__horloge = { t0: D0, avance: async (ms) => {
    const fin = maint + ms;
    for (let garde = 0; garde < 5000; garde++){
      let p = null;
      for (const [i, x] of minut) if (x.at <= fin && (!p || x.at < p[1].at || (x.at === p[1].at && x.ordre < p[1].ordre))) p = [i, x];
      if (!p) break;
      minut.delete(p[0]); maint = Math.max(maint, p[1].at);
      try { p[1].fn(...p[1].a); } catch (e) { console.error(e); }
      await vide();
    }
    maint = fin;
    const r = [...rafs.values()]; rafs.clear(); for (const fn of r){ try { fn(maint); } catch (e) {} }
    await vide();
    anims();
    return maint;
  } };
})();
"""


def servir(dossier):
    class Silencieux(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    h = functools.partial(Silencieux, directory=dossier)
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def enregistrer(url, dossier_tmp, max_s=120, taille=(LARGEUR, HAUTEUR)):
    """Renvoie (chemin de la vidéo brute, événements sonores [(secondes depuis le début de la vidéo, nom)])."""
    import time
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(viewport={'width': taille[0], 'height': taille[1]}, device_scale_factor=1,
                              record_video_dir=dossier_tmp, record_video_size={'width': taille[0], 'height': taille[1]})
        page = ctx.new_page()
        t0 = time.time()                     # l'enregistrement commence avec la page
        page.goto(url)
        page.wait_for_function('window.__fini === true', timeout=max_s * 1000, polling=250)
        sons = page.evaluate('window.__sons || []')
        chemin = page.video.path()
        ctx.close()
        nav.close()
    return chemin, [(e['t'] / 1000 - t0, e['type']) for e in sons]


def enregistrer_images(url, mp4, ips=IPS, max_s=150, taille=(LARGEUR, HAUTEUR)):
    """Capture image par image (horloge virtuelle) → MP4 muet ; renvoie (durée en s, événements sonores [(s, nom)])."""
    from playwright.sync_api import sync_playwright
    ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(ips), '-c:v', 'mjpeg',
                           '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p',
                           '-r', str(ips), '-movflags', '+faststart', '-an', mp4], stdin=subprocess.PIPE)
    n = 0
    try:
        with sync_playwright() as p:
            nav = p.chromium.launch()
            page = nav.new_page(viewport={'width': taille[0], 'height': taille[1]}, device_scale_factor=1)
            page.add_init_script(HORLOGE)
            page.goto(url)
            # pas de wait_for_function : son attente passe par les minuteries de la page, ici virtuelles
            import time
            limite = time.time() + 30
            while not page.evaluate('window.__sons !== undefined || window.__fini === true'):
                if time.time() > limite:
                    raise RuntimeError('la page vidéo ne démarre pas')
                time.sleep(0.1)
            pas = 1000.0 / ips
            while n < max_s * ips:
                ff.stdin.write(page.screenshot(type='jpeg', quality=92))
                n += 1
                if page.evaluate('window.__fini === true'):
                    break
                page.evaluate('ms => window.__horloge.avance(ms)', pas)
            t0 = page.evaluate('window.__horloge.t0')
            sons = page.evaluate('window.__sons || []')
            nav.close()
    finally:
        ff.stdin.close()
        ff.wait()
    if ff.returncode:
        raise RuntimeError('ffmpeg a échoué (capture image par image)')
    return n / ips, [((e['t'] - t0) / 1000.0, e['type']) for e in sons]


def carte(url, chemin):
    """Carte de stats du match (PNG 1080×1350, format portrait de X) : capture de la page en mode ?carte=1."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch()
        page = nav.new_page(viewport={'width': 1080, 'height': 1350}, device_scale_factor=1)
        page.goto(url)
        page.wait_for_function('window.__fini === true', timeout=30000, polling=200)
        page.screenshot(path=chemin)
        nav.close()
    return chemin


def carte_bilan(url, chemin):
    """05/11/2026 — carte bilan (PNG 1080×1350) : prévu contre réel du match du jour (ou de la veille) ; None si le
    résultat n'est pas encore disponible."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch()
        page = nav.new_page(viewport={'width': 1080, 'height': 1350}, device_scale_factor=1)
        page.goto(url)
        page.wait_for_function('window.__fini === true', timeout=30000, polling=200)
        vide, uid = page.evaluate('window.__vide === true'), page.evaluate('window.__uid || null')
        if not vide:
            page.screenshot(path=chemin)
        nav.close()
    return None if vide else uid


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--lang', default='fr', choices=['fr', 'en'])
    ap.add_argument('--uid', default='')
    ap.add_argument('--seed', default='', help='tirage précis ; vide = le scénario le plus fréquent des 5 000 (défaut)')
    ap.add_argument('--vitesse', default='1')
    ap.add_argument('--muet', action='store_true', help='sans bande-son')
    ap.add_argument('--adresse', action='store_true', help="afficher l'adresse du site en fin de vidéo (non par défaut)")
    ap.add_argument('--carte', action='store_true', help='carte de stats (PNG) au lieu de la vidéo')
    ap.add_argument('--bilan', action='store_true', help='carte bilan prévu / réel (PNG) du match du jour ou de la veille')
    ap.add_argument('--capture', default='images', choices=['images', 'ecran'],
                    help="images : image par image, sans saccade (défaut) ; ecran : ancien enregistrement d'écran")
    ap.add_argument('--format', default='9x16', choices=sorted(FORMATS), help='9x16 (défaut) ou 4x5 (fil de X)')
    ap.add_argument('--sortie', default=os.path.join(RACINE, 'videos'))
    a = ap.parse_args(argv[1:])
    algo = os.path.join(RACINE, 'algo')
    if not os.path.exists(os.path.join(algo, 'donnees.json')):
        print('algo/donnees.json absent : lancer simulateur/vitrine.py d\'abord.')
        return 1
    srv = servir(algo)
    if a.bilan:
        os.makedirs(a.sortie, exist_ok=True)
        png = os.path.join(a.sortie, f"bilan_{a.lang}.png")
        try:
            uid = carte_bilan(f"http://127.0.0.1:{srv.server_address[1]}/index.html?bilan=1&lang={a.lang}"
                              + (f"&uid={a.uid}" if a.uid else ''), png)
        finally:
            srv.shutdown()
        print(f"Bilan : {png} ({uid})" if uid else 'Bilan : résultat pas encore disponible')
        return 0
    if a.carte:
        os.makedirs(a.sortie, exist_ok=True)
        png = os.path.join(a.sortie, f"stats_{a.lang}.png")
        try:
            carte(f"http://127.0.0.1:{srv.server_address[1]}/index.html?carte=1&lang={a.lang}"
                  + (f"&uid={a.uid}" if a.uid else ''), png)
        finally:
            srv.shutdown()
        print(f"Carte : {png} ({os.path.getsize(png) / 1e3:.0f} Ko)")
        return 0
    q = (f"video=1&lang={a.lang}&vitesse={a.vitesse}" + (f"&seed={a.seed}" if str(a.seed).strip() else '')
         + (f"&uid={a.uid}" if a.uid else '')
         + ('&adresse=1' if a.adresse else ''))
    url = f"http://127.0.0.1:{srv.server_address[1]}/index.html?{q}"
    tmp = os.path.join(a.sortie, '_brut')
    os.makedirs(tmp, exist_ok=True)
    taille = FORMATS[a.format]
    nom = f"simulation_{a.lang}{'' if a.format == '9x16' else '_' + a.format}.mp4"
    mp4 = os.path.join(a.sortie, nom)
    if a.capture == 'images':
        try:
            muet = os.path.join(tmp, 'images.mp4')
            duree, sons = enregistrer_images(url, muet, taille=taille)
        finally:
            srv.shutdown()
        if a.muet:
            shutil.move(muet, mp4)
        else:
            import sons as SN
            wav = os.path.join(tmp, 'son.wav')
            SN.piste(sons, duree, wav)
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', muet, '-i', wav, '-map', '0:v', '-map', '1:a',
                            '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', mp4],
                           check=True)
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"Vidéo : {mp4} ({os.path.getsize(mp4) / 1e6:.1f} Mo, {duree:.1f} s, image par image à {IPS} i/s)")
        return 0
    try:
        webm, sons = enregistrer(url, tmp, taille=taille)
    finally:
        srv.shutdown()
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
