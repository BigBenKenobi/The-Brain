"""Project Brain: canonical JSON snapshots and conservative local retrieval."""
from __future__ import annotations
import contextlib
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import time
import uuid
import zipfile

VERSION = 1
STORE_VERSION = 4
EXTRACTOR = 'deterministic-4'
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

def match_tokens(text):
    # Retrieval-only normalisation preserves immutable legacy search indexes.
    return {token.rstrip('.') for token in tokens(text)}

def initialize(root):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not (root / 'config.json').exists():
        write(root / 'config.json', {'schema_version': STORE_VERSION, 'max_files': 10000, 'max_file_bytes': 262144, 'max_total_bytes': 16777216, 'max_seconds': 60, 'review_days': 365, 'ai': {'provider': None, 'model': None, 'enabled': False}})
    if not (root / 'registry.json').exists():
        write(root / 'registry.json', {'schema_version': VERSION, 'projects': {}})
    for name in ('projects', 'shared', 'archives'):
        (root / name).mkdir(exist_ok=True)
    return {'brain': str(root), 'schema_version': read(root / 'config.json')['schema_version']}

class CaptureDeadlineExceeded(TimeoutError):
    """The scan deadline expired before any files could be inventoried."""

    reason = 'scan_deadline'


class Brain:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.config = read(self.root / 'config.json')
        self.registry_path = self.root / 'registry.json'
        if self.config.get('schema_version') not in (1, 2, 3, STORE_VERSION):
            raise ValueError('Unsupported configuration version')
        for key in ('max_files', 'max_file_bytes', 'max_total_bytes', 'max_seconds', 'review_days'):
            if type(self.config.get(key)) is not int or self.config[key] <= 0:
                raise ValueError('Invalid positive budget: ' + key)
        if self.config.get('ai', {}).get('enabled') is not False:
            raise ValueError('AI execution is unavailable; ai.enabled must remain false')

    @contextlib.contextmanager
    def lock(self, writable=True, blocking=True):
        # Advisory flock is automatically released on process failure; no stale locks.
        import fcntl
        with (self.root / '.lock').open('a') as f:
            fcntl.flock(f, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            if writable and read(self.root / 'config.json').get('schema_version') != STORE_VERSION:
                raise ValueError('Legacy store is read-only; run upgrade-store with a backup destination first')
            yield

    def project(self, project_id):
        registry = read(self.registry_path)
        if project_id not in registry['projects']:
            raise ValueError('Unknown project ID')
        return registry['projects'][project_id]

    def upgrade_store(self, backup):
        """Guard older writers only after creating a coherent code/store backup."""
        requested = Path(backup)
        backup = requested.resolve()
        if backup == self.root or self.root in backup.parents or backup in self.root.parents:
            raise ValueError('Backup must be outside the store')
        from .refresh import RefreshWorker
        with RefreshWorker(self).worker_lock() as available:
            if not available:
                raise ValueError('Stop the active refresh worker before upgrading')
            with self.lock(writable=False):
                config = read(self.root / 'config.json')
                if config['schema_version'] == STORE_VERSION:
                    return {'changed': False, 'schema_version': STORE_VERSION}
                if requested.is_symlink() or os.path.lexists(backup):
                    raise FileExistsError(errno.EEXIST, 'Backup destination already exists', requested)
                backup.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix='.brain-upgrade-', dir=backup.parent) as temporary:
                    staging = Path(temporary)
                    count = self._prepare_upgrade_backup(staging, config['schema_version'])
                    if os.path.lexists(backup):
                        raise FileExistsError(errno.EEXIST, 'Backup destination already exists', backup)
                    staging.rename(backup)
                config['schema_version'] = STORE_VERSION
                write(self.root / 'config.json', config)
                self.config = config
                return {'changed': True, 'schema_version': STORE_VERSION, 'backup': str(backup), 'snapshots_validated': count}

    def _prepare_upgrade_backup(self, staging, schema_version):
        import shutil
        store_copy = staging / 'store'
        shutil.copytree(self.root, store_copy, symlinks=True)
        shutil.copytree(Path(__file__).parent, staging / 'code' / 'brain',
                        ignore=shutil.ignore_patterns('__pycache__'))
        hashes, links = {}, {}
        for path in self.root.rglob('*'):
            relative = str(path.relative_to(self.root))
            copied_path = store_copy / relative
            if path.is_symlink():
                links[relative] = os.readlink(path)
                if not copied_path.is_symlink() or os.readlink(copied_path) != links[relative]:
                    raise ValueError('Backup symbolic link verification failed')
                target = Path(links[relative])
                target_path = copied_path.parent / target
                prefixes = (target_path, *target_path.parents)
                message = f'Backup symbolic link must resolve inside the copied store ({relative})'
                try:
                    # Check intermediate paths too so a link cannot leave and reenter the copy.
                    if target.is_absolute() or any(
                            not prefix.resolve(strict=True).is_relative_to(store_copy)
                            for prefix in prefixes if prefix.is_relative_to(store_copy)):
                        raise ValueError(message)
                except (OSError, RuntimeError) as error:
                    raise ValueError(message) from error
            elif path.is_file() and path.name != '.lock':
                hashes[relative] = digest(path.read_bytes())
                if copied_path.is_symlink() or digest(copied_path.read_bytes()) != hashes[relative]:
                    raise ValueError('Backup copy verification failed')
        copied = Brain(store_copy)
        count = 0
        for project_id, project in read(copied.registry_path)['projects'].items():
            active = project.get('snapshot')
            if not active:
                continue
            snapshots = store_copy / 'projects' / project_id / 'snapshots'
            snapshot_ids = {path.stem for path in snapshots.glob('*.json')}
            snapshot_ids.add(active)
            for snapshot_id in sorted(snapshot_ids):
                validate(copied.snapshot(project_id, snapshot_id))
                count += 1
        write(staging / 'rollback.json', {'store': str(self.root), 'schema_version': schema_version,
            'snapshots_validated': count, 'store_file_sha256': hashes, 'store_symlink_targets': links,
            'instruction': 'Stop all Brain writers; restore store/ and use code/ together. Historical snapshots were not rewritten.'})
        return count

    def configure_source(self, source_id, *, excluded_paths=None, historical=None,
                         budgets=None, enabled=None, new_location=None):
        from .sources import configuration, location
        with self.lock():
            registry = read(self.registry_path)
            sources = registry.get('sources', {})
            if source_id not in sources:
                raise ValueError('Unknown source ID')
            source = sources[source_id]
            config = configuration(self.config, source['configuration'], excluded_paths=excluded_paths,
                historical=historical, budgets=budgets, enabled=enabled)
            if new_location is not None:
                path = str(location(self.root, new_location))
                if any(s['id'] != source_id and s['location'] == path for s in sources.values()):
                    raise ValueError('Location already registered')
                if path != source['location']:
                    config['revision'] += 1
                    source['location'] = path
                    project = registry['projects'][source['project_id']]
                    if path not in project['locations']:
                        project['locations'].append(path)
            source['configuration'] = config
            write(self.registry_path, registry)
            return source

    def refresh(self, source_id, *, automatic=False):
        registry = read(self.registry_path)
        source = registry.get('sources', {}).get(source_id)
        if source is None:
            raise ValueError('Unknown source ID')
        if automatic and not source['configuration']['enabled']:
            raise ValueError('Source is disabled for automatic capture')
        return self.ingest(source['location'], source_id=source_id, automatic=automatic)

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
        if result.get('storage_format') == 'observation-1':
            base_id = result['content_snapshot']
            if str(uuid.UUID(base_id)) != base_id or base_id == sid:
                raise ValueError('Invalid observation content reference')
            base = read(self.root / 'projects' / project_id / 'snapshots' / (base_id + '.json'))
            if base.get('storage_format') not in (None, 'evidence-blobs-1') or base['id'] != base_id or base['project_id'] != project_id:
                raise ValueError('Observation must reference a full snapshot in the same project')
            from .storage import materialize
            base = materialize(self.root, base)
            validate(base)
            for key in ('evidence', 'records', 'search_index'):
                if key in result:
                    raise ValueError('Observation contains conflicting embedded content')
                result[key] = base[key]
            del result['storage_format']
            del result['content_snapshot']
            validate(result)
        elif result.get('storage_format') == 'evidence-blobs-1':
            from .storage import materialize
            result = materialize(self.root, result)
            validate(result)
        elif result.get('storage_format'):
            raise ValueError('Unsupported snapshot storage format')
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
            relations = snapshot.setdefault('relations', [])
            for edge in source.get('relations', []):
                mapped = dict(edge)
                for key in ('older', 'replacement'):
                    mapped[key] = digest(f"{snapshot['project_id']}:{origin}:{edge[key]}".encode())
                if mapped not in relations:
                    relations.append(mapped)
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

    def ingest(self, source, project_id=None, excluded_paths=None, historical=None, **options):
        attempted_at = time.time()
        try:
            return self._ingest(source, project_id, excluded_paths, historical, **options)
        except OSError as error:
            if isinstance(error, (BlockingIOError, CaptureDeadlineExceeded)):
                # Contention stays nonblocking. The writer already recorded deadline deferrals.
                raise
            registry = read(self.registry_path)
            sid = options.get('source_id')
            path = str(Path(source).resolve())
            if sid is None:
                matches = [s['id'] for s in registry.get('sources', {}).values()
                           if s['location'] == path and (project_id is None or s['project_id'] == project_id)]
                sid = matches[0] if len(matches) == 1 else None
            if sid in registry.get('sources', {}):
                with self.lock():
                    write(self.root / 'health' / (sid + '.json'), {
                        'source_id': sid, 'attempted_at': attempted_at,
                        'finished_at': time.time(), 'state': 'failed', 'error': type(error).__name__})
            raise

    def _ingest(self, source, project_id=None, excluded_paths=None, historical=None,
               *, source_id=None, budgets=None, new_source=False, adopt_legacy=False, automatic=False,
               max_store_bytes=None, runtime_budgets=None, runtime_deadline=None):
        from .sources import BUDGETS, location, resolve
        # Resolution and publication share one writer lock. No half-saved settings.
        source = location(self.root, source)
        explicit_project = project_id is not None
        with self.lock(blocking=not automatic):
            registry = read(self.registry_path)
            projects = registry['projects']
            sources = registry.get('sources', {})
            if source_id:
                configured = sources.get(source_id)
                if not configured:
                    raise ValueError('Unknown source ID')
                if project_id and project_id != configured['project_id']:
                    raise ValueError('Source belongs to another project')
                project_id = configured['project_id']
            else:
                active = [entry for entry in sources.values() if entry['location'] == str(source)]
                if explicit_project and active:
                    active = [entry for entry in active if entry['project_id'] == project_id]
                    if not active:
                        raise ValueError('Location already registered to another project')
                if len(active) > 1:
                    raise ValueError('Ambiguous source location; supply source ID')
                if active:
                    project_id = active[0]['project_id']
                elif project_id is None:
                    registered = {entry['project_id'] for entry in sources.values()}
                    matches = [p for p, entry in projects.items()
                               if p not in registered and str(source) in entry['locations']]
                    if len(matches) > 1:
                        raise ValueError('Ambiguous project location; supply project ID')
                    project_id = matches[0] if matches else None
            if project_id is not None and project_id not in projects:
                raise ValueError('Unknown project ID')
            project_id = project_id or str(uuid.uuid4())
            old = self.snapshot(project_id) if project_id in projects and projects[project_id].get('snapshot') else {'files': [], 'records': [], 'extractor': None}
            # Preserve the callable API's existing in-memory budget overrides.
            disk_defaults = read(self.root / 'config.json')
            overrides = {k: self.config[k] for k in BUDGETS if self.config[k] != disk_defaults[k]}
            overrides.update(budgets or {})
            configured = resolve(registry, self.config, source, project_id, old,
                source_id=source_id, new_source=new_source, adopt_legacy=adopt_legacy,
                excluded_paths=excluded_paths, historical=historical, budgets=overrides or None,
                allow_relocation=explicit_project)
            if automatic and not configured['configuration']['enabled']:
                raise ValueError('Source is disabled for automatic capture')
            source_id = configured['id']
            effective = configured['configuration']
            excluded_paths = set(effective['excluded_paths'])
            historical = effective['historical']
            limits = dict(effective['budgets'])
            for key, value in (runtime_budgets or {}).items():
                if key not in limits or type(value) is not int or value < 1:
                    raise ValueError('Invalid runtime budget')
                limits[key] = min(limits[key], value)
            prefix = configured['prefix']
            old_effective = old.get('source_configurations', {}).get(source_id, {})
            previous_historical = old_effective.get('configuration', {}).get('historical', old.get('historical', False))
            attempted_at = time.time()
            oldfiles = {f['path']: f for f in old['files']}
            oldrecords = {}
            for r in old['records']:
                oldrecords.setdefault(r['evidence']['path'], []).append(r)
            start = time.monotonic()
            deadline = start + limits['max_seconds']
            if runtime_deadline is not None:
                deadline = min(deadline, runtime_deadline)
            files, records, seen, evidence = [], [], {}, {}
            metrics = {'files_seen': 0, 'bytes_read': 0, 'extractions': 0, 'cache_hits': 0, 'model_calls': 0}
            coverage = []
            def walk_error(error):
                coverage.append({'reason': 'inaccessible_directory', 'path': prefix + os.path.relpath(error.filename, source), 'source_id': source_id})

            def inventory_exhausted(directory, *, for_file=False):
                has_time = time.monotonic() < deadline
                has_file_budget = not for_file or metrics['files_seen'] < limits['max_files']
                if has_time and has_file_budget:
                    return False
                coverage.append({'reason': 'inventory_budget_exhausted', 'path': prefix + str(Path(directory).relative_to(source)), 'source_id': source_id, 'detail': 'Remaining tree not inventoried'})
                return True

            halted = False
            directories = () if inventory_exhausted(source) else os.walk(source, followlinks=False, onerror=walk_error)
            for directory, dirs, names in directories:
                if inventory_exhausted(directory):
                    break
                dirs.sort()
                names.sort(key=lambda n: (not n.lower().startswith(('readme', 'architecture', 'decision')), n))
                for d in dirs[:]:
                    p = Path(directory) / d
                    if d in EXCLUDED or p.is_symlink() or p.resolve() == self.root or str(p.relative_to(source)) in excluded_paths:
                        files.append({'path': prefix + str(p.relative_to(source)), 'source_id': source_id, 'status': 'excluded_directory', 'reason': 'explicit scoped exclusion; subtree not inspected' if str(p.relative_to(source)) in excluded_paths else 'dependency/cache/history or symlink; subtree not inspected'})
                        dirs.remove(d)
                for name in names:
                    if inventory_exhausted(directory, for_file=True):
                        halted = True
                        break
                    p = Path(directory) / name
                    local_rel = str(p.relative_to(source))
                    rel = prefix + local_rel
                    entry = {'path': rel, 'source_id': source_id}
                    files.append(entry)
                    metrics['files_seen'] += 1
                    try:
                        info = p.lstat()
                        if not stat.S_ISREG(info.st_mode):
                            entry.update(status='excluded', reason='symlink or special file')
                            continue
                        entry['size'] = info.st_size
                        if local_rel in excluded_paths:
                            entry.update(status='excluded', reason='explicit scoped exclusion')
                            continue
                        if name.startswith('.env') or p.suffix.lower() in {'.pem', '.key', '.p12', '.pfx'} or re.search(r'credential|secret|id_rsa|id_ed25519|(?:^|[._-])(?:auth|cookies?|tokens?)(?:[._-]|$)', name, re.I):
                            entry.update(status='sensitive', reason='sensitive filename; content not retained')
                            continue
                        if p.suffix.lower() not in TEXT and p.suffix and name not in {'Dockerfile', 'Makefile', 'LICENSE'}:
                            entry.update(status='unsupported', reason='format not interpreted or retained')
                            continue
                        if info.st_size > limits['max_file_bytes'] or metrics['bytes_read'] + info.st_size > limits['max_total_bytes']:
                            entry.update(status='unprocessed', reason='byte budget')
                            continue
                        # O_NOFOLLOW prevents a final-component symlink swap.
                        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                        with os.fdopen(fd, 'rb') as handle:
                            before = os.fstat(handle.fileno())
                            if not stat.S_ISREG(before.st_mode):
                                raise OSError('Not a regular file')
                            data = handle.read(int(limits['max_file_bytes']) + 1)
                            after = os.fstat(handle.fileno())
                        if len(data) > limits['max_file_bytes'] or (before.st_mtime_ns, before.st_size, before.st_ino) != (after.st_mtime_ns, after.st_size, after.st_ino) or (info.st_ino, info.st_mtime_ns) != (after.st_ino, after.st_mtime_ns):
                            entry.update(status='unprocessed', reason='source changed during read or exceeded budget')
                            continue
                        if metrics['bytes_read'] + len(data) > limits['max_total_bytes']:
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
                        entry.update(sha256=sha, status='retained', observed_at=time.time(), configuration_revision=effective['revision'])
                        evidence[sha] = text
                        if sha in seen:
                            entry.update(status='duplicate', duplicate_of=seen[sha])
                            continue
                        seen[sha] = rel
                        # Duplicate inventory entries never completed extraction.
                        # Retained empty files did, and may legitimately cache [].
                        if (old.get('extractor') == EXTRACTOR
                                and previous_historical == historical
                                and oldfiles.get(rel, {}).get('status') == 'retained'
                                and oldfiles.get(rel, {}).get('sha256') == sha):
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
            if not metrics['files_seen'] and any(w['reason'] == 'inventory_budget_exhausted' for w in coverage):
                if source_id in sources:
                    write(self.root / 'health' / (source_id + '.json'), {
                        'source_id': source_id, 'attempted_at': attempted_at, 'finished_at': time.time(),
                        'state': 'deferred', 'error': CaptureDeadlineExceeded.reason})
                raise CaptureDeadlineExceeded('Capture deferred: deadline reached before inventory')
            if not files and any(w['reason'] == 'inaccessible_directory' for w in coverage):
                raise OSError('Source inventory unavailable; previous snapshot preserved')
            sid = str(uuid.uuid4())
            snap = {'schema_version': VERSION, 'id': sid, 'project_id': project_id, 'created_at': time.time(), 'extractor': EXTRACTOR, 'historical': historical, 'excluded_paths': sorted(excluded_paths), 'files': files, 'records': records, 'coverage_warnings': coverage, 'metrics': metrics, 'ai': {'available': False, 'reason': 'No model execution adapter configured; lexically prioritized excerpts only'}, 'evidence': evidence}
            other_files = [f for f in old['files'] if f.get('source_id') not in (None, source_id) and not f.get('consolidated_from')]
            other_paths = {f['path'] for f in other_files}
            if other_paths & {f['path'] for f in files}:
                raise ValueError('Source evidence namespace collision')
            snap['files'].extend(other_files)
            snap['records'].extend(r for r in old['records'] if r['evidence']['path'] in other_paths)
            for f in other_files:
                if f.get('sha256') in old.get('evidence', {}):
                    snap['evidence'][f['sha256']] = old['evidence'][f['sha256']]
            snap['source_configurations'] = dict(old.get('source_configurations', {}))
            snap['source_configurations'][source_id] = configured
            # Per-source state is authoritative for mixed historical/current captures.
            snap['historical'] = all(c['configuration']['historical'] for c in snap['source_configurations'].values())
            partial = bool(coverage) or any(f['status'] in ('inaccessible', 'unprocessed') for f in files if f.get('source_id') == source_id)
            snap['capture'] = {'source_id': source_id, 'attempted_at': attempted_at,
                               'finished_at': time.time(), 'state': 'partial' if partial else 'complete'}
            snap['source_health'] = dict(old.get('source_health', {}))
            snap['source_health'][source_id] = dict(snap['capture'],
                last_complete_at=(old.get('source_health', {}).get(source_id, {}).get('last_complete_at') if partial else snap['capture']['finished_at']))
            snap['coverage_warnings'].extend(w for w in old.get('coverage_warnings', [])
                if w.get('source_id') not in (None, source_id) and not w.get('consolidated_from'))
            snap['relations'] = old.get('relations', [])
            snap['parent_snapshot'] = old.get('id')
            snap['processing_budgets'] = dict(limits)
            snap['search_index'] = {r['id']: sorted(tokens(r['statement'])) for r in records}
            paths = {f['path'] for f in files}
            snap['project_types'] = [kind for filename, kind in [('pyproject.toml', 'Python'), ('requirements.txt', 'Python'), ('package.json', 'JavaScript/TypeScript'), ('Cargo.toml', 'Rust'), ('go.mod', 'Go'), ('project.godot', 'Godot')] if filename in paths]
            snap['project_types'] = sorted(set(snap['project_types'])) or ['unclassified']
            self._include_supplements(snap, projects.get(project_id, {}).get('supplements', {}))
            validate(snap)
            folder = self.root / 'projects' / project_id
            # Same evidence and canonical records can reference one immutable full
            # snapshot. Inventory and observation metadata remain independent.
            unchanged = old.get('id') is not None and all(snap[k] == old.get(k) for k in ('evidence', 'search_index')) and {
                r['id']: r for r in snap['records']} == {r['id']: r for r in old['records']}
            stored = dict(snap)
            from .storage import encode, store_blobs
            pending_blobs = {}
            if unchanged:
                previous_storage = read(folder / 'snapshots' / (old['id'] + '.json'))
                base_id = previous_storage.get('content_snapshot', old['id'])
                stored.update(storage_format='observation-1', content_snapshot=base_id)
                for key in ('evidence', 'records', 'search_index'):
                    del stored[key]
            else:
                stored, pending_blobs = encode(self.root, snap)
            # Only this atomic pointer publication exposes a completed snapshot.
            project = projects.setdefault(project_id, {'id': project_id, 'name': source.name, 'locations': []})
            if str(source) not in project['locations']:
                project['locations'].append(str(source))
            project['snapshot'] = sid
            registry.setdefault('sources', {})[source_id] = configured
            from .state import load_catalog, prepare_catalog
            previous_catalog = load_catalog(self, project_id, project['state_catalog']) if project.get('state_catalog') else None
            catalog = None
            if not unchanged or previous_catalog is None:
                catalog = prepare_catalog(self, project_id, old, snap, previous_catalog)
                project['state_catalog'] = catalog['id']
            if max_store_bytes is not None:
                if type(max_store_bytes) is not int or max_store_bytes < 1:
                    raise ValueError('Invalid storage capacity')
                used = sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file())
                # Reserve temporary atomic-publication space and bounded health state.
                state_path = self.root / 'refresh-state.json'
                control_reserve = max(65536, 2 * state_path.stat().st_size + 8192) if state_path.exists() else 65536
                needed = len(json.dumps(stored, indent=2, sort_keys=True).encode()) + len(json.dumps(registry, indent=2, sort_keys=True).encode()) + control_reserve
                if catalog is not None:
                    needed += len(json.dumps(catalog, indent=2, sort_keys=True).encode())
                needed += sum(len(value) for value in pending_blobs.values())
                if used + needed > max_store_bytes:
                    raise OSError('Capture deferred: storage capacity reached')
            store_blobs(self.root, project_id, pending_blobs)
            write(folder / 'snapshots' / (sid + '.json'), stored)
            if catalog is not None:
                write(folder / 'state' / 'catalogs' / (catalog['id'] + '.json'), catalog)
            write(self.registry_path, registry)
            return {'project_id': project_id, 'source_id': source_id, 'snapshot': sid, 'observation_only': unchanged,
                    'metrics': metrics, 'records': len(snap['records']), 'capture': snap['capture'], 'report': self.retirement(project_id)}

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

    def relate(self, project_id, older, replacement, kind, rationale):
        """Explicit reviewed precedence, published atomically without changing evidence."""
        if kind not in {'corrects', 'supersedes', 'duplicates'} or not rationale.strip():
            raise ValueError('A supported relationship and rationale are required')
        if SECRET.search(rationale):
            raise ValueError('Suspected sensitive content')
        with self.lock():
            registry = read(self.registry_path)
            s = self.snapshot(project_id)
            ids = {r['id'] for r in s['records']}
            if older not in ids or replacement not in ids:
                raise ValueError('Both records must exist in the same project snapshot')
            edges = s.setdefault('relations', [])
            edge = {'older': older, 'replacement': replacement, 'kind': kind, 'rationale': rationale}
            if edge in edges:
                return {'changed': False, 'snapshot': s['id']}
            edges.append(edge)
            validate(s)
            s['parent_snapshot'] = s['id']
            s['id'] = str(uuid.uuid4())
            s['created_at'] = time.time()
            write(self.root / 'projects' / project_id / 'snapshots' / (s['id'] + '.json'), s)
            registry['projects'][project_id]['snapshot'] = s['id']
            write(self.registry_path, registry)
            return {'changed': True, 'snapshot': s['id'], 'relation': edge}

    def undo_relation(self, project_id, older, rationale):
        if not rationale.strip() or len(rationale) > 1000 or SECRET.search(rationale):
            raise ValueError('A non-sensitive undo rationale is required')
        with self.lock():
            registry = read(self.registry_path)
            snapshot = self.snapshot(project_id)
            edge = next((e for e in snapshot.get('relations', []) if e['older'] == older), None)
            if edge is None:
                raise ValueError('No active relationship for that older record')
            snapshot['relations'].remove(edge)
            snapshot['interpretation_change'] = {'action': 'undo_record_relation', 'edge': edge,
                                                  'rationale': rationale, 'at': time.time()}
            snapshot['parent_snapshot'] = snapshot['id']
            snapshot['id'] = str(uuid.uuid4())
            snapshot['created_at'] = time.time()
            validate(snapshot)
            write(self.root / 'projects' / project_id / 'snapshots' / (snapshot['id'] + '.json'), snapshot)
            registry['projects'][project_id]['snapshot'] = snapshot['id']
            write(self.registry_path, registry)
            return {'snapshot': snapshot['id'], 'undone': edge}

    def retrieve(self, query, project_id=None, technologies=(), limit=5, max_chars=6000,
                 blocked=(), history=False, explain=False, max_age_days=None):
        if limit < 1 or max_chars < 1:
            raise ValueError('Retrieval budgets must be positive')
        if max_age_days is not None and (type(max_age_days) is not int or max_age_days < 0):
            raise ValueError('Observation age must be a nonnegative integer')
        if project_id:
            self.project(project_id)
        q = match_tokens(query)
        target = set(t.lower() for t in technologies)
        found, omissions = {}, []
        projects = read(self.registry_path)['projects']
        # Sharing metadata determines which foreign projects may contribute.
        # Do not load unrelated private evidence just to discover it is unapproved.
        approvals = {}
        for path in (self.root / 'shared').glob('*.json'):
            try:
                a = read(path)
                if (not isinstance(a, dict) or a.get('schema_version') != VERSION
                        or a.get('record_id') != path.stem or a.get('project_id') not in projects
                        or a.get('permission') != 'shared'
                        or type(a.get('review_after')) not in (int, float)
                        or not (time.time() <= a['review_after'] < float('inf'))
                        or not isinstance(a.get('technologies'), list) or not a['technologies']
                        or not all(isinstance(t, str) and t for t in a['technologies'])
                        or not set(a['technologies']).issubset(target)):
                    continue
            except (OSError, ValueError, TypeError):
                # Invalid approvals confer no permission. They are never evidence.
                continue
            approvals.setdefault(a['project_id'], {})[a['record_id']] = a
        for origin in projects:
            own = origin == project_id
            if not own and origin not in approvals:
                continue
            s = self.snapshot(origin)
            validate(s)
            edges = {e['older']: e for e in s.get('relations', [])}
            replacements = {e['replacement'] for e in edges.values()}
            allowed = {}
            for r in s['records']:
                if not own:
                    a = approvals[origin].get(r['id'])
                    if a is None:
                        continue
                    if a['review_after'] < time.time() or a.get('evidence_sha256') != r['evidence']['sha256']:
                        continue
                rt = match_tokens(r['statement'])
                observation = next((f.get('observed_at') for f in s['files']
                    if f['path'] == r['evidence']['path'] and f.get('sha256') == r['evidence']['sha256']), None)
                fresh_enough = max_age_days is None or (observation is not None and time.time() - observation <= max_age_days * 86400)
                if fresh_enough and not any(match_tokens(b) & rt for b in blocked):
                    allowed[r['id']] = r
            for rid, r in allowed.items():
                overlap = q & match_tokens(r['statement'])
                if not q or len(overlap) < min(2, len(q)) or len(overlap) / len(q) < .5:
                    continue
                chain, resolved = [], rid
                if not history:
                    while resolved in edges:
                        chain.append(edges[resolved])
                        resolved = edges[resolved]['replacement']
                    if resolved not in allowed:
                        # Never fall back to an obsolete claim if its correction is unavailable.
                        omissions.append({'record_id': rid, 'reason': 'replacement unavailable, excluded, expired or unapproved'})
                        continue
                item = dict(allowed[resolved])
                observed = next((f.get('observed_at') for f in s['files']
                    if f['path'] == item['evidence']['path'] and f.get('sha256') == item['evidence']['sha256']), None)
                item['observation'] = {'observed_at': observed, 'status': 'unknown' if observed is None else 'observed',
                                       'extracted_at': item['created_at'], 'claim_review': 'not established by capture'}
                item.update(score=len(overlap) / len(q), why='same project' if own else 'explicit sharing approval',
                            precedence='Reviewed explicit relationships applied; verify changeable claims.',
                            retrieval_state='historical' if history and rid in edges else 'current candidate')
                item['reviewed_replacement'] = resolved in replacements
                if chain:
                    item['resolved_from'] = rid
                    # Do not expose private intermediate records or rationales through sharing.
                    item['resolution'] = chain if own else 'approved replacement of historical match'
                if history and own and rid in edges:
                    item['outgoing_relation'] = edges[rid]
                previous = found.get(resolved)
                if previous is None or (bool(chain), item['score']) > (bool(previous.get('resolved_from')), previous['score']):
                    found[resolved] = item
        def substantive(r):
            lines = [line.strip() for line in r['statement'].splitlines() if line.strip()]
            return any(not line.startswith(('#', '|')) and not re.match(r'^(Project root|Project|Capture date|Capture chat|Date|Task/chat|Task|Chat|Sources?|Evidence status):', line) for line in lines)
        ranked = sorted(found.values(), key=lambda r: (-bool(r.get('reviewed_replacement')), -bool(r.get('resolved_from')), -substantive(r), -r['score'], r['id']))
        result, size = [], 0
        seen = set()
        for r in ranked:
            fingerprint = ' '.join(r['statement'].split())
            cost = len(r['statement'])
            reason = ('duplicate statement' if fingerprint in seen else 'limit' if len(result) >= limit else
                      'text budget' if size + cost > max_chars else None)
            if reason:
                omissions.append({'record_id': r['id'], 'reason': reason})
            else:
                result.append(r)
                size += cost
                seen.add(fingerprint)
        if explain:
            return {'results': result, 'omitted': omissions, 'text_chars': size,
                    'budget_scope': 'statement text; provenance metadata additional',
                    'mode': 'history' if history else 'current',
                    'limits': 'Explicit reviewed links only; no semantic completeness or truth guarantee.'}
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
        briefing = build_briefing(self.project(project_id)['name'], current, previous, limit)
        health = []
        for sid, configured in read(self.registry_path).get('sources', {}).items():
            if configured['project_id'] != project_id:
                continue
            captured = current.get('source_health', {}).get(sid, {})
            attempt = captured
            health_path = self.root / 'health' / (sid + '.json')
            if health_path.exists():
                recorded = read(health_path)
                if recorded.get('attempted_at', 0) > captured.get('attempted_at', 0):
                    attempt = recorded
            effective = current.get('source_configurations', {}).get(sid, {}).get('configuration', {})
            health.append({'source_id': sid, 'state': attempt.get('state', 'unknown'),
                           'last_attempt_at': attempt.get('attempted_at'),
                           'last_complete_at': captured.get('last_complete_at'),
                           'enabled': configured['configuration']['enabled'],
                           'configured_revision': configured['configuration']['revision'],
                           'captured_revision': effective.get('revision')})
        briefing['source_health'] = health
        from .state import ProjectState, bounded_view
        briefing['maintained_state'] = bounded_view(ProjectState(self, project_id).view(), limit)
        return briefing

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
    if Path(path).suffix.lower() in {'.md', '.txt', '.rst'}:
        from .briefing import substantive_table_row
        fenced = False
        boundaries = set(starts)
        for i, line in enumerate(lines):
            if line.lstrip().startswith(('```', '~~~')):
                fenced = not fenced
            if not fenced and substantive_table_row(line):
                # A row remains an exact source excerpt with its own line span;
                # do not synthesize headings or combine non-contiguous cells.
                boundaries.update((i, i + 1))
        starts = sorted(boundaries)
    windows = []
    signals = {
        'decision': r'\b(decision|decided|chosen|because|rationale)\b',
        'solution': r'\b(solution|workaround|fixed|resolved|resolution)\b',
        'lesson': r'\b(lesson|learned|avoid|pitfall)\b',
        'limitation': r'\b(limit|limitation|unsupported|cannot|caveat|timed out)\b',
        'unresolved': r'\b(unresolved|todo|blocked|remaining|regression|known issue|pending|timeout)\b|\bOpen:',
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
        records.append({'id': digest(f'{EXTRACTOR}:{project_id}:{path}:{sha}:{start}:{end}'.encode()), 'project_id': project_id, 'category': 'project_specific', 'knowledge_kinds': kinds, 'source_role': 'historical_copy' if archived else ('implementation' if code else 'documented_claim'), 'subject': f'{path}:{start+1}', 'statement': statement, 'evidence': {'path': path, 'sha256': sha, 'start_line': start+1, 'end_line': end}, 'evidence_status': status, 'technologies': [], 'constraints': ['Environment and version compatibility require explicit review'], 'limitations': ['Source excerpt; claims and outcomes have not been independently tested', f'Lexical selection is limited to {window_limit} windows per file, 24 lines and 1800 characters per window; surrounding context may be omitted'], 'relationships': [], 'reuse_candidate': candidate, 'reuse_eligibility': 'private_pending_approval', 'freshness': 'unreviewed', 'created_at': time.time()})
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
    from .sources import validate_source
    for sid, configured in s.get('source_configurations', {}).items():
        validate_source(configured)
        if configured['id'] != sid or configured['project_id'] != s['project_id']:
            raise ValueError('Source configuration identity mismatch')
    paths = set()
    for entry in s['files']:
        if entry['path'] in paths:
            raise ValueError('Duplicate evidence path')
        paths.add(entry['path'])
        if 'observed_at' in entry:
            import math
            observed = entry['observed_at']
            if (type(observed) not in (int, float) or not math.isfinite(observed) or observed < 0
                    or entry['status'] not in ('retained', 'duplicate') or 'sha256' not in entry):
                raise ValueError('Invalid successful observation')
        if 'configuration_revision' in entry and (type(entry['configuration_revision']) is not int or entry['configuration_revision'] < 1):
            raise ValueError('Invalid source configuration revision')
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
    edges = {}
    for edge in s.get('relations', []):
        if edge.get('kind') not in {'corrects', 'supersedes', 'duplicates'} or not edge.get('rationale', '').strip():
            raise ValueError('Invalid relationship')
        for key in ('older', 'replacement'):
            if not re.fullmatch(r'[0-9a-f]{64}', edge.get(key, '')):
                raise ValueError('Invalid relationship record ID')
        if edge['older'] in edges:
            raise ValueError('Ambiguous replacement; extend the existing correction chain instead')
        edges[edge['older']] = edge['replacement']
    for start in edges:
        visited, current = set(), start
        while current in edges:
            if current in visited:
                raise ValueError('Cyclic correction relationship')
            visited.add(current)
            current = edges[current]
    missing = sorted({rid for pair in edges.items() for rid in pair if rid not in ids})
    return {'valid': True, 'records': len(ids), 'relationship_warnings':
            [{'reason': 'relationship endpoint absent; obsolete matches remain suppressed', 'record_id': rid} for rid in missing]}
