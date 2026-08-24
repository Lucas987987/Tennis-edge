#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
paper_journal_canal.py — Le track record de CE QUI EST PUBLIÉ, à la lettre.

LE PROBLÈME QU'IL RÉSOUT
Deux systèmes coexistaient, avec des critères différents :
  • canal_public  publie sur des paliers FIXES (3, 5, 8, 12 pts) et un écart
    book >= GAP_MIN. 68 matchs alertés.
  • paper_journal enregistre selon les seuils ADAPTATIFS par book de
    steam_alert, plus un filtre EV. 17 matchs seulement.
Les 17 sont un sous-ensemble strict des 68 : le journal forward mesurait donc
une stratégie que les abonnés NE VOIENT PAS.

C'est disqualifiant pour l'usage prévu. La monétisation repose sur un track
record forward publié ; s'il ne correspond pas aux alertes reçues, il n'a
aucune valeur — et le publier serait trompeur, même involontairement.

LA SOLUTION : NE RIEN RÉINTERPRÉTER
Ce script ne recalcule aucun signal. Il LIT canal_public_log.jsonl, la trace
de ce qui est réellement parti sur Telegram, et crée un pari par alerte. Par
construction, le track record ne peut plus diverger de la publication : si le
canal change de critères, le journal suit automatiquement.

paper_journal.py CONTINUE de tourner en parallèle — les seuils adaptatifs sont
une stratégie légitime, simplement différente. Deux journaux, deux noms, aucune
confusion possible.

CONVENTION DE PARI
Une alerte liste jusqu'à 3 opérateurs en retard, triés par écart décroissant.
Un abonné en joue UN. On retient le premier, c'est-à-dire le meilleur écart.
Les alertes SANS opérateur en retard ne produisent aucun pari : il n'y a
littéralement rien à jouer. Elles sont comptées à part, car elles font 30 % du
volume publié et diluent le signal si elles partent comme les autres.

DEUX UNITÉS DE COMPTE, LES DEUX RAPPORTÉES
  • par ALERTE — un pari par publication. Un match republié à un palier
    supérieur compte deux fois, comme le vivrait un abonné qui suit tout.
  • par MATCH — première alerte seulement. C'est la mesure honnête d'un edge :
    sinon un même mouvement gonfle le n et resserre faussement l'intervalle.

