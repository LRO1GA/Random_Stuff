# generate_report.py — Communications Summary Generator

Files away manually-requested Copilot (Teams/Outlook) communications summaries
as dated Weekly/Monthly/Yearly Markdown reports. Monthly and Yearly reports are
auto-assembled from their lower-level reports already on disk (only a short
Global Summary "polish" prompt is needed at those levels) — only Weekly
reports require a full manual Copilot query.

## How it works

1. You run the script for the period you want (`--type weekly|monthly|yearly`).
2. The script prints (and saves to a scratch file) a ready-to-use prompt.
   Paste that prompt into Copilot in Teams or Outlook, and ask it to save its
   reply as a downloadable `.md` file (see the "Output File Requirements"
   section at the bottom of `prompts/weekly_prompt_template.md`).
3. A file-open dialog pops up — pick the `.md` file Copilot saved (defaults to
   your Downloads folder, then remembers the last folder you picked from).
4. The script validates/assembles the report and writes it to the configured
   report folder with the correct name.

For **Monthly** reports, the script needs all the **Weekly** reports that
overlap that month to already exist; for **Yearly** reports, it needs all 12
**Monthly** reports for that year. If any are missing, it lists exactly which
ones and cancels — generate those first, then retry.

## Report structure

Every report has exactly 4 sections, in this order: `Global Summary`,
`Detailed Summary`, `Tasks Mentioned`, `Metrics`. For Weekly reports the
Detailed Summary is broken down by day; for Monthly it's broken down by week;
for Yearly it's broken down by month. Metrics are Copilot's best-effort
approximate counts — see the `Metrics` block format in
`prompts/weekly_prompt_template.md`, which must be followed for Monthly/Yearly
aggregation to parse correctly.

## Requirements

Python's standard library, including `tkinter` (bundled with the standard
Windows python.org installer) for the file-open dialog.

## Usage

```
python generate_report.py --type weekly [--date YYYY-MM-DD] [--input-file PATH]
python generate_report.py --type monthly [--date YYYY-MM-DD] [--input-file PATH]
python generate_report.py --type yearly [--date YYYY-MM-DD] [--input-file PATH]
python generate_report.py --set-root "C:\Path\To\Reports"
```

- `--type` — which report to generate. The date range is derived from
  `--date` (default: today): the Sunday–Saturday week, the calendar month, or
  the calendar year containing that date.
- `--input-file` — read the Copilot reply from a given path, skipping the
  file-open dialog (useful for scripting/testing).
- `--set-root` — change where reports are stored. This only recreates an
  empty `Weekly_Reports`/`Monthly_Reports`/`Yearly_Reports` skeleton at the
  new location and prints a warning; it does **not** move existing reports.

### First run

The first time you run the script (no `config.json` yet), it asks you to
enter the folder where reports should be stored and remembers it.

### Folder layout

```
<report root>/
  Weekly_Reports/<MMDDYY-MMDDYY>_Weekly_CommunicationsReport.md
  Monthly_Reports/<MMDDYY-MMDDYY>_Monthly_CommunicationsReport.md
  Yearly_Reports/<MMDDYY-MMDDYY>_Yearly_CommunicationsReport.md
```

## Important: don't store report data in this repo

Reports contain personal/work communications content. `config.json` is
git-ignored, but you're responsible for choosing a report root **outside**
this repository (e.g. a folder in your Documents or OneDrive) — don't point
`--set-root` at a path inside `Random_Stuff`.

## Future enhancement (not implemented)

Metrics are currently Copilot's own approximate recollection. A future
version could compute exact counts via the Microsoft Graph API instead.
