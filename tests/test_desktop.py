"""Desktop contract tests use only disposable stores and offscreen Qt."""
import hashlib
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from brain.core import Brain, initialize, read, write
from brain.desktop_data import DesktopReader
from brain.state import ProjectState

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtWidgets import QApplication
    from brain.desktop import BrainWindow
except ImportError:
    QApplication = None


class DesktopDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / 'store'
        self.source = self.root / 'source'
        self.source.mkdir()
        self.note = self.source / 'decision.md'
        self.note.write_text('# Decision\nUse polling because partial writes need stable observation.\n')
        (self.source / 'idea.md').write_text('# Proposed idea\nFuture opportunity: batch events after testing.\n')
        initialize(self.store)
        self.brain = Brain(self.store)
        self.pid = self.brain.ingest(self.source)['project_id']
        self.reader = DesktopReader(self.store)

    def fingerprint(self):
        return {str(p.relative_to(self.store)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.store.rglob('*') if p.is_file()}

    def test_read_paths_preserve_store_and_pin_evidence(self):
        data = self.reader.project(self.pid)
        sid = data['snapshot']
        record = self.reader.search(self.pid, 'polling')['results'][0]
        self.note.write_text('# Decision\nUse explicit refresh instead of polling.\n')
        self.brain.ingest(self.source)
        before = self.fingerprint()
        self.reader.projects()
        self.reader.project(self.pid)
        self.reader.history(self.pid)
        capture = self.reader.capture(self.pid, sid)
        self.reader.record(self.pid, sid, record['id'])
        claim = {**record['evidence'], 'snapshot': record['snapshot']}
        evidence = self.reader.evidence(self.pid, claim)
        self.assertIn('partial writes', evidence['text'])
        self.assertNotIn('explicit refresh', evidence['text'])
        self.assertEqual(capture['snapshot'], sid)
        self.assertEqual(before, self.fingerprint())

    def test_project_load_reuses_the_same_maintained_state_for_overview(self):
        with patch.object(ProjectState, 'view', autospec=True, side_effect=ProjectState.view) as view:
            data = self.reader.project(self.pid)
        view.assert_called_once()
        self.assertEqual(data['briefing']['maintained_state']['snapshot'], data['state']['snapshot'])

    def test_shared_search_never_reads_unapproved_project(self):
        with patch.object(Brain, 'snapshot', side_effect=AssertionError('Private snapshot read')):
            self.assertEqual(self.reader.search(None, 'polling', ['python'])['results'], [])

    def test_shared_approval_requires_matching_technology(self):
        record = self.reader.search(self.pid, 'polling')['results'][0]
        self.brain.promote(self.pid, record['id'], ['python'], 'Reviewed for polling')
        self.assertEqual(self.reader.search(None, 'polling', ['sqlite'])['results'], [])
        result = self.reader.search(None, 'polling', ['python'])['results']
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['snapshot'], self.brain.project(self.pid)['snapshot'])

    def approve_polling(self):
        record = self.reader.search(self.pid, 'polling')['results'][0]
        self.brain.promote(self.pid, record['id'], ['python'], 'Reviewed polling scope')
        return self.reader.search(None, 'polling', ['python'])['results'][0]

    def test_shared_evidence_is_the_approved_statement_at_the_pinned_capture(self):
        self.note.write_text('# Background\nPrivate preceding context.\n'
                             '# Decision\nUse polling because events arrive asynchronously.\n'
                             '# Internal\nPrivate following context.\n')
        self.brain.ingest(self.source)
        record = self.approve_polling()
        self.brain.ingest(self.source)  # Same evidence, newer capture.
        before = self.fingerprint()
        evidence = self.reader.shared_evidence(self.pid, record['snapshot'], record['id'], ['PYTHON'])
        self.assertEqual(evidence['text'], record['statement'])
        self.assertEqual(evidence['snapshot'], record['snapshot'])
        self.assertEqual(evidence['start_line'], 3)
        self.assertEqual(evidence['end_line'], 4)
        self.assertNotIn('total_lines', evidence)
        self.assertEqual(before, self.fingerprint())

    def test_shared_evidence_respects_the_character_cutoff_within_a_source_line(self):
        self.note.write_text('Decision: Use polling. ' + 'x' * 1800 + ' Private remainder.\n')
        self.brain.ingest(self.source)
        record = self.approve_polling()
        evidence = self.reader.shared_evidence(self.pid, record['snapshot'], record['id'], ['python'])
        self.assertEqual(evidence['text'], record['statement'])
        self.assertEqual(len(evidence['text']), 1800)

    def test_shared_evidence_rechecks_expiry_revocation_and_current_record(self):
        record = self.approve_polling()
        approval_path = self.store / 'shared' / (record['id'] + '.json')
        approval = read(approval_path)
        args = (self.pid, record['snapshot'], record['id'])
        with self.assertRaisesRegex(ValueError, 'Sharing approval'):
            self.reader.shared_evidence(*args, ['sqlite'])
        with patch('brain.core.time.time', return_value=approval['review_after'] + 1):
            with self.assertRaisesRegex(ValueError, 'Sharing approval'):
                self.reader.shared_evidence(*args, ['python'])
        approval_path.unlink()
        with self.assertRaisesRegex(ValueError, 'Sharing approval'):
            self.reader.shared_evidence(*args, ['python'])
        write(approval_path, approval)
        replacement = next(r for r in self.brain.snapshot(self.pid)['records'] if r['id'] != record['id'])
        self.brain.relate(self.pid, record['id'], replacement['id'], 'supersedes', 'Reviewed precedence')
        with self.assertRaisesRegex(ValueError, 'Sharing approval'):
            self.reader.shared_evidence(*args, ['python'])
        self.assertEqual(self.reader.shared_evidence(*args, ['python'], history=True)['text'], record['statement'])
        self.note.write_text('# Decision\nReplace polling with explicit refresh.\n')
        self.brain.ingest(self.source)
        with self.assertRaisesRegex(ValueError, 'Sharing approval'):
            self.reader.shared_evidence(*args, ['python'], history=True)

    def test_writer_contention_is_reported_without_waiting(self):
        with self.brain.lock():
            with self.assertRaisesRegex(ValueError, 'capturing'):
                self.reader.project(self.pid)

    def test_legacy_and_empty_stores_are_readable_without_upgrade(self):
        config = read(self.store / 'config.json')
        config['schema_version'] = 3
        write(self.store / 'config.json', config)
        before = self.fingerprint()
        self.reader.project(self.pid)
        self.assertEqual(before, self.fingerprint())
        empty = self.root / 'empty'
        initialize(empty)
        self.assertEqual(DesktopReader(empty).projects(), {})
        self.assertFalse((empty / '.lock').exists())

    def test_evidence_hash_mismatch_and_missing_snapshot_are_explicit(self):
        record = self.reader.search(self.pid, 'polling')['results'][0]
        claim = {**record['evidence'], 'snapshot': record['snapshot'], 'sha256': 'wrong'}
        with self.assertRaisesRegex(ValueError, 'hash'):
            self.reader.evidence(self.pid, claim)
        (self.store / 'projects' / self.pid / 'snapshots' / (record['snapshot'] + '.json')).unlink()
        with self.assertRaises(FileNotFoundError):
            self.reader.evidence(self.pid, claim)


