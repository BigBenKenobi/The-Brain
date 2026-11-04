import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from brain.core import Brain, digest, initialize, read, validate, write


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.source = self.base / 'alpha'
        self.source.mkdir()
        (self.source / 'README.md').write_text('# Decision: SQLite locking\nSolution: use a bounded retry for SQLite database locking.\nLimit: retry only transient contention, never corrupt databases.\n')
        (self.source / 'proposal.md').write_text('# Proposed solution\nUntested SQLite database locking approach: retry forever.\n')
        (self.source / 'private.md').write_text('Internal customer roadmap for the orchard service.')
        (self.source / 'main.py').write_text('def add(a, b):\n    return a + b\n')
        (self.source / 'copy.py').write_bytes((self.source / 'main.py').read_bytes())
        (self.source / '.env').write_text('PASSWORD=super-private-value')
        (self.source / 'config.txt').write_text('api_key = sk-abcdefghijklmnopqrstuvwxyz')
        (self.source / 'image.bin').write_bytes(b'\x00\xff')
        (self.source / 'node_modules').mkdir()
        (self.source / 'node_modules' / 'ignored.js').write_text('generated')
        initialize(self.base / 'Project-Brain')
        self.b = Brain(self.base / 'Project-Brain')

    def ingest(self):
        return self.b.ingest(self.source)['project_id']

    def test_inventory_provenance_and_source_unchanged(self):
        before = {str(p): p.read_bytes() for p in self.source.rglob('*') if p.is_file()}
        pid = self.ingest()
        s = self.b.snapshot(pid)
        self.assertTrue(validate(s)['valid'])
        statuses = {f['path']: f['status'] for f in s['files']}
        self.assertEqual(statuses['.env'], 'sensitive')
        self.assertEqual(statuses['config.txt'], 'sensitive')
        self.assertEqual(statuses['image.bin'], 'unsupported')
        self.assertIn('duplicate', statuses.values())
        self.assertEqual(statuses['node_modules'], 'excluded_directory')
        self.assertNotIn('super-private-value', json.dumps(s))
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.source.rglob('*') if p.is_file()})

    def test_incremental_and_historical_snapshots(self):
        pid = self.ingest()
        first = self.b.snapshot(pid)
        second = self.b.ingest(self.source)
        self.assertEqual(second['project_id'], pid)
        self.assertEqual(second['metrics']['extractions'], 0)
        self.assertGreater(second['metrics']['cache_hits'], 0)
        (self.source / 'main.py').write_text('def add(a, b):\n    return a + b + 1\n')
        third = self.b.ingest(self.source)
        self.assertEqual(third['metrics']['extractions'], 1)
        self.assertIn('return a + b', self.b.retained_evidence(pid, 'main.py', snapshot_id=first['id'])['text'])
        with self.assertRaises(ValueError):
            self.b.snapshot(pid, '../escape')
        self.assertTrue((self.b.root / 'projects' / pid / 'snapshots' / (first['id'] + '.json')).exists())

    def test_retrieval_after_source_deleted_and_isolation(self):
        pid = self.ingest()
        r = next(r for r in self.b.snapshot(pid)['records'] if r['evidence']['path'] == 'README.md')
        other = self.base / 'beta'
        other.mkdir()
        (other / 'README.md').write_text('New SQLite application')
        target = self.b.ingest(other)['project_id']
        self.assertEqual(self.b.retrieve('SQLite database locking', target, ['sqlite']), [])
        self.b.promote(pid, r['id'], ['sqlite'], 'Reviewed for general SQLite contention handling')
        shutil.rmtree(self.source)  # disposable fixture only
        hits = self.b.retrieve('SQLite database locking', target, ['sqlite'])
        self.assertEqual(len(hits), 1)
        self.assertIn('why', hits[0])
        self.assertIn('evidence', hits[0])
        self.assertEqual(hits[0]['evidence_status'], 'historical_record')
        self.assertEqual(self.b.retrieve('customer orchard roadmap', target, ['sqlite']), [])
        self.assertEqual(self.b.retrieve('SQLite database locking', target, ['postgres']), [])
        self.assertEqual(self.b.retrieve('SQLite art museum', target, ['sqlite']), [])
        self.assertEqual(self.b.retrieve('SQLite database locking', target, ['sqlite'], blocked=['retry']), [])
        report = self.b.retirement(pid)
        self.assertFalse(report['verified_recoverable_source_archive'])
        self.assertEqual(report['classification'], 'knowledge-only')
        self.assertIn('Limit:', self.b.summary(pid))

    def test_proposals_remain_unverified(self):
        pid = self.ingest()
        r = next(r for r in self.b.snapshot(pid)['records'] if r['evidence']['path'] == 'proposal.md')
        self.b.promote(pid, r['id'], ['sqlite'], 'Share as an explicitly untested proposal')
        hits = self.b.retrieve('SQLite database locking', technologies=['sqlite'])
        self.assertEqual(hits[0]['evidence_status'], 'proposal')

    def test_failed_publication_preserves_previous_snapshot(self):
        pid = self.ingest()
        previous = self.b.snapshot(pid)
        (self.source / 'README.md').write_text('changed')
        original = write
        def fail_pointer(path, value):
            if Path(path) == self.b.registry_path:
                raise OSError('simulated disk failure')
            return original(path, value)
        with patch('brain.core.write', side_effect=fail_pointer):
            with self.assertRaises(OSError):
                self.b.ingest(self.source)
        self.assertEqual(self.b.snapshot(pid), previous)

    def test_inaccessible_is_explicit(self):
        real = os.open
        def deny(path, *args, **kwargs):
            if Path(path).name == 'private.md':
                raise PermissionError('fixture denied')
            return real(path, *args, **kwargs)
        with patch('brain.core.os.open', side_effect=deny):
            pid = self.ingest()
        self.assertTrue(any(f['status'] == 'inaccessible' for f in self.b.snapshot(pid)['files']))

    def test_archive_integrity_and_no_retirement_mutation(self):
        pid = self.ingest()
        report = self.b.archive(pid)
        self.assertTrue(report['integrity_verified'])
        self.assertFalse(report['recoverable_source_archive'])
        self.b.retirement(pid)
        self.assertTrue(self.source.exists())
        archive = Path(report['archive'])
        with zipfile.ZipFile(archive) as z:
            payload, manifest = z.read('snapshot.json'), z.read('manifest.json')
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('snapshot.json', payload + b' ')
            z.writestr('manifest.json', manifest)
        with self.assertRaises(ValueError):
            self.b.verify_archive(archive)

    def test_budget_and_symlinks(self):
        (self.source / 'link.md').symlink_to(self.source / 'README.md')
        pid = self.ingest()
        self.assertTrue(any(f['path'] == 'link.md' and f['status'] == 'excluded' for f in self.b.snapshot(pid)['files']))
        self.b.config['max_files'] = 1
        self.b.ingest(self.source)
        self.assertTrue(self.b.snapshot(pid)['coverage_warnings'])

    def test_changed_shared_evidence_invalidates_approval(self):
        pid = self.ingest()
        r = next(r for r in self.b.snapshot(pid)['records'] if r['evidence']['path'] == 'README.md')
        self.b.promote(pid, r['id'], ['sqlite'], 'Reviewed')
        (self.source / 'README.md').write_text('New solution: SQLite database locking requires review.')
        self.b.ingest(self.source)
        self.assertEqual(self.b.retrieve('SQLite database locking', technologies=['sqlite']), [])

    def test_stable_id_relocation(self):
        pid = self.ingest()
        new = self.base / 'renamed'
        self.source.rename(new)
        self.assertEqual(self.b.ingest(new, pid)['project_id'], pid)

    def test_expired_approval_and_context_cost(self):
        pid = self.ingest()
        r = next(r for r in self.b.snapshot(pid)['records'] if r['evidence']['path'] == 'README.md')
        self.b.promote(pid, r['id'], ['sqlite'], 'Reviewed')
        self.assertEqual(self.b.retrieve('SQLite database locking', technologies=['sqlite'], max_chars=1), [])
        path = self.b.root / 'shared' / (r['id'] + '.json')
        a = read(path)
        a['review_after'] = 0
        write(path, a)
        self.assertEqual(self.b.retrieve('SQLite database locking', technologies=['sqlite']), [])

    def test_brain_source_overlap_rejected(self):
        with self.assertRaises(ValueError):
            self.b.ingest(self.base)

    def test_ai_configuration_fails_clearly(self):
        path = self.b.root / 'config.json'
        config = read(path)
        config['ai']['enabled'] = True
        write(path, config)
        with self.assertRaisesRegex(ValueError, 'AI execution is unavailable'):
            Brain(self.b.root)

    def test_late_knowledge_and_retained_evidence(self):
        content = ''.join(f'# Background {i}\nOrdinary introductory material.\n' for i in range(45))
        content = content.replace('# Background 40\nOrdinary introductory material.', '# Background 40\nQuartz amphibian observation.')
        content += '# Decision\nChosen SQLite because offline operation is required.\n'
        content += '# Known issue\nUnresolved regression: concurrent writers remain blocked.\n'
        content += '# Lessons\nLesson learned: avoid unbounded retries.\n'
        (self.source / 'long.md').write_text(content)
        pid = self.ingest()
        s = self.b.snapshot(pid)
        records = [r for r in s['records'] if r['evidence']['path'] == 'long.md']
        self.assertLessEqual(len(records), 128)
        self.assertTrue(self.b.retrieve('Quartz amphibian', pid))
        self.assertTrue(any('Chosen SQLite' in r['statement'] for r in records))
        self.assertTrue(any('unresolved' in r['knowledge_kinds'] for r in records))
        self.assertTrue(any('lesson' in r['knowledge_kinds'] for r in records))
        shutil.rmtree(self.source)  # disposable fixture only
        evidence = self.b.retained_evidence(pid, 'long.md')
        self.assertEqual(evidence['text'], content.rstrip())
        self.assertEqual(evidence['source'], 'retained_snapshot')
        self.assertTrue(self.b.retrieve('concurrent writers', pid))
        with self.assertRaises(ValueError):
            self.b.retained_evidence(pid, '.env')

    def test_long_section_late_solution_and_proposal(self):
        (self.source / 'long.md').write_text('# Background\n' + 'Background information.\n' * 90 +
            'Proposed solution: bounded retry; untested.\n')
        pid = self.ingest()
        hits = self.b.retrieve('bounded retry', pid)
        self.assertTrue(any(r['evidence_status'] == 'proposal' and r['evidence']['path'] == 'long.md' for r in hits))
        self.assertTrue(validate(self.b.snapshot(pid))['valid'])
        self.assertEqual(self.b.ingest(self.source)['metrics']['extractions'], 0)

    def test_fedora_formats_sensitive_json_and_scoped_history(self):
        (self.source / 'unit.service').write_text('[Service]\nExecStart=/bin/example\n')
        (self.source / 'survey').write_text('#!/bin/sh\necho example\n')
        (self.source / 'settings.json').write_text('{"password": "private-example-value"}')
        (self.source / 'empty.txt').write_text('')
        nested = self.source / 'separate'
        nested.mkdir()
        (nested / 'README.md').write_text('Separate project uniquephrase')
        result = self.b.ingest(self.source, excluded_paths=['separate'])
        pid = result['project_id']
        snap = self.b.snapshot(pid)
        statuses = {f['path']: f['status'] for f in snap['files']}
        self.assertEqual(statuses['settings.json'], 'sensitive')
        self.assertEqual(statuses['unit.service'], 'retained')
        self.assertEqual(statuses['survey'], 'retained')
        self.assertEqual(statuses['separate'], 'excluded_directory')
        self.assertNotIn('private-example-value', json.dumps(snap))
        child = self.b.ingest(nested, historical=True)['project_id']
        self.assertNotEqual(child, pid)
        self.assertEqual(self.b.retrieve('uniquephrase', pid), [])
        self.assertTrue(all(r['source_role'] == 'historical_copy' for r in self.b.snapshot(child)['records']))
        self.assertEqual(self.b.ingest(self.source, excluded_paths=['separate'])['metrics']['extractions'], 0)
        with self.assertRaises(ValueError):
            self.b.ingest(self.source, excluded_paths=['../escape'])

    def test_cli_budget_scope_and_history(self):
        command = [sys.executable, '-m', 'brain', '--brain', str(self.b.root)]
        result = subprocess.run(command + ['ingest', str(self.source), '--max-files', '2',
            '--exclude-path', 'node_modules', '--historical'], capture_output=True, text=True, check=True)
        output = json.loads(result.stdout)
        pid = output['project_id']
        snap = self.b.snapshot(pid)
        self.assertEqual(snap['processing_budgets']['max_files'], 2)
        self.assertEqual(snap['excluded_paths'], ['node_modules'])
        self.assertTrue(snap['historical'])
        self.assertTrue(snap['coverage_warnings'])
        result = subprocess.run(command + ['history', pid], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)[0]['snapshot'], snap['id'])
        invalid = subprocess.run(command + ['ingest', str(self.source), '--max-files', '0'], capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 1)

    def test_knowledge_retirement_review_is_snapshot_bound(self):
        pid = self.ingest()
        self.assertFalse(self.b.retirement(pid)['knowledge_retirement_ready'])
        rid = self.b.snapshot(pid)['records'][0]['id']
        with self.assertRaises(ValueError):
            self.b.review_retirement(pid, 'Reviewed', [], [rid])
        with self.assertRaises(ValueError):
            self.b.review_retirement(pid, 'Reviewed', ['Binary material omitted'], ['unknown'])
        result = self.b.review_retirement(pid, 'Checked decisions and unresolved issues',
            ['Binary material and credential files intentionally omitted'], [rid])
        self.assertTrue(result['knowledge_retirement_ready'])
        self.assertFalse(result['source_recovery_required'])
        self.assertFalse(result['verified_recoverable_source_archive'])
        self.assertFalse(result['deletion_authorized'])
        self.b.ingest(self.source)
        self.assertFalse(self.b.retirement(pid)['knowledge_retirement_ready'])
        self.b.config['max_files'] = 1
        self.b.ingest(self.source)
        rid = self.b.snapshot(pid)['records'][0]['id']
        self.assertFalse(self.b.review_retirement(pid, 'Budget truncated', ['Uninventoried tree'], [rid])['knowledge_retirement_ready'])

    def test_consolidation_preserves_private_evidence_and_reingestion(self):
        pid = self.ingest()
        previous = self.b.snapshot(pid)
        docs = self.base / 'docs'
        docs.mkdir()
        (docs / 'README.md').write_text('# Survey status\nKnown issue: survey IndexError on missing address.\n')
        sid = self.b.ingest(docs)['project_id']
        supplement = self.b.snapshot(sid)
        self.assertEqual(self.b.retrieve('survey IndexError', pid), [])
        result = self.b.consolidate(pid, sid)
        merged = self.b.snapshot(pid)
        self.assertEqual(len(merged['records']), len(previous['records']) + len(supplement['records']))
        hits = self.b.retrieve('survey IndexError', pid)
        self.assertTrue(hits)
        r = hits[0]
        self.assertEqual(r['project_id'], pid)
        self.assertEqual(r['consolidated_from']['project_id'], sid)
        self.assertEqual(r['evidence_status'], supplement['records'][0]['evidence_status'])
        self.assertEqual(self.b.retrieve('survey IndexError'), [])
        self.assertEqual(self.b.snapshot(pid, previous['id']), previous)
        self.assertEqual(self.b.snapshot(sid), supplement)
        shutil.rmtree(docs)  # disposable fixture only
        self.assertIn('IndexError', self.b.retained_evidence(pid, r['evidence']['path'])['text'])
        self.assertFalse(self.b.consolidate(pid, sid)['changed'])
        self.b.ingest(self.source)
        self.assertTrue(self.b.retrieve('survey IndexError', pid))
        self.assertEqual(self.b.snapshot(pid)['consolidation'][0]['snapshot'], supplement['id'])
        self.assertTrue(validate(self.b.snapshot(pid))['valid'])

    def test_consolidation_failed_publication_and_invalid_sources(self):
        pid = self.ingest()
        child = self.base / 'child'
        child.mkdir()
        (child / 'README.md').write_text('Decision: preserve bounded retries.')
        sid = self.b.ingest(child)['project_id']
        previous = self.b.snapshot(pid)
        registry = read(self.b.registry_path)
        original = write
        def fail_pointer(path, value):
            if Path(path) == self.b.registry_path:
                raise OSError('simulated publication failure')
            return original(path, value)
        with patch('brain.core.write', side_effect=fail_pointer):
            with self.assertRaises(OSError):
                self.b.consolidate(pid, sid)
        self.assertEqual(read(self.b.registry_path), registry)
        self.assertEqual(self.b.snapshot(pid), previous)
        with self.assertRaises(ValueError):
            self.b.consolidate(pid, pid)
        self.b.consolidate(pid, sid)
        with self.assertRaises(ValueError):
            self.b.consolidate(sid, pid)

    def test_corrupt_evidence_rejected(self):
        pid = self.ingest()
        s = self.b.snapshot(pid)
        s['records'][0]['statement'] = 'invented claim'
        with self.assertRaises(ValueError):
            validate(s)

if __name__ == '__main__':
    unittest.main()
