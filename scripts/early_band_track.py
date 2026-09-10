#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
early_band_track.py — suivi de la piste « books précoces, cote 2,60-3,50 ».

    Le décalage entre le consensus des books ouverts AVANT Pinnacle et le
    premier prix de Pinnacle prédit-il le résidu de Pinnacle, sur les matchs
    de cote 2,60-3,50 ?

CE N'EST PAS UNE HYPOTHÈSE GELÉE. C'est un suivi d'observation, écrit le
09/09/2026 pour voir converger un signal plutôt que d'attendre deux mois.
Rien ici n'entre dans validation_report ni dans Holm.

──────────────────────────────────────────────────────────────────────────
CE QUI A ÉTÉ MESURÉ, ET CE QUI RESTE INCERTAIN

Sur 11 121 couples (match, book) où le book a ouvert avant Pinnacle, la
corrélation entre le décalage et le résidu de Pinnacle vaut +0,060 en
moyenne. Découpée par tranche de cote :

    < 1,60      n=4074   r=+0,011   [-0,020 ; +0,042]
    1,60-2,00   n=2271   r=+0,042   [+0,001 ; +0,083]
    2,00-2,60   n=1958   r=+0,040   [-0,004 ; +0,084]
    2,60-3,50   n=1446   r=+0,165   [+0,114 ; +0,215]   <- trois fois plus
    > 3,50      n=1372   r=+0,037   [-0,016 ; +0,090]

Sur observations INDÉPENDANTES (244 matchs, un consensus par match) :
    ensemble    r=+0,242   [+0,120 ; +0,357]
    1re moitié  r=+0,322   [+0,153 ; +0,473]
    2e  moitié  r=+0,123   [-0,056 ; +0,294]   <- ne franchit plus le seuil

TROIS RAISONS DE SE MÉFIER :
  1. la tranche a été choisie APRÈS avoir vu que l'ensemble donnait un
     signal faible — sept tranches testées ;
  2. la seconde moitié ne réplique pas la significativité ;
  3. le ROI ne réplique pas non plus : +15,5 % puis -2,1 %.

UNE RAISON D'Y CROIRE : la zone n'est pas arbitraire. Le rapport de
robustesse externe identifiait 2,50-4,00, l'hypothèse gelée n°13 porte sur
2,00-3,00, et cette analyse tombe sur 2,60-3,50. Trois découpages menés
indépendamment convergent vers la même région.

C'est pour trancher entre ces deux lectures que ce suivi existe : à ~100
matchs par mois dans la bande, deux mois donneront une réponse nette.

Env : CURVES (déf. book_curves.jsonl), OUT, SET_RESULTS, TELEGRAM_*,
      DRY_RUN=1.
