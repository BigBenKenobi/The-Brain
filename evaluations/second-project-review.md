# Second-project technical pilot: Tinker

This trial captures only `README.md`, `docs/PROJECT_ASSISTANT.md` and, where present,
`docs/RELEASE_READINESS.md` at three explicit tracked Tinker revisions. The Git blob
hash manifest and external answer keys are retained with the evaluation. Tinker's
checkout, databases, conversations, model files and runtime are untouched. The pilot
store is independent of the live Brain store, with no enabled automation or sharing.

The initial briefing surfaced 1/3, 1/3 and 2/5 reference phrases across the three
checkpoints. The most consequential miss was release-gate prose inside Markdown
tables: a reported full-suite timeout and a direct-connectivity limitation were
retained and searchable, but not represented as separate maintained blockers.

The revised deterministic extractor splits substantial prose rows into exact,
contiguous source excerpts. Numeric coverage rows remain excluded from narrative
selection. Failure wording receives ranking priority among table excerpts; it does
not certify a failure, completion or resolution. Project introductions can appear
as objective candidates without becoming release-acceptance claims.

The final view surfaces 2/3, 2/3 and 3/5 reference phrases. Both the timeout and the
connectivity limitation now survive in maintained state, although the short briefing
only shows the timeout. The retired-device-gate distinction and some longer
qualification statements remain absent from the short view. All reference phrases
remain retrievable with scoped context. These misses are recorded rather than
counted as semantic acceptance.

Every selected excerpt traces to retained evidence. An unrelated private canary
stays out of the briefing. Unchanged capture uses observation storage; source outage
preserves the last snapshot and reports failure; restoration refreshes successfully.
This is a second real-project *technical* pilot, not proof of reduced human
resumption effort or validated local-model understanding.

The extractor identity changes from deterministic-3 to deterministic-4. New record
IDs include extractor identity and the full span, preventing altered excerpts from
inheriting an approval for an older extraction. Historical snapshots and approval
files remain immutable; new interpretations require their own reviewed mapping and
sharing approval. The live timer remains pinned to its earlier runtime, so no live
re-extraction or approval migration was performed.

Reproduce with `python3 scripts/evaluate_second_project.py --tinker-repo PATH
--output NEW_DIRECTORY`. Raw artifacts are under
`evaluations/runs/2026-11-10/tinker-history-final/`; compact results are in
`evaluations/second-project-results.json`. Owner review and semantic evaluation
remain outstanding.
