# Runtime watch contract

Specification 0.4.0 introduces `sq64-watch-rules` version 1 and vocabulary version 1. The executable authority is [`watch-rules.json`](../sq64_spec/watch-rules.json), interpreted by dependency-free [`watch.py`](../sq64_spec/watch.py). The [generated rule reference](watch-rules.md) contains the actual predicates and canonical ruleset digest. [`critical.json`](../sq64_spec/critical.json) is now generated compatibility metadata, not an independently maintained set of conditions.

All five rules are mandatory in every declared phase and execution mode. The contract's ranges, SPI allowlist, erase mask and DMA layout are **conservative emulator policy**, copied from the existing models. They do not establish actual board part identities, flash capacity, wiring, OTP geometry or hardware safety. In particular, the broad internal/system-memory windows intentionally exceed the currently mapped 64 KiB internal image. A stock updater can trigger these restrictions when installing firmware. Normal SPI staging remains distinct from installed storage.

## Public API and execution gate

```python
from sq64_spec.watch import WatchMonitor, load_rules, ruleset_digest

rules = load_rules()
monitor = WatchMonitor(rules, identity=identity, capabilities=implemented_capabilities)
# Construction is not permission to run: can_execute remains False until
# the complete initial-state event is validated and all invariants pass.
outcome = monitor.evaluate(initial_state_event)
if not outcome['allow']:
    terminate_session(monitor.report())

# At each required hook, BEFORE any attempted operation can commit:
outcome = monitor.evaluate(event)
if not outcome['allow']:
    terminate_session(monitor.report())
    return  # Do not perform the operation.
```

`terminate_session` is the consumer's backend/UI operation, not a function provided by the pure monitor. The reference implementation never accesses an emulator, peripherals, MIDI, network or wall clock. Its constructor takes a contract dict or exact JSON bytes/string. Events may be dicts or JSON bytes/strings. Unknown fields, unsupported versions/opcodes, duplicate JSON keys, unsupported scalars, missing fields, invalid ranges and resource-limit violations are rejected. Do not use an ordinary JSON parser that silently loses duplicate keys before validation. The dict API assumes an already unique-key object.

| API | Meaning |
| --- | --- |
| `load_rules()` | Validate and return the packaged contract |
| `validate_contract(data)` | Validate and copy a contract; raises `ValueError` for invalid input |
| `ruleset_digest(contract)` | SHA-256 of validated canonical contract bytes |
| `required_capabilities(contract)` | Export required declarations; does **not** prove the caller implements them |
| `state_addresses(contract)` | Sorted required initial 32-bit register addresses; input must already be validated |
| `WatchMonitor(contract, identity=…, capabilities=…)` | Create an isolated session; initialization errors latch `monitoring-error` |
| `evaluate(event)` | Return exactly `{allow: bool, status: string}`; terminal sessions always return `allow: false` |
| `can_execute`, `terminated` | Read-only execution-gate properties |
| `violation()` | Copy of the first violation, or `None` |
| `report()` | Independent JSON-serializable copy of diagnostics and legacy results |
| `fail(reason)` | Latch an observer/backend failure without creating a firmware violation |

Statuses are `awaiting-initial-state`, `active`, `violation`, `monitoring-error`. Only `active` permits execution. The last two statuses are terminal. `fail` accepts `observer-failure`, `backend-failure`, or `capability-lost`; other values become `observer-failure`. Constructor/schema errors, missing capabilities, malformed/out-of-order observations and unexpected evaluator exceptions also terminate with monitoring-error diagnostics. Report export never resumes execution. After termination, further events and errors cannot replace the first terminal evidence.

Initialization requires an identity object with exactly:

```json
{
  "imageSha256": "<64 lowercase hexadecimal digits: exact loaded file>",
  "specVersion": "0.8.0",
  "rulesetSha256": "<canonical ruleset digest>",
  "modelContractSha256": "<SHA-256 of exact packaged board.json bytes>",
  "emulator": {
    "name": "<implementation name>",
    "version": "<implementation version>",
    "sha256": "<build/artifact SHA-256>",
    "tickUnit": "<unit of the model virtual tick counter>"
  }
}
```

