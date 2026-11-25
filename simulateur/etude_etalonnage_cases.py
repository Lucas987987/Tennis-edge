#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_etalonnage_cases.py — RAMENER CHAQUE NIVEAU DE FIABILITÉ À SON ATTENDU (25/11/2026, paquet 447)

QUESTION (Lucas : « peut-on trouver d'où viennent les différences pour que l'on soit à l'attendu ? »). En direct, du
22/10 au 25/11/2026, le niveau « fragile » fait PIRE que son attendu (log loss 0,588 contre 0,546 : favoris surcotés,
surtout à 70 % et plus quand les joueurs ont peu d'expérience) et « solide » / « correct » font MIEUX (gros favoris
sous-cotés). La note v3 MESURE déjà, case par case, de combien nos % s'écartent de la réalité (pente d'étalonnage a,
etude_fiabilite_v3.py) — mais le % affiché ne s'en sert pas. Ces chiffres en direct (250 à 570 matchs par niveau)
orientent la question ; ils ne décident de rien.

CORRECTION ÉTUDIÉE : z' = a_k · z, z = logit du % de BASE (Elo de production mis à jour après chaque match + les
signaux solides, comme etude_pente_niveau.py), k = CASE du match connue avant le match, la même que la note v3 :
circuit × expérience du moins connu des deux (moins de 30, 30–99, 100–299, 300 matchs et plus) × ampleur de la
correction des signaux (nulle, moins de 0,15, 0,15 et plus en logit). a_k appris par maximum de vraisemblance,
rétréci vers la pente du circuit (poids n / (n + 300)). a < 1 : la case est trop sûre d'elle (on rapproche de 50 %) ;
a > 1 : trop prudente (on écarte de 50 %). La case ne dépend pas du % : la correction garde l'ordre des favoris.
Référence publiée à côté, sans décider : une seule pente par circuit (déjà rejetée en direct le 04/11).

RÈGLE ÉCRITE LE 25/11/2026, AVANT TOUT RÉSULTAT, CIRCUIT PAR CIRCUIT (ATP, WTA, Challenger séparément) :
  1. les pentes sont apprises sur 2018–2022 SEULEMENT ;
  2. jugées UNE SEULE FOIS sur 2023 → juin 2026 (sans abandon, sans compétition par équipes ; ITF jamais jugée, ses
     résultats ne servent qu'à l'Elo) ;
  3. la correction est RETENUE sur un circuit seulement si, sur la période jugée :
       a. au moins 1 000 matchs jugés,
       b. gain de log loss ≥ 0,001 par match par rapport à la base,
       c. même sens sur les deux périodes : apprises sur 2023 → juin 2026 et jugées sur 2018–2022, les pentes font
          aussi gagner (gain > 0) ;
  4. publiés à côté, sans décider : erreur type du gain, Brier, gain par rapport à la pente unique du circuit, et
     pour chaque niveau de fiabilité (prudent < 78, correct < 85, solide < 93, fragile en dessous de 78… comme en
     production : note = 100 · min(a, 1/a)) l'écart du log loss à son attendu, avant et après correction ;
  5. rien n'entre en production par ce paquet : un circuit retenu est PROPOSÉ à Lucas pour un paquet suivant (suivi
     en fantôme, puis deux semaines gagnantes par circuit, règle de retrait cumulée habituelle) ; un circuit non
     retenu est écarté et la piste n'est pas rejouée sur ce circuit.
