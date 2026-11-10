"""Source configuration helpers; no source discovery or content execution."""
from copy import deepcopy
from pathlib import Path
import uuid

BUDGETS = ('max_files', 'max_file_bytes', 'max_total_bytes', 'max_seconds')


def validate_source(source):
    for key in ('id', 'project_id'):
        if str(uuid.UUID(source[key])) != source[key]:
            raise ValueError('Invalid source identity')
    if source['kind'] != 'local_directory' or not Path(source['location']).is_absolute():
        raise ValueError('Invalid local source location')
    if source['prefix'] not in ('', f"sources/{source['id']}/"):
        raise ValueError('Invalid source namespace')
    cfg = source['configuration']
    if type(cfg['revision']) is not int or cfg['revision'] < 1:
        raise ValueError('Invalid configuration revision')
    if set(cfg['budgets']) != set(BUDGETS):
        raise ValueError('Incomplete source budgets')
    configuration(cfg['budgets'], excluded_paths=cfg['excluded_paths'], historical=cfg['historical'],
                  enabled=cfg['enabled'], budgets=cfg['budgets'])


def location(root, path, must_exist=True):
    path = Path(path).resolve(strict=must_exist)
    if must_exist and not path.is_dir():
        raise ValueError('Source must be a directory')
    if path == root or root in path.parents or path in root.parents:
        raise ValueError('Brain and source directories must not overlap')
    return path


def configuration(defaults, previous=None, *, excluded_paths=None, historical=None,
                  budgets=None, enabled=None):
    result = deepcopy(previous) if previous else {
        'excluded_paths': [], 'historical': False, 'enabled': False,
        'budgets': {key: defaults[key] for key in BUDGETS}, 'revision': 1,
    }
    if excluded_paths is not None:
        paths = sorted({str(Path(p)) for p in excluded_paths})
        if any(Path(p).is_absolute() or '..' in Path(p).parts or p == '.' for p in paths):
            raise ValueError('Exclusions must be relative subpaths')
        result['excluded_paths'] = paths
    for key, value in (('historical', historical), ('enabled', enabled)):
        if value is not None:
            if type(value) is not bool:
                raise ValueError(key + ' must be a boolean')
            result[key] = value
    if budgets:
        for key, value in budgets.items():
            if key not in BUDGETS or type(value) is not int or value <= 0:
                raise ValueError('Invalid positive processing budget: ' + key)
            result['budgets'][key] = value
    if previous and result != previous:
        result['revision'] += 1
    return result


def resolve(registry, defaults, path, project_id, old, *, source_id=None,
            new_source=False, adopt_legacy=False, excluded_paths=None,
            historical=None, budgets=None, enabled=None, allow_relocation=False):
    """Resolve only explicit mappings, never infer identity from content."""
    sources = registry.setdefault('sources', {})
    candidates = [s for s in sources.values() if s['project_id'] == project_id]
    for candidate in candidates:
        validate_source(candidate)
    selected = None
    if source_id:
        selected = sources.get(source_id)
        if not selected or selected['project_id'] != project_id:
            raise ValueError('Unknown source or source belongs to another project')
        if selected['location'] != str(path):
            raise ValueError('Use relocate-source to change a configured source location')
    elif not new_source:
        selected = next((s for s in candidates if s['location'] == str(path)), None)
        if candidates and selected is None:
            if allow_relocation and len(candidates) == 1:
                selected = deepcopy(candidates[0])
                selected['location'] = str(path)
                selected['configuration']['revision'] += 1
            else:
                raise ValueError('Unknown source location; use relocate-source or explicitly add --new-source')
    elif any(s['location'] == str(path) for s in sources.values()):
        raise ValueError('Location already registered')
    if selected is None:
        locations = registry['projects'].get(project_id, {}).get('locations', [])
        legacy = old.get('id') and not candidates
        if legacy and (len(locations) != 1 or locations[0] != str(path)) and not adopt_legacy:
            raise ValueError('Ambiguous legacy locations; explicitly adopt this source with --adopt-legacy and reviewed settings')
        if legacy and adopt_legacy and (excluded_paths is None or historical is None or budgets is None or set(budgets) != set(BUDGETS)):
            raise ValueError('Legacy adoption requires explicit exclusions, historical flag and all four budgets')
        sid = str(uuid.uuid4())
        previous = None
        if legacy and not adopt_legacy:
            previous = configuration(defaults, excluded_paths=old.get('excluded_paths', []),
                                     historical=old.get('historical', False), budgets=old.get('processing_budgets'))
        selected = {'id': sid, 'project_id': project_id, 'kind': 'local_directory',
                    'location': str(path), 'prefix': f'sources/{sid}/' if candidates else '',
                    'configuration': previous or configuration(defaults)}
    selected = deepcopy(selected)
    selected['configuration'] = configuration(defaults, selected['configuration'],
        excluded_paths=excluded_paths, historical=historical, budgets=budgets, enabled=enabled)
    validate_source(selected)
    return selected
