#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
controle_donnees.py — CONTRÔLE QUOTIDIEN DE LA QUALITÉ DES DONNÉES (18/11/2026, paquet 272, demande de Lucas :
« on travaille sur la qualité des données »).

Pour chaque match de notre journal (simulateur/pronostics_log.jsonl) commencé depuis plus de 12 h et depuis moins de
JOURS jours, une seule cause, dans cet ordre :
  résolu                 — présent dans Tennis_Edge_Lab/live/pronostics_resultats.json ;
  adversaire fictif      — « R16P3 », « QF7 »… (vainqueur à venir ; filtré depuis le 04/11, restes du journal) ;
  doublon reprogrammé    — même paire de joueurs sous un autre uid à moins de 48 h (match déplacé) : une seule fois
                           dans les bilans, rien à réparer ;
  abandon / forfait      — feuille TennisApi « Retired » / « Walkover » : volontairement non jugés ;
  annulé ou reporté      — feuille « Canceled », « Postponed »… ;
  feuille terminée non résolue — feuille « Ended » trouvée mais pas de résultat : DÉFAUT à corriger ;
  adversaire remplacé    — pas de feuille pour la paire, mais un des joueurs a joué un autre adversaire à ± 3 h de
                           l'horaire prévu (repêché, forfait remplacé) : le match annoncé n'a pas eu lieu ;
  aucune feuille         — rien du tout : TROU DE COLLECTE (ou match pas encore relevé).
