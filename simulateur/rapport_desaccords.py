#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rapport_desaccords.py — OÙ l'algo et le marché ne sont pas d'accord, et QUI avait raison (28/10/2026).
INTERNE : Telegram privé + coffre R2 ; jamais dans le dépôt public, jamais une entrée du modèle.

Le marché sert de LOUPE, pas de cible : on liste les matchs où l'algo s'écarte d'au moins 8 points de la clôture
Pinnacle (sans marge), on regarde le résultat, et on cherche CE QUI distingue les cas où le marché avait raison. Une
piste ne devient un facteur (sans cote, jugé sur les résultats) qu'après plusieurs semaines et 30 matchs au moins.

Situations testées, pour le joueur que l'algo SURESTIME (plus haut que le marché) et celui qu'il SOUS-ESTIME,
calculées avec les seuls matchs joués AVANT (archive Sackmann + feuilles TennisApi) :
  en_progression  : Elo +80 ou plus sur 180 jours        en_baisse : Elo −80 ou moins sur 180 jours
  retour_absence  : aucun match dans les 45 jours avant  enchaine  : 4 matchs ou plus dans les 10 jours avant
  peu_documente   : moins de 20 matchs sur 2 ans
Et par match : circuit, « l'algo donne favori l'outsider du marché ».
Deux échantillons jamais mélangés : EN DIRECT (dernier pronostic affiché avant le match, depuis le 21/10/2026) et
REJOUÉ (pronostics hors échantillon). Mesure : log loss de l'algo et du marché sur les mêmes matchs, et taux de
victoire du joueur surestimé contre ce que disaient l'algo et le marché.

