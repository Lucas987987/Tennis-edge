#!/usr/bin/env python3
"""build_profiles.py — construit players_profile.json, une fiche par joueur.

Assemble ce que le dépôt possède déjà, sans aucune source externe :

  moves_detail_hist.csv  les cotes : ouverture Pinnacle, entrée, book retenu
  set_results.json       les résultats : match, set 1, set 2
  player_form.json       forme sur 10 matchs et fatigue sur 7 / 14 jours

CE QUI N'EST PAS DANS LA FICHE, ET POURQUOI
-------------------------------------------
Pas de CLV par joueur, pas de taux de réussite des alertes, pas de dérive
du marché. Les trois sont du BIAIS DE SÉLECTION : moves_detail_hist ne
contient que des mouvements détectés, donc un joueur y figure parce que
le marché a bougé vers lui.

Mesuré : le côté steamé est raccourci dans 81 % des cas sur l'ensemble du
fichier. Afficher « le marché le raccourcit dans 80 % des cas » pour un
joueur donné décrit la détection, pas le joueur.

Même chose pour « 9 victoires sur 9 en favori » : neuf matchs steamés,
IC95 [70 ; 100]. C'est exactement le reproche fait aux sites de tipsters.

LES NOMS
--------
Trois conventions coexistent :
  moves_detail_hist  « Ben Shelton », « Mattia Bellucci »
  player_form        « ben shelton » MAIS « bellucci mattia » — ordre
                     inversé selon les entrées
  set_results        deux formats de clé, voir plus bas

D'où la clé par JEU DE TOKENS TRIÉ : accents retirés, minuscules, tokens
ordonnés. « Mattia Bellucci » et « bellucci mattia » donnent la même clé.
Taux de raccordement mesuré : 84 % sur la forme.

LES RÉSULTATS
-------------
set_results.json mélange deux formats :
  2 575 clés  {date}_{home}_{away}   = le uid de moves_detail_hist
    738 clés  {tournoi}_{home}_vs_{away}

Le premier se joint EXACTEMENT sur uid, sans deviner où finit le premier
nom — 76 % des matchs de moves. Le second se parse sur « _vs_ ».
"""

import csv
import json
import os
import re
import statistics as st
import unicodedata
from collections import defaultdict

MOVES = os.environ.get('MOVES', 'moves_detail_hist.csv')
SETRES = os.environ.get('SETRES', 'set_results.json')
FORM = os.environ.get('FORM', 'player_form.json')
OUT = os.environ.get('OUT', 'players_profile.json')

# Nombre minimal d'observations pour publier une médiane de cote. En
# dessous, la fiche affiche le compte mais pas la médiane : une médiane
# sur 2 cotes n'est pas une médiane.
MIN_COTES = int(os.environ.get('MIN_COTES', '4'))

# Nombre minimal pour entrer au CLASSEMENT, plus exigeant que pour
# afficher une médiane. À 4 cotes, un joueur de challenger favori quatre
# fois d'affilée sortait devant Zverev et Sabalenka : la médiane était
# juste, le rang trompeur. À 8, les 145 classés sont ceux que le marché
# a réellement cotés assez souvent pour qu'un rang veuille dire quelque
# chose. Les autres gardent leur médiane, sans rang.
MIN_RANG = int(os.environ.get('MIN_RANG', '8'))

# Profondeur de l'historique conservé par joueur. À 8, neuf fiches
# étaient tronquées ; à 16 aucune ne l'est, pour quelques ko de plus.
N_DERNIERS = int(os.environ.get('N_DERNIERS', '16'))


def cle(nom):
    """Jeu de tokens trié — absorbe l'ordre prénom/nom et les accents."""
    if not nom:
        return ''
    s = unicodedata.normalize('NFKD', str(nom)).encode('ascii', 'ignore').decode()
    toks = [t for t in re.split(r'[^A-Za-z]+', s.lower()) if len(t) > 1]
    return ' '.join(sorted(toks))


def num(v):
    try:
        x = float(v)
        return x if x == x else None          # écarte NaN
    except (TypeError, ValueError):
        return None


def slug(nom):
    """Nom au format du uid : minuscules, accents retirés, _ entre mots."""
    s = unicodedata.normalize('NFKD', str(nom)).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z]+', '_', s.lower()).strip('_')


