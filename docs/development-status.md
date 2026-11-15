# Development execution status

Updated 10 November 2026. [Development plan](development-plan.md) is the delivery
scope; [vision](vision.md) remains the product direction. This ledger records
implementation evidence, not acceptance of the entire plan.

## Inspected baseline

- Workstation: Fedora 44; Python 3.14.10.
- Local HEAD: `de1384e06e0339948637c6aab3bdaabad25e48bf` with pre-existing uncommitted
  correction/retrieval features in core, CLI, README and `tests/test_corrections.py`.
  Those changes were preserved. Initial suite: 27 tests passed.
- Remote main: `773a803a0a9939cc4fd33a7ae5c937d57a781d34`.
- Existing briefing PR head: `dba69ef01233278fe847541966a65419fd18807f`.
  Fetched into an isolated checkout; no remote branch was changed.
- Initial live store: `Project-Brain/`, schema 1. It was upgraded through writer schema 2 to schema 3 with verified backups; historical logical snapshot schema stays 1.

## Implemented locally

### B01: duplicate cache repair

Reuse extracted records only when the previous inventory entry was `retained`,
not merely when its path and hash match. A duplicate promoted to the surviving
copy is extracted; a completed empty-file extraction remains cacheable.

The added regression suite first failed for removal, exclusion, and promotion
after an earlier-sorted duplicate disappeared. It now passes and checks searchable
surviving evidence, path/hash correctness, immutable snapshots, unchanged source
content, empty-file cache hits, and separation of sharing approval by record ID.

### B02: automatic checks configured

`.github/workflows/tests.yml` runs unittest on Python 3.11 and 3.14, with read-only
repository permissions. The local environment is Python 3.14.10. Hosted CI and
Python 3.11 execution remain unverified until the workflow runs remotely.

### B05: existing briefing baseline integrated

Imported the PR's implementation and nine tests, preserving its evidence spans,
bounded excerpts, omitted counts, explicit unknowns, predecessor comparison and
suggestions separated from commitments. Integrated the existing local correction
feature: obsolete records are suppressed even when their replacements disappear,
and correction publications preserve predecessor links. Added a regression for
this interaction. This is the baseline, not completion of B05: source health and
freshness are now implemented below; useful selection still requires the pilot.

## Validation

Command: `python3 -m unittest discover -s tests -v`.
Result: **64 tests passed** on Fedora 44 / Python 3.14.10.
`git diff --check` passed. Changes are an uncommitted working tree over the local
HEAD above; `docs/development-validation.json` identifies the tested file hashes.

A coherent copy of the real store was taken while holding its writer lock.
On that copy, all 175 historical snapshots validated (28,336 record instances;
zero relationship warnings), and all 49 active project briefings built without
error. This verifies structural compatibility, not the quality of each briefing.
The original store was not migrated or refreshed by that check. Private copy and
verification results are under `/tmp/brain-plan-compatibility-azzulsxq/` and are
temporary, not a durable rollback backup. Before a schema migration, create a
durable compatible code/store backup and exercise failure recovery.

## Remaining delivery gates

| Scope | State and next evidence required |
| --- | --- |
| B01 | Focused duplicate-cache repair published as draft PR #2 at 526d6866b37a44e047013bf7b260151c3ec9cec9; isolated regression, local tests and hosted Python 3.11/3.14 CI pass. |
| B02 | Workflow published in draft PR #2; hosted 3.11/3.14 run 42790214633 passed both jobs. |
| B03 | Implemented locally: source IDs, saved settings, resets, relocation, independent sources, opt-in and atomic effective configuration; 12 source/migration tests cover B03/B04 together. |
| B04 | Implemented locally: file observations, complete/partial/failed capture health, unknown legacy dates, independent sharing expiry and explicit observation-age filtering. |
| B05 | Source health and measured ranking improvements integrated; semantic and owner acceptance gaps remain. |
| B06/M2 | Reproducible real-history checkpoints, external keys, same-corpus replay, held-out synthetic case, execution receipt and cost measurements implemented. Owner resumption baseline and semantic gaps remain. |
| M3 | Worker, storage/work limits, retry, pause/resume and service units implemented. Fixture failure cases and a real transient timer run pass; real-source activation was explicitly approved and its first scheduled capture verified. |
| M4 | Deterministic stable items, evidence relationships and correction undo implemented. Portable model input/proposal validation implemented; actual local runtime adapter and host evaluation remain pending. |
| M5 | Measured storage and copy-only lossless evidence compaction implemented; production activation and second-project owner acceptance remain pending; explicit purpose-preserving support consolidation is tested locally. Tinker consumer and real-history technical pilot are tested locally. |
| Deployment | Local store upgraded with verified backup; curated-note service installed and verified. No model selected; focused delivery PRs #2 and #3 are published as drafts. |

Stable state and correction undo are implemented locally. Remaining M4 work is
evaluated local interpretation and host-specific runtime validation.
M3 curated-note activation was approved and its first scheduled run verified. Owner resumption measurement is pending; this does not block
independent implementation work. The
store sits inside the application checkout, so a self-pilot must use a selected
source copy or independent store to preserve the existing non-overlap rule. Do not
ingest this entire checkout into its own store.

## B03/B04 implementation and deployment

Source identities are independent from project identity. The first source keeps
legacy paths; explicit additional sources use UUID namespaces and refresh without
removing other sources. Omitted settings reuse saved values; explicit clearing,
historical changes, budget resets, relocation and opt-in are exposed through the
CLI. Effective configuration and snapshot pointers publish atomically. Legacy
single-location settings are seeded only on explicit ingestion; ambiguous locations
require explicit reviewed adoption and do not become automatic targets.

