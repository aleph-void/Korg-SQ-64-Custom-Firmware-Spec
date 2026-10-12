# SQ-64 requirements catalog

Version 0.6.0. Generated from `sq64_spec/requirements.json`.

SHALL is mandatory within the selected profile. Each named case must have an explicit expected result, observation and status. Missing cases are not-run. Extra cases may extend coverage; they cannot replace required cases.

Hardware and compatibility profiles require candidate hardware observations for runtime requirements. Software and application-only profiles also accept candidate emulator observations for inherited software requirements. Recovery requirements use their explicit evidence kinds. Application-only rejects any missing requirement or failed mandatory policy check. Review evidence is accepted only where listed. Image checks are executed directly and cannot be overridden.

## PKG-001 — Container

**Requirement:** Firmware or its delivery tooling SHALL use one 256-byte VSB header and a 0x38000-byte full system payload.

**Verification:** Executed by sq64_spec.image.inspect; corrupt-field negative fixtures cover each check.

**Profiles:** image, software, hardware, korg-compatible, application-only

**Evidence kinds:** static

## PKG-002 — Target identity

**Requirement:** Firmware or its delivery tooling SHALL identify SQ-64 SYSTEM block zero, product ID 00 01 60, and member FF.

**Verification:** Executed by sq64_spec.image.inspect; corrupt-field negative fixtures cover each check.

**Profiles:** image, software, hardware, korg-compatible, application-only

**Evidence kinds:** static

## PKG-003 — Geometry

**Requirement:** Firmware or its delivery tooling SHALL use base zero, start zero, and total and payload length 0x38000.

**Verification:** Executed by sq64_spec.image.inspect; corrupt-field negative fixtures cover each check.

**Profiles:** image, software, hardware, korg-compatible, application-only

**Evidence kinds:** static

## PKG-004 — Version encoding

**Requirement:** Firmware or its delivery tooling SHALL use major <64, minor <128 and delay <=60000 ms or FFFFFFFF.

**Verification:** Executed by sq64_spec.image.inspect; corrupt-field negative fixtures cover each check.

**Profiles:** image, software, hardware, korg-compatible, application-only

**Evidence kinds:** static

## PKG-005 — Payload checksums

**Requirement:** Firmware or its delivery tooling SHALL make each documented checksum region sum to zero modulo 65536.

**Verification:** Executed by sq64_spec.image.inspect; corrupt-field negative fixtures cover each check.

**Profiles:** image, software, hardware, korg-compatible, application-only

**Evidence kinds:** static

## BOOT-001 — Initial stack

**Requirement:** Firmware or its delivery tooling SHALL place the eight-byte-aligned initial stack within 0x20000000..0x20040000, excluding the lower bound.

**Verification:** Executed by sq64_spec.image.inspect; corrupt-field negative fixtures cover each check.

**Profiles:** image, software, hardware, korg-compatible, application-only

**Evidence kinds:** static

## BOOT-002 — Reset vector

**Requirement:** Firmware or its delivery tooling SHALL provide a Thumb reset vector in loaded internal flash.

**Verification:** Executed by sq64_spec.image.inspect; corrupt-field negative fixtures cover each check.

**Profiles:** image, software, hardware, korg-compatible, application-only

**Evidence kinds:** static

## BOOT-003 — Cold startup

**Requirement:** Firmware or its delivery tooling SHALL initialize every RAM value read before first assignment and reach an observable ready state from cold reset.

**Verification:** Cold boot twice with RAM filled with 00, FF and deterministic random bytes; compare declared ready condition.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `zero-ram`, `ff-ram`, `seeded-ram`, `repeat-ready`

## BOOT-004 — Startup modes

**Requirement:** Firmware or its delivery tooling SHALL interpret GLOBAL held at power-on as version mode and GLOBAL+PATTERN as update mode.

**Verification:** Boot using held panel signals, then release; verify version and updater discovery on candidate execution.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `normal`, `global-version`, `global-pattern-update`, `release-chord`

## BOOT-005 — Reboot persistence

**Requirement:** Firmware or its delivery tooling SHALL retain committed user data over normal software and power-button restart.

**Verification:** Save distinct values, restart twice, export and compare logical data.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `committed-save`, `software-restart`, `power-button-shutdown`, `cold-readback`

## BOOT-006 — Fault behavior

**Requirement:** Firmware or its delivery tooling SHALL report unrecoverable faults without continuing uncontrolled output or corrupting persistent data.

**Verification:** Inject invalid vectors and unaligned multiword access in original diagnostic builds; expect explicit failure.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `invalid-vector`, `unaligned-multiword`, `inactive-outputs`, `persistent-data-guards`

## BOOT-007 — Power sources

**Requirement:** Firmware or its delivery tooling SHALL start and operate with each supported power source.

**Verification:** Physical USB-power and external-adapter cold-start trials with candidate hashes recorded.

**Profiles:** hardware, korg-compatible

