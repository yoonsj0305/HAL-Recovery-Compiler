"""Create a clean HAL Recovery Compiler release ZIP with POSIX entry names."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hal_rc import __release_label__  # noqa: E402

DEFAULT_OUTPUT = ROOT.parent / f"{ROOT.name}-{__release_label__}-github.zip"

EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "artifacts",
    "build",
    "dist",
    "venv",
}


def _included(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    for part in relative.parts:
        if part in EXCLUDED_PARTS:
            return False
        if part.endswith(".egg-info") or part.startswith(".tmp"):
            return False
    return path.suffix not in {".pyc", ".pyo"}


def create_release(output: Path) -> Path:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in ROOT.rglob("*") if path.is_file() and _included(path))
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(ROOT)
            archive_name = PurePosixPath(ROOT.name, *relative.parts).as_posix()
            if "\\" in archive_name:
                raise ValueError(f"release ZIP entry is not POSIX-style: {archive_name}")
            archive.write(path, archive_name)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )
    args = parser.parse_args()
    output = create_release(args.output)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
