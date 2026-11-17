"""Native, read-only navigation for Project Brain (optional PySide6 extra)."""
import argparse
from datetime import datetime
import html
import os
from pathlib import Path
import sys

from .desktop_data import DesktopReader

try:
    from PySide6.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, QTimer, Signal, Slot
    from PySide6.QtGui import QColor, QFontDatabase, QIcon, QKeySequence, QShortcut, QTextCharFormat, QTextCursor
    from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFileDialog, QFrame,
        QHBoxLayout, QLabel, QLayout, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
        QPushButton, QScrollArea, QSplitter, QStackedWidget, QTabWidget, QTextBrowser,
        QTextEdit, QVBoxLayout, QWidget)
except ImportError:
    raise SystemExit('The Brain desktop needs PySide6. Install with: pip install ".[desktop]"')


STYLE = '''
QWidget { background: #141719; color: #eee9df; font-size: 13px; }
QFrame#Sidebar, QFrame#Sidebar QWidget { background: #101416; }
QFrame#Inspector, QFrame#Inspector QWidget { background: #1c2023; }
QLabel#Brand { color: #ffd58a; font-size: 22px; font-weight: bold; }
QLabel#Title { font-size: 25px; font-weight: bold; }
QLabel#Section { font-size: 16px; color: #ffd58a; }
QLabel#Muted { color: #a6afa9; }
QLabel#Notice { color: #ffd58a; background: #282a24; padding: 10px; border-radius: 5px; }
QLineEdit, QComboBox { background: #1c2023; border: 1px solid #343a3e;
 border-radius: 5px; padding: 8px; selection-background-color: #4e5a55; }
QLineEdit:focus, QComboBox:focus { border-color: #ffd58a; }
QPushButton { background: #1c2023; border: 1px solid #343a3e; border-radius: 4px; padding: 7px 10px; }
QPushButton:hover, QPushButton:focus { border-color: #ffd58a; color: #ffd58a; }
QPushButton:disabled { color: #85908b; }
QFrame#Card { background: #1c2023; border: 1px solid #343a3e; border-radius: 5px; }
QFrame#Card QLabel { background: transparent; border: none; }
QListWidget { border: none; outline: none; background: #141719; }
QListWidget::item { padding: 12px 9px; border-bottom: 1px solid #262d30; }
QListWidget::item:selected { background: #282a24; color: #ffd58a; border-left: 2px solid #ffd58a; }
QListWidget::item:hover { background: #252b2d; }
QTabWidget::pane { border: none; border-top: 1px solid #343a3e; }
QTabBar::tab { background: #141719; border: none; padding: 12px 16px; color: #a6afa9; }
QTabBar::tab:selected { color: #ffd58a; border-bottom: 2px solid #ffd58a; }
QTabBar::tab:focus { background: #282a24; }
QTextEdit, QTextBrowser { border: 1px solid #343a3e; border-radius: 4px; padding: 7px; selection-background-color: #4e5a55; }
QScrollArea { border: none; }
QScrollBar:vertical { width: 10px; background: #141719; }
QScrollBar::handle:vertical { background: #434943; min-height: 28px; border-radius: 4px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { height: 10px; background: #141719; }
QScrollBar::handle:horizontal { background: #434943; min-width: 28px; border-radius: 4px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QCheckBox::indicator { width: 14px; height: 14px; border: 1px solid #85908b; border-radius: 3px; background: #1c2023; }
QCheckBox::indicator:checked { background: #ffd58a; border-color: #ffd58a; }
QSplitter::handle { background: #343a3e; width: 1px; }
QToolTip { background: #101416; color: #eee9df; border: 1px solid #343a3e; }
'''


def date(value):
    if value is None:
        return 'Unknown'
    try:
        dt = datetime.fromisoformat(value) if isinstance(value, str) else datetime.fromtimestamp(value).astimezone()
        return dt.astimezone().strftime('%d %b %Y, %H:%M')
    except (ValueError, TypeError, OverflowError):
        return 'Unknown'


def words(value):
    return str(value).replace('_', ' ')


def label(text, name=None):
    widget = QLabel(str(text))
    widget.setTextFormat(Qt.PlainText)
    widget.setWordWrap(True)
    if name:
        widget.setObjectName(name)
    if name == 'Section':
        widget.setMinimumHeight(32)
    return widget


def page():
    widget = QWidget()
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(12)
    return widget, layout


def scroll_page():
    widget, layout = page()
    layout.setSizeConstraint(QLayout.SetMinimumSize)
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setWidget(widget)
    return scroll, layout


