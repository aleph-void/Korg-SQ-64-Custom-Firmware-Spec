import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from sq64_spec.image import inspect, REGIONS
from sq64_spec.report import evaluate, catalog
from sq64_spec.protocol import PREFIX, validate_transfer


def image():
    data = bytearray(0x38100)
    data[:16] = b'KORG SYSTEM FILE'; data[16:32] = b'SQ-64'.ljust(16, b'\0'); data[32:40] = b'SYSTEM\0\0'
    data[0x2c:0x30] = bytes([0, 1, 96, 255]); struct.pack_into('<4I', data, 0x30, 0, 0x38000, 0, 0x38000)
    struct.pack_into('<2I', data, 256, 0x20010000, 0x00200009)
    for start, length in REGIONS:
        checksum = sum(struct.unpack_from('<' + 'H' * (length // 2), data, 256 + start)) & 65535
        struct.pack_into('<H', data, 256 + start + length - 2, -checksum & 65535)
    return data


def integer(n, width=4): return bytes((n >> (7 * i)) & 127 for i in reversed(range(width)))
def frame(direction, command, body=b''): return {'direction': direction, 'hex': (PREFIX + bytes([command]) + body + b'\xf7').hex()}
def transcript(payload):
    events = [frame('host', 0), frame('device', 1, b'\1' + integer(1024) + b'\0'), frame('host', 2, b'\0'), frame('device', 3, b'\2\0'), frame('host', 4, b'\0\0' + integer(0) + integer(len(payload)) + b'\x43\0' + integer(1024)), frame('device', 5, b'\0')]
    for i in range(0, len(payload), 1024):
        raw = payload[i:i+1024]; packed = bytearray()
        for j in range(0, len(raw), 7):
            group = raw[j:j+7]; packed.append(sum((b >> 7) << bit for bit, b in enumerate(group))); packed.extend(b & 127 for b in group)
        events.extend([frame('host', 6, integer(i // 1024) + packed + bytes([sum(packed) & 127])), frame('device', 5, b'\0')])
    return events


class ContractTests(unittest.TestCase):
    def test_image_profile_is_bounded(self):
        report = evaluate(image(), profile='image')
        self.assertEqual(report['status'], 'pass'); self.assertFalse(report['hardwareValidated']); self.assertEqual(len(report['results']), 7)

    def test_default_cannot_claim_hardware(self):
        report = evaluate(image()); self.assertEqual(report['status'], 'incomplete'); self.assertTrue(report['releaseBlockers'])

    def test_mutations_fail_each_static_requirement(self):
        cases = [(0, 'PKG-001'), (16, 'PKG-002'), (0x30, 'PKG-003'), (0x2a, 'PKG-004'), (0x110, 'PKG-005'), (256, 'BOOT-001'), (260, 'BOOT-002')]
        for offset, expected in cases:
            with self.subTest(requirement=expected):
                data = image(); data[offset] ^= 0x40 if offset == 0x2a else 1
                rows = {r['id']: r['status'] for r in inspect(data)[1]}; self.assertEqual(rows[expected], 'fail')
        for n in (0, 15, 255, 256, 0x380ff, 0x38101): self.assertEqual(evaluate(bytes(n), profile='image')['status'], 'fail')

    def test_evidence_binding_overrides_duplicates(self):
        base = {'format': 'sq64-evidence', 'version': 1, 'imageSha256': hashlib.sha256(image()).hexdigest(), 'results': []}
        for results in ([{'id': 'PKG-001', 'status': 'pass'}], [{'id': 'unknown', 'status': 'fail'}], [{'id': 'CPU-001', 'status': 'fail'}] * 2):
            with self.assertRaises(ValueError): evaluate(image(), evidence=dict(base, results=results))
        with self.assertRaises(ValueError): evaluate(image(), evidence=dict(base, imageSha256='0' * 64))

    def test_artifacts_verified_and_confined(self):
        item = {'id': 'CPU-001', 'status': 'pass', 'procedure': 'Directed alignment capture', 'observations': 'Fault observed', 'artifact': 'capture.json', 'artifactSha256': hashlib.sha256(b'{}').hexdigest()}
        evidence = {'format': 'sq64-evidence', 'version': 1, 'imageSha256': hashlib.sha256(image()).hexdigest(), 'results': [item]}
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'capture.json').write_bytes(b'{}')
            row = lambda report: next(r for r in report['results'] if r['id'] == 'CPU-001')
            self.assertEqual(row(evaluate(image(), evidence=evidence))['status'], 'not-run')
            self.assertTrue(row(evaluate(image(), evidence=evidence, artifact_root=folder))['artifactVerified'])
            item['artifact'] = '../capture.json'
            with self.assertRaises(ValueError): evaluate(image(), evidence=evidence, artifact_root=folder)
            item['artifact'] = 'capture.json'; item['artifactSha256'] = '0' * 64
            with self.assertRaises(ValueError): evaluate(image(), evidence=evidence, artifact_root=folder)

    def test_full_transfer_reconstructs_payload(self):
        data = image()[256:]; self.assertEqual(validate_transfer(transcript(data), data)['status'], 'pass')

    def test_transfer_rejects_order_truncation_error_extra_fill(self):
        data = image()[256:]; good = transcript(data)
        bad = [good[:-1], good[:7] + good[8:], good + good[-2:], [good[0], frame('device', 1)], good[:7] + [frame('device', 5, b'\1')] + good[8:], good[:6] + [frame('host', 8, integer(0) + b'\0\0')] + good[7:]]
        for events in bad:
            with self.subTest(length=len(events)):
                with self.assertRaises(ValueError): validate_transfer(events, data)

    def test_unique_catalog_ids_and_procedures(self):
        rows = catalog()['requirements']; self.assertEqual(len(rows), len({r['id'] for r in rows}))
        self.assertTrue(all(r['shall'] and r['verification'] and r['profiles'] for r in rows))

if __name__ == '__main__': unittest.main()
