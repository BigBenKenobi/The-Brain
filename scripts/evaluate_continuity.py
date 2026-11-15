"""Reproducible B06 evidence pilot. Never execute discovered source scripts.

The sole executed test command is explicitly defined here against this checkout.
Answer keys and reports live outside the ingestion directory. A synthetic held-out
case tests generalisation; it is not a second real-project acceptance trial.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from brain.core import Brain, initialize
from brain.briefing import render_briefing

MAIN = '773a803a0a9939cc4fd33a7ae5c937d57a781d34'
DRAFT = 'dba69ef01233278fe847541966a65419fd18807f'
SELECTED = ('README.md', 'docs/vision.md', 'brain/core.py', 'pyproject.toml')


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def history(repo, revision, path):
    return subprocess.check_output(['git', '-C', str(repo), 'show', revision + ':' + path])


def put(source, path, data):
    dest = source / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data if isinstance(data, bytes) else data.encode())


def selected_items(briefing):
    return [i for section in briefing['sections'].values() for i in section['items']]


def assess(brain, pid, expectations):
    briefing = brain.briefing(pid)
    items = selected_items(briefing)
    checks = []
    for item in items:
        e = item['evidence']
        retained = brain.retained_evidence(pid, e['path'], e['start_line'], e['end_line'], item['snapshot'])
        checks.append(item['excerpt'] in retained['text'])
    expected = []
    for label, phrase in expectations.items():
        matches = [i for i in items if phrase.casefold() in i['excerpt'].casefold()]
        searchable = brain.retrieve(phrase, pid, limit=5)
        expected.append({'label': label, 'phrase': phrase, 'surfaced': bool(matches),
                         'selected_records': [i['record_id'] for i in matches], 'context_retrievable': bool(searchable)})
    text = json.dumps(briefing)
    fingerprints = [' '.join(i['excerpt'].split()) for i in items]
    return briefing, {'traceability': all(checks), 'selected_count': len(items),
        'repeated_excerpts': len(fingerprints) - len(set(fingerprints)),
        'expectations': expected, 'critical_hits': sum(e['surfaced'] for e in expected),
        'critical_total': len(expected),
        'unrelated_private_canary_absent': 'PRIVATE_CANARY_JUNIPER' not in text,
        'statuses_not_elevated': all(i['evidence_status'] in ('proposal', 'historical_record', 'observed_implementation') for i in items),
        'semantic_accuracy': 'Requires manual evidence review; phrase checks alone do not prove meaning or completeness.'}


def capture(brain, source, out, label, expectations, **kwargs):
    started = time.monotonic()
    result = brain.ingest(source, **kwargs)
    briefing, evaluation = assess(brain, result['project_id'], expectations)
    evaluation.update({'elapsed_seconds': round(time.monotonic()-started, 6), 'metrics': result['metrics'],
                       'snapshot': result['snapshot'], 'project_id': result['project_id'],
                       'source_id': result['source_id'],
                       'store_bytes': sum(p.stat().st_size for p in brain.root.rglob('*') if p.is_file())})
    save(out / (label + '-briefing.json'), briefing)
    (out / (label + '-briefing.md')).write_text(render_briefing(briefing) + '\n')
    return evaluation


def run(output, repo):
    # Read and verify exact public revisions before creating any output directory.
    initial = {p: history(repo, MAIN, p) for p in SELECTED}
    draft = {p: history(repo, DRAFT, p) for p in (*SELECTED, 'brain/briefing.py')}
    output.mkdir(parents=True, exist_ok=False)
    source = output / 'source'
    source.mkdir()
    initialize(output / 'store')
    brain = Brain(output / 'store')
    private = output / 'unrelated'
    private.mkdir()
    put(private, 'README.md', 'Decision: PRIVATE_CANARY_JUNIPER must never appear in another project briefing.\n')
    brain.ingest(private)
    expectations = {
        '01-main': {'continuity objective': 'switching between projects'},
        '02-briefing-pr': {'continuity objective': 'switching between projects', 'purposeful memory': 'Preserve nothing without a reason'},
        '03-local': {'duplicate correction': 'duplicate promoted', 'future work': 'B06',
                     'failed approach': 'duplicate-only inventory', 'unfinished idea': 'local semantic extraction',
                     'attributable run': 'Executed test receipt'},
    }
    save(output / 'answer-key.json', expectations)
    checkpoints = {}
    for path, data in initial.items():
        put(source, path, data)
    checkpoints['01-main'] = capture(brain, source, output, '01-main', expectations['01-main'])
    for path, data in draft.items():
        put(source, path, data)
    checkpoints['02-briefing-pr'] = capture(brain, source, output, '02-briefing-pr', expectations['02-briefing-pr'])
    for path in (*SELECTED, 'brain/briefing.py', 'brain/sources.py', 'docs/development-status.md', 'docs/development-plan.md'):
        put(source, path, (ROOT / path).read_bytes())
    # Attributable test run against the owning checkout, not scripts discovered by ingestion.
    command = [sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v']
    started = time.time()
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
    tracked = sorted([*ROOT.joinpath('brain').glob('*.py'), *ROOT.joinpath('tests').glob('test*.py')])
    receipt = {'command': command, 'cwd': str(ROOT), 'python': platform.python_version(),
               'started_at': started, 'finished_at': time.time(), 'returncode': result.returncode,
               'base_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'working_tree_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in tracked},
               'stdout': result.stdout, 'stderr': result.stderr}
    save(output / 'test-receipt.json', receipt)
    put(source, 'validation/test-receipt.md', '# Executed test receipt\n\nSolution validation: an explicitly invoked unittest run completed.\n'
        + 'This is a captured execution receipt scoped to the command and hashed working tree; it does not verify the whole product.\n'
        + json.dumps(receipt, indent=2) + '\n')
    put(source, 'history/capture-review.md', '''# Decision and rationale
Use the prior retained inventory disposition as the extraction-cache completion signal.
A duplicate promoted to the surviving path must be extracted. Empty retained files may cache no records.

# Failed approach
Agent report from the 10 November implementation session: duplicate-only inventory
was reused as an empty extraction cache. Removal and exclusion regression cases failed
before the repair. This account is reported evidence; the original failing terminal
run is not an independently captured receipt in this corpus.

# Unfinished idea
The development plan proposes local semantic extraction after evidence contracts and
evaluation. This remains a proposal; deterministic capture works without a model.
''')
    checkpoints['03-local'] = capture(brain, source, output, '03-local', expectations['03-local'])
    sid, pid = checkpoints['03-local']['source_id'], checkpoints['03-local']['project_id']
    before_bytes = checkpoints['03-local']['store_bytes']
    checkpoints['04-unchanged'] = capture(brain, source, output, '04-unchanged', expectations['03-local'])
    checkpoints['04-unchanged']['growth_bytes'] = checkpoints['04-unchanged']['store_bytes'] - before_bytes
    unavailable = output / 'source-unavailable'
    source.rename(unavailable)
    try:
        brain.refresh(sid)
    except OSError:
        pass
    else:
        raise AssertionError('Missing source unexpectedly refreshed')
    outage = brain.briefing(pid)
    save(output / '05-outage-briefing.json', outage)
    resilience = {'last_snapshot_preserved': outage['snapshot'] == checkpoints['04-unchanged']['snapshot'],
                  'failure_visible': any(s['state']=='failed' for s in outage['source_health'])}
    unavailable.rename(source)
    # Held-out synthetic domain: distinct terms and ordering; no rules tuned to these names.
    held = output / 'held-out-source'
    held.mkdir()
    put(held, 'z-decision.md', '# Decision\nUse kiln temperature logs because glaze defects depend on thermal drift.\n')
    put(held, 'a-background.md', '# Background\nA ceramics workshop prepares samples.\n' * 12)
    put(held, 'blocker.md', '# Known issue\nUnresolved blocker: the kiln thermocouple is intermittent.\n')
    put(held, 'idea.md', '# Proposed idea\nUntested infrared monitoring for glaze trials.\n')
    held_key = {'decision rationale': 'thermal drift', 'unresolved blocker': 'thermocouple', 'proposal': 'infrared monitoring'}
    save(output / 'held-out-answer-key.json', held_key)
    checkpoints['06-held-out'] = capture(brain, held, output, '06-held-out', held_key)
    held_pid=checkpoints['06-held-out']['project_id']
    (held / 'blocker.md').unlink()
    brain.ingest(held)
    deletion = brain.briefing(held_pid)
    save(output/'07-missing-blocker-briefing.json',deletion)
    resilience['missing_blocker_does_not_assert_resolution'] = ('does not prove deletion or completed work' in deletion['changes']['interpretation'])
    report={'real_history_revisions':[MAIN,DRAFT], 'current_working_tree':receipt['working_tree_sha256'],
            'checkpoints':checkpoints,'resilience':resilience,'executed_tests_passed':result.returncode==0,
            'human_resumption_measurement':{'baseline_seconds':None,'brain_seconds':None,'status':'pending actual owner return'},
            'limitations':['Critical-hit checks are lexical screens, not a semantic accuracy certificate.',
                'The held-out ceramics case is synthetic, not a second real-project pilot.',
                'The task-history supplement is an agent-authored report with explicit limits.',
                'Timing measures capture/assessment cost, not human resumption effort.']}
    save(output / 'report.json',report)
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--history-repo',type=Path,default=ROOT)
    args=parser.parse_args()
    result=run(args.output.resolve(),args.history_repo.resolve())
    print(json.dumps({'report':str(args.output/'report.json'),
        'critical_hits':{k:[v['critical_hits'],v['critical_total']] for k,v in result['checkpoints'].items()},
        'resilience':result['resilience'],'tests_passed':result['executed_tests_passed']},indent=2))
