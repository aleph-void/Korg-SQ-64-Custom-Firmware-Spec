"""Reference-monitor and protocol tests; these do not execute an emulator."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from sq64_spec.watch import (WatchMonitor, WatchValidationError, canonical_bytes, load_rules,
                             required_capabilities, ruleset_digest, state_addresses, validate_contract)
from sq64_spec.report import evaluate
from test_contract import image

ROOT = Path(__file__).resolve().parents[1]


def changes(value, edits):
    value=deepcopy(value)
    for edit in edits:
        cursor=value
        for component in edit['path'][:-1]: cursor=cursor[component]
        cursor[edit['path'][-1]]=deepcopy(edit['value'])
    return value


class WatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract=load_rules()
        cls.fixtures=json.loads((ROOT/'sq64_spec/watch-fixtures.json').read_text())

    def monitor(self, **kwargs):
        return WatchMonitor(kwargs.get('contract',self.contract),identity=kwargs.get('identity',self.fixtures['identity']),
                            capabilities=kwargs.get('capabilities',self.fixtures['capabilities']))

    def initial(self): return deepcopy(self.fixtures['cases'][0]['events'][0])

    def test_shared_vectors(self):
        self.assertEqual(self.fixtures['rulesetSha256'],ruleset_digest(self.contract))
        for case in self.fixtures['cases']:
            with self.subTest(case=case['name']):
                contract=changes(self.contract,case['contractChanges']);identity=changes(self.fixtures['identity'],case['identityChanges'])
                if case['rebindRules']:identity['rulesetSha256']=ruleset_digest(contract)
                monitor=WatchMonitor(contract,identity=identity,capabilities=changes(self.fixtures['capabilities'],case['capabilityChanges']))
                first=None
                for e in case['events']:
                    outcome=monitor.evaluate(e)
                    if monitor.terminated:
                        if first is None:first=monitor.report()
                        else:self.assertEqual(monitor.report(),first,'Terminal evidence changed')
                    self.assertEqual(outcome['allow'],not monitor.terminated)
                result=monitor.report();expected=case['expected']
                self.assertEqual(result['status'],expected['status'])
                self.assertEqual((result['violation'] or {}).get('ruleId'),expected['ruleId'])
                self.assertEqual((result['monitoringError'] or {}).get('code'),expected['errorCode'])
                if expected['ruleId']:
                    v=result['violation'];self.assertEqual(v['event']['sequence'],expected['sequence']);self.assertEqual(v['matchingRuleIds'],expected['matchingRuleIds'])
                    self.assertEqual(v['identity']['imageSha256'],identity['imageSha256'])
                    self.assertEqual([r['id'] for r in result['critical']['results'] if r['status']=='pass'],[expected['ruleId']])
                else:self.assertTrue(all(r['status']=='not-run' for r in result['critical']['results']))
                self.assertFalse(result['recoveryGuaranteed']);self.assertFalse(result['hardwareValidated'])
                json.dumps(result,allow_nan=False)

    def test_no_execution_before_initial_state(self):
        monitor=self.monitor();self.assertFalse(monitor.can_execute);self.assertFalse(monitor.terminated)
        self.assertEqual(monitor.evaluate(self.initial()),dict(allow=True,status='active'))
        self.assertTrue(monitor.can_execute)

    def test_contract_strictness_and_parser_limits(self):
        for key,value in [('version',True),('specVersion',1),('rules',[]),('unknown',1),('normalization',None)]:
            c=deepcopy(self.contract);c[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate_contract(c)
            self.assertEqual(self.monitor(contract=c).report()['status'],'monitoring-error')
        for raw in ('{"version":1,"version":1}', '{"x":NaN}', '{"x":1.0}', '{"x":1e999}', b'\xff', '['*10000, ' '*65537):
            with self.subTest(raw=str(raw)[:30]),self.assertRaises(ValueError):validate_contract(raw)
        c=deepcopy(self.contract);c['rules'].pop()
        with self.assertRaisesRegex(ValueError,'mandatory'):validate_contract(c)
        c=deepcopy(self.contract);c['rules'][0]['predicate']={'op':'all','args':[]}
        with self.assertRaises(ValueError):validate_contract(c)
        c=deepcopy(self.contract)
        for _ in range(10):c['rules'][0]['predicate']={'op':'all','args':[c['rules'][0]['predicate']]}
        with self.assertRaises(ValueError):validate_contract(c)
        cycle={};cycle['cycle']=cycle
        with self.assertRaises(ValueError):validate_contract(cycle)

    def test_canonical_digest_has_independent_known_vector(self):
        value={'z':[0,True,None],'a':'ASCII "quoted" \\'}
        expected=b'{"a":"ASCII \\"quoted\\" \\\\","z":[0,true,null]}'
        self.assertEqual(canonical_bytes(value),expected)
        c=self.contract
        text=json.dumps(c,sort_keys=False,indent=4)
        self.assertEqual(ruleset_digest(text),ruleset_digest(c))
        independent=json.dumps(c,ensure_ascii=True,sort_keys=True,separators=(',', ':')).encode('ascii')
        self.assertEqual(ruleset_digest(c),hashlib.sha256(independent).hexdigest())
        reordered=deepcopy(c);reordered['rules'].reverse()
        self.assertNotEqual(ruleset_digest(reordered),ruleset_digest(c))
        for bad in (float('inf'),1.0,-1,'non-ASCII é',{'x':2**53},'x'*513):
            with self.assertRaises(ValueError):canonical_bytes(bad)

    def test_monitors_do_not_retain_mutable_caller_state(self):
        c=deepcopy(self.contract);identity=deepcopy(self.fixtures['identity']);caps=deepcopy(self.fixtures['capabilities'])
        m=WatchMonitor(c,identity=identity,capabilities=caps)
        c['rules'].clear();identity.clear();caps.clear()
        event=self.initial();m.evaluate(event);event['registers'].clear()
        self.assertEqual(m.report()['recentEvents'][0]['registers'],self.initial()['registers'])
        report=m.report();report['critical']['results'].clear();report['identity'].clear()
        self.assertEqual(len(m.report()['critical']['results']),5)

    def test_latch_survives_error_and_reports_are_copies(self):
        m=self.monitor()
        for e in self.fixtures['cases'][0]['events']:m.evaluate(e)
        before=m.report();v=m.violation();v.clear()
        self.assertEqual(m.fail('backend-failure')['status'],'violation')
        self.assertEqual(m.evaluate(None)['status'],'violation');self.assertEqual(m.report(),before)
        self.assertIsNotNone(m.violation())

    def test_monitor_failures_are_not_firmware_hazards(self):
        for reason in ('observer-failure','backend-failure','capability-lost'):
            m=self.monitor();self.assertFalse(m.fail(reason)['allow']);r=m.report()
            self.assertEqual(r['monitoringError']['code'],reason);self.assertIsNone(r['violation'])
            self.assertTrue(r['terminated']);self.assertFalse(r['critical']['terminated'])
            self.assertFalse(any(row['status']=='pass' for row in r['critical']['results']))
            self.assertFalse(m.evaluate(self.initial())['allow'])
        m=self.monitor()
        with patch('sq64_spec.watch._matches',side_effect=RuntimeError('internal failure')):m.evaluate(self.initial())
        self.assertEqual(m.report()['monitoringError']['code'],'internal-error');self.assertIsNone(m.violation())

    def test_history_and_malformed_diagnostics_are_bounded(self):
        m=self.monitor();m.evaluate(self.initial())
        for i in range(1,20):
            e=dict(kind='instruction-boundary',sequence=i,tick=i,source='cpu',pc=None,exception=None,phase='application',mode='fast')
            self.assertTrue(m.evaluate(e)['allow'])
        self.assertEqual([e['sequence'] for e in m.report()['recentEvents']],[16,17,18,19])
        m.evaluate({'kind':'x'*100000,'payload':[0]*100000})
        self.assertEqual(m.report()['monitoringError']['code'],'invalid-event')
        self.assertLess(len(json.dumps(m.report()['monitoringError'])),1024)

    def test_attempts_do_not_commit_register_state(self):
        m=self.monitor();m.evaluate(self.initial())
        # Safe proposed DMA target is rejected by the model: no transition follows.
        write=dict(kind='memory-write',sequence=1,tick=1,source='cpu',pc=0x200008,exception=0,phase='boot',mode='run',space='cpu',address=0x4002601c,width=4,value='00000008',locked=True)
        self.assertTrue(m.evaluate(write)['allow'])
        # Enabling the still-zero target cannot discover a mutation we did not commit.
        transition=dict(kind='register-transition',sequence=2,tick=2,source='cpu',pc=0x200008,exception=0,phase='boot',mode='run',registers=[dict(address=0x40026010,value=1)])
        self.assertTrue(m.evaluate(transition)['allow'])
        # Applying the same target as an actual transition must trip immediately.
        transition.update(sequence=3,tick=3,registers=[dict(address=0x4002601c,value=0x8000000)])
        self.assertFalse(m.evaluate(transition)['allow']);self.assertEqual(m.violation()['ruleId'],'CRITICAL-001')

    def test_ordinary_conformance_pass_has_no_hazard_polarity(self):
        r=evaluate(image(),profile='image');self.assertEqual(r['status'],'pass')
        hazard=lambda row:row.get('severity')=='critical' and row.get('unsafeWhen')=='pass' and row.get('status')=='pass'
        self.assertFalse(any(hazard(row) for row in r['results']))
        m=self.monitor();m.evaluate(self.initial());self.assertFalse(any(hazard(row) for row in m.report()['critical']['results']))
        metadata=dict(severity='critical',unsafeWhen='pass',status='pass')
        for field,value in [('severity','warning'),('unsafeWhen','fail'),('status','fail'),('status','not-run')]:
            self.assertFalse(hazard(dict(metadata,**{field:value})))

    def test_model_rules_and_legacy_metadata_stay_in_sync(self):
        self.assertEqual(self.contract['modelContractSha256'],hashlib.sha256((ROOT/'sq64_spec/board.json').read_bytes()).hexdigest())
        old=json.loads((ROOT/'sq64_spec/critical.json').read_text())
        self.assertEqual(old['specVersion'],self.contract['specVersion'])
        self.assertEqual([r['id'] for r in old['checks']],[r['id'] for r in self.contract['rules']])
        for a,b in zip(old['checks'],self.contract['rules']):
            self.assertEqual(a['title'],b['title']);self.assertEqual(a['requirements'],b['requirements'])

    def test_generated_artifacts(self):
        for tool in ('render_requirements.py','build_watch_fixtures.py','render_watch_rules.py'):
            result=subprocess.run([sys.executable,str(ROOT/'tools'/tool),'--check'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_cli_exports_and_offline_session_polarity(self):
        def cli(*args):
            return subprocess.run([sys.executable,'-m','sq64_spec',*args],cwd=ROOT,capture_output=True,text=True)
        for flag,expected in (('--watch-rules','sq64-watch-rules'),('--watch-fixtures','sq64-watch-fixtures')):
            result=cli(flag);self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(json.loads(result.stdout)['format'],expected)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'session.json';out=Path(folder)/'report.json'
            session=dict(format='sq64-watch-session',version=1,identity=self.fixtures['identity'],capabilities=self.fixtures['capabilities'],events=[self.initial()])
            path.write_text(json.dumps(session))
            result=cli('--watch-session',str(path),'--output',str(out));self.assertEqual(result.returncode,0,result.stderr)
            report=json.loads(out.read_text());self.assertEqual(report['inputScope'],'supplied-observations-only');self.assertEqual(report['status'],'active')
            session['events']=self.fixtures['cases'][0]['events'];path.write_text(json.dumps(session))
            result=cli('--watch-session',str(path));self.assertEqual(result.returncode,1,result.stderr);self.assertEqual(json.loads(result.stdout)['status'],'violation')
            session['events']=[self.initial(),{}];path.write_text(json.dumps(session))
            result=cli('--watch-session',str(path));self.assertEqual(result.returncode,3,result.stderr);self.assertEqual(json.loads(result.stdout)['status'],'monitoring-error')
            self.assertEqual(cli('--watch-session',str(path),'--catalog').returncode,2)
            path.write_text('{"format":NaN}')
            result=cli('--watch-session',str(path));self.assertEqual(result.returncode,3);self.assertIn('Watch tooling error',result.stderr)

    def test_contract_limits_and_maximum_predicate_depth(self):
        c=deepcopy(self.contract)
        c['rules'][0]['predicate']={'op':'eq','field':'kind','value':'memory-write'}
        for _ in range(8):c['rules'][0]['predicate']={'op':'all','args':[c['rules'][0]['predicate']]}
        self.assertEqual(validate_contract(c)['rules'][0]['id'],'CRITICAL-001')
        c['rules'][0]['predicate']={'op':'all','args':[c['rules'][0]['predicate']]}
        with self.assertRaises(ValueError):validate_contract(c)

    def test_complete_metadata_in_violation(self):
        c=next(c for c in self.fixtures['cases'] if c['name']=='spi-dma-locked-interrupt')
        m=self.monitor()
        for e in c['events']:m.evaluate(e)
        report=m.report();v=report['violation'];self.assertTrue(report['identityVerified'])
        self.assertEqual(v['event'],c['events'][1]);self.assertIsNone(v['event']['pc'])
        self.assertEqual(v['match']['value'],'c7');self.assertEqual(v['match']['source'],'dma')
        self.assertEqual(v['match']['width'],1);self.assertIsNone(v['match']['address'])
        self.assertEqual(v['identity'],self.fixtures['identity'])
        self.assertEqual(report['rulesetSha256'],self.fixtures['rulesetSha256'])

    def test_invalid_contract_retains_supplied_image_identity_without_trusting_it(self):
        m=self.monitor(contract={});report=m.report()
        self.assertEqual(report['identity']['imageSha256'],self.fixtures['identity']['imageSha256'])
        self.assertFalse(report['identityVerified']);self.assertIsNone(report['rulesetSha256'])
        self.assertIsNone(report['violation']);self.assertEqual(report['monitoringError']['code'],'invalid-contract')
