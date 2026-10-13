# Codex guidance for SQ-64 custom firmware

Help users build original custom SQ-64 firmware against this specification, with
reproducible builds, explicit behavior, and candidate-specific validation.
These instructions apply throughout this repository. Paths and commands below
are relative to its root unless stated otherwise.

## Repository scope

This repository contains an independent interface specification, a Python
conformance CLI, runtime watch rules, and synthetic test fixtures. It does not
contain a firmware build system, a cross-compiler, or a running emulator. Python
3.10+ is required; the validators have no runtime dependencies.

Read `README.md` and `PROVENANCE.md` first. The project discloses observations
from a private reference implementation and **does not claim a formal clean-room
process**. Write original code against the published interfaces; do not import
vendor firmware, decompiled implementations, factory assets, calibration bytes,
or user data into this repository or its fixtures.

Custom sequencing behavior is welcome. Declare intended features and deviations
instead of assuming stock Korg behavior is the goal. Physical MCU identity,
wiring, protected storage ownership, electrical limits, and worst-case timing
remain unresolved. Treat modeled behavior as a software contract, and label
unknown hardware facts explicitly.

## Read the sources needed for the task

| Task | Source of truth |
| --- | --- |
| Requirements, profiles, named cases, acceptance bounds | `sq64_spec/requirements.json`; rendered reference: `docs/requirements.md` |
| VSB packaging, memory installation, panel, power, update and backup protocols | `docs/contracts.md` |
| Register addresses, interrupts, DMA assignments and programming sequences | `docs/peripheral-registers.md` |
| Machine-readable memory, panel and output model | `sq64_spec/board.json` |
| Candidate declarations, evidence v2, capture integrity and report semantics | `docs/verification.md` |
| Preserved recovery baseline and application-only restrictions | `docs/application-only.md` |
| Executable hazard predicates | `sq64_spec/watch-rules.json`; reference: `docs/runtime-watch.md` |
| Connecting a monitor to an emulator | `docs/emulator-watch-handoff.md` |

Parse machine-readable facts when generating code or tooling. Do not substitute
a plausible STM32 pin, register, flash layout, or calibration value for a missing
SQ-64 fact. If documentation and an executable check disagree, report the exact
discrepancy and add a focused regression case when fixing it; do not silently
weaken the check to accept a candidate.

## Starting a firmware project

1. Inspect the workspace and preserve existing changes. Locate the user's
   firmware sources, build commands, toolchain and emulator before using them.
   Sibling projects mentioned in the docs are optional external resources;
   confirm their presence and read their instructions. Do not assume a path or
   command exists in a standalone clone of this spec.
2. Establish the requested musical behavior, destination for new firmware code,
   and execution target. Default initial development to the documented emulator
   model and explicit `image`/`software` checks. Clarify consequential missing
   choices while continuing independent work. Keep new firmware in a distinct
   project directory, outside `sq64_spec/` and its synthetic fixtures.
3. Use the project's existing build conventions. If creating a new project,
   record the compiler version, target/ABI flags, linker script, startup code,
   packaging command and output paths. Keep platform I/O separate from sequencing
   logic so behavior can be tested on the host. Add a repeatable build and an
   image-validation target; do not invent a firmware build command for this repo.
4. Implement in observable increments: reset/startup and fault handling; timing
   and transport; panel/display; sequencing and outputs; project persistence;
   then any requested update/backup support. Map each increment to requirement
   IDs and named cases. Partial prototypes are useful, but report their missing
   coverage rather than claiming whole-profile conformance.
5. Complete the requested implementation and available checks. If a compiler,
   emulator or capture is unavailable, identify that limitation precisely and
   retain runnable commands for the next environment. Never report an unrun
   build or hypothetical observation as successful.

## Firmware implementation constraints

- The modeled target is ARMv7E-M/Cortex-M7 at 216 MHz, with 64 KiB of internal
  flash at `0x00200000` (alias `0x08000000`) and 256 KiB SRAM at `0x20000000`.
  These values do not establish the physical part or its full capabilities.
- Supply a vector table and explicit startup initialization, including `.data`
  copying and `.bss` clearing. The emulator does not relocate the application
  into RAM for you. Validate reset-stack alignment, Thumb reset-vector range,
  and linker bounds with the actual linked image and `--profile image`.
- A full-system VSB is exactly `0x38100` bytes, including its `0x100`-byte header.
  Follow the four checksum regions and the noncontiguous payload-to-SPI mapping
  in `docs/contracts.md`. An arbitrary ELF or raw binary is not a VSB. Tests use
  synthetic, non-deployable images; do not treat those fixtures as firmware.
- Use bounded work in interrupt handlers and timing-critical paths, explicit
  buffer limits, and deterministic handling of malformed MIDI/SysEx, queue
  overflow, disconnects and timeouts. Test sequencing with controlled virtual
  time and reproducible inputs. Declare acceptance bounds before measuring.
- Preserve the panel scan pipeline and USB-MIDI cable direction: host-to-device
  uses cable 2; device-to-host uses cable 1. Verify firmware responses, not just
  host UI state. Read the peripheral contract before configuring DMA or outputs.
- Exercise project create/load/save/delete, slot boundaries, empty slots and
  interrupted operations. A transfer ACK is not durable storage. Persistence
  evidence needs normal power-button shutdown, a cold restart and fresh readback;
  immediate reset or closing a browser page is not equivalent.
