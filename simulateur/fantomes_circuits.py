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

12/11/2026 (audit, paquet 234) — CETTE RÈGLE EST REMPLACÉE PAR LA RÈGLE CUMULÉE, pour tous les signaux.
etude_regle_hebdomadaire.py a rejoué les deux règles semaine par semaine sur 2023 → juin 2026, avec un signal connu bon
(retour d'absence) et un signal au hasard de même taille : part des semaines passées dans le mauvais état, 38 % pour
« deux semaines de suite », 26 % pour la règle cumulée (en Challenger, le bon signal en place passait 78 % des semaines
HORS de l'algo avec l'ancienne règle, 1 % avec la nouvelle). La règle, pour chaque couple (signal, circuit) :
  EN PLACE → RETIRÉ dès que, depuis son adoption, sur au moins 300 matchs concernés, gain + 2 erreurs types < 0 ;
  EN ATTENTE → ADOPTÉ dès que, depuis le début du suivi (ou son dernier retrait), sur au moins 300 matchs concernés,
  gain − 2 erreurs types > 0 ; les compteurs repartent de zéro à chaque changement d'état ; entre les deux, rien ne
  change. Le gain est le gain PROPRE du signal (log loss sans lui − avec lui, les autres signaux en place).
  Départ des compteurs : 12/11/2026 (DEBUT_CUMUL). Un signal écarté par etude_signaux_reappris.py reste écarté.
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
           'favori_outsider', 'parcours_tournoi', 'favori_sous_estime', 'tiebreak', 'documentation_faible', 'format_match',
           'grand_chelem', 'qualifs_grand_chelem')
CIRCUITS = ('ATP', 'WTA', 'CH')
MIN_MATCHS, MARGE = 30, 0.001
SORTIE = os.path.join('simulateur', 'fantomes_circuits.json')
# 04/11/2026 — ADOPTION DIRECTE (décision de Lucas) : les signaux appris ENSEMBLE sur l'archive (etude_signaux_combines.py)
# sont en place dès le départ sur les circuits où le combiné gagne ≥ 0,001 sur 2023 →. Pas de période de fantôme ;
# RETRAIT : deux semaines de suite où, avec au moins 30 matchs concernés, la log loss affichée est PIRE d'au moins 0,001
# que sans eux (une semaine trop pauvre en matchs ne compte ni pour ni contre).
COMBINES = os.path.join('simulateur', 'rapport_signaux_combines.json')
# 11/11/2026 (paquet 228) — RÈGLE CUMULÉE pour les signaux listés ici. L'audit a montré que la règle « deux semaines de
# suite » retire à tort un signal qui vaut vraiment +0,005 dans 71 % des cas en 12 semaines (30 matchs par semaine) :
# son seuil de 0,001 est 17 fois sous le hasard d'une semaine. Pour ces signaux, jugés sur leur EFFET PROPRE :
#   RETIRÉ si, depuis l'adoption, sur au moins 300 matchs concernés, le gain est négatif d'au moins 2 erreurs types ;
#   sinon il reste en place. Une semaine isolée ne décide de rien.
REGLE_CUMULEE = SIGNAUX                                 # 12/11/2026 (paquet 234) : tous les signaux
DEBUT_CUMUL = '2026-11-12'                              # départ des compteurs de la règle cumulée     # 11/11/2026 (paquet 231) : + pente Grand Chelem (décision de Lucas)
CUMUL_MIN_MATCHS, CUMUL_ERREURS_TYPES = 300, 2.0
FORMAT = os.path.join('simulateur', 'format_match.json')
GRAND_CHELEM = os.path.join('simulateur', 'grand_chelem.json')
QUALIFS_GC = os.path.join('simulateur', 'qualifs_grand_chelem.json')
SIGNAUX_COMBINES = ('changement_surface', 'retour_absence', 'age', 'favori_outsider')


REAPPRIS = os.path.join('simulateur', 'rapport_signaux_reappris.json')


