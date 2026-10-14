#!/usr/bin/env python3
"""
Quick Gen Cleanup.

Interactively searches a starting folder for "Gen"/"GEN" folders, up to
4 sublevels deep, and offers to delete the ones found.

Rules implemented:
  - The user provides a starting folder to search.
  - Each direct subfolder of the starting folder is a "workspace" candidate.
  - A workspace is counted once a Gen/GEN folder is found anywhere within
    its first 4 sublevels (search stops for that workspace as soon as a
    match is found, or after 4 sublevels have been checked).
  - The user picks which workspaces to clean up; their Gen folder (and
    all its contents) is deleted after confirmation.
  - Afterwards the user can process another starting folder or exit.
    No input for 30 seconds automatically selects Exit.
"""

from __future__ import annotations

import queue
import shutil
import threading
from collections import deque
from pathlib import Path

MAX_SUBLEVELS = 4
CONTINUE_TIMEOUT = 30.0


def input_with_timeout(prompt: str, timeout: float) -> str | None:
    """Read a line of input, returning None if nothing is entered in time."""
    print(prompt, end="", flush=True)
    result: "queue.Queue[str]" = queue.Queue()

    def reader() -> None:
        try:
            result.put(input())
        except EOFError:
            result.put("")

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        return result.get(timeout=timeout)
    except queue.Empty:
        print("\n  -> No input received, selecting Option 2 (Exit).")
        return None


def prompt_starting_folder() -> Path:
    while True:
        raw = input("\nEnter the starting folder to search (e.g. C:\\SharCC): ").strip().strip('"')
        path = Path(raw)
        if path.is_dir():
            return path
        print(f"  -> Path not found or not a directory: {path}")


def find_gen_folder(candidate: Path, max_sublevels: int) -> Path | None:
    """Breadth-first search for a folder named 'gen' (case-insensitive) within max_sublevels."""
    queue_: deque[tuple[Path, int]] = deque([(candidate, 0)])
    while queue_:
        current, depth = queue_.popleft()
        if current.name.lower() == "gen":
            return current
        if depth >= max_sublevels - 1:
            continue
        try:
            children = sorted(p for p in current.iterdir() if p.is_dir())
        except OSError:
            continue
        for child in children:
            queue_.append((child, depth + 1))
    return None


def discover_workspaces(root: Path, max_sublevels: int) -> list[tuple[Path, Path]]:
    try:
        candidates = sorted(p for p in root.iterdir() if p.is_dir())
    except OSError as exc:
        print(f"  -> Could not read starting folder: {exc}")
        return []

    workspaces = []
    for candidate in candidates:
        gen_path = find_gen_folder(candidate, max_sublevels)
        if gen_path is not None:
            workspaces.append((candidate, gen_path))
    return workspaces


def parse_selection(raw: str, count: int) -> list[int]:
    raw = raw.strip().lower()
    if raw in ("all", "a", "*"):
        return list(range(count))

    seen: set[int] = set()
    indices: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            idx = int(part) - 1
            if 0 <= idx < count and idx not in seen:
                seen.add(idx)
                indices.append(idx)
    return indices


def prompt_workspace_selection(workspaces: list[tuple[Path, Path]]) -> list[int]:
    print(f"\nFound {len(workspaces)} workspace(s) with a Gen folder:\n")
    for i, (workspace, gen_path) in enumerate(workspaces, start=1):
        print(f"  {i}. {workspace.name}  ({gen_path})")

    raw = input(
        "\nEnter the number(s) of the workspace(s) to clean up "
        "(comma-separated, 'all', or Enter to skip): "
    )
    return parse_selection(raw, len(workspaces))


def cleanup_workspace(gen_path: Path) -> bool:
    try:
        shutil.rmtree(gen_path)
        print(f"  -> Removed {gen_path}")
        return True
    except OSError as exc:
        print(f"  -> Failed to remove {gen_path}: {exc}")
        return False


def confirm_and_cleanup(workspaces: list[tuple[Path, Path]], selected_indices: list[int]) -> None:
    if not selected_indices:
        print("No workspaces selected, skipping cleanup.")
        return

    selected = [workspaces[i] for i in selected_indices]
    names = ", ".join(workspace.name for workspace, _ in selected)
    confirm = input(
        f"\nThis will permanently delete the Gen folder for: {names}\nAre you sure? (y/n): "
    ).strip().lower()
    if confirm != "y":
        print("Cleanup cancelled.")
        return

    print()
    for workspace, gen_path in selected:
        print(f"Cleaning up {workspace.name} ...")
        cleanup_workspace(gen_path)


def main() -> None:
    print("=== Quick Gen Cleanup ===")

    while True:
        root = prompt_starting_folder()
        workspaces = discover_workspaces(root, MAX_SUBLEVELS)

        if not workspaces:
            print("\nNo workspaces with a Gen/GEN folder were found.")
        else:
            selected_indices = prompt_workspace_selection(workspaces)
            confirm_and_cleanup(workspaces, selected_indices)

        choice = input_with_timeout(
            f"\n1) Process more folders\n2) Exit\nSelect an option (default: 2 after {int(CONTINUE_TIMEOUT)}s): ",
            CONTINUE_TIMEOUT,
        )
        if choice is None or choice.strip() != "1":
            print("Exiting.")
            break


if __name__ == "__main__":
    main()