**Evidence kinds:** hardware

**Required cases:** `usb-power`, `external-power`

## CPU-001 — Alignment

**Requirement:** Firmware or its delivery tooling SHALL honor architectural alignment requirements for stack, exception frames and multiword/FP transfers.

**Verification:** Directed aligned/misaligned scalar, LDM/STM, LDRD/STRD and FP cases; no model bypass.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `scalar-alignment`, `ldm-stm`, `ldrd-strd`, `floating-point`, `stack-alignment`

## CPU-002 — Interrupt masking

**Requirement:** Firmware or its delivery tooling SHALL honor PRIMASK, BASEPRI, FAULTMASK, NVIC enable and priorities.

**Verification:** Pending interrupts across mask transitions and nested higher/lower-priority delivery.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `primask`, `basepri`, `faultmask`, `nvic-enable`, `nested-priorities`

## CPU-003 — Exception context

**Requirement:** Firmware or its delivery tooling SHALL preserve architectural integer, stack, status and active floating-point state through interrupts.

**Verification:** Preempt thread/handler on MSP/PSP, including IT slots, nested IRQs, eager and lazy FP.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `msp`, `psp`, `it-slots`, `nested-irqs`, `stack-padding`, `eager-fp`, `lazy-fp`

## CPU-004 — Memory bounds

**Requirement:** Firmware or its delivery tooling SHALL keep code, data, stack and DMA accesses within the image and board memory contracts.

**Verification:** Guard every mapped boundary; stress maximum queues and stack depth under simultaneous events.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `code-boundaries`, `data-boundaries`, `stack-guards`, `dma-boundaries`, `maximum-queues`

## CPU-005 — Concurrency

**Requirement:** Firmware or its delivery tooling SHALL preserve storage, MIDI and control invariants under racing interrupt and DMA schedules.

**Verification:** Replay deterministic varied interleavings; retain every counterexample and its seed.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `storage-midi-races`, `control-dma-races`, `seeded-replay`, `counterexample-replay`

## PANEL-001 — Buttons

**Requirement:** Firmware or its delivery tooling SHALL read each supported physical button independently without aliasing another control.

**Verification:** Exercise 64 pads, 21 named buttons, release, hold, simultaneous presses and repeated transitions.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `all-85-press-release`, `holds`, `simultaneous-presses`, `repeated-transitions`

## PANEL-002 — Encoders

**Requirement:** Firmware or its delivery tooling SHALL read six encoders with both directions and bounded burst rates.

**Verification:** One detent each way, wrap, acceleration and bursts; compare physical and modeled input events.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `all-six-both-directions`, `reversals`, `wrap`, `acceleration`, `bounded-bursts`

## PANEL-003 — LEDs

**Requirement:** Firmware or its delivery tooling SHALL drive each physical indicator within the board signaling contract.

**Verification:** One indicator at a time and all indicators; inspect row multiplexing and physical output.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `each-panel-indicator`, `all-panel-indicators`, `top-edge-17`, `multiplexing`

## PANEL-004 — Display

**Requirement:** Firmware or its delivery tooling SHALL write display commands and frame data within controller and DMA limits.

**Verification:** Blank, all-on, checkerboard, edge pixels, frame refresh and custom menu drawing from candidate data.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `blank`, `all-on`, `checkerboard`, `edge-pixels`, `refresh`, `command-bounds`

## PANEL-005 — Input under load

**Requirement:** Firmware or its delivery tooling SHALL continue servicing controls while sequencing, receiving MIDI and saving.

**Verification:** Deterministic combined workload; no stuck press or silently lost release.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `sequencing-midi-save-load`, `press-release-latency`, `no-stuck-controls`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## MIDI-001 — Enumeration

**Requirement:** Firmware or its delivery tooling SHALL enumerate as the declared USB MIDI interfaces and cable routing.

**Verification:** Enumerate host descriptors, inspect endpoint types/lengths and probe each cable on physical hardware.

**Profiles:** hardware, korg-compatible

**Evidence kinds:** hardware

**Required cases:** `descriptors`, `endpoint-types-lengths`, `each-cable`, `cold-enumeration`

## MIDI-002 — Channel messages

**Requirement:** Firmware or its delivery tooling SHALL parse declared MIDI channel messages without buffer overrun or stuck notes.

**Verification:** All status/channel values, two/three-byte messages, all data bytes, running status, truncation and saturation.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `all-status-channel-values`, `data-boundaries`, `running-status`, `truncation`, `saturation`, `no-stuck-notes`

## MIDI-003 — Realtime interleaving

**Requirement:** Firmware or its delivery tooling SHALL handle realtime bytes inserted inside other MIDI messages and SysEx.

**Verification:** Insert clock/start/continue/stop at every boundary; verify parser state remains valid.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `clock-boundaries`, `start-continue-stop-boundaries`, `sysex-interleaving`, `parser-recovery`

