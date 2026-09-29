#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kalshi_lead_track.py — collecteur d'observations pour l'HYPOTHÈSE GELÉE N°13.

    « L'écart entre le prix Kalshi et la probabilité Pinnacle dévigée (Shin)
      PRÉDIT le sens du mouvement de Pinnacle dans les 45 minutes suivantes. »

Gelée le 2026-09-05. Tous les paramètres ci-dessous sont FIXÉS et ne doivent
plus bouger : c'est la seule chose qui distingue une hypothèse d'un ajustement
rétrospectif.

──────────────────────────────────────────────────────────────────────────
POURQUOI CETTE HYPOTHÈSE, ET POURQUOI ELLE SEULE

Exploration du 05/09/2026 sur 7 jours de ticks (3,3 M de points, 730 matchs
Kalshi, 113 Polymarket), croisés aux courbes Pinnacle et aux résultats :

  - Kalshi et Pinnacle affichent LE MÊME PRIX : écart moyen +0,00 pt,
    écart-type 0,89 pt sur 21 000 instants liquides. Aucun arbitrage : un
    aller-retour Kalshi coûte ~2,2 pts (0,5 de demi-fourchette + ~1,7 de
    frais), l'écart dépasse ce seuil dans 1,3 % des instants seulement.
  - Aucune dérive : entre T-240 et T-10 le prix Kalshi bouge de 0,00 pt en
    médiane, |dérive| > 5 pts dans 0 % des 177 matchs. Le log-loss à T-240
    (0,5511) est identique à celui de T-10 (0,5518) : ces marchés n'ajoutent
    AUCUNE information en quatre heures.
  - Calibration : 33 tests de zones (source x marché x horizon x tranche de
    prix) sur observations indépendantes, correction Holm-Bonferroni ->
    ZÉRO survivant. Le plus petit p vaut 0,063 pour un seuil à 0,0015.

Le seul signal qui ait survécu à l'exploration :

  corrélation(écart Kalshi−Pinnacle ; mouvement Pinnacle à +45 min)
      = +0,163   IC95 [+0,012 ; +0,306]   n = 170

Il est faible, sa borne basse frôle zéro, et le gradient par tranche d'écart
est plat — profil typique d'un artefact porté par quelques points extrêmes.
D'où le gel plutôt que l'exploitation.

