#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etude_irregularite.py — LES JOUEURS IRRÉGULIERS RENDENT-ILS NOS % TROP SÛRS ? (26/11/2026, paquet 456)

POURQUOI. L'Elo traduit un écart de niveau en % de la même façon pour tous les joueurs. Or certains joueurs ont des
résultats plus « en dents de scie » que leur niveau ne le laisse attendre : ils battent des mieux classés ET perdent
contre des moins bien classés plus souvent que l'Elo ne le prévoit. Si c'est un trait stable, un match qui implique un
tel joueur devrait recevoir un % moins tranché (plus proche de 50 %), et l'outsider y gagner plus souvent qu'annoncé.
Ce qui existe déjà et que cette étude ne refait pas : la « fiabilité du joueur » (paquets 438 et 452) est calculée sur
nos seuls matchs publiés (20 derniers, depuis octobre 2026) et ne sert qu'à la note de fiabilité, jamais au % ; les
bilans au set décisif et au tie-break (paquets 192, 193) mesurent une « habitude » de gagner, pas l'irrégularité ; le
balayage du paquet 236 cherchait des pentes par case (niveau, surface, tour, expérience), pas par joueur. Ici la
question est posée sur l'archive, avec l'Elo de production, circuit par circuit.

L'INDICE, connu avant chaque match (aucune information du match lui-même) : pour chaque joueur, sur ses 40 derniers
matchs, la somme des (résultat − % Elo annoncé pour lui)² rapportée à la somme attendue Σ p(1 − p), rétrécie vers 1
par un a priori équivalent à 15 matchs :
    I = (Σ (y − p)² + 15 · v̄) / (Σ p(1 − p) + 15 · v̄),   v̄ = moyenne de p(1 − p) de ses matchs (0,22 sans match)
I > 1 : plus de surprises que prévu (irrégulier) ; I < 1 : plus régulier que prévu. Indice du match :
    x = moyenne des (I − 1) des deux joueurs, bornée à [−0,5 ; 1].
Correction étudiée : le logit du % devient a(x) · logit p avec a(x) = exp(β · x) ; β < 0 rapproche de 50 % les
matchs d'irréguliers. Mis à jour APRÈS chaque match (le % de ce match est lu avant).

REJEU. Comme en production (etude_depart_itf.matchs : archive depuis 2012 + résultats ITF hommes du dépôt ;
elo.de_production, départs par niveau, Elo mis à jour après chaque match ; sans abandon ni compétition par équipes pour
le jugement). Base : l'Elo seul, sans les signaux ni la simulation.

RÈGLE ÉCRITE LE 26/11/2026, AVANT TOUT ESSAI, circuit par circuit (ATP, WTA, Challenger jugés à part) :
  R1. β appris sur 2018–2022, jugé UNE SEULE FOIS sur 2023 → mai 2026 (fin de l'archive).
  R2. Retenu sur un circuit seulement si, sur au moins 1 000 matchs jugés, le gain de log loss par match contre l'Elo
      seul atteint 0,001 ET au moins 2 erreurs types, ET si le β réappris sur la période jugée a le même signe que le
      β appris (même sens sur les deux périodes).
  R3. Challenger : l'archive 2018–2022 n'a pas les résultats ITF hommes (leçon du paquet 319). Le Challenger n'est
      retenu que s'il passe AUSSI le contrôle « comme en production » : β appris du 01/01 au 30/09/2025, jugé une fois
      du 01/10/2025 au 31/05/2026, mêmes seuils (≥ 1 000 matchs, ≥ 0,001, ≥ 2 erreurs types, même signe).
  Publiés sans décider : le Brier avant / après, le détail par quintile de l'indice (favori annoncé contre réel), et
  l'outsider dans le quintile le plus irrégulier (« là où l'outsider peut gagner »).
  Rien n'entre en production par ce paquet : un circuit retenu est proposé à Lucas, avec la règle de retrait cumulée
  (300 matchs concernés, 2 erreurs types).
Limite : l'Elo seul ; le % publié a en plus la simulation et les signaux de circuit.

Rapport public : simulateur/rapport_irregularite.json — comptes, pentes et moyennes seulement, aucun nom de joueur.
Usage : python simulateur/etude_irregularite.py /tmp/sackmann .
        python simulateur/etude_irregularite.py --journal-depuis-rapport simulateur/rapport_irregularite.json
