from __future__ import annotations

import argparse
import hashlib
import html
import getpass
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SIGNX = Path(r"C:\Program Files (x86)\Robert Bosch GmbH\SignX\SignX_3.exe")
DEFAULT_WORKBOOK = Path(r"C:\Users\LRO1GA\Documents\CSW\1_Signed_HexFiles\FinalizeRelease_V12.xlsm")
EXTERNAL_TOOL_ARTIFACT_PATTERNS = (
    "ecc470.log",
    "log*.txt",
    "trace*.txt",
    "SignXLog*.log",
)


@dataclass(frozen=True)
class StageDirs:
    root: Path
    extracted: Path
    unsigned: Path
    signed: Path
    logs: Path
    signed_bl: Path


@dataclass(frozen=True)
class ReportRow:
    filename: str
    crc: str
    md5: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare Gen9 hex release files by extracting, signing, processing with Excel, and zipping the result.")
    parser.add_argument(
        "input_zip", type=Path, 
        help="Input .appl.zip file containing PRJ_*.hex files.")
    parser.add_argument(
        "--release-name", default=None,
        help="Name for the final folder and zip. Defaults to BL<V>_<BB> parsed from the input .appl.zip name.",)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT_DIR / "output", 
        help="Directory where the final zip will be created.")
    parser.add_argument(
        "--work-dir", type=Path, default=None, 
        help="Working directory. Defaults to work/<release-name>.")
    parser.add_argument(
        "--signx", type=Path, default=DEFAULT_SIGNX, 
        help="Path to SignX_3.exe.")
    parser.add_argument(
        "--workbook", type=Path, default=DEFAULT_WORKBOOK, 
        help="Path to FinalizeRelease workbook.")
    parser.add_argument(
        "--processing-mode", choices=("embedded", "excel", "manual"), default="embedded",
        help="How to perform ECC removal and release report generation. Default: embedded Python implementation.",)
    parser.add_argument(
        "--excel-macro", default="ManualRun", 
        help="Excel macro name used when --processing-mode excel is selected.")
    parser.add_argument(
        "--pin-signx", default=None, 
        help="Optional environment variable containing the smartcard PIN.")
    parser.add_argument(
        "--force", action="store_true", 
        help="Delete an existing work directory before running.")
    parser.add_argument(
        "--keep-work", action="store_true", 
        help="Keep the working directory after the final zip is created.")
    parser.add_argument(
        "--dry-run", action="store_true", 
        help="Create folders and show actions without calling SignX or Excel.")
    return parser.parse_args()


def make_stage_dirs(work_dir: Path, force: bool) -> StageDirs:
    if work_dir.exists():
        if not force:
            raise FileExistsError(f"Work directory already exists: {work_dir}. Use --force to replace it.")
        shutil.rmtree(work_dir)

    dirs = StageDirs(
        root=work_dir,
        extracted=work_dir / "_Extracted",
        unsigned=work_dir / "Unsigned",
        signed=work_dir / "Signed",
        logs=work_dir / "Logs",
        signed_bl=work_dir / "Signed_BL",
    )
    for folder in (dirs.extracted, dirs.unsigned, dirs.signed, dirs.logs, dirs.signed_bl):
        folder.mkdir(parents=True, exist_ok=True)
    return dirs


def extract_prj_hex_files(input_zip: Path, dirs: StageDirs) -> list[Path]:
    extracted_files: list[Path] = []
    with zipfile.ZipFile(input_zip, "r") as archive:
        for entry in archive.infolist():
            entry_name = Path(entry.filename).name
            if entry.is_dir() or not entry_name.lower().endswith(".hex") or not entry_name.startswith("PRJ_"):
                continue

            destination = dirs.extracted / entry_name
            with archive.open(entry) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target)
            extracted_files.append(destination)

    if not extracted_files:
        raise RuntimeError(f"No top-level PRJ_*.hex files were found in {input_zip}")
    return sorted(extracted_files, key=lambda path: path.name.lower())


def is_boot_block_1(path: Path) -> bool:
    return path.name.startswith("PRJ_BootBlock1_")


def is_prj_hex_file(path: Path) -> bool:
    return path.name.startswith("PRJ_HexFile_")


