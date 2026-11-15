# Contributing to Project Brain

Start with the [README](README.md) for CLI usage and the
[architecture](docs/architecture.md) for the storage and retrieval boundaries.
The [development status](docs/development-status.md) separates implemented
behavior, measured evidence and remaining product acceptance.

## Development checks

Use Python 3.11 or newer on Linux/POSIX and run commands from the repository
root. The CLI and test suite use the Python standard library; installing the
package, model weights or provider credentials is unnecessary.

```bash
python3 -m unittest discover -s tests -v
python3 -m brain --help
```

[Python tests](.github/workflows/tests.yml) runs the unittest command on Python
3.11 and 3.14. A focused iteration can use discovery's filename filter, for
example `python3 -m unittest discover -s tests -p 'test_sources.py' -v`.
Run the complete suite before submitting changes across shared storage,
ingestion or retrieval boundaries.

The tests create disposable stores and synthetic sources in temporary
directories. Keep fixtures synthetic. Do not copy a real knowledge store,
private retained evidence, credentials or local project records into tests or
pull-request output. Historical local paths in documentation do not exist in a
fresh checkout.

## Try a CLI change in isolation

Use sibling source and store directories outside the checkout, and pass
`--brain` on every command so an inherited `PROJECT_BRAIN_HOME` cannot select
your normal store:

```bash
trial_dir="$(mktemp -d)"
mkdir "$trial_dir/source"
cat > "$trial_dir/source/README.md" <<'EOF'
# Synthetic contributor fixture

## Decision and rationale
Use a disposable source to exercise ingestion without personal project data.

## Limitations and unresolved issues
This fixture does not establish product or real-project acceptance.
EOF
python3 -m brain --brain "$trial_dir/store" init
python3 -m brain --brain "$trial_dir/store" ingest "$trial_dir/source"
python3 -m brain --brain "$trial_dir/store" list
```

Use the returned project ID for `status`, `context` and `validate`, for example:

```bash
python3 -m brain --brain "$trial_dir/store" status PROJECT_ID
python3 -m brain --brain "$trial_dir/store" context PROJECT_ID 'disposable source'
python3 -m brain --brain "$trial_dir/store" validate PROJECT_ID
```

Replace `PROJECT_ID` with the actual ID. Inspect ingestion omissions and coverage
warnings as well as the exit status. Keep the trial directory while reviewing
the result; it contains only the synthetic source and disposable store.

## Match evidence to the change

Add regression coverage for changed behavior using the existing `tests/`
modules. Preserve the distinctions between captured excerpts, interpretation,
reviewed verification and retirement readiness. A successful capture or test
does not establish the truth of every retained claim or real-user acceptance.

Submit focused pull requests that explain the resulting behavior, commands
actually run and any remaining limits. Documentation-only changes need command,
path and content checks appropriate to the edit. Do not regenerate dated
evaluation reports merely to refresh their timestamps or present historical
measurements as new results.