"""
import datetime as dt
import json
import math
import os
import sys
from collections import deque

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

PAQUET = 456
CIRCUITS = ('ATP', 'WTA', 'CH')
NOM_CIRCUIT = {'ATP': 'ATP', 'WTA': 'WTA', 'CH': 'Challenger'}
FENETRE, A_PRIORI, V_DEFAUT = 40, 15.0, 0.22
X_MIN, X_MAX = -0.5, 1.0
PERIODES_ARCHIVE = (('apprentissage', dt.date(2018, 1, 1), dt.date(2023, 1, 1)),
                    ('jugement', dt.date(2023, 1, 1), dt.date(2026, 6, 1)))
PERIODES_PROD = (('apprentissage', dt.date(2025, 1, 1), dt.date(2025, 10, 1)),
                 ('jugement', dt.date(2025, 10, 1), dt.date(2026, 6, 1)))
MIN_JUGES, MARGE, ERREURS_TYPES = 1000, 0.001, 2.0
BETA_MAX = 5.0                     # borne de sécurité : a(x) reste entre exp(−5x) et exp(5x)
SORTIE = os.path.join(ICI, 'rapport_irregularite.json')
JOURNAL = os.path.join(ICI, 'journal_changements.json')
GABARIT_JOURNAL = os.path.join(ICI, 'journal_ajouts', 'paquet_456.json')


# ------------------------------------------------------------------ mesures (z = logit du % donné au vainqueur)
def _sg(z):
    return 1 / (1 + math.exp(-max(min(z, 30), -30)))


def _lg(p):
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def ll(z):
    return -math.log(max(_sg(z), 1e-12))


def brier(z):
    return (1 - _sg(z)) ** 2


# ------------------------------------------------------------------ l'indice d'irrégularité, joueur par joueur
class Irregularite:
    """Historique glissant (40 matchs) de (y − p)² et p(1 − p) par joueur ; indice lu AVANT la mise à jour."""

    def __init__(self, fenetre=FENETRE, a_priori=A_PRIORI):
        self.fenetre, self.k = fenetre, a_priori
        self.h = {}

    def indice(self, j):
        H = self.h.get(j)
        if not H:
            return 1.0
        s_obs = sum(o for o, _ in H)
        s_att = sum(a for _, a in H)
        v = s_att / len(H) if s_att > 0 else V_DEFAUT
        return (s_obs + self.k * v) / (s_att + self.k * v)

    def x_match(self, a, b):
        x = (self.indice(a) - 1 + self.indice(b) - 1) / 2
        return max(min(x, X_MAX), X_MIN)

    def maj(self, j, p, y):
        """p : % annoncé pour j avant le match ; y : 1 s'il a gagné."""
        H = self.h.setdefault(j, deque(maxlen=self.fenetre))
        H.append(((y - p) ** 2, p * (1 - p)))


# ------------------------------------------------------------------ apprentissage et jugement
def apprendre_beta(R, iterations=60):
    """β tel que le vainqueur ~ σ(exp(β x) · z) — Newton à un paramètre. R : [(z, x)]."""
    b = 0.0
    for _ in range(iterations):
        g = h = 0.0
        for z, x in R:
            a = math.exp(b * x)
            u = a * z
            q = _sg(u)
            du = u * x                                 # d(u)/dβ
            g += (q - 1) * du
            h += q * (1 - q) * du * du + (q - 1) * u * x * x
        if h <= 1e-12:
            break
        pas = max(min(g / h, 1.0), -1.0)
        b = max(min(b - pas, BETA_MAX), -BETA_MAX)
        if abs(pas) < 1e-9:
            break
    return b


def gain(R, b):
    """Gain moyen de log loss (Elo seul − corrigé), son erreur type, et le Brier avant / après."""
    d = [ll(z) - ll(math.exp(b * x) * z) for z, x in R]
    n = len(d)
    if not n:
        return {'matchs': 0}
    g = sum(d) / n
    et = math.sqrt(sum((v - g) ** 2 for v in d) / max(n - 1, 1)) / math.sqrt(n)
    return {'matchs': n, 'gain': round(g, 5), 'erreur_type': round(et, 5),
            'brier_avant': round(sum(brier(z) for z, _ in R) / n, 5),
            'brier_apres': round(sum(brier(math.exp(b * x) * z) for z, x in R) / n, 5)}


