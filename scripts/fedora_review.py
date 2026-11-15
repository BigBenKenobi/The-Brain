"""Generate a private review from stored snapshots only; never open the source."""
from collections import Counter
import json
from pathlib import Path
import shlex
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from brain.core import Brain,read,write,validate
BASE=Path(__file__).resolve().parents[1]
b=Brain(BASE/'Project-Brain'); out=b.root/'reviews/fedora-first-ingestion'
runs=read(out/'first-runs.json'); verification=read(out/'verification.json');pre=read(out/'preflight.json')
latest={r['project_id']:r for r in runs};fedora=next(p for p,r in latest.items() if r['name']=='Fedora setup');network=next(p for p,r in latest.items() if r['name']=='NetworkSurvey')
commands=[['context',fedora,'Firefox Codex VPN','--limit','2'],['context',fedora,'panel pointer interaction','--limit','2'],['context',fedora,'keyboard kernel safeguard','--limit','1'],['context',network,'cross-device wireless throughput','--limit','2'],['evidence',fedora,'Support/private-internet-access/README.md','--start-line','1','--end-line','14'],['history',fedora],['validate',fedora],['retire-check',fedora]]
results=[]
for args in commands:
 cmd=[sys.executable,'-m','brain','--brain',str(b.root),*args]
 result=subprocess.run(cmd,cwd=BASE,text=True,capture_output=True,check=True)
 results.append(dict(command=shlex.join(cmd),result=json.loads(result.stdout)))
write(out/'query-examples.json',results)
entries={};total_metrics=Counter()
for run in runs:
 s=b.snapshot(run['project_id'],run['snapshot'])
 validate(s);total_metrics.update(run['metrics'])
 for f in s['files']:
  if f['status']!='excluded_directory':entries[str(Path(run['source'])/f['path'])]=f
