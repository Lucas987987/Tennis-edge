#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fantomes_circuits.py — chaque signal est jugé SÉPARÉMENT sur l'ATP, la WTA et le Challenger (04/11/2026, décision de
Lucas : « les analyses doivent être faites indépendamment du circuit ; si un signal est positif sur un circuit, on doit
l'utiliser sur ce circuit »).

Signaux suivis (modèles fantômes, jamais affichés avant adoption) :
  forme_service       — service / retour du moment (forme_service.py)
  entree              — statut d'entrée (invité en Challenger, qualifié en ATP)
  serveuses_wta       — profil serveur contre non-serveur (WTA seulement par construction)
  elo_service_retour  — Elo au service et au retour (elo_service_retour.py), β = 0,284
  forme_set           — (04/11/2026) ATP : relâchement du joueur qui mène d'un set ; ne change que la FORME du match
                        (sets, tie-break), jugée sur la vraisemblance de la forme réelle ; adopté → intégré au calcul des
                        scores (distribution_exacte.py), pas à la probabilité de victoire
  changement_surface  — (04/11/2026) 1er ou 2e match sur une surface depuis un changement (etude_changement_surface.py),
                        β par circuit (ATP −0,172, WTA −0,114, Challenger −0,171)
  retour_absence      — (04/11/2026) retour après 45 jours ou plus sans match (etude_retour_absence.py), poids 1, 1/2,
                        1/4 sur les trois premiers matchs, β court / long par circuit
  age                 — (04/11/2026) années au-delà de 30 ans et sous 23 ans (etude_age.py), β par circuit
  favori_outsider     — (04/11/2026) résidu propre au joueur dans son rôle du match (etude_profils_contexte.py)

Chaque match joué donne, pour un signal et le circuit du match : log loss SANS le signal et AVEC lui
(apres_match : fantome_<signal> tant qu'il n'est pas adopté sur ce circuit, signaux_circuit une fois appliqué).

RÈGLE FIXÉE LE 04/11/2026, AVANT TOUT RÉSULTAT DE CETTE PROCÉDURE, pour chaque couple (signal, circuit) :
  semaine gagnante si, sur la dernière semaine complète (lundi → dimanche), au moins 30 matchs concernés,
  gain de log loss ≥ 0,001 sur la semaine ET gain ≥ 0,001 sur TOUS les matchs concernés depuis le début du suivi
  (garde-fou contre une bonne semaine de hasard : 4 signaux × 3 circuits = 12 essais chaque semaine) ;
  ADOPTÉ sur ce circuit après deux semaines gagnantes de suite (stabilite.py, série « circuit|signal|circuit ») ;
  RETIRÉ après deux semaines de suite sans gain (même série). Un signal adopté ne touche QUE son circuit.
