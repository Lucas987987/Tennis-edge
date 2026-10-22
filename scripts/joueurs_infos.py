#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
joueurs_infos.py — fiche d'identité des joueurs des feuilles de match (TennisApi) — 22/10/2026.

Pour chaque joueur rencontré dans feuilles/ et pas encore connu : main (gaucher /
droitier), taille, date de naissance, pays. UNE requête par joueur, une seule fois :
  /api/tennis/player/{id}   (repli : /api/tennis/team/{id})
Les champs sont cherchés où qu'ils soient dans la réponse (playerTeamInfo, team…),
car leur emplacement n'est pas documenté : « plays » (« left-handed »…),
« height » (mètres ou centimètres), « birthDateTimestamp » / « dateOfBirth ».
Les informations déjà présentes dans les fiches (homeTeam.playerTeamInfo, gardé par
le collecteur depuis le 22/10) évitent la requête.

Sortie : feuilles/joueurs.json {id: {nom, main, taille_cm, naissance, pays, maj}}.
Mêmes garde-fous que feuilles_match.py (budget, réserve de quota, 5 requêtes/s).
Usage : python scripts/joueurs_infos.py [budget]
"""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feuilles_match as FM  # noqa: E402

FICHIER = os.path.join(FM.DOSSIER, 'joueurs.json')


def chercher(doc, cles):
    """Première valeur (non vide) d'une des clés, n'importe où dans le JSON."""
    pile = [doc]
    while pile:
        x = pile.pop(0)
        if isinstance(x, dict):
            for k in cles:
                if x.get(k) not in (None, '', 0):
                    return x[k]
            pile.extend(x.values())
        elif isinstance(x, list):
            pile.extend(x)
    return None


def lire_infos(doc):
    """{main, taille_cm, naissance} depuis une réponse joueur ou un playerTeamInfo."""
    if not doc:
        return {}
    out = {}
    plays = chercher(doc, ('plays',))
    if isinstance(plays, str):
        p = plays.lower()
        out['main'] = 'gauche' if 'left' in p else ('droite' if 'right' in p else None)
    h = chercher(doc, ('height',))
    try:
        h = float(h)
        out['taille_cm'] = round(h * 100) if h < 3 else round(h)
        if not 140 <= out['taille_cm'] <= 230:
            out.pop('taille_cm')
    except (TypeError, ValueError):
        pass
    b = chercher(doc, ('birthDateTimestamp', 'dateOfBirthTimestamp', 'dateOfBirth'))
    try:
        out['naissance'] = dt.datetime.fromtimestamp(int(b), dt.timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        pass
    return {k: v for k, v in out.items() if v is not None}


def lire():
    try:
        with open(FICHIER, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def ecrire(J):
    os.makedirs(FM.DOSSIER, exist_ok=True)
    with open(FICHIER + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(J, f, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    os.replace(FICHIER + '.tmp', FICHIER)


def joueurs_des_feuilles():
    """{id: (nom, pays, infos déjà présentes dans les fiches)}."""
    out = {}
    import glob
    import gzip
    for p in sorted(glob.glob(os.path.join(FM.DOSSIER, '*.jsonl.gz'))):
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                for l in f:
                    r = json.loads(l)
                    for c in ('home', 'away'):
                        j = r.get(c) or {}
                        if j.get('id'):
                            out[str(j['id'])] = (j.get('nom'), j.get('pays'), j.get('infos') or {})
        except (OSError, ValueError):
            continue
    return out


def main(argv):
    cle = os.environ.get('RAPIDAPI_KEY', '').strip()
    budget = int(argv[1]) if len(argv) > 1 and argv[1] else int(os.environ.get('INFOS_BUDGET', '1500'))
    J = lire()
    vus = joueurs_des_feuilles()
    maintenant = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    a_faire = []
    for i, (nom, pays, infos) in vus.items():
        if i in J and J[i].get('main') and J[i].get('taille_cm'):
            continue
        lu = lire_infos(infos)
        if lu.get('main') and lu.get('taille_cm'):
            J[i] = dict(lu, nom=nom, pays=pays, maj=maintenant, source='fiche')
        elif J.get(i, {}).get('essais', 0) < 2:
            a_faire.append((i, nom, pays))
    print(f"Joueurs des feuilles : {len(vus)} · connus : {len(J)} · à demander : {len(a_faire)} (budget {budget})")
    if not cle:
        ecrire(J)
        print('RAPIDAPI_KEY absent : seules les infos des fiches sont reprises.')
        return 0
    c = FM.Client(cle, budget=budget)
    n_ok = 0
    try:
        for i, nom, pays in a_faire:
            code, doc = c.get(f"/api/tennis/player/{i}")
            info = lire_infos(doc) if code == 200 else {}
            if not info.get('main') and not info.get('taille_cm'):
                code, doc = c.get(f"/api/tennis/team/{i}")
                info = lire_infos(doc) if code == 200 else {}
            e = J.get(i, {})
            J[i] = dict(e, **info, nom=nom, pays=pays, maj=maintenant, essais=e.get('essais', 0) + 1, source='api')
            n_ok += bool(info)
    except FM.QuotaAtteint as e:
        print(f"::warning::Arrêt : {e}")
    ecrire(J)
    gauchers = sum(1 for v in J.values() if v.get('main') == 'gauche')
    print(f"Requêtes {c.n} · infos trouvées {n_ok} · total {len(J)} joueurs dont {gauchers} gauchers · quota restant {c.restant}")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
