"""Evidence-backed project items and reversible, explicit interpretation events.

Automatic candidates never certify commitments, resolution, or verified behavior.
The journal is separate from capture snapshots, so older capture writers cannot
silently discard reviewed state. Read operations never mutate the store.
"""
from copy import deepcopy
import re
import time
import uuid
from .core import digest, read, write, validate, SECRET
from .briefing import configuration_source
from .verification import load_bundle, validate_bundle, subject

KINDS = {'decision', 'idea', 'attempt', 'blocker'}
STAGES = {'proposed', 'accepted', 'in_progress', 'implemented', 'unknown'}
CURRENCIES = {'active', 'superseded', 'historical', 'uncertain'}
PURPOSES = {'active_work', 'decision_rationale', 'unresolved_problem', 'avoid_repeated_failure', 'future_opportunity'}
RELATIONS = {'supports', 'contradicts', 'supersedes', 'implements', 'blocks', 'derives_from'}
DEFAULT_PURPOSE = {'decision': 'decision_rationale', 'idea': 'future_opportunity',
                   'attempt': 'avoid_repeated_failure', 'blocker': 'unresolved_problem'}


def item_id(project_id, record_id):
    return digest(f'item:{project_id}:{record_id}'.encode())


def candidate_kind(record):
    if record.get('source_role') == 'implementation' or configuration_source(record):
        return None
    text = record['statement']
    if re.search(r'(?im)^#+\s*(failed approach|discarded|rejected|attempt)', text):
        return 'attempt'
    if record['evidence_status'] == 'proposal' or re.search(r'(?im)^#+\s*(unfinished idea|idea|proposal)', text):
        return 'idea'
    kinds = set(record.get('knowledge_kinds', []))
    if kinds & {'unresolved', 'limitation'}:
        return 'blocker'
    if 'decision' in kinds:
        return 'decision'
    if kinds & {'solution', 'lesson'}:
        return 'attempt'
    return None


def reference(snapshot, record):
    return {'snapshot': snapshot['id'], 'record_id': record['id'], **record['evidence'],
            'observed_at': next((f.get('observed_at') for f in snapshot['files']
                                if f['path'] == record['evidence']['path'] and f.get('sha256') == record['evidence']['sha256']), None)}


def seed(project_id, snapshot, record, kind=None):
    kind = kind or candidate_kind(record)
    if kind not in KINDS:
        raise ValueError('Record has no supported automatic item kind; supply an explicit kind')
    return {'id': item_id(project_id, record['id']), 'project_id': project_id, 'kind': kind,
            'summary': record['statement'], 'work_stage': 'proposed' if record['evidence_status'] == 'proposal' else 'unknown',
            'evidence_strength': 'source_observed' if record.get('source_role') == 'implementation' else 'reported',
            'currency': 'historical' if record.get('source_role') == 'historical_copy' else 'uncertain',
            'purpose': DEFAULT_PURPOSE[kind], 'claims': [reference(snapshot, record)],
            'origin': 'deterministic_candidate', 'reviewed': False}


