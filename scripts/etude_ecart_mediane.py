#!/usr/bin/env python3
"""etude_ecart_mediane.py — la cote du match contre la cote habituelle du joueur.

    python scripts/etude_ecart_mediane.py

LECTURE SEULE. N'écrit aucun fichier, ne fait aucune requête réseau, ne
touche à aucune constante gelée. Relançable autant de fois qu'on veut, et
faite pour l'être : les seuils du bas sont gelés, l'échantillon grossit.

LA QUESTION
-----------
La fiche joueur affiche depuis le 08/10 un écart : la cote de ce match
contre la médiane des cotes que le marché donne d'habitude à ce joueur.

    Pinnacle 1,37   +17 pts
    Match plus facile que son ordinaire — coté 1,37 contre 1,78 en médiane.

C'est une information d'affichage. Est-ce aussi un FILTRE ? Autrement dit :
quand le marché cote un joueur bien plus court que son ordinaire, le
mouvement détecté sur lui vaut-il mieux que la moyenne de vos alertes ?

RÉPONSE : NON. Mesuré ci-dessous, trois cibles, aucune ne tient.

POURQUOI UNE RECONSTRUCTION POINT-IN-TIME
------------------------------------------
La médiane de players_profile.json agrège TOUTE la période, le match jugé
compris. S'en servir pour juger ce match, c'est le bug H14 à l'identique :
corrélation +0,593 en posthoc contre +0,213 en causal.

Ici la médiane est reconstruite au fil de l'eau. Deux raisons de pouvoir
le faire exactement, sans jointure ni tolérance :

  1. build_profiles.py ne fabrique la médiane QUE depuis moves_detail_hist :
     pin_open du côté steamé, son complément 1/(1-1/pin_open) du côté
     adversaire (lignes 199-235). Rien d'autre n'y entre. La même boucle
     reproduit donc la médiane au caractère près.

  2. On avance par JOUR. Avant de mesurer une alerte du jour J, on a
     injecté tout ce qui est antérieur à J et rien du jour même. La
     médiane lue ne peut pas contenir le match qu'on cherche à juger.

C'est la mécanique d'etude_forme_alertes.py, pour la même raison.

EN POINTS DE PROBABILITÉ
-------------------------
L'écart se mesure 1/cote - 1/médiane, pas en pourcentage de cote. Les
cotes sont multiplicatives : passer de 1,10 à 1,20 vaut 7,6 points de
probabilité, passer de 5,00 à 5,10 en vaut 0,4. Le même « +9 % de cote »
ne décrit pas le même événement.

Convention de signe : POSITIF = coté plus court que son ordinaire, donc
match plus facile pour lui. C'est la convention de la fiche.

CE QUE LE RÉSULTAT NE DIT PAS
------------------------------
Le résidu se mesure contre la clôture Pinnacle. Il dit si le marché se
trompe, pas si un opérateur accessible offre ce prix. Le P&L, lui, est au
prix d'entrée réel : c'est lui qui dit « jouable ».
"""

import csv
import math
import os
import random
import re
import statistics as st
import unicodedata
from collections import defaultdict

MOVES = os.environ.get('MOVES', 'moves_detail_hist.csv')

# Nombre minimal de cotes ANTÉRIEURES pour qu'une médiane existe. Même
# valeur que MIN_COTES de build_profiles.py : on juge la fiche telle
# qu'elle est publiée, pas une version plus exigeante.
MIN_COTES = int(os.environ.get('MIN_COTES', '4'))

# ── PRÉ-ENREGISTREMENT DU 09/10/2026 ───────────────────────────────────
#
# Les deux seuils ci-dessous sont GELÉS. Ils sortent de la recherche faite
# ce jour-là, donc ils ne prouvent rien sur les données qui les ont
# produits — ils ne valent que sur ce qui arrivera après.
#
# Pourquoi une cible et pas le 100 par défaut : à n=100, l'IC95 du résidu
# vaut +-9,0 points (écart-type 45,7). Un effet de 5 points ne peut pas en
# sortir, le verdict serait « non concluant » par construction. Les cibles
# sont calculées pour que l'effet OBSERVÉ, s'il est réel, exclue zéro.
ECART_SEUIL = float(os.environ.get('ECART_SEUIL', '5'))
ECART_N_CIBLE = int(os.environ.get('ECART_N_CIBLE', '320'))

