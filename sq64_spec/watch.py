"""Dependency-free interpreter for the bounded SQ-64 watch vocabulary v1.

No emulator access, expression evaluation, wall clock, or arbitrary callbacks.
Only the caller can stop its backend; allow=False is an unconditional stop order.
"""
from collections import deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

from .validation import load_json, digest

MAX_INT = (1 << 53) - 1
U32 = 1 << 32
EVENT_KINDS = ('initial-state', 'instruction-boundary', 'memory-write',
               'register-transition', 'spi-command', 'spi-mutation', 'dma-transfer')
SOURCES = ('cpu', 'dma', 'peripheral', 'model')
MODES = ('run', 'step', 'replay', 'fast')
PHASES = ('boot', 'application', 'interrupt')
OPS = ('all', 'any', 'eq', 'in', 'not-in', 'gt', 'overlap', 'bits-any', 'write-bits')
GUARANTEES = ('before-first-instruction', 'pre-side-effect', 'locked-attempts', 'all-cpu-aliases', 'unmapped-protected-writes', 'partial-writes', 'side-effect-free-state', 'all-dma-transitions', 'all-peripheral-writers', 'interrupt-paths', 'ordered-events', 'terminal-session', 'stop-midi', 'final-report')
FIELDS = {'kind': str, 'space': str, 'operation': str, 'source': str, 'origin': str,
          'address': int, 'width': int, 'length': int, 'end': int, 'number': int, 'command': int}
FACT_KINDS = ('memory-write', 'register-state', 'spi-command', 'spi-mutation', 'dma-span')
ERROR_WARNING = 'Runtime monitoring failed. Execution is stopped; no firmware hazard has been established by this error.'
CLAIM = 'No observed violation is not proof of hardware safety or complete conformance.'


class WatchValidationError(ValueError):
    """An invalid contract/observation, never evidence of a firmware hazard."""


def _require(condition, message):
    if not condition:
        raise WatchValidationError(message)


def _keys(value, names):
    _require(type(value) is dict and set(value) == set(names), 'Missing or unknown object fields')


def _int(value, low=0, high=MAX_INT):
    _require(type(value) is int and low <= value <= high, 'Invalid unsigned integer')


def _text(value):
    _require(type(value) is str and 0 < len(value) <= 512 and
             all(32 <= ord(c) < 127 for c in value), 'Expected bounded printable ASCII text')


def _list(value, maximum=64, minimum=1):
    _require(type(value) is list and minimum <= len(value) <= maximum, 'Invalid bounded list')


def _unique(value, maximum=64):
    _list(value, maximum)
    _require(all(type(v) in (int, str) for v in value) and len(value) == len(set(value)), 'Duplicate or invalid list members')


def _tree(value):
    """Reject unbounded, cyclic, non-JSON, floating-point and non-ASCII input."""
    stack, count = [(value, 0)], 0
    while stack:
        item, depth = stack.pop(); count += 1
        _require(count <= 8192 and depth <= 32, 'JSON structure exceeds limits')
        if type(item) is dict:
            _require(len(item) <= 256, 'Object exceeds field limit')
            for key, child in item.items():
                _text(key); stack.append((child, depth + 1))
        elif type(item) is list:
            _require(len(item) <= 512, 'Array exceeds limit')
            stack.extend((child, depth + 1) for child in item)
        elif type(item) is str:
            _text(item)
        elif type(item) is int:
            _int(item)
        else:
            _require(item is None or type(item) is bool, 'Non-JSON or unsupported scalar')


def _document(value, limit):
    if type(value) in (bytes, str):
        _require(len(value) <= limit, 'JSON document exceeds byte limit')
        if type(value) is bytes:
            value = value.decode('utf-8')
        value = load_json(value)
    _tree(value)
    _require(len(_canonical(value)) <= limit, 'JSON document exceeds byte limit')
    return deepcopy(value)


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def canonical_bytes(value):
    """Canonical restricted JSON: ASCII, sorted keys, no whitespace, integer numbers."""
    _tree(value)
    return _canonical(value)


