# The Brain: development understanding and purposeful memory

Product direction and initial implementation audit, 4 November 2026.
Baseline inspected: `773a803a0a9939cc4fd33a7ae5c937d57a781d34`.

## Outcome

The Brain should understand the user's development across local workspaces and
permitted integrations with little ongoing maintenance. It must distinguish ideas,
commitments, attempted approaches, source implementation and verified behavior.
It should retain information for a clear reason and surface relevant current
knowledge without requiring the user to filter a growing archive.

The first delivery is a conservative evidence briefing over existing captures.
It is a foundation for maintained project state, not a claim that semantic
understanding or live tracking already works.

## Three separate layers

1. **Observation:** source identity, revision/content hash, capture time, scope,
   permissions and a retained evidence span. Observation establishes what was seen.
2. **Project understanding:** objectives, ideas, decisions, attempts, work items,
   blockers and relationships, each with supporting observations and explicit
   uncertainty. This layer must reconcile revisions without silently rewriting history.
3. **Useful memory:** admitted knowledge with a purpose, relevance conditions,
   supporting evidence and a lifecycle. A briefing selects from this knowledge for
   the user's current question; omission from a briefing is not deletion.

Today snapshots mostly implement the first layer, with heuristic excerpt labels.
`briefing` provides a bounded view of those observations while the second and
third layers are designed. Avoid encoding confidence as an arbitrary percentage.

## State model to implement next

Keep independent dimensions rather than a single misleading progress score:

| Dimension | Proposed values or information |
| --- | --- |
| Item kind | Objective, idea, decision, attempt, work item, blocker, lesson |
| Work stage | Proposed, accepted, in progress, implemented, retired; unknown allowed |
| Evidence strength | Reported, source observed, independently verified; scoped to revision and environment |
| Currency | Active, superseded, historical, uncertain |
| Relationships | Supports, contradicts, supersedes, implements, blocks, derived from |
| Memory purpose | Active work, rationale, unresolved problem, avoid repeated failure, future opportunity |

A test file is observed source, not a passing test. A report saying tests passed
is a claim until an attributable run with revision, command, environment and result
is captured. A code change suggests activity but does not identify the user's
current intention. A proposal can remain useful without becoming a commitment.
Completion is specific to an acceptance criterion; never infer an entire feature
is complete because a matching function or phrase exists.

## Memory policy to implement

- Admit a durable item only with an explicit purpose and attributable evidence.
  Explain the admission reason without asking the user to tag every observation.
- Merge repeated support for the same item; do not infer identity from wording
  similarity alone when doing so could combine unrelated ideas or projects.
- Preserve a concise superseded decision and its rationale when it explains current
  work; surface the current decision first. Unresolved conflicts remain visible.
- Keep unsuccessful attempts when their result prevents repeated effort or explains
  a decision. Routine duplicate logs do not deserve independent memory entries.
- Treat an unimplemented idea as a future opportunity with its context and trigger
  for revisiting; lack of recent activity alone does not make it worthless.
- Separate active retrieval, compact historical memory, retained evidence and
  permanent erasure. Design correction/undo and dependency checks before purging.
- Never delete or modify original project files as a side effect of memory policy.

Initially retain the existing evidence store unchanged. The future retention
implementation needs explicit handling of record references, historical approvals,
exports and accidental sensitive-data retention. Presentation filtering alone does
not satisfy the goal of purposeful storage.

## Implementation audit

Inspected the CLI, `core.py`, extraction interface, schemas and existing tests.
The baseline's 21 unittest tests passed locally on disposable fixtures. No private
Fedora knowledge store or real workstation was available. This is a focused
architecture/behavior audit, not a comprehensive security or performance assessment.

| Finding and evidence | Consequence | Action |
| --- | --- | --- |
| `Brain.ingest`, `validate`, retained-evidence and archive checks preserve hashes and source spans; publication is atomic | Useful evidence foundation with existing failure-path tests | Keep and extend; avoid a rewrite |
| `extract` selects windows using keywords; record relationships are always empty | No maintained semantic entities, contradiction resolution or feature lifecycle | Add the state model with provenance and explicit uncertainty |
| `Brain.summary` emits all records plus a retirement report | High reading effort; no concise state view | First milestone adds a separate bounded briefing |
| `ingest` defaults exclusions to an empty collection; CLI defaults `--exclude-path` to an empty list | A refresh without repeated flags expands capture scope | Persist per-source capture settings before automating; require an explicit action to broaden scope |
| Cache hits reuse records including `created_at`; `retrieve` filters on that extraction timestamp | An unchanged file can be newly observed but its records still age out of retrieval | Separate extraction time, last observation and semantic review time; test all three |
| Accepted text is stored whole in each snapshot and history has no pruning | Storage growth and retained noise conflict with the long-term memory goal | Design deduplicated evidence storage and purpose-based retention with migration tests |
| Non-code text uses `historical_record` even when it is a current document | Existing status name cannot establish semantic currency | Keep backward compatibility; introduce an explicit currency dimension |
| `project_types` checks inventoried filenames, not necessarily retained/parsed contents | Metadata is a hint, not verified project structure | Label hints and eventually derive richer metadata from accepted evidence |
| Snapshot creation also occurs during consolidation; records may come from older pinned supplements | Latest publication time cannot mean latest source observation | Show pinned provenance now; add explicit per-source observation metadata next |
| Many omissions are file statuses rather than `coverage_warnings` | Looking only at warnings understates coverage gaps | Briefing displays omission counts and warnings; future state engine must consume both |
| No `.github/workflows` in baseline | Checks depend on manual execution | Add a small supported-Python CI matrix in a follow-up |
| `brain/extraction.py` is only a future adapter protocol | There is no installed semantic model or provider execution | Make semantic extraction opt-in, bounded and validated before integration |

