# V6.4 R2 shadow rollout

V6.4 integration with the current collectors is deliberately **shadow-only**:
the existing JSONL/Git history remains the read path and is still written. New
R2 objects use isolated `parts/v64/shadow/collectors/...` namespaces; the
historical archive under `parts/` and the normal V6.4 namespaces are not
rewritten by this mode.

## Enable a canary

Each collector workflow has a `workflow_dispatch` input named
`r2_v64_shadow`, defaulting to `false`. Scheduled runs and repository-dispatch
runs therefore keep their existing behavior. To test the shadow path:

1. Confirm the `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, and `R2_ENDPOINT`
   Actions secrets exist and are scoped to the repository.
2. Manually dispatch **one** collector with `r2_v64_shadow=true`. Start with a
   short, explicitly supervised run; do not enable it on recurring schedules.
3. Confirm that the collector's normal Git commit completed, then inspect its
   `V6.4 shadow vérifié` report. The report covers segments produced or
   recovered during that run; the sink checks the remote index SHA-256, each
   segment SHA-256, JSONL decoding, and segment record counts.
4. Restore the reported namespace into a temporary directory. Verify the
   complete restored namespace with `LocalPartitionStore.verify()` and confirm
   the report's segment checksums and line counts before considering a larger
   canary.

Every accepted record is appended locally and its R2 publication is attempted
before the collector proceeds. Successful segment uploads are immutable and
indexed with conditional manifest writes; retries are idempotent. If a runner
stops after a segment upload but before its index update, the next enabled run
scans the isolated namespace and reindexes valid orphan segments. If R2 is
unavailable, the existing collector continues writing its legacy output,
retries the shadow publication, and reports the shadow failure at shutdown.
The workflow's final commit step runs even when the collector reports a shadow
error, so the existing history path remains available. An external R2 outage
can still delay V6.4 visibility until a later successful retry/run; the
existing Git-backed path remains the fallback during this shadow phase.

## Rollback and promotion gates

Rollback is immediate: stop selecting `r2_v64_shadow=true`. No collector,
schedule, or legacy read path needs to be disabled or changed. Shadow objects
are retained; do not delete them as part of rollback.

Do not promote these shadow namespaces to the canonical V6.4 namespaces or
change analytics to read them until all of the following have been verified:

- supervised canaries for bookmaker, Polymarket, and Kalshi each complete with
  successful Git persistence and R2 read-back verification;
- measured collection cadence and throughput remain acceptable under R2
  latency, especially for WebSocket callbacks and the 30-second Kalshi poll;
- a subsequent-run restore/replay check proves restart idempotence and reports
  matching segment checksums and record counts;
- readers have an explicit compatibility/migration policy for existing Git and
  archived R2 history.

The shadow writer performs synchronous R2 requests on a newly accepted record.
This is intentionally conservative for durability but can add latency. The
mode is opt-in for supervised canaries only; it has not been enabled in this
change on scheduled or repository-dispatch collector runs.