def is_in_manualrun_list(filename: str) -> bool:
    upper_name = filename.upper()
    return (
        upper_name.startswith("PRJ_CALBLOCK")
        or upper_name.startswith("PRJ_BOOTBLOCK2")
        or upper_name.startswith("PRJ_CODEBLOCK")
        or "LN000" in upper_name
        or upper_name.startswith("PRJ_HEXPART")
    )


def copy_unsigned_inputs(extracted_files: list[Path], unsigned_dir: Path) -> list[Path]:
    unsigned_files: list[Path] = []
    for source in extracted_files:
        if is_boot_block_1(source):
            continue
        destination = unsigned_dir / source.name
        shutil.copy2(source, destination)
        unsigned_files.append(destination)
    return unsigned_files


def signed_name(input_file: Path) -> str:
    return input_file.with_suffix("").name + "_S.hex"


def processed_name(signed_file: Path) -> str:
    if not is_in_manualrun_list(signed_file.name):
        return signed_file.name
    return signed_file.with_suffix("").name + "_withoutECC.hex"


def mid_vb(text: str, start: int, length: int | None = None) -> str:
    start_index = max(start - 1, 0)
    if length is None:
        return text[start_index:]
    return text[start_index : start_index + length]


def instr_vb(text: str, needle: str, start: int = 1) -> int:
    index = text.find(needle, max(start - 1, 0))
    return 0 if index < 0 else index + 1


def mot_to_intel(value: str) -> str:
    return "".join(value[index - 2 : index] for index in range(len(value), 0, -2))


def read_hex_text(path: Path) -> str:
    with path.open("r", encoding="ascii", errors="ignore", newline="") as handle:
        return handle.read()


def get_generation(hex_text: str) -> int:
    generation = 0
    first_20 = instr_vb(hex_text, ":20")
    if instr_vb(hex_text, ":020000040000FA") == 1 and 0 < first_20 < 20:
        gen_id = instr_vb(hex_text, ":20100000") + 2 + 9
        generation = 1
    else:
        gen_id = 16 + 11 + 2

    marker = mid_vb(hex_text, gen_id, 6)
    if marker in ("52454C", "53544D"):
        generation += 930

    first_10_after_9 = instr_vb(hex_text, ":10", 9)
    if 0 < first_10_after_9 < 20:
        block_pos = instr_vb(hex_text, ":", 2 * (11 + 2 * 16))
        device_id = mid_vb(hex_text, block_pos + 9 + 24, 4)
        if device_id == "804C":
            generation = 92
        if device_id == "802A":
            generation = 91
    return generation