## MIDI-004 — SysEx framing

**Requirement:** Firmware or its delivery tooling SHALL bound SysEx buffers and reject malformed framing or incorrect product routing.

**Verification:** Wrong IDs, incomplete groups, excessive lengths, timeout, nested F0 and recovery to next valid frame.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `wrong-routing`, `incomplete-groups`, `oversized-input`, `timeout`, `nested-f0`, `recovery`

## MIDI-005 — USB packetization

**Requirement:** Firmware or its delivery tooling SHALL handle MIDI event packets and short USB transfers correctly.

**Verification:** Every supported CIN, all final SysEx group sizes, cable indices, 0/4/64-byte transfers and invalid sizes.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `supported-cin`, `sysex-tails`, `cable-indices`, `zero-four-64-byte-transfers`, `invalid-sizes`

## MIDI-006 — DIN transport

**Requirement:** Firmware or its delivery tooling SHALL maintain correct MIDI DIN framing and supported receive/transmit behavior.

**Verification:** Loopback and independent receiver trials at 31250 baud, including two outputs and receive overrun.

**Profiles:** hardware, korg-compatible

**Evidence kinds:** hardware

**Required cases:** `31250-baud`, `input`, `output-one`, `output-two`, `overrun`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## MIDI-007 — Isolation

**Requirement:** Firmware or its delivery tooling SHALL prevent one MIDI cable or physical port from corrupting another port state.

**Verification:** Interleave distinct streams on every available logical and physical port.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `logical-cable-isolation`, `physical-port-isolation`, `concurrent-streams`

## CLOCK-001 — Internal clock

**Requirement:** Firmware or its delivery tooling SHALL meet the timing and jitter limits declared by the selected sequencing profile.

**Verification:** Measure output intervals with independent capture; declare tempo, load, tolerance and sample count.

**Profiles:** hardware, korg-compatible

**Evidence kinds:** hardware

**Required cases:** `tempo-minimum`, `tempo-maximum`, `jitter-under-load`, `independent-capture`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## CLOCK-002 — External clock

**Requirement:** Firmware or its delivery tooling SHALL handle declared sync/MIDI clock ratios, missing pulses and wraparound.

**Verification:** First pulse, rate changes, missing/extra pulses, timestamp wrap and maximum supported rate.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `first-pulse`, `rate-changes`, `missing-extra-pulses`, `timestamp-wrap`, `maximum-rate`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## CLOCK-003 — Transport

**Requirement:** Firmware or its delivery tooling SHALL handle start, stop and continue without unintended lingering outputs.

**Verification:** Repeated transitions at step boundaries and during note/gate activity.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `start`, `stop`, `continue`, `step-boundary`, `active-note-gate`

## CLOCK-004 — Scheduling

**Requirement:** Firmware or its delivery tooling SHALL satisfy declared output deadlines during concurrent storage, display and USB traffic.

**Verification:** Independent timing capture under worst documented simultaneous workload; software ticks alone do not pass.

**Profiles:** hardware, korg-compatible

**Evidence kinds:** hardware

**Required cases:** `storage-display-usb-load`, `worst-deadline`, `independent-capture`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## OUTPUT-001 — CV range

**Requirement:** Firmware or its delivery tooling SHALL keep pitch/modulation outputs within the supported configured voltage range.

**Verification:** Physical measurements at minimum, midpoint and maximum with declared calibration and equipment.

**Profiles:** hardware, korg-compatible

**Evidence kinds:** hardware

**Required cases:** `each-range-minimum`, `each-range-midpoint`, `each-range-maximum`, `calibration-equipment`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## OUTPUT-002 — Gate polarity

**Requirement:** Firmware or its delivery tooling SHALL apply selected gate/trigger polarity and configured inactive state.

**Verification:** Verify every gate/trigger jack in each declared polarity and during reset, stop and error.

**Profiles:** hardware, korg-compatible

**Evidence kinds:** hardware

**Required cases:** `each-gate-trigger`, `each-polarity`, `reset`, `stop`, `fault`

## OUTPUT-003 — Calibration

**Requirement:** Firmware or its delivery tooling SHALL preserve device-specific calibration data and use the declared conversion contract.

**Verification:** Before/after hashes of protected storage plus measured conversion at documented test points.

**Profiles:** hardware, korg-compatible

**Evidence kinds:** hardware

**Required cases:** `protected-before-after`, `conversion-test-points`, `measurement-uncertainty`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## OUTPUT-004 — Pin configuration

**Requirement:** Firmware or its delivery tooling SHALL avoid conflicting peripheral assignments and unsupported electrical drive modes.

**Verification:** Review GPIO configuration against board evidence; verify physical output behavior.

**Profiles:** hardware, korg-compatible

**Evidence kinds:** hardware

**Required cases:** `gpio-assignments`, `drive-modes`, `independent-pin-verification`

## OUTPUT-005 — Sequencer semantics