def clear(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().hide()
            item.widget().deleteLater()
        elif item.layout():
            clear(item.layout())


class Result(QObject):
    finished = Signal(str, int, object, str)


class ReadTask(QRunnable):
    def __init__(self, channel, token, function):
        super().__init__()
        self.channel, self.token, self.function = channel, token, function
        self.result = Result()

    @Slot()
    def run(self):
        try:
            value = self.function()
        except Exception as error:
            self.result.finished.emit(self.channel, self.token, None, str(error))
        else:
            self.result.finished.emit(self.channel, self.token, value, '')


class BrainWindow(QMainWindow):
    def __init__(self, root, settings=None):
        super().__init__()
        self.reader = DesktopReader(root)
        self.settings = settings if settings is not None else QSettings('ProjectBrain', 'Desktop')
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(3)
        self.tokens, self.callbacks, self.jobs = {}, {}, {}
        self.input_revision = 0
        self.project_id = None
        self.projects, self.data = {}, None
        self.recent = list(self.settings.value('recent', [], type=list))
        self.views = {}
        self.trail = []
        self.going_back = False
        self.claim = None
        self.evidence_result = None
        self.capture_id = None
        self.pending_capture = False
        self.setWindowTitle('The Brain')
        icon = Path(__file__).resolve().parent.parent / 'desktop/the-brain.svg'
        if icon.exists():
            self.setWindowIcon(QIcon(str(icon)))
        self.setMinimumSize(1024, 700)
        self.resize(1440, 900)
        self.setStyleSheet(STYLE)
        self.split = QSplitter()
        self.setCentralWidget(self.split)
        self.build_sidebar()
        self.build_workspace()
        self.build_inspector()
        self.split.setSizes([245, 805, 390])
        self.inspector.hide()
        for sequence, callback in [('Ctrl+K', self.focus_search), ('Alt+Left', self.back),
                                   ('Escape', self.close_inspector), ('Ctrl+R', self.reload)]:
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(callback)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)
        self.search_timer.timeout.connect(self.search)
        self.query.textChanged.connect(self.schedule_search)
        self.scope.currentIndexChanged.connect(self.schedule_search)
        self.technologies.textChanged.connect(self.schedule_search)
        geometry = self.settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        sizes = self.settings.value('panes', [], type=list)
        if len(sizes) == 3:
            self.split.setSizes([int(n) for n in sizes])
        self.reload()

    def button(self, text, callback):
        widget = QPushButton(text)
        widget.clicked.connect(callback)
        return widget

    def build_sidebar(self):
        side = QFrame()
        side.setObjectName('Sidebar')
        side.setMinimumWidth(205)
        side.setMaximumWidth(340)
        layout = QVBoxLayout(side)
        layout.setContentsMargins(18, 25, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(label('◈  THE BRAIN', 'Brand'))
        layout.addWidget(label('A place to pick up the thread.', 'Muted'))
        self.project_filter = QLineEdit()
        self.project_filter.setPlaceholderText('Filter projects…')
        self.project_filter.setAccessibleName('Filter projects')
        self.project_filter.textChanged.connect(self.filter_projects)
        layout.addWidget(self.project_filter)
        layout.addWidget(label('PROJECTS', 'Muted'))
        self.project_list = QListWidget()
        self.project_list.setAccessibleName('Projects')
        self.project_list.currentItemChanged.connect(self.select_project)
        layout.addWidget(self.project_list, 1)
        layout.addWidget(label('LOCAL  /  READ ONLY', 'Muted'))
        layout.addWidget(self.button('Choose Brain store…', self.choose_store))
        self.store_label = label(str(self.reader.root), 'Muted')
        self.store_label.setToolTip(str(self.reader.root))
        layout.addWidget(self.store_label)
        self.split.addWidget(side)

    def build_workspace(self):
        center, layout = page()
        header = QHBoxLayout()
        self.title = label('Your project memory', 'Title')
        header.addWidget(self.title, 1)
        header.addWidget(self.button('↶ Back', self.back))
        header.addWidget(self.button('↻ Reload', self.reload))
        layout.addLayout(header)
        self.subtitle = label('Choose a project to continue.', 'Muted')
        layout.addWidget(self.subtitle)
        search_row = QHBoxLayout()
        self.query = QLineEdit()
        self.query.setPlaceholderText('Search this project’s knowledge…   Ctrl+K')
        self.query.setAccessibleName('Search knowledge')
        search_row.addWidget(self.query, 1)
        self.scope = QComboBox()
        self.scope.addItems(['This project', 'Shared knowledge'])
        self.scope.setAccessibleName('Search scope')
        search_row.addWidget(self.scope)
        layout.addLayout(search_row)
        self.technologies = QLineEdit()
        self.technologies.setPlaceholderText('Required technology labels, comma separated — e.g. python:3.14, sqlite')
        self.technologies.setAccessibleName('Shared knowledge technology labels')
        self.technologies.hide()
        layout.addWidget(self.technologies)
        self.notice = label('Loading projects…', 'Notice')
        layout.addWidget(self.notice)
        self.stack = QStackedWidget()
        self.tabs = QTabWidget()
        self.overview, self.overview_layout = scroll_page()
        self.tabs.addTab(self.overview, 'Overview')
        knowledge, kl = page()
        filters = QHBoxLayout()
        self.kind = QComboBox()
        self.kind.addItems(['All kinds', 'Decisions', 'Ideas', 'Attempts', 'Blockers'])
        self.kind.setAccessibleName('Knowledge kind')
        self.kind.currentIndexChanged.connect(self.render_knowledge)
        filters.addWidget(self.kind)
        self.include_history = QCheckBox('Include superseded items')
        self.include_history.toggled.connect(self.render_knowledge)
        self.include_history.toggled.connect(self.schedule_search)
        filters.addWidget(self.include_history)
        filters.addStretch()
        kl.addLayout(filters)
        self.knowledge = QListWidget()
        self.knowledge.setWordWrap(True)
        self.knowledge.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.knowledge.itemActivated.connect(self.open_list_item)
        self.knowledge.itemClicked.connect(self.open_list_item)
        kl.addWidget(self.knowledge)
        self.knowledge_count = label('', 'Muted')
        kl.addWidget(self.knowledge_count)
        self.tabs.addTab(knowledge, 'Knowledge')
        history, hl = page()
        hl.addWidget(label('Capture history', 'Section'))
        hl.addWidget(label('Each capture preserves its own evidence. Missing files do not mean resolved work.', 'Muted'))
        self.history_list = QListWidget()
        self.history_list.itemClicked.connect(self.open_capture_item)
        self.history_list.itemActivated.connect(self.open_capture_item)
        hl.addWidget(self.history_list)
        self.tabs.addTab(history, 'History')
        self.sources, self.sources_layout = scroll_page()
        self.tabs.addTab(self.sources, 'Sources')
        self.tabs.currentChanged.connect(self.tab_changed)
        self.stack.addWidget(self.tabs)
        results, rl = page()
        self.results_title = label('Search results', 'Section')
        rl.addWidget(self.results_title)
        self.results = QListWidget()
        self.results.setWordWrap(True)
        self.results.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.results.itemClicked.connect(self.open_list_item)
        self.results.itemActivated.connect(self.open_list_item)
        rl.addWidget(self.results)
        self.results_note = label('', 'Muted')
        rl.addWidget(self.results_note)
        rl.addWidget(self.button('Clear search', self.query.clear))
        self.stack.addWidget(results)
        self.capture_page, self.capture_layout = scroll_page()
        self.stack.addWidget(self.capture_page)
        layout.addWidget(self.stack, 1)
        self.split.addWidget(center)
        self.split.setStretchFactor(1, 1)

    def build_inspector(self):
        self.inspector = QFrame()
        self.inspector.setObjectName('Inspector')
        self.inspector.setMinimumWidth(330)
        il = QVBoxLayout(self.inspector)
        il.setContentsMargins(16, 20, 16, 16)
        row = QHBoxLayout()
        row.addWidget(label('EVIDENCE & CONTEXT', 'Section'), 1)
        row.addWidget(self.button('×', self.close_inspector))
        il.addLayout(row)
        self.detail = QTextBrowser()
        self.detail.setOpenExternalLinks(False)
        self.detail.setAccessibleName('Item details and qualifications')
        il.addWidget(self.detail, 2)
        self.claims = QComboBox()
        self.claims.setAccessibleName('Supporting evidence')
        self.claims.currentIndexChanged.connect(self.load_evidence)
        il.addWidget(self.claims)
        self.citation = label('', 'Muted')
        self.citation.setTextInteractionFlags(Qt.TextSelectableByMouse)
        il.addWidget(self.citation)
        self.retry_evidence = self.button('Retry evidence', lambda: self.load_evidence(start=self.evidence_start))
        self.retry_evidence.hide()
        il.addWidget(self.retry_evidence)
        self.evidence = QTextEdit()
        self.evidence.setReadOnly(True)
        self.evidence.setLineWrapMode(QTextEdit.NoWrap)
        self.evidence.setAccessibleName('Retained source evidence with line numbers')
        il.addWidget(self.evidence, 3)
        paging = QHBoxLayout()
        self.previous_lines = self.button('Previous lines', lambda: self.page_evidence(-200))
        self.next_lines = self.button('Next lines', lambda: self.page_evidence(200))
        paging.addWidget(self.previous_lines)
        paging.addWidget(self.next_lines)
        il.addLayout(paging)
        copy_row = QHBoxLayout()
        self.copy_excerpt = self.button('Copy excerpt', self.copy_text)
        self.copy_citation = self.button('Copy citation', lambda: QApplication.clipboard().setText(self.citation.text()))
        copy_row.addWidget(self.copy_excerpt)
        copy_row.addWidget(self.copy_citation)
        il.addLayout(copy_row)
        self.split.addWidget(self.inspector)

    def request(self, channel, function, callback):
        token = self.tokens.get(channel, 0) + 1
        self.tokens[channel] = token
        self.callbacks[channel] = callback
        job = ReadTask(channel, token, function)
        self.jobs[(channel, token)] = job
        job.result.finished.connect(self.finished)
        self.pool.start(job)

    @Slot(str, int, object, str)
    def finished(self, channel, token, value, error):
        self.jobs.pop((channel, token), None)
        if self.tokens.get(channel) != token:
            return
        if error:
            if channel in ('evidence', 'record'):
                self.evidence.setPlainText('Evidence unavailable\n\n' + error)
                self.copy_excerpt.setEnabled(False)
                if channel == 'evidence':
                    self.retry_evidence.show()
            else:
                self.set_notice(error)
                if channel == 'search':
                    self.results_title.setText('Search unavailable')
                if channel == 'capture':
                    self.pending_capture = False
            return
        self.callbacks[channel](value)

    def invalidate(self, *channels):
        for channel in channels or tuple(self.tokens):
            self.tokens[channel] = self.tokens.get(channel, 0) + 1

    def set_notice(self, text):
        self.notice.setText(text)
        self.notice.setVisible(bool(text))

    def reload(self):
        self.save_view()
        self.reload_input_revision = self.input_revision
        self.invalidate()
        self.search_timer.stop()
        self.close_inspector()
        self.capture_id = None
        self.pending_capture = False
        self.data = None
        self.tabs.setEnabled(False)
        self.project_list.blockSignals(True)
        self.project_list.clear()
        self.project_list.blockSignals(False)
        self.knowledge.clear()
        self.history_list.clear()
        clear(self.overview_layout)
        clear(self.sources_layout)
        clear(self.capture_layout)
        self.results.clear()
        self.stack.setCurrentIndex(0)
        self.set_notice('Reading stored knowledge…')
        self.request('projects', self.reader.projects, self.loaded_projects)

    def loaded_projects(self, projects):
        self.projects = projects
        selected = self.project_id or self.settings.value('project', '')
        if self.project_id and self.input_revision != self.reload_input_revision:
            view = list(self.views.get(self.project_id, (0, '', 0, False, 0, 0, 0, '', 0, 0)))
            view[1], view[6], view[7] = self.query.text(), self.scope.currentIndex(), self.technologies.text()
            self.views[self.project_id] = tuple(view)
        self.project_list.blockSignals(True)
        self.project_list.clear()
        ordered = sorted(projects, key=lambda pid: (self.recent.index(pid) if pid in self.recent else 999,
                                                    projects[pid]['name'].lower()))
        target = None
        for pid in ordered:
            item = QListWidgetItem(projects[pid]['name'])
            item.setData(Qt.UserRole, pid)
            item.setToolTip('\n'.join(projects[pid].get('locations', [])))
            self.project_list.addItem(item)
            if pid == selected:
                target = item
        self.project_list.blockSignals(False)
        self.filter_projects(self.project_filter.text())
        self.project_id = None
        if projects:
            self.project_list.setCurrentItem(target or self.project_list.item(0))
        else:
            self.data = None
            self.knowledge.clear()
            self.history_list.clear()
            clear(self.overview_layout)
            clear(self.sources_layout)
            self.tabs.setEnabled(False)
            self.title.setText('Your project memory')
            self.subtitle.setText('No projects have been captured in this store.')
            self.set_notice('This Brain is empty. Choose a populated store, or use the existing Brain CLI to capture a project.')

    def filter_projects(self, text):
        for index in range(self.project_list.count()):
            item = self.project_list.item(index)
            item.setHidden(text.casefold() not in item.text().casefold())

    def save_view(self):
        if self.project_id and self.data is not None:
            self.views[self.project_id] = (self.tabs.currentIndex(), self.query.text(), self.kind.currentIndex(),
                                          self.include_history.isChecked(), self.knowledge.verticalScrollBar().value(),
                                          self.overview.verticalScrollBar().value(), self.scope.currentIndex(),
                                          self.technologies.text(), self.results.verticalScrollBar().value(),
                                          self.history_list.verticalScrollBar().value())

    def select_project(self, item, previous=None):
        if item is None:
            return
        pid = item.data(Qt.UserRole)
        if pid == self.project_id:
            return
        self.save_view()
        if self.project_id and not self.going_back:
            self.trail.append(self.project_id)
        self.invalidate()
        self.search_timer.stop()
        self.close_inspector()
        self.capture_id = None
        self.pending_capture = False
        self.project_id, self.data = pid, None
        self.recent = [pid] + [p for p in self.recent if p != pid][:19]
        self.title.setText(self.projects[pid]['name'])
        self.subtitle.setText('Loading last captured state…')
        self.set_notice('Reading project…')
        self.tabs.setEnabled(False)
        self.stack.setCurrentIndex(0)
        self.history_list.clear()
        self.knowledge.clear()
        self.results.clear()
        self.results_note.clear()
        clear(self.overview_layout)
        clear(self.sources_layout)
        clear(self.capture_layout)
        # Restore controls before starting I/O, so later typing is never overwritten.
        view = self.views.get(pid, (0, '', 0, False, 0, 0, 0, '', 0, 0))
        controls = (self.query, self.kind, self.include_history, self.scope, self.technologies, self.tabs)
        for control in controls:
            control.blockSignals(True)
        self.tabs.setCurrentIndex(view[0])
        self.query.setText(view[1])
        self.kind.setCurrentIndex(view[2])
        self.include_history.setChecked(view[3])
        self.scope.setCurrentIndex(view[6])
        self.technologies.setText(view[7])
        for control in controls:
            control.blockSignals(False)
        self.technologies.setVisible(view[6] == 1)
        self.request('project', lambda reader=self.reader: reader.project(pid), self.loaded_project)

    def loaded_project(self, value):
        self.data = value
        self.tabs.setEnabled(True)
        self.subtitle.setText('Last capture  ' + date(value['created_at']) + '   ·   Private project knowledge')
        self.set_notice('')
        self.render_briefing(self.overview_layout, value['briefing'])
        self.render_sources()
        view = self.views.get(self.project_id, (0, '', 0, False, 0, 0, 0, '', 0, 0))
        self.render_knowledge()
        self.tab_changed(self.tabs.currentIndex())
        self.search_timer.stop()
        self.search()
        pid, token = self.project_id, self.tokens.get('project')
        QTimer.singleShot(0, lambda: self.restore_scroll(view) if
                          (self.project_id, self.tokens.get('project')) == (pid, token) else None)

    def restore_scroll(self, view):
        self.knowledge.verticalScrollBar().setValue(view[4])
        self.overview.verticalScrollBar().setValue(view[5])

    def render_briefing(self, layout, briefing, historical=False):
        clear(layout)
        layout.addWidget(label('Historical capture' if historical else 'Where you left off', 'Title'))
        layout.addWidget(label('Recorded excerpts with supporting evidence. Capture does not establish completion or verification.', 'Muted'))
        for section in briefing['sections'].values():
            if not section['items']:
                continue
            layout.addWidget(label(section['title'], 'Section'))
            for entry in section['items']:
                text = ' '.join(entry['excerpt'].split())
                card = QFrame()
                card.setObjectName('Card')
                bl = QVBoxLayout(card)
                bl.setContentsMargins(12, 10, 12, 10)
                bl.addWidget(label(text[:360] + ('…' if len(text) > 360 else '')))
                bl.addWidget(label(words(entry['evidence_status']) + '  ·  ' + entry['evidence']['path'], 'Muted'))
                button = self.button('Open evidence →', lambda checked=False, e=entry: self.open_excerpt(e))
                button.setAccessibleName('Open evidence: ' + text[:120])
                bl.addWidget(button, 0, Qt.AlignRight)
                layout.addWidget(card)
            if section.get('omitted'):
                layout.addWidget(label(f"{section['omitted']} more excerpts omitted from this briefing; explore Knowledge or search.", 'Muted'))
        layout.addWidget(label('Capture coverage', 'Section'))
        coverage = briefing['coverage']
        layout.addWidget(label(f"{coverage['retained_paths']} retained paths · {coverage['warning_count']} capture warnings", 'Muted'))
        for reason, count in coverage.get('omitted_by_status', {}).items():
            layout.addWidget(label(f'{words(reason)}: {count}', 'Muted'))
        for reason, count in coverage.get('warning_reasons', {}).items():
            layout.addWidget(label(f'{words(reason)}: {count}', 'Muted'))
        for limitation in briefing.get('limitations', []):
            layout.addWidget(label('• ' + str(limitation), 'Muted'))
        suggestions = briefing.get('suggested_review_actions', [])
        if suggestions:
            layout.addWidget(label('Suggested review actions · not commitments', 'Section'))
            layout.addWidget(label('\n'.join(str(s) for s in suggestions), 'Muted'))
        if historical:
            layout.addWidget(label('Changes from recorded predecessor', 'Section'))
            changes = briefing['changes']
            if changes.get('available'):
                for kind, group in changes['groups'].items():
                    layout.addWidget(label(f"{words(kind)}: {group['count']}\n" + '\n'.join(group['paths']), 'Muted'))
                    if group.get('omitted'):
                        layout.addWidget(label(f"{group['omitted']} additional paths omitted.", 'Muted'))
            else:
                layout.addWidget(label(changes['reason'], 'Muted'))
        layout.addStretch()

    def render_knowledge(self, *args):
        self.knowledge.clear()
        if not self.data:
            return
        kind = ['', 'decision', 'idea', 'attempt', 'blocker'][self.kind.currentIndex()]
        items = self.data['state']['items'].values()
        chosen = [i for i in items if (not kind or i['kind'] == kind) and
                  (self.include_history.isChecked() or (i['currency'] != 'superseded' and not i.get('consolidated_into')))]
        chosen.sort(key=lambda i: (not i['reviewed'], i['kind'], i['id']))
        for item in chosen:
            claim = item['claims'][0] if item['claims'] else {}
            text = f"{words(item['kind']).upper()}  ·  {words(item['work_stage'])}  ·  {words(item['evidence_strength'])}\n"
            text += ' '.join(item['summary'].split())[:260] + '\n'
            text += f"{words(item['currency'])}  ·  {date(claim.get('observed_at'))}"
            row = QListWidgetItem(text)
            row.setData(Qt.UserRole, ('state', item))
            self.knowledge.addItem(row)
        coverage = self.data['state']['coverage']
        warnings = [words(k) for k, v in coverage.items() if v is True]
        self.knowledge_count.setText(f'{len(chosen)} items' + (' · Coverage: ' + ', '.join(warnings) if warnings else '') +
                                     (' · No items match these filters.' if not chosen else ''))

    def render_sources(self):
        clear(self.sources_layout)
        health = {s['source_id']: s for s in self.data['briefing'].get('source_health', [])}
        self.sources_layout.addWidget(label('Sources & capture health', 'Section'))
        for source in self.data['sources']:
            self.sources_layout.addWidget(label(source['location']))
            sid = source.get('id', source.get('source_id'))
            status = health.get(sid, {})
            self.sources_layout.addWidget(label('Last complete observation: ' + date(status.get('last_complete_at')) +
                '\nLatest attempt: ' + date(status.get('last_attempt_at')) + ' · ' + words(status.get('state', 'unknown')), 'Muted'))
            config = source['configuration']
            self.sources_layout.addWidget(label('Automatic capture: ' + ('Enabled' if config.get('enabled') else 'Disabled') +
                '\nExcluded paths: ' + (', '.join(config.get('excluded_paths', [])) or 'None') +
                '\nHistorical source: ' + ('Yes' if config.get('historical') else 'No'), 'Muted'))
            budgets = config.get('budgets', {})
            self.sources_layout.addWidget(label('Capture limits\n' + '\n'.join(
                f'{words(key).capitalize()}: {value:,}' for key, value in budgets.items()), 'Muted'))
            if status.get('configured_revision') != status.get('captured_revision'):
                self.sources_layout.addWidget(label('Source settings changed since the last capture.', 'Notice'))
        if not self.data['sources']:
            self.sources_layout.addWidget(label('No source configuration is recorded for this project.', 'Muted'))
        self.sources_layout.addStretch()

    def tab_changed(self, index):
        self.invalidate('capture')
        self.pending_capture = False
        if index == 2 and self.project_id and self.data:
            pid = self.project_id
            self.request('history', lambda: self.reader.history(pid), self.loaded_history)

    def loaded_history(self, rows):
        self.history_list.clear()
        for row in rows:
            item = QListWidgetItem(date(row['created_at']) + ('  ·  Latest' if row['active'] else '') + '\n' + row['snapshot'])
            item.setData(Qt.UserRole, row['snapshot'])
            self.history_list.addItem(item)
        view = self.views.get(self.project_id)
        if view:
            self.history_list.verticalScrollBar().setValue(view[9])

    def open_capture_item(self, item):
        pid, sid = self.project_id, item.data(Qt.UserRole)
        self.close_inspector()
        self.pending_capture = True
        self.set_notice('Loading historical capture…')
        self.request('capture', lambda: self.reader.capture(pid, sid), self.loaded_capture)

    def loaded_capture(self, value):
        self.pending_capture = False
        self.capture_id = value['snapshot']
        self.set_notice('HISTORICAL VIEW  ·  ' + date(value['created_at']) + '  ·  Use Back to return')
        self.render_briefing(self.capture_layout, value['briefing'], historical=True)
        # All records remain reachable even when briefing selection omits them.
        self.capture_layout.insertWidget(self.capture_layout.count() - 1, label('All captured records', 'Section'))
        records = QListWidget()
        records.setMinimumHeight(300)
        records.setWordWrap(True)
        for record in value['records']:
            row = QListWidgetItem(' '.join(record['statement'].split())[:220])
            row.setData(Qt.UserRole, ('record', {**record, 'snapshot': value['snapshot']}))
            records.addItem(row)
        records.itemClicked.connect(self.open_list_item)
        records.itemActivated.connect(self.open_list_item)
        self.capture_layout.insertWidget(self.capture_layout.count() - 1, records)
        self.stack.setCurrentIndex(2)

    def schedule_search(self, *args):
        self.input_revision += 1
        self.invalidate('search', 'capture')
        if self.pending_capture:
            self.set_notice('')
        self.pending_capture = False
        self.close_inspector()
        self.results.clear()
        self.results_note.clear()
        self.technologies.setVisible(self.scope.currentIndex() == 1)
        if self.query.text().strip():
            self.search_timer.start()
        else:
            self.search_timer.stop()
            self.search()

    def search(self):
        query = self.query.text().strip()
        if not query:
            self.stack.setCurrentIndex(2 if self.capture_id else 0)
            return
        if self.data is None:
            return  # Project completion will run the latest query.
        self.close_inspector()
        self.capture_id = None
        self.set_notice('')
        self.stack.setCurrentIndex(1)
        self.results.clear()
        self.results_note.clear()
        self.results_title.setText('Searching…')
        pid = self.project_id if self.scope.currentIndex() == 0 else None
        if pid is None and self.scope.currentIndex() == 0:
            self.results_title.setText('Select a project to search')
            return
        technologies = tuple(t.strip() for t in self.technologies.text().split(',') if t.strip()) if pid is None else ()
        if pid is None and not technologies:
            self.results_title.setText('Enter technology labels to search approved shared knowledge')
            self.results_note.setText('Shared retrieval requires labels matching the original sharing approval.')
            return
        history = self.include_history.isChecked()
        self.request('search', lambda reader=self.reader: reader.search(pid, query, technologies, history), self.loaded_search)

    def loaded_search(self, value):
        self.results_title.setText(f"{len(value['results'])} search results")
        for record in value['results']:
            name = self.projects.get(record['project_id'], {}).get('name', record['project_id'])
            row = QListWidgetItem(name + '  ·  ' + words(record['evidence_status']) + '\n' +
                                  ' '.join(record['statement'].split())[:320] + '\n' + record['evidence']['path'])
            row.setData(Qt.UserRole, ('record', record))
            self.results.addItem(row)
        self.results_note.setText((f"{len(value['omitted'])} results omitted by retrieval limits. " if value['omitted'] else '') +
            ('No matching retained knowledge. Try fewer or different words. ' if not value['results'] else '') + value['limits'])
        view = self.views.get(self.project_id)
        if view and (view[1], view[6], view[7]) == (self.query.text(), self.scope.currentIndex(), self.technologies.text()):
            self.results.verticalScrollBar().setValue(view[8])

    def open_list_item(self, row):
        kind, value = row.data(Qt.UserRole)
        if kind == 'state':
            relations = [r for r in self.data['state']['relationships'] if value['id'] in (r['from'], r['to'])]
            self.show_item(value['summary'], value['claims'], {**value, 'relationships': relations})
        else:
            self.show_record(value)

    def open_excerpt(self, entry):
        pid, sid, rid = self.project_id, entry['snapshot'], entry['record_id']
        self.show_item(entry['excerpt'], [], entry)
        self.request('record', lambda: self.reader.record(pid, sid, rid),
                     lambda record: self.show_record({**record, 'snapshot': sid}))

    def show_record(self, record):
        claim = {**record['evidence'], 'snapshot': record['snapshot'], 'record_id': record['id']}
        self.show_item(record['statement'], [claim], record, record['project_id'])

    def show_item(self, summary, claims, metadata, project_id=None):
        self.invalidate('record', 'evidence')
        self.detail_pid = project_id or self.project_id
        fields = [('kind', 'Kind'), ('work_stage', 'Work stage'), ('evidence_strength', 'Evidence strength'),
                  ('evidence_status', 'Evidence status'), ('currency', 'Currency'), ('purpose', 'Memory purpose'),
                  ('source_role', 'Source'), ('availability', 'Availability'), ('availability_reason', 'Qualification'),
                  ('retrieval_state', 'Retrieval state'), ('why', 'Retrieved because')]
        details = ['<p style="white-space:pre-wrap">' + html.escape(summary) + '</p><hr>']
        for key, title in fields:
            if key in metadata:
                details.append('<p><b>' + title + '</b><br>' + html.escape(words(metadata[key])) + '</p>')
        if 'reviewed' in metadata:
            details.append('<p><b>Interpretation</b><br>' + ('Explicitly reviewed' if metadata['reviewed'] else 'Automatic candidate · not an accepted commitment') + '</p>')
        for relation in metadata.get('relationships', []):
            other_id = relation['to'] if relation['from'] == metadata['id'] else relation['from']
            other = self.data['state']['items'].get(other_id, {}) if self.data else {}
            details.append('<p><b>' + html.escape(words(relation['kind'])) + '</b><br>' +
                           html.escape(other.get('summary', 'Related item outside this bounded view')) + '</p>')
        for verification in metadata.get('verified_behaviors', []):
            details.append('<p><b>Scoped verification</b></p>')
            for key in ('behavior', 'environment', 'source_revision', 'reviewer', 'rationale', 'applicability', 'limitation'):
                if key in verification:
                    details.append('<p><b>' + words(key).capitalize() + '</b><br>' + html.escape(str(verification[key])) + '</p>')
        details.append('<p>Recorded claims retain their original qualifications. Observation alone does not verify behavior.</p>')
        self.detail.setHtml(''.join(details))
        self.claims.blockSignals(True)
        self.claims.clear()
        for claim in claims:
            self.claims.addItem(claim['path'] + ':' + str(claim['start_line']), claim)
        self.claims.blockSignals(False)
        self.inspector.show()
        self.place_inspector()
        self.load_evidence()

    def place_inspector(self):
        if self.width() < 1250:
            if self.inspector.parent() is self.split:
                self.inspector.setParent(self)
            self.inspector.setGeometry(max(0, self.width() - 460), 0, 460, self.height())
            self.inspector.show()
            self.inspector.raise_()
        elif self.inspector.parent() is not self.split:
            self.split.addWidget(self.inspector)
            self.split.setSizes([235, max(430, self.width() - 635), 400])
            self.inspector.show()

    def load_evidence(self, *args, start=None):
        self.invalidate('evidence')
        self.evidence_start = start
        self.retry_evidence.hide()
        self.claim = self.claims.currentData()
        self.evidence_result = None
        self.evidence.clear()
        self.citation.clear()
        for button in (self.copy_excerpt, self.copy_citation, self.previous_lines, self.next_lines):
            button.setEnabled(False)
        if not self.claim:
            self.evidence.setPlainText('No retained evidence reference is available for this item.')
            return
        claim, pid = dict(self.claim), self.detail_pid
        self.evidence.setPlainText('Loading retained evidence…')
        self.request('evidence', lambda: self.reader.evidence(pid, claim, start), self.loaded_evidence)

    def loaded_evidence(self, value):
        self.evidence_result = value
        self.citation.setText(f"{value['path']}:{value['start_line']}–{value['end_line']}\nCaptured {date(value['created_at'])}\nSnapshot {value['snapshot']}\nProject {value['project_id']} · retained evidence")
        self.evidence.setPlainText('\n'.join(f'{i:5}  {line}' for i, line in enumerate(value['text'].splitlines(), value['start_line'])))
        highlights = []
        for line in range(max(self.claim['start_line'], value['start_line']), min(self.claim['end_line'], value['end_line']) + 1):
            selection = QTextEdit.ExtraSelection()
            selection.cursor = QTextCursor(self.evidence.document().findBlockByNumber(line - value['start_line']))
            selection.format.setBackground(QColor('#34392f'))
            selection.format.setProperty(QTextCharFormat.FullWidthSelection, True)
            highlights.append(selection)
        self.evidence.setExtraSelections(highlights)
        self.copy_excerpt.setEnabled(True)
        self.copy_citation.setEnabled(True)
        self.previous_lines.setEnabled(value['start_line'] > 1)
        self.next_lines.setEnabled(value['end_line'] < value['total_lines'])

    def page_evidence(self, offset):
        if self.evidence_result:
            self.load_evidence(start=max(1, self.evidence_result['start_line'] + offset))

    def copy_text(self):
        if self.evidence_result:
            text = self.evidence.textCursor().selectedText().replace('\u2029', '\n')
            QApplication.clipboard().setText(text or self.evidence_result['text'])

    def close_inspector(self):
        self.invalidate('evidence', 'record')
        self.inspector.hide()

    def back(self):
        if self.inspector.isVisible():
            self.close_inspector()
        elif self.capture_id or self.pending_capture:
            self.capture_id = None
            self.pending_capture = False
            self.invalidate('capture')
            self.stack.setCurrentIndex(0)
            self.set_notice('')
        elif self.query.text():
            self.query.clear()
        elif self.trail:
            pid = self.trail.pop()
            for i in range(self.project_list.count()):
                item = self.project_list.item(i)
                if item.data(Qt.UserRole) == pid:
                    if item.isHidden():
                        self.project_filter.clear()
                    self.going_back = True
                    self.project_list.setCurrentItem(item)
                    self.going_back = False
                    break

    def focus_search(self):
        self.query.setFocus()
        self.query.selectAll()

    def choose_store(self):
        path = QFileDialog.getExistingDirectory(self, 'Choose an existing Brain store', str(self.reader.root))
        if path:
            self.save_view()
            self.reader = DesktopReader(path)
            self.project_id, self.data = None, None
            self.views.clear()
            self.trail.clear()
            self.store_label.setText(path)
            self.store_label.setToolTip(path)
            self.reload()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'inspector') and self.inspector.isVisible():
            self.place_inspector()

    def closeEvent(self, event):
        self.invalidate()
        self.search_timer.stop()
        self.settings.setValue('geometry', self.saveGeometry())
        if self.inspector.parent() is self.split and self.inspector.isVisible():
            self.settings.setValue('panes', self.split.sizes())
        self.settings.setValue('project', self.project_id or '')
        self.settings.setValue('recent', self.recent)
        self.settings.setValue('store', str(self.reader.root))
        self.pool.clear()
        self.pool.waitForDone()
        super().closeEvent(event)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Read-only desktop navigation for The Brain')
    parser.add_argument('--brain', help='Existing Brain store; never created or upgraded by the desktop')
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName('The Brain')
    app.setDesktopFileName('the-brain')
    app.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
    settings = QSettings('ProjectBrain', 'Desktop')
    root = args.brain or os.environ.get('PROJECT_BRAIN_HOME') or settings.value('store') or str(Path.cwd() / 'Project-Brain')
    window = BrainWindow(root, settings)
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