def read_at_address(hex_text: str, address: str, length: int, generation: int) -> str:
    address = address.zfill(8)
    if len(address) != 8:
        raise ValueError(f"Address {address} is not valid; expected 8 hex digits")

    address_section = address[:4]
    line_prefix = ":20" if generation in (930, 931) else ":10"
    divisor = 32 if generation in (930, 931) else 16

    address_offset = address[4:]
    aligned_address = (int(address_offset, 16) // divisor) * divisor
    address_segment = f"{aligned_address:04X}"
    offset = int(address_offset, 16) - int(address_segment, 16)

    sector_start = instr_vb(hex_text, ":02000004" + address_section) + 9
    value_pointer = instr_vb(hex_text, line_prefix + address_segment, sector_start) + 9 + offset * 2
    if value_pointer <= 9:
        raise ValueError(f"Address {address} was not found in hex file")

    output = ""
    for _ in range(length):
        if ":" in mid_vb(hex_text, value_pointer, 5):
            value_pointer += 13
        output += mid_vb(hex_text, value_pointer, 2)
        value_pointer += 2

    if generation in (930, 931):
        output = mot_to_intel(output)
    return output


def get_crc(hex_text: str, generation: int) -> str:
    if generation in (930, 931):
        if generation == 931:
            checksum_ref = mid_vb(hex_text, instr_vb(hex_text, ":201000") + 7 + 2 + 2 * 0x10, 8)
        else:
            checksum_ref = mid_vb(hex_text, instr_vb(hex_text, ":20") + 9 + 0x10 * 2, 8)
        checksum_ref = mot_to_intel(checksum_ref)
        checksum_segmentation = read_at_address(hex_text, f"{int(checksum_ref, 16) + 2:08X}", 1, 3)
        checksum_ref = f"{int(checksum_ref, 16) + 0x10 - 8:08X}"
        crc_value = read_at_address(hex_text, checksum_ref, 8, 3)
        if int(checksum_segmentation, 16) == 1:
            crc_2 = int(crc_value[:8], 16)
            crc_1 = int(crc_value[-8:], 16)
            crc_value = f"{crc_1 ^ crc_2:X}"
        else:
            crc_value = mid_vb(crc_value, 9, 8)
    elif generation in (91, 92):
        checksum_ref = mid_vb(hex_text, instr_vb(hex_text, ":", 2 * (11 + 3 * 16)) + 9 + 8, 8)
        checksum_ref = f"{int(checksum_ref, 16) + 8:08X}"
        crc_value = read_at_address(hex_text, checksum_ref, 8, 0)
    else:
        return ""
    return crc_value[-8:].zfill(8).upper()


def remove_ecc(source: Path, destination: Path) -> None:
    hex_text = read_hex_text(source)
    start_of_ecc = instr_vb(hex_text, ":20")
    if start_of_ecc > 0 and mid_vb(hex_text, start_of_ecc - 16, 3) == ":02":
        output_text = mid_vb(hex_text, 1, start_of_ecc - 16) + "00000001FF"
        with destination.open("w", encoding="ascii", newline="") as handle:
            handle.write(output_text + "\r\n")
        return
    raise RuntimeError(f"Could not remove ECC from {source.name}; expected extended address record before first :20 record")


def process_signed_files_embedded(signed_files: list[Path], extracted_files: list[Path], dirs: StageDirs) -> list[ReportRow]:
    rows: list[ReportRow] = []

    for source in extracted_files:
        if is_boot_block_1(source):
            destination = dirs.signed_bl / source.name
            shutil.copy2(source, destination)
            rows.append(ReportRow(destination.name, "", ""))

    for signed_file in signed_files:
        hex_text = read_hex_text(signed_file)
        generation = get_generation(hex_text)
        include_in_checks = "_S" in signed_file.name and is_in_manualrun_list(signed_file.name)

        if include_in_checks and generation in (91, 92):
            destination = dirs.signed_bl / processed_name(signed_file)
            remove_ecc(signed_file, destination)
            report_text = read_hex_text(destination)
            report_generation = get_generation(report_text)
        else:
            destination = dirs.signed_bl / signed_file.name
            shutil.copy2(signed_file, destination)
            report_text = hex_text
            report_generation = generation

        crc_value = get_crc(report_text, report_generation) if include_in_checks else ""
        md5_value = hashlib.md5(destination.read_bytes()).hexdigest() if include_in_checks else ""
        rows.append(ReportRow(destination.name, f"0x{crc_value}" if crc_value else "", f"0x{md5_value}" if md5_value else ""))

    return rows


def write_release_report(report_path: Path, rows: list[ReportRow]) -> None:
    sheet_rows = [["File", "CRC", "MD5"]] + [[row.filename, row.crc, row.md5] for row in rows]

    def cell_ref(row_index: int, column_index: int) -> str:
        return f"{chr(ord('A') + column_index)}{row_index}"

    row_xml = []
    for row_index, values in enumerate(sheet_rows, start=1):
        cells = []
        for column_index, value in enumerate(values):
            escaped = html.escape(value)
            cells.append(f'<c r="{cell_ref(row_index, column_index)}" t="inlineStr"><is><t>{escaped}</t></is></c>')
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData></worksheet>'
    )
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="Deliveries" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )

    with zipfile.ZipFile(report_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", workbook_xml)
        archive.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def sign_files(signx: Path, unsigned_files: list[Path], pin: str, dirs: StageDirs, dry_run: bool) -> list[Path]:
    signed_files = [unsigned_file.with_name(signed_name(unsigned_file)) for unsigned_file in unsigned_files]
    file_list_path = dirs.root / "sign_file_list.txt"
    log_file = dirs.logs / "SignX_batch.log"
    command = [str(signx), "-l", str(file_list_path), "-s", "-pw", pin]

    file_list_path.write_text("".join(f"{unsigned_file}\n" for unsigned_file in unsigned_files), encoding="ascii")
    print(f"Signing {len(unsigned_files)} files in one SignX batch")

    if dry_run:
        log_file.write_text("DRY RUN: " + subprocess.list2cmdline(command[:-1] + ["<PIN>"]) + os.linesep, encoding="utf-8")
        return signed_files

    completed = subprocess.run(command, text=True, capture_output=True)
    log_text = (completed.stdout + completed.stderr).replace(pin, "<PIN>")
    log_file.write_text(log_text, encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        raise RuntimeError(f"SignX batch signing failed. See log: {log_file}")

    missing_files = [signed_file for signed_file in signed_files if not signed_file.exists()]
    if missing_files:
        missing_names = ", ".join(path.name for path in missing_files)
        raise RuntimeError(f"SignX completed but did not create expected signed files: {missing_names}")

    for unsigned_file, signed_file in zip(unsigned_files, signed_files):
        if not is_prj_hex_file(unsigned_file):
            shutil.copy2(signed_file, dirs.signed / signed_file.name)
    return signed_files


def seed_signed_bl_for_excel(extracted_files: list[Path], signed_files: list[Path], dirs: StageDirs, dry_run: bool) -> None:
    for source in extracted_files:
        if is_boot_block_1(source):
            shutil.copy2(source, dirs.signed_bl / source.name)

    if dry_run:
        for signed_file in signed_files:
            placeholder = dirs.signed_bl / processed_name(signed_file)
            placeholder.write_text(f"DRY RUN placeholder for {signed_file.name}{os.linesep}", encoding="utf-8")
        return

    for signed_file in signed_files:
        if signed_file.exists():
            shutil.copy2(signed_file, dirs.signed_bl / signed_file.name)


def copy_workbook(workbook: Path, dirs: StageDirs) -> Path:
    release_id = None
    for hex_file in dirs.signed_bl.glob("PRJ_*.hex"):
        match = re.search(r"(BB\d+_V\d+)", hex_file.name)
        if match:
            release_id = match.group(1)
            break

    workbook_name = f"Bosch_Release_Documentation_{release_id}.xlsm" if release_id else "Bosch_Release_Documentation.xlsm"
    destination = dirs.signed_bl / workbook_name
    shutil.copy2(workbook, destination)
    return destination


def run_excel_macro(workbook: Path, macro_name: str) -> None:
    ps_command = rf"""
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
try {{
    $workbook = $excel.Workbooks.Open('{workbook}')
    $excel.Run('{macro_name}')
    $workbook.Save()
    $workbook.Close($true)
}} finally {{
    $excel.Quit()
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel) | Out-Null
}}
"""
    completed = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command], text=True)
    if completed.returncode != 0:
        raise RuntimeError(f"Excel macro failed: {macro_name}")


