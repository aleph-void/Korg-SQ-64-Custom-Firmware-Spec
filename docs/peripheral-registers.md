# Peripheral register interface for firmware authors

Specification version 0.6.0 supplement. [Contracts](contracts.md) describe the
package, wire and panel formats; this page records the **register-level
software interface** a custom firmware needs in order to drive the board
model: the addresses, bit assignments and sequencing that supplied-image
execution has been observed to use. They follow STM32F7 peripheral layouts.

These are software interface facts exercised by the independent emulator's
board model. They carry the same caveat as the rest of the board contract:
**no physical register map, wiring or electrical behavior has been
independently verified**, and the exact MCU part remains an open release
blocker. Values are byte addresses; registers are 32-bit little-endian unless
stated.

## Clock and timing

The modeled core clock is 216 MHz; emulator virtual time converts cycles to
wall time at that rate. General-purpose timers count core cycles divided by
`PSC + 1` under reset RCC settings (RCC CFGR/DCKCFGR prescalers are modeled
at 0x40023808 / 0x4002388c for firmware that changes them).

| Timer base | IRQ |
| --- | --- |
| 0x40000000 | 28 |
| 0x40000400 | 29 |
| 0x40000800 | 30 |
| 0x40000c00 | 50 |
| 0x40001000 | 54 |
| 0x40001400 | 55 |
| 0x40011400 | 24 |

Offsets: +0x00 control (bit 0 enables), +0x0c interrupt enable (bit 0),
+0x10 status (bit 0 update flag, write 0 to clear), +0x24 count, +0x28
prescaler, +0x2c auto-reload. The vector table address resets to 0x00200000
(VTOR at 0xe000ed08); IRQ *n* dispatches through vector slot 16 + *n*, and
NVIC enable/pend/priority registers live at their architectural 0xe000e100
block addresses.

## GPIO

Ports are 0x400 apart from 0x40020000 (A), 0x40020400 (B), 0x40020800 (C).
Offsets: +0x00 mode (2 bits per pin; 01 = output), +0x10 input data, +0x14
output data, +0x18 bit set/reset (low halfword sets, high halfword resets).

| Pin | Role |
| --- | --- |
| PB0 | Panel polled-scan latch: falling edge samples the selected row, rising edge latches the next row select |
| PB4 | Sync jack detect input; high = unplugged |
| PB7 | Power hold output; releasing a previously asserted hold powers off |
| PB9 | External SPI flash chip select, active low |
| PB12 / PB15 / PC9 | Track A / B / C gate outputs; jack drivers invert, and the top-edge observer counts a pin only when configured as an output |
| PC13 | Power button input, active low |

## SPI blocks

Each modeled SPI exposes a status register (bit 1 transmit-ready, bit 9
receive-not-empty) and a data register. Every transmitted byte queues one
received byte; firmware must drain the receive side.

| Block | Status | Data | Role |
| --- | --- | --- | --- |
| Panel scan | 0x40013008 | 0x4001300c (byte writes) | Startup polled frames and DMA scan frames; serial clock divider in control bits 5:3 at 0x40013000 |
| Storage NOR | 0x40003808 | 0x4000380c (8/16-bit, MSB first) | External SPI flash, selected via PB9 |
| Display | 0x40003c08 | 0x40003c0c | Command bytes (recorded, not interpreted) and the DMA frame target |

The modeled NOR command set is exactly: 0x00 (no-op), 0x02 page program
(256-byte pages, AND semantics), 0x03 read, 0x0b fast read (one dummy byte),
0x04/0x06 write disable/enable, 0x05 status (bit 1 = write enabled), 0x20 4 KiB
erase, 0xd8 64 KiB erase, 0x9f JEDEC identity. Any other command byte is a
critical hazard. Write enable clears on deselect after program/erase.
Addresses are three bytes, big-endian.

## DMA controllers

DMA1 at 0x40026000, DMA2 at 0x40026400. Stream *n* registers sit at
`base + 0x10 + 0x18·n`: +0 control, +4 count, +8 peripheral address, +0xc
memory address. Control bits follow STM32: bit 0 enable, bits 7:6 direction
(01 = memory-to-peripheral), bit 8 circular, bit 10 memory increment, bits
14:13 memory size. Status/clear registers are at +0x00/+0x08 (streams 0–3)
and +0x04/+0x0c (streams 4–7). Writing the count while a stream is disabled
sets its reload value, restored when the stream is re-enabled.

