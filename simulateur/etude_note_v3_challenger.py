#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_note_v3_challenger.py — RÉAPPRENDRE LA NOTE DE FIABILITÉ DU CHALLENGER SUR LE REJEU COMME EN PRODUCTION
(25/11/2026, paquet 449, accord de Lucas après l'analyse 448).

POURQUOI. La note v3 (simulateur/rapport_fiabilite_v3.json, etude_fiabilite_v3.py) donne à chaque match la note
100 · min(a, 1/a), a = pente d'étalonnage de sa case, apprise sur l'archive 2016–2022. En Challenger, l'archive n'a pas
les résultats ITF hommes : ses pentes y sont 0,75 (moins de 30 matchs), 0,79 (30–99), 0,92 (100–299 et 300 +), donc
« % trop sûrs », alors que le rejeu comme en production (ITF hommes compris) trouve l'Elo Challenger un peu trop
TIMIDE (analyse 448). Les niveaux fragile / prudent / correct / solide du Challenger reposeraient donc en partie sur
une mesure faussée — le piège déjà rencontré aux paquets 229, 230 et 317–319.

CE QUE J'AI DÉJÀ VU DE LA PÉRIODE avant d'écrire cette règle (honnêteté) : l'analyse 448 a publié la pente de chaque
classe d'expérience sur TOUTE la fenêtre 01/01/2025 → 31/05/2026 (1,09 ; 1,075 ; 1,10 ; 0,89). Le découpage
apprentissage / jugement ci-dessous n'a pas été regardé. Les résultats ITF hommes n'existent que depuis juin 2024 :
2018–2022 → 2023 est impossible ici (comme au paquet 230).

CANDIDATE (une seule, fixée avant tout essai) : pour chaque classe d'expérience du moins connu des deux (moins de 30,
30–99, 100–299, 300 matchs et plus), la pente de l'Elo de production seul sur le rejeu Challenger comme en production
(etude_depart_itf.matchs, elo.de_production, départs par niveau, mis à jour après chaque match ; sans abandon ni
compétition par équipes), rétrécie vers la pente du circuit (poids n / (n + 300), comme la v3). Le rejeu n'a pas les
signaux : la même pente est écrite pour les trois ampleurs (CH|i|0, CH|i|1, CH|i|2). ATP et WTA ne changent pas.
En place, pour comparer : la pente de la note v3 de la classe (moyenne de ses cases pondérée par leurs matchs).