def handle_excel(workbook: Path, dirs: StageDirs, macro_name: str | None, manual: bool, dry_run: bool) -> Path:
    workbook_copy = copy_workbook(workbook, dirs)
    if dry_run:
        print(f"Dry run: workbook staged at {workbook_copy}")
        return workbook_copy

    if macro_name:
        print(f"Running Excel macro {macro_name}")
        run_excel_macro(workbook_copy, macro_name)
    elif manual:
        print(f"Workbook staged at {workbook_copy}")
        print("Run the workbook macro, save the workbook, then press Enter to continue.")
        os.startfile(workbook_copy)  # type: ignore[attr-defined]
        input()
    else:
        print("No Excel macro was provided. Signed_BL has been staged for macro processing.")
    return workbook_copy


def embedded_report_name(dirs: StageDirs) -> str:
    release_id = None
    for hex_file in dirs.signed_bl.glob("PRJ_*.hex"):
        match = re.search(r"(BB\d+_V\d+)", hex_file.name)
        if match:
            release_id = match.group(1)
            break
    return f"Bosch_Release_Documentation_{release_id}.xlsx" if release_id else "Bosch_Release_Documentation.xlsx"


def create_final_zip(signed_bl_dir: Path, output_dir: Path, release_name: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    final_zip = output_dir / f"{release_name}.zip"
    if final_zip.exists():
        final_zip.unlink()

    with zipfile.ZipFile(final_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(signed_bl_dir.iterdir(), key=lambda path: path.name.lower()):
            if file_path.is_file():
                archive.write(file_path, Path(release_name) / file_path.name)
    return final_zip


def cleanup_external_tool_artifacts(work_dir: Path) -> list[Path]:
    removed_files: list[Path] = []
    work_root = work_dir.resolve()
    search_dirs = {ROOT_DIR.resolve(), Path.cwd().resolve()}

    for search_dir in search_dirs:
        for pattern in EXTERNAL_TOOL_ARTIFACT_PATTERNS:
            for artifact in search_dir.glob(pattern):
                if not artifact.is_file():
                    continue
                try:
                    artifact.resolve().relative_to(work_root)
                    continue
                except ValueError:
                    pass
                artifact.unlink()
                removed_files.append(artifact)

    return removed_files


def derive_release_name(input_zip: Path) -> str:
    input_name = input_zip.name
    bb_match = re.search(r"_(BB\d+)_", input_name, flags=re.IGNORECASE)
    version_match = re.search(r"_V(\d{4}|\d{8})_", input_name, flags=re.IGNORECASE)
    if not bb_match or not version_match:
        raise ValueError(
            "Could not derive --release-name from input zip name. Expected tokens like _BB56480_ and _V1100_."
        )

    version_parts = []
    version_digits = version_match.group(1)
    for index in range(0, len(version_digits), 2):
        version_part = version_digits[index : index + 2]
        version_parts.append("0" if version_part == "00" else version_part.lstrip("0") or "0")

    return f"BL{'.'.join(version_parts)}_{bb_match.group(1).upper()}"


def get_pin(args: argparse.Namespace) -> str:
    if args.dry_run:
        return "0000"
    if args.pin_signx:
        pin = os.getenv(args.pin_signx)
        if not pin:
            raise RuntimeError(f"Environment variable {args.pin_signx} is not set.")
        return pin
    while True:
        pin = getpass.getpass("Please enter smart card PIN (input hidden): ")
        if pin.isdigit():
            return pin
        print("Invalid entry, PIN cannot contain letters.")


def validate_inputs(args: argparse.Namespace) -> None:
    if not args.input_zip.exists():
        raise FileNotFoundError(args.input_zip)
    if not args.input_zip.name.lower().endswith(".zip"):
        raise ValueError("Input file must be a zip file.")
    if "_ECB_" not in args.input_zip.name.upper():
        print("WARNING: The provided .appl.zip filename does not include _ECB_. Only ECB files are supported for signing for now.")
    if not args.dry_run and not args.signx.exists():
        raise FileNotFoundError(f"SignX_3 was not found: {args.signx}")
    if not args.workbook.exists():
        raise FileNotFoundError(f"Workbook was not found: {args.workbook}")


def main() -> int:
    args = parse_args()

    try:
        validate_inputs(args)
        if not args.release_name:
            args.release_name = derive_release_name(args.input_zip)
            print(f"Using derived release name: {args.release_name}")

        work_dir = args.work_dir or ROOT_DIR / "work" / args.release_name
        dirs = make_stage_dirs(work_dir, args.force)
        extracted_files = extract_prj_hex_files(args.input_zip, dirs)
        unsigned_files = copy_unsigned_inputs(extracted_files, dirs.unsigned)
        print(f"Extracted {len(extracted_files)} PRJ hex files; staged {len(unsigned_files)} files for signing.")

        pin = get_pin(args)
        signed_files = sign_files(args.signx, unsigned_files, pin, dirs, args.dry_run)

        if args.processing_mode == "embedded":
            if args.dry_run:
                seed_signed_bl_for_excel(extracted_files, signed_files, dirs, args.dry_run)
                rows = [ReportRow(path.name, "", "") for path in sorted(dirs.signed_bl.glob("*.hex"), key=lambda item: item.name.lower())]
            else:
                rows = process_signed_files_embedded(signed_files, extracted_files, dirs)
            report_path = dirs.signed_bl / embedded_report_name(dirs)
            write_release_report(report_path, rows)
            print(f"Embedded processing created {report_path}")
        else:
            seed_signed_bl_for_excel(extracted_files, signed_files, dirs, args.dry_run)
            handle_excel(args.workbook, dirs, args.excel_macro, args.processing_mode == "manual", args.dry_run)

        final_zip = create_final_zip(dirs.signed_bl, args.output_dir, args.release_name)
        print(f"Created {final_zip}")

        removed_artifacts = cleanup_external_tool_artifacts(dirs.root)
        if removed_artifacts:
            print(f"Removed {len(removed_artifacts)} external SignX/ECC artifact files.")

        if not args.keep_work and not args.dry_run:
            shutil.rmtree(dirs.root)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())