def quintiles(R):
    """Par quintile de l'indice du match : % annoncé au favori contre % réel, et l'outsider dans le quintile haut."""
    if len(R) < 50:
        return {}
    S = sorted(R, key=lambda r: r[1])
    out = {}
    for q in range(5):
        G = S[q * len(S) // 5:(q + 1) * len(S) // 5]
        fav = [max(_sg(z), 1 - _sg(z)) for z, _ in G]
        juste = [1.0 if z > 0 else 0.5 if z == 0 else 0.0 for z, _ in G]
        out[f'Q{q + 1}'] = {'matchs': len(G), 'indice_moyen': round(sum(x for _, x in G) / len(G), 3),
                            'favori_annonce_pct': round(100 * sum(fav) / len(G), 1),
                            'favori_reel_pct': round(100 * sum(juste) / len(G), 1),
                            'outsider_annonce_pct': round(100 - 100 * sum(fav) / len(G), 1),
                            'outsider_reel_pct': round(100 - 100 * sum(juste) / len(G), 1)}
    return out


def juger_bloc(R_app, R_jug):
    b = apprendre_beta(R_app)
    b_re = apprendre_beta(R_jug) if R_jug else 0.0
    j = gain(R_jug, b)
    a = gain(R_app, b)
    passe = bool(j.get('matchs', 0) >= MIN_JUGES and j.get('gain', 0) >= MARGE
                 and j.get('gain', 0) >= ERREURS_TYPES * j.get('erreur_type', 1)
                 and b != 0 and b * b_re > 0)
    return {'beta_appris': round(b, 4), 'beta_reappris_sur_jugement': round(b_re, 4),
            'pente_a_indice_0_5': round(math.exp(b * 0.5), 3),
            'apprentissage': a, 'jugement': j, 'quintiles_jugement': quintiles(R_jug), 'passe': passe}


def decouper(rows, c, periodes):
    """rows : [(circuit, date, z, x)] → (apprentissage, jugement) pour ce circuit."""
    (_, a0, a1), (_, j0, j1) = periodes
    A = [(z, x) for cc, d, z, x in rows if cc == c and a0 <= d < a1]
    J = [(z, x) for cc, d, z, x in rows if cc == c and j0 <= d < j1]
    return A, J


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


# ------------------------------------------------------------------ rejeu comme en production
def rejeu(archive, racine):
    """[(circuit, date, z Elo du vainqueur, indice du match)] — ATP, WTA, Challenger, 2018 → mai 2026."""
    import backtest_pronostic as BP
    import elo as E
    import etude_depart_itf as ED
    M, n_itf = ED.matchs(archive, racine)
    el, bas = E.de_production(racine)
    irr = Irregularite()
    debut = PERIODES_ARCHIVE[0][1]
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
        if (c in CIRCUITS and debut <= m['date'] < PERIODES_ARCHIVE[1][2] and not m.get('abandon')
                and m.get('niveau') != 'D'):
            rows.append((c, m['date'], _lg(pg), irr.x_match(g, p)))
        if not m.get('abandon'):
            irr.maj(g, pg, 1)
            irr.maj(p, 1 - pg, 0)
        el.maj(g, p, s, m.get('niveau') == 'G', E.part_jeux(m['sets']) if m.get('complet') and m.get('sets') else None)
    return rows, n_itf


# ------------------------------------------------------------------ journal
def fr(v):
    return str(v).replace('.', ',')


def entree_journal(doc, gabarit):
    morceaux = []
    for c in CIRCUITS:
        b = doc['jugement'][c]
        a, j = b['archive'], b['archive']['jugement']
        t = (f"{NOM_CIRCUIT[c]} : β {fr(round(a['beta_appris'], 2))} (réappris {fr(round(a['beta_reappris_sur_jugement'], 2))}), "
             f"{j.get('matchs', 0)} matchs jugés, gain {fr(j.get('gain'))} ± {fr(j.get('erreur_type'))}, "
             f"Brier {fr(j.get('brier_avant'))} → {fr(j.get('brier_apres'))}")
        q5 = (a.get('quintiles_jugement') or {}).get('Q5')
        if q5:
            t += (f" ; joueurs les plus irréguliers : outsider {fr(q5['outsider_reel_pct'])} % réels pour "
                  f"{fr(q5['outsider_annonce_pct'])} % annoncés")
        if c == 'CH':
            p = b['comme_en_production']['jugement']
            t += (f" ; contrôle comme en production {p.get('matchs', 0)} matchs, gain {fr(p.get('gain'))} ± "
                  f"{fr(p.get('erreur_type'))}")
        t += ' — ' + ('RETENU' if b['retenu'] else 'non retenu')
        morceaux.append(t)
    res = ' RÉSULTAT : ' + ' ; '.join(morceaux) + '.'
    fin = (" Proposé à Lucas pour les circuits retenus ; rien n'est changé par ce paquet."
           if any(doc['jugement'][c]['retenu'] for c in CIRCUITS) else
           " Aucun circuit retenu : l'Elo traite déjà correctement les joueurs irréguliers ; la piste est close.")
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
    rows, n_itf = rejeu(archive, racine)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'paquet': PAQUET,
           'nature': "étude seule : rien n'entre dans l'algo",
           'indice': (f"irrégularité du joueur = Σ(y − p)² / Σ p(1 − p) sur ses {FENETRE} derniers matchs, rétrécie vers 1 "
                      f"(a priori {int(A_PRIORI)} matchs) ; indice du match = moyenne des (I − 1) des deux joueurs, "
                      f"bornée à [{X_MIN} ; {X_MAX}] ; correction : logit × exp(β · indice)"),
           'itf_hommes_dans_le_rejeu': n_itf, 'matchs_rejoues': len(rows),
           'jugement': juger(rows), 'en_production': False}
    with open(GABARIT_JOURNAL, encoding='utf-8') as f:
        doc['entree_journal'] = entree_journal(doc, json.load(f))
    with open(SORTIE, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    ajouter_au_journal(JOURNAL, doc['entree_journal'])
    print(json.dumps({c: {'retenu': v['retenu'], 'archive': {k: v['archive'][k] for k in
                                                             ('beta_appris', 'beta_reappris_sur_jugement', 'jugement')}}
                      for c, v in doc['jugement'].items()}, ensure_ascii=False, indent=1))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
