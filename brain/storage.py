"""Lossless project-scoped evidence blobs and copy-only storage migration."""
import json
import contextlib
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid
import zlib
from .core import Brain, STORE_VERSION, _internal_link_target, digest, read, validate, write

MAX_BLOB_BYTES = 128 * 1024 * 1024


def blob_path(root, project_id, sha):
    if not isinstance(project_id, str) or not isinstance(sha, str) or str(uuid.UUID(project_id)) != project_id or not re.fullmatch('[0-9a-f]{64}', sha):
        raise ValueError('Invalid evidence blob identity')
    return Path(root)/'projects'/project_id/'evidence-blobs'/(sha+'.zlib')


def decode_blob(data, sha):
    decoder = zlib.decompressobj()
    try:
        raw = decoder.decompress(data, MAX_BLOB_BYTES + 1)
    except zlib.error as exc:
        raise ValueError('Invalid compressed evidence blob') from exc
    if len(raw) > MAX_BLOB_BYTES or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError('Invalid or oversized evidence blob')
    if digest(raw) != sha:
        raise ValueError('Evidence blob hash mismatch')
    return raw.decode('utf-8')


def load_blob(root, project_id, sha):
    path = blob_path(root, project_id, sha)
    with path.open('rb') as stream:
        data = stream.read(MAX_BLOB_BYTES + 1025)
    if len(data) > MAX_BLOB_BYTES + 1024:
        raise ValueError('Compressed evidence blob exceeds budget')
    return decode_blob(data, sha)


def encode(root, snapshot):
    if snapshot.get('storage_format'):
        raise ValueError('Encode requires a materialized snapshot')
    stored = dict(snapshot)
    pending = {}
    for sha, text in snapshot['evidence'].items():
        raw = text.encode('utf-8')
        if len(raw) > MAX_BLOB_BYTES or digest(raw) != sha:
            raise ValueError('Invalid or oversized retained evidence')
        path = blob_path(root, snapshot['project_id'], sha)
        if path.exists():
            if load_blob(root, snapshot['project_id'], sha) != text:
                raise ValueError('Conflicting existing evidence blob')
        else:
            pending[sha] = zlib.compress(raw)
    stored['evidence_refs'] = sorted(snapshot['evidence'])
    stored['storage_format'] = 'evidence-blobs-1'
    del stored['evidence']
    return stored, pending


def store_blobs(root, project_id, blobs):
    for sha, data in blobs.items():
        decode_blob(data, sha)
        target = blob_path(root, project_id, sha)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if target.exists():
            load_blob(root, project_id, sha)
            continue
        fd, temporary = tempfile.mkstemp(prefix='.blob-', dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)


def materialize(root, stored):
    if stored.get('storage_format') is None:
        return stored
    if stored.get('storage_format') != 'evidence-blobs-1' or 'evidence' in stored:
        raise ValueError('Invalid evidence blob snapshot')
    refs = stored.get('evidence_refs')
    if not isinstance(refs, list) or len(refs) != len(set(refs)):
        raise ValueError('Invalid evidence blob references')
    result = {k: v for k, v in stored.items() if k not in ('storage_format', 'evidence_refs')}
    result['evidence'] = {sha: load_blob(root, stored['project_id'], sha) for sha in refs}
    return result


def _published_snapshots(brain):
    for project_id in read(brain.registry_path)['projects']:
        for stored in brain.history_snapshots(project_id):
            path = brain.root / 'projects' / project_id / 'snapshots' / (stored['id'] + '.json')
            yield path, stored


def preview(brain):
    totals = {'snapshots': 0, 'physical_snapshot_bytes': 0, 'embedded_evidence_bytes': 0}
    unique = {}
    with brain.lock(writable=False):
        for path, physical in _published_snapshots(brain):
            snapshot = brain.snapshot(physical['project_id'], physical['id'])
            validate(snapshot)
            totals['snapshots'] += 1
            totals['physical_snapshot_bytes'] += path.stat().st_size
            for sha, text in physical.get('evidence', {}).items():
                totals['embedded_evidence_bytes'] += len(text.encode())
            for sha, text in snapshot['evidence'].items():
                unique[(snapshot['project_id'], sha)] = len(zlib.compress(text.encode()))
    return {**totals, 'unique_project_blobs': len(unique), 'compressed_blob_bytes': sum(unique.values()),
        'loss_preview': {'snapshots_removed': 0, 'evidence_removed': 0, 'approvals_changed': 0,
                         'source_files_changed': 0},
        'operation': 'copy-only; no activation, deletion, semantic forgetting or source modification'}


@contextlib.contextmanager
def coherent_read(brain):
    from .refresh import RefreshWorker
    with RefreshWorker(brain).worker_lock() as available:
        if not available:
            raise ValueError('Refresh worker is active; retry compaction after it finishes')
        with brain.lock(writable=False):
            yield