"""
import os
import sys
import csv
import json
import math
import datetime
import statistics as st
import collections
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov      # noqa: E402

CURVES = os.environ.get('CURVES', 'book_curves.jsonl')
OUT = os.environ.get('OUT', 'early_band_detail.csv')
SET_RESULTS = os.environ.get('SET_RESULTS', 'set_results.json')
SHARP = os.environ.get('SHARP', 'pinnacle')
EXCLURE = {'pinnacle', 'betfair-ex', 'betfair', 'matchbook', 'smarkets'}
COTE_MIN, COTE_MAX = 2.60, 3.50      # la bande observée
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'

# Références in-sample au 09/09, pour situer la mesure du jour.
REF_R, REF_N = 0.242, 244


def _dt(s):
    try:
        return datetime.datetime.fromisoformat(
            str(s).replace('Z', '').replace('+00:00', ''))
    except (ValueError, TypeError):
        return None


def _pts(seq):
    out = []
    for p in (seq or []):
        if isinstance(p, (list, tuple)) and len(p) >= 2:
            t = _dt(p[0])
            try:
                v = float(p[1])
            except (TypeError, ValueError):
                continue
            if t and v > 1:
                out.append((t, v))
    out.sort()
    return out


def _avant(serie, t):
    v = None
    for tt, o in serie:
        if tt <= t:
            v = o
        else:
            break
    return v


def shin_ph(oh, oa):
    """Probabilité home dévigée (Shin). Même formule que le reste du projet."""
    ih, ia = 1 / oh, 1 / oa
    s = ih + ia
    if s <= 1:
        return ih / s
    z = 0.02
    for _ in range(40):
        ph = (math.sqrt(z * z + 4 * (1 - z) * ih * ih / s) - z) / (2 * (1 - z))
        pa = (math.sqrt(z * z + 4 * (1 - z) * ia * ia / s) - z) / (2 * (1 - z))
        t = ph + pa
        if abs(t - 1) < 1e-9:
            break
        z += 0.01 if t > 1 else -0.01
        z = max(0.0, min(0.5, z))
    return ph


def collecter():
    """Un enregistrement par match : consensus des books précoces vs Pinnacle.

    DEUX PASSES, et c'est indispensable pour deux raisons.

    MÉMOIRE. Les partitions hist_book pèsent ~600 Mo ; tout charger d'un
    coup fait tuer le process par l'OOM killer du runner (constaté le
    09/09). On ne conserve jamais une courbe entière.

    JUSTESSE. Le prix retenu pour chaque book est celui EN VIGUEUR À
    L'INSTANT OÙ PINNACLE OUVRE, pas le prix d'ouverture du book. La
    différence n'est pas cosmétique : mesurée sur l'historique, la
    corrélation vaut +0,242 avec le prix à t_pin et +0,019 avec le prix
    d'ouverture. Un book ouvert huit heures plus tôt a eu le temps de se
    corriger ; c'est son état au moment de la confrontation qui porte
    l'information, pas son premier jet.
    """
    try:
        RES = json.load(open(SET_RESULTS, encoding='utf-8'))
    except (OSError, ValueError):
        RES = {}

    # ── passe 1 : Pinnacle seul -> t_pin, prix d'ouverture, clôture ──
    PIN, meta = {}, {}
    try:
        for ligne in ov.open_curves(CURVES):
            ligne = ligne.strip()
            if not ligne or '"' + SHARP + '"' not in ligne:
                continue
            try:
                r = json.loads(ligne)
            except ValueError:
                continue
            if r.get('book') != SHARP:
                continue
            u, ct = r.get('uid'), _dt(r.get('commence_time'))
            h, a_ = _pts(r.get('home_curve')), _pts(r.get('away_curve'))
            if not u or not ct or not h or not a_:
                continue
            PIN[u] = {'t': max(h[0][0], a_[0][0]), 'oh': h[0][1],
                      'oa': a_[0][1], 'ch': _avant(h, ct), 'ct': ct}
            meta[u] = {'tour': r.get('tournament')}
    except FileNotFoundError as e:
        print(f"  ❌ {e}")
        return []
    if not PIN:
        return []

    # ── passe 2 : books mous -> prix EN VIGUEUR à t_pin ──
    obs = collections.defaultdict(list)
    for ligne in ov.open_curves(CURVES):
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            r = json.loads(ligne)
        except ValueError:
            continue
        u, b = r.get('uid'), r.get('book')
        if b in EXCLURE or u not in PIN:
            continue
        h, a_ = _pts(r.get('home_curve')), _pts(r.get('away_curve'))
        if not h or not a_:
            continue
        t_pin = PIN[u]['t']
        if min(h[0][0], a_[0][0]) >= t_pin:
            continue                      # pas ouvert avant Pinnacle
        vh, va = _avant(h, t_pin), _avant(a_, t_pin)
        if vh and va:
            obs[u].append((b, vh, va))

    out = []
    for u, cotes in obs.items():
        if len(cotes) < 3:
            # Sous 3 books, le « consensus » n'en est pas un : l'écart-type
            # entre books vaut 0,74 pt, un seul book porterait tout le bruit.
            continue
        P = PIN[u]
        ch = P['ch']
        if not ch or not (COTE_MIN <= ch < COTE_MAX):
            continue
        p_pin = shin_ph(P['oh'], P['oa'])
        p_book = st.mean([shin_ph(vh, va) for _, vh, va in cotes])
        delta = p_book - p_pin
        side = 'home' if delta > 0 else 'away'
        best = max(cotes, key=lambda c: c[1] if side == 'home' else c[2])
        cote = best[1] if side == 'home' else best[2]
        g = (RES.get(u) or {}).get('match')
        win = None if g not in ('home', 'away') else (1 if g == 'home' else 0)
        rec = {'date': P['ct'].date().isoformat(), 'uid': u,
               'tournoi': meta[u]['tour'], 'n_books': len(cotes),
               'p_book': round(p_book, 4), 'p_pin': round(p_pin, 4),
               'delta_pts': round(100 * delta, 3), 'cote_pin_clot': ch,
               'side': side, 'book': best[0], 'cote': cote}
        if win is not None:
            w = win if side == 'home' else 1 - win
            rec.update({'win_home': win, 'gagne': 'oui' if w else 'non',
                        'pnl': round((cote - 1) if w else -1, 2),
                        'residu': round(win - p_pin, 4)})
        else:
            rec.update({'win_home': '', 'gagne': '', 'pnl': '', 'residu': ''})
        out.append(rec)
    return out


def corr_ic(xs, ys):
    if len(xs) < 10 or st.pstdev(xs) == 0 or st.pstdev(ys) == 0:
        return None
    r = st.correlation(xs, ys)
    if abs(r) >= 1:
        return None
    n = len(xs)
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1 / math.sqrt(n - 3)
    return r, math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se), n


def envoyer(txt):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat = os.environ.get('TELEGRAM_CHAT_ID')       # PRIVÉ uniquement
    if DRY_RUN or not token or not chat:
        print(txt.replace('<b>', '').replace('</b>', '')
              .replace('<i>', '').replace('</i>', ''))
        return False
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=urllib.parse.urlencode(
                {'chat_id': chat, 'text': txt, 'parse_mode': 'HTML',
                 'disable_web_page_preview': 'true'}).encode())
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print(f"  ⚠️ Telegram : {e}")
        return False


def main():
    recs = collecter()
    if not recs:
        print("  aucun match exploitable.")
        return 0
    cols = ['date', 'uid', 'tournoi', 'n_books', 'p_book', 'p_pin',
            'delta_pts', 'cote_pin_clot', 'side', 'book', 'cote',
            'win_home', 'gagne', 'pnl', 'residu']
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(recs)

    den = [r for r in recs if r['gagne'] in ('oui', 'non')]
    L = [f"🔬 <b>Piste books précoces</b> — cote {COTE_MIN:.2f}-{COTE_MAX:.2f}",
         f"\n{len(recs)} matchs · {len(den)} dénoué(s)"]
    if den:
        c = corr_ic([r['delta_pts'] for r in den], [r['residu'] for r in den])
        if c:
            r, lo, hi, n = c
            fl = '✅' if lo > 0 else ('❌' if hi < 0 else '—')
            L.append(f"corrélation décalage ↔ résidu : <b>{r:+.3f}</b> "
                     f"[{lo:+.3f} ; {hi:+.3f}] {fl}")
            L.append(f"<i>référence in-sample au 09/09 : "
                     f"{REF_R:+.3f} sur {REF_N} matchs</i>")
        pnl = [r['pnl'] for r in den]
        k = sum(1 for r in den if r['gagne'] == 'oui')
        p0 = st.mean([1 / r['cote'] for r in den])
        roi = 100 * st.mean(pnl)
        ic = 1.96 * st.pstdev(pnl) / math.sqrt(len(pnl)) * 100
        L.append(f"\nROI {roi:+.1f} % [{roi-ic:+.1f} ; {roi+ic:+.1f}] · "
                 f"gains {k}/{len(den)} = {100*k/len(den):.1f} % "
                 f"(équilibre {100*p0:.1f} %)")
        L.append(f"<i>ROI in-sample : +15,5 % puis -2,1 % sur deux moitiés — "
                 f"il ne réplique PAS. C'est la corrélation qu'il faut "
                 f"suivre, pas le ROI.</i>")
    L.append(f"\n<i>Observation, PAS une hypothèse gelée. La bande a été "
             f"choisie après exploration (7 tranches testées) et la seconde "
             f"moitié historique ne réplique pas la significativité. "
             f"Ne rien en conclure avant ~200 matchs dénoués.</i>")
    txt = '\n'.join(L)
    ok = envoyer(txt)
    print(f"\n  {len(recs)} matchs -> {OUT} · envoi {'OK' if ok else 'non effectué'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
