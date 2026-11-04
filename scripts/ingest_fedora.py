"""Reproducible local-only ingestion of the selected Fedora knowledge collection.

Never imports, invokes, or writes files in the source. No provider calls.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import stat
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from brain.core import Brain, EXCLUDED, SECRET, TEXT, read, validate, write

BASE = Path(__file__).resolve().parents[1]
SOURCE = Path('/home/KenobiBigBen/Setup Fedora')
ROOT = BASE / 'Project-Brain'
REVIEW = ROOT / 'reviews' / 'fedora-first-ingestion'
BUDGETS = dict(max_files=10000, max_file_bytes=8388608, max_total_bytes=67108864, max_seconds=180)


def partitions():
    groups = {}
    for date in ('24', '25'):
        base = SOURCE / f'Replication-2026-10-{date}' / 'application-reference'
        for child in sorted(base.iterdir()):
            if child.is_dir() and not child.is_symlink():
                groups.setdefault(child.name, []).append(str(child.relative_to(SOURCE)))
    # These are historical copies of the same named applications, not live projects.
    old = SOURCE / 'Archive/Development-preparation-20261024-214358/Applications'
    for child in sorted(old.iterdir()):
        if child.is_dir() and not child.is_symlink():
            groups.setdefault(child.name, []).insert(0, str(child.relative_to(SOURCE)))
    for name, rel in [('Image Swipe', 'Archive/Image-Swipe-rename-20261024-150739'),
                      ('Unsubbed', 'Archive/Unsubbed-browser-addition-20261025-075817')]:
        groups.setdefault(name, []).insert(0, rel)
    return groups


def inventory():
    files, excluded, errors = [], [], []
    for directory, dirs, names in os.walk(SOURCE, followlinks=False, onerror=lambda e: errors.append(str(e))):
        for name in dirs[:]:
            path = Path(directory) / name
            if name in EXCLUDED or path.is_symlink():
                excluded.append(str(path.relative_to(SOURCE)))
                dirs.remove(name)
        for name in sorted(names):
            path = Path(directory) / name
            try:
                info = path.lstat()
                files.append(dict(path=str(path.relative_to(SOURCE)), bytes=info.st_size,
                                  mtime_ns=info.st_mtime_ns, mode=info.st_mode,
                                  format=path.suffix.lower() or '[none]'))
            except OSError as error:
                errors.append(str(error))
    return dict(files=files, excluded_subtrees=excluded, errors=errors)


def preflight():
    inv = inventory()
    suspicious = []
    # Bounded content screening; report paths/reasons only, never rejected values.
    for entry in inv['files']:
        path = SOURCE / entry['path']
        if not stat.S_ISREG(entry['mode']):
            continue
        if entry['bytes'] > BUDGETS['max_file_bytes'] or (path.suffix and path.suffix.lower() not in TEXT):
            continue
        try:
            text = path.read_text(encoding='utf-8')
            if SECRET.search(text):
                suspicious.append(entry['path'])
        except (OSError, UnicodeError):
            pass
    result = dict(source=str(SOURCE), inventory=inv, files=len(inv['files']),
                  approximate_bytes=sum(f['bytes'] for f in inv['files']),
                  formats=dict(Counter(f['format'] for f in inv['files'])),
                  suspected_sensitive_content=suspicious, historical_application_groups=partitions(),
                  budgets=BUDGETS,
                  authority=['README.md is a navigation entry, but its latest-state claim stops at October 25.',
                             'Dated Reports, Support component documentation and panel/AUDIT.txt provide later component evidence.',
                             'Replication, Archive and Backups are historical, not assertions of live installed state.',
                             'NetworkSurvey-setup is a separate project; application references are historical partial projects.'],
                  ai={'usable_adapter':False,'provider_contacted':False,'model_calls':0,
                      'checks':'No provider keys in standard environment variables; no ollama, llama-server or vllm executable; no text extraction adapter installed.'})
    write(REVIEW / 'preflight.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'inventory','suspected_sensitive_content'}},indent=2))
    print('Suspected-sensitive content files:', len(suspicious))


def ingest():
    pre = read(REVIEW / 'preflight.json')
    groups = pre['historical_application_groups']
    exclusions = ['NetworkSurvey-setup'] + [p for paths in groups.values() for p in paths]
    b = Brain(ROOT)
    b.config.update(BUDGETS)
    runs = []
    # Explicit identities prevent old reference locations from merging unrelated projects.
    for name, paths in sorted(groups.items()):
        pid = None
        for relative in paths:
            result = b.ingest(SOURCE / relative, pid, historical=True)
            pid = result['project_id']
            runs.append(dict(name=name, source=str(SOURCE/relative), historical=True, **result))
    for name, source, excludes in [('NetworkSurvey', SOURCE/'NetworkSurvey-setup', []),
                                   ('Fedora setup', SOURCE, exclusions)]:
        result = b.ingest(source, excluded_paths=excludes)
        runs.append(dict(name=name, source=str(source), excluded_paths=excludes, historical=False, **result))
    write(REVIEW / 'first-runs.json', runs)
    print(json.dumps([dict(name=r['name'],project_id=r['project_id'],records=r['records'],metrics=r['metrics']) for r in runs],indent=2))


def verify():
    b = Brain(ROOT)
    b.config.update(BUDGETS)
    first = read(REVIEW / 'first-runs.json')
    latest = {r['project_id']:r for r in first}
    results = []
    for pid, run in latest.items():
        before = b.snapshot(pid)
        repeat = b.ingest(run['source'], pid, run.get('excluded_paths', []), run['historical'])
        current = b.snapshot(pid)
        if repeat['metrics']['extractions'] != 0:
            raise RuntimeError('Unexpected extraction on unchanged repeat: '+run['name'])
        if before['records'] != current['records'] or before['evidence'] != current['evidence']:
            raise RuntimeError('Unchanged content or identity differs')
        # Block source opens while reading stored evidence, retrieval and reports.
        original_open = os.open
        original_path_open = Path.open
        def guarded_open(path, *args, **kwargs):
            if str(path).startswith(str(SOURCE)):
                raise AssertionError('Source read during retained-evidence verification')
            return original_open(path, *args, **kwargs)
        def guarded_path_open(path, *args, **kwargs):
            if str(path).startswith(str(SOURCE)):
                raise AssertionError('Source read during retained-evidence verification')
            return original_path_open(path, *args, **kwargs)
        with patch('os.open', guarded_open), patch.object(Path, 'open', guarded_path_open):
            validation = validate(current)
            sample = next((r for r in current['records']), None)
            evidence = b.retained_evidence(pid, sample['evidence']['path'], sample['evidence']['start_line'], sample['evidence']['end_line']) if sample else None
            b.retrieve('solution decision',pid)
            retirement = b.retirement(pid)
        results.append(dict(name=run['name'],project_id=pid,first_snapshot=before['id'],repeat_snapshot=current['id'],
                            validation=validation, repeat_metrics=repeat['metrics'],source_reads_blocked=True,
                            statuses=dict(Counter(f['status'] for f in current['files'])),
                            retained_bytes=sum(len(t.encode()) for t in current['evidence'].values()),
                            records=len(current['records']), retirement=retirement))
    old = read(REVIEW/'preflight.json')['inventory']
    after = inventory()
    unchanged = old == after
    if not unchanged:
        raise RuntimeError('Source inventory metadata changed; inspect before claiming immutability')
    write(REVIEW/'verification.json',dict(projects=results,source_inventory_metadata_unchanged=unchanged,
                                         source_immutability_limit='Compared paths, sizes, mtimes and modes; not a full binary hash audit. Retained text hashes matched across runs.'))
    print(json.dumps([{k:v for k,v in r.items() if k!='retirement'} for r in results],indent=2))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['preflight','ingest','verify'])
    args=parser.parse_args()
    {'preflight':preflight,'ingest':ingest,'verify':verify}[args.action]()