RÈGLE ÉCRITE LE 25/11/2026, AVANT TOUT ESSAI :
  1. apprise du 01/01/2025 au 30/09/2025 ; jugée UNE SEULE FOIS du 01/10/2025 au 31/05/2026 ;
  2. mesure : la log loss de σ(a · logit p) — la pente qui décrit le mieux la réalité de la classe gagne ; c'est
     ce que la note affirme (« nos % s'écartent de la réalité de tant ») ;
  3. RETENUE seulement si, sur la période jugée :
       a. au moins 1 000 matchs Challenger jugés,
       b. gain ≥ 0,001 par match sur les pentes de la note en place,
       c. même sens sur les deux périodes : apprise sur la période jugée et jugée sur la période d'apprentissage,
          elle bat aussi la note en place (gain > 0) ;
  4. publiés sans décider : erreur type du gain ; la promesse de la note (le tiers des notes les plus hautes a une
     pente plus proche de 1 et une erreur d'étalonnage plus petite que le tiers le plus bas), en place et candidate ;
     sur nos matchs Challenger en direct notés v3 : les niveaux en place et ceux qu'aurait donnés la candidate (mêmes
     critères « fragile », même plafond), la pente de chaque niveau, et les matchs qui entreraient dans ou sortiraient
     du niveau « correct » (celui que corrige la pente 1,142 du paquet 270) ;
  5. RIEN N'ENTRE EN PRODUCTION par ce paquet. Retenue : proposée à Lucas pour un paquet suivant, avec la question de
     la correction « correct » (gardée sur l'ancienne note, ou rejugée). Non retenue : la note en place reste.
Limite : l'Elo seul, sans la simulation ni les signaux (le % publié en a, la note v3 en place aussi les avait sur
l'archive) ; nos matchs en direct (moins de 1 000) ne servent qu'à regarder, jamais à décider.

Rapport public : simulateur/rapport_note_v3_challenger.json — comptes et pentes seulement, aucun nom de joueur.
Usage : python simulateur/etude_note_v3_challenger.py /tmp/sackmann .
        python simulateur/etude_note_v3_challenger.py --journal-depuis-rapport simulateur/rapport_note_v3_challenger.json
"""
import datetime as dt
import json
import math
import os
import random
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
import etude_etalonnage_cases as EC  # noqa: E402  (rejeu comme en production, pente, decrire, journal)

PAQUET = 449
DEBUT, COUPURE, FIN = dt.date(2025, 1, 1), dt.date(2025, 10, 1), dt.date(2026, 6, 1)
MIN_JUGES, MARGE, RETRECI = 1000, 0.001, 300.0
SEUILS_V3 = {'prudent': 78, 'correct': 85, 'solide': 93}       # ceux de simulateur/fiabilite.py
NIVEAUX = ('fragile', 'prudent', 'correct', 'solide')
SORTIE = os.path.join(ICI, 'rapport_note_v3_challenger.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_449.json')


def note(a):
    return round(100 * min(a, 1 / a)) if a and a > 0 else 0


def niveau(n):
    s = SEUILS_V3
    return 'fragile' if n < s['prudent'] else 'prudent' if n < s['correct'] else 'correct' if n < s['solide'] else 'solide'


def ll(a, z):
    return EC.ll(a * z)


# ------------------------------------------------------------------ pentes
def apprendre(R):
    """R : [(classe, z)] → {classe: pente rétrécie vers celle du circuit}, '_circuit'."""
    if not R:
        return {'_circuit': 1.0}
    a_c, _ = EC.pente([z for _, z in R])
    out = {'_circuit': round(a_c, 4)}
    for i in range(4):
        v = [z for k, z in R if k == i]
        if v:
            w = len(v) / (len(v) + RETRECI)
            out[i] = round(w * EC.pente(v)[0] + (1 - w) * a_c, 4)
    return out


def pente_de(M, i):
    return M.get(i, M.get('_circuit', 1.0))


def en_place(racine):
    """Pentes de la note v3 en place pour le Challenger, par classe d'expérience (moyenne pondérée de ses cases)."""
    with open(os.path.join(racine, 'simulateur', 'rapport_fiabilite_v3.json'), encoding='utf-8') as f:
        mod = json.load(f)['modele']
    out = {'_circuit': mod['_circuits']['CH']}
    for i in range(4):
        ks = [k for k in mod if k.startswith(f'CH|{i}|')]
        w = sum(mod[k]['matchs'] for k in ks)
        if w:
            out[i] = round(sum(mod[k]['pente'] * mod[k]['matchs'] for k in ks) / w, 4)
    return out, mod


def comparer(R, M_old, M_new):
    n = len(R)
    if not n:
        return {'matchs': 0}
    d = [ll(pente_de(M_old, i), z) - ll(pente_de(M_new, i), z) for i, z in R]
    g = sum(d) / n
    et = math.sqrt(sum((v - g) ** 2 for v in d) / max(n - 1, 1)) / math.sqrt(n)
    return {'matchs': n, 'gain': round(g, 5), 'erreur_type': round(et, 5), 'erreurs_types': round(g / et, 2) if et else None,
            'log_loss_en_place': round(sum(ll(pente_de(M_old, i), z) for i, z in R) / n, 5),
            'log_loss_candidate': round(sum(ll(pente_de(M_new, i), z) for i, z in R) / n, 5)}


def promesse(R, M):
    """Le tiers aux notes les plus hautes a-t-il une pente plus proche de 1 et une erreur d'étalonnage plus petite que le
    tiers le plus bas ? (définition de la note v3 ; match vu d'un côté tiré au hasard fixe)."""
    rnd = random.Random(20261125)
    X = sorted(((note(pente_de(M, i)), z, rnd.random() < 0.5) for i, z in R), key=lambda x: x[0])
    k = len(X) // 3
    out = {}
    for nom, g in (('bas', X[:k]), ('haut', X[2 * k:])):
        if not g:
            return {'tient': None}
        a, _ = EC.pente([z for _, z, _ in g])
        P = [(EC._sg(z), 1) if s else (1 - EC._sg(z), 0) for _, z, s in g]
        tot, n = 0.0, 0
        for lo in range(0, 100, 10):
            b = [(p, y) for p, y in P if lo <= 100 * p < lo + 10]
            if b:
                tot += abs(sum(y for _, y in b) - sum(p for p, _ in b))
                n += len(b)
        out[nom] = {'matchs': len(g), 'notes': [g[0][0], g[-1][0]], 'pente': round(a, 3), 'distance_a_1': round(abs(1 - a), 3),
                    'erreur_etalonnage_pts': round(100 * tot / max(n, 1), 2)}
    out['tient'] = bool(out['haut']['distance_a_1'] < out['bas']['distance_a_1']
                        and out['haut']['erreur_etalonnage_pts'] < out['bas']['erreur_etalonnage_pts'])
    out['remarque'] = ('notes toutes égales : pas de tiers à comparer' if out['bas']['notes'] == out['haut']['notes']
                       else None)
    return out


def juger(rows, M_old):
    A = [(EC.classe_experience(n), z) for c, d, n, z in rows if c == 'CH' and DEBUT <= d < COUPURE]
    J = [(EC.classe_experience(n), z) for c, d, n, z in rows if c == 'CH' and COUPURE <= d < FIN]
    M = apprendre(A)
    M_inv = apprendre(J)
    juge, inverse = comparer(J, M_old, M), comparer(A, M_old, M_inv)
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append('moins de 1 000 matchs jugés')
    if juge.get('gain', -1.0) < MARGE:
        raisons.append('gain sous 0,001')
    if not inverse.get('gain', -1.0) > 0:
        raisons.append('pas le même sens sur les deux périodes')
    classes = {}
    for i in range(4):
        Ji = [z for k, z in J if k == i]
        classes[str(i)] = {'classe': EC.NOM_CLASSE[i], 'matchs_appris': sum(1 for k, _ in A if k == i), 'matchs_juges': len(Ji),
                           'pente_reelle_jugee': EC.decrire(Ji).get('pente'),
                           'en_place': {'pente': pente_de(M_old, i), 'note': note(pente_de(M_old, i)),
                                        'niveau': niveau(note(pente_de(M_old, i)))},
                           'candidate': {'pente': pente_de(M, i), 'note': note(pente_de(M, i)),
                                         'niveau': niveau(note(pente_de(M, i)))},
                           'reapprise_sur_la_periode_jugee': pente_de(M_inv, i)}
    return {'pentes_candidates': {str(k): v for k, v in M.items()}, 'par_classe': classes,
            'periode_jugee': juge, 'sens_inverse': inverse,
            'promesse_en_place': promesse(J, M_old), 'promesse_candidate': promesse(J, M),
            'retenue': not raisons, 'raisons': raisons}


def modele_candidat(mod, M):
    """Le modèle v3 complet, avec les cases Challenger remplacées (mêmes pentes pour les trois ampleurs)."""
    out = {k: v for k, v in mod.items() if not k.startswith('CH|')}
    for i in range(4):
        for a in range(3):
            out[f'CH|{i}|{a}'] = {'pente': pente_de(M, i), 'matchs': None}
    out['_circuits'] = dict(mod['_circuits'], CH=M['_circuit'])
    return out


# ------------------------------------------------------------------ nos matchs en direct (regarder, jamais décider)
def direct(racine, M_old_mod, M_new):
    with open(os.path.join(racine, 'Tennis_Edge_Lab', 'live', 'pronostics_resultats.json'), encoding='utf-8') as f:
        doc = json.load(f)
    L = []
    for m in doc.get('matchs') or []:
        fi, reel = m.get('fiabilite') or {}, m.get('reel') or {}
        mj = [x for x in (m.get('matchs_joues') or []) if x is not None]
        if (m.get('circuit') != 'CH' or fi.get('version_fiabilite') != 'pente_v3' or fi.get('note_v3') is None
                or m.get('p_affiche') is None or reel.get('gagnant') not in ('home', 'away') or reel.get('interrompu')
                or len(mj) != 2):
            continue
        i = EC.classe_experience(min(mj))
        nv = note(pente_de(M_new, i))
        if fi.get('fragile_criteres'):
            nv = min(nv, SEUILS_V3['prudent'] - 1)
        z = EC._lg(m['p_affiche'])
        L.append({'z': z if reel['gagnant'] == 'home' else -z, 'avant': fi.get('niveau'), 'apres': niveau(nv)})
    out = {'matchs': len(L), 'niveaux': {}}
    for nom in NIVEAUX:
        a = [r['z'] for r in L if r['avant'] == nom]
        b = [r['z'] for r in L if r['apres'] == nom]
        out['niveaux'][nom] = {'en_place': {k: v for k, v in EC.decrire(a).items() if k != 'par_tranche'},
                               'candidate': {k: v for k, v in EC.decrire(b).items() if k != 'par_tranche'}}
    out['changent_de_niveau'] = sum(r['avant'] != r['apres'] for r in L)
    out['correct_entrent'] = sum(r['avant'] != 'correct' and r['apres'] == 'correct' for r in L)
    out['correct_sortent'] = sum(r['avant'] == 'correct' and r['apres'] != 'correct' for r in L)
    out['passages'] = {}
    for r in L:
        k = f"{r['avant']} → {r['apres']}"
        out['passages'][k] = out['passages'].get(k, 0) + 1
    return out


# ------------------------------------------------------------------ journal
def fr(v):
    return str(v).replace('.', ',')


def entree_journal(doc, gabarit):
    j = doc['jugement']
    pj = j['periode_jugee']
    cl = ', '.join(f"{v['classe']} {fr(v['en_place']['pente'])} → {fr(v['candidate']['pente'])} "
                   f"({v['en_place']['niveau']} → {v['candidate']['niveau']})" for v in j['par_classe'].values())
    fin = (" RETENUE : proposée à Lucas pour un paquet suivant (et la question de la correction « correct » du paquet 270) ; "
           "rien n'est changé par ce paquet." if j['retenue'] else
           f" NON RETENUE ({', '.join(j['raisons'])}) : la note en place reste.")
    res = (f" RÉSULTAT : jugée sur {pj.get('matchs', 0)} matchs Challenger (01/10/2025 → 31/05/2026), gain "
           f"{fr(pj.get('gain'))} ± {fr(pj.get('erreur_type'))} ; sens inverse {fr(j['sens_inverse'].get('gain'))} ; pentes par "
           f"classe (en place → candidate) : {cl}.")
    return {'date': gabarit['date'], 'statut': gabarit['statut'], 'paquet': gabarit['paquet'],
            'quoi': gabarit['quoi_debut'] + res + fin + ' Le % de victoire ne change pas.', 'garde_fou': gabarit['garde_fou']}


def main(argv):
    if len(argv) > 2 and argv[1] == '--journal-depuis-rapport':
        with open(argv[2], encoding='utf-8') as f:
            EC.ajouter_au_journal(JOURNAL, json.load(f)['entree_journal'])
        print('journal : entrée du paquet', PAQUET, 'ajoutée')
        return 0
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows, n_itf = EC.rejeu(archive, racine)
    M_old, mod = en_place(racine)
    jug = juger(rows, M_old)
    M_new = {('_circuit' if k == '_circuit' else int(k)): v for k, v in jug['pentes_candidates'].items()}
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': PAQUET,
           'regle': ("Challenger seul. Pente par classe d'expérience de l'Elo de production seul, rejeu comme en production "
                     "(ITF hommes compris), apprise du 01/01/2025 au 30/09/2025, jugée une fois du 01/10/2025 au 31/05/2026 "
                     "contre la note v3 en place (log loss de σ(a · logit p)). Retenue si ≥ 1 000 matchs, gain ≥ 0,001 et "
                     "même sens sur les deux périodes. Rien en production par ce paquet."),
           'itf_hommes_dans_le_rejeu': n_itf, 'pentes_en_place': {str(k): v for k, v in M_old.items()},
           'jugement': jug, 'direct_challenger_note_v3': direct(racine, mod, M_new),
           'modele_candidat': modele_candidat(mod, M_new) if jug['retenue'] else None, 'en_production': False}
    with open(GABARIT_JOURNAL, encoding='utf-8') as f:
        doc['entree_journal'] = entree_journal(doc, json.load(f))
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    EC.ajouter_au_journal(JOURNAL, doc['entree_journal'])
    print('jugée :', jug['periode_jugee'])
    print('sens inverse :', jug['sens_inverse'])
    for v in jug['par_classe'].values():
        print('  ', v)
    print('promesse en place :', jug['promesse_en_place'])
    print('promesse candidate :', jug['promesse_candidate'])
    print('retenue :', jug['retenue'], jug['raisons'])
    dr = doc['direct_challenger_note_v3']
    print('direct :', dr['matchs'], 'matchs ; changent de niveau :', dr['changent_de_niveau'], dr['passages'])
    for nom, v in dr['niveaux'].items():
        print('  ', nom, 'en place', v['en_place'].get('matchs'), v['en_place'].get('pente'), '| candidate',
              v['candidate'].get('matchs'), v['candidate'].get('pente'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
