#!/usr/bin/env python3
"""
Creates a folder structure from an indented text file.

Rules implemented:
  - Each line's indentation determines its folder level:
      no indentation      -> level 1
      4 spaces or 1 tab    -> level 2
      8 spaces or 2 tabs   -> level 3
      ...and so on
  - Folders are created in sequence, nested under the last folder seen at
    the level above them.
  - --root-dir selects where the top-level folders are created
    (default: the input file's own directory).
  - --max-level limits how many folder levels are created:
      - Lines exactly 1 level over the limit become a .txt file (named
        after the line's content) placed inside the deepest allowed folder.
      - Lines 2 or more levels over the limit are skipped entirely.
  - Lines whose content starts with "##" are ignored (comments).
  - Every leaf folder (a created folder that never receives a deeper
    subfolder) also gets a fixed set of subfolders, defined in
    LEAF_SUBFOLDERS.

Usage:
    python generate_folders_from_text.py Folder_List.txt [--root-dir PATH] [--max-level N]
"""

import argparse
import re
import sys
from pathlib import Path

INVALID_WIN_CHARS = r'<>:"/\|?*'

# Subfolders created inside every leaf folder; edit this list to add/remove them.
LEAF_SUBFOLDERS = ["Resumenes", "Ejercicios", "Bibliografia", "Resultados_Evaluaciones"]


def sanitize(name: str) -> str:
    """Strip characters illegal in Windows folder/file names."""
    name = name.strip()
    return re.sub(f"[{re.escape(INVALID_WIN_CHARS)}]", "", name)


def parse_indent(line: str):
    """Return (level, name) for a line, consuming one tab or 4 spaces per level."""
    level = 1
    i = 0
    while True:
        if line[i:i + 1] == "\t":
            level += 1
            i += 1
        elif line[i:i + 4] == "    ":
            level += 1
            i += 4
        else:
            break
    return level, line[i:].strip()


def get_parent(paths_by_level: dict, level: int):
    """Find the nearest existing ancestor folder for the given level."""
    for l in range(level - 1, -1, -1):
        if l in paths_by_level:
            return paths_by_level[l]
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "input_file",
        help="Path to the indented text file describing the folder structure")
    parser.add_argument(
        "--root-dir", default=None,
        help="Root folder where the top-level folders are created (default: the input file's directory)")
    parser.add_argument(
        "--max-level", type=int, default=None,
        help="Maximum folder depth to create. One level beyond this becomes a .txt file; deeper lines are skipped")
    args = parser.parse_args()

    if args.max_level is not None and args.max_level < 1:
        sys.exit("--max-level must be 1 or greater.")

    input_path = Path(args.input_file).resolve()
    if not input_path.is_file():
        sys.exit(f"Input file not found: {input_path}")

    root_dir = Path(args.root_dir).resolve() if args.root_dir else input_path.parent
    root_dir.mkdir(parents=True, exist_ok=True)

    max_level = args.max_level
    paths_by_level = {0: root_dir}

    created_folders = []
    parents_with_children = set()
    folder_count = 0
    text_file_count = 0

    with input_path.open("r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    for raw_line in lines:
        line = raw_line.rstrip("\r\n")
        if not line.strip():
            continue

        level, name = parse_indent(line)
        if not name or name.startswith("##"):
            continue

        if max_level is not None and level > max_level:
            if level == max_level + 1:
                parent = get_parent(paths_by_level, level)
                file_path = parent / f"{sanitize(name)}.txt"
                print(f"Creating file: {file_path}")
                file_path.touch(exist_ok=True)
                text_file_count += 1
            else:
                print(f"Skipping (level {level} exceeds limit by 2+): {name}")
            continue

        parent = get_parent(paths_by_level, level)
        folder_path = parent / sanitize(name)
        print(f"Creating folder: {folder_path}")
        folder_path.mkdir(parents=True, exist_ok=True)
        created_folders.append(folder_path)
        parents_with_children.add(parent)
        folder_count += 1

        paths_by_level[level] = folder_path
        for l in list(paths_by_level):
            if l > level:
                del paths_by_level[l]

    leaf_folders = [p for p in created_folders if p not in parents_with_children]
    for leaf in leaf_folders:
        for subfolder in LEAF_SUBFOLDERS:
            sub_path = leaf / subfolder
            print(f"Creating folder: {sub_path}")
            sub_path.mkdir(parents=True, exist_ok=True)
            folder_count += 1

    print(f"Done. Created {folder_count} folder(s) and {text_file_count} text file(s).")


if __name__ == "__main__":
    main()
