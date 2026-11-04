# Brain — mission and guiding product requirement

**Status:** Current governing product direction (4 November 2026).

## North star

**Product clarification, 4 November 2026:** The Brain is a workstation-integrated
development memory and organisational system. It should maintain an evidence-backed
understanding of projects, current work, implementation stage, decisions, concepts
and ideas that have not been implemented, tailored to non-linear working habits.
Returning to a project is one benefit of that continuously maintained understanding.

**Preserve nothing without a reason.** Capture is not automatically lasting memory.
Useful reasons include an active objective, a decision and its rationale, an open
problem, a lesson that avoids repeated work, or an idea with a future use. Keep the
minimum supporting context needed to understand and check those items. Repetition
should reinforce or update memory, not fill it with duplicate observations.
The existing full-evidence snapshot store does not yet implement this policy.

Precision includes saying what is unknown. Observed source code, reported success,
verified behavior, and a user's commitment are distinct. A stale or partial capture
must never claim exact live state. Routine capture should require little maintenance
after the user chooses sources and boundaries.

See [the delivery specification and audit](development-state-plan.md) for the first
milestone, memory rules, acceptance criteria and implementation backlog.

**Brain is a personal knowledge and continuity system that makes switching between projects and ideas inexpensive.** It should capture, organise, preserve and retrieve meaningful context with as little manual maintenance as possible, so someone can leave a project at any point and return later without reconstructing their progress or reasoning.

**The user should not have to maintain Brain in order for Brain to be useful.**

## Core user experience

1. **Capture with minimal interruption.** Import existing project workspaces and, with explicit source permissions, progressively ingest ongoing files, repositories, conversations and notes where integrations support it. Manual capture remains an option, not the assumed routine.
2. **Make sense of the work.** Organise evidence into projects, ideas, decisions and their rationale, discarded approaches, attempted solutions, observed implementation, open questions, and relationships across sessions. Distinguish what is proposed, reported, implemented and independently verified.
3. **Preserve continuity.** Keep meaningful history and provenance across pauses, project changes and source retirement. Recognise superseded decisions without silently erasing them or treating old context as current.
4. **Retrieve precisely.** Answer natural questions about a project using the most relevant, current, source-grounded context. Disclose uncertainty, gaps and conflicts instead of manufacturing certainty.
5. **Resume with momentum.** On returning after days or months, provide an accurate, concise briefing: the objective, last known state, decisions and reasons, completed versus uncompleted work, blockers, and the next practical actions. Supply direct pointers to supporting evidence.

## Product design rules

- **Low cognitive overhead beats elaborate organisation.** Avoid mandatory tagging, filing, check-ins, task grooming or rigid processes.
- **Continuity beats feature count.** Prioritise successful return-to-work experiences over dashboards and general project-management features.
- **Adapt to non-linear work.** Frequent context switching, unfinished ideas and long pauses are normal inputs, not errors to correct.
- **Truth and traceability matter.** Preserve source identity, dates, evidence and uncertainty. Never confuse a discussion, plan or code observation with tested functionality.
- **Privacy and control are foundational.** Ingestion and automation must respect explicit source permissions and data boundaries. Do not silently transmit, share, modify or delete source material. Project knowledge is private by default.
- **Remain useful without automation.** If an integration or model is unavailable, offer an honest, lower-friction manual or deterministic path instead of pretending the feature exists.

## Primary acceptance scenario

Someone explores an idea, works on a project for several sessions, changes focus repeatedly, and comes back weeks later without having maintained project notes. Brain can recover where the project stands, what was decided and why, which work actually happened, what remains unresolved, and what to do next—backed by original evidence. The user spends substantially less effort reconstructing context than they would without Brain.

**Decision test for every feature:** Does this reduce the effort required to capture work, find useful knowledge, or resume a project **without adding comparable maintenance work**?

## Relationship to the current implementation

The current repository supplies an initial deterministic foundation: read-only source ingestion, private evidence-backed records, historical snapshots, deduplication, scoped retrieval, review and knowledge-retirement checks. It does **not** yet provide automatic ongoing capture from conversations or repositories, semantic project-state reconciliation, or a complete one-step resume experience. Those are product objectives, not delivered capabilities.

Knowledge retention when retiring or discarding a source remains an important use case. It is **one part of the wider continuity mission**, not the mission's limit. See [architecture](architecture.md), [implementation progress](progress.md), and the [knowledge-retirement standard](knowledge-retirement-standard.md) for the existing implementation and its boundaries.

