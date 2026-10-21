#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
journal_direct.py — ligne de journal COMPLÈTE d'une détection en direct (H13…H18, H14).

DÉCISION DU 16/10/2026 : les verdicts des hypothèses gelées se rendent sur
les ALERTES EN DIRECT. Tout ce qui est connu au moment de la décision est
écrit UNE FOIS, dans h*_signal_log.jsonl, et n'est plus jamais modifié ;
le résultat, la clôture Pinnacle et la CLV sont AJOUTÉS plus tard par
scripts/suivi_direct.py, dans un fichier séparé.

Chaque script h*_signal.py appelle `ligne(...)` puis `ecrire(...)` pour
CHAQUE détection qui satisfait la règle de l'hypothèse — envoyée, doublon
d'une autre alerte, envoi échoué ou non tenté (DRY_RUN / jeton absent) :
aucune détection ne peut disparaître sans ligne de journal.

Champs (schéma 2) :
    uid, hypothese, joueur, adversaire, side, tournoi, circuit,
    detecte_le (franchissement Pinnacle), signale_le (passage du script),
    commence, book, cote (meilleur prix mou à detecte_le),
    cote_signal / book_signal (meilleur prix mou à signale_le),
    pin_open (Pinnacle ouverture, côté joué), pin_decision (Pinnacle à
    detecte_le), pin_signal (Pinnacle à signale_le), mag_cote_pct (raccour-
    cissement Pinnacle ouverture→détection, %), ampleur_pts, lead_min,
    ecart_pct (cote / pin_open − 1), envoye, statut_envoi, doublon,
    doublon_ref (alerte d'origine), regle, regle_hash, gele_le, schema.

Sans dépendance réseau : 0 requête API.
"""
import hashlib
import json
import os

import validation_report as _vr

SCHEMA = 2
SHARP = os.environ.get('SHARP', 'pinnacle')
SOFTS = list(_vr.H14_SOFTS)

# Règle de chaque hypothèse : texte + constantes gelées (source unique :
# validation_report). Le hachage change si une constante change.
REGLES = {
    'H13': (f"{_vr.H13_COTE_MIN:.2f} ≤ cote entrée ≤ {_vr.H13_COTE_MAX:.2f}",
            {'H13_COTE_MIN': _vr.H13_COTE_MIN, 'H13_COTE_MAX': _vr.H13_COTE_MAX,
             'gel': _vr.FREEZE_DATE_ROIBANDE}),
    'H14': (f"mouvement Pinnacle > {_vr.H14_MOVE_MIN_PCT:g} % à la détection · "
            f"{_vr.H14_LEAD_MIN / 60:.0f}–{_vr.H14_LEAD_MAX / 60:.0f} h avant le match",
            {'H14_MOVE_MIN_PCT': _vr.H14_MOVE_MIN_PCT, 'H14_LEAD_MIN': _vr.H14_LEAD_MIN,
             'H14_LEAD_MAX': _vr.H14_LEAD_MAX, 'gel': _vr.FREEZE_DATE_AMPLI}),
    'H15': (f"{_vr.H15_COTE_MIN:.2f} ≤ cote entrée < {_vr.H15_COTE_MAX:.2f}",
            {'H15_COTE_MIN': _vr.H15_COTE_MIN, 'H15_COTE_MAX': _vr.H15_COTE_MAX,
             'gel': _vr.FREEZE_DATE_H15}),
    'H16': (f"Pinnacle ouverture < {_vr.H16_PIN_OPEN_MAX:.2f}",
            {'H16_PIN_OPEN_MAX': _vr.H16_PIN_OPEN_MAX, 'gel': _vr.FREEZE_DATE_H16}),
    'H16B': (f"{_vr.H16B_PIN_OPEN_MIN:.2f} ≤ Pinnacle ouverture < {_vr.H16_PIN_OPEN_MAX:.2f}",
             {'H16B_PIN_OPEN_MIN': _vr.H16B_PIN_OPEN_MIN, 'H16_PIN_OPEN_MAX': _vr.H16_PIN_OPEN_MAX,
              'gel': _vr.FREEZE_DATE_H16B}),
    'H17': (f"{_vr.H17_ECART_MIN:.0f} ≤ écart entrée vs Pinnacle ouverture < {_vr.H17_ECART_MAX:.0f} %",
            {'H17_ECART_MIN': _vr.H17_ECART_MIN, 'H17_ECART_MAX': _vr.H17_ECART_MAX,
             'gel': _vr.FREEZE_DATE_H17}),
    'H18': (f"Pinnacle ouverture < {_vr.H16_PIN_OPEN_MAX:.2f} et écart {_vr.H17_ECART_MIN:.0f}–"
            f"{_vr.H17_ECART_MAX:.0f} %",
            {'H16_PIN_OPEN_MAX': _vr.H16_PIN_OPEN_MAX, 'H17_ECART_MIN': _vr.H17_ECART_MIN,
             'H17_ECART_MAX': _vr.H17_ECART_MAX, 'gel': _vr.FREEZE_DATE_H18}),
}
COMMUN = {'SOFTS': SOFTS, 'SHARP': SHARP, 'THR': float(os.environ.get('THR', '0.02')),
          'MIN_LEAD': float(os.environ.get('MIN_LEAD', '5'))}


def regle_hash(code):
    texte, consts = REGLES[code]
    blob = json.dumps({'code': code, 'regle': texte, 'constantes': consts, 'commun': COMMUN},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()[:12]


def _at(serie, t):
    v = None
    for tt, o in serie or []:
        if tt <= t:
            v = o
        else:
            break
    return v


def circuit(tournoi):
    t = str(tournoi or '').lower()
    if 'challenger' in t:
        return 'Challenger'
    if t.startswith('wta'):
        return 'WTA'
    if t.startswith('atp'):
        return 'ATP'
    if 'itf' in t:
        return 'ITF'
    return 'Autre'


def meilleur_mou(g, steam, t):
    cote, book = None, None
    for b in SOFTS:
        s = g.get(b)
        if not s:
            continue
        pr = _at(s['h'] if steam == 'h' else s['a'], t)
        if pr and (cote is None or pr > cote):
            cote, book = pr, b
    return cote, book


def pinnacle(g, steam, t_det, maintenant):
    """(pin_open, pin_decision, pin_signal, mag_cote_pct) du côté joué."""
    pin = g.get(SHARP)
    if not pin:
        return None, None, None, None
    serie = pin['h'] if steam == 'h' else pin['a']
    topen = pin['h'][0][0]
    po, pd, ps = _at(serie, topen), _at(serie, t_det), _at(serie, maintenant)
    mag = 100.0 * (po - pd) / po if (po and pd) else None
    return po, pd, ps, mag


def statut_envoi(envoye, doublon):
    # Depuis le 21/10/2026, H14 et H15 envoient AUSSI leurs doublons (message
    # marqué « déjà signalé ») : le champ `doublon` garde le canal d'origine,
    # pour que chaque match ne compte qu'une fois dans les études de prix.
    if doublon and envoye:
        return f'envoyé (déjà signalé par {doublon})'
    if doublon:
        return 'doublon'
    if envoye:
        return 'envoyé'
    if os.environ.get('DRY_RUN', '') == '1':
        return 'non tenté (DRY_RUN)'
    if not os.environ.get('TELEGRAM_TOKEN') or not os.environ.get('TELEGRAM_CHAT_ID'):
        return 'non tenté (jeton Telegram absent)'
    return 'échec Telegram'


def doublon_ref(doublon, uid):
    """Alerte d'origine d'un doublon : lue dans l'état du canal qui l'a envoyée."""
    if not doublon:
        return None
    try:
        etat = json.load(open(f'{doublon}_signal_state.json', encoding='utf-8'))
    except (OSError, ValueError):
        return {'canal': doublon}
    e = etat.get(uid) or {}
    return {'canal': doublon, 'signale_le': e.get('t'), 'cote': e.get('cote'), 'book': e.get('book')}


def ligne(code, uid, g, steam, t_det, maintenant, cote, book, ampleur, lead, envoye, doublon=None):
    po, pd, ps, mag = pinnacle(g, steam, t_det, maintenant)
    cs, bs = meilleur_mou(g, steam, maintenant)
    texte, consts = REGLES[code]
    return {
        'uid': uid, 'hypothese': code,
        'joueur': g['_home'] if steam == 'h' else g['_away'],
        'adversaire': g['_away'] if steam == 'h' else g['_home'],
        'side': 'home' if steam == 'h' else 'away',
        'tournoi': g.get('_tour'), 'circuit': circuit(g.get('_tour')),
        'detecte_le': t_det.isoformat(timespec='seconds'),
        'signale_le': maintenant.isoformat(timespec='seconds'),
        'commence': g['_ct'].isoformat(),
        'book': book, 'cote': round(cote, 3),
        'cote_signal': round(cs, 3) if cs else None, 'book_signal': bs,
        'pin_open': round(po, 3) if po else None,
        'pin_decision': round(pd, 3) if pd else None,
        'pin_signal': round(ps, 3) if ps else None,
        'mag_cote_pct': round(mag, 2) if mag is not None else None,
        'ampleur_pts': round(ampleur, 2), 'lead_min': round(lead, 0),
        'ecart_pct': round(100.0 * (cote / po - 1.0), 2) if po else None,
        'envoye': bool(envoye), 'statut_envoi': statut_envoi(envoye, doublon),
        'doublon': doublon or '', 'doublon_ref': doublon_ref(doublon, uid),
        'regle': texte, 'regle_hash': regle_hash(code), 'gele_le': consts['gel'],
        'schema': SCHEMA,
    }


def ecrire(chemin, rec):
    with open(chemin, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def purger(etat, maintenant, jours=2):
    """Garde l'anti-doublon jusqu'au DÉBUT du match (+ marge), pas 3 jours après le signal.

    L'ancienne purge sur `t` (heure du signal) pouvait oublier un match
    détecté plus de 3 jours avant son début et le journaliser deux fois.
    """
    import datetime
    limite = (maintenant - datetime.timedelta(days=jours)).isoformat()
    return {k: v for k, v in etat.items()
            if str(v.get('commence') or v.get('t', '')) >= limite}


def deja_txt(doublon, uid):
    """Ligne « déjà signalé » d'un message envoyé malgré un doublon (H14, H15)."""
    if not doublon:
        return ''
    r = doublon_ref(doublon, uid) or {}
    prix = f" ({r['book']} @ {r['cote']:.2f})" if r.get('book') and r.get('cote') else ''
    return f"🔁 Match déjà signalé par {doublon.upper()}{prix}."


def suivi_txt(code, cible):
    """Bloc « Suivi en direct » commun à tous les messages : paris dénoués, gains, ROI, CLV."""
    s = suivi(code)
    if s is None:
        return []
    if not s.get('n'):
        return [f"\n📊 <b>Suivi en direct</b> : aucun pari dénoué pour l'instant "
                f"({s.get('n_detectees') or 0} détection(s))."]
    L = [f"\n📊 <b>Suivi en direct</b> : {s['n']}/{cible} paris dénoués ({100 * s['n'] / cible:.0f} %)",
         f"gains {s['k']}/{s['n']} = {s['taux']:.1f} % (seuil {s['p0']:.1f} %) · écart {s['taux'] - s['p0']:+.1f} pts",
         f"ROI {s['roi']:+.1f} % · P&L {s['pnl']:+.1f} u"
         + (f" · CLV Pinnacle {s['clv']:+.1f} %" if s.get('clv') is not None else '')]
    return L


def suivi(code, chemin='verdicts_direct.json'):
    """Bilan EN DIRECT (verdicts_direct.json) pour la ligne « Suivi » des messages.

    Même forme que l'ancien _suivi() lu sur la reconstruction :
    {'n', 'k', 'taux', 'p0', 'roi', 'pnl', 'cible', 'n_detectees'}.
    """
    try:
        doc = json.load(open(chemin, encoding='utf-8'))
    except (OSError, ValueError):
        return None
    h = next((x for x in doc.get('hypotheses', []) if x.get('code') == code), None)
    if not h:
        return None
    o = h.get('out_of_sample') or {}
    if not o.get('n'):
        return {'n': 0, 'n_detectees': o.get('n_detectees', 0)}
    return {'n': o['n'], 'k': o['gains'], 'taux': o['taux'], 'p0': o['seuil'],
            'roi': o['roi'], 'pnl': o['pnl'], 'cible': h.get('cible'),
            'n_detectees': o.get('n_detectees'), 'clv': o.get('clv_pin_moyen')}