Env : LOG, OUT, RESULTS_DERIVED.
Usage : python scripts/paper_journal_canal.py
"""
import os
import sys
import json
import math
import datetime
import statistics as st
import collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from results_join import ResultIndex  # noqa: E402

LOG = os.environ.get('LOG', 'canal_public_log.jsonl')
OUT = os.environ.get('OUT', 'paper_trades_canal.jsonl')
RAPPORT = os.environ.get('RAPPORT', 'paper_canal_report.json')


def _dt(x):
    try:
        return datetime.datetime.fromisoformat(
            str(x).replace('Z', '').replace('+00:00', ''))
    except Exception:
        return None


def ic(v):
    n = len(v)
    if n < 2:
        return None, None, None
    m = st.mean(v)
    se = st.stdev(v) / math.sqrt(n)
    return m, m - 1.96 * se, m + 1.96 * se


def charger_alertes():
    if not os.path.exists(LOG):
        print(f"❌ {LOG} absent.")
        return []
    out = []
    for ligne in open(LOG, encoding='utf-8'):
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            out.append(json.loads(ligne))
        except json.JSONDecodeError:
            continue
    out.sort(key=lambda x: str(x.get('t')))
    return out


def main():
    alertes = charger_alertes()
    if not alertes:
        return 1
    idx = ResultIndex()

    trades, sans_ecart, sans_resultat = {}, 0, 0
    vus_match = set()
    for a in alertes:
        uid = a.get('uid')
        t = _dt(a.get('t'))
        ct = _dt(a.get('commence'))
        if not uid or not t or not ct:
            continue
        # retards_tous depuis le 24/08 ; retards (3 max) pour l'historique.
        lags = a.get('retards_tous') or a.get('retards') or []
        if not lags:
            sans_ecart += 1
            continue
        book, cote, ecart = lags[0][0], float(lags[0][1]), float(lags[0][2])

        # Le joueur signalé donne le côté ; les noms viennent de l'uid, dont la
        # convention est <date>_<home>_<away>. On les retrouve via le résultat
        # plutôt que de découper l'uid, qui a connu trois conventions.
        joueur = a.get('joueur') or ''

        cle = f"{uid}|{book}|{a.get('palier')}"
        if cle in trades:
            continue
        premier = uid not in vus_match
        vus_match.add(uid)

        trades[cle] = {
            'id': cle, 'uid': uid, 'alerte_t': a.get('t'),
            'commence': a.get('commence'),
            'joueur': joueur, 'book': book, 'cote': cote,
            'ecart_pct': ecart, 'palier': a.get('palier'),
            'categorie': a.get('categorie'), 'tournoi': a.get('tournoi'),
            'lead_min': a.get('lead_min'), 'n_retards': len(lags),
            'premier_du_match': premier,
            'statut': 'OUVERT', 'gagne': None, 'pnl': None,
        }

    # ── Règlement ────────────────────────────────────────────────────────
    for tr in trades.values():
        ct = _dt(tr['commence'])
        # L'uid porte home_away ; le joueur signalé dit de quel côté on est.
        # winner() attend (home, away) : on interroge avec le joueur signalé
        # en premier, ResultIndex recalcule le côté à partir des noms.
        parts = str(tr['uid']).split('_', 1)
        reste = parts[1] if len(parts) > 1 else ''
        gagnant = None
        if tr['joueur'] and reste:
            # On teste le joueur signalé contre le reste de la paire.
            for autre in _autres_joueurs(reste, tr['joueur']):
                gagnant = idx.winner(tr['joueur'], autre, ct)
                if gagnant is not None:
                    break
        if gagnant is None:
            sans_resultat += 1
            continue
        gagne = (gagnant == 'home')       # 'home' = le joueur signalé
        tr['statut'] = 'REGLE'
        tr['gagne'] = gagne
        tr['pnl'] = (tr['cote'] - 1) if gagne else -1.0

    with open(OUT, 'w', encoding='utf-8') as f:
        for tr in trades.values():
            f.write(json.dumps(tr, ensure_ascii=False) + '\n')

    regles = [t for t in trades.values() if t['statut'] == 'REGLE']
    print()
    print("=" * 78)
    print("TRACK RECORD DU CANAL — ce qui a été PUBLIÉ, rien d'autre")
    print("=" * 78)
    print(f"  {len(alertes)} alerte(s) publiée(s)")
    print(f"  {sans_ecart} sans opérateur en retard -> rien à jouer "
          f"({100*sans_ecart/max(1,len(alertes)):.0f} % du volume publié)")
    print(f"  {len(trades)} pari(s) · {len(regles)} réglé(s) · "
          f"{sans_resultat} sans résultat connu")

    if len(regles) < 10:
        print("\n⏳ trop peu de paris réglés pour publier quoi que ce soit.")
        _ecrire(RAPPORT, alertes, trades, regles, sans_ecart, sans_resultat, {})
        return 0

    resume = {}
    print()
    print(f"  {'unité de compte':<26}{'n':>5}{'ROI':>9}{'IC95':>19}"
          f"{'réussite':>10}{'cote moy':>10}")
    print("-" * 78)
    for lab, lot in (('par ALERTE', regles),
                     ('par MATCH (1re alerte)',
                      [t for t in regles if t['premier_du_match']])):
        if len(lot) < 10:
            print(f"  {lab:<26}{len(lot):>5}   trop peu")
            continue
        pnl = [t['pnl'] for t in lot]
        roi, lo, hi = ic(pnl)
        hit = 100 * sum(1 for t in lot if t['gagne']) / len(lot)
        cote = st.mean(t['cote'] for t in lot)
        resume[lab] = {'n': len(lot), 'roi_pct': round(roi * 100, 2),
                       'ic': [round(lo * 100, 2), round(hi * 100, 2)],
                       'hit_pct': round(hit, 1), 'cote_moy': round(cote, 3),
                       'significatif': bool(lo > 0)}
        marque = '  ✅' if lo > 0 else ''
        print(f"  {lab:<26}{len(lot):>5}{roi*100:>+8.1f}%"
              f"  [{lo*100:>+6.1f} ; {hi*100:>+6.1f}]{hit:>9.1f}%{cote:>10.2f}{marque}")

    # Ventilation par catégorie : les Challengers dominent le volume et ne se
    # comportent pas comme un Grand Chelem.
    par_cat = collections.defaultdict(list)
    for t in regles:
        par_cat[t.get('categorie') or 'inconnu'].append(t['pnl'])
    if len(par_cat) > 1:
        print()
        print(f"  {'catégorie':<26}{'n':>5}{'ROI':>9}{'IC95':>19}")
        print("-" * 78)
        for cat, pnl in sorted(par_cat.items(), key=lambda x: -len(x[1])):
            if len(pnl) < 10:
                print(f"  {cat:<26}{len(pnl):>5}   trop peu")
                continue
            roi, lo, hi = ic(pnl)
            resume[f'cat:{cat}'] = {'n': len(pnl), 'roi_pct': round(roi * 100, 2),
                                    'ic': [round(lo * 100, 2), round(hi * 100, 2)]}
            print(f"  {cat:<26}{len(pnl):>5}{roi*100:>+8.1f}%"
                  f"  [{lo*100:>+6.1f} ; {hi*100:>+6.1f}]")

    print()
    print("  ⚠️ Ces chiffres décrivent le prix AFFICHÉ au moment de l'alerte.")
    print("  Rien ne garantit qu'il aurait été servi, ni pour quel montant.")
    print("  Un IC qui traverse zéro ne permet AUCUNE conclusion.")
    _ecrire(RAPPORT, alertes, trades, regles, sans_ecart, sans_resultat, resume)
    print(f"\n{OUT} · rapport dans {RAPPORT}")
    return 0


def _autres_joueurs(reste, joueur):
    """Candidats pour l'adversaire, depuis la partie 'home_away' de l'uid.

    L'uid ne dit pas où s'arrête un nom : « jurij_rodionov_kimmer_coppejans »
    peut se couper à plusieurs endroits. On teste toutes les coupures
    plausibles plutôt que de deviner — ResultIndex rejettera les mauvaises.
    """
    mots = reste.split('_')
    out = []
    for i in range(1, len(mots)):
        out.append(' '.join(mots[:i]))
        out.append(' '.join(mots[i:]))
    # Le joueur signalé lui-même n'est pas son propre adversaire.
    j = joueur.lower().replace('-', ' ')
    return [x for x in dict.fromkeys(out) if x and x.lower() != j]


def _ecrire(chemin, alertes, trades, regles, sans_ecart, sans_res, resume):
    json.dump({
        'genere_le': datetime.datetime.now(datetime.timezone.utc)
                     .replace(tzinfo=None).isoformat(timespec='seconds'),
        'source': LOG,
        'n_alertes': len(alertes), 'n_sans_ecart': sans_ecart,
        'n_paris': len(trades), 'n_regles': len(regles),
        'n_sans_resultat': sans_res, 'resume': resume,
    }, open(chemin, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    sys.exit(main())
