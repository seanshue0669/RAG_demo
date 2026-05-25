"""One-shot script to generate all fake datasets and serialize them to JSON.

Usage:
    # From the project root (recommended):
    python -m backend.data_gen.run_all

    # Or directly:
    python backend/data_gen/run_all.py

Both forms are supported. The script:
    1. Ensures all configured directories exist.
    2. Invokes each generator with a deterministic seed.
    3. Writes the resulting record lists to `data/generated/*.json`.
    4. Prints a small summary table to stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Callable

# Make `backend.config.settings` importable when this file is executed both as
# a module and as a script.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.config.settings import get_settings  # noqa: E402
from backend.data_gen import (  # noqa: E402
    generate_employees,
    generate_internal_docs,
    generate_poisoned_docs,
    generate_public_docs,
)


# Deterministic seeds — one per generator so each dataset is reproducible
# independently of the others.
_SEED_EMPLOYEES: int = 42
_SEED_INTERNAL: int = 43
_SEED_PUBLIC: int = 44
_SEED_POISONED: int = 45


def _write_json(records: list[dict[str, Any]], path: Path) -> None:
    """Serialize a record list to disk as a UTF-8 JSON array.

    Args:
        records: The record dicts to serialize.
        path: Destination file path. Parent directories must already exist.
    """
    path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _run_one(
    label: str,
    filename: str,
    fn: Callable[[int, int | None], list[dict[str, Any]]],
    n: int,
    seed: int,
    out_dir: Path,
) -> tuple[str, str, int]:
    """Run a single generator and write its output.

    Args:
        label: Human-readable label shown in the summary table.
        filename: Output filename (relative to `out_dir`).
        fn: The generator callable; must accept `(n, seed)` and return records.
        n: Number of records to produce.
        seed: Seed value passed to the generator.
        out_dir: Output directory.

    Returns:
        A tuple of `(label, filename, count)` for the summary table.
    """
    records = fn(n, seed)
    _write_json(records, out_dir / filename)
    return (label, filename, len(records))


def _print_summary(rows: list[tuple[str, str, int]], out_dir: Path) -> None:
    """Print a fixed-width summary table to stdout.

    Args:
        rows: Result rows produced by `_run_one`.
        out_dir: The output directory (printed in the header).
    """
    print(f"\nGenerated data written to: {out_dir}")
    print("-" * 60)
    print(f"{'Dataset':<22} {'File':<24} {'Count':>6}")
    print("-" * 60)
    for label, filename, count in rows:
        print(f"{label:<22} {filename:<24} {count:>6}")
    print("-" * 60)
    print(f"{'TOTAL':<22} {'':<24} {sum(r[2] for r in rows):>6}\n")


def main() -> None:
    """Generate all four datasets and write them to `DATA_GENERATED_DIR`."""
    settings = get_settings()
    settings.ensure_dirs()

    out_dir = settings.DATA_GENERATED_DIR

    rows: list[tuple[str, str, int]] = [
        _run_one(
            "Employees (L3)",
            "employees.json",
            generate_employees.generate,
            settings.NUM_EMPLOYEES,
            _SEED_EMPLOYEES,
            out_dir,
        ),
        _run_one(
            "Internal docs (L2)",
            "internal_docs.json",
            generate_internal_docs.generate,
            settings.NUM_INTERNAL_DOCS,
            _SEED_INTERNAL,
            out_dir,
        ),
        _run_one(
            "Public docs (L1)",
            "public_docs.json",
            generate_public_docs.generate,
            settings.NUM_PUBLIC_DOCS,
            _SEED_PUBLIC,
            out_dir,
        ),
        _run_one(
            "Poisoned docs (L1)",
            "poisoned_docs.json",
            generate_poisoned_docs.generate,
            settings.NUM_POISONED_DOCS,
            _SEED_POISONED,
            out_dir,
        ),
    ]

    _print_summary(rows, out_dir)


if __name__ == "__main__":
    main()