class ProjectState:
    def __init__(self, brain, project_id):
        self.brain, self.project_id = brain, project_id
        brain.project(project_id)
        self.root = brain.root / 'projects' / project_id / 'state'
        self.head = self.root / 'head.json'
        self._snapshots = {}

    def events(self):
        if not self.head.exists():
            return []
        head = read(self.head)
        if head.get('version') not in (1, 2, 3) or head.get('project_id') != self.project_id:
            raise ValueError('Invalid state journal identity')
        events = []
        seen = set()
        undone = set()
        for eid in head['events']:
            if str(uuid.UUID(eid)) != eid or eid in seen:
                raise ValueError('Invalid state event identity')
            event = read(self.root / 'events' / (eid + '.json'))
            if event['id'] != eid or event['project_id'] != self.project_id:
                raise ValueError('State event identity mismatch')
            if event.get('type') not in ('correct', 'relate', 'consolidate', 'verify', 'undo'):
                raise ValueError('Unsupported state event')
            self._rationale(event.get('rationale'))
            if event['type'] == 'verify':
                if head['version'] < 3 or event.get('attestation') != 'observed_execution_and_reviewed_scope':
                    raise ValueError('Invalid verification authority or journal version')
                self._rationale(event.get('reviewer'))
                validate_bundle(event['verification_bundle'])
            if event['type'] == 'undo':
                target = next((e for e in events if e['id'] == event.get('target')), None)
                if target is None or target['type'] == 'undo' or target['id'] in undone:
                    raise ValueError('Invalid state undo target')
                undone.add(target['id'])
            events.append(event)
            seen.add(eid)
        return events

    def evidence(self, ref):
        snapshot = self._snapshots.get(ref['snapshot'])
        if snapshot is None:
            snapshot = self.brain.snapshot(self.project_id, ref['snapshot'])
            validate(snapshot)
            self._snapshots[ref['snapshot']] = snapshot
        record = next((r for r in snapshot['records'] if r['id'] == ref['record_id']), None)
        if record is None:
            raise ValueError('State evidence record is absent from the cited project snapshot')
        return snapshot, record

    def view(self, *, max_snapshots=64, max_items=2000, _events=None):
        if type(max_snapshots) is not int or not 1 <= max_snapshots <= 1000:
            raise ValueError('State snapshot budget must be 1..1000')
        if type(max_items) is not int or not 1 <= max_items <= 10000:
            raise ValueError('State item budget must be 1..10000')
        self._snapshots = {}
        current = self.brain.snapshot(self.project_id)
        validate(current)
        active_records = {r['id'] for r in current['records']}
        items, visited, snapshots = {}, set(), 0
        cursor = current['id']
        truncated_items = False
        legacy_boundary = False
        while cursor and snapshots < max_snapshots:
            if cursor in visited:
                raise ValueError('Cyclic snapshot lineage')
            visited.add(cursor)
            snapshot = self.brain.snapshot(self.project_id, cursor)
            validate(snapshot)
            self._snapshots[cursor] = snapshot
            snapshots += 1
            for record in snapshot['records']:
                iid = item_id(self.project_id, record['id'])
                if iid in items or not candidate_kind(record):
                    continue
                if len(items) >= max_items:
                    truncated_items = True
                    continue
                items[iid] = seed(self.project_id, snapshot, record)
            legacy_boundary = 'parent_snapshot' not in snapshot
            physical = read(self.brain.root / 'projects' / self.project_id / 'snapshots' / (cursor + '.json'))
            cursor = physical['content_snapshot'] if physical.get('storage_format') == 'observation-1' else snapshot.get('parent_snapshot')
        catalog = load_catalog(self.brain, self.project_id)
        if catalog:
            for rid, entry in catalog['entries'].items():
                iid = item_id(self.project_id, rid)
                if iid in items:
                    continue
                if len(items) >= max_items:
                    truncated_items = True
                    continue
                snapshot, record = self.evidence(entry)
                if record['id'] != rid:
                    raise ValueError('State catalogue record mismatch')
                if configuration_source(record):
                    continue  # Explicit reviewed journal seeds are restored below.
                items[iid] = seed(self.project_id, snapshot, record, entry['kind'])
        events = self.events() if _events is None else _events
        disabled = {event['target'] for event in events if event['type'] == 'undo'}
        relations = []
        for event in events:
            if event['type'] == 'undo' or event['id'] in disabled:
                continue
            if event['type'] not in ('correct', 'relate', 'consolidate', 'verify'):
                raise ValueError('Unsupported state event')
            # Explicitly reviewed endpoints remain available even outside the scan budget.
            for endpoint in event['seeds']:
                snapshot, record = self.evidence(endpoint['evidence'])
                iid = item_id(self.project_id, record['id'])
                if iid != endpoint['item_id']:
                    raise ValueError('State endpoint identity mismatch')
                items.setdefault(iid, seed(self.project_id, snapshot, record, endpoint['kind']))
            snapshot, record = self.evidence(event['evidence'])
            if event['type'] == 'verify':
                receipt = validate_bundle(event['verification_bundle'])
                items[event['item_id']].setdefault('verified_behaviors', []).append({
                    'event_id': event['id'], 'behavior': receipt['scope'],
                    'environment': receipt['environment_description'],
                    'source_revision': receipt['source_before']['head'],
                    'receipt_sha256': event['verification_bundle']['receipt_sha256'],
                    'reviewer': event['reviewer'], 'rationale': event['rationale'],
                    'subject': event['subject'], 'evidence_strength': 'independently_verified',
                    'authority': 'explicit_local_observer_attestation',
                    'limitation': 'Scoped reviewer attestation; receipt hashes do not authenticate authorship or prove unrelated claims.'})
            elif event['type'] == 'correct':
                item = items[event['item_id']]
                self.validate_changes(event['changes'])
                item.update(event['changes'])
                ref = reference(snapshot, record)
                if not any(c['record_id'] == ref['record_id'] for c in item['claims']):
                    item['claims'].append(ref)
                # Evidence strength is scoped to sources, never raised by a free-text correction.
                item['evidence_strength'] = 'source_observed' if all(self.evidence(c)[1].get('source_role') == 'implementation' for c in item['claims']) else 'reported'
                item.update(reviewed=True, origin='explicit_interpretation', last_correction=event['id'])
            elif event['type'] == 'consolidate':
                self._consolidate_items(items, relations, event['survivor'], event['absorbed'], event['id'])
            else:
                if event['kind'] not in RELATIONS:
                    raise ValueError('Unsupported state relationship')
                relations.append({'id': event['id'], 'from': event['from'], 'to': event['to'],
                                  'kind': event['kind'], 'rationale': event['rationale'],
                                  'evidence': reference(snapshot, record)})
        # Existing reviewed record precedence remains authoritative for candidate currency.
        for edge in current.get('relations', []):
            older, replacement = item_id(self.project_id, edge['older']), item_id(self.project_id, edge['replacement'])
            if older in items:
                items[older]['currency'] = 'superseded'
            if older in items and replacement in items:
                relations.append({'id': 'record:' + edge['older'], 'from': replacement, 'to': older,
                    'kind': 'supersedes', 'rationale': edge['rationale'], 'origin': 'reviewed_record_precedence'})
        self.validate_relations(relations)
        for edge in relations:
            if edge['kind'] == 'supersedes':
                items[edge['to']]['currency'] = 'superseded'
        for item in items.values():
            if item.get('consolidated_members'):
                members = {item['id'], *item['consolidated_members']}
                conflicts = [edge['id'] for edge in relations if edge['from'] in members and edge['to'] in members
                             and edge['kind'] in ('contradicts', 'supersedes')]
                if conflicts:
                    item['consolidation_conflicts'] = conflicts
                    item['currency'] = 'uncertain'
        for item in items.values():
            available = any(c['record_id'] in active_records for c in item['claims'])
            for verification in item.get('verified_behaviors', []):
                # Verification stays scoped and historical; a later correction,
                # grouping or contradictory relation cannot inherit its authority.
                conflicts = any(e['kind'] in ('contradicts', 'supersedes') and
                                item['id'] in (e['from'], e['to']) for e in relations)
                verification['applicability'] = ('reviewed_subject' if
                    verification['subject'] == subject(item) and not conflicts
                    and not item.get('consolidated_into') else 'historical_review_required')
            item['availability'] = 'retained_in_current_capture' if available else 'retained_history_only'
            if not available and item['currency'] not in ('superseded', 'historical'):
                # Absence affects source availability, not work stage or resolution.
                item['availability_reason'] = 'No supporting claim in latest capture; resolution is unknown'
        return {'state_version': 1, 'project_id': self.project_id, 'snapshot': current['id'], 'visibility': 'project_private',
            'items': items, 'relationships': relations,
            'coverage': {'snapshots_read': snapshots, 'history_truncated': cursor is not None,
                         'legacy_lineage_unknown': legacy_boundary or bool(catalog and catalog.get('legacy_lineage_unknown')),
                         'catalogue_items': len(catalog['entries']) if catalog else 0,
                         'catalogue_backfill_pending': bool(catalog and catalog.get('pending_snapshot')),
                         'items_truncated': truncated_items},
            'events': [{'id': e['id'], 'type': e['type'], 'active': e['id'] not in disabled} for e in events],
            'limitations': ['Automatic items are candidates, not accepted commitments or verified behavior.',
                'Changed wording creates a separate candidate until an explicit evidence mapping connects it.',
                'Manual interpretations and relationships cite evidence but are not semantic truth certificates.',
                'No file absence or later timestamp establishes resolution; bounded legacy coverage remains explicit.']}

    def sync(self, max_snapshots=64):
        if type(max_snapshots) is not int or not 1 <= max_snapshots <= 1000:
            raise ValueError('Backfill snapshot budget must be 1..1000')
        with self.brain.lock():
            registry = read(self.brain.registry_path)
            current = self.brain.snapshot(self.project_id)
            catalog = load_catalog(self.brain, self.project_id)
            if catalog is None:
                catalog = prepare_catalog(self.brain, self.project_id, {'records': []}, current)
                catalog['pending_snapshot'] = current.get('parent_snapshot')
                catalog['legacy_lineage_unknown'] = 'parent_snapshot' not in current
            else:
                catalog = deepcopy(catalog)
                if catalog.get('based_on_snapshot') != current['id']:
                    # Compatible older capture writers preserve but do not update
                    # this optional pointer. Reconcile their intervening history.
                    catalog['pending_snapshot'] = current['id']
                    catalog['based_on_snapshot'] = current['id']
            cursor = catalog.get('pending_snapshot')
            count, seen = 0, set()
            while cursor and count < max_snapshots:
                if cursor in seen:
                    raise ValueError('Cyclic backfill lineage')
                seen.add(cursor)
                snapshot = self.brain.snapshot(self.project_id, cursor)
                validate(snapshot)
                for record in snapshot['records']:
                    kind = candidate_kind(record)
                    if kind:
                        catalog['entries'].setdefault(record['id'], {
                            'snapshot': snapshot['id'], 'record_id': record['id'], 'kind': kind})
                if 'parent_snapshot' not in snapshot:
                    catalog['legacy_lineage_unknown'] = True
                cursor = snapshot.get('parent_snapshot')
                count += 1
            catalog.update(id=str(uuid.uuid4()), pending_snapshot=cursor)
            write(self.root / 'catalogs' / (catalog['id'] + '.json'), catalog)
            registry['projects'][self.project_id]['state_catalog'] = catalog['id']
            write(self.brain.registry_path, registry)
            return {'project_id': self.project_id, 'catalogue': catalog['id'],
                    'items': len(catalog['entries']), 'snapshots_processed': count,
                    'backfill_pending': cursor is not None,
                    'legacy_lineage_unknown': catalog['legacy_lineage_unknown']}

    @staticmethod
    def validate_changes(changes):
        allowed = {'summary', 'kind', 'work_stage', 'currency', 'purpose'}
        if not changes or set(changes) - allowed:
            raise ValueError('Only supported interpretation fields can be corrected; verification cannot be asserted')
        for key, choices in (('kind', KINDS), ('work_stage', STAGES), ('currency', CURRENCIES), ('purpose', PURPOSES)):
            if key in changes and changes[key] not in choices:
                raise ValueError('Invalid interpretation field: ' + key)
        if 'summary' in changes and (not isinstance(changes['summary'], str) or not changes['summary'].strip() or len(changes['summary']) > 1800):
            raise ValueError('Summary must be 1..1800 characters')
        if SECRET.search(str(changes)):
            raise ValueError('Suspected sensitive interpretation')

    @staticmethod
    def validate_relations(relations):
        edges = {}
        for edge in relations:
            if edge['from'] == edge['to']:
                raise ValueError('An item cannot relate to itself')
            if edge['kind'] == 'supersedes':
                if edge['to'] in edges and edges[edge['to']] != edge['from']:
                    raise ValueError('Ambiguous supersession; extend the existing chain')
                edges[edge['to']] = edge['from']
        for start in edges:
            seen, cursor = set(), start
            while cursor in edges:
                if cursor in seen:
                    raise ValueError('Cyclic supersession')
                seen.add(cursor)
                cursor = edges[cursor]

    def _append(self, event):
        events = self.events()
        event = dict(event, id=str(uuid.uuid4()), project_id=self.project_id, created_at=time.time(),
                     authority='explicit_local_interpretation', evidence_strength='reported')
        write(self.root / 'events' / (event['id'] + '.json'), event)
        previous_version = read(self.head).get('version', 1) if self.head.exists() else 1
        version = max(previous_version, 3 if event['type'] == 'verify' else 2 if event['type'] == 'consolidate' else 1)
        write(self.head, {'version': version, 'project_id': self.project_id, 'events': [e['id'] for e in events] + [event['id']]})
        return event

    def _seed_refs(self, state, identities):
        refs = []
        for iid in identities:
            if iid not in state['items']:
                raise ValueError('Unknown item identity')
            item = state['items'][iid]
            if item.get('consolidated_into'):
                raise ValueError('Use the consolidation survivor, or undo consolidation first')
            refs.append({'item_id': iid, 'kind': item['kind'], 'evidence': item['claims'][0]})
        return refs

    @staticmethod
    def _consolidate_items(items, relations, survivor, absorbed, event_id):
        """Combine reviewed support, retaining the original items as historical aliases.

        Relationships continue to name original identities; consolidation does not
        manufacture precedence or retarget a contradiction to a different claim.
        """
        if survivor == absorbed or survivor not in items or absorbed not in items:
            raise ValueError('Consolidation requires two distinct known items')
        target, source = items[survivor], items[absorbed]
        if target.get('consolidated_into') or source.get('consolidated_into') or source.get('consolidated_members'):
            raise ValueError('Use active survivors; consolidate additional items into the existing survivor')
        for field in ('kind', 'work_stage', 'currency', 'purpose'):
            if target[field] != source[field]:
                raise ValueError('Consolidation interpretation conflict: ' + field)
        members = {survivor, absorbed, *target.get('consolidated_members', [])}
        if any(e['from'] in members and e['to'] in members and e['kind'] in ('contradicts', 'supersedes') for e in relations):
            raise ValueError('Resolve contradictory or superseding relationships before consolidation')
        claims = {(c['snapshot'], c['record_id']) for c in target['claims']}
        for claim in source['claims']:
            if (claim['snapshot'], claim['record_id']) not in claims:
                target['claims'].append(deepcopy(claim))
                claims.add((claim['snapshot'], claim['record_id']))
        target.setdefault('consolidated_members', []).append(absorbed)
        target.update(reviewed=True, origin='explicit_interpretation', last_consolidation=event_id)
        target['evidence_strength'] = 'source_observed' if target['evidence_strength'] == source['evidence_strength'] == 'source_observed' else 'reported'
        source['consolidated_into'] = survivor
        source['consolidation_event'] = event_id

    def consolidate(self, survivor, absorbed, rationale):
        """Explicitly group duplicate support without deleting evidence or approvals."""
        self._rationale(rationale)
        with self.brain.lock():
            state = self.view()
            refs = self._seed_refs(state, [survivor, absorbed])
            self._consolidate_items(deepcopy(state['items']), state['relationships'], survivor, absorbed, 'preview')
            return self._append({'type': 'consolidate', 'survivor': survivor, 'absorbed': absorbed,
                'evidence': refs[0]['evidence'], 'rationale': rationale, 'seeds': refs})

    def correct(self, iid, changes, evidence, rationale):
        self.validate_changes(changes)
        self._rationale(rationale)
        with self.brain.lock():
            state = self.view()
            snapshot, record = self.evidence(evidence)
            refs = self._seed_refs(state, [iid])
            return self._append({'type': 'correct', 'item_id': iid, 'changes': deepcopy(changes),
                'evidence': reference(snapshot, record), 'rationale': rationale, 'seeds': refs})

    def verify(self, iid, directory, reviewer, rationale, *, observed=False):
        """Adopt one scoped check only with an explicit local observer attestation.

        Retain receipt/output bytes in the immutable event. This never changes
        item-wide strength, work stage, currency, sharing or capture policy.
        """
        if observed is not True:
            raise ValueError('Explicit observation and scope-review attestation required')
        self._rationale(reviewer); self._rationale(rationale)
        bundle = load_bundle(directory)
        with self.brain.lock():
            receipt = validate_bundle(bundle)
            if receipt['cwd'] not in self.brain.project(self.project_id).get('locations', []):
                raise ValueError('Receipt working directory is not a recorded location of this project')
            state = self.view()
            refs = self._seed_refs(state, [iid])
            return self._append({'type': 'verify', 'item_id': iid,
                'verification_bundle': bundle, 'reviewer': reviewer,
                'attestation': 'observed_execution_and_reviewed_scope',
                'subject': subject(state['items'][iid]), 'evidence': refs[0]['evidence'],
                'rationale': rationale, 'seeds': refs})

    def receipt(self, event_id):
        """Read preserved receipt bytes, including revoked verification history."""
        events = self.events()
        event = next((e for e in events if e['id'] == event_id and e['type'] == 'verify'), None)
        if event is None:
            raise ValueError('Unknown verification event')
        return {'event': event, 'active': not any(e.get('target') == event_id for e in events)}

    def relate(self, source, target, kind, evidence, rationale):
        if kind not in RELATIONS:
            raise ValueError('Unsupported state relationship')
        self._rationale(rationale)
        with self.brain.lock():
            state = self.view()
            refs = self._seed_refs(state, [source, target])
            snapshot, record = self.evidence(evidence)
            self.validate_relations(state['relationships'] + [{'from': source, 'to': target, 'kind': kind}])
            return self._append({'type': 'relate', 'from': source, 'to': target, 'kind': kind,
                'evidence': reference(snapshot, record), 'rationale': rationale, 'seeds': refs})

    def undo(self, event_id, rationale):
        self._rationale(rationale)
        with self.brain.lock():
            events = self.events()
            target = next((e for e in events if e['id'] == event_id), None)
            if target is None or target['type'] == 'undo':
                raise ValueError('Undo requires an existing correction, relationship or consolidation event')
            if any(e.get('target') == event_id for e in events if e['type'] == 'undo'):
                raise ValueError('Event is already undone')
            # Removing an earlier correction must not publish an unreadable
            # dependent consolidation. Undo the dependent grouping first.
            self.view(_events=events + [{'id': str(uuid.uuid4()), 'type': 'undo', 'target': event_id}])
            return self._append({'type': 'undo', 'target': event_id, 'rationale': rationale})

    @staticmethod
    def _rationale(text):
        if not isinstance(text, str) or not text.strip() or len(text) > 1000 or SECRET.search(text):
            raise ValueError('A non-sensitive rationale of 1..1000 characters is required')


