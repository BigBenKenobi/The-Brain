# Project Brain

> **North star:** Brain makes it easy to switch between projects and ideas without
> losing your place. It captures, organises, preserves and retrieves meaningful
> context with minimal manual maintenance, so you can return to work without
> reconstructing decisions, progress or reasoning.

**The core requirement is effortless project continuity—not another system the
user must spend time maintaining.** Brain should eventually import existing
workspaces, capture new work from explicitly permitted sources as it happens,
distinguish ideas from actual implementation, and offer concise, evidence-backed
"where did I leave off?" briefings whenever a project is resumed.

The [project vision and guiding product requirements](docs/vision.md) define
this priority, its design rules and a practical acceptance scenario. When choosing
features, favour reduced effort to capture, understand, retrieve and resume work
over additional organisational complexity.

The product direction is project continuity: recover objectives, decisions,
supporting evidence and unfinished work when returning to a project. See the
[vision](docs/vision.md), [development plan](docs/development-plan.md), and
[implementation evidence](docs/development-status.md). Knowledge preservation and
retirement remain part of that foundation.

Project Brain preserves useful knowledge from material you intend to discard.
Retirement readiness measures reviewed knowledge survival, with explicit gaps;
a complete source backup is an optional separate goal.
See [the ingestion and retirement standard](docs/knowledge-retirement-standard.md).

A working local CLI for read-only project ingestion, private structured knowledge,
retained evidence, explicitly approved cross-project retrieval and retirement
readiness reports. Python 3.11+; no runtime dependencies or model credentials needed.
The current extractor selects bounded source excerpts across each whole file using
explicit decision, solution, lesson, limitation and unresolved-issue language.
These remain documented excerpts, not AI-generated or independently verified insights.

## Run

For a native read-only interface, see [The Brain desktop](docs/desktop.md).
With PySide6 installed, run `./scripts/launch_desktop.sh` to browse the local store.
The optional `desktop` package extra also provides a `brain-desktop` entry point.

For development checks, disposable CLI fixtures and contribution guidance, see
[CONTRIBUTING.md](CONTRIBUTING.md).

For development on another machine or in an online terminal with Python 3.11+
(Linux/POSIX), clone the repository and run the tests:

```bash
git clone https://github.com/BigBenKenobi/The-Brain.git
cd The-Brain
python3 -m unittest discover -s tests -v
python3 -m brain --help
```

The repository includes source, tests, schemas and development documentation.
The private `Project-Brain/` knowledge store, retained source evidence and local
reviews are excluded from Git. Initialize a fresh store for development; the
historical project IDs and local paths below describe the original installation
and are not available in a fresh clone. Fedora collection scripts such as
`scripts/ingest_fedora.py` target that local installation; they are not development
prerequisites. Other helpers are portable: the tests exercise
`scripts/run_verification.py` against synthetic processes.

From this directory, use `python3 -m brain`. An optional installed `brain` entry point
is declared in `pyproject.toml`; no installation is necessary for the commands below.
The Brain must be outside any project being ingested.

```bash
python3 -m brain --brain /tmp/my-brain init
python3 -m brain --brain /tmp/my-brain ingest /path/to/project
python3 -m brain --brain /tmp/my-brain list
python3 -m brain --brain /tmp/my-brain status PROJECT_ID
python3 -m brain --brain /tmp/my-brain context PROJECT_ID 'SQLite database locking'
python3 -m brain --brain /tmp/my-brain summary PROJECT_ID
python3 -m brain --brain /tmp/my-brain briefing PROJECT_ID
python3 -m brain --brain /tmp/my-brain briefing PROJECT_ID --json --limit 3
python3 -m brain --brain /tmp/my-brain evidence PROJECT_ID README.md --start-line 1 --end-line 20
python3 -m brain --brain /tmp/my-brain validate PROJECT_ID
python3 -m brain --brain /tmp/my-brain retire-check PROJECT_ID
```

