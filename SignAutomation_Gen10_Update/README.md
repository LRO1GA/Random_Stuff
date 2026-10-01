# Tesla D4 Release Tool (One Bank)

Interactive Python CLI that automates CRC patching and signing of Tesla D4 software
releases for two project types: ESP and IB2/Rivian.

Script: [Tesla_D4_release_tool_OneBank_FileList.py](Tesla_D4_release_tool_OneBank_FileList.py)

## Requirements

- Windows, Python 3 (stdlib only: no extra packages to install).
- Hexview available at the path in the `hexview` environment variable, or `C:\Hexview` by
  default. Required for project 1 only (CRC patching, export, merge).
- SignX installed at `C:\Program Files (x86)\Robert Bosch GmbH\SignX\signx.exe`.
- A smart card with signing credentials (PIN prompted at runtime, hidden input).

## Running

```powershell
python Tesla_D4_release_tool_OneBank_FileList.py
```

The script is fully interactive: native Windows "Open File" dialogs are used to pick the
`.appl.zip` container (or loose `PRJ_HEX` files), and the console prompts for the
remaining choices described below.

## Prompts / Workflow

1. **Select project**: `1` = ESP, `2` = Tesla IB2/Rivian.
2. **Select source**: `1` = prepare from an ApplContainer (`.appl.zip`) only, or
   `2` = prepare from a `PRJ_HEX` file exported from PMSE.
3. **Smart card PIN**: numeric input, hidden.
4. **Bootloader (HexPart) selection** *(project 2 only)*: containers can bundle several
   unrelated `PRJ_HexPart_*.hex` variants (bootloader, boot manager, etc.) and the correct
   one can't be reliably guessed from the filename. The script lists every
   `PRJ_HexPart_*.hex` file found and lets the operator pick one, or choose `0` if none of
   them belong to this release.
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

This chip family has no CRC address to patch (the linker map contains no
`.crc32_fsw`/`.crc32_cal` markers), so the flow is simpler:

1. Sign the operator-selected bootloader (if any), the hex file, the code block, and each
   calibration block as-is — no CRC patching.
2. Strip the signed code block's trailing ECC/reserve section: find the first
   `:020000040FF0` extended linear address record and truncate there, appending a clean
   `:00000001FF` EOF record.
3. Compute an MD5 hash of every signed file and write `signed\crcList.xlsx` (`File`, `MD5`
   columns) in place of a CRC list.

## Output

All signed files (`*_S.hex`) plus the CRC/MD5 report are copied into a `signed` folder
next to the source container/file. The working `temp` extraction folder is removed when
the script completes successfully.
