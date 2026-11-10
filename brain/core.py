"""Project Brain: canonical JSON snapshots and conservative local retrieval."""
from __future__ import annotations
import contextlib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time
import uuid
import zipfile

VERSION = 1
EXTRACTOR = 'deterministic-3'
EXCLUDED = {'.git', 'node_modules', '__pycache__', '.venv', 'venv', 'dist', 'build', '.cache', '.pytest_cache', 'target'}
TEXT = {'.md', '.rst', '.txt', '.py', '.js', '.ts', '.tsx', '.jsx', '.json', '.toml', '.yaml', '.yml', '.ini', '.cfg', '.rs', '.go', '.java', '.c', '.h', '.cpp', '.cs', '.sh', '.sql', '.conf', '.config', '.service', '.timer', '.target', '.desktop', '.rules', '.container', '.widget', '.menu', '.theme', '.dirs', '.list', '.log', '.stderr', '.patch', '.xml', '.ui', '.css', '.html', '.swift', '.plist', '.xcprivacy', '.pbxproj', '.xcscheme', '.sha256', '.tsv'}
SECRET = re.compile(r'-----BEGIN .*PRIVATE KEY|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b|\b(?:sk-|ghp_)[A-Za-z0-9_-]{16,}|(?:password|secret|api[_-]?key|access[_-]?token)[\"\']?\s*[=:]\s*[\"\']?[^\s\"\']{4,}', re.I)
STOP = set('the and for with from this that into using a an to of in is on or as be by it'.split())

def digest(data):
    return hashlib.sha256(data).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with tmp.open('w') as f:
            json.dump(value, f, indent=2, sort_keys=True)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)

def tokens(text):
    return set(re.findall(r'[a-z0-9][a-z0-9+#.-]*', text.lower())) - STOP

