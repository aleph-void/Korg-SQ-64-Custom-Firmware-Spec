"""Contract tests for recorded update sessions, independent of any updater."""
from .validation import integer, unhex

PREFIX = bytes([240, 66, 35, 0, 1, 96])

def parse(data):
    if len(data) < 8 or data[:6] != PREFIX or data[-1] != 247 or any(b >= 128 for b in data[6:-1]): raise ValueError('Invalid update frame')
    return data[6], data[7:-1]

def number(data):
    if len(data) not in (2, 4) or any(b > 127 for b in data): raise ValueError('Invalid update integer')
    value = 0
    for b in data: value = value * 128 + b
    return value

def decode(data, length):
    if not integer(length, 0, 0x38000) or any(b > 127 for b in data): raise ValueError('Invalid packed length or byte')
    if len(data) != length + (length + 6) // 7: raise ValueError('Wrong packed length')
    result = bytearray()
    for i in range(0, len(data), 8):
        mask, group = data[i], data[i + 1:i + 8]
        if mask >> len(group): raise ValueError('Noncanonical packing')
        result.extend(b | ((mask >> bit & 1) << 7) for bit, b in enumerate(group))
    return bytes(result)

def validate_transfer(events, expected_payload, *, expected_version=None):
    """Require one complete successful, serialized VUP transaction transcript."""
    if not isinstance(events, list) or len(expected_payload) != 0x38000: raise ValueError('Expected a transcript array and full payload')
    if expected_version is not None and (not isinstance(expected_version, (list, tuple, bytes, bytearray)) or len(expected_version) != 2 or not integer(expected_version[0], 0, 63) or not integer(expected_version[1], 0, 127)):
        raise ValueError('Invalid expected firmware version')
    stage = 'search'; waiting = None; protocol = None; size = None; count = 0; fill = False
    reconstructed = bytearray(); saw_error = False
    for event in events:
        if saw_error: raise ValueError('Traffic continued after NAK')
        if not isinstance(event, dict): raise ValueError('Invalid transcript event')
        if event.get('direction') not in ('host', 'device'): raise ValueError('Invalid transcript direction')
        if not isinstance(event.get('hex'), str): raise ValueError('Missing frame hex')
        command, body = parse(unhex(event['hex'], maximum=1200))
        if event['direction'] == 'device':
            if waiting == 'search':
                if command != 1 or not body or body[0] not in (0, 1): raise ValueError('Invalid discovery response')
                protocol = body[0]; width = 4 if protocol else 2
                if len(body) != width + 2: raise ValueError('Bad discovery length')
                size = min(1024, number(body[1:-1]))
                if not size or len(expected_payload) % size: raise ValueError('Invalid packet size')
                if len(expected_payload) // size > 1 << (7 * width): raise ValueError('Packet index overflow')
                fill = bool(body[-1] & 2)
                stage = 'version'
            elif waiting == 'version':
                if command != 3 or len(body) != 2: raise ValueError('Invalid version reply')
                stage = 'begin'
            elif waiting in ('begin', 'packet'):
                if command == 0x13:
                    if len(body) != 4 or number(body[:2]) > number(body[2:]): raise ValueError('Invalid progress')
                    continue
                if command != 5 or len(body) not in (1, 2): raise ValueError('Missing ACK')
                if body[0]: saw_error = True; waiting = None; continue
                stage = 'packet'
            else: raise ValueError('Unsolicited acknowledgement')
            waiting = None
        else:
            if waiting: raise ValueError('Host sent before acknowledgement')
            if stage == 'search' and command == 0 and not body: waiting = 'search'
            elif stage == 'version' and command == 2 and body == b'\0': waiting = 'version'
            elif stage == 'begin' and command == 4:
                if protocol:
                    if len(body) != 16 or body[:2] != b'\0\0' or number(body[2:6]) != 0 or number(body[6:10]) != len(expected_payload) or number(body[12:16]) != size: raise ValueError('Invalid begin geometry')
                    version = body[10:12]
                else:
                    if len(body) != 4 or body[:2] != b'\0\0': raise ValueError('Invalid protocol-zero begin')
                    version = body[2:4]
                if not version[0] & 64: raise ValueError('Begin version marker missing')
                if expected_version is not None and (version[0] & 63, version[1]) != tuple(expected_version):
                    raise ValueError('Begin version differs from candidate VSB')
                waiting = 'begin'
            elif stage == 'packet' and command in (6, 8):
                width = 4 if protocol else 2
                if len(body) < width + 2 or len(reconstructed) + size > len(expected_payload): raise ValueError('Truncated or excess packet')
                if number(body[:width]) != count: raise ValueError('Packet order mismatch')
                if command == 8:
                    if not fill: raise ValueError('Fill was not advertised')
                    if len(body) != width + 2 or any(b > 15 for b in body[width:]): raise ValueError('Invalid fill packet')
                    raw = bytes([body[width] * 16 + body[width + 1]]) * size
                else:
                    if (sum(body[width:-1]) & 127) != body[-1]: raise ValueError('Packet checksum mismatch')
                    raw = decode(body[width:-1], size)
                reconstructed.extend(raw); count += 1; waiting = 'packet'
            else: raise ValueError('Unexpected host command or session order')
    if saw_error or waiting or bytes(reconstructed) != expected_payload: raise ValueError('Transfer incomplete or payload differs')
    return {'check': 'update-transfer', 'requirements': ['VUP-001', 'VUP-003', 'VUP-004'],
            'status': 'pass', 'packets': count, 'protocol': protocol, 'packetSize': size,
            'versionBound': expected_version is not None,
            'detail': f'{count} sequential packets acknowledged; receiver rejection behavior and device programming completion remain separate'}
