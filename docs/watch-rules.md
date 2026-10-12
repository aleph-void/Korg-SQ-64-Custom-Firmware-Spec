# Runtime watch rule reference

Specification 0.4.0; contract/vocabulary v1. Generated from `sq64_spec/watch-rules.json`.

Canonical ruleset SHA-256: `fbc67b69cb0a9e092ddec3a19e5d962bbcbf12e30a862ac61970818236c1f51b`

See [runtime monitoring](runtime-watch.md) for event schemas, normalization, predicate semantics, resource limits and termination. Every rule is mandatory in boot, application and interrupt phases and in run, step, replay and fast modes. These are conservative emulator restrictions, not verified board limits. Array order selects the first violation when multiple rules match one observation.

## CRITICAL-001 — Internal recovery flash mutation attempted

Reject writes to both conservative internal-flash windows, erase-mode bits written in their actual byte lanes, and armed erase state. DMA destinations at the erase-control register are unsafe without needing transfer values.

**Requirements:** RECOVERY-001, RECOVERY-002

**Required observations:** initial-state, instruction-boundary, memory-write, register-transition, dma-transfer

**Action:** `terminate-session`. **Warning:** Your custom firmware probably will brick your device. Do not flash it.

**Violation predicate:**

```json
{
  "op": "any",
  "args": [
    {
      "op": "all",
      "args": [
        {
          "op": "in",
          "field": "kind",
          "values": [
            "memory-write",
            "dma-span"
          ]
        },
        {
          "op": "overlap",
          "space": "cpu",
          "ranges": [
            [
              2097152,
              3145728
            ],
            [
              134217728,
              136314880
            ]
          ]
        }
      ]
    },
    {
      "op": "all",
      "args": [
        {
          "op": "in",
          "field": "kind",
          "values": [
            "memory-write",
            "dma-span"
          ]
        },
        {
          "op": "write-bits",
          "address": 1073888272,
          "width": 4,
          "mask": 6,
          "unknown": "match"
        }
      ]
    },
    {
      "op": "all",
      "args": [
        {
          "op": "in",
          "field": "kind",
          "values": [
            "register-state"
          ]
        },
        {
          "op": "eq",
          "field": "address",
          "value": 1073888272
        },
        {
          "op": "bits-any",
          "field": "number",
          "mask": 6
        }
      ]
    }
  ]
}
```

## CRITICAL-002 — Persistent system configuration write attempted

Reject write attempts touching the conservative system-memory or option-control windows, including DMA destinations and locked attempts.

**Requirements:** RECOVERY-003

**Required observations:** memory-write, initial-state, instruction-boundary, register-transition, dma-transfer

**Action:** `terminate-session`. **Warning:** Your custom firmware probably will brick your device. Do not flash it.

**Violation predicate:**

```json
{
  "op": "all",
  "args": [
    {
      "op": "in",
      "field": "kind",
      "values": [
        "memory-write",
        "dma-span"
      ]
    },
    {
      "op": "overlap",
      "space": "cpu",
      "ranges": [
        [
          535822336,
          536870912
        ],
        [
          1073888264,
          1073888268
        ],
        [
          1073888276,
          1073888288
        ]
      ]
    }
  ]
}
```

## CRITICAL-003 — Forbidden or unmodeled SPI flash command attempted

Reject each selected SPI NOR command byte outside the modeled allowlist before command handling. This includes unknown commands; it is a conservative emulator restriction.

**Requirements:** RECOVERY-003

**Required observations:** spi-command

**Action:** `terminate-session`. **Warning:** Your custom firmware probably will brick your device. Do not flash it.

**Violation predicate:**

```json
{
  "op": "all",
  "args": [
    {
      "op": "in",
      "field": "kind",
      "values": [
        "spi-command"
      ]
    },
    {
      "op": "not-in",
      "field": "command",
      "values": [
        0,
        2,
        3,
        4,
        5,
        6,
        11,
        32,
        159,
        216
      ]
    }
  ]
}
```

## CRITICAL-004 — Installed SPI firmware mutation attempted

Reject every program or aligned erase effect overlapping installed SPI storage [0, 196608), even while locked or if bytes would remain identical.

**Requirements:** RECOVERY-002, RECOVERY-004

**Required observations:** spi-mutation

**Action:** `terminate-session`. **Warning:** Your custom firmware probably will brick your device. Do not flash it.

**Violation predicate:**

```json
{
  "op": "all",
  "args": [
    {
      "op": "in",
      "field": "kind",
      "values": [
        "spi-mutation"
      ]
    },
    {
      "op": "overlap",
      "space": "spi-flash",
      "ranges": [
        [
          0,
          196608
        ]
      ]
    }
  ]
}
```

## CRITICAL-005 — Unsafe DMA destination attempted

Reject a DMA destination span whose mathematical exclusive end exceeds the 32-bit CPU address space. Both potential memory buffers are examined before enable/configuration and reload.

**Requirements:** RECOVERY-002, RECOVERY-003

**Required observations:** initial-state, instruction-boundary, memory-write, register-transition, dma-transfer

**Action:** `terminate-session`. **Warning:** Your custom firmware probably will brick your device. Do not flash it.

**Violation predicate:**

```json
{
  "op": "all",
  "args": [
    {
      "op": "in",
      "field": "kind",
      "values": [
        "dma-span"
      ]
    },
    {
      "op": "gt",
      "field": "end",
      "value": 4294967296
    }
  ]
}
```
