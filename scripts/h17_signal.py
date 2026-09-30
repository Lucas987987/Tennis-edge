#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h17_signal.py — 17e hypothèse gelée : écart d'entrée de 0 à 3 %.

    Parier le côté steamé au book d'entrée quand son prix dépasse de 0 à
    3 % le prix PINNACLE À L'OUVERTURE du même côté.

Gelée le 25/09/2026. Envoi sur le canal PRIVÉ uniquement.

──────────────────────────────────────────────────────────────────────────
L'ÉCART EST CAUSAL — ET C'EST TOUT L'ENJEU

    écart = 100 × (prix d'entrée / prix Pinnacle à l'OUVERTURE − 1)

Les deux termes sont connus au moment du pari. NE PAS CONFONDRE avec
`clv_vs_pin_pct` de moves_detail_hist, qui utilise pin_CLOSE et n'existe
qu'après le coup d'envoi : découper le portefeuille avec cette
colonne-là, c'est du look-ahead — le même piège que `mag_cote_pct` avant
sa correction du 06/09.

──────────────────────────────────────────────────────────────────────────
POURQUOI CETTE VARIABLE

L'écart à l'entrée est, de loin, le meilleur prédicteur du CLV mesuré sur
ces données :

    corrélation(écart ; CLV vs clôture Pinnacle) = +0,5866
    IC95 [+0,5529 ; +0,6184]   n=1543

À comparer aux 0,06 à 0,24 de tout le reste. Le gradient est monotone :
0,90 % de CLV médian sous 0 d'écart, 4,30 % entre 0 et 3, jusqu'à 28,90 %
au-delà de 10 — avec 97,6 % de CLV positif dans cette dernière tranche.

C'est mécanique : un prix très au-dessus du marché sharp a peu de chances
d'être rattrapé. LE CLV EST PRÉVISIBLE.

MAIS LE ROI NE SUIT PAS LE GRADIENT : -2,4 % / +3,3 % / +12,4 % / +4,3 %
/ -19,5 % / +74,6 %. Aucune monotonie. C'est la dissociation CLV/ROI,
déjà démontrée par la tranche de cote > 6,00 (+23 % de CLV, -34 % de ROI).

POURQUOI 0-3 % ET PAS > 10 %. La tranche > 10 % affiche +74,6 % de ROI et
p=0,0222, avec une réplication apparente (+93,0 % puis +56,2 %). Mais sur
42 paris, soit 21 par moitié : à ce volume, +93 % veut dire « deux ou
trois gros outsiders sont passés ».

0-3 % est retenue pour sa RÉPLICATION : +10,6 % puis +14,1 %, soit 3,5
points d'écart — la meilleure du dispositif, devant H15 et H16.

RÉSERVE. p = 0,0439 sur six tranches testées ; après Bonferroni, 0,26.
C'est la réplication qui justifie ce gel, pas la significativité.

──────────────────────────────────────────────────────────────────────────
Env : CURVES, SHARP, THR, MIN_LEAD, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
      DRY_RUN=1. Les BORNES viennent de validation_report, source unique.
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
ECART_MIN = _vr.H17_ECART_MIN
ECART_MAX = _vr.H17_ECART_MAX
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'

ETAT = 'h17_signal_state.json'      # anti-doublon, un signal par match
LOG = 'h17_signal_log.jsonl'        # journal PERMANENT, append-only
FREEZE = _vr.FREEZE_DATE_H17


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


def _suivi():
    """Bilan out-of-sample courant, recalculé à chaque alerte.

    C'est le SUIVI INTÉGRÉ : chaque message porte l'état d'avancement de
    l'hypothèse qu'il alimente. Sans ça, il faut attendre le récapitulatif
    quotidien pour savoir où on en est — et on finit par juger une
    hypothèse sur l'impression laissée par les derniers messages.
    """
    try:
        import csv as _csv
        lignes = list(_csv.DictReader(open('moves_detail_hist.csv',
                                           encoding='utf-8')))
    except OSError:
        return None
    k = n = 0
    somme = 0.0
    inv = 0.0
    for r in lignes:
        try:
            cote = float(r['entry'])
            po = float(r['pin_open'])
        except (TypeError, ValueError, KeyError):
            continue
        if not po:
            continue
        if not (ECART_MIN <= 100.0 * (cote / po - 1.0) < ECART_MAX):
            continue
        if str(r.get('date') or '')[:10] < FREEZE:
            continue
        gagne = r.get('steame_gagne')
        if gagne not in ('oui', 'non'):
            continue
        try:
            pnl = float(r['pnl'])
        except (TypeError, ValueError, KeyError):
            pnl = (cote - 1.0) if gagne == 'oui' else -1.0
        n += 1
        k += 1 if gagne == 'oui' else 0
        somme += pnl
        inv += 1.0 / cote
    if not n:
        return {'n': 0}
    return {'n': n, 'k': k, 'taux': 100.0 * k / n, 'p0': 100.0 * inv / n,
            'roi': 100.0 * somme / n, 'pnl': somme}


