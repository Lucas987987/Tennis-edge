#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bilan_direct_tt_badminton.py — paquet 535 (28/11/2026, Lucas : « bilan du tennis de table vers le 04/12 » et « pages
joueurs badminton : revoir le seuil dans une semaine »). LECTURE SEULE : rien n'est modifié, ni l'algo ni les pages.

Lit l'archive privée des matchs jugés (R2 : prive/tennis_de_table/archive/, prive/badminton/archive/) — chaque pronostic
figé au début du match et son résultat — et l'état des pages badminton (prive/badminton/pages.json).

RÈGLE ÉCRITE LE 28/11/2026, AVANT D'AVOIR VU LES MATCHS EN DIRECT :
  Tennis de table, ligue par ligue (International, Pologne), sur tous les matchs jugés depuis le lancement :
    • moins de 300 matchs : trop tôt, rien n'est dit ; 300 à 999 : une indication ; 1 000 et plus : un constat ;
    • log loss en direct comparée à celle de l'étude (tennis_de_table/rapport_etape2_tt.json, bilan_par_ligue) :
      « conforme » si elle ne la dépasse pas de plus de 2 erreurs types, sinon « à surveiller » ;
    • même chose pour le taux de bons vainqueurs (2 erreurs types de la proportion) ;
    • étalonnage par tranche du % annoncé au favori : une tranche d'au moins 100 matchs est signalée si l'écart entre
      réel et annoncé dépasse 2 erreurs types ;
    • score exact et manche décisive : descriptifs.
  Badminton (lancé le 27/11) : descriptif seulement (trop peu de jours pour juger), épreuve par épreuve ; et, pour le
  seuil des pages joueurs (3 matchs jugés aujourd'hui), le nombre de joueurs à 1, 2, 3, 4 et 5 matchs jugés ou plus.
  Aucun réglage ne change à cause de ce bilan : un écart « à surveiller » ouvre une étude, avec sa propre règle.
Aucune cote. Le journal n'affiche que des comptes, des % et des log loss.

Usage : python scripts/bilan_direct_tt_badminton.py [racine]   (R2 : R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ENDPOINT ;
        ou BILAN_COFFRE_LOCAL=dossier pour un coffre local)
"""
import collections
import datetime as dt
import json
import math
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
TT_ARCHIVE = 'prive/tennis_de_table/archive/{mois}.jsonl'
BAD_ARCHIVE = 'prive/badminton/archive/{mois}.jsonl'
BAD_PAGES = 'prive/badminton/pages.json'
TRANCHES = ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 1.01))
N_INDICATION, N_CONSTAT, N_TRANCHE = 300, 1000, 100
DEBUT = dt.date(2026, 11, 1)
SORTIE = 'rapport_bilan_direct_tt_badminton.json'


class CoffreLocal:
    def __init__(self, d):
        self.d = d

    def get(self, cle):
        try:
            with open(os.path.join(self.d, cle), 'rb') as f:
                return f.read()
        except OSError:
            return None


def coffre():
    if os.environ.get('BILAN_COFFRE_LOCAL'):
        return CoffreLocal(os.environ['BILAN_COFFRE_LOCAL'])
    sys.path.insert(0, ICI)
    import r2_io
    return r2_io.client(quiet=True)


def mois_depuis(debut, fin):
    m, out = dt.date(debut.year, debut.month, 1), []
    while m <= fin:
        out.append(m.strftime('%Y-%m'))
        m = dt.date(m.year + (m.month == 12), m.month % 12 + 1, 1)
    return out


def lire_archive(cf, modele, fin):
    """Matchs jugés (pronostic figé + vainqueur), sans doublon d'identifiant (le dernier écrit l'emporte)."""
    par_id = {}
    for mois in mois_depuis(DEBUT, fin):
        brut = cf.get(modele.format(mois=mois)) or b''
        for l in brut.decode('utf-8', 'replace').splitlines():
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if isinstance(x, dict) and 'p_h' in x and x.get('g') in (1, 2):
                par_id[x.get('id', len(par_id))] = x
    return list(par_id.values())


def mesurer(L):
    """{n, log_loss, erreur_type_ll, bons_pct, annonce_pct, tranches, score_trouve_pct, decisive…} d'une liste de matchs."""
    n = len(L)
    if not n:
        return {'matchs': 0}
    ll, bons, pf_s = [], 0, 0.0
    tr = collections.defaultdict(lambda: [0, 0.0, 0])
    sc_n = sc_ok = dec_n = dec_r = 0
    dec_a = 0.0
    for x in L:
        p = min(max(float(x['p_h']), 1e-6), 1 - 1e-6)
        pg = p if x['g'] == 1 else 1 - p
        ll.append(-math.log(pg))
        pf = max(p, 1 - p)
        bon = (x['g'] == 1) == (p >= 0.5)
        bons += bon
        pf_s += pf
        for lo, hi in TRANCHES:
            if lo <= pf < hi:
                t = tr[round(lo * 100)]
                t[0] += 1
                t[1] += pf
                t[2] += bon
        if 'score_trouve' in x:
            sc_n += 1
            sc_ok += bool(x['score_trouve'])
        if x.get('decisive') is not None and x.get('decisive_reelle') is not None:
            dec_n += 1
            dec_a += float(x['decisive'])
            dec_r += bool(x['decisive_reelle'])
    m = sum(ll) / n
    et = math.sqrt(sum((v - m) ** 2 for v in ll) / max(n - 1, 1) / n)
    out = {'matchs': n, 'log_loss': round(m, 5), 'erreur_type_ll': round(et, 5), 'bons_pct': round(100 * bons / n, 1),
           'annonce_pct': round(100 * pf_s / n, 1), 'tranches': {}}
    for lo, (k, s, b) in sorted(tr.items()):
        a, r = s / k, b / k
        e = math.sqrt(a * (1 - a) / k)
        out['tranches'][f'{lo}'] = {'matchs': k, 'annonce_pct': round(100 * a, 1), 'reel_pct': round(100 * r, 1),
                                    'signalee': k >= N_TRANCHE and abs(r - a) > 2 * e}
    if sc_n:
        out['score_trouve_pct'] = round(100 * sc_ok / sc_n, 1)
    if dec_n:
        out['decisive_annoncee_pct'] = round(100 * dec_a / dec_n, 1)
        out['decisive_reelle_pct'] = round(100 * dec_r / dec_n, 1)
    return out


