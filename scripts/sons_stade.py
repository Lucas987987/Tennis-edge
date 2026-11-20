#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sons_stade.py — la bande-son « stade » de la vidéo du jour en 3D (paquet 277, 18/11/2026), en STÉRÉO.

Paquet 302 : frappes, services, rebonds et public sont de VRAIS ENREGISTREMENTS sous licence Creative Commons 0
(domaine public, freesound.org ; dossier sons/, sources dans sons/SOURCES.md). Le reste est fabriqué ici (numpy,
scipy), aucune musique d'autrui ; les sons synthétiques d'avant restent en secours si un fichier manque.
  — le public : un vrai stade entre les points, vrais applaudissements, vraie clameur sur les grands points ;
    « ooooh » encore synthétique ;
  — le court : vraies frappes (services à part) et vrais rebonds ; filet et crissement des semelles synthétiques,
    placés à gauche ou à droite selon l'image ;
  — l'habillage : souffle des transitions, impact du face-à-face, jingles télé courts, nappe musicale en ouverture
    et en fin ;
  — la voix de l'arbitre (synthèse vocale, scripts/voix.py) passée dans la sono du stade ; le public baisse quand
    elle parle ;
  — une réverbération de grande salle sur le tout, puis un limiteur.
Repli : si numpy ou scipy manque, scripts/video_simulation.py garde la bande-son de scripts/sons.py.
"""
import json
import os
from math import gcd

import numpy as np
from scipy import signal
from scipy.io import wavfile

TAUX = 48000


def _rng(graine):
    return np.random.default_rng(graine)


def _bande(x, bas=None, haut=None, ordre=2):
    if bas and haut:
        sos = signal.butter(ordre, [bas, haut], 'bandpass', fs=TAUX, output='sos')
    elif bas:
        sos = signal.butter(ordre, bas, 'highpass', fs=TAUX, output='sos')
    else:
        sos = signal.butter(ordre, haut, 'lowpass', fs=TAUX, output='sos')
    return signal.sosfilt(sos, x, axis=0)


def _env(n, attaque, chute):
    t = np.arange(n) / TAUX
    return np.minimum(1.0, t / max(attaque, 1e-4)) * np.exp(-np.maximum(0, t - attaque) / max(chute, 1e-4))


def _st(x, pan=0.0):
    """Mono → stéréo, panoramique à puissance constante (pan −1 gauche … +1 droite)."""
    a = (pan + 1) * np.pi / 4
    return np.stack([x * np.cos(a), x * np.sin(a)], axis=1)


def _lisse(n, freq, r):
    """Enveloppe aléatoire lisse (bruit basse fréquence), entre 0 et 1."""
    pas = max(1, int(TAUX / freq))
    k = r.random(n // pas + 3)
    return np.interp(np.arange(n), np.arange(len(k)) * pas, k)


# ── le court ────────────────────────────────────────────────────────────────────────────────────────────────
# 19/11/2026 (paquet 301, Lucas : « la balle ne fait pas le bruit d'une balle de tennis qui frappe ») : l'ancien
# « pock » tenait une note pure 18 ms (un « bip ») sur un « boum » grave. Une vraie frappe est un choc très bref et
# CREUX : la coque de la balle sonne quelques millisecondes (trois résonances qui ne sont pas des harmoniques, la
# hauteur baisse un peu en s'éteignant), le tamis donne un « ping » court vers 550 Hz, le cadre un petit coup sourd.
def _mode(t, f, chute, glisse=0.05, phase=0.0):
    """Une résonance amortie dont la hauteur baisse un peu en s'éteignant."""
    fi = f * (1 - glisse * (1 - np.exp(-t / max(chute, 1e-4))))
    return np.sin(2 * np.pi * np.cumsum(fi) / TAUX + phase) * np.exp(-t / chute)


