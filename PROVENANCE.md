# Provenance

This specification describes interface facts and verification obligations. Its validators and synthetic fixtures are original host code. No original Korg firmware, decompiled functions, reconstructed firmware source, factory assets, calibration bytes or user data are included.

Format/protocol knowledge comes from published SQ-64 documentation and observations from a private reference implementation. That access is disclosed; this project does not claim a formal clean-room process. Functional compatibility does not require copying the reference code. Public requirement IDs and test records must remain independent of private symbol addresses or vendor implementation bodies.

The 0.2.0 model contract records interface facts also described by the sibling emulator, including panel positions, scan framing, power signals and sampled output routing. These facts have bounded supplied-image execution evidence, not independent electrical certification. The Python archive validator was authored here against the public interchange contract without importing the sibling JavaScript codec or validator. Test data is generated from original synthetic patterns; literal packing vectors provide expectations independent of round trips. All tests, declarations and successful synthetic reports exercise the tooling, not physical SQ-64 firmware conformance.

Primary references:
- Korg SQ-64 product and specifications: https://www.korg.com/us/products/dj/sq_64/
- Korg SQ-64 support downloads, including MIDI implementation: https://www.korg.com/us/support/download/product/0/872/
- ST PM0253 Cortex-M7 programming manual and STM32F7 peripheral reference manuals. Exact board part/pin assignments remain open evidence items.
- Web MIDI: https://www.w3.org/TR/webmidi/

Original source, documentation and tests in this project use the MIT license. Korg and SQ-64 identify the compatibility target; this project is independent and not endorsed by Korg.
