#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
controle_doublons_fin_archive.py — paquet 533 (28/11/2026). COMPTAGE SEUL : rien n'est modifié.

Question : un match joué à la fin de l'archive Sackmann (Roland-Garros 2026, joué jusqu'au 07/06) est-il compté deux
fois ? L'archive date chaque match du DÉBUT de son tournoi ; l'algo ajoute ensuite nos matchs « après la dernière date
de l'archive » (fin), ou « après fin + 3 jours » pour le classement Elo (backtest_pronostic.py). Un match de la 2e
semaine d'un tournoi commencé avant cette date peut donc être dans l'archive ET dans nos données.

Pour chaque source ajoutée après l'archive, on compte les matchs qui ont un jumeau dans l'archive (même paire de
joueurs, joué entre le début du tournoi de l'archive et 16 jours après) :
  • nos feuilles, après fin            (Elo service / retour, profils de service, styles, facteurs…) ;
  • nos feuilles, après fin + 3 jours  (classement Elo) ;
  • nos matchs suivis, après fin + 3 jours (classement Elo ; lus seulement s'ils sont là) ;
  • les résultats tennis-data, après fin + 3 jours (classement Elo, mises à jour sans surface).
Le journal n'affiche que des comptes, par circuit et par tournoi.

Usage : python simulateur/controle_doublons_fin_archive.py /tmp/sackmann [racine]
"""
import collections
import datetime as dt
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

import donnees  # noqa: E402
import elo as E  # noqa: E402
import feuilles as FE  # noqa: E402

FENETRE = 16
SORTIE = os.path.join(ICI, 'rapport_doublons_fin_archive.json')


def jumeaux(S, lignes, cle_s, cle_l, date_l, fenetre=FENETRE):
    """Indices des `lignes` qui ont un jumeau dans l'archive S (même paire, date dans [début ; début + fenêtre])."""
    index = collections.defaultdict(list)
    for s in S:
        for k in cle_s(s):
            index[k].append(s)
    out = {}
    for i, x in enumerate(lignes):
        d = date_l(x)
        for k in cle_l(x):
            t = [s for s in index.get(k, ()) if s['date'] <= d <= s['date'] + dt.timedelta(days=fenetre)]
            if t:
                out[i] = t[0]
                break
    return out


def resume(lignes, J, circuit, tournoi):
    par_c = collections.Counter(circuit(lignes[i]) for i in J)
    par_t = collections.Counter(tournoi(J[i]) for i in J)
    return {'ajoutes': len(lignes), 'en_double': len(J), 'par_circuit': dict(sorted(par_c.items())),
            'par_tournoi_archive': dict(par_t.most_common(12))}


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    archive = args[0] if args else '/tmp/sackmann'
    racine = args[1] if len(args) > 1 else os.path.join(ICI, '..')
    S = donnees.charger(archive, 2025)
    if not S:
        print('::error::archive absente')
        return 1
    fin = max(s['date'] for s in S)
    fin3 = fin + dt.timedelta(days=3)
    proches = [s for s in S if s['date'] >= fin - dt.timedelta(days=FENETRE)]
    print(f"Archive : dernière date {fin} (début du dernier tournoi) · {len(proches)} matchs datés des 16 derniers jours",
          flush=True)
    try:
        with open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8') as f:
            alias = dict(E.migrer_etat(json.load(f)).get('alias') or {})
    except (OSError, ValueError):
        alias = {}
    F = FE.charger(racine)
    connus = {}
    for s in S:
        for n in (s['nom_g'], s['nom_p']):
            connus.setdefault(E.cle(n), n)
    for k, v in E.unifier(connus, {n for m in F for n in (m['nom_g'], m['nom_p']) if n}).items():
        alias.setdefault(k, v)
    ck = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    paire_s = lambda s: [frozenset((ck(s['nom_g']), ck(s['nom_p'])))]  # noqa: E731
    tournoi_s = lambda s: f"{s.get('tournoi') or '?'} ({s['circuit']}, début {s['date']})"  # noqa: E731
    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': 533,
           'archive_derniere_date': fin.isoformat(), 'archive_16_derniers_jours': len(proches), 'sources': {}}

    def compter(nom, lignes, cle_l, date_l, circuit, extra=None, cle_s=paire_s):
        J = jumeaux(proches, lignes, cle_s, cle_l, date_l)
        r = resume(lignes, J, circuit, tournoi_s)
        if extra:
            r.update(extra(lignes, J))
        rap['sources'][nom] = r
        print(f"  {nom} : {r['en_double']} en double sur {r['ajoutes']} ajoutés · par circuit {r['par_circuit']}",
              flush=True)
        for t, n in r['par_tournoi_archive'].items():
            print(f"      {n:5d}  {t}")

    paire_f = lambda m: [frozenset((ck(m['nom_g']), ck(m['nom_p'])))]  # noqa: E731
    stats = lambda L, J: {'en_double_avec_stats': sum(1 for i in J if L[i].get('stats'))}  # noqa: E731
    compter('feuilles après fin (service / retour, profils, styles)', [m for m in F if m['date'] > fin],
            paire_f, lambda m: m['date'], lambda m: m['circuit'], stats)
    fe3 = [m for m in F if m['date'] > fin3 and m['nom_g'] and m['nom_p']]
    compter('feuilles après fin + 3 j (classement Elo)', fe3, paire_f, lambda m: m['date'], lambda m: m['circuit'], stats)

    try:                                                   # nos matchs suivis : seulement s'ils ont été rapatriés
        import nos_resultats as NR
        nous = [x for x in NR.charger(racine, NR.surfaces_tournois(S)) if x['date'] > fin3]
    except Exception as ex:  # noqa: BLE001
        nous = None
        print(f'  nos matchs suivis : non lus ({type(ex).__name__})')
    if nous is not None:
        compter('nos matchs suivis après fin + 3 j (classement Elo)', nous,
                lambda x: [frozenset((ck(x['home']), ck(x['away'])))], lambda x: x['date'],
                lambda x: 'GC' if x.get('grand_chelem') else 'autres')

    td = []
    try:
        import csv
        import gzip
        with gzip.open(os.path.join(racine, 'historique', 'tennis_data_resultats.csv.gz'), 'rt', encoding='utf-8') as fh:
            for r in csv.DictReader(fh):
                try:
                    d = dt.date.fromisoformat(r['date'])
                except (KeyError, ValueError):
                    continue
                if d > fin3 and r.get('vainqueur') and r.get('perdant'):
                    td.append((d, r['vainqueur'], r['perdant'], r.get('circuit') or '?'))
    except OSError:
        print('  tennis-data : fichier absent')
    if td:
        cles_s = lambda s: [(a, b) for a in donnees.cles_sackmann(s['nom_g'])  # noqa: E731
                            for b in donnees.cles_sackmann(s['nom_p'])]          # même appariement que donnees.joindre
        compter('tennis-data après fin + 3 j (classement Elo)', td,
                lambda t: [(donnees.cle_td(t[1]), donnees.cle_td(t[2]))], lambda t: t[0], lambda t: t[3], cle_s=cles_s)
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