**Requirement:** Firmware or its delivery tooling SHALL meet the behavior and boundaries of the firmware's declared sequencing profile.

**Verification:** Custom firmware supplies explicit feature profile; Korg-compatible profile adds stock-semantic tests.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `declared-features`, `feature-boundaries`, `expected-output-traces`

## STORE-001 — Address ownership

**Requirement:** Firmware or its delivery tooling SHALL write only declared user-data or firmware regions and preserve reserved/device-specific regions.

**Verification:** Trace all erase/program commands and compare guard regions before and after.

**Profiles:** hardware, korg-compatible

**Evidence kinds:** hardware

**Required cases:** `ownership-map`, `erase-program-trace`, `reserved-before-after`

## STORE-002 — Flash semantics

**Requirement:** Firmware or its delivery tooling SHALL respect erase geometry, write enable, page limits and zero-to-one restrictions.

**Verification:** Boundary and cross-page writes, disabled writes, busy status, sector ends and malformed requests.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `page-sector-boundaries`, `cross-page`, `write-enable`, `busy`, `zero-to-one`, `malformed`

## STORE-003 — Save and load

**Requirement:** Firmware or its delivery tooling SHALL restore complete committed projects and settings without cross-slot contamination.

**Verification:** Exercise every project/control/scale slot with distinct synthetic data and normal restart.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `all-project-slots`, `all-control-slots`, `all-scale-slots`, `settings`, `normal-restart`, `cross-slot-guards`

## STORE-004 — Interrupted data save

**Requirement:** Firmware or its delivery tooling SHALL define and meet a recoverable outcome for interrupted project/settings saves.

**Verification:** Interrupt each save phase in software; require previous or new valid state, or documented explicit recovery.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `each-save-phase`, `previous-or-new-valid-state`, `explicit-recovery`

## STORE-005 — Input validation

**Requirement:** Firmware or its delivery tooling SHALL reject or safely represent malformed imported data without memory corruption.

**Verification:** Every field boundary, cross-field invalid combination, truncated dump and inconsistent presence map.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `field-boundaries`, `cross-field-invalid`, `truncated-dump`, `presence-map`, `memory-guards`

## STORE-006 — Migration

**Requirement:** Firmware or its delivery tooling SHALL handle declared older/newer data formats without silent destructive conversion.

**Verification:** Round-trip supported formats; explicitly reject unsupported versions before writing.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `supported-older`, `supported-newer`, `round-trip`, `reject-unsupported-before-write`

## STORE-007 — Wear behavior

**Requirement:** Firmware or its delivery tooling SHALL bound redundant erase/program operations for repeated unchanged settings.

**Verification:** Trace operation counts under repeated edits/saves and compare declared endurance policy.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `unchanged-settings`, `repeated-edits`, `erase-program-counts`, `endurance-policy`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## PROJECT-001 — Create project

**Requirement:** Firmware or its delivery tooling SHALL provide a documented operation that creates a new project with the declared default state in the current workspace without modifying any saved project slot.

**Verification:** Create new projects over empty and fully populated catalogs; compare the exported workspace against declared defaults and digest-compare all 64 saved slots before and after.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `documented-operation`, `declared-defaults`, `empty-catalog`, `populated-catalog`, `saved-slot-guards`

## PROJECT-002 — Load project

**Requirement:** Firmware or its delivery tooling SHALL load any saved project slot into the current workspace exactly as committed, and report an empty or invalid slot without changing the workspace.

**Verification:** Load every populated slot holding distinct synthetic data and compare exported workspace bytes; attempt empty and corrupted slots, requiring an explicit report and an unchanged workspace.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `every-populated-slot`, `exact-reproduction`, `empty-slot-report`, `invalid-slot-report`, `workspace-unchanged-on-rejection`

## PROJECT-003 — Save project

**Requirement:** Firmware or its delivery tooling SHALL save the current workspace to any selected project slot only through an explicit documented operation, modify only that slot, and report completion only after the data is committed.

**Verification:** Save distinct data to first, middle and last slots and over an existing project; digest-compare untouched slots and read back after normal shutdown and cold restart.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `first-middle-last-slots`, `overwrite-existing`, `explicit-operation-only`, `completion-report`, `untouched-slot-guards`, `shutdown-cold-readback`

## PROJECT-004 — Delete project

**Requirement:** Firmware or its delivery tooling SHALL delete any saved project slot only through an explicit documented operation, leave the slot observably empty, and preserve every other slot, the current workspace and settings.

**Verification:** Delete populated first, middle and last slots and verify emptiness by load attempt and export after restart; repeat deletion of an empty slot; interrupt delete phases in software, requiring the previous project or a valid empty slot; digest-compare remaining slots, workspace and settings.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `first-middle-last-slots`, `explicit-operation-only`, `observably-empty`, `empty-after-restart`, `repeated-delete`, `interrupted-delete`, `other-slot-workspace-settings-guards`