@unittest.skipIf(QApplication is None, 'Optional PySide6 is not installed')
class DesktopUiTests(DesktopDataTests):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        super().setUp()
        self.window = BrainWindow(self.store, QSettings(str(self.root / 'ui.ini'), QSettings.IniFormat))
        self.window.show()
        self.addCleanup(self.window.close)
        self.wait(lambda: self.window.data is not None)

    def wait(self, condition):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            self.app.processEvents()
            if condition():
                return
            time.sleep(.01)
        self.fail('Timed out waiting for UI: ' + self.window.notice.text())

    def test_search_inspect_and_back_preserve_navigation(self):
        before = self.fingerprint()
        w = self.window
        w.query.setText('polling')
        self.wait(lambda: w.results.count() == 1)
        w.open_list_item(w.results.item(0))
        self.wait(lambda: w.evidence_result is not None)
        self.assertIn('partial writes', w.evidence.toPlainText())
        self.assertTrue(w.inspector.isVisible())
        w.back()
        self.assertFalse(w.inspector.isVisible())
        self.assertEqual(w.query.text(), 'polling')
        self.assertEqual(before, self.fingerprint())

    def test_late_response_cannot_replace_current_results(self):
        w = self.window
        old = w.tokens.get('project', 0)
        w.invalidate('project')
        w.finished('project', old, None, 'stale failure')
        self.assertNotEqual(w.notice.text(), 'stale failure')
        w.query.setText('polling')
        w.search()
        old = w.tokens['search']
        w.query.setText('missing')
        w.finished('search', old, {'results': [], 'omitted': [], 'limits': 'stale'}, '')
        self.assertNotEqual(w.results_note.text(), 'stale')
        self.wait(lambda: w.results_title.text() == '0 search results')

    def test_history_and_overlay(self):
        w = self.window
        w.tabs.setCurrentIndex(2)
        self.wait(lambda: w.history_list.count() > 0)
        w.open_capture_item(w.history_list.item(0))
        self.wait(lambda: w.capture_id is not None)
        self.assertEqual(w.stack.currentIndex(), 2)
        self.assertIn('HISTORICAL', w.notice.text())
        w.back()
        self.assertEqual(w.stack.currentIndex(), 0)
        w.resize(1024, 700)
        w.tabs.setCurrentIndex(1)
        w.open_list_item(w.knowledge.item(0))
        self.wait(lambda: w.evidence_result is not None)
        self.assertIs(w.inspector.parent(), w)
        w.resize(1440, 900)
        self.app.processEvents()
        self.assertIs(w.inspector.parent(), w.split)

    def test_kind_filter_and_no_matches(self):
        w = self.window
        w.kind.setCurrentIndex(2)
        self.assertEqual(w.knowledge.count(), 1)
        self.assertIn('IDEA', w.knowledge.item(0).text())
        w.kind.setCurrentIndex(4)
        self.assertEqual(w.knowledge.count(), 0)
        self.assertIn('No items', w.knowledge_count.text())

    def test_project_switch_and_back_restore_filters(self):
        other = self.root / 'another'
        other.mkdir()
        (other / 'note.md').write_text('# Decision\nUse a different project for independent work.\n')
        second = self.brain.ingest(other)['project_id']
        w = self.window
        w.kind.setCurrentIndex(2)
        w.tabs.setCurrentIndex(1)
        w.reload()
        self.wait(lambda: w.data is not None and w.tabs.isEnabled() and w.project_list.count() == 2)
        self.assertEqual(w.kind.currentIndex(), 2)
        for index in range(w.project_list.count()):
            if w.project_list.item(index).data(Qt.UserRole) == second:
                w.project_list.setCurrentRow(index)
                break
        self.wait(lambda: w.data is not None and w.project_id == second)
        w.back()
        self.wait(lambda: w.data is not None and w.project_id == self.pid)
        self.assertEqual(w.kind.currentIndex(), 2)
        self.assertEqual(w.tabs.currentIndex(), 1)
        self.assertEqual(w.trail, [])

    def test_new_query_cancels_pending_history_view(self):
        w = self.window
        w.tabs.setCurrentIndex(2)
        self.wait(lambda: w.history_list.count() > 0)
        w.open_capture_item(w.history_list.item(0))
        old = w.tokens['capture']
        w.query.setText('polling')
        w.finished('capture', old, None, 'old capture failed')
        self.assertNotEqual(w.notice.text(), 'old capture failed')
        self.wait(lambda: w.results.count() == 1)
        self.assertEqual(w.stack.currentIndex(), 1)


    def test_reload_reexecutes_unchanged_search(self):
        w = self.window
        w.query.setText('polling')
        self.wait(lambda: w.results.count() == 1)
        w.reload()
        self.wait(lambda: w.tabs.isEnabled() and not w.jobs)
        self.wait(lambda: w.stack.currentIndex() == 1 and w.results.count() == 1)

    def test_clear_search_closes_its_evidence(self):
        w = self.window
        w.query.setText('polling')
        self.wait(lambda: w.results.count() == 1)
        w.open_list_item(w.results.item(0))
        self.wait(lambda: w.evidence_result is not None)
        w.query.clear()
        self.wait(lambda: w.stack.currentIndex() == 0)
        self.assertFalse(w.inspector.isVisible())

    def test_failed_store_switch_clears_previous_store_content(self):
        w = self.window
        w.project_filter.setText('source')
        w.query.setText('polling')
        self.wait(lambda: w.results.count() == 1)
        w.open_list_item(w.results.item(0))
        self.wait(lambda: w.evidence_result is not None)
        with patch('brain.desktop.QFileDialog.getExistingDirectory', return_value=str(self.root / 'missing')):
            w.choose_store()
        self.wait(lambda: not w.jobs)
        self.assertEqual(w.project_list.count(), 0)
        self.assertEqual(w.knowledge.count(), 0)
        self.assertEqual(w.overview_layout.count(), 0)
        self.assertEqual(w.title.text(), 'Your project memory')
        self.assertNotIn('Last capture', w.subtitle.text())
        self.assertEqual(w.project_filter.text(), '')
        self.assertEqual(w.query.text(), '')
        self.assertEqual(w.detail.toPlainText(), '')
        self.assertIsNone(w.evidence_result)
        self.assertIsNone(w.project_id)

    def test_search_scope_is_restored_per_project(self):
        other = self.root / 'another'
        other.mkdir()
        (other / 'note.md').write_text('# Decision\nUse another project for independent work.\n')
        second = self.brain.ingest(other)['project_id']
        w = self.window
        w.reload()
        self.wait(lambda: w.tabs.isEnabled() and w.project_list.count() == 2)
        w.scope.setCurrentIndex(1)
        w.technologies.setText('python')
        w.query.setText('polling')
        self.wait(lambda: w.results_title.text() == '0 search results')
        for i in range(w.project_list.count()):
            if w.project_list.item(i).data(Qt.UserRole) == second:
                w.project_list.setCurrentRow(i)
                break
        self.wait(lambda: w.data is not None and w.project_id == second)
        self.assertEqual(w.scope.currentIndex(), 0)
        w.back()
        self.wait(lambda: w.data is not None and w.project_id == self.pid)
        self.assertEqual(w.scope.currentIndex(), 1)
        self.assertEqual(w.technologies.text(), 'python')
        self.assertEqual(w.query.text(), 'polling')

    def test_typing_during_project_load_is_not_discarded(self):
        w = self.window
        original = w.reader.project
        def slow(pid):
            time.sleep(.15)
            return original(pid)
        with patch.object(w.reader, 'project', side_effect=slow):
            w.reload()
            self.wait(lambda: w.data is None)
            w.query.setText('batch')
            self.wait(lambda: w.data is not None)
            self.assertEqual(w.query.text(), 'batch')
            self.wait(lambda: w.results.count() == 1)
            self.assertIn('batch', w.results.item(0).text())


    def test_keyboard_search_open_and_escape(self):
        from PySide6.QtTest import QTest
        w = self.window
        w.activateWindow()
        w.raise_()
        self.app.processEvents()
        QTest.keyClick(w, Qt.Key_K, Qt.ControlModifier)
        self.assertTrue(w.query.hasFocus())
        QTest.keyClicks(w.query, 'polling')
        self.wait(lambda: w.results.count() == 1)
        w.results.setFocus()
        w.results.setCurrentRow(0)
        QTest.keyClick(w.results, Qt.Key_Return)
        self.wait(lambda: w.evidence_result is not None)
        QTest.keyClick(w, Qt.Key_Escape)
        self.assertFalse(w.inspector.isVisible())
        self.assertEqual(w.query.text(), 'polling')
        QTest.keyClick(w, Qt.Key_Left, Qt.AltModifier)
        self.assertEqual(w.query.text(), '')
        self.assertEqual(w.stack.currentIndex(), 0)

    def test_shared_search_opens_originating_projects_evidence(self):
        other = self.root / 'shared-source'
        other.mkdir()
        (other / 'shared.md').write_text('# Background\nPrivate preceding context.\n'
                                       '# Decision\nUse shared polling only with compatible labels.\n'
                                       '# Internal\nPrivate following context.\n')
        origin = self.brain.ingest(other)['project_id']
        record = self.reader.search(origin, 'polling')['results'][0]
        self.brain.promote(origin, record['id'], ['python'], 'Reviewed polling scope')
        w = self.window
        w.scope.setCurrentIndex(1)
        w.technologies.setText('python')
        w.query.setText('polling')
        self.wait(lambda: w.results.count() == 1)
        w.open_list_item(w.results.item(0))
        self.wait(lambda: w.evidence_result is not None)
        self.assertEqual(w.evidence_result['project_id'], origin)
        self.assertEqual(w.evidence.toPlainText(), record['statement'])
        self.assertFalse(w.previous_lines.isEnabled())
        self.assertFalse(w.next_lines.isEnabled())
        w.copy_excerpt.click()
        self.assertEqual(self.app.clipboard().text(), record['statement'])

        w.close_inspector()
        approval_path = self.store / 'shared' / (record['id'] + '.json')
        write(approval_path, dict(read(approval_path), review_after=0))
        w.open_list_item(w.results.item(0))
        self.wait(lambda: 'Sharing approval is unavailable' in w.evidence.toPlainText())
        self.assertNotIn(record['statement'], w.detail.toPlainText())
        self.assertIsNone(w.evidence_result)
        self.assertFalse(w.copy_excerpt.isEnabled())
        self.assertFalse(w.copy_citation.isEnabled())

    def test_evidence_paging_copy_and_retry_after_busy_writer(self):
        self.note.write_text('\n'.join(f'Line {i}: retained evidence' for i in range(1, 451)) + '\n')
        self.brain.ingest(self.source)
        snap = self.brain.snapshot(self.pid)
        source = next(f for f in snap['files'] if f['path'] == 'decision.md')
        claim = {'path': 'decision.md', 'snapshot': snap['id'], 'sha256': source['sha256'],
                 'start_line': 250, 'end_line': 252}
        before = self.fingerprint()
        w = self.window
        with self.brain.lock():
            w.show_item('Long retained source', [claim], {})
            self.wait(lambda: w.retry_evidence.isVisible())
            self.assertFalse(w.copy_excerpt.isEnabled())
        w.retry_evidence.click()
        self.wait(lambda: w.evidence_result is not None)
        self.assertEqual(len(w.evidence.extraSelections()), 3)
        first = w.evidence_result['start_line']
        w.copy_excerpt.click()
        self.assertEqual(self.app.clipboard().text(), w.evidence_result['text'])
        w.copy_citation.click()
        self.assertIn(snap['id'], self.app.clipboard().text())
        w.next_lines.click()
        self.wait(lambda: w.evidence_result is not None and w.evidence_result['start_line'] != first)
        self.assertEqual(w.evidence_result['end_line'], 450)
        self.assertFalse(w.next_lines.isEnabled())
        w.previous_lines.click()
        self.wait(lambda: w.evidence_result is not None and w.evidence_result['start_line'] == first)
        self.assertEqual(before, self.fingerprint())

    def test_historical_record_does_not_follow_new_capture(self):
        from PySide6.QtWidgets import QListWidget
        w = self.window
        original = w.data['snapshot']
        self.note.write_text('# Decision\nUse explicit refresh instead.\n')
        self.brain.ingest(self.source)
        w.tabs.setCurrentIndex(2)
        self.wait(lambda: w.history_list.count() == 2)
        row = next(w.history_list.item(i) for i in range(2)
                   if w.history_list.item(i).data(Qt.UserRole) == original)
        w.open_capture_item(row)
        self.wait(lambda: w.capture_id == original)
        records = w.capture_page.findChild(QListWidget)
        row = next(records.item(i) for i in range(records.count()) if 'polling' in records.item(i).text())
        records.itemActivated.emit(row)
        self.wait(lambda: w.evidence_result is not None)
        self.assertEqual(w.evidence_result['snapshot'], original)
        self.assertIn('partial writes', w.evidence_result['text'])
        self.assertIn('HISTORICAL', w.notice.text())

    def test_source_health_and_empty_store_are_visible(self):
        w = self.window
        w.tabs.setCurrentIndex(3)
        from PySide6.QtWidgets import QLabel
        labels = '\n'.join(l.text() for l in w.sources.findChildren(QLabel))
        self.assertIn(str(self.source), labels)
        self.assertIn('Last complete observation:', labels)
        empty = self.root / 'empty-store'
        initialize(empty)
        with patch('brain.desktop.QFileDialog.getExistingDirectory', return_value=str(empty)):
            w.choose_store()
        self.wait(lambda: not w.jobs)
        self.assertIn('empty', w.notice.text())
        self.assertEqual(w.project_list.count(), 0)
        self.assertEqual(w.knowledge.count(), 0)


if __name__ == '__main__':
    unittest.main()
