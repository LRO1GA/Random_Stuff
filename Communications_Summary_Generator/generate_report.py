"""CLI to file away Copilot (Teams/Outlook) communications summaries, downloaded as a
Markdown file and picked via a file dialog, as Weekly/Monthly/Yearly reports, auto-
assembling Monthly/Yearly reports from their lower-level reports on disk.
"""
import argparse
import calendar
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = TOOL_DIR / "prompts"
CONFIG_PATH = TOOL_DIR / "config.json"
SCRATCH_PROMPT_PATH = TOOL_DIR / "_scratch_prompt.md"

REQUIRED_SECTIONS = ["Global Summary", "Detailed Summary", "Tasks Mentioned", "Metrics"]
# Copying Copilot's reply out of Teams/Outlook often strips Markdown ("## ", "**"),
# so a header line can show up as plain text. Match either form, case-insensitively.
SECTION_RE = re.compile(
    r"^[ \t]*#{0,6}[ \t]*\*{0,2}[ \t]*(" + "|".join(re.escape(s) for s in REQUIRED_SECTIONS) + r")[ \t]*\*{0,2}[ \t]*:?[ \t]*$",
    re.MULTILINE | re.IGNORECASE,
)

# --- Config / storage root -------------------------------------------------

def load_config():
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return None


def save_config(cfg):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def update_config(**kwargs):
    """Merge the given keys into the existing config instead of overwriting it."""
    cfg = load_config() or {}
    cfg.update(kwargs)
    save_config(cfg)


def ensure_report_folders(root: Path):
    for sub in ("Weekly_Reports", "Monthly_Reports", "Yearly_Reports"):
        (root / sub).mkdir(parents=True, exist_ok=True)


def get_report_root() -> Path:
    cfg = load_config()
    if cfg and cfg.get("report_root_path"):
        root = Path(cfg["report_root_path"])
        ensure_report_folders(root)
        return root
    print("No report storage location configured yet.")
    path_str = input("Enter the folder path where reports should be stored: ").strip().strip('"')
    root = Path(path_str).expanduser()
    ensure_report_folders(root)
    update_config(report_root_path=str(root))
    print(f"Report root set to: {root}")
    return root


def set_root(new_path_str: str):
    new_root = Path(new_path_str).expanduser()
    ensure_report_folders(new_root)
    update_config(report_root_path=str(new_root))
    print(f"Report root updated to: {new_root}")
    print(
        "WARNING: existing reports were NOT moved. If you want to keep them, manually copy "
        "the Weekly_Reports/Monthly_Reports/Yearly_Reports folders from the old location "
        "to the new one."
    )


# --- Date ranges -------------------------------------------------------------

def week_range(anchor: date):
    """Sunday-Saturday week containing anchor."""
    days_since_sunday = (anchor.weekday() + 1) % 7  # Monday=0 .. Sunday=6
    start = anchor - timedelta(days=days_since_sunday)
    return start, start + timedelta(days=6)


def month_range(anchor: date):
    start = anchor.replace(day=1)
    last_day = calendar.monthrange(anchor.year, anchor.month)[1]
    return start, anchor.replace(day=last_day)


def year_range(anchor: date):
    return date(anchor.year, 1, 1), date(anchor.year, 12, 31)


def weeks_overlapping(month_start: date, month_end: date):
    weeks = []
    cur_start, cur_end = week_range(month_start)
    while cur_start <= month_end:
        weeks.append((cur_start, cur_end))
        cur_start += timedelta(days=7)
        cur_end += timedelta(days=7)
    return weeks


def months_of_year(year: int):
    months = []
    for m in range(1, 13):
        start = date(year, m, 1)
        end = date(year, m, calendar.monthrange(year, m)[1])
        months.append((start, end))
    return months


def fmt(d: date) -> str:
    return d.strftime("%m%d%y")


def report_filename(start: date, end: date, type_label: str) -> str:
    return f"{fmt(start)}-{fmt(end)}_{type_label}_CommunicationsReport.md"


def week_label(start: date, end: date) -> str:
    return f"Week of {start.strftime('%b %d')} - {end.strftime('%b %d, %Y')}"


def month_label(start: date, _end: date) -> str:
    return start.strftime("%B %Y")


# --- Markdown section parsing -------------------------------------------------

def split_sections(text: str) -> dict:
    sections = {}
    matches = list(SECTION_RE.finditer(text))
    for i, m in enumerate(matches):
        # normalize to canonical casing regardless of how the header was copy-pasted
        name = next(s for s in REQUIRED_SECTIONS if s.lower() == m.group(1).strip().lower())
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()
    return sections


def validate_sections(sections: dict, source_label: str):
    missing = [name for name in REQUIRED_SECTIONS if name not in sections]
    if missing:
        print(f"WARNING: {source_label} is missing section(s): {', '.join(missing)}")


