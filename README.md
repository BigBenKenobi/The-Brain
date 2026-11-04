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

**Current implementation:** a working local Python 3.11+ CLI for read-only
project ingestion, private structured knowledge, retained source evidence,
incremental snapshots, explicitly approved cross-project retrieval, and
knowledge-retirement readiness reports. It uses no runtime dependencies or
model credentials. The current extractor selects bounded source excerpts
across whole files using explicit decision, solution, lesson, limitation and
unresolved-issue language. These are documented excerpts, not AI-generated
or independently verified insights. Automatic ongoing capture and one-step
project-resumption briefings remain future work.

Preserving useful knowledge from material you intend to discard remains an
important use case, not the limit of Brain's purpose. Retirement readiness
measures reviewed knowledge survival with explicit gaps; complete source backup
is an optional separate goal. See the
[ingestion and retirement standard](docs/knowledge-retirement-standard.md).

## Run

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
and are not available in a fresh clone. The scripts in `scripts/` are specific to
that local Fedora collection and are not required for development or tests.

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
python3 -m brain --brain /tmp/my-brain evidence PROJECT_ID README.md --start-line 1 --end-line 20
python3 -m brain --brain /tmp/my-brain validate PROJECT_ID
python3 -m brain --brain /tmp/my-brain retire-check PROJECT_ID
```

Set `PROJECT_BRAIN_HOME` to avoid repeating `--brain`. Default is `./Project-Brain`.
Re-ingest the same path to reuse unchanged extraction results. Supply
`ingest NEW_PATH --project-id PROJECT_ID` when relocating a known project.

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
Budgets and scope are recorded in each new snapshot. Exclusions must be supplied
again on later CLI ingestions; the collection runner preserves its explicit partition.
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
