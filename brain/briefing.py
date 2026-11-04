"""Read-only, deterministic evidence briefings; never inferred completion claims."""
from collections import Counter
from datetime import datetime, timezone
import re


SECTIONS = {
    'objectives': 'Objective candidates',
    'ideas': 'Ideas and proposals',
    'decisions': 'Decision and rationale excerpts',
    'problems': 'Problem and constraint excerpts',
    'outcomes': 'Reported outcomes and lessons',
    'implementation': 'Observed source code (not verified functionality)',
    'historical': 'Historical reference excerpts',
}


def classify(record):
    """Presentation reasons only; these do not change canonical memory or status."""
    kinds = set(record.get('knowledge_kinds', []))
    if record.get('source_role') == 'historical_copy':
        if kinds or record['evidence_status'] == 'proposal':
            return 'historical', 'Historical source contains an explicit knowledge signal'
        return None
    if record['evidence_status'] == 'proposal':
        return 'ideas', 'Source is explicitly labelled proposal or untested'
    if record.get('source_role') == 'implementation':
        return 'implementation', 'Source code was observed; execution and completion are unknown'
    text = record['statement']
    if re.search(r'\b(idea|ideas|proposed|proposal)\b', text, re.I):
        return 'ideas', 'Source mentions an idea or proposal; adoption is unknown'
    if kinds & {'unresolved', 'limitation'}:
        return 'problems', 'Source contains unresolved-work or limitation language'
    if 'decision' in kinds:
        return 'decisions', 'Source contains decision or rationale language'
    if kinds & {'solution', 'lesson'}:
        return 'outcomes', 'Source reports a solution or lesson; outcome is unverified'
    if re.search(r'\b(objective|north star|mission|goal)\b', text, re.I):
        return 'objectives', 'Source explicitly describes a possible project objective'
    return None


def changes(current, previous):
    if previous is None:
        return {'available': False, 'reason': 'No recorded predecessor; first or legacy snapshot. No baseline is guessed.'}
    before = {f['path']: f['sha256'] for f in previous['files'] if f['status'] in {'retained', 'duplicate'}}
    after = {f['path']: f['sha256'] for f in current['files'] if f['status'] in {'retained', 'duplicate'}}
    groups = {
        'newly_retained': sorted(after.keys() - before.keys()),
        'content_changed': sorted(p for p in after.keys() & before.keys() if after[p] != before[p]),
        'no_longer_retained': sorted(before.keys() - after.keys()),
    }
    return {
        'available': True, 'baseline_snapshot': previous['id'],
        'groups': {key: {'count': len(paths), 'paths': paths[:20], 'omitted': max(0, len(paths) - 20)}
                   for key, paths in groups.items()},
        'scope_changed': any(current.get(k) != previous.get(k) for k in
                             ('excluded_paths', 'processing_budgets', 'historical', 'consolidation')),
        'interpretation': 'Retained-text differences only. Missing evidence can reflect exclusions, budgets or unreadable files; it does not prove deletion or completed work.',
    }


