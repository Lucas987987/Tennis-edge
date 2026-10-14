#!/usr/bin/env python3
"""V6.4: independent historical ROI+/CLV+ shortlist from exhaustive V6.1 shards.

Historical screening is outcome-informed, not prospective validation. The existing
V6.3 frozen registries are not imported, modified, or ranked by this program.
"""
from __future__ import annotations

import argparse
import collections
from datetime import datetime, timezone, timedelta, date
import gzip
import hashlib
import json
import math
from pathlib import Path

POLICY = 'tennis-edge-economic-v64-1'
ARCHIVE_REL = 'Tennis_Edge_Lab/live/archive/bookmakers_sets_v61/current'
AUDIT_REL = 'Tennis_Edge_Lab/live/bookmakers_sets_audit.json'
MARKETS = ('match', 'set1', 'set2')
MIN_MATCHES = 80
MIN_DAYS = 20
MIN_CLV_N = 50
OVERLAP = 0.85


def sha_file(path):
    d = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            d.update(chunk)
    return d.hexdigest()


def sha_object(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def eligible(row, as_of):
    """Hard, auditable constraints; no arbitrary quota per market."""
    n = row.get('unique_matches')
    days = row.get('distinct_days')
    clv_n = row.get('clv_n')
    if row.get('market') not in MARKETS:
        return 'market_invalid'
    if not isinstance(row.get('end_date'), str) or row['end_date'] > as_of:
        return 'future_or_unknown_discovery_date'
    if not isinstance(n, int) or n < MIN_MATCHES or row.get('n') != n:
        return 'matches_or_duplicate_count'
    if not isinstance(days, int) or days < MIN_DAYS:
        return 'days_insufficient'
    if not isinstance(clv_n, int) or clv_n < MIN_CLV_N:
        return 'clv_sample_insufficient'
    if not finite(row.get('roi_pct')) or row['roi_pct'] <= 0:
        return 'roi_not_positive'
    if not finite(row.get('clv_mean_pct')) or row['clv_mean_pct'] <= 0:
        return 'clv_not_positive'
    if row.get('duplicate_of'):
        return 'exact_population_duplicate'
    if not row.get('p_fair_valid') or row.get('feature_availability', {}).get('verified') is not True:
        return 'quality_or_feature_unverified'
    criteria = row.get('criteria')
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 3:
        return 'invalid_rule'
    for c in criteria:
        if not isinstance(c, dict) or not c.get('dimension') or 'value' not in c:
            return 'invalid_rule'
    members = row.get('discovery_fixture_hashes')
    if (not isinstance(members, list) or len(members) != n
        or len(set(members)) != n
        or any(not isinstance(m, str) or len(m) != 64 for m in members)):
        return 'population_proof_missing'
    if row.get('first_half') is None or row.get('second_half') is None:
        return 'temporal_splits_missing'
    return None


def normalized_score(row):
    """Explicit heuristic 0..100, not a probability or forecast."""
    roi = min(row['roi_pct'] / 30, 1)
    clv = min(row['clv_mean_pct'] / 5, 1)
    n = min(math.log1p(row['unique_matches']) / math.log1p(2000), 1)
    days = min(row['distinct_days'] / 120, 1)
    simplicity = 1 / len(row['criteria'])
    return round(100 * (0.40 * roi + 0.25 * clv + 0.15 * n
                        + 0.10 * days + 0.10 * simplicity), 5)


def robustness_score(row, score):
    ci = row.get('roi_ci95')
    ci_pos = isinstance(ci, list) and len(ci) == 2 and finite(ci[0]) and ci[0] > 0
    halves_positive = all(finite(row.get(key, {}).get('roi_pct')) and
                          row[key]['roi_pct'] > 0 for key in ('first_half', 'second_half'))
    # Descriptive ordering only, not a significance test.
    return round(score + (15 if ci_pos else 0) + (12 if halves_positive else 0), 5)


def _candidate(row):
    signature = {key: row.get(key) for key in ('market', 'book', 'horizon', 'selection')}
    signature['criteria'] = sorted(row['criteria'], key=lambda r: (r['dimension'], str(r['value'])))
    ident = sha_object(signature)
    score = normalized_score(row)
    return {
        'id': ident,
        **{k: row.get(k) for k in ('market', 'book', 'horizon', 'selection', 'circuit')},
        'criteria': signature['criteria'],
        'roi_pct': row['roi_pct'],
        'roi_ci95': row.get('roi_ci95'),
        'clv_mean_pct': row['clv_mean_pct'],
        'clv_n': row['clv_n'],
        'unique_matches': row['unique_matches'],
        'distinct_days': row['distinct_days'],
        'first_half_roi_pct': row['first_half'].get('roi_pct'),
        'second_half_roi_pct': row['second_half'].get('roi_pct'),
        'p_holm': row.get('p_holm'),
        'p_fair_valid': row.get('p_fair_valid'),
        'historical_start': row.get('start_date'),
        'historical_end': row.get('end_date'),
        'score': score,
        'robustness_score': robustness_score(row, score),
        'population_size': len(row['discovery_fixture_hashes']),
    }


class PopulationDeduper:
    """Near duplicate Jaccard, within market across books/horizons."""
    def __init__(self, threshold=OVERLAP):
        self.threshold = threshold
        self.postings = collections.defaultdict(lambda: collections.defaultdict(list))
        self.sizes = collections.defaultdict(list)

    def accept(self, market, members):
        population = set(members)
        counts = collections.Counter()
        postings = self.postings[market]
        for fixture in population:
            counts.update(postings.get(fixture, []))
        for index, intersect in counts.items():
            size = self.sizes[market][index]
            union = len(population) + size - intersect
            if union and intersect / union >= self.threshold:
                return False
        idx = len(self.sizes[market])
        self.sizes[market].append(len(population))
        for fixture in population:
            postings[fixture].append(idx)
        return True


def read_segments(root, as_of, rejected):
    audit = json.loads((root / AUDIT_REL).read_text(encoding='utf8'))
    source_hashes = audit.get('source_hashes')
    if not isinstance(source_hashes, dict) or not source_hashes:
        raise ValueError('Audit V6.1 sans inventaire de sources')
    source_snapshot = sha_object(source_hashes)
    if source_snapshot != audit.get('archive', {}).get('source_snapshot_sha256'):
        raise ValueError('Empreinte source V6.1 différente')
    manifest = json.loads((root / ARCHIVE_REL / 'manifest.json').read_text(encoding='utf8'))
    if manifest.get('source_snapshot_sha256') != source_snapshot:
        raise ValueError('Manifeste archive V6.1 différent des sources')
    if set(manifest.get('markets', {})) != set(MARKETS):
        raise ValueError('Inventaire V6.1 incomplet : marchés manquants')
    count = 0
    candidates = []
    for market in MARKETS:
        part = manifest['markets'][market]
        archive = (root / part['compressed_jsonl']).resolve()
        if not archive.is_relative_to(root.resolve()):
            raise ValueError('Chemin archive extérieur au dépôt')
        if sha_file(archive) != part['compressed_sha256']:
            raise ValueError(f'Archive {market} corrompue')
        found = 0
        with gzip.open(archive, 'rt', encoding='utf8') as fh:
            for line in fh:
                if not line.strip():
                    continue
                found += 1
                row = json.loads(line)
                if not isinstance(row, dict) or row.get('market') != market:
                    raise ValueError(f'Archive {market} : ligne ou marché invalide')
                reason = eligible(row, as_of)
                if reason:
                    rejected[reason] += 1
                    continue
                candidates.append((row, _candidate(row)))
        if found != part['segment_count']:
            raise ValueError(f'Archive {market} incomplète : {found} != {part["segment_count"]}')
        count += found
    if count != audit['segment_count']:
        raise ValueError(f'Audit incomplet : {count} != {audit["segment_count"]}')
    return candidates, count, source_snapshot, manifest


def build(root, as_of=None):
    root = Path(root).resolve()
    as_of_date = as_of or datetime.now(timezone.utc).date()
    rejected = collections.Counter()
    candidates, total, source_hash, manifest = read_segments(root, as_of_date.isoformat(), rejected)
    candidates.sort(key=lambda row: (-row[1]['score'], -row[1]['roi_pct'],
                                     -row[1]['clv_mean_pct'], -row[1]['unique_matches'],
                                     row[1]['id']))
    dedup = PopulationDeduper()
    selected = []
    ids = set()
    for source, entry in candidates:
        if entry['id'] in ids:
            rejected['duplicate_signature'] += 1
            continue
        ids.add(entry['id'])
        if not dedup.accept(entry['market'], source['discovery_fixture_hashes']):
            rejected['near_duplicate_population'] += 1
            continue
        selected.append(entry)
    if not selected:
        raise ValueError('Aucune hypothèse ROI+ et CLV+ éligible : publication refusée')
    by_market = dict(collections.Counter(r['market'] for r in selected))
    selected_ids = [r['id'] for r in selected]
    selection_id = sha_object({'policy': POLICY, 'source_snapshot': source_hash,
                              'as_of_utc': as_of_date.isoformat(), 'ids': selected_ids})
    out = {
        'schema_version': 1, 'policy_version': POLICY,
        'selection_id': selection_id,
        'created_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'as_of_utc': as_of_date.isoformat(),
        'eligible_after_utc': (as_of_date + timedelta(days=1)).isoformat(),
        'checkpoints_utc': [(as_of_date + timedelta(days=k)).isoformat() for k in (30,60,90)],
        'source_snapshot_sha256': source_hash,
        'source_commit': manifest.get('source_commit'),
        'source_market_count': total,
        'candidate_count_before_near_dedup': len(candidates),
        'selected_count': len(selected),
        'by_market': {m: by_market.get(m, 0) for m in MARKETS},
        'rejected': dict(rejected),
        'thresholds': {'min_matches': MIN_MATCHES,'min_distinct_days': MIN_DAYS,
                       'min_clv_n': MIN_CLV_N,'roi_pct_gt':0,'clv_mean_pct_gt':0,
                       'max_near_duplicate_jaccard':OVERLAP,'market_quota':None},
        'score_weights': {'roi':0.40,'clv':0.25,'sample_size':0.15,
                          'distinct_days':0.10,'simplicity':0.10},
        'tops': {
            'top10':selected_ids[:10], 'top20':selected_ids[:20], 'top50':selected_ids[:50],
            'top_roi':[r['id'] for r in sorted(selected,key=lambda x:(-x['roi_pct'],-x['unique_matches'],x['id']))[:50]],
            'top_clv':[r['id'] for r in sorted(selected,key=lambda x:(-x['clv_mean_pct'],-x['clv_n'],x['id']))[:50]],
            'top_robust':[r['id'] for r in sorted(selected,key=lambda x:(-x['robustness_score'],-x['unique_matches'],x['id']))[:50]],
        },
        'candidates':selected,
        'validation_status':'HISTORIQUE UNIQUEMENT; sélection informée par ROI/CLV, non validée sur résultats futurs',
        'selection_method':'Filtres ROI > 0 ET CLV > 0; score descriptif (ROI 40 %, CLV 25 %, volume 15 %, jours 10 %, simplicité 10 %); tri déterministe; suppression des quasi-doublons dans chaque marché',
        'prospective':'Aucun ROI/CLV futur ne doit être déduit de cette sélection. Contrôles J+30/60/90 à implémenter séparément.',
    }
    return out


def verify(payload):
    if payload.get('policy_version') != POLICY:
        raise ValueError('Version du classement inconnue')
    cand = payload['candidates']
    ids = [x['id'] for x in cand]
    if len(ids) != len(set(ids)) or payload.get('selected_count') != len(ids):
        raise ValueError('Doublons ou compte invalide')
    if sum(payload['by_market'].values()) != len(ids):
        raise ValueError('Marchés incomplets')
    if any(x['roi_pct'] <= 0 or x['clv_mean_pct'] <= 0 for x in cand):
        raise ValueError('ROI/CLV non strictement positifs')
    if any(x['unique_matches'] < MIN_MATCHES or x['distinct_days'] < MIN_DAYS
           or x['clv_n'] < MIN_CLV_N for x in cand):
        raise ValueError('Seuils non respectés')
    for key, n in [('top10',10),('top20',20),('top50',50),('top_roi',50),('top_clv',50),('top_robust',50)]:
        if len(payload['tops'][key]) != min(n, len(ids)):
            raise ValueError(f'{key} incorrect')
        if any(x not in set(ids) for x in payload['tops'][key]):
            raise ValueError(f'{key} non relié aux sélections')
    return True


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', default='.')
    p.add_argument('--output', required=True)
    p.add_argument('--as-of', default=None)
    args = p.parse_args(argv)
    doc = build(args.root, date.fromisoformat(args.as_of) if args.as_of else None)
    verify(doc)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(doc, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n', encoding='utf8')
    print(json.dumps({'selection_id': doc['selection_id'], 'segments_explored':doc['source_market_count'],
                      'eligible_pre_dedup':doc['candidate_count_before_near_dedup'],
                      'selected':doc['selected_count'], 'by_market':doc['by_market'],
                      'tops':{key:len(value) for key,value in doc['tops'].items()}}, ensure_ascii=False))


if __name__ == '__main__':
    main()
