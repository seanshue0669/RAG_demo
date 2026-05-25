"""Benchmark the CKKS encrypted search against the plaintext baseline.

This script runs a small fixed set of natural-language queries through
``backend.defenses.he_search.encrypted_search.encrypted_search`` and prints a
per-query table of timings:

    * ``enc``   -- query-embedding CKKS encryption time (ms)
    * ``comp``  -- encrypted dot-product compute time over the corpus (ms)
    * ``dec``   -- per-document similarity decryption time (ms)
    * ``total`` -- sum of the three encrypted stages (ms)
    * ``plain`` -- plaintext ChromaDB search wall-clock time (ms)

The encrypted store is populated on-demand if it has not been initialised:
the script loads the four generated JSON dataset files, re-embeds them via
the shared embedder, and feeds the records to
``EncryptedStore.encrypt_all``. This sidesteps the need for the seed
pipeline to persist ``*_with_emb.json`` files and lets the benchmark run
directly after ``python -m backend.scripts.seed`` on a fresh checkout.

Usage:

    # As a module (preferred):
    python -m backend.scripts.benchmark_he

    # Direct invocation also works thanks to the sys.path shim below.
    python backend/scripts/benchmark_he.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path shim
# ---------------------------------------------------------------------------
# Support both `python -m backend.scripts.benchmark_he` and
# `python backend/scripts/benchmark_he.py` by inserting the project root
# into sys.path when needed.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixed query set
# ---------------------------------------------------------------------------
# Five Traditional-Chinese queries spanning the HR demo's typical access
# patterns: leave policy, performance review, employee PII, overtime
# computation, and the employee assistance programme.
QUERIES: list[str] = [
    "公司的請假規定是什麼？",
    "工程部的績效評核流程？",
    "張小明的薪資與聯絡電話",
    "加班費如何計算？",
    "員工協助方案有哪些？",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_generated_records(generated_dir: Path) -> list[dict[str, Any]]:
    """Load every generated dataset JSON and return the merged record list.

    The four canonical dataset filenames (employees, internal docs, public
    docs, poisoned docs) are read if present. Missing files are silently
    skipped so partial seeds still benchmark.

    Args:
        generated_dir: Directory containing the generated JSON files
            (typically ``settings.DATA_GENERATED_DIR``).

    Returns:
        A flat list of record dicts (without ``embedding`` fields).
    """
    filenames = (
        "employees.json",
        "internal_docs.json",
        "public_docs.json",
        "poisoned_docs.json",
    )
    records: list[dict[str, Any]] = []
    for filename in filenames:
        path = generated_dir / filename
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            records.extend(data)
    return records


def _ensure_encrypted_store(store: Any) -> None:
    """Populate the encrypted store from disk if it is empty.

    When the benchmark is invoked in a fresh process the singleton
    ``EncryptedStore`` will be empty (the FastAPI server hasn't run). In
    that case we re-build the plaintext embeddings from the generated JSON
    files and ask the store to encrypt them.

    Args:
        store: The process-wide ``EncryptedStore`` singleton.

    Raises:
        SystemExit: If ChromaDB is empty *and* no generated JSON files are
            available, indicating the user has not run the seed script yet.
    """
    if store.is_ready():
        return

    # Deferred heavy imports keep `python -m backend.scripts.benchmark_he`
    # cheap to fail-fast on missing seed data.
    from backend.config.settings import get_settings
    from backend.embedding.batch_embed import embed_records
    from backend.embedding.embedder import get_embedder
    from backend.vectordb.chroma_store import ChromaStore

    settings = get_settings()

    chroma = ChromaStore()
    if chroma.count() == 0:
        print("ERROR: ChromaDB is empty -- run scripts/seed.py first.")
        sys.exit(1)

    records = _load_generated_records(settings.DATA_GENERATED_DIR)
    if not records:
        print(
            "ERROR: No generated dataset files found under "
            f"{settings.DATA_GENERATED_DIR}. Run scripts/seed.py first."
        )
        sys.exit(1)

    print(f"Embedding {len(records)} documents for encrypted store...")
    embedder = get_embedder()
    embedded = embed_records(records, embedder=embedder)

    print(f"Encrypting {len(embedded)} documents...")
    store.encrypt_all(embedded)


def _run_benchmark() -> int:
    """Run all queries through ``encrypted_search`` and print a timing table.

    Returns:
        The process exit code (0 on success, non-zero on setup failure).
    """
    # Deferred imports so this script can be imported (e.g. for argument
    # parsing in tests) without pulling in TenSEAL / sentence-transformers.
    from backend.defenses.he_search.encrypted_search import encrypted_search
    from backend.defenses.he_search.encrypted_store import get_encrypted_store

    store = get_encrypted_store()
    _ensure_encrypted_store(store)

    print()
    header = (
        f"{'Query':<40s} {'enc':>8s} {'comp':>8s} "
        f"{'dec':>8s} {'total':>8s} {'plain':>8s}"
    )
    print(header)
    print("-" * len(header))

    for query in QUERIES:
        result = encrypted_search(query=query, top_k=5)
        timing = result.timing
        # Truncate the query so the column width stays tidy; the underlying
        # query is still used in full when calling `encrypted_search`.
        label = query if len(query) <= 40 else query[:37] + "..."
        print(
            f"{label:<40s} "
            f"{timing['encrypt_query_ms']:>8.1f} "
            f"{timing['compute_similarity_ms']:>8.1f} "
            f"{timing['decrypt_ms']:>8.1f} "
            f"{timing['total_ms']:>8.1f} "
            f"{result.plaintext_timing_ms:>8.1f}"
        )

    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Unused; accepted for symmetry with other CLI scripts. The
            benchmark currently takes no flags.

    Returns:
        The process exit code (0 on success).
    """
    del argv  # Reserved for future flags (e.g. custom query files).
    return _run_benchmark()


if __name__ == "__main__":
    sys.exit(main())


__all__: list[str] = ["QUERIES", "main"]