## GLOBAL-001 — Global settings mode

**Requirement:** Firmware or its delivery tooling SHALL enter a documented global settings mode from the GLOBAL key during normal operation and leave it, with browsing alone changing no workspace, saved-slot or committed-settings data.

**Verification:** Enter and exit global mode while stopped and while sequencing, browse every settings page without committing, and digest-compare the exported workspace, all 64 saved slots and the global record.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `global-key-entry`, `documented-exit`, `browse-without-commit`, `entry-while-sequencing`, `workspace-slot-settings-guards`

## GLOBAL-002 — Edit global settings

**Requirement:** Firmware or its delivery tooling SHALL allow editing every supported global setting, apply committed edits to device behavior and the exported global record, and preserve them over normal shutdown and cold restart without changing project, control or scale data.

**Verification:** Edit each documented global field at its boundary values, compare the exported global record, observe a behavioral effect for each functional field, read back after normal shutdown and cold restart, and digest-compare projects, controls and scales.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `each-documented-field`, `boundary-values`, `export-match`, `behavioral-effect`, `shutdown-cold-readback`, `non-global-guards`

## PATTERN-001 — Pattern selection

**Requirement:** Firmware or its delivery tooling SHALL select any of the 16 patterns of each of the four tracks as the track's active pattern through a documented operation from the PATTERN key, and make the active selection observable.

**Verification:** Select every pattern slot on every track holding distinct synthetic data; confirm the reported selection and that sequencing and export follow the selected pattern.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `pattern-key-entry`, `every-track`, `all-16-slots`, `selection-report`, `selected-pattern-effective`

## PATTERN-002 — Pattern integrity

**Requirement:** Firmware or its delivery tooling SHALL preserve every non-selected pattern across selection changes and edits, and keep each project's pattern presence map consistent with its stored patterns.

**Verification:** Fill all 64 patterns with distinct synthetic data, switch and edit repeatedly, digest-compare non-selected patterns, and compare presence bytes against stored pattern data after save and normal restart.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `non-selected-preserved`, `repeated-switching`, `edit-isolation`, `presence-map-consistency`, `save-restart-consistency`

## SHIFT-001 — Shift-modified functions

**Requirement:** Firmware or its delivery tooling SHALL treat SHIFT as a modifier only: declare every supported SHIFT-modified function or mode, perform each declared function only while SHIFT is held with its companion control, and cause no state change from SHIFT alone or from undeclared combinations.

**Verification:** Exercise every declared SHIFT combination with press/release ordering variants, then SHIFT alone and undeclared combinations with explicit no-effect expectations; digest-compare the workspace, saved slots and settings afterward. A candidate declaring no SHIFT functions still requires the no-effect cases.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `declared-combinations`, `press-release-ordering`, `shift-alone-no-effect`, `undeclared-combination-guards`, `state-guards`

## TRACK-001 — Track selection

**Requirement:** Firmware or its delivery tooling SHALL select the corresponding track as the active edit track through each of the A, B, C and D keys, make the active track observable, route subsequent edits to the selected track only, and change no pattern, workspace or settings data from track selection alone.

**Verification:** Select every track while each holds distinct synthetic data, stopped and while sequencing; confirm the reported selection, apply an edit and verify only the selected track changes, and digest-compare all patterns, the workspace and settings after selection-only sequences.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `each-track-key`, `selection-report`, `edits-follow-selection`, `selection-only-no-mutation`, `while-sequencing`

## MODE-001 — Edit mode keys

**Requirement:** Firmware or its delivery tooling SHALL enter a documented edit mode from each of the PITCH, GATE, MOD and CONTROL keys, make the active mode observable, scope edits in each mode to that mode's documented parameters on the active track, and change no data from mode entry or exit alone.

**Verification:** Enter and leave each mode while stopped and while sequencing, confirm the reported mode, perform a documented edit in each mode and verify only that mode's parameters change; digest-compare the workspace, saved slots and settings after entry-and-exit-only sequences.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `pitch-key`, `gate-key`, `mod-key`, `control-key`, `mode-report`, `edit-scoping`, `entry-exit-no-mutation`

## LOOP-001 — Loop key

**Requirement:** Firmware or its delivery tooling SHALL provide the documented loop function from the LOOP key, declare its operations and bounds, keep every loop operation within the declared bounds of the active pattern, and resume the declared normal playback behavior when the loop is cleared.

**Verification:** Exercise each declared loop operation at its boundary values, verify playback output honors the declared loop region, clear the loop and compare subsequent output against never-looped playback; digest-compare saved slots and settings afterward.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `declared-loop-operations`, `boundary-values`, `playback-honors-loop`, `clear-restores-normal`, `saved-data-guards`

## BAR-001 — Bar selection

**Requirement:** Firmware or its delivery tooling SHALL select the corresponding documented bar of the active pattern through each of the numbered keys 1 to 4, make the selected bar observable, direct step edits to steps within the selected bar, and change no pattern data from bar selection alone.