Corollaire, si elle tient : l'usage n'est PAS de trader Kalshi (les frais
l'interdisent) mais d'ANTICIPER les mouvements Pinnacle, donc d'améliorer le
timing du canal — là où le CLV est déjà démontré à +8 % médian.

──────────────────────────────────────────────────────────────────────────
PARAMÈTRES GELÉS — NE PLUS TOUCHER

  source           Kalshi uniquement, marché 'match'
                   (Polymarket exclu : fourchette médiane 4 pts contre 1,
                    profondeur 150 contre 2106, deux fois moins de matchs)
  liquidité        fourchette <= 2 pts au moment de l'observation
  écart            p_kalshi(home) − p_pinnacle_shin(home), en points
  horizon          +45 minutes
  grille           1 observation par match et par tranche de 30 min
  SEUIL_SIGNAL     |écart| >= 1,0 pt

Sur le SEUIL, qui est le seul degré de liberté réel : l'exploration donnait
0,5 -> 58,6 % · 1,0 -> 60,8 % · 1,5 -> 86,7 % · 2,0 -> 100 %.
Prendre 1,5 (86,7 %) serait choisir le seuil APRÈS avoir vu le résultat, sur
n=15. On retient 1,0 pt parce qu'il vaut ~1 écart-type de la divergence
Kalshi−Pinnacle (0,89 pt), grandeur mesurée INDÉPENDAMMENT et avant ce test.
C'est le seul choix qui ne soit pas rétrospectif.

──────────────────────────────────────────────────────────────────────────
TEST : test de signe contre GROUPE TÉMOIN

Succès = sign(mouvement Pinnacle à +45 min) == sign(écart initial).

H0 n'est PAS « 50 % ». Le groupe |écart| < 1,0 pt affiche déjà 57,3 % de
succès : il existe une tendance de fond, indépendante de tout signal, à ce
que le mouvement suive le signe de l'écart même minuscule. Comparer le
groupe signal à 50 % rejetterait H0 pour cette seule raison.
p0 = taux de succès du groupe témoin, recalculé à CHAQUE lecture sur les
données out-of-sample. Même parti pris que p0_temoin() pour les hypothèses
CLV (audit du 25/08 : « son H0 honnête est pas mieux que le move moyen, pas
pas mieux qu'une pièce »).

Référence in-sample au gel (NON confirmatoire, pour mémoire) :
    signal n=51  60,8 %  IC95 [47,1 ; 73,0]
    témoin n=117 57,3 %

Env : KX_GLOB, PIN_SOURCE, OBS_OUT, HORIZON_MIN, SEUIL_SIGNAL_PTS.
"""
import os
import sys
import json
import glob
import gzip
import math
import bisect
import datetime
import unicodedata
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov  # noqa: E402

FREEZE_DATE = '2026-09-05'
HORIZON_MIN = float(os.environ.get('HORIZON_MIN', '45'))
SEUIL_SIGNAL = float(os.environ.get('SEUIL_SIGNAL_PTS', '1.0'))
MAX_SPREAD = 0.02
TOL_PIN_MIN = 8.0          # appariement temporel Pinnacle, serré volontairement
GRILLE_MIN = 30
KX_GLOB = os.environ.get('KX_GLOB', 'parts/kx_ticks_*.jsonl*')
OBS_OUT = os.environ.get('OBS_OUT', 'kalshi_lead_obs.jsonl')


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z]', '', s)


def _ts(s):
    try:
        return datetime.datetime.fromisoformat(str(s).replace('Z', '').replace('+00:00', ''))
    except (ValueError, TypeError):
        return None


def shin(oh, oa):
    """Dévigage Shin à 2 issues — même formule que canal_public.py.

    Validé indépendamment le 05/09 : le mid Kalshi et cette probabilité
    coïncident à 0,89 pt d'écart-type sur 21 000 instants. C'est la
    validation la plus solide dont dispose le projet sur le dévigage.
    """
    if not oh or not oa or oh <= 1 or oa <= 1:
        return None
    ph, pa = 1.0 / oh, 1.0 / oa
    s = ph + pa
    if s <= 1:
        return ph
    z = max(0.0, min(0.2, (s - 1) / (s + 1) * 2))
    if z >= 1:
        return ph / s

    def f(p):
        return (math.sqrt(z * z + 4 * (1 - z) * p * p / s) - z) / (2 * (1 - z))
    h, a = f(ph), f(pa)
    return h / (h + a) if (h + a) else None


def charger_pinnacle():
    """Courbes Pinnacle dévigées, indexées par (date, noms normalisés)."""
    try:
        cl = json.load(open('closing_lines.json', encoding='utf-8'))
    except (OSError, ValueError) as e:
        print(f"  ❌ closing_lines.json illisible ({e}) — rien à faire.")
        return {}
    items = cl.values() if isinstance(cl, dict) else cl
    idx = {}
    for m in items:
        if not isinstance(m, dict):
            continue
        ct = m.get('commence_time')
        serie = []
        for p in (m.get('history') or []):
            if not isinstance(p, dict):
                continue
            pr = shin(p.get('home'), p.get('away'))
            t = _ts(p.get('t'))
            if pr is not None and t is not None:
                serie.append((t, pr))
        if len(serie) >= 2 and ct:
            cle = (str(ct)[:10], _norm(m.get('home')) + _norm(m.get('away')))
            idx[cle] = sorted(serie)
    return idx


def prob_pin(serie, t):
    ts = [x[0] for x in serie]
    i = bisect.bisect_left(ts, t)
    best = None
    for j in (i - 1, i):
        if 0 <= j < len(serie):
            dt = abs((serie[j][0] - t).total_seconds()) / 60.0
            if dt <= TOL_PIN_MIN and (best is None or dt < best[0]):
                best = (dt, serie[j][1])
    return best[1] if best else None


def collecter():
    pin = charger_pinnacle()
    if not pin:
        return []
    fichiers = sorted(glob.glob(KX_GLOB))
    if not fichiers:
        print(f"  ⚠️ aucune partition Kalshi ({KX_GLOB}).")
        return []
    # AVERTISSEMENT DE TRONCATURE : archive_ticks.py sort les partitions de
    # plus de 7 jours vers les Releases GitHub. Une étude qui globe parts/
    # ne voit qu'une fenêtre glissante — sans le dire.
    try:
        ai = json.load(open('parts/ARCHIVE_INDEX.json', encoding='utf-8'))
        d = sorted({a['date'] for a in ai.get('archives', []) if 'kx_ticks' in a.get('fichier', '')})
        if d:
            print(f"  ⚠️ historique tronqué : partitions Kalshi du {d[0]} au {d[-1]} "
                  f"archivées hors git (voir parts/ARCHIVE_INDEX.json)")
    except (OSError, ValueError):
        pass

    series = {}
    for f in fichiers:
        ouvre = gzip.open if f.endswith('.gz') else open
        try:
            fh = ouvre(f, 'rt', encoding='utf-8')
        except OSError:
            continue
        for ligne in fh:
            try:
                r = json.loads(ligne)
            except ValueError:
                continue
            if r.get('local_side') != 'home':
                continue
            u, mid, sp = r.get('local_uid'), r.get('mid'), r.get('spread')
            if not u or not isinstance(mid, (int, float)) or not (0 < mid < 1):
                continue
            if not isinstance(sp, (int, float)) or sp > MAX_SPREAD:
                continue
            t = _ts(r.get('ts'))
            if t is None:
                continue
            series.setdefault(u, []).append((t, mid))

    obs = []
    for u, pts in series.items():
        cle = (u[:10], _norm(u[11:]))
        if cle not in pin:
            continue
        serie = pin[cle]
        vus = set()
        for t, mid in sorted(pts):
            g = t.replace(minute=(t.minute // GRILLE_MIN) * GRILLE_MIN,
                          second=0, microsecond=0)
            if g in vus:
                continue
            p0 = prob_pin(serie, t)
            p1 = prob_pin(serie, t + datetime.timedelta(minutes=HORIZON_MIN))
            if p0 is None or p1 is None:
                continue
            vus.add(g)
            obs.append({
                'uid': u,
                't': t.isoformat(timespec='seconds'),
                'ecart_pts': round(100 * (mid - p0), 3),
                'mvt_pts': round(100 * (p1 - p0), 3),
                'p_kalshi': round(mid, 4),
                'p_pinnacle': round(p0, 4),
                'horizon_min': HORIZON_MIN,
                'seuil_gele': SEUIL_SIGNAL,
                'gele_le': FREEZE_DATE,
            })
    return obs


def fusionner(obs):
    """Journal APPEND-ONLY, dédupliqué sur (uid, t). Permanent.

    Les partitions de ticks sont purgées et archivées ; ce fichier est la
    seule trace durable des observations. Le rejeu d'anciennes partitions ne
    doit jamais dupliquer une observation déjà enregistrée.
    """
    deja = set()
    try:
        for ligne in open(OBS_OUT, encoding='utf-8'):
            try:
                r = json.loads(ligne)
                deja.add((r.get('uid'), r.get('t')))
            except ValueError:
                continue
    except OSError:
        pass
    neuf = [o for o in obs if (o['uid'], o['t']) not in deja]
    if neuf:
        with open(OBS_OUT, 'a', encoding='utf-8') as f:
            for o in neuf:
                f.write(json.dumps(o, ensure_ascii=False) + '\n')
    return len(neuf), len(deja) + len(neuf)


def main():
    print(f"HYPOTHÈSE GELÉE N°13 — Kalshi mène-t-il Pinnacle ? (gel {FREEZE_DATE})")
    print(f"  horizon {HORIZON_MIN:.0f} min · seuil signal {SEUIL_SIGNAL:.1f} pt · "
          f"fourchette <= {100 * MAX_SPREAD:.0f} pts")
    obs = collecter()
    if not obs:
        print("  aucune observation exploitable ce run.")
        return 0
    neuf, total = fusionner(obs)
    print(f"  {len(obs)} observation(s) construite(s) · {neuf} nouvelle(s) · "
          f"{total} au journal {OBS_OUT}")
    # Le VERDICT est rendu par validation_report.kalshi_lead_watch(), qui
    # applique le plancher n>=30, le filtre out-of-sample et Holm. Ici on ne
    # fait que collecter : un collecteur qui conclurait serait un second
    # juge, et deux juges finissent par diverger.
    return 0


if __name__ == '__main__':
    sys.exit(main())
