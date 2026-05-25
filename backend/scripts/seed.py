"""User-facing seed script for the Cloud RAG Security Demo.

This is a thin CLI wrapper around `backend.vectordb.seed_db.seed`. It runs the
canonical seed pipeline end-to-end:

    1. Generate the four Faker-based HR datasets (employees, internal docs,
       public docs, poisoned docs) under ``settings.DATA_GENERATED_DIR``.
       Existing files are reused unless ``--force`` is supplied.
    2. Embed every record's ``text`` field via the shared
       ``sentence-transformers`` embedder (may download the model on the
       first run).
    3. Upsert every record into the persistent ChromaDB collection.

Note on CKKS pre-encryption (CLAUDE.md `§同態加密規則`): all embeddings must
be pre-encrypted at *seed time* and held in process memory. Because this
script is a short-lived CLI process, populating the in-memory
``EncryptedStore`` here would be discarded the moment the script exits. The
encryption is therefore performed automatically when the FastAPI server
starts (the server's lifespan handler calls ``EncryptedStore.encrypt_all``
against the freshly-seeded ChromaDB contents). This script only prints a
reminder of that behaviour after the seed completes.

Usage:

    # Reuse any existing generated JSON files; upsert into ChromaDB.
    python -m backend.scripts.seed

    # Regenerate every dataset and reset the ChromaDB collection first.
    python -m backend.scripts.seed --force

    # Direct invocation also works thanks to the sys.path shim below.
    python backend/scripts/seed.py --force
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path shim
# ---------------------------------------------------------------------------
# Support both `python -m backend.scripts.seed` (where `backend.*` is already
# importable) and `python backend/scripts/seed.py` (where the project root
# must be added to sys.path so the `backend` package is discoverable).
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.vectordb.seed_db import seed  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments for the user-facing seed CLI.

    Args:
        argv: Optional explicit argument list (mainly for tests). When
            ``None``, ``sys.argv[1:]`` is used.

    Returns:
        The parsed ``argparse.Namespace``.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Seed the Cloud RAG Security Demo: generate fake HR data, embed "
            "it with sentence-transformers, and load the result into "
            "ChromaDB. CKKS pre-encryption runs at FastAPI server startup."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Regenerate every dataset even if its JSON file already exists, "
            "and reset the ChromaDB collection before inserting."
        ),
    )
    return parser.parse_args(argv)


def _print_result(result: dict[str, Any]) -> None:
    """Print a concise human-readable summary of a ``seed`` result.

    Args:
        result: The dict returned by ``backend.vectordb.seed_db.seed``.
    """
    print()
    print("Seed complete:")
    for key, value in result.items():
        print(f"  {key}: {value}")
    print()
    print(
        "Note: CKKS pre-encryption will run automatically when the FastAPI "
        "server starts (no separate command needed)."
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Optional explicit argument list (mainly for tests). When
            ``None``, ``sys.argv[1:]`` is used.

    Returns:
        The process exit code (0 on success).
    """
    args = _parse_args(argv)
    result = seed(force=args.force)
    _print_result(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__: list[str] = ["main"]
