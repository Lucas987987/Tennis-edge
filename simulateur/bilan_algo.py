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
22/10/2026 : chaque semaine, les décisions des règles sont ajoutées à simulateur/journal_decisions.jsonl ;
le premier lundi du mois, un BILAN DU MOIS en une page (fiabilité par circuit, % annoncé, ce qui a changé et
pourquoi) part aussi sur le canal privé (--mois pour le forcer).
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
    # abandons et forfaits exclus aussi (22/10/2026) : ils ne jugent pas le modèle
    Tous = [m for m in R.get('matchs') or [] if m.get('circuit') != 'ITF' and not (m.get('reel') or {}).get('interrompu')]
    n_int = sum(1 for m in R.get('matchs') or [] if (m.get('reel') or {}).get('interrompu') and m.get('debut', '') >= depuis)
    S = [m for m in Tous if m.get('debut', '') >= depuis]
    L = [f"🧠 <b>Bilan de l'algorithme</b> — semaine au {maintenant.date().strftime('%d/%m')}"]
    if S:
        L.append(f"\n🎾 <b>{len(S)} matchs joués</b> sur tes circuits (1re prédiction, avant le match ; ITF non compté)"
                 + (f" · {n_int} abandon(s) ou forfait(s) non compté(s)" if n_int else ''))
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


# ------------------------------------------------------------------ 22/10/2026 : journal des décisions, bilan du mois
JOURNAL = 'journal_decisions.jsonl'
MOIS = ('janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre')


def decisions(C, F):
    """Ce que les règles ont décidé, en clair (une ligne par décision ; comparé d'une semaine à l'autre)."""
    d = {}
    rg = C.get('reglage_simulation') or {}
    d['forme du jour (σ)'] = f"σ = {rg.get('sigma')}" if rg.get('adopte') else 'σ = 0,15 (réglage historique)'
    for cle_c, src in (('combinaison_continue', 'nos pronostics'), ('combinaison_feuilles', 'les feuilles'), ('combinaison', "l'archive")):
        c = C.get(cle_c) or {}
        if c.get('adopte') and c.get('poids'):
            w = c['poids']
            d['mélange simulation + Elo'] = (f"{100 * abs(w['simulation']) / (abs(w['simulation']) + abs(w['elo'])):.0f} % "
                                             f"simulation (appris sur {src})")
            break
    else:
        d['mélange simulation + Elo'] = 'non adopté'
    cb = C.get('combinaison') or {}
    poids = cb.get('poids') or {}
    d['correction de confiance'] = 'adoptée' if poids.get('calibration') else 'non adoptée'
    d['poids selon le contexte'] = 'adoptés' if poids.get('contexte') else 'non adoptés'
    d['apprend de qui a gagné'] = 'adopté' if (C.get('couche_resultats') or {}).get('adopte') else 'non adopté'
    d['poids propres aux Challenger'] = 'adoptés' if (C.get('poids_challenger') or {}).get('adopte') else 'non adoptés'
    nv = C.get('nouveaux_venus') or {}
    d['nouveaux venus'] = f"corrigés (δ = {nv.get('delta')})" if nv.get('adopte') else 'pas de correction'
    d['facteurs du match'] = ', '.join(LIB.get(g, g) for g in (F.get('adoptes') or [])) or 'aucun'
    return d


def raisons(C):
    """Le pourquoi de chaque décision (texte des règles), pour le bilan du mois."""
    out = []
    for cle_c, lib in (('reglage_simulation', 'Réglage de la simulation'), ('combinaison', 'Mélange simulation + Elo'),
                       ('combinaison_feuilles', 'Mélange appris sur les feuilles'), ('combinaison_continue', 'Mélange appris sur nos pronostics'),
                       ('poids_challenger', 'Poids propres aux Challenger'), ('nouveaux_venus', 'Nouveaux venus'),
                       ('couche_resultats', 'Apprendre de qui a gagné')):
        r = (C.get(cle_c) or {}).get('raison')
        if r:
            out.append(f"• {lib} : {r}")
    return out