def charger_resultats(setres, moves):
    """uid -> (nom_home, nom_away, resultat) pour ce qu'on sait nommer.

    Deux sources de noms, par ordre de fiabilité :
      1. moves_detail_hist, qui donne explicitement steame et opp ;
      2. le format _vs_, où la séparation est explicite.

    Le format {date}_{home}_{away} ne dit PAS où finit le premier nom
    (deux noms de plusieurs tokens collés). On ne devine pas : les uid
    absents de moves restent non nommés et ne comptent que dans le total.

    ATTENTION — `steame` N'EST PAS `home`.
    -------------------------------------
    `steame` est le côté vers lequel le marché a bougé ; il occupe la
    position « away » du uid dans 48 % des cas (mesuré sur 1 177 uid).
    Prendre (steame, opp) pour (home, away) inversait donc un résultat
    sur deux : Mattia Bellucci apparaissait battu quatre jours d'affilée,
    ce qui est impossible — on est éliminé à la première défaite.

    L'ordre se lit dans le uid lui-même : on compare le nom au préfixe
    qui suit la date. C'est exact, pas déduit.
    """
    noms = {}
    for r in moves:
        u, s, o = r.get('uid'), r.get('steame'), r.get('opp')
        if not (u and s and o):
            continue
        m = re.match(r'^\d{4}-\d{2}-\d{2}_(.+)$', u)
        if not m:
            continue
        reste = m.group(1)
        if reste.startswith(slug(s)):
            noms[u] = (s, o)
        elif reste.startswith(slug(o)):
            noms[u] = (o, s)
        # ni l'un ni l'autre : nom tronqué ou translittéré autrement.
        # On s'abstient plutôt que de risquer une inversion silencieuse.

    out = {}
    for k, v in setres.items():
        if k in noms:
            h, a = noms[k]
        elif '_vs_' in k:
            g, d = k.rsplit('_vs_', 1)
            parts = g.split('_')
            # le préfixe est le tournoi : « atp_stuttgart_jurij_rodionov »
            h = ' '.join(parts[2:]) if len(parts) > 2 else g
            a = d.replace('_', ' ')
        else:
            continue
        out[k] = (h, a, v)
    return out