The spec, ruleset and model digests must agree with the validated contract. Keep the loaded-file hash across guest resets; a hash of a later storage snapshot is a different identity and must not replace it. The consumer must pin the reviewed contract digest independently of untrusted firmware. Computing a digest over an arbitrary replacement contract does not approve it. An invalid initialization retains syntactically valid supplied image/digest fields where possible, sets `identityVerified: false`, and uses null for unavailable identity fields. A verified identity binds artifacts, not the truth of an implementation's claims.

The capability object has exactly `vocabularyVersion`, `predicateOps`, `rules`, `eventKinds`, `sources`, `modes`, `guarantees`. Version must be 1. Each other field is a unique string list including every corresponding requirement: all nine opcodes, every mandatory rule ID and every item in `requiredCapabilities`. Extra supported capabilities are permitted within the list bounds. Establish these facts from the actual installed hooks and tested execution paths, before initialization; copying the export into a manifest is not an implementation. If any capability disappears, call `fail('capability-lost')` before the next operation.

## Continuous event stream

Every relevant attempt or state transition must be observed synchronously **before side effects** from before the first firmware instruction. Boot, exception entry/handlers/return, normal execution, single stepping, replay and fast/batched execution all use the same gate. Validation buttons, enabled debugging, screen refreshes and periodic snapshots do not control monitoring.

Initialization has sequence 0, tick 0 and a complete side-effect-free state snapshot. Subsequent sequences are consecutive unsigned integers, globally ordered across CPU, DMA and peripherals. They cannot reset on a guest reset. Virtual ticks are nondecreasing integers in `identity.emulator.tickUnit`; several events may share a tick. The sequence, not the tick, orders simultaneous activity. Integer counters never wrap; exhausting their range stops with a monitoring error. Host wall-clock time is not an input.

Every event contains these keys, even when a nullable field is unavailable:

| Field | Schema |
| --- | --- |
| `kind` | One of the seven kinds below |
| `sequence`, `tick` | Unsigned integer, at most 9007199254740991; booleans/floats are invalid |
| `source` | `cpu`, `dma`, `peripheral`, or `model`; `model` is only for initial state |
| `pc` | Actual guest execution location as unsigned 32-bit address, or null if unavailable; null never means address zero |
| `exception` | Modeled exception number 0–511, or null if unavailable; 0 means thread context |
| `phase` | `boot`, `application`, or `interrupt`; all apply |
| `mode` | `run`, `step`, `replay`, or `fast`; all apply |

For DMA/peripheral activity, `pc` may identify the paused CPU location if known; it must not be presented as a CPU instruction that issued that asynchronous effect. The `source` and normalized match origin retain attribution. Unknown field names are errors, including unrecognized extensions. This makes missing required observations visible rather than silently ignored.

| Kind | Additional required fields | Evaluation boundary |
| --- | --- | --- |
| `initial-state` | `registers` | `source: model`, sequence/tick 0, before any firmware instruction, DMA action or firmware-triggered peripheral transition |
| `instruction-boundary` | None | `source: cpu`, before **each** instruction executes, including handler instructions and stepped/replayed/fast instructions; checks the monitor's coherent state image |
| `memory-write` | `space: cpu`, `address`, `width`, `value`, `locked` | Before each CPU/DMA/peripheral bus write attempt, including unmapped/protected accesses, partial/unaligned writes and attempts rejected by a lock |
| `register-transition` | `registers` | Before each actual change to tracked logical register state, including CPU side effects, reset, DMA reload/enable/double-buffer transitions and peripheral-driven changes |
| `spi-command` | `command`, `locked` | Before dispatch or rejection of the first command byte of **every selected NOR transaction**, including commands supplied through DMA |
| `spi-mutation` | `operation`, `address`, `length`, `value`, `locked` | Before each actual target byte/chunk program or aligned erase footprint, before lock/enable rejection and before storage mutation |
| `dma-transfer` | `controller`, `stream`, `buffer`, `address`, `width`, `count`, `increment` | `source: dma`, before each transfer/atomic batch writes any destination or consumes a side-effectful source |

