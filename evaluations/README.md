# Continuity pilot

The B06 pilot uses selected files from main revision
`773a803a0a9939cc4fd33a7ae5c937d57a781d34`, briefing PR revision
`dba69ef01233278fe847541966a65419fd18807f`, and the local working tree.
It includes an explicitly labelled agent report of the duplicate-cache failure,
decision rationale and unfinished model idea. An explicitly invoked unittest run
produces a separate execution receipt with command, interpreter, return code,
output, base revision and working-tree hashes. Ingestion never executes source scripts.

Answer keys, execution receipts, reports and the store are outside the source
directory. An unrelated private canary tests project isolation. A synthetic ceramics
history is held out from Brain's real history; it is not a second real-project trial.

Run from the checkout, with a history clone containing both pinned revisions:

```bash
python3 scripts/evaluate_continuity.py --output /tmp/new-brain-pilot --history-repo /path/to/history-clone
python3 scripts/replay_continuity.py --corpus /tmp/new-brain-pilot --output /tmp/new-brain-replay
```

Output directories must be new. The first command executes the explicitly specified
test suite against the owning checkout. The replay evaluates the exact same immutable
snapshots with the current reader in a disposable store copy; it does not recapture
changed source files or alter the baseline corpus.

## 10 November results

Local retained artifacts are in `runs/2026-11-10/baseline/` and `replay/`, excluded
from Git. Compact metrics are in [pilot-results.json](pilot-results.json).

| Checkpoint | Baseline phrase hits | Revised phrase hits |
| --- | --- | --- |
| Main vision | 0/1 | 1/1 |
| Expanded briefing-PR vision | 0/2 | 0/2 |
| Current development history | 2/5 | 5/5 |
| Unchanged repeat | 2/5 | 5/5 |
| Synthetic held-out ceramics history | 3/3 | 3/3 |

Every selected excerpt resolves to retained evidence; no unrelated private canary
appeared. Source outages preserve the published snapshot and report failure. Missing
blocker evidence is described as unavailable, never as resolved. The revised reader
also cites missing context from the immediate predecessor. All 54 unit tests pass.

Measured capture-plus-assessment times were 0.028–0.279 seconds for this small corpus;
these are not general performance claims or human resumption times. One unchanged
capture added 359,548 bytes despite nine cache hits. M3 must avoid repeating full
unchanged evidence and enforce capacity before unattended scheduling.

## Manual review and remaining misses

- Phrase hits are a screening measure, not semantic acceptance. In particular,
  the B06 hit can come from the earlier roadmap's proposed sequence rather than
  the newest actual next step. Next-step excerpts are explicitly currency-unreviewed.
- Expanded vision excerpts remain bounded at 400 characters. The substantive
  workstation-memory objective is visible, but the exact continuity sentence and
  purposeful-memory statement remain omitted. Their evidence remains retrievable.
- Code containing secret-pattern examples can be omitted by source screening. The
  omission is reported; the pilot does not bypass screening to inflate coverage.
- Immediate-predecessor context does not maintain an unresolved blocker forever.
  Stable state and evidence-backed resolution/supersession remain M4 requirements.
- Semantic interpretation, contradictions, complete recall and user usefulness are
  not proven by these checks. The human resumption baseline is still missing.

Changes driven by these misses prefer substantive explicit headings, diversify
selected source paths, suppress title/metadata-only excerpts, distinguish code strings
from project proposals, and show attempts and next-step statements separately.
Retrieval strips terminal full stops while leaving canonical historical indexes
unchanged, fixing the concrete `thermal drift.` and version-number matching misses.

## Owner resumption measurement

Use [owner-review.md](owner-review.md) after genuine returns to work. Record actual
time and important misses; do not fill in estimated or agent-generated timings.
The product milestone remains unaccepted until this evidence exists.