Successful retained/duplicate reads carry observation timestamps and configuration
revisions. Cached extraction timestamps stay unchanged. Failed, excluded and skipped
reads receive no new observation. Snapshot health tracks partial/complete captures;
failed attempts are separate operational health and preserve the last published
snapshot. Same-project context no longer expires due to extraction age. Explicit
observation-age filters exclude unknown dates. Sharing approval remains independent;
consolidation preserves supplement observation dates.

Tests cover persistence across new Brain instances, explicit resets, multiple
sources, relocation, atomic failure, source outages/recovery, automatic opt-in,
500-day-old extraction after refresh, unrenewed approval, failed/skipped reads,
pinned dates, legacy unknowns, ambiguous adoption, failed upgrade and the CLI.
A lexical limitation found during these tests: punctuation at the end of words is
retained by the current tokenizer (`indexing.` differs from `indexing`). Record this
as a measured retrieval miss for B06 rather than claiming semantic retrieval works.

Before deployment, upgraded a coherent real-store copy at
`/tmp/brain-source-migration-2gy_3xtg/`: 176 snapshots validated, 49 briefings built,
scoped context and archive verification passed, all store files except config were
byte-identical, and the actual upstream schema-1 reader rejected the new writer
version. Failed upgrade and failed snapshot publication are covered by injected
failure regressions.

Applied the version guard to the local store using `upgrade-store`. Durable private
backup: `backups/source-settings-v2-20261110/`. Its rollback manifest contains file
hashes; all original files except config remained byte-identical after upgrade.
`legacy-code/brain` is the pre-upgrade code, verified against the prior 39-test hash
manifest, and can write the backed-up schema-1 store. `code/brain` is the upgrade
reader, whose schema-1 mode is read-only. Stop writers and preserve post-backup
captures before any rollback; restore a compatible code/store pair. No service
or source was enabled for automatic capture.


## B06 pilot and measured briefing improvements

See `evaluations/README.md` and `evaluations/pilot-results.json`. Selected public
main/briefing revisions and the current checkout form real history checkpoints;
an explicitly labelled agent report supplies failure/rationale context. A captured
unittest receipt includes the executed command, environment and working-tree hashes.
Keys and reports stay outside ingestion scope. The synthetic ceramics case is a
held-out mechanical check, not a second real-project acceptance trial.

Replayed the exact same snapshots with the revised reader: current-history target
phrase hits increased from 2/5 to 5/5; main vision improved 0/1 to 1/1; held-out
remained 3/3. The expanded vision remains 0/2 for its two target phrases, though its
substantive workstation-memory objective is visible. All selected excerpts resolve
to retained evidence, with no private canary leaks. 54 unit tests pass.

Selection now prefers substantive explicit headings, diversifies source paths,
separates attempts and currency-unreviewed next-step statements, suppresses bare
metadata, and keeps code strings out of the proposal section. Missing immediate-
predecessor context is cited as unavailable, never resolved. Retrieval-only terminal
full-stop normalisation fixes measured punctuation misses without changing stored
legacy indexes.

These checks do not establish semantic acceptance: an old roadmap can still supply
a next-step phrase; truncation omits useful policy text; unavailable-context carryover
currently covers one predecessor rather than stable unresolved state. Owner review
was requested asynchronously. Human resumption times remain unknown.

An unchanged pilot capture added 359,548 bytes despite nine extraction cache hits.
That is concrete evidence for lightweight observations and capacity limits before
unattended capture. The retained corpus and before/after briefings are stored locally
under `evaluations/runs/2026-11-10/` and excluded from Git.


## M3 worker and lightweight observation storage

Unchanged evidence now uses `observation-1` storage records with a one-hop reference
to an immutable full content snapshot. Each observation preserves its own inventory,
configuration, source health, timestamp and predecessor. Readers and archives return
materialised complete evidence; the original snapshots and approvals are unchanged.
The exact pilot corpus now uses 5,141 bytes instead of 359,548 for an unchanged
refresh (98.57% reduction), with valid materialisation and verified export.

`RefreshWorker` implements explicit enablement, persisted policy, pause/resume,
source due times, bounded exponential retry, fair ordering, global per-run file/byte/
time limits and storage capacity. Runtime limits do not rewrite saved source settings.
A dedicated worker lock prevents overlapping passes; background capture defers on
manual writer contention. Saved `running` markers are checked against the actual
lock and recovered with backoff. Capacity defers new evidence without deleting it.
Control updates have reserved space; an already over-limit store remains readable.

64 tests pass, including source outage/recovery, partial writes, repeated saves,
failed publication, paused scheduling, runtime limits, capacity, writer contention,
observation integrity, chronology and approval preservation. Fedora unit verification
passed. A transient systemd user timer ran the hardened service against a disposable
source, captured a subsequent edit, and exited successfully; snapshot validation and
retrieval confirmed it. The transient units were automatically unloaded afterward.
See `evaluations/refresh-results.json` and `systemd/README.md`.

A coherent real-store copy validated 178 historical snapshots; existing files except
config were byte-identical, an observation refresh and archive succeeded, and the
actual version-2 writer rejected configuration version 3. Applied the version-3 guard
to the local store with durable backup `backups/observation-storage-v3-20261110/`.
`legacy-code/brain` preserves the verified pre-upgrade version-2 writer for rollback.

