#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zone_signal.py — ZONE DE COTE 2,50-3,20, observation en temps réel.

    Parier le côté steamé au book d'entrée quand sa cote se situe entre
    2,50 et 3,20 au moment de la détection.

CE N'EST PAS UNE HYPOTHÈSE GELÉE. Aucune entrée dans validation_report ni
dans Holm. C'est un suivi d'observation, écrit le 11/09/2026.

──────────────────────────────────────────────────────────────────────────
POURQUOI CETTE ZONE, ET POURQUOI ELLE N'EST PAS GELÉE

Découpage du côté steamé par tranche de cote, sur 1 419 matchs :

    < 1,50       n=286  ROI  +0,4 %
    1,50-1,80    n=258  ROI  -1,6 %
    1,80-2,10    n=169  ROI  -2,0 %
    2,10-2,50    n=230  ROI  -2,5 %
    2,50-3,20    n=196  ROI +13,7 %
    3,20-5,00    n=196  ROI +24,8 %
    > 5,00       n= 84  ROI -17,9 %

Quatre tranches plates, deux hautes, une chute. Testé en découpage
temporel — exploration sur la 1re moitié, validation sur la 2e :

    2,50-3,20   +12,7 % (n=117)  ->  +15,3 % (n=79)   RÉPLIQUE
    3,20-5,00   +43,1 % (n= 98)  ->   +6,5 % (n=98)   s'effondre

3,20-5,00 est le piège classique : intervalle excluant zéro en
exploration, rien en validation. C'est elle qui portait le +24,8 % de la
moyenne. Seule 2,50-3,20 survit, à 2,6 points d'écart entre les deux
moitiés.

PAS GELÉE pour trois raisons :
  1. la zone a été trouvée en découpant sept tranches APRÈS avoir vu la
     moyenne — le contexte exact où l'on fabrique des faux positifs ;
  2. les deux intervalles traversent zéro (n=117 et n=79) ;
  3. elle est un SOUS-ENSEMBLE de l'hypothèse 13 (2,00-3,00) sur 81 % de
     son volume : la geler ferait payer Holm deux fois pour le même effet.

Quatre analyses indépendantes convergent pourtant vers cette région : le
rapport de robustesse externe (2,50-4,00), l'hypothèse 13 (2,00-3,00),
l'analyse des books précoces (2,60-3,50) et celle-ci. Intersection :
2,50-3,00. C'est ce qui justifie de l'observer, pas de la jouer.

──────────────────────────────────────────────────────────────────────────
DOUBLONS : LOGUÉ TOUJOURS, ENVOYÉ PARFOIS

81 % des matchs de cette zone déclenchent DÉJÀ une alerte h13_signal
(bande 2,00-3,00). Envoyer un second message ferait doublon sur quatre
alertes sur cinq.

Le journal enregistre donc TOUS les matchs de la zone — la mesure doit
être complète — mais le message Telegram n'est envoyé que si h13_signal
n'a pas déjà couvert ce match (champ `doublon_h13` dans le journal).

Env : CURVES, SHARP, THR, MIN_LEAD, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
      DRY_RUN=1. La BANDE n'est pas paramétrable.
"""
import os
import sys
import json
import datetime
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import oddspapi_v5 as ov      # noqa: E402

CURVES = os.environ.get('CURVES', 'book_curves_live.jsonl')
SHARP = os.environ.get('SHARP', 'pinnacle')
import validation_report as _vr      # noqa: E402 — source unique des
                                     # constantes gelées (bande, books)

# BOOKS D'ENTRÉE : importés de validation_report, comme la bande de cote.
# Ce script vit dans courbes_alertes.yml, move_audit.py dans
# steam_pipeline.yml : deux variables d'environnement séparées auraient
# laissé le détecteur temps réel travailler sur 3 books pendant que
# l'hypothèse se validait sur 7.
SOFTS = list(_vr.H14_SOFTS)
THR = float(os.environ.get('THR', '0.02'))
MIN_LEAD = float(os.environ.get('MIN_LEAD', '5'))
# BANDE : importée de validation_report, JAMAIS redéfinie ici.
# La version précédente la lisait dans l'environnement, ce qui permettait à
# un COTE_MAX=3.5 posé "pour voir" de faire diverger silencieusement ce
# canal de ce que roi_bande_watch() valide. Une seule source de vérité.
# Bande propre à cette observation — volontairement PAS celle de
# l'hypothèse 13, qu'on ne touche pas.
COTE_MIN, COTE_MAX = 2.50, 3.20
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'

ETAT = 'zone_signal_state.json'      # anti-doublon, un signal par match
LOG = 'zone_signal_log.jsonl'        # journal PERMANENT, append-only
OBSERVE_DEPUIS = '2026-09-11'


def _dt(s):
    try:
        d = datetime.datetime.fromisoformat(
            str(s).replace('Z', '').replace('+00:00', ''))
        return d.replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _at(serie, t):
    """Dernière valeur connue À t. Strictement causal : jamais d'interpolation,
    jamais un point postérieur. Copie conforme de move_audit._at()."""
    v = None
    for tt, o in serie:
        if tt <= t:
            v = o
        else:
            break
    return v


def prob_home(oh, oa):
    """Normalisation proportionnelle — identique à move_audit.prob_home().
    Volontairement PAS Shin : la population de l'hypothèse est définie par
    cette formule, en changer changerait ce qu'on mesure."""
    if not oh or not oa or oh <= 1 or oa <= 1:
        return None
    ih, ia = 1 / oh, 1 / oa
    return ih / (ih + ia)