def load_catalog(brain, project_id, catalog_id=None):
    catalog_id = catalog_id or brain.project(project_id).get('state_catalog')
    if catalog_id is None:
        return None
    if str(uuid.UUID(catalog_id)) != catalog_id:
        raise ValueError('Invalid state catalogue identity')
    catalog = read(brain.root / 'projects' / project_id / 'state' / 'catalogs' / (catalog_id + '.json'))
    if catalog.get('version') != 1 or catalog['id'] != catalog_id or catalog['project_id'] != project_id:
        raise ValueError('State catalogue identity mismatch')
    return catalog


def prepare_catalog(brain, project_id, old, current, previous_catalog=None):
    """Called under the capture lock; caller publishes its pointer atomically."""
    catalog = deepcopy(previous_catalog) if previous_catalog else {
        'version': 1, 'project_id': project_id, 'entries': {},
        'pending_snapshot': old.get('parent_snapshot'),
        'legacy_lineage_unknown': bool(old.get('id') and 'parent_snapshot' not in old)}
    for snapshot in (old, current):
        for record in snapshot.get('records', []):
            kind = candidate_kind(record)
            if kind:
                catalog['entries'][record['id']] = {'snapshot': snapshot['id'], 'record_id': record['id'], 'kind': kind}
    catalog.update(id=str(uuid.uuid4()), based_on_snapshot=current['id'])
    return catalog