def reappris(racine):
    """12/11/2026 (paquet 233, etude_signaux_reappris.py) — ({(signal, circuit)} en place, {(signal, circuit)} écartés)
    sur les circuits où la configuration réapprise contre l'Elo de production est adoptée. Un signal écarté n'est plus
    appliqué sur ce circuit et la règle hebdomadaire ne peut pas le réadopter : il faudrait une nouvelle étude."""
    try:
        with open(os.path.join(racine, REAPPRIS), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        return set(), set()
    places, ecartes = set(), set()
    for c, v in (doc.get('circuits') or {}).items():
        if not (v or {}).get('adopte'):
            continue
        places |= {(s, c) for s in (v.get('signaux_gardes') or []) + (v.get('signaux_en_sursis') or [])}
        ecartes |= {(s, c) for s in (v.get('signaux_ecartes') or [])}
    return places, ecartes


def directs(racine):
    """{(signal, circuit)} adoptés directement par l'étude combinée."""
    return (_directs(racine) | reappris(racine)[0]) - reappris(racine)[1]


def _directs(racine):
    try:
        with open(os.path.join(racine, COMBINES), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = {}
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
    try:                                                    # 05/11/2026 (Lucas) : matchs peu documentés, adoptés directement
        with open(os.path.join(racine, 'simulateur', 'rapport_documentation.json'), encoding='utf-8') as f:
            for c, v in (json.load(f).get('circuits') or {}).items():
                if v.get('adopte'):
                    out.add(('documentation_faible', c))
    except (OSError, ValueError):
        pass
    try:                                                    # 05/11/2026 (Lucas) : tie-breaks du Challenger, adoptés directement
        with open(os.path.join(racine, 'simulateur', 'rapport_tiebreaks.json'), encoding='utf-8') as f:
            tbr = json.load(f)
        for c, v in (tbr.get('circuits') or {}).items():
            if v.get('retenu_pour_fantome'):
                out.add(('tiebreak', c))
    except (OSError, ValueError):
        pass
    try:                                                    # 11/11/2026 (paquet 228) : pente de l'Elo selon le format du match
        with open(os.path.join(racine, FORMAT), encoding='utf-8') as f:
            for c, v in (json.load(f).get('pentes') or {}).items():
                if v:
                    out.add(('format_match', c))
    except (OSError, ValueError, AttributeError):
        pass
    try:                                                    # 11/11/2026 (paquet 231) : pente Grand Chelem (décision de Lucas)
        with open(os.path.join(racine, GRAND_CHELEM), encoding='utf-8') as f:
            for c, v in (json.load(f).get('pentes') or {}).items():
                if v:
                    out.add(('grand_chelem', c))
    except (OSError, ValueError, AttributeError):
        pass
    try:                                                    # 11/11/2026 (paquet 232) : pente des qualifications de Grand Chelem
        with open(os.path.join(racine, QUALIFS_GC), encoding='utf-8') as f:
            for c, v in (json.load(f).get('pentes') or {}).items():
                if v:
                    out.add(('qualifs_grand_chelem', c))
    except (OSError, ValueError, AttributeError):
        pass
    return out


def retrait_cumule(v):
    """Règle cumulée (REGLE_CUMULEE) : True si le signal doit être retiré d'après son bilan depuis l'adoption."""
    n, g, et = v.get('matchs_total') or 0, v.get('gain_total'), v.get('erreur_type_total')
    return bool(n >= CUMUL_MIN_MATCHS and g is not None and et is not None and g + CUMUL_ERREURS_TYPES * et < 0)


def entree_cumulee(v):
    """12/11/2026 (paquet 234) — entrée d'un signal en attente : au moins 300 matchs concernés depuis le début de son
    suivi (ou son dernier retrait) et gain propre positif de plus de 2 erreurs types."""
    n, g, et = v.get('matchs_total') or 0, v.get('gain_total'), v.get('erreur_type_total')
    return bool(n >= CUMUL_MIN_MATCHS and g is not None and et is not None and g - CUMUL_ERREURS_TYPES * et > 0)


DOSSIER_BILANS = os.path.join('simulateur', 'journal_pronostics', 'apres_match')


def paires(bilan, signal):
    """(log loss sans le signal, avec le signal) pour ce match, ou None."""
    e = bilan.get('ecarts') or {}
    f = e.get('fantome_' + signal)
    if f and f.get('ll_elo') is not None and f.get('ll_reference') is not None:
        return f['ll_elo'], f['ll_reference']
    sc = e.get('signaux_circuit') or {}
    if signal in (sc.get('appliques') or []) and sc.get('ll_sans') is not None and sc.get('ll_affiche') is not None:
        if signal in REGLE_CUMULEE:                         # jugé sur son effet propre, pas sur celui de tous les signaux
            seul = (sc.get('sans_chacun') or {}).get(signal)
            return (seul, sc['ll_affiche']) if seul is not None else None
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


def verdicts(bilans, aujourdhui, depuis=None):
    """depuis : {« signal|circuit »: date ISO} — début du compteur cumulé de ce couple (DEBUT_CUMUL par défaut)."""
    debut, fin = semaine_jugee(aujourdhui)
    out = {}
    for sgn in SIGNAUX:
        for c in CIRCUITS:
            tout, sem = [], []
            depuis_ = (depuis or {}).get(f'{sgn}|{c}') or DEBUT_CUMUL
            for b in bilans:
                if b.get('circuit') != c:
                    continue
                pr = paires(b, sgn)
                jour = str(b.get('debut') or '')[:10]
                if pr is None or not jour or jour >= fin.isoformat() or jour < depuis_:
                    continue
                tout.append(pr)
                if jour >= debut.isoformat():
                    sem.append(pr)
            g = lambda L: round(sum(a - b for a, b in L) / len(L), 5) if L else None
            gs, gt = g(sem), g(tout)
            ok = len(sem) >= MIN_MATCHS and gs is not None and gs >= MARGE and gt is not None and gt >= MARGE
            et = None                                       # 11/11/2026 : erreur type du gain depuis le début (règle cumulée)
            if len(tout) >= 2:
                d_ = [a - b for a, b in tout]
                m_ = sum(d_) / len(d_)
                et = round((sum((x - m_) ** 2 for x in d_) / len(d_)) ** .5 / len(d_) ** .5, 5)
            out[f'{sgn}|{c}'] = {'adopte': ok, 'matchs_semaine': len(sem), 'gain_semaine': gs, 'depuis': depuis_,
                                 'matchs_total': len(tout), 'gain_total': gt, 'erreur_type_total': et,
                                 'raison': (f"{c} · semaine du {debut.isoformat()} : {len(sem)} matchs, gain {gs} ; "
                                            f"depuis le début : {len(tout)} matchs, gain {gt}")}
    return out


def _retire(d):
    """Retrait qui compte : celui de la règle cumulée (il porte la date « depuis »). Un retrait prononcé par l'ancienne
    règle « deux semaines de suite » (sans date) est annulé le 12/11/2026 (paquet 234) : l'étude montre qu'elle sortait
    un bon signal par hasard ; le signal revient à son adoption directe et la règle cumulée le juge depuis DEBUT_CUMUL."""
    return bool((d or {}).get('retire') and (d or {}).get('depuis'))


def lire(racine):
    """{signal: [circuits où il est adopté]} — utilisé par le pronostic du jour."""
    try:
        with open(os.path.join(racine, SORTIE), encoding='utf-8') as f:
            doc = json.load(f)
    except (OSError, ValueError):
        doc = {}
    out = {}
    dec = doc.get('decisions') or {}
    ecartes = reappris(racine)[1]                           # 12/11/2026 : écartés par l'étude des signaux réappris
    for cle, d in dec.items():
        if (d or {}).get('adopte'):
            sgn, c = cle.split('|')
            if (sgn, c) not in ecartes:
                out.setdefault(sgn, []).append(c)
    for sgn, c in sorted(directs(racine)):                 # adoption directe, sauf retrait constaté
        if not _retire(dec.get(f'{sgn}|{c}')) and c not in out.get(sgn, []):
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
    chemin = os.path.join(racine, SORTIE)
    try:
        ancien = json.load(open(chemin, encoding='utf-8')).get('decisions') or {}
    except (OSError, ValueError):
        ancien = {}
    D = directs(racine)
    ecartes = reappris(racine)[1]
    fin = semaine_jugee(aujourdhui)[1].isoformat()
    V = verdicts(lire_bilans(racine), aujourdhui, {cle: (d or {}).get('depuis') for cle, d in ancien.items()})
    dec = {}
    for cle, v in V.items():
        sgn, c = cle.split('|')
        a = ancien.get(cle) or {}
        if (sgn, c) in ecartes:                             # 12/11/2026 (paquet 233) : ni appliqué, ni réadoptable
            dec[cle] = {'adopte': False, 'ecarte': True,
                        'raison': "écarté par l'étude des signaux réappris sur l'Elo de production (rapport_signaux_reappris.json)"}
            continue
        # 12/11/2026 (paquet 234) — RÈGLE CUMULÉE pour tous les signaux (etude_regle_hebdomadaire.py)
        direct = (sgn, c) in D and not _retire(a)
        en_place = direct or bool(a.get('adopte'))
        bilan = f"{v['raison']} — depuis le {v['depuis']}, erreur type {v.get('erreur_type_total')}"
        garde = dict({'depuis': a['depuis']} if a.get('depuis') else {}, **({'retire': True} if _retire(a) else {}))
        if en_place and retrait_cumule(v):
            dec[cle] = {'adopte': False, 'retire': True, 'depuis': fin, 'stabilite': 'retiré',
                        'raison': bilan + f" : négatif de {CUMUL_ERREURS_TYPES:g} erreurs types sur ≥ {CUMUL_MIN_MATCHS} matchs, retiré"}
        elif en_place:
            dec[cle] = dict(garde, adopte=True, direct=direct, stabilite='en place', raison=bilan + ' : en place')
        elif entree_cumulee(v):
            dec[cle] = dict(garde, adopte=True, depuis=fin, stabilite='adopté',
                            raison=bilan + f" : positif de {CUMUL_ERREURS_TYPES:g} erreurs types sur ≥ {CUMUL_MIN_MATCHS} matchs, adopté")
        else:
            dec[cle] = dict(garde, adopte=False, stabilite='en attente', raison=bilan + ' : en attente')
    doc = {'genere_le': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
           'regle': (f"par signal et par circuit, règle cumulée : en place → retiré si, depuis son adoption, sur au moins "
                     f"{CUMUL_MIN_MATCHS} matchs concernés, le gain propre est négatif de plus de {CUMUL_ERREURS_TYPES:g} erreurs "
                     f"types ; en attente → adopté si, sur au moins {CUMUL_MIN_MATCHS} matchs, il est positif de plus de "
                     f"{CUMUL_ERREURS_TYPES:g} erreurs types ; compteurs remis à zéro à chaque changement ; un signal adopté ne "
                     "touche que son circuit"),
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
