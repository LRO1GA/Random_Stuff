# Quick Gen Cleanup

A small interactive Python script that searches for `Gen`/`GEN` folders under a starting folder and deletes the ones you pick.

Current script: [Gen_cleanup.py](Gen_cleanup.py)

## What it does

1. Asks for a **starting folder** to search (e.g. `C:\SharCC`).
2. Treats each **direct subfolder** of the starting folder as a "workspace" candidate.
3. For each candidate, searches for a folder named `Gen`/`GEN` (case-insensitive), checking up to **4 sublevels** deep (the candidate itself counts as sublevel 1). The search for that candidate stops as soon as a match is found, or once all 4 sublevels have been checked without one.
4. Reports how many workspaces have a Gen folder, e.g. `Found 10 workspace(s) with a Gen folder`, and lists each one with its resolved Gen path.
5. Asks which workspace(s) to clean up — comma-separated numbers, `all`, or Enter to skip.
6. Asks for a final `y/n` confirmation, then deletes the Gen folder (and all its contents) for each selected workspace.
7. Afterwards, asks whether to process another starting folder (Option 1) or exit (Option 2). If no input is received within **30 seconds**, it automatically exits.

## Requirements

None. Uses only the Python standard library (`pathlib`, `shutil`, `threading`, `queue`, `collections.deque`).

Compatible with Python 3.9+ (uses `from __future__ import annotations` for newer-style type hints).

## Usage

```powershell
python .\Gen_cleanup.py
```

### Example session

```
=== Quick Gen Cleanup ===

Enter the starting folder to search (e.g. C:\SharCC): C:\SharCC

Found 2 workspace(s) with a Gen folder:

  1. WorkspaceA  (C:\SharCC\WorkspaceA\level2\level3\Gen)
  2. WorkspaceC  (C:\SharCC\WorkspaceC\Gen)

Enter the number(s) of the workspace(s) to clean up (comma-separated, 'all', or Enter to skip): 1

This will permanently delete the Gen folder for: WorkspaceA
Are you sure? (y/n): y

Cleaning up WorkspaceA ...
  -> Removed C:\SharCC\WorkspaceA\level2\level3\Gen

1) Process more folders
2) Exit
Select an option (default: 2 after 30s): 2
Exiting.
```

## Behavior notes

- Matching is case-insensitive and exact (`gen`), so folders like `Generation` are **not** matched.
- Workspace candidates and their subfolders are visited in alphabetical order, breadth-first, so the shallowest match is always found first.
- Folders that can't be read (permission errors, etc.) are skipped silently rather than stopping the whole search.
- Deletion is permanent (`shutil.rmtree`) — always review the listed paths and confirm before proceeding.
- If no workspaces are found, or none are selected for cleanup, the script skips straight to the Option 1/2 prompt.

## Customization

The sublevel search depth and the idle timeout are defined as constants near the top of the script:

```python
MAX_SUBLEVELS = 4
CONTINUE_TIMEOUT = 30.0
```

Edit these to search deeper/shallower or change how long the script waits before auto-exiting.
