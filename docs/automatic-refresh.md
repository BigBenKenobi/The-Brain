# Bounded automatic local refresh

The worker refreshes only registered, enabled sources using saved settings. Source
automation defaults off and global policy defaults paused. Explicit manual refresh
continues to work independently. No source discovery, network submission or source
execution is performed.

```sh
python3 -m brain --brain /path/to/store sources
python3 -m brain --brain /path/to/store refresh-status
python3 -m brain --brain /path/to/store configure-source SOURCE_ID --enabled
python3 -m brain --brain /path/to/store refresh-policy --interval-seconds 900 --max-store-bytes 1073741824 --no-paused
python3 -m brain --brain /path/to/store refresh-once
```

Enabling capture is an explicit opt-in decision for the selected source. The
900-second interval and1GiB cap above are examples matching the approved curated-note
deployment, not permission to enable other sources. Pause with `refresh-policy
--paused`; disable an individual source with `configure-source SOURCE_ID --no-enabled`.
Read `refresh-status` for paused/disabled, idle, running, partial, deferred, stale and failed
states, last success, next attempt and errors. An on-disk running marker alone does
not prove a live worker.

A non-overlapping worker lock and a nonblocking writer-lock check prevent concurrent
capture. Per-run file, byte, source and time budgets bound work without overwriting
saved source configuration. The worker shares one scan deadline across due sources.
If the deadline cuts off inventory before any files are processed, the worker records a
deferral and retries while keeping the previous snapshot active.
Transient failures persist bounded exponential retry
state. Failed publication keeps the previous valid snapshot. Capacity exhaustion
stops new capture with an explicit error; existing knowledge is not deleted.

Unchanged captures use `observation-1` snapshots referencing one retained full
content snapshot, with new observation metadata and chronological parent links.
Readers materialize the original evidence and records. Missing, corrupt or chained
content references fail closed. Sharing approvals and their expiry are not renewed
by observation. Meaningful changes still publish a full content snapshot.

## Writer compatibility

Lightweight observations were introduced with writer version3. New stores now use
writer version4 for evidence blobs; see [storage compaction](storage-compaction.md). Readers accept versions1–3, but an explicit
`upgrade-store --backup /separate/new/backup` is required before writing. Exercise
that upgrade against a coherent copy first. Historical snapshots are not rewritten;
older writers reject the newer configuration. Restore the complete matching backup
store and compatible code for rollback, with writers stopped. Version3 runtimes cannot read version4 evidence-blob stores.

## Fedora timer installation

`scripts/install_runtime.py --brain /path/to/store` copies the exact Python package
into a content-addressed runtime directory, checks an existing copy's hashes and
atomically switches `runtime/current`. It requires a writable supported store and
does not install or enable systemd units. Review and test the package before pinning.

The checked-in service/timer templates target `%h/Documents/The Brain/Project-Brain`.
For another installation, adjust WorkingDirectory, the explicit `--brain` argument
and ReadWritePaths together. The service runs from the pinned package, restricts
writes to the store, and sets a process time/memory limit. The timer checks due work
each minute; the saved source interval prevents minute-by-minute capture. Persistent
scheduling handles missed timer events after startup; it does not certify actual
hardware sleep/reboot behavior without a workstation acceptance run.

After reviewing the paths and opting in the intended source, install the templates
in the user's systemd unit directory, reload that user's manager and enable
`brain-refresh.timer`. Inspect both timer state and source health: a successful
service exit can mean no source was due, not that a new capture occurred. Disabling
the timer stops scheduled invocation; policy pause and source disable remain useful
independent controls. This document does not enable anything by itself.

## Validation scope

The original refresh delivery matched pinned runtime `227e5c7fbcf35d6bb8f6`.
The newer package in this branch adds writer4 and must be validated separately
before activation; it has not replaced that live pinned runtime.
The suite covers repeated saves, unchanged storage, corruption, failed publication,
source disappearance/recovery, persisted retry after process restart, contention,
pause/resume, partial writes and capacity limits. The live curated-note deployment
has also produced repeated scheduled captures; only that source is enabled.
Tests and observed service operation do not establish owner resumption benefit or
native hardware sleep/reboot acceptance. No model runtime is included.
