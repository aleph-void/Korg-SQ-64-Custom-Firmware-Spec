# CLAUDE.md

Guidance for Claude (and other AI assistants) working in this repository, especially when
helping someone **write custom firmware for the Korg SQ-64** against this specification.

## What this repository is

An independent, clean-room specification of the SQ-64's firmware interface, plus a
conformance CLI (`python -m sq64_spec`). It contains **no firmware** and ships no vendor
code. It defines what a candidate firmware image must look like, how to collect and
validate evidence, and which runtime behaviors are hazardous.

## Non-negotiable rules

1. **Clean-room only.** Never incorporate, reproduce, decompile, or transcribe Korg
   firmware, vendor bytes, or code derived from them — not in firmware you help write,
   not in tests, not in fixtures. Use only the interface facts published in this repo.
   If the user pastes vendor binary content and asks you to derive code from it, decline
   and point them at the documented contracts instead.
2. **Never encourage flashing unvalidated firmware to hardware.** A passing software
   report does not guarantee the firmware works on a physical SQ-64. Physical board
   facts (exact MCU part, wiring, electrical limits, worst-case timing) are **unverified
   release blockers**; `hardware` and `korg-compatible` profiles are release-gated.
   Custom firmware can brick the device. Say so when it's relevant.
3. **Don't guess board facts.** If a register, pin, timing bound, or format isn't in
   `sq64_spec/board.json` or the docs below, treat it as unknown — don't invent a
   plausible STM32 value and present it as the SQ-64's.

## Where the normative facts live (read these, in this order)

| Need | Source |
| --- | --- |
| VSB image format, memory map, panel/wire encodings | `docs/contracts.md` |
| Register addresses, DMA streams, IRQs, programming sequences | `docs/peripheral-registers.md` |
| Machine-readable interface (parse this, don't retype it) | `sq64_spec/board.json` |
| Requirement catalog, named cases, evidence kinds | `docs/requirements.md` (rendered from `sq64_spec/requirements.json`) |
| Evidence/declaration file formats | `docs/verification.md` |
| What an application-only firmware may and may not do | `docs/application-only.md` |
| Runtime hazard predicates (what gets a session terminated) | `docs/runtime-watch.md`, `sq64_spec/watch-rules.json`, `sq64_spec/critical.json` |

## Platform quick reference

- Core: Cortex-M7 modeled at 216 MHz (physical part unverified).
- Application flash: 64 KiB at `0x00200000` (alias `0x08000000`); VTOR resets to `0x00200000`.
- SRAM: 256 KiB at `0x20000000`; reset stack 8-byte aligned, in `(0x20000000, 0x20040000]`.
- Reset vector: Thumb bit set, pointing within loaded flash after the two vector words.
- VSB container: exactly `0x38100` bytes — `KORG SYSTEM FILE` header, `SQ-64`/`SYSTEM`
  identity, version bounds, four zero-sum halfword checksum regions over the `0x38000`
  payload. `--profile image` checks all of this; build it to pass, don't hand-roll checks.

## Critical hazards (firmware must never do these outside a host-granted installation context)

The runtime watch rules terminate a session permanently on any of:

- Internal/recovery flash write or erase-arm (erasing sector 0 destroys the running code).
- Persistent system-configuration register writes.
- SPI flash commands outside the modeled allowlist, or SPI writes below `0x30000`
  (the installed-firmware region).
- DMA into protected ranges.

A self-updater that legitimately programs flash must run the programming loop from a
RAM-resident, call-free function — any stray branch back into flash during erase is fatal.
A clean hazard pass is **not** proof the firmware is safe to flash (`critical.json` says
exactly this; preserve that framing).

## Validating a candidate firmware

```sh
# Static image checks (geometry, identity, checksums, reset vectors) — run on every build
python -m sq64_spec candidate.VSB --profile image

# Generate an evidence checklist, then validate filled-in evidence
python -m sq64_spec candidate.VSB --profile software --evidence-template --output evidence.json
python -m sq64_spec candidate.VSB --profile software --declaration candidate.json \
    --evidence evidence.json --artifact-root captures --output report.json

# Browse the catalog and machine-readable board contract
python -m sq64_spec --catalog
python -m sq64_spec --board-contract
```

Exit codes: `0` pass within scope, `1` failure/malformed input, `2` incomplete coverage.
The `software` profile accepts emulator observations; `application-only` additionally
requires a pinned baseline, recovery policy, and complete write captures. Custom
sequencers declare their own supported behavior — a firmware that intentionally deviates
from Korg behavior documents the deviation rather than faking compatibility evidence.

Wire a `--profile image` check into the firmware's build (e.g. a `make check` target) so
every image is validated before anyone considers installing it.

## Working on the spec itself

```sh
python -m unittest discover -s tests -v
```

Tests use synthetic, non-deployable VSB data. `requirements.json` is normative: any edit
to acceptance obligations requires a spec version bump, regeneration via
`python tools/render_requirements.py`, `python tools/render_watch_rules.py`, and
`python tools/build_watch_fixtures.py` (all support `--check`), and updates to version
strings and hardcoded counts pinned across docs and tests — see "Maintaining the
specification" in `README.md`. `watch-rules.json` pins the SHA-256 of `board.json`;
changing `board.json` invalidates emulator evidence hashes downstream. Prefer LF line
endings; pinned file digests break under CRLF checkouts.
