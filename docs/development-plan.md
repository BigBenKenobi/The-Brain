# Brain Development Plan

Draft plan dated 10 November 2026.

Brain should let you leave a project, work on something else, and return with the important context intact: what you were trying to achieve, what changed, why decisions were made, what is actually supported by evidence, and what needs attention next. Routine capture and organisation should require little maintenance after sources are configured.

The proposed delivery order is dependable capture, useful briefings, automatic local refresh, maintained project understanding, and sustainable daily use. Automatic refresh and richer understanding can progress in parallel once capture boundaries and freshness are reliable. Keep the current evidence foundation and improve it through small, testable changes.

# First usable release

The first release worth using regularly should support one complete workflow:

1. Register a project and its permitted sources once.
2. Refresh without repeating exclusions, historical settings or processing budgets.
3. Preserve useful searchable knowledge through ordinary edits, duplicate cleanup and source relocation.
4. Produce a concise briefing with supporting evidence, capture health and explicit unknowns.
5. Let the user correct a misleading interpretation without rewriting project notes.
6. Preserve the previous valid state if a capture or publication fails.

The first release can use explicit refresh. Background capture follows as soon as its reliability requirements are met. Success is measured by the effort saved when returning to work, alongside factual accuracy and low maintenance.

# Verified starting point

| Area | Current position |
| --- | --- |
| Main branch | Commit 773a803a0a9939cc4fd33a7ae5c937d57a781d34. The preceding repository review ran all 21 tests successfully under Python 3.12.14. |
| Existing briefing work | Draft PR 1, head dba69ef01233278fe847541966a65419fd18807f, remains open and unmerged. Its 30 tests passed in the same review environment. |
| Implemented foundation | Local Python CLI, read-only ingestion, retained text evidence, hashes and spans, private records, historical snapshots, extraction caching, explicit cross-project sharing and retained-snapshot consolidation. |
| Understanding | Deterministic excerpt extraction and lexical retrieval. The draft briefing groups selected excerpts but does not reconcile project state semantically. |
| Known correctness defect | Removing or excluding the initially extracted member of identical files can leave the surviving duplicate retained but absent from current searchable records. |
| Source configuration | Ordinary ingestion does not persistently reuse all source-specific exclusions, historical settings and budget overrides. |
| Freshness | Cached records keep their original extraction timestamp; the default 365-day retrieval filter can hide unchanged evidence even after it is freshly captured. |
| Runtime target | The user's Fedora 44 workstation. Confirm its actual checkout, Python interpreter, installed services and knowledge-store location before deployment. |
| Model requirement | Local inference only. Choose a model by measured usefulness and resource use on the workstation; model selection is not a prerequisite for the first reliability fixes. |

The main and PR heads were rechecked while preparing this plan and match the tested revisions. The tests used disposable fixtures; the private workstation knowledge store was outside that review.