statuses=Counter(f['status'] for f in entries.values());repeat=Counter()
for p in verification['projects']:repeat.update(p['repeat_metrics'])
# No sharing approval may refer to any project created for this collection.
assert not any(read(p)['project_id'] in latest for p in (b.root/'shared').glob('*.json'))
rows=['| Project | Stable private identity | Active records |','|---|---|---:|']
for p in verification['projects']:rows.append(f"| {p['name']} | `{p['project_id']}` | {p['records']} |")
text=f'''# Fedora knowledgebase ingestion review

Historical initial assessment; superseded by `final-review.md` and the knowledge-retirement standard.

Completed 1 November 2026 (Australia/Melbourne). Source:
`/home/KenobiBigBen/Setup Fedora`. Independent destination: `{b.root}`.
The source was not executed, moved, overwritten, deleted or retired.

## Result and scope

All 2,985 inventoried file entries have an explicit disposition across the initial
snapshots. Metadata inventory totals 2,914,163,485 bytes (about 2.91 GB); a
2,851,612,672-byte recovery ISO dominates that size. Ten dependency/cache subtrees
were excluded before individual inventory. Counts below do not include their
uninspected contents. Root exclusions for delegated projects are scope boundaries,
not lost files: those paths were ingested under separate private identities.

{chr(10).join(rows)}

Twelve application identities represent **partial historical reference copies**,
not the actual live application repositories. Older Archive and October 24 copies
were saved before the October 25 references. Earlier snapshots remain retained;
active context queries only search each project's latest snapshot. This avoids
silently combining historical copies with live projects or treating partial copies
as complete repositories. NetworkSurvey is separate from the Fedora host setup.

## Coverage and omissions

Across all initial historical and active snapshots, counting each source file once:

| Disposition | Files |
|---|---:|
{chr(10).join(f'| {k} | {v} |' for k,v in sorted(statuses.items()))}

822 retained files plus 452 duplicate files have retained text evidence somewhere
in the initial snapshots. There are no inaccessible files or exhausted-tree warnings.
Two oversized historical plans are explicitly unprocessed:
`Archive/odysseus-archive-plan.json` (7,793,755 bytes) and
`Archive/storage-cleanup-plan.json` (4,120,749 bytes). The 1 MiB per-file budget
intentionally omits them; they are not summarized or silently called complete.

Unsupported materials include SVG/icon assets, PNG screenshots, ISO recovery media,
compressed archives, shared libraries, DER certificates, and unrecognized
extensionless/other files. No OCR, binary interpretation or archive expansion was
performed. The 33 excluded file entries are symlinks or special files. The 26
sensitive omissions are filename/content heuristic matches, not 26 confirmed secrets;
some code/templates may be false positives. No rejected values are retained.
Private addresses, usernames and hardware identifiers can remain in accepted text.

The latest 14 snapshots contain **5,175 records**, **766 distinct retained file
entries**, 452 duplicate aliases, and **6,371,350 bytes of unique-per-project text**.
Older historical snapshots contain additional records. Deduplication is local to a
snapshot, not global storage compression. Full path-level dispositions and hashes
are in each snapshot; `first-runs.json` maps every source scope to its snapshot.

## Useful retrieved knowledge

These are interpretations of documented excerpts, not fresh verification of the
machine or source-described outcomes. `query-examples.json` contains actual CLI
outputs, record IDs, evidence hashes and line spans.

- **VPN decision:** Firefox-only VPN with Codex/ChatGPT bypass and the Automatic
  kill switch retained. Executable-path changes may require updating rules.
  Evidence: Fedora `Support/private-internet-access/README.md:1–14`, SHA-256
  `629368ceed86ec41180edf867f013966c707f85c25f26feaddb6b82f19d566d6`.
- **Panel solution:** the handoff records replacing a blocking modifier query,
  restricting preload to SFWBar, and correcting the Wi-Fi password reply type.
  Evidence: Fedora `Reports/panel-context-handoff-2026-11-01.txt:73–96`.
- **Panel limitation:** no deadlock stack was captured for the original freeze;
  long-term stability still needs ordinary use. Native integration is tied to
  the recorded SFWBar ABI/version. Evidence: the same report, lines 97–120,
  SHA-256 `f2d6c6f88e9789b984d0f3289390d538cb7a06f139036f0b3e3cf058d5cfa816`.
- **Kernel safeguards:** the October 31 report records prepared target modules,
  signature checks and retention of the previously working kernel default.
  Evidence: Fedora `Reports/kernel-preparation-result-2026-10-31.txt:1–24`.
  This is historical reported verification, not a claim about today's boot state.
- **Unresolved survey validation:** same-machine tests do not measure Ethernet
  cable/Wi-Fi throughput; cross-device Chromebook tests remain required.
  Evidence: NetworkSurvey `VALIDATION.md:36–46`, SHA-256
  `04d47b19db814615a050fa2c64b4098634547520c17b234dca2285ef2945c6be`.

Candidate reusable lessons for later human review include limiting injected native
libraries to their intended process, checking structured D-Bus reply types, preserving
a known-working boot fallback, and distinguishing local-loopback measurements from
cross-device validation. These are review candidates only; **nothing was promoted
or shared**. Existing demo sharing approvals were preserved unchanged.

## Validation, budgets and usage

18 disposable-fixture tests pass, including late-section selection, secret-shaped
JSON, Fedora formats, nested-project isolation, historical provenance, unchanged
reuse, failed-publication recovery, archive corruption and source-independent retrieval.
All initial snapshots and all 14 repeated active snapshots validated. Every project
was queried and its evidence read with source opens blocked during verification.
The CLI evidence/query examples also succeeded using the stored snapshots.

Per snapshot: 10,000 files, 1,048,576 bytes/file, 67,108,864 bytes total read, 180
seconds cooperative processing limit. The extractor selects at most 32 windows
per file, each up to 24 lines/1,800 characters. Settings are recorded per snapshot.

Initial processing across {len(runs)} snapshots: {total_metrics['bytes_read']:,} bytes read,
{total_metrics['extractions']} extractions, {total_metrics['cache_hits']} cache hits,
{total_metrics['elapsed_seconds']:.6f} seconds summed extraction-phase time.
Unchanged repeat across 14 active snapshots: {repeat['bytes_read']:,} bytes read,
**zero extractions**, {repeat['cache_hits']} cache hits, {repeat['elapsed_seconds']:.6f}
seconds summed extraction-phase time. These timings exclude validation/publication
and CLI startup and are not an end-to-end speed benchmark.

Model calls: **zero**. Provider submissions: **zero**. Token usage: not applicable.
Provider/model configuration remains available but execution is disabled because no
text-extraction adapter, standard provider credential variables or installed local
model runner were found. No remote model name or availability is claimed. Source
content was never sent by the ingestion code to a provider.

Source inventory paths, sizes, modification times and modes matched preflight after
repeat. Accepted text hashes matched between ingestions. This is not a complete
binary hash audit; filesystem reads may update access times.

## Limits and retirement readiness

Classification: **knowledge-only; not ready for full source retirement**.
The implementation preserves screened text, provenance and historical snapshots.
It does not provide a verified recoverable source archive. Existing replication
bundles were inventoried, not executed, expanded, restored or independently verified.
Binary assets, credentials, excluded environments/history, unsupported materials,
and oversized plans cannot be recovered from these evidence snapshots.

Extraction is lexical, not semantic. Late decisions/solutions/limitations now have
selection priority, but implicit lessons, cross-file relationships, contradictory
historical claims and text outside the selected windows may be missed. Whole accepted
text remains available through `evidence`. A broad query such as `recovery limitation`
returned no results; this is a known lexical retrieval gap, not proof of absence.
Configuration and JSON reports are documented claims; source code is observed text,
not observed execution. No record was upgraded to independently verified success.

## Query and maintenance commands

Run from the implementation workspace:

```bash
cd '/home/KenobiBigBen/The Brain'
export PROJECT_BRAIN_HOME='/home/KenobiBigBen/The Brain/Project-Brain'
python3 -m brain context {fedora} 'Firefox Codex VPN' --limit 2
python3 -m brain context {fedora} 'panel pointer interaction' --limit 2
python3 -m brain context {network} 'cross-device wireless throughput' --limit 2
python3 -m brain evidence {fedora} 'Support/private-internet-access/README.md' --start-line 1 --end-line 14
python3 -m brain validate {fedora}
python3 -m brain history {fedora}
python3 -m brain retire-check {fedora}
python3 scripts/ingest_fedora.py verify
```

The last command re-ingests the 14 current project scopes with the recorded explicit
budgets/exclusions and requires unchanged extraction reuse. If sources have changed,
it may publish a valid new snapshot and then report that the unchanged-source check
failed; previous snapshots remain preserved. For a deliberate refreshed collection
run, use `python3 scripts/ingest_fedora.py preflight`, then `ingest`, then `verify`.
The runner reuses known path identities; do not use a new folder location without
an explicit identity review. Review JSON outputs are replaced on another run, while
published project snapshots remain immutable historical files.

To inspect older evidence, obtain a UUID from `history` and run
`python3 -m brain evidence PROJECT_ID RELATIVE_PATH --snapshot SNAPSHOT_UUID`.
This reads the historical retained snapshot, not the original folder. To inspect
all omission paths, use `status PROJECT_ID` or the stored snapshot JSON.
`archive-evidence PROJECT_ID` can produce a verified **evidence-only** ZIP; that
export is still not a recoverable source archive. No retirement/deletion command
was run or added.
'''
(out/'review.md').write_text(text)
write(out/'coverage-by-source-file.json',entries)
print(out/'review.md')
print(json.dumps(dict(statuses=statuses,first_metrics=total_metrics,repeat_metrics=repeat),indent=2))
