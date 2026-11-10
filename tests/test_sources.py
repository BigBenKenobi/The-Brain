"""Source settings, observation provenance and migration behavior."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from brain.core import Brain, initialize, read, validate, write
from brain.sources import BUDGETS


class Sources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        (self.source / 'README.md').write_text('Decision: SQLite locking uses bounded retry.\n')
        (self.source / 'excluded.md').write_text('Idea: keep this reference separately.\n')
        initialize(self.base / 'store')
        self.b = Brain(self.base / 'store')

    def ingest(self, **kwargs):
        return self.b.ingest(self.source, **kwargs)

    def config(self, sid):
        return read(self.b.registry_path)['sources'][sid]['configuration']

    def test_saved_settings_omission_clear_and_future_revision(self):
        first = self.ingest(excluded_paths=['excluded.md'], historical=True, budgets={'max_files': 7})
        pid, sid = first['project_id'], first['source_id']
        saved = self.config(sid)
        self.assertFalse(saved['enabled'])
        fresh_instance = Brain(self.b.root)
        fresh_instance.refresh(sid)
        snapshot = self.b.snapshot(pid)
        self.assertEqual(snapshot['excluded_paths'], ['excluded.md'])
        self.assertEqual(snapshot['processing_budgets']['max_files'], 7)
        self.assertTrue(snapshot['historical'])
        self.assertEqual(self.config(sid), saved)
        self.b.configure_source(sid, excluded_paths=[], historical=False)
        # Configuration does not rewrite a completed observation.
        self.assertEqual(self.b.snapshot(pid), snapshot)
        self.b.refresh(sid)
        current = self.b.snapshot(pid)
        self.assertEqual(current['excluded_paths'], [])
        self.assertFalse(current['historical'])
        self.assertGreater(self.config(sid)['revision'], saved['revision'])
        self.assertTrue(any(r['evidence']['path'] == 'excluded.md' for r in current['records']))
        self.assertEqual(self.b.snapshot(pid, snapshot['id']), snapshot)

    def test_relocation_and_multiple_sources_preserve_independent_settings(self):
        first = self.ingest(excluded_paths=['excluded.md'])
        pid, sid = first['project_id'], first['source_id']
        old = self.b.snapshot(pid)
        other = self.base / 'notes'
        other.mkdir()
        (other / 'README.md').write_text('Idea: future offline indexing.\n')
        second = self.b.ingest(other, pid, new_source=True, historical=True)
        sid2 = second['source_id']
        self.assertNotEqual(sid, sid2)
        self.assertEqual(len(self.b.snapshot(pid)['source_configurations']), 2)
        self.assertTrue(self.b.retrieve('SQLite locking', pid))
        self.assertTrue(self.b.retrieve('future offline', pid))
        note_record = self.b.retrieve('future offline', pid)[0]
        self.assertEqual(note_record['source_role'], 'historical_copy')
        self.assertTrue(note_record['evidence']['path'].startswith('sources/' + sid2 + '/'))
        moved = self.base / 'moved'
        self.source.rename(moved)
        self.b.configure_source(sid, new_location=moved)
        self.b.refresh(sid)
        current = self.b.snapshot(pid)
        self.assertFalse(current['historical'])
        self.assertEqual(self.config(sid)['excluded_paths'], ['excluded.md'])
        self.assertTrue(self.b.retrieve('future offline', pid))
        self.assertEqual(current['source_configurations'][sid]['location'], str(moved))
        self.assertEqual(self.b.snapshot(pid, old['id']), old)
        with self.assertRaises(ValueError):
            self.b.ingest(other, source_id=sid)

    def test_failed_publication_does_not_commit_config_or_observation(self):
        first = self.ingest(excluded_paths=['excluded.md'])
        pid, sid = first['project_id'], first['source_id']
        old = self.b.snapshot(pid)
        registry = read(self.b.registry_path)
        def fail(path, value):
            if Path(path) == self.b.registry_path:
                raise OSError('simulated pointer failure')
            write(path, value)
        with patch('brain.core.write', side_effect=fail):
            with self.assertRaises(OSError):
                self.ingest(excluded_paths=[], historical=True, budgets={'max_files': 1})
        self.assertEqual(self.b.snapshot(pid), old)
        self.assertEqual(read(self.b.registry_path), registry)
        with patch('brain.core.write', side_effect=fail):
            with self.assertRaises(OSError):
                self.b.refresh(sid)
        self.assertEqual(self.b.briefing(pid)['source_health'][0]['state'], 'failed')
        self.assertEqual(self.b.snapshot(pid), old)

    def test_missing_source_failure_then_recovery(self):
        first = self.ingest()
        pid, sid = first['project_id'], first['source_id']
        old = self.b.snapshot(pid)
        moved = self.base / 'unavailable'
        self.source.rename(moved)
        with self.assertRaises(OSError):
            self.b.refresh(sid)
        self.assertEqual(self.b.snapshot(pid), old)
        health = self.b.briefing(pid)['source_health'][0]
        self.assertEqual(health['state'], 'failed')
        self.assertIsNotNone(health['last_complete_at'])
        self.assertTrue(self.b.retrieve('SQLite locking', pid))
        moved.rename(self.source)
        self.b.refresh(sid)
        self.assertEqual(self.b.briefing(pid)['source_health'][0]['state'], 'complete')

    def test_automatic_targets_require_registration_and_opt_in(self):
        first = self.ingest()
        sid = first['source_id']
        with self.assertRaises(ValueError):
            self.b.refresh(sid, automatic=True)
        with self.assertRaises(ValueError):
            self.b.refresh('missing', automatic=True)
        self.b.configure_source(sid, enabled=True)
        self.b.refresh(sid, automatic=True)
        self.b.configure_source(sid, enabled=False)
        with self.assertRaises(ValueError):
            self.b.refresh(sid, automatic=True)

    def test_refresh_observes_old_extraction_without_reviewing_or_renewing_approval(self):
        with patch('brain.core.time.time', return_value=1000):
            first = self.ingest()
            pid, sid = first['project_id'], first['source_id']
            record = self.b.snapshot(pid)['records'][0]
            self.b.promote(pid, record['id'], ['sqlite'], 'Reviewed original excerpt')
        approval = read(self.b.root / 'shared' / (record['id'] + '.json'))
        later = 1000 + 500 * 86400
        with patch('brain.core.time.time', return_value=later):
            self.b.refresh(sid)
            hits = self.b.retrieve('SQLite locking', pid)
            self.assertTrue(hits)
            self.assertEqual(hits[0]['created_at'], 1000)
            self.assertEqual(hits[0]['observation']['observed_at'], later)
            self.assertEqual(hits[0]['evidence_status'], 'historical_record')
            self.assertEqual(self.b.retrieve('SQLite locking', technologies=['sqlite']), [])
        self.assertEqual(read(self.b.root / 'shared' / (record['id'] + '.json')), approval)

    def test_partial_reads_exclusions_and_budgets_never_gain_observation(self):
        first = self.ingest()
        sid, pid = first['source_id'], first['project_id']
        real_open = os.open
        def deny(path, *args, **kwargs):
            if Path(path).name == 'README.md':
                raise PermissionError('simulated unreadable source')
            return real_open(path, *args, **kwargs)
        with patch('brain.core.os.open', side_effect=deny):
            self.b.refresh(sid)
        snap = self.b.snapshot(pid)
        entry = next(f for f in snap['files'] if f['path'] == 'README.md')
        self.assertEqual(entry['status'], 'inaccessible')
        self.assertNotIn('observed_at', entry)
        self.assertEqual(snap['capture']['state'], 'partial')
        self.b.configure_source(sid, excluded_paths=['excluded.md'], budgets={'max_file_bytes': 1})
        self.b.refresh(sid)
        snap = self.b.snapshot(pid)
        self.assertTrue(all('observed_at' not in f for f in snap['files']))
        self.assertEqual(snap['capture']['state'], 'partial')

    def test_supplement_preserves_observation_date(self):
        with patch('brain.core.time.time', return_value=1000):
            supplement = self.ingest()['project_id']
        target = self.base / 'target'
        target.mkdir()
        (target / 'README.md').write_text('Objective: maintain project context.\n')
        pid = self.b.ingest(target)['project_id']
        self.b.consolidate(pid, supplement)
        hits = self.b.retrieve('SQLite locking', pid)
        self.assertEqual(hits[0]['observation']['observed_at'], 1000)
        self.assertEqual(self.b.retrieve('SQLite locking', pid, max_age_days=1), [])

    def make_legacy(self):
        first = self.ingest(excluded_paths=['excluded.md'], historical=True, budgets={'max_files': 9})
        registry = read(self.b.registry_path)
        registry.pop('sources')
        write(self.b.registry_path, registry)
        snap = self.b.snapshot(first['project_id'])
        for key in ('source_configurations', 'source_health', 'capture'):
            snap.pop(key)
        for f in snap['files']:
            for key in ('source_id', 'configuration_revision', 'observed_at'):
                f.pop(key, None)
        write(self.b.root / 'projects' / first['project_id'] / 'snapshots' / (snap['id'] + '.json'), snap)
        config = read(self.b.root / 'config.json')
        config['schema_version'] = 1
        write(self.b.root / 'config.json', config)
        return first['project_id'], snap

    def test_upgrade_legacy_unknown_dates_saved_settings_and_rollback_copy(self):
        pid, old = self.make_legacy()
        self.b = Brain(self.b.root)
        hit = self.b.retrieve('SQLite locking', pid)[0]
        self.assertIsNone(hit['observation']['observed_at'])
        self.assertEqual(self.b.retrieve('SQLite locking', pid, max_age_days=1), [])
        with self.assertRaisesRegex(ValueError, 'Legacy store'):
            self.ingest()
        backup = self.base / 'backup'
        result = self.b.upgrade_store(backup)
        self.assertEqual(result['snapshots_validated'], 1)
        copied = Brain(backup / 'store')
        self.assertEqual(copied.snapshot(pid), old)
        first = self.ingest()
        self.assertEqual(self.b.snapshot(pid)['excluded_paths'], ['excluded.md'])
        self.assertEqual(self.config(first['source_id'])['budgets']['max_files'], 9)
        self.assertTrue(self.config(first['source_id'])['historical'])
        self.assertFalse(self.config(first['source_id'])['enabled'])
        self.assertEqual(self.b.snapshot(pid, old['id']), old)

    def test_ambiguous_legacy_requires_explicit_reviewed_adoption(self):
        pid, old = self.make_legacy()
        registry = read(self.b.registry_path)
        registry['projects'][pid]['locations'].append(str(self.base / 'historical-location'))
        write(self.b.registry_path, registry)
        self.b.upgrade_store(self.base / 'backup')
        with self.assertRaisesRegex(ValueError, 'Ambiguous legacy'):
            self.ingest()
        with self.assertRaisesRegex(ValueError, 'requires explicit'):
            self.ingest(adopt_legacy=True)
        result = self.ingest(adopt_legacy=True, excluded_paths=[], historical=False,
                             budgets={k: self.b.config[k] for k in BUDGETS})
        self.assertEqual(len(read(self.b.registry_path)['sources']), 1)
        self.assertEqual(self.b.snapshot(pid, old['id']), old)
        self.assertFalse(self.config(result['source_id'])['historical'])

    def test_failed_upgrade_keeps_legacy_store_readable(self):
        pid, old = self.make_legacy()
        def fail(path, value):
            if Path(path) == self.b.root / 'config.json':
                raise OSError('simulated version publication failure')
            write(path, value)
        with patch('brain.core.write', side_effect=fail):
            with self.assertRaises(OSError):
                self.b.upgrade_store(self.base / 'backup')
        self.assertEqual(read(self.b.root / 'config.json')['schema_version'], 1)
        self.assertEqual(Brain(self.b.root).snapshot(pid), old)
        self.assertEqual(Brain(self.base / 'backup' / 'store').snapshot(pid), old)

    def test_cli_refresh_reuses_and_explicitly_resets_settings(self):
        def cli(*args):
            result = subprocess.run([sys.executable, '-m', 'brain', '--brain', str(self.b.root), *args], capture_output=True, text=True, check=True)
            return json.loads(result.stdout)
        first = cli('ingest', str(self.source), '--historical', '--exclude-path', 'excluded.md', '--max-files', '8')
        sid, pid = first['source_id'], first['project_id']
        cli('ingest', str(self.source))
        self.assertEqual(self.config(sid)['budgets']['max_files'], 8)
        self.assertTrue(self.b.snapshot(pid)['historical'])
        cli('configure-source', sid, '--no-historical', '--clear-exclusions', '--reset-budgets')
        cli('refresh', sid)
        self.assertFalse(self.b.snapshot(pid)['historical'])
        self.assertEqual(self.config(sid)['excluded_paths'], [])
        self.assertEqual(self.config(sid)['budgets']['max_files'], self.b.config['max_files'])
        self.assertEqual(len(cli('sources')), 1)