- For the browser emulator, inspect long branch-free runs in the linked code.
  `docs/contracts.md` describes its translation-block budget and an approximate
  80-instruction working margin. This is an engine limitation, not a hardware
  requirement or a guarantee for every instruction mix.

## Recovery and runtime monitoring

Read `docs/application-only.md` before designing installation or persistent
write paths. `application-only` is a conformance profile, not a raw application
image format: it still takes a full VSB and requires the first 64 KiB of internal
flash to remain identical to a reviewed, known-recoverable baseline. Additional
recovery dependencies must also be identified and protected. A replacement of
that internal image cannot qualify merely by calling itself application-only.

The profile requires an independently reviewed policy hash, separate installation
and runtime write allowlists, complete mutation-attempt captures, and recovery
and interruption cases. Do not manufacture a permissive policy, approve a policy
just by hashing it, or infer storage ownership from unused addresses.

For emulator work, preserve monitoring from before the first instruction and
before side effects, across CPU aliases, DMA, interrupts and all execution modes.
Internal/recovery flash writes, system/option writes, forbidden SPI commands,
installed SPI writes below `0x30000`, and unsafe DMA destinations are covered by
the executable rules. Do not disable rules to make a candidate run or infer a
guest-controlled installation exemption. An updater needs its separately
documented host context and recovery review; SRAM execution alone grants neither.

`CRITICAL-*` results with `unsafeWhen: "pass"` mean a hazard was detected.
Ordinary conformance passes retain their normal meaning. A violation or monitoring
error permanently terminates that session; preserve diagnostics and report
export. Untriggered rules remain `not-run`, and an active offline replay does not
prove that live emulator instrumentation is complete.

Keep hardware installation separate from software development. A request to
write or validate firmware does not by itself authorize flashing a device.
Never present a software pass as hardware certification or a recovery guarantee.
The physical profiles remain release-gated. Use software fault injection for
programming interruptions; do not perform destructive physical power-cut trials.

## Candidate validation workflow

Run these commands from this spec checkout, replacing example artifact paths
with the actual firmware build outputs. Always select a profile explicitly:
the CLI defaults to `hardware`.

```sh
# Run static checks on each newly packaged image.
python -m sq64_spec candidate.VSB --profile image --output image-report.json

# Generate a fresh checklist for this exact candidate (do not overwrite captures).
python -m sq64_spec candidate.VSB --profile software --evidence-template --output evidence-template.json

# After authoring candidate.json and collecting evidence.json plus captures:
python -m sq64_spec candidate.VSB --profile software --declaration candidate.json --evidence evidence.json --artifact-root captures --output report.json
```

Use `docs/verification.md` for the declaration and evidence schemas. Declare all
seven feature areas, intentional deviations and quantitative limits. Each
required case needs actual expected/observed results, a qualifying execution or
review context, and a verified capture under `--artifact-root`. Unsupported
optional behavior still needs its declared absence/rejection case.

Bind the declaration and evidence to the exact VSB SHA-256 and source revision;
emulator evidence also binds the current `board.json` hash. A rebuilt candidate
needs matching evidence. Preserve failed cases and leave unexecuted cases
`not-run`. Tooling tests, diagnostic probes and another image's captures cannot
substitute for candidate execution. Hashes establish artifact integrity, not the
truth of an experiment.

Conformance exits are `0` for pass within scope, `1` for failure/malformed input,
and `2` for incomplete coverage. Usage errors also use `2` but have no report.
Template/catalog exports exit `0` without running conformance. The
`application-only` gate rejects missing evidence with `1`; use its full command
and required inputs from `docs/application-only.md`.

For relevant tasks, the CLI also supports:

```sh
python -m sq64_spec --catalog
python -m sq64_spec --board-contract
python -m sq64_spec candidate.VSB --profile image --transcript update.json --output transfer-report.json
python -m sq64_spec --backup backup.json --readback after-restart.json
python -m sq64_spec --watch-session observations.json --output watch-report.json
```

Transcript validation checks bytes and begin-update version, not programming
completion. Backup comparison checks logical contents, not whether a restart
occurred. Offline watch exits are separately `0` active, `1` violation and `3`
monitoring/tooling error. Read each report's scope before drawing conclusions.

## Maintaining this specification

Keep the Python validators dependency-free and compatible with Python 3.10+.
Use independently authored fixtures and literal protocol expectations alongside
round-trip tests. Add focused regression coverage for changed validation logic.
For code or contract changes, run the existing suite and generated-file checks:

```sh
python -m unittest discover -s tests -v
python tools/render_requirements.py --check
python tools/render_watch_rules.py --check
python tools/build_watch_fixtures.py --check
```

Edit `sq64_spec/requirements.json` for catalog changes and
`sq64_spec/watch-rules.json` for runtime predicates. Regenerate affected outputs
with the corresponding commands above without `--check`; do not hand-edit
generated requirement docs, watch docs, `critical.json`, or shared watch fixtures.
Changes to acceptance obligations require a spec revision and consistent
metadata/docs/tests. Changes to `board.json` also affect pinned model hashes and
invalidate older emulator evidence. Preserve LF endings for digest-bound files.

When handing off firmware work, give the changed behavior, build/artifact paths,
exact checks run and their results, outstanding named cases and unresolved
hardware dependencies. Keep emulator observations and physical measurements
distinct. For documentation-only work, verify paths, commands and consistency
with the authoritative contracts.
