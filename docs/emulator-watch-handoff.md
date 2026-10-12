# Emulator implementation handoff: watch contract v1

The specification implementation is complete in 0.4.0. Integration into the sibling emulator is intentionally left to its implementation instance. The existing Python/JavaScript critical checks are context for migration; they do not establish conformance with this new continuous contract. Normative schemas, predicate semantics and all limits are in [runtime-watch.md](runtime-watch.md); generated predicates are in [watch-rules.md](watch-rules.md).

## Files to vendor and API to expose

Vendor these files unchanged from the same spec revision:

- `sq64_spec/watch.py` and its dependency `sq64_spec/validation.py`: dependency-free Python interpreter and strict JSON decoder.
- `sq64_spec/watch-rules.json`: the sole source of predicate constants, DMA normalization layout, policy ranges and command allowlist.
- `sq64_spec/board.json`: exact model identity bytes.
- `sq64_spec/critical.json`: generated legacy compatibility metadata, including canonical rules digest.
- `sq64_spec/watch-fixtures.json`: shared expected outcomes and validation vectors.
- `sq64_spec/watch-example.json`: complete synthetic example violation, generated from the first fixture.
- `LICENSE`; preserve the rest of the existing vendored package for static conformance. `watch_session.py` and the CLI are optional for live monitoring, required for offline replay tooling.

Extend `tools/sync_conformance.py` to synchronize these exports and the browser rule data. Do not hand-copy the five predicates into `sq64_emulator/critical.py` or `web/emulator/critical.js`. The native adapter should call the vendored interpreter. The browser needs a generic interpreter/normalizer for the nine versioned opcodes, strict event parser, fixed state layout, and rules data. Reject unknown versions/opcodes before execution. JavaScript must reject duplicate raw JSON keys and non-integer scalars, preserve all eight bytes of write payloads, and avoid signed/32-bit truncation when computing addresses, spans and masks. Validate raw documents before converting them to ordinary objects.

The public Python API is `WatchMonitor(rules, identity=identity, capabilities=implemented_capabilities)`, `evaluate(event) -> {allow, status}`, `can_execute`, `terminated`, `violation()`, `report()`, and `fail(reason)`. Use the same observable semantics in JavaScript. `load_rules()`, `validate_contract()`, `ruleset_digest()`, `required_capabilities()` and `state_addresses()` provide tooling. The required-capabilities export describes obligations; never copy it blindly as evidence of installed hooks.

Pin the reviewed ruleset digest, hash the exact loaded image file, hash exact `board.json` bytes, and supply the emulator name/version/build SHA-256 and virtual tick unit. All bindings are immutable for a session. A modified firmware image cannot approve modified rules. A constructor failure or unavailable identity prevents execution. All initial logical register values must be read without peripheral side effects and submitted as sequence/tick zero. Only an allowed complete `initial-state` opens the execution gate.

## Observation and hook checklist

The exact common event fields are `kind`, `sequence`, `tick`, `source`, `pc`, `exception`, `phase`, `mode`. Null location/exception means unavailable and must be explicit. Consecutive sequences globally order CPU, DMA and peripheral activity; ticks may be equal. Never reset either counter on a guest reset. Sources are `cpu`, `dma`, `peripheral`, `model`; only initialization uses `model`. Phases are boot/application/interrupt, modes run/step/replay/fast.

| Event | Payload | Native locations to audit | Browser locations to audit |
| --- | --- | --- | --- |
| `initial-state` | Complete `registers: [{address, value}]` | `core.py` after image/model initialization, before backend start | `core.js` after model initialization, before worker Run/Step |
| `instruction-boundary` | None | `core.py` instruction hook, including exception paths | `core.js` scalar hook and `bridge.js` / `tools/wasm_bridge.c` fast path, every instruction |
| `memory-write` | `space: cpu`, address, width, hex value, locked | Valid/unmapped/protected CPU hooks, `board.py` host/DMA writes and memory helpers | Equivalent core hooks, bridge write callback, memory helpers and `board.js` DMA paths |
| `register-transition` | Changed full logical words in `registers` | Board write handlers, flash-control shadow, DMA reload/completion, reset and peripheral updates | Board write handlers, flash-control shadow, DMA reload/completion, reset and peripheral updates |
| `spi-command` | Command byte, locked | `flash.py` transaction parser before opcode dispatch/rejection, including DMA-fed commands | `flash.js` transaction parser, including DMA-fed commands |
| `spi-mutation` | operation program/erase, offset, length, hex value or null, locked | `flash.py` normalized target effects before lock check or storage changes | `flash.js` same, including chip-select-triggered completion |
| `dma-transfer` | controller, stream, buffer, destination address, width, count, increment | `board.py` all transfer/atomic-batch paths before source reads/destination writes | `board.js` corresponding paths, including optimized copies |

