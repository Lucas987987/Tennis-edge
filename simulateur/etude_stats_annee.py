#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_stats_annee.py — LES STATISTIQUES DE L'ANNÉE AJOUTENT-ELLES QUELQUE CHOSE À L'ELO ? (27/11/2026, paquet 491)

POURQUOI. Le fournisseur de TennisApi donne, pour chaque joueur et chaque année, ses statistiques par surface (collecte
du paquet 482, historique/stats_annee/ ; affichées comme information descriptive depuis le paquet 487). Question de Lucas :
peuvent-elles améliorer le %, en particulier pour les joueurs peu documentés ? L'indicateur le plus direct est la part
de points gagnés au service. Un écart de service que l'Elo ne voit pas devrait se lire dans les résultats.

LIMITE DES DONNÉES (constat du 27/11, avant tout essai) : le fournisseur n'a ces statistiques qu'à partir de 2023
(2023 : 651 joueurs, partiel ; 2024 : 1 641 ; 2025 : 1 854 ; 2026 : 2 218 ; 2022 et avant : aucun). Le découpage
habituel (2018–2022 / 2023 → 2026) est impossible ; on utilise toujours les statistiques de l'ANNÉE PRÉCÉDENTE
(complètes et connues avant le match) :
  APPRENTISSAGE = matchs de 2025, profil tiré des statistiques 2024 ;
  JUGEMENT, UNE SEULE FOIS = matchs de 2026 jusqu'à la fin de l'archive (mai 2026), profil tiré des statistiques 2025.

L'INDICE, connu avant le match : x = (ps du vainqueur − ps du perdant) / 10, ps = % de points gagnés au service
l'année précédente. Correction étudiée : logit du % du vainqueur z → z + β · x (β > 0 : le meilleur serveur gagne plus
souvent que l'Elo ne le dit). Trois variantes fixées ici :
  V1 « service de l'année » : toutes surfaces, chaque joueur avec au moins 10 matchs dans ses statistiques ;
  V2 « service sur la surface » : sur la surface du match, chaque joueur avec au moins 5 matchs sur cette surface ;
  V3 « joueurs peu connus » : V1, seulement quand l'un des deux a moins de 40 matchs dans l'Elo avant ce match.

REJEU. Comme l'étude 456 : etude_depart_itf.matchs (archive depuis 2012 + résultats ITF hommes du dépôt),
elo.de_production, départs par niveau, Elo mis à jour après chaque match ; jugés : ATP, WTA, Challenger, sans abandon
ni compétition par équipes. Base : l'Elo seul, sans les signaux ni la simulation. Noms rapprochés par la même clé que
scripts/profils_saison.py ; un nom porté par deux joueurs dans les statistiques est écarté.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI, circuit par circuit et variante par variante :
  R1. β appris sur l'apprentissage, jugé UNE SEULE FOIS sur le jugement.
  R2. Retenu seulement si, sur au moins 1 000 matchs jugés, le gain de log loss par match contre l'Elo seul atteint
      0,001 ET au moins 2 erreurs types, ET si le β réappris sur le jugement a le même signe (même sens sur les deux
      périodes). Moins de 1 000 matchs jugés : « non jugeable », rien n'est conclu.
  Publiés sans décider : la couverture (part des matchs où les deux joueurs ont des statistiques), le Brier avant /
  après, et par quintile de x le favori annoncé contre réel.
  Rien n'entre en production par ce paquet : une variante retenue est proposée à Lucas, avec une règle de retrait.