**Verification:** Select each bar of patterns holding distinct synthetic data per bar, confirm the reported bar and that pad edits land only in the selected bar's steps; digest-compare pattern data after selection-only sequences, stopped and while sequencing.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `each-bar-key`, `selection-report`, `edits-land-in-selected-bar`, `selection-only-no-mutation`, `while-sequencing`

## TAP-001 — Tap tempo

**Requirement:** Firmware or its delivery tooling SHALL derive the internal tempo from the documented TAP key sequence within the declared supported tempo range, handle out-of-range and incomplete tap sequences as documented without undefined tempo, and change no stored data from taps alone.

**Verification:** Tap documented sequences at the minimum, a nominal and the maximum supported tempo and measure resulting output intervals against the declared tolerance; apply too-fast, too-slow and single taps with explicit expected handling; digest-compare saved slots and committed settings afterward.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `minimum-tempo`, `nominal-tempo`, `maximum-tempo`, `out-of-range-taps`, `single-tap`, `measured-intervals`, `stored-data-guards`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## TEMPO-001 — Tempo knob

**Requirement:** Firmware or its delivery tooling SHALL adjust the internal tempo from the TEMPO encoder across the declared supported tempo range, apply one documented increment per detent in each direction, clamp at the declared limits without wraparound, and make the current tempo observable.

**Verification:** Step the encoder through the full range in both directions, including repeated detents at both limits and any declared acceleration; measure output intervals at the minimum, a nominal and the maximum tempo against the declared tolerance; digest-compare saved slots and committed settings after adjustment-only sequences.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `each-direction-detent`, `full-range-sweep`, `clamp-at-limits`, `tempo-report`, `measured-intervals`, `settings-guards`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## SWING-001 — Swing knob

**Requirement:** Firmware or its delivery tooling SHALL adjust the documented swing amount from the SWING encoder across the declared supported range, apply the declared timing offset only to the documented steps, clamp at the declared limits, and produce unswung timing at the neutral setting.

**Verification:** Measure step timing at the neutral setting and at the declared boundary swing values against the declared tolerance, verify steps outside the documented swing set keep nominal timing, sweep both directions with clamping at the limits, and digest-compare saved slots and committed settings after adjustment-only sequences.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `neutral-unswung`, `boundary-swing-values`, `affected-steps-offset`, `unaffected-steps-nominal`, `clamp-at-limits`, `measured-timing`, `settings-guards`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## VUP-001 — Discovery

**Requirement:** Firmware or its delivery tooling SHALL report a supported protocol and nonzero packet size, with truthful capabilities.

**Verification:** Search/version requests in update mode on cold boot and after an update.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `cold-discovery-version`, `post-update-discovery-version`, `packet-size-capabilities`

## VUP-002 — Begin validation

**Requirement:** Firmware or its delivery tooling SHALL reject wrong targets, invalid geometry and unsupported packet sizes before programming.

**Verification:** Malformed begin matrix and boundary lengths; inspect flash before and after rejection.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `wrong-target`, `geometry-boundaries`, `unsupported-size`, `no-write-on-rejection`

## VUP-003 — Packing

**Requirement:** Firmware or its delivery tooling SHALL use canonical seven-bit MIDI packing and encoded-payload additive checksums.

**Verification:** All input byte values and all partial groups; injected mask/checksum faults must fail.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `all-byte-values`, `all-partial-groups`, `mask-errors`, `checksum-errors`

## VUP-004 — Transfer order

**Requirement:** Firmware or its delivery tooling SHALL acknowledge each accepted packet and reject invalid order without committing unrelated data.

**Verification:** Executed transcript validator plus candidate receiver tests for duplicates, gaps and NAK behavior.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `complete-ordered-transfer`, `duplicate`, `gap`, `nak`, `unrelated-data-guards`

## VUP-005 — Completion

**Requirement:** Firmware or its delivery tooling SHALL distinguish packet receipt, programming completion and successful restart.

**Verification:** Complete update in emulation and hardware; verify display completion and post-reboot identity.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `final-packet-ack`, `programming-completion`, `installed-bytes`, `cold-version`, `normal-boot`

## VUP-006 — Interrupted transfer

**Requirement:** Firmware or its delivery tooling SHALL define behavior for host disconnect or timeout at each transfer phase.

**Verification:** Stop host traffic at each boundary; verify declared response and retained data without blind retry.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `each-disconnect-phase`, `each-timeout-phase`, `retained-data`, `no-blind-retry`

## VUP-007 — Future updates

**Requirement:** Firmware or its delivery tooling SHALL retain a working documented method to install a subsequent firmware image.

**Verification:** Candidate-to-candidate or candidate-to-approved-restore update, then cold boot.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `subsequent-update`, `cold-boot`, `normal-operation`

## VUP-008 — Flash power loss scope

