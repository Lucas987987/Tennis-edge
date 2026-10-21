#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h14_signal.py — 14e hypothèse gelée : amplitude + timing, CANAL EN DIRECT (créé le 16/10/2026).

    « Parier le côté steamé au book d'entrée, mouvement Pinnacle > 5 %
      MESURÉ À LA DÉTECTION, détection entre 8 h et 24 h avant le coup
      d'envoi, SANS filtre de cote. »  — gelée le 2026-10-02 (FREEZE_DATE_AMPLI)

Jusqu'au 16/10/2026, H14 n'avait AUCUN canal : elle n'était suivie que sur la
reconstruction (moves_detail_hist.csv). Depuis la décision du 16/10 (verdicts
rendus sur les alertes en direct), son ÉCHANTILLON EN DIRECT COMMENCE AU
DÉPLOIEMENT DE CE SCRIPT : aucune détection antérieure n'existe ni ne sera
reconstituée. La date de gel ne change pas.

Règle : constantes de validation_report (H14_MOVE_MIN_PCT, H14_LEAD_MIN/MAX,
H14_SOFTS), même détecteur causal que H13…H18 (premier franchissement de THR
sur Pinnacle, côté du mouvement à cet instant). L'ampleur est celle de
move_audit.py : (cote Pinnacle à l'ouverture − cote à la détection) / ouverture.

Canal PRIVÉ uniquement. H14 recoupe toutes les autres hypothèses : si une
autre alerte a déjà couvert le match, la détection est JOURNALISÉE (elle
compte pour H14) mais pas renvoyée (doublon).

Env : CURVES, SHARP, THR, MIN_LEAD, TELEGRAM_*, DRY_RUN=1.
"""
import os
import sys
import json
import datetime
import urllib.request
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import journal_direct              # noqa: E402 — journal complet (schéma 2)
import meilleurs_prix               # noqa: E402 — 3 meilleurs prix (affichage)
import lien_joueur                   # noqa: E402 — liens vers les fiches
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
MOVE_MIN = _vr.H14_MOVE_MIN_PCT
LEAD_MIN_H14 = _vr.H14_LEAD_MIN
LEAD_MAX_H14 = _vr.H14_LEAD_MAX
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'

ETAT = 'h14_signal_state.json'      # anti-doublon, un signal par match
LOG = 'h14_signal_log.jsonl'        # journal PERMANENT, append-only
FREEZE = _vr.FREEZE_DATE_AMPLI


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
    # PRIX PINNACLE À L'OUVERTURE du côté steamé — c'est LE filtre de H16.
    # Pris à `topen`, l'instant du premier point Pinnacle : c'est ce que le
    # marché sharp pensait AVANT tout mouvement, et c'est connu bien avant
    # la détection. Rien de rétrospectif ici.
    pin_open = _at(pin['h'] if steam == 'h' else pin['a'], topen)
    if not pin_open:
        return None
    return (steam, t_det, cote, book, abs(p_det - p_open) * 100, lead,
            pin_open)


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


def message(g, steam, cote, book, ampleur, lead, mag, deja=''):
    joueur = g['_home'] if steam == 'h' else g['_away']
    adv = g['_away'] if steam == 'h' else g['_home']
    hh = int(lead // 60)
    lead_txt = f"{int(lead)} min" if lead < 60 else f"{hh}h{int(lead % 60):02d}"
    L = [f"🧪 <b>H14 — amplitude + timing</b>",
         f"Pinnacle raccourcie de {mag:.1f} % · T-{lead_txt}",
         f"{g.get('_tour') or '?'}",
         f"{lien_joueur.duo_html(joueur, adv)}",
         f"📉 mouvement Pinnacle {ampleur:.1f} pts · entrée {book} @ {cote:.2f}"]
    prix = meilleurs_prix.ligne(g, steam)  # 3 meilleurs prix frais (affichage seul)
    if prix:
        L.append(prix)
    if deja:
        L.append(deja)
    L += journal_direct.suivi_txt('H14', 166)  # bilan EN DIRECT (verdicts_direct.json)
    L.append(f"\n<i>Hypothèse gelée le {FREEZE}, NON VALIDÉE. Échantillon EN "
             f"DIRECT commencé au déploiement du canal (16/10/2026). Référence "
             f"in-sample (reconstruction, avant regel) : 146/275 = 53,1 % · "
             f"p0 46,0 %. Ne pas diffuser.</i>")
    return '\n'.join(L)


def _deja_signale(uid):
    """Un autre canal a-t-il déjà ENVOYÉ ce match ? (H14 recoupe tout.)"""
    for cle in ('h13', 'zone', 'h15', 'h16', 'h17', 'h18', 'h16b'):
        try:
            etat = json.load(open(f'{cle}_signal_state.json', encoding='utf-8'))
        except (OSError, ValueError):
            continue
        e = etat.get(uid)
        if e and (e.get('envoye') or cle == 'zone'):
            return cle
    return None


def main():
    print(f"H14 SIGNAL (canal privé) — mouvement > {MOVE_MIN:g} % · "
          f"{LEAD_MIN_H14 / 60:.0f}-{LEAD_MAX_H14 / 60:.0f} h · "
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
        steam, t_det, cote, book, ampleur, lead, pin_open = d
        _po, _pd, _ps, mag = journal_direct.pinnacle(g, steam, t_det, maintenant)
        if mag is None or not mag > MOVE_MIN:
            continue
        if not (LEAD_MIN_H14 <= lead <= LEAD_MAX_H14):
            continue
        n_bande += 1
        if uid in etat:
            continue                   # déjà traité par CE script
        doublon = _deja_signale(uid)
        # Depuis le 21/10/2026 : envoyé MÊME en doublon (demande de Lucas), avec
        # la mention « déjà signalé ». La règle et la mesure ne changent pas.
        ok = envoyer(message(g, steam, cote, book, ampleur, lead, mag, deja=journal_direct.deja_txt(doublon, uid)))
        n_envoyes += 1
        # Journal COMPLET (schéma 2, scripts/journal_direct.py) : TOUTE
        # détection dans la règle est écrite — envoyée, doublon, échec ou
        # non tentée. Champs de décision écrits une fois, jamais modifiés.
        rec = journal_direct.ligne('H14', uid, g, steam, t_det, maintenant,
                                   cote, book, ampleur, lead, ok, doublon)
        etat[uid] = {'t': maintenant.isoformat(timespec='seconds'),
                     'commence': g['_ct'].isoformat(),
                     'cote': round(cote, 2), 'pin_open': rec['pin_open'],
                     'book': book, 'envoye': ok, 'doublon': doublon or ''}
        journal_direct.ecrire(LOG, rec)

    # Purge des états dont le match est passé : sans elle le fichier gonfle
    # indéfiniment et l'anti-doublon finit par coûter plus cher que le calcul.
    etat = journal_direct.purger(etat, maintenant)
    try:
        ov.ecriture_atomique(ETAT, etat, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"  ℹ️ état non écrit : {e}")

    print(f"  {len(games)} matchs · {n_vus} avec mouvement détecté · "
          f"{n_bande} dans la bande · {n_envoyes} signal(aux) envoyé(s)")
    # DEPUIS LE 16/10/2026 le verdict se rend sur CE journal (suivi_direct.py
    # -> verdicts_direct.json) ; la reconstruction n'est plus qu'un contrôle.
    return 0


if __name__ == '__main__':
    sys.exit(main())