`registers` is a nonempty list of unique `{address, value}` objects: address is a tracked aligned CPU byte address and value is an unsigned 32-bit word. Initial state contains **all** `state_addresses(contract)` exactly once (81 in this revision). A transition lists the full proposed post-transition word for each changed tracked register; omitted registers retain their current values. Emit the transition before committing it. Only changes belonging to one atomic model transition may be grouped. Two transitions that create and then restore a bad state must never be collapsed into their net effect. Reads of authoritative shadow state must not invoke guest peripheral-read hooks, consume FIFOs, acknowledge interrupts or clear status bits.

`memory-write.address` is unsigned 32-bit. `width` is exactly 1, 2, 4 or 8 **bytes**. `value` is exactly `2 * width` lowercase hexadecimal characters, representing the byte at the lowest address first. For example, a 32-bit little-endian write of numeric 6 is `"06000000"`. Eight-byte values must retain all eight bytes; JavaScript Number/bitwise truncation is unacceptable. `locked` is a boolean or null if unknown. It never suppresses a predicate. CPU/bus accesses crossing the end of the 32-bit space are malformed observations, not wrapped accesses or evidence of a detected hardware hazard. A backend that splits an operation must observe every actual constituent effect before it commits.

For SPI, address/length use NOR byte offsets in the contract's `spi-flash` space (16 MiB in the software model). `command` is an unsigned byte. Emit command events from the device's actual transaction parser, not for every dummy/read-data byte. `operation` is `program` or `erase`. Length is positive and the entire effect must fit the space. Program events supply exactly two lowercase hex characters per target byte; chunks are limited to 256 bytes as an observation-size bound, not a new hardware page-size fact. Erases use `value: null`. Erase `width` is null in reports. The device model computes the true aligned erase footprint and page-wrap effects; each resulting contiguous effect must be checked. A wrapped program cannot be reported as a misleading straight interval. No programming geometry or command authorization may be guessed from this watch contract beyond its explicit policy allowlist.

DMA `controller` and `stream` identify a slot in the declared layout. `buffer` is `peripheral`, `primary` or `secondary`. `address` is the actual destination offset in CPU space, `width` is 1/2/4/8 bytes, `count` is 1–65535 and `increment` is boolean. The span is `[address, address + width * count)` if incrementing, otherwise `[address, address + width)`. Calculate the end without modulo arithmetic. An end of 4294967296 is legal; a larger DMA end is a valid observation of the CRITICAL-005 hazard. No transfer values are required for the planned span. Every actual destination write still needs its `memory-write` event with complete value bytes. Every resulting SPI command/mutation or logical register transition also needs its respective event. Configuration checks do not replace transfer checks, and transfer checks do not prove configuration observations are complete. The monitor does not independently establish that a transfer's declared destination agrees with the engine's real destination; integration tests must prove that link.

## Normalization and predicate vocabulary

All address intervals are half-open: `[start, end)`. An overlap is `a < end && start < a + length`. Touching endpoints do not overlap. CPU aliases remain raw CPU addresses; the two flash windows in the rules are both checked, without address masking or modulo alias conversion. Additional model aliases or writers are a capability gap until incorporated and tested. SPI uses its own offset space, never a CPU address. The instruction ITCM RAM at zero is not silently treated as persistent flash.

For state observations, normalize each explicitly listed `normalization.stateRegisters` word into a `register-state` fact, in that array's order. Also derive DMA spans using only `normalization.dma`:

1. Visit controller-array order, then stream number ascending. Register address is controller + streamOffset + stream * streamStride + named register offset. Decode bitfields as `(control >> shift) & ((1 << bits) - 1)`, with unsigned 32-bit words.
2. A stream participates if any `enabledMask` bit is set. If decoded direction is in `peripheralDirections`, use the peripheral destination, peripheral-width table index and peripheral-increment mask. Otherwise use memory width/increment and the primary destination.
3. When the memory destination is selected and `alternateMask` is set, inspect **both** primary and secondary destinations in that order, regardless of which is currently active. A peripheral destination does not add a secondary memory destination.
4. Width comes from the `widths` lookup table. Count is `max(minimumCount, countRegister & countMask)`. The current zero-count/8-byte/reserved-direction interpretations are conservative compatibility policies; they are not asserted to be valid hardware DMA configurations.
5. Compute the mathematical exclusive span end without wrapping. Derived facts use `source: dma` and origin `dma:<decimal-controller>:<stream>:<buffer>`.

An attempted memory write first creates its direct `memory-write` fact. Overlay its actual byte lanes onto a **temporary** copy of any touched tracked register words, then normalize that prospective state and all DMA destinations. This catches unsafe configuration attempts even when the peripheral is locked. It does **not** commit the monitor's state. Only an allowed `initial-state` or `register-transition` commits state; an attempted write later rejected by the model cannot poison subsequent snapshots. Instruction boundaries evaluate the last committed coherent state. SPI and actual-transfer events create their own direct facts; they do not alter the register image.

Normalized facts have fixed fields `kind`, `space`, `operation`, `source`, `address`, `length`, `width`, `value`, `origin`, `number`, `command`, `end`. Kinds are `memory-write`, `register-state`, `spi-command`, `spi-mutation`, `dma-span`. Operations are `write`, `state`, `command`, `program`, `erase`, `dma-plan`, `dma-transfer`. `number` is the unsigned state word, otherwise null. `command` is the SPI command byte, otherwise null. Non-applicable addresses, widths and values are null, not omitted. A program has width 1 and its actual chunk length. A command has null address/end, width/length 1 and its hex command value. DMA values are null because a conservative plan does not depend on their contents.

There are no expression strings, variable assignments, recursion references, external calls or embedded executable code. Each predicate uses exactly its declared fields:

| Opcode | Fields besides `op` | Semantics |
| --- | --- | --- |
| `all`, `any` | `args`: 1–32 predicates | Boolean conjunction/disjunction on the **same fact**, left to right |
| `eq` | `field`, `value` | Exact typed scalar equality |
| `in`, `not-in` | `field`, `values`: unique scalars | Membership/non-membership with the field's declared scalar type |
| `gt` | integer `field`, integer `value` | Mathematical greater-than |
| `overlap` | `space`, `ranges`: positive `[start,end]` pairs | Fact interval intersects the union of the listed ranges; overlapping listed ranges are harmless |
| `bits-any` | integer `field`, unsigned 32-bit nonzero `mask` | At least one masked bit is set |
| `write-bits` | CPU `address`, register `width` 1/2/4, nonzero in-width `mask`, `unknown: match` | The fact overlaps that register and a written byte lane sets a corresponding mask bit; if its value is null, any overlap conservatively matches |

Allowed string fields are `kind`, `space`, `operation`, `source`, `origin`; integer fields are `address`, `width`, `length`, `end`, `number`, `command`. Other field names are invalid. A null field makes scalar comparisons, including `not-in`, false. The special unknown-value policy belongs only to `write-bits`; required missing event values are schema errors. `write-bits` indexes bytes relative to the actual write address and register address. It never applies the low mask byte to a different lane, and never uses JavaScript's modulo-32 shift behavior.

A rule matches if its predicate is true for **any one** normalized fact. Evaluate every rule for the triggering observation; `matchingRuleIds` follows rule-array order. The first matching rule in that array is the latched violation; within that rule, the first matching normalized fact is retained. Rule-array and fact order are normative. No later operation is allowed after that observation. This makes simultaneous matches deterministic without allowing the legacy adapter to mark unrelated rules as passed.

## Reports, compatibility and terminal handling

`report()` returns `sq64-watch-report` version 1 with status/gate state, verified-or-partial identity, rules version/digest, last successfully evaluated sequence/tick, first violation or monitoring error, at most four recent valid events, and a `critical` compatibility report. A violation contains its `ruleId`, all matching IDs, warning/action, the complete triggering event, first matching normalized fact and full session identity. The match reports operation/address/width/value/source; the event reports issuing context, virtual time, ordering, lock state and any additional source fields. Reports have no wall-clock timestamps or nondeterministic identifiers.