def charger():
    """{uid: {book: {'h': [(t, cote)], 'a': [...]}}, '_ct', '_home', '_away'}"""
    games = {}
    try:
        lignes = ov.open_curves(CURVES)
    except FileNotFoundError as e:
        print(f"  ❌ {e}")
        return games
    for ligne in lignes:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            r = json.loads(ligne)
        except ValueError:
            continue
        ct = _dt(r.get('commence_time'))
        if ct is None or not r.get('book'):
            continue
        h = [(t, o) for t, o in
             ((_dt(p[0]), p[1]) for p in (r.get('home_curve') or []))
             if t and o]
        a = [(t, o) for t, o in
             ((_dt(p[0]), p[1]) for p in (r.get('away_curve') or []))
             if t and o]
        if not h or not a:
            continue
        g = games.setdefault(r['uid'], {'_ct': ct, '_home': r.get('home'),
                                        '_away': r.get('away'),
                                        '_tour': r.get('tournament')})
        g[r['book']] = {'h': sorted(h), 'a': sorted(a)}
    return games


def detecter(g, maintenant):
    """(côté, t_det, cote, book, ampleur_pts) ou None.

    Balayage causal : on s'arrête au PREMIER franchissement de THR, quel que
    soit son sens, et le côté est celui du mouvement à cet instant.
    """
    pin = g.get(SHARP)
    if not pin:
        return None
    topen = pin['h'][0][0]
    p_open = prob_home(_at(pin['h'], topen), _at(pin['a'], topen))
    if p_open is None:
        return None
    t_det, steam, p_det = None, None, None
    for t, _ in pin['h']:
        if t > maintenant:
            break                      # on ne lit jamais le futur
        p = prob_home(_at(pin['h'], t), _at(pin['a'], t))
        if p is None:
            continue
        if abs(p - p_open) >= THR:
            t_det, steam, p_det = t, ('h' if p > p_open else 'a'), p
            break
    if t_det is None:
        return None
    lead = (g['_ct'] - t_det).total_seconds() / 60.0
    if lead < MIN_LEAD:
        return None
    # meilleur prix mou sur le côté steamé, AU MOMENT de la détection
    cote, book = None, None
    for b in SOFTS:
        s = g.get(b)
        if not s:
            continue
        pr = _at(s['h'] if steam == 'h' else s['a'], t_det)
        if pr and (cote is None or pr > cote):
            cote, book = pr, b
    if cote is None:
        return None
    return steam, t_det, cote, book, abs(p_det - p_open) * 100, lead


def envoyer(texte):
    """Canal PRIVÉ uniquement. TELEGRAM_PUBLIC_CHAT_ID n'est pas lu ici, et
    ne doit pas l'être : voir l'en-tête du fichier."""
    token = os.environ.get('TELEGRAM_TOKEN')
    chat = os.environ.get('TELEGRAM_CHAT_ID')
    if DRY_RUN or not token or not chat:
        print(f"  [non envoyé] {texte.splitlines()[0]}")
        return False
    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=urllib.parse.urlencode(
                {'chat_id': chat, 'text': texte,
                 'parse_mode': 'HTML',
                 'disable_web_page_preview': 'true'}).encode())
        with urllib.request.urlopen(req, timeout=15) as r:
            # On vérifie la RÉPONSE, pas seulement l'absence d'exception :
            # un journal qui enregistre l'intention plutôt que l'envoi ferait
            # croire à des messages reçus qui ne l'ont pas été.
            return r.status == 200
    except Exception as e:
        print(f"  ⚠️ Telegram : {e}")
        return False


