"""Duplicate promotion must extract evidence without transferring sharing consent."""
from pathlib import Path
import tempfile
import unittest

from brain.core import Brain, digest, initialize, validate


class DuplicateCache(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        self.text = 'Decision: SQLite locking uses bounded retry.\n'
        for name in ('a.md', 'b.md'):
            (self.source / name).write_text(self.text)
        initialize(self.base / 'store')
        self.brain = Brain(self.base / 'store')

    def test_surviving_duplicate_is_searchable_without_inheriting_approval(self):
        for operation in ('remove', 'exclude'):
            with self.subTest(operation=operation):
                (self.source / 'a.md').write_text(self.text)
                pid = self.brain.ingest(self.source)['project_id']
                first = self.brain.snapshot(pid)
                path = self.brain.root / 'projects' / pid / 'snapshots' / (first['id'] + '.json')
                original_snapshot = path.read_bytes()
                record = first['records'][0]
                self.brain.promote(pid, record['id'], ['sqlite'], 'Reviewed original path')
                if operation == 'remove':
                    (self.source / 'a.md').unlink()
                self.brain.ingest(self.source, excluded_paths=['a.md'] if operation == 'exclude' else [])
                current = self.brain.snapshot(pid)
                self.assertTrue(validate(current)['valid'])
                hits = self.brain.retrieve('SQLite locking', pid)
                self.assertTrue(hits)
                self.assertEqual(hits[0]['evidence']['path'], 'b.md')
                self.assertEqual(hits[0]['evidence']['sha256'], digest(self.text.encode()))
                self.assertNotEqual(hits[0]['id'], record['id'])
                self.assertEqual(self.brain.retrieve('SQLite locking', technologies=['sqlite']), [])
                self.assertEqual(path.read_bytes(), original_snapshot)
                self.assertEqual((self.source / 'b.md').read_text(), self.text)
                self.assertEqual(self.brain.retained_evidence(pid, 'b.md')['text'], self.text.rstrip())

    def test_earlier_duplicate_and_empty_extraction_cache(self):
        (self.source / 'empty.txt').write_text('')
        pid = self.brain.ingest(self.source)['project_id']
        (self.source / '0.md').write_text(self.text)
        self.brain.ingest(self.source)
        self.assertEqual(self.brain.retrieve('SQLite locking', pid)[0]['evidence']['path'], '0.md')
        (self.source / '0.md').unlink()
        self.brain.ingest(self.source)
        self.assertEqual(self.brain.retrieve('SQLite locking', pid)[0]['evidence']['path'], 'a.md')
        refresh = self.brain.ingest(self.source)
        self.assertEqual(refresh['metrics']['extractions'], 0)
        self.assertEqual(refresh['metrics']['cache_hits'], 2)
