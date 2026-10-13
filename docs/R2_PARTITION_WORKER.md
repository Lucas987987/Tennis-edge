# R2 V6.4 partition worker (async, independent of the collectors)

Archives **frozen tick partitions already published on Git** (`parts/pm_ticks_*.jsonl.gz`,
`parts/kx_ticks_*.jsonl.gz`) into R2. It never runs inside, next to, or because of a
collector, and it never writes to Git.

Status: merged, **disabled by default**. No schedule; every run is a manual dispatch, and a
real write is authorised **per run**, never by a persistent repository setting.

## Guarantees

| Property | Mechanism |
|---|---|
| Collectors untouched | Own files only: `scripts/r2_partition_worker.py`, `.github/workflows/r2_partition_worker.yml`. Own concurrency group, `contents: read`, no `schedule`. |
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
* `sync`: create-only archive of **one exact partition version** + read-back verification + manifest.
* `verify`: read-only Git vs R2 comparison (SHA-256, normalized records, counts, timestamps).
* `restore` (CLI): writes one verified version to a directory and refuses to overwrite.
* `r2_partition_restore.yml`: separate, manual, read-only restore audit for Kalshi 2026-10-06.
  It pins the source commit and blob, verifies the R2 manifest/data, restores under `$RUNNER_TEMP`,
  compares bytes and tick statistics with Git, and publishes JSON reports as a workflow artifact.
  It has `contents: read`, no automatic trigger, and no R2 write or delete path.
* `r2_polymarket_restore.yml`: equivalent read-only restore audit for Polymarket 2026-10-08.
  It pins the published source version and explicitly checks its 152,161 lines, 152,156 unique ticks,
  and 5 historical duplicate lines before publishing the restore reports.
* `r2_partition_batch.yml`: separate manual batch controller. `dry-run` is the default; a batch
  contains at most 3 exact `{provider, day, blob}` targets and preflights every R2 prefix before
  any sync. `sync` requires `confirm_write=true`, calls the existing worker once per exact target,
  stops on the first anomaly, and re-verifies each completed version. `verify` and `restore-sample`
  are read-only; sample restores use a temporary directory and compare bytes, SHA-256 and tick
  statistics. All modes publish a JSON batch report. The workflow is `workflow_dispatch` only and
  has `contents: read`.

Report statuses: `uploaded`, `verified`, `pending` (deadline/limit/dry-run), `skipped_unfrozen`,
`error` (retries exhausted; retried next run), `conflict` (differing object, permanent error;
needs a human). `attempts_total` comes from the optional `--state-file`.

## Per-run write authorisation (mode=sync)

A real write needs **all** of the following in the same dispatch. The workflow gate checks them
first, and the worker re-checks them (`write_authorization_problems`), so neither is the single
point of failure:

| Requirement | Input / flag |
|---|---|
| Explicit confirmation, off by default, not persisted | `confirm_write=true` / `--confirm-write` |
| Exactly one partition processed | `max_partitions=1` |
| One exact partition version | `provider` + `partition_day` + `partition_blob` (40-hex Git blob id) |
| Worker-owned namespace only | `root_prefix` = `parts/v64-archive` or `parts/v64-archive-test/<name>` |

* The blob id must equal the file currently published on the Git ref. If the file was rewritten,
  retired from `main` (7-day retention by `archive_ticks`) or never existed, the run stops with
  `success=false` and **no write**; it never falls back to another partition.
* Retired partitions: pass `source_commit=<40-hex commit>` (optional input, needs `partition_day`
  and `partition_blob`). The commit must be an ancestor of `main` no older than 30 days; the
  worker then reads the partition from that commit instead of `main`'s tip. The blob id must still
  match exactly and the content is re-hashed against it. Find the commit with
  `git log -1 --format=%H <last-commit-containing-the-file>` (e.g. `git log -1 --diff-filter=AM -- parts/pm_ticks_<day>.jsonl.gz`).
* A targeted run succeeds only if that partition ends `uploaded` or `verified`. An unfrozen
  target (today) is refused.