Sources: [main README](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/README.md), [PR 1](https://github.com/BigBenKenobi/The-Brain/pull/1), [cache handling](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/brain/core.py#L251-L264), [retrieval age filter](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/brain/core.py#L376-L396), [existing implementation audit](https://github.com/BigBenKenobi/The-Brain/blob/dba69ef01233278fe847541966a65419fd18807f/docs/development-state-plan.md).

# Development milestones

| Milestone | User outcome | Main deliverables | Exit condition |
| --- | --- | --- | --- |
| M1 Dependable capture | Refresh a configured project without losing searchable knowledge or reconstructing flags. | Duplicate-cache repair, persistent source settings, observation freshness, focused regression tests and CI. | Cleanup, unchanged refresh, relocation, partial failure and legacy data behave predictably. |
| M2 Useful project briefings | Understand where a project was left and inspect the evidence. | Complete PR 1, add capture-health information, evaluate a real project history and improve selection from measured misses. | The pilot meets the traceability and status rules and reduces resumption effort. |
| M3 Automatic local refresh | Routine work is captured from chosen sources with little intervention. | Opt-in local scheduling, bounded processing and storage, pause, retry, health reporting and recovery. | Repeated normal work needs no capture intervention; failures preserve the last good state and remain visible. |
| M4 Maintained project understanding | Decisions, ideas, attempts and blockers stay connected across changes. | Stable state items, evidence-backed relationships, correction and undo, followed by evaluated local semantic extraction. | Supersession and contradictions are handled honestly; unsupported completion claims cannot become verified facts. |
| M5 Sustainable daily use | Useful memory stays manageable and can serve another application. | Measured evidence deduplication and reversible compaction, purpose-based memory, one consuming integration and an additional project pilot. | Growth is bounded, references survive migration and the second project confirms the workflow generalises. |

M1 enables M2. M3 requires M1, basic operational health and the M2 baseline experience. M4 starts from the M2 evaluation and can proceed alongside M3. M5 is driven by observed storage and integration needs rather than an arbitrary feature count.

CI, documentation and compatibility checks accompany the relevant change. A calendar estimate should follow the first implementation cycle and workstation inventory; the current plan commits to ordering and acceptance criteria.

# First development cycle

The identifiers below are planning labels, not GitHub issue or pull-request numbers.

| Work item | Scope | Dependency |
| --- | --- | --- |
| B01 Repair duplicate caching | Small, focused correctness patch with regression coverage. | Ready to implement. |
| B02 Establish automatic checks | Existing unittest suite, regression tests and a supported-Python CI matrix. | Can run alongside B01. |
| B03 Persist source settings | Source identity, effective configuration, predictable refresh and relocation. | Builds on the existing registry; precedes automatic capture. |
| B04 Separate observation freshness | Per-source and per-file observation metadata, retrieval policy and legacy handling. | Coordinate schema decisions with B03. |
| B05 Complete the briefing | Review existing PR 1; incorporate reliable source and freshness reporting. | Basic briefing can land after B01 and review; milestone acceptance also needs B03 and B04. |
| B06 Run the first pilot | A small project history, reference answers and resumption measurements. | Requires the briefing baseline; feeds M4 priorities. |

## B01 Repair duplicate caching

The current cache checks path and content hash, but a previously duplicate file may never have had extracted records. If it becomes the surviving copy, reusing an empty record list is incorrect.

Distinguish a completed extraction from a duplicate-only inventory entry, using the previous file disposition or an explicit completion marker. A completed extraction may legitimately contain no records, so checking only for a nonempty list would create a new empty-file caching problem.

Acceptance checks:

- Removing the first of two identical files leaves the surviving file searchable.
- Excluding the first copy produces the same correct outcome.
- Introducing a differently ordered duplicate does not discard current knowledge.
- An unchanged empty file still benefits from caching.
- Retained evidence references resolve to the surviving path and correct hash.
- Source files and historical snapshots remain unchanged.
- A newly created record does not silently inherit another record's sharing approval.
- The existing suite and focused regression tests pass at the exact proposed revision.

The full retained text is already preserved in the reproduced failure. This patch repairs current extraction and retrieval; it is not a recovery of lost source bytes.

Source: [duplicate and cache handling](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/brain/core.py#L251-L264).

## B02 Establish automatic checks

Add a small CI workflow that runs the existing unittest suite and the new regressions. Include the declared minimum Python version, currently 3.11, and the workstation interpreter version once inspected and available in CI. Keep local Fedora validation as a separate result when the environments differ.

Retain the tested commit, interpreter version, command and result in each implementation handoff. If CI cannot run, report the local result and the specific CI gap; a missing run is not a successful check.

Tests should exercise externally meaningful behavior and failure paths. Avoid tests that merely restate the implementation or make cosmetic changes expensive.

Sources: [package requirements](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/pyproject.toml), [current test suite](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/tests/test_brain.py).

## B03 Persist source settings

Introduce source identity separately from project identity. A project may eventually contain a repository, a selected notes export and historical reference material; each source needs its own boundaries.

The initial source configuration should include source ID, project ID, source kind, location, enabled state, exclusions, historical designation, processing budgets and configuration revision. Capture the effective configuration revision with each new observation.

Ordinary refresh reuses the stored settings. Omitted CLI options must mean “use the configured value”; clearing exclusions or changing a source's historical designation must be distinguishable from omission. An explicit configuration change controls future captures.

An explicit relocation preserves the known source's identity and settings. Similar filenames or content do not establish that a new folder is the same source.

Acceptance checks:

- Repeated ordinary refresh preserves exclusions, budgets and historical designation.
- Explicit overrides and resets have documented, testable behavior.
- Relocation preserves identity without silently adding another root.
- A scope change does not retroactively delete previously retained evidence.
- Configurations and effective capture metadata remain consistent after failed publication.
- A disabled or unconfigured source never becomes an automatic-capture target.
- Project boundaries and the rule that Brain storage stays outside ingested roots remain enforced.

Legacy migration needs special care: the registry records historical locations, but old snapshots do not reliably identify which location produced their settings. Seed an unambiguous source from attributable existing configuration; keep ambiguous legacy locations manual until the intended source is identified. Do not spread the most recent snapshot's exclusions across every historical path.

Sources: [ingestion defaults and registry behavior](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/brain/core.py#L161-L183), [CLI defaults](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/brain/__main__.py#L16-L22).

## B04 Separate observation freshness

Keep extraction time, successful source observation, source-provided dates, substantive review and sharing approval as distinct facts.

A successful stable read and hash establishes that a particular file version was observed. A refresh attempt, failed read, skipped file, snapshot publication or supplement consolidation does not establish that every source was freshly seen. A historical document can be observed today while its claims remain historical.

For same-project retrieval, the proposed default is to return relevant retained material with clear currency and observation status rather than silently remove it solely because extraction happened long ago. Stricter filters can be explicit. Cross-project approval, evidence identity and expiry remain separate eligibility requirements.

Acceptance checks:

- Unchanged evidence remains discoverable after a successful refresh beyond the configured age threshold.
- Unreadable, excluded or budget-skipped files do not receive a successful observation timestamp.
- Partial capture is distinguished from a complete successful capture.
- Consolidating a pinned supplement preserves its original observation status.
- New observations neither certify a claim nor renew sharing approval.
- Legacy observation times remain unknown unless attributable evidence establishes them.
- The briefing distinguishes a current capture attempt from the last successful observation.

Sources: [extraction reuse](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/brain/core.py#L258-L264), [retrieval filter](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/brain/core.py#L376-L396), [supplement handling](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/brain/core.py#L94-L129).

## B05 Complete the briefing

Continue the existing PR rather than create a competing briefing implementation. Reconcile its branch with any merged reliability fixes and rerun the combined suite.

The useful default view should cover the objective, meaningful changes, key decisions and rationale, unresolved work, evidence of implementation or test results, and suggested next actions. Label suggestions separately from recorded user commitments. Every factual statement must resolve to supporting evidence; missing support should remain unknown.

Keep bounded output, omitted counts, source spans, predecessor links and the distinction between missing evidence and confirmed deletion. Add source health and observation age once B03 and B04 make them reliable.

Initial selection can remain deterministic. Improve ranking against measured misses in the pilot rather than assuming alphabetical file order identifies what matters. The complete evidence remains available behind the brief view.

Acceptance includes absent sources, legacy snapshots, failed publication, incomplete inventories, pinned supplements, stale observations and corrupted evidence. The existing PR's nine added tests provide a starting point, not proof of semantic quality.

Sources: [briefing implementation](https://github.com/BigBenKenobi/The-Brain/blob/dba69ef01233278fe847541966a65419fd18807f/brain/briefing.py), [briefing tests](https://github.com/BigBenKenobi/The-Brain/blob/dba69ef01233278fe847541966a65419fd18807f/tests/test_briefing.py).

# Pilot and acceptance measurements

Use The-Brain itself as the proposed first pilot because its source and decisions are already accessible and its scope is manageable. Add only specifically selected notes or conversation exports. A later trial can use a more complex project such as Tinker.

Build a short reference history covering:

1. An objective and initial proposal.
2. An accepted decision with a reason.
3. Partial implementation and an unresolved blocker.
4. An attempted approach that failed.
5. A replacement decision and a reported test result.
6. A later revision, an unavailable source and an unfinished idea.

Include a genuinely attributable test run as a separate case. Preserve the distinction between a document reporting success and captured test evidence tied to a revision and environment. Brain ingestion must not execute discovered source scripts to obtain that evidence.

Keep evaluation answer keys outside the ingestion scope. Use a held-out checkpoint or a second project to detect rules tuned only to the first example.

| Measure | Proposed acceptance rule |
| --- | --- |
| Evidence traceability | Every substantive briefing claim resolves to retained evidence that supports the wording. |
| Status accuracy | No proposal becomes a commitment, and no observed code or reported success becomes independently verified behavior without appropriate evidence. |
| Critical context | Each reference decision, blocker and discarded approach is correctly surfaced or explicitly marked unavailable for an observed reason. |
| Change interpretation | A missing blocker document never establishes that the blocker is resolved. |
| Isolation | No unrelated private project knowledge appears in the briefing or local-model input. |
| Freshness | Newly observed unchanged material remains discoverable; failed capture is visible. |
| Effort | Measure time needed to recover the next practical step with and without Brain across comparable returns to work; set a numerical target after the baseline. |
| Maintenance | Routine refresh requires no repeated flags, tagging, daily check-ins or manual filing. |
| Resilience | Source outages and publication failures preserve the last valid state and identify its age. |

Report important misses, unsupported claims, repeated noise, capture cost and resumption time. A short owner check after a real pause is more useful than requiring new daily project notes.

# Automatic local capture

After M1 and the baseline briefing, add a small opt-in local refresh service. A Fedora user service or timer is a candidate implementation to assess against the actual workstation. Begin with the simplest scheduling mechanism that handles the selected sources predictably; a complex watcher is unnecessary unless measurements show a need.

Required behavior:

- Refresh only registered, enabled sources using their saved settings.
- Coalesce repeated changes, avoid overlapping writers and apply per-run budgets.
- Distinguish idle, running, paused, partial, stale and failed capture.
- Retry transient failures with bounded backoff and preserve the last good snapshot.
- Resume predictably after sleep, restart and a missing source.
- Offer clear pause and disable controls.
- Bound disk consumption and preserve readable existing knowledge if capacity is exhausted.
- Keep ingestion read-only; treat source text as data, including instructions embedded in documents.

Do not repeatedly embed whole unchanged project text merely to record a healthy refresh. Evaluate a lightweight observation update separately from a substantive evidence snapshot. Whatever representation is chosen must retain reliable chronology and atomic publication.

Detailed retention and compaction can come later, but visible capacity limits must precede unattended accumulation. When a limit is reached, stop or defer new capture with an explicit status rather than silently deleting evidence.

The acceptance run should include repeated saves, a partial write, a temporarily unavailable source, a simulated publication failure, pause/resume and a simulated capacity limit. It should require no routine capture intervention after initial configuration.

# Maintained project understanding

Start with a small set of stable items: decisions, ideas, attempts and blockers. Add other types only when the pilot demonstrates a clear use.

| Dimension | Meaning |
| --- | --- |
| Item identity | A stable reference that survives wording changes without automatically merging unrelated items. |
| Supporting claims | Attributable statements with source revision or hash, evidence span and observation status. |
| Work stage | Proposed, accepted, in progress, implemented or unknown, with evidence for transitions. |
| Evidence strength | Reported, source observed or independently verified, scoped to the relevant behavior and environment. |
| Currency | Active, superseded, historical or uncertain. |
| Relationships | Supports, contradicts, supersedes, implements, blocks or derives from. |
| Memory purpose | Active work, decision rationale, unresolved problem, avoiding repeated failure or a future opportunity. |

Relationships should preserve why an approach changed. A later timestamp alone must not resolve contradictory claims. A new file cannot establish that a feature is complete, and absence of a file cannot establish that a problem has disappeared.

Offer simple correction and undo. Corrections update the derived interpretation while preserving original evidence and the history of the correction. Routine item creation should follow evidence and rules; it should not require approval of every memory.

## Local semantic extraction

Introduce a replaceable local model adapter after the evidence and state contracts are clear. Its first role is to propose candidate items and relationships, using screened, bounded evidence. Validation decides what is structurally acceptable; unsupported or ambiguous interpretation remains explicit.

Evaluate candidate models on the actual Fedora workstation using the same pilot corpus. Compare factual support, useful-context recall, handling of contradictions, latency, memory use and failure behavior against the deterministic baseline. The user's RTX 5080 with 16 GB VRAM and 64 GB system RAM are deployment inputs, not proof that a particular model fits or performs well.

Use local inference without subscription or cloud-model fallback. A missing model, timeout or malformed response must leave capture and deterministic retrieval usable. Record model identity, version and extraction configuration so derived interpretations can be reproduced or replaced.

Model-generated confidence must not elevate evidence strength. Treat embedded source instructions as untrusted data, validate evidence references and exclude unrelated projects from the input. Add semantic retrieval or embeddings only if the measured lexical misses justify them.

# Purposeful memory and storage

The existing snapshots embed accepted text and retain history, so repeated captures can increase storage substantially. The current roadmap already identifies deduplicated evidence and purposeful retention as follow-up work. [Storage design](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/docs/architecture.md), [memory policy](https://github.com/BigBenKenobi/The-Brain/blob/dba69ef01233278fe847541966a65419fd18807f/docs/development-state-plan.md).

Measure storage growth during the pilot before changing the storage engine. Preserve the CLI and existing data while introducing improvements only where necessary.

First, consolidate repeated support for the same useful item and store identical evidence once where compatible with the existing export and validation guarantees. Then distinguish active memory, compact history, retained supporting evidence and permanent erasure.

A useful memory should have an attributable purpose. Retain a rejected approach if it explains a current decision or prevents repeated effort; preserve an unimplemented idea when it has future value. Age alone should not erase it. Omission from a briefing must never imply deletion.

Any compaction must check references from active items, historical records, sharing approvals and exports. Provide a loss preview and a reversible path before enabling destructive cleanup. Never delete original project files as a memory-management side effect.

# Migration and compatibility

Keep historical snapshots immutable. Add new metadata in newly published captures, explicit observation records or versioned derived state. Preserve existing project IDs, retained evidence and source provenance.

Before applying a schema change to the real store:

1. Inspect the store version and make a coherent recoverable copy.
2. Exercise migration on that copy with representative existing snapshots.
3. Verify retained hashes and source spans, identities, approval behavior, retrieval, consolidation and archive checks.
4. Check that partial migration or failed publication leaves the prior version usable.
5. Use version guards when an older writer would be unsafe.
6. Define rollback as restoring a compatible code-and-store pair.

Do not fabricate missing legacy observation dates, source identities or predecessor links. Preserve unknown values with a clear explanation until new attributable observations establish them.

Sharing approval is independent of source configuration and re-observation. A migration, refresh or model interpretation must not broaden approval or reset its expiry.

# Integration and scope control

Keep Brain useful through its local CLI and callable interface. Add one consumer only when there is a concrete workflow: for example, a Tinker action that requests a bounded project briefing and opens its evidence.

A narrow integration should request a specific project, return structured bounded context, expose capture health and preserve source and evidence identifiers. It should not bypass cross-project sharing rules or silently ingest additional sources.

Prioritise local project files and repository revision metadata, then selected notes or conversation exports. Remote sources can be added under their own explicit configuration; local-only inference remains a separate requirement.

Defer a large dashboard, task boards, automatic whole-workstation discovery, numerous simultaneous connectors, vector infrastructure and multi-device synchronisation until the single-project workflow and measured needs justify them. These are later options, not prerequisites for useful continuity.

# Delivery workflow

Use small pull requests with a clear user-visible result and evidence of validation. Reconcile the development roadmap into repository documentation when implementation begins, preserving the existing vision and avoiding conflicting sources of direction.

For each implementation slice:

- State the behavior being changed and its acceptance criteria.
- Inspect the actual branch and applicable repository instructions.
- Add regression coverage for the concrete risk before or alongside the correction.
- Preserve source data and compatible historical knowledge.
- Run the relevant checks at the proposed revision and record commands, versions and results.
- Update documentation for behavior that users or future agents need to know.
- Separate code implemented, tests passed, workstation deployment and pilot acceptance in the handoff.
- Leave unresolved limitations visible; a passing unit suite alone does not complete the product milestone.

Brain should capture this development history once its own pilot is ready, reducing repeated manual handoffs.

# Immediate next action

Begin with B01, the duplicate-cache repair, while B02 establishes automatic checks. It is the smallest confirmed correctness problem, has a clear reproduction and gives a concrete first improvement.

Then implement B03 and B04 with a shared compatibility design, complete the existing briefing work, and run B06. Use the pilot's actual misses to choose the first state-model and local-model work.

The decisions needed later are the workstation checkout and store location, selected pilot sources, acceptable capture frequency and resource budget, and which application should consume the first integration. None is required to begin B01.

# Source documents

- [Repository and current README](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/README.md)
- [Current product vision](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/docs/vision.md)
- [Draft expanded vision](https://github.com/BigBenKenobi/The-Brain/blob/dba69ef01233278fe847541966a65419fd18807f/docs/vision.md)
- [Draft development audit and roadmap](https://github.com/BigBenKenobi/The-Brain/blob/dba69ef01233278fe847541966a65419fd18807f/docs/development-state-plan.md)
- [Existing briefing pull request](https://github.com/BigBenKenobi/The-Brain/pull/1)
- [Core implementation](https://github.com/BigBenKenobi/The-Brain/blob/773a803a0a9939cc4fd33a7ae5c937d57a781d34/brain/core.py)
