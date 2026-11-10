# Saved sources and observation freshness

A registered local source has a stable identity, a project identity, a location,
and revisioned capture settings. Repeating an ingest without settings reuses its
exclusions, historical designation and budgets. Explicit settings affect future
captures; historical snapshots remain immutable. Multiple sources belonging to
one project retain independent settings and namespaced evidence paths.

Use an explicit store path for every command:

```sh
python3 -m brain --brain /path/to/store ingest /path/to/project --exclude-path private --max-files 1000
python3 -m brain --brain /path/to/store sources
python3 -m brain --brain /path/to/store refresh SOURCE_ID
python3 -m brain --brain /path/to/store configure-source SOURCE_ID --clear-exclusions
python3 -m brain --brain /path/to/store relocate-source SOURCE_ID /new/project/location
```

`--exclude-path` replaces the saved exclusion list; omission preserves it.
`--clear-exclusions` explicitly empties it. `--reset-budgets` on
`configure-source` restores store defaults. `--new-source --project-id PROJECT_ID`
adds an independent source. Relocation preserves identity and configuration;
ambiguous legacy adoption requires an explicit `--adopt-legacy` mapping.
Sources start with automatic capture disabled. The bounded worker and optional timer are described in [automatic refresh](automatic-refresh.md).

Successful observation, extraction time, historical status, and approval expiry
are separate facts. An unchanged successful read updates observation without
re-extracting evidence or renewing sharing approval. Unknown legacy dates stay
unknown. `context --max-age-days N` filters by successful observation and excludes
unknown dates. Unreadable or unvisited files cannot gain a successful observation.
Capture health distinguishes complete, partial and failed attempts and exposes
coverage limitations. A missing source keeps the last usable snapshot available.

Briefings show source health and bounded supporting excerpts. Explicit correction
relationships suppress obsolete records without granting sharing permission;
missing replacement evidence stays visible as a limitation. Retrieval normalizes
terminal punctuation without rewriting historical search indexes. A cited report
or implementation is not independently verified behavior.

## Store compatibility and rollback

Source settings introduced writer format 2. This package now creates writer-3
stores for lightweight observations. Version-1/2 stores remain readable but require an
explicit upgrade before writes:

```sh
python3 -m brain --brain /path/to/store upgrade-store --backup /separate/new/backup
```

Run this against a coherent disposable copy first. The command holds the writer
lock, copies the store and compatible reader code, verifies copied file hashes
and snapshot structure, and only then changes the configuration writer version.
The backup destination must not exist and must be outside the store. Existing
snapshots and approval files are not rewritten. Old version-1 writers reject the
version-3 configuration. For rollback, stop writers and restore the complete
backup store with its saved code; do not mix files from before and after upgrade.
The saved version-3 reader reads the version-1 backup but requires upgrade before
writing it; retain the previous application release for immediate legacy writes.

This delivery cannot open later version-4 stores. It is not a
runtime replacement for such deployments.

## Validation

`python3 -m unittest discover -s tests` passes 54 tests on Python 3.11.18 and
3.14.10. Coverage includes duplicate survivor caching, independent source
settings, relocation, explicit clearing, unchanged freshness, approval expiry,
failed publication, missing-source recovery, bounded/partial reads, legacy
unknown dates, backup integrity, upgrade failure and briefing corrections.
The inherited GitHub workflow runs the suite on Python 3.11 and 3.14.
These checks do not establish human resumption benefit or production acceptance.
