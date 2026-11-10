# Surviving duplicate capture

If two paths contain the same text, Brain retains one extraction and records the
other path as a duplicate. When the extracted path is removed or excluded, the
surviving duplicate must be extracted even though its bytes have not changed.

Cache reuse now requires the previous inventory entry to be `retained`, as well as
matching hash, extractor and historical designation. A `duplicate` entry has no
completed extraction of its own. Empty retained files can still reuse a completed
empty result, avoiding unnecessary extraction on every refresh.

The repair does not change snapshot format, source files, retained historical
snapshots or sharing approvals. The surviving path receives its own record IDs and
does not inherit approval granted to the previous path.

Regression coverage checks removal, explicit exclusion, an earlier-sorting duplicate,
source/evidence preservation, approval separation and unchanged empty-file caching.
The new regressions fail on the previous code. The full suite passes on Python 3.11
and 3.14; the added GitHub workflow runs both versions on pushes and pull requests.
This fixes duplicate capture only; source configuration, briefings and model work
remain separate delivery slices.