def lire_journal(chemin):
    out = []
    try:
        with open(chemin, encoding='utf-8') as f:
            for l in f:
                try:
                    out.append(json.loads(l))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def bilan_du_mois(racine, maintenant, journal):
    """Le mois civil précédent, en une page : fiabilité par circuit (ITF non compté), le % annoncé tient-il,
    ce que les règles ont changé, et pourquoi."""
    fin = maintenant.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    debut = (fin - dt.timedelta(days=1)).replace(day=1)
    R = lire(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), {})
    C = lire(os.path.join(ICI, 'choix_simulation.json'), {})
    Mm = [m for m in R.get('matchs') or [] if m.get('circuit') != 'ITF' and not (m.get('reel') or {}).get('interrompu')
          and debut.isoformat(timespec='minutes') <= m.get('debut', '') < fin.isoformat(timespec='minutes')]
    L = [f"📅 <b>Bilan de {MOIS[debut.month - 1]} {debut.year}</b>"]
    v = [version_principale(m) for m in Mm]
    ok, n = taux(v, 'vainqueur_juste')
    if n:
        L.append(f"\n🎾 <b>{n} matchs</b> sur tes circuits · vainqueur trouvé {ok}/{n} ({100 * ok / n:.0f} %)")
        for c, lib in CIRCUITS:
            o, k = taux([version_principale(m) for m in Mm if m.get('circuit') == c], 'vainqueur_juste')
            if k:
                L.append(f"• {lib} : {o}/{k} ({100 * o / k:.0f} %)" + (' — moins de 30 matchs, ne pas conclure' if k < 30 else ''))
        tr = {}
        for x in v:
            if not x or x.get('proba_du_vainqueur') is None:
                continue
            p = x['proba_du_vainqueur']
            fav = max(p, 1 - p)
            t = min(int(fav * 10), 9) * 10
            tr.setdefault(t, []).append(fav == p and p != 0.5)
        if tr:
            L.append("\n📐 <b>Le % annoncé tient-il ?</b> (favori annoncé → gagne)")
            for t in sorted(tr):
                g = tr[t]
                L.append(f"• {t}–{t + 10} % → {100 * sum(g) / len(g):.0f} % ({len(g)} matchs)")
    else:
        L.append("\n🎾 Aucun match joué avec résultat ce mois-ci sur tes circuits.")
    J = [j for j in journal if debut.isoformat() <= j.get('date', '') < fin.isoformat()]
    if len(J) >= 2:
        a, b = J[0]['decisions'], J[-1]['decisions']
        ch = [f"• {k} : {a.get(k, '—')} → {b[k]}" for k in b if a.get(k) != b[k]]
        L.append("\n🔧 <b>Ce que les règles ont changé ce mois-ci</b>")
        L.extend(ch or ["• rien : le modèle est resté le même"])
    cur = J[-1]['decisions'] if J else decisions(C, lire(os.path.join(ICI, 'facteurs.json'), {}))
    L.append("\n🧭 <b>Le modèle aujourd'hui</b>")
    L.extend(f"• {k} : {v_}" for k, v_ in cur.items())
    rz = raisons(C)
    if rz:
        L.append("\n📝 <b>Pourquoi</b> (règles fixées avant de voir les résultats)")
        L.extend(rz)
    return '\n'.join(L)


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
    maintenant = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    texte, etat = construire(racine, maintenant)
    print(texte)
    envoyer(texte)
    # journal des décisions (une ligne par semaine) puis, le premier lundi du mois, le bilan du mois précédent
    chemin = os.path.join(ICI, JOURNAL)
    d = decisions(lire(os.path.join(ICI, 'choix_simulation.json'), {}), lire(os.path.join(ICI, 'facteurs.json'), {}))
    with open(chemin, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'date': maintenant.date().isoformat(), 'decisions': d}, ensure_ascii=False) + '\n')
    if maintenant.day <= 7 or '--mois' in argv:
        mois = bilan_du_mois(racine, maintenant, lire_journal(chemin))
        print('\n' + mois)
        envoyer(mois)
    with open(os.path.join(ICI, 'bilan_algo_etat.json'), 'w', encoding='utf-8') as f:
        json.dump(etat, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
