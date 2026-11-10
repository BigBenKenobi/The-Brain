"""Configuration strings must not become inferred project commitments."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from brain.core import Brain, initialize
from brain.state import ProjectState


class ConfigurationContextTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / 'source'
        self.source.mkdir()
        (self.source / 'pyproject.toml').write_text(
            '[project]\nname = "example-tool"\n'
            'description = "Decision: chosen because unresolved timeout is a test label"\n')
        (self.source / 'mission.md').write_text(
            '# Mission\nThe project should keep garden watering schedules easy to inspect.\n')
        initialize(root / 'store')
        self.brain = Brain(root / 'store')

    def test_configuration_visible_without_claiming_objective_or_blocker(self):
        pid = self.brain.ingest(self.source)['project_id']
        before = {p: p.read_bytes() for p in self.brain.root.rglob('*') if p.is_file()}
        brief = self.brain.briefing(pid)
        item = brief['sections']['configuration']['items'][0]
        self.assertEqual(item['evidence']['path'], 'pyproject.toml')
        for section in ('objectives', 'decisions', 'problems', 'ideas'):
            self.assertTrue(all(x['evidence']['path'] != 'pyproject.toml'
                                for x in brief['sections'][section]['items']))
        self.assertIn('garden watering', brief['sections']['objectives']['items'][0]['excerpt'])
        self.assertFalse(ProjectState(self.brain, pid).view()['items'])
        self.assertEqual(before, {p: p.read_bytes() for p in self.brain.root.rglob('*') if p.is_file()})

    def test_legacy_automatic_catalog_filtered_but_reviewed_correction_preserved(self):
        # Emulate the previous reader publishing a candidate from config strings.
        with patch('brain.state.configuration_source', return_value=False):
            pid = self.brain.ingest(self.source)['project_id']
            state = ProjectState(self.brain, pid)
            original = next(iter(state.view()['items'].values()))
            with patch('brain.state.configuration_source', return_value=True):
                self.assertFalse(ProjectState(self.brain, pid).view()['items'])
            evidence = original['claims'][0]
            state.correct(original['id'], {'summary': 'Configuration contains a timeout test label.'},
                          evidence, 'Explicit review of configuration evidence.')
        current = ProjectState(self.brain, pid).view()['items']
        self.assertEqual(current[original['id']]['summary'], 'Configuration contains a timeout test label.')
        self.assertTrue(current[original['id']]['reviewed'])
