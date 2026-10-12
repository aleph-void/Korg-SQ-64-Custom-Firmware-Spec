"""Synthetic policy/capture fixtures; these are not recovery trial evidence."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from sq64_spec.recovery import evaluate_recovery, FORBIDDEN
from sq64_spec.report import evaluate, catalog, model_contract_digest
from test_contract import image
from test_evidence import evidence, declaration

def raw(value): return json.dumps(value).encode()
def sha(value): return hashlib.sha256(value).hexdigest()
def region(start, length, **extra): return dict(space='spi-flash',start=start,length=length,purpose='Synthetic ownership',**extra)

class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        Path(self.folder.name,'installer').write_bytes(b'installer'); Path(self.folder.name,'observer').write_bytes(b'observer'); Path(self.folder.name,'capture.json').write_bytes(b'{}')
        self.baseline=image(); self.candidate=image()
        self.policy=dict(format='sq64-recovery-policy',version=1,specVersion='0.3.0',baselineSha256=sha(self.baseline),reviewRevision='synthetic-review',
            installer=dict(artifact='installer',artifactSha256=sha(b'installer')),observer=dict(artifact='observer',artifactSha256=sha(b'observer')),
            protected=[region(0,0x8000,kind='recovery'),region(0x80000,0x1000,kind='calibration')],
            writes=dict(installation=[region(0x10000,0x20000)],runtime=[region(0x40000,0x40000)]),spiGeometry=dict(pageSize=256,eraseSizes=[4096,65536]))
        self.doc=evidence(kind='emulator'); self.doc['results']=[]
        self.doc['contexts']['test']['tools']=[dict(name=n,version='1',sha256=sha(n.encode())) for n in ('installer','observer')]
        self.trace=dict(format='sq64-write-trace',version=1,runs=[dict(name=p,phase=p,complete=True,captureStart='before-execution',captureEnd='after-completion',baselineIdentity='content-measurement',coverage='all-persistent-mutation-attempts',context='test',eventCount=0,events=[]) for p in ('installation','runtime')])
    def inputs(self):
        policy=raw(self.policy)
        identity=dict(imageSha256=sha(self.candidate),baselineSha256=sha(self.baseline),policySha256=sha(policy),installerSha256=sha(b'installer'),observerSha256=sha(b'observer'))
        self.trace.update(identity); trace=raw(self.trace)
        self.doc.update(imageSha256=sha(self.candidate),recovery=dict(identity,traceSha256=sha(trace)))
        return dict(baseline=self.baseline,policy_data=policy,approved_policy_sha256=sha(policy),trace_data=trace,evidence=self.doc,contexts=self.doc['contexts'],artifact_root=self.folder.name,spec_version='0.3.0',model_hash=model_contract_digest())
    def check(self, **override):
        options=self.inputs(); options.update(override); return evaluate_recovery(self.candidate,**options)
    def event(self, operation='program',phase=1,**data):
        events=self.trace['runs'][phase]['events']; events.append(dict(sequence=len(events),operation=operation,**data)); self.trace['runs'][phase]['eventCount']=len(events)
    def test_bounded_capture_pass_is_not_recovery_guarantee(self):
        result=self.check(); self.assertEqual(result['status'],'pass',result); self.assertFalse(result['recoveryGuaranteed'])
    def test_missing_inputs_fail_closed(self):
        for key in ('baseline','policy_data','approved_policy_sha256','trace_data','artifact_root'):
            with self.subTest(key=key): self.assertEqual(self.check(**{key:None})['status'],'fail')
        for key in ('policy_data','trace_data'):
            for value in ({},[],True):
                with self.subTest(key=key,value=value): self.assertEqual(self.check(**{key:value})['status'],'fail')
    def test_policy_pin_artifacts_and_baseline(self):
        self.assertIn('pinned',self.check(approved_policy_sha256='0'*64)['error'])
        self.policy['baselineSha256']='0'*64; self.assertEqual(self.check()['status'],'fail')
        self.policy['baselineSha256']=sha(self.baseline)
        Path(self.folder.name,'installer').write_bytes(b'changed'); self.assertEqual(self.check()['status'],'fail')
    def test_policy_cannot_waive_internal_or_reserved_regions(self):
        for item in (dict(space='internal-flash',start=0,length=1,purpose='waiver'),region(0x80000,1)):
            self.policy['writes']['runtime']=[item]; self.assertEqual(self.check()['status'],'fail')
    def test_changed_internal_recovery_bytes_fail(self):
        self.candidate[300]^=1
        result=self.check(); self.assertEqual(result['checks'][0]['status'],'fail')
        self.assertEqual(result['status'],'fail')
    def test_all_forbidden_operations_fail(self):
        for op in FORBIDDEN:
            with self.subTest(operation=op):
                self.trace['runs'][1]['events']=[]; self.event(op)
                result=self.check(); self.assertEqual(next(r for r in result['checks'] if r['id']=='RECOVERY-003')['status'],'fail')
    def test_same_bytes_erase_then_restore_is_still_forbidden(self):
        self.event('erase',space='internal-flash',start=0,length=16384)
        self.event('program',space='internal-flash',start=0,length=16384)
        result=self.check(); self.assertEqual(next(r for r in result['checks'] if r['id']=='RECOVERY-002')['status'],'fail')
    def test_geometry_boundaries_and_phase_allowlists(self):
        for operation,phase,start,length in [('program',1,0x400ff,2),('erase',1,0x40001,4096),('erase',1,0x40000,8192),('program',0,0x40000,1),('program',1,0x7ffff,2)]:
            with self.subTest(operation=operation,start=start,length=length):
                for run in self.trace['runs']:run.update(events=[],eventCount=0)
                self.event(operation,phase,space='spi-flash',start=start,length=length)
                result=self.check(); self.assertEqual(next(r for r in result['checks'] if r['id']=='RECOVERY-004')['status'],'fail')
    def test_complete_trace_must_cover_changed_candidate_bytes(self):
        self.candidate[256+0x14000]^=1
        self.assertIn('every changed',self.check()['error'])
        self.event('program',0,space='spi-flash',start=0x10000,length=1)
        self.assertEqual(self.check()['status'],'pass')
    def test_trace_truncation_unknown_operations_and_identity(self):
        for key,value in [('complete',False),('eventCount',1),('context','missing'),('captureStart','after-execution')]:
            old=self.trace['runs'][0][key]; self.trace['runs'][0][key]=value
            self.assertEqual(self.check()['status'],'fail'); self.trace['runs'][0][key]=old
        self.event('made-up'); self.assertIn('Unrecognized',self.check()['error'])
    def test_wrong_context_or_observer_rejected(self):
        self.doc['contexts']['test']['target']='probe'; self.assertEqual(self.check()['status'],'fail')
        self.doc['contexts']['test']['target']='candidate'; self.doc['contexts']['test']['tools']=[]; self.assertEqual(self.check()['status'],'fail')
    def test_incomplete_application_evidence_is_rejected(self):
        r=evaluate(self.candidate,profile='application-only'); self.assertEqual(r['status'],'fail'); self.assertEqual(r['acceptance'],'rejected')
        with self.assertRaises(ValueError):evaluate(self.candidate,profile='image',baseline=self.baseline)
    def test_full_synthetic_acceptance_and_hazard_override(self):
        candidate=declaration()
        self.doc['contexts']['review']=dict(self.doc['contexts']['test'],kind='review')
        for requirement in catalog()['requirements']:
            if 'application-only' not in requirement['profiles'] or 'image' in requirement['profiles']:continue
            row=evidence(requirement['id'],kind='emulator')['results'][0]
            if requirement['id']=='RECOVERY-001':row['context']='review'
            if requirement['quantitative']:
                candidate['limits'].append(dict(id=requirement['id'],metric='fixture',unit='count',min=0,max=1));row['measurements']=[dict(metric='fixture',unit='count',value=1,uncertainty=0)]
            self.doc['results'].append(row)
        def report():
            args=self.inputs()
            return evaluate(self.candidate,profile='application-only',declaration=candidate,evidence=self.doc,artifact_root=self.folder.name,baseline=args['baseline'],recovery_policy=args['policy_data'],approved_policy_sha256=args['approved_policy_sha256'],write_trace=args['trace_data'])
        result=report(); self.assertEqual(result['status'],'pass',result); self.assertFalse(result['hardwareValidated']); self.assertFalse(result['recoveryGuaranteed'])
        self.event('mass-erase'); result=report(); self.assertEqual(result['status'],'fail'); self.assertEqual(result['acceptance'],'rejected')
