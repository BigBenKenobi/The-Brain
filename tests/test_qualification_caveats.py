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
