#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h13_recap.py — suivi QUOTIDIEN de l'hypothèse gelée n°13, sur Telegram privé.

    « Parier le côté steamé au book d'entrée, cote entre 2,00 et 3,00,
      SANS aucun autre filtre. »  — gelée le 2026-09-06

Envoie chaque jour, sur le canal PRIVÉ (TELEGRAM_CHAT_ID), l'avancement
out-of-sample : ROI, CLV, taux de gain contre le seuil de rentabilité, et la
distance restante avant que le verdict soit lisible.

──────────────────────────────────────────────────────────────────────────
POURQUOI CE SCRIPT NE CALCULE RIEN LUI-MÊME

Il importe H13_COTE_MIN/MAX et FREEZE_DATE_ROIBANDE depuis
validation_report.py, et lit le même moves_detail_hist.csv. Aucune constante
n'est redéfinie ici.

C'est délibéré : trois programmes regardent désormais la même population —
le watcher qui juge, h13_signal.py qui alerte en direct, et ce récapitulatif.
S'ils portaient chacun leur copie de la bande, il suffirait d'en modifier une
pour que le suivi affiche autre chose que ce qui sera validé, sans qu'aucune
erreur ne se déclenche. Le projet a déjà connu ça : trois copies de
player_match() avaient dérivé au point qu'une seule était correcte.

CE SCRIPT NE REND PAS DE VERDICT. Le verdict appartient à
validation_report.roi_bande_watch(), qui applique le plancher n>=30, N_CIBLE
et Holm. Ici on informe, on ne conclut pas — deux juges finissent par
diverger.

──────────────────────────────────────────────────────────────────────────
LECTURE DU MESSAGE

  ROI       = (taux de gain / seuil de rentabilité - 1). Le seuil est la
              moyenne des 1/cote sur les paris retenus : c'est le taux
              qu'il faut dépasser pour gagner de l'argent, et il varie avec
              les cotes réellement rencontrées. Comparer à 50 % n'aurait
              aucun sens.
  CLV       = médiane de clv_book_pct, l'écart entre le prix d'entrée et la
              clôture du MÊME book. Indicateur avancé : il se stabilise bien
              plus vite que le ROI, et c'est lui qui dira le plus tôt si
              l'hypothèse tient.
  IC95      = Wilson sur le taux de gain. Tant qu'il contient le seuil de
              rentabilité, rien n'est démontré.

