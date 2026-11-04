# Implementation progress — 2026-11-01

## Delivered and exercised

- Python standard-library CLI and callable `Brain` interface.
- Independent initialized `Project-Brain/` workspace, UUID project registry and
  explicit identity reuse after source relocation.
- Read-only inventory, exclusions, secret heuristics, byte/file/time budgets,
  SHA-256 evidence, deduplication, common root manifest identification.
- Structured private records with source spans, retained evidence, uncertainty,
  reuse candidates and canonical JSON schemas.
- Explicit, audited sharing approvals with technology constraints and expiry.
- Token index and relevance/compatibility/freshness/context-cost filtered retrieval.
- Markdown summaries, validation, coverage and knowledge-only retirement reports.
- Unchanged extraction caching, historical snapshots and atomic publication.
- Verified evidence ZIP exports, explicitly not recoverable source archives.
- AI adapter protocol and explicit unavailable status; no network transmission.

## Validation evidence

`python3 -m unittest discover -s tests -v`: **14 tests passed**, final run 0.027 s.
Tests cover provenance, source content immutability, secrets, duplicates, omissions,
symlinks, budgets, incremental extraction, relocation, private isolation, compatible
cross-project retrieval, source-independent preservation, proposal labels, expiry,
output budgets, tampered archives/evidence and failed publication recovery.
Inaccessibility and publication failures are injected deterministically with mocks;
these are not claims of physical disk-failure or every filesystem's permissions behavior.

`python3 tests/demo.py`: successful subprocess-based end-to-end demonstration.
All supported commands were exercised: init, doctor, ingest, context, promote,
search, status, validate, summary, retire-check, archive-evidence, verify-archive,
and list. Only disposable fixture source folders were removed.
`docs/demo-results.json` contains exact executed CLI commands and results.

Demo: five files inventoried, three extracted, 308 bytes read. First extraction
phase took 0.000524 s; unchanged phase took 0.000325 s with zero extractions and
three cache hits. Both read and hash accepted source bytes; this demonstrates less
extraction work, not a reliable general performance speedup. Timings exclude CLI
startup and publication; fixtures are deliberately tiny. Model calls: zero.

The persisted demonstration Brain contains source project
`6f15f6e6-f5b0-402f-9a69-49a225f04cbf` and target
`15e021e2-8c29-4b9e-bf2f-70c4d21af1ae`. The original disposable folders no longer
exist. A subsequent direct CLI validation and cross-project retrieval still pass.

## Most valuable unfinished work

1. Add an opt-in AI provider with live model availability checks, bounded semantic
   extraction, strict evidence validation and measurable usage. Configuring a model
   alone currently does nothing; enabling AI explicitly fails with an explanation.
2. Evaluate retrieval with realistic positive/negative corpora, version conflicts,
   superficial overlap and privacy cases. Current lexical matching is deliberately
   simple and cannot reason about arbitrary target requirements.
3. Optional separate source-recovery work: complete archival with a sensitive-material
   policy and tested restoration. This is not a prerequisite for knowledge retirement.
4. Expand schema/type validation to all nested structures and add migration tools.
   Published JSON schemas document contracts; the built-in validator checks crucial
   integrity invariants but is not a complete JSON Schema interpreter.
5. Improve extraction selection, language-aware evidence, actual test-result
   verification, dependency-aware invalidation, supersession and approval revocation UI.
6. Add interrupted-run checkpoints, disk budgets/retention policy and adversarial
   filesystem hardening. Current recovery is safe repeat ingestion, not partial resume.

No web app, services, agents, vector database or external dependencies were added.

## First real ingestion — 1 November 2026

Inspected the existing system and reran its original 14 tests before editing.
Implemented deterministic-2 selection across whole documents with explicit knowledge
kinds; retained-evidence CLI including historical snapshot access; broader Fedora text
formats and shebang-script support; quoted-JSON credential screening; explicit scoped
exclusions, historical roles and per-run budget flags. JSON/configuration records no
longer imply observed execution. Empty-file extraction reuse is fixed. Schemas document
the additional fields while remaining compatible with original demo snapshots.

Final fixture suite: **18 tests pass**. Existing demo snapshots still validate.
The real source `/home/KenobiBigBen/Setup Fedora` was partitioned into 14 private
identities: Fedora setup, NetworkSurvey, and 12 historical application reference groups.
Initial runs covered all 2,985 inventoried files across 36 historical/active snapshots;
10 dependency/cache subtrees were not individually inventoried. See the actual run
manifest for exact scopes and counts. Nothing was promoted or shared.

