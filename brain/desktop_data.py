"""Read-only desktop queries. Qt-independent; never initializes or upgrades a store."""
from contextlib import contextmanager
import fcntl
from pathlib import Path

from .core import Brain, read, validate
from .state import ProjectState
from .briefing import build_briefing


class DesktopReader:
    def __init__(self, root):
        self.root = Path(root).resolve()

    @contextmanager
    def session(self):
        # Cooperate with capture writers without creating/changing their lock file.
        # Fresh empty stores may not have a lock yet; there are no snapshots to race.
        handle = None
        try:
            try:
                handle = (self.root / '.lock').open('rb')
            except FileNotFoundError:
                if read(self.root / 'registry.json').get('projects'):
                    raise ValueError('Store lock is missing. Open a complete Brain store.')
            if handle:
                try:
                    fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError('Brain is capturing changes. Please reload in a moment.') from None
            yield Brain(self.root)
        finally:
            if handle:
                handle.close()

    def projects(self):
        with self.session() as brain:
            return read(brain.registry_path)['projects']

    def project(self, project_id):
        with self.session() as brain:
            state = ProjectState(brain, project_id).view()
            snapshot = brain.snapshot(project_id, state['snapshot'])
            briefing = brain._build_current_briefing(project_id, snapshot, 3, state)
            registry = read(brain.registry_path)
            return {'snapshot': snapshot['id'], 'created_at': snapshot['created_at'],
                    'briefing': briefing, 'state': state,
                    'sources': [source for source in registry.get('sources', {}).values()
                                if source['project_id'] == project_id]}

    def search(self, project_id, query, technologies=(), history=False):
        with self.session() as brain:
            result = brain.retrieve(query, project_id, technologies=technologies,
                                    limit=100, max_chars=60000, history=history, explain=True)
            for item in result['results']:
                # Bind result to the snapshot used during the locked query.
                item['snapshot'] = brain.project(item['project_id'])['snapshot']
            return result

    def history(self, project_id):
        with self.session() as brain:
            rows = [{'snapshot': value['id'], 'created_at': value['created_at'], 'active': index == 0}
                    for index, value in enumerate(brain.history_snapshots(project_id))]
            return sorted(rows, key=lambda row: row['created_at'], reverse=True)

    def capture(self, project_id, snapshot_id):
        with self.session() as brain:
            snap = brain.snapshot(project_id, snapshot_id)
            validate(snap)
            parent = snap.get('parent_snapshot')
            previous = brain.snapshot(project_id, parent) if parent else None
            return {'snapshot': snapshot_id, 'created_at': snap['created_at'],
                    'briefing': build_briefing(brain.project(project_id)['name'], snap, previous),
                    'records': snap['records']}

    def record(self, project_id, snapshot_id, record_id):
        with self.session() as brain:
            snap = brain.snapshot(project_id, snapshot_id)
            validate(snap)
            record = next((r for r in snap['records'] if r['id'] == record_id), None)
            if record is None:
                raise ValueError('The cited record is unavailable in this snapshot.')
            return record

    def evidence(self, project_id, claim, start=None):
        with self.session() as brain:
            start = max(1, claim['start_line'] - 5) if start is None else start
            result = brain.retained_evidence(project_id, claim['path'], start,
                                             snapshot_id=claim['snapshot'])
            if claim.get('sha256') and result['sha256'] != claim['sha256']:
                raise ValueError('Retained evidence does not match the cited content hash.')
            snapshot = brain.snapshot(project_id, claim['snapshot'])
            result['created_at'] = snapshot['created_at']
            result['total_lines'] = len(snapshot['evidence'][result['sha256']].splitlines())
            return result

    def shared_evidence(self, project_id, snapshot_id, record_id, technologies, history=False):
        with self.session() as brain:
            return brain.shared_evidence(project_id, snapshot_id, record_id, technologies, history=history)
