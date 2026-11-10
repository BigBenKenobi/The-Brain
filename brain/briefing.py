"""Read-only, deterministic evidence briefings; never inferred completion claims."""
from collections import Counter
from datetime import datetime, timezone
import re


SECTIONS = {
    'objectives': 'Objective candidates',
    'ideas': 'Ideas and proposals',
    'decisions': 'Decision and rationale excerpts',
    'problems': 'Problem and constraint excerpts',
    'attempts': 'Attempted and discarded approaches',
    'next_actions': 'Recorded next-step statements (currency unreviewed)',
    'outcomes': 'Reported outcomes and lessons',
    'implementation': 'Observed source code (not verified functionality)',
    'historical': 'Historical reference excerpts',
    'unavailable': 'Previously retained context now unavailable (resolution unknown)',
}


HEADING_SIGNALS = {
    'objectives': r'objective|north star|mission|product direction|core user experience|memory policy',
    'ideas': r'idea|proposal|proposed',
    'attempts': r'failed approach|discarded|rejected|attempt',
    'next_actions': r'next|remaining|unfinished|backlog|pending',
    'problems': r'known issue|blocker|problem|constraint|limitation',
    'decisions': r'decision|rationale',
    'outcomes': r'outcome|lesson|solution|validation|test receipt',
}


def heading_section(record):
    lines = record['statement'].lstrip().splitlines()
    heading = lines[0].lstrip('# ').lower() if lines and lines[0].startswith('#') else ''
    return next((key for key, pattern in HEADING_SIGNALS.items() if re.search(pattern, heading)), None)


def classify(record):
    """Presentation candidates, never a transition of canonical claim status."""
    kinds = set(record.get('knowledge_kinds', []))
    if record.get('source_role') == 'historical_copy':
        return ('historical', 'Explicit historical source; currency is not inferred') if kinds or heading_section(record) else None
    # Strings in source code describing proposals are not project proposals.
    if record.get('source_role') == 'implementation':
        return 'implementation', 'Source code was observed; execution and completion are unknown'
    if not narrative_lines(record):
        return None
    explicit = heading_section(record)
    if explicit == 'objectives':
        return explicit, 'Source heading describes an objective or guiding policy; excerpt is not a verified state'
    if record['evidence_status'] == 'proposal':
        return 'ideas', 'Source is labelled proposal or untested; adoption is unknown'
    if explicit:
        return explicit, 'Explicit source heading; recorded wording is not independently verified'
    text = record['statement']
    if re.search(r'(?im)^next (?:implementation|step|action)', text):
        return 'next_actions', 'Source records a next step; adoption and completion remain unknown'
    if kinds & {'unresolved', 'limitation'}:
        return 'problems', 'Source contains unresolved-work or limitation language'
    if 'decision' in kinds:
        return 'decisions', 'Source contains decision or rationale language'
    if kinds & {'solution', 'lesson'}:
        return 'outcomes', 'Source reports a solution or lesson; outcome is unverified'
    if re.search(r'\b(objective|north star|mission|goal|should)\b', text, re.I):
        return 'objectives', 'Source describes a possible objective; normative wording is not a commitment'
    if re.search(r'\b(idea|ideas|proposed|proposal)\b', text, re.I):
        return 'ideas', 'Source mentions an idea or proposal; adoption is unknown'
    return None


def narrative_lines(record):
    lines = [line.strip() for line in record['statement'].splitlines() if line.strip()]
    return [line for line in lines if not line.startswith(('#', '|', '```', 'python', '$', 'git '))
            and not re.match(r'^\*{0,2}(status|date|updated|project root|chat):', line, re.I)]


def quality(record):
    lines = [line.strip() for line in record['statement'].splitlines() if line.strip()]
    narrative = narrative_lines(record)
    body = sum(len(line) for line in narrative)
    commands = sum(line.startswith(('python', '$', 'git ', '```', '|')) for line in lines)
    return (-bool(heading_section(record)), -(body >= 60), commands,
            record['evidence']['path'], record['evidence']['start_line'], record['id'])


