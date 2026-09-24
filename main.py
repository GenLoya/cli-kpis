"""CLI that fills the Weekly Development Summary PPTX template from a JSON file.

Usage:
    uv run main.py data.json
    uv run main.py data.json -o out.pptx -t template.pptx
"""

import argparse
import copy
import json
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

OUTPUT_DIR = Path("my-kpis")
OUTPUT_FILENAME = "weekly_summary_{friday}.pptx"
FRIDAY_WEEKDAY = 4  # Python weekday(): Monday=0 .. Sunday=6


def friday_of(today: date) -> date:
    """Return the Friday of the ISO week `today` belongs to (next Fri on Sat/Sun)."""
    return today + timedelta(days=(FRIDAY_WEEKDAY - today.weekday()) % 7)


def expand_placeholders(name: str, today: date) -> str:
    """Replace supported placeholders. Currently {friday} → ISO date of Friday."""
    return name.replace("{friday}", friday_of(today).isoformat())


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


def default_output_path(config: dict, today: date | None = None) -> Path:
    """Compute the default output path using config keys with hardcoded fallbacks."""
    if today is None:
        today = date.today()
    output_dir = Path(config.get("output_dir", str(OUTPUT_DIR)))
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = expand_placeholders(
        config.get("output_filename", OUTPUT_FILENAME),
        today,
    )
    return output_dir / filename


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
        description="Fill a Weekly Development Summary PPTX from a JSON file."
    )
    parser.add_argument(
        "input",
        help="JSON file with keys: last_week, this_week, roadblocks, key_objectives",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output .pptx path (default: from config.json or ./my-kpis/weekly_summary_<friday>.pptx)",
    )
    parser.add_argument(
        "-c",
        "--config",
        default="config.json",
        help="Path to config JSON file (default: config.json)",
    )
    parser.add_argument(
        "-t", "--template", default="template.pptx", help="Template .pptx path"
    )
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    config = load_config(Path(args.config))
    output_path = Path(args.output) if args.output else default_output_path(config)
    fill_template(Path(args.template), data, output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