def juger(mes, ref):
    """Applique la règle de l'en-tête (tennis de table) à une ligue."""
    n = mes.get('matchs', 0)
    if n < N_INDICATION:
        return {'niveau': 'trop tôt', 'detail': f'{n} matchs jugés (il en faut {N_INDICATION} pour une indication)'}
    niveau = 'constat' if n >= N_CONSTAT else 'indication'
    out = {'niveau': niveau}
    if ref:
        lim = ref['log_loss'] + 2 * mes['erreur_type_ll']
        out['log_loss'] = 'conforme' if mes['log_loss'] <= lim else 'à surveiller'
        b = ref['bons_vainqueurs_pct'] / 100
        e = math.sqrt(b * (1 - b) / n)
        out['bons_vainqueurs'] = 'conforme' if mes['bons_pct'] / 100 >= b - 2 * e else 'à surveiller'
    out['tranches_signalees'] = [k for k, t in mes['tranches'].items() if t['signalee']]
    return out


def main(argv):
    racine = argv[1] if len(argv) > 1 else os.path.join(ICI, '..')
    cf = coffre()
    if cf is None:
        print('::error::coffre R2 indisponible')
        return 1
    fin = dt.datetime.now(dt.timezone.utc).date()
    rap = {'genere_le': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'paquet': 535,
           'regle': 'voir l’en-tête de scripts/bilan_direct_tt_badminton.py (écrite le 28/11/2026)'}
    try:
        with open(os.path.join(racine, 'tennis_de_table', 'rapport_etape2_tt.json'), encoding='utf-8') as f:
            REF = json.load(f).get('bilan_par_ligue') or {}
    except (OSError, ValueError):
        REF = {}
    TT = lire_archive(cf, TT_ARCHIVE, fin)
    print(f'Tennis de table : {len(TT)} matchs jugés en direct', flush=True)
    rap['tennis_de_table'] = {}
    for ligue in ('International', 'Poland'):
        L = [x for x in TT if x.get('ligue') == ligue]
        mes = mesurer(L)
        ref = REF.get(ligue)
        j = juger(mes, ref)
        rap['tennis_de_table'][ligue] = {'direct': mes, 'etude': ref and {k: ref[k] for k in ('log_loss', 'bons_vainqueurs_pct')},
                                         'verdict': j}
        if mes['matchs']:
            print(f"  {ligue:13s} n={mes['matchs']:5d}  log loss {mes['log_loss']:.4f} ± {mes['erreur_type_ll']:.4f}"
                  + (f" (étude {ref['log_loss']:.4f})" if ref else '')
                  + f" · bons vainqueurs {mes['bons_pct']} %" + (f" (étude {ref['bons_vainqueurs_pct']} %)" if ref else '')
                  + f" · annoncé {mes['annonce_pct']} %")
            for k, t in mes['tranches'].items():
                print(f"      {k}–{100 if k == '80' else int(k) + 10} % : {t['matchs']:5d} matchs, annoncé {t['annonce_pct']} %, "
                      f"réel {t['reel_pct']} %{'  ← signalée' if t['signalee'] else ''}")
            if 'score_trouve_pct' in mes:
                print(f"      score exact trouvé {mes['score_trouve_pct']} % · manche décisive annoncée "
                      f"{mes.get('decisive_annoncee_pct')} %, réelle {mes.get('decisive_reelle_pct')} %")
        print(f"    → {j['niveau']}" + ''.join(f" · {k.replace('_', ' ')} {v}" for k, v in j.items()
                                                 if k in ('log_loss', 'bons_vainqueurs')) + (f" · {j['detail']}" if 'detail' in j else ''))
    BAD = lire_archive(cf, BAD_ARCHIVE, fin)
    print(f'Badminton : {len(BAD)} matchs jugés en direct (descriptif)', flush=True)
    rap['badminton'] = {'tout': mesurer(BAD)}
    for ep in sorted({x.get('epreuve') for x in BAD if x.get('epreuve')}):
        rap['badminton'][ep] = mesurer([x for x in BAD if x.get('epreuve') == ep])
    for k, m in rap['badminton'].items():
        if m['matchs']:
            print(f"  {k:17s} n={m['matchs']:5d}  log loss {m['log_loss']:.4f} · bons vainqueurs {m['bons_pct']} % · annoncé {m['annonce_pct']} %")
    brut = cf.get(BAD_PAGES)
    try:
        J = (json.loads(brut) if brut else {}).get('joueurs') or {}
    except ValueError:
        J = {}
    seuils = {f'{s}+': sum(1 for j in J.values() if (j.get('n') or 0) >= s) for s in (1, 2, 3, 4, 5)}
    rap['badminton_pages_joueurs'] = {'joueurs_vus': len(J), 'au_moins_n_matchs_juges': seuils, 'seuil_actuel': 3}
    print(f"  pages joueurs badminton : {len(J)} joueurs vus · avec au moins 1/2/3/4/5 matchs jugés : "
          + ' / '.join(str(v) for v in seuils.values()) + ' (seuil actuel : 3)')
    with open(os.path.join(racine, SORTIE), 'w', encoding='utf-8') as f:
        json.dump(rap, f, ensure_ascii=False, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
