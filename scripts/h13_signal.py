#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h13_signal.py — détecteur TEMPS RÉEL de l'hypothèse gelée n°13, canal PRIVÉ.

    « Parier le côté steamé au book d'entrée, cote entre 2,00 et 3,00,
      SANS aucun autre filtre. »  — gelée le 2026-09-06

CE SCRIPT NE PUBLIE QUE SUR LE CANAL PRIVÉ (TELEGRAM_CHAT_ID). Jamais sur
TELEGRAM_PUBLIC_CHAT_ID.

──────────────────────────────────────────────────────────────────────────
POURQUOI PRIVÉ, ET POURQUOI CE N'EST PAS UNE PRÉCAUTION DE FORME

1. L'hypothèse N'EST PAS VALIDÉE. ROI +13,7 % sur 316 paris, IC95
   [+0,3 ; +27,0] : la borne basse frôle zéro. Il faut ~300 paris
   out-of-sample, soit environ 3 mois, pour trancher. Publier maintenant
   reviendrait à promettre un résultat qui a une chance réelle de ne pas
   exister.

2. CE N'EST PAS LE MÊME FLUX QUE LE CANAL. Recouvrement mesuré : sur 359
   matchs de la bande et 126 matchs alertés sur le canal, 16 en commun.
   Soit 4 % des paris de l'hypothèse déjà publiés, et 13 % du canal dans la
   bande. Ce serait un SECOND flux (118 paris/mois contre 164 alertes), pas
   une amélioration du premier.

3. LE CANAL PUBLIC N'EST PAS UN SERVICE DE PRONOSTICS. Il publie une
   observation de marché et dit « ceci n'est pas un signal d'entrée » (voir
   CANAL.md). Un flux de paris avec cote et sélection est autre chose, et
   les abonnés actuels n'ont pas souscrit à ça.

Dans trois mois, avec un verdict et un track record, la question de publier
se posera sur des bases solides. Pas avant.

──────────────────────────────────────────────────────────────────────────
DÉTECTION — STRICTEMENT LA MÊME QUE move_audit.py CORRIGÉ

C'est le point critique de ce script : il doit détecter EXACTEMENT ce que
move_audit.py enregistre dans moves_detail_hist.csv, sinon vous suivriez en
direct une population et valideriez l'autre.

  - probabilité : prob_home(oh, oa) = (1/oh) / (1/oh + 1/oa), la même
    normalisation proportionnelle que move_audit — PAS Shin. Shin donnerait
    une autre population.
  - détection : premier instant où |p(t) - p_open| >= THR, et le côté est
    celui du mouvement OBSERVÉ À CET INSTANT (correctif du look-ahead du
    06/09 : l'ancien code choisissait le côté avec la clôture).
  - entrée : meilleur prix parmi SOFTS sur le côté steamé, AU MOMENT de la
    détection.
  - bande : 2,00 <= entrée <= 3,00.

Toute divergence avec move_audit.py invaliderait la comparaison. Si vous
modifiez l'un, modifiez l'autre.

──────────────────────────────────────────────────────────────────────────
Env : CURVES (déf. book_curves_live.jsonl), SHARP, SOFTS, THR, MIN_LEAD,
      TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, DRY_RUN=1.
      La BANDE n'est PAS paramétrable : elle vient de validation_report.
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
SOFTS = [b.strip() for b in os.environ.get(
    'SOFTS', 'unibet,bwin,betsson').split(',') if b.strip()]
THR = float(os.environ.get('THR', '0.02'))
MIN_LEAD = float(os.environ.get('MIN_LEAD', '5'))
# BANDE : importée de validation_report, JAMAIS redéfinie ici.
# La version précédente la lisait dans l'environnement, ce qui permettait à
# un COTE_MAX=3.5 posé "pour voir" de faire diverger silencieusement ce
# canal de ce que roi_bande_watch() valide. Une seule source de vérité.
import validation_report as _vr      # noqa: E402
COTE_MIN = _vr.H13_COTE_MIN
COTE_MAX = _vr.H13_COTE_MAX
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'

ETAT = 'h13_signal_state.json'      # anti-doublon, un signal par match
LOG = 'h13_signal_log.jsonl'        # journal PERMANENT, append-only
FREEZE = _vr.FREEZE_DATE_ROIBANDE


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
    return (f"🧪 <b>H13 — signal privé</b> (cote {cote:.2f})\n"
            f"{g.get('_tour') or '?'} · T-{lead_txt}\n"
            f"<b>{joueur}</b> vs {adv}\n"
            f"📉 mouvement Pinnacle {ampleur:.1f} pts · entrée {book} @ {cote:.2f}\n"
            f"\n"
            f"<i>Hypothèse gelée le {FREEZE}, NON VALIDÉE. ROI in-sample "
            f"+13,7 % sur 316 paris, IC95 [+0,3 ; +27,0] — la borne basse "
            f"frôle zéro. Verdict attendu vers décembre 2026. "
            f"Ne pas diffuser.</i>")


def main():
    print(f"H13 SIGNAL (canal privé) — bande {COTE_MIN:.2f}-{COTE_MAX:.2f} · "
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
            continue                   # déjà signalé
        ok = envoyer(message(g, steam, cote, book, ampleur, lead))
        n_envoyes += 1
        etat[uid] = {'t': maintenant.isoformat(timespec='seconds'),
                     'cote': round(cote, 2), 'book': book, 'envoye': ok}
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps({
                'uid': uid, 'detecte_le': t_det.isoformat(timespec='seconds'),
                'signale_le': maintenant.isoformat(timespec='seconds'),
                'joueur': g['_home'] if steam == 'h' else g['_away'],
                'adversaire': g['_away'] if steam == 'h' else g['_home'],
                'tournoi': g.get('_tour'), 'cote': round(cote, 2),
                'book': book, 'ampleur_pts': round(ampleur, 2),
                'lead_min': round(lead, 0), 'commence': g['_ct'].isoformat(),
                'envoye': ok, 'gele_le': FREEZE,
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
          f"{n_bande} dans la bande · {n_envoyes} signal(aux) envoyé(s)")
    # Le VERDICT reste rendu par validation_report.roi_bande_watch() sur
    # moves_detail_hist.csv. Ce journal-ci sert à SUIVRE en direct et à
    # vérifier que la détection temps réel voit bien la même population que
    # la reconstruction batch — pas à juger. Deux juges finissent par
    # diverger.
    return 0


if __name__ == '__main__':
    sys.exit(main())
