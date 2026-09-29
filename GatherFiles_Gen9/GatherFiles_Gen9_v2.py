"""
PostBuild Operations - Gen folder file collector.

Prompts for a project root path and a BB number, locates the corresponding
GEN\\BB<number> folder, finds which of the 4 known CSW sub-folders exist,
and copies the relevant PRJ_Anamap / PRJ_AnaStack / ApplContainer files
from each into Postbuild_Out\\<folder_name>, created next to this script.
"""

import shutil
import sys
from pathlib import Path

# The 4 folders to look for inside GEN\BB<number>
TARGET_FOLDERS = [
    "CSW_CapF021_FinAll_ECB",
    "CSW_CapF021OnGlad_FinALL_ECD",
    "CSW_F021OnGlad_FA_ECE_Runtime",
    "CSW_GladF021OnGlad_FinNo_ECA",
]

# Search patterns to collect from each found folder (recursive, first match only)
FILE_PATTERNS = [
    "PRJ_Anamap*.txt",
    "PRJ_AnaStack*.txt",
    "ApplContainer_BB*.appl.zip",
]


def prompt_project_root() -> Path:
    while True:
        raw = input("Enter the Project Root path (TESLA_M3_NV44_MY19): ").strip().strip('"')
        path = Path(raw)
        if path.is_dir():
            return path
        print(f"  -> Path not found or not a directory: {path}\n")


def prompt_bb_number() -> str:
    while True:
        raw = input("Enter the BB Number: ").strip()
        if raw:
            return raw
        print("  -> BB Number cannot be empty.\n")


def prompt_output_root(default_root: Path) -> Path:
    while True:
        raw = input(
            f"Enter the output folder path (0 = default: {default_root}): "
        ).strip().strip('"')
        if raw == "0" or raw == "":
            return default_root

        path = Path(raw)
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"  -> Could not use that path: {exc}\n")
            continue
        return path


def find_gen_folder(project_root: Path, bb_number: str) -> Path:
    gen_folder = project_root / "GEN" / f"BB{bb_number}"
    if not gen_folder.is_dir():
        print(f"\nERROR: Could not find Gen folder at expected path:\n  {gen_folder}")
        sys.exit(1)
    return gen_folder


def find_existing_target_folders(gen_folder: Path) -> list[Path]:
    found = [gen_folder / name for name in TARGET_FOLDERS if (gen_folder / name).is_dir()]

    if not found:
        print(f"\nNo target folders found inside:\n  {gen_folder}")
        return found

    names = ", ".join(f.name for f in found)
    count = len(found)
    plural = "folder" if count == 1 else "folders"
    print(f"Found {names}, {count} {plural} to process")
    return found


def copy_first_match(source_folder: Path, pattern: str, dest_folder: Path) -> None:
    match = next(source_folder.rglob(pattern), None)
    if match is None:
        print(f"    - No file matching '{pattern}' found, skipped.")
        return

    dest_path = dest_folder / match.name
    shutil.copy2(match, dest_path)
    print(f"    - Copied {match.name}")


def process_folder(folder: Path, output_root: Path) -> None:
    print(f"\nProcessing {folder.name} ...")
    dest_folder = output_root / folder.name
    dest_folder.mkdir(parents=True, exist_ok=True)

    for pattern in FILE_PATTERNS:
        copy_first_match(folder, pattern, dest_folder)


def main() -> None:
    print("=== PostBuild Operations - File Collector ===\n")

    project_root = prompt_project_root()
    bb_number = prompt_bb_number()

    gen_folder = find_gen_folder(project_root, bb_number)
    found_folders = find_existing_target_folders(gen_folder)

    if not found_folders:
        sys.exit(1)

    default_output_root = Path(__file__).resolve().parent / "Postbuild_out"
    output_root = prompt_output_root(default_output_root)
    output_root.mkdir(parents=True, exist_ok=True)

    for folder in found_folders:
        process_folder(folder, output_root)

    print(f"\nDone. Files copied to:\n  {output_root}")


if __name__ == "__main__":
    main()
