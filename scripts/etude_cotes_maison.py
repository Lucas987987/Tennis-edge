#!/usr/bin/env python3
"""etude_cotes_maison.py — peut-on fabriquer nos propres cotes ?

    python scripts/etude_cotes_maison.py

LECTURE SEULE. N'écrit aucun fichier, aucune requête réseau.

LA QUESTION
-----------
Avec l'Elo publié, la forme, les surfaces, on peut calculer une
probabilité par match et la comparer au prix affiché. Là où notre
probabilité dépasse celle du book, il y a de la value — en théorie.

Le mot qui compte est « en théorie ». Une cote maison ne vaut que si elle
prédit MIEUX que le marché. Sinon l'écart qu'on appelle value n'est pas
l'erreur du book, c'est la nôtre, et on mise dessus.

Ce script fait donc une seule chose : mesurer notre Brier contre celui du
marché. Et il commence par écarter le piège qui rend cette mesure fausse
dans neuf cas sur dix.

LE PIÈGE : elo_reference.json EST UN INSTANTANÉ
------------------------------------------------
Le fichier est un relevé des notes D'AUJOURD'HUI, rapatrié chaque lundi
par elo_fetch.py. La note de Sinner au 28/09 contient le résultat de tous
ses matchs jusqu'au 28/09.

S'en servir pour prédire un match du mois d'août, c'est lui demander un
résultat qu'il connaît déjà. C'est H14 à l'identique, en pire : là-bas la
contamination valait +0,38 de corrélation, ici elle inverse le verdict.

Le script le démontre au lieu de l'affirmer, avec deux mesures :

  1. Le Brier mois par mois. S'il s'améliore à mesure qu'on approche de la
     date de l'instantané, puis s'effondre après, c'est la signature.

  2. Le Brier avant / après la date de l'instantané. Après, l'Elo ne peut
     pas connaître le résultat : c'est la seule fenêtre PROPRE du dépôt.

La date de coupure n'est pas écrite en dur : elle est lue dans
elo_reference.json['meta'][*]['derniere_maj']. Le script reste donc juste
après chaque passage d'elo_fetch.

CE QUE CE SCRIPT NE PEUT PAS FAIRE
-----------------------------------
Accumuler un échantillon propre. La fenêtre propre est toujours « depuis
le dernier instantané », soit une semaine : elle ne grossit pas, elle se
déplace. Relancer le script dans un mois donnera encore une semaine.

Pour trancher pour de bon il faut ÉCRIRE LE PRIX AVANT LE MATCH, chaque
jour, comme h16_signal_log.jsonl et h18_signal_log.jsonl le font déjà pour
leurs hypothèses. Le dernier bloc chiffre l'échantillon qu'il faudrait.
"""

import csv
import json
import math
import os
import re
import statistics as st
import unicodedata

MOVES = os.environ.get('MOVES', 'moves_detail_hist.csv')
ELO = os.environ.get('ELO', 'elo_reference.json')

# Marge Pinnacle retirée avant comparaison. On n'a qu'un côté du marché
# dans moves_detail_hist, donc impossible de normaliser les deux faces :
# on divise par une marge forfaitaire. Mesuré : le verdict ne bouge pas
# entre 1,00 et 1,05, la marge Pinnacle réelle tournant autour de 2,5 %.
MARGE = float(os.environ.get('MARGE_PIN', '1.025'))


def cle(nom):
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


def brier(v, k):
    return st.mean([(x[k] - x['y']) ** 2 for x in v])


