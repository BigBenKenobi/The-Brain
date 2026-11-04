# original

Project ID: 6f15f6e6-f5b0-402f-9a69-49a225f04cbf

Deterministic excerpts, not verified conclusions.

## README.md:1
# Decision: SQLite retry
Solution: bounded retry handles SQLite database locking during transient contention.
Limitation: never retry permanent corruption. Outcome is documented, not independently verified.
Evidence: README.md:1 (historical_record)

## private.md:1
Internal confidential launch plans for orchard customers.
Evidence: private.md:1 (historical_record)

## pyproject.toml:1
[project]
name = "original"
version = "1.0"
Evidence: pyproject.toml:1 (observed_implementation)

## Retirement readiness
Knowledge-only. No complete recoverable source archive exists.
{
  "project_id": "6f15f6e6-f5b0-402f-9a69-49a225f04cbf",
  "classification": "knowledge-only",
  "verified_recoverable_source_archive": false,
  "records_preserved": 3,
  "evidence_blobs_retained": 3,
  "omitted": [
    {
      "path": ".env",
      "reason": "sensitive filename; content not retained",
      "size": 29,
      "status": "sensitive"
    },
    {
      "path": "asset.bin",
      "reason": "format not interpreted or retained",
      "size": 2,
      "status": "unsupported"
    }
  ],
  "coverage_warnings": [],
  "limitations": [
    "Only selected UTF-8 evidence is retained. No complete source archive exists.",
    "Binary assets, dependencies, Git history and omitted materials cannot be reconstructed.",
    "Extraction does not prove correctness or capture every decision. Review retained evidence before retirement.",
    "Removing the source can lose working functionality, history, assets and secrets. This command never deletes or moves sources."
  ]
}