All emulator paths here are relative to `sq64_emulator/` or `web/emulator/`, except `tools/wasm_bridge.c`. Inspect actual data flow when integrating; these are entry points, not proof that all writers have been enumerated.

Every event is evaluated synchronously before the operation it describes. If `allow` is false, latch termination and abort that operation. No callbacks, source FIFO reads, destination writes, interrupts, peripheral transitions or MIDI output may follow a terminal observation. A bus attempt and its actual logical register transition are separate: emit the attempt even if locked/rejected; emit an actual transition only if it will commit. For partial writes use exact byte lanes. For an atomic transition changing several registers, supply all resulting full logical values together; never group distinct transitions that temporarily violate a rule.

The initial snapshot and transition values must use authoritative logical state. For example, a flash-control shadow can differ from the raw memory backing a MMIO page. Observation must not call guest read handlers that clear flags, consume FIFOs or run DMA. A guest peripheral read that *itself causes* DMA/another transition must run the corresponding watch gate before those effects.

Pre-instruction checks are mandatory even in optimized execution. JavaScript refresh timers, batch-end state polling, debugger hooks that exist only when debugging is on, and periodic `complete_dma()` checks do not satisfy this contract. Both primary and secondary DMA buffers must be covered when double buffering is enabled. Planned spans, actual transfer destinations, each bus write and each resulting SPI/register effect are complementary events. Replay must use the same adapter and gates as live execution.

In Unicorn, calling `emu_stop()` from a pre-write callback alone must not be assumed to prevent that instruction's store from committing. Preserve/prove the appropriate protected-memory or backend abort mechanism, including internal aliases and eight-byte stores. Test memory, shadow registers, DMA counters, SPI state and output queues after rejection; the backend reporting that it stopped is insufficient evidence.

Before running, establish all seven event sources, four source kinds, four modes, every mandatory rule and all nine opcodes, plus all guarantees listed in `requiredCapabilities.guarantees`: before-first-instruction, pre-side-effect, locked-attempts, all-cpu-aliases, unmapped-protected-writes, partial-writes, side-effect-free-state, all-dma-transitions, all-peripheral-writers, interrupt-paths, ordered-events, terminal-session, stop-midi, final-report. Missing coverage rejects startup. A lost hook, snapshot failure, invalid event, evaluator exception or backend failure calls `fail(...)` and terminates with `monitoring-error`.

## Results, stopping and report delivery

Keep runtime watch results separate from static image/profile validation. Only the latched watch rule maps to the legacy hazard triple:

```json
{"id":"CRITICAL-001","severity":"critical","unsafeWhen":"pass","status":"pass"}
```

Other critical results stay `not-run`. Ordinary conformance passes never trigger this mapping. Simultaneous matches appear in `violation.matchingRuleIds`; rule array order chooses the first. The full report's `terminated`/`canExecute` gate also covers monitoring errors, which have **no hazard pass**. Existing `criticalStop()` or a `critical.hit` check alone is therefore insufficient for the new adapter. Read the outer watch status.

[`watch-example.json`](../sq64_spec/watch-example.json) is a complete example violation with real rules/model digests and intentionally synthetic image/build identities. Its shape includes `ruleId`, `warning`, `action`, the triggering event, normalized match and identity. The warning is exactly: **Your custom firmware probably will brick your device. Do not flash it.** A monitoring error instead says runtime monitoring failed and does not accuse firmware of a detected hazard. The four-event diagnostic history is bounded; preserve the first terminal event permanently.

Native: stop the backend immediately, stop its execution thread/scheduling, disconnect MIDI input/output and discard queued output/commands. Freeze diagnostics and report before disposing of execution state. `server.py` must reject Run, Step, Reset, replay, event/MIDI commands and further image loads after the latch. Download/report endpoints remain usable. Recovery requires a native workbench restart.