The user explicitly approved the curated-note source. Installed and enabled the
Fedora user timer, enabled only source `c0124389-159b-4733-af8e-30503e87fb00`, and
unpaused its 15-minute/1-GiB policy. The first scheduled service run exited with
success; worker state and a valid new observation snapshot independently confirmed
capture. Every other project remains outside automatic targets. The service now
runs pinned package `227e5c7fbcf35d6bb8f6`, isolating it from ongoing checkout edits.
The queued milestone note was captured at the next normal due run without manual
intervention. Retained evidence, snapshot validation and scoped retrieval passed.
Owner resumption acceptance
and a second real-project pilot also remain pending.

## M4 deterministic state foundation

Added private stable items for decisions, ideas, attempts and blockers, with separate
work stage, evidence strength, currency and memory purpose. Explicit corrections
and relationships cite same-project retained evidence; append-only undo preserves
the audit trail. Contradictions remain visible and supersession rejects cycles and
competing replacements. A missing document does not resolve its blocker.

Immutable derived catalogues preserve candidates beyond the recent-history budget.
Capture publishes catalogue and snapshot pointers together; unchanged captures reuse
catalogues. Bounded legacy backfill reports unknown lineage and handles stale
catalogues from compatible capture writers. Read-only briefings show candidates and
reviewed interpretations distinctly, with bounded excerpts and coverage warnings.

77 tests pass on Python 3.14.10, including failed pointer publication, cross-project
isolation, unchanged storage, blocker persistence, correction undo, malformed undo
rejection, and stale-catalogue reconciliation. Existing historical decisions remain
uncertain until explicit precedence is recorded; the briefing test now checks this
rather than assuming changed wording automatically supersedes an older claim.
See `docs/maintained-state.md`. The scheduled service remains pinned to the earlier
64-test runtime while this foundation is developed. An evaluated local model adapter,
real-project state evaluation, human resumption review, sustainable compaction and
a consumer integration remain unfinished. The full goal is still active.

## M4 portable model evidence boundary

Added read-only model-input/model-check commands and same-corpus input preparation.
Input packing is project-scoped, bounded, screened and reproducible against immutable
evidence. Model outputs require exact quotations; structural validity does not certify
semantic correctness or change reviewed state. Eight new contract tests pass.
Role-diverse packing recovered five of five current-checkpoint reference phrases
where alphabetical packing recovered zero; this is input coverage, not inference.
See docs/local-model-evaluation.md. Hosting device access and runtime evaluation are
deferred at the user's request; no model was installed or run.

## M5 lossless evidence compaction trial

Writer version 4 adds project-scoped compressed evidence blobs for meaningful new
captures, with the existing observation format for unchanged captures. Canonical
evidence, citations and record identities remain unchanged. Older stores remain
readable; the actual version-3 runtime is retained for the live store.

The copy-only compactor checks every materialized snapshot for equality and preserves
approvals, state and export artifacts. It publishes only a complete verified copy;
there is no in-place rewriting or deletion. The copy's automatic policy is paused.
The live store and its pinned timer remain on version 3. A durable compact trial
with compatible pre/post code copies is in backups/compaction-v4-20261110/.

95 tests pass, covering cross-capture blob reuse, unchanged observations, publication
failure, safe retry, missing/corrupt blobs, traversal rejection, capacity, immutable
history, copy failure, reviewed state, approvals, exports and legacy upgrades.
The initial real-store trial preserved all 181 canonical snapshots and reduced
physical bytes by 68,641,025 (40.5%) before receipt overhead. See
docs/storage-compaction.md for boundaries and remaining activation work.

The full copy trial also produced identical briefings and representative retrieval
results for all 49 active projects. Actual pre-change version-3 code rejected the
version-4 compact store. Copy preflight now rejects unexpected symlinks; its regression
passed. The cross-project retrieval scan made the full comparison slow, exposing a
separate performance issue for the next implementation cycle.

## Retrieval scope and latency repair

Retrieval now inspects sharing metadata before loading foreign snapshots. It loads
only the requested project and projects with unexpired approvals compatible with
the requested technologies, then checks the actual current record/evidence hash.
Invalid or mismatched approval identities confer no permission. Revocation is read
again on the next query; no persistent approval cache was introduced. Corruption in
an unrelated unapproved project no longer breaks a scoped query, while corruption
in a contributing project still fails closed.

101 tests pass, including six new scope/security regressions. On the unchanged
49-project compact trial, three fresh-process comparisons without foreign technology
and three with SQLite sharing returned identical complete structured results.
Median measured time fell from about 4.1 seconds to 8 milliseconds; snapshot loads
fell from 49 to one/two. Peak process RSS fell from roughly 99,000 KiB to 19,000 KiB.
These are local observations, not universal performance guarantees. Reproduction
and exact samples are in scripts/benchmark_retrieval_scope.py and
evaluations/retrieval-performance.json. The pinned timer runtime is unchanged.

Read-only discovery found the existing local Tinker application and its native
Project workspace. Consumer integration preference is being clarified; no Tinker
code or user data has been changed, and no Tinker source has been ingested.

## Maintained-state pilot and Python compatibility

The default state display now balances item kinds and source paths while retaining
explicitly reviewed-item priority. On the same captured local-history checkpoint,
reference-phrase visibility improved from two of five to four of five. All displayed
claims traced to retained evidence. A simulated absence extension removed only the
copied capture-review note, added ten later captures, and retained its three stable
items under a one-snapshot scan budget without changing work stage or currency.
The original pilot corpus remained byte-identical. The fifth next-step phrase and
expanded-vision phrases remain outside the short state display; objectives continue
in briefing sections. These checks do not establish semantic or human acceptance.
See evaluations/maintained-state-results.json and scripts/evaluate_maintained_state.py.