def _field(node):
    _require(type(node.get('field')) is str and node['field'] in FIELDS, 'Unknown fact field')
    return FIELDS[node['field']]


def _predicate(node, spaces, depth=0, budget=None):
    budget = [0] if budget is None else budget; budget[0] += 1
    _require(depth <= 8 and budget[0] <= 256 and type(node) is dict, 'Predicate exceeds limits')
    op = node.get('op')
    _require(type(op) is str and op in OPS, 'Unknown predicate opcode')
    if op in ('all', 'any'):
        _keys(node, ('op', 'args')); _list(node['args'], 32)
        for child in node['args']: _predicate(child, spaces, depth + 1, budget)
    elif op in ('eq', 'gt'):
        _keys(node, ('op', 'field', 'value')); expected = _field(node)
        _require(type(node['value']) is expected, 'Predicate operand type mismatch')
        if op == 'gt': _require(expected is int, 'gt requires an integer field')
    elif op in ('in', 'not-in'):
        _keys(node, ('op', 'field', 'values')); expected = _field(node); _unique(node['values'], 256)
        _require(all(type(v) is expected for v in node['values']), 'Predicate set type mismatch')
        if node['field'] == 'kind': _require(set(node['values']) <= set(FACT_KINDS), 'Unknown fact kind')
    elif op == 'overlap':
        _keys(node, ('op', 'space', 'ranges'))
        _require(type(node['space']) is str and node['space'] in spaces, 'Unknown address space')
        _list(node['ranges'], 32)
        for pair in node['ranges']:
            _list(pair, 2, 2); _int(pair[0], 0, spaces[node['space']] - 1); _int(pair[1], pair[0] + 1, spaces[node['space']])
    elif op == 'bits-any':
        _keys(node, ('op', 'field', 'mask')); _require(_field(node) is int, 'Mask requires an integer field'); _int(node['mask'], 1, U32 - 1)
    else:
        _keys(node, ('op', 'address', 'width', 'mask', 'unknown'))
        _require(type(node['width']) is int and node['width'] in (1, 2, 4), 'Invalid masked register width')
        _int(node['address'], 0, U32 - node['width']); _int(node['mask'], 1, (1 << (8 * node['width'])) - 1)
        _require(node['unknown'] == 'match', 'Unknown write values must conservatively match')


def state_addresses(contract):
    """Return the sorted complete initial-state register address set."""
    n = contract['normalization']; d = n['dma']
    return sorted(n['stateRegisters'] + [c + d['streamOffset'] + s * d['streamStride'] + offset
                  for c in d['controllers'] for s in range(d['streams']) for offset in d['registers'].values()])


