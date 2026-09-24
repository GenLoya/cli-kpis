"""CLI that fills the Weekly Development Summary PPTX template from a per-week folder.

The CLI takes a folder containing a weekly_summary_*.json (input). The output
PPTX location and filename come from config.json — output_dir is resolved to
an absolute path (with ~ expansion) and the filename supports {friday} as
a placeholder.

Usage:
    uv run main.py .config/my-kpis/kpi-2026-09-25/
    uv run main.py .config/my-kpis/kpi-2026-09-25/ -o custom.pptx -c custom-config.json
"""

import argparse
import copy
import json
import os
import sys
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

from lxml import etree

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}
A = "{%s}" % NS["a"]

LABELS = {
    "last_week": "last week",
    "this_week": "this week",
    "roadblocks": "roadblocks",
    "key_objectives": "key objectives",
}

JSON_GLOB = "weekly_summary_*.json"
FRIDAY_WEEKDAY = 4  # Python weekday(): Monday=0 .. Sunday=6

DEFAULT_OUTPUT_DIR = "~/Documents"
DEFAULT_OUTPUT_FILENAME = "weekly_summary_{friday}.pptx"


def friday_of(today: date) -> date:
    """Return the Friday of the ISO week `today` belongs to (next Fri on Sat/Sun)."""
    return today + timedelta(days=(FRIDAY_WEEKDAY - today.weekday()) % 7)


def expand_placeholders(name: str, today: date) -> str:
    """Replace supported placeholders. Currently {friday} → ISO date of Friday."""
    return name.replace("{friday}", friday_of(today).isoformat())


def resolve_output_dir(output_dir: str | Path) -> Path:
    """Expand ~ to user home and resolve to an absolute path."""
    return Path(os.path.expanduser(str(output_dir))).resolve()


def load_config(config_path: Path) -> dict:
    """Load configuration from a JSON file. Returns {} if the file does not exist.

    Raises SystemExit(1) on malformed JSON so we fail loud instead of silently
    falling back when the user did intend to use a config.
    """
    if not config_path.exists():
        return {}
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON in {config_path}: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(config, dict):
        print(
            f"error: {config_path} must contain a JSON object at the top level",
            file=sys.stderr,
        )
        sys.exit(1)
    return config


def resolve_config_path(args: argparse.Namespace) -> Path:
    """Pick which config.json to read.

    Lookup order:
      1. Explicit -c argument (always wins)
      2. ./config.json in the current working directory
      3. config.json next to the executable (set by 'irm' during install)

    Falls through to a non-existent path if nothing is found; load_config()
    will then return {} and the CLI uses hardcoded defaults.
    """
    if "config" in args:
        return Path(args.config)
    cwd_config = Path("config.json")
    if cwd_config.exists():
        return cwd_config
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
    else:
        exe_dir = Path(__file__).resolve().parent
    return exe_dir / "config.json"


def resolve_template_path(args: argparse.Namespace) -> Path:
    """Pick which template.pptx to read.

    Lookup order:
      1. Explicit -t argument (always wins)
      2. ./template.pptx in the current working directory
      3. template.pptx next to the executable (set by 'irm' during install)

    Returns a Path; the caller should .exists()-check it before use.
    """
    if "template" in args:
        return Path(args.template)
    cwd_template = Path("template.pptx")
    if cwd_template.exists():
        return cwd_template
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
    else:
        exe_dir = Path(__file__).resolve().parent
    return exe_dir / "template.pptx"


def default_output_path(config: dict, today: date | None = None) -> Path:
    """Compute the default output path using config keys with hardcoded fallbacks.

    output_dir is resolved to an absolute path (~ expanded). output_filename
    supports {friday} as a placeholder. The directory is created if missing.
    """
    if today is None:
        today = date.today()
    output_dir = resolve_output_dir(config.get("output_dir", DEFAULT_OUTPUT_DIR))
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = expand_placeholders(
        config.get("output_filename", DEFAULT_OUTPUT_FILENAME),
        today,
    )
    return output_dir / filename


def find_json_in(folder: Path) -> Path:
    """Locate the weekly_summary_*.json inside `folder`. Exit 1 on failure."""
    if not folder.is_dir():
        print(f"error: {folder} is not a directory", file=sys.stderr)
        sys.exit(1)
    candidates = sorted(folder.glob(JSON_GLOB))
    if not candidates:
        print(f"error: no {JSON_GLOB} found in {folder}", file=sys.stderr)
        sys.exit(1)
    if len(candidates) > 1:
        print(
            f"warning: multiple {JSON_GLOB} found in {folder}, using {candidates[0].name}",
            file=sys.stderr,
        )
    return candidates[0]


