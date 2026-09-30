cd# generate_folders_from_text.py

Creates a folder structure from an indented text file.

## Rules implemented

- Each line's indentation determines its folder level:
  - no indentation -> level 1
  - 4 spaces or 1 tab -> level 2
  - 8 spaces or 2 tabs -> level 3
  - ...and so on
- Folders are created in sequence, nested under the last folder seen at the
  level above them.
- Lines whose content starts with `##` are ignored (comments).
- `--root-dir` selects where the top-level folders are created (default: the
  input file's own directory).
- `--max-level` limits how many folder levels are created:
  - Lines exactly 1 level over the limit become a `.txt` file (named after
    the line's content) placed inside the deepest allowed folder.
  - Lines 2 or more levels over the limit are skipped entirely.
- Every leaf folder (a created folder that never receives a deeper
  subfolder) also gets a fixed set of subfolders: `Resumenes`, `Ejercicios`,
  `Bibliografia`, `Resultados_Evaluaciones`. This list is defined in the
  `LEAF_SUBFOLDERS` constant at the top of the script, so it can be edited
  to add/remove subfolders.
- At the end, the script prints the total number of folders and text files
  created.

## Requirements

None. Uses only the Python standard library.

## Usage

```
python generate_folders_from_text.py <input_file> [options]
```

### Options

| Option | Default | Description |
| --- | --- | --- |
| `input_file` | required | Path to the indented text file describing the folder structure |
| `--root-dir` | the input file's own directory | Root folder where the top-level folders are created |
| `--max-level` | none | Maximum folder depth to create. One level beyond this becomes a `.txt` file; deeper lines are skipped |

### Examples

Create the full structure next to the input file:

```
python generate_folders_from_text.py Folder_List.txt
```

Create the structure in a specific folder:

```
python generate_folders_from_text.py Folder_List.txt --root-dir "C:\Some\Other\Folder"
```

Limit folder creation to 2 levels deep (level-3 lines become `.txt` files,
level-4+ lines are skipped):

```
python generate_folders_from_text.py Folder_List.txt --max-level 2
```
