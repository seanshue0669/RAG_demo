"""End-to-end seeding pipeline for the Cloud RAG Security Demo.

This module wires together the three preceding stages of the demo
bootstrap into a single callable pipeline:

    1. Generate the four Faker-based HR datasets (employees, internal
       docs, public docs, poisoned docs) under
       `settings.DATA_GENERATED_DIR` if they are missing (or always if
       `force=True`).
    2. Load all generated JSON files, embed their `text` fields using
       the shared `Embedder` singleton, and attach an `embedding` field
       to each record.
    3. Insert every record into the persistent ChromaDB collection via
       the `ChromaStore` wrapper. When `force=True`, the collection is
       reset before insertion to guarantee a clean slate.

Both module (`python -m backend.vectordb.seed_db`) and script
(`python backend/vectordb/seed_db.py`) invocations are supported via a
sys.path shim. The CLI accepts a single `--force` flag.

Typical usage:

    # From Python:
    from backend.vectordb.seed_db import seed
    summary = seed(force=True)

    # From the shell:
    python -m backend.vectordb.seed_db --force
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# sys.path shim
# ---------------------------------------------------------------------------
# Allow this file to be executed both as `python -m backend.vectordb.seed_db`
# (in which case `backend.*` is already importable) and as
# `python backend/vectordb/seed_db.py` (in which case the project root must
# be added to sys.path so the `backend` package is discoverable).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.config.settings import Settings, get_settings  # noqa: E402
from backend.data_gen import (  # noqa: E402
    generate_employees,
    generate_internal_docs,
    generate_poisoned_docs,
    generate_public_docs,
)
from backend.embedding.batch_embed import embed_records  # noqa: E402
from backend.embedding.embedder import get_embedder  # noqa: E402
from backend.vectordb.chroma_store import ChromaStore  # noqa: E402


# Deterministic seeds — must stay aligned with `backend/data_gen/run_all.py`
# so re-seeding produces the exact same corpus.
_SEED_EMPLOYEES: int = 42
_SEED_INTERNAL: int = 43
_SEED_PUBLIC: int = 44
_SEED_POISONED: int = 45


# Ordered tuple of (label, filename, generator-module, count-attr, seed).
# Defined as a function so we resolve counts from a fresh `Settings` instance
# at call time rather than at import time.
def _dataset_specs(
    settings: Settings,
) -> list[tuple[str, str, Callable[[int, int | None], list[dict]], int, int]]:
    """Return the ordered seeding plan for the four datasets.

    Args:
        settings: The active `Settings` instance.

    Returns:
        A list of `(label, filename, generate_fn, count, seed)` tuples in
        the deterministic order used by `run_all.py`.
    """
    return [
        (
            "Employees (L3)",
            "employees.json",
            generate_employees.generate,
            settings.NUM_EMPLOYEES,
            _SEED_EMPLOYEES,
        ),
        (
            "Internal docs (L2)",
            "internal_docs.json",
            generate_internal_docs.generate,
            settings.NUM_INTERNAL_DOCS,
            _SEED_INTERNAL,
        ),
        (
            "Public docs (L1)",
            "public_docs.json",
            generate_public_docs.generate,
            settings.NUM_PUBLIC_DOCS,
            _SEED_PUBLIC,
        ),
        (
            "Poisoned docs (L1)",
            "poisoned_docs.json",
            generate_poisoned_docs.generate,
            settings.NUM_POISONED_DOCS,
            _SEED_POISONED,
        ),
    ]


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


def _load_json(path: Path) -> list[dict[str, Any]]:
    """Load a JSON file containing a list of record dicts.

    Args:
        path: Path to the JSON file.

    Returns:
        The parsed list of records.

    Raises:
        ValueError: If the file does not contain a JSON list.
    """
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError(
            f"{path} must contain a JSON list of records, "
            f"got {type(data).__name__}"
        )
    return data


def _generate_all(
    settings: Settings,
    force: bool,
) -> dict[str, int]:
    """Generate the four datasets and persist them to disk if needed.

    Each generator is invoked when its output JSON is missing or when
    `force=True`. Files that already exist on disk are left untouched
    unless `force` is set.

    Args:
        settings: The active `Settings` instance.
        force: When `True`, always regenerate every dataset.

    Returns:
        A mapping `{filename: record_count}` describing every dataset
        that is now on disk (regardless of whether this call produced it
        or whether it pre-existed).
    """
    counts: dict[str, int] = {}
    for label, filename, generate_fn, n, seed in _dataset_specs(settings):
        out_path = settings.DATA_GENERATED_DIR / filename
        if out_path.exists() and not force:
            # File already on disk: just record its count without
            # regenerating to avoid re-running Faker unnecessarily.
            existing = _load_json(out_path)
            counts[filename] = len(existing)
            print(
                f"  [skip] {label}: {filename} already present "
                f"({len(existing)} records)",
                flush=True,
            )
            continue

        print(f"  [gen]  {label}: producing {n} records -> {filename}", flush=True)
        records = generate_fn(n, seed)
        _write_json(records, out_path)
        counts[filename] = len(records)
    return counts


def _to_chroma_record(raw: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Reshape a flat generated record into the form `ChromaStore` expects.

    Generators emit flat dicts whose top-level keys come from
    `settings.METADATA_KEYS`. `ChromaStore.insert_many` expects each
    record to expose `doc_id`, `text`, `embedding`, and a nested
    `metadata` dict holding the rest. This helper performs that
    repackaging while preserving every original metadata field.

    Args:
        raw: A record dict produced by one of the generators, augmented
            with an `embedding` field.
        settings: The active `Settings` instance (for `METADATA_KEYS`).

    Returns:
        A new dict with the canonical `ChromaStore` shape.
    """
    keys = settings.METADATA_KEYS
    doc_id_key = keys["doc_id"]
    text_key = keys["text"]

    metadata: dict[str, Any] = {
        keys["doc_id"]: raw[doc_id_key],
        keys["doc_type"]: raw[keys["doc_type"]],
        keys["department"]: raw[keys["department"]],
        keys["security_level"]: raw[keys["security_level"]],
        keys["text"]: raw[text_key],
    }

    return {
        "doc_id": raw[doc_id_key],
        "text": raw[text_key],
        "embedding": raw["embedding"],
        "metadata": metadata,
    }


