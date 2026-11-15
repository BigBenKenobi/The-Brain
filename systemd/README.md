# Opt-in local refresh

The prepared units target this Fedora installation:
`~/Documents/The Brain/Project-Brain`. Review the paths before using another
installation. Unit verification has passed; activation is a separate operation.

Both gates must be enabled: the worker policy must be unpaused and an explicitly
configured source must be enabled. The default policy is paused, every source
starts disabled, and no historical location is discovered automatically.

```bash
python3 -m brain --brain '/path/to/store' sources
python3 -m brain --brain '/path/to/store' configure-source SOURCE_ID --enabled
python3 -m brain --brain '/path/to/store' refresh-policy --no-paused --interval-seconds 900 --max-store-bytes 1073741824
python3 -m brain --brain '/path/to/store' refresh-once
python3 -m brain --brain '/path/to/store' refresh-status
```

After testing the application revision, install a pinned runtime with
`python3 scripts/install_runtime.py --brain '/path/to/store'`. The service runs that
hashed package copy so ongoing edits in the development checkout cannot break it.
The `runtime/current` link changes atomically; previous runtimes remain available.
Update it only after validating a new revision and store compatibility.

After the source choice is confirmed, copy the two units to `~/.config/systemd/user/`,
run `systemctl --user daemon-reload`, then
`systemctl --user enable --now brain-refresh.timer`. The timer checks due sources
each minute; each source's healthy interval defaults to 15 minutes. Repeated saves
coalesce into the next due capture. Persistent scheduling catches up after a user
session restarts; an outage or partial capture uses persisted bounded backoff.

Pause/resume at the next capture boundary:

```bash
python3 -m brain --brain '/path/to/store' refresh-policy --paused
python3 -m brain --brain '/path/to/store' refresh-policy --no-paused
python3 -m brain --brain '/path/to/store' configure-source SOURCE_ID --no-enabled
```

Stop scheduling with `systemctl --user disable --now brain-refresh.timer`. A capture
already running may finish; stop `brain-refresh.service` as well before migration or
rollback. Writer locks and atomic publication preserve the prior pointer on process
termination. A stale saved `running` marker is treated as interrupted, not as proof
of a live worker, and receives bounded retry backoff.

Default pass limits: 4 sources, 2,000 files, 8 MiB read, 30 cooperative seconds,
and 1 GiB store capacity. Runtime limits do not rewrite saved source settings.
The service imposes a 90-second process timeout and 512 MiB memory limit. Source
filesystem calls can block beyond cooperative Python timing; the process timeout
is the backstop. Capture is read-only and the service restricts writes to its store.

Automatic capture defers immediately if another writer holds the store lock. Worker
passes cannot overlap. Source outages, partial writes, failed publication and capacity
exhaustion remain visible through `refresh-status`. Capacity checks reserve atomic
publication and bounded control-state space; they never delete evidence. If an
existing store is already over the chosen limit, new evidence is deferred while
small health/status updates remain possible. Manual capture and explicit exports
are not governed by the worker's capacity policy.

Unchanged evidence uses immutable observation records referencing a full snapshot,
with independent inventory/timestamps and a one-hop content reference. Readers and
exports materialise a complete snapshot; original files and historical snapshots
are untouched. Configuration version 3 prevents version-2 writers from mishandling
this representation. Never delete a full snapshot while observations reference it.

Local checks cover repeated saves, missing sources, process restart, partial writes,
publication failure, pause/resume, writer contention and capacity exhaustion. A real
enabled timer acceptance run remains separate from unit-file verification.

The development reader now also supports writer version 4 and project-scoped evidence
blobs. The installed curated-note timer remains pinned to version-3-compatible code
and its existing version-3 store. Do not point that runtime at a version-4 compact
copy. A compact copy has its refresh policy paused; activation requires a verified
runtime/store pair and explicit service-path checks. See `docs/storage-compaction.md`.