## First milestone delivered on this branch

Command: `python3 -m brain --brain /path/to/store briefing PROJECT_ID`.
Use `--json` for structured output and `--limit 1..20` for excerpts per section.

- Read-only, same-project briefing from a validated active snapshot.
- Objective candidates, ideas, decisions, problems, reported outcomes, observed
  code and historical evidence; every excerpt explains its selection and cites
  its record, snapshot, file hash and source span in JSON.
- Markdown includes file/line/record references and supplement provenance.
- Bounded excerpts and path lists, with omitted counts. Unknown sections stay
  unknown. Section labels describe lexical candidates, not established facts.
- Explicit predecessor links on ingestion/consolidation; comparisons cover new,
  changed and no-longer-retained paths. An exclusion is not called a deletion.
- Legacy captures remain readable with no guessed predecessor. A failed publication
  cannot become the next baseline merely because its JSON exists on disk.
- No new runtime dependency, provider call, source execution or retention mutation.

Classification is deliberately coarse: one excerpt belongs to one section; a
mixed excerpt can contain both a rejected idea and a chosen approach. Negative
phrasing, contradictions and chronology are not resolved. A default briefing can
omit useful excerpts because it orders by source path/line, not semantic importance.
This is visible in the output and is part of the next milestone, not hidden accuracy.

## Acceptance scenario and verification

A disposable project begins with an objective, an untested idea, a decision, a
blocker and partial code. A later capture changes the decision and code, adds a
test-success claim and removes the blocker document. The briefing must:

1. Keep the proposal distinct from observed code and the test-success claim.
2. Cite retained evidence for each selected excerpt and avoid certifying completion.
3. Report changed paths against the published predecessor; omit obsolete text from
   the active briefing while keeping old snapshots available.
4. Describe missing evidence without inferring deletion, resolution or success.
5. Work without original source files and without exposing unrelated projects.
6. Disclose incomplete inventory, selection limits, historical captures and pinned
   supplements. Reject corrupted evidence rather than print it as trustworthy.

`tests/test_briefing.py` covers this scenario plus unchanged refreshes, exclusions,
failed publication, legacy snapshots, read-only behavior, display bounds, corruption,
consolidation and both CLI output modes. Run:

```bash
python3 -m unittest discover -s tests -v
```

The full suite contains 30 tests after this change. These tests validate mechanics
and conservative claims; they do not establish semantic understanding quality.

## Ordered follow-up backlog

1. **Remember source boundaries.** Persist exclusions, historical designation and
   budgets per configured source; design explicit reset/override behavior. Verify
   an ordinary refresh never silently broadens scope.
2. **Represent observation freshness.** Track last-seen content separately from
   extraction/review timestamps. Verify unchanged content refreshes observation,
   not proof of correctness or approval expiry. Distinguish consolidation time.
3. **Introduce attributable state items.** Add stable entity identities, claims and
   relations alongside existing snapshots. Begin with one project's decisions,
   ideas and blockers; preserve conflicting claims rather than selecting a winner
   by keyword or timestamp alone. Test correction and supersession.
4. **Evaluate against a real project.** Choose one permitted repository and a small
   relevant conversation/notes export. Have the owner check factual errors, missing
   important context, repeated noise and time needed to resume work. Do not ingest
   the whole workstation to obtain this evaluation.
5. **Implement useful-memory admission and compaction.** Require machine-readable
   retention purposes, preserve referenced evidence, test rollback and storage
   growth, and assess what information would be lost before deletion is enabled.
6. **Automate capture.** Only after boundaries and freshness work, add an opt-in
   local refresh service with debounce, backoff, pause and clear capture health.
   Persist scope; never execute discovered project scripts as part of ingestion.
7. **Extend understanding and integrations.** Add a validated semantic adapter and
   repository/conversation integrations as independently permissioned sources.
   Cross-project sharing remains explicit and separate from project organisation.

The next best implementation step is source-boundary persistence, followed by
observation freshness. Those make future automation predictable while the current
briefing gives us a concrete surface for evaluating usefulness.