def _tally_levels(records: list[dict[str, Any]], settings: Settings) -> dict[int, int]:
    """Count records grouped by `security_level`.

    Args:
        records: The merged record list (post-embedding).
        settings: The active `Settings` instance (for `METADATA_KEYS`).

    Returns:
        A dict `{security_level: count}` covering levels 1, 2, and 3.
        Levels with zero records are still represented with `0`.
    """
    level_key = settings.METADATA_KEYS["security_level"]
    counts: dict[int, int] = {1: 0, 2: 0, 3: 0}
    for rec in records:
        level = int(rec.get(level_key, 0))
        counts[level] = counts.get(level, 0) + 1
    return counts


def seed(force: bool = False) -> dict[str, Any]:
    """Run the full data-generation -> embedding -> ChromaDB pipeline.

    The pipeline is idempotent by default: if the four generated JSON
    files already exist on disk they are reused as-is, and the ChromaDB
    collection is upserted (not reset). When `force=True`, every dataset
    is regenerated from scratch and the ChromaDB collection is dropped
    and recreated before insertion.

    Args:
        force: When `True`, regenerate all datasets and reset the
            ChromaDB collection before inserting. When `False` (the
            default), reuse any existing JSON files and upsert into the
            existing collection.

    Returns:
        A summary dict with the following shape::

            {
                "generated": {"employees.json": 50, ...},
                "embedded": 88,
                "inserted": 88,
                "level_counts": {1: 18, 2: 20, 3: 50},
            }
    """
    settings = get_settings()
    settings.ensure_dirs()

    # ------------------------------------------------------------------
    # 1. Generate datasets (or reuse existing JSON files).
    # ------------------------------------------------------------------
    print("Generating data...", flush=True)
    generated_counts = _generate_all(settings, force=force)

    # ------------------------------------------------------------------
    # 2. Load every JSON file and merge into a single record list.
    # ------------------------------------------------------------------
    merged: list[dict[str, Any]] = []
    for _, filename, _, _, _ in _dataset_specs(settings):
        path = settings.DATA_GENERATED_DIR / filename
        merged.extend(_load_json(path))

    total = len(merged)
    print(
        f"Embedding {total} documents... "
        f"(this may download the model on first run)",
        flush=True,
    )

    # ------------------------------------------------------------------
    # 3. Embed every record's `text` field.
    # ------------------------------------------------------------------
    embedder = get_embedder()
    embedded = embed_records(merged, embedder=embedder)

    # ------------------------------------------------------------------
    # 4. Open ChromaDB, optionally reset, then bulk insert.
    # ------------------------------------------------------------------
    print("Writing to ChromaDB...", flush=True)
    store = ChromaStore()
    if force:
        store.reset()

    chroma_records = [_to_chroma_record(rec, settings) for rec in embedded]
    store.insert_many(chroma_records)

    level_counts = _tally_levels(embedded, settings)

    print("Done.", flush=True)

    return {
        "generated": generated_counts,
        "embedded": len(embedded),
        "inserted": len(chroma_records),
        "level_counts": level_counts,
    }


def _print_summary(summary: dict[str, Any]) -> None:
    """Print a human-readable summary of the seed result.

    Args:
        summary: The dict returned by `seed()`.
    """
    print("\n" + "=" * 60)
    print("Seed summary")
    print("=" * 60)
    print("Generated files:")
    for filename, count in summary["generated"].items():
        print(f"  {filename:<28} {count:>4} records")
    print(f"\nEmbedded:  {summary['embedded']}")
    print(f"Inserted:  {summary['inserted']}")
    print("Level counts:")
    for level in sorted(summary["level_counts"].keys()):
        print(f"  L{level}: {summary['level_counts'][level]}")
    print("=" * 60 + "\n")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the seed CLI.

    Args:
        argv: Optional explicit argument list (mainly for tests). When
            `None`, `sys.argv[1:]` is used.

    Returns:
        The parsed `argparse.Namespace`.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Generate fake HR data, embed it, and load the result into "
            "ChromaDB. By default, existing JSON files are reused and the "
            "ChromaDB collection is upserted; pass --force to regenerate "
            "everything and reset the collection."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Regenerate all datasets even if their JSON files already "
            "exist, and reset the ChromaDB collection before inserting."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional explicit argument list (mainly for tests). When
            `None`, `sys.argv[1:]` is used.

    Returns:
        The process exit code (0 on success).
    """
    args = _parse_args(argv)
    summary = seed(force=args.force)
    _print_summary(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__: list[str] = ["seed", "main"]