def main():
    for f in (MOVES, ELO):
        if not os.path.exists(f):
            print(f'{f} introuvable — lancer depuis la racine du dépôt.')
            return 1

    E = json.load(open(ELO, encoding='utf-8'))
    elo = {cle(v['nom']): v for v in E.get('joueurs', {}).values()
           if isinstance(v, dict) and v.get('elo')}
    # La coupure propre : la PLUS RÉCENTE des mises à jour de source. Prendre
    # la plus ancienne laisserait passer un circuit déjà contaminé.
    majs = [m.get('derniere_maj') for m in E.get('meta', {}).values()
            if isinstance(m, dict) and m.get('derniere_maj')]
    coupe = max(majs) if majs else (E.get('genere_le') or '')[:10]
    print(f'{ELO} : {len(elo)} joueurs, relevé le {coupe}')

    L = []
    for r in csv.DictReader(open(MOVES, encoding='utf-8')):
        if r.get('steame_gagne') not in ('oui', 'non'):
            continue
        a, b = elo.get(cle(r.get('steame'))), elo.get(cle(r.get('opp')))
        pc, en = num(r.get('pin_close')), num(r.get('entry'))
        if not (a and b and pc and pc > 1):
            continue
        L.append({
            'd': r['date'],
            'y': 1.0 if r['steame_gagne'] == 'oui' else 0.0,
            # La formule Elo, sans réglage : 400 points = 10 contre 1.
            'elo': 1 / (1 + 10 ** (-(a['elo'] - b['elo']) / 400)),
            'marche': min(.99, max(.01, (1 / pc) / MARGE)),
            'entry': en,
            'pnl': num(r.get('pnl')),
        })
    L.sort(key=lambda x: x['d'])
    print(f'matchs dénoués avec Elo des DEUX côtés : {len(L)}')
    if len(L) < 100:
        print('trop peu pour mesurer quoi que ce soit.')
        return 0

    def bloc(v, lib, marque=''):
        if len(v) < 30:
            print(f'  {lib:32} n={len(v):4}   trop peu')
            return
        be, bm = brier(v, 'elo'), brier(v, 'marche')
        fl = 'ELO MEILLEUR' if be < bm else 'marché meilleur'
        print(f'  {lib:32} n={len(v):4}   Elo {be:.4f}   marché {bm:.4f}   '
              f'{fl}{marque}')

    print('\n' + '=' * 72)
    print('1. LA CONTAMINATION, MOIS PAR MOIS')
    print('=' * 72)
    print('   Si l\'Elo « sait », il prédit d\'autant mieux que le match est')
    print('   proche de la date du relevé — puis s\'effondre juste après.\n')
    for m in sorted({x['d'][:7] for x in L}):
        bloc([x for x in L if x['d'][:7] == m], m,
             ' ← après le relevé' if m > coupe[:7] else '')

    print('\n' + '=' * 72)
    print(f'2. AVANT / APRÈS LE RELEVÉ DU {coupe}')
    print('=' * 72)
    av = [x for x in L if x['d'] < coupe]
    ap = [x for x in L if x['d'] >= coupe]
    print('   Avant : l\'Elo connaît déjà les résultats. Chiffre inutilisable,')
    print('   donné seulement pour montrer de combien il trompe.')
    bloc(av, 'avant (CONTAMINÉ)')
    print('   Après : l\'Elo est antérieur aux matchs. Seule fenêtre propre.')
    bloc(ap, 'après (PROPRE)')

    if len(ap) >= 30:
        d = [(x['elo'] - x['y']) ** 2 - (x['marche'] - x['y']) ** 2 for x in ap]
        m = st.mean(d)
        se = st.stdev(d) / math.sqrt(len(d))
        print(f'\n   écart de Brier apparié : {m:+.4f}  '
              f'IC95 [{m-1.96*se:+.4f} ; {m+1.96*se:+.4f}]  t={m/se:+.2f}')
        print('   (positif = notre cote est MOINS bonne que le marché)')

    print('\n' + '=' * 72)
    print('3. ET SI ON MÉLANGEAIT ? w × Elo + (1−w) × marché')
    print('=' * 72)
    print('   Un modèle battu peut encore servir si ses erreurs ne sont pas')
    print('   celles du marché. Le poids optimal le dit : s\'il vaut 0,')
    print('   l\'Elo n\'apporte rien, même en appoint.\n')
    for v, lib in ((ap, 'PROPRE'), (av, 'contaminé')):
        if len(v) < 30:
            continue
        best = None
        out = []
        for i in range(0, 11):
            w = i / 10
            b = st.mean([((w * x['elo'] + (1 - w) * x['marche']) - x['y']) ** 2
                         for x in v])
            out.append((w, b))
            if best is None or b < best[1]:
                best = (w, b)
        print(f'   {lib:10} ' + '  '.join(f'w={w:.1f}:{b:.4f}'
                                          for w, b in out[::2]))
        print(f'   {"":10} poids optimal w = {best[0]:.1f}  '
              f'(brier {best[1]:.4f})')

    print('\n' + '=' * 72)
    print('4. LA VALUE QU\'ON AURAIT JOUÉE, SUR LA FENÊTRE PROPRE')
    print('=' * 72)
    ref = [x['pnl'] for x in ap if x['pnl'] is not None]
    for seuil in (.03, .05, .08):
        g = [x for x in ap if x['entry'] and x['pnl'] is not None
             and x['elo'] - 1 / x['entry'] > seuil]
        if len(g) < 20:
            print(f'   marge > {seuil:.0%} : n={len(g)} — trop peu')
            continue
        p = [x['pnl'] for x in g]
        mm = st.mean(p)
        se = st.stdev(p) / math.sqrt(len(p))
        print(f'   marge > {seuil:.0%} : n={len(g):3}   ROI {100*mm:+6.1f} %   '
              f'IC95 [{100*(mm-1.96*se):+6.1f} ; {100*(mm+1.96*se):+6.1f}]')
    if len(ref) >= 30:
        mm = st.mean(ref)
        se = st.stdev(ref) / math.sqrt(len(ref))
        print(f'   témoin, TOUTES les alertes : n={len(ref):3}   '
              f'ROI {100*mm:+6.1f} %   '
              f'IC95 [{100*(mm-1.96*se):+6.1f} ; {100*(mm+1.96*se):+6.1f}]')

    print('\n' + '=' * 72)
    print('5. CE QU\'IL FAUDRAIT POUR TRANCHER')
    print('=' * 72)
    if len(ap) >= 30:
        sd = st.stdev([(x['elo'] - x['y']) ** 2 - (x['marche'] - x['y']) ** 2
                       for x in ap])
        print(f'   écart-type de l\'écart de Brier par match : {sd:.4f}')
        for gain in (0.005, 0.010, 0.020):
            print(f'   pour prouver un gain de {gain:.3f} de Brier : '
                  f'n ~ {int((1.96*sd/gain)**2)} matchs')
    print(f"""
   Ces n ne s'obtiennent pas en relançant ce script : la fenêtre propre
   fait une semaine et se déplace à chaque passage d'elo_fetch.

   Ils s'obtiennent en ÉCRIVANT LE PRIX AVANT LE MATCH. Une ligne par
   match coté, avec la date, les deux noms, l'Elo de chacun à cet
   instant, notre probabilité et le prix du marché — le format de
   h16_signal_log.jsonl. Après coup, le résultat se joint sur l'uid et
   la mesure devient incontestable.

   Deuxième raison de passer par un journal : il couvre TOUS les matchs
   cotés, pas seulement ceux où un mouvement a été détecté. Les {len(ap)}
   lignes propres d'ici sont des alertes ; le collecteur en voit
   plusieurs fois plus. La cible se remplit alors en semaines, pas en
   trimestres.
""")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