MED_SEUIL = float(os.environ.get('MED_SEUIL', '2.16'))
MED_N_CIBLE = int(os.environ.get('MED_N_CIBLE', '240'))


def cle(nom):
    """Jeu de tokens trié — la clé de build_profiles.py, à l'identique."""
    if not nom:
        return ''
    s = unicodedata.normalize('NFKD', str(nom)).encode('ascii', 'ignore').decode()
    return ' '.join(sorted(t for t in re.split(r'[^A-Za-z]+', s.lower())
                           if len(t) > 1))


def num(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def ic(v):
    """Moyenne et IC95."""
    n = len(v)
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n) if n > 1 else 0.0
    return m, m - 1.96 * se, m + 1.96 * se


def corr(a, b):
    """Pearson, et le t de Student qui va avec."""
    n = len(a)
    if n < 10:
        return 0.0, 0.0
    ma, mb = st.mean(a), st.mean(b)
    sa, sb = st.stdev(a), st.stdev(b)
    if not sa or not sb:
        return 0.0, 0.0
    c = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (n - 1) / (sa * sb)
    return c, c * math.sqrt((n - 2) / max(1e-9, 1 - c * c))


def ligne(lib, v, cle_val='res'):
    """Une ligne de sous-groupe : résidu en points, ROI en pourcent."""
    if len(v) < 30:
        print(f'  {lib:38} n={len(v):4}   trop peu pour conclure')
        return
    r = [x['res'] for x in v]
    p = [x['pnl'] for x in v if x['pnl'] is not None]
    m, a, b = ic(r)
    pm, pa, pb = ic(p) if len(p) >= 30 else (0, 0, 0)
    verdict = 'EXCLUT ZÉRO' if (a > 0 or b < 0) else 'traverse zéro'
    print(f'  {lib:38} n={len(v):4}   res {100*m:+6.2f} '
          f'[{100*a:+6.2f};{100*b:+6.2f}]  ROI {100*pm:+6.1f}%  {verdict}')


def construire():
    """Les alertes dénouées, avec la médiane de chaque camp à leur date."""
    rows = [r for r in csv.DictReader(open(MOVES, encoding='utf-8'))
            if r.get('date')]
    rows.sort(key=lambda r: (r['date'], r.get('uid') or ''))

    hist = defaultdict(list)
    brut = []
    i = 0
    while i < len(rows):
        # Toutes les lignes du même jour sont mesurées AVANT d'être apprises.
        j = i
        while j < len(rows) and rows[j]['date'] == rows[i]['date']:
            j += 1
        for r in rows[i:j]:
            brut.append((r, list(hist[cle(r.get('steame'))]),
                         list(hist[cle(r.get('opp'))])))
        for r in rows[i:j]:
            po = num(r.get('pin_open'))
            if not po:
                continue
            ks, ko = cle(r.get('steame')), cle(r.get('opp'))
            if ks:
                hist[ks].append(po)
            if ko:
                # Le complément, comme build_profiles.py ligne 235.
                hist[ko].append(1 / max(0.02, 1 - 1 / po))
        i = j

    L = []
    sans_med = 0
    for r, hs, ho in brut:
        if r.get('steame_gagne') not in ('oui', 'non'):
            continue
        po, pc, en = (num(r.get('pin_open')), num(r.get('pin_close')),
                      num(r.get('entry')))
        if not (po and pc and pc > 1 and en):
            continue
        if len(hs) < MIN_COTES:
            sans_med += 1
            continue
        med = st.median(hs)
        y = 1.0 if r['steame_gagne'] == 'oui' else 0.0
        d = {
            'date': r['date'],
            'tour': r.get('tour') or '?',
            'med': med,
            'po': po,
            'n_hist': len(hs),
            # L'écart tel que la fiche l'affiche, sur le prix sharp.
            'ecart': (1 / po - 1 / med) * 100,
            # Le même sur le prix réellement pris, qui porte la marge du soft.
            'ecart_entry': (1 / en - 1 / med) * 100,
            'res': y - 1 / pc,
            'clv': num(r.get('clv_vs_pin_pct')),
            'pnl': num(r.get('pnl')),
        }
        if len(ho) >= MIN_COTES:
            med_o = st.median(ho)
            ci = 1 / max(0.02, 1 - 1 / po)       # cote implicite adversaire
            d['ecart_opp'] = (1 / ci - 1 / med_o) * 100
            d['diff'] = d['ecart'] - d['ecart_opp']
        L.append(d)
    return L, sans_med, len(rows)


