# Firmware interface contracts

Specification version 0.6.0. All integers are little-endian unless the wire encoding below says otherwise. These are interoperability facts, not a redistribution of vendor code. Unverified board facts are explicit gaps; a firmware author must not substitute guessed pin wiring or calibration limits. `sq64_spec/board.json` is the versioned machine-readable software interface; it does not certify a physical board. The register addresses, DMA stream assignments and programming sequences behind these contracts are collected in the [peripheral register interface](peripheral-registers.md).

## Full-system VSB

| File offset | Width | Required value |
| --- | --- | --- |
| 0x00 | 16 bytes | ASCII `KORG SYSTEM FILE` |
| 0x10 | 16 | `SQ-64` followed by NUL padding |
| 0x20 | 8 | `SYSTEM` followed by two NUL bytes |
| 0x29 | 1 | block 0 |
| 0x2a, 0x2b | 1 each | major <64, minor <128 |
| 0x2c | 4 | product/member `00 01 60 ff` |
| 0x30 | four uint32 | base 0, total 0x38000, start 0, length 0x38000 |
| 0x44 | uint32 | delay 0..60000 ms, or 0xffffffff for no specified delay |
| 0x100 | 0x38000 | system payload |

The total file length is exactly 0x38100 (229,632) bytes. For each payload-relative `(start,length)` pair below, the unsigned sum of little-endian halfwords modulo 65536 is zero:

```
(0x00000, 0x10000)
(0x10000, 0x04000)
(0x14000, 0x0bdd8)
(0x20000, 0x14000)
```

Checksums are corruption checks, not signatures or evidence of functional correctness. Bytes outside these checksum regions are not thereby authenticated. The reset stack is eight-byte aligned, greater than 0x20000000 and at most 0x20040000. The reset vector has its Thumb bit set and points within loaded internal flash after the two vector words.

## Memory and installation

| Payload range | Destination |
| --- | --- |
| 0x00000..0x10000 | internal flash 0x00200000..0x00210000 |
| 0x10000..0x14000 | external SPI flash 0x00000..0x04000 |
| 0x34000..0x38000 | external SPI flash 0x04000..0x08000 |
| 0x14000..0x34000 | external SPI flash 0x10000..0x30000 |

Ranges are end-exclusive. The emulator maps the internal flash alias at 0x08000000 and SRAM at 0x20000000..0x20040000, and the browser model provides 16 MiB of SPI NOR storage. Saved project slot n occupies a 0x3d000-byte region starting at 0xc0000 + n×0x3d000; slot 63 ends at 0x1000000 (end-exclusive). A 1 MiB model cannot represent all 64 slots. These are executable interoperability bounds, not a verified schematic. The complete reserved/calibration storage ownership map, MCU part, board pin map, clocks and electrical output topology remain unresolved release blockers. Custom firmware must supply initialization and copying routines itself; the emulator does not silently load the application into RAM.

Firmware must support the full project lifecycle: creating a new project in the current workspace, loading any of the 64 saved slots into the workspace, saving the workspace to a selected slot, and deleting a saved slot (PROJECT-001..004). Save and delete are explicit operations against exactly one slot region above; nothing may mutate another slot, the workspace (on rejection), reserved storage or settings. A deleted or never-written slot is observably empty: a load attempt reports it instead of producing undefined data, and the backup transport returns the empty-slot status (30) with explicit null archive records rather than invented contents. Durable commitment follows the shutdown contract below; completion may only be reported once the data would survive a normal shutdown and cold restart. Interrupted saves and deletes must leave the previous contents or a valid new/empty state (STORE-004, PROJECT-004).

The engine enforces eight-byte reset-stack alignment and faults misaligned multiword/FP transfers. Scalar unaligned support follows the modeled Cortex-M configuration. Exception nesting must preserve MSP/PSP, integer registers, status/IT state, alignment padding and floating-point context. See CPU-001..005 for directed cases.

## Browser panel and USB model

The packaged model contract supplies all 85 distinct `(row, bit)` switch positions and six encoder pairs, so a consumer does not need the sibling source tree to obtain those facts. Encoder first bits are tempo 4, swing 6, parameter 1/2 at 12/14, and parameter 3/4 at 8/10; positive phases are `00,01,11,10,00`. Interactive browser detents consist of two phase edges, paced at 40 ms of virtual time. That pacing is a UI policy, not an electrical timing requirement.

