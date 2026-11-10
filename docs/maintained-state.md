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

The bounded display balances item kinds and source paths after giving reviewed
items priority. Configuration values do not seed project commitments. Long prose
under explicit headings can yield exact paragraph previews, while explicit
verification caveats remain separate from inferred blockers or passed gates. Preview
character offsets and original record/source references preserve attribution; partial
previews require surrounding evidence to interpret qualifications.

## Delivery boundary and validation

This delivery reads/writes store version3 and derived journal version1. It does not
include later version4 evidence blobs or journal-version2 support consolidation,
and must not replace a deployment requiring those newer formats. Older capture
writers can leave a catalogue stale; explicit state-sync is the supported recovery.
Do not manually lower format versions. Preserve compatible code and store backups.

86 unittest tests pass on Python3.11.18 and3.14.10. State tests cover stable identity,
missing blockers beyond the history budget, correction/undo, cycle and scope checks,
failed publication, catalogue reuse/reconciliation and balanced bounded output.
Configuration and paragraph-preview tests preserve reviewed corrections and exact
evidence spans. These tests establish neither local-model quality nor human benefit.
