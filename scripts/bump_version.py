#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"
CHART = ROOT / "helm" / "data-forge" / "Chart.yaml"
VALUES = ROOT / "helm" / "data-forge" / "values.yaml"
OVERRIDES = ROOT / "helm" / "data-forge" / "overrides.yaml"


def replace_once(text: str, pattern: str, replacement: str, *, file_path: Path) -> str:
    new_text, count = re.subn(pattern, replacement, text, count=1, flags=re.M)
    if count != 1:
        raise SystemExit(f"expected exactly one match for {pattern!r} in {file_path}")
    return new_text


def update_pyproject(version: str) -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    text, count = re.subn(
        r'^(version = ")([^"]+)(")$',
        rf'\g<1>{version}\g<3>',
        text,
        count=2,
        flags=re.M,
    )
    if count != 2:
        raise SystemExit(f"expected exactly two version fields in {PYPROJECT}")
    PYPROJECT.write_text(text, encoding="utf-8")


def update_chart(version: str) -> None:
    text = CHART.read_text(encoding="utf-8")
    text = replace_once(text, r'^(version: )(.+)$', rf'\g<1>{version}', file_path=CHART)
    text = replace_once(text, r'^(appVersion: ")([^"]+)(")$', rf'\g<1>{version}\g<3>', file_path=CHART)
    CHART.write_text(text, encoding="utf-8")


def update_values(version: str) -> None:
    for path in (VALUES, OVERRIDES):
        text = path.read_text(encoding="utf-8")
        text = replace_once(text, r'^(\s*tag: )(.+)$', rf'\g<1>{version}', file_path=path)
        path.write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bump Data-Forge package and chart versions.")
    parser.add_argument("version", help="New release version, for example 0.2.0")
    args = parser.parse_args()

    update_pyproject(args.version)
    update_chart(args.version)
    update_values(args.version)


if __name__ == "__main__":
    main()