def _pock_synth(fort=1.0, r=None):
    """Frappe de raquette (fort > 1 : service, plus sec et plus brillant)."""
    r = r or _rng(1)
    n = int(0.09 * TAUX)
    t = np.arange(n) / TAUX
    sec = 1.0 if fort <= 1 else 0.8                                         # le service : sons encore plus courts
    contact = _bande(r.standard_normal(n), 1500, 9000) * np.exp(-t / (0.0011 * sec))
    f1 = r.uniform(1150, 1450) * (1.06 if fort > 1 else 1.0)
    coque = (_mode(t, f1, 0.0055 * sec, phase=r.uniform(0, 6.28))
             + 0.45 * _mode(t, f1 * r.uniform(1.9, 2.1), 0.0035 * sec, phase=r.uniform(0, 6.28))
             + 0.22 * _mode(t, f1 * r.uniform(2.9, 3.2), 0.0024 * sec, phase=r.uniform(0, 6.28)))
    tamis = _mode(t, r.uniform(500, 620), 0.009, 0.02)
    cadre = _mode(t, r.uniform(140, 190), 0.012, 0.0)
    x = 0.55 * contact + coque + 0.28 * tamis + 0.15 * cadre
    x *= np.minimum(1, t / 0.0002)                                          # attaque franche, sans clic numérique
    return 0.9 * fort * x / (np.abs(x).max() + 1e-9)


def _rebond_synth(r=None):
    """La balle sur le court : choc mat, coque plus grave et plus courte qu'à la frappe, petit coup du sol."""
    r = r or _rng(2)
    n = int(0.07 * TAUX)
    t = np.arange(n) / TAUX
    contact = _bande(r.standard_normal(n), 700, 5000) * np.exp(-t / 0.0014)
    f1 = r.uniform(880, 1100)
    coque = _mode(t, f1, 0.004, phase=r.uniform(0, 6.28)) + 0.35 * _mode(t, f1 * r.uniform(1.9, 2.1), 0.0025)
    sol = _mode(t, r.uniform(120, 170), 0.012, 0.0)
    x = 0.6 * contact + 0.75 * coque + 0.5 * sol
    x *= np.minimum(1, t / 0.0003)
    return 0.26 * x / (np.abs(x).max() + 1e-9)


def filet(r=None):
    r = r or _rng(3)
    n = int(0.4 * TAUX)
    t = np.arange(n) / TAUX
    return 0.45 * (np.sin(2 * np.pi * 85 * t) * np.exp(-t / 0.06) + 0.6 * _bande(r.standard_normal(n), 200, 1500) * np.exp(-t / 0.09))


def crisse(r=None):
    r = r or _rng(4)
    n = int(r.uniform(0.07, 0.13) * TAUX)
    t = np.arange(n) / TAUX
    f = np.linspace(r.uniform(2100, 2600), r.uniform(2900, 3600), n) + 120 * np.sin(2 * np.pi * 38 * t)
    ph = 2 * np.cumsum(np.pi * f / TAUX)
    return 0.07 * np.sin(ph) * np.abs(np.sin(np.pi * t / t[-1])) ** 0.6


def _somme(a, b):
    n = max(len(a), len(b))
    return np.pad(a, ((0, n - len(a)), (0, 0))) + np.pad(b, ((0, n - len(b)), (0, 0)))


# ── le public ───────────────────────────────────────────────────────────────────────────────────────────────
# 19/11/2026 (paquet 300, Lucas : « le bruit du public, ce n'est pas du tout clair ») : l'ancien public était fait de
# bruit filtré (souffle, pluie) : on n'y reconnaissait ni des voix ni des mains. Il est maintenant fait de VOIX
# synthétiques (cordes vocales : impulsions à la hauteur de chaque voix ; bouche : trois formants de voyelle ;
# syllabes, consonnes, pauses) et de VRAIS RYTHMES D'APPLAUDISSEMENTS (chaque spectateur frappe 3 à 5,5 fois par
# seconde, avec la résonance de ses mains, puis s'arrête à son moment). Toujours rien d'enregistré.
VOYELLES = {'a': (730, 1090, 2440), 'e': (530, 1840, 2480), 'i': (300, 2250, 3000), 'o': (570, 840, 2410),
            'u': (320, 870, 2240), 'eu': (480, 1350, 2400), 'ou': (350, 750, 2300)}


