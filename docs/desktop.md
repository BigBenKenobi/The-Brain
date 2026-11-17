# The Brain desktop

The optional PySide6 desktop is a local, read-only navigator with the same charcoal,
ivory, sage and gold styling used by Stashed and Affinity.

## Launch

From a checkout with PySide6 available:

```sh
./scripts/launch_desktop.sh
```

For another existing store:

```sh
python3 -m brain.desktop --brain /absolute/path/to/Project-Brain
```

For a packaged installation, install the optional `desktop` extra and use
`brain-desktop --brain /absolute/path/to/Project-Brain`. The CLI still has no Qt
requirement. `python3 scripts/install_desktop.py` installs a per-user application
menu entry for the current checkout. An existing launcher is backed up with a
`.previous` suffix. Remove `the-brain.desktop` and `the-brain.svg` from the user
applications/icon directories to uninstall that entry; knowledge is untouched.

## Navigation

Select a project in the sidebar. Overview shows bounded recorded excerpts and
capture limitations. Knowledge provides decisions, ideas, attempts and blockers;
filters do not change the underlying knowledge. History opens an exact capture,
including all its retained records and recorded predecessor changes. Sources
shows configured scope, budgets and observation health.

Select an item or **Open evidence** to read the full statement and its qualifications.
The inspector opens the exact cited snapshot, highlights referenced lines, and
pages retained text in blocks of at most 200 lines. Copy excerpt copies the selected
visible text (including displayed line numbers), or the whole displayed retained
text when nothing is selected. Copy citation includes the project, snapshot and
visible line range. At narrow widths the inspector overlays the workspace; Escape
closes it without losing the underlying view.
If a capture writer temporarily blocks evidence reading, **Retry evidence** retries
the same snapshot and page without restarting navigation.

Search defaults to the selected project's private context. Shared knowledge requires
explicit technology labels matching the original approval; the desktop never approves
sharing. Search is the existing deterministic word matching, not a model answer.

- `Ctrl+K`: focus search.
- `Alt+Left`: close evidence, return from history/search, or return to the previous project.
- `Escape`: close evidence.
- `Ctrl+R`: reload stored knowledge; does not capture sources.

The desktop saves geometry, pane sizes, recent projects and selected store through
Qt's application settings, outside the Brain store. Project filters and scroll
positions, search scope and technology labels survive navigation within the session.
Clearing or changing a search closes its evidence inspector; typing during a project
load is preserved. Selecting a different store clears the previous store's views,
including when the new path is empty or invalid. Initial store selection uses
`--brain`, then `PROJECT_BRAIN_HOME`, saved selection, or `./Project-Brain`.

## Read-only boundary and limits

The presentation adapter calls existing readers and opens the existing store lock
read-only, taking a nonblocking shared lock for each query. Capture writers hold
exclusive locks. A busy writer produces a retryable message rather than freezing
the interface. The desktop never initializes, upgrades, ingests, corrects or shares
knowledge. Older supported stores remain readable without an upgrade.

Queries run in background Qt workers. Generation tokens discard results that belong
to an older project, store or query. Search results retain the snapshot identity used
for the query; later capture cannot redirect a citation to different text.

Knowledge discovery retains the core's bounded history/candidate limits. Coverage
warnings are shown, not interpreted as completeness. Historical snapshots do not
reconstruct past review-journal state. Verification remains scoped to its recorded
behavior and environment. The app is not a chat client or an AI interpretation layer.

Preview screenshots under `outputs/desktop/` use a disposable, synthetic collection.
They contain no private project evidence.

## Checks

```sh
python3 -m unittest discover -s tests -p test_desktop.py -v
python3 -m unittest discover -s tests -v
```

Qt tests run offscreen and are skipped when the optional dependency is unavailable.
The adapter tests still run without Qt. Test cases cover store fingerprints,
concurrent writer contention, retained snapshot identity, sharing restrictions,
legacy/empty stores, missing evidence, stale results, navigation and compact layout.