**Requirement:** Firmware or its delivery tooling SHALL document that power loss during internal-flash programming is not guaranteed recoverable under this profile.

**Verification:** Documentation check; deliberate physical power cuts during internal flash programming are excluded.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** review, hardware; emulator also accepted in software

**Required cases:** `document-unrecoverable-power-loss`, `exclude-physical-programming-power-cuts`

## BACKUP-001 — Coverage

**Requirement:** Firmware or its delivery tooling SHALL list every included user-data category and explicitly list exclusions.

**Verification:** Check 64 saved project slots, current edit buffer, pattern presence, controls, scales and global settings.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** review, hardware; emulator also accepted in software

**Required cases:** `included-categories`, `explicit-exclusions`, `scope-and-empty-slots`

## BACKUP-002 — Project sessions

**Requirement:** Firmware or its delivery tooling SHALL transfer project headers and present patterns in a bounded session and finalize it.

**Verification:** Normal, empty, partial and interrupted project sessions; no incomplete archive may be labeled complete.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `normal-session`, `empty-session`, `partial-session`, `interrupted-session`, `finalize-ack`

## BACKUP-003 — Integrity

**Requirement:** Firmware or its delivery tooling SHALL bind each backup record to its type, slot, length, canonical encoding and digest.

**Verification:** Wrong slot, wrong type, altered payload, duplicate/missing pattern and oversized archive tests.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `record-type-slot-length`, `canonical-packing`, `digest`, `missing-duplicate-pattern`, `oversized-archive`

## BACKUP-004 — Restoration

**Requirement:** Firmware or its delivery tooling SHALL restore included data and verify it through independent readback and normal restart.

**Verification:** Compare all included logical bytes after write, restart and export; preserve intentionally excluded slots.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `all-included-data`, `independent-readback`, `normal-shutdown`, `cold-readback`, `excluded-slot-guards`

## ROBUST-001 — Boundary coverage

**Requirement:** Firmware or its delivery tooling SHALL exercise valid extremes and invalid adjacent values for each public input field.

**Verification:** Versioned field inventory, partitioned tests and deterministic fuzz seeds.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `field-inventory`, `valid-extremes`, `invalid-adjacent`, `seeded-fuzz`

## ROBUST-002 — Resource limits

**Requirement:** Firmware or its delivery tooling SHALL remain within declared stack, RAM, queues and storage budgets.

**Verification:** High water marks under maximal simultaneous supported workload; detect guard violations.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `stack-high-water`, `ram-budget`, `queue-budget`, `storage-budget`, `concurrent-maximum`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## ROBUST-003 — Long run

**Requirement:** Firmware or its delivery tooling SHALL meet declared sustained-operation behavior without accumulating corrupt state.

**Verification:** Record duration, traffic and state checks; reproduce with instruction/event replay where applicable.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** hardware; emulator also accepted in software

**Required cases:** `declared-duration`, `declared-traffic`, `periodic-state-checks`, `replay-seeds`

**Quantitative bounds:** A candidate limit and matching measurements, including uncertainty, are required. Every declared metric must be present.

## ROBUST-004 — Evidence identity

**Requirement:** Firmware or its delivery tooling SHALL bind every result to the exact candidate, tool versions, model profile and procedure.

**Verification:** Reject stale hashes, unknown IDs and missing evidence; never convert not-run into pass.

**Profiles:** hardware, software, korg-compatible, application-only

**Evidence kinds:** review, hardware; emulator also accepted in software

**Required cases:** `candidate-hash`, `tool-identities`, `environment-profile`, `procedure-revision`, `missing-stale-rejection`

## COMPAT-001 — Project layout

**Requirement:** Firmware or its delivery tooling SHALL preserve the documented project and pattern data layouts.

**Verification:** Round-trip all documented fields and reserved bytes; reference fixtures supplied locally only.

**Profiles:** korg-compatible

**Evidence kinds:** hardware

**Required cases:** `documented-fields`, `reserved-bytes`, `project-round-trip`, `pattern-round-trip`

## COMPAT-002 — Global and controls

**Requirement:** Firmware or its delivery tooling SHALL preserve documented global/control/scale serialization and supported settings.

**Verification:** Boundary matrix for every field and slot.

**Profiles:** korg-compatible

**Evidence kinds:** hardware

**Required cases:** `global-fields`, `control-fields-slots`, `scale-fields-slots`, `boundaries`

## COMPAT-003 — Sequencing

**Requirement:** Firmware or its delivery tooling SHALL match the declared Korg-compatible note, gate, modulation and probability semantics.

**Verification:** Independent expected MIDI/CV event traces for every claimed feature; random seeds fixed.

**Profiles:** korg-compatible

**Evidence kinds:** hardware

**Required cases:** `notes`, `gates`, `modulation`, `probability`, `fixed-seeds`, `expected-event-traces`

## COMPAT-004 — Intentional deviations

**Requirement:** Firmware or its delivery tooling SHALL declare each intentional compatibility deviation and its rationale.

