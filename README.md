# Random_Stuff

## Overview

This is an overview of the standalone tools in this workspace. Each tool lives in its own folder with a dedicated `README.md` containing full usage details — this file is just an index with a quick summary and a CLI example for each.


### Folder_Generator_Excel_CSW

Generates a folder structure (plus placeholder `.md` files) from the "Key Roles Incubator - CSW" sheet of an Excel workbook. Parses the `.xlsx` directly (no `openpyxl` dependency needed).

```powershell
python generate_folders_Excel.py "Key Roles_CSW_ProgressReport.xlsx" --sheet "Key Roles Incubator - CSW" --output-dir "C:\Some\Other\Folder"
```

### Folder_Generator_with_Text_CLI

Creates a folder structure from an indented text file, where each line's indentation level maps to a folder depth. Supports a `--max-level` cap that converts deeper lines into placeholder `.txt` files.

```powershell
python generate_folders_from_text.py Folder_List.txt --max-level 2
```

### GatherFiles_Gen9

Interactive Python script that collects specific PostBuild files (`PRJ_Anamap*`, `PRJ_AnaStack*`, `ApplContainer_BB*.appl.zip`) out of a project's `GEN\BB<number>` folder structure and copies them into a single, organized output folder.

```powershell
python GatherFiles_Gen9_v2.py
```

### PDF_Parser_CLI

Extracts the text of a 1-indexed, inclusive page range from a PDF into a plain-text file using `pypdf`, with each page separated by a `----- Page N -----` header.

```powershell
python extract_pdf_pages.py "input_test/Master-En-Robotica-Y-Sistemas-De-Control-Ceupe.pdf" 15 36
```

### SignAutomation_Gen10_Update

Interactive CLI that automates CRC patching and signing of Tesla D4 software releases for ESP and IB2/Rivian projects, including bootloader selection, SignX batch signing, and a CRC/MD5 report of the signed outputs.

```powershell
python Tesla_D4_release_tool_OneBank_FileList.py
```

### SignAutomation_Gen9_CLI

CLI tool that prepares Gen9 hex release packages from an application container: stages unsigned/signed hex files, signs them via `SignX_3.exe`, removes ECC blocks, and produces a release report and final zip.

```powershell
python Gen9_Sign_release_tool_CLI.py <ApplContainerInput> --output-dir <OutputPath> --release-name Signed_ESP9_BLx.x.x.x_Intx --force
```

---

### Prompt template to add a new tool

Use this prompt whenever you want me to add another tool's entry to this root `README.md`:

> Add the `<FolderName>` tool to the root `README.md` in this workspace. Read its `README.md` inside that folder, then add a new section following the same format as the existing entries (brief summary + one CLI example), keeping sections in the same style and alphabetical/folder order as the rest of the file. Only do this if the tool's folder has its own `README.md`.