def parse_metrics(metrics_text: str) -> dict:
    result = {"people_messaged": 0, "messages_sent": 0, "most_messaged_person": (None, 0), "busiest_day": (None, 0)}
    m = re.search(r"People/groups messaged:\s*(\d+)", metrics_text)
    if m:
        result["people_messaged"] = int(m.group(1))
    m = re.search(r"Messages sent by me:\s*(\d+)", metrics_text)
    if m:
        result["messages_sent"] = int(m.group(1))
    m = re.search(r"Most messaged person:\s*(.+?)\s*\((\d+)\s*messages?\)", metrics_text)
    if m:
        result["most_messaged_person"] = (m.group(1).strip(), int(m.group(2)))
    m = re.search(r"Day with most volume:\s*(.+?)\s*\((\d+)\s*interactions?\)", metrics_text)
    if m:
        result["busiest_day"] = (m.group(1).strip(), int(m.group(2)))
    return result


def aggregate_metrics(metrics_list: list) -> str:
    total_people = sum(m["people_messaged"] for m in metrics_list)
    total_messages = sum(m["messages_sent"] for m in metrics_list)
    most_person = max(metrics_list, key=lambda m: m["most_messaged_person"][1])["most_messaged_person"]
    busiest = max(metrics_list, key=lambda m: m["busiest_day"][1])["busiest_day"]
    person_name = most_person[0] or "N/A"
    day_name = busiest[0] or "N/A"
    return (
        f"- People/groups messaged: {total_people}\n"
        f"- Messages sent by me: {total_messages}\n"
        f"- Most messaged person: {person_name} ({most_person[1]} messages)\n"
        f"- Day with most volume: {day_name} ({busiest[1]} interactions)"
    )


# --- Prompt rendering / reply collection ---------------------------------------

def render_prompt(template_name: str, substitutions: dict) -> str:
    template = (PROMPTS_DIR / template_name).read_text(encoding="utf-8")
    for key, val in substitutions.items():
        template = template.replace(f"{{{{{key}}}}}", val)
    return template


def emit_prompt(rendered: str):
    SCRATCH_PROMPT_PATH.write_text(rendered, encoding="utf-8")
    print("\n" + "=" * 70)
    print(f"Copy the prompt below (also saved to {SCRATCH_PROMPT_PATH}) into Teams/Outlook Copilot:")
    print("=" * 70)
    print(rendered)
    print("=" * 70 + "\n")


def wait_for_user(message: str):
    """Block with a popup so the user has time to run the prompt in Copilot before being
    asked to pick the reply file."""
    import tkinter as tk
    from tkinter import messagebox

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showinfo("Communications Summary Generator", message, parent=root)
    root.destroy()


def pick_reply_file(title: str) -> Path:
    """Pop up a native file-open dialog so the user can select the .md file Copilot saved."""
    import tkinter as tk
    from tkinter import filedialog

    cfg = load_config() or {}
    initial_dir = cfg.get("last_browse_dir") or str(Path.home() / "Downloads")
    if not Path(initial_dir).is_dir():
        initial_dir = str(Path.home())

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path_str = filedialog.askopenfilename(
        title=title,
        initialdir=initial_dir,
        filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
    )
    root.destroy()

    if not path_str:
        print("No file selected. Cancelling.")
        sys.exit(1)

    picked = Path(path_str)
    update_config(last_browse_dir=str(picked.parent))
    return picked


def collect_reply(input_file: str = None) -> str:
    if input_file:
        return Path(input_file).read_text(encoding="utf-8")
    wait_for_user(
        "Paste the prompt into Copilot (Teams/Outlook) and save its reply as a .md file.\n\n"
        "Click OK once that file is ready, then select it in the dialog that follows."
    )
    path = pick_reply_file("Select the Copilot reply Markdown file")
    print(f"Reading reply from: {path}")
    return path.read_text(encoding="utf-8")


# --- Report generation ----------------------------------------------------------

def generate_weekly(root: Path, anchor: date, input_file: str):
    start, end = week_range(anchor)
    substitutions = {
        "START_DATE": start.isoformat(),
        "END_DATE": end.isoformat(),
        "RANGE_LABEL": week_label(start, end),
    }
    emit_prompt(render_prompt("weekly_prompt_template.md", substitutions))
    reply = collect_reply(input_file)
    sections = split_sections(reply)
    validate_sections(sections, "the pasted reply")

    title = f"# Weekly Communications Report ({start.isoformat()} - {end.isoformat()})"
    body = reply.strip()
    out_path = root / "Weekly_Reports" / report_filename(start, end, "Weekly")
    out_path.write_text(f"{title}\n\n{body}\n", encoding="utf-8")
    print(f"Saved: {out_path}")


