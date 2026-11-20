#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sons.py — la bande-son des vidéos de simulation (24/10/2026), entièrement SYNTHÉTISÉE ici : aucun fichier
audio, aucune musique d'autrui, donc aucun droit à payer ni à citer.

Une musique de fond façon jeu vidéo (boucle 8 bits : grosse caisse, charleston, basse en arpège) et des
bruitages calés sur le déroulé de la vidéo : chaque frappe de balle, l'impact du « VS », les annonces (balle de
break, de set, de match), le BREAK, le set, le combo, la victoire avec la foule. La page (algo/index.html, mode
vidéo) note chaque événement et son heure ; scripts/video_simulation.py les place sur la piste.
Bibliothèque standard seulement (math, random, struct, wave).

18/11/2026 (paquet 276) — AMBIANCE « STADE » pour la vidéo en 3D : pas de musique 8 bits, mais la rumeur d'un
stade, le « pop » de la raquette, le rebond, le filet, les applaudissements et l'ovation sur les grands points,
un souffle sur les transitions. Toujours fabriqué ici, sans aucun enregistrement.
"""
import math
import random
import struct
import wave

TAUX = 32000
TEMPO = 128                                     # battements par minute de la musique


def _env(n, attaque, chute):
    """Enveloppe : montée linéaire sur `attaque` échantillons puis décroissance exponentielle."""
    k = math.log(1000) / max(1, chute)
    return [(i / attaque if i < attaque else math.exp(-k * (i - attaque))) for i in range(n)]


def _sin(f, i):
    return math.sin(2 * math.pi * f * i / TAUX)


def _carre(f, i):
    return 1.0 if (f * i / TAUX) % 1 < 0.5 else -1.0


def frappe(gagnant=0, rnd=None):
    """Toc de raquette : bruit très court + corps grave ; un peu plus aigu pour le joueur du bas."""
    rnd = rnd or random.Random(1)
    n = int(0.07 * TAUX)
    e = _env(n, 40, n * 0.6)
    f = 210 if gagnant == 0 else 180
    return [0.55 * e[i] * (0.6 * _sin(f, i) + 0.4 * (rnd.random() * 2 - 1) * math.exp(-i / 300)) for i in range(n)]


def impact(rnd=None):
    """Boum du VS / de la fin : sinus qui plonge + souffle."""
    rnd = rnd or random.Random(2)
    n = int(0.9 * TAUX)
    e = _env(n, 60, n * 0.8)
    out, ph = [], 0.0
    for i in range(n):
        f = 40 + 120 * math.exp(-i / 2500)
        ph += 2 * math.pi * f / TAUX
        out.append(0.9 * e[i] * (0.8 * math.sin(ph) + 0.25 * (rnd.random() * 2 - 1) * math.exp(-i / 4000)))
    return out


def montee(duree=0.6):
    """Annonce (balle de break / set / match) : balayage montant façon arcade."""
    n = int(duree * TAUX)
    out, ph = [], 0.0
    for i in range(n):
        f = 300 + 900 * (i / n) ** 1.5
        ph += 2 * math.pi * f / TAUX
        a = 0.32 * min(1, i / 400) * (1 - i / n) ** 0.3
        out.append(a * (1 if math.sin(ph) > 0 else -1) * 0.6 + a * 0.4 * math.sin(ph * 2))
    return out


def arpege(notes, pas=0.09, tenue=0.35, vol=0.3, forme=_carre):
    """Petite fanfare : notes (Hz) jouées l'une après l'autre."""
    n = int((pas * len(notes) + tenue) * TAUX)
    out = [0.0] * n
    for k, f in enumerate(notes):
        d0, dn = int(k * pas * TAUX), int((tenue + pas) * TAUX)
        e = _env(dn, 80, dn * 0.7)
        for i in range(dn):
            if d0 + i < n:
                out[d0 + i] += vol * e[i] * forme(f, i)
    return out


def piece(vol=0.28):
    """Combo : la « pièce » de jeu vidéo (deux notes aiguës)."""
    return arpege([988, 1319], pas=0.07, tenue=0.18, vol=vol)


def foule(duree=2.5, vol=0.5, rnd=None):
    """Clameur : bruit filtré qui enfle puis retombe."""
    rnd = rnd or random.Random(3)
    n = int(duree * TAUX)
    out, y1, y2 = [], 0.0, 0.0
    for i in range(n):
        x = rnd.random() * 2 - 1
        y1 += 0.08 * (x - y1)                     # passe-bas : souffle
        y2 += 0.02 * (y1 - y2)                    # second passe-bas : rumeur
        env = math.sin(math.pi * min(1, i / n)) ** 0.6
        out.append(vol * env * (y1 * 2.2 - y2 * 1.5))
    return out


def _filtre_bas(x, a):
    """Passe-bas simple (a petit = plus sourd)."""
    out, y = [], 0.0
    for v in x:
        y += a * (v - y)
        out.append(y)
    return out


def pop(fort=1.0, rnd=None):
    """Raquette : claquement bref (bruit) + résonance aiguë des cordes qui s'éteint vite."""
    rnd = rnd or random.Random(3)
    n = int(0.09 * TAUX)
    f = 820 * (0.9 + 0.2 * rnd.random()) * (1.1 if fort > 1 else 1)
    return [fort * (0.55 * (rnd.random() * 2 - 1) * math.exp(-i / 90) + 0.45 * math.sin(2 * math.pi * f * i / TAUX) * math.exp(-i / 420)
                    + 0.25 * math.sin(2 * math.pi * 180 * i / TAUX) * math.exp(-i / 700)) for i in range(n)]


