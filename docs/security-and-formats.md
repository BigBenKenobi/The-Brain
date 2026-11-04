# Data handling and supported formats

Accepted UTF-8 formats: Markdown, reStructuredText, plain text, Python, JavaScript,
TypeScript, JSX/TSX, JSON, TOML, YAML, INI/CFG, Rust, Go, Java, C/C++ headers and
source, C#, shell, SQL, and extensionless Dockerfile/Makefile/LICENSE or UTF-8 shebang scripts.
Additional text formats include Fedora .conf/.config, systemd .service/.timer/.target,
.desktop/.rules/.container, panel .widget/.menu, logs/stderr, patches, XML/UI,
CSS/HTML, Swift/plist/Xcode metadata, checksums and TSV. These are preserved as
plain text without executing or semantically parsing their configuration. Files are
read as text, not executed. Other formats (including PDFs, Office documents,
images, audio, video, archives, notebooks and most game assets) are reported as
unsupported. Symlinks and special files are not followed. Git history, dependency
folders and common build/cache folders are excluded as whole subtrees; their
individual contents are not inventoried. Hidden files are not automatically safe.

Filename checks exclude environment files, keys, credentials and secret-named
files. Content checks omit an entire file if it resembles private keys, common
access tokens or password/secret assignments. No rejected content or content hash
is retained. Reports retain relative filenames and omission reasons; filenames
and source directory locations may themselves be sensitive. These heuristics can
miss secrets, personal information and proprietary content, and can omit harmless
examples. Accepted files are retained in full as evidence even though extraction
is bounded; this is intentional for provenance, not a promise of minimal retention.

The Brain is local and private by policy, not encrypted or access-controlled per
user. A newly created root has mode 0700; existing root permissions are preserved.
No network calls or model submission occur. Do not use this version as a DLP
boundary for hostile or highly sensitive repositories. Sharing approval is a human
assertion of permission and applicability; there is no organizational ACL service.

Sources should be quiescent and trusted. Reads check file identity/mtime/size and
refuse final-component symlink swaps. This does not eliminate parent-directory
replacement races in an adversarial tree or provide a whole-project transactional
snapshot. Filesystem reads can update access times; file contents are never written.
Processing budgets limit files, bytes, per-file size and elapsed time, but filesystem
calls can still block and elapsed budgets are cooperative. Large directory listings
and regex screening remain practical bottlenecks. Unchanged ingestions still read,
screen and hash source bytes to establish current content identity.

Archives verify accidental corruption with hashes, not authenticity against an
attacker able to replace both payload and manifest. Archive verification does not
extract files. Retained historical snapshots and expired approval files are not
automatically purged; sensitive material accidentally retained in an earlier run
requires explicit cleanup across history and exports. No automatic deletion exists.

Quoted JSON secret assignments are screened, alongside credential/auth/cookie/token
filenames and SSH key names. This remains a heuristic, not full personal-data
redaction: local addresses, usernames and hardware identifiers may be retained in
private evidence. Sensitive files are omitted in full, not partially redacted.

Selection scans all accepted text but only indexes at most 128 excerpts for .md/.txt/.rst and 32 for other files.
Full accepted evidence is retained, including lines outside those excerpts. A
single line longer than 1800 characters is truncated in its record, not in retained
evidence. Explicit per-run budgets are recorded; format support does not imply
full interpretation, full search coverage or source-recovery readiness.

Knowledge retirement deliberately permits loss of original artifacts after useful
information is reviewed and preserved. A complete backup/restoration test is not
required for this goal. Coverage gaps and privacy omissions remain explicit; no
percentage-of-important-knowledge guarantee is made. Source deletion and sharing
require their own authorization and are never performed by retirement checks.
