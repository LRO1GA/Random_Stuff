# Flash Release Tool

Python CLI for preparing Gen9 hex release packages from an application container.

## Last Tool Run + Template

python Gen9_Sign_release_tool_CLI.py C:\Users\LRO1GA\Documents\CSW\1_Signed_HexFiles\HAD_BL12.0.0.0_Int3\ApplContainer_BB57434_V1200_ECB_CSW_CapF021_FinAll_ECB.appl.zip --output-dir C:\Users\LRO1GA\Documents\CSW\1_Signed_HexFiles\HAD_BL12.0.0.0_Int3 --release-name Signed_ESP_HAD_BL12.0.0.0_Int3 --force

python Gen9_Sign_release_tool_CLI.py <ApplContainerInput> --output-dir <OutputPath> --release-name Signed_ESP9_BLx.x.x.x_Intx --force

## CLI Command Samples

Automatic release-name detection from the `.appl.zip` filename:

```powershell
python Project\Gen9_Sign_release_tool_CLI.pyInput\ApplContainer_BB56480_V1100_ECB_CSW_CapF021_FinAll_ECB.appl.zip --force --keep-work
```

For that sample file, the derived release name is:

```text
BL11.0_BB56480
```

Explicit release-name override:

```powershell
python Project\Gen9_Sign_release_tool_CLI.pyInput\ApplContainer_BB56480_V1100_ECB_CSW_CapF021_FinAll_ECB.appl.zip --release-name Signed_ESP_HAD_BL11.0.0.0_Int2 --force --keep-work
```

Dry run without SignX or Excel:

```powershell
python Project\Gen9_Sign_release_tool_CLI.pyInput\ApplContainer_BB56480_V1100_ECB_CSW_CapF021_FinAll_ECB.appl.zip --output-dir Project\dryrun_output --work-dir Project\dryrun_work --force --dry-run --keep-work
```

Excel compatibility mode using `ManualRun`:

```powershell
python Project\Gen9_Sign_release_tool_CLI.pyInput\ApplContainer_BB56480_V1100_ECB_CSW_CapF021_FinAll_ECB.appl.zip --processing-mode excel --excel-macro ManualRun --force
```

## Current Workflow

The first implementation in `flash_release_tool.py` does the following:

1. Extracts top-level `PRJ_*.hex` files from an `.appl.zip` file.
2. Stages files into `Unsigned`, `Signed`, `Logs`, and `Signed_BL` folders.
3. Matches the sample special case where `PRJ_BootBlock1_*.hex` is copied unchanged into `Signed_BL` and is not staged in `Unsigned`.
4. Calls `SignX_3.exe` once with a generated file list so all staged unsigned hex files are signed in one SignX instance, then writes the combined output to `Logs\SignX_batch.log`.
5. Copies signed outputs into `Signed` and seeds `Signed_BL` for ECC-removal processing.
6. Removes ECC blocks and creates a release report using the embedded Python implementation of the workbook's `ManualRun` logic.
7. Optionally stages/runs `FinalizeRelease_V12.xlsm` through Excel COM when `--processing-mode excel` is selected.
8. Creates the final zip with one top-level folder named by `--release-name`.
9. Removes known SignX/ECC side artifacts created outside the work folder, such as `ecc470.log`, `log*.txt`, `trace*.txt`, and `SignXLog*.log`.

## Parameters

`input_zip`: Required path to the input `.appl.zip` file that contains the `PRJ_*.hex` files.

`--release-name`: Optional final zip and top-level folder name. If omitted, the tool derives `BL<V>_<BB>` from `_V*_` and `_BB*_` in the input filename, for example `BL01.01_BB12345`.

`--output-dir`: Optional output directory for the final zip. Defaults to the workspace `output` folder.

`--work-dir`: Optional working directory for extracted, unsigned, signed, log, and processed files. Defaults to `work\<release-name>`.

`--signx`: Optional path to `SignX_3.exe`. Defaults to `C:\Program Files (x86)\Robert Bosch GmbH\SignX\SignX_3.exe`.

`--workbook`: Optional path to `FinalizeRelease_V12.xlsm`. Only needed when using `--processing-mode excel` or `--processing-mode manual`.

`--processing-mode`: Optional processing mode. Use `embedded` for the default Python ECC/report flow, `excel` to call the workbook macro through COM, or `manual` to stage the workbook and pause for operator processing.

`--excel-macro`: Optional macro name used with `--processing-mode excel`. Defaults to `ManualRun`.

`--pin-signx`: Optional environment variable name containing the smartcard PIN. If omitted, the tool prompts for the PIN with hidden input.

`--force`: Deletes an existing work directory before running.

`--keep-work`: Keeps the work directory after successful completion. Without this flag, successful real runs delete the work directory.

`--dry-run`: Creates folders, file lists, placeholder outputs, and the final zip without calling SignX or Excel.

After the final zip is created, the tool cleans known SignX/ECC artifact files generated outside the work folder. The scoped logs under the work folder, such as `Logs\SignX_batch.log`, are kept with the release work files.

## Dry Run

```powershell
python Project\Gen9_Sign_release_tool_CLI.pyInput\ApplContainer_BB56480_V1100_ECB_CSW_CapF021_FinAll_ECB.appl.zip --release-name Signed_ESP_HAD_BL11.0.0.0_Int2 --output-dir Project\dryrun_output --work-dir Project\dryrun_work --force --dry-run --keep-work
```

## Real Run

```powershell
python Project\Gen9_Sign_release_tool_CLI.py<Applcontainer-Path> --output-dir <Output-Path> --release-name Signed_ESP_HAD_BL12.0.0.0_Int2 --force
```

By default, SignX is expected at:

```text
C:\Program Files (x86)\Robert Bosch GmbH\SignX\SignX_3.exe
```

Use `--signx <path>` if a different location is needed.

## Processing Modes

Default mode is `embedded`. This does not depend on `FinalizeRelease_V12.xlsm`; it reproduces the workbook's non-interactive `ManualRun` behavior for the release files:

- Uses the workbook include list: `PRJ_CalBlock*`, `PRJ_BootBlock2*`, `PRJ_CodeBlock*`, `*LN000*`, and `PRJ_HexPart*`.
- Removes ECC from Gen9.1/Gen9.2 signed files by trimming the ECC section and writing `_withoutECC.hex`.
- Calculates CRC and MD5 values for signed files in the include list.
- Creates `Bosch_Release_Documentation_<BB>_<Version>.xlsx` in `Signed_BL`.

The Excel macro is still available for compatibility:

```powershell
python Project\Gen9_Sign_release_tool_CLI.py<input.appl.zip> --release-name <zip-folder-name> --processing-mode excel --excel-macro ManualRun --force
```

`ManualRun` opens a file picker and asks for a comment through Excel UI, so unattended COM runs can wait indefinitely. Use `embedded` for automated runs.