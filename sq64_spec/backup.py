"""Independent validation of the public sq64-backup v1 interchange contract.

This module validates bytes and coverage, never device writes or persistence.
"""
import hashlib

from .protocol import decode
from .validation import digest, integer, nonempty, unhex

# reply command, raw length, indexed slot count (None for current), data tag
RECORDS = {
    'global': (0x50, 512, None, b'GLOB'),
    'currentControl': (0x44, 2048, None, b'CTRL'),
    'control': (0x45, 2048, 16, b'CTRL'),
    'scale': (0x47, 36, 6, None),
    'currentProject': (0x41, 512, None, b'PROJ'),
    'project': (0x4d, 512, 64, b'PROJ'),
    'melody': (0x48, 3104, 48, None),
    'rhythm': (0x49, 6176, 16, None),
}
EXCLUSIONS = {'firmware', 'factory-calibration', 'undocumented-device-storage'}
REQUIRED_DATA = {'global', 'currentControl', 'currentProject', 'melody', 'rhythm'}


def _records(archive):
    if (not isinstance(archive, dict) or archive.get('format') != 'sq64-backup'
            or type(archive.get('version')) is not int or archive['version'] != 1
            or archive.get('complete') is not True
            or archive.get('scope') not in ('settings', 'current', 'all')
            or not integer(archive.get('channel'), 0, 15)
            or not isinstance(archive.get('records'), list)
            or len(archive['records']) > 4250):
        raise ValueError('Invalid or incomplete backup archive')
    exclusions = archive.get('excludes')
    if (not isinstance(exclusions, list) or not all(nonempty(x) for x in exclusions)
            or len(set(exclusions)) != len(exclusions) or not EXCLUSIONS <= set(exclusions)):
        raise ValueError('Backup must explicitly exclude firmware, calibration and undocumented storage')
    prefix = bytes((0xf0, 0x42, 0x30 + archive['channel'], 0, 1, 0x60))
    decoded = {}
    for record in archive['records']:
        if not isinstance(record, dict) or not {'kind', 'index', 'project', 'data', 'sha256'} <= record.keys():
            raise ValueError('Missing backup record fields')
        kind, index, project = record['kind'], record['index'], record['project']
        if not isinstance(kind, str) or kind not in RECORDS:
            raise ValueError('Unknown backup record type')
        command, length, slots, tag = RECORDS[kind]
        if (index is not None if slots is None else not integer(index, 0, slots - 1)):
            raise ValueError('Invalid backup slot')
        if kind in ('melody', 'rhythm'):
            if project is not None and not integer(project, 0, 63):
                raise ValueError('Invalid pattern owner')
        elif kind == 'project':
            if not integer(project, 0, 63) or project != index:
                raise ValueError('Project header owner differs from slot')
        elif project is not None:
            raise ValueError('Unexpected project owner')
        key = (kind, index, project)
        if key in decoded:
            raise ValueError('Duplicate backup record')
        if record['data'] is None:
            if record['sha256'] is not None or kind in REQUIRED_DATA:
                raise ValueError('Missing required backup data')
            decoded[key] = None
            continue
        wire = unhex(record['data'], maximum=7500)
        if not digest(record['sha256']) or hashlib.sha256(wire).hexdigest() != record['sha256']:
            raise ValueError('Backup record digest mismatch')
        if (len(wire) < 8 or wire[:6] != prefix or wire[-1] != 0xf7
                or wire[6] != command or any(b > 127 for b in wire[6:-1])):
            raise ValueError('Wrong backup frame, channel or record type')
        body = wire[7:-1]
        if slots is not None:
            if not body or body[0] != index:
                raise ValueError('Backup response slot mismatch')
            body = body[1:]
        raw = decode(body, length)
        if tag is not None and not raw.startswith(tag):
            raise ValueError('Wrong backup data tag')
        decoded[key] = raw

    expected = {('global', None, None), ('currentControl', None, None)}
    expected.update(('scale', slot, None) for slot in range(6))
    if archive['scope'] == 'all':
        expected.update(('control', slot, None) for slot in range(16))
    projects = ([None] + list(range(64)) if archive['scope'] == 'all'
                else [None] if archive['scope'] == 'current' else [])
    for project in projects:
        key = ('currentProject' if project is None else 'project', project, project)
        expected.add(key)
        header = decoded.get(key)
        if header is not None:
            for track in range(4):
                presence = int.from_bytes(header[40 + 2 * track:42 + 2 * track], 'little')
                for pattern in range(16):
                    if presence & (1 << pattern):
                        expected.add(('melody', track * 16 + pattern, project) if track < 3
                                     else ('rhythm', pattern, project))
    if decoded.keys() != expected:
        raise ValueError('Backup has missing, unreferenced or out-of-scope records')
    return decoded


def validate_backup(archive):
    records = _records(archive)
    return {'check': 'backup-archive', 'status': 'pass', 'scope': archive['scope'],
            'records': len(records), 'populatedRecords': sum(v is not None for v in records.values()),
            'requirements': ['BACKUP-001', 'BACKUP-003'],
            'claim': 'Archive coverage, framing and integrity only; session finalization and persistence are unverified'}


def compare_backups(expected, actual):
    """Compare full logical content, ignoring capture time and MIDI channel."""
    before, after = _records(expected), _records(actual)
    if expected['scope'] != actual['scope'] or before != after:
        raise ValueError('Backup logical contents differ')
    return {'check': 'backup-readback', 'status': 'pass', 'records': len(before),
            'claim': 'Logical bytes match; the caller must separately establish device identity and normal restart'}
