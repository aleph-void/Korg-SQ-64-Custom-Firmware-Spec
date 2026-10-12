# Independent SQ-64 firmware specification

Version **0.5.0** defines 80 requirements, 340 named execution/review cases, seven executable image checks, a machine-readable emulator interface, independent update and backup validators, evidence reporting, and five executable continuous runtime watch rules. The code, documentation and fixtures are original; no Korg firmware or decompiled functions are distributed.

The software contract and validation tooling are usable now. **Physical hardware conformance remains incomplete:** exact board parts/wiring, protected storage ownership, electrical limits and worst-case timing still require independent measurements. A passing software report does not guarantee that arbitrary firmware will work on a physical SQ-64.

## Run

Python 3.10+; no runtime dependencies. From this directory:

```sh
python -m unittest discover -s tests -v
python -m sq64_spec candidate.VSB --profile image
python -m sq64_spec candidate.VSB --profile software --evidence-template --output evidence.json
python -m sq64_spec candidate.VSB --profile software --declaration candidate.json --evidence evidence.json --artifact-root captures --output report.json
python -m sq64_spec candidate.VSB --profile image --transcript update.json --output transfer-report.json
python -m sq64_spec --backup backup.json --readback after-restart.json
python -m sq64_spec --catalog
python -m sq64_spec --board-contract
python -m sq64_spec --watch-rules
python -m sq64_spec --watch-fixtures
python -m sq64_spec --watch-session observations.json --output watch-report.json
```

Install with `python -m pip install .` to use `sq64-conformance` from any directory. The wheel includes the requirement catalog, model contract, watch interpreter, rules, shared fixtures and example violation.

| Profile | Requirements | Meaning of a passing report |
| --- | ---: | --- |
| `image` | 7 | Full-system package geometry, identity, version, checksums and reset vectors |
| `software` | 60 | All applicable named cases have qualifying candidate evidence against the bounded software interface |
| `application-only` | 66 | Software evidence plus a pinned baseline, recovery policy, complete write captures and recovery/interruption cases; missing evidence is rejection |
| `hardware` (default) | 70 | Requires device measurements and a completed board contract; release-gated in this revision |
| `korg-compatible` | 74 | Hardware contract plus strict declared compatibility; release-gated in this revision |

Exit codes are `0` pass within the selected scope, `1` failure/malformed input and `2` incomplete coverage. Command-line usage errors also use argparse's exit code `2` and produce no conformance report. Standalone archive checks have their own artifact report and never imply candidate execution. Template/catalog exports exit `0` without running conformance checks. Offline watch replay has separate exits: `0` active after the supplied observations, `1` detected violation, `3` monitoring/tooling error. An active replay report is not a safety certificate.

Reports bind image results to the exact VSB SHA-256 and include hashes of successfully parsed input documents. A supplemental transcript or archive failure fails the overall report; a successful supplemental check does not replace a whole firmware requirement. A transfer checks every payload byte **and the begin-update version**, but does not prove programming completion. An archive comparison checks logical contents, but cannot itself establish that shutdown or restart occurred.

## Contract and evidence

- [Normative requirement catalog](docs/requirements.md): required cases, profiles, evidence kinds and quantitative obligations.
- [Image, memory, panel, power and wire contracts](docs/contracts.md), with [machine-readable model facts](sq64_spec/board.json).
- [Peripheral register interface for firmware authors](docs/peripheral-registers.md): the modeled register addresses, DMA stream assignments, clock rate and programming sequences a custom firmware drives.
- [Evidence and candidate declaration format](docs/verification.md), including migration from v1 and the physical test campaign.
- [Application-only restrictions and emulator critical results](docs/application-only.md).
- [Runtime watch API, event schemas and deterministic predicates](docs/runtime-watch.md), with [native/browser integration handoff](docs/emulator-watch-handoff.md).
- [Public-source provenance](PROVENANCE.md).

Generate a checklist, fill in the declared features and acceptance bounds, run the named cases, then attach observations and artifact hashes. The validator rejects stale identity, missing cases, failed cases hidden under a pass, invalid measurements and artifacts escaping the capture root. Tool hashes and observations remain supplied assertions; verifying an artifact's bytes does not independently reproduce its experiment. Diagnostic probes are useful model tests but cannot satisfy candidate execution requirements.

`software` can credit emulator observations; `hardware` cannot. No evidence file can remove the board release blockers. Custom sequencers declare their own supported behavior. Strict `korg-compatible` reports additionally require documented layout and sequencing compatibility; intentional deviations are disclosed and do not count as waivers.

## Maintaining the specification

`requirements.json` is the normative catalog. Regenerate its documentation with `python tools/render_requirements.py`; `--check` detects drift. Changes to `board.json` change the hash required by emulator evidence. Change the spec revision when altering acceptance obligations and collect matching evidence. Tests use synthetic non-deployable VSB data, independent wire vectors, populated first/last project slots and both update protocol versions. They do not constitute hardware trials.

`watch-rules.json` owns runtime predicates and normalization constants. Run `python tools/render_watch_rules.py` and `python tools/build_watch_fixtures.py` after changing it; both support `--check`. Generated `critical.json` retains legacy hazard-result polarity. Runtime monitoring starts before the first instruction, is independent of static image validation and debugging, and requires complete emulator instrumentation. A violation or monitoring error ends the session permanently while retaining diagnostics and export. The emulator integration is a separate implementation task; passing the reference tests alone does not establish complete observation or pre-side-effect stopping.
