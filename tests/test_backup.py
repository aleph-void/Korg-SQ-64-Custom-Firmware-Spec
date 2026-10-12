import hashlib
import unittest

from sq64_spec.backup import compare_backups, validate_backup
from sq64_spec.protocol import decode


def pack(raw):
    out = bytearray()
    for offset in range(0, len(raw), 7):
        group = raw[offset:offset + 7]
        out.append(sum((value // 128) * 2 ** i for i, value in enumerate(group)))
        out.extend(value % 128 for value in group)
    return out


def record(kind, slot=None, owner=None, *, empty=False, presence=False, channel=0):
    # Independent fixture descriptors: do not import the validator's table.
    command, length, tag = {
        'global': (0x50, 512, b'GLOB'), 'currentControl': (0x44, 2048, b'CTRL'),
        'scale': (0x47, 36, b''), 'control': (0x45, 2048, b'CTRL'),
        'currentProject': (0x41, 512, b'PROJ'), 'project': (0x4d, 512, b'PROJ'),
        'melody': (0x48, 3104, b''), 'rhythm': (0x49, 6176, b''),
    }[kind]
    raw = bytearray((i * 19 + (slot or 0)) % 256 for i in range(length))
    raw[:len(tag)] = tag
    if kind in ('project', 'currentProject'):
        raw[40:48] = bytes(8)
        if presence:
            raw[40] = 1  # A pattern 1
            raw[47] = 128  # D pattern 16
    frame = bytes((0xf0, 0x42, 0x30 + channel, 0, 1, 0x60, command))
    if slot is not None:
        frame += bytes([slot])
    frame += pack(raw) + b'\xf7'
    return {'kind': kind, 'index': slot, 'project': owner,
            'data': None if empty else frame.hex(),
            'sha256': None if empty else hashlib.sha256(frame).hexdigest()}


def archive(scope='all', channel=0):
    rows = [record('global', channel=channel), record('currentControl', channel=channel)]
    rows += [record('scale', n, empty=n == 5, channel=channel) for n in range(6)]
    if scope == 'all':
        rows += [record('control', n, empty=n > 0, channel=channel) for n in range(16)]
    if scope != 'settings':
        rows += [record('currentProject', presence=True, channel=channel),
                 record('melody', 0, channel=channel), record('rhythm', 15, channel=channel)]
    if scope == 'all':
        for n in range(64):
            rows.append(record('project', n, n, empty=n not in (0, 63), presence=True, channel=channel))
            if n in (0, 63):
                rows += [record('melody', 0, n, channel=channel), record('rhythm', 15, n, channel=channel)]
    return {'format': 'sq64-backup', 'version': 1, 'channel': channel, 'scope': scope,
            'createdAt': '2026-01-01T00:00:00Z', 'complete': True,
            'excludes': ['firmware', 'factory-calibration', 'undocumented-device-storage'], 'records': rows}


class BackupTests(unittest.TestCase):
    def test_golden_partial_groups(self):
        # Expected bytes are literal wire vectors, not codec round trips.
        self.assertEqual(decode(bytes.fromhex('0100'), 1), b'\x80')
        self.assertEqual(decode(bytes.fromhex('557f00017f55002a'), 7), bytes.fromhex('ff00817fd500aa'))
        for packed, length in [(b'\x02\x00', 1), (b'\x00\x80', 1), (b'\0', 0), (b'', -1)]:
            with self.assertRaises(ValueError):
                decode(packed, length)

    def test_each_scope_and_populated_first_last_slots(self):
        for scope, count in [('settings', 8), ('current', 11), ('all', 95)]:
            with self.subTest(scope=scope):
                result = validate_backup(archive(scope))
                self.assertEqual(result['records'], count)

    def test_readback_ignores_channel_time_and_order(self):
        actual = archive(channel=15)
        actual['records'].reverse()
        actual['createdAt'] = 'different capture time'
        self.assertEqual(compare_backups(archive(), actual)['status'], 'pass')

    def test_readback_detects_data_and_empty_slot_changes(self):
        changed = archive()
        changed['records'][0] = record('global', channel=0)
        wire = bytearray.fromhex(changed['records'][0]['data'])
        wire[30] ^= 1
        changed['records'][0].update(data=wire.hex(), sha256=hashlib.sha256(wire).hexdigest())
        with self.assertRaises(ValueError): compare_backups(archive(), changed)
        with self.assertRaises(ValueError): compare_backups(archive(), archive('current'))
        changed = archive()
        changed['records'][7] = record('scale', 5)
        with self.assertRaises(ValueError): compare_backups(archive(), changed)

    def test_missing_duplicate_orphan_and_wrong_owner(self):
        baseline = archive()
        variants = [baseline['records'][:-1], baseline['records'] + [baseline['records'][0]],
                    baseline['records'] + [record('melody', 1)],
                    baseline['records'] + [record('melody', 0, 62)]]
        for rows in variants:
            with self.assertRaises(ValueError): validate_backup(dict(baseline, records=rows))

    def test_malformed_archive_fields(self):
        for key, value in [('channel', True), ('channel', 16), ('version', True),
                           ('complete', 1), ('scope', []), ('records', {}),
                           ('excludes', []), ('excludes', ['firmware'] * 3)]:
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError): validate_backup(dict(archive(), **{key: value}))

    def test_malformed_record_fields(self):
        for key, value in [('kind', []), ('index', 0), ('project', 0), ('data', None),
                           ('data', '00 '), ('data', '00' * 7501), ('sha256', '0' * 64)]:
            bad = archive()
            bad['records'][0][key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError): validate_backup(bad)
        for key in ('index', 'project', 'sha256'):
            bad = archive()
            del bad['records'][0][key]
            with self.assertRaises(ValueError): validate_backup(bad)

    def test_wrong_frame_tag_slot_and_noncanonical_packing(self):
        for row_index, byte_index, value in [(0, 2, 0x31), (0, 6, 0x44), (0, 8, 0),
                                            (2, 7, 4), (2, -3, 2), (0, 9, 128)]:
            bad = archive()
            row = bad['records'][row_index]
            wire = bytearray.fromhex(row['data'])
            wire[byte_index] = value
            row.update(data=wire.hex(), sha256=hashlib.sha256(wire).hexdigest())
            with self.subTest(row=row_index, byte=byte_index):
                with self.assertRaises(ValueError): validate_backup(bad)

    def test_empty_required_data_and_boolean_indices(self):
        for kind in ('currentProject', 'melody', 'rhythm'):
            bad = archive()
            row = next(r for r in bad['records'] if r['kind'] == kind)
            row.update(data=None, sha256=None)
            with self.assertRaises(ValueError): validate_backup(bad)
        bad = archive()
        bad['records'][2]['index'] = False
        with self.assertRaises(ValueError): validate_backup(bad)