Coverage across original source files: 822 retained, 452 duplicate, 1,650 unsupported,
26 sensitivity omissions, 33 excluded special/symlink files, two oversized plans
unprocessed. No inaccessible files or inventory-budget truncation occurred. The 14
active snapshots contain 5,175 records and 6,371,350 bytes of retained evidence.
All initial snapshots and all repeated active snapshots validate. Unchanged repeat:
zero extractions and 766 cache hits. Source-open guards proved stored-evidence access,
retrieval and retirement reports work without original-folder reads. Source metadata
inventory was unchanged; retained text hashes matched. No full binary recovery audit
or source execution occurred. Model calls and provider submissions were zero.

Private results: `Project-Brain/reviews/fedora-first-ingestion/review.md`, with
preflight, first-run manifest, verification, query outputs and file-level coverage.
The review includes exact commands, authority caveats, reusable candidates awaiting
approval, lexical misses, omissions and a knowledge-only retirement assessment.
`python3 scripts/fedora_review.py` regenerates the review from stored evidence only.
No complete recoverable source archive exists; source reconstruction would require separately retained source material.

## Knowledge-retirement standard and final Fedora pass — 1 November 2026

The owner clarified that Brain preserves useful information from material they would
otherwise discard. Source reconstruction is optional and is no longer a readiness
prerequisite. `retire-check` now validates knowledge and reports snapshot-bound review
status, known gaps and evidence checks independently of recoverable archival status.
`review-retirement` records the assessment. New snapshots require new reviews; these
commands neither delete sources nor grant deletion/sharing permission.

Deterministic-3 indexes up to 128 documentation windows (32 for other text). The
final Fedora pass raised the per-file budget to 8 MiB after reviewing the two large
JSON historical inventories; both are now screened and retained. All 2,985 source
entries have explicit dispositions: 824 retained, 452 duplicates, 1,650 unsupported,
26 sensitivity omissions and 33 special/symlink exclusions. No unprocessed files
remain; excluded subtree contents are still not individually inventoried.

The 14 active private scopes hold 5,396 records, 221 more than the first ingestion.
All pass validation, unchanged reuse and retained-evidence checks with source reads
blocked. Each has a knowledge-retirement assessment with known gaps. Source metadata
was unchanged during this pass. Important surfaced knowledge includes DKMS masked
signing/depmod failures, rollback residue, srcversion validation, updater umask and
prompt handling, and the boundary between guest recovery tests and physical results.
No source-described experiment was executed. Model calls/submissions/sharing: zero.

19 fixture tests pass, including readiness requiring review, stale-snapshot reviews,
inventory-truncation blocking, invalid evidence and late unflagged documentation.
The governing standard is `docs/knowledge-retirement-standard.md`; the private final
report is `Project-Brain/reviews/fedora-first-ingestion/final-review.md`, with exact
highlights and verification JSON beside it. Earlier review metrics and conclusions
are historical and superseded where the goal or coverage changed.

## Consolidated Fedora documents cross-check — 1 November 2026

Reviewed the three user-selected documents in `/home/KenobiBigBen/New` against
retained Fedora knowledge. Preserved all three privately under supplement identity
`5f25c9ba-2279-4336-b6d1-5b126505ccfd`: 120,830 bytes, 115 excerpt records. Primary
Fedora snapshots remain unchanged; its assessment links the supplement. Exact
hashes, validation, six useful queries and evidence access passed with source reads
blocked; unchanged repeat had zero extractions/three cache hits. No source bytes or
metadata changed. No embedded operational instructions executed, no external model
submission or sharing. The primary lexical query had missed a survey status crash
already retained in raw evidence; the supplement makes it and the consolidated
chronology/task dependencies accessible. Outcomes in those documents remain their
authors' dated reported observations, not newly verified host results by Brain.
Private comparison: `Project-Brain/reviews/fedora-document-crosscheck/review.md`.

## Unified Setup Fedora queries — 1 November 2026

Added explicit retained-snapshot consolidation and consolidated the three New intake
documents into the main Fedora identity. Main context/evidence/summary/archive and
retirement operations now include those documents. Provenance, original evidence
statuses and history remain; canonical records remain private. Pinned supplements
survive main re-ingestion, while unchanged consolidation is idempotent. Newer intake
snapshots require explicit reconsolidation. Atomic-publication recovery, isolation,
retained evidence, historical snapshots and continued inclusion after ingestion
are covered by fixtures; **21 tests pass**. The main retirement review is refreshed.
Verification: `Project-Brain/reviews/fedora-document-crosscheck/consolidation-verification.json`.
Earlier separate-ID guidance is superseded for everyday Fedora queries.