* Before writing, the worker lists the destination prefix (`destination_existing` in the report).
  Anything other than `data.jsonl.gz` / `manifest.json` is a `conflict`; existing objects are never
  overwritten (`If-None-Match: *`).
* `dry-run` and `verify` need no confirmation, and `confirm_write` has no effect outside `sync`.
* The old `R2_PARTITION_WORKER_ENABLED` variable and `confirm_sync` input no longer exist. If the
  variable is still set in the repository it is ignored and can be deleted.

## First real write: exact procedure

1. Pick the version from a dry-run on the current `main`:
   `gh workflow run r2_partition_worker.yml -f mode=dry-run -f provider=polymarket -f partition_day=<YYYY-MM-DD> -f partition_blob=<blob> -f max_partitions=1`
   (get `<blob>` with `git rev-parse origin/main:parts/pm_ticks_<YYYY-MM-DD>.jsonl.gz`).
   Check the artifact: `summary: {"pending": 1}`, `destination_existing: []`.
2. Optional rehearsal in a sandbox: same inputs plus `mode=sync -f confirm_write=true -f root_prefix=parts/v64-archive-test/<name>`.
3. Real write: `gh workflow run r2_partition_worker.yml -f mode=sync -f confirm_write=true -f provider=polymarket -f partition_day=<YYYY-MM-DD> -f partition_blob=<blob> -f max_partitions=1 -f root_prefix=parts/v64-archive`.
4. Review the artifact `r2-partition-*`: `uploaded: 1`, `r2_objects_created: 2`, `deletions_performed: 0`,
   `overwrites_performed: 0`, then the read-only verify report (`verified`).
5. Nothing to switch back: the next dispatch is a dry-run unless `confirm_write=true` is typed again.

## Progressive batches

`.github/workflows/r2_partition_batch.yml` is a separate manual controller for up to three exact
partition versions per run. Its default is `dry-run`; `targets_json` is a JSON array of
`{"provider":"kalshi|polymarket","day":"YYYY-MM-DD","blob":"<40-hex Git blob>"}` objects.
`max_partitions` is limited to 1–3, the batch deadline to 1,200 seconds, and each R2 operation to
240 seconds. It reads R2 credentials only in the worker step and has `contents: read`.

The batch report classifies every target as `verified`, `absent`, `incomplete`, `divergent`,
`non_eligible` or `error`. In `sync`, all targets are preflighted before the first write; only
`absent` and already `verified` targets proceed. A write requires `confirm_write=true`; the existing
worker is called once per exact target with its own `max_partitions=1` gate. Any anomaly stops the
batch. Re-running is idempotent: matching versions become `verified`; conflicts are never
overwritten, and no code path deletes objects. `restore-sample` is read-only and restores selected
versions to a temporary directory for byte/SHA/stat comparisons. JSON reports are uploaded as an
Actions artifact.

Historical GitHub Release entries in `parts/ARCHIVE_INDEX.json` are not automatically treated as
R2 objects. The worker's retired-version source-commit path is bounded to an ancestor commit within
30 days; older Release-only history needs a separately verified source procedure before it can be
included in a batch.

Stop: `gh run cancel <run-id>`. Objects are create-only and the manifest is written last, so a
cancelled run leaves at most a manifest-less `data.jsonl.gz`, which the next run re-verifies.

## Restore

```
python scripts/r2_partition_worker.py --mode restore --provider polymarket \
  --day 2026-10-12 --destination /tmp/restore
```

Compare the printed SHA-256 with the manifest and with `git cat-file blob <blob> | sha256sum`.
Copy back into `parts/` manually and only if the Git file is lost. The restored file is
byte-identical to the Git blob (the worker checks `git hash-object` equivalence).

## Rollback

* Stop: cancel the running job and do not dispatch again. There is no persistent switch to unset.
* Remove the feature: revert the merge of the worker files. Collectors are unaffected.
* R2 objects created by the worker live under `<root>/` only. They are not deleted by any
  code; removal, if ever wanted, is a separate, manually approved operation.