Eight-byte DMA scans have 15 leading serial clocks before the 32 input bits; bytes are low first and bits MSB first. TX byte 2 selects the next row. Six-byte startup frames select via TX byte 0; PB0 falling samples the old row and rising latches the next. This pipeline applies to startup chords as well as normal input. LED columns use TX bytes 5, 4 and the low five bits of 3, with paired rows for two channels. Active-low auxiliary transport bits occupy byte 7 bits 2–5 on rows 0/1. The display consumes 8192 bytes for 256×64 four-bit pixels, low nibble and bottom row first. Complete controller commands remain unverified.

The top-edge model observes six CV slots (A/B/C MOD then PITCH) from SAI1 block B via DMA2 stream 6, inverted gate outputs PB12/PB15/PC9, and eight active-low trigger bits from DMA TX byte 6 or latched polled byte 4. CV samples use descending signed 24-bit coding from `0x7fffff`; this establishes no voltage calibration. Observations do not alter firmware state. PB4 high represents unplugged sync. Timer and UI observations are not cycle-accurate electrical measurements.

The browser emulator implements an eight-row active-high input matrix, six quadrature encoders, polled startup SPI and normal DMA scanning, PWM LED sampling, and grayscale display DMA decoding. See the emulator's `docs/panel-interface.md` for the independently authored wiring contract and its evidence limits. Host UI state is not evidence that firmware consumed an input: observe firmware dispatch or an externally visible response. Power-on chords must pass through the panel signals.

The host sends USB setup requests after reset recovery even if the device masks ENUMDNE. The model respects soft-disconnect, exposes frame/idle IN-token activity to polling firmware, and supplies OUT data and completion statuses. The sequencer uses USB-MIDI cable 2 for host-to-device packets and cable 1 for device-to-host packets; these directions are not symmetric. All-zero event packets are padding. Electrical USB behavior and exact endpoint timing remain outside the browser model's conformance claims.

## Update protocol

SysEx prefix: `f0 42 23 00 01 60`; suffix `f7`. Command and body bytes are seven-bit values. Multi-byte wire integers are big-endian base-128, two bytes in protocol 0 and four in protocol 1 where indicated.

| Host command | Device response / body |
| --- | --- |
| 00 search | 01: protocol (0/1), packet size (2/4 bytes), capability flags |
| 02 version, body 00 | 03: major, minor |
| 04 begin | 05 acknowledgement: status 00; optional programming-status byte |
| 06 data | packet index (2/4), seven-bit packed payload, checksum; then 05 ACK |
| 08 repeated-byte packet | index (2/4), value high nibble, low nibble; then 05 ACK |
| — | 13 progress: done (2), total (2) |

Fill packets require capability flag `0x02`. Protocol 1 begin body is flags 00, block 00, base (4), payload length (4), major OR 0x40, minor, packet size (4): 16 bytes. Protocol 0 begin has flags 00, block 00, major OR 0x40, minor. The web tool uses at most 1024 payload bytes per packet, with exact divisibility of the full image.

Packing groups up to seven raw bytes: emit a bit mask of their high bits (bit 0 corresponds to the first raw byte), then each byte's low seven bits. Unused high-mask bits must be zero. The data-packet checksum is the sum of the **packed data bytes**, modulo 128; exclude packet index and checksum itself.

Wait for a matching acknowledgement before every next message; packet indices start at zero and increase by one. The web tool inserts a minimum 2 ms delay between packets and uses a 5 s real-device response timeout. Those are host policies, not measured device timing guarantees. Negative acknowledgements, timeouts and disconnects terminate the operation without automatic retry. A final packet ACK is not proof that internal programming finished. Preserve power until the device signals completion, then restart and verify version and normal-mode behavior. No bounded checksum test proves that interruption during internal flash programming is recoverable.

A transcript is a JSON array of `{ "direction": "host"|"device", "hex": "f042...f7" }`, containing one successful search/version/begin/data transaction. `validate_transfer` reconstructs and compares every payload byte. It does not validate timing, malformed-request rejection, analog signals or storage persistence.

Hex fields contain contiguous hexadecimal byte pairs without whitespace. CLI validation additionally binds the begin version to the supplied VSB header. The low-level API accepts `expected_version=(major, minor)`; when omitted, its result explicitly reports `versionBound: false`. This transcript format covers the sibling host policy: packet size `min(1024, advertised)` and a payload evenly divisible into packets. It is not a claim that every other legal VUP host negotiation has been modeled. Protocol-zero packet indices must fit 14 bits.

