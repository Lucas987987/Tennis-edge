#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bilan_algo.py — bilan de la semaine de l'algorithme, sur Telegram (canal PRIVÉ) — 22/10/2026.

Envoyé après le ré-apprentissage du lundi (« Pronostic - test du modèle ») :
  — les 7 derniers jours : vainqueurs trouvés, sets justes, scores justes, par version ;
  — les plus grosses erreurs (le favori annoncé le plus sûr qui a perdu) ;
  — ce qui a changé dans le modèle : facteurs entrés / sortis, poids de la simulation, source des poids ;
  — l'entraînement semaine après semaine (progression).
Mémoire d'une semaine à l'autre : simulateur/bilan_algo_etat.json.
Env : TELEGRAM_TOKEN / TELEGRAM_CHAT_ID (sans eux : affiché seulement). Usage : python simulateur/bilan_algo.py [racine]
"""
import datetime as dt
import json
import os
import sys
import urllib.parse
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
VERSIONS = (('combinaison', 'Simulation + Elo'), ('simulation', 'Simulation'), ('stats', 'Elo'), ('marche', 'Pinnacle'))
LIB = {'forme_fatigue': 'forme/fatigue', 'vitesse_court': 'vitesse du court', 'morphologie': 'gaucher/taille',
       'points_importants': 'points importants', 'styles': 'styles', 'face_a_face': 'face-à-face', 'conditions': 'conditions',
       'contexte_tournoi': 'contexte du tournoi', 'charting': 'Match Charting', 'blessure': 'blessure'}


def lire(chemin, defaut):
    try:
        with open(chemin, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def taux(L, cle):
    g = [x for x in L if x is not None and x.get(cle) is not None]
    return (sum(1 for x in g if x[cle]), len(g))


CIRCUITS = (('ATP', 'ATP'), ('WTA', 'WTA'), ('CH', 'Challenger'))


def version_principale(m):
    pr = m.get('premier') or {}
    return next((pr[k] for k in ('combinaison', 'simulation', 'stats') if pr.get(k) and pr[k].get('vainqueur_juste') is not None), None)


def lignes_circuits(S, Tous):
    """22/10/2026 — fiabilité sur les circuits JOUÉS (ATP, WTA, Challenger), semaine et depuis le début ;
    version principale (Simulation + Elo, sinon simulation, sinon Elo). L'ITF n'est pas compté."""
    out = []
    for c, lib in CIRCUITS:
        def t(L):
            v = [version_principale(m) for m in L if m.get('circuit') == c]
            return taux(v, 'vainqueur_juste')
        (o7, n7), (o, n) = t(S), t(Tous)
        if not n:
            continue
        out.append(f"• {lib} : " + (f"{o7}/{n7} ({100 * o7 / n7:.0f} %) cette semaine · " if n7 else 'rien cette semaine · ')
                   + f"{o}/{n} ({100 * o / n:.0f} %) depuis le début")
    return out


def construire(racine, maintenant=None):
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    R = lire(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), {})
    F = lire(os.path.join(ICI, 'facteurs.json'), {})
    C = lire(os.path.join(ICI, 'choix_simulation.json'), {})
    E = lire(os.path.join(ICI, 'bilan_algo_etat.json'), {})
    depuis = (maintenant - dt.timedelta(days=7)).isoformat(timespec='minutes')
    # ITF exclu partout (22/10/2026) : aucun pari n'y est joué, il ne doit pas peser sur la fiabilité lue
    Tous = [m for m in R.get('matchs') or [] if m.get('circuit') != 'ITF']
    S = [m for m in Tous if m.get('debut', '') >= depuis]
    L = [f"🧠 <b>Bilan de l'algorithme</b> — semaine au {maintenant.date().strftime('%d/%m')}"]
    if S:
        L.append(f"\n🎾 <b>{len(S)} matchs joués</b> sur tes circuits (1re prédiction, avant le match ; ITF non compté)")
        for k, lab in VERSIONS:
            v = [(m.get('premier') or {}).get(k) for m in S]
            ok, n = taux(v, 'vainqueur_juste')
            if not n:
                continue
            s_ok, s_n = taux(v, 'sets_justes')
            c_ok, c_n = taux(v, 'score_juste')
            L.append(f"• {lab} : vainqueur {ok}/{n} ({100 * ok / n:.0f} %)"
                     + (f" · sets {s_ok}/{s_n}" if s_n else '') + (f" · score exact {c_ok}/{c_n}" if c_n else ''))
        lc = lignes_circuits(S, Tous)
        if lc:
            L.append("\n🎯 <b>Par circuit</b> (vainqueur trouvé, version principale ; ITF non compté)")
            L.extend(lc)
        err = []
        for m in S:
            pr = m.get('premier') or {}
            k = next((x for x in ('combinaison', 'simulation', 'stats') if pr.get(x)), None)
            if k and pr[k].get('vainqueur_juste') is False:
                err.append((1 - pr[k]['proba_du_vainqueur'], m))
        err.sort(key=lambda e: -e[0])
        if err:
            L.append("\n❌ <b>Plus grosses erreurs</b>")
            for p, m in err[:3]:
                perdant = m['away'] if (m.get('reel') or {}).get('gagnant') == 'home' else m['home']
                L.append(f"• {perdant} annoncé à {100 * p:.0f} %, battu ({m.get('tournoi', '')}"
                         + (f", {m['reel']['score']}" if (m.get('reel') or {}).get('score') else '') + ")")
    else:
        L.append("\n🎾 Aucun match joué avec son résultat cette semaine (enregistrement « prédit / réel » en cours).")
    ad = F.get('adoptes') or []
    avant = E.get('adoptes')
    L.append("\n🔧 <b>Modèle</b>")
    L.append(f"• Facteurs retenus : {', '.join(LIB.get(g, g) for g in ad) or 'aucun'}")
    if avant is not None:
        entres, sortis = [g for g in ad if g not in avant], [g for g in avant if g not in ad]
        if entres or sortis:
            L.append(f"• Changements : " + ' · '.join([f"+ {LIB.get(g, g)}" for g in entres] + [f"− {LIB.get(g, g)}" for g in sortis]))
        else:
            L.append("• Aucun facteur entré ni sorti")
    for cle_c, src in (('combinaison_continue', 'nos pronostics en direct'), ('combinaison_feuilles', 'les feuilles semaine après semaine'),
                       ('combinaison', "l'archive 2024–2026")):
        c = C.get(cle_c) or {}
        if c.get('adopte') and c.get('poids'):
            w = c['poids']
            part = 100 * abs(w['simulation']) / (abs(w['simulation']) + abs(w['elo']))
            L.append(f"• Simulation + Elo : poids de la simulation {part:.0f} % (appris sur {src})")
            break
    cc = C.get('combinaison_continue') or {}
    if cc and not cc.get('adopte'):
        L.append(f"• Apprentissage sur nos pronostics : {cc.get('raison', '—')}")
    ep = F.get('entrainement_progressif') or {}
    W = ep.get('semaines') or []
    if W:
        a, b = W[0], W[-1]
        L.append(f"\n📈 <b>Entraînement semaine après semaine</b> ({len(W)} semaines rejouées) : simulation "
                 f"{a['simulation']['reussite_pct']} % → {b['simulation']['reussite_pct']} % · Elo {a['elo']['reussite_pct']} % → "
                 f"{b['elo']['reussite_pct']} % (1re et dernière semaine)")
    return '\n'.join(L), {'adoptes': ad, 'genere_le': maintenant.isoformat(timespec='seconds')}


def envoyer(texte):
    token, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not token or not chat:
        print('[non envoyé : TELEGRAM_TOKEN / TELEGRAM_CHAT_ID absents]')
        return False
    try:
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                     data=urllib.parse.urlencode({'chat_id': chat, 'text': texte, 'parse_mode': 'HTML',
                                                                  'disable_web_page_preview': 'true'}).encode())
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ Telegram : {e}")
        return False


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    texte, etat = construire(racine)
    print(texte)
    envoyer(texte)
    with open(os.path.join(ICI, 'bilan_algo_etat.json'), 'w', encoding='utf-8') as f:
        json.dump(etat, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
