# Maintained project state

`python3 -m brain --brain STORE state PROJECT_ID --limit 20` returns private,
evidence-backed candidates for decisions, ideas, attempts and blockers. Briefings
include the same bounded view. Candidates distinguish work stage, evidence strength,
currency and memory purpose. Reported outcomes remain reported; proposals are not
accepted commitments. File removal changes availability, never resolution.

Each item has a project-scoped ID derived from its original canonical record.
Changed wording creates another candidate until explicitly reviewed. `state-correct`
can attach supporting evidence to the original item and revise its interpretation;
it does not merge other candidates automatically. Every correction requires a
same-project record, optional snapshot (default current), and rationale:

```text
state-correct PROJECT_ID ITEM_ID --work-stage accepted --record-id RECORD_ID --rationale "Reviewed decision"
state-relate PROJECT_ID NEW_ITEM OLD_ITEM --kind supersedes --record-id RECORD_ID --rationale "Explicit replacement"
state-undo PROJECT_ID EVENT_ID --rationale "Withdraw interpretation"
```

Relationship kinds are supports, contradicts, supersedes, implements, blocks and
derives_from. Supersession rejects cycles and competing replacements. Contradictions
remain explicit; timestamps alone cannot resolve them. Free-text corrections cannot
assert independently verified behavior. Undo appends an event and preserves evidence
and audit history. `undo-relation` separately withdraws an existing canonical-record
precedence edge using a new snapshot; it does not revoke sharing approvals.

Capture publishes a derived catalogue pointer atomically with the snapshot pointer.
Its immutable catalogue stores record/snapshot references, so older unresolved items
survive bounded recent-history scans. Unchanged captures reuse the catalogue.
`state-sync PROJECT_ID --max-snapshots 64` explicitly backfills known legacy ancestry
in bounded passes. Missing legacy lineage remains unknown. Compatible capture writers
that do not maintain catalogues may leave them stale; sync reconciles their published
history. Ordinary reads merge recent evidence and never write back.

The journal lives in `projects/PROJECT_ID/state`: `head.json` contains version 1,
project identity and ordered published event UUIDs. Immutable `events/UUID.json`
records corrections, relationships or undo targets; an atomic head write publishes
them. Failed publication leaves unreachable events. Catalogues live in `catalogs/`
and are selected by the registry's optional `state_catalog` pointer. These derived
files do not change the immutable evidence snapshot format or sharing permissions.

Read limits and omissions are explicit. Default discovery reads at most 64 snapshots
and 2,000 candidates; explicitly reviewed endpoints are replayed from the journal.
Display returns at most 100 items, 400 summary characters and five evidence references
per item. Superseded items require `--include-history`. Large legacy stores may need
multiple sync passes. The journal is currently replayed in full, so long-term journal
compaction remains future work.

This is the deterministic foundation of milestone 4. It is not a local model adapter,
a semantic truth check, or proof that a briefing improves human resumption time.

The bounded display balances item kinds and source paths after giving explicit
reviewed items priority. It does not resolve or delete omitted items. Same-corpus
paired selection and a ten-capture simulated absence trial are recorded in
`evaluations/maintained-state-results.json`.

## Explicit consolidation of duplicate support

```text
state-consolidate PROJECT_ID SURVIVOR_ITEM ABSORBED_ITEM --rationale "Reviewed as the same decision"
state-undo PROJECT_ID EVENT_ID --rationale "Withdraw equivalence review"
```

Consolidation is an explicit local interpretation. It keeps the survivor's summary,
identity and memory purpose, combines retained evidence claims, and marks the other
item as represented by that survivor. Original identities remain in `--include-history`;
no snapshot, evidence, record, source file or sharing approval is rewritten or removed.
Work stage and verification strength are not elevated. A bounded view reports how
many original items are represented by consolidation and still limits displayed
claims; the full state retains the complete claim set.

Kind, work stage, currency and purpose must agree before grouping. Resolve differences
with explicit corrections first. Contradictory or superseding items cannot be grouped.
Other relationships keep their original endpoint identities and remain visible when
the consolidated group is displayed. Later canonical precedence conflicting with a
group marks it uncertain and reports that consolidation needs review; it never erases
the conflicting relationship. Additional duplicates can be grouped into an existing
survivor; absorbed identities cannot be independently edited until consolidation is
undone. This avoids silently redirecting corrections to a different item.

Undo is append-only and validates the resulting replay before publication. If undoing
an earlier correction would invalidate a dependent grouping, undo that grouping first.
Publication failure leaves the old journal head authoritative. No automated semantic
matching, permanent erasure, source cleanup or journal garbage collection is added.

The first consolidation publishes state journal head version 2. New readers accept
versions 1 and 2; older version-1 state readers reject version 2 explicitly. The store
writer format remains 4, and snapshot readers still materialize canonical schema 1.
After undo the journal stays version 2 because its audit history still contains the
consolidation. Keep a compatible reader for that history; undo does not authorize
rewriting the head back to version 1.
