import json
from itertools import count
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from brain.core import Brain, initialize, read, validate, write
from brain.refresh import RefreshWorker


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'decision.md').write_text('Decision: SQLite locking uses bounded retry.\n')
        initialize(self.root / 'store')
        self.b = Brain(self.root / 'store')
        first = self.b.ingest(self.source)
        self.pid, self.sid = first['project_id'], first['source_id']
        self.worker = RefreshWorker(self.b)

    def snapshots(self):
        return list((self.b.root / 'projects' / self.pid / 'snapshots').glob('*.json'))

    def enable(self):
        self.b.configure_source(self.sid, enabled=True)
        self.worker.configure(paused=False, interval_seconds=900, retry_seconds=10, max_retry_seconds=20)

    def test_unchanged_observations_share_content_without_losing_chronology(self):
        (self.source / 'large.md').write_text('# Decision\n' + 'Observed source material and constraints.\n' * 3000)
        self.b.ingest(self.source)
        first = self.b.snapshot(self.pid)
        first_path = self.b.root / 'projects' / self.pid / 'snapshots' / (first['id'] + '.json')
        before = first_path.read_bytes()
        r = next(r for r in first['records'] if r['evidence']['path'] == 'decision.md')
        self.b.promote(self.pid, r['id'], ['sqlite'], 'Reviewed original evidence')
        approval_path = self.b.root / 'shared' / (r['id'] + '.json')
        approval = approval_path.read_bytes()
        previous = first['id']
        for _ in range(4):
            result = self.b.refresh(self.sid)
            self.assertTrue(result['observation_only'])
            raw = read(first_path.with_name(result['snapshot'] + '.json'))
            self.assertEqual(raw['content_snapshot'], first['id'])
            self.assertNotIn('evidence', raw)
            self.assertNotIn('records', raw)
            self.assertEqual(raw['parent_snapshot'], previous)
            self.assertLess(len(json.dumps(raw)), len(before) // 5)
            current = self.b.snapshot(self.pid)
            self.assertTrue(validate(current)['valid'])
            self.assertEqual(current['evidence'], first['evidence'])
            self.assertGreaterEqual(current['files'][0]['observed_at'], first['files'][0]['observed_at'])
            previous = result['snapshot']
        self.assertEqual(first_path.read_bytes(), before)
        self.assertEqual(approval_path.read_bytes(), approval)
        self.assertTrue(self.b.retrieve('SQLite locking', self.pid))
        self.assertTrue(self.b.archive(self.pid)['integrity_verified'])

    def test_corrupt_missing_or_chained_content_reference_is_rejected(self):
        result = self.b.refresh(self.sid)
        path = self.b.root / 'projects' / self.pid / 'snapshots' / (result['snapshot'] + '.json')
        raw = read(path)
        raw['content_snapshot'] = result['snapshot']
        write(path, raw)
        with self.assertRaisesRegex(ValueError, 'Invalid observation'):
            self.b.snapshot(self.pid)

    def test_changed_content_materialises_and_failed_publication_preserves_pointer(self):
        first = self.b.snapshot(self.pid)
        real = write
        def fail(path, value):
            if Path(path) == self.b.registry_path:
                raise OSError('simulated publication failure')
            real(path, value)
        with patch('brain.core.write', side_effect=fail):
            with self.assertRaises(OSError):
                self.b.refresh(self.sid)
        self.assertEqual(self.b.snapshot(self.pid), first)
        (self.source / 'decision.md').write_text('Decision: SQLite locking needs a retry deadline.\n')
        result = self.b.refresh(self.sid)
        self.assertFalse(result['observation_only'])
        self.assertEqual(self.b.snapshot(self.pid, first['id']), first)

    def test_pause_opt_in_and_coalescing_repeated_saves(self):
        self.assertEqual(self.worker.run_once()['state'], 'paused')
        self.worker.configure(paused=False)
        self.assertEqual(self.worker.run_once()['processed'], 0)
        self.enable()
        now = time.time()
        first = self.worker.run_once(now=now)
        self.assertEqual(first['processed'], 1)
        count = len(self.snapshots())
        (self.source / 'decision.md').write_text('Decision: newer SQLite locking deadline.\n')
        self.assertEqual(self.worker.run_once(now=now + 1)['processed'], 0)
        self.assertEqual(len(self.snapshots()), count)
        self.worker.configure(paused=True)
        self.assertEqual(self.worker.run_once(now=now + 1000)['state'], 'paused')
        self.worker.configure(paused=False)
        self.assertEqual(self.worker.run_once(now=now + 1000)['processed'], 1)
        self.assertTrue(self.b.retrieve('newer SQLite', self.pid))

    def test_missing_source_bounded_retry_and_restart_recovery(self):
        self.enable()
        moved = self.root / 'offline'
        self.source.rename(moved)
        old = self.b.snapshot(self.pid)
        now = time.time()
        first = self.worker.run_once(now=now)['results'][0]
        self.assertEqual(first['state'], 'failed')
        self.assertEqual(first['next_due'], now + 10)
        self.assertEqual(self.worker.run_once(now=now + 5)['processed'], 0)
        # A new process instance reuses persisted backoff and last valid evidence.
        worker = RefreshWorker(Brain(self.b.root))
        second = worker.run_once(now=now + 10)['results'][0]
        self.assertEqual(second['next_due'], now + 30)
        third = worker.run_once(now=now + 30)['results'][0]
        self.assertEqual(third['next_due'], now + 50)
        self.assertEqual(self.b.snapshot(self.pid), old)
        moved.rename(self.source)
        result = worker.run_once(now=now + 50)['results'][0]
        self.assertEqual(result['state'], 'idle')
        self.assertEqual(result['failures'], 0)

    def test_no_overlapping_workers_and_saved_running_is_not_a_live_process(self):
        self.enable()
        with self.worker.worker_lock() as acquired:
            self.assertTrue(acquired)
            other = RefreshWorker(Brain(self.b.root))
            self.assertTrue(other.status()['running'])
            self.assertEqual(other.run_once()['processed'], 0)
        state = {'sources': {self.sid: {'state': 'running', 'last_attempt_at': 0}}}
        write(self.worker.state_path, state)
        status = self.worker.status()
        self.assertFalse(status['running'])
        self.assertEqual(status['sources'][0]['state'], 'failed')
        now = time.time()
        self.assertEqual(self.worker.run_once(now=now)['processed'], 0)
        self.assertEqual(self.worker.run_once(now=now + 10)['processed'], 1)

    def test_background_capture_defers_when_manual_writer_holds_lock(self):
        self.enable()
        old = self.b.snapshot(self.pid)
        with self.b.lock():
            result = self.worker.run_once()
        self.assertEqual(result['results'][0]['error'], 'BlockingIOError')
        self.assertEqual(self.b.snapshot(self.pid), old)

    def test_storage_capacity_defers_capture_preserving_readable_knowledge(self):
        self.enable()
        old = self.b.snapshot(self.pid)
        used = sum(p.stat().st_size for p in self.b.root.rglob('*') if p.is_file())
        self.worker.configure(max_store_bytes=used + 65536 + 100)
        (self.source / 'large.md').write_text('# Decision\n' + 'SQLite locking needs bounded retry.\n' * 3000)
        result = self.worker.run_once()['results'][0]
        self.assertEqual(result['error'], 'storage_capacity')
        self.assertEqual(self.b.snapshot(self.pid), old)
        self.assertTrue(self.b.retrieve('SQLite locking', self.pid))
        self.assertEqual(len(self.snapshots()), 1)

    def test_runtime_budgets_are_bounded_without_rewriting_source_settings(self):
        for i in range(3):
            (self.source / f'{i}.md').write_text('Idea: bounded batch extraction.\n')
        self.enable()
        saved = read(self.b.registry_path)['sources'][self.sid]['configuration']
        self.worker.configure(max_files_per_run=1)
        result = self.worker.run_once()['results'][0]
        self.assertEqual(result['state'], 'partial')
        snap = self.b.snapshot(self.pid)
        self.assertEqual(snap['metrics']['files_seen'], 1)
        self.assertEqual(snap['processing_budgets']['max_files'], 1)
        self.assertEqual(read(self.b.registry_path)['sources'][self.sid]['configuration'], saved)
        self.assertTrue(snap['coverage_warnings'])

    def test_exact_file_budget_with_empty_subdirectory_completes(self):
        self.enable()
        self.worker.configure(max_files_per_run=1)
        subdirectory = self.source / 'notes'
        subdirectory.mkdir()
        now = time.time()

        result = self.worker.run_once(now=now)['results'][0]
        self.assertEqual(result['state'], 'idle')
        self.assertEqual(result['next_due'], now + 900)
        snapshot = self.b.snapshot(self.pid)
        self.assertEqual(snapshot['metrics']['files_seen'], 1)
        self.assertEqual(snapshot['coverage_warnings'], [])

        (subdirectory / 'extra.md').write_text('Idea: review during a later pass.\n')
        result = self.worker.run_once(now=result['next_due'])['results'][0]
        self.assertEqual(result['state'], 'partial')
        snapshot = self.b.snapshot(self.pid)
        self.assertEqual(snapshot['metrics']['files_seen'], 1)
        self.assertEqual(snapshot['coverage_warnings'][0]['path'], 'notes')

    def test_one_second_run_budget_can_start_due_work(self):
        self.enable()
        self.worker.configure(max_run_seconds=1)
        ticks = count()
        with patch('brain.refresh.time.monotonic', side_effect=lambda: next(ticks) / 100):
            result = self.worker.run_once()
        self.assertEqual(result['processed'], 1)
        self.assertEqual(result['results'][0]['state'], 'idle')

    def test_expired_deadline_before_scan_defers_and_preserves_searchable_evidence(self):
        self.enable()
        self.worker.configure(max_run_seconds=1)
        previous = self.b.snapshot(self.pid)
        now = time.time()
        elapsed = 0
        snapshot = self.b.snapshot

        def slow_snapshot(*args, **kwargs):
            nonlocal elapsed
            elapsed = 2
            return snapshot(*args, **kwargs)

        with patch('brain.refresh.time.monotonic', side_effect=lambda: elapsed):
            with patch.object(self.b, 'snapshot', side_effect=slow_snapshot):
                result = self.worker.run_once(now=now)
        self.assertEqual(result['state'], 'deferred')
        self.assertEqual(result['results'][0]['state'], 'deferred')
        self.assertEqual(result['results'][0]['error'], 'scan_deadline')
        self.assertEqual(result['results'][0]['next_due'], now + 10)
        self.assertEqual(self.worker.status()['sources'][0]['state'], 'deferred')
        self.assertEqual(self.b.briefing(self.pid)['source_health'][0]['state'], 'deferred')
        self.assertEqual(self.b.snapshot(self.pid), previous)
        self.assertEqual(len(self.snapshots()), 1)
        matches = self.b.retrieve('SQLite locking', self.pid)
        self.assertTrue(matches)
        self.assertIn('bounded retry', matches[0]['statement'])
        self.assertEqual(self.worker.run_once(now=now + 9)['processed'], 0)
        self.assertEqual(self.worker.run_once(now=now + 10)['results'][0]['state'], 'idle')
        self.assertEqual(self.b.briefing(self.pid)['source_health'][0]['state'], 'complete')

    def test_partial_write_has_no_successful_observation_and_retries(self):
        self.enable()
        size = (self.source / 'decision.md').stat().st_size
        other = self.source / 'other.md'
        other.write_text('Keep this file for a later pass.\n')
        self.worker.configure(max_bytes_per_run=size + other.stat().st_size - 1)
        import os
        original = os.fstat
        calls = []
        def changing(fd):
            result = original(fd)
            calls.append(fd)
            if len(calls) == 2:
                from types import SimpleNamespace
                return SimpleNamespace(st_mode=result.st_mode, st_size=result.st_size + 1,
                    st_ino=result.st_ino, st_mtime_ns=result.st_mtime_ns + 1)
            return result
        with patch('brain.core.os.fstat', side_effect=changing):
            result = self.worker.run_once()['results'][0]
        self.assertEqual(result['state'], 'partial')
        snapshot = self.b.snapshot(self.pid)
        entry, skipped = snapshot['files']
        self.assertNotIn('observed_at', entry)
        self.assertEqual(entry['status'], 'unprocessed')
        self.assertEqual(snapshot['metrics']['bytes_read'], size)
        self.assertEqual(skipped['reason'], 'byte budget')
        self.assertNotIn('observed_at', skipped)
        self.assertGreater(result['next_due'], result['last_attempt_at'])