All 103 Brain tests passed on both Python 3.14.10 and the newly discovered local
Python 3.11.18. Hosted CI remains unrun; read-only GitHub inspection confirmed PR #1
is still open at dba69ef01233278fe847541966a65419fd18807f with no check runs.
The user chose Tinker's Project workspace as the first consumer. Implementation and
Qt verification are now in progress, separate from automatic source capture and
model-context submission.

## Tinker Project memory consumer

The user selected Tinker's existing Project workspace. Added its Project memory tab
with explicit trusted executable/store/project selection, bounded asynchronous reads,
plain-text briefings, capture health and pinned retained-evidence citations. Opening
the view performs no read. It does not ingest, share, enable capture, invoke a model
or attach memory to chat. Clear, Revoke, owner changes and shutdown cancel requests
and discard memory/path selections. Existing Tinker changes were preserved.

All 50 focused Project tests passed on Python 3.11.18 / PySide6 6.11.3, including
seven new memory tests. The first sandboxed run passed 42 but eight existing model
transport fixtures timed out before Ready; rerunning with local subprocess/socket
access passed all 50. A real Brain CLI disposable-store trial loaded project metadata,
a briefing and exact retained evidence, preserved every store byte and left model
context empty. Owner revocation cleared the memory view. Visual offscreen review
confirmed the tab and prompted readable UTC dates and citation deduplication.

Evidence: evaluations/tinker-memory-results.json and scripts/check_tinker_memory.py.
Consumer implementation is in the existing Tinker checkout: ui/project_memory.py,
ui/project.py, tests/test_project_memory.py and docs/PROJECT_MEMORY.md. Native desktop
and installed-wheel acceptance remain pending. This is not a second real-project
capture trial; Tinker's source/data were not imported. Hosting-device work remains
deferred, and the full development goal remains active.

## Focused B01/B02 delivery

Prepared a separate clean checkout against current upstream main
773a803a0a9939cc4fd33a7ae5c937d57a781d34. The duplicate regressions fail on that
revision (surviving paths lose searchable records), then all 23 tests pass on
Python 3.11.18 and 3.14.10 with the retained-status cache guard. Published only the
repair, its tests, focused documentation and CI workflow at
526d6866b37a44e047013bf7b260151c3ec9cec9 on codex/fix-duplicate-cache.
Draft PR: https://github.com/BigBenKenobi/The-Brain/pull/2. The broader worktree,
installed timer, original main branch and existing briefing PR #1 are unchanged.
Hosted CI was confirmed running as 42790214633; final result is recorded separately
in evaluations/b01-delivery-results.json. This does not publish the later milestones.

Hosted delivery verification completed: both Python 3.11 and 3.14 jobs passed for
PR #2 at the published commit. The PR description now links the successful run.
PR #2 remains draft and unmerged; this closes the hosted-check gap for the focused
B01/B02 slice, not for the full 103-test local development state.

## Second real-project technical pilot

Captured three explicitly selected tracked Tinker documents at three exact Git
revisions in an independent pilot store. No application database, chats, model files
or working-tree edits were imported. This exposed a generalization gap: substantive
release-gate table rows were retained/searchable but absent from briefing/state.

Deterministic-4 splits prose table rows into exact retained spans and includes them
as uncertain candidates; numeric metadata tables remain excluded. Recorded failure
language ranks ahead of general table checklist prose, and source introductions
can describe objective candidates without asserting release acceptance. New record
IDs bind extractor version and full span so changed extractions cannot inherit old
sharing approvals. Historical snapshots and approval files remain unchanged; the
live pinned runtime has not been updated.

Paired reference visibility improved from 1/3, 1/3, 2/5 to 2/3, 2/3, 3/5. The timeout
and connectivity limitation are now represented in maintained state. All selected
excerpts trace to retained evidence; all reference phrases remain context-retrievable.
Unchanged refresh, outage preservation/health and recovery pass. The retired-gate
nuance and some qualification text remain short-view misses. Full evidence and
limitations: evaluations/second-project-results.json and
 evaluations/second-project-review.md. This completes a second-project technical
trial, not owner resumption or model acceptance.

All 109 tests pass on Python 3.11.18 and 3.14.10. Replaying the original immutable
first-project corpus retains 5/5 current-context hits and 3/3 held-out hits, with
all excerpts traceable; the expanded-vision 0/2 short-excerpt limitation remains.

## Installed Brain–Tinker integration verification

Built both wheels from separate byte-copied source trees; original build directories
and application environments were not modified. Installed wheels into the isolated
Python 3.11.18 / PySide6 6.11.3 environment, then ran from `/tmp` with Python `-I`.
Both Brain and Tinker's memory module resolved under site-packages. The installed
Brain entry point successfully supplied metadata, a briefing and retained evidence;
store bytes/model context stayed unchanged and Revoke cleared the view.

All 109 Brain tests and seven focused Tinker memory tests passed against installed
packages outside their checkouts. `pip check` reported no broken requirements.
Wheel SHA-256 values, source manifests, logs and an offscreen screenshot are retained
under evaluations/runs/2026-11-10/installed-memory/; compact results are in
evaluations/installed-memory-results.json. `scripts/check_tinker_memory.py --installed`
now supports reproducing the actual entry-point check without source-path injection.

This closes the focused installed-package consumer check on Python 3.11. It does
not establish native KDE acceptance, the whole Tinker release matrix, owner resumption
benefit or model quality. No release was published and live services are unchanged.