def bounded_view(state, limit=20, include_history=False):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError('State display limit must be 1..100')
    items = [i for i in state['items'].values() if include_history or (i['currency'] != 'superseded' and not i.get('consolidated_into'))]
    from collections import Counter
    from .briefing import quality
    priority = {'blocker': 0, 'decision': 1, 'attempt': 2, 'idea': 3}
    kind_counts, path_counts = Counter(), Counter()
    ranked = []
    remaining = list(items)
    while remaining and len(ranked) < limit:
        def rank(item):
            path = item['claims'][0]['path']
            record = {'statement': item['summary'], 'evidence': item['claims'][0], 'id': item['id']}
            return (-item['reviewed'], kind_counts[item['kind']], path_counts[path],
                    item['availability'] != 'retained_in_current_capture',
                    quality(record), priority[item['kind']], item['id'])
        item = min(remaining, key=rank)
        remaining.remove(item)
        ranked.append(item)
        kind_counts[item['kind']] += 1
        path_counts[item['claims'][0]['path']] += 1
    chosen = []
    for item in ranked:
        chosen.append({**item, 'summary': item['summary'][:400],
            'summary_truncated': len(item['summary']) > 400,
            'claims': item['claims'][:5], 'claims_omitted': max(0, len(item['claims']) - 5)})
    selected_ids = {i['id'] for i in chosen}
    selected_ids.update(member for i in chosen for member in i.get('consolidated_members', []))
    relations = [e for e in state['relationships'] if e['from'] in selected_ids or e['to'] in selected_ids]
    return {**{k: state[k] for k in ('state_version', 'project_id', 'snapshot', 'visibility', 'coverage', 'limitations')},
            'items': chosen, 'omitted_items': len(items) - len(chosen),
            'consolidated_items': sum(bool(i.get('consolidated_into')) for i in state['items'].values()),
            'relationships': relations[:limit], 'omitted_relationships': max(0, len(relations) - limit)}
