import hashlib
from pathlib import Path
import tempfile
import unittest

from sq64_spec.declaration import FEATURES
from sq64_spec.report import catalog, evaluate, model_contract_digest
from sq64_spec.validation import load_json
from test_contract import image


def declaration():
    return {'format': 'sq64-candidate', 'version': 1,
            'imageSha256': hashlib.sha256(image()).hexdigest(), 'sourceRevision': 'synthetic-fixture-1',
            'features': {key: 'Original synthetic test declaration; not a hardware bound' for key in FEATURES},
            'limits': [], 'deviations': []}


def evidence(identifier='PANEL-001', kind='hardware'):
    requirement = next(r for r in catalog()['requirements'] if r['id'] == identifier)
    return {'format': 'sq64-evidence', 'version': 2, 'specVersion': catalog()['version'],
            'imageSha256': hashlib.sha256(image()).hexdigest(),
            'contexts': {'test': {'kind': kind, 'target': 'candidate', 'environment': 'Original synthetic fixture',
                                 'sourceRevision': 'synthetic-fixture-1', 'fixtureRevision': '1',
                                 'modelContractSha256': model_contract_digest(),
                                 'tools': [{'name': 'synthetic fixture', 'version': '1', 'sha256': '0' * 64}]}},
            'results': [{'id': identifier, 'status': 'pass', 'context': 'test', 'procedure': 'Synthetic test only',
                         'observations': 'Synthetic test only', 'artifact': 'capture.json',
                         'artifactSha256': hashlib.sha256(b'{}').hexdigest(),
                         'cases': [{'name': name, 'expected': 'Fixture pass', 'observed': 'Fixture pass', 'status': 'pass'}
                                   for name in requirement['cases']]}]}


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        Path(self.folder.name, 'capture.json').write_bytes(b'{}')

    def run_evidence(self, document, profile='hardware', candidate=None):
        return evaluate(image(), profile=profile, evidence=document, artifact_root=self.folder.name,
                        declaration=declaration() if candidate is None else candidate)

    def row(self, document, **kwargs):
        return next(r for r in self.run_evidence(document, **kwargs)['results'] if r['id'] == document['results'][0]['id'])

    def test_complete_hardware_row_retains_release_gate(self):
        report = self.run_evidence(evidence())
        self.assertEqual(self.row(evidence())['status'], 'pass')
        self.assertEqual(report['status'], 'incomplete')
        self.assertFalse(report['hardwareValidated'])
        self.assertEqual(sum(report['counts'].values()), len(report['results']))

    def test_emulator_result_is_only_software_evidence(self):
        document = evidence(kind='emulator')
        self.assertEqual(self.row(document)['status'], 'not-run')
        self.assertEqual(self.row(document, profile='software')['status'], 'pass')
        document['contexts']['test']['modelContractSha256'] = '0' * 64
        with self.assertRaises(ValueError): self.row(document, profile='software')

    def test_probe_cannot_pass_candidate_requirement(self):
        document = evidence()
        document['contexts']['test']['target'] = 'probe'
        self.assertEqual(self.row(document)['status'], 'not-run')

    def test_cases_missing_not_run_failed_and_duplicate(self):
        document = evidence()
        document['results'][0]['cases'].pop()
        self.assertEqual(self.row(document)['status'], 'not-run')
        for status in ('fail', 'not-run'):
            document = evidence()
            document['results'][0]['cases'][0]['status'] = status
            self.assertEqual(self.row(document)['status'], status)
        document = evidence()
        document['results'][0]['cases'] *= 2
        with self.assertRaises(ValueError): self.row(document)

    def test_context_source_tool_and_spec_identity(self):
        for key, value in [('kind', 'browser'), ('tools', []), ('fixtureRevision', ''), ('sourceRevision', 'other')]:
            document = evidence()
            document['contexts']['test'][key] = value
            with self.subTest(field=key):
                with self.assertRaises(ValueError): self.row(document)
        document = evidence()
        document['specVersion'] = 'old'
        with self.assertRaises(ValueError): self.row(document)
        document = evidence()
        document['results'][0]['context'] = []
        with self.assertRaises(ValueError): self.row(document)

    def test_legacy_evidence_is_visible_but_not_credited(self):
        document = evidence()
        document['version'] = 1
        row = self.row(document)
        self.assertTrue(row['artifactVerified'])
        self.assertEqual(row['status'], 'not-run')
        self.assertEqual(row['suppliedStatus'], 'pass')

    def test_declaration_required_and_strict(self):
        report = evaluate(image(), evidence=evidence(), artifact_root=self.folder.name)
        self.assertEqual(next(r['status'] for r in report['results'] if r['id'] == 'PANEL-001'), 'not-run')
        for key, value in [('imageSha256', '0' * 64), ('features', {}), ('limits', {}), ('deviations', None)]:
            candidate = declaration()
            candidate[key] = value
            with self.assertRaises(ValueError): self.run_evidence(evidence(), candidate=candidate)

    def test_quantitative_missing_limits_and_measurements(self):
        document = evidence('CLOCK-001')
        self.assertEqual(self.row(document)['status'], 'not-run')
        candidate = declaration()
        candidate['limits'] = [{'id': 'CLOCK-001', 'metric': 'jitter', 'unit': 'us', 'min': 0, 'max': 20}]
        self.assertEqual(self.row(document, candidate=candidate)['status'], 'not-run')
        document['results'][0]['measurements'] = [{'metric': 'jitter', 'unit': 'us', 'value': 19, 'uncertainty': 1}]
        self.assertEqual(self.row(document, candidate=candidate)['status'], 'pass')
        document['results'][0]['measurements'][0]['uncertainty'] = 2
        self.assertEqual(self.row(document, candidate=candidate)['status'], 'fail')

    def test_measurement_schema_units_duplicates_and_nonfinite(self):
        candidate = declaration()
        candidate['limits'] = [{'id': 'CLOCK-001', 'metric': 'jitter', 'unit': 'us', 'min': 0, 'max': 20}]
        for key, value in [('metric', 'unknown'), ('unit', 'ms'), ('value', float('nan')),
                           ('value', True), ('uncertainty', -1), ('value', 10 ** 400)]:
            document = evidence('CLOCK-001')
            measurement = {'metric': 'jitter', 'unit': 'us', 'value': 1, 'uncertainty': 0}
            measurement[key] = value
            document['results'][0]['measurements'] = [measurement]
            with self.subTest(field=key, value=str(value)[:20]):
                with self.assertRaises(ValueError): self.row(document, candidate=candidate)

    def test_traversal_absolute_windows_and_symlink_paths(self):
        for path in ('../capture.json', '/tmp/capture.json', 'sub/../capture.json', 'C:\\capture.json'):
            document = evidence()
            document['results'][0]['artifact'] = path
            with self.assertRaises(ValueError): self.row(document)
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside, 'secret')
            target.write_bytes(b'{}')
            link = Path(self.folder.name, 'escape')
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest('Host does not permit symlinks')
            document = evidence()
            document['results'][0]['artifact'] = 'escape'
            with self.assertRaises(ValueError): self.row(document)

    def test_strict_json_duplicate_keys_and_nonfinite_constants(self):
        for text in ('{"status":"fail","status":"pass"}', '{"value":NaN}', '{"value":Infinity}', '{"value":1e999}'):
            with self.assertRaises(ValueError): load_json(text)

    def test_malformed_identifier_and_boolean_version(self):
        for key, value in [('id', []), ('id', {}), ('status', [])]:
            document = evidence()
            document['results'][0][key] = value
            with self.assertRaises(ValueError): self.row(document)
        document = evidence()
        document['version'] = True
        with self.assertRaises(ValueError): self.row(document)

    def test_complete_synthetic_software_profile_and_hardware_gate(self):
        document = evidence(kind='emulator')
        document['results'] = []
        candidate = declaration()
        for requirement in catalog()['requirements']:
            if 'software' not in requirement['profiles'] or 'image' in requirement['profiles']:
                continue
            row = evidence(requirement['id'], kind='emulator')['results'][0]
            if requirement['quantitative']:
                candidate['limits'].append({'id': requirement['id'], 'metric': 'fixture', 'unit': 'count', 'min': 0, 'max': 1})
                row['measurements'] = [{'metric': 'fixture', 'unit': 'count', 'value': 1, 'uncertainty': 0}]
            document['results'].append(row)
        report = self.run_evidence(document, profile='software', candidate=candidate)
        self.assertEqual(report['status'], 'pass')
        self.assertFalse(report['hardwareValidated'])
        self.assertEqual(self.run_evidence(document, candidate=candidate)['status'], 'incomplete')

    def test_compatibility_deviations_are_not_waivers(self):
        candidate = declaration()
        candidate['deviations'] = ['Synthetic incompatible behavior']
        report = self.run_evidence(evidence('COMPAT-004', kind='review'), profile='korg-compatible', candidate=candidate)
        self.assertTrue(any('deviations' in b for b in report['releaseBlockers']))

    def test_all_passing_hardware_rows_cannot_remove_board_release_gate(self):
        document = evidence()
        document['results'] = []
        candidate = declaration()
        for requirement in catalog()['requirements']:
            if 'hardware' not in requirement['profiles'] or 'image' in requirement['profiles']:
                continue
            row = evidence(requirement['id'])['results'][0]
            if requirement['quantitative']:
                candidate['limits'].append({'id': requirement['id'], 'metric': 'fixture', 'unit': 'count', 'min': 0, 'max': 1})
                row['measurements'] = [{'metric': 'fixture', 'unit': 'count', 'value': 1, 'uncertainty': 0}]
            document['results'].append(row)
        report = self.run_evidence(document, candidate=candidate)
        self.assertEqual(report['counts'], {'pass': 70, 'fail': 0, 'not-run': 0})
        self.assertEqual(report['status'], 'incomplete')
        self.assertFalse(report['hardwareValidated'])