Browser: stop the engine immediately and cancel worker scheduling and MIDI processing. The worker must deliver a final diagnostic snapshot containing the watch report, warning, image identity and display/report state before closing. `client.js` must latch the containing-session state, retain that snapshot, terminate the execution worker, reject pending/queued mutation commands, ignore stale worker replies and keep report downloads functional. Preserve the warning visibly after worker termination. Recovery requires a fresh browser page session; making a new worker or loading a different image inside the terminated page must not clear the latch. Unexpected worker failure becomes a monitoring-error session stop, with the last available diagnostics rather than a fabricated firmware hazard.

There is no GUI bypass, debug dependency, Validate Image prerequisite or reset API on the monitor. Later script commands must obey the same session gate. Exporting a report never executes firmware or peripheral reads.

## Required integration tests

The reference suite proves the interpreter, schema validation, normalization, deterministic matches, bounds, diagnostics, CLI and generated artifacts. It cannot prove that an emulator supplies every real event or stops before a side effect. These remain required in **both** native and browser implementations:

1. Execute the packaged shared JSON cases against each adapter/interpreter. Match status, first ID/sequence, all simultaneous IDs, errors, legacy polarity and immutable terminal reports. Compare canonical digest output. Test malformed raw JSON (including duplicate keys), wrong image/model/rules identities, unsupported vocabulary, missing mandatory rule/hook/mode and observer/evaluator/backend failure. None may execute firmware or claim a detected hazard.
2. Run synthetic guest instructions that exercise both internal-flash aliases, system/option windows, endpoints, overlapping/unaligned/partial/eight-byte accesses, locked/rejected and unmapped/protected attempts. Verify attempted writes are observed *before* every side effect; memory and model state must remain unchanged at the first hit.
3. Drive real SPI transactions through CPU and DMA: allowed commands, unknown/status/security/chip-erase commands, command-vs-data parser boundaries, locked writes, aligned erase footprints, page-wrapped program effects, protected installed storage and allowed staging. Verify no forbidden command effect, byte mutation or FIFO consumption follows rejection.
4. Exercise both DMA controllers and every stream slot, enable/disable and partial configuration writes, peripheral direction, fixed/incrementing destinations, exact 2^32 endpoint and overflow, both alternate buffers, reload and peripheral-driven transitions. Include an unsafe enable followed by immediate disable, and unsafe target followed by immediate restoration within one batch. Assert rejection before any transfer and before source read side effects.
5. Repeat guest triggers during boot, interrupt entry/handlers/return, normal run, single Step, replay and fast/batched execution; include debug off/on paths. A trigger in the middle of a long batch must stop there. Assert instruction-boundary counts and event ordering against executed instructions and real effects, not GUI updates. Confirm shadow snapshots never invoke peripheral read side effects.
6. Verify first-hit order for simultaneous erase/option matches and that later hazards/errors do not overwrite evidence. Check exact loaded-image hash survives state saves and resets. Confirm ordinary image/conformance passes never stop execution and untriggered watch rows remain `not-run`.
7. At a terminal event, assert immediate backend stop, no subsequent instruction, no MIDI input processing/output (including previously queued sends), no peripheral service or scripted action. Native must stop its backend/thread. Browser must deliver its final snapshot, close/terminate the worker and handle stale/pending replies without reactivating state.
8. Try Run, Step, Reset, replay, script actions, queued commands and another image load after both violation and monitoring error. Every mutation must remain blocked. Confirm visible warning and downloadable JSON report remain available with no live worker/backend. Only a fresh browser session/native restart may create a new execution session.

These tests should extend the existing `tests/test_critical.py`, `web/tests/critical.test.js`, conformance-safety and browser critical workflows, with direct backend/bridge tests for pre-side-effect behavior. Passing the old critical tests or the new reference fixtures is insufficient by itself.

Coverage remains the declared software model: additional aliases/controllers, unknown hardware storage, calibration ownership, electrical behavior, baseline recovery dependencies, power-interruption campaigns and real-device recovery are not proved. A run without a violation does not establish hardware safety or complete conformance.