def _validate_contract(raw):
    """Validate and copy v1 data. Raises WatchValidationError/ValueError on failure."""
    c = _document(raw, 65536)
    _keys(c, ('format', 'version', 'vocabularyVersion', 'specVersion', 'modelContractSha256',
              'addressSpaces', 'requiredCapabilities', 'normalization', 'rules'))
    _require(c['format'] == 'sq64-watch-rules' and type(c['version']) is int and c['version'] == 1 and
             type(c['vocabularyVersion']) is int and c['vocabularyVersion'] == 1, 'Unsupported watch contract version')
    _require(re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', c['specVersion'] or '') is not None, 'Invalid spec version')
    _require(digest(c['modelContractSha256']), 'Invalid model contract digest')
    _keys(c['addressSpaces'], ('cpu', 'spi-flash'))
    _require(type(c['addressSpaces']['cpu']) is int and c['addressSpaces']['cpu'] == U32, 'CPU space must be unsigned 32-bit')
    _int(c['addressSpaces']['spi-flash'], 1, U32)
    caps = c['requiredCapabilities']; _keys(caps, ('eventKinds', 'sources', 'modes', 'guarantees'))
    for key, expected in (('eventKinds', EVENT_KINDS), ('sources', SOURCES), ('modes', MODES)):
        _unique(caps[key]); _require(set(caps[key]) == set(expected), 'Incomplete observation capability contract')
    _unique(caps['guarantees']); _require(set(caps['guarantees']) == set(GUARANTEES), 'Incomplete or unknown observation guarantees')
    n = c['normalization']; _keys(n, ('byteOrder', 'stateRegisters', 'dma'))
    _require(n['byteOrder'] == 'little', 'Unsupported byte order'); _unique(n['stateRegisters'], 64)
    for address in n['stateRegisters']: _int(address, 0, U32 - 4); _require(address % 4 == 0, 'Unaligned state register')
    d = n['dma']; _keys(d, ('controllers', 'streamOffset', 'streamStride', 'streams', 'registers', 'enabledMask', 'countMask', 'minimumCount', 'direction',
                           'peripheralDirections', 'peripheralWidth', 'memoryWidth', 'widths', 'peripheralIncrementMask', 'memoryIncrementMask', 'alternateMask'))
    _unique(d['controllers'], 4); _int(d['streams'], 1, 16); _int(d['streamOffset'], 0, 4096); _int(d['streamStride'], 4, 4096)
    _require(d['streamOffset'] % 4 == 0 and d['streamStride'] % 4 == 0, 'Unaligned DMA layout')
    _keys(d['registers'], ('control', 'count', 'peripheral', 'primary', 'secondary'))
    _require(len(set(d['registers'].values())) == 5, 'Overlapping DMA registers')
    for offset in d['registers'].values(): _int(offset, 0, d['streamStride'] - 4); _require(offset % 4 == 0, 'Unaligned DMA offset')
    for base in d['controllers']: _int(base, 0, U32 - d['streamOffset'] - d['streams'] * d['streamStride']); _require(base % 4 == 0, 'Unaligned DMA base')
    for field in ('enabledMask', 'countMask', 'peripheralIncrementMask', 'memoryIncrementMask', 'alternateMask'): _int(d[field], 1, U32 - 1)
    _int(d['countMask'], 1, 65535); _int(d['minimumCount'], 1, 65535)
    for field in ('direction', 'peripheralWidth', 'memoryWidth'):
        _keys(d[field], ('shift', 'bits')); _int(d[field]['bits'], 1, 3); _int(d[field]['shift'], 0, 32 - d[field]['bits'])
    _unique(d['peripheralDirections'], 8)
    for direction in d['peripheralDirections']: _int(direction, 0, (1 << d['direction']['bits']) - 1)
    _list(d['widths'], 8)
    _require(len(d['widths']) == 1 << d['peripheralWidth']['bits'] == 1 << d['memoryWidth']['bits'], 'Incomplete width decoding table')
    for width in d['widths']: _require(type(width) is int and width in (1, 2, 4, 8), 'Invalid DMA unit width')
    addresses = state_addresses(c)
    _require(len(addresses) <= 256 and len(addresses) == len(set(addresses)), 'Overlapping or excessive state registers')
    _list(c['rules'], 32); ids = set()
    for rule in c['rules']:
        _keys(rule, ('id', 'title', 'description', 'requirements', 'classification', 'mandatory', 'applicability', 'requiredObservations', 'predicate', 'action', 'warning', 'legacy'))
        _require(type(rule['id']) is str and re.fullmatch(r'[A-Z][A-Z0-9-]{1,47}', rule['id']) is not None and rule['id'] not in ids, 'Invalid or duplicate rule ID'); ids.add(rule['id'])
        _text(rule['title']); _text(rule['description']); _text(rule['warning']); _unique(rule['requirements'], 32)
        _require(all(type(v) is str and re.fullmatch(r'[A-Z][A-Z0-9-]{1,47}', v) for v in rule['requirements']), 'Invalid requirement reference')
        _require(rule['classification'] == 'conservative-emulator-policy' and rule['mandatory'] is True and rule['action'] == 'terminate-session', 'Unsupported rule applicability/action/classification')
        _keys(rule['applicability'], ('phases', 'modes'))
        for key, expected in (('phases', PHASES), ('modes', MODES)):
            _unique(rule['applicability'][key]); _require(set(rule['applicability'][key]) == set(expected), 'All execution paths must apply')
        _unique(rule['requiredObservations']); _require(set(rule['requiredObservations']) <= set(EVENT_KINDS), 'Unknown required observation')
        _keys(rule['legacy'], ('severity', 'unsafeWhen', 'status'))
        _require(rule['legacy'] == dict(severity='critical', unsafeWhen='pass', status='pass'), 'Invalid legacy hazard polarity')
        _predicate(rule['predicate'], c['addressSpaces'])
    _require({f'CRITICAL-{n:03}' for n in range(1, 6)} <= ids, 'Missing mandatory v1 rule')
    return c


def validate_contract(raw):
    try: return _validate_contract(raw)
    except WatchValidationError: raise
    except Exception as error: raise WatchValidationError('Invalid watch contract') from error


def load_rules():
    return validate_contract(Path(__file__).with_name('watch-rules.json').read_bytes())


def ruleset_digest(contract):
    return hashlib.sha256(_canonical(validate_contract(contract))).hexdigest()


def required_capabilities(contract):
    """Export obligations, NOT evidence that a consumer actually implements them."""
    c = validate_contract(contract)
    return dict(deepcopy(c['requiredCapabilities']), vocabularyVersion=c['vocabularyVersion'],
                predicateOps=list(OPS), rules=[r['id'] for r in c['rules']])


def _capabilities(c, supplied):
    expected = required_capabilities(c); _keys(supplied, expected)
    _require(type(supplied['vocabularyVersion']) is int and supplied['vocabularyVersion'] == 1, 'Unsupported vocabulary')
    for field in expected.keys() - {'vocabularyVersion'}:
        _unique(supplied[field], 256)
        _require(all(type(v) is str for v in supplied[field]) and set(expected[field]) <= set(supplied[field]), 'Missing mandatory capability: ' + field)


def _identity(c, supplied, digest_value):
    _keys(supplied, ('imageSha256', 'specVersion', 'rulesetSha256', 'modelContractSha256', 'emulator'))
    _require(digest(supplied['imageSha256']) and supplied['specVersion'] == c['specVersion'] and
             supplied['rulesetSha256'] == digest_value and supplied['modelContractSha256'] == c['modelContractSha256'], 'Identity mismatch')
    _keys(supplied['emulator'], ('name', 'version', 'sha256', 'tickUnit')); _text(supplied['emulator']['tickUnit']); _text(supplied['emulator']['name']); _text(supplied['emulator']['version'])
    _require(digest(supplied['emulator']['sha256']), 'Invalid emulator build digest')


META = ('kind', 'sequence', 'tick', 'source', 'pc', 'exception', 'phase', 'mode')
PAYLOAD = {'initial-state': ('registers',), 'instruction-boundary': (),
           'memory-write': ('space', 'address', 'width', 'value', 'locked'),
           'register-transition': ('registers',), 'spi-command': ('command', 'locked'),
           'spi-mutation': ('operation', 'address', 'length', 'value', 'locked'),
           'dma-transfer': ('controller', 'stream', 'buffer', 'address', 'width', 'count', 'increment')}


def _registers(event, addresses, initial):
    rows = event['registers']; _list(rows, 256); found = {}
    for row in rows:
        _keys(row, ('address', 'value')); _int(row['address'], 0, U32 - 4); _int(row['value'], 0, U32 - 1)
        _require(row['address'] in addresses and row['address'] not in found, 'Unknown or duplicate register observation')
        found[row['address']] = row['value']
    if initial: _require(set(found) == addresses, 'Incomplete initial register state')
    return found


def _hex(value, length):
    _require(type(value) is str and len(value) == 2 * length and re.fullmatch('[0-9a-f]+', value) is not None, 'Missing or invalid little-endian value bytes')


def _validate_event(raw, contract):
    """Strict structural validation. Sequence/state validation is per monitor."""
    e = _document(raw, 32768)
    _require(type(e) is dict and type(e.get('kind')) is str and e['kind'] in EVENT_KINDS, 'Unknown event kind')
    kind = e['kind']; _keys(e, META + PAYLOAD[kind])
    _int(e['sequence']); _int(e['tick']); _require(e['source'] in SOURCES and e['phase'] in PHASES and e['mode'] in MODES, 'Invalid event context')
    if e['pc'] is not None: _int(e['pc'], 0, U32 - 1)
    if e['exception'] is not None: _int(e['exception'], 0, 511)
    if 'locked' in e: _require(e['locked'] is None or type(e['locked']) is bool, 'Invalid locked state')
    if kind == 'initial-state':
        _require(e['source'] == 'model' and e['sequence'] == 0 and e['tick'] == 0, 'Initial state must precede execution')
        _registers(e, set(state_addresses(contract)), True)
    else:
        _require(e['source'] != 'model', 'Model source is only for initial state')
    if kind == 'instruction-boundary': _require(e['source'] == 'cpu', 'Instruction source must be CPU')
    if kind == 'register-transition': _registers(e, set(state_addresses(contract)), False)
    if kind == 'memory-write':
        _require(e['space'] == 'cpu', 'Memory writes use CPU byte addresses')
        _require(type(e['width']) is int and e['width'] in (1, 2, 4, 8), 'Unsupported access width')
        _int(e['address'], 0, U32 - e['width']); _hex(e['value'], e['width'])
    if kind == 'spi-command': _int(e['command'], 0, 255)
    if kind == 'spi-mutation':
        _require(e['operation'] in ('program', 'erase'), 'Unknown SPI mutation')
        _int(e['address'], 0, contract['addressSpaces']['spi-flash'] - 1)
        _int(e['length'], 1, contract['addressSpaces']['spi-flash'] - e['address'])
        if e['operation'] == 'program': _int(e['length'], 1, 256); _hex(e['value'], e['length'])
        else: _require(e['value'] is None, 'Erase has no supplied value')
    if kind == 'dma-transfer':
        d = contract['normalization']['dma']; _int(e['controller'], 0, U32 - 1)
        _require(e['source'] == 'dma' and e['controller'] in d['controllers'], 'Unknown DMA source/controller')
        _int(e['stream'], 0, d['streams'] - 1); _require(e['buffer'] in ('peripheral', 'primary', 'secondary'), 'Unknown DMA buffer')
        _int(e['address'], 0, U32 - 1); _int(e['count'], 1, 65535)
        _require(type(e['width']) is int and e['width'] in (1, 2, 4, 8) and type(e['increment']) is bool, 'Invalid DMA span geometry')
    return e


def validate_event(raw, contract):
    try: return _validate_event(raw, contract)
    except WatchValidationError: raise
    except Exception as error: raise WatchValidationError('Invalid watch event') from error


def _fact(kind, space, operation, source, address=None, length=None, width=None, value=None, origin=None, number=None, command=None):
    return dict(kind=kind, space=space, operation=operation, source=source, address=address, length=length,
                width=width, value=value, origin=origin, number=number, command=command,
                end=None if address is None else address + length)


def _span(address, width, count, increment, operation, origin):
    return _fact('dma-span', 'cpu', operation, 'dma', address, width * count if increment else width, width, origin=origin)


def _state_facts(c, state, source):
    n = c['normalization']; d = n['dma']
    facts = [_fact('register-state', 'cpu', 'state', source, a, 4, 4, state[a].to_bytes(4, 'little').hex(), 'register-state', state[a]) for a in n['stateRegisters']]
    def bits(control, field): return control >> field['shift'] & ((1 << field['bits']) - 1)
    for controller in d['controllers']:
        for stream in range(d['streams']):
            base = controller + d['streamOffset'] + stream * d['streamStride']
            registers = {k: state[base + offset] for k, offset in d['registers'].items()}; control = registers['control']
            if not control & d['enabledMask']: continue
            peripheral = bits(control, d['direction']) in d['peripheralDirections']
            width = d['widths'][bits(control, d['peripheralWidth' if peripheral else 'memoryWidth'])]
            count = max(d['minimumCount'], registers['count'] & d['countMask'])
            increment = bool(control & d['peripheralIncrementMask' if peripheral else 'memoryIncrementMask'])
            buffers = ['peripheral'] if peripheral else ['primary', 'secondary'] if control & d['alternateMask'] else ['primary']
            for buffer in buffers:
                facts.append(_span(registers[buffer], width, count, increment, 'dma-plan', f'dma:{controller}:{stream}:{buffer}'))
    return facts


def _facts(c, e, state):
    kind = e['kind']
    if kind in ('initial-state', 'register-transition', 'instruction-boundary'):
        return _state_facts(c, state, e['source'])
    if kind == 'memory-write':
        facts = [_fact(kind, 'cpu', 'write', e['source'], e['address'], e['width'], e['width'], e['value'], kind)]
        prospective = dict(state); changed = False; data = bytes.fromhex(e['value'])
        for address, value in state.items():
            for lane in range(4):
                index = address + lane - e['address']
                if 0 <= index < len(data):
                    value = (value & ~(255 << (8 * lane))) | (data[index] << (8 * lane)); changed = True
            prospective[address] = value
        if changed: facts.extend(_state_facts(c, prospective, e['source']))
        return facts
    if kind == 'spi-command': return [_fact(kind, 'spi-flash', 'command', e['source'], length=1, width=1, value=f"{e['command']:02x}", origin=kind, command=e['command'])]
    if kind == 'spi-mutation': return [_fact(kind, 'spi-flash', e['operation'], e['source'], e['address'], e['length'], 1 if e['operation'] == 'program' else None, e['value'], kind)]
    return [_span(e['address'], e['width'], e['count'], e['increment'], 'dma-transfer', f"dma:{e['controller']}:{e['stream']}:{e['buffer']}")]


def _matches(node, fact):
    op = node['op']
    if op == 'all': return all(_matches(child, fact) for child in node['args'])
    if op == 'any': return any(_matches(child, fact) for child in node['args'])
    if op in ('eq', 'gt', 'in', 'not-in', 'bits-any'):
        value = fact[node['field']]
        if value is None: return False  # Missing never turns not-in into a violation.
        if op == 'eq': return type(value) is type(node['value']) and value == node['value']
        if op == 'gt': return value > node['value']
        if op == 'in': return value in node['values']
        if op == 'not-in': return value not in node['values']
        return bool(value & node['mask'])
    if op == 'overlap':
        return fact['space'] == node['space'] and fact['address'] is not None and any(fact['address'] < end and start < fact['end'] for start, end in node['ranges'])
    start, end = node['address'], node['address'] + node['width']
    if fact['space'] != 'cpu' or fact['address'] is None or not (fact['address'] < end and start < fact['end']): return False
    if fact['value'] is None: return True
    data = bytes.fromhex(fact['value'])
    # Only mask bits whose byte lanes were actually written. No JS modulo-32 shift.
    for address in range(max(start, fact['address']), min(end, fact['end'])):
        if data[address - fact['address']] & ((node['mask'] >> (8 * (address - start))) & 255): return True
    return False


def _preview(raw):
    # Errors must not retain unbounded/malformed attacker-controlled objects.
    if type(raw) is not dict: return {'inputType': type(raw).__name__[:48]}
    return {key: raw[key][:160] if type(raw[key]) is str else raw[key] for key in META + ('address', 'width', 'command')
            if key in raw and (type(raw[key]) is str or raw[key] is None or type(raw[key]) is bool or type(raw[key]) is int and 0 <= raw[key] <= MAX_INT)}


class WatchMonitor:
    """Fail-closed session monitor. evaluate() returns allow/status, not a hazard boolean."""
    def __init__(self, contract, *, identity, capabilities):
        self._contract = None; self._identity = {key: identity.get(key) if type(identity) is dict and digest(identity.get(key)) else None for key in ('imageSha256', 'rulesetSha256', 'modelContractSha256')}; self._identity_verified = False; self._rules_hash = None; self._state = {}
        self._status = 'awaiting-initial-state'; self._violation = None; self._error = None
        self._sequence = -1; self._tick = 0; self._history = deque(maxlen=4)
        try:
            self._contract = validate_contract(contract)
            self._rules_hash = hashlib.sha256(_canonical(self._contract)).hexdigest()
        except Exception:
            self._stop_error('invalid-contract'); return
        try:
            i = _document(identity, 4096); _identity(self._contract, i, self._rules_hash); self._identity = i; self._identity_verified = True
        except Exception:
            self._stop_error('invalid-identity'); return
        try:
            _capabilities(self._contract, _document(capabilities, 16384))
        except Exception:
            self._stop_error('missing-capability'); return

    @property
    def terminated(self): return self._status in ('violation', 'monitoring-error')

    @property
    def can_execute(self): return self._status == 'active'

    def _outcome(self): return dict(allow=self.can_execute, status=self._status)

    def _stop_error(self, code, event=None):
        if not self.terminated:
            self._status = 'monitoring-error'
            self._error = dict(kind='monitoring-error', code=code, warning=ERROR_WARNING, action='terminate-session', event=_preview(event))
        return self._outcome()

    def fail(self, reason='observer-failure'):
        """Consumer detected a missing hook/read failure/backend failure; latch a stop."""
        if reason not in ('observer-failure', 'backend-failure', 'capability-lost'): reason = 'observer-failure'
        return self._stop_error(reason)

    def evaluate(self, event):
        if self.terminated: return self._outcome()
        try:
            e = validate_event(event, self._contract)
        except Exception:
            return self._stop_error('invalid-event', event)
        if e['sequence'] != self._sequence + 1 or e['tick'] < self._tick:
            return self._stop_error('event-order', e)
        if self._status == 'awaiting-initial-state' and e['kind'] != 'initial-state':
            return self._stop_error('missing-initial-state', e)
        if self._status == 'active' and e['kind'] == 'initial-state':
            return self._stop_error('duplicate-initial-state', e)
        try:
            state = dict(self._state)
            if e['kind'] in ('initial-state', 'register-transition'):
                state.update({r['address']: r['value'] for r in e['registers']})
            facts = _facts(self._contract, e, state)
            matches = []
            for rule in self._contract['rules']:
                for fact in facts:
                    if _matches(rule['predicate'], fact):
                        matches.append((rule, fact)); break
            self._sequence, self._tick = e['sequence'], e['tick']; self._history.append(e)
            if matches:
                rule, fact = matches[0]
                self._violation = dict(kind='watch-violation', ruleId=rule['id'], matchingRuleIds=[r['id'] for r, _ in matches],
                                       warning=rule['warning'], action=rule['action'], event=e, match=fact, identity=deepcopy(self._identity))
                self._status = 'violation'
            else:
                self._state = state; self._status = 'active'
            return self._outcome()
        except Exception:
            return self._stop_error('internal-error', e)

    def violation(self): return deepcopy(self._violation)

    def report(self):
        results = []
        for rule in self._contract['rules'] if self._contract else []:
            result = dict(rule['legacy'], id=rule['id'], title=rule['title'], status='not-run', requirements=rule['requirements'])
            if self._violation and self._violation['ruleId'] == rule['id']:
                e = self._violation['event']; fact = self._violation['match']
                result.update(status='pass', warning=rule['warning'], imageSha256=self._identity['imageSha256'],
                              **{k: fact[k] for k in ('operation', 'address', 'width', 'length', 'value', 'source')},
                              space=fact['space'], pc=e['pc'], exception=e['exception'], sequence=e['sequence'], tick=e['tick'])
            results.append(result)
        critical = dict(format='sq64-critical-results', version=1, specVersion=self._contract['specVersion'] if self._contract else None,
                        terminateOnCritical=True, terminated=self._status == 'violation', imageSha256=self._identity.get('imageSha256'),
                        warning=self._violation['warning'] if self._violation else None, claim=CLAIM, results=results)
        return deepcopy(dict(format='sq64-watch-report', version=1, status=self._status, terminated=self.terminated, canExecute=self.can_execute,
                             identity=self._identity, identityVerified=self._identity_verified, rulesVersion=self._contract['version'] if self._contract else None,
                             rulesetSha256=self._rules_hash, lastSequence=self._sequence if self._sequence >= 0 else None, lastTick=self._tick,
                             violation=self._violation, monitoringError=self._error, recentEvents=list(self._history),
                             critical=critical, hardwareValidated=False, recoveryGuaranteed=False, claim=CLAIM))