"""
import datetime as dt
import gzip
import json
import math
import os
import re
import sys
import unicodedata

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

PAQUET = 491
CIRCUITS = ('ATP', 'WTA', 'CH')
NOM_CIRCUIT = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger'}
APPRENTISSAGE = (dt.date(2025, 1, 1), dt.date(2026, 1, 1), 2024)       # (début, fin exclue, année des statistiques)
JUGEMENT = (dt.date(2026, 1, 1), dt.date(2026, 6, 1), 2025)
MIN_MATCHS_TOUT, MIN_MATCHS_SURFACE, PEU_CONNU = 10, 5, 40
MIN_JUGES, MARGE, ERREURS_TYPES, BETA_MAX = 1000, 0.001, 2.0, 5.0
VARIANTES = ('V1_service_annee', 'V2_service_surface', 'V3_peu_connus')
DOSSIER_STATS = os.path.join('historique', 'stats_annee')
SORTIE = os.path.join(ICI, 'rapport_stats_annee.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_491.json')


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def _lg(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def ll(z):
    return -math.log(max(_sg(z), 1e-12))


def brier(z):
    return (1 - _sg(z)) ** 2


# ------------------------------------------------------------------ statistiques d'une année
def cle(nom):
    """Clé de nom, identique à scripts/profils_saison.cle (recopiée ici, 27/11 : les tests du simulateur tournent dans
    le workflow des pronostics sans le dossier scripts/)."""
    n = unicodedata.normalize('NFD', str(nom or '')).encode('ascii', 'ignore').decode().lower()
    return ' '.join(re.findall(r'[a-z]+', n))


def surface_site(g):
    g = str(g or '').lower()
    return 'Clay' if 'clay' in g else 'Hard' if 'hard' in g else 'Grass' if 'grass' in g else 'Carpet' if 'carpet' in g else None


def _service(L):
    m = sum(x.get('matches', 0) for x in L)
    pts = sum(x.get('firstServePointsTotal', 0) + x.get('secondServePointsTotal', 0) for x in L)
    gag = sum(x.get('firstServePointsScored', 0) + x.get('secondServePointsScored', 0) for x in L)
    return (m, 100.0 * gag / pts) if pts else (m, None)


def stats_annee(racine, an):
    """{clé du nom: {'tout': (matchs, ps), 'Clay': (…), …}} ; noms en double écartés."""
    p = os.path.join(racine, DOSSIER_STATS, f'{an}.jsonl.gz')
    out, vus = {}, {}
    try:
        with gzip.open(p, 'rt', encoding='utf-8') as f:
            lignes = [json.loads(l) for l in f if l.strip()]
    except OSError:
        return {}
    for r in lignes:
        k = cle(r.get('nom'))
        if not k:
            continue
        vus[k] = vus.get(k, 0) + 1
        S = r.get('stats') or []
        if not S:
            continue
        d = {'tout': _service(S)}
        par = {}
        for x in S:
            s = surface_site(x.get('groundType'))
            if s:
                par.setdefault(s, []).append(x)
        for s, L in par.items():
            d[s] = _service(L)
        out[k] = d
    return {k: v for k, v in out.items() if vus.get(k) == 1}


def indice(variante, sg, sp, surface, n_min):
    """x = (ps vainqueur − ps perdant) / 10 selon la variante, ou None si le match n'est pas concerné."""
    if not sg or not sp:
        return None
    if variante == 'V2_service_surface':
        a, b = sg.get(surface), sp.get(surface)
        if not a or not b or a[0] < MIN_MATCHS_SURFACE or b[0] < MIN_MATCHS_SURFACE or a[1] is None or b[1] is None:
            return None
        return (a[1] - b[1]) / 10.0
    a, b = sg.get('tout'), sp.get('tout')
    if not a or not b or a[0] < MIN_MATCHS_TOUT or b[0] < MIN_MATCHS_TOUT or a[1] is None or b[1] is None:
        return None
    if variante == 'V3_peu_connus' and n_min >= PEU_CONNU:
        return None
    return (a[1] - b[1]) / 10.0


# ------------------------------------------------------------------ apprentissage et jugement
def apprendre_beta(R, iterations=60):
    """β tel que le vainqueur ~ σ(z + β x) — Newton à un paramètre. R : [(z, x)]."""
    b = 0.0
    for _ in range(iterations):
        g = h = 0.0
        for z, x in R:
            q = _sg(z + b * x)
            g += (q - 1) * x
            h += q * (1 - q) * x * x
        if h <= 1e-12:
            break
        pas = max(min(g / h, 1.0), -1.0)
        b = max(min(b - pas, BETA_MAX), -BETA_MAX)
        if abs(pas) < 1e-9:
            break
    return b