def verify_derived_state(brain):
    """Validate all published state references, including undone event evidence.

    Display budgets must not hide invalid catalogue references. Unpublished orphan
    events are copied byte-for-byte but are not replayed as authoritative history.
    Canonical snapshot validation remains the separate complete snapshot pass.
    """
    from .state import ProjectState, load_catalog, KINDS
    results = {}
    for pid, project in read(brain.registry_path)['projects'].items():
        state = ProjectState(brain, pid)
        catalog = load_catalog(brain, pid)
        if catalog is None and not state.head.exists():
            continue
        refs = []
        if catalog:
            for rid, entry in catalog['entries'].items():
                if rid != entry['record_id'] or entry['kind'] not in KINDS:
                    raise ValueError('Invalid published state catalogue entry')
                refs.append(entry)
            for key in ('based_on_snapshot', 'pending_snapshot'):
                if catalog.get(key):
                    validate(brain.snapshot(pid, catalog[key]))
        for event in state.events():
            refs.extend(seed['evidence'] for seed in event.get('seeds', []))
            if event.get('evidence'):
                refs.append(event['evidence'])
        # Group references to avoid retaining every historical snapshot in memory.
        grouped = {}
        for ref in refs:
            grouped.setdefault(ref['snapshot'], []).append(ref)
        for sid, references in grouped.items():
            snapshot = brain.snapshot(pid, sid)
            validate(snapshot)
            records = {r['id']: r for r in snapshot['records']}
            for ref in references:
                record = records.get(ref['record_id'])
                if record is None:
                    raise ValueError('Published state reference has no retained record')
                if any(key in ref and ref[key] != record['evidence'][key]
                       for key in ('path', 'sha256', 'start_line', 'end_line')):
                    raise ValueError('Published state reference disagrees with canonical evidence')
        # Replaying every published journal event checks relationships and undo.
        # The bounded automatic discovery coverage is included in the comparison.
        view = state.view()
        results[pid] = {'references_checked': len(refs),
                       'view_sha256': digest(json.dumps(view, sort_keys=True, allow_nan=False).encode())}
    return results


def compact_copy(brain, destination):
    """Publish a verified independent store. Originals remain the rollback path."""
    destination = Path(destination).resolve()
    if destination == brain.root or brain.root in destination.parents or destination in brain.root.parents:
        raise ValueError('Compact destination must be separate from the source store')
    if destination.exists():
        raise ValueError('Compact destination must not exist')
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.brain-compact-', dir=destination.parent))
    try:
        with coherent_read(brain):
            runtime = brain.root / 'runtime'
            for path in brain.root.rglob('*'):
                if path.is_symlink():
                    target = _internal_link_target(path, brain.root) if path.is_relative_to(runtime) else None
                    if target is None or not target.is_relative_to(runtime):
                        raise ValueError(f'Compaction found an unexpected symlink at {path.relative_to(brain.root)}')
            original_state = verify_derived_state(brain)
            shutil.copytree(brain.root, staging, dirs_exist_ok=True, symlinks=True)
            config = read(staging/'config.json');config['schema_version'] = STORE_VERSION
            write(staging/'config.json', config)
            original_hashes, count = {}, 0
            original_bytes = sum(p.stat().st_size for p in brain.root.rglob('*') if p.is_file())
            for path, physical in _published_snapshots(brain):
                relative = path.relative_to(brain.root)
                original_hashes[str(relative)] = digest(path.read_bytes())
                snapshot = brain.snapshot(physical['project_id'], physical['id'])
                validate(snapshot)
                if physical.get('storage_format') != 'observation-1':
                    encoded, blobs = encode(staging, snapshot)
                    store_blobs(staging, snapshot['project_id'], blobs)
                    write(staging/relative, encoded)
                count += 1
            compact = Brain(staging)
            for relative in original_hashes:
                path = Path(relative)
                before = brain.snapshot(path.parts[1], path.stem)
                after = compact.snapshot(path.parts[1], path.stem)
                validate(after)
                if before != after:
                    raise ValueError('Compaction changed a canonical snapshot')
            copied_state = verify_derived_state(compact)
            if original_state != copied_state:
                raise ValueError('Compaction changed derived state behavior')
            # Sharing approvals, derived state and all other artifacts stay byte-identical.
            preserved = 0
            for path in brain.root.rglob('*'):
                if not path.is_file():
                    continue
                relative = str(path.relative_to(brain.root))
                if relative in original_hashes or relative in ('config.json', '.lock', '.refresh.lock'):
                    continue
                if path.read_bytes() != (staging/relative).read_bytes():
                    raise ValueError('Compaction changed a non-snapshot artifact')
                preserved += 1
            for archive in (staging/'archives').glob('*.zip'):
                compact.verify_archive(archive)
            compact_bytes = sum(p.stat().st_size for p in staging.rglob('*') if p.is_file())
            report = {'format': 'evidence-blobs-1', 'source': str(brain.root),
                'destination': str(destination), 'snapshots_compared_equal': count,
                'other_artifacts_byte_preserved': preserved, 'original_bytes': original_bytes,
                'compact_bytes_before_receipt': compact_bytes,
                'original_snapshot_sha256': original_hashes,
                'derived_state_projects_checked': len(original_state),
                'derived_state': original_state,
                'loss_preview': {'evidence_removed': 0, 'snapshots_removed': 0, 'approvals_changed': 0},
                'activated': False, 'source_modified': False,
                'rollback': 'Original store and its existing compatible runtime remain unchanged. Do not delete either. Do not run an older writer on this version-4 copy.',
                'limits': 'Physical representation changes only in the copy. No garbage collection or semantic pruning.'}
            write(staging/'compaction-receipt.json', report)
            # Both stores must not schedule the same intake independently.
            policy_path = staging/'refresh-policy.json'
            if policy_path.exists():
                policy = read(policy_path);policy['paused'] = True;write(policy_path, policy)
                report['copied_refresh_policy_paused'] = True
                write(staging/'compaction-receipt.json', report)
            os.rename(staging, destination)
        return report
    finally:
        if staging.exists():
            shutil.rmtree(staging)
