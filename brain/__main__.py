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
    p = sub.add_parser('briefing', help='Bounded evidence briefing of the last captured project state')
    p.add_argument('project_id')
    p.add_argument('--limit', type=int, default=3, help='Excerpts per section, 1 through 20')
    p.add_argument('--json', action='store_true', help='Return structured briefing data')
    p = sub.add_parser('ingest')
    p.add_argument('source')
    p.add_argument('--project-id', help='Explicit stable identity when relocating a project')
    p.add_argument('--exclude-path', action='append', default=[])
    p.add_argument('--historical', action='store_true', help='Label the entire source as a historical copy')
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
        p.add_argument('--max-chars', type=int, default=6000)
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
            if args.command == 'ingest':
                for key in ('max_files', 'max_file_bytes', 'max_total_bytes', 'max_seconds'):
                    value = getattr(args, key)
                    if value is not None:
                        if value <= 0:
                            raise ValueError('Processing budgets must be positive')
                        b.config[key] = value
                result = b.ingest(args.source, args.project_id, args.exclude_path, args.historical)
            elif args.command == 'evidence':
                result = b.retained_evidence(args.project_id, args.path, args.start_line, args.end_line, args.snapshot)
            elif args.command == 'history':
                project = b.project(args.project_id)
                from .core import read
                result = []
                for path in sorted((b.root / 'projects' / args.project_id / 'snapshots').glob('*.json')):
                    snap = read(path)
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
            elif args.command == 'promote':
                result = b.promote(args.project_id, args.record_id, args.technology, args.rationale, args.review_days)
            elif args.command in ('search', 'context'):
                if args.limit < 1 or args.max_chars < 1:
                    raise ValueError('Retrieval budgets must be positive')
                result = b.retrieve(args.query, getattr(args, 'project_id', None), args.technology, args.limit, args.max_chars, args.exclude)
            elif args.command == 'doctor':
                result = {'python': sys.version.split()[0], 'ai_available': False, 'model_availability_verified': False, 'reason': 'No executable AI adapter installed. Model names are configurable placeholders, not availability claims.', 'network_submission': False, 'extraction': EXTRACTOR}
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as e:
        print(f'brain: {e}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    sys.exit(main())