"""
import datetime as dt
import glob
import gzip
import json
import os
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

SIGNAUX = ('forme_service', 'entree', 'serveuses_wta', 'elo_service_retour', 'forme_set', 'changement_surface', 'retour_absence', 'age',
           'favori_outsider', 'parcours_tournoi', 'favori_sous_estime')
CIRCUITS = ('ATP', 'WTA', 'CH')
MIN_MATCHS, MARGE = 30, 0.001
SORTIE = os.path.join('simulateur', 'fantomes_circuits.json')
# 04/11/2026 — ADOPTION DIRECTE (décision de Lucas) : les signaux appris ENSEMBLE sur l'archive (etude_signaux_combines.py)
# sont en place dès le départ sur les circuits où le combiné gagne ≥ 0,001 sur 2023 →. Pas de période de fantôme ;
# RETRAIT : deux semaines de suite où, avec au moins 30 matchs concernés, la log loss affichée est PIRE d'au moins 0,001
# que sans eux (une semaine trop pauvre en matchs ne compte ni pour ni contre).
COMBINES = os.path.join('simulateur', 'rapport_signaux_combines.json')
SIGNAUX_COMBINES = ('changement_surface', 'retour_absence', 'age', 'favori_outsider')


def directs(racine):
    """{(signal, circuit)} adoptés directement par l'étude combinée."""
    try:
        with open(os.path.join(racine, COMBINES), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return set()
    out = {(s, c) for c, v in (doc.get('circuits') or {}).items() if v.get('adopte') for s in SIGNAUX_COMBINES}
    try:                                                    # pistes ajoutées au combiné (etude_pistes_tournoi.py)
        with open(os.path.join(racine, 'simulateur', 'rapport_pistes_tournoi.json'), encoding='utf-8') as f:
            pistes = json.load(f)
        for c, v in (pistes.get('circuits') or {}).items():
            for nom in ('parcours_tournoi', 'montee_petits_tournois'):
                if (v.get(nom) or {}).get('adoptee'):
                    out.add((nom, c))
    except (OSError, ValueError):
        pass
    return out
DOSSIER_BILANS = os.path.join('simulateur', 'journal_pronostics', 'apres_match')


def paires(bilan, signal):
    """(log loss sans le signal, avec le signal) pour ce match, ou None."""
    e = bilan.get('ecarts') or {}
    f = e.get('fantome_' + signal)
    if f and f.get('ll_elo') is not None and f.get('ll_reference') is not None:
        return f['ll_elo'], f['ll_reference']
    sc = e.get('signaux_circuit') or {}
    if signal in (sc.get('appliques') or []) and sc.get('ll_sans') is not None and sc.get('ll_affiche') is not None:
        return sc['ll_sans'], sc['ll_affiche']
    return None


def lire_bilans(racine):
    out = []
    for chemin in sorted(glob.glob(os.path.join(racine, DOSSIER_BILANS, '*.json.gz'))):
        try:
            with gzip.open(chemin, 'rt', encoding='utf-8') as f:
                out.extend(json.load(f).values())
        except (OSError, ValueError):
            continue
    return out


def semaine_jugee(aujourdhui):
    lundi = aujourdhui - dt.timedelta(days=aujourdhui.weekday())
    return lundi - dt.timedelta(days=7), lundi


def verdicts(bilans, aujourdhui):
    debut, fin = semaine_jugee(aujourdhui)
    out = {}
    for sgn in SIGNAUX:
        for c in CIRCUITS:
            tout, sem = [], []
            for b in bilans:
                if b.get('circuit') != c:
                    continue
                pr = paires(b, sgn)
                jour = str(b.get('debut') or '')[:10]
                if pr is None or not jour or jour >= fin.isoformat():
                    continue
                tout.append(pr)
                if jour >= debut.isoformat():
                    sem.append(pr)
            g = lambda L: round(sum(a - b for a, b in L) / len(L), 5) if L else None
            gs, gt = g(sem), g(tout)
            ok = len(sem) >= MIN_MATCHS and gs is not None and gs >= MARGE and gt is not None and gt >= MARGE
            out[f'{sgn}|{c}'] = {'adopte': ok, 'matchs_semaine': len(sem), 'gain_semaine': gs,
                                 'matchs_total': len(tout), 'gain_total': gt,
                                 'raison': (f"{c} · semaine du {debut.isoformat()} : {len(sem)} matchs, gain {gs} ; "
                                            f"depuis le début : {len(tout)} matchs, gain {gt}")}
    return out


def lire(racine):
    """{signal: [circuits où il est adopté]} — utilisé par le pronostic du jour."""
    try:
        with open(os.path.join(racine, SORTIE), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = {}
    out = {}
    dec = doc.get('decisions') or {}
    for cle, d in dec.items():
        if (d or {}).get('adopte'):
            sgn, c = cle.split('|')
            out.setdefault(sgn, []).append(c)
    for sgn, c in sorted(directs(racine)):                 # adoption directe, sauf retrait constaté
        if not (dec.get(f'{sgn}|{c}') or {}).get('retire') and c not in out.get(sgn, []):
            out.setdefault(sgn, []).append(c)
    return out


def message(doc):
    L = ['<b>Signaux par circuit</b> (jugés séparément sur ATP, WTA, Challenger)']
    for cle, d in sorted((doc.get('decisions') or {}).items()):
        v = (doc.get('semaine') or {}).get(cle) or {}
        if v.get('matchs_total'):
            L.append(f"{cle.replace('|', ' · ')} : {'✅ ' if d.get('adopte') else ''}{d.get('stabilite', '')} — "
                     f"{v['matchs_semaine']} m. semaine ({v['gain_semaine']}), {v['matchs_total']} au total ({v['gain_total']})")
    return '\n'.join(L)


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    racine = args[0] if args else os.path.join(ICI, '..')
    aujourdhui = dt.date.fromisoformat(os.environ['FANTOMES_JOUR']) if os.environ.get('FANTOMES_JOUR') else dt.date.today()
    import stabilite as ST
    chemin = os.path.join(racine, SORTIE)
    try:
        ancien = json.load(open(chemin, encoding='utf-8')).get('decisions') or {}
    except (OSError, ValueError):
        ancien = {}
    V = verdicts(lire_bilans(racine), aujourdhui)
    etat_path = os.path.join(racine, 'simulateur', 'stabilite.json')
    etat = ST.lire(etat_path)
    D = directs(racine)
    lundi_juge = semaine_jugee(aujourdhui)[0].isocalendar()
    sem = f'{lundi_juge[0]}-W{lundi_juge[1]:02d}'           # la semaine JUGÉE (rejouable, une décision par semaine)
    dec = {}
    for cle, v in V.items():
        sgn, c = cle.split('|')
        if (sgn, c) in D and not (ancien.get(cle) or {}).get('retire'):
            k_st = 'circuit|' + cle
            if k_st not in etat or not (ancien.get(cle) or {}).get('direct'):
                etat[k_st] = {'adopte': True, 'semaine': None, 'serie_avant': 0, 'serie': 0}
            if v['matchs_semaine'] < MIN_MATCHS:
                dec[cle] = dict(ancien.get(cle) or {}, adopte=True, direct=True, raison=v['raison'] + ' — trop peu de matchs cette semaine : en place')
                continue
            perte = -(v['gain_semaine'] or 0.0)
            v_ = dict(v, adopte=perte < MARGE, ll={'avec': 1.0 + perte, 'sans': 1.0})
            d_ = ST.appliquer(etat, k_st, {'adopte': True}, v_, semaine=sem)
            d_['direct'] = True
            if not d_['adopte']:
                d_['retire'] = True
            dec[cle] = d_
        else:
            dec[cle] = ST.appliquer(etat, 'circuit|' + cle, ancien.get(cle), v)
    ST.ecrire(etat, etat_path)
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': ("par signal et par circuit : semaine gagnante si ≥ 30 matchs, gain ≥ 0,001 sur la semaine et ≥ 0,001 "
                     "depuis le début ; adopté après deux semaines gagnantes de suite, retiré après deux sans gain ; "
                     "un signal adopté ne touche que son circuit"),
           'semaine': V, 'decisions': dec}
    with open(chemin, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    txt = message(doc)
    print(txt.replace('<b>', '').replace('</b>', ''))
    if '--telegram' in argv:
        import urllib.parse
        import urllib.request
        tok, chat = os.environ.get('TELEGRAM_TOKEN'), os.environ.get('TELEGRAM_CHAT_ID')
        if tok and chat:
            try:
                from bilan_algo import texte_telegram
                for m in texte_telegram(txt):
                    data = urllib.parse.urlencode({'chat_id': chat, 'text': m, 'parse_mode': 'HTML'}).encode()
                    urllib.request.urlopen(f'https://api.telegram.org/bot{tok}/sendMessage', data=data, timeout=20).read()
            except Exception as e:  # noqa: BLE001
                print(f'::warning::Telegram impossible ({type(e).__name__})')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