## Purpose-preserving duplicate consolidation

Added explicit `state-consolidate` with append-only undo. Equivalent reviewed items
can share one displayed identity and a combined evidence set while preserving their
original identities in history. Grouping requires matching kind, stage, currency and
purpose, rejects contradictory/superseding members, and retains other relationships
on their original endpoints. Later conflicting canonical precedence flags review
instead of silently certifying the group. Undo validates dependency replay before
publication so an earlier correction cannot be withdrawn into an unreadable journal.

State journal head version 2 guards the new event type; an actual older reader was
confirmed to reject it. This does not alter store version or canonical snapshots.
117 tests pass on Python 3.11.18 and 3.14.10. A CLI trial combined two cited claims,
validated an evidence export, and restored the exact original items via undo while
preserving snapshot and sharing approval bytes. No production items were grouped.
Results: evaluations/consolidation-results.json. This implements explicit useful
support consolidation, not semantic forgetting, evidence deletion or journal pruning.

## Source-settings delivery prepared locally

Isolated branch `codex/persistent-source-observations` at
`a4a0b3669d456b919367054e9b715354e6dc2432` builds on the briefing PR and
the duplicate-cache repair. It delivers saved sources, observation freshness,
capture health, correction-aware briefings and explicit version-2 migration.
All 54 tests pass on Python 3.11.18 and 3.14.10. A verified complete Git bundle,
patch and logs are retained in evaluations/runs/2026-11-10/source-settings-delivery/.

After explicit user approval, the branch was published as draft PR #3:
https://github.com/BigBenKenobi/The-Brain/pull/3. Hosted Python 3.11/3.14 jobs
both passed in run 42794187421.
No live store or runtime was changed. This historical writer-2 delivery cannot read the live
writer-3 store or the current writer-4 development store. Results:
evaluations/source-settings-delivery-results.json.

## Configuration evidence classification

Real-history replay exposed pyproject.toml occupying an objective slot because
metadata contained “project” and “tool.” Known configuration formats now have an
observed-configuration section and do not seed automatic decisions or blockers.
Existing reviewed journal corrections still replay; canonical records, historical
snapshots and sharing approvals are unchanged. JSON/YAML remain outside this
filename rule because they can contain narrative exports.

119 tests pass on Python 3.11.18 and 3.14.10. Both project-history pilots preserve
their preceding phrase scores and traceability. All external answer phrases remain
in the bounded model-input packs. The expanded-vision short-view miss remains 0/2;
this change fixes misleading classification, not the long-excerpt limitation.
Results: evaluations/configuration-context-results.json. This work is local and
is not included in source-settings PR #3. Live services are unchanged.

## Current installed consumer: grouping conflicts

Tinker's Project workspace now shows combined support, retained original identities
and the explicit consolidation-conflict warning emitted by Brain. Its regression
test verifies both supporting citations survive. The real-CLI trial builds a grouped
item, adds later canonical precedence, opens the absorbed item's evidence and checks
that neither store bytes nor model context change. Revocation clears the view.

Both current wheels were built from isolated source copies and installed into the
existing disposable environment. From outside the checkouts with Python `-I`,
119 Brain tests and eight Tinker memory tests pass on Python 3.11.18 / Qt 6.11.3.
The configuration section and conflict warning were visually checked offscreen.
Source manifests, wheel hashes, logs and screenshot are retained under
evaluations/runs/2026-11-10/installed-memory-current/. Results:
evaluations/installed-memory-current-results.json. No package was published or
live application/service changed; native KDE and human acceptance remain pending.

## Full-plan acceptance audit and live refresh follow-up

The requirement matrix in [acceptance-audit.md](acceptance-audit.md) separates
technical implementation, delivery, deployment and owner/model acceptance. It
identifies remaining semantic/critical-context, independently-verified-behavior,
host-model evaluation, native acceptance and resumption-measurement gaps. The goal
is not complete.

Read-only live inspection found the approved timer active and its latest inspected
service exit successful. Only the curated Brain source is enabled;900-second source
interval and1GiB cap remain configured. Pinned runtime hashes match. Nine scoped
snapshots include lightweight unchanged observations and subsequent scheduled
notes; current retained evidence validates. No service or source settings changed
and no capture was forced. Operational receipt: evaluations/live-refresh-followup.json.
Hardware sleep/reboot is not proven by a process-restart fixture.

## Measured long-record preview improvement

Explicitly headed prose now offers exact paragraph candidates for the bounded
briefing. Opening emphasis can prioritize a source's guiding statement; it never
changes evidence strength. Each preview keeps the canonical record ID, whole source
span and exact character offsets. Code, configuration, fences and unheaded records
retain their preceding behavior. Tinker labels partial records and opens the full
cited evidence. This is a read-only projection, not re-extraction or migration.

The final immutable first-corpus replay improves expanded vision0/2→2/2 while
preserving current5/5, unchanged5/5 and heldout3/3. The second real-project trial
remains2/3,2/3,3/5. All excerpts trace to retained text.122 tests pass on Python3.11
and3.14; eight focused Tinker tests pass. Results and precise limits are recorded
in evaluations/briefing-preview-results.json. Prior intermediate replays are retained
as experiments; only replay-preview-final and tinker-preview-final describe the
final implementation. These local changes are not deployed or published.

## Automatic-refresh delivery prepared

