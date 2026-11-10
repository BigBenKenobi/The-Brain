"""Integrity checks for explicitly reviewed, behavior-scoped execution receipts.

Hashes prove retained-byte consistency, not authorship or semantic adequacy. Only
an explicit local reviewer can attest the observed run and its stated scope. No
captured document, model or background worker calls the adoption path.
"""
import base64
import json
import re
from pathlib import Path
from .core import digest, SECRET

MAX_OUTPUT = 1048576
MAX_RECEIPT = 65536


def fingerprint(value):
    return digest(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())


def subject(item):
    """Bind interpretation and evidence bytes, ignoring fresh observation dates."""
    return fingerprint({'summary': item['summary'], 'kind': item['kind'],
        'claims': sorted({(c['record_id'], c['sha256'], c['path'], c['start_line'], c['end_line'])
                          for c in item['claims']})})


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate receipt key')
        result[key] = value
    return result


def validate_bundle(bundle):
    """Validate retained receipt bytes even for undone published journal events."""
    if not isinstance(bundle, dict) or set(bundle) != {'receipt_json', 'receipt_sha256', 'outputs'}:
        raise ValueError('Invalid verification bundle')
    if not isinstance(bundle['receipt_json'], str) or not isinstance(bundle['outputs'], dict):
        raise ValueError('Invalid verification bundle fields')
    raw = bundle['receipt_json'].encode()
    if len(raw) > MAX_RECEIPT or digest(raw) != bundle['receipt_sha256']:
        raise ValueError('Verification receipt hash or budget mismatch')
    receipt = json.loads(raw, object_pairs_hook=unique_object)
    if not isinstance(receipt, dict):
        raise ValueError('Invalid execution receipt')
    if (type(receipt.get('version')) is not int or receipt['version'] != 1
            or receipt.get('status') != 'execution_observed_not_adopted'
            or receipt.get('outcome') != 'passed' or type(receipt.get('exit_code')) is not int
            or receipt['exit_code'] != 0 or receipt.get('output_complete') is not True):
        raise ValueError('Verification requires a complete successful execution receipt')
    before, after = receipt.get('source_before'), receipt.get('source_after')
    if (not isinstance(before, dict) or before != after or not isinstance(before.get('head'), str)
            or not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', before['head'])
            or before.get('tracked_clean') is not True):
        raise ValueError('Verification requires an unchanged tracked source revision')
    if (set(bundle['outputs']) != {'stdout', 'stderr'} or not isinstance(receipt.get('outputs'), dict)
            or set(receipt['outputs']) != {'stdout', 'stderr'}):
        raise ValueError('Invalid verification outputs')
    total = 0
    for name, encoded in bundle['outputs'].items():
        if not isinstance(encoded, str) or len(encoded) > 4 * MAX_OUTPUT // 3 + 4:
            raise ValueError('Verification output budget exceeded')
        try:
            data = base64.b64decode(encoded, validate=True)
        except ValueError as exc:
            raise ValueError('Invalid verification output encoding') from exc
        total += len(data)
        info = receipt['outputs'][name]
        if (not isinstance(info, dict) or type(info.get('bytes')) is not int
                or info.get('file') != name + '.bin' or info['bytes'] != len(data) or info.get('sha256') != digest(data)):
            raise ValueError('Verification output hash or size mismatch')
        if SECRET.search(data.decode('utf-8', errors='replace')):
            raise ValueError('Suspected sensitive verification output')
    if total > MAX_OUTPUT or SECRET.search(bundle['receipt_json']):
        raise ValueError('Verification budget or sensitive-content boundary exceeded')
    for field in ('scope', 'environment_description', 'cwd'):
        if not isinstance(receipt.get(field), str) or not receipt[field].strip() or len(receipt[field]) > 1800:
            raise ValueError('Missing verification context')
    if not isinstance(receipt.get('command'), list) or not receipt['command'] or any(
            not isinstance(arg, str) for arg in receipt['command']):
        raise ValueError('Missing verification command')
    return receipt


def load_bundle(directory):
    """Copy fixed receipt filenames from an explicit directory; never execute them."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError('Receipt directory must be a regular directory')
    def bounded(name, cap):
        path = directory / name
        if path.is_symlink() or not path.is_file():
            raise ValueError('Receipt files must be regular files')
        with path.open('rb') as stream:
            data = stream.read(cap + 1)
        if len(data) > cap:
            raise ValueError('Verification file budget exceeded')
        return data
    raw = bounded('receipt.json', MAX_RECEIPT)
    bundle = {'receipt_json': raw.decode('utf-8'), 'receipt_sha256': digest(raw),
              'outputs': {name: base64.b64encode(bounded(name + '.bin', MAX_OUTPUT)).decode()
                          for name in ('stdout', 'stderr')}}
    validate_bundle(bundle)
    return bundle
