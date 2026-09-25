#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
h16_signal.py — 16e hypothèse gelée : le côté steamé partait favori net.

    Parier le côté steamé au book d'entrée quand le prix PINNACLE À
    L'OUVERTURE de ce côté est inférieur à 1,80.

Gelée le 25/09/2026. Envoi sur le canal PRIVÉ uniquement.

──────────────────────────────────────────────────────────────────────────
LE FILTRE PORTE SUR pin_open, PAS SUR LA COTE D'ENTRÉE

C'est le point à ne pas confondre. Le même seuil appliqué à la cote
d'entrée donne n=608 et p=0,0933 — soit rien. Appliqué au prix Pinnacle
d'ouverture, il donne n=580 et p=0,0246.

Les deux sont causaux (connus au moment de l'alerte), mais ils ne
sélectionnent pas les mêmes matchs : pin_open décrit ce que le marché
sharp pensait AVANT le mouvement, la cote d'entrée ce qu'un book mou
propose APRÈS.

──────────────────────────────────────────────────────────────────────────
CE QUI L'A FAIT RETENIR

Référence in-sample : n=580 · 429 gains = 74,0 % contre 70,2 % de seuil
· écart +3,8 · ROI +5,5 % · P&L +31,8 u.

    IC95 du taux   [70,2 ; 77,4]   exclut le seuil
    IC95 du ROI    [+0,2 ; +10,8]  exclut zéro
    binomial exact p = 0,0246
    placebo 500 tirages : plage [-4,31 ; +4,64], observé +5,48 %

RÉPLICATION à effectifs rigoureusement égaux :
    1re moitié  écart +3,0  ROI +4,3 %  (n=290)
    2e  moitié  écart +4,6  ROI +6,6 %  (n=290)

POURQUOI 1,80 ET PAS 1,65. Le balayage donne 1,65 comme meilleur seuil
(écart +4,6, p=0,0149) — c'est exactement pour cela qu'il est écarté :
c'est le maximum d'un balayage. 1,80 est le seuil de départ, choisi avant
tout découpage, avec le plus gros volume.

Point rassurant : l'effet ne dépend pas du seuil, il reste entre +2,8 et
+4,6 sur toute la plage 1,60-1,80.

RÉSERVES. L'effet est modeste et l'IC du ROI frôle zéro (+0,2 %). Les 25
meilleurs paris font 63 % du P&L : à cote médiane 1,44, un gain rapporte
0,44 u et une perte coûte 1,00.

──────────────────────────────────────────────────────────────────────────
DOUBLONS

H16 est DISJOINTE de H15 (recouvrement 0/580 : H15 porte sur les cotes
d'entrée 2,40-3,10, H16 sur des favoris à cote médiane 1,44). Elle
recoupe en revanche H13 et H14 sur certains matchs. Le journal enregistre
TOUT — la mesure doit être complète — mais le message n'est envoyé que si
aucun autre signal n'a déjà couvert le match.

Env : CURVES, SHARP, THR, MIN_LEAD, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID,
      DRY_RUN=1. Le SEUIL n'est pas paramétrable : il vient de
      validation_report, source unique.
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
PIN_OPEN_MAX = _vr.H16_PIN_OPEN_MAX
DRY_RUN = os.environ.get('DRY_RUN', '') == '1'

ETAT = 'h16_signal_state.json'      # anti-doublon, un signal par match
LOG = 'h16_signal_log.jsonl'        # journal PERMANENT, append-only
FREEZE = _vr.FREEZE_DATE_H16


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
        if po >= PIN_OPEN_MAX:
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
    L = [f"🧪 <b>H16 — favori net</b> (Pinnacle ouv. {pin_open:.2f} · "
         f"entrée {cote:.2f})",
         f"{g.get('_tour') or '?'} · T-{lead_txt}",
         f"<b>{joueur}</b> vs {adv}",
         f"📉 mouvement Pinnacle {ampleur:.1f} pts · entrée {book} @ {cote:.2f}"]
    s = _suivi()
    if s and s.get('n'):
        L.append(f"\n📊 <b>Suivi</b> : {s['n']}/600 paris dénoués "
                 f"({100 * s['n'] / 600:.0f} %)")
        L.append(f"gains {s['k']}/{s['n']} = {s['taux']:.1f} % "
                 f"(seuil {s['p0']:.1f} %) · écart {s['taux'] - s['p0']:+.1f} pts")
        L.append(f"ROI {s['roi']:+.1f} % · P&L {s['pnl']:+.1f} u")
    elif s is not None:
        L.append("\n📊 <b>Suivi</b> : aucun pari dénoué depuis le gel.")
    L.append(f"\n<i>Hypothèse gelée le {FREEZE}, NON VALIDÉE. Référence "
             f"in-sample : 429/580 = 74,0 % contre 70,2 % de seuil, "
             f"ROI +5,5 %. Filtre sur le prix PINNACLE d'ouverture, pas sur "
             f"la cote d'entrée — le même seuil sur la cote d'entrée donne "
             f"p=0,09, soit rien. Effet modeste (+3,8 pts) et concentré : "
             f"les 25 meilleurs paris font 63 % du P&L. Verdict vers n=600. "
             f"Ne pas diffuser.</i>")
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
    print(f"H16 SIGNAL (canal privé) — pin_open < {PIN_OPEN_MAX:.2f} · "
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
        if pin_open >= PIN_OPEN_MAX:
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