def build_briefing(name, current, previous=None, limit=3):
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError('Briefing limit must be between 1 and 20')
    sections = {key: {'title': title, 'items': [], 'omitted': 0} for key, title in SECTIONS.items()}
    unselected = 0
    # Source order is deterministic; it is not an importance or activity ranking.
    for record in sorted(current['records'], key=lambda r: (r['evidence']['path'], r['evidence']['start_line'], r['id'])):
        classification = classify(record)
        if classification is None:
            unselected += 1
            continue
        key, reason = classification
        section = sections[key]
        if len(section['items']) >= limit:
            section['omitted'] += 1
            continue
        section['items'].append({
            'record_id': record['id'], 'snapshot': current['id'],
            'excerpt': record['statement'][:400], 'excerpt_truncated': len(record['statement']) > 400,
            'evidence': dict(record['evidence']), 'evidence_status': record['evidence_status'],
            'source_role': record.get('source_role', 'unknown'), 'selection_reason': reason,
            'consolidated_from': record.get('consolidated_from'),
        })
    omissions = Counter(f['status'] for f in current['files'] if f['status'] not in {'retained', 'duplicate'})
    limitations = [
        'This describes the last captured evidence, not live workstation activity. Snapshot publication time is not source freshness.',
        'Sections are lexical candidates, not reconciled facts. Negation, superseded decisions and contradictions require review.',
        'Current activity, exact completion stage and independent test results are unknown.',
        'Selection reasons explain this briefing only. All previously retained evidence remains stored; no forgetting policy is implemented.',
    ]
    if current.get('historical'):
        limitations.append('This entire capture is marked historical; it must not be treated as current project state.')
    suggestions = ['Review the cited objective and decision evidence before choosing the next development task.']
    if omissions or current['coverage_warnings']:
        suggestions.append('Inspect ingestion omissions and coverage warnings before relying on completeness.')
    if current.get('consolidation'):
        limitations.append('Consolidated supplements are pinned historical observations; publishing this snapshot did not refresh their sources.')
    return {
        'briefing_version': 1, 'project_id': current['project_id'], 'project_name': name,
        'snapshot': current['id'], 'snapshot_published_at': datetime.fromtimestamp(current['created_at'], timezone.utc).isoformat(),
        'historical_capture': current.get('historical', False), 'sections': sections,
        'changes': changes(current, previous),
        'coverage': {'retained_paths': sum(f['status'] in {'retained', 'duplicate'} for f in current['files']),
                     'omitted_by_status': dict(sorted(omissions.items())),
                     'warning_count': len(current['coverage_warnings']),
                     'warning_reasons': dict(Counter(w.get('reason', 'unknown') for w in current['coverage_warnings'])),
                     'records_without_briefing_signal': unselected},
        'limitations': limitations, 'suggested_review_actions': suggestions,
    }


def render_briefing(briefing):
    lines = [f"# {briefing['project_name']} — evidence briefing", '',
             f"Snapshot: {briefing['snapshot']}", f"Published: {briefing['snapshot_published_at']}", '',
             'Last captured evidence; not a live status or verified completion report.', '']
    for section in briefing['sections'].values():
        lines += ['## ' + section['title']]
        if not section['items']:
            lines += ['Unknown: no matching excerpt selected.']
        for item in section['items']:
            e = item['evidence']
            lines += ['\n'.join('> ' + line for line in item['excerpt'].splitlines()) + (' …' if item['excerpt_truncated'] else ''),
                      f"Evidence: {e['path']}:{e['start_line']}-{e['end_line']} ({item['evidence_status']}); record {item['record_id']}",
                      'Included because: ' + item['selection_reason']]
            if item['consolidated_from']:
                origin = item['consolidated_from']
                lines += [f"Pinned supplement: {origin['project_id']} / {origin['snapshot']} / {origin['path']}"]
        if section['omitted']:
            lines += [f"{section['omitted']} further matching excerpts omitted by the display limit."]
        lines += ['']
    delta = briefing['changes']
    lines += ['## Changes in retained evidence']
    if not delta['available']:
        lines += [delta['reason']]
    else:
        lines += ['Compared with: ' + delta['baseline_snapshot'], delta['interpretation']]
        for key, group in delta['groups'].items():
            lines += [f"{key}: {group['count']}" + (': ' + ', '.join(group['paths']) if group['paths'] else '')]
            if group['omitted']:
                lines += [f"{group['omitted']} additional paths omitted."]
        if delta['scope_changed']:
            lines += ['Capture scope, budgets, historical flag or supplement pins changed.']
    coverage = briefing['coverage']
    lines += ['', '## Coverage', f"Retained paths: {coverage['retained_paths']}; warnings: {coverage['warning_count']}",
              'Omitted inventory entries by status: ' + str(coverage['omitted_by_status']),
              'Warning reasons: ' + str(coverage['warning_reasons']),
              f"Records without a briefing signal: {coverage['records_without_briefing_signal']}",
              '', '## Limits', *('- ' + item for item in briefing['limitations']),
              '', '## Suggested review actions (not recorded commitments)',
              *('- ' + item for item in briefing['suggested_review_actions'])]
    return '\n'.join(lines)
