"""Show explicit qualification limits without inferring failed or passed gates."""
from pathlib import Path
import tempfile
import unittest
from brain.core import Brain, initialize
from brain.briefing import qualification_caveat
from brain.state import ProjectState


class QualificationCaveatTests(unittest.TestCase):
    def test_retired_gate_is_cited_as_caveat_not_inferred_blocker_or_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'source';source.mkdir()
            (source/'release.md').write_text('# Scope\n\n'+('Interfaces need an explicit release scope. '*14)+
                '\n\n**Old tablet qualification is retired.** It is not a blocker and has not been relabelled\nas passed. Original reports remain available.\n')
            initialize(root/'store');b=Brain(root/'store');pid=b.ingest(source)['project_id']
            snap=b.snapshot(pid);before={p:p.read_bytes() for p in b.root.rglob('*') if p.is_file()}
            brief=b.briefing(pid);items=brief['sections']['qualification']['items']
            self.assertEqual(len(items),1)
            self.assertIn('not a blocker',items[0]['excerpt'])
            self.assertIn('as passed',items[0]['excerpt'])
            self.assertGreater(items[0]['excerpt_start_char'],400)
            record=next(r for r in snap['records'] if r['id']==items[0]['record_id'])
            self.assertEqual(items[0]['excerpt'],record['statement'][items[0]['excerpt_start_char']:items[0]['excerpt_end_char']])
            self.assertFalse(brief['sections']['problems']['items'])
            self.assertFalse(ProjectState(b,pid).view()['items'])
            self.assertEqual(before,{p:p.read_bytes() for p in b.root.rglob('*') if p.is_file()})

    def test_caveat_does_not_mean_negated_success_for_not_only_language(self):
        self.assertTrue(qualification_caveat('This has not been independently verified.'))
        self.assertTrue(qualification_caveat('The result is unverified.'))
        self.assertFalse(qualification_caveat('The check not only passed but exceeded its target.'))
        self.assertFalse(qualification_caveat('The check not just passed but exceeded its target.'))
        self.assertFalse(qualification_caveat('The test passed.'))

    def test_explicit_pending_and_separate_gates_without_generic_open_matches(self):
        for text in ('Hardware acceptance remains open.',
                     'Release qualification is still pending.',
                     'Model usefulness and native acceptance are separate gates.'):
            with self.subTest(text=text):
                self.assertTrue(qualification_caveat(text))
        for text in ('The window remains open.', 'Acceptance is complete.',
                     'Acceptance no longer remains open.',
                     'Validation is not pending.', 'Separate gates control access.'):
            with self.subTest(text=text):
                self.assertFalse(qualification_caveat(text))

    def test_pending_acceptance_paragraph_keeps_exact_evidence_and_other_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source'; source.mkdir()
            text = '# Release overview\n\n' + ('The application supports local work. ' * 20)
            caveat = 'Synthetic checks passed; physical-device acceptance remains open.'
            (source / 'release.md').write_text(text + '\n\n' + caveat + '\n')
            initialize(root / 'store'); brain = Brain(root / 'store')
            pid = brain.ingest(source)['project_id']
            before = {p: p.read_bytes() for p in brain.root.rglob('*') if p.is_file()}
            items = brain.briefing(pid)['sections']['qualification']['items']
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]['excerpt'], caveat)
            record = next(r for r in brain.snapshot(pid)['records']
                          if r['id'] == items[0]['record_id'])
            self.assertIn('application supports local work', record['statement'])
            self.assertEqual(record['statement'][items[0]['excerpt_start_char']:
                                                  items[0]['excerpt_end_char']], caveat)
            self.assertEqual(before, {p: p.read_bytes() for p in brain.root.rglob('*') if p.is_file()})

    def test_late_sentence_and_product_introduction_both_remain_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); source = root / 'source'; source.mkdir()
            intro = 'A local application for editing diagrams with the Atlas model.'
            caveat = 'Physical-device acceptance remains open.'
            (source / 'README.md').write_text('# Product\n\n' + intro + '\n\n' +
                ('Synthetic checks passed for the editing controls. ' * 12) + caveat)
            initialize(root / 'store'); brain = Brain(root / 'store')
            pid = brain.ingest(source)['project_id']
            brief = brain.briefing(pid)
            self.assertTrue(any(intro in i['excerpt'] for i in brief['sections']['objectives']['items']))
            item = brief['sections']['qualification']['items'][0]
            self.assertEqual(item['excerpt'], caveat)
            record = next(r for r in brain.snapshot(pid)['records'] if r['id'] == item['record_id'])
            self.assertEqual(record['statement'][item['excerpt_start_char']:item['excerpt_end_char']], caveat)
