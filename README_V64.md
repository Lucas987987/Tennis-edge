# V6.4 R2 shadow rollout

V6.4 integration with the current collectors is deliberately **shadow-only**:
the existing JSONL/Git history remains the read path and is still written. New
collector data uses isolated `parts/v64/shadow/collectors/...` namespaces; the
historical archive under `parts/` and canonical V6.4 namespaces are not
rewritten.

## Isolated real-R2 validation

Each collector workflow has a `workflow_dispatch` input named
`r2_v64_shadow`, defaulting to `false`. Shadow writes also require the
`R2_V64_SHADOW_ENABLED` repository variable to equal `true`; undefined or
false keeps the feature off. Schedules and repository-dispatch runs therefore
retain their existing collection behavior.

To validate R2 without starting a collector:

1. In GitHub Actions on mobile or web, open **R2 V6.4 isolated validation**
   on the reviewed PR branch and dispatch it with
   `confirm_isolated_r2_writes=true`.
2. The workflow writes synthetic records only beneath a unique
   `parts/v64/shadow/validation/<run-id>/...` prefix. It uploads immutable
   segments without an index to simulate runner interruption, recovers and
   publishes the index, restores the namespace, and verifies SHA-256,
   JSONL/record counts, loss/duplicate accounting, and tick compatibility.
   The unique synthetic objects are retained; the workflow does not delete
   R2 objects or access historical prefixes.
3. Download the `r2-v64-validation-...` artifact and verify all three
   collectors report `read_back_verified: true`, `missing_r2_records: 0`,
   and one recovered orphan segment. The workflow never prints secret values.

Each collector's `V6.4 shadow vérifié` report compares accepted collector
calls, local writes, duplicate/no-op records, R2-verified records, duplicate
record IDs in verified segments, and missing R2 records. It reports only
segments produced during that collector run, not all prior namespace data.

Every accepted record is appended locally and its R2 publication is attempted
before the collector proceeds. Successful segment uploads are immutable and
indexed with conditional manifest writes; retries are idempotent. If a runner
stops after a segment upload but before its index update, a later enabled run
scans the isolated collector namespace and reindexes valid orphan segments.
If R2 is unavailable, the existing collector continues writing its legacy
output, retries shadow publication, and reports the failure at shutdown. The
workflow's final commit step still runs after a shadow error. An R2 outage can
delay V6.4 visibility until a later successful retry/run; the existing
Git-backed path remains the fallback during this shadow phase.

## Progressive collector canary

After successful isolated R2 validation and review, keep shadow disabled until
ready for a real collector canary. Do not change the existing collection
frequencies:

1. From the default branch, dispatch **V6.4 shadow control** with
   `state=enabled`.
2. Dispatch exactly one existing collector workflow on the default branch,
   select `r2_v64_shadow`, and leave its duration/frequency settings
   unchanged. Wait for its normal Git persistence and review its
   reconciliation report. Do not start overlapping canaries; existing
   concurrency groups are unchanged.
3. Repeat separately for bookmaker, Polymarket, then Kalshi, only after the
   previous run's legacy persistence, R2 checksums, record counts, and latency
   have been reviewed. Do not enable shadow on scheduled runs.

## Immediate rollback and mobile procedure

From GitHub Actions on mobile or web, dispatch **V6.4 shadow control** with
`state=disabled`. It sets `R2_V64_SHADOW_ENABLED=false`, blocking shadow on
subsequent collector workflow runs even if the per-workflow checkbox is
selected. Let any already-running collector finish; do not cancel it, because
that would interrupt collection. The control switch does not remotely stop an
in-progress collector process. All shadow objects are retained; never delete
them as part of rollback.

Do not promote shadow namespaces to canonical V6.4 namespaces or change
analytics to read them until supervised canaries for all three providers
complete, read-back and restart checks pass, collection throughput remains
acceptable (especially for Polymarket callbacks and Kalshi polling), and
readers have an explicit compatibility policy for existing Git and archived
R2 history. Synchronous R2 writes may add latency and require measurement
before promotion.
