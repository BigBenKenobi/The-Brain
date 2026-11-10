# Scoped verification evidence

Ordinary corrections cannot assert `independently_verified`. Keep that restriction:
an ingested test report, source file, model proposal or zero exit code does not prove
the entire summary of an item.

`scripts/run_verification.py` records an explicitly supplied command independently
of capture. For example, from a reviewed checkout:

```text
python3 scripts/run_verification.py --cwd /path/to/reviewed-checkout --output /path/to/new-receipt-directory --scope "Duplicate-cache regression suite" --environment "Local Python test environment" --timeout 60 -- python3 -m unittest discover -s tests -p test_duplicate_cache.py
```

The output parent must exist; the receipt directory must not. No shell interprets
arguments. The POSIX runner provides a deadline and combined stdout/stderr cap,
terminates its process group, and records success, failure, launch failure, timeout
or output exhaustion separately. Private output files retain exact bytes and SHA-256
hashes. The receipt records command arguments, cwd, platform, timing, exit status,
Git revision and tracked-dirty status before and after execution. It does not archive
untracked inputs, inherited environment values or external dependencies. Store the
compatible source/package and environment manifest separately for reproduction.

Run only a command the caller has explicitly selected and reviewed. This helper is
not a sandbox and does not prevent network access or filesystem changes by that
command. Source documents cannot invoke it: capture, refresh, briefings and model
validation do not call this runner. Output remains local and is never automatically
ingested, shared, or added to model context.

Every runner receipt is labelled `execution_observed_not_adopted`. Scope and
environment descriptions are caller-supplied; exit status and captured output are
observed process facts. Hashes establish byte consistency, not authorship or that
an assertion adequately tests the stated behavior.

After observing the execution and reviewing its assertions, an explicit local
reviewer can attach it to a maintained item:

```text
brain --brain STORE state-verify PROJECT_ID ITEM_ID RECEIPT_DIRECTORY --reviewer "Local observer" --rationale "What the assertions establish and their limits" --attest-observed
brain --brain STORE state-receipt PROJECT_ID EVENT_ID
brain --brain STORE state-undo PROJECT_ID EVENT_ID --rationale "Withdraw this review"
```

The attestation means the local caller observed this execution and checked the
behavioral scope and environment. It is not an authenticated remote signer or an
automatic inference of semantic correctness. Do not attest merely because a file
looks like a receipt. The receipt must record a complete successful command, an
unchanged tracked Git revision, matching output hashes, and a working directory
listed among this project's recorded source locations. Untracked inputs and external
dependencies still require explicit reviewer assessment. Failed, truncated, dirty,
foreign-location, malformed or sensitive-pattern receipts are rejected.

The immutable journal event retains the receipt and exact output bytes, so deleting
the original receipt directory does not lose verification evidence. `state-receipt`
returns those bytes as a bundle (outputs are base64) and includes revocation status.
Publication is atomic through the journal head. Undo withdraws the review while
preserving its audit history and output integrity checks.

Each `verified_behaviors` entry states its behavior, environment, source revision,
reviewer and receipt hash. Its evidence strength is `independently_verified` **only
within the explicit observer attestation and stated scope**. Item-wide strength,
work stage, currency, source records and sharing approvals remain unchanged. A
changed summary/support set, consolidation or contradictory/superseding relationship
marks the review historical and requiring reassessment. Restoring the exact subject
with undo restores applicability. A healthy unchanged observation alone does not
invalidate its evidence binding, and an applicable historical check never proves
present-day behavior.

The first review publishes journal version 3. Compatible readers accept versions
1–3; preceding readers reject version 3 rather than silently discarding verification.
Undo retains version 3 because the receipt remains in history. Compaction validates
receipt bytes even in undone events and compares replayed state. Do not activate this
code against the live store without the required compatible code/store rehearsal.
CLI briefings display scoped reviews explicitly. The currently published Tinker
consumer does not yet render these additional fields; its item-wide reported label
remains conservative. Native and owner acceptance remain separate requirements.
