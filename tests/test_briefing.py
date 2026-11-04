import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from brain.core import Brain, initialize, write
from brain.briefing import render_briefing


class BriefingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'app'
        self.source.mkdir()
        initialize(self.root / 'memory')
        self.brain = Brain(self.root / 'memory')

    def put(self, path, text):
        target = self.source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def ingest(self, **kwargs):
        return self.brain.ingest(self.source, **kwargs)['project_id']

    def test_development_history_keeps_claims_distinct_from_verification(self):
        self.put('README.md', '# Objective\nMake project switching easier.\n')
        self.put('proposal.md', '# Proposed approach\nUntested filesystem watcher.\n')
        self.put('decision.md', '# Decision\nUse polling because it is portable.\n')
        self.put('issue.md', '# Known issue\nBlocked by partial writes.\n')
        self.put('main.py', 'def poll():\n    pass\n')
        pid = self.ingest()
        first = self.brain.briefing(pid)
        self.assertFalse(first['changes']['available'])
        self.assertEqual(len(first['sections']['objectives']['items']), 1)
        self.assertEqual(first['sections']['ideas']['items'][0]['evidence_status'], 'proposal')
        self.assertEqual(first['sections']['implementation']['items'][0]['evidence_status'], 'observed_implementation')
        self.put('decision.md', '# Decision\nUse explicit refresh because polling observed partial writes.\n')
        self.put('results.md', '# Solution\nFixed partial writes; tests passed for revision abc123.\n')
        self.put('main.py', 'def refresh():\n    return True\n')
        (self.source / 'issue.md').unlink()
        self.ingest()
        second = self.brain.briefing(pid)
        self.assertEqual(second['changes']['baseline_snapshot'], first['snapshot'])
        self.assertEqual(second['changes']['groups']['content_changed']['paths'], ['decision.md', 'main.py'])
        self.assertEqual(second['changes']['groups']['newly_retained']['paths'], ['results.md'])
        self.assertEqual(second['changes']['groups']['no_longer_retained']['paths'], ['issue.md'])
        self.assertEqual(second['sections']['outcomes']['items'][0]['evidence_status'], 'historical_record')
        self.assertNotIn('Use polling', json.dumps(second))
        self.assertTrue(any('independent test results are unknown' in s for s in second['limitations']))
        for section in second['sections'].values():
            for item in section['items']:
                e = item['evidence']
                evidence = self.brain.retained_evidence(pid, e['path'], e['start_line'], e['end_line'], item['snapshot'])
                self.assertIn(item['excerpt'], evidence['text'])
                self.assertTrue(item['selection_reason'])

    def test_unchanged_refresh_and_exclusions_are_not_deletion_claims(self):
        self.put('main.py', 'print(1)\n')
        pid = self.ingest()
        self.ingest()
        self.assertTrue(all(g['count'] == 0 for g in self.brain.briefing(pid)['changes']['groups'].values()))
        self.ingest(excluded_paths=['main.py'])
        briefing = self.brain.briefing(pid)
        self.assertTrue(briefing['changes']['scope_changed'])
        self.assertEqual(briefing['changes']['groups']['no_longer_retained']['paths'], ['main.py'])
        self.assertIn('does not prove deletion', briefing['changes']['interpretation'])
        self.assertTrue((self.source / 'main.py').exists())
        self.assertEqual(briefing['coverage']['omitted_by_status'], {'excluded': 1})

    def test_failed_publication_does_not_become_baseline(self):
        self.put('README.md', 'Objective: first state.\n')
        pid = self.ingest()
        baseline = self.brain.snapshot(pid)['id']
        self.put('README.md', 'Objective: unpublished state.\n')
        def fail(path, value):
            if Path(path) == self.brain.registry_path:
                raise OSError('simulated publication failure')
            write(path, value)
        with patch('brain.core.write', side_effect=fail):
            with self.assertRaises(OSError):
                self.ingest()
        self.put('README.md', 'Objective: final state.\n')
        self.ingest()
        briefing = self.brain.briefing(pid)
        self.assertEqual(briefing['changes']['baseline_snapshot'], baseline)
        self.assertNotIn('unpublished state', json.dumps(briefing))

    def test_legacy_snapshot_has_no_guessed_baseline(self):
        self.put('README.md', 'Objective: test legacy compatibility.\n')
        pid = self.ingest()
        self.ingest()
        snapshot = self.brain.snapshot(pid)
        del snapshot['parent_snapshot']
        write(self.brain.root / 'projects' / pid / 'snapshots' / (snapshot['id'] + '.json'), snapshot)
        self.assertFalse(self.brain.briefing(pid)['changes']['available'])

    def test_read_only_private_and_available_without_source(self):
        self.put('README.md', 'Objective: keep this project separate.\n')
        self.put('.env', 'PASSWORD=never-retain-this\n')
        pid = self.ingest()
        other = self.root / 'other'
        other.mkdir()
        (other / 'README.md').write_text('Decision: other-project-only-marker\n')
        self.brain.ingest(other)
        before = {p: p.read_bytes() for p in self.brain.root.rglob('*') if p.is_file()}
        shutil.rmtree(self.source)
        output = json.dumps(self.brain.briefing(pid))
        self.assertNotIn('never-retain-this', output)
        self.assertNotIn('other-project-only-marker', output)
        self.assertEqual(before, {p: p.read_bytes() for p in self.brain.root.rglob('*') if p.is_file()})

    def test_bounded_selection_reports_omissions_and_uncertain_coverage(self):
        for i in range(5):
            self.put(f'{i}.md', f'Decision {i}: ' + ('x' * 1000))
        self.brain.config['max_files'] = 3
        pid = self.ingest()
        briefing = self.brain.briefing(pid, limit=1)
        section = briefing['sections']['decisions']
        self.assertEqual(len(section['items']), 1)
        self.assertEqual(section['omitted'], 2)
        self.assertEqual(len(section['items'][0]['excerpt']), 400)
        self.assertTrue(section['items'][0]['excerpt_truncated'])
        self.assertGreater(briefing['coverage']['warning_count'], 0)
        for limit in (0, -1, 21, True):
            with self.assertRaises(ValueError):
                self.brain.briefing(pid, limit)

    def test_historical_and_consolidated_sources_remain_labelled(self):
        self.put('README.md', 'Decision: old approach.\n')
        historical = self.ingest(historical=True)
        result = self.brain.briefing(historical)
        self.assertTrue(result['historical_capture'])
        self.assertEqual(len(result['sections']['historical']['items']), 1)
        other = self.root / 'current'
        other.mkdir()
        (other / 'README.md').write_text('Objective: current project.\n')
        pid = self.brain.ingest(other)['project_id']
        previous = self.brain.snapshot(pid)['id']
        self.brain.consolidate(pid, historical)
        result = self.brain.briefing(pid)
        self.assertEqual(result['changes']['baseline_snapshot'], previous)
        origin = result['sections']['historical']['items'][0]['consolidated_from']
        self.assertEqual(origin['project_id'], historical)
        self.assertIn('Pinned supplement:', render_briefing(result))

    def test_corruption_is_rejected(self):
        self.put('README.md', 'Objective: original.\n')
        pid = self.ingest()
        snapshot = self.brain.snapshot(pid)
        snapshot['records'][0]['statement'] = 'Fabricated completion'
        write(self.brain.root / 'projects' / pid / 'snapshots' / (snapshot['id'] + '.json'), snapshot)
        with self.assertRaises(ValueError):
            self.brain.briefing(pid)

    def test_cli_markdown_json_and_invalid_limit(self):
        self.put('README.md', 'Objective: CLI coverage.\n')
        pid = self.ingest()
        command = [sys.executable, '-m', 'brain', '--brain', str(self.brain.root), 'briefing', pid]
        plain = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertIn('Objective candidates', plain.stdout)
        data = subprocess.run(command + ['--json'], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(data.stdout)['project_id'], pid)
        error = subprocess.run(command + ['--limit', '0'], capture_output=True, text=True)
        self.assertEqual(error.returncode, 1)
        self.assertIn('between 1 and 20', error.stderr)


if __name__ == '__main__':
    unittest.main()