def initialize(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not (root / 'config.json').exists():
        write(root / 'config.json', {'schema_version': VERSION, 'max_files': 10000, 'max_file_bytes': 262144, 'max_total_bytes': 16777216, 'max_seconds': 60, 'review_days': 365, 'ai': {'provider': None, 'model': None, 'enabled': False}})
    if not (root / 'registry.json').exists():
        write(root / 'registry.json', {'schema_version': VERSION, 'projects': {}})
    for name in ('projects', 'shared', 'archives'):
        (root / name).mkdir(exist_ok=True)
    return {'brain': str(root), 'schema_version': VERSION}

class Brain:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.config = read(self.root / 'config.json')
        self.registry_path = self.root / 'registry.json'
        if self.config.get('schema_version') != VERSION:
            raise ValueError('Unsupported configuration version')
        for key in ('max_files', 'max_file_bytes', 'max_total_bytes', 'max_seconds', 'review_days'):
            if type(self.config.get(key)) is not int or self.config[key] <= 0:
                raise ValueError('Invalid positive budget: ' + key)
        if self.config.get('ai', {}).get('enabled') is not False:
            raise ValueError('AI execution is unavailable; ai.enabled must remain false')

    @contextlib.contextmanager
    def lock(self):
        # Advisory flock is automatically released on process failure; no stale locks.
        import fcntl
        with (self.root / '.lock').open('a') as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            yield

    def project(self, project_id):
        registry = read(self.registry_path)
        if project_id not in registry['projects']:
            raise ValueError('Unknown project ID')
        return registry['projects'][project_id]

    def snapshot(self, project_id, snapshot_id=None):
        project = self.project(project_id)
        if not project.get('snapshot'):
            raise ValueError('Project has no published ingestion')
        sid = snapshot_id or project['snapshot']
        if str(uuid.UUID(sid)) != sid:
            raise ValueError('Invalid snapshot identity')
        result = read(self.root / 'projects' / project_id / 'snapshots' / (sid + '.json'))
        if result['project_id'] != project_id or result['id'] != sid:
            raise ValueError('Snapshot identity mismatch')
        return result

    def _include_supplements(self, snapshot, supplements):
        """Import pinned retained snapshots without reopening their source folders."""
        for origin, sid in sorted(supplements.items()):
            source = self.snapshot(origin, sid)
            validate(source)
            # Refresh this namespace on reconsolidation; preserve primary records.
            prefix = f'supplements/{origin}/'
            snapshot['files'] = [f for f in snapshot['files'] if f.get('consolidated_from', {}).get('project_id') != origin]
            snapshot['records'] = [r for r in snapshot['records'] if r.get('consolidated_from', {}).get('project_id') != origin]
            existing_paths = {f['path'] for f in snapshot['files']}
            if any(prefix + f['path'] in existing_paths for f in source['files']):
                raise ValueError('Supplement namespace conflicts with primary source paths')
            snapshot['coverage_warnings'] = [w for w in snapshot['coverage_warnings'] if w.get('consolidated_from') != origin]
            snapshot['coverage_warnings'].extend(dict(w, consolidated_from=origin) for w in source['coverage_warnings'])
            for entry in source['files']:
                entry = dict(entry)
                original_path = entry['path']
                entry['path'] = prefix + original_path
                if 'duplicate_of' in entry:
                    entry['duplicate_of'] = prefix + entry['duplicate_of']
                entry['consolidated_from'] = {'project_id': origin, 'snapshot': sid, 'path': original_path}
                snapshot['files'].append(entry)
            snapshot['evidence'].update(source['evidence'])
            for original in source['records']:
                record = dict(original)
                record['id'] = digest(f"{snapshot['project_id']}:{origin}:{original['id']}".encode())
                record['project_id'] = snapshot['project_id']
                record['evidence'] = dict(original['evidence'], path=prefix + original['evidence']['path'])
                record['subject'] = prefix + original['subject']
                record['consolidated_from'] = {'project_id': origin, 'snapshot': sid,
                                                'record_id': original['id'], 'path': original['evidence']['path']}
                snapshot['records'].append(record)
        referenced = {f['sha256'] for f in snapshot['files'] if 'sha256' in f}
        snapshot['evidence'] = {sha: text for sha, text in snapshot['evidence'].items() if sha in referenced}
        snapshot['consolidation'] = [{'project_id': p, 'snapshot': sid} for p, sid in sorted(supplements.items())]
        snapshot['search_index'] = {r['id']: sorted(tokens(r['statement'])) for r in snapshot['records']}
        snapshot['metrics']['consolidated_records'] = sum('consolidated_from' in r for r in snapshot['records'])
        return snapshot

    def consolidate(self, project_id, supplement_id):
        """Publish a new primary snapshot with a pinned private supplement."""
        if project_id == supplement_id:
            raise ValueError('Cannot consolidate a project into itself')
        with self.lock():
            registry = read(self.registry_path)
            target = self.snapshot(project_id)
            source = self.snapshot(supplement_id)
            validate(target)
            validate(source)
            if source.get('consolidation'):
                raise ValueError('Consolidate direct sources only; nested consolidation is unsupported')
            project = registry['projects'][project_id]
            supplements = dict(project.get('supplements', {}))
            if supplements.get(supplement_id) == source['id']:
                return {'project_id': project_id, 'snapshot': target['id'], 'changed': False}
            supplements[supplement_id] = source['id']
            target['parent_snapshot'] = target['id']
            target['id'] = str(uuid.uuid4())
            target['created_at'] = time.time()
            self._include_supplements(target, supplements)
            validate(target)
            write(self.root / 'projects' / project_id / 'snapshots' / (target['id'] + '.json'), target)
            project['supplements'] = supplements
            project['snapshot'] = target['id']
            write(self.registry_path, registry)
            return {'project_id': project_id, 'snapshot': target['id'], 'changed': True,
                    'records': len(target['records']), 'consolidation': target['consolidation']}

    def ingest(self, source, project_id=None, excluded_paths=(), historical=False):
        source = Path(source).resolve(strict=True)
        if not source.is_dir():
            raise ValueError('Source must be a directory')
        if source == self.root or self.root in source.parents or source in self.root.parents:
            raise ValueError('Brain and source directories must not overlap')
        excluded_paths = {str(Path(p)) for p in excluded_paths}
        if any(Path(p).is_absolute() or '..' in Path(p).parts or p == '.' for p in excluded_paths):
            raise ValueError('Exclusions must be relative subpaths')
        with self.lock():
            registry = read(self.registry_path)
            projects = registry['projects']
            if project_id:
                if project_id not in projects:
                    raise ValueError('Unknown project ID')
            else:
                project_id = next((p for p, v in projects.items() if str(source) in v['locations']), None)
            project_id = project_id or str(uuid.uuid4())
            old = self.snapshot(project_id) if project_id in projects and projects[project_id].get('snapshot') else {'files': [], 'records': [], 'extractor': None}
            oldfiles = {f['path']: f for f in old['files']}
            oldrecords = {}
            for r in old['records']:
                oldrecords.setdefault(r['evidence']['path'], []).append(r)
            start = time.monotonic()
            files, records, seen, evidence = [], [], {}, {}
            metrics = {'files_seen': 0, 'bytes_read': 0, 'extractions': 0, 'cache_hits': 0, 'model_calls': 0}
            coverage = []
            def walk_error(error):
                coverage.append({'reason': 'inaccessible_directory', 'path': os.path.relpath(error.filename, source)})
            halted = False
            for directory, dirs, names in os.walk(source, followlinks=False, onerror=walk_error):
                dirs.sort()
                names.sort(key=lambda n: (not n.lower().startswith(('readme', 'architecture', 'decision')), n))
                for d in dirs[:]:
                    p = Path(directory) / d
                    if d in EXCLUDED or p.is_symlink() or p.resolve() == self.root or str(p.relative_to(source)) in excluded_paths:
                        files.append({'path': str(p.relative_to(source)), 'status': 'excluded_directory', 'reason': 'explicit scoped exclusion; subtree not inspected' if str(p.relative_to(source)) in excluded_paths else 'dependency/cache/history or symlink; subtree not inspected'})
                        dirs.remove(d)
                for name in names:
                    if metrics['files_seen'] >= self.config['max_files'] or time.monotonic() - start > self.config['max_seconds']:
                        coverage.append({'reason': 'inventory_budget_exhausted', 'path': str(Path(directory).relative_to(source)), 'detail': 'Remaining tree not inventoried'})
                        halted = True
                        break
                    p = Path(directory) / name
                    rel = str(p.relative_to(source))
                    entry = {'path': rel}
                    files.append(entry)
                    metrics['files_seen'] += 1
                    try:
                        info = p.lstat()
                        if not stat.S_ISREG(info.st_mode):
                            entry.update(status='excluded', reason='symlink or special file')
                            continue
                        entry['size'] = info.st_size
                        if rel in excluded_paths:
                            entry.update(status='excluded', reason='explicit scoped exclusion')
                            continue
                        if name.startswith('.env') or p.suffix.lower() in {'.pem', '.key', '.p12', '.pfx'} or re.search(r'credential|secret|id_rsa|id_ed25519|(?:^|[._-])(?:auth|cookies?|tokens?)(?:[._-]|$)', name, re.I):
                            entry.update(status='sensitive', reason='sensitive filename; content not retained')
                            continue
                        if p.suffix.lower() not in TEXT and p.suffix and name not in {'Dockerfile', 'Makefile', 'LICENSE'}:
                            entry.update(status='unsupported', reason='format not interpreted or retained')
                            continue
                        if info.st_size > self.config['max_file_bytes'] or metrics['bytes_read'] + info.st_size > self.config['max_total_bytes']:
                            entry.update(status='unprocessed', reason='byte budget')
                            continue
                        # O_NOFOLLOW prevents a final-component symlink swap.
                        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                        with os.fdopen(fd, 'rb') as handle:
                            before = os.fstat(handle.fileno())
                            if not stat.S_ISREG(before.st_mode):
                                raise OSError('Not a regular file')
                            data = handle.read(int(self.config['max_file_bytes']) + 1)
                            after = os.fstat(handle.fileno())
                        if len(data) > self.config['max_file_bytes'] or (before.st_mtime_ns, before.st_size, before.st_ino) != (after.st_mtime_ns, after.st_size, after.st_ino) or (info.st_ino, info.st_mtime_ns) != (after.st_ino, after.st_mtime_ns):
                            entry.update(status='unprocessed', reason='source changed during read or exceeded budget')
                            continue
                        if metrics['bytes_read'] + len(data) > self.config['max_total_bytes']:
                            entry.update(status='unprocessed', reason='total byte budget')
                            continue
                        metrics['bytes_read'] += len(data)
                        text = data.decode('utf-8')
                        if '\x00' in text:
                            raise UnicodeError('binary text')
                        if SECRET.search(text):
                            entry.update(status='sensitive', reason='suspected secret; entire file omitted')
                            continue
                        if not p.suffix and name not in {'Dockerfile', 'Makefile', 'LICENSE'} and not text.startswith('#!'):
                            entry.update(status='unsupported', reason='extensionless file without recognized text role or shebang')
                            continue
                        sha = digest(data)
                        entry.update(sha256=sha, status='retained')
                        evidence[sha] = text
                        if sha in seen:
                            entry.update(status='duplicate', duplicate_of=seen[sha])
                            continue
                        seen[sha] = rel
                        # Duplicate inventory entries have no completed extraction to reuse.
                        if old.get('extractor') == EXTRACTOR and old.get('historical', False) == historical and oldfiles.get(rel, {}).get('status') == 'retained' and oldfiles.get(rel, {}).get('sha256') == sha:
                            extracted = oldrecords.get(rel, [])
                            metrics['cache_hits'] += 1
                        else:
                            extracted = extract(project_id, rel, text, sha, historical)
                            metrics['extractions'] += 1
                        records.extend(extracted)
                    except UnicodeError:
                        entry.update(status='unsupported', reason='not UTF-8 text')
                    except OSError as error:
                        entry.update(status='inaccessible', reason=type(error).__name__)
                if halted:
                    break
            metrics['elapsed_seconds'] = round(time.monotonic() - start, 6)
            sid = str(uuid.uuid4())
            snap = {'schema_version': VERSION, 'id': sid, 'project_id': project_id, 'created_at': time.time(), 'extractor': EXTRACTOR, 'historical': historical, 'excluded_paths': sorted(excluded_paths), 'files': files, 'records': records, 'coverage_warnings': coverage, 'metrics': metrics, 'ai': {'available': False, 'reason': 'No model execution adapter configured; lexically prioritized excerpts only'}, 'evidence': evidence}
            snap['parent_snapshot'] = old.get('id')
            snap['processing_budgets'] = {k: self.config[k] for k in ('max_files', 'max_file_bytes', 'max_total_bytes', 'max_seconds')}
            snap['search_index'] = {r['id']: sorted(tokens(r['statement'])) for r in records}
            paths = {f['path'] for f in files}
            snap['project_types'] = [kind for filename, kind in [('pyproject.toml', 'Python'), ('requirements.txt', 'Python'), ('package.json', 'JavaScript/TypeScript'), ('Cargo.toml', 'Rust'), ('go.mod', 'Go'), ('project.godot', 'Godot')] if filename in paths]
            snap['project_types'] = sorted(set(snap['project_types'])) or ['unclassified']
            self._include_supplements(snap, projects.get(project_id, {}).get('supplements', {}))
            validate(snap)
            folder = self.root / 'projects' / project_id
            write(folder / 'snapshots' / (sid + '.json'), snap)
            # Only this atomic pointer publication exposes a completed snapshot.
            project = projects.setdefault(project_id, {'id': project_id, 'name': source.name, 'locations': []})
            if str(source) not in project['locations']:
                project['locations'].append(str(source))
            project['snapshot'] = sid
            write(self.registry_path, registry)
            return {'project_id': project_id, 'snapshot': sid, 'metrics': metrics, 'records': len(snap['records']), 'report': self.retirement(project_id)}

    def retained_evidence(self, project_id, path, start_line=1, end_line=None, snapshot_id=None):
        """Read only the published snapshot; never reopen the original source."""
        s = self.snapshot(project_id, snapshot_id)
        validate(s)
        entry = next((f for f in s['files'] if f['path'] == path and f['status'] in {'retained', 'duplicate'}), None)
        if entry is None:
            raise ValueError('No retained evidence for this path')
        lines = s['evidence'][entry['sha256']].splitlines()
        end_line = min(len(lines), start_line + 199) if end_line is None else end_line
        if start_line < 1 or end_line < start_line or end_line > len(lines) or end_line - start_line >= 200:
            raise ValueError('Choose a valid range of at most 200 retained lines')
        return {'project_id': project_id, 'snapshot': s['id'], 'path': path,
                'sha256': entry['sha256'], 'start_line': start_line, 'end_line': end_line,
                'text': '\n'.join(lines[start_line - 1:end_line]), 'source': 'retained_snapshot'}

    def review_retirement(self, project_id, summary, known_gaps, record_ids):
        """Record a human/agent knowledge review, never authorization to delete."""
        if not summary.strip() or not known_gaps or not record_ids:
            raise ValueError('Review summary, explicit known gaps and evidence record IDs required')
        with self.lock():
            s = self.snapshot(project_id)
            validate(s)
            records = {r['id']: r for r in s['records']}
            checks = []
            for rid in sorted(set(record_ids)):
                if rid not in records:
                    raise ValueError('Review evidence must belong to the active snapshot')
                r = records[rid]
                e = r['evidence']
                retained = self.retained_evidence(project_id, e['path'], e['start_line'], e['end_line'])
                checks.append({'record_id': rid, 'evidence': e, 'retained_text_checked': bool(retained['text'])})
            review = {'project_id': project_id, 'snapshot': s['id'], 'reviewed_at': time.time(),
                      'goal': 'preserve_useful_knowledge_before_intentional_discard',
                      'summary': summary, 'known_gaps': list(known_gaps), 'evidence_checks': checks,
                      'assessment_only': True, 'deletion_authorized': False}
            if SECRET.search(json.dumps(review)):
                raise ValueError('Suspected sensitive review content')
            write(self.root / 'projects' / project_id / 'retirement-reviews' / (s['id'] + '.json'), review)
            return self.retirement(project_id)

    def retirement(self, project_id):
        s = self.snapshot(project_id)
        validate(s)
        omitted = [f for f in s['files'] if f['status'] not in {'retained', 'duplicate'}]
        path = self.root / 'projects' / project_id / 'retirement-reviews' / (s['id'] + '.json')
        review = read(path) if path.exists() else None
        ids = {r['id'] for r in s['records']}
        reviewed = bool(review and review.get('snapshot') == s['id'] and review.get('project_id') == project_id
                        and review.get('summary') and review.get('known_gaps') and review.get('evidence_checks')
                        and all(c.get('record_id') in ids and c.get('retained_text_checked') for c in review['evidence_checks']))
        blockers = []
        if not s['records']:
            blockers.append('No knowledge records preserved')
        if s['coverage_warnings']:
            blockers.append('Inventory coverage incomplete; resolve warnings before final review')
        if not reviewed:
            blockers.append('Active snapshot requires a substantive knowledge/omission review and retained-evidence checks')
        return {'project_id': project_id, 'snapshot': s['id'], 'classification': 'knowledge-only',
                'goal': 'preserve_useful_knowledge_before_intentional_discard',
                'knowledge_retirement_ready': not blockers,
                'assessment': 'reviewed_with_known_gaps' if not blockers else 'review_required',
                'blockers': blockers, 'review': review,
                'verified_recoverable_source_archive': False,
                'source_recovery_required': False, 'deletion_authorized': False,
                'records_preserved': len(s['records']), 'evidence_blobs_retained': len(s['evidence']),
                'omitted': omitted, 'coverage_warnings': s['coverage_warnings'],
                'limitations': ['Readiness means reviewed useful knowledge survives intentional source disposal; it does not quantify a percentage of all important knowledge.',
                               'Documented outcomes remain documented claims unless independently verified.',
                               'Known omissions and bounded extraction remain visible; full source recovery is a separate optional objective.',
                               'This assessment never deletes sources or grants deletion permission.']}

    def promote(self, project_id, record_id, technologies, rationale, review_days=90):
        if not technologies or not rationale.strip() or review_days <= 0:
            raise ValueError('Explicit technologies, rationale and positive review period required')
        with self.lock():
            s = self.snapshot(project_id)
            r = next((r for r in s['records'] if r['id'] == record_id), None)
            if not r or not r['reuse_candidate']:
                raise ValueError('Record is not an eligible reusable candidate')
            if SECRET.search(json.dumps(r)) or SECRET.search(rationale):
                raise ValueError('Suspected sensitive content')
            approval = {'schema_version': VERSION, 'record_id': record_id, 'project_id': project_id, 'evidence_sha256': r['evidence']['sha256'], 'technologies': sorted(set(t.lower() for t in technologies)), 'rationale': rationale, 'approved_at': time.time(), 'review_after': time.time() + review_days * 86400, 'permission': 'shared', 'evidence_status': r['evidence_status']}
            write(self.root / 'shared' / (record_id + '.json'), approval)
            return approval

    def retrieve(self, query, project_id=None, technologies=(), limit=5, max_chars=6000, blocked=()):
        if project_id:
            self.project(project_id)
        q = tokens(query)
        if not q:
            return []
        target = set(t.lower() for t in technologies)
        found = []
        for origin in read(self.registry_path)['projects']:
            s = self.snapshot(origin)
            for r in s['records']:
                own = origin == project_id
                approval_path = self.root / 'shared' / (r['id'] + '.json')
                if not own:
                    if not approval_path.exists():
                        continue
                    a = read(approval_path)
                    if a['permission'] != 'shared' or a['review_after'] < time.time() or a['evidence_sha256'] != r['evidence']['sha256'] or not set(a['technologies']).issubset(target):
                        continue
                if time.time() - r['created_at'] > self.config['review_days'] * 86400:
                    continue
                rt = set(s.get('search_index', {}).get(r['id'], tokens(r['statement'])))
                overlap = q & rt
                if len(overlap) < min(2, len(q)) or len(overlap) / len(q) < .5 or any(tokens(b) & rt for b in blocked):
                    continue
                score = len(overlap) / len(q)
                item = dict(r)
                item.update(score=score, why=f"Task terms match: {', '.join(sorted(overlap))}; " + ('same project' if own else 'explicit sharing approval and declared technology compatibility'), precedence='Current project requirements override this historical evidence; resolve conflicts before use.')
                found.append(item)
        found.sort(key=lambda r: (-r['score'], r['id']))
        result, size = [], 0
        for r in found:
            cost = len(json.dumps(r))
            if size + cost <= max_chars and len(result) < limit:
                result.append(r)
                size += cost
        return result

    def summary(self, project_id):
        s = self.snapshot(project_id)
        lines = [f"# {self.project(project_id)['name']}", '', f"Project ID: {project_id}", '', 'Deterministic excerpts, not verified conclusions.', '']
        for r in s['records']:
            lines += [f"## {r['subject']}", r['statement'], f"Evidence: {r['evidence']['path']}:{r['evidence']['start_line']} ({r['evidence_status']})", '']
        lines += ['## Retirement readiness', 'Knowledge-only. No complete recoverable source archive exists.', json.dumps(self.retirement(project_id), indent=2)]
        return '\n'.join(lines)

    def briefing(self, project_id, limit=3):
        from .briefing import build_briefing
        current = self.snapshot(project_id)
        validate(current)
        parent = current.get('parent_snapshot')
        previous = self.snapshot(project_id, parent) if parent else None
        if previous is not None:
            validate(previous)
        return build_briefing(self.project(project_id)['name'], current, previous, limit)

    def archive(self, project_id):
        # Evidence export, explicitly never classified as a recoverable source archive.
        s = self.snapshot(project_id)
        target = self.root / 'archives' / (s['id'] + '.zip')
        payload = json.dumps(s, sort_keys=True).encode()
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('snapshot.json', payload)
            z.writestr('manifest.json', json.dumps({'snapshot.json': digest(payload)}))
        return self.verify_archive(target)

    @staticmethod
    def verify_archive(path):
        with zipfile.ZipFile(path) as z:
            if set(z.namelist()) != {'snapshot.json', 'manifest.json'}:
                raise ValueError('Unexpected archive members')
            if any(i.file_size > 128 * 1024 * 1024 for i in z.infolist()):
                raise ValueError('Archive exceeds verification budget')
            payload = z.read('snapshot.json')
            manifest = json.loads(z.read('manifest.json'))
            if manifest != {'snapshot.json': digest(payload)}:
                raise ValueError('Archive integrity mismatch')
            validate(json.loads(payload))
        return {'archive': str(path), 'integrity_verified': True, 'classification': 'knowledge-only', 'recoverable_source_archive': False}


def extract(project_id, path, text, sha, historical=False):
    """Bounded source excerpts. No inferred facts or proof of solution correctness."""
    lines = text.splitlines()
    records = []
    # Scan all sections and bounded windows before selecting excerpts. This is
    # lexical prioritization, not semantic analysis or independent verification.
    starts = sorted(set([0] + [i for i, line in enumerate(lines) if line.startswith('#')]))
    windows = []
    signals = {
        'decision': r'\b(decision|decided|chosen|because|rationale)\b',
        'solution': r'\b(solution|workaround|fixed|resolved|resolution)\b',
        'lesson': r'\b(lesson|learned|avoid|pitfall)\b',
        'limitation': r'\b(limit|limitation|unsupported|cannot|caveat)\b',
        'unresolved': r'\b(unresolved|todo|blocked|remaining|regression|known issue)\b',
    }
    for n, section_start in enumerate(starts):
        section_end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        start = section_start
        while start < section_end:
            end = start
            chars = 0
            while end < min(section_end, start + 24):
                length = len(lines[end]) + 1
                if end > start and chars + length > 1800:
                    break
                chars += length
                end += 1
            fragment = '\n'.join(lines[start:end])[:1800].strip()
            kinds = [kind for kind, pattern in signals.items() if re.search(pattern, fragment, re.I)]
            if fragment:
                windows.append((start, end, kinds))
            start = end
    # Reserve representation for each explicit knowledge kind, then rank the
    # remaining windows. Stable source order keeps summaries readable.
    selected = {}
    for kind in signals:
        for window in windows:
            if kind in window[2]:
                selected[window[0]] = window
                break
    window_limit = 128 if Path(path).suffix.lower() in {'.md', '.txt', '.rst'} else 32
    for window in sorted(windows, key=lambda w: (-len(w[2]), w[0])):
        if len(selected) >= window_limit:
            break
        selected[window[0]] = window
    for start, end, kinds in sorted(selected.values()):
        statement = '\n'.join(lines[start:end])[:1800].strip()
        if not statement:
            continue
        candidate = bool(re.search(r'\b(solution|workaround|lesson|pattern|troubleshoot|decision)\b', statement, re.I))
        archived = historical or any(part.lower() in {'archive', 'backups', 'application-reference'} or part.startswith('Replication-') for part in Path(path).parts)
        code = Path(path).suffix.lower() in {'.py', '.sh', '.c', '.h', '.cpp', '.rs', '.go', '.java', '.cs', '.js', '.ts', '.jsx', '.tsx', '.swift'} or text.startswith('#!')
        status = 'proposal' if re.search(r'\b(proposed|proposal|untested)\b', statement, re.I) or 'proposal' in path.lower() else ('observed_implementation' if code and not archived else 'historical_record')
        records.append({'id': digest(f'{project_id}:{path}:{sha}:{start}'.encode()), 'project_id': project_id, 'category': 'project_specific', 'knowledge_kinds': kinds, 'source_role': 'historical_copy' if archived else ('implementation' if code else 'documented_claim'), 'subject': f'{path}:{start+1}', 'statement': statement, 'evidence': {'path': path, 'sha256': sha, 'start_line': start+1, 'end_line': end}, 'evidence_status': status, 'technologies': [], 'constraints': ['Environment and version compatibility require explicit review'], 'limitations': ['Source excerpt; claims and outcomes have not been independently tested', f'Lexical selection is limited to {window_limit} windows per file, 24 lines and 1800 characters per window; surrounding context may be omitted'], 'relationships': [], 'reuse_candidate': candidate, 'reuse_eligibility': 'private_pending_approval', 'freshness': 'unreviewed', 'created_at': time.time()})
    return records


def validate(s):
    if s.get('schema_version') != VERSION:
        raise ValueError('Unsupported snapshot version')
    parent = s.get('parent_snapshot')
    if parent is not None:
        if str(uuid.UUID(parent)) != parent or parent == s.get('id'):
            raise ValueError('Invalid parent snapshot identity')
    for key in ('id', 'project_id', 'files', 'records', 'evidence', 'metrics', 'coverage_warnings'):
        if key not in s:
            raise ValueError('Missing snapshot field: ' + key)
    ids = set()
    for sha, text in s['evidence'].items():
        if digest(text.encode()) != sha or SECRET.search(text):
            raise ValueError('Evidence integrity or sensitivity failure')
    for r in s['records']:
        required = {'id', 'project_id', 'category', 'subject', 'statement', 'evidence', 'evidence_status', 'technologies', 'constraints', 'limitations', 'relationships', 'reuse_candidate', 'reuse_eligibility', 'freshness', 'created_at'}
        if not required.issubset(r):
            raise ValueError('Incomplete knowledge record')
        if r['category'] != 'project_specific' or r['reuse_eligibility'] != 'private_pending_approval':
            raise ValueError('Canonical records must remain private; sharing requires a separate approval')
        if r['id'] in ids or r['project_id'] != s['project_id']:
            raise ValueError('Record identity failure')
        ids.add(r['id'])
        e = r['evidence']
        if type(e['start_line']) is not int or type(e['end_line']) is not int or not 1 <= e['start_line'] <= e['end_line']:
            raise ValueError('Invalid source line range')
        if not any(f['path'] == e['path'] and f.get('sha256') == e['sha256'] and f['status'] == 'retained' for f in s['files']):
            raise ValueError('Record source absent from inventory')
        if e['sha256'] not in s['evidence'] or r['evidence_status'] not in {'proposal', 'historical_record', 'observed_implementation'}:
            raise ValueError('Invalid evidence reference/status')
        if e['end_line'] > len(s['evidence'][e['sha256']].splitlines()):
            raise ValueError('Source line range exceeds retained evidence')
        fragment = '\n'.join(s['evidence'][e['sha256']].splitlines()[e['start_line']-1:e['end_line']])[:1800].strip()
        if fragment != r['statement']:
            raise ValueError('Statement is not backed by retained evidence')
    if 'search_index' in s and s['search_index'] != {r['id']: sorted(tokens(r['statement'])) for r in s['records']}:
        raise ValueError('Search index disagrees with canonical records')
    return {'valid': True, 'records': len(ids)}