def rebond(rnd=None):
    rnd = rnd or random.Random(4)
    n = int(0.07 * TAUX)
    return [0.32 * (0.6 * math.sin(2 * math.pi * 150 * i / TAUX) + 0.4 * (rnd.random() * 2 - 1) * math.exp(-i / 60)) * math.exp(-i / 380) for i in range(n)]


def filet(rnd=None):
    rnd = rnd or random.Random(5)
    n = int(0.35 * TAUX)
    br = _filtre_bas([rnd.random() * 2 - 1 for _ in range(n)], 0.15)
    return [0.5 * (0.7 * math.sin(2 * math.pi * 95 * i / TAUX) * math.exp(-i / 1500) + br[i] * math.exp(-i / 2600)) for i in range(n)]


def applaudir(duree=2.6, vol=0.5, rnd=None, densite=55):
    """Applaudissements : des centaines de claquements très courts, aléatoires, qui montent puis s'éteignent."""
    rnd = rnd or random.Random(6)
    n = int(duree * TAUX)
    out = [0.0] * n
    clap = [(rnd.random() * 2 - 1) * math.exp(-i / 70) for i in range(int(0.012 * TAUX))]
    nb = int(densite * duree)
    for _ in range(nb):
        t = rnd.random() ** 0.8
        d0 = int(t * n)
        g = vol * 0.22 * (0.4 + 0.6 * rnd.random()) * min(1.0, t * 8) * (1 - t) ** 0.7
        for i, v in enumerate(clap):
            if d0 + i < n:
                out[d0 + i] += g * v
    return out


def acclamation(duree=3.5, vol=0.5, rnd=None):
    """Ovation : applaudissements nourris + clameur (bruit filtré qui gonfle puis retombe)."""
    rnd = rnd or random.Random(8)
    n = int(duree * TAUX)
    cl = _filtre_bas([rnd.random() * 2 - 1 for _ in range(n)], 0.09)
    cl = [v - w for v, w in zip(cl, _filtre_bas(cl, 0.01))]                         # garde la bande des voix
    env = [min(1.0, i / (0.25 * TAUX)) * (1 - i / n) ** 1.2 for i in range(n)]
    return _mix(applaudir(duree, vol * 1.3, rnd, densite=110), [vol * 1.6 * cl[i] * env[i] for i in range(n)])


def souffle(duree=0.5, rnd=None):
    """Transition : souffle qui balaie l'image."""
    rnd = rnd or random.Random(10)
    n = int(duree * TAUX)
    x = _filtre_bas([rnd.random() * 2 - 1 for _ in range(n)], 0.25)
    return [0.35 * x[i] * math.sin(math.pi * i / n) ** 2 for i in range(n)]


def rumeur(duree, rnd=None):
    """Fond de stade : brouhaha sourd qui respire lentement."""
    rnd = rnd or random.Random(11)
    n = int(duree * TAUX)
    x = _filtre_bas([rnd.random() * 2 - 1 for _ in range(n)], 0.05)
    x = [v - w for v, w in zip(x, _filtre_bas(x, 0.004))]
    fondu = int(1.2 * TAUX)
    return [0.9 * x[i] * (0.75 + 0.25 * math.sin(2 * math.pi * 0.13 * i / TAUX)) * min(1.0, i / fondu, (n - 1 - i) / fondu) for i in range(n)]


def _mix(*pistes):
    n = max(len(x) for x in pistes)
    return [sum(x[i] for x in pistes if i < len(x)) for i in range(n)]


