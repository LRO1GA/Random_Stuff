#!/usr/bin/env python3
"""
Generates a folder structure (plus placeholder .md files) from the
"Key Roles Incubator - CSW" sheet of an Excel workbook.

Rules implemented:
  - Only columns A (level-1 folder) and B (level-2 folder) are used for folders.
  - Rows 1-3 are skipped (data starts at row 4 by default).
  - Repeated column A values only create their folder once.
  - Spaces in folder/file name parts are replaced with underscores.
  - Each level-2 folder gets 4 files:
      Trainee_Target_Level_<ColumnC>.md
      CSWPR_Target_Level_<ColumnD>.md
      Useful-Links.md
      BDH-Reference.md
  - Each level-2 folder also gets 3 subfolders:
      Documentation
      Recordings
      Templates
  - Folders are created relative to this script's location.

Usage:
    python generate_folders.py [path_to_xlsx] [--sheet "Sheet Name"] [--start-row N] [--output-dir PATH] [--dry-run]

If no workbook path is given, the script looks for a single .xlsx file next
to itself. If no output directory is given, folders are created next to the
script. No third-party packages are required (parses the .xlsx directly as
a zip/XML archive).
"""

import argparse
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL_NS = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
R_ID_ATTR = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
INVALID_WIN_CHARS = r'<>:"/\|?*'


def sanitize(value: str) -> str:
    """Replace whitespace runs with underscores; strip characters illegal in Windows paths."""
    value = value.strip()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(f"[{re.escape(INVALID_WIN_CHARS)}]", "", value)
    return value


def col_letters(cell_ref: str) -> str:
    return re.match(r"[A-Z]+", cell_ref).group()


def find_default_workbook(script_dir: Path) -> Path:
    candidates = sorted(script_dir.glob("*.xlsx"))
    if not candidates:
        sys.exit("No .xlsx file found next to the script. Pass the path explicitly.")
    if len(candidates) > 1:
        sys.exit(f"Multiple .xlsx files found: {[c.name for c in candidates]}. Pass the path explicitly.")
    return candidates[0]


def load_shared_strings(z: zipfile.ZipFile):
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("xl/sharedStrings.xml"))
    strings = []
    for si in root.findall("m:si", NS):
        texts = si.findall(".//m:t", NS)
        strings.append("".join(t.text or "" for t in texts))
    return strings


def find_sheet_xml_path(z: zipfile.ZipFile, sheet_name: str) -> str:
    workbook = ET.fromstring(z.read("xl/workbook.xml"))
    rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
    rid_to_target = {rel.get("Id"): rel.get("Target") for rel in rels.findall("r:Relationship", REL_NS)}

    for sheet in workbook.findall(".//m:sheet", NS):
        if sheet.get("name") == sheet_name:
            target = rid_to_target[sheet.get(R_ID_ATTR)]
            return target if target.startswith("xl/") else f"xl/{target}"

    available = [s.get("name") for s in workbook.findall(".//m:sheet", NS)]
    sys.exit(f"Sheet '{sheet_name}' not found. Available sheets: {available}")


def read_rows(xlsx_path: Path, sheet_name: str) -> dict:
    with zipfile.ZipFile(xlsx_path) as z:
        shared = load_shared_strings(z)
        sheet_root = ET.fromstring(z.read(find_sheet_xml_path(z, sheet_name)))

    rows = {}
    sheet_data = sheet_root.find("m:sheetData", NS)
    for row in sheet_data.findall("m:row", NS):
        row_num = int(row.get("r"))
        values = {}
        for cell in row.findall("m:c", NS):
            col = col_letters(cell.get("r"))
            cell_type = cell.get("t")
            v = cell.find("m:v", NS)
            value = v.text if v is not None else None
            if cell_type == "s" and value is not None:
                value = shared[int(value)]
            elif cell_type == "inlineStr":
                is_el = cell.find("m:is", NS)
                if is_el is not None:
                    value = "".join(t.text or "" for t in is_el.findall(".//m:t", NS))
            values[col] = value.strip() if isinstance(value, str) else value
        rows[row_num] = values
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "workbook", nargs="?", 
        help="Path to the .xlsx file")
    parser.add_argument(
        "--sheet", default="Key Roles Incubator - CSW",
        help="Worksheet name")
    parser.add_argument(
        "--start-row", type=int, default=4,
        help="First data row (1-indexed)")
    parser.add_argument(
        "--end-row",type=int, default=None,
        help="Last data row (1-indexed). If omitted, processing stops at the first fully blank row.",)
    parser.add_argument(
        "--output-dir", default=None,
        help="Root folder where the structure is created (default: the script's own folder)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print actions without creating anything")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    output_dir = Path(args.output_dir).resolve() if args.output_dir else script_dir
    xlsx_path = Path(args.workbook).resolve() if args.workbook else find_default_workbook(script_dir)

    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    rows = read_rows(xlsx_path, args.sheet)
    max_row = args.end_row if args.end_row else (max(rows) if rows else 0)

    created_level1 = set()
    for row_num in range(args.start_row, max_row + 1):
        row = rows.get(row_num, {})
        col_a, col_b, col_c, col_d = row.get("A"), row.get("B"), row.get("C"), row.get("D")

        if not col_a and not col_b and args.end_row is None:
            print(f"Stopping at row {row_num}: first fully blank row (use --end-row to override).")
            break

        if not col_a or not col_b:
            continue

        level1 = sanitize(col_a)
        level2 = sanitize(col_b)
        trainee_level = sanitize(col_c) if col_c else "Unspecified"
        cswpr_level = sanitize(col_d) if col_d else "Unspecified"

        level1_dir = output_dir / level1
        level2_dir = level1_dir / level2

        if level1 not in created_level1:
            created_level1.add(level1)
            print(f"{'[dry-run] ' if args.dry_run else ''}Creating folder: {level1}")
            if not args.dry_run:
                level1_dir.mkdir(parents=True, exist_ok=True)

        print(f"{'[dry-run] ' if args.dry_run else ''}Creating folder: {level1}\\{level2}")
        if not args.dry_run:
            level2_dir.mkdir(parents=True, exist_ok=True)

        md_files = [
            f"Trainee_Target_Level_{trainee_level}.md",
            f"CSWPR_Target_Level_{cswpr_level}.md",
            "Useful-Links.md",
            "BDH-Reference.md",
        ]
        for filename in md_files:
            file_path = level2_dir / filename
            if file_path.exists():
                continue
            print(f"{'[dry-run] ' if args.dry_run else ''}  Creating file: {filename}")
            if not args.dry_run:
                file_path.touch()

        for subfolder in ("Documentation", "Recordings", "Templates"):
            subfolder_dir = level2_dir / subfolder
            print(f"{'[dry-run] ' if args.dry_run else ''}  Creating folder: {subfolder}")
            if not args.dry_run:
                subfolder_dir.mkdir(parents=True, exist_ok=True)

    print("Done.")


if __name__ == "__main__":
    main()
