# Project Brain architecture — decision 001

Status: implemented deterministic MVP, 2026-11-01.

## Continuity direction and first briefing milestone — 4 November 2026

The snapshot lifecycle below describes the existing implementation. The governing
product direction is now workstation-integrated development understanding and
purposeful memory, as specified in [vision](vision.md) and the
[delivery plan](development-state-plan.md). Retirement is one consumer of evidence.

`briefing PROJECT_ID` adds a read-only presentation layer in `brain/briefing.py`.
It validates a pinned active snapshot, selects bounded excerpts with explicit
selection reasons, exposes unknowns and omissions, and compares retained paths
against the recorded predecessor. It does not infer a feature lifecycle, reconcile
contradictions, query other projects or contact a model. Historical sources and
pinned supplements retain their provenance and status. Each section uses source
path/line order, not an inferred importance or activity ranking.

New ingestion and consolidation snapshots carry optional `parent_snapshot`, pointing
to the previously published snapshot, or null for a first ingestion. Schema version
1 remains compatible with existing stores: a legacy snapshot with no parent has
no automatic comparison baseline. We do not guess from timestamps or directory
contents, which may include abandoned snapshots from failed publications. The
briefing fails on invalid evidence or an unreadable recorded parent instead of
silently presenting an unverified comparison. Retained-path absence is not proof
of deletion, and publication time is not proof that source content is fresh.

The briefing's selection reasons are presentation metadata. They do not implement
memory admission, compaction or forgetting. Existing full accepted text and history
remain intact pending a separate, tested retention design.

## Existing-project assessment

The provided `/home/KenobiBigBen/The Brain` workspace contained no project files,
code, tests, documentation or usable Git repository. Only reserved environment
mount directories were present. No previous implementation could be verified or
reused. The previous design is known only from the user's redirection brief;
this is not an assessment of an unseen prior repository.

## Redirection and rationale

The primary unit of work is a read-only ingestion snapshot, replacing continuous
project auditing. The lifecycle is inventory → screened evidence → private records
→ explicit sharing approval → task-specific retrieval → retirement assessment.
Evidence provenance, project isolation, stable identities, incremental extraction,
explicit uncertainty and safe publication remain core requirements.

Use Python's standard library, canonical JSON and generated Markdown. This avoids
services, infrastructure dependencies and model credentials for the useful baseline.
SHA-256 identifies exact content; UUIDs identify projects independent of folder
names. A relocated project must supply `--project-id`; guessing identity from
similar content could merge unrelated private projects.

## Storage and transactions

`config.json` holds budgets and reserved optional AI settings. `registry.json`
holds stable project IDs, historical locations and the active snapshot pointer.
`projects/<id>/snapshots/<uuid>.json` contains inventory, structured records,
retained text evidence, coverage warnings, metrics and a deterministic token index.
`shared/<record-id>.json` holds explicit sharing approval, technology constraints,
rationale and expiry. `archives/` contains optional evidence-only ZIP exports.

A Linux/POSIX advisory lock serializes ingestion and promotion. Snapshots are
written and fsynced before an atomic registry replacement publishes them. Readers
see a complete old or new snapshot. A failure before publication leaves the old
snapshot active; abandoned snapshots are harmless. Rerunning ingestion is supported;
resuming a partially processed individual snapshot is not. Directory fsync and
power-loss guarantees across all filesystem implementations remain future work.

Each accepted file is hashed and screened on every ingestion. Unchanged extracts
are reused by path, hash and extractor version. Identical files share evidence and
only the first gets extracted. A changed source produces new record identities;
old approvals cannot authorize new records. Removed material disappears from
current retrieval but remains in historical snapshots. Snapshots currently embed
whole accepted text, so history can consume substantial disk space.

## Extraction and retrieval

