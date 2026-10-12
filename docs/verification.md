# Verification and evidence

## Report semantics

Every applicable requirement is `pass`, `fail` or `not-run`. Any failure makes the selected profile fail; otherwise missing coverage or a release blocker makes it incomplete. Static image checks are executed locally. Runtime and review observations remain externally supplied evidence, visibly labeled as such. Supplemental update/archive checks validate only their stated scope and never silently fill a firmware requirement.

`image` contains seven static checks. `software` contains those checks plus 44 execution/review requirements and can accept emulator evidence. It excludes physical power sources, USB enumeration, DIN electrical framing, real clock accuracy/deadlines, electrical outputs/calibration/pin assignments and protected storage ownership. `hardware` has 61 requirements and only credits physical candidate execution for runtime checks. `korg-compatible` adds four compatibility requirements. Every physical profile remains release-gated on independently completing the board contract.

The [catalog](requirements.md) enumerates every required case. A single case may summarize a complete parameter matrix (for example `all-85-press-release`), but its artifact must contain the individual inputs, expectations and outcomes. Extra case names are allowed; missing required names remain not-run. Unsupported optional behavior must have an explicit rejection/absence expectation in the candidate declaration and a measured case; omitting the case is not a pass. The validator checks accounting and integrity, not whether a claimed observation is true or a chosen test adequately exercises the firmware.

## Candidate declaration

Use `--declaration candidate.json`. This example shows the shape; replace the placeholders and choose quantitative bounds before collecting measurements. Example numbers are illustrative, not hardware limits.

```json
{
  "format": "sq64-candidate",
  "version": 1,
  "imageSha256": "<SHA-256 of exact VSB>",
  "sourceRevision": "<source revision or source-tree hash>",
  "features": {
    "power": "Supported sources and startup conditions",
    "midi": "Ports, channels, messages, routing and maximum traffic",
    "sequencing": "Rules, feature boundaries, concurrency and expected traces",
    "storage": "Formats, slot coverage, migration and endurance policy",
    "recovery": "Fault, interrupted-save and update recovery behavior",
    "outputs": "Modes, inactive states and supported voltage ranges",
    "clocks": "Sources, ratios, tempo ranges and timing policy"
  },
  "deviations": [],
  "limits": [
    {"id": "CLOCK-001", "metric": "peak-jitter", "unit": "us", "min": 0, "max": 20}
  ]
}
```

All seven feature fields require nonempty descriptions. `deviations` is an explicit string array; use `[]` for none. Limits have unique `(id, metric)` pairs, finite `min <= max` and explicit units. For every quantitative requirement, declare at least one meaningful metric covering its acceptance criterion. All metrics declared for a passing requirement must have measurements. Counts, duration and uncertainty belong in the capture as well as the summary. A complete interval `value ± uncertainty` must fit inside its declared bounds; units must match exactly, with no implicit conversions. An omitted limit or measurement is incomplete; an out-of-bounds measurement is a failure even if its row says pass.

## Evidence v2

Generate the candidate-bound checklist:

```sh
python -m sq64_spec candidate.VSB --profile software --evidence-template --output evidence.json
```

The generated cases start as not-run and require no execution contexts until a pass is supplied. Add named contexts and artifact details after running the corresponding procedure. The following is an illustrative review row; use the catalog's complete case list for each requirement.

```json
{
  "format": "sq64-evidence",
  "version": 2,
  "specVersion": "0.2.0",
  "imageSha256": "<SHA-256 of exact VSB>",
  "contexts": {
    "documentation-review": {
      "kind": "review",
      "target": "candidate",
      "environment": "Reviewer and review environment",
      "sourceRevision": "<same revision as candidate declaration>",
      "fixtureRevision": "review-procedure-1",
      "tools": [{"name": "review tool", "version": "1", "sha256": "<tool SHA-256>"}]
    }
  },
  "results": [{
    "id": "VUP-008",
    "status": "pass",
    "context": "documentation-review",
    "procedure": "Review the candidate recovery instructions, revision 1",
    "observations": "Instructions state the limitation and exclude deliberate physical programming power cuts",
    "artifact": "review/recovery.txt",
    "artifactSha256": "<SHA-256 of artifact bytes>",
    "cases": [
      {"name": "document-unrecoverable-power-loss", "expected": "Limitation stated", "observed": "Section 3 states the limitation", "status": "pass"},
      {"name": "exclude-physical-programming-power-cuts", "expected": "Power-cut trial excluded", "observed": "Procedure excludes that trial", "status": "pass"}
    ]
  }]
}
```

Context kinds are `hardware`, `emulator` and `review`; targets are `candidate` or `probe`. Record the physical unit/board revision and instrument setup for hardware, or model/runtime revision and configuration for emulator runs. Every tool has a name, version and lowercase 64-character SHA-256; the tool identity is recorded, not independently authenticated. Emulator contexts also require `modelContractSha256`, the SHA-256 of this release's `sq64_spec/board.json`. Reports include that digest for convenient comparison. A candidate pass requires the source revision to match the declaration. Probe evidence remains visible but does not pass candidate requirements.

Passing rows require nonempty procedure and observations, a known context, every named case, and a relative artifact path plus its SHA-256. Cases require unique names, expected and observed strings, and `pass`, `fail` or `not-run`. Any failed case makes the row fail. Missing/unrun cases make it not-run. For quantitative rows, add:

```json
"measurements": [{"metric": "peak-jitter", "unit": "us", "value": 18, "uncertainty": 1}]
```

Supply `--artifact-root captures` to verify artifact bytes. Absolute paths, parent traversal, Windows drive paths and escaping symlinks are rejected. Without the root, supplied passes remain not-run. Static checks cannot be overridden; unknown/duplicate IDs, duplicate JSON keys, nonfinite numbers, wrong image/spec revisions and invalid evidence are errors. A reviewer should retain the original declaration with the campaign artifacts to establish that bounds were chosen in advance; the tool does not attest chronology or authenticate an experiment.

Rows may share a capture containing several independent cases, but each row must identify its procedure and observations. A digest proves neither the truth nor completeness of a capture. Hardware profiles do not credit software-only observations. Strict compatibility deviations remain blockers. Expected failures are not passes.

## Migrating v1 evidence

Version 1 evidence remains readable and artifact digests are still checked. Its supplied passes become not-run because it lacks the required environment, tools and case identity. Retain the original evidence, generate a v2 checklist, and explicitly map observations to each required case and execution context. Do not relabel old emulator captures as hardware evidence or manufacture missing observations.

## Backup and update artifacts

`--transcript` validates a single successful serialized search/version/begin/data exchange, both protocol versions, advertised fill capability, canonical packing, checksums, sequential packet indices, every ACK, exact payload bytes and the candidate header's version. Negative ACKs, host traffic before ACK, duplicate/gapped packets, missing final ACK and traffic beyond the completed transfer fail. Progress messages are permitted while waiting for begin/data ACKs. Packet receipt does not establish installed bytes, reboot success or malformed-request rejection by firmware.

`--backup` independently checks the public `sq64-backup` version 1 format. `--readback` requires `--backup` and compares decoded logical bytes, scope, empty slots and the complete record set, ignoring timestamp, record order and MIDI channel. It is a strict snapshot comparison: restore operations that intentionally preserve pre-existing data in source-empty slots need a separately reviewed expected snapshot. A matching file is not proof that the capture came from a real restart; BACKUP-004 requires the shutdown/restart procedure and candidate-bound capture separately.

Every parsed input document's exact byte hash is retained in `inputArtifacts`. Archive-only reports have no image identity and cannot satisfy candidate execution requirements on their own. Malformed evidence/declarations stop with exit code 1; supplemental validator failures are included in the report and make the overall status fail.

## Hardware campaign

1. **Read-only baseline.** Record identity, descriptors, channel/cable mapping and firmware hash from the candidate artifact. Capture a user-data backup through the normal published protocol. Mark calibration ranges as unresolved until the ownership map is established.
2. **Original diagnostic probes.** Establish each button scan position, encoder quadrature sequence, LED row/column and display command/pixel ordering independently. Exercise each control alone, simultaneous holds and release under load. Record both incoming signals and firmware observations; visual UI state alone is not evidence.
3. **CPU and initialization.** Use directed original code for aligned/misaligned scalar and multiple transfers, exception stack alignment, all mask levels, nested priorities, MSP/PSP, IT slots and eager/lazy FPU state. Cold boot with 00, FF and seeded RAM. Keep firmware failures distinct from engine limitations.
4. **Storage.** Establish protected ownership first. Test every page/sector boundary, write-enable and busy transition, zero-to-one prohibition, slot save/load, format migration and normal restart. Software fault injection covers each save phase; no test in this repository instructs power removal during real internal flash programming.
5. **MIDI and USB.** Test every supported status/channel/data boundary, truncated/running-status streams, realtime inside SysEx, oversized requests, cable isolation, USB transfer/CIN tail sizes, full-rate DIN and concurrent display/storage load. Retain raw traffic and expected replies, including rejections.
6. **Clock and outputs.** Use independent timing/voltage instruments. Capture each declared CV range and midpoint, every gate polarity, inactive/reset/stop/fault states, sync ratios, rate extremes and missing pulses. A nominal software timer value does not satisfy an electrical requirement.
7. **Updater and backup.** Exercise discovery/version/begin, every malformed field and packet boundary, fill capability, all checksum errors, ordering, timeout and disconnect. Separately verify installed bytes/version and normal boot. For backup/restore, fill every supported slot with distinct synthetic data, read back after restart and compare logical content. ACK-only peers do not satisfy persistence.
8. **Combined workload and soak.** Combine maximum supported notes, controls, clock input, storage and USB traffic. Vary seeded event schedules and long counters, retain failures, and repeat every fixed counterexample. Declare duration and sample counts; do not promote a finite soak into an exhaustive claim.

## Relationship to the emulator

The sibling browser model has bounded private stock/custom-image results for startup, panel input, USB, both update directions, installed-byte comparisons and backup/readback after normal shutdown. Its original public integration probe exercises the host/worker/ARM/peripheral path. Neither a public probe nor results for a different firmware image establish candidate conformance; the Python/native engine also has a separate coverage scope.

The model contract records 85 button positions, six encoder pairs, panel SPI pipelines, display pixel order, power-hold behavior and 17 top-edge output observations. It does not certify board wiring or voltages. Treat normal firmware power-button shutdown as part of persistence acceptance; immediate reset and closing the browser are not equivalent.

Keep these validators independent of the updater implementation. Literal golden vectors and independently authored fixtures supplement round trips. Independent physical captures and a reviewed spec revision are required before removing the hardware release gate. No bounded profile guarantees every possible input or event schedule.