def gain(R, b):
    d = [ll(z) - ll(z + b * x) for z, x in R]
    n = len(d)
    if not n:
        return {'matchs': 0}
    g = sum(d) / n
    et = math.sqrt(sum((v - g) ** 2 for v in d) / max(n - 1, 1)) / math.sqrt(n)
    return {'matchs': n, 'gain': round(g, 5), 'erreur_type': round(et, 5),
            'brier_avant': round(sum(brier(z) for z, _ in R) / n, 5),
            'brier_apres': round(sum(brier(z + b * x) for z, x in R) / n, 5)}


def quintiles(R):
    """Par quintile de x vu du FAVORI de l'Elo : % annoncé au favori contre % réel."""
    if len(R) < 50:
        return {}
    F = []
    for z, x in R:                                     # réorienter vers le favori de l'Elo
        F.append((abs(z), x if z >= 0 else -x, 1.0 if z > 0 else 0.5 if z == 0 else 0.0))
    S = sorted(F, key=lambda r: r[1])
    out = {}
    for q in range(5):
        G = S[q * len(S) // 5:(q + 1) * len(S) // 5]
        out[f'Q{q + 1}'] = {'matchs': len(G), 'ecart_service_moyen_pts': round(10 * sum(x for _, x, _ in G) / len(G), 2),
                            'favori_annonce_pct': round(100 * sum(_sg(z) for z, _, _ in G) / len(G), 1),
                            'favori_reel_pct': round(100 * sum(y for _, _, y in G) / len(G), 1)}
    return out


def juger_bloc(R_app, R_jug):
    b = apprendre_beta(R_app)
    b_re = apprendre_beta(R_jug) if R_jug else 0.0
    j = gain(R_jug, b)
    jugeable = j.get('matchs', 0) >= MIN_JUGES
    passe = bool(jugeable and j.get('gain', 0) >= MARGE and j.get('gain', 0) >= ERREURS_TYPES * j.get('erreur_type', 1)
                 and b != 0 and b * b_re > 0)
    return {'beta_appris': round(b, 4), 'beta_reappris_sur_jugement': round(b_re, 4),
            'apprentissage': gain(R_app, b), 'jugement': j, 'jugeable': jugeable,
            'quintiles_jugement': quintiles(R_jug), 'retenu': passe}


def juger(rows, stats):
    """rows : [(circuit, date, z, clé vainqueur, clé perdant, surface, n_min)] ; stats : {année: stats_annee}."""
    out = {}
    for c in CIRCUITS:
        bloc = {}
        tous = {'apprentissage': 0, 'jugement': 0}
        for v in VARIANTES:
            R = {'apprentissage': [], 'jugement': []}
            for cc, d, z, g, p, s, n in rows:
                if cc != c:
                    continue
                for nom, (d0, d1, an) in (('apprentissage', APPRENTISSAGE), ('jugement', JUGEMENT)):
                    if d0 <= d < d1:
                        if v == VARIANTES[0]:
                            tous[nom] += 1
                        S = stats.get(an) or {}
                        x = indice(v, S.get(g), S.get(p), s, n)
                        if x is not None:
                            R[nom].append((z, x))
            b = juger_bloc(R['apprentissage'], R['jugement'])
            b['couverture_jugement_pct'] = round(100 * len(R['jugement']) / tous['jugement'], 1) if tous['jugement'] else 0.0
            bloc[v] = b
        bloc['matchs_du_circuit'] = tous
        bloc['retenu'] = [v for v in VARIANTES if bloc[v]['retenu']]
        out[c] = bloc
    return out


# ------------------------------------------------------------------ rejeu comme en production
def rejeu(archive, racine):
    import backtest_pronostic as BP
    import elo as E
    import etude_depart_itf as ED
    M, n_itf = ED.matchs(archive, racine)
    el, bas = E.de_production(racine)
    nb = {}
    rows = []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        if bas and c in BP.BAS:
            el.presenter(g, E.depart_du_niveau(c, bas))
            el.presenter(p, E.depart_du_niveau(c, bas))
        pg = el.proba(g, p, s)
        if (c in CIRCUITS and APPRENTISSAGE[0] <= m['date'] < JUGEMENT[1] and not m.get('abandon')
                and m.get('niveau') != 'D'):
            rows.append((c, m['date'], _lg(pg), cle(m.get('nom_g')), cle(m.get('nom_p')), s,
                         min(nb.get(g, 0), nb.get(p, 0))))
        nb[g], nb[p] = nb.get(g, 0) + 1, nb.get(p, 0) + 1
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows, n_itf


# ------------------------------------------------------------------ journal
def fr(v):
    return str(v).replace('.', ',')


NOM_VARIANTE = {'V1_service_annee': 'service de l\'année', 'V2_service_surface': 'service sur la surface',
                'V3_peu_connus': 'joueurs peu connus'}


def entree_journal(doc, gabarit):
    morceaux = []
    for c in CIRCUITS:
        b = doc['jugement'][c]
        t = []
        for v in VARIANTES:
            x, j = b[v], b[v]['jugement']
            if not x['jugeable']:
                t.append(f"{NOM_VARIANTE[v]} non jugeable ({j.get('matchs', 0)} matchs)")
                continue
            t.append(f"{NOM_VARIANTE[v]} : β {fr(round(x['beta_appris'], 3))} (réappris {fr(round(x['beta_reappris_sur_jugement'], 3))}), "
                     f"{j['matchs']} matchs jugés, gain {fr(j.get('gain'))} ± {fr(j.get('erreur_type'))}"
                     + (' RETENU' if x['retenu'] else ''))
        morceaux.append(f"{NOM_CIRCUIT[c]} — " + ' ; '.join(t))
    res = ' RÉSULTAT : ' + ' | '.join(morceaux) + '.'
    fin = (" Proposé à Lucas pour les cas retenus ; rien n'est changé par ce paquet."
           if any(doc['jugement'][c]['retenu'] for c in CIRCUITS) else
           " Aucun cas retenu : l'écart de service de l'année ne dit rien que l'Elo ne sache déjà ; les statistiques restent descriptives.")
    return {'date': gabarit['date'], 'statut': gabarit['statut'], 'paquet': gabarit['paquet'],
            'quoi': gabarit['quoi_debut'] + res + fin + ' Le % de victoire ne change pas.',
            'garde_fou': gabarit['garde_fou']}


def ajouter_au_journal(chemin, entree):
    with open(chemin, encoding='utf-8') as f:
        doc = json.load(f)
    L = doc.setdefault('changements', [])
    for i, x in enumerate(L):
        if x.get('paquet') == entree['paquet']:
            L[i] = entree
            break
    else:
        L.append(entree)
    with open(chemin, 'w', encoding='utf-8') as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=1) + '\n')