def _source(n, f0, r, souffle=0.04):
    """Cordes vocales : train d'impulsions à la hauteur f0 (tableau ou nombre), un peu irrégulier, + souffle."""
    f0 = np.broadcast_to(np.asarray(f0, dtype=float), (n,)) * (1 + 0.012 * (_lisse(n, 6, r) - 0.5))
    ph = np.cumsum(f0 / TAUX) % 1.0
    impulsion = np.where(ph < 0.6, np.sin(np.pi * ph / 0.6) ** 2, 0.0)
    x = np.diff(impulsion, prepend=0.0)
    x /= np.sqrt((x ** 2).mean()) + 1e-12                                     # puissance 1, puis un peu de souffle
    return x + souffle * r.standard_normal(n)


def _bouche(x, formants, femme=False):
    """Trois résonances (formants) d'une voyelle, en parallèle."""
    k = 1.17 if femme else 1.0
    out = np.zeros_like(x)
    for f, g, q in zip(formants, (1.0, 0.55, 0.28), (7, 11, 14)):
        b, a = signal.iirpeak(min(f * k, TAUX / 2 - 100), q, fs=TAUX)
        out += g * signal.lfilter(b, a, x)
    return out


def _parleur(n, r):
    """Une personne qui parle : syllabes (voyelle + parfois consonne), pauses, intonation."""
    femme = r.random() < 0.45
    f0 = r.uniform(175, 245) if femme else r.uniform(95, 140)
    out = np.zeros(n)
    i = int(r.uniform(0, 0.6) * TAUX)
    while i < n:
        if r.random() < 0.18:                                               # respiration, silence
            i += int(r.uniform(0.25, 0.8) * TAUX)
            continue
        lg = int(r.uniform(0.11, 0.26) * TAUX)
        if i + lg >= n:
            break
        t = np.arange(lg) / lg
        hauteur = f0 * (1 + 0.12 * (r.random() - 0.5) - 0.06 * t)              # l'intonation retombe un peu
        v = _bouche(_source(lg, hauteur, r), VOYELLES[r.choice(list(VOYELLES))], femme)
        v /= np.sqrt((v ** 2).mean()) + 1e-12
        env = np.sin(np.pi * np.minimum(1, t * 1.15)) ** 1.5
        syl = v * env * r.uniform(0.5, 1.0)
        if r.random() < 0.4:                                                 # consonne : s, ch, t, k… (discrète)
            lc = int(r.uniform(0.02, 0.045) * TAUX)
            c = _bande(r.standard_normal(lc), r.uniform(2500, 4500), 7500) * np.hanning(lc) * 0.12
            syl[:lc] += c[:lg]
        out[i:i + lg] += syl
        i += lg + int(r.uniform(0.0, 0.07) * TAUX)
    return out


def _boucle_brouhaha(duree, nb, r):
    """nb personnes qui parlent, réparties dans la salle (stéréo), un peu lointaines."""
    n = int(duree * TAUX)
    out = np.zeros((n, 2))
    for _ in range(nb):
        x = _parleur(n, r)
        loin = r.uniform(0.35, 1.0)
        x = _bande(x, 200, 2600 + 2400 * loin)                                 # pas de grondement ; les voix lointaines perdent leurs aigus
        out += _st(x * loin, r.uniform(-0.95, 0.95))
    return out / (np.sqrt((out ** 2).mean()) + 1e-9)


