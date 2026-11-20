# Lossless evidence storage and reversible compaction

Writer version 4 stores retained UTF-8 evidence as compressed, SHA-256-addressed
blobs within each project's `evidence-blobs/` directory. Meaningful new captures
reuse unchanged blobs while keeping their own records, inventory and timestamps.
Unchanged captures still use lightweight observation records. Readers materialize
the same canonical snapshot objects and validate evidence hashes and source spans.
Exports remain self-contained, with no dependency on the blob directory.

No content is deduplicated across project boundaries. Missing, corrupt, oversized or
conflicting blobs fail closed. Publication writes blobs before the snapshot and
atomic registry pointer. A failed publication can leave unreachable blobs; it does
not expose an incomplete snapshot. Capacity calculations include pending blob bytes.
There is no automatic orphan deletion. The format limits each decoded evidence blob
to 128 MiB; normal capture budgets are much smaller.

## Preview and copy migration

```text
python3 -m brain --brain SOURCE_STORE storage-preview
python3 -m brain --brain SOURCE_STORE compact-copy NEW_STORE
```

Preview validates snapshots and reports evidence/storage counts and a zero-loss
plan. `compact-copy` acquires the worker and writer locks and creates a private
staging copy. It converts and compares published snapshots, including unlinked
legacy history, checks other artifacts byte-for-byte, and verifies existing exports.
Runtime symlinks must use relative paths that resolve within the copied runtime.
Only after checks pass is the destination published. Failure removes staging and
leaves the original intact. Destination must be absent and outside the source store.

Snapshot IDs, retained hashes, record IDs, citations, source observations, reviewed
state and sharing approvals are preserved. Historical snapshot files in the original
store remain byte-identical. Only their physical representation in the new copy is
changed. A receipt records original snapshot hashes and the comparison results.
The copied refresh policy is deliberately paused so two stores do not independently
capture the same intake. Its old pinned runtime is retained as an artifact, not
selected as a version-4 writer.

This command does not activate the new store, edit service units, remove the old
store, delete sources, prune memory or perform permanent erasure. Reverting the trial
means continuing to use the original store and its compatible runtime. Before any
later activation, stop writers, establish a coherent final copy, install a verified
version-4 runtime, and verify its service/store paths. If captures have been made in
the new store, preserve them before returning to an older store. Do not silently
throw away post-migration work.

Versions 1–3 remain readable by the new reader but require `upgrade-store --backup`
before new writes. An upgrade changes only the writer guard, not historical files.
It does not compact old captures. Actual version-3 code rejects a version-4 store;
this prevents an older reader from overlooking external evidence. Keep the original
compatible writer along with the source store for rollback; a new reader is not a
substitute for a historical writable runtime.

## Trial and remaining work

The initial real-store trial compared 181 canonical snapshots for exact equality.
Physical store size fell from 169,517,179 to 100,876,154 bytes before adding the
receipt: 68,641,025 bytes saved, about 40.5%. This is whole-store reduction including
records, reviews and runtime artifacts, not just evidence compression. The compact
copy is under `backups/compaction-v4-20261110/store`; it is not the live store.
Full results are in `evaluations/storage-results.json`.

This implements lossless evidence compaction. Purpose-based summarization, semantic
pruning, journal compaction, garbage collection, production activation and the second
real-project acceptance trial are separate remaining work. Omission from a briefing
continues to mean neither deletion nor resolution.

## Derived-state integrity gate

Before publishing a compacted copy, Brain validates all active catalogue references
and all published journal evidence references, including undone corrections. Missing
events, nonexistent records and mismatched saved evidence hashes/spans abort the
copy. Unpublished orphan events remain byte-preserved, not authoritative history.
This validation is independent of the ordinary display's candidate limits.

The same reader replays published state on both stores and compares fingerprints,
including bounded discovery coverage, relationships and uncertainty. The receipt
records checked projects/reference counts. Grouping conflicts and later undo remain
usable in the copy. This establishes structural/replay preservation, not the truth
of a user's interpretation. The original store remains untouched and is the rollback
path; no destructive cleanup or runtime activation is introduced.

## This delivery

The isolated delivery suite passes 120 tests on Python 3.11.18 and 3.14.10. A
separate explicit CLI trial creates a version3 fixture with the preceding delivery,
previews and compacts it, opens maintained state with the new reader, verifies an
evidence archive, and checks that the actual preceding reader rejects version4.
Original store file hashes remain unchanged. The current publication does not
activate any copy or replace an installed runtime.

Support consolidation uses journal head version2, preserves original identities and
all claims, and exposes later grouping conflicts; undo keeps its append-only history.
Configuration/writer versions and derived-journal versions are separate compatibility
boundaries. No evidence or source file is deleted by grouping.

This slice also includes the tested retrieval prefilter for explicit sharing
approvals, avoiding unnecessary foreign-snapshot loads without broadening approval.
The deterministic-4 extractor gives substantive Markdown table rows exact source
spans and binds new record IDs to extractor version and full span. Changed extraction
cannot inherit an older record's sharing approval. Existing snapshots and their
identities remain unchanged. These improvements have dedicated regression suites.

The real-store figures above describe an earlier private copy trial; its raw store
and private evaluation receipts are not distributed in this repository. They do not
replace the exact-revision tests or establish production activation of this delivery.