ROLLUP_CONFIGS = {
    "monthly": {
        "type_label": "Monthly",
        "period_type": "monthly",
        "own_folder": "Monthly_Reports",
        "range_fn": month_range,
        "sub_type_label": "Weekly",
        "sub_folder": "Weekly_Reports",
        "sub_periods_fn": lambda start, end: weeks_overlapping(start, end),
        "sub_label_fn": week_label,
    },
    "yearly": {
        "type_label": "Yearly",
        "period_type": "yearly",
        "own_folder": "Yearly_Reports",
        "range_fn": year_range,
        "sub_type_label": "Monthly",
        "sub_folder": "Monthly_Reports",
        "sub_periods_fn": lambda start, end: months_of_year(start.year),
        "sub_label_fn": month_label,
    },
}


def generate_rollup(root: Path, anchor: date, input_file: str, level: str):
    cfg = ROLLUP_CONFIGS[level]
    start, end = cfg["range_fn"](anchor)
    sub_periods = cfg["sub_periods_fn"](start, end)
    sub_folder = root / cfg["sub_folder"]

    missing = []
    sub_reports = []
    for sub_start, sub_end in sub_periods:
        sub_path = sub_folder / report_filename(sub_start, sub_end, cfg["sub_type_label"])
        if not sub_path.exists():
            missing.append(cfg["sub_label_fn"](sub_start, sub_end))
        else:
            sub_reports.append((sub_start, sub_end, sub_path))

    if missing:
        print(f"Cannot generate {cfg['type_label']} report: missing {cfg['sub_type_label']} report(s) for:")
        for label in missing:
            print(f"  - {label}")
        print(f"Generate those {cfg['sub_type_label']} reports first, then retry. Cancelling.")
        sys.exit(1)

    parsed = []
    for sub_start, sub_end, sub_path in sub_reports:
        text = sub_path.read_text(encoding="utf-8")
        sections = split_sections(text)
        validate_sections(sections, sub_path.name)
        parsed.append((cfg["sub_label_fn"](sub_start, sub_end), sections))

    detailed_summary = "\n\n".join(
        f"### {label}\n\n{sections.get('Global Summary', '_No summary available._')}" for label, sections in parsed
    )
    tasks_mentioned = "\n\n".join(
        f"### {label}\n\n{sections.get('Tasks Mentioned', '_No tasks recorded._')}" for label, sections in parsed
    )
    metrics_list = [parse_metrics(sections.get("Metrics", "")) for _, sections in parsed]
    metrics_block = aggregate_metrics(metrics_list)

    sub_summaries_text = "\n\n".join(
        f"**{label}**\n{sections.get('Global Summary', '_No summary available._')}" for label, sections in parsed
    )
    rollup_substitutions = {
        "PERIOD_TYPE": cfg["period_type"],
        "START_DATE": start.isoformat(),
        "END_DATE": end.isoformat(),
        "RANGE_LABEL": f"{start.isoformat()} - {end.isoformat()}",
        "SUB_SUMMARIES": sub_summaries_text,
    }
    emit_prompt(render_prompt("rollup_prompt_template.md", rollup_substitutions))
    global_summary = collect_reply(input_file).strip()

    title = f"# {cfg['type_label']} Communications Report ({start.isoformat()} - {end.isoformat()})"
    body = (
        f"## Global Summary\n\n{global_summary}\n\n"
        f"## Detailed Summary\n\n{detailed_summary}\n\n"
        f"## Tasks Mentioned\n\n{tasks_mentioned}\n\n"
        f"## Metrics\n\n{metrics_block}\n"
    )
    out_path = root / cfg["own_folder"] / report_filename(start, end, cfg["type_label"])
    out_path.write_text(f"{title}\n\n{body}", encoding="utf-8")
    print(f"Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate Communications Summary reports from Copilot (Teams/Outlook) replies saved as Markdown files."
    )
    parser.add_argument(
        "--type", 
        choices=["weekly", "monthly", "yearly"], 
        help="Report type to generate.")
    parser.add_argument(
        "--date", 
        help="Anchor date (YYYY-MM-DD) within the desired period. Defaults to today.")
    parser.add_argument(
        "--input-file",
        help="Path to the Copilot reply .md file, instead of picking it via the file-open dialog.",
    )
    parser.add_argument(
        "--set-root",
        metavar="PATH",
        help="Repoint the report storage root to PATH (recreates empty folder skeleton; does not migrate old files).",
    )
    args = parser.parse_args()

    if args.set_root:
        set_root(args.set_root)
        return

    if not args.type:
        parser.error("--type is required unless --set-root is used.")

    anchor = date.fromisoformat(args.date) if args.date else date.today()
    root = get_report_root()

    if args.type == "weekly":
        generate_weekly(root, anchor, args.input_file)
    else:
        generate_rollup(root, anchor, args.input_file, args.type)


if __name__ == "__main__":
    main()