def main():
    if not os.path.exists(MOVES):
        print(f'{MOVES} introuvable — lancer depuis la racine du dépôt.')
        return 1

    L, sans_med, n_rows = construire()
    print(f'{MOVES} : {n_rows} lignes')
    print(f'alertes dénouées avec médiane point-in-time '
          f'(>= {MIN_COTES} cotes antérieures) : {len(L)}')
    print(f'  {sans_med} écartées, historique du joueur trop court')
    if not L:
        return 0
    print(f'  période {min(x["date"] for x in L)} -> {max(x["date"] for x in L)}')
    d2 = sum(1 for x in L if 'diff' in x)
    print(f'  dont {d2} avec une médiane des DEUX côtés')

    if len(L) < 60:
        print('\nÉCHANTILLON TROP FAIBLE — toute lecture serait du bruit.')
        return 0

    sd = st.stdev([x['res'] for x in L])
    print(f'\nécart-type du résidu : {100*sd:.1f} points '
          f'-> IC95 à n={len(L)} : +-{196*sd/math.sqrt(len(L)):.2f} pts')
    e = sorted(x['ecart'] for x in L)
    print(f'écart affiché : médiane {e[len(e)//2]:+.1f}, '
          f'décile {e[len(e)//10]:+.1f} à {e[9*len(e)//10]:+.1f} pts')

    # ── TEST PRINCIPAL ──────────────────────────────────────────────────
    print('\n' + '=' * 72)
    print('TEST PRINCIPAL — l\'écart affiché prédit-il quoi que ce soit ?')
    print('=' * 72)
    for f, lib in (('ecart', 'écart sur le prix Pinnacle'),
                   ('ecart_entry', 'écart sur le prix d\'entrée réel')):
        print(f'\n  {lib}')
        for tgt in ('res', 'clv', 'pnl'):
            v = [(x[f], x[tgt]) for x in L if x[tgt] is not None]
            c, t = corr([a for a, _ in v], [b for _, b in v])
            print(f'    corr(écart, {tgt:4}) = {c:+.4f}   t={t:+5.2f}   '
                  f'n={len(v)}')

    print('\n  TÉMOIN — le prix du match seul, sans la médiane')
    for tgt in ('res', 'pnl'):
        v = [(math.log(x['po']), x[tgt]) for x in L if x[tgt] is not None]
        c, t = corr([a for a, _ in v], [b for _, b in v])
        print(f'    corr(log cote, {tgt:4}) = {c:+.4f}   t={t:+5.2f}')

    print('\n  PAR QUARTILE D\'ÉCART')
    s = sorted(L, key=lambda x: x['ecart'])
    q = len(s) // 4
    for i in range(4):
        g = s[i*q:(i+1)*q if i < 3 else len(s)]
        ligne(f'Q{i+1}  écart [{g[0]["ecart"]:+6.1f} ; {g[-1]["ecart"]:+6.1f}]', g)
    ligne('ENSEMBLE', L)

    # Le meilleur quartile vaut-il mieux que le meilleur de quatre tirages
    # au hasard ? C'est la seule façon honnête de lire un maximum.
    obs = max(st.mean([x['res'] for x in s[i*q:(i+1)*q if i < 3 else len(s)]])
              for i in range(4))
    pool = [x['res'] for x in L]
    random.seed(7)
    N = 4000
    cnt = sum(1 for _ in range(N)
              if (random.shuffle(pool) or
                  max(st.mean(pool[i*q:(i+1)*q if i < 3 else len(pool)])
                      for i in range(4)) >= obs))
    print(f'\n  meilleur quartile {100*obs:+.2f} pts — p = {cnt/N:.3f} '
          f'contre un tirage au hasard ({N} permutations)')

    # ── L'ÉCART DES DEUX CÔTÉS ──────────────────────────────────────────
    D = [x for x in L if 'diff' in x]
    if len(D) >= 60:
        print('\n' + '=' * 72)
        print('VARIANTE — l\'écart du steamé MOINS celui de l\'adversaire')
        print('=' * 72)
        print('  (si le marché déforme les deux prix, seul le différentiel')
        print('   porte de l\'information)')
        for tgt in ('res', 'clv', 'pnl'):
            v = [(x['diff'], x[tgt]) for x in D if x[tgt] is not None]
            c, t = corr([a for a, _ in v], [b for _, b in v])
            print(f'    corr(différentiel, {tgt:4}) = {c:+.4f}   t={t:+5.2f}   '
                  f'n={len(v)}')

    # ── CE QUI EST SORTI DE LA RECHERCHE ────────────────────────────────
    print('\n' + '=' * 72)
    print('EXPLORATOIRE — ce qui est sorti en cherchant, et ne prouve rien')
    print('=' * 72)
    print('  L\'écart est nul. En le décomposant, c\'est la MÉDIANE seule —')
    print('  le prix habituel du joueur, sans le prix de ce match — qui')
    print('  ressort. Trouvée après une quinzaine de spécifications : à ce')
    print('  compte, un t autour de 2 est ce qu\'on attend du hasard. Les')
    print('  tests de stabilité comptent donc plus que la corrélation.')
    print()
    # Trois écritures de la même idée. Qu'elles ne donnent pas le même t
    # est en soi un signe de fragilité : un effet réel ne dépend pas du
    # choix entre la médiane, son log et son inverse.
    for lib, f in (('médiane', lambda x: x['med']),
                   ('log(médiane)', lambda x: math.log(x['med'])),
                   ('1/médiane', lambda x: 1 / x['med'])):
        bout = []
        for tgt in ('res', 'clv', 'pnl'):
            v = [(f(x), x[tgt]) for x in L if x[tgt] is not None]
            c, t = corr([a for a, _ in v], [b for _, b in v])
            bout.append(f'{tgt} {c:+.4f} (t={t:+5.2f})')
        print(f'    {lib:13} ' + '   '.join(bout))

    print('\n  PAR TERCILE DE MÉDIANE')
    s = sorted(L, key=lambda x: x['med'])
    q = len(s) // 3
    for i in range(3):
        g = s[i*q:(i+1)*q if i < 2 else len(s)]
        ligne(f'T{i+1}  médiane [{g[0]["med"]:.2f} ; {g[-1]["med"]:.2f}]', g)

    print('\n  STABILITÉ 1 — les deux moitiés de la période')
    L.sort(key=lambda x: x['date'])
    mid = len(L) // 2
    for g, lib in ((L[:mid], '1re moitié'), (L[mid:], '2e moitié')):
        c, t = corr([x['med'] for x in g], [x['res'] for x in g])
        print(f'    {lib:12} {g[0]["date"]} -> {g[-1]["date"]}  n={len(g):3}  '
              f'corr={c:+.4f}  t={t:+5.2f}')

    print('\n  STABILITÉ 2 — selon la PROFONDEUR de l\'historique')
    print('    (un vrai signal se renforce quand la médiane se précise ;')
    print('     du bruit fait l\'inverse)')
    s = sorted(L, key=lambda x: x['n_hist'])
    h = len(s) // 2
    for g, lib in ((s[:h], f'médiane courte (<= {s[h-1]["n_hist"]} cotes)'),
                   (s[h:], f'médiane longue (>= {s[h]["n_hist"]} cotes)')):
        c, t = corr([x['med'] for x in g], [x['res'] for x in g])
        print(f'    {lib:34} n={len(g):3}  corr={c:+.4f}  t={t:+5.2f}')

    print('\n  STABILITÉ 3 — à tournoi constant (les plus gros seulement)')
    par = defaultdict(list)
    for x in L:
        par[x['tour']].append(x)
    for t_ in sorted(par, key=lambda k: -len(par[k]))[:5]:
        g = par[t_]
        if len(g) < 40:
            continue
        c, tv = corr([x['med'] for x in g], [x['res'] for x in g])
        print(f'    {t_[:28]:30} n={len(g):3}  corr={c:+.4f}  t={tv:+5.2f}')

    # ── PRÉ-ENREGISTREMENT ──────────────────────────────────────────────
    print('\n' + '=' * 72)
    print('PRÉ-ENREGISTREMENT DU 09/10/2026 — verdict quand n sera atteint')
    print('=' * 72)
    for lib, f, seuil, cible in (
            ('écart affiché', 'ecart', ECART_SEUIL, ECART_N_CIBLE),
            ('médiane du joueur', 'med', MED_SEUIL, MED_N_CIBLE)):
        g = [x for x in L if x[f] > seuil]
        p = [x['pnl'] for x in g if x['pnl'] is not None]
        print(f'\n  {lib} > {seuil}')
        if len(g) < 30:
            print(f'    n={len(g)} / {cible} — rien à lire encore')
            continue
        m, a, b = ic([x['res'] for x in g])
        pm, pa, pb = ic(p)
        print(f'    n = {len(g)} / {cible}  '
              f'({100*len(g)/cible:.0f} % de la cible)')
        print(f'    résidu {100*m:+6.2f} pts  IC95 [{100*a:+6.2f} ; {100*b:+6.2f}]')
        print(f'    ROI    {100*pm:+6.2f} %    IC95 [{100*pa:+6.2f} ; {100*pb:+6.2f}]')
        # Un ROI dont l'IC exclut zéro alors que celui du résidu le
        # traverse, sur les MÊMES lignes, ne décrit pas un avantage : il
        # décrit quels matchs ont gagné à quel prix. On le montre en
        # retirant les plus gros gains un par un.
        if pa > 0:
            ps = sorted(p)
            print('    (ROI positif : on retire les plus gros gains)')
            for k in (1, 2, 3, 5):
                if len(ps) - k < 30:
                    break
                km, ka, kb = ic(ps[:-k])
                print(f'      sans les {k} plus gros : ROI {100*km:+6.2f} % '
                      f'[{100*ka:+6.2f} ; {100*kb:+6.2f}]')
        if len(g) < cible:
            manque = cible - len(g)
            # Rythme observé DANS CE SOUS-GROUPE, pas le rythme global.
            par_jour = len(g) / _duree_jours(L)
            print(f'    VERDICT : en attente — {manque} alertes de plus, '
                  f'soit ~{manque / par_jour / 30.4:.1f} mois au rythme actuel')
        elif a > 0:
            print('    VERDICT : TENU — l\'IC95 du résidu exclut zéro')
        else:
            print('    VERDICT : REJETÉ — n atteint, l\'IC95 traverse zéro')

    print('\n' + '=' * 72)
    print('CONCLUSION AU 09/10/2026')
    print('=' * 72)
    print("""
  L'écart cote-du-match / cote-habituelle est une bonne information
  d'AFFICHAGE : il dit au lecteur si le joueur est dans un match plus
  facile que son ordinaire, ce qu'aucun autre champ de la fiche ne dit.

  Ce n'est pas un FILTRE. Les trois cibles sont nulles, le meilleur
  quartile ne se distingue pas d'un tirage au hasard, et le différentiel
  entre les deux camps est nul à la quatrième décimale.

  Un seul intervalle exclut zéro : le ROI à écart > 5 points. Il ne tient
  pas : retirer deux gains sur 177 le fait retraverser zéro, le résidu du
  même sous-groupe ne l'exclut pas, et la CLV du même sous-groupe est
  nulle. Trois mesures des mêmes lignes qui se contredisent décrivent
  quels matchs ont gagné à quel prix, pas un avantage.

  La médiane seule ressort mieux, mais elle échoue aux trois tests de
  stabilité : portée par la seconde moitié de la période, plus forte là où
  la médiane est la plus BRUITÉE, et incohérente d'un tournoi à l'autre.
  C'est la signature du bruit, pas celle d'un effet.

  Rien à changer dans les alertes. Relancer ce script quand les cibles
  ci-dessus seront atteintes : c'est la mesure qui tranchera, pas une
  relecture des mêmes données.
""")
    return 0


def _duree_jours(L):
    d = sorted(x['date'] for x in L)
    import datetime
    a = datetime.date.fromisoformat(d[0])
    b = datetime.date.fromisoformat(d[-1])
    return max(1, (b - a).days)


if __name__ == '__main__':
    raise SystemExit(main())
