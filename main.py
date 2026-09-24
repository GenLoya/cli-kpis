"""CLI that fills the Weekly Development Summary PPTX template from a per-week folder.

A weekly folder looks like:
    .config/my-kpis/kpi-2026-09-25/
    ├── weekly_summary_2026-09-25.json   (input)
    └── weekly_summary_2026-09-25.pptx   (output, generated next to the JSON)

Usage:
    uv run main.py .config/my-kpis/kpi-2026-09-25/
    uv run main.py .config/my-kpis/kpi-2026-09-25/ -t template.pptx
"""

import argparse
import copy
import json
import sys
import tempfile
import zipfile
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


def derive_paths(folder: Path) -> tuple[Path, Path]:
    """Return (json_path, pptx_path) derived from the weekly folder contents."""
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
    json_path = candidates[0]
    return json_path, json_path.with_suffix(".pptx")


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
            "(default: same folder, same basename as the .json)"
        ),
    )
    parser.add_argument(
        "-t", "--template", default="template.pptx", help="Template .pptx path"
    )
    args = parser.parse_args()

    json_path, default_pptx = derive_paths(Path(args.folder))
    data = load_and_validate(json_path)
    output_path = Path(args.output) if args.output else default_pptx
    fill_template(Path(args.template), data, output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
