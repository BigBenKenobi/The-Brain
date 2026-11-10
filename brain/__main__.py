import argparse
import json
import os
from pathlib import Path
import sys
from .core import Brain, EXTRACTOR, initialize, validate


def main(argv=None):
    parser = argparse.ArgumentParser(description='Project Brain: local evidence preservation and selective reuse')
    parser.add_argument('--brain', default=os.environ.get('PROJECT_BRAIN_HOME', './Project-Brain'), help='Independent Brain workspace')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init')
    sub.add_parser('list')
    sub.add_parser('doctor')
    sub.add_parser('storage-preview', help='Preview lossless evidence compaction and current storage')
    p = sub.add_parser('compact-copy', help='Create a verified compact store without changing the original')
    p.add_argument('destination')
    sub.add_parser('sources', help='List explicitly configured sources')
    sub.add_parser('refresh-once', help='Run one bounded due-source refresh pass')
    sub.add_parser('refresh-status', help='Show automatic capture policy and health')
    p = sub.add_parser('refresh-policy', help='Configure opt-in background capture')
    p.add_argument('--paused', action=argparse.BooleanOptionalAction, default=None)
    for setting in ('interval-seconds', 'retry-seconds', 'max-retry-seconds', 'max-sources-per-run',
                    'max-run-seconds', 'max-files-per-run', 'max-bytes-per-run', 'max-store-bytes'):
        p.add_argument('--' + setting, type=int)
    p = sub.add_parser('upgrade-store', help='Back up and upgrade the store writer format')
    p.add_argument('--backup', required=True)
    p = sub.add_parser('refresh', help='Refresh one source using saved settings')
    p.add_argument('source_id')
    p = sub.add_parser('relocate-source', help='Move a source identity without losing settings')
    p.add_argument('source_id')
    p.add_argument('location')
    p = sub.add_parser('configure-source', help='Change settings for future captures')
    p.add_argument('source_id')
    p.add_argument('--enabled', action=argparse.BooleanOptionalAction, default=None)
    group = p.add_mutually_exclusive_group()
    group.add_argument('--exclude-path', action='append', default=None)
    group.add_argument('--clear-exclusions', action='store_true')
    p.add_argument('--historical', action=argparse.BooleanOptionalAction, default=None)
    p.add_argument('--reset-budgets', action='store_true')
    for budget in ('max-files', 'max-file-bytes', 'max-total-bytes', 'max-seconds'):
        p.add_argument('--' + budget, type=int)

    p = sub.add_parser('briefing', help='Bounded evidence briefing of the last captured project state')
    p.add_argument('project_id')
    p.add_argument('--limit', type=int, default=3, help='Excerpts per section, 1 through 20')
    p.add_argument('--json', action='store_true', help='Return structured briefing data')
    p = sub.add_parser('ingest')
    p.add_argument('source')
    p.add_argument('--project-id', help='Explicit stable identity when relocating a project')
    p.add_argument('--source-id', help='Explicit registered source identity')
    p.add_argument('--new-source', action='store_true', help='Add another independent source to this project')
    p.add_argument('--adopt-legacy', action='store_true', help='Explicitly map ambiguous legacy evidence using supplied settings')
    group = p.add_mutually_exclusive_group()
    group.add_argument('--exclude-path', action='append', default=None)
    group.add_argument('--clear-exclusions', action='store_true')
    p.add_argument('--historical', action=argparse.BooleanOptionalAction, default=None, help='Historical designation; omitted reuses saved setting')
    for budget in ('max-files', 'max-file-bytes', 'max-total-bytes', 'max-seconds'):
        p.add_argument('--' + budget, type=int)
    for cmd in ('history', 'status', 'retire-check', 'summary', 'validate', 'archive-evidence'):
        p = sub.add_parser(cmd)
        p.add_argument('project_id')
    p = sub.add_parser('evidence')
    p.add_argument('project_id')
    p.add_argument('path')
    p.add_argument('--start-line', type=int, default=1)
    p.add_argument('--end-line', type=int)
    p.add_argument('--snapshot', help='Read a preserved historical snapshot UUID')
    p = sub.add_parser('review-retirement')
    p.add_argument('project_id')
    p.add_argument('--summary', required=True)
    p.add_argument('--known-gap', action='append', required=True)
    p.add_argument('--record-id', action='append', required=True)
    p = sub.add_parser('consolidate')
    p.add_argument('project_id')
    p.add_argument('supplement_id')
    p = sub.add_parser('verify-archive')
    p.add_argument('path')
    for cmd in ('search', 'context'):
        p = sub.add_parser(cmd)
        if cmd == 'context':
            p.add_argument('project_id')
        p.add_argument('query')
        p.add_argument('--technology', action='append', default=[], help='Explicit compatible technology/version, repeatable')
        p.add_argument('--exclude', action='append', default=[], help='Task constraints: reject records matching these terms')
        p.add_argument('--limit', type=int, default=5)
        p.add_argument('--max-chars', type=int, default=6000, help='Statement-text budget; metadata additional')
        p.add_argument('--include-history', action='store_true')
        p.add_argument('--explain', action='store_true')
        p.add_argument('--max-age-days', type=int, help='Explicit successful-observation age filter; excludes unknown dates')
    p = sub.add_parser('relate')
    p.add_argument('project_id')
    p.add_argument('older')
    p.add_argument('replacement')
    p.add_argument('--kind', required=True, choices=['corrects', 'supersedes', 'duplicates'])
    p.add_argument('--rationale', required=True)
    p = sub.add_parser('undo-relation', help='Undo a reviewed record relationship without altering evidence')
    p.add_argument('project_id')
    p.add_argument('older')
    p.add_argument('--rationale', required=True)
    p = sub.add_parser('state', help='Bounded maintained project items')
    p.add_argument('project_id')
    p.add_argument('--limit', type=int, default=20)
    p.add_argument('--max-snapshots', type=int, default=64)
    p.add_argument('--include-history', action='store_true')
    p = sub.add_parser('state-sync', help='Backfill the retained item catalogue within an explicit budget')
    p.add_argument('project_id')
    p.add_argument('--max-snapshots', type=int, default=64)
    p = sub.add_parser('state-correct', help='Correct a derived interpretation with retained evidence')
    p.add_argument('project_id')
    p.add_argument('item_id')
    p.add_argument('--summary')
    p.add_argument('--kind', choices=['decision', 'idea', 'attempt', 'blocker'])
    p.add_argument('--work-stage', choices=['proposed', 'accepted', 'in_progress', 'implemented', 'unknown'])
    p.add_argument('--currency', choices=['active', 'superseded', 'historical', 'uncertain'])
    p.add_argument('--purpose', choices=['active_work', 'decision_rationale', 'unresolved_problem', 'avoid_repeated_failure', 'future_opportunity'])
    p.add_argument('--record-id', required=True)
    p.add_argument('--snapshot')
    p.add_argument('--rationale', required=True)
    p = sub.add_parser('state-relate', help='Relate two items with an evidence-backed rationale')
    p.add_argument('project_id')
    p.add_argument('source_item')
    p.add_argument('target_item')
    p.add_argument('--kind', required=True, choices=['supports', 'contradicts', 'supersedes', 'implements', 'blocks', 'derives_from'])
    p.add_argument('--record-id', required=True)
    p.add_argument('--snapshot')
    p.add_argument('--rationale', required=True)
    p = sub.add_parser('state-undo', help='Undo one interpretation event, retaining its audit history')
    p.add_argument('project_id')
    p.add_argument('event_id')
    p.add_argument('--rationale', required=True)
    p = sub.add_parser('state-consolidate', help='Group reviewed duplicate items while preserving evidence and undo')
    p.add_argument('project_id')
    p.add_argument('survivor')
    p.add_argument('absorbed')
    p.add_argument('--rationale', required=True)
    p = sub.add_parser('promote')
    p.add_argument('project_id')
    p.add_argument('record_id')
    p.add_argument('--approve-sharing', action='store_true', required=True, help='Explicitly permit this record to be shared across projects')
    p.add_argument('--technology', action='append', required=True)
    p.add_argument('--rationale', required=True)
    p.add_argument('--review-days', type=int, default=90)
    args = parser.parse_args(argv)
    try:
        if args.command == 'init':
            result = initialize(args.brain)
        else:
            b = Brain(args.brain)
            if args.command in ('ingest', 'configure-source'):
                from .sources import BUDGETS
                budgets = {key: getattr(args, key) for key in BUDGETS if getattr(args, key) is not None}
                exclusions = [] if args.clear_exclusions else args.exclude_path
                if args.command == 'ingest':
                    result = b.ingest(args.source, args.project_id, exclusions, args.historical,
                        source_id=args.source_id, budgets=budgets, new_source=args.new_source,
                        adopt_legacy=args.adopt_legacy)
                else:
                    if args.reset_budgets:
                        budgets = {**{key: b.config[key] for key in BUDGETS}, **budgets}
                    result = b.configure_source(args.source_id, excluded_paths=exclusions,
                        historical=args.historical, budgets=budgets, enabled=args.enabled)
            elif args.command in ('refresh-once', 'refresh-status', 'refresh-policy'):
                from .refresh import RefreshWorker, DEFAULT_POLICY
                worker = RefreshWorker(b)
                if args.command == 'refresh-once':
                    result = worker.run_once()
                elif args.command == 'refresh-status':
                    result = worker.status()
                else:
                    result = worker.configure(**{key: getattr(args, key) for key in DEFAULT_POLICY if getattr(args, key) is not None})
            elif args.command == 'sources':
                from .core import read
                result = list(read(b.registry_path).get('sources', {}).values())
            elif args.command in ('storage-preview', 'compact-copy'):
                from .storage import preview, compact_copy
                result = preview(b) if args.command == 'storage-preview' else compact_copy(b, args.destination)
            elif args.command == 'refresh':
                result = b.refresh(args.source_id)
            elif args.command == 'relocate-source':
                result = b.configure_source(args.source_id, new_location=args.location)
            elif args.command == 'upgrade-store':
                result = b.upgrade_store(args.backup)
            elif args.command == 'evidence':
                result = b.retained_evidence(args.project_id, args.path, args.start_line, args.end_line, args.snapshot)
            elif args.command == 'history':
                project = b.project(args.project_id)
                from .core import read
                result = []
                for path in sorted((b.root / 'projects' / args.project_id / 'snapshots').glob('*.json')):
                    snap = b.snapshot(args.project_id, path.stem)
                    result.append({'snapshot': snap['id'], 'created_at': snap['created_at'], 'active': snap['id'] == project['snapshot'], 'records': len(snap['records'])})
                result.sort(key=lambda item: item['created_at'])
            elif args.command == 'review-retirement':
                result = b.review_retirement(args.project_id, args.summary, args.known_gap, args.record_id)
            elif args.command == 'consolidate':
                result = b.consolidate(args.project_id, args.supplement_id)
            elif args.command == 'list':
                from .core import read
                result = read(b.registry_path)
            elif args.command == 'status':
                s = b.snapshot(args.project_id)
                result = {k: v for k, v in s.items() if k not in {'evidence', 'records'}}
            elif args.command == 'retire-check':
                result = b.retirement(args.project_id)
            elif args.command == 'summary':
                print(b.summary(args.project_id))
                return 0
            elif args.command == 'briefing':
                result = b.briefing(args.project_id, args.limit)
                if not args.json:
                    from .briefing import render_briefing
                    print(render_briefing(result))
                    return 0
            elif args.command == 'validate':
                result = validate(b.snapshot(args.project_id))
            elif args.command == 'archive-evidence':
                result = b.archive(args.project_id)
            elif args.command == 'verify-archive':
                result = b.verify_archive(args.path)
            elif args.command == 'relate':
                result = b.relate(args.project_id, args.older, args.replacement, args.kind, args.rationale)
            elif args.command == 'undo-relation':
                result = b.undo_relation(args.project_id, args.older, args.rationale)
            elif args.command in ('state', 'state-sync', 'state-correct', 'state-relate', 'state-undo', 'state-consolidate'):
                from .state import ProjectState, bounded_view
                state = ProjectState(b, args.project_id)
                if args.command == 'state':
                    result = bounded_view(state.view(max_snapshots=args.max_snapshots), args.limit, args.include_history)
                elif args.command == 'state-sync':
                    result = state.sync(args.max_snapshots)
                elif args.command == 'state-undo':
                    result = state.undo(args.event_id, args.rationale)
                elif args.command == 'state-consolidate':
                    result = state.consolidate(args.survivor, args.absorbed, args.rationale)
                else:
                    evidence = {'snapshot': args.snapshot or b.project(args.project_id)['snapshot'], 'record_id': args.record_id}
                    if args.command == 'state-correct':
                        changes = {key: getattr(args, key) for key in ('summary', 'kind', 'work_stage', 'currency', 'purpose') if getattr(args, key) is not None}
                        result = state.correct(args.item_id, changes, evidence, args.rationale)
                    else:
                        result = state.relate(args.source_item, args.target_item, args.kind, evidence, args.rationale)
            elif args.command == 'promote':
                result = b.promote(args.project_id, args.record_id, args.technology, args.rationale, args.review_days)
            elif args.command in ('search', 'context'):
                if args.limit < 1 or args.max_chars < 1:
                    raise ValueError('Retrieval budgets must be positive')
                result = b.retrieve(args.query, getattr(args, 'project_id', None), args.technology, args.limit, args.max_chars, args.exclude, args.include_history, args.explain, args.max_age_days)
            elif args.command == 'doctor':
                result = {'python': sys.version.split()[0], 'ai_available': False, 'model_availability_verified': False, 'reason': 'No executable AI adapter installed. Model names are configurable placeholders, not availability claims.', 'network_submission': False, 'extraction': EXTRACTOR}
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f'brain: {e}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())