def _brouhaha_synth(duree, r=None, niveau=0.06):
    """Le stade qui parle à voix basse entre les points : trois boucles de 9 s de 40 voix, enchaînées en fondu, gauche
    et droite décalées (pas de répétition audible)."""
    r = r or _rng(5)
    n = int(duree * TAUX)
    boucles = [_boucle_brouhaha(9.0, 40, r) for _ in range(3)]
    L = len(boucles[0])
    fondu = int(1.5 * TAUX)
    rampe = np.linspace(0, 1, fondu)[:, None]
    out = np.zeros((n + L, 2))
    pos, k = 0, 0
    while pos < n:
        b = boucles[k % 3].copy()
        b[:fondu] *= rampe
        b[-fondu:] *= rampe[::-1]
        out[pos:pos + L] += b
        pos += L - fondu
        k += 1
    out = out[:n]
    out[:, 1] = np.roll(out[:, 1], int(3.1 * TAUX))                          # gauche et droite jamais en même temps
    debut = int(min(1.0, duree / 3) * TAUX)
    env = np.minimum(1, np.minimum(np.arange(n), n - 1 - np.arange(n)) / max(1, debut))
    return niveau * 0.42 * out * env[:, None]                               # un peu plus bas qu'avant : le court s'entend mieux


def _claquement(r):
    """Une paire de mains : choc bref + résonance du creux des mains (800–2 300 Hz selon la personne)."""
    lg = int(0.03 * TAUX)
    t = np.arange(lg) / TAUX
    choc = r.standard_normal(lg) * np.exp(-t / r.uniform(0.0025, 0.005))
    b, a = signal.iirpeak(r.uniform(800, 2300), r.uniform(2.0, 4.0), fs=TAUX)
    x = 0.65 * signal.lfilter(b, a, choc) + 0.35 * _bande(choc, 1500, 9000)
    return x / (np.abs(x).max() + 1e-9)


def _applaudir_synth(duree=2.6, densite=900, vol=0.5, r=None):
    """Applaudissements : densite/4 spectateurs, chacun à son rythme (3–5,5 frappes par seconde), qui commencent
    presque ensemble et s'arrêtent peu à peu ; proches (nets) ou lointains (plus sourds)."""
    r = r or _rng(6)
    n = int(duree * TAUX)
    out = np.zeros((n, 2))
    mains = [_claquement(r) for _ in range(24)]
    lg = len(mains[0])
    gens = max(8, int(densite / 4))
    for _ in range(gens):
        rythme = r.uniform(3.0, 5.5)
        t = r.beta(1.5, 6) * 0.5
        fin = duree * r.uniform(0.45, 1.0)
        m = mains[r.integers(len(mains))]
        loin = r.uniform(0.25, 1.0)
        p = r.uniform(-1, 1)
        g = np.array([np.cos((p + 1) * np.pi / 4), np.sin((p + 1) * np.pi / 4)]) * loin
        while t < fin:
            d0 = int(t * TAUX)
            if d0 + lg >= n:
                break
            out[d0:d0 + lg] += np.outer(m * r.uniform(0.7, 1.0), g)
            t += (1 / rythme) * r.uniform(0.92, 1.08)
    out = _bande(out, 250, 9000)
    env = np.minimum(1, np.arange(n) / (0.08 * TAUX))[:, None]
    return vol * env * out / (np.abs(out).max() + 1e-9)


def _voix_foule(duree, nb, voyelles, f0_h, f0_f, profil, r, vol):
    """nb voix qui tiennent une voyelle ensemble (cri, « oooh ») ; profil(t 0→1) → (hauteur relative, volume)."""
    n = int(duree * TAUX)
    out = np.zeros((n, 2))
    t = np.arange(n) / n
    haut, force = profil(t)
    for _ in range(nb):
        femme = r.random() < 0.45
        f0 = r.uniform(*(f0_f if femme else f0_h))
        retard = int(r.uniform(0, 0.15) * n)
        x = np.zeros(n)
        m = n - retard
        v = _bouche(_source(m, f0 * haut[:m] * (1 + 0.02 * np.sin(2 * np.pi * r.uniform(4, 6) * np.arange(m) / TAUX)), r, 0.06),
                    VOYELLES[r.choice(voyelles)], femme)
        x[retard:] = v / (np.sqrt((v ** 2).mean()) + 1e-12) * force[:m]
        x = _bande(x, 180, 6000)
        out += _st(x * r.uniform(0.4, 1.0), r.uniform(-0.95, 0.95))
    return vol * out / (np.abs(out).max() + 1e-9)