def main(argv):
    if len(argv) > 2 and argv[1] == '--journal-depuis-rapport':
        with open(argv[2], encoding='utf-8') as f:
            ajouter_au_journal(JOURNAL, json.load(f)['entree_journal'])
        print('journal : entrée du paquet', PAQUET, 'ajoutée')
        return 0
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    stats = {an: stats_annee(racine, an) for an in (APPRENTISSAGE[2], JUGEMENT[2])}
    rows, n_itf = rejeu(archive, racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': PAQUET,
           'nature': "étude seule : rien n'entre dans l'algo",
           'indice': "x = (% de points gagnés au service du vainqueur − celui du perdant, l'année précédente) / 10 ; "
                     "correction : logit + β · x",
           'joueurs_avec_statistiques': {str(an): len(s) for an, s in stats.items()},
           'itf_hommes_dans_le_rejeu': n_itf, 'matchs_rejoues': len(rows),
           'jugement': juger(rows, stats), 'en_production': False}
    with open(GABARIT_JOURNAL, encoding='utf-8') as f:
        doc['entree_journal'] = entree_journal(doc, json.load(f))
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    ajouter_au_journal(JOURNAL, doc['entree_journal'])
    print(json.dumps({c: {v: (b[v]['retenu'], b[v]['beta_appris'], b[v]['beta_reappris_sur_jugement'], b[v]['jugement'],
                              b[v]['couverture_jugement_pct'])
                          for v in VARIANTES} for c, b in doc['jugement'].items()}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