The deterministic-3 extractor scans every section and 24-line/1800-character
window, reserves representation for explicit decision, solution, lesson, limitation
and unresolved language, and selects at most 128 windows for documentation (.md/.txt/.rst), 32 for other text, per accepted file;
full accepted UTF-8 files remain as supporting evidence. It flags potential reuse
from explicit solution/decision/lesson language. It never establishes that a
solution works, that a decision was approved, or that a claim is true. Proposals,
historical source records and observed implementation are separate statuses.
Only recognized source code or shebang scripts receive observed-implementation
status; this means source text was observed, not executed or tested. JSON reports
and configuration remain documented claims. Historical roots and archive/backup
paths carry a historical-copy role, including source code. No extracted record
is labeled independently verified.
Common root manifest filenames identify project types; deeper language-aware
analysis is not implemented. README/architecture/decision files have priority
within each directory, not a global semantic importance ranking.

Private records are only searchable with their owning project's `context` command.
Global `search` only returns explicitly approved shared records. Cross-project
retrieval requires exact declared technology/version labels, non-expired approval,
current evidence identity, freshness and at least half the non-stop query terms
(with at least two matches for multi-term queries). A character budget limits
context cost. Explicit `--exclude` constraints reject matching records. Each result
explains term matches and eligibility and retains evidence references and status.

This is a conservative lexical gate, not semantic understanding: ambiguous terms,
negation, incompatible undocumented assumptions and superficial multiword overlap
can still fool it. Human sharing review is essential. Current target requirements
always override history; arbitrary natural-language conflicts are not automatically
resolved. Fail-closed compatibility means omitted technology labels exclude shared
results. Shared approval does not mean independent verification.

## AI boundary

No model credential variable was found in the execution environment and no suitable
text-model execution tool was exposed. No provider was contacted and no model
availability is claimed. `doctor` reports this explicitly. The extraction protocol
in `brain/extraction.py` defines a future adapter boundary; it is not an installed
AI implementation. Configurable provider/model fields are reserved and do not enable
network submissions. Add explicit opt-in provider execution, model discovery,
bounded evidence prompts, response validation, usage accounting and privacy review
before using those fields. Do not treat the requested model names as verified runtime
identifiers.

## Retirement

The goal is to preserve useful decisions, fixes, lessons, limitations and unfinished
work from sources the owner would otherwise discard. Readiness is a knowledge
assessment with disclosed omissions; complete source recovery is optional.

`retire-check` validates the active snapshot. It requires nonempty knowledge, no
inventory truncation warnings, and a substantive review bound to that snapshot's
UUID, including explicit known gaps and checks against retained record evidence.
`review-retirement` writes this assessment under the project's retirement-reviews.
A new snapshot requires a new review, even when extraction was reused. Missing
binary assets or a full source archive do not alone prevent knowledge retirement.
A readiness result never grants deletion permission, shares records or deletes files.
Evidence export remains knowledge-only and must never be called a recoverable archive.

## Real collection scope

Per-run relative path exclusions separate nested projects without copying or moving
sources. Historical reference copies of the same named application are ingested
chronologically under an explicitly reused UUID; the latest reference is active,
and earlier snapshots remain accessible as stored JSON. They are not merged with
unseen live application repositories. NetworkSurvey and Fedora setup are separate.
The collection runner records all runs and scopes in the independent private Brain.
Historical copies may be incomplete subsets; active retrieval does not union all
historical snapshots. Retrieval is lexical and does not resolve conflicting dates.

## Retained supplement consolidation

An explicitly requested same-project supplement can be consolidated with
`consolidate MAIN_ID SUPPLEMENT_ID`. The main registry entry pins supplement UUIDs
and their snapshot UUIDs. A new validated main snapshot imports retained inventory,
evidence and records under `supplements/<origin-id>/`, retaining original
project/snapshot/path/record provenance in `consolidated_from`. Imported records
receive main-project IDs; evidence status and source dates remain unchanged. No
sharing approvals transfer. The original intake and all old main snapshots remain.

Snapshot write precedes atomic registry publication. Failed publication keeps the
old main and its supplement pins active. Self-imports, nested consolidation and
namespace collisions are rejected. Source coverage warnings propagate. Imports
use retained snapshots, never original folders, and survive main-source ingestion.
Newer supplement snapshots are adopted only by explicit reconsolidation. Validation,
retained evidence, summaries, exports, context and retirement checks therefore all
operate on the consolidated main snapshot. Consolidation does not semantically
resolve historical contradictions; source dates/status still matter.

