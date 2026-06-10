#!/usr/bin/env python3
"""Initialize an image-slides project directory."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path


FORMATS = {
    "slide169": ("1920x1080", 1920, 1080),
    "slide43": ("1600x1200", 1600, 1200),
    "story": ("1080x1920", 1080, 1920),
    "square": ("1600x1600", 1600, 1600),
}


def slugify(value: str) -> str:
    out = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in value.strip())
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("._") or "image_slides_project"


def init_project(name: str, fmt: str, base_dir: Path) -> Path:
    if fmt not in FORMATS:
        raise SystemExit(f"Unsupported format {fmt!r}. Available: {', '.join(FORMATS)}")

    date = datetime.now().strftime("%Y%m%d")
    project_path = base_dir / f"{slugify(name)}_{fmt}_{date}"
    if project_path.exists():
        raise SystemExit(f"Project already exists: {project_path}")

    for dirname in ("sources", "data", "slides", "drafts", "edits", "exports"):
        (project_path / dirname).mkdir(parents=True, exist_ok=True)

    size, width, height = FORMATS[fmt]
    (project_path / "render_lock.md").write_text(
        "\n".join(
            [
                "# Render Lock",
                "",
                "## canvas",
                f"- format: {fmt}",
                f"- size: {size}",
                "- safe_margin: 72",
                "",
                "## master",
                "- layout_family: institutional_finance",
                "- logo_policy: user_or_template_only",
                "- footer_required: true",
                "- source_note_required: true",
                "- page_number_required: true",
                "",
                "## style",
                "- rendering: swiss_investment_research_infographic",
                "- palette: deep_blue_bluegray_orange_teal",
                "- primary: #194F90",
                "- accent: #E07A5F",
                "- secondary: #6D8EB3",
                "- teal: #2A9D8F",
                "- grid: #DDE3EA",
                "- positive: #138A36",
                "- negative: #C62828",
                "- text: #111827",
                "- background: #FFFFFF",
                "- typography: compact sans with tabular numerals",
                "",
                "## data_policy",
                "- image_model_may_invent_numbers: false",
                "- chart_table_text_source: deck_plan/data only",
                "- exact_text_threshold_words: 40",
                "- deterministic_overlay_required_for_tables: true",
                "",
                "## page_rhythm",
                "- P01: anchor",
                "",
                "## pages",
                "- P01: cover",
                "",
                "## forbidden",
                "- invented numbers",
                "- fake source notes",
                "- fake logos",
                "- unreadable small text",
                "- changing pixels outside bbox for local edits",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (project_path / "deck_plan.md").write_text("# Deck Plan\n\n", encoding="utf-8")
    (project_path / "deck_plan.json").write_text(
        json.dumps({"project": name, "format": fmt, "canvas": {"width": width, "height": height}, "pages": []}, indent=2),
        encoding="utf-8",
    )
    (project_path / "data_audit.md").write_text("# Data Audit\n\n", encoding="utf-8")
    return project_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--format", default="slide169", choices=sorted(FORMATS))
    parser.add_argument("--dir", default="projects")
    args = parser.parse_args()

    path = init_project(args.name, args.format, Path(args.dir))
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