def message(g, steam, cote, book, ampleur, lead, pin_open):
    joueur = g['_home'] if steam == 'h' else g['_away']
    adv = g['_away'] if steam == 'h' else g['_home']
    hh = int(lead // 60)
    lead_txt = f"{int(lead)} min" if lead < 60 else f"{hh}h{int(lead % 60):02d}"
    ecart = 100.0 * (cote / pin_open - 1.0) if pin_open else 0.0
    L = [f"🧪 <b>H17 — écart d'entrée {ecart:+.1f} %</b> "
         f"(Pinnacle ouv. {pin_open:.2f} → entrée {cote:.2f})",
         f"{g.get('_tour') or '?'} · T-{lead_txt}",
         f"<b>{joueur}</b> vs {adv}",
         f"📉 mouvement Pinnacle {ampleur:.1f} pts · entrée {book} @ {cote:.2f}"]
    s = _suivi()
    if s and s.get('n'):
        L.append(f"\n📊 <b>Suivi</b> : {s['n']}/350 paris dénoués "
                 f"({100 * s['n'] / 350:.0f} %)")
        L.append(f"gains {s['k']}/{s['n']} = {s['taux']:.1f} % "
                 f"(seuil {s['p0']:.1f} %) · écart {s['taux'] - s['p0']:+.1f} pts")
        L.append(f"ROI {s['roi']:+.1f} % · P&L {s['pnl']:+.1f} u")
    elif s is not None:
        L.append("\n📊 <b>Suivi</b> : aucun pari dénoué depuis le gel.")
    L.append(f"\n<i>Hypothèse gelée le {FREEZE}, NON VALIDÉE. Référence "
             f"in-sample : 152/255 = 59,6 % contre 54,1 % de seuil, "
             f"ROI +12,4 %. L'écart est CAUSAL (prix d'entrée vs Pinnacle "
             f"à l'ouverture) — il prédit très bien le CLV (r=+0,59) mais "
             f"PAS le ROI. Retenue pour sa réplication (+10,6 % puis "
             f"+14,1 %), pas pour son p (0,044 brut, 0,26 après "
             f"correction). Verdict vers n=350. Ne pas diffuser.</i>")
    return '\n'.join(L)


def _deja_signale(uid):
    """Un autre signal a-t-il déjà couvert ce match ?

    La bande 2,40-3,10 recoupe H13 (2,00-3,00) et la zone 2,50-3,20.
    On LOGUE tout — la mesure doit porter sur toute la bande — mais on
    n'envoie pas trois messages pour le même match.
    """
    for fichier, cle in (('h13_signal_state.json', 'h13'),
                         ('zone_signal_state.json', 'zone')):
        try:
            etat = json.load(open(fichier, encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if uid in etat:
            return cle
    return None


def main():
    print(f"H17 SIGNAL (canal privé) — écart {ECART_MIN:.0f}-{ECART_MAX:.0f} % · "
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
        ecart = 100.0 * (cote / pin_open - 1.0) if pin_open else -99.0
        if not (ECART_MIN <= ecart < ECART_MAX):
            continue
        n_bande += 1
        if uid in etat:
            continue                   # déjà traité par CE script
        doublon = _deja_signale(uid)
        ok = False
        if not doublon:
            ok = envoyer(message(g, steam, cote, book, ampleur, lead, pin_open))
            n_envoyes += 1
        etat[uid] = {'t': maintenant.isoformat(timespec='seconds'),
                     'cote': round(cote, 2), 'pin_open': round(pin_open, 3),
                'book': book, 'envoye': ok,
                     'doublon': doublon or ''}
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
                'envoye': ok, 'doublon': doublon or '',
                'gele_le': FREEZE,
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