def select_diverse(records, limit):
    """Prefer explicit substantive excerpts, then broaden source representation."""
    ranked = sorted(records, key=quality)
    selected, seen_text, path_counts = [], set(), Counter()
    while ranked and len(selected) < limit:
        best = min(ranked, key=lambda r: (path_counts[r['evidence']['path']], quality(r)))
        ranked.remove(best)
        fingerprint = ' '.join(best['statement'].split())
        if fingerprint in seen_text:
            continue
        selected.append(best)
        seen_text.add(fingerprint)
        path_counts[best['evidence']['path']] += 1
    return selected


def excerpt_item(record, snapshot, reason):
    return {
        'record_id': record['id'], 'snapshot': snapshot['id'],
        'excerpt': record['statement'][:400], 'excerpt_truncated': len(record['statement']) > 400,
        'evidence': dict(record['evidence']), 'evidence_status': record['evidence_status'],
        'source_role': record.get('source_role', 'unknown'), 'selection_reason': reason,
        'consolidated_from': record.get('consolidated_from'),
        'observed_at': next((f.get('observed_at') for f in snapshot['files'] if f['path'] == record['evidence']['path'] and f.get('sha256') == record['evidence']['sha256']), None),
    }


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
    obsolete = {edge['older'] for edge in current.get('relations', [])}
    suppressed = 0
    candidates = {key: [] for key in SECTIONS}
    reasons = {}
    for record in current['records']:
        if record['id'] in obsolete:
            suppressed += 1
            continue
        classification = classify(record)
        if classification is None:
            unselected += 1
            continue
        key, reason = classification
        candidates[key].append(record)
        reasons[record['id']] = reason
    for key, records in candidates.items():
        chosen = select_diverse(records, limit)
        sections[key]['items'] = [excerpt_item(r, current, reasons[r['id']]) for r in chosen]
        sections[key]['omitted'] = len(records) - len(chosen)
    if previous is not None:
        retained_paths = {f['path'] for f in current['files'] if f['status'] in ('retained', 'duplicate')}
        prior_obsolete = obsolete | {e['older'] for e in previous.get('relations', [])}
        missing = [r for r in previous['records'] if r['evidence']['path'] not in retained_paths
                   and r['id'] not in prior_obsolete and classify(r)
                   and classify(r)[0] in ('problems', 'attempts', 'decisions', 'next_actions')]
        chosen = select_diverse(missing, limit)
        sections['unavailable']['items'] = [excerpt_item(r, previous,
            'Previously retained evidence is absent from this capture; cause and resolution remain unknown') for r in chosen]
        sections['unavailable']['omitted'] = len(missing) - len(chosen)
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
        'corrections': {'suppressed_obsolete_records': suppressed,
                        'policy': 'Explicit correction links suppress obsolete excerpts; missing replacements do not restore obsolete claims.'},
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
    lines += ['', '## Source capture health']
    if not briefing.get('source_health'):
        lines += ['Unknown: no attributable source observation metadata.']
    for source in briefing.get('source_health', []):
        lines += [f"Source {source['source_id']}: {source['state']}; last attempt {source['last_attempt_at']}; last complete observation {source['last_complete_at']}; configured/captured revision {source['configured_revision']}/{source['captured_revision']}."]
    lines += ['', '## Coverage', f"Retained paths: {coverage['retained_paths']}; warnings: {coverage['warning_count']}",
              'Omitted inventory entries by status: ' + str(coverage['omitted_by_status']),
              'Warning reasons: ' + str(coverage['warning_reasons']),
              f"Records without a briefing signal: {coverage['records_without_briefing_signal']}",
              f"Obsolete records suppressed by explicit corrections: {briefing['corrections']['suppressed_obsolete_records']}",
              '', '## Limits', *('- ' + item for item in briefing['limitations']),
              '', '## Suggested review actions (not recorded commitments)',
              *('- ' + item for item in briefing['suggested_review_actions'])]
    return '\n'.join(lines)