Set `PROJECT_BRAIN_HOME` to avoid repeating `--brain`. Default is `./Project-Brain`.
Re-ingest the same path or use `refresh SOURCE_ID` to reuse saved settings and
unchanged extraction results. Ingestion returns both the project and source IDs.
For a project with one configured source, `ingest NEW_PATH --project-id PROJECT_ID`
remains an explicit relocation shortcut. With multiple sources, use
`relocate-source SOURCE_ID NEW_PATH` to select the source unambiguously.

Briefings show bounded, cited excerpts from the last published capture. They
compare recorded predecessor snapshots, report omissions, and label suggestions
separately from commitments. Missing evidence does not establish deletion or
resolved work. Explicit correction relationships suppress obsolete excerpts;
legacy snapshots without a predecessor retain an unknown baseline. Source health
reports the latest capture attempt separately from the last complete observation.
An observation confirms bytes were read, not that a claim was reviewed or verified.
Briefings prefer substantive explicit headings and varied sources, distinguish code
strings from proposals, and label recorded next steps as currency-unreviewed. Missing
context from the immediate predecessor is cited as unavailable, not resolved. This
is still deterministic excerpt selection, not maintained semantic project state.
See the [measured continuity pilot](evaluations/README.md) for results and remaining
misses; human resumption-time acceptance is pending.

## Configure and refresh sources

```bash
python3 -m brain --brain /tmp/my-brain ingest /path/to/project --exclude-path generated --max-files 1000
python3 -m brain --brain /tmp/my-brain sources
python3 -m brain --brain /tmp/my-brain refresh SOURCE_ID
python3 -m brain --brain /tmp/my-brain configure-source SOURCE_ID --clear-exclusions --no-historical --reset-budgets
python3 -m brain --brain /tmp/my-brain relocate-source SOURCE_ID /new/path/to/project
python3 -m brain --brain /tmp/my-brain ingest /path/to/notes --project-id PROJECT_ID --new-source --historical
```

Omitted options reuse each source's exclusions, historical designation and budgets.
Explicit ingestion overrides are saved only when the capture publishes successfully.
`configure-source` changes future settings without rewriting prior observations;
the briefing distinguishes configured and captured revisions. Use
`--clear-exclusions`, `--no-historical`, or `--reset-budgets` for explicit resets.
Sources start with automatic capture disabled. Enable a source with
`configure-source SOURCE_ID --enabled` and resume the worker with
`refresh-policy --no-paused`. Use `refresh-once` to run one pass over due sources.

The first source retains ordinary evidence paths. Additional sources use
`sources/SOURCE_ID/` prefixes; refreshing one preserves the others. Pinned
supplements retain their original observation dates. Same-project context no longer
expires solely because extraction is old; `context ... --max-age-days DAYS` applies
an explicit successful-observation filter, excluding unknown legacy dates. Sharing
still requires separate, unexpired approval and matching evidence identity.

Existing schema-1, schema-2 and schema-3 stores remain readable, but require an explicit upgrade before
writes. Stop any older Brain writers, then run:

```bash
python3 -m brain --brain /path/to/store upgrade-store --backup /separate/new/backup-folder
```

The upgrade verifies a coherent code/store backup, validates retained snapshots,
and publishes configuration version 4 to reject older writers. Historical snapshots
stay at version 1 and are not rewritten. Rollback requires stopping writers and
restoring the backed-up store with compatible code; the upgrade tool saves its
current code, which reads older stores but requires re-upgrade for writes. Keep the
pre-upgrade application version if rollback must restore the older writer. Rollback loses post-backup
captures, so preserve those before any rollback. Single-location legacy settings
are adopted on explicit ingestion. Ambiguous location histories require
`--adopt-legacy` together with explicit exclusions, historical designation and all
four budgets. Historical locations never automatically become capture targets.

Inspect the project snapshot or `context` output to obtain a candidate record ID.
Sharing requires deliberate approval and compatible technology labels:

```bash
python3 -m brain --brain /tmp/my-brain promote SOURCE_PROJECT RECORD_ID \
  --approve-sharing --technology sqlite --rationale 'Reviewed for transient contention only'
python3 -m brain --brain /tmp/my-brain search 'SQLite database locking' --technology sqlite
python3 -m brain --brain /tmp/my-brain context TARGET_PROJECT 'SQLite database locking' --technology sqlite
```

Use exact version labels such as `python:3.14` when version matters; labels must be
supplied on both approval and retrieval. `--exclude` applies term-based constraints;
`--limit` and `--max-chars` bound output. Search does not expose private records.
Approval never upgrades a proposal or documented claim into a verified solution.

`archive-evidence PROJECT_ID` creates and verifies a portable knowledge snapshot;
`verify-archive PATH` rechecks its hashes and records. **This is not a recoverable
source archive.** `retire-check` never deletes anything and always reports
knowledge-only preservation in this version.

## Validation and demonstration

```bash
python3 -m unittest discover -s tests -v
python3 tests/demo.py
```

The demo invokes real CLI commands against disposable projects, approves one
sharing candidate, retrieves it from another project, removes only the disposable
source, and retrieves retained evidence again. Results and timings are written to
`docs/demo-results.json`. See [architecture](docs/architecture.md),
[security and formats](docs/security-and-formats.md), and [progress](docs/progress.md).
Canonical schemas are in `schemas/`. The generated `Project-Brain/` workspace holds
the demo's persistent knowledge and can be inspected after the demo completes.

## First real collection ingestion

The Fedora ingestion review is private at
`Project-Brain/reviews/fedora-first-ingestion/review.md`. Its preflight, run manifest,
repeat verification and query examples are stored beside it. No source files were
executed. The source folder is `/home/KenobiBigBen/Setup Fedora`.

`ingest` accepts per-run `--max-files`, `--max-file-bytes`, `--max-total-bytes`,
`--max-seconds`, repeatable relative `--exclude-path`, and `--historical`.
Budgets and scope are recorded in each new snapshot. Later ingestions reuse the
source's saved exclusions and budgets when those options are omitted; use
`configure-source` to change the saved settings. The collection runner also
preserves its explicit partition.
`python3 scripts/ingest_fedora.py verify` repeats the current collection ingestion
with those scopes, checks extraction reuse and validates retained evidence.
`evidence` reads only stored text, bounded to 200 lines per call. Historical
snapshots remain on disk; `history PROJECT_ID` lists them and
`evidence PROJECT_ID PATH --snapshot SNAPSHOT_UUID` reads their retained text.
Normal context queries search active snapshots only.

The final Fedora pass and current decision are recorded privately in
`Project-Brain/reviews/fedora-first-ingestion/final-review.md`; the first-ingestion
review is historical. Run `python3 scripts/fedora_final_pass.py` for the full scoped
refresh, unchanged-repeat/evidence verification and new snapshot-bound assessments.
A plain ingestion creates a new snapshot requiring a fresh retirement review.
`review-retirement PROJECT_ID --summary TEXT --known-gap TEXT --record-id ID`
records that assessment, checking nominated retained evidence. Repeat gap and record
flags as needed. This is an assessment, not a deletion command or sharing approval.

## Consolidated project knowledge

Setup Fedora's main identity `bfab8d3f-aaff-48a7-b24e-7895473640b2` now includes the
three handoff/knowledge-base/task documents previously held in a separate intake.
Use the main ID for both original and supplemental knowledge:

```bash
python3 -m brain context bfab8d3f-aaff-48a7-b24e-7895473640b2 'N02 IndexError'
python3 -m brain context bfab8d3f-aaff-48a7-b24e-7895473640b2 'Firefox Codex VPN'
```

