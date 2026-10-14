# OSS Legacy Package Automation

A Windows batch script that strips a legacy embedded/automotive SW repository
(AUTOSAR-style trees: `ASW`, `CM`, `DSW`, `FLM`, `Hdr`, etc.) down to just its
`.c`/`.h` sources, so the result is ready for an OSS (Open Source Software)
scan.

## What it does

`Legacy_OSS_Helper.bat` processes a target workspace in four steps:

1. **Count** the total number of files in the target folder.
2. **Remove excluded folders** anywhere in the tree: `tst stubs stub doc sim
   tmp dsmsim bauhaus bswsim`.
3. **Delete every file that isn't `.c` or `.h`**.
4. **Remove the empty folders** left behind.

It then counts the remaining files and writes a `Summary_<timestamp>.txt`
report (starting/ending file counts plus the final file listing) next to the
script.

## Requirements

- Windows with `cmd.exe` and PowerShell available (PowerShell is only used to
  fetch a timestamp).

## Usage

Run the script and enter the path to the workspace you want to process:

```
Legacy_OSS_Helper.bat
```

```
=========================================================================
                      OSS Helper GUI
=========================================================================
Target: "C:\path\to\your\workspace"
=========================================================================
[1] Full Processing
[2] Start from Step 2  (Delete folders tst stubs stub doc sim tmp dsmsim bauhaus bswsim)
[3] Start from Step 3  (Delete non .c/.h files)
[4] Start from Step 4  (Delete Empty folders)
[5] Cancel
=========================================================================
```

- **[1] Full Processing** — runs all four steps.
- **[2]/[3]/[4]** — resume from a specific step (useful if a previous run was
  interrupted).
- **[5] Cancel** — exits without touching anything.

> **Warning**: this is a destructive operation. Steps 2 and 3 permanently
> delete folders and files. Always test against a disposable copy of the
> workspace first.

## Safety checks

Before touching anything, the script:
- Rejects an empty or nonexistent target path.
- Rejects drive roots (e.g. `C:\`).
- Rejects protected system paths (`%SystemRoot%`, `%ProgramFiles%`,
  `%ProgramFiles(x86)%`, `%SystemDrive%\Users`).

## Long-path handling

Deeply nested AUTOSAR trees can exceed Windows' 260-character `MAX_PATH`
limit, which breaks legacy `cmd` builtins (`dir`, `rd`, `del`, `for /r`). To
avoid this, the script maps the target folder to a free drive letter (`Z:`
down to `M:`, whichever is free) using `subst`, and runs all steps against
that short path instead. The original path is still shown in the report.

The temporary drive mapping is removed automatically once the report is
generated. If cleanup is blocked (e.g. a lingering file handle), the script
retries once and, if it still fails, prints the exact command to remove it
manually:

```
subst <Letter>: /d
```

## Report output

`Summary_<timestamp>.txt` is written next to the script and contains:

```
=== File ===
Date: <date/time>
Source Folder: <original target path>
Starting files: <count>
Remaining files: <count>
--------------------------------------------
<full list of remaining .c/.h files>
```
