"""Batch embed generated HR documents and write augmented JSON files.

This script reads the four Faker-generated JSON files from
`settings.DATA_GENERATED_DIR` (`employees.json`, `internal_docs.json`,
`public_docs.json`, `poisoned_docs.json`), calls the shared `Embedder`
on each record's `text` field, attaches the resulting embedding under
the `embedding` key, and writes the augmented records to a NEW file in
the same directory (e.g. `employees_with_emb.json`).

The function `embed_records` is also exported for direct in-process use
by `backend/vectordb/seed_db.py` so that seeding can run without first
materialising the `*_with_emb.json` files on disk.

Run with:

    python -m backend.embedding.batch_embed

or, equivalently:

    python backend/embedding/batch_embed.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

from backend.config.settings import Settings, get_settings
from backend.embedding.embedder import Embedder, get_embedder

# Mapping of input file name -> output file name. Kept ordered so that the
# CLI output is deterministic across runs.
_FILE_MAP: list[tuple[str, str]] = [
    ("employees.json", "employees_with_emb.json"),
    ("internal_docs.json", "internal_docs_with_emb.json"),
    ("public_docs.json", "public_docs_with_emb.json"),
    ("poisoned_docs.json", "poisoned_docs_with_emb.json"),
]


def embed_records(
    records: list[dict],
    embedder: Embedder | None = None,
    batch_size: int = 32,
) -> list[dict]:
    """Attach an `embedding` field to each record in-place-style.

    The function does not mutate the input list; it returns a new list of
    shallow-copied dicts each carrying an extra `embedding` key.

    Args:
        records: A list of dicts. Each dict must contain a `text` key
            holding the natural-language content to embed.
        embedder: Optional `Embedder` to reuse. When `None`, the shared
            singleton from `get_embedder()` is used.
        batch_size: Number of texts to process per model forward pass.

    Returns:
        A new list of dicts, in the same order as `records`, each one
        identical to its input plus an `embedding: list[float]` field.

    Raises:
        KeyError: If any record is missing the `text` field.
    """
    if not records:
        return []
    emb = embedder if embedder is not None else get_embedder()
    texts: list[str] = [rec["text"] for rec in records]
    vectors = emb.encode_batch(texts, batch_size=batch_size)
    augmented: list[dict] = []
    for rec, vec in zip(records, vectors):
        new_rec = dict(rec)
        new_rec["embedding"] = vec
        augmented.append(new_rec)
    return augmented


def _mean_vector_norm(vectors: list[list[float]]) -> float:
    """Compute the mean L2 norm across a batch of vectors.

    Args:
        vectors: A list of embedding vectors.

    Returns:
        The arithmetic mean of the L2 norms. Returns 0.0 for an empty
        input to avoid a ZeroDivisionError.
    """
    if not vectors:
        return 0.0
    total = 0.0
    for v in vectors:
        total += math.sqrt(sum(x * x for x in v))
    return total / len(vectors)


def _process_one_file(
    input_path: Path,
    output_path: Path,
    embedder: Embedder,
) -> tuple[int, float] | None:
    """Embed a single JSON file and write the augmented version.

    Args:
        input_path: Path to the input JSON file (list of records).
        output_path: Path of the file to write.
        embedder: The shared `Embedder` instance.

    Returns:
        A `(num_records, mean_norm)` tuple on success, or `None` if the
        input file is missing.
    """
    if not input_path.exists():
        print(f"  [skip] {input_path.name} not found", flush=True)
        return None

    with input_path.open("r", encoding="utf-8") as fh:
        records = json.load(fh)
    if not isinstance(records, list):
        raise ValueError(
            f"{input_path} must contain a JSON list of records, "
            f"got {type(records).__name__}"
        )

    augmented = embed_records(records, embedder=embedder)
    vectors = [rec["embedding"] for rec in augmented]
    mean_norm = _mean_vector_norm(vectors)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(augmented, fh, ensure_ascii=False, indent=2)

    return len(augmented), mean_norm


def main(settings: Settings | None = None) -> int:
    """CLI entry point: embed every generated JSON file in turn.

    Args:
        settings: Optional settings override (used by tests). Defaults to
            `get_settings()`.

    Returns:
        Process exit code (0 on success, non-zero on hard failure).
    """
    cfg = settings if settings is not None else get_settings()
    embedder = get_embedder()

    print(
        f"[batch_embed] model={embedder.model_name} "
        f"device={embedder.device} dim={embedder.dim}",
        flush=True,
    )
    print(f"[batch_embed] reading from {cfg.DATA_GENERATED_DIR}", flush=True)

    total_records = 0
    for in_name, out_name in _FILE_MAP:
        in_path = cfg.DATA_GENERATED_DIR / in_name
        out_path = cfg.DATA_GENERATED_DIR / out_name
        print(f"[batch_embed] processing {in_name} -> {out_name}", flush=True)
        result = _process_one_file(in_path, out_path, embedder)
        if result is None:
            continue
        count, mean_norm = result
        total_records += count
        print(
            f"  [done] {count} records embedded, "
            f"mean vector norm = {mean_norm:.4f}",
            flush=True,
        )

    print(f"[batch_embed] finished. total records embedded: {total_records}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__: list[str] = ["embed_records", "main"]