def clameur(duree=3.0, vol=0.4, r=None, voyelle=None):
    """Le public crie sa joie : « ouais ! », « aaah ! » — monte vite, retombe."""
    r = r or _rng(7)
    def profil(t):
        return 1 + 0.25 * np.minimum(1, t / 0.15) - 0.15 * t, np.minimum(1, t / 0.08) * (1 - t) ** 1.2
    return _voix_foule(duree, 70, ['a', 'e', 'o', 'eu'], (150, 230), (260, 380), profil, r, vol)


def houle(r=None):
    """« Ooooh » : le public retient son souffle quand l'échange dure (la hauteur monte, puis retombe)."""
    r = r or _rng(8)
    def profil(t):
        return 1 + 0.18 * np.sin(np.pi * np.minimum(1, t * 1.2)), np.sin(np.pi * t) ** 1.4
    return _voix_foule(1.8, 60, ['ou', 'o', 'u'], (110, 160), (200, 280), profil, r, 0.3)


def sifflet(duree=1.2, r=None):
    """Un spectateur qui siffle (deux doigts) : glissando aigu."""
    r = r or _rng(13)
    n = int(duree * TAUX)
    t = np.arange(n) / TAUX
    f = r.uniform(2300, 2900) + 500 * np.sin(np.pi * np.minimum(1, t / duree)) + 25 * np.sin(2 * np.pi * 6 * t)
    x = np.sin(2 * np.pi * np.cumsum(f) / TAUX) + 0.04 * r.standard_normal(n)
    env = np.minimum(1, t / 0.05) * np.minimum(1, (duree - t) / 0.2)
    return x * env


def _ovation_synth(duree=3.8, r=None):
    r = r or _rng(9)
    out = _somme(_applaudir_synth(duree, 1900, 0.5, r), clameur(duree * 0.8, 0.3, r))
    for _ in range(2):                                                       # deux sifflets dans la salle
        s = sifflet(r.uniform(0.8, 1.3), r) * 0.07
        d0 = int(r.uniform(0.2, 1.2) * TAUX)
        fin = min(len(out), d0 + len(s))
        out[d0:fin] += _st(s[:fin - d0], r.uniform(-0.8, 0.8))
    return out


# ── l'habillage ─────────────────────────────────────────────────────────────────────────────────────────────
def souffle(duree=0.55, r=None):
    r = r or _rng(10)
    n = int(duree * TAUX)
    t = np.arange(n) / n
    x = r.standard_normal(n)
    f = 300 * (10 ** (t * 1.1))
    out = np.zeros(n)
    for k in range(0, n, 512):                                                 # filtre qui balaie (par blocs)
        sos = signal.butter(2, [max(80, f[k] * 0.7), min(18000, f[k] * 1.4)], 'bandpass', fs=TAUX, output='sos')
        out[k:k + 512] = signal.sosfilt(sos, x[k:k + 512])
    env = np.sin(np.pi * t) ** 2
    st = np.stack([out * env * (1 - t), out * env * t], axis=1)
    return 0.4 * st / (np.abs(st).max() + 1e-9)


def impact(r=None):
    r = r or _rng(11)
    n = int(1.4 * TAUX)
    t = np.arange(n) / TAUX
    f = 30 + 70 * np.exp(-t / 0.08)
    boum = np.sin(2 * np.pi * np.cumsum(f) / TAUX) * np.exp(-t / 0.45)
    return 0.8 * (boum + 0.3 * _bande(r.standard_normal(n), 2000, None) * np.exp(-t / 0.05))


def _scie(f, t):
    return 2 * ((f * t) % 1) - 1


def accord(notes, duree, vol=0.25, ouverture=1800):
    """Nappe de cuivres synthétiques (scies désaccordées, filtrées), pour les jingles."""
    n = int(duree * TAUX)
    t = np.arange(n) / TAUX
    x = sum(_scie(f * d, t) for f in notes for d in (0.997, 1.0, 1.004))
    x = _bande(x, None, ouverture, 2)
    env = np.minimum(1, t / 0.03) * np.exp(-t / (duree * 0.45))
    return vol * x * env / (np.abs(x).max() + 1e-9)


