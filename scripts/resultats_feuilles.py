#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resultats_feuilles.py — COMPLÉTER LES RÉSULTATS MANQUANTS DES JOURNAUX DE SUIVI AVEC LES FEUILLES DE MATCH
(20/11/2026, paquet 305, chantier « qualité des données » de Lucas).

Constat (copie du dépôt du 19/11) : des positions de suivi restent « ouvertes » des semaines après le match, faute de
résultat dans set_results.json (la source de règlement de l'API ne renvoie rien pour une partie des Challenger et des
qualifications) :
  paper_trades_match.jsonl : 46 positions ouvertes sur des matchs commencés il y a plus de 3 jours, 0 avec un résultat ;
  paper_trades_set1.jsonl  : 37 dans le même cas ;
  paper_trades_canal.jsonl : 151 alertes du canal encore « OUVERT » sans résultat.
Ces matchs ont pourtant une feuille de match TennisApi dans feuilles/AAAA-MM-JJ.jsonl.gz (relevée pour l'algo) : on y
lit le vainqueur du match et de chaque set.

Ce que fait le script, à chaque cycle du pipeline, AVANT les journaux :
  - pour chaque position ou alerte (ouverte, sans résultat, ou abandonnée faute de résultat) dont le match a commencé
    depuis plus de 6 h et dont l'uid n'a pas de vainqueur dans set_results.json ;
  - cherche la feuille du même jour (± 1) : mêmes deux joueurs (nom complet, sans accents ni tirets ; sinon même nom
    de famille et même initiale), début à moins de 18 h de l'horaire annoncé, match TERMINÉ (« Ended ») — les abandons,
    forfaits et matchs annulés ne sont PAS remplis (les journaux gardent leur règle) ;
  - écrit {"match", "set1", "set2"} dans set_results.json sous l'uid, dans le sens de l'uid (date_domicile_extérieur),
    jamais par-dessus un résultat déjà là, et garde la trace dans set_results_feuilles.json (uid → id de la feuille).
Rien ne change dans la façon de juger : seul le résultat manquant est ajouté, depuis une source déjà utilisée par l'algo.
0 requête d'API. Usage : python scripts/resultats_feuilles.py [racine]
"""
import datetime as dt
import gzip
import json
import os
import re
import sys
import unicodedata

JOURNAUX = ('paper_trades_match.jsonl', 'paper_trades_set1.jsonl', 'paper_trades_set2.jsonl', 'paper_trades_canal.jsonl')
A_COMPLETER = {'OPEN', 'CLOSED_NO_RESULT', 'ABANDONNED', 'OUVERT'}
DELAI_H, ECART_H = 6, 18


def slug(x):
    x = unicodedata.normalize('NFD', str(x or '').lower().strip())
    x = ''.join(c for c in x if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '_', x).strip('_')


def compact(x):
    return slug(x).replace('_', '')


def court(nom):
    """(initiale du prénom, nom de famille) — repli quand les deux sources écrivent le prénom différemment."""
    t = slug(nom).split('_')
    return (t[0][:1], t[-1]) if t and t[0] else ('', '')


def instant(v):
    if v is None or v == '':
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        d = dt.datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.timestamp()


def lire_journal(chemin):
    out = []
    try:
        with open(chemin, encoding='utf-8') as f:
            for ligne in f:
                ligne = ligne.strip()
                if ligne:
                    try:
                        out.append(json.loads(ligne))
                    except ValueError:
                        continue
    except OSError:
        pass
    return out


class Feuilles:
    def __init__(self, dossier):
        self.dossier, self.cache = dossier, {}

    def du_jour(self, jour):
        if jour not in self.cache:
            L = []
            ch = os.path.join(self.dossier, f'{jour}.jsonl.gz')
            try:
                with gzip.open(ch, 'rt', encoding='utf-8') as f:
                    for ligne in f:
                        try:
                            L.append(json.loads(ligne))
                        except ValueError:
                            continue
            except (OSError, EOFError):
                pass
            self.cache[jour] = L
        return self.cache[jour]

    def autour(self, t):
        j = dt.datetime.fromtimestamp(t, dt.timezone.utc).date()
        for k in (0, -1, 1):
            yield from self.du_jour((j + dt.timedelta(days=k)).isoformat())


def gagnants(fe):
    """{'match', 'set1', 'set2'} du point de vue de la feuille ('home' / 'away'), ou None si pas terminé."""
    st = fe.get('statut') or {}
    if st.get('type') != 'finished' or str(st.get('texte', '')).lower() != 'ended':
        return None
    v = fe.get('vainqueur')
    if v not in (1, 2):
        return None
    out = {'match': 'home' if v == 1 else 'away'}
    sh, sa = (fe.get('score_home') or {}).get('sets') or [], (fe.get('score_away') or {}).get('sets') or []
    th, ta = (fe.get('score_home') or {}).get('tb') or [], (fe.get('score_away') or {}).get('tb') or []
    for i, cle in ((0, 'set1'), (1, 'set2')):
        if i < len(sh) and i < len(sa) and sh[i] is not None and sa[i] is not None:
            if sh[i] != sa[i]:
                out[cle] = 'home' if sh[i] > sa[i] else 'away'
            elif i < len(th) and i < len(ta) and th[i] is not None and ta[i] is not None and th[i] != ta[i]:
                out[cle] = 'home' if th[i] > ta[i] else 'away'
    return out


def sens(fe, uid, home=None, away=None):
    """+1 si la feuille est dans le sens de l'UID (celui de set_results.json : date_domicile_extérieur), −1 si inversée,
    0 si ce n'est pas le même match. Les champs home/away d'une position ne servent qu'à reconnaître les joueurs : ils
    ne sont pas toujours dans le sens de l'uid (vu le 20/11 sur 2 matchs)."""
    fh, fa = (fe.get('home') or {}).get('nom'), (fe.get('away') or {}).get('nom')
    if not fh or not fa:
        return 0
    ch, ca = compact(fh), compact(fa)
    reste = compact(uid[11:]) if re.match(r'^\d{4}-\d{2}-\d{2}_', uid or '') else ''
    if reste and reste == ch + ca:
        return 1
    if reste and reste == ca + ch:
        return -1
    if home and away:
        # joueurs reconnus par les champs : le sens est celui de l'uid si l'uid commence par le domicile du champ
        s = _sens_champs(fh, fa, home, away)
        if s and reste:
            return s if reste.startswith(compact(home)) else (-s if reste.startswith(compact(away)) else 0)
        return s
    return 0


def _sens_champs(fh, fa, home, away):
    """Mêmes joueurs que les champs home/away (nom complet, sinon initiale + nom) : +1 même ordre, −1 inversé, 0 non."""
    ch, ca, uh, ua = compact(fh), compact(fa), compact(home), compact(away)
    if (ch, ca) == (uh, ua) or (court(fh), court(fa)) == (court(home), court(away)):
        return 1
    if (ch, ca) == (ua, uh) or (court(fh), court(fa)) == (court(away), court(home)):
        return -1
    return 0


def a_completer(racine, sr, maintenant):
    """{uid: (instant du match, domicile, extérieur)} des positions sans résultat."""
    out = {}
    for nom in JOURNAUX:
        for t in lire_journal(os.path.join(racine, nom)):
            uid = t.get('uid')
            st = t.get('status') or t.get('statut')
            if not uid or st not in A_COMPLETER or (sr.get(uid) or {}).get('match') in ('home', 'away'):
                continue
            ti = instant(t.get('commence'))
            if ti is None or maintenant - ti < DELAI_H * 3600:
                continue
            # L'uid porte la date d'UNE rencontre : si le match annoncé est à plus d'un jour de cette date, c'est une
            # autre rencontre des mêmes joueurs (vu le 20/11 sur 3 alertes du canal) : on n'écrit rien sous cet uid.
            if re.match(r'^\d{4}-\d{2}-\d{2}_', uid):
                jour_uid = dt.date.fromisoformat(uid[:10])
                if abs((dt.datetime.fromtimestamp(ti, dt.timezone.utc).date() - jour_uid).days) > 1:
                    continue
            if uid not in out or (t.get('home') and not out[uid][1]):
                out[uid] = (ti, t.get('home'), t.get('away'))
    return out


def completer(racine='.', maintenant=None, ecrire=True):
    maintenant = maintenant if maintenant is not None else dt.datetime.now(dt.timezone.utc).timestamp()
    ch_sr = os.path.join(racine, 'set_results.json')
    try:
        with open(ch_sr, encoding='utf-8') as f:
            sr = json.load(f)
    except (OSError, ValueError):
        print('set_results.json illisible : rien fait.')
        return {}
    ch_trace = os.path.join(racine, 'set_results_feuilles.json')
    try:
        with open(ch_trace, encoding='utf-8') as f:
            trace = json.load(f)
    except (OSError, ValueError):
        trace = {}
    F = Feuilles(os.path.join(racine, 'feuilles'))
    besoin = a_completer(racine, sr, maintenant)
    ajoutes, non_finis, introuvables = {}, 0, 0
    for uid, (ti, home, away) in sorted(besoin.items()):
        trouve = None
        for fe in F.autour(ti):
            if abs(float(fe.get('debut') or 0) - ti) > ECART_H * 3600:
                continue
            s = sens(fe, uid, home, away)
            if s:
                trouve = (fe, s)
                break
        if not trouve:
            introuvables += 1
            continue
        fe, s = trouve
        g = gagnants(fe)
        if not g:
            non_finis += 1
            continue
        if s < 0:
            g = {k: ('away' if v == 'home' else 'home') for k, v in g.items()}
        ajoutes[uid] = g
        trace[uid] = {'feuille': fe.get('id'), 'jour': fe.get('jour'), 'ajoute_le': dt.datetime.now(dt.timezone.utc)
                      .isoformat(timespec='seconds')}
    if ajoutes and ecrire:
        sr.update(ajoutes)
        tmp = ch_sr + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(sr, f, ensure_ascii=False, indent=1)
        os.replace(tmp, ch_sr)
        with open(ch_trace, 'w', encoding='utf-8') as f:
            json.dump(trace, f, ensure_ascii=False, indent=1, sort_keys=True)
    print(f"Résultats depuis les feuilles : {len(besoin)} match(s) sans résultat → {len(ajoutes)} complété(s), "
          f"{non_finis} non terminé(s) (abandon, forfait, annulé : laissés tels quels), {introuvables} sans feuille.")
    return ajoutes


if __name__ == '__main__':
    completer(sys.argv[1] if len(sys.argv) > 1 else '.')