Local commit b76062b0e216c65f61d74fe5c95cf23f2a13486a on
`codex/bounded-local-refresh` is stacked on source-settings PR3. Its seven package
files exactly match live pinned runtime227e5c7fbcf35d6bb8f6. The slice adds the
bounded opt-in worker, lightweight writer3 observations, service templates, runtime
pinning and operation/rollback documentation. It excludes later state/blob features.

64 tests pass on Python3.11.18 and3.14.10. `systemd-analyze --user verify` passes
for both templates. A disposable installer fixture verified repeatable pinning,
default paused policy, actual pinned CLI loading and rejection of altered runtime
bytes. The complete Git bundle verifies and is saved with patch/logs under
evaluations/runs/2026-11-10/refresh-delivery/. No live service was changed.
The user approved publication; draft PR4 is open at
https://github.com/BigBenKenobi/The-Brain/pull/4. Hosted Python3.11/3.14 jobs
both passed run42797179112. Results are recorded in
evaluations/refresh-delivery-results.json.

## Explicit qualification caveats

The latest Tinker pilot retained a retired qualification that explicitly had not
passed, but no excerpt was selected. Briefings now expose explicit verification
limits in a separate source-caveat section. A matching paragraph can be previewed
with exact record offsets even under an otherwise unclassified heading. The rule
does not infer a blocker, pass, accepted work stage or verification strength.
“Not only passed” and “not just passed” are excluded from negation matching.

124 tests pass on Python3.11.18 and3.14.10. The latest Tinker checkpoint improves
3/5→4/5, with earlier checkpoints unchanged2/3 and2/3; first-project scores remain
current5/5, unchanged5/5, vision2/2 and heldout3/3. All reference phrases remain
in bounded model inputs. The displayed retired-gate paragraph retains the explicit
not-a-blocker, not-passed and no-remote-issue-closure qualifications. The implementation
is local; PR4 contains only the separately tested automatic-refresh slice. Receipt:
evaluations/qualification-results.json. Other semantic and owner/model gates remain.

## Expanded consumer view

Tinker's Project workspace now offers Brief (three excerpts per section) and
Expanded (eight). Changing detail clears prior results without starting a read;
Load briefing remains explicit and Revoke restores Brief. Response/time limits
and citation bindings are unchanged. The exact final Tinker pilot snapshot shows
4/5 reference statements in Brief and5/5 in Expanded, including connectivity scope.
Every displayed excerpt traces to retained evidence. This does not make the default
view complete or establish semantic acceptance.

New isolated wheels pass124 Brain tests and nine Tinker consumer tests outside
their source trees with Python3.11.18 `-I` / Qt6.11.3. The real CLI/UI trial reveals
omitted context on expansion, preserves conflict/configuration displays, opens an
absorbed item's evidence, preserves store bytes/model context and clears on revoke.
The offscreen screenshot was inspected. Artifacts and limits:
evaluations/expanded-memory-results.json. No published package or live runtime changed.

## Maintained-state delivery prepared

Local commit5c6ceaf2941a18c102153c2165074dc7f1f3d784 on
`codex/maintained-project-state` builds on refresh PR4. It delivers deterministic
items, catalogue persistence, evidence-backed correction and undo, relationship
checks, bounded history, balanced display and the tested configuration/paragraph/
qualification briefing improvements. Store writer3 and journal reader1 remain
explicit; model boundary/transport, blobs and support consolidation are excluded.

86 tests pass on Python3.11.18 and3.14.10. This exact isolated reader replayed the
first corpus with1/1,2/2,5/5,5/5,3/3 reference hits and exact excerpt traceability.
The source corpus's file hashes stayed unchanged. Bundle, patch, logs and pilot
receipt are retained in evaluations/runs/2026-11-10/state-delivery/. Results:
evaluations/state-delivery-results.json. The user approved publication; draft PR5 is open at
https://github.com/BigBenKenobi/The-Brain/pull/5. Hosted Python3.11/3.14 jobs
both passed run42799274286. No live
runtime changed. Unit and phrase checks do not establish model or owner acceptance.

## Compaction validates derived-state behavior

Regression tests showed compact-copy could publish a verified-looking destination
when a published state event was missing or a catalogue referenced an absent record.
The new gate validates every active catalogue and published journal reference,
including undone-event evidence, before publication. Canonical saved hash/span
metadata must match. Replayed state fingerprints must match between original and
copy; byte-preservation checks remain in place.

128 tests pass on Python3.11.18 and3.14.10. Four new regression cases cover grouped
conflicts/undo, missing published events, absent catalogue records and damaged
undone-event evidence. Failed validation leaves no destination and preserves the
original. Results: evaluations/compaction-state-integrity-results.json. These are
local changes; no live store migration or runtime activation was performed.

## Sustainable-storage delivery prepared

Local commit2a1aaac22f18e131a95510a0d50c04936671a03f on
`codex/evidence-storage-consolidation` builds on state PR5. It delivers writer4
evidence blobs, copy-only verified compaction including derived-state validation,
journal2 support consolidation/undo, table-span extraction and scoped retrieval
prefiltering. No model transport or runtime activation is included.

120 tests pass on Python3.11.18 and3.14.10. An explicit disposable CLI trial created
a writer3 store with the preceding delivery, previewed and copied it to writer4,
verified maintained-state access and an archive, and confirmed the actual preceding
reader rejects the copy. Original hashes stayed unchanged. A verified complete
Git bundle, patch and logs are retained in evaluations/runs/2026-11-10/storage-delivery/.
Results: evaluations/storage-delivery-results.json. Publication awaits approval;
no live store or runtime was changed.

## Offline proposal-boundary delivery prepared