Env : TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, DRY_RUN=1, N_LISIBLE (déf. 300).
"""
import os
import sys
import csv
import math
import datetime
import statistics as st
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import validation_report as vr      # noqa: E402  — source unique de la bande

SRC = os.environ.get('MOVES', 'moves_detail_hist.csv')
# Volume à partir duquel l'IC95 a une chance d'exclure le seuil de
# rentabilité, estimé le 06/09 sur la variance observée dans la bande.
# Sert uniquement à afficher une progression : ce n'est pas un critère.
N_LISIBLE = int(os.environ.get('N_LISIBLE', '300'))
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def charger():
    """Paris de la bande, séparés in-sample / out-of-sample."""
    ins, outs = [], []
    try:
        fh = open(SRC, encoding='utf-8')
    except OSError:
        return None, None
    with fh:
        for r in csv.DictReader(fh):
            try:
                cote = float(r['entry'])
            except (TypeError, ValueError, KeyError):
                continue
            if not (vr.H13_COTE_MIN <= cote <= vr.H13_COTE_MAX):
                continue
            g = r.get('steame_gagne')
            if g not in ('oui', 'non'):
                continue                  # pari non dénoué
            try:
                clv = float(r['clv_book_pct'])
            except (TypeError, ValueError, KeyError):
                clv = None
            pari = {'date': str(r.get('date') or '')[:10], 'cote': cote,
                    'win': 1 if g == 'oui' else 0, 'clv': clv}
            (outs if pari['date'] >= vr.FREEZE_DATE_ROIBANDE else ins).append(pari)
    return ins, outs


def bloc(paris):
    if not paris:
        return None
    n = len(paris)
    k = sum(p['win'] for p in paris)
    p0 = st.mean([1.0 / p['cote'] for p in paris])
    lo, hi = wilson(k, n)
    clvs = [p['clv'] for p in paris if p['clv'] is not None]
    return {'n': n, 'k': k, 'taux': k / n, 'p0': p0,
            'roi': (k / n) / p0 - 1 if p0 else 0.0,
            'lo': lo, 'hi': hi,
            'clv': st.median(clvs) if clvs else None,
            'cote': st.median([p['cote'] for p in paris])}


def message(outs, ins, hier):
    b = bloc(outs)
    L = [f"📊 <b>H13 — suivi quotidien</b> (bande "
         f"{vr.H13_COTE_MIN:.2f}-{vr.H13_COTE_MAX:.2f})"]
    if not b:
        L.append(f"\nAucun pari dénoué depuis le gel du "
                 f"{vr.FREEZE_DATE_ROIBANDE}.")
        L.append(f"\n<i>Débit attendu : ~105 paris/mois. "
                 f"Premier verdict lisible vers {N_LISIBLE} paris.</i>")
        return '\n'.join(L)

    signe = '+' if b['roi'] >= 0 else ''
    L.append(f"\n<b>ROI {signe}{100 * b['roi']:.1f} %</b> "
             f"sur {b['n']} pari(s) dénoué(s)")
    L.append(f"gains {b['k']}/{b['n']} = {100 * b['taux']:.1f} % · "
             f"rentabilité à {100 * b['p0']:.1f} % · cote médiane {b['cote']:.2f}")
    L.append(f"IC95 du taux : [{100 * b['lo']:.1f} ; {100 * b['hi']:.1f}]")
    if b['clv'] is not None:
        L.append(f"CLV médian {b['clv']:+.1f} % <i>(indicateur avancé)</i>")

    # Progression : ce qui manque avant que le verdict soit lisible.
    reste = max(0, N_LISIBLE - b['n'])
    if reste:
        jours = reste / 3.5          # ~105 paris/mois
        L.append(f"\nAvancement : {b['n']}/{N_LISIBLE} "
                 f"({100 * b['n'] / N_LISIBLE:.0f} %) · "
                 f"~{jours:.0f} jours restants")
    # Verdict lisible ? On le DIT sans le rendre : c'est roi_bande_watch()
    # qui juge, avec Holm et le plancher n>=30.
    if 100 * b['lo'] > 100 * b['p0']:
        L.append("\n⚠️ L'IC95 est passé AU-DESSUS du seuil de rentabilité. "
                 "Verdict à lire dans validation_report, pas ici.")
    elif 100 * b['hi'] < 100 * b['p0']:
        L.append("\n⚠️ L'IC95 est passé SOUS le seuil de rentabilité. "
                 "Verdict à lire dans validation_report, pas ici.")

    if hier:
        L.append(f"\nDernières 24 h : {hier['n']} pari(s), "
                 f"{hier['k']} gagné(s)"
                 + (f", CLV médian {hier['clv']:+.1f} %"
                    if hier['clv'] is not None else ""))

    bi = bloc(ins)
    if bi:
        L.append(f"\n<i>Référence in-sample au gel, NON confirmatoire : "
                 f"{bi['k']}/{bi['n']} = {100 * bi['taux']:.1f} %, "
                 f"ROI {100 * bi['roi']:+.1f} %. Hypothèse NON VALIDÉE — "
                 f"ne pas diffuser.</i>")
    return '\n'.join(L)


def envoyer(texte):
    token = os.environ.get('TELEGRAM_TOKEN')
    chat = os.environ.get('TELEGRAM_CHAT_ID')       # PRIVÉ uniquement
    if DRY_RUN or not token or not chat:
        print(texte.replace('<b>', '').replace('</b>', '')
              .replace('<i>', '').replace('</i>', ''))
        return False
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=urllib.parse.urlencode(
                {'chat_id': chat, 'text': texte, 'parse_mode': 'HTML',
                 'disable_web_page_preview': 'true'}).encode())
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print(f"  ⚠️ Telegram : {e}")
        return False


def main():
    ins, outs = charger()
    if ins is None:
        print(f"  ❌ {SRC} illisible.")
        return 0
    veille = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
    hier = bloc([p for p in outs if p['date'] == veille])
    txt = message(outs, ins, hier)
    ok = envoyer(txt)
    print(f"  {len(outs)} pari(s) out-of-sample · {len(ins)} in-sample · "
          f"envoi {'OK' if ok else 'non effectué'}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
