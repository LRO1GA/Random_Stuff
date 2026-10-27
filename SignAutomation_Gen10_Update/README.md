# Tesla D4 Release Tool (One Bank)

Interactive Python CLI that automates CRC patching and signing of Tesla D4 software
releases for two project types: ESP and IB2/Rivian.

Script: [Gen10_Sign_release_tool_CLI.py](Gen10_Sign_release_tool_CLI.py)

## Requirements

- Windows, Python 3 (stdlib only: no extra packages to install).
- Hexview available at the path in the `hexview` environment variable, or `C:\Hexview` by
  default. Required for project 1 and the BLU Hexfile option only (CRC patching, export,
  merge).
- SignX installed at `C:\Program Files (x86)\Robert Bosch GmbH\SignX\signx.exe`.
- A smart card with signing credentials (PIN prompted at runtime, hidden input).

## Running

```powershell
python Gen10_Sign_release_tool_CLI.py
```

The script is fully interactive: native Windows "Open File" dialogs are used to pick the
`.appl.zip` container (or loose `PRJ_HEX`/BLU hex files), and the console prompts for the
remaining choices described below.

## Prompts / Workflow

1. **Select project**: `1` = ESP, `2` = Tesla IB2/Rivian.
2. **Select source**: `1` = prepare from an ApplContainer (`.appl.zip`) only, `2` =
   prepare from a `PRJ_HEX` file exported from PMSE, or `3` = process a standalone BLU
   Hexfile (see [BLU Hexfile option](#blu-hexfile-option) below; this choice skips the
   project selection entirely).
3. **Smart card PIN**: numeric input, hidden.
4. **IB2 variant selection** *(project 2 only)*: `1` = Legacy (no bootloader HexPart is
   part of the release, skipped automatically) or `2` = Europium, in which case the
   script automatically locates the bootloader by finding the `PRJ_HexPart_*.hex` file
   whose name contains `EverestBldr` or `HighlandBldr` — no manual file picking required.
5. **ESP-only prompts**: whether to use the `OEMBLDR` map file for boot patch addresses,
   plus (if source is `PRJ_HEX`) variant name(s) for each calibration block.

## Project 1 (ESP) behavior

Unchanged from the original flow:

1. Patch CRCs into the hex file and each calibration block (via Hexview).
2. Sign the bootloader (HexPart), patched hex file, and calibration blocks in one SignX
   batch call.
3. Patch the signed bootloader's CRC, export its Block 0, and merge it into the signed hex
   file.
4. Export the final code block from the merged/signed hex file.
5. Read back each CRC (via Hexview) and write `signed\crcList.csv` (`fileName,crc`).

## Project 2 (IB2/Rivian) behavior

This chip family has no CRC address to patch via Hexview — the CRC is a value baked into
the image at build time (a "App Info CRC" read through a pointer-chasing structure
embedded in the firmware, reverse-engineered from the official `FinalizeRelease_V12.xlsm`
documentation macro), so the flow is simpler:

1. Sign the bootloader (if any, selected automatically per the Legacy/Europium choice
   above), the hex file, the code block, and each calibration block as-is — no CRC
   patching.
2. Strip the trailing ECC/reserve section from every signed file that carries one (hex
   file, code block, and bootloader HexPart): find the first `:020000040FF0` extended
   linear address record and truncate there, appending a clean `:00000001FF` EOF record.
3. Read the real CRC directly out of each signed file (where applicable) and compute an
   MD5 hash of every signed file, then write `signed\crcList.xlsx` (`File`, `CRC`, `MD5`
   columns).

## BLU Hexfile option

Selecting `3` at the source prompt processes a single standalone hexfile independently of
the ApplContainer/`PRJ_HEX` flows above:

1. Pick the BLU hexfile, then its matching `.map` file (used to find the `.crc32_fsw`
   code-block CRC address, same as ESP project preparation).
2. Sign the hexfile with SignX.
3. Patch the CRC into the signed hexfile via Hexview (sign happens before the CRC patch,
   unlike the ESP project1 flow where the CRC is patched before signing).
4. Rename the result, replacing `HexPart` with `BLUPart`, and copy it into a `signed`
   folder next to the source file.

## Output

All signed files (`*_S.hex`) plus the CRC/MD5 report are copied into a `signed` folder
next to the source container/file. The working `temp` extraction folder is removed when
the script completes successfully.