def jingle(niveau=1):
    """Annonce télé : accord qui monte (1 : balle de break / de set ; 2 : balle de match ; 3 : break, set ; 4 : fin)."""
    base = {1: [220, 277.2, 329.6], 2: [196, 246.9, 293.7, 392], 3: [261.6, 329.6, 392, 523.3], 4: [261.6, 329.6, 392, 523.3, 659.3]}[niveau]
    d = {1: 0.7, 2: 1.2, 3: 0.9, 4: 2.4}[niveau]
    a = accord(base, d, 0.22, 2400 if niveau > 2 else 1500)
    if niveau in (2, 4):
        b = impact()[:len(a)]; a = a.copy(); a[:len(b)] += b * 0.35
    return _st(a, 0)


def nappe(duree, r=None):
    """Musique d'ouverture et de fin : quatre accords lents, très doux, sous le public."""
    suite = [[220, 261.6, 329.6], [174.6, 220, 261.6], [261.6, 329.6, 392], [196, 246.9, 293.7]]
    n = int(duree * TAUX)
    out = np.zeros(n)
    d = duree / 4
    for k, ac in enumerate(suite):
        a = accord([f / 2 for f in ac] + ac, d * 1.25, 0.18, 900)
        d0 = int(k * d * TAUX)
        fin = min(n, d0 + len(a))
        out[d0:fin] += a[:fin - d0]
    t = np.arange(n) / n
    return _st(out * np.minimum(1, t / 0.08) * np.minimum(1, (1 - t) / 0.2), 0)


# ── la salle et la sono ─────────────────────────────────────────────────────────────────────────────────────
def reponse_salle(duree=1.9, r=None):
    r = r or _rng(12)
    n = int(duree * TAUX)
    t = np.arange(n) / TAUX
    ir = r.standard_normal((n, 2)) * np.exp(-t / 0.42)[:, None]
    ir = _bande(ir, None, 5000, 2)
    ir[:int(0.025 * TAUX)] = 0                                                  # pré-délai
    return ir / np.sqrt((ir ** 2).sum(axis=0))


def sono(x):
    """La voix de l'arbitre dans les haut-parleurs du stade : bande étroite, un peu saturée."""
    x = _bande(x, 280, 4800, 2)
    return np.tanh(2.2 * x / (np.abs(x).max() + 1e-9)) * 0.42


# ── vrais sons (paquet 302) ────────────────────────────────────────────────────────────────────────────────
# 20/11/2026 (Lucas : « On doit pouvoir récupérer des sons déjà faits ») : frappes, services, rebonds et public
# ENREGISTRÉS, tous sous licence Creative Commons 0 (domaine public), pris sur freesound.org, découpés et égalisés une
# fois (dossier sons/, sources dans sons/SOURCES.md). S'il manque un fichier, le son synthétique d'avant prend le relais.
DOSSIER_SONS = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sons')
_BANQUE = None


