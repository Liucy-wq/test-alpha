#!/usr/bin/env python3
"""Validate and append a bbox edit manifest for image-slides projects."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime
from pathlib import Path


SIZE_RE = re.compile(r"^-\s*size:\s*(\d+)x(\d+)\s*$", re.MULTILINE)


def read_canvas_size(project: Path) -> tuple[int, int]:
    lock = project / "render_lock.md"
    if not lock.exists():
        raise SystemExit(f"Missing render_lock.md: {lock}")
    match = SIZE_RE.search(lock.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit("render_lock.md missing canvas size line like '- size: 1920x1080'")
    return int(match.group(1)), int(match.group(2))


def validate_bbox(bbox: dict, width: int, height: int) -> None:
    for key in ("x", "y", "w", "h"):
        if key not in bbox:
            raise SystemExit(f"bbox missing {key!r}")
        if not isinstance(bbox[key], int):
            raise SystemExit(f"bbox.{key} must be an integer")
    if bbox["w"] <= 0 or bbox["h"] <= 0:
        raise SystemExit("bbox width/height must be positive")
    if bbox["x"] < 0 or bbox["y"] < 0:
        raise SystemExit("bbox x/y must be non-negative")
    if bbox["x"] + bbox["w"] > width or bbox["y"] + bbox["h"] > height:
        raise SystemExit(f"bbox exceeds canvas {width}x{height}")


def load_manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("page", "image", "bbox", "prompt"):
        if key not in data:
            raise SystemExit(f"manifest missing {key!r}")
    data.setdefault("scope", "local")
    if data["scope"] not in {"local", "local_plus_style", "global"}:
        raise SystemExit("scope must be local, local_plus_style, or global")
    return data


def append_edit(project: Path, manifest_path: Path, copy_previous: bool) -> Path:
    width, height = read_canvas_size(project)
    data = load_manifest(manifest_path)
    validate_bbox(data["bbox"], width, height)

    image_path = project / data["image"]
    if not image_path.exists():
        raise SystemExit(f"Image not found: {image_path}")

    page = data["page"]
    edits_dir = project / "edits"
    drafts_dir = project / "drafts"
    edits_dir.mkdir(exist_ok=True)
    drafts_dir.mkdir(exist_ok=True)

    edit_log = edits_dir / f"{page}_edits.json"
    existing = json.loads(edit_log.read_text(encoding="utf-8")) if edit_log.exists() else {"edits": []}
    edit_id = f"{page}-E{len(existing['edits']) + 1:02d}"
    before_path = drafts_dir / f"{Path(data['image']).stem}_before_{edit_id}{image_path.suffix}"
    if copy_previous:
        shutil.copy2(image_path, before_path)

    record = {
        "edit_id": edit_id,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "page": page,
        "input_image": str(before_path.relative_to(project)) if copy_previous else data["image"],
        "output_image": data["image"],
        "bbox": data["bbox"],
        "prompt": data["prompt"],
        "scope": data["scope"],
        "status": "pending",
        "qa": [],
    }
    existing["edits"].append(record)
    edit_log.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return edit_log


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("manifest")
    parser.add_argument("--no-copy-previous", action="store_true")
    args = parser.parse_args()

    path = append_edit(Path(args.project), Path(args.manifest), not args.no_copy_previous)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