Local commitc5b4c26f43f9dcd864b5d523d22a833bdc7604f0 on
`codex/offline-model-boundary` builds on the prepared storage commit2a1aaac. It
adds only bounded evidence export, offline proposal validation, preparation tooling
and documentation/tests. All Brain Python package bytes in this staged stack now
match the current development package.128 tests pass on Python3.11.18 and3.14.10.

An explicit disposable CLI trial exported input, validated exact-quote proposals
as unreviewed/unknown-stage, rejected oversized files and duplicate keys, and
preserved every store byte. No model was invoked or attested. The verified complete
bundle, patch and logs are retained in evaluations/runs/2026-11-10/model-boundary-delivery/.
Results: evaluations/model-boundary-delivery-results.json. This branch remains local
while storage-parent publication approval is pending. It does not complete M4's
actual local-runtime adapter or host evaluation requirement.

## Tinker consumer delivery prepared independently

Tinker commit6e3987dcddfcb3280707c47afec72691be0d0071 on
`codex/project-memory` is isolated over424d1b52b69147a3ff29d32b3c2721e3b1d70109.
Only five integration files are included; unrelated development edits remain in
the original Tinker checkout. The change adds a read-only Project memory tab with
bounded explicit reads, Brief/Expanded detail, exact evidence binding, conflict
and truncation warnings, and owner revoke/cancellation.

All52 Project assistant/memory tests pass with local fake-runtime process/socket
access; sandbox restrictions caused eight readiness timeouts in the first run.
The isolated installed wheel passes nine memory tests and the actual Brain CLI
workflow from outside both checkouts. Runtime module bytes match the commit and
the screenshot was checked offscreen. Verified bundle, patch, wheels and logs:
evaluations/runs/2026-11-10/tinker-delivery/. Receipt:
evaluations/tinker-delivery-results.json. Publication awaits approval for the
Tinker repository; no merge, deployment or native acceptance is claimed.

## Current-store preactivation rehearsal

The exact tested package at local commitc5b4c26 copied the current live writer3
store into backups/preactivation-20261110/store without activating it.188 canonical
snapshots compared equal; all188 original physical snapshot hashes still match.
The copied representation fell from170,610,166 to101,793,332 bytes before its receipt
and newly pinned runtime. Refresh is paused in the copy.

Compatible code and hashes are preserved beside it. Pinned copied runtime
8c5a0bba7b4078d12b50 reads all49 project state views (752 automatic candidates,
no discovery truncation); the actual old runtime rejects the writer4 copy. The
original remains writer3 on227e5c7fbcf35d6bb8f6. There were no live derived journals,
so grouped conflict/undo migration remains fixture evidence only. Results:
evaluations/preactivation-results.json. This copy will age and is not an approved
production cutover; service paths and source permissions remain unchanged.

## Explicit open acceptance gates

The local briefing follow-up recognizes explicit pending acceptance and separate qualification gates. It surfaces a later caveat sentence with exact canonical offsets when the paragraph prefix would conceal it, and preserves ordinary product context alongside caveats. The first attempted selection displaced the model introduction; the final selection retains both. The Tinker reference checks now read 3/3, 3/3, 4/5 in Brief and 5/5 for the latest Expanded view. All first-project checks remain unchanged and traceable. Both Python versions pass 131 tests. See `evaluations/open-gates-results.json`. This is local source work beyond delivery c5b4c26; existing bundles, pinned runtimes and the preactivation copy remain unchanged. No semantic, human, or native acceptance is claimed.

The follow-up is isolated as `codex/explicit-acceptance-caveats` at `9ab32d0ed69cd7e29a236725f7f9cfd25d4109dd`, based on c5b4c26. Both interpreter suites pass131 tests. Its installed wheel reproduces first-project1/1,2/2,5/5,5/5,3/3 and Tinker Brief3/3,3/3,4/5, Expanded3/3,3/3,5/5 via the actual CLI. Every excerpt offset and evidence identity matched; original corpora and copied store bytes stayed unchanged during reads. The verified bundle, wheel, patch and executable validation script are retained under `evaluations/runs/2026-11-10/open-gates-delivery/`. Publication is not performed.

## Tinker publication and hosted validation

User-approved commit6e3987d is published in Tinker draft PR70, open and unmerged. Updated main eb8ec7f merges cleanly with the branch. Hosted run42802654326 passed Python3.11/3.14 with1839 checkout and1839 archive tests each, plus installed-package checks. Python3.12 failed twice at unchanged Note-chat token-budget test: it waits for runtime/auto-search idle but sees DocumentAdmission.pending still true at the next assertion. Both runs passed1838 tests, including all9 memory tests. The targeted test passes locally on3.11. This suggests a completion-observation problem but does not prove its cause; no test was weakened and no repeated retries will hide the failure. PR description includes the failed gate. Exact failure logs and delivery receipt retained.

Tinker CI follow-up0f0b9bd is published to PR70. Delayed terminal delivery reproduces the old Note wait failure; waiting for DocumentAdmission cleanup as well as runtime/planner idle fixes it without dropping assertions or changing the timeout. All89 Note/Project tests pass locally. Runtime application files and the original Tinker working tree are unchanged. Hosted checks for the new head remain pending.

Tinker head0f0b9bd hosted run42805111608 completed successfully on Python3.11/3.12/3.14. Each passed1842 checkout and1842 archive tests plus fresh-wheel checks. Python3.12 additionally passed the configured Affinity/LaMa installation gate. This supersedes the pending CI status above, retaining the previous failure evidence. Draft PR70 description and delivery receipts are updated; no merge, deployment, native acceptance, or Brain model-host evaluation is implied.