Aussi : paires affichées deux fois sur le site (algo/donnees.json) et paires résolues deux fois (bilans faussés).
ALERTE (Telegram privé) si, sur la veille, « aucune feuille » + « feuille terminée non résolue » dépassent 10 % des
matchs réels (hors adversaires fictifs et doublons), ou si une paire est résolue deux fois.
Sorties : simulateur/rapport_qualite_donnees.json (public : des comptes, aucun nom, aucune cote) ;
détail des matchs sur le Telegram privé. Descriptif : rien n'entre dans le %.
Usage : python simulateur/controle_donnees.py [racine] [--telegram]
"""
import collections
import datetime as dt
import json
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
JOURS = 30
SEUIL_ALERTE = 0.10
FENETRE_REPLACE_H = 3
CAUSES = ('résolu', 'adversaire fictif', 'doublon reprogrammé', 'abandon / forfait', 'annulé ou reporté',
          'feuille terminée non résolue', 'adversaire remplacé', 'aucune feuille')
DEFAUTS = ('feuille terminée non résolue', 'aucune feuille')
_FICTIF = re.compile(r'^(r\d+p\d+|qf\d+|sf\d+|f\d+)$', re.I)


def _utc(s):
    d = dt.datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def fictif(nom):
    return bool(_FICTIF.match(re.sub(r'[^a-z0-9]', '', str(nom).lower())))


def journal(racine):
    out, vus = [], set()
    try:
        with open(os.path.join(racine, 'simulateur', 'pronostics_log.jsonl'), encoding='utf-8') as f:
            for l in f:
                try:
                    r = json.loads(l)
                except ValueError:
                    continue
                if r.get('uid') and r['uid'] not in vus:
                    vus.add(r['uid'])
                    out.append(r)
    except OSError:
        pass
    return out


def resolus(racine):
    try:
        with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
            return json.load(f).get('matchs') or []
    except (OSError, ValueError):
        return []


def paire(m):
    import elo as E
    return frozenset((E.cle(m['home']), E.cle(m['away'])))


class ParJoueur:
    """Feuilles indexées par joueur (clé Elo) : [(début UTC, clé de l'adversaire, feuille)]."""

    def __init__(self, fiches):
        import elo as E
        self.d = collections.defaultdict(list)
        for r in fiches:
            try:
                t = dt.datetime.fromtimestamp(int(r['debut']), dt.timezone.utc)
            except (KeyError, TypeError, ValueError):
                continue
            h, a = E.cle((r.get('home') or {}).get('nom') or ''), E.cle((r.get('away') or {}).get('nom') or '')
            self.d[h].append((t, a, r))
            self.d[a].append((t, h, r))

    def remplace(self, m):
        """Vrai si un des deux joueurs a joué un AUTRE adversaire à ± 3 h de l'horaire annoncé."""
        import elo as E
        t0 = _utc(m['debut'])
        h, a = E.cle(m['home']), E.cle(m['away'])
        for j, adv in ((h, a), (a, h)):
            for t, autre, _ in self.d.get(j, []):
                if autre != adv and abs((t - t0).total_seconds()) <= FENETRE_REPLACE_H * 3600:
                    return True
        return False


def classer(racine, maintenant=None):
    import feuilles as FE
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    J = journal(racine)
    lim0, lim1 = maintenant - dt.timedelta(days=JOURS), maintenant - dt.timedelta(hours=12)
    P = [r for r in J if r.get('debut') and lim0 <= _utc(r['debut']) <= lim1]
    R = resolus(racine)
    ok = {m['uid'] for m in R}
    depuis = (lim0.date() - dt.timedelta(days=1)).isoformat()
    fiches = FE.lire(racine, depuis=depuis)
    idx, pj = FE.Index(fiches), ParJoueur(fiches)
    par_paire = collections.defaultdict(list)
    for r in J:
        if r.get('debut') and not (fictif(r['home']) or fictif(r['away'])):
            par_paire[paire(r)].append(r)
    out = []
    for r in P:
        if r['uid'] in ok:
            c = 'résolu'
        elif fictif(r['home']) or fictif(r['away']):
            c = 'adversaire fictif'
        elif any(o['uid'] != r['uid'] and abs((_utc(o['debut']) - _utc(r['debut'])).total_seconds()) < 48 * 3600
                 for o in par_paire[paire(r)]):
            c = 'doublon reprogrammé'
        else:
            fi, _ = idx.trouver(r['debut'][:10], r['home'], r['away'])
            txt = str(((fi or {}).get('statut') or {}).get('texte') or '').lower()
            if fi is not None and txt in ('retired', 'defaulted', 'walkover'):
                c = 'abandon / forfait'
            elif fi is not None and txt in ('canceled', 'cancelled', 'postponed', 'abandoned', 'interrupted', 'suspended'):
                c = 'annulé ou reporté'
            elif fi is not None and txt == 'ended':
                c = 'feuille terminée non résolue'
            elif fi is None and pj.remplace(r):
                c = 'adversaire remplacé'
            elif fi is None:
                c = 'aucune feuille'
            else:
                c = 'annulé ou reporté'
        out.append({'uid': r['uid'], 'jour': r['debut'][:10], 'circuit': r.get('circuit') or '?', 'cause': c})
    return out, R


def doubles_resolus(R):
    G = collections.defaultdict(list)
    for m in R:
        if m.get('debut') and m.get('home') and m.get('away'):
            G[paire(m)].append(m)
    n = []
    for L in G.values():
        L.sort(key=lambda m: m['debut'])
        for a, b in zip(L, L[1:]):
            ra, rb = a.get('reel') or {}, b.get('reel') or {}
            # même match compté deux fois = même score (ou même vainqueur sans score) ; deux vrais matchs de suite
            # (finale de qualifications puis tableau principal, ex. Bâle 25-26/10) ne sont pas un défaut
            meme = (ra.get('score') and ra.get('score') == rb.get('score')) or (
                not ra.get('score') and not rb.get('score') and ra.get('gagnant')
                and {a.get('home'): ra.get('gagnant')} == {b.get('home'): rb.get('gagnant')})
            if meme and abs((_utc(b['debut']) - _utc(a['debut'])).total_seconds()) < 72 * 3600:
                n.append((a['uid'], b['uid']))
    return n


def doubles_site(racine):
    try:
        with open(os.path.join(racine, 'algo', 'donnees.json'), encoding='utf-8') as f:
            M = json.load(f).get('matchs') or []
    except (OSError, ValueError):
        return []
    G = collections.defaultdict(list)
    for m in M:
        if m.get('home') and m.get('away'):
            G[paire(m)].append(m['uid'])
    return [L for L in G.values() if len(L) > 1]


def rapport(racine, maintenant=None):
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    L, R = classer(racine, maintenant)
    compte = lambda X: {c: sum(x['cause'] == c for x in X) for c in CAUSES}  # noqa: E731
    reels = lambda X: [x for x in X if x['cause'] not in ('adversaire fictif', 'doublon reprogrammé')]  # noqa: E731
    taux = lambda X: round(100 * sum(x['cause'] in DEFAUTS for x in reels(X)) / len(reels(X)), 1) if reels(X) else None  # noqa: E731
    veille = (maintenant - dt.timedelta(days=1)).date().isoformat()
    V = [x for x in L if x['jour'] == veille]
    dr, ds = doubles_resolus(R), doubles_site(racine)
    alerte = []
    if taux(V) is not None and taux(V) > 100 * SEUIL_ALERTE:
        alerte.append(f'veille : {taux(V)} % de matchs sans résultat exploitable (seuil {int(100 * SEUIL_ALERTE)} %)')
    if dr:
        alerte.append(f'{len(dr)} paire(s) résolue(s) deux fois')
    par_jour = {}
    for j in sorted({x['jour'] for x in L})[-14:]:
        X = [x for x in L if x['jour'] == j]
        par_jour[j] = {'matchs': len(X), 'resolus': sum(x['cause'] == 'résolu' for x in X), 'defauts_pct': taux(X)}
    return {'genere_le': maintenant.isoformat(timespec='seconds'), 'paquet': 272, 'fenetre_jours': JOURS,
            'regle': __doc__.split('JOURS jours, une seule cause, dans cet ordre :')[1].split('Sorties :')[0]
            .replace('\n', ' ').strip(),
            'matchs': len(L), 'causes': compte(L),
            'par_circuit': {c: compte([x for x in L if x['circuit'] == c]) for c in ('ATP', 'WTA', 'CH')},
            'defauts_pct': taux(L), 'veille': {'jour': veille, 'causes': compte(V), 'defauts_pct': taux(V)},
            'par_jour': par_jour, 'paires_resolues_deux_fois': len(dr), 'paires_en_double_sur_le_site': len(ds),
            'alerte': alerte, 'descriptif': 'le % de victoire ne change pas'}, L, dr, ds


def message(r, L, dr, ds):
    v = r['veille']
    lignes = [f"🧹 Qualité des données — veille ({v['jour']}) : {v['defauts_pct']} % de défauts",
              *(f"  {c} : {n}" for c, n in v['causes'].items() if n),
              f"30 jours : {r['matchs']} matchs · défauts {r['defauts_pct']} %"]
    for c in ('feuille terminée non résolue', 'aucune feuille', 'adversaire remplacé'):
        X = [x['uid'] for x in L if x['jour'] == v['jour'] and x['cause'] == c]
        if X:
            lignes.append(f"{c} : " + ', '.join(X[:12]) + (' …' if len(X) > 12 else ''))
    if dr:
        lignes.append('Résolus deux fois : ' + ', '.join(f'{a} / {b}' for a, b in dr[:6]))
    if ds:
        lignes.append('En double sur le site : ' + ', '.join(' / '.join(x) for x in ds[:6]))
    if r['alerte']:
        lignes.insert(0, '⚠️ ' + ' ; '.join(r['alerte']))
    return '\n'.join(lignes)


def envoyer(texte):
    import urllib.request
    tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
    if not tok or not chat:
        print('Telegram non configuré : message non envoyé')
        return
    data = json.dumps({'chat_id': chat, 'text': texte[:4000]}).encode()
    req = urllib.request.Request(f'https://api.telegram.org/bot{tok}/sendMessage', data=data,
                                 headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req, timeout=30).read()


def main(argv):
    racine = next((a for a in argv if not a.startswith('--')), os.path.join(ICI, '..'))
    r, L, dr, ds = rapport(racine)
    with open(os.path.join(racine, 'simulateur', 'rapport_qualite_donnees.json'), 'w', encoding='utf-8') as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    texte = message(r, L, dr, ds)
    if '--telegram' in argv:
        envoyer(texte)
    print(texte)


if __name__ == '__main__':
    main(sys.argv[1:])