Legacy mapping is explicit: **only the latched rule** receives `severity: critical`, `unsafeWhen: pass`, `status: pass`. Other critical rows retain `status: not-run`, even after a long uneventful run. Neither `fail` nor a conformance pass is synthesized to mean safety. The compatibility report remains `sq64-critical-results` version 1 with existing IDs/titles/requirements and extra diagnostic fields. New `operation` values follow the normalized vocabulary above; old host-generated operation strings are not needed for matching.

`RECOVERY-*` conformance pass still means a restriction was satisfied. Static image validation remains a separate API/profile. Watch events do not consume ordinary conformance results. The existing critical triple remains the legacy polarity test, but consumers must also honor the **outer watch report's execution gate**: a monitoring error stops execution even though its compatibility report has no critical pass and `critical.terminated` is false. Otherwise a failed monitor would silently allow execution.

Monitoring errors have `kind: monitoring-error`, a code (`invalid-contract`, `invalid-identity`, `missing-capability`, `invalid-event`, `event-order`, `missing-initial-state`, `duplicate-initial-state`, `internal-error`, or an explicit `fail` reason), a distinct warning/action and a bounded input preview. Error codes describe the first rejection boundary; for example, an incorrectly numbered repeated initial event can fail schema/sequence validation before the duplicate-state check. Invalid input is never copied wholesale into diagnostics. Malformed observations cannot establish a firmware hazard.

On either terminal outcome, the consumer must immediately latch termination, cancel firmware/DMA/peripheral work, stop MIDI processing and output, reject queued mutation/execution commands, and preserve a final diagnostic snapshot and report export. The violation warning is **“Your custom firmware probably will brick your device. Do not flash it.”** Monitoring failures use **“Runtime monitoring failed. Execution is stopped; no firmware hazard has been established by this error.”**

In a browser worker, capture the final report and side-effect-free execution state, post an explicit terminal snapshot to the UI, then close the worker. The UI must latch that snapshot, disconnect MIDI, terminate/discard the worker, ignore stale messages and leave the warning/report download visible. A worker crash or missing final snapshot is a monitoring failure; the UI should preserve its last diagnostics and identify unavailable fields rather than invent a completed final report. Native execution must stop the backend and workbench processing thread, while retaining a frozen exportable report. Cleanup exceptions cannot cancel the latch or re-enable output.

Run, Step, Reset, replay, input/MIDI injection, queued work, or loading another image cannot revive a terminated session or create a replacement monitor inside it. Only reloading the containing browser session or restarting the native workbench creates a fresh session. There is no GUI bypass. Ordinary guest reset before termination preserves monitoring identity, event sequence and the active gate; each reset-state transition is observed before committing it.

## Canonical identity and bounds

Ruleset digest is SHA-256 of the **entire** validated contract serialized as restricted canonical JSON: recursively lexicographically sorted ASCII object keys, array order unchanged, no insignificant whitespace, unsigned base-10 integer numbers without leading zeros, literal `true`/`false`/`null`, standard JSON escaping of quote and backslash, and ASCII bytes with **no final newline**. Strings are nonempty printable ASCII (32–126), at most 512 characters; floats and Unicode strings are outside v1. Other restrictions below also apply. Whitespace/key-order changes do not change the digest; predicate constants, array order, warnings, spec/model identity and any other content do. `ruleset_digest` and the independent canonical test vector fix serialization details.