def banque():
    """{nom: liste d'extraits mono (frappes, services, rebonds) ou tableau stéréo (public)}, au taux du mixage."""
    global _BANQUE
    if _BANQUE is not None:
        return _BANQUE
    _BANQUE = {}
    try:
        with open(os.path.join(DOSSIER_SONS, 'banque.json'), encoding='utf-8') as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return _BANQUE
    for nom, m in meta.items():
        try:
            sr, x = wavfile.read(os.path.join(DOSSIER_SONS, nom + '.wav'))
        except (OSError, ValueError):
            continue
        x = x.astype(np.float64) / 32767
        if sr != TAUX:
            g = gcd(TAUX, sr)
            x = signal.resample_poly(x, TAUX // g, sr // g, axis=0)
        if 'case_s' in m:
            lg = int(round(m['case_s'] * TAUX))
            mono = x if x.ndim == 1 else x.mean(axis=1)
            _BANQUE[nom] = [mono[k * lg:(k + 1) * lg] for k in range(len(mono) // lg)]
        else:
            _BANQUE[nom] = x if x.ndim == 2 else np.stack([x, x], axis=1)
    return _BANQUE


def _extrait(x, duree, r, debut=None, fondu_entree=0.12, fondu_sortie=0.8):
    """Un morceau stéréo de `duree` s d'un enregistrement (bouclé en fondu s'il est trop court)."""
    n = int(duree * TAUX)
    if len(x) < n + 1:
        fo = int(1.0 * TAUX)
        rampe = np.linspace(0, 1, fo)[:, None]
        out = np.zeros((n + len(x), 2))
        pos = 0
        while pos < n:
            b = x.copy()
            b[:fo] *= rampe
            b[-fo:] *= rampe[::-1]
            out[pos:pos + len(b)] += b[:len(out) - pos]
            pos += len(x) - fo
        x = out
    d = int(r.integers(0, max(1, len(x) - n))) if debut is None else min(int(debut * TAUX), len(x) - n)
    y = x[d:d + n].copy()
    fe, fs = int(fondu_entree * TAUX), int(min(fondu_sortie, duree / 2) * TAUX)
    if fe:
        y[:fe] *= np.linspace(0, 1, fe)[:, None]
    if fs:
        y[-fs:] *= np.linspace(1, 0, fs)[:, None] ** 1.5
    return y


def pock(fort=1.0, r=None):
    """Frappe : un vrai enregistrement (service si fort > 1), sinon la frappe synthétique du paquet 301."""
    r = r or _rng(1)
    b = banque().get('services' if fort > 1 else 'frappes')
    if not b:
        return _pock_synth(fort, r)
    x = b[int(r.integers(len(b)))]
    return 0.9 * fort * x / (np.abs(x).max() + 1e-9)


def rebond(r=None):
    r = r or _rng(2)
    b = banque().get('rebonds')
    if not b:
        return _rebond_synth(r)
    x = b[int(r.integers(len(b)))]
    return 0.26 * x / (np.abs(x).max() + 1e-9)


def brouhaha(duree, r=None, niveau=0.06):
    """Le public entre les points : un vrai stade enregistré (même niveau moyen que l'ancien), sinon les voix
    synthétiques du paquet 300."""
    r = r or _rng(5)
    x = banque().get('public_murmure')
    if x is None:
        return _brouhaha_synth(duree, r, niveau)
    y = _extrait(x, duree, r, fondu_entree=min(1.0, duree / 3), fondu_sortie=min(1.0, duree / 3))
    return niveau * 0.42 * y / (np.sqrt((y ** 2).mean()) + 1e-9)


def applaudir(duree=2.6, densite=900, vol=0.5, r=None):
    """Applaudissements enregistrés (deux couches décalées si le public est nombreux), sinon synthétiques."""
    r = r or _rng(6)
    x = banque().get('public_applaudissements')
    if x is None:
        return _applaudir_synth(duree, densite, vol, r)
    y = _extrait(x, duree, r, fondu_sortie=duree * 0.45)
    if densite > 1500:
        y = y + 0.8 * _extrait(x, duree, r, fondu_sortie=duree * 0.45)[:, ::-1]
    return vol * y / (np.abs(y).max() + 1e-9)


def ovation(duree=3.8, r=None):
    """Grand point : la clameur d'un vrai stade (deux enregistrements au choix) sur des applaudissements."""
    r = r or _rng(9)
    B = banque()
    choix = [B[k] for k in ('public_ovation', 'public_ovation2') if k in B]
    if not choix:
        return _ovation_synth(duree, r)
    cri = _extrait(choix[int(r.integers(len(choix)))], duree, r, debut=0.0, fondu_entree=0.02, fondu_sortie=duree * 0.4)
    cri = cri / (np.abs(cri).max() + 1e-9)
    return 0.8 * cri + applaudir(duree, 1900, 0.35, r)


SONS = {
    'service': lambda r: _st(pock(1.25, r), 0), 'frappe0': lambda r: _st(pock(1.0, r), 0), 'frappe1': lambda r: _st(pock(0.8, r), 0),
    'rebond': lambda r: _st(rebond(r), 0), 'filet': lambda r: _st(filet(r), 0), 'crisse': lambda r: _st(crisse(r), 0),
    'applaudissements': lambda r: applaudir(2.6, 1000, 0.42, r), 'ovation': lambda r: ovation(3.8, r),
    'foule_entree': lambda r: ovation(4.5, r) * 0.8, 'houle': lambda r: houle(r),
    'volet': lambda r: souffle(0.55, r), 'vs': lambda r: _st(impact(r), 0),
    'annonce': lambda r: jingle(1), 'balle_match': lambda r: jingle(2), 'break': lambda r: jingle(3), 'set': lambda r: jingle(3),
    'jeu_decisif': lambda r: jingle(1), 'fin': lambda r: _somme(jingle(4), ovation(4.5, r)),
}
REVERBE = {'service': 0.25, 'frappe0': 0.25, 'frappe1': 0.25, 'rebond': 0.15, 'filet': 0.2, 'crisse': 0.15,
           'applaudissements': 0.3, 'ovation': 0.3, 'foule_entree': 0.3, 'houle': 0.35, 'voix': 0.45}


def piste(evenements, duree, chemin, voix=None, graine=7):
    """evenements : [{'t': s, 'type': nom, 'pan': −1…1, 'texte': …}] ; voix(texte) → tableau mono à TAUX ou None.
    Écrit un WAV stéréo 16 bits de `duree` secondes ; renvoie le nombre de phrases dites par l'arbitre."""
    r = _rng(graine)
    n = int(duree * TAUX)
    sec = np.zeros((n, 2))                                                      # sons secs
    hum = np.zeros((n, 2))                                                      # envoyés dans la salle
    public = brouhaha(duree, r)
    parle = np.zeros(n)
    dites = 0
    for e in sorted(evenements, key=lambda e: e['t']):
        t, nom = float(e['t']), e['type']
        if t < 0 or t >= duree:
            continue
        if nom == 'voix':
            if not voix or not e.get('texte'):
                continue
            v = voix(e['texte'])
            if v is None or not len(v):
                continue
            s = _st(sono(np.asarray(v, dtype=float)), 0)
            dites += 1
        elif nom in ('musique_intro', 'musique_fin'):
            s = nappe(float(e.get('duree') or 7.0), r)
        elif nom in SONS:
            s = SONS[nom](r)
            if nom in ('service', 'frappe0', 'frappe1', 'rebond', 'filet', 'crisse'):
                s = _st(s[:, 0] * np.sqrt(2), float(e.get('pan') or 0))
        else:
            continue
        d0 = int(t * TAUX)
        fin = min(n, d0 + len(s))
        sec[d0:fin] += s[:fin - d0]
        hum[d0:fin] += s[:fin - d0] * REVERBE.get(nom, 0.12)
        if nom == 'voix':
            parle[d0:fin] = 1
    # le public baisse quand l'arbitre parle (enveloppe lissée)
    baisse = 1 - 0.55 * signal.lfilter([0.0008], [1, -0.9992], parle)
    public *= np.clip(baisse, 0.4, 1)[:, None]
    ir = reponse_salle(1.9, r)
    salle = np.stack([signal.fftconvolve(hum[:, k] + public[:, k] * 0.25, ir[:, k])[:n] for k in (0, 1)], axis=1)
    mix = np.nan_to_num(sec + public + 0.55 * salle)
    rms = np.sqrt((mix ** 2).mean()) + 1e-9
    mix *= 0.16 / rms                                                           # niveau régulier d'une vidéo à l'autre
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)                                     # limiteur doux
    mix = np.clip(np.nan_to_num(mix), -0.98, 0.98)                            # jamais de silence par un calcul raté
    wavfile.write(chemin, TAUX, (mix * 32767).astype(np.int16))
    return dites