Usage : python simulateur/rapport_desaccords.py <archive Sackmann> [racine] [--telegram]
Sortie : simulateur/rapport_desaccords.json (coffre privé, ignoré par git).
"""
import bisect
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
SEUIL = 0.08
N_MIN = 30
PROGRESSION_ELO, PROGRESSION_J = 80.0, 180
ABSENCE_J, ENCHAINE_J, ENCHAINE_N = 45, 10, 4
DOC_J, DOC_N = 730, 20
SORTIE = os.path.join('simulateur', 'rapport_desaccords.json')
SITUATIONS = ('en_progression', 'en_baisse', 'retour_absence', 'enchaine', 'peu_documente')
LIB = {'en_progression': 'en progression (Elo +80 sur 6 mois)', 'en_baisse': 'en baisse (Elo −80 sur 6 mois)',
       'retour_absence': 'de retour après 45 j sans match', 'enchaine': 'qui enchaîne (4+ matchs en 10 j)',
       'peu_documente': 'peu documenté (< 20 matchs sur 2 ans)'}


class Historique:
    """Dates de match et Elo de chaque joueur, interrogeables à une date (strictement avant)."""

    def __init__(self, matchs):
        import elo as E
        self.E = E
        elo = E.Elo()
        self.dates = collections.defaultdict(list)
        self.notes = collections.defaultdict(list)          # (date, note générale après le match)
        for m in sorted(matchs, key=lambda m: (m['date'], m.get('tour', 0), m.get('num', 0))):
            g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
            if not g or not p or g == p:
                continue
            if m.get('circuit') in ('CH', 'ITF'):
                elo.presenter(g, 1200.0)
                elo.presenter(p, 1200.0)
            elo.maj(g, p, m.get('surface'), m.get('niveau') == 'G', None)
            for j in (g, p):
                self.dates[j].append(m['date'])
                self.notes[j].append((m['date'], elo.note(j)))

    def situations(self, nom, jour):
        j = self.E.cle(nom)
        D = self.dates.get(j) or []
        k = bisect.bisect_left(D, jour)                      # matchs strictement avant le jour
        avant = D[:k]
        out = set()
        if not avant or (jour - avant[-1]).days > ABSENCE_J:
            out.add('retour_absence')
        if sum(1 for d in avant if (jour - d).days <= ENCHAINE_J) >= ENCHAINE_N:
            out.add('enchaine')
        if sum(1 for d in avant if (jour - d).days <= DOC_J) < DOC_N:
            out.add('peu_documente')
        N = self.notes.get(j) or []
        if k:
            maintenant = N[k - 1][1]
            i = bisect.bisect_left(D, jour - dt.timedelta(days=PROGRESSION_J))
            if i < k:
                ancienne = N[i - 1][1] if i else N[0][1]
                if maintenant - ancienne >= PROGRESSION_ELO:
                    out.add('en_progression')
                elif maintenant - ancienne <= -PROGRESSION_ELO:
                    out.add('en_baisse')
        return out


def _ll(p, ok):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -math.log(p if ok else 1 - p)


def desaccords(L, C, noms, H, cote):
    """L : [(uid, circuit, p_home, gagnant)] ; C : clôtures ; noms : {uid: (home, away)} ; H : Historique."""
    out = []
    for uid, circuit, p, g in L:
        c = cote(C, uid, None)
        if not c or uid not in noms:
            continue
        qh, qa = 1 / c[0], 1 / c[1]
        pm = qh / (qh + qa)
        if abs(p - pm) < SEUIL:
            continue
        sur_home = p > pm                                     # le joueur que l'algo surestime
        home, away = noms[uid]
        jour = dt.date.fromisoformat(uid[:10])
        sh, sa = H.situations(home, jour), H.situations(away, jour)
        out.append({'uid': uid, 'circuit': circuit,
                    'p_algo': p if sur_home else 1 - p, 'p_marche': pm if sur_home else 1 - pm,
                    'gagne': (g == 'home') == sur_home,
                    'surestime': sorted(sh if sur_home else sa), 'sous_estime': sorted(sa if sur_home else sh),
                    'contre_favori_marche': (p >= 0.5) != (pm >= 0.5)})
    return out


def bilan(X):
    n = len(X)
    if not n:
        return {'n': 0}
    return {'n': n, 'gagne_pct': round(100 * sum(x['gagne'] for x in X) / n, 1),
            'algo_pct': round(100 * sum(x['p_algo'] for x in X) / n, 1),
            'marche_pct': round(100 * sum(x['p_marche'] for x in X) / n, 1),
            'log_loss_algo': round(sum(_ll(x['p_algo'], x['gagne']) for x in X) / n, 4),
            'log_loss_marche': round(sum(_ll(x['p_marche'], x['gagne']) for x in X) / n, 4),
            'conclusion_possible': n >= N_MIN}


def par_situation(X):
    out = {'tous': bilan(X), 'contre_favori_marche': bilan([x for x in X if x['contre_favori_marche']])}
    for c in ('ATP', 'WTA', 'CH'):
        out[f'circuit:{c}'] = bilan([x for x in X if x['circuit'] == c])
    for s in SITUATIONS:
        out[f'surestime:{s}'] = bilan([x for x in X if s in x['surestime']])
        out[f'sous_estime:{s}'] = bilan([x for x in X if s in x['sous_estime']])
    return out


def calculer(racine, archive):
    import donnees
    import feuilles as FE
    import roi_algo as RA
    import etude_rentabilite_marches as ER
    M = donnees.charger(archive, dt.date.today().year - 3)
    fin = max(m['date'] for m in M) if M else dt.date(2000, 1, 1)
    H = Historique(M + [m for m in FE.charger(racine) if m['date'] > fin])
    C = RA.clotures(racine)
    MP = ER.matchs_pinnacle(racine, ER._books(racine))
    noms = {uid: (m['home'], m['away']) for uid, m in MP.items()}
    try:
        R = json.load(open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8'))
        for m in R.get('matchs') or []:
            noms.setdefault(m['uid'], (m['home'], m['away']))
    except (OSError, ValueError, KeyError):
        pass
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'seuil_points': 100 * SEUIL,
           'regle': ("Loupe seulement : aucune entrée du modèle. Une piste devient un facteur candidat (sans cote, "
                     "jugé sur les résultats) après 30 matchs et plusieurs semaines dans le même sens.")}
    for nom, L in (('direct', RA.direct(racine)), ('rejoue', RA.rejoue(racine))):
        X = desaccords(L, C, noms, H, RA._cote)
        doc[nom] = par_situation(X)
    return doc


def _ligne(nom, b):
    if not b.get('n'):
        return None
    marque = '' if b['conclusion_possible'] else ' (n < 30)'
    qui = 'algo' if b['log_loss_algo'] < b['log_loss_marche'] else 'marché'
    return (f"• {nom} : n={b['n']}{marque} · a gagné {b['gagne_pct']} % (algo {b['algo_pct']} %, marché "
            f"{b['marche_pct']} %) → plus juste : {qui}")


def message(doc):
    L = ['<b>🔎 Désaccords algo / marché (≥ 8 pts vs clôture Pinnacle)</b>',
         "<i>Joueur que l'algo SURESTIME : a-t-il gagné autant que l'algo le disait ?</i>"]
    for ech in ('direct', 'rejoue'):
        P = doc.get(ech) or {}
        L.append(f"\n<b>{'EN DIRECT' if ech == 'direct' else 'REJOUÉ'}</b>")
        for k, lib in [('tous', 'tous les désaccords'), ('contre_favori_marche', "algo favori = outsider du marché"),
                       ('circuit:ATP', 'ATP'), ('circuit:WTA', 'WTA'), ('circuit:CH', 'Challenger')] + \
                      [(f'surestime:{s}', f'surestimé {LIB[s]}') for s in SITUATIONS] + \
                      [(f'sous_estime:{s}', f'sous-estimé {LIB[s]}') for s in SITUATIONS]:
            x = _ligne(lib, P.get(k) or {})
            if x:
                L.append(x)
    L.append("\n<i>Loupe seulement, rien n'entre dans le modèle. Ne pas diffuser.</i>")
    return '\n'.join(L)


def envoyer(texte):
    import urllib.parse
    import urllib.request
    tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not tok or not chat:
        return False
    data = urllib.parse.urlencode({'chat_id': chat, 'text': texte, 'parse_mode': 'HTML'}).encode()
    urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', data=data, timeout=20).read()
    return True


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    if not args:
        print('Usage : python simulateur/rapport_desaccords.py <archive Sackmann> [racine] [--telegram]')
        return 2
    racine = args[1] if len(args) > 1 else os.path.join(ICI, '..')
    doc = calculer(racine, args[0])
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    if '--telegram' in argv:
        try:
            envoyer(message(doc))
            print('Désaccords : envoyé sur le Telegram privé.')
        except Exception as e:
            print(f'::warning::Désaccords : Telegram impossible ({type(e).__name__})')
    else:
        print(message(doc))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
