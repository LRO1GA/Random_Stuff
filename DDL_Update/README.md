# DDL Generator — Setup & Build Guide

`bin/` and `obj/` are gitignored, so after pulling this repo you need to restore and build locally before you have a runnable `.exe`.

## Prerequisites

- [.NET SDK 8.0+](https://dotnet.microsoft.com/download) (check with `dotnet --list-sdks`)
- Internet access on first build, to restore the `EPPlus` and `CsvHelper` NuGet packages declared in `DDL_Generator.csproj`

## Build

From this folder (`DDL_Update/work`):

```powershell
dotnet build
```

This restores the NuGet packages automatically and produces `bin/Debug/net8.0/DDL_Generator.exe` (plus its dependent DLLs, which must stay alongside the `.exe`).

## Publish a standalone executable

```powershell 
dotnet publish -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -o publish
```

Produces a single-file `publish/DDL_Generator.exe` (requires the .NET 8 runtime on the machine that runs it — use `--self-contained true` instead if you need it to run without the runtime installed).

## Run

Normal mode (expects a `Gen\<build_id>\src_out\DDL` folder structure):

```powershell
dotnet run -- <customer> <build_id>
```

Dry-run mode (reads CSVs directly from a folder, skipping the `Gen` folder search):

```powershell
dotnet run -- --dry-run <input_folder> <customer> [output_folder]
```

Output file is named `<customer>_DDLReport.xlsx`.