`consolidate MAIN_ID SUPPLEMENT_ID` imports a pinned retained snapshot into a new
main snapshot. It reads no original folders. Imported evidence has a namespaced
path and retains original project/snapshot/record/path provenance. Prior snapshots
and the intake remain available. Re-ingesting the main source carries the pinned
supplement forward. Re-run consolidation explicitly to adopt a newer supplement
snapshot; repeating an unchanged consolidation is a no-op. New merged snapshots
require a fresh retirement review. Consolidation leaves information private and
preserves documented/proposal/implementation status without elevating outcomes.

## Reviewed corrections and current context

`relate PROJECT_ID OLDER_RECORD_ID REPLACEMENT_RECORD_ID --kind corrects --rationale 'Evidence and scope of correction'`
creates a new immutable snapshot with an explicit reviewed precedence link. `supersedes`
(new decision) and `duplicates` (canonical equivalent) use the same direction. Both endpoints
must belong to the project. Cycles and competing replacements are rejected; extend the
existing chain for a later correction. Source evidence and old snapshots remain intact.
Relations survive re-ingestion and are remapped with pinned consolidated supplements.
Missing endpoints appear in validation warnings; they never restore an obsolete match.

`context PROJECT_ID QUERY --explain` resolves historical matches to their final replacement
before limits. Missing, expired, excluded or unapproved replacements suppress the old match.
Cross-project retrieval still requires explicit approval of the replacement itself.
`--include-history` exposes original matches marked historical. New timestamps alone do not
establish precedence, and unlinked contradictions still require review.

Substantive text outranks headings/tables; exact repeated statements are collapsed. This
is not semantic deduplication. `--max-chars` now budgets statement text, with provenance
metadata additional; `--limit` bounds returned records. `--explain` reports omitted matches
and budget reasons. Validation proves retained evidence integrity, not truth or complete
chat discovery. When a record mixes corrected and still-valid claims, write a replacement
that preserves the valid limitations before linking it.


## Bounded automatic refresh

An opt-in worker and Fedora user timer are available; see
[activation and controls](systemd/README.md). The policy starts paused and every
source starts disabled. `refresh-status` shows actual worker-lock status, last
successful capture, retry state and capacity. The worker coalesces changes,
serialises writers, applies per-run limits, and preserves the published evidence
when sources are unavailable or capacity is reached.

Unchanged refreshes retain separate observation history but reference existing
canonical content instead of copying it again. On the continuity pilot this reduced
one refresh from 359,548 to 5,141 bytes (98.6%). No evidence is deleted. Full snapshots
referenced by observations must remain available; archives materialise their content.
[Refresh validation results](evaluations/refresh-results.json) distinguish fixture
checks and a successful transient timer run from real-source activation.

Long prose under explicit section headings can supply paragraph previews instead of
only the record prefix. Each preview remains an exact substring of retained evidence
with its original record identity and source range; JSON includes character offsets
within that record. The 400-character per-preview bound and section limits still
apply. Ellipses/partial-record labels indicate omitted surrounding context; open the
evidence before relying on qualifications. Omitted counts refer to preview candidates.

Explicit limits such as “not independently verified” are shown as qualification
caveats. These are cited source statements, not inferred failed gates or acceptance.
A caveat paragraph may be selected directly when its own wording supplies that context.

## Further documentation

Saved source configuration, observation freshness and the explicit version-1 to
version-2 store upgrade are documented in [source settings](docs/source-settings.md).

Opt-in scheduling, pause/retry, bounded storage and writer-3 observations are
documented in [automatic local refresh](docs/automatic-refresh.md).

[Maintained project state](docs/maintained-state.md) describes private decisions,
ideas, attempts and blockers with evidence-backed correction, relationships and undo.

[Evidence storage and compaction](docs/storage-compaction.md) covers writer4,
copy-only migration, derived-state integrity checks and rollback. Explicit support
consolidation and its undo are described in [maintained state](docs/maintained-state.md).

The [offline model boundary](docs/local-model-evaluation.md) exports bounded
project evidence and validates externally supplied proposals. It does not invoke a
model, establish runtime identity, or promote suggestions into reviewed state.