## Backup transport

Normal-operation prefix is `f0 42 (30 + zero-based-global-channel) 00 01 60`; suffix `f7`. Packed payloads use the same high-bit mask convention. Indexed requests/replies place the slot index before packed data.

| Record | Request | Reply | Raw bytes | Slots / tag |
| --- | --- | --- | --- | --- |
| Global | 0e | 50 | 512 | current / GLOB |
| Current control | 14 | 44 | 2048 | current / CTRL |
| Saved control | 15 | 45 | 2048 | 0..15 / CTRL |
| User scale | 17 | 47 | 36 | 0..5 |
| Current project | 11 | 41 | 512 | current / PROJ |
| Saved project | 1d | 4d | 512 | 0..63 / PROJ |
| Melodic pattern | 18 | 48 | 3104 | track×16 + pattern, 0..47 |
| Rhythm pattern | 19 | 49 | 6176 | 0..15 |

A project header's bytes 40..47 contain two presence bytes for each of tracks A..D, least-significant-bit first, for 16 patterns per track. Read only patterns marked present. Terminate each project transaction with command 70 and expect empty-body ACK 23. Empty slots return 30. Error responses include 24 busy, 25 parameter and 26 format. No undocumented data is invented for empty slots.

Archives retain exact response messages, SHA-256 for each message, its kind, slot and owning project; empty slots are explicit nulls. Validate the entire expected record set before writing anything. Restore control/scales first, project headers followed by their present patterns and finalization, and global settings last because they can change the MIDI channel. ACK confirms receipt, not durable save. Finish normal power-button shutdown before restarting: the current workspace and saved-project catalog are committed during shutdown, and an abrupt reset can lose them. Compare a fresh backup after normal shutdown and cold restart to establish persistence, including populated first and last saved slots. In the browser model, GPIO C13 is the active-low power input and GPIO B7 is firmware power-hold; CPU execution stops when firmware releases the previously asserted hold. Closing the page is not a persistence mechanism. Firmware, calibration and undocumented device storage are outside the backup contract.

### Archive schema and coverage

The top-level object has `format: "sq64-backup"`, integer `version: 1`, integer `channel: 0..15`, `complete: true`, `scope`, `excludes` and `records`. `createdAt` is informational. `excludes` is a unique string array containing `firmware`, `factory-calibration` and `undocumented-device-storage`. Additional explicit exclusions are retained. No included record required by scope may be omitted through an exclusion.

| Scope | Required records |
| --- | --- |
| `settings` | Global, current control and six scale slots |
| `current` | Settings plus current project and every present pattern |
| `all` | Current scope plus 16 control slots, 64 saved project headers and each present pattern |

Every record includes `kind`, `index`, `project`, `data` and `sha256`. Kinds are `global`, `currentControl`, `control`, `scale`, `currentProject`, `project`, `melody` and `rhythm`. Unindexed records use `index: null`; other indices obey the transport table above. Saved project headers have `project == index`; patterns identify their owning saved slot or `null` for the current project. All other records have `project: null`.

`data` is the contiguous hexadecimal response message and `sha256` is the lowercase digest of its decoded wire bytes. Empty optional slots use null for both fields. Global, current control, current project and every pattern referenced by a header must have data. Empty-response frames are not stored as populated records. Reject wrong channel/product/command/tag, noncanonical packing, incorrect length/index, duplicate keys, unmatched digests, orphan patterns, missing required records and out-of-scope data. Records are limited to 7500 wire bytes, and archives to 4250 records; the exact expected set is additionally checked. JSON booleans do not count as integer indices or versions.

An archive does not store project-session ACK traffic. Its integrity check therefore cannot establish BACKUP-002 finalization, receiver input validation, successful restore or persistence. `compare_backups` checks complete logical snapshots, including source-empty slots; it does not assume that an empty source instructs erasure of a populated destination.

## Recovery restrictions and hazard results

See [application-only acceptance](application-only.md) for the pinned policy, write-capture schema and default emulator termination contract. Critical hazard results use `severity: "critical"` and `unsafeWhen: "pass"`; ordinary conformance passes retain their existing meaning.
