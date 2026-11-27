#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_courbure.py — LA FORME DE LA COURBE D'ÉTALONNAGE : LES % EXTRÊMES ET LES % DU MILIEU SONT-ILS FAUX DANS DES SENS
DIFFÉRENTS ? (27/11/2026, paquet 497)

POURQUOI. Toutes les corrections du % étudiées jusqu'ici sont des PENTES : le logit du % est multiplié par un même
facteur a, partout sur la courbe (par circuit, par case de fiabilité, par tranche de documentation, par format, en
Grand Chelem : paquets 228, 231, 236, 317, 449, 465). Une pente rapproche (ou écarte) de 50 % tous les matchs dans la
même proportion. Elle ne peut pas corriger une courbe dont les deux bouts ont des défauts opposés : par exemple des
matchs à 55–65 % un peu trop timides ET des favoris à 85 % et plus un peu trop sûrs. Le paquet du 04/11 « pronostics
forts (> 70 %) » ne regardait que la queue, sur nos 5 571 pronostics figés, sans l'archive. Ici la question est posée
sur l'archive, avec l'Elo de production, circuit par circuit, et le témoin est la MEILLEURE PENTE apprise sur la même
période : le gain mesuré est ce que la courbure ajoute à une simple pente, pas un réapprentissage déguisé.

CORRECTION ÉTUDIÉE (z = logit du % Elo donné au vainqueur) :
    témoin   : z' = a · z
    candidat : z' = a · z + k · z · |z| / 2
k < 0 : les % extrêmes sont rapprochés de 50 % plus fort que ceux du milieu ; k > 0 : l'inverse. Le terme est impair
(symétrique pour les deux joueurs). |z| / 2 vaut 1 autour de 88 % : k est l'écart de pente entre un match à 50 % et un
match à 88 %.

REJEU. Comme en production (etude_depart_itf.matchs : archive depuis 2012 + résultats ITF hommes du dépôt ;
elo.de_production, départs par niveau, Elo mis à jour après chaque match ; sans abandon ni compétition par équipes
pour le jugement). Base : l'Elo seul, sans les signaux ni la simulation.

RÈGLE ÉCRITE LE 27/11/2026, AVANT TOUT ESSAI, circuit par circuit (ATP, WTA, Challenger jugés à part) :
  R1. a (témoin) et (a, k) (candidat) appris sur 2018–2022, jugés UNE SEULE FOIS sur 2023 → mai 2026.
  R2. Retenu sur un circuit seulement si, sur au moins 1 000 matchs jugés, le gain de log loss par match du candidat
      SUR LE TÉMOIN atteint 0,001 ET au moins 2 erreurs types, ET si k réappris sur la période jugée a le même signe
      que k appris (même sens sur les deux périodes), ET si le candidat gagne aussi sur le témoin en apprentissage.
  R3. Challenger : l'archive 2018–2022 n'a pas les résultats ITF hommes (leçon du paquet 319). Le Challenger n'est
      retenu que s'il passe AUSSI le contrôle « comme en production » : appris du 01/01 au 30/09/2025, jugé une fois
      du 01/10/2025 au 31/05/2026, mêmes seuils.
  Publiés sans décider : Brier avant / après, et pour chaque tranche de 5 points du % annoncé au favori (50–55 …
  95–100) sur la période jugée : % annoncé par l'Elo seul, par le témoin, par le candidat, et % réel (« les % annoncés
  se réalisent-ils, tranche par tranche ? ») ; une tranche n'est lue qu'à partir de 100 matchs.
  Rien n'entre en production par ce paquet : un circuit retenu est proposé à Lucas, avec la règle de retrait cumulée
  (300 matchs concernés, 2 erreurs types), et la courbure appliquée en dernier, jamais en plus d'une pente déjà en
  place sur le même match sans étude.
Limite : l'Elo seul ; le % publié a en plus la simulation et les signaux de circuit.

Rapport public : simulateur/rapport_courbure.json — comptes, coefficients et moyennes seulement, aucun nom de joueur.
Usage : python simulateur/etude_courbure.py /tmp/sackmann .
        python simulateur/etude_courbure.py --journal-depuis-rapport simulateur/rapport_courbure.json
