#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pipeline_status.py — Rend l'état du pipeline LISIBLE DEPUIS LE REPO.

POURQUOI CE SCRIPT
Toutes les pannes de ce projet ont la même signature : rien ne plante, tout est
vide, et il faut ouvrir les logs GitHub Actions pour s'en apercevoir — souvent
des jours plus tard.
  - 14/08 : push bloqué 5 jours (>100 Mo), avalé par "git push || true"
  - 15/08 : commit écarté en silence par "git pull --rebase" après commit
  - 15/08 : "git add" en bloc qui échoue si UN fichier manque
  - 16/08 : book_curves_live.jsonl absent -> sorties vides, aucun code d'erreur
  - 16/08 : resultats.json à "count": 0 depuis des semaines
Le point commun n'est pas la cause, c'est l'INVISIBILITÉ. Ce script inverse le
défaut : après chaque run, l'état de chaque livrable est écrit dans un fichier
COMMITÉ, donc consultable depuis GitHub sans ouvrir un seul log.

VERDICTS
  ✅ OK      — présent, non vide, écrit pendant ce run
  ⏳ FIGÉ    — présent mais pas réécrit pendant ce run (le script n'a rien produit)
  ⚠️ VIDE    — présent mais réduit à son en-tête / 0 entrée
  ❌ ABSENT  — pas produit du tout

SORTIES : pipeline_status.json (machine) + pipeline_status.md (lisible sur GitHub)

Env : RUN_STARTED (ISO 8601, injecté par le workflow — sert à distinguer
      "réécrit pendant ce run" de "figé depuis un run précédent"), OUT_JSON, OUT_MD.
"""
import os, json, glob, datetime

OUT_JSON = os.environ.get('OUT_JSON', 'pipeline_status.json')
OUT_MD   = os.environ.get('OUT_MD', 'pipeline_status.md')

# (chemin, libellé, seuil d'octets sous lequel on considère le fichier vide)
ARTIFACTS = [
    ('set_results.json',          'Résultats match + set',              200),
    ('resultats_derived.json',    'Pont résultats (études)',            200),
    ('paper_trades_match.jsonl',  'Journal forward — match',             50),
    ('paper_trades_set1.jsonl',   'Journal forward — set 1',             50),
    ('paper_trades_set2.jsonl',   'Journal forward — set 2',              0),
    ('moves_detail.csv',          'Audit des moves (live)',             200),
    ('moves_detail_hist.csv',     'Audit des moves (historique)',       200),
    ('canal_clv_detail.csv',      'CLV réalisé du canal public',        100),
    ('book_curves_live.jsonl',    'Courbes live reconstruites',        1000),
]


def _run_started():
    s = os.environ.get('RUN_STARTED', '')
    try:
        return datetime.datetime.fromisoformat(s.replace('Z', ''))
    except Exception:
        # Repli : tout fichier touché dans la dernière heure compte comme "ce run"
        return datetime.datetime.utcnow() - datetime.timedelta(hours=1)


def _lines(path):
    try:
        if path.endswith('.json'):
            d = json.load(open(path, encoding='utf-8'))
            if isinstance(d, dict):
                return len(d.get('results', d))
            return len(d)
        with open(path, encoding='utf-8', errors='replace') as f:
            return sum(1 for l in f if l.strip())
    except Exception:
        return None


def inspect(started):
    rows = []
    for path, label, min_bytes in ARTIFACTS:
        r = {'fichier': path, 'libellé': label}
        if not os.path.exists(path):
            r.update(verdict='❌ ABSENT', octets=0, lignes=0, ecrit_ce_run=False)
            rows.append(r); continue
        size = os.path.getsize(path)
        mtime = datetime.datetime.utcfromtimestamp(os.path.getmtime(path))
        fresh = mtime >= started
        n = _lines(path)
        if size <= min_bytes or not n:
            verdict = '⚠️ VIDE'
        elif not fresh:
            verdict = '⏳ FIGÉ'
        else:
            verdict = '✅ OK'
        r.update(verdict=verdict, octets=size, lignes=n, ecrit_ce_run=fresh,
                 modifie=mtime.isoformat(timespec='seconds'))
        rows.append(r)
    return rows


def partitions_health():
    """Surveille la trajectoire de taille du repo : c'est ce qui a bloqué tous
    les push pendant 5 jours en août. Une partition >90 Mo est en zone rouge
    (mur dur GitHub : 100 Mo par fichier)."""
    out = {'total_mo': 0.0, 'zone_rouge': [], 'n_partitions': 0}
    for p in sorted(glob.glob('parts/*.jsonl')):
        mo = os.path.getsize(p) / 1e6
        out['total_mo'] += mo
        out['n_partitions'] += 1
        if mo >= 90:
            out['zone_rouge'].append({'fichier': p, 'mo': round(mo, 1)})
    out['total_mo'] = round(out['total_mo'], 1)
    return out


def main():
    started = _run_started()
    rows = inspect(started)
    parts = partitions_health()
    ko = [r for r in rows if r['verdict'] != '✅ OK']

    payload = {
        'run_termine': datetime.datetime.utcnow().isoformat(timespec='seconds'),
        'run_demarre': started.isoformat(timespec='seconds'),
        'verdict_global': 'OK' if not ko else f'{len(ko)} livrable(s) à vérifier',
        'livrables': rows,
        'partitions': parts,
    }
    json.dump(payload, open(OUT_JSON, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    L = []
    L.append('# État du dernier run — Steam Pipeline\n')
    L.append(f"Run démarré `{payload['run_demarre']}` · terminé `{payload['run_termine']}` (UTC)\n")
    L.append(f"**Verdict : {payload['verdict_global']}**\n")
    L.append('| Livrable | Fichier | Lignes | Octets | État |')
    L.append('|---|---|---:|---:|---|')
    for r in rows:
        L.append(f"| {r['libellé']} | `{r['fichier']}` | {r.get('lignes') or 0} | "
                 f"{r.get('octets') or 0} | {r['verdict']} |")
    L.append('')
    L.append(f"**Partitions** : {parts['n_partitions']} fichiers, {parts['total_mo']} Mo au total.")
    if parts['zone_rouge']:
        L.append('')
        L.append('> ⛔ **Zone rouge** — une partition approche le mur GitHub de 100 Mo :')
        for z in parts['zone_rouge']:
            L.append(f"> - `{z['fichier']}` : {z['mo']} Mo")
    L.append('')
    L.append('Légende : ✅ produit pendant ce run · ⏳ présent mais non réécrit '
             '(le script n\'a rien produit) · ⚠️ vide ou réduit à son en-tête · ❌ absent.')
    open(OUT_MD, 'w', encoding='utf-8').write('\n'.join(L) + '\n')

    print(f"PIPELINE STATUS -> {OUT_JSON} + {OUT_MD}")
    for r in rows:
        print(f"  {r['verdict']:<10} {r['fichier']:<28} {r.get('lignes') or 0} lignes")
    print(f"  partitions : {parts['n_partitions']} fichiers, {parts['total_mo']} Mo")
    for z in parts['zone_rouge']:
        print(f"  ⛔ ZONE ROUGE : {z['fichier']} = {z['mo']} Mo (mur GitHub 100 Mo)")


if __name__ == '__main__':
    main()
