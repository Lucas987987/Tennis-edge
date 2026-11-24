#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
journaux_chauds.py — les journaux en ajout seul réécrits à chaque collecte passent par Cloudflare R2 ; git n'en reçoit
qu'une photo toutes les ~2 h (24/11/2026, paquet 416, Lucas : « stocker sur Cloudflare comme le reste »).

POURQUOI. Mesure du 23/11 (croissance_depot.json, 24 h) : le registre Kalshi du jour (67 versions), celui de
Polymarket (44) et le journal mensuel des alertes de cotes (53) étaient recommités à chaque passage de leur collecteur :
~70 Mo de nouvelles versions par jour. Même méthode que etat_chaud.py (états chauds) et le paquet 414 (pronostics).

FICHIERS « CHAUDS » (seule la partition en cours bouge ; les anciennes restent dans git, figées) :
  kalshi      registres_marches/kalshi_<jour>.jsonl         rédacteur : kalshi_collector.yml
  polymarket  registres_marches/polymarket_<jour>.jsonl     rédacteur : polymarket_collector.yml
  alertes     odds_alerts_log/odds_alerts_log_<mois>.jsonl  rédacteur : capture_closing.yml (odds_movement.py)
  (jour et mois UTC ; la partition de la veille / du mois précédent est aussi suivie, pour le passage de minuit)

ACTIONS
  pull GROUPE    au début : la copie R2 (préfixe « chaud/journaux/ ») complète la copie git — UNION des lignes, ordre de
                 R2 d'abord puis les lignes que seul git a (rien ne se perd, jamais de doublon).
  push GROUPE    à la fin (rédacteur seul) : la copie locale part sur R2.
  garde GROUPE   après « git add » : la partition chaude n'est gardée dans le commit que si la dernière photo git a plus
                 de JOURNAUX_INTERVALLE_MIN minutes (110 par défaut) ; « --lecteur » : jamais (un lecteur qui a
                 rapatrié la copie R2 ne la republie pas).
SANS SECRETS R2 : pull et push ne font rien et garde laisse tout passer (comportement d'avant). Journaux Actions :
des nombres seulement, jamais le contenu.

Usage : python scripts/journaux_chauds.py pull|push|garde [--lecteur] GROUPE
"""
import datetime as dt
import os
import subprocess
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)

PREFIXE = 'chaud/journaux/'
INTERVALLE_MIN = float(os.environ.get('JOURNAUX_INTERVALLE_MIN', '110'))
MODELES = {
    'kalshi': ('registres_marches/kalshi_{jour}.jsonl',),
    'polymarket': ('registres_marches/polymarket_{jour}.jsonl',),
    'alertes': ('odds_alerts_log/odds_alerts_log_{mois}.jsonl',),
}


def fichiers(groupe, maintenant=None):
    """Chemins chauds du groupe : partition en cours et celle d'avant (passage de minuit ou de fin de mois)."""
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    out = []
    for t in (maintenant - dt.timedelta(days=1), maintenant):
        for m in MODELES[groupe]:
            p = m.format(jour=t.strftime('%Y-%m-%d'), mois=t.strftime('%Y-%m'))
            if p not in out:
                out.append(p)
    return out


def union(r2_texte, local_texte):
    """Ajout seul : si une copie prolonge l'autre, la plus longue telle quelle (cas normal, octet pour octet). Sinon,
    lignes de R2 dans leur ordre, puis celles que seule la copie locale a (sans doublon)."""
    r2_texte, local_texte = r2_texte or '', local_texte or ''
    if local_texte.startswith(r2_texte):
        return local_texte
    if r2_texte.startswith(local_texte):
        return r2_texte
    vues, out = set(), []
    for t in (r2_texte, local_texte):
        for l in (t or '').splitlines():
            if l.strip() and l not in vues:
                vues.add(l)
                out.append(l)
    return ''.join(x + '\n' for x in out)


def _client():
    try:
        import r2_io
        return r2_io.client()
    except Exception:  # noqa: BLE001 — sans R2, rien ne change
        return None


def pull(r2, groupe, racine='.'):
    n = 0
    for rel in fichiers(groupe):
        got = r2.get_with_etag(PREFIXE + rel)
        if got is None:
            continue
        p = os.path.join(racine, rel)
        local = open(p, encoding='utf-8').read() if os.path.exists(p) else ''
        fus = union(got[0].decode('utf-8', 'replace'), local)
        if fus != local:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', encoding='utf-8') as f:
                f.write(fus)
            n += 1
    print(f"Journaux chauds ({groupe}) : {n} fichier(s) complété(s) depuis R2")
    return n


def push(r2, groupe, racine='.'):
    n = 0
    for rel in fichiers(groupe):
        p = os.path.join(racine, rel)
        if not os.path.exists(p):
            continue
        with open(p, 'rb') as f:
            data = f.read()
        got = r2.get_with_etag(PREFIXE + rel)
        if got is not None and got[0] == data:
            continue
        r2.put(PREFIXE + rel, data, content_type='application/x-ndjson')
        n += 1
    print(f"Journaux chauds ({groupe}) : {n} fichier(s) envoyé(s) à R2")
    return n


def derniere_photo(rel, racine='.'):
    r = subprocess.run(['git', 'log', '-1', '--format=%ct', '--', rel], capture_output=True, text=True, cwd=racine)
    try:
        return int(r.stdout.strip() or 0)
    except ValueError:
        return 0


def garde(groupe, racine='.', lecteur=False, maintenant=None, r2=None):
    """Retire du commit les partitions chaudes trop récentes ; renvoie le nombre retiré. Un rédacteur ne retire une
    partition que si R2 en a EXACTEMENT la même copie (envoi réussi) : sinon git la garde, rien ne se perd."""
    maintenant = maintenant if maintenant is not None else time.time()
    n = 0
    for rel in fichiers(groupe):
        indexe = subprocess.run(['git', 'diff', '--cached', '--quiet', '--', rel], cwd=racine).returncode != 0
        if not indexe:
            continue
        if not lecteur:
            p = os.path.join(racine, rel)
            got = r2.get_with_etag(PREFIXE + rel) if r2 is not None else None
            if got is None or not os.path.exists(p) or got[0] != open(p, 'rb').read():
                continue
        if lecteur or maintenant - derniere_photo(rel, racine) < INTERVALLE_MIN * 60:
            subprocess.run(['git', 'reset', '-q', '--', rel], cwd=racine)
            n += 1
    print(f"Journaux chauds ({groupe}) : {n} fichier(s) gardé(s) hors de ce commit (photo git toutes les "
          f"{INTERVALLE_MIN:g} min ; R2 est à jour)")
    return n


def main(argv):
    lecteur = '--lecteur' in argv
    args = [a for a in argv[1:] if a != '--lecteur']
    if len(args) != 2 or args[0] not in ('pull', 'push', 'garde') or args[1] not in MODELES:
        print('Usage : journaux_chauds.py pull|push|garde [--lecteur] ' + '|'.join(MODELES))
        return 2
    action, groupe = args
    r2 = _client()
    if action == 'garde':
        if r2 is None:
            print(f"Journaux chauds ({groupe}) : R2 indisponible — git garde tout, comme avant")
            return 0
        garde(groupe, lecteur=lecteur, r2=r2)
        return 0
    if r2 is None:
        print(f"Journaux chauds ({groupe}) : R2 indisponible — rien à faire")
        return 0
    (pull if action == 'pull' else push)(r2, groupe)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