Contract/event limits are 64 KiB/32 KiB of raw serialized input and canonical serialization, JSON depth 32, 8192 visited values, 256 keys per object, 512 elements per generic array. Contracts have 1–32 rules, retain all five mandatory v1 IDs, and permit at most 256 predicate nodes per rule, depth 8 and 32 children/ranges per operator. Scalar-membership lists have at most 256 members. Rules have at most 32 requirement references. At most four controllers, 16 streams/controller, 64 explicit state registers and **256 total distinct tracked words** are accepted; the complete shape is strictly validated. State cannot grow with event count. Initialization retains a private validated contract/identity, fixed register image, at most four valid events, and one terminal diagnostic. A malformed-event preview retains only recognized scalar metadata (strings truncated to 160 characters); arrays/nested payloads are omitted. Event sequences/ticks and all generic integer scalars are at most 2^53−1; register words/CPU start addresses are unsigned 32-bit. No numeric operation needed by this ruleset exceeds exact integer precision in JavaScript; 64-bit write payloads remain hex bytes.

## Compatibility corrections and limits

The existing five IDs and their hazard conditions are retained. This revision intentionally adds initial-state/instruction/transition observation, fixes upper-byte/eight-byte masked-write handling, and defines rule-array precedence for simultaneous matches. For an eight-byte write starting at FLASH_CR with an erase bit set that also touches the option window, the new deterministic first result is CRITICAL-001 with CRITICAL-002 also listed in `matchingRuleIds`; the old hand-coded option-check branch could select CRITICAL-002 first. Termination is unchanged. These corrections have named shared fixtures.

This monitor implements the declared restriction policy. It does not perform baseline/dependency comparison, prove recovery entry after a corrupt application, run power-interruption campaigns, validate calibration ownership, discover unmodeled physical aliases, or replace an application-only write allowlist. It also cannot detect events a dishonest or incomplete observer never supplies. A capability declaration and passing reference fixtures are necessary, not proof of complete instrumentation. Unsupported parts, unobservable transitions or missing paths require monitoring error/failure to start, not a claim of hardware safety. Reports retain `hardwareValidated: false` and `recoveryGuaranteed: false`. A finite run without a violation does not establish safety for future inputs or schedules.

## Tooling and shared fixtures

```sh
python -m sq64_spec --watch-rules > watch-rules.json
python -m sq64_spec --watch-fixtures > watch-fixtures.json
python -m sq64_spec --watch-session observed-session.json --output watch-report.json
python -m unittest discover -s tests -v
python tools/render_requirements.py --check
python tools/render_watch_rules.py --check
python tools/build_watch_fixtures.py --check
```

`--watch-session` is offline replay, not live monitoring or a conformance certificate. Its exact envelope is `{format: "sq64-watch-session", version: 1, identity, capabilities, events}`. It accepts at most 16 MiB/100000 events, stops at the first terminal outcome and exports `inputScope: supplied-observations-only`. Exit codes are 0 for an active monitor after supplied observations, 1 for a violation, and 3 for a monitoring/tooling error; argument usage errors remain 2. An absent initial state is an error. Unparseable envelopes produce an error message on stderr; structured monitor errors remain downloadable JSON reports. Static/profile CLI exit meanings are unchanged.

Shared [`watch-fixtures.json`](../sq64_spec/watch-fixtures.json) contains ruleset identity, baseline identity/capability inputs and named cases. For each case: deep-copy the contract/identity/capabilities; apply `contractChanges`, `identityChanges`, `capabilityChanges` as exact path-array replacements; recompute the fixture identity's ruleset hash only when `rebindRules: true`; initialize; feed `events` in order. String events are raw JSON parser tests. Compare final status, first rule/event sequence, matching IDs and monitoring-error code with `expected`; ensure later events cannot alter a terminal report. Empty events can intentionally test preflight errors; normal sessions contain a complete initial event. Mutation paths are a **fixture harness convention**, not a runtime predicate or executable expression. Rebinding is for explicit test-only altered contracts, never an automatic production approval mechanism.

`tools/build_watch_fixtures.py` authors expected results independently; it does not call the monitor to generate answers. `tests/test_watch.py` tests the fixture protocol, strict parsing, identity, immutable exports, bounds, capability failures, internal monitor failures, canonical hashing, CLI exits and legacy polarity. The [emulator handoff](emulator-watch-handoff.md) enumerates the separate native/browser tests needed to prove real observation coverage and stopping before side effects.