Subsequent merge check found main eb8ec7f independently strengthened the Note wait. Published merge-resolution head a11d51f retains its exact rejection-message assertion and retry setup, adding delayed terminal coverage and admission cleanup. All89 focused tests pass in21.14s and merge-tree is clean. Prior three-version hosted success belongs to0f0b9bd; new-head hosted validation is pending. PR70 remains draft and no main merge or deployment occurred.

Reconciled-head CI was queued behind a duplicate push run whose Python3.12 job remained live with no active step after automatic cancellation. Force-cancelling only superseded run42806830738 unblocked the existing PR run42806837566. All three jobs started normally at the same a11d51f head. No new workflow or source revision was created; final results remain pending.

Installed combined-package validation: reconciled Tinker a11d51f with Brain9ab32d0 passes9 focused installed tests and the actual CLI/offscreen trial. Expanded context, support citations, conflict warning, revoke reset and unchanged store/model context are verified. Screenshot inspected; both wheels and verified complete bundle saved under evaluations/runs/2026-11-10/tinker-reconciled/. Native acceptance remains open.

Final reconciled-head result: Tinker a11d51f PR run42806837566 passed Python3.11/3.12/3.14, with1863 checkout and1863 archive tests each plus fresh-wheel checks; Python3.12 also passed Affinity/LaMa installation. PR70 is verified draft/open/unmerged and mergeable against eb8ec7f. Receipt evaluations/tinker-reconciled-results.json supersedes pending status for this head. Native acceptance, owner resumption, Brain model-host evaluation and release gates remain open.

## Explicit command verification receipts

Added scripts/run_verification.py as an explicit caller-operated POSIX check runner. It records exact private stdout/stderr hashes, command/cwd, observed platform, Git revision and tracked status before/after, execution outcome and bounds. Timeout/output exhaustion kill the owned process group; commands are never read from captured source. Six process tests cover failure, missing executable, descendant timeout cleanup, output cap, literal shell syntax and changed tracked inputs. Both source suites pass137 tests, recorded through the runner with output hashes independently checked. Receipts remain execution_observed_not_adopted; scoped review/adoption, undo and status integration are still required. No live store or runtime changed.

## Scoped observer verification review

Added state-verify and state-receipt, preserving exact private receipt/output bytes in journal3 events. Explicit local observation/scope attestation is required, with complete successful output hashes, unchanged tracked Git revision and a recorded same-project working directory. Item-wide evidence strength/stage/currency remain unchanged. Corrections, grouping or conflicts require historical review; undo retains audit evidence. Compaction validates even undone receipts. Nine new state/CLI/process integration tests bring both interpreter suites to146; actual prior reader9ab32d0 rejects journal3 and archive fixture checks pass. This is local-only, with no live store mutation. Tinker rendering of scoped fields remains pending, as do release, semantic and owner acceptance.

## Scoped verification consumer delivery

Prepared isolated Brain9bdeade (journal3 receipt review,146 tests on both Python versions) and Tinker84d6cc5 (scoped display and fixed state-receipt reads). Tinker91 Note/Project tests and11 isolated installed-memory tests pass. The actual installed pair loads historical/conflicting scoped reviews, validates receipt identity and output hashes, opens retained outputs as plain text, preserves store/model-context bytes and clears on revoke. Screenshot inspected. Verified bundles/wheels/patches are retained under evaluations/runs/2026-11-10/scoped-memory-delivery/. No remote branch, live store, original Tinker checkout or production runtime changed. Existing published PR70 remains at a11d51f.

Copy-only rehearsal for exact Brain9bdeade preserves193 snapshots and50 other artifacts, reducing171678566 bytes to102690871 before receipt/runtime additions. Pinned copy runtime ab1479f4ac517fc09ef8 reads49 projects/762 candidates without discovery truncation or store-byte changes. Actual old live runtime rejects the writer4 copy. Live writer3/runtime227e5c7fbcf35d6bb8f6 remain unchanged; copied policy is paused. No live journals existed, so journal3 review/undo behavior remains separately fixture-tested. Receipt: evaluations/scoped-preactivation-results.json.

User explicitly approved remaining publication. Exact prepared heads now published as stacked Brain PR6(storage2a1aaac)→PR7(model boundary c5b4c26)→PR8(caveats9ab32d0)→PR9(scoped verification9bdeade), with PR6 based on PR5. Tinker scoped consumer84d6cc5 is draft PR71 based on PR70. All remain drafts/unmerged. Hosted checks newly started; local test receipts remain separate. No deployment or live store/runtime change.

Final publication checks passed: Brain PR6–9 passed both hosted Python versions with120,128,131,146 tests respectively. Tinker71 run42812059392 passed Python3.11/3.12/3.14 with1865 checkout and1865 source-archive tests on each, plus installed checks; Python3.12 also passed installed LaMa repair/network isolation. See evaluations/remaining-publication-results.json and evaluations/tinker-scoped-hosted-results.json. These results supersede the pending hosted status above without establishing native desktop or real model acceptance.

Remaining-work review confirms that the model boundary exports and validates proposals but executes no inference. No Ollama or llama.cpp executable is available on this workspace's PATH; the actual hosting runtime/model remains unspecified and hosting access remains deferred. Implementing an arbitrary runtime now would not verify compatibility with that device or satisfy the required comparative evaluation. Owner resumption measurements and native hardware acceptance also remain outstanding. Existing drafts require review/release and any live format activation requires a fresh compatible cutover. No completion is claimed.