**Verification:** Expected-failure entries may not count as passes for a strict compatibility claim.

**Profiles:** korg-compatible

**Evidence kinds:** review, hardware

**Required cases:** `declared-deviations`, `rationale`, `no-expected-failure-passes`

## RECOVERY-001 — Preserved recovery image

**Requirement:** Firmware or its delivery tooling SHALL preserve the entire first 64 KiB and all reviewed recovery code/data dependencies byte-for-byte against an explicitly approved baseline; identify the actual installed baseline by content, not a version string.

**Verification:** Execute protected-image comparison with a reviewer-pinned policy; independently review dependency closure, including SPI-loaded code/data, vectors, startup, panel entry, USB, installer and RAM writer. Verify baseline content and approved installer/observer artifacts.

**Profiles:** application-only

**Evidence kinds:** review, hardware

**Required cases:** `installed-baseline-content`, `reset-and-vectors`, `startup-and-recovery-chord`, `usb-and-updater`, `ram-writer`, `external-dependency-closure`, `approved-installer-and-observer`

## RECOVERY-002 — No recovery mutation

**Requirement:** Firmware or its delivery tooling SHALL perform no erase or program attempts on protected recovery, reserved or calibration regions during installation or application execution, even if an operation would restore identical bytes or be rejected by hardware.

**Verification:** Validate complete installation and runtime mutation captures. Review capture coverage of flash aliases, CPU, DMA, SPI commands and every programming path; before/after equality alone does not pass.

**Profiles:** application-only

**Evidence kinds:** hardware, emulator

**Required cases:** `zero-protected-install-writes`, `zero-protected-runtime-writes`, `erase-before-rewrite-rejected`, `all-aliases-and-dma-observed`, `capture-start-to-completion`

## RECOVERY-003 — No irreversible configuration

**Requirement:** Firmware or its delivery tooling SHALL never unlock or program option bytes, write OTP, change protection/boot/debug configuration, issue mass/chip erase or alter persistent flash status/security configuration in this profile.

**Verification:** Reject every prohibited or unclassified persistent mutation attempt in both captures, and review instrumentation coverage of irreversible controls. Missing register/command modeling is rejection, not an ignored event.

**Profiles:** application-only

**Evidence kinds:** hardware, emulator

**Required cases:** `option-unlock-and-write`, `otp`, `protection-and-rdp`, `boot-and-debug`, `chip-and-mass-erase`, `persistent-status-security`, `unknown-operation-rejection`

## RECOVERY-004 — Persistent write allowlist

**Requirement:** Firmware or its delivery tooling SHALL restrict candidate changes and every persistent mutation to reviewed phase-specific application/user-data ranges, preserving all other storage; respect approved page and erase geometry.

**Verification:** Validate non-overlapping policy ranges, protected-region exclusion, candidate destination changes, exact event ranges and geometry. A mutation crossing an allowlist boundary fails even if its start address is permitted. Installation traces must cover every changed payload byte.

**Profiles:** application-only

**Evidence kinds:** review, hardware, emulator

**Required cases:** `reviewed-storage-ownership`, `installation-ranges`, `runtime-ranges`, `reserved-and-calibration-guards`, `cross-boundary-rejection`, `page-and-erase-geometry`, `changed-byte-program-coverage`

## RECOVERY-005 — Recovery before application

**Requirement:** Firmware or its delivery tooling SHALL enter trusted recovery from the physical startup chord before executing custom application code, with the application absent, corrupt or immediately faulting; keep the recovery transport and approved restore operation usable.

**Verification:** Cold boot using modeled or physical panel inputs, record execution ordering and restore traffic. Include a valid-checksum bad application, invalid vectors and corrupt application metadata; do not patch runtime state to force update mode.

**Profiles:** application-only

**Evidence kinds:** hardware, emulator

**Required cases:** `chord-before-application`, `application-absent`, `application-corrupt`, `application-immediate-fault`, `valid-checksum-bad-application`, `invalid-application-vectors`, `corrupt-application-metadata`, `approved-restore`

## RECOVERY-006 — Recovery after interrupted installation

**Requirement:** Firmware or its delivery tooling SHALL preserve a usable trusted recovery path after interruption at every installation phase, without relying on the custom application or previously erased recovery dependencies.

**Verification:** Use software fault injection before/after every persistent mutation and model partial erase/program, commit metadata and transport interruption. Prove recovery entry and a subsequent approved restore for each resulting state. Deliberate physical programming power cuts remain excluded; physical guarantees require separate evidence and enforcement.

**Profiles:** application-only

**Evidence kinds:** hardware, emulator

**Required cases:** `before-first-mutation`, `each-erase-boundary`, `each-program-boundary`, `partial-erase-and-program`, `commit-metadata`, `disconnect-and-timeout`, `cold-recovery-each-state`, `approved-restore-each-state`, `fault-model-and-coverage`
