#!/usr/bin/env python3
"""Tennis Edge Lab V6.3.1: cache de partitions + suivi prospectif sans redécouverte.

- Seules les partitions sources nouvelles ou modifiées sont reparsées.
- Reconstitue exactement les identités, conflits, fusions et statistiques de
  couverture au niveau GLOBAL, avec les fonctions V5 d'origine.
- Charge les résultats de matchs à chaque passage (jamais mis en cache),
  puis évalue UNIQUEMENT les 60 règles V6.3 déjà préenregistrées.
- Ne modifie ni les registres, ni les gels, ni les preuves V6.2/V6.3.
- Cache accélérateur invalidable, JAMAIS unique preuve historique.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import bookmakers_sets_v5 as engine
import candidate_registry_v62 as compact
import candidate_selection_v63 as selection
import candidate_watch_v61 as v61

SCHEMA = 1
CACHE_PROTOCOL = "tennis-edge-anchors-v631-1"
REPORT = Path(compact.REPORT)
ALLOWED_MARKETS = frozenset(compact.MARKETS)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _signature(root: Path) -> str:
    """Invalidate when parsing/selection rules change; NOT for new results.

    A changed set_results.json (or circuit hints) is read fresh downstream.
    """
    payload = {
        "protocol": CACHE_PROTOCOL,
        "horizons": engine.HORIZONS,
        "min_odds": engine.MIN_ODDS,
        "max_odds": engine.MAX_ODDS,
        "parser_files": {},
    }
    for relative in ("Tennis_Edge_Lab/bookmakers_sets_v5.py",
                     "Tennis_Edge_Lab/source_features.py",
                     "scripts/oddspapi_v5.py"):
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Lecteur nécessaire absent : {relative}")
        payload["parser_files"][relative] = _hash_file(path)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _serialize_anchor(anchor: dict) -> dict:
    def encode(point):
        return None if point is None else [point[0].isoformat(), point[1], point[2]]
    return {"open": encode(anchor["open"]), "close": encode(anchor["close"]),
            "horizons": {name: encode(anchor["horizons"].get(name)) for name in engine.HORIZONS}}


def _restore_anchor(anchor: dict) -> dict:
    def decode(point):
        return None if point is None else (engine.parse_time(point[0]), point[1], point[2])
    return {"open": decode(anchor["open"]), "close": decode(anchor["close"]),
            "horizons": {name: decode(anchor["horizons"].get(name)) for name in engine.HORIZONS}}


def _normalized_partition(path: Path, market: str, root: Path, signature: str,
                          source_sha: str) -> dict:
    open_any = engine.load_oddspapi_reader()
    source_digest = hashlib.sha256()
    events = []
    with open_any(str(path)) as stream:
        for line in stream:
            source_digest.update(line.encode('utf-8'))
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                events.append({"kind": "invalid_json"})
                continue
            if not isinstance(row, dict):
                events.append({"kind": "invalid_row"})
                continue
            uid, book = row.get('uid'), row.get('book')
            book_key = book.strip().lower() if isinstance(book, str) and book.strip() else None
            book_uid = str(uid or '') if book_key else None
            start = engine.parse_time(row.get('commence_time'))
            if start is None:
                events.append({"kind": "invalid_start", "book_key": book_key, "book_uid": book_uid})
                continue
            identity = engine._identity(row, start)
            if identity is None:
                events.append({"kind": "invalid_identity", "book_key": book_key, "book_uid": book_uid})
                continue
            norm_uid, fixture, _, home, away, normalized_book = identity
            curve_counter = collections.Counter()
            curves = {
                side: _serialize_anchor(engine._anchors(
                    engine._curve_points(row.get(f'{side}_curve'), start, curve_counter), start
                ))
                for side in ('home', 'away')
            }
            events.append({
                "kind": "valid", "book_key": book_key, "book_uid": book_uid,
                "uid": norm_uid, "fixture": fixture, "start": start.isoformat(),
                "home_identity": home, "away_identity": away,
                "book": normalized_book, "home": row['home'], "away": row['away'],
                "tournament": str(row.get('tournament') or ''), "curves": curves,
                "curve_counters": dict(curve_counter),
            })
    return {"schema_version": SCHEMA, "signature": signature,
            "partition_sha256": source_sha,
            "path": path.relative_to(root).as_posix(), "market": market,
            "source_digest": source_digest.hexdigest(), "events": events}


def _cache_path(cache_root: Path, relative: str) -> Path:
    return cache_root / (hashlib.sha256(relative.encode()).hexdigest() + '.json.gz')


def _cache_digest(doc: dict) -> str:
    """Detect corrupted or partially restored cache payloads."""
    payload = {key: val for key, val in doc.items() if key != 'payload_sha256'}
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=False, allow_nan=False).encode('utf8')
    return hashlib.sha256(raw).hexdigest()


def _cached_partition(path: Path, market: str, root: Path, signature: str,
                      cache_root: Path, metrics: collections.Counter) -> dict:
    relative = path.relative_to(root).as_posix()
    source_sha = _hash_file(path)
    target = _cache_path(cache_root, relative)
    try:
        with gzip.open(target, 'rt', encoding='utf8') as stream:
            doc = json.load(stream)
        if not (doc.get('schema_version') == SCHEMA
                and doc.get('signature') == signature
                and doc.get('partition_sha256') == source_sha
                and doc.get('path') == relative
                and doc.get('market') == market
                and len(doc.get('source_digest', '')) == 64
                and isinstance(doc.get('events'), list)
                and doc.get('payload_sha256') == _cache_digest(doc)):
            raise ValueError('Cache incompatible')
        metrics['reused'] += 1
        return doc
    except (OSError, EOFError, ValueError, KeyError, TypeError, gzip.BadGzipFile):
        # Corrupted/missing accelerator => rebuild from the ORIGINAL source.
        pass
    doc = _normalized_partition(path, market, root, signature, source_sha)
    doc['payload_sha256'] = _cache_digest(doc)
    cache_root.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=cache_root, prefix='.anchor-', suffix='.gz')
    try:
        with os.fdopen(fd, 'wb') as raw:
            with gzip.GzipFile(fileobj=raw, mode='wb', compresslevel=6, mtime=0) as stream:
                stream.write(json.dumps(doc, ensure_ascii=False, separators=(',', ':'),
                                        allow_nan=False).encode('utf8'))
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    metrics['rebuilt'] += 1
    return doc


def collect_cached(root: Path, cache_root: Path) -> tuple[dict, dict, dict]:
    root = root.resolve()
    paths = engine.partition_paths(root)
    if not paths:
        raise RuntimeError('Aucune partition historique disponible : refus de publier un suivi vide')
    signature = _signature(root)
    records = {}
    uid_identity = {}
    conflicted_uids = set()
    fixture_uids = collections.defaultdict(set)
    counters = collections.Counter()
    market_books = collections.defaultdict(lambda: collections.defaultdict(set))
    source_hashes = {}
    metrics = collections.Counter()

    # Iterate in precisely the same order as engine.collect. Cross-file joins,
    # identities and duplicates must NEVER be computed inside isolated shards.
    for market, path in paths:
        doc = _cached_partition(path, market, root, signature, cache_root, metrics)
        counters['partition_files'] += 1
        source_hashes[path.relative_to(root).as_posix()] = doc['source_digest']
        for event in doc['events']:
            counters['partition_records'] += 1
            kind = event['kind']
            if kind == 'invalid_json':
                counters['invalid_json_rows'] += 1
                continue
            if kind == 'invalid_row':
                counters['invalid_rows'] += 1
                continue
            if event.get('book_key'):
                market_books[market][event['book_key']].add(event['book_uid'])
            if kind == 'invalid_start':
                counters['invalid_start_times'] += 1
                continue
            if kind == 'invalid_identity':
                counters['invalid_match_ids'] += 1
                continue
            if kind != 'valid':
                raise ValueError('Unknown normalized event kind')
            uid = event['uid']
            fixture = event['fixture']
            start = engine.parse_time(event['start'])
            fixture_uids[fixture].add(uid)
            match_identity = (fixture, start, event['home_identity'], event['away_identity'])
            old_identity = uid_identity.setdefault(uid, match_identity)
            if old_identity != match_identity:
                conflicted_uids.add(uid)
                counters['match_identity_conflicts'] += 1
                continue
            counters.update(event['curve_counters'])
            curves = {side: _restore_anchor(event['curves'][side]) for side in ('home', 'away')}
            key = (market, uid, event['book'])
            previous = records.get(key)
            if previous is None:
                records[key] = {
                    'market': market, 'uid': uid, 'fixture_id': fixture,
                    'start': start, 'home': event['home'], 'away': event['away'],
                    'book': event['book'], 'tournament': event['tournament'],
                    'curves': curves,
                }
            else:
                counters['duplicate_records_merged'] += 1
                previous['curves'] = {
                    side: engine._merge_anchor(previous['curves'][side], curves[side])
                    for side in ('home', 'away')
                }
                if not previous['tournament'] and event['tournament']:
                    previous['tournament'] = event['tournament']
    conflicted_fixtures = {fixture for fixture, uids in fixture_uids.items() if len(uids) > 1}
    counters['fixture_uid_conflicts'] = len(conflicted_fixtures)
    coverage = {
        'partition_files': len(paths),
        'partition_records': counters['partition_records'],
        'source_hashes': source_hashes,
        'market_book_record_uids': {
            market: {book: len(uids - {''}) for book, uids in books.items()}
            for market, books in sorted(market_books.items())
        },
        'counters': dict(counters),
        'conflicted_uids': sorted(conflicted_uids),
        'conflicted_fixtures': sorted(conflicted_fixtures),
    }
    return records, coverage, dict(metrics)


def load_cached_observations(root: Path, cache_root: Path):
    """Native V5 post-processing applied to identical globally merged records."""
    root = root.resolve()
    results = engine.load_results(root)  # fresh on every run
    circuit_hints = engine.load_circuit_hints(root)  # fresh on every run
    records, source, metrics = collect_cached(root, cache_root)
    source['results_uids'] = len(results)
    source['unique_market_book_matches'] = len(records)
    rows, coverage = engine.make_observations(
        records, results, set(source['conflicted_uids']),
        set(source['conflicted_fixtures']), circuit_hints,
    )
    result_path = root / 'set_results.json'
    source['source_hashes']['set_results.json'] = _hash_file(result_path)
    source['source_hash_basis'] = (
        'SHA-256 des octets du fichier pour JSON/CSV; lignes UTF-8 décompressées pour les partitions .gz.'
    )
    hints_path = root / 'moves_detail_hist.csv'
    if hints_path.is_file():
        source['source_hashes']['moves_detail_hist.csv'] = _hash_file(hints_path)
    return rows, coverage, source, metrics


def evaluate(root: Path, cache_root: Path, now: dt.datetime | None = None) -> dict:
    root = root.resolve()
    now = v61.utc(now or dt.datetime.now(dt.timezone.utc))
    selection.verify_manifest(root, now.date())
    records = compact._load_ledger(root)
    if not records:
        raise ValueError('Pas de règles gelées V6.3 : publication bloquée')
    evidence = compact._load_evidence(root, records)
    expanded = [{**row, 'discovery_fixture_hashes': evidence[row['candidate_id']]}
                for row in records]
    events = selection._manifest_events(root / selection.MANIFEST)
    permitted = {cid for event in events for cid in event['selected_candidate_ids']}
    known = {row['candidate_id'] for row in records}
    if not permitted or known != permitted:
        raise ValueError('Le registre V6.3 ne correspond pas aux preuves autorisées')
    path = root / REPORT
    previous = json.loads(path.read_text(encoding='utf8'))
    if not isinstance(previous, dict) or previous.get('schema_version') != 3:
        raise ValueError('Rapport V6.3 de référence absent ou mal formé')
    rows, _, source, metrics = load_cached_observations(root, cache_root)
    if not rows:
        raise ValueError('Aucune observation réglée : publication refusée')
    prospect = compact._apply_family_correction(v61.evaluate(expanded, rows, now))
    active = [row for row in records if selection._active(row, now.date())]
    active_by_market = {market: 0 for market in compact.MARKETS}
    for row in active:
        active_by_market[row['signature']['scope']['market']] += 1
    records_by_id = {row['candidate_id']: row for row in records}
    for item in prospect['candidates']:
        item['lifecycle_state'] = ('active' if selection._active(
            records_by_id[item['candidate_id']], now.date()) else 'archivée')
    # All historical discovery metadata and pre-registered choices stay frozen.
    prospect.update({
        'schema_version': 3,
        'policy_version': selection.POLICY,
        'generated_at': now.isoformat(timespec='seconds'),
        'selection_manifest': previous['selection_manifest'],
        'exploratory_inventory_count': previous['exploratory_inventory_count'],
        'redundant_exploratory_count': previous['redundant_exploratory_count'],
        'candidate_redundant_count': previous['candidate_redundant_count'],
        'active_limit': selection.ACTIVE_LIMIT,
        'active_total': len(active),
        'active_by_market': active_by_market,
        'completed_and_archived': len(records) - len(active),
        'source_snapshot_sha256': previous['source_snapshot_sha256'],
        'evaluated_future_period': {
            'starts_after_freeze': True,
            'latest_cutoff_utc': now.isoformat(timespec='seconds'),
        },
        'selection': previous.get('selection', {}),
    })
    if ({item['candidate_id'] for item in prospect['candidates']} != known
            or len(prospect['candidates']) != len(known)
            or len(active) > selection.ACTIVE_LIMIT):
        raise ValueError('Une hypothèse non enregistrée a été ajoutée au rapport')
    # Re-verify chain and exclusion of discovery matches before publishing.
    selection.verify_manifest(root, now.date())
    compact._load_ledger(root)
    v61._write_report(path, prospect)
    return {
        'report': REPORT.as_posix(), 'frozen': len(known),
        'active': len(active), 'observations': len(rows),
        'cache_reused': metrics.get('reused', 0),
        'cache_rebuilt': metrics.get('rebuilt', 0),
        'partition_count': len(engine.partition_paths(root)),
        'source_hash_count': len(source['source_hashes']),
        'cutoff': now.isoformat(timespec='seconds'),
    }


def verify_full(root: Path, cache_root: Path) -> dict:
    """Optional parity audit; costly, never required in the daily workflow."""
    from hashlib import sha256
    def fingerprint(rows):
        canonical = (json.dumps(item, sort_keys=True, separators=(',', ':'),
                                ensure_ascii=False, allow_nan=False) for item in rows)
        return sha256(('\n'.join(sorted(canonical))).encode('utf8')).hexdigest()
    actual_rows, _, coverage, metrics = load_cached_observations(root, cache_root)
    original_rows, _, native_source = engine.load_observations(root)
    if coverage != native_source or fingerprint(actual_rows) != fingerprint(original_rows):
        raise AssertionError('ALERTE : cache V6.3.1 divergent du lecteur V5 officiel')
    return {'parity': 'ok', 'rows': len(actual_rows), 'reused': metrics.get('reused', 0)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('evaluate', 'audit'))
    ap.add_argument('--root', default='.')
    ap.add_argument('--cache', required=True)
    args = ap.parse_args()
    root = Path(args.root).resolve()
    cache = Path(args.cache).resolve()
    if args.action == 'evaluate':
        result = evaluate(root, cache)
    else:
        result = verify_full(root, cache)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))


if __name__ == '__main__':
    main()