NOTES = {'do': 262, 'mi': 330, 'sol': 392, 'la': 440, 'do2': 523, 'mi2': 659, 'sol2': 784, 'do3': 1047}
SONS = {
    'vs': lambda r: impact(r),
    'frappe0': lambda r: frappe(0, r),
    'frappe1': lambda r: frappe(1, r),
    'annonce': lambda r: montee(0.6),
    'balle_match': lambda r: _mix(montee(0.8), [0.5 * v for v in impact(r)]),
    'break': lambda r: arpege([NOTES['sol'], NOTES['do2'], NOTES['mi2']], pas=0.07, tenue=0.3, vol=0.28),
    'set': lambda r: arpege([NOTES['do2'], NOTES['mi2'], NOTES['sol2'], NOTES['do3']], pas=0.08, tenue=0.45, vol=0.3),
    'jeu_decisif': lambda r: montee(0.5),
    'combo': lambda r: piece(),
    # ambiance stade (vidéo 3D)
    'service': lambda r: pop(1.35, r),
    'rebond': lambda r: rebond(r),
    'filet': lambda r: filet(r),
    'applaudissements': lambda r: applaudir(2.4, 0.5, r),
    'ovation': lambda r: acclamation(3.6, 0.55, r),
    'foule_entree': lambda r: acclamation(4.2, 0.4, r),
    'volet': lambda r: souffle(0.55, r),
    'fin': lambda r: _mix(impact(r), arpege([NOTES['do2'], NOTES['mi2'], NOTES['sol2'], NOTES['do3'], NOTES['sol2'],
                                            NOTES['do3']], pas=0.12, tenue=0.8, vol=0.32), foule(3.2, 0.55, r)),
}


def musique(duree):
    """Boucle 8 bits au tempo TEMPO : grosse caisse sur les temps, charleston entre, basse en arpège."""
    n = int(duree * TAUX)
    out = [0.0] * n
    t = 60 / TEMPO
    rnd = random.Random(9)
    basse = [65.4, 65.4, 98.0, 87.3, 73.4, 73.4, 110.0, 98.0]       # do do sol fa ré ré la sol (grave)
    k = 0
    while k * t / 2 < duree:
        d0 = int(k * t / 2 * TAUX)
        if k % 2 == 0:                                                  # temps : grosse caisse
            dn = int(0.18 * TAUX)
            ph = 0.0
            for i in range(dn):
                if d0 + i >= n:
                    break
                f = 50 + 90 * math.exp(-i / 500)
                ph += 2 * math.pi * f / TAUX
                out[d0 + i] += 0.42 * math.exp(-i / 1800) * math.sin(ph)
        else:                                                           # contretemps : charleston
            for i in range(int(0.04 * TAUX)):
                if d0 + i >= n:
                    break
                out[d0 + i] += 0.07 * math.exp(-i / 250) * (rnd.random() * 2 - 1)
        f = basse[(k // 2) % len(basse)] * 2                            # basse : une note par demi-temps
        dn = int(t / 2 * TAUX * 0.9)
        for i in range(dn):
            if d0 + i >= n:
                break
            out[d0 + i] += 0.07 * _carre(f, i) * math.exp(-i / (dn * 0.6))
        k += 1
    fondu = int(1.5 * TAUX)                                             # fondus d'entrée et de sortie
    for i in range(min(fondu, n)):
        out[i] *= i / fondu
        out[n - 1 - i] *= i / fondu
    return out


STADE = {'frappe0': lambda r: pop(1.0, r), 'frappe1': lambda r: pop(0.95, r)}   # en 3D : la vraie raquette


def piste(evenements, duree, chemin, volume_musique=0.6, ambiance='arcade'):
    """evenements : [(secondes, nom)] — écrit un WAV mono 16 bits de `duree` secondes.
    ambiance 'stade' (vidéo 3D) : rumeur du public au lieu de la musique, raquette réaliste."""
    n = int(duree * TAUX)
    mix = [v * 0.22 for v in rumeur(duree)] if ambiance == 'stade' else [v * volume_musique for v in musique(duree)]
    sons = dict(SONS, **STADE) if ambiance == 'stade' else SONS
    rnd = random.Random(7)
    cache = {}
    for t, nom in evenements:
        if nom not in sons or t < 0 or t >= duree:
            continue
        if nom not in cache or nom.startswith('frappe') or nom in ('service', 'rebond', 'applaudissements'):
            cache[nom] = sons[nom](rnd)
        s, d0 = cache[nom], int(t * TAUX)
        for i, v in enumerate(s):
            if d0 + i >= n:
                break
            mix[d0 + i] += v
    crete = max(1e-9, max(abs(v) for v in mix))
    g = min(1.0, 0.95 / crete)                                          # pas de saturation
    with wave.open(chemin, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAUX)
        w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, v * g)) * 32767)) for v in mix))
    return chemin
