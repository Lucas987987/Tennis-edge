#!/usr/bin/env python3
"""Suivi LECTURE SEULE des collecteurs Kalshi/Polymarket (gh + git + fichiers locaux).
Usage : python suivi_collecteurs.py <repo> [--deploy ISO] [--now ISO] [--json out.json]
Fenêtres de 24 h : A = 48h..24h avant 'deploy', B = 24h avant 'deploy' (référence),
C = depuis 'deploy' (après correctif). Aucune écriture Git/R2, aucun dispatch."""
import argparse, collections, datetime as dt, glob, gzip, json, os, subprocess, sys

WF = {'kalshi': ('kalshi_collector.yml', 'kx'), 'polymarket': ('polymarket_collector.yml', 'pm')}
H = dt.timedelta(hours=1)


def P(s):
    return dt.datetime.fromisoformat(s.replace('Z', '+00:00')).astimezone(dt.timezone.utc)


def run(cmd, cwd=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode:
        raise RuntimeError(r.stderr[:200])
    return r.stdout


def gh_runs(wf, since):
    out = run(['gh', 'api', '--paginate', '-X', 'GET',
               f'repos/{{owner}}/{{repo}}/actions/workflows/{wf}/runs',
               '-f', 'per_page=100', '-f', 'created=>=' + since, '--jq',
               '.workflow_runs[]|[.id,.created_at,.status,.conclusion,.event]|@tsv'])
    rows = []
    for ln in out.splitlines():
        i, c, s, k, e = ln.split('\t')
        rows.append({'id': int(i), 'created': P(c), 'status': s, 'conclusion': k, 'event': e})
    return rows


def commit_step_failed(run_id):
    try:
        out = run(['gh', 'api', f'repos/{{owner}}/{{repo}}/actions/runs/{run_id}/jobs',
                   '--jq', '.jobs[].steps[]|select(.conclusion=="failure")|.name'])
    except RuntimeError:
        return None
    return [n for n in out.splitlines()]


def categorie(noms):
    """collecte = étape du collecteur en échec ; publication_git = étape Commit."""
    if noms is None:
        return 'inconnu'
    if any('Commit' in n for n in noms):
        return 'publication_git'
    return 'collecte' if noms else 'inconnu'


def classer(rows, a, b):
    sel = [r for r in rows if a <= r['created'] < b]
    c = collections.Counter()
    for r in sel:
        if r['status'] != 'completed':
            c['actifs_ou_en_attente'] += 1
        else:
            c[r['conclusion']] += 1
    ev = collections.Counter(r['event'] for r in sel)
    cat = collections.Counter()
    for r in sel:
        if r['conclusion'] == 'failure':
            cat[categorie(commit_step_failed(r['id']))] += 1
    conflits = cat['publication_git']
    return {'echecs_collecte': cat['collecte'], 'echecs_inconnus': cat['inconnu'],
            'annulations_normales_concurrence': c['cancelled'],'total': len(sel), 'success': c['success'], 'failure': c['failure'],
            'cancelled': c['cancelled'], 'actifs_ou_en_attente': c['actifs_ou_en_attente'],
            'echecs_a_l_etape_commit': conflits,
            'dispatch_manuels_workflow_dispatch': ev['workflow_dispatch'],
            'dispatch_externes_repository_dispatch': ev['repository_dispatch'],
            'schedule': ev['schedule']}


def ticks_minutes(repo, prefix, a, b):
    """Minutes (UTC) avec >=1 tick et trous >=3 min dans [a,b[, lus dans parts/ de main."""
    minutes = set()
    d = a.date()
    while d <= b.date():
        f = os.path.join(repo, 'parts', f'{prefix}_ticks_{d}.jsonl.gz')
        if os.path.exists(f):
            with gzip.open(f, 'rt', encoding='utf-8', errors='replace') as fh:
                for ln in fh:
                    i = ln.find('"ts"')
                    if i < 0:
                        continue
                    ts = ln[i + 6:i + 6 + 16].strip('" :')  # YYYY-MM-DDTHH:MM
                    try:
                        t = dt.datetime.fromisoformat(ts[:16]).replace(tzinfo=dt.timezone.utc)
                    except ValueError:
                        continue
                    if a <= t < b:
                        minutes.add(t)
        d += dt.timedelta(days=1)
    return minutes


def gaps(minutes, a, b, seuil=3):
    if not minutes:
        return [(a, b, int((b - a).total_seconds() // 60))]
    pts = [a] + sorted(minutes) + [b]
    res = []
    for x, y in zip(pts, pts[1:]):
        m = int((y - x).total_seconds() // 60) - 1
        if m >= seuil:
            res.append((x, y, m))
    return res


def fenetre(repo, kind, rows, a, b):
    pref = WF[kind][1]
    mins = ticks_minutes(repo, pref, a, b)
    g = gaps(mins, a, b)
    dur = int((b - a).total_seconds() // 60)
    return {'debut': a.isoformat(), 'fin': b.isoformat(), 'duree_min': dur,
            'runs': classer(rows, a, b),
            'minutes_avec_ticks': len(mins),
            'couverture_pct': round(100 * len(mins) / dur, 1) if dur else None,
            'trous_ge_3min': len(g),
            'minutes_dans_trous': sum(x[2] for x in g),
            'plus_long_trou_min': max((x[2] for x in g), default=0),
            'trous_top5': [{'de': x[0].isoformat(), 'a': x[1].isoformat(), 'min': x[2]}
                           for x in sorted(g, key=lambda z: -z[2])[:5]]}


def attribuer_relances(rows, debut, fin):
    """Relances `workflow_dispatch` d'un collecteur après `debut`, rattachées au
    watchdog si un run capture_closing terminé juste avant (<= 150 s) contient
    « relancé » dans son log ; sinon non attribuées (Cloudflare ou manuel)."""
    caps = []
    out = run(['gh', 'api', '--paginate', '-X', 'GET',
               'repos/{owner}/{repo}/actions/workflows/capture_closing.yml/runs',
               '-f', 'per_page=100', '-f', 'created=>=' + (debut - dt.timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%SZ'),
               '--jq', '.workflow_runs[]|[.id,.created_at,.updated_at]|@tsv'])
    for ln in out.splitlines():
        i, c, u = ln.split('\t')
        caps.append((int(i), P(c), P(u)))
    cache, res = {}, {'watchdog_confirme': 0, 'non_attribue': 0, 'detail': []}
    for r in rows:
        if r['event'] != 'workflow_dispatch' or not (debut <= r['created'] < fin):
            continue
        cand = [c for c in caps if 0 <= (r['created'] - c[2]).total_seconds() <= 150
                or c[1] <= r['created'] <= c[2]]
        ok = False
        for cid, _, _ in cand:
            if cid not in cache:
                try:
                    cache[cid] = 'relancé (déclenchement manuel via API)' in run(['gh', 'run', 'view', str(cid), '--log'])
                except RuntimeError:
                    cache[cid] = False
            ok = ok or cache[cid]
        res['watchdog_confirme' if ok else 'non_attribue'] += 1
        res['detail'].append({'run': r['id'], 'created': r['created'].isoformat(),
                              'attribution': 'watchdog' if ok else 'non_attribue'})
    return res


def derniere_publication(repo, kind):
    pref = {'kalshi': 'Kalshi collector', 'polymarket': 'Polymarket collector'}[kind]
    out = run(['git', 'log', 'origin/main', '-1', '--format=%cI|%h|%s', f'--grep=^{pref}'], cwd=repo)
    return out.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('repo')
    ap.add_argument('--deploy', default='2026-10-14T09:14:44Z')
    ap.add_argument('--now')
    ap.add_argument('--json')
    a = ap.parse_args()
    now = P(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    dep = P(a.deploy)
    run(['git', 'fetch', '-q', 'origin', 'main'], cwd=a.repo)
    rep = {'genere_a': now.isoformat(), 'deploy': dep.isoformat(), 'providers': {}}
    for kind, (wf, _) in WF.items():
        rows = gh_runs(wf, (dep - 49 * H).strftime('%Y-%m-%dT%H:%M:%SZ'))
        w = {'A_avant_deploy_-48h_-24h': fenetre(a.repo, kind, rows, dep - 48 * H, dep - 24 * H),
             'B_reference_-24h': fenetre(a.repo, kind, rows, dep - 24 * H, dep)}
        if now > dep:
            w['C_apres_deploy'] = fenetre(a.repo, kind, rows, dep, min(now, dep + 24 * H))
            w['C_apres_deploy']['relances_attribuees'] = attribuer_relances(rows, dep, min(now, dep + 24 * H))
        rep['providers'][kind] = {'fenetres': w, 'derniere_publication': derniere_publication(a.repo, kind)}
    txt = json.dumps(rep, indent=1, ensure_ascii=False)
    if a.json:
        open(a.json, 'w', encoding='utf-8').write(txt)
    print(txt)


if __name__ == '__main__':
    sys.exit(main())