"""
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

PAQUET = 497
CIRCUITS = ('ATP', 'WTA', 'CH')
NOM_CIRCUIT = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger'}
PERIODES_ARCHIVE = (('apprentissage', dt.date(2018, 1, 1), dt.date(2023, 1, 1)),
                    ('jugement', dt.date(2023, 1, 1), dt.date(2026, 6, 1)))
PERIODES_PROD = (('apprentissage', dt.date(2025, 1, 1), dt.date(2025, 10, 1)),
                 ('jugement', dt.date(2025, 10, 1), dt.date(2026, 6, 1)))
MIN_JUGES, MARGE, ERREURS_TYPES = 1000, 0.001, 2.0
MIN_TRANCHE = 100
A_BORNES, K_BORNE = (0.3, 3.0), 1.5
SORTIE = os.path.join(ICI, 'rapport_courbure.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_497.json')


# ------------------------------------------------------------------ mesures (z = logit du % donné au vainqueur)
def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30.0), -30.0)))


def _lg(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def ll(z):
    return -math.log(max(_sg(z), 1e-12))


def brier(z):
    return (1 - _sg(z)) ** 2


def corriger(z, a, k=0.0):
    return a * z + k * z * abs(z) / 2.0


# ------------------------------------------------------------------ apprentissage (Newton, 1 ou 2 paramètres)
def apprendre(Z, courbure=True, iterations=80):
    """(a, k) du maximum de vraisemblance de z' = a z + k z|z|/2, lignes vues du vainqueur. Sans courbure : k = 0."""
    a, k = 1.0, 0.0
    for _ in range(iterations):
        ga = gk = haa = hak = hkk = 0.0
        for z in Z:
            u = z * abs(z) / 2.0
            q = _sg(a * z + k * u)
            r, w = q - 1.0, q * (1.0 - q)
            ga += r * z
            haa += w * z * z
            if courbure:
                gk += r * u
                hak += w * z * u
                hkk += w * u * u
        if courbure:
            det = haa * hkk - hak * hak
            if det <= 1e-12:
                break
            da = (hkk * ga - hak * gk) / det
            dk = (haa * gk - hak * ga) / det
        else:
            if haa <= 1e-12:
                break
            da, dk = ga / haa, 0.0
        da, dk = max(min(da, 0.5), -0.5), max(min(dk, 0.5), -0.5)
        a = max(min(a - da, A_BORNES[1]), A_BORNES[0])
        k = max(min(k - dk, K_BORNE), -K_BORNE) if courbure else 0.0
        if abs(da) < 1e-9 and abs(dk) < 1e-9:
            break
    return a, k


def comparer(Z, temoin, candidat):
    """Gain moyen de log loss du candidat sur le témoin (positif = mieux), erreur type, Brier."""
    n = len(Z)
    if not n:
        return {'matchs': 0}
    d = [ll(corriger(z, temoin[0])) - ll(corriger(z, *candidat)) for z in Z]
    g = sum(d) / n
    et = math.sqrt(sum((v - g) ** 2 for v in d) / max(n - 1, 1)) / math.sqrt(n)
    return {'matchs': n, 'gain_sur_temoin': round(g, 5), 'erreur_type': round(et, 5),
            'log_loss_elo_seul': round(sum(ll(z) for z in Z) / n, 5),
            'log_loss_temoin': round(sum(ll(corriger(z, temoin[0])) for z in Z) / n, 5),
            'log_loss_candidat': round(sum(ll(corriger(z, *candidat)) for z in Z) / n, 5),
            'brier_elo_seul': round(sum(brier(z) for z in Z) / n, 5),
            'brier_temoin': round(sum(brier(corriger(z, temoin[0])) for z in Z) / n, 5),
            'brier_candidat': round(sum(brier(corriger(z, *candidat)) for z in Z) / n, 5)}