def main():
    moves = [r for r in csv.DictReader(open(MOVES, encoding='utf-8'))]
    setres = json.load(open(SETRES, encoding='utf-8'))
    forme = json.load(open(FORM, encoding='utf-8')).get('joueurs', {})
    form_k = {cle(k): v for k, v in forme.items()}

    res = charger_resultats(setres, moves)

    P = defaultdict(lambda: {
        'nom': None, 'cotes': [], 'cotes_adv': [], 'circuits': defaultdict(int),
        'books': defaultdict(int), 'matchs': [], 'dates': [],
    })

    # ── Le marché : cote d'ouverture Pinnacle ───────────────────────────
    #
    # Pour le côté steamé, pin_open est sa cote. Pour l'adversaire, on la
    # déduit de la probabilité complémentaire — approximation, la marge
    # n'est pas retirée, mais elle suffit à situer un joueur.
    for r in moves:
        po = num(r.get('pin_open'))
        s, o = r.get('steame'), r.get('opp')
        d, t = r.get('date'), r.get('tour')
        if s:
            k = cle(s)
            P[k]['nom'] = P[k]['nom'] or s
            if po:
                P[k]['cotes'].append(po)
            if t:
                P[k]['circuits'][t] += 1
            if d:
                P[k]['dates'].append(d)
            b = r.get('entry_book')
            if b:
                P[k]['books'][b] += 1
            if po:
                P[k]['cotes_adv'].append(1 / max(0.02, 1 - 1 / po))
        if o:
            k = cle(o)
            P[k]['nom'] = P[k]['nom'] or o
            if t:
                P[k]['circuits'][t] += 1
            if d:
                P[k]['dates'].append(d)
            if po:
                P[k]['cotes'].append(1 / max(0.02, 1 - 1 / po))
                P[k]['cotes_adv'].append(po)

    # ── Les résultats : match, set 1, set 2 ─────────────────────────────
    for uid, (h, a, v) in res.items():
        date = uid[:10] if re.match(r'^\d{4}-\d{2}-\d{2}', uid) else None
        for nom, cote in ((h, 'home'), (a, 'away')):
            k = cle(nom)
            if not k:
                continue
            P[k]['nom'] = P[k]['nom'] or nom
            P[k]['matchs'].append({
                'date': date,
                'adv': a if cote == 'home' else h,
                'match': v.get('match') == cote if v.get('match') else None,
                'set1': v.get('set1') == cote if v.get('set1') else None,
                'set2': v.get('set2') == cote if v.get('set2') else None,
            })

    # ── Assemblage ──────────────────────────────────────────────────────
    out = {}
    for k, p in P.items():
        if not p['nom']:
            continue
        f = form_k.get(k, {})
        ms = sorted([m for m in p['matchs'] if m['date']],
                    key=lambda m: m['date'], reverse=True)
        joues = [m for m in ms if m['match'] is not None]
        s1 = [m for m in ms if m['set1'] is not None]

        fiche = {
            'nom': p['nom'],
            'n_matchs_vus': len(set(p['dates'])),
            'periode': [min(p['dates']), max(p['dates'])] if p['dates'] else None,
            'circuits': [c for c, _ in sorted(p['circuits'].items(),
                                              key=lambda x: -x[1])[:4]],
        }

        if len(p['cotes']) >= MIN_COTES:
            fiche['cote_mediane'] = round(st.median(p['cotes']), 2)
            fiche['cote_min'] = round(min(p['cotes']), 2)
            fiche['cote_max'] = round(max(p['cotes']), 2)
            fiche['n_cotes'] = len(p['cotes'])
            fiche['pct_favori'] = round(
                100 * sum(1 for c in p['cotes'] if c < 2) / len(p['cotes']))
        if len(p['cotes_adv']) >= MIN_COTES:
            fiche['cote_adversaires'] = round(st.median(p['cotes_adv']), 2)

        if joues:
            fiche['bilan'] = {
                'n': len(joues),
                'victoires': sum(1 for m in joues if m['match']),
            }
        if s1:
            # Gagner le 1er set est une information que presque personne
            # ne publie, et elle est disponible sur 100 % des matchs joués.
            fiche['set1'] = {
                'n': len(s1),
                'gagnes': sum(1 for m in s1 if m['set1']),
            }
        if ms:
            # adv_cle permet la confrontation directe : deux fiches se
            # croisent sans retraverser set_results.json côté client.
            fiche['derniers'] = [
                {'date': m['date'], 'adv': m['adv'], 'gagne': m['match'],
                 'set1': m['set1'], 'adv_cle': cle(m['adv'])}
                for m in ms[:N_DERNIERS]
            ]

        if f:
            fiche['forme'] = f.get('forme')
            fiche['fatigue'] = f.get('fatigue')

        if p['books']:
            fiche['meilleur_prix'] = max(p['books'].items(), key=lambda x: x[1])[0]

        out[k] = fiche

    # ── Classement marché ───────────────────────────────────────────────
    #
    # La médiane de la cote d'ouverture EST un classement, et c'est le
    # plus pertinent ici : il intègre la forme, la surface et le contexte,
    # ce qu'un classement ATP ne fait pas. Rang publié seulement au-delà
    # de MIN_RANG cotes — sinon il ferait croire à une précision qui
    # n'existe pas.
    cl = sorted([(k, v['cote_mediane']) for k, v in out.items()
                 if v.get('n_cotes', 0) >= MIN_RANG], key=lambda x: x[1])
    for rang, (k, _) in enumerate(cl, 1):
        out[k]['rang_marche'] = rang
        out[k]['rang_sur'] = len(cl)

    import datetime as _dt
    meta = {
        'genere_le': _dt.datetime.now(_dt.timezone.utc).isoformat(
            timespec='seconds'),
        'n_joueurs': len(out),
        'n_classes': len(cl),
        'min_cotes': MIN_COTES,
        'min_rang': MIN_RANG,
        'sources': ['moves_detail_hist.csv', 'set_results.json',
                    'player_form.json'],
        'avertissement': (
            "Aucun CLV ni taux de reussite par joueur : moves_detail_hist "
            "ne contient que des mouvements detectes, donc tout taux calcule "
            "dessus est du biais de selection."),
    }
    json.dump({'meta': meta, 'joueurs': out},
              open(OUT, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    n_med = sum(1 for v in out.values() if 'cote_mediane' in v)
    print(f"{OUT} : {len(out)} joueurs, {n_med} avec mediane "
          f"(>= {MIN_COTES} cotes), {len(cl)} classes (>= {MIN_RANG})")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