| Transfer | Controller / stream | Requirements |
| --- | --- | --- |
| Panel scan TX | DMA2 stream 3 | Peripheral 0x4001300c, circular, byte-size, memory-to-peripheral, count 128 (sixteen 8-byte frames, processed 64 bytes per half) |
| Panel scan RX | DMA2 stream 2 | Peripheral 0x4001300c, circular, byte-size, peripheral-to-memory, same count |
| Display frame | DMA1 stream 5 | Peripheral 0x40003c0c, memory-to-peripheral, 16-bit memory size, memory increment, count 4096 halfwords |
| CV slots | DMA2 stream 6 | Control exactly 0x06005541 under mask 0x0e047fc1 (enabled, circular, incrementing, word sizes), count 8, peripheral 0x40015c40, word-aligned SRAM source |

Panel-scan half/full-transfer flags are DMA2 status bits 26/27 (IRQ 59 when
the matching interrupt-enable control bits are set); pacing follows the panel
SPI clock divider. The display stream raises DMA1 stream-5 completion and
clears its enable bit when the frame has been consumed. The CV observer reads
the eight-word buffer only while SAI1 block B's configuration register at
0x40015c24 matches 0x300c0 under mask 0x300e3; slot coding is in
[contracts](contracts.md).

## MIDI transports

DIN MIDI is a UART at 0x40004800 (a second modeled UART sits at 0x40004400):
+0x00 status (bit 5 receive-ready), +0x04 data (reads pop the receive queue;
writes transmit), +0x0c control bit 5 enables the receive interrupt (IRQ 39,
and 38 for the second UART).

USB device is an OTG-FS controller at 0x50000000, word access only. Offsets:
0x008 AHB config (bit 0 unmasks IRQ 67), 0x014 interrupt status (write-one-
to-clear; bit 3 SOF, bit 4 receive-level, bits 12/13 reset/enumeration-done),
0x018 interrupt mask, 0x020 receive status pop (`endpoint | byteCount << 4 |
kind << 17`; kinds: 2 OUT data, 3 OUT complete, 4 setup complete, 6 setup
data), 0x804 device control (bit 1 soft disconnect; clear it to present the
device). IN endpoint *n*: control 0x900+0x20·n (bit 31 arms a zero-length
transfer; bit 15 marks the endpoint active for host polling), transfer size
0x910+0x20·n. OUT endpoint control is 0xb00+0x20·n (bit 15 must be set to
accept traffic). FIFOs are at 0x1000+0x1000·n: reads at +0x1000 pop received
words, writes push transmit words; an IN transfer completes when the bytes
written reach the programmed size. After reset recovery the host model issues
SET_ADDRESS, GET_DESCRIPTOR(configuration) and SET_CONFIGURATION; the
configuration descriptor must contain a standard bulk OUT endpoint
descriptor, which selects the MIDI OUT endpoint number. Cable routing and
packet forms are in [contracts](contracts.md).

## Internal flash programming

Programming is modeled only through the 0x08000000 alias: unlock the control
register at 0x40023c10 by writing 0x45670123 then 0xcdef89ab to the key
register at 0x40023c04; sector erase writes `0x10002 | sector << 3` (sectors
0–3 only, 16 KiB each); word programming requires control bit 0 and aligned
32-bit writes whose value only clears bits. Writes to 0x40023c08 or
0x40023c14..0x40023c1f are system/option hazards (CRITICAL-002), and any
erase arming or alias write outside a host-granted installation context is a
critical hazard, as is touching installed SPI below 0x30000 — see
[application-only](application-only.md). A self-updater must execute its
erase/program sequence from SRAM: erasing sector 0 destroys the code,
vectors and literal pools it would otherwise be running from.

## Reference firmware

An original, buildable reference that exercises this whole interface —
startup chords, panel DMA scan, display, CV/gates/triggers, DIN and USB MIDI,
a RAM-resident VUP self-updater and SPI settings persistence — is maintained
alongside the emulator tooling (the `custom-firmare/euclidean` sibling
project), with emulator-backed behavioral tests.
