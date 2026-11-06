#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sante_algo.py — contrôles quotidiens de l'algo et de ses données (06/11/2026, demande de Lucas), appelés par
scripts/health_check.py. Ces derniers jours, les pannes ont été trouvées par hasard (132 tournois mal placés, un
forfait en match du jour, une vidéo annulée, des fichiers absents de R2) : ce module les cherche chaque matin.

controles(racine, maintenant) → (alertes, infos), lignes courtes prêtes pour Telegram.
  — fraîcheur : site public (algo/donnees.json), feuilles de match, facteurs (jugement hebdomadaire) ;
  — volume : matchs du jour pronostiqués, matchs d'hier comparés au résultat ;
  — anomalies : tournois récents sans lieu, catégories TennisApi inconnues, matchs ATP / WTA / Challenger sans
    simulation, forfaits encore listés.
Ne lève jamais d'exception : un contrôle impossible devient une alerte.
"""
import datetime as dt
import glob
import gzip
import json
import os
import sys

CIRC = ('ATP', 'WTA', 'CH')
ANNULES = ('walkover', 'canceled', 'cancelled', 'postponed')


def _lire(p, defaut=None):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return defaut


def _age_h(iso, maintenant):
    try:
        t = dt.datetime.fromisoformat(str(iso).replace('Z', '+00:00'))
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        return (maintenant - t).total_seconds() / 3600
    except (TypeError, ValueError):
        return None


def feuilles_recentes(racine, depuis):
    out = []
    for p in sorted(glob.glob(os.path.join(racine, 'feuilles', '*.jsonl.gz'))):
        if os.path.basename(p)[:10] < depuis:
            continue
        try:
            with gzip.open(p, 'rt', encoding='utf-8') as f:
                out += [json.loads(l) for l in f if l.strip()]
        except (OSError, ValueError):
            continue
    return out


def controles(racine='.', maintenant=None):
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    if maintenant.tzinfo is None:
        maintenant = maintenant.replace(tzinfo=dt.timezone.utc)
    A, I = [], []
    auj = maintenant.date()
    hier = (auj - dt.timedelta(days=1)).isoformat()

    # 1. site public
    doc = _lire(os.path.join(racine, 'algo', 'donnees.json'), {}) or {}
    age = _age_h(doc.get('genere_le') or doc.get('maj'), maintenant)
    if age is None:
        A.append("❌ Site de l'algo : données illisibles")
    elif age > 4:
        A.append(f"❌ Site de l'algo : données vieilles de {age:.0f} h (pronostics du jour arrêtés ?)")
    else:
        I.append(f"✅ Site de l'algo à jour ({age:.1f} h)")
    M = [m for m in doc.get('matchs') or [] if m.get('circuit') in CIRC]
    sans_sim = [m for m in M if not m.get('simulation')]
    I.append(f"📊 {len(M)} matchs ATP/WTA/Challenger en ligne")
    if M and len(sans_sim) > max(2, len(M) // 10):
        A.append(f"⚠️ {len(sans_sim)} matchs sans simulation sur {len(M)} (ex. {sans_sim[0].get('home')} – {sans_sim[0].get('away')})")
    hier_juges = [x for x in (doc.get('apres_match') or {}).values() if str(x.get('debut', ''))[:10] == hier]
    if not hier_juges:
        A.append(f"⚠️ Aucun match d'hier ({hier}) comparé au résultat")
    else:
        ok = sum(1 for x in hier_juges if (x.get('ecarts') or {}).get('vainqueur_juste'))
        I.append(f"✅ Hier : {len(hier_juges)} matchs comparés au résultat ({ok} bons vainqueurs)")

    # 2. feuilles de match
    F = feuilles_recentes(racine, (auj - dt.timedelta(days=7)).isoformat())
    jours = sorted({r.get('jour') for r in F if r.get('jour')})
    if not jours or jours[-1] < hier:
        A.append(f"❌ Feuilles de match : dernière journée {jours[-1] if jours else 'aucune'} (collecte arrêtée ?)")
    else:
        I.append(f"✅ Feuilles de match jusqu'au {jours[-1]}")
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'simulateur'))
        import feuilles as FE
        inconnues = sorted({str(r.get('categorie')) for r in F if r.get('jour', '') >= hier
                            and FE.circuit_de(r.get('categorie')) == 'AUTRE'})
        if inconnues:
            A.append(f"⚠️ Catégorie TennisApi inconnue : {', '.join(inconnues[:3])} (hors bilans, à ranger ?)")
    except Exception as e:  # noqa: BLE001
        A.append(f"⚠️ Catégories non contrôlées ({type(e).__name__})")
    T = _lire(os.path.join(racine, 'feuilles', 'tournois.json'), {}) or {}
    recents = {str(r.get('tournoi_id')) for r in F if r.get('jour', '') >= (auj - dt.timedelta(days=3)).isoformat()}
    perdus = [v.get('nom') or k for k, v in T.items() if k in recents and v.get('lat') is None and v.get('ville')]
    if perdus:
        A.append(f"⚠️ {len(perdus)} tournoi(s) récent(s) sans lieu : {', '.join(map(str, perdus[:3]))}")
    nom_m = {(m.get('home'), m.get('away')) for m in M}
    annules = [r for r in F if r.get('jour', '') >= hier and str((r.get('statut') or {}).get('texte') or '').lower() in ANNULES
               and (r['home'].get('nom'), r['away'].get('nom')) in nom_m]
    if annules:
        A.append(f"⚠️ Forfait encore en ligne : {annules[0]['home'].get('nom')} – {annules[0]['away'].get('nom')}")

    # 3. jugement hebdomadaire des facteurs
    fa = _lire(os.path.join(racine, 'simulateur', 'facteurs.json'), {}) or {}
    age_f = _age_h(fa.get('genere_le'), maintenant)
    if age_f is None or age_f > 8 * 24:
        A.append(f"⚠️ Facteurs pas rejugés depuis {'?' if age_f is None else f'{age_f / 24:.0f} j'} (workflow « Pronostic » du lundi)")
    else:
        I.append(f"✅ Facteurs jugés il y a {age_f / 24:.1f} j")
    return A, I


def echecs_workflows(owner, repo, jeton, maintenant=None, heures=24):
    """[(workflow, conclusion, n, lien)] des runs ratés ou annulés sur les dernières heures."""
    import urllib.request
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    depuis = (maintenant - dt.timedelta(hours=heures)).strftime('%Y-%m-%dT%H:%M:%SZ')
    runs = []
    for page in (1, 2, 3):
        url = (f"https://api.github.com/repos/{owner}/{repo}/actions/runs?per_page=100&page={page}"
               f"&created=%3E%3D{depuis}")
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {jeton}', 'Accept': 'application/vnd.github+json',
                                                   'User-Agent': 'tennis-edge-sante'})
        with urllib.request.urlopen(req, timeout=20) as r:
            lot = json.loads(r.read()).get('workflow_runs', [])
        runs += lot
        if len(lot) < 100:
            break
    agg = {}
    for r in runs:
        c = r.get('conclusion')
        if c in ('failure', 'cancelled', 'timed_out', 'startup_failure'):
            k = (r.get('name') or '?', c)
            n, lien = agg.get(k, (0, r.get('html_url')))
            agg[k] = (n + 1, lien)
    return len(runs), [(n_, c_, n, lien) for (n_, c_), (n, lien) in sorted(agg.items(), key=lambda x: -x[1][0])]


if __name__ == '__main__':
    a, i = controles(sys.argv[1] if len(sys.argv) > 1 else '.')
    print('\n'.join(a + i))