def load_and_validate(json_path: Path) -> dict:
    """Read and strictly validate the weekly JSON. Exit 1 on any failure."""
    try:
        raw = json_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"error: cannot read {json_path}: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON in {json_path}: {e}", file=sys.stderr)
        sys.exit(1)
    if not isinstance(data, dict):
        print(
            f"error: {json_path} must contain a JSON object at the top level",
            file=sys.stderr,
        )
        sys.exit(1)
    missing = [k for k in LABELS if k not in data]
    if missing:
        print(
            f"error: {json_path} is missing required keys: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)
    return data


def cell_header_text(tc):
    p = tc.find("a:txBody/a:p", NS)
    if p is None:
        return ""
    return "".join(t.text or "" for t in p.findall(".//a:t", NS)).strip().lower()


def as_bullets(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def set_cell_bullets(tc, bullets):
    txBody = tc.find("a:txBody", NS)
    paragraphs = txBody.findall("a:p", NS)
    if not paragraphs:
        return
    header_p = paragraphs[0]
    template_p = paragraphs[1] if len(paragraphs) > 1 else header_p

    for p in paragraphs[1:]:
        txBody.remove(p)

    insert_after = header_p
    for text in bullets:
        new_p = copy.deepcopy(template_p)
        for r in new_p.findall("a:r", NS):
            new_p.remove(r)
        for epr in new_p.findall("a:endParaRPr", NS):
            new_p.remove(epr)
        r = etree.SubElement(new_p, A + "r")
        rPr = etree.SubElement(r, A + "rPr")
        rPr.set("lang", "es-MX")
        rPr.set("sz", "1400")
        rPr.set("dirty", "0")
        t = etree.SubElement(r, A + "t")
        t.text = text
        insert_after.addnext(new_p)
        insert_after = new_p


def fill_template(template_path: Path, data: dict, output_path: Path):
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        with zipfile.ZipFile(template_path) as zf:
            zf.extractall(tmp)

        slide_path = tmp / "ppt" / "slides" / "slide1.xml"
        tree = etree.parse(str(slide_path))
        root = tree.getroot()

        matched = set()
        for tc in root.findall(".//a:tbl//a:tc", NS):
            header = cell_header_text(tc)
            for key, label in LABELS.items():
                if header.startswith(label) and key in data:
                    set_cell_bullets(tc, as_bullets(data[key]))
                    matched.add(key)
                    break

        missing = set(LABELS) - matched
        if missing:
            print(
                f"warning: could not locate/fill cells for: {', '.join(sorted(missing))}",
                file=sys.stderr,
            )

        tree.write(
            str(slide_path), xml_declaration=True, encoding="UTF-8", standalone=True
        )

        if output_path.exists():
            output_path.unlink()
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in tmp.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(tmp))


def main():
    parser = argparse.ArgumentParser(
        description="Fill a Weekly Development Summary PPTX from a per-week folder."
    )
    parser.add_argument(
        "folder",
        help=(
            "Folder containing weekly_summary_*.json with keys: "
            "last_week, this_week, roadblocks, key_objectives"
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help=(
            "Override output .pptx path "
            "(default: from config.json's output_dir + output_filename)"
        ),
    )
    parser.add_argument(
        "-c",
        "--config",
        default=argparse.SUPPRESS,
        help=(
            "Path to config JSON file "
            "(default: ./config.json, then <exe-dir>/config.json)"
        ),
    )
    parser.add_argument(
        "-t",
        "--template",
        default=argparse.SUPPRESS,
        help=(
            "Path to template .pptx "
            "(default: ./template.pptx, then <exe-dir>/template.pptx)"
        ),
    )
    args = parser.parse_args()

    json_path = find_json_in(Path(args.folder))
    data = load_and_validate(json_path)
    config = load_config(resolve_config_path(args))
    output_path = Path(args.output) if args.output else default_output_path(config)
    template_path = resolve_template_path(args)
    if not template_path.exists():
        print(
            f"error: template not found: {template_path} "
            "(checked ./template.pptx and <exe-dir>/template.pptx)",
            file=sys.stderr,
        )
        sys.exit(1)
    fill_template(template_path, data, output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
