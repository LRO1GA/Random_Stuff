# generate_folders_Excel.py

Generates a folder structure (plus placeholder `.md` files) from the
"Key Roles Incubator - CSW" sheet of an Excel workbook.

## Rules implemented

- Only columns A (level-1 folder) and B (level-2 folder) are used for folders.
- Rows 1-3 are skipped (data starts at row 4 by default).
- Repeated column A values only create their folder once.
- Spaces in folder/file name parts are replaced with underscores.
- Each level-2 folder gets 4 files:
  - `Trainee_Target_Level_<ColumnC>.md`
  - `CSWPR_Target_Level_<ColumnD>.md`
  - `Useful-Links.md`
  - `BDH-Reference.md`
- Each level-2 folder also gets 3 subfolders:
  - `Documentation`
  - `Recordings`
  - `Templates`
- Folders are created in the output directory (default: next to the script).
- Existing folders and `.md` files are never overwritten — re-running the
  script is safe and only fills in what's missing.

## Requirements

None. The script parses the `.xlsx` file directly as a zip/XML archive, so
no third-party packages (e.g. `openpyxl`) are required.

## Usage

```
python generate_folders_Excel.py [path_to_xlsx] [options]
```

If no workbook path is given, the script looks for a single `.xlsx` file
next to itself and uses that.

### Options

| Option | Default | Description |
| --- | --- | --- |
| `path_to_xlsx` | auto-detected `.xlsx` next to the script | Path to the Excel workbook |
| `--sheet` | `Key Roles Incubator - CSW` | Worksheet name to read |
| `--start-row` | `4` | First data row (1-indexed) |
| `--end-row` | none | Last data row (1-indexed). If omitted, processing stops at the first fully blank row |
| `--output-dir` | the script's own folder | Root folder where the structure is created |
| `--dry-run` | off | Print the actions that would be taken without creating anything |

### Examples

Preview what would be created, without touching disk:

```
python generate_folders_Excel.py --dry-run
```

Create the structure in a specific folder, using a specific workbook and sheet:

```
python generate_folders_Excel.py "Key Roles_CSW_ProgressReport.xlsx" --sheet "Key Roles Incubator - CSW" --output-dir "C:\Some\Other\Folder"
```
