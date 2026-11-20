"""Opt-in bounded refresh worker, suitable for a systemd user timer.

No watchers, source discovery, network calls, shell execution or evidence deletion.
"""
import contextlib
import fcntl
from pathlib import Path
import time
from .core import CaptureDeadlineExceeded, read, write

DEFAULT_POLICY = {
    'paused': True, 'interval_seconds': 900, 'retry_seconds': 60,
    'max_retry_seconds': 3600, 'max_sources_per_run': 4,
    'max_run_seconds': 30, 'max_files_per_run': 2000,
    'max_bytes_per_run': 8388608, 'max_store_bytes': 1073741824,
}


class RefreshWorker:
    def __init__(self, brain):
        self.brain = brain
        self.policy_path = brain.root / 'refresh-policy.json'
        self.state_path = brain.root / 'refresh-state.json'
        self.lock_path = brain.root / '.refresh.lock'

    def policy(self):
        policy = dict(DEFAULT_POLICY)
        if self.policy_path.exists():
            saved = read(self.policy_path)
            if set(saved) != set(policy):
                raise ValueError('Unsupported refresh policy')
            policy.update(saved)
        self.validate_policy(policy)
        return policy

    @staticmethod
    def validate_policy(policy):
        if set(policy) != set(DEFAULT_POLICY) or type(policy['paused']) is not bool:
            raise ValueError('Invalid refresh policy')
        for key in set(policy) - {'paused'}:
            if type(policy[key]) is not int or policy[key] < 1:
                raise ValueError('Invalid positive refresh budget: ' + key)
        if policy['max_store_bytes'] < 65536:
            raise ValueError('Store capacity must reserve at least 64 KiB for control state')
        if policy['retry_seconds'] > policy['max_retry_seconds']:
            raise ValueError('Retry base exceeds maximum backoff')

    def configure(self, **updates):
        if set(updates) - set(DEFAULT_POLICY):
            raise ValueError('Unknown refresh policy setting')
        with self.brain.lock():
            policy = self.policy()
            policy.update(updates)
            self.validate_policy(policy)
            write(self.policy_path, policy)
            return policy

    def state(self):
        return read(self.state_path) if self.state_path.exists() else {'sources': {}}

    @contextlib.contextmanager
    def worker_lock(self):
        with self.lock_path.open('a') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                yield False
                return
            try:
                yield True
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def status(self, now=None):
        now = time.time() if now is None else now
        policy, state = self.policy(), self.state()
        with self.worker_lock() as acquired:
            running = not acquired
        sources = []
        for sid, configured in read(self.brain.registry_path).get('sources', {}).items():
            previous = state['sources'].get(sid, {})
            status = previous.get('state', 'idle')
            captured = self.brain.snapshot(configured['project_id']).get('source_health', {}).get(sid, {})
            dates = [d for d in (previous.get('last_success_at'), captured.get('last_complete_at')) if d is not None]
            success = max(dates) if dates else None
            stale = success is None or now - success > policy['interval_seconds'] * 3
            enabled = configured['configuration']['enabled']
            if not enabled:
                status = 'disabled'
            elif policy['paused']:
                status = 'paused'
            elif running and previous.get('state') == 'running':
                status = 'running'
            elif previous.get('state') == 'running':
                status = 'failed'  # A saved marker is not evidence of a live worker.
            elif status not in ('partial', 'failed', 'deferred') and stale:
                status = 'stale'
            sources.append({'source_id': sid, 'project_id': configured['project_id'],
                **previous, 'state': status, 'stale': stale, 'enabled': enabled, 'last_success_at': success})
        return {'policy': policy, 'running': running, 'sources': sources,
                'store_bytes': sum(p.stat().st_size for p in self.brain.root.rglob('*') if p.is_file()),
                'last_run': state.get('last_run')}

    def run_once(self, now=None):
        now = time.time() if now is None else now
        with self.worker_lock() as acquired:
            if not acquired:
                return {'state': 'running', 'processed': 0, 'reason': 'another worker owns the lock'}
            policy = self.policy()
            if policy['paused']:
                return {'state': 'paused', 'processed': 0}
            state = self.state()
            # Recover interrupted operational state without modifying evidence.
            for previous in state['sources'].values():
                if previous.get('state') == 'running':
                    previous.update(state='failed')
                    self.retry(previous, now, policy, 'interrupted_previous_run')
            registry = read(self.brain.registry_path)
            candidates = [s for s in registry.get('sources', {}).values()
                          if s['configuration']['enabled']
                          and state['sources'].get(s['id'], {}).get('next_due', 0) <= now]
            candidates.sort(key=lambda s: (state['sources'].get(s['id'], {}).get('last_attempt_at', 0), s['id']))
            deadline = time.monotonic() + policy['max_run_seconds']
            remaining_bytes, remaining_files = policy['max_bytes_per_run'], policy['max_files_per_run']
            results = []
            for configured in candidates[:policy['max_sources_per_run']]:
                if self.policy()['paused']:
                    break
                if time.monotonic() >= deadline or remaining_bytes < 1 or remaining_files < 1:
                    break
                sid = configured['id']
                previous = state['sources'].setdefault(sid, {})
                previous.update(state='running', last_attempt_at=now)
                write(self.state_path, state)
                try:
                    capture = self.brain.ingest(configured['location'], source_id=sid, automatic=True,
                        max_store_bytes=policy['max_store_bytes'], runtime_deadline=deadline, runtime_budgets={
                            'max_seconds': policy['max_run_seconds'], 'max_total_bytes': remaining_bytes,
                            'max_files': remaining_files})
                    remaining_bytes -= capture['metrics']['bytes_read']
                    remaining_files -= capture['metrics']['files_seen']
                    complete = capture['capture']['state'] == 'complete'
                    previous.update(state='idle' if complete else 'partial', snapshot=capture['snapshot'],
                                    observation_only=capture['observation_only'], last_finished_at=time.time())
                    if complete:
                        previous.update(failures=0, last_success_at=time.time(), next_due=now + policy['interval_seconds'])
                        previous.pop('error', None)
                    else:
                        self.retry(previous, now, policy, 'partial_capture')
                except CaptureDeadlineExceeded as error:
                    previous.update(state='deferred', last_finished_at=time.time())
                    self.retry(previous, now, policy, error.reason)
                except (OSError, ValueError) as error:
                    previous.update(state='failed', last_finished_at=time.time())
                    reason = 'storage_capacity' if isinstance(error, OSError) and str(error).startswith('Capture deferred: storage capacity') else type(error).__name__
                    self.retry(previous, now, policy, reason)
                    # A failed publication may have consumed all allocated scan work.
                    remaining_bytes = remaining_files = 0
                results.append({'source_id': sid, **previous})
                write(self.state_path, state)
            state['last_run'] = {'attempted_at': now, 'finished_at': time.time(), 'processed': len(results)}
            write(self.state_path, state)
            outcomes = {r['state'] for r in results}
            outcome = next((status for status in ('failed', 'partial', 'deferred') if status in outcomes), 'idle')
            return {'state': 'paused' if self.policy()['paused'] else outcome, 'processed': len(results), 'results': results}

    @staticmethod
    def retry(previous, now, policy, reason):
        failures = previous.get('failures', 0) + 1
        delay = min(policy['max_retry_seconds'], policy['retry_seconds'] * 2 ** min(failures - 1, 20))
        previous.update(failures=failures, error=reason, next_due=now + delay)
