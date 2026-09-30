# PostBuild Operations AI

A small interactive Python script that collects specific PostBuild files out of a project's `GEN\BB<number>` folder structure and copies them into a single, organized output folder.

Current script: [postbuild_copy_v2.py](postbuild_copy_v2.py)

## What it does

1. Asks for the **Project Root** path (e.g. `C:\SharCC\S3XY_Legacy\TESLA_M3_NV44_MY19`).
2. Asks for the **BB Number** (e.g. `57434`) and locates `GEN\BB57434` inside the project root.
3. Checks which of these 4 known sub-folders exist inside the Gen folder:
   - `CSW_CapF021_FinAll_ECB`
   - `CSW_CapF021OnGlad_FinALL_ECD`
   - `CSW_F021OnGlad_FA_ECE_Runtime`
   - `CSW_GladF021OnGlad_FinNo_ECA`
4. Prints which of those folders were found, e.g. `Found CSW_CapF021_FinAll_ECB, 1 folder to process`.
5. Asks for an **output folder path**. Enter `0` (or leave blank) to use the default: a `Postbuild_out` folder created next to the script.
6. For each folder found, recursively searches for and copies (first match only, per pattern):
   - `PRJ_Anamap*.txt`
   - `PRJ_AnaStack*.txt`
   - `ApplContainer_BB*.appl.zip`

   into `<output_root>\<folder_name>\`, keeping results from each of the 4 folders separate.

## Requirements

- Python 3.9+ (uses `pathlib` and `list[Path]` type hints).
- No third-party dependencies — only the standard library (`shutil`, `sys`, `pathlib`).

## Usage

```powershell
py .\postbuild_copy_v2.py
```

or, if `python` is on your `PATH`:

```powershell
python .\postbuild_copy_v2.py
```

You'll be prompted for:

1. **Project Root path** — must be an existing directory.
2. **BB Number** — used to build `GEN\BB<number>`.
3. **Output folder path** — enter `0` to use the default (`Postbuild_out` next to the script), or provide a custom path (created automatically if it doesn't exist).

### Example session

```
=== PostBuild Operations - File Collector ===

Enter the Project Root path (TESLA_M3_NV44_MY19): C:\SharCC\S3XY_Legacy\TESLA_M3_NV44_MY19
Enter the BB Number: 57434
Found CSW_CapF021_FinAll_ECB, CSW_GladF021OnGlad_FinNo_ECA, 2 folders to process
Enter the output folder path (0 = default: C:\VSCode\PostBuild_Operations_AI\Postbuild_out):

Processing CSW_CapF021_FinAll_ECB ...
    - Copied PRJ_Anamap_v1.txt
    - Copied PRJ_AnaStack_v1.txt
    - Copied ApplContainer_BB57434.appl.zip

Processing CSW_GladF021OnGlad_FinNo_ECA ...
    - Copied PRJ_Anamap_v2.txt
    - No file matching 'PRJ_AnaStack*.txt' found, skipped.
    - No file matching 'ApplContainer_BB*.appl.zip' found, skipped.

Done. Files copied to:
  C:\VSCode\PostBuild_Operations_AI\Postbuild_out
```

## Behavior notes

- If the Gen folder (`GEN\BB<number>`) doesn't exist, the script prints an error and exits.
- If none of the 4 target folders exist inside the Gen folder, the script prints a message and exits.
- Search for the 3 file patterns is **recursive** within each target folder — files can live in nested sub-folders.
- If a pattern matches multiple files in the same folder, only the **first match** is copied.
- If a pattern has no match in a folder, a skip message is printed and processing continues with the next pattern/folder.
- The output structure mirrors the source folder names, e.g.:

```
Postbuild_out/
├── CSW_CapF021_FinAll_ECB/
│   ├── PRJ_Anamap_v1.txt
│   ├── PRJ_AnaStack_v1.txt
│   └── ApplContainer_BB57434.appl.zip
└── CSW_GladF021OnGlad_FinNo_ECA/
    └── PRJ_Anamap_v2.txt
```

## Customization

The 4 target folder names and the 3 file search patterns are defined as constants near the top of the script:

```python
TARGET_FOLDERS = [
    "CSW_CapF021_FinAll_ECB",
    "CSW_CapF021OnGlad_FinALL_ECD",
    "CSW_F021OnGlad_FA_ECE_Runtime",
    "CSW_GladF021OnGlad_FinNo_ECA",
]

FILE_PATTERNS = [
    "PRJ_Anamap*.txt",
    "PRJ_AnaStack*.txt",
    "ApplContainer_BB*.appl.zip",
]
```

Edit these lists to add/remove folders or file patterns without touching the rest of the logic.
