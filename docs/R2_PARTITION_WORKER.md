# R2 V6.4 partition worker (async, independent of the collectors)

Archives **frozen tick partitions already published on Git** (`parts/pm_ticks_*.jsonl.gz`,
`parts/kx_ticks_*.jsonl.gz`) into R2. It never runs inside, next to, or because of a
collector, and it never writes to Git.

Status: **prepared, not merged, not activated**. Default state is disabled.

## Guarantees

| Property | Mechanism |
|---|---|
| Collectors untouched | New files only: `scripts/r2_partition_worker.py`, `.github/workflows/r2_partition_worker.yml`. Own concurrency group, `contents: read`, no `schedule`. |
| Only published data | Partitions are listed with `git ls-tree` on a Git ref (default `origin/main`) and read by blob id. Working-tree files are ignored. |
| Only frozen data | UTC day closed + grace (default 6 h). Today's partition is never read. |
| No shared index | One prefix per partition **version**: `<root>/<provider>/<YYYY-MM-DD>/<git-blob-sha>/{data.jsonl.gz,manifest.json}`. |
| Durable checkpoint | The manifest is written **last**; a partition is done only when manifest + data verify. Resume after a crash = rerun. |
| Idempotence | Create-only writes (`If-None-Match: *`). Existing identical objects are a no-op; differing ones are a reported `conflict`, never overwritten. A re-compressed Git file gets a new blob prefix; old versions stay. |
| No deletion | The code has no delete call (tests assert it). |
| Verifiable | Manifest has a self SHA-256, data SHA-256/size, Git blob id, line/unique/duplicate counts, min/max `ts`, SHA-256 of sorted normalized tick ids. |
| Bounded | Per-call botocore timeouts (5 s connect, 20 s read), 3 attempts with capped backoff, per-partition and global deadlines, `--max-partitions`. |

## Modes

* `dry-run` (default): no R2 write. Lists what is pending (queries R2 read-only when credentials exist).
* `sync`: create-only archive + read-back verification + manifest.
* `verify`: read-only Git vs R2 comparison (SHA-256, normalized records, counts, timestamps).
* `restore` (CLI): writes the verified bytes of one version to a directory; refuses to overwrite.

Report statuses: `uploaded`, `verified`, `pending` (deadline/limit/dry-run), `skipped_unfrozen`,
`error` (retries exhausted; retried next run), `conflict` (differing object, permanent error;
needs a human). `attempts_total` comes from the optional `--state-file`.

## Activation (manual, off by default)

1. Dry run: `gh workflow run r2_partition_worker.yml -f mode=dry-run`.
2. Sandbox sync (no activation needed): `-f mode=sync -f confirm_sync=true -f root_prefix=parts/v64-archive-test/<name> -f max_partitions=1`.
3. Production sync requires **both** the repository variable `R2_PARTITION_WORKER_ENABLED=true`
   (`gh variable set R2_PARTITION_WORKER_ENABLED --body true`) **and** `-f mode=sync -f confirm_sync=true`.
4. Review the artifact `r2-partition-worker-*` (summary, `success`, `complete`, verify report).

## Restore

```
python scripts/r2_partition_worker.py --mode restore --provider polymarket \
  --day 2026-10-12 --blob <git-blob-sha> --destination /tmp/restore
```

Compare the printed SHA-256 with the manifest and with `git cat-file blob <blob> | sha256sum`.
Copy back into `parts/` manually and only if the Git file is lost. The restored file is
byte-identical to the Git blob (the worker checks `git hash-object` equivalence).

## Rollback

* Stop: leave/unset `R2_PARTITION_WORKER_ENABLED` (`gh variable delete R2_PARTITION_WORKER_ENABLED`)
  and do not dispatch. A running job can be cancelled; objects are create-only, so a partial
  state is valid (manifest-less data is simply re-verified next run).
* Remove the feature: revert the merge of the worker files. Collectors are unaffected.
* R2 objects created by the worker live under `<root>/` only. They are not deleted by any
  code; removal, if ever wanted, is a separate, manually approved operation.