Limite connue : l'archive n'a pas la simulation point par point (le désaccord Elo / simulation, critère « fragile »
le plus fréquent en direct, n'y existe pas) ; la base est l'Elo de production + signaux, comme les autres études.
Les pronostics en direct ne servent qu'à confirmer, jamais à décider ; rien n'est jugé sur une centaine de matchs.

Rapport public : simulateur/rapport_etalonnage_cases.json — comptes et moyennes seulement, aucun nom de joueur.
L'entrée du journal (paquet 447) est écrite par cette étude avec ses résultats.

Usage : python simulateur/etude_etalonnage_cases.py /tmp/sackmann .
        python simulateur/etude_etalonnage_cases.py --journal-depuis-rapport simulateur/rapport_etalonnage_cases.json
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

DEBUT, COUPURE, FIN = dt.date(2018, 1, 1), dt.date(2023, 1, 1), dt.date(2026, 7, 1)
MIN_JUGES, MARGE = 1000, 0.001
CIRCUITS = ('ATP', 'WTA', 'CH')
NOM_CIRCUIT = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger'}
EXPERIENCE = (0, 30, 100, 300, 10 ** 9)
AMPLEUR = 0.15
RETRECI = 300.0
SEUILS = (('fragile', 78), ('prudent', 85), ('correct', 93), ('solide', 101))
SORTIE = os.path.join(ICI, 'rapport_etalonnage_cases.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_447.json')
PAQUET = 447


def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def ll(z):
    """Log loss d'une ligne vue du vainqueur (logit du % donné au vainqueur)."""
    return -math.log(max(_sg(z), 1e-12))


def brier(z):
    return (1 - _sg(z)) ** 2


def ll_attendu(z):
    """Log loss qu'on aurait en moyenne si le % était exactement la réalité (entropie du %)."""
    p = min(max(_sg(z), 1e-12), 1 - 1e-12)
    return -(p * math.log(p) + (1 - p) * math.log(1 - p))


def classe_experience(n):
    for i, (lo, hi) in enumerate(zip(EXPERIENCE[:-1], EXPERIENCE[1:])):
        if lo <= n < hi:
            return i
    return 0


def case(c, n_min, ampleur):
    a = abs(ampleur or 0.0)
    return f"{c}|{classe_experience(n_min)}|{0 if a < 1e-9 else 1 if a < AMPLEUR else 2}"


def pente(Z, iterations=50):
    """a tel que le vainqueur ~ σ(a·z) (lignes vues du vainqueur) : Newton à un paramètre."""
    a = 1.0
    for _ in range(iterations):
        g = h = 0.0
        for z in Z:
            q = _sg(a * z)
            g += (q - 1) * z
            h += q * (1 - q) * z * z
        if h <= 1e-12:
            break
        pas = g / h
        a -= max(min(pas, 2.0), -2.0)
        if abs(pas) < 1e-9:
            break
    return a


def apprendre(R):
    """{case: pente rétrécie vers celle du circuit, '_circuit': pente du circuit} — R : [(case, z)] d'un circuit."""
    if not R:
        return {'_circuit': 1.0}
    a_c = pente([z for _, z in R])
    par = {}
    for k, z in R:
        par.setdefault(k, []).append(z)
    out = {'_circuit': round(a_c, 4)}
    for k, v in par.items():
        w = len(v) / (len(v) + RETRECI)
        out[k] = round(w * pente(v) + (1 - w) * a_c, 4)
    return out


def pente_de(modele, k):
    return modele.get(k, modele.get('_circuit', 1.0))


def niveau(a):
    note = round(100 * min(a, 1 / a)) if a > 0 else 0
    for nom, s in SEUILS:
        if note < s:
            return nom
    return 'solide'


def bilan(Z, Zc):
    n = len(Z)
    if not n:
        return {'matchs': 0}
    d = [ll(a) - ll(b) for a, b in zip(Z, Zc)]
    g = sum(d) / n
    et = math.sqrt(sum((v - g) ** 2 for v in d) / max(n - 1, 1)) / math.sqrt(n)
    return {'matchs': n, 'gain': round(g, 5), 'erreur_type': round(et, 5), 'erreurs_types': round(g / et, 2) if et else None,
            'log_loss_base': round(sum(ll(a) for a in Z) / n, 5), 'log_loss': round(sum(ll(b) for b in Zc) / n, 5),
            'brier_base': round(sum(brier(a) for a in Z) / n, 5), 'brier': round(sum(brier(b) for b in Zc) / n, 5)}


def par_niveau(L):
    """L : [(niveau, z base, z corrigé)] → par niveau : écart du log loss à son attendu, avant et après."""
    out = {}
    for nom, _ in SEUILS:
        g = [(zb, zc) for n, zb, zc in L if n == nom]
        if not g:
            continue
        n = len(g)
        out[nom] = {'matchs': n,
                    'ecart_a_l_attendu_avant': round(sum(ll(zb) - ll_attendu(zb) for zb, _ in g) / n, 4),
                    'ecart_a_l_attendu_apres': round(sum(ll(zc) - ll_attendu(zc) for _, zc in g) / n, 4),
                    'favori_annonce_pct_avant': round(100 * sum(max(_sg(zb), 1 - _sg(zb)) for zb, _ in g) / n, 1),
                    'favori_annonce_pct_apres': round(100 * sum(max(_sg(zc), 1 - _sg(zc)) for _, zc in g) / n, 1),
                    'favori_reel_pct': round(100 * sum(1.0 if zb > 0 else 0.5 if zb == 0 else 0.0 for zb, _ in g) / n, 1)}
    return out


def juger_circuit(rows, c):
    A = [r for r in rows if r['c'] == c and r['d'] < COUPURE]
    J = [r for r in rows if r['c'] == c and r['d'] >= COUPURE]
    M = apprendre([(r['k'], r['zb']) for r in A])
    M_inverse = apprendre([(r['k'], r['zb']) for r in J])
    corr = lambda R, m: [pente_de(m, r['k']) * r['zb'] for r in R]  # noqa: E731
    juge = bilan([r['zb'] for r in J], corr(J, M))
    appr = bilan([r['zb'] for r in A], corr(A, M))
    inverse = bilan([r['zb'] for r in A], corr(A, M_inverse))
    unique = bilan([r['zb'] for r in J], [M['_circuit'] * r['zb'] for r in J])
    raisons = []
    if juge.get('matchs', 0) < MIN_JUGES:
        raisons.append('moins de 1 000 matchs jugés')
    if juge.get('gain', -1.0) < MARGE:
        raisons.append('gain sous 0,001')
    if not inverse.get('gain', -1.0) > 0:
        raisons.append('pas le même sens sur les deux périodes')
    niveaux = par_niveau([(niveau(pente_de(M, r['k'])), r['zb'], pente_de(M, r['k']) * r['zb']) for r in J])
    return {'circuit': NOM_CIRCUIT[c], 'pentes_2018_2022': M, 'pentes_reapprises_2023_juin_2026': M_inverse,
            '2018–2022': appr, '2023 → juin 2026': juge, 'sens_inverse_2018_2022': inverse,
            'reference_pente_unique_2023_juin_2026': unique,
            'gain_sur_la_pente_unique': round(juge.get('gain', 0) - unique.get('gain', 0), 5) if juge.get('matchs') else None,
            'par_niveau_2023_juin_2026': niveaux, 'retenu': not raisons, 'raisons': raisons}


def etudier(rows):
    return {c: juger_circuit(rows, c) for c in CIRCUITS}


REGLE = ("Circuit par circuit (ATP, WTA, Challenger). Correction z' = a_k·z, k = case de la note v3 (circuit × expérience du "
         "moins connu × ampleur des signaux), a_k appris sur 2018–2022 (rétréci vers la pente du circuit), jugé une fois sur "
         "2023 → juin 2026. Retenu si : ≥ 1 000 matchs jugés, gain de log loss ≥ 0,001, même sens sur les deux périodes "
         "(appris sur 2023 → juin 2026, gain > 0 sur 2018–2022). Erreur type, Brier, pente unique et écart à l'attendu par "
         "niveau de fiabilité publiés sans décider. Rien en production par ce paquet.")


def fr(v):
    return str(v).replace('.', ',')


def phrase_resultats(res):
    morceaux = []
    for c in CIRCUITS:
        v = res[c]
        j = v['2023 → juin 2026']
        if not j.get('matchs'):
            morceaux.append(f"{v['circuit']} : aucun match jugé")
            continue
        niv = v['par_niveau_2023_juin_2026']
        det = ', '.join(f"{n} {fr(x['ecart_a_l_attendu_avant'])} → {fr(x['ecart_a_l_attendu_apres'])}" for n, x in niv.items())
        morceaux.append(f"{v['circuit']} : {j['matchs']} matchs jugés, gain {fr(j['gain'])} ± {fr(j['erreur_type'])} "
                        f"(sur la pente unique {fr(v['gain_sur_la_pente_unique'])}), Brier {fr(j['brier_base'])} → {fr(j['brier'])}"
                        f" ; écart du log loss à l'attendu par niveau : {det} — "
                        f"{'RETENU' if v['retenu'] else 'non retenu (' + ', '.join(v['raisons']) + ')'}")
    return ' ; '.join(morceaux) + '.'


def entree_journal(res, gabarit):
    retenus = [res[c]['circuit'] for c in CIRCUITS if res[c]['retenu']]
    fin = (f" Retenu sur : {', '.join(retenus)}. Proposé à Lucas pour un paquet suivant (fantôme, puis deux semaines "
           f"gagnantes par circuit) ; rien n'est changé dans l'algo par ce paquet." if retenus else
           " Aucun circuit retenu : les cases de fiabilité ne corrigent pas le % sur l'archive ; la piste est close et ne "
           "sera pas rejouée.")
    return {'date': gabarit['date'], 'statut': gabarit['statut'], 'paquet': gabarit['paquet'],
            'quoi': gabarit['quoi_debut'] + ' RÉSULTAT : ' + phrase_resultats(res) + fin + ' Le % de victoire ne change pas.',
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


# ------------------------------------------------------------------ rejeu de l'archive (dépôt complet nécessaire)
def lignes(archive, racine):
    """Comme etude_pente_niveau.lignes, plus l'expérience des deux joueurs (matchs déjà joués) avant le match."""
    import donnees as DN
    import elo as E
    import etude_age as EA
    import etude_changement_surface as ECS
    import etude_retour_absence as ERA
    M = DN.charger(archive, 2012)
    etat = E.migrer_etat(json.load(open(os.path.join(racine, 'simulateur', 'elo_etat.json'), encoding='utf-8')))
    alias = dict(etat.get('alias') or {})
    k = lambda n: alias.get(E.cle(n), E.cle(n)) if n else None  # noqa: E731
    naiss = EA.naissances(archive, k)
    el, bas = E.de_production(racine)
    su, rt, rows = ECS.Suivi(), ERA.Retours(), []
    for m in M:
        g, p = k(m.get('nom_g')), k(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s, d = m['circuit'], m['surface'], m['date']
        if bas and c in ('CH', 'ITF'):
            el.presenter(g, bas)
            el.presenter(p, bas)
        if c in CIRCUITS and DEBUT <= d < FIN and not m.get('abandon') and m.get('niveau') != 'D':
            pr = min(max(el.proba(g, p, s), 1e-6), 1 - 1e-6)
            xa = ERA.variables(rt.etat(g, d), rt.etat(p, d))
            xg = EA.variables(EA.age_au(naiss, g, d), EA.age_au(naiss, p, d)) or (0.0, 0.0)
            rows.append({'c': c, 'd': d, 'z': math.log(pr / (1 - pr)),
                         'x5': (float(su.nouveau(g, d, s) - su.nouveau(p, d, s)), xa[0], xa[1], xg[0], xg[1]),
                         'n_min': min(el.matchs(g), el.matchs(p))})
        su.jouer(g, d, s)
        su.jouer(p, d, s)
        rt.jouer(g, d)
        rt.jouer(p, d)
        part = E.part_jeux(m['sets']) if m.get('complet') else None
        el.maj(g, p, s, m.get('niveau') == 'G', part)
    return rows


def poser_cases(rows):
    """Écrit r['k'] (case connue avant le match) ; r['zb'] doit déjà exister (base + signaux)."""
    for r in rows:
        r['k'] = case(r['c'], r['n_min'], r['zb'] - r['z'])


def main(argv):
    if len(argv) > 2 and argv[1] == '--journal-depuis-rapport':
        with open(argv[2], encoding='utf-8') as f:
            ajouter_au_journal(JOURNAL, json.load(f)['entree_journal'])
        print('journal : entrée du paquet', PAQUET, 'ajoutée')
        return 0
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    import etude_outsiders as EO
    rows = lignes(archive, racine)
    betas = EO.poser_la_base(rows)
    poser_cases(rows)
    res = etudier(rows)
    with open(GABARIT_JOURNAL, encoding='utf-8') as f:
        gabarit = json.load(f)
    entree = entree_journal(res, gabarit)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': PAQUET, 'regle': REGLE,
           'cases': "circuit | expérience du moins connu (0 : < 30, 1 : 30–99, 2 : 100–299, 3 : 300 +) | ampleur des signaux "
                    "(0 : nulle, 1 : < 0,15, 2 : ≥ 0,15)",
           'base': {'elo': 'de production, mis à jour après chaque match', 'betas_signaux_2018_2022': betas},
           'circuits': res, 'en_production': False, 'entree_journal': entree}
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    ajouter_au_journal(JOURNAL, entree)
    for c in CIRCUITS:
        v = res[c]
        print(v['circuit'], '| jugé', v['2023 → juin 2026'], '| sens inverse', v['sens_inverse_2018_2022'].get('gain'),
              '| sur pente unique', v['gain_sur_la_pente_unique'], '| retenu :', v['retenu'], v['raisons'])
        for n, x in v['par_niveau_2023_juin_2026'].items():
            print('   ', n, x)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