def message(g, steam, cote, book, ampleur, lead):
    joueur = g['_home'] if steam == 'h' else g['_away']
    adv = g['_away'] if steam == 'h' else g['_home']
    hh = int(lead // 60)
    lead_txt = f"{int(lead)} min" if lead < 60 else f"{hh}h{int(lead % 60):02d}"
    return (f"🔭 <b>ZONE 2,50-3,20</b> — observation (cote {cote:.2f})\n"
            f"{g.get('_tour') or '?'} · T-{lead_txt}\n"
            f"<b>{joueur}</b> vs {adv}\n"
            f"📉 mouvement Pinnacle {ampleur:.1f} pts · entrée {book} @ {cote:.2f}\n"
            f"\n"
            f"<i>Zone observée depuis le {OBSERVE_DEPUIS}, NON GELÉE et NON "
            f"VALIDÉE. Historique : +12,7 % puis +15,3 % de ROI sur deux "
            f"moitiés (n=117 et 79), les deux intervalles traversant zéro. "
            f"Zone trouvée en découpant 7 tranches après coup — à traiter "
            f"comme une piste, pas un signal. Ne pas diffuser.</i>")


def deja_vu_h13(uid):
    """h13_signal a-t-il déjà alerté sur ce match ?

    81 % des matchs de cette zone tombent dans la bande 2,00-3,00 de
    l'hypothèse 13. Envoyer un second message ferait doublon quatre fois
    sur cinq. On LOGUE quand même — la mesure doit porter sur toute la
    zone — mais on n'envoie pas.
    """
    try:
        etat = json.load(open('h13_signal_state.json', encoding='utf-8'))
    except (OSError, ValueError):
        return False
    return uid in etat


def main():
    print(f"ZONE 2,50-3,20 (canal privé) — bande {COTE_MIN:.2f}-{COTE_MAX:.2f} · "
          f"THR {THR:.3f} · softs {','.join(SOFTS)}"
          + ("  [DRY RUN]" if DRY_RUN else ""))
    # utcnow() est déprécié depuis 3.12 ; les courbes portent des
    # horodatages naïfs en UTC, on reste naïf des deux côtés.
    maintenant = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
    try:
        etat = json.load(open(ETAT, encoding='utf-8'))
    except (OSError, ValueError):
        etat = {}
    games = charger()
    if not games:
        print("  aucune courbe exploitable.")
        return 0

    n_vus, n_bande, n_envoyes = 0, 0, 0
    for uid, g in games.items():
        if g['_ct'] <= maintenant:
            continue                   # match commencé : hors périmètre
        d = detecter(g, maintenant)
        if not d:
            continue
        n_vus += 1
        steam, t_det, cote, book, ampleur, lead = d
        if not (COTE_MIN <= cote <= COTE_MAX):
            continue
        n_bande += 1
        if uid in etat:
            continue                   # déjà traité par CE script
        doublon = deja_vu_h13(uid)
        ok = False
        if not doublon:
            ok = envoyer(message(g, steam, cote, book, ampleur, lead))
            n_envoyes += 1
        etat[uid] = {'t': maintenant.isoformat(timespec='seconds'),
                     'cote': round(cote, 2), 'book': book, 'envoye': ok,
                     'doublon_h13': doublon}
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'uid': uid, 'detecte_le': t_det.isoformat(timespec='seconds'),
                'signale_le': maintenant.isoformat(timespec='seconds'),
                'joueur': g['_home'] if steam == 'h' else g['_away'],
                'adversaire': g['_away'] if steam == 'h' else g['_home'],
                # `side` ENREGISTRÉ LE 09/09/2026. Sans lui, il fallait le
                # déduire en comparant le nom du joueur au uid — fragile sur
                # les noms composés, les accents et les homonymes. Un journal
                # permanent doit porter ce qu'il sait, pas obliger à le
                # reconstituer.
                'side': 'home' if steam == 'h' else 'away',
                'tournoi': g.get('_tour'), 'cote': round(cote, 2),
                'book': book, 'ampleur_pts': round(ampleur, 2),
                'lead_min': round(lead, 0), 'commence': g['_ct'].isoformat(),
                'envoye': ok, 'doublon_h13': doublon,
                'observe_depuis': OBSERVE_DEPUIS,
            }, ensure_ascii=False) + '\n')

    # Purge des états dont le match est passé : sans elle le fichier gonfle
    # indéfiniment et l'anti-doublon finit par coûter plus cher que le calcul.
    limite = (maintenant - datetime.timedelta(days=3)).isoformat()
    etat = {k: v for k, v in etat.items() if str(v.get('t', '')) >= limite}
    try:
        ov.ecriture_atomique(ETAT, etat, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"  ℹ️ état non écrit : {e}")

    print(f"  {len(games)} matchs · {n_vus} avec mouvement détecté · "
          f"{n_bande} dans la zone · {n_envoyes} envoyé(s) · "
          f"{n_bande - n_envoyes} en doublon avec h13 (logué, non envoyé)")
    # Le VERDICT reste rendu par validation_report.roi_bande_watch() sur
    # moves_detail_hist.csv. Ce journal-ci sert à SUIVRE en direct et à
    # vérifier que la détection temps réel voit bien la même population que
    # la reconstruction batch — pas à juger. Deux juges finissent par
    # diverger.
    return 0


if __name__ == '__main__':
    sys.exit(main())
