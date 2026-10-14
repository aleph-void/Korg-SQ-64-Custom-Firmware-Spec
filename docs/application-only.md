# Application-only recovery restrictions

Specification 0.9.0 retains the opt-in `application-only` acceptance gate. It includes the 68 software requirements and RECOVERY-001 through RECOVERY-006. Missing policy, missing evidence, unverified artifacts, incomplete captures, or a failed requirement reject acceptance with exit code 1. Existing profiles retain their scope.

The first 64 KiB of internal flash is immutable against a reviewed, known-recoverable baseline. The reviewer must identify and preserve every additional recovery code/data dependency. Neither installation nor runtime may attempt to erase or program protected ranges, even if the resulting bytes would be identical. Option unlocking/programming, OTP writes, protection/RDP changes, boot/debug configuration changes, persistent status/security writes, chip/mass erases and unknown persistent operations are forbidden. Reviewed write allowlists differ between installation and runtime. Reserved, calibration and unknown ownership remain protected by omission from those allowlists.

Recovery must execute before the custom application and must remain usable with an absent, corrupt, immediately faulting or invalid-vector application. Software fault injection must cover each erase/program boundary, partial operations, commit metadata, disconnects and timeouts. Each interrupted state needs a cold recovery and approved restore trial. Do not perform destructive physical power-cut trials to populate these cases. See the normative catalog for the full case lists.

## Invoke the gate

```sh
python -m sq64_spec candidate.VSB --profile application-only \
  --baseline reviewed-baseline.VSB --recovery-policy recovery-policy.json \
  --policy-sha256 REVIEWER_APPROVED_SHA256 --write-trace writes.json \
  --declaration candidate.json --evidence evidence.json --artifact-root captures \
  --output application-report.json
```

The policy hash is an explicit reviewer-selected trust anchor, not an approval inferred from the candidate. Bind it to the exact raw JSON bytes. Evidence uses the existing v2 schema and exact specification/model revision. Recovery inputs supplied to another profile are rejected rather than ignored. Policy and trace paths are CLI inputs; installer, observer and evidence artifact paths must stay within `--artifact-root` and their bytes must match their hashes.

A policy has `format: "sq64-recovery-policy"`, integer `version: 1`, `specVersion: "0.9.0"`, `baselineSha256`, a nonempty `reviewRevision`, and `installer` and `observer` objects, each containing `artifact` and `artifactSha256`. It also requires:

- `protected`: additional nonoverlapping ranges with `space`, `start`, `length`, `purpose` and `kind` (`recovery`, `reserved` or `calibration`). The mandatory internal 64 KiB cannot be redefined. Recovery dependencies must be fully available in the baseline package.
- `writes`: exactly `installation` and `runtime` lists of nonoverlapping ranges with the same range fields except `kind`. They cannot overlap protected storage.
- `spiGeometry`: a power-of-two `pageSize` and nonempty distinct power-of-two `eraseSizes` reviewed for the actual board.

Addresses are integer offsets in `internal-flash` (64 KiB) or `spi-flash` (16 MiB); lengths are positive and endpoints exclusive. CPU aliases and DMA must be normalized by the observer. These bounds describe the software contract, not verified board part identities. No permissive default policy is supplied.

A write trace has `format: "sq64-write-trace"`, integer `version: 1`, and `imageSha256`, `baselineSha256`, `policySha256`, `installerSha256`, `observerSha256`. Evidence's top-level `recovery` object must contain exactly those five bindings plus `traceSha256`. Every hash binds exact artifact bytes.

Trace `runs` must contain both installation and runtime captures. Each run needs a unique `name`, `phase`, candidate execution `context`, `complete: true`, `captureStart: "before-execution"`, `captureEnd: "after-completion"`, `baselineIdentity: "content-measurement"`, `coverage: "all-persistent-mutation-attempts"`, `eventCount` and `events`. Context tools must identify the approved observer and, for installation, the approved installer. An emulator context must bind this revision's model hash. A probe or review context cannot substitute for an execution capture.

Each event has a consecutive zero-based `sequence` and `operation`. `program` and `erase` events include `space`, `start`, `length`; all mutation attempts must be recorded, including failed/unlocked attempts. Forbidden operation names are `chip-erase`, `mass-erase`, `option-unlock`, `option-write`, `otp-write`, `protection-change`, `boot-config`, `debug-config`, `status-write`, `unknown-write`. Other names are rejected. Erases must have approved aligned geometry and programs cannot cross a page. Each complete installation must cover all changed candidate bytes with program events. Captures do not replace required named-case evidence or dependency review.

## Emulator critical result contract

[`watch-rules.json`](../sq64_spec/watch-rules.json) defines executable runtime hazard predicates. [`critical.json`](../sq64_spec/critical.json) is generated legacy metadata. See the [runtime contract](runtime-watch.md) for continuous observation, strict validation, capabilities, ordering and terminal-session behavior, and the [emulator handoff](emulator-watch-handoff.md) for implementation hooks and required integration tests. Each result carries `severity: "critical"` and `unsafeWhen: "pass"`. A predicate **passing means a hazard was detected**. Conformance `RECOVERY-*` results retain ordinary semantics: pass means the restriction was satisfied. Consumers must never treat every conformance pass as a hazard.

```json
{
  "id": "CRITICAL-002",
  "severity": "critical",
  "unsafeWhen": "pass",
  "status": "pass",
  "operation": "write",
  "space": "cpu",
  "width": 4,
  "value": "00000000",
  "address": 1073888276,
  "length": 4,
  "source": "cpu",
  "imageSha256": "<exact loaded image SHA-256>"
}
```

Automatic termination is enabled by default and has no GUI bypass. Monitoring starts before firmware execution and does not depend on Validate Image or debugging. A monitoring failure also terminates, with a distinct monitoring-error diagnostic and no fabricated hazard pass. A matching result stops firmware execution, disconnects its MIDI transport, latches the first detection and warns: **“Your custom firmware probably will brick your device. Do not flash it.”** Preserve the result, operation/address, source, image identity and execution report. Run, Step, Reset, replay and MIDI cannot resume the terminated image. Further image loads are blocked in that terminated session. Reload the containing browser page or restart the native workbench to investigate another image. Saving the report must remain possible. In the browser, terminate the execution worker after delivering its final snapshot.

The current runtime predicates conservatively detect internal recovery flash writes/erase arming, system/option writes, forbidden or unknown SPI commands, installed SPI image writes and unsafe DMA destinations. They watch attempted operations even if the modeled flash is locked. The stock updater may trigger them when it attempts to rewrite installed firmware. SPI installation destinations `[0, 0x30000)` are frozen during ordinary emulation; staging writes are separate. Untriggered predicates remain `not-run`: they do not claim that every triggering path was exercised.

The default monitor is not a complete application-only trial runner or a device-specific ownership policy. Dependency review, baseline comparison, additional protected ranges and recovery/interruption campaigns still require their own bounded evidence. The emulator's default report cannot be used directly as a complete write trace. Physical board identity, DMA coverage beyond the modeled controllers and persistent storage ownership remain unverified.

## Meaning of acceptance

`acceptance: "accepted"` means the supplied bounded checks passed. Reports always retain `recoveryGuaranteed: false` and `hardwareValidated: false`. Artifact hashes establish integrity, not the truth or completeness of supplied observations. Arbitrary privileged firmware can take a dangerous path after finite testing. A stronger guarantee needs independently reviewed hardware enforcement or a trusted supervisor/interpreter that contains unprivileged application code, DMA and privileged exception handlers. This profile reduces risk; it cannot certify that an arbitrary binary will never brick hardware.