def tranches(Z, temoin, candidat):
    """Par tranche de 5 points du % Elo annoncé au favori : annoncé (Elo, témoin, candidat) contre réel."""
    cases = {}
    for z in Z:
        pf = max(_sg(z), 1 - _sg(z))
        b = min(int((pf * 100 - 50) // 5), 9)
        cases.setdefault(b, []).append(z)
    out = {}
    for b in sorted(cases):
        L = cases[b]
        n = len(L)
        nom = f'{50 + 5 * b}–{55 + 5 * b} %'
        if n < MIN_TRANCHE:
            out[nom] = {'matchs': n, 'lecture': 'trop peu de matchs'}
            continue

        # % donné au FAVORI DE L'ELO par chaque version, et % réel où ce favori a gagné
        def pour_fav(f):
            return round(100 * sum(_sg(f(z)) if z > 0 else 1 - _sg(f(z)) for z in L) / n, 1)
        out[nom] = {'matchs': n,
                    'annonce_elo_pct': pour_fav(lambda z: z),
                    'annonce_temoin_pct': pour_fav(lambda z: corriger(z, temoin[0])),
                    'annonce_candidat_pct': pour_fav(lambda z: corriger(z, *candidat)),
                    'reel_pct': round(100 * sum(1.0 for z in L if z > 0) / n, 1)}
    return out


def juger_bloc(Z_app, Z_jug):
    t = apprendre(Z_app, courbure=False)
    c = apprendre(Z_app, courbure=True)
    c_re = apprendre(Z_jug, courbure=True) if Z_jug else (1.0, 0.0)
    app, jug = comparer(Z_app, t, c), comparer(Z_jug, t, c)
    g = jug.get('gain_sur_temoin', 0)
    passe = bool(jug.get('matchs', 0) >= MIN_JUGES and g >= MARGE and g >= ERREURS_TYPES * jug.get('erreur_type', 1)
                 and c[1] != 0 and c[1] * c_re[1] > 0 and app.get('gain_sur_temoin', 0) > 0)
    raisons = []
    if jug.get('matchs', 0) < MIN_JUGES:
        raisons.append('moins de 1 000 matchs jugés')
    if g < MARGE:
        raisons.append('gain sur la pente seule sous 0,001')
    elif g < ERREURS_TYPES * jug.get('erreur_type', 1):
        raisons.append('gain à 2 erreurs types ou moins')
    if not (c[1] * c_re[1] > 0 and app.get('gain_sur_temoin', 0) > 0):
        raisons.append('pas le même sens sur les deux périodes')
    return {'temoin_pente_a': round(t[0], 4), 'candidat_a': round(c[0], 4), 'candidat_k': round(c[1], 4),
            'reappris_sur_jugement': {'a': round(c_re[0], 4), 'k': round(c_re[1], 4)},
            'apprentissage': app, 'jugement': jug, 'tranches_jugement': tranches(Z_jug, t, c),
            'passe': passe, 'raisons': [] if passe else raisons}


def decouper(rows, c, periodes):
    (_, a0, a1), (_, j0, j1) = periodes
    return ([z for cc, d, z in rows if cc == c and a0 <= d < a1],
            [z for cc, d, z in rows if cc == c and j0 <= d < j1])


def juger(rows):
    out = {}
    for c in CIRCUITS:
        bloc = {'archive': juger_bloc(*decouper(rows, c, PERIODES_ARCHIVE))}
        if c == 'CH':
            bloc['comme_en_production'] = juger_bloc(*decouper(rows, c, PERIODES_PROD))
            bloc['retenu'] = bool(bloc['archive']['passe'] and bloc['comme_en_production']['passe'])
        else:
            bloc['retenu'] = bloc['archive']['passe']
        out[c] = bloc
    return out


# ------------------------------------------------------------------ rejeu comme en production (dépôt complet)
def rejeu(archive, racine):
    """[(circuit, date, z Elo du vainqueur)] — ATP, WTA, Challenger, 2018 → mai 2026, Elo de production."""
    import backtest_pronostic as BP
    import elo as E
    import etude_depart_itf as ED
    M, n_itf = ED.matchs(archive, racine)
    el, bas = E.de_production(racine)
    debut, fin = PERIODES_ARCHIVE[0][1], PERIODES_ARCHIVE[1][2]
    rows = []
    for m in M:
        g, p = E.cle(m.get('nom_g')), E.cle(m.get('nom_p'))
        if not g or not p or g == p:
            continue
        c, s = m['circuit'], m.get('surface')
        if bas and c in BP.BAS:
            el.presenter(g, E.depart_du_niveau(c, bas))
            el.presenter(p, E.depart_du_niveau(c, bas))
        if (c in CIRCUITS and debut <= m['date'] < fin and not m.get('abandon') and m.get('niveau') != 'D'):
            rows.append((c, m['date'], _lg(el.proba(g, p, s))))
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows, n_itf


# ------------------------------------------------------------------ journal
def fr(v):
    return str(v).replace('.', ',')


def entree_journal(doc, gabarit):
    morceaux = []
    for c in CIRCUITS:
        b = doc['jugement'][c]
        a = b['archive']
        j = a['jugement']
        t = (f"{NOM_CIRCUIT[c]} : pente seule {fr(a['temoin_pente_a'])}, pente {fr(a['candidat_a'])} et courbure "
             f"{fr(a['candidat_k'])} (réapprise {fr(a['reappris_sur_jugement']['k'])}), {j.get('matchs', 0)} matchs jugés, "
             f"gain sur la pente seule {fr(j.get('gain_sur_temoin'))} ± {fr(j.get('erreur_type'))}, Brier "
             f"{fr(j.get('brier_temoin'))} → {fr(j.get('brier_candidat'))}")
        if c == 'CH':
            p = b['comme_en_production']['jugement']
            t += (f" ; contrôle comme en production {p.get('matchs', 0)} matchs, gain {fr(p.get('gain_sur_temoin'))} ± "
                  f"{fr(p.get('erreur_type'))}")
        t += ' — ' + ('RETENU' if b['retenu'] else 'non retenu' + (
            ' (' + ', '.join(a['raisons']) + ')' if a['raisons'] else ''))
        morceaux.append(t)
    fin = (" Proposé à Lucas pour les circuits retenus ; rien n'est changé par ce paquet."
           if any(doc['jugement'][c]['retenu'] for c in CIRCUITS) else
           " Aucun circuit retenu : une pente suffit, la forme de la courbe n'a pas de défaut à corriger ; la piste "
           "est close et ne sera pas rejouée.")
    return {'date': gabarit['date'], 'statut': gabarit['statut'], 'paquet': gabarit['paquet'],
            'quoi': gabarit['quoi_debut'] + ' RÉSULTAT : ' + ' ; '.join(morceaux) + '.' + fin
            + ' Le % de victoire ne change pas.',
            'garde_fou': gabarit['garde_fou']}


def ajouter_au_journal(chemin, entree):
    """Ajoute l'entrée, ou remplace celle du même paquet (mise en forme du fichier : indentation 1, UTF-8)."""
    with open(chemin, encoding='utf-8') as f:
        doc = json.load(f)
    L = doc.setdefault('changements', [])
    for i, x in enumerate(L):
        if x.get('paquet') == entree['paquet']:
            L[i] = entree
            break
    else:
        L.append(entree)
    tmp = chemin + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    os.replace(tmp, chemin)


def main(argv):
    if len(argv) > 2 and argv[1] == '--journal-depuis-rapport':
        with open(argv[2], encoding='utf-8') as f:
            ajouter_au_journal(JOURNAL, json.load(f)['entree_journal'])
        print('journal : entrée du paquet', PAQUET, 'ajoutée')
        return 0
    archive, racine = argv[1], (argv[2] if len(argv) > 2 else '.')
    rows, n_itf = rejeu(archive, racine)
    if not n_itf:
        print('::error::aucun résultat ITF hommes dans le rejeu : le Challenger ne serait pas comme en production')
        return 1
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': PAQUET,
           'nature': "étude seule : rien n'entre dans l'algo",
           'correction': "témoin z' = a·z ; candidat z' = a·z + k·z·|z|/2 (z = logit du % Elo)",
           'itf_hommes_dans_le_rejeu': n_itf, 'matchs_rejoues': len(rows),
           'jugement': juger(rows), 'en_production': False}
    with open(GABARIT_JOURNAL, encoding='utf-8') as f:
        doc['entree_journal'] = entree_journal(doc, json.load(f))
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    ajouter_au_journal(JOURNAL, doc['entree_journal'])
    for c, v in doc['jugement'].items():
        print(c, '| retenu :', v['retenu'], '| matchs jugés :', v['archive']['jugement'].get('matchs'))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
