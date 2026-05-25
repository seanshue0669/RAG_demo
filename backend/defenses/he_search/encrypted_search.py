"""Encrypted top-k search pipeline for the Cloud RAG Security Demo.

This module orchestrates a CKKS-based homomorphic-encryption search against
the pre-encrypted document store (`EncryptedStore`) built at seed time. It
also runs the equivalent plaintext search against `ChromaStore` so the demo
frontend can render a side-by-side comparison of the two pipelines.

Per CLAUDE.md (`§同態加密規則`), each of the three encrypted-pipeline stages
must be timed independently rather than reported as a single total:

    1. encrypt query embedding         -> ``encrypt_query_ms``
    2. compute encrypted dot products  -> ``compute_similarity_ms``
    3. decrypt similarity scalars      -> ``decrypt_ms``

The plaintext baseline is also wall-clock timed (``plaintext_timing_ms``)
so the operator can visualise the ~3-4 orders of magnitude gap between the
two.

TenSEAL is intentionally NOT imported here, not even lazily. All CKKS
operations are delegated to `CKKSEngine`, which performs its own lazy
`tenseal` import inside its methods. Likewise, the heavy backend imports
(`get_engine`, `get_encrypted_store`, `get_embedder`, `ChromaStore`) are
deferred into the function body so this module is importable in
environments where TenSEAL / ChromaDB are not yet installed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from backend.config.settings import get_settings


# ---------------------------------------------------------------------------
# Public result dataclass
# ---------------------------------------------------------------------------
@dataclass
class EncryptedSearchResult:
    """Container for an encrypted-search call's full output.

    The frontend HEDashboard consumes both the encrypted-pipeline results
    and the plaintext baseline so the audience can see that:

        * the encrypted top-k matches the plaintext top-k (up to CKKS
          approximation error in the scores), and
        * the encrypted pipeline is dramatically slower than the plaintext
          one.

    Attributes:
        results: Top-k results from the encrypted pipeline. Each entry is
            a dict with keys ``doc_id``, ``similarity``, ``text``, and
            ``security_level``.
        timing: Per-stage timing dict with keys ``encrypt_query_ms``,
            ``compute_similarity_ms``, ``decrypt_ms``, ``total_ms`` (all
            floats, in milliseconds).
        plaintext_results: Top-k results from the equivalent plaintext
            search, in the same dict shape as ``results``.
        plaintext_timing_ms: Wall-clock total of the plaintext search,
            in milliseconds.
    """

    results: list[dict]
    timing: dict
    plaintext_results: list[dict]
    plaintext_timing_ms: float


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def encrypted_search(
    query: str | None = None,
    query_embedding: list[float] | None = None,
    top_k: int = 5,
    ckks_engine: Any = None,
    encrypted_store: Any = None,
    embedder: Any = None,
    plaintext_store: Any = None,
) -> EncryptedSearchResult:
    """Run a CKKS-encrypted top-k search and a plaintext baseline.

    The function follows the encrypted-search pipeline mandated by the
    project spec (`docs/cloud-rag-demo-spec.md §四.6`):

        1. Resolve the query embedding. If ``query_embedding`` is not
           provided, the natural-language ``query`` is embedded via
           ``embedder.encode``.
        2. CKKS-encrypt the query vector (timed as ``encrypt_query_ms``).
        3. Compute the encrypted dot product against every document in
           ``encrypted_store`` (timed as ``compute_similarity_ms``).
           Crucially, decryption is *not* performed inside this stage —
           the per-stage timing requirement in CLAUDE.md demands that
           encrypted compute and decrypt are measured separately.
        4. Decrypt all per-document similarity scalars (timed as
           ``decrypt_ms``).
        5. Sort by similarity (descending) and take the top-k.
        6. Run the equivalent plaintext search via ``plaintext_store``
           (timed separately as ``plaintext_timing_ms``).

    Args:
        query: Natural-language query string. Ignored when
            ``query_embedding`` is supplied directly; otherwise embedded
            via ``embedder``. Exactly one of ``query`` or
            ``query_embedding`` must be provided.
        query_embedding: Pre-computed plaintext embedding for the query.
            When ``None``, ``query`` is embedded via the embedder.
        top_k: Number of nearest documents to return from both the
            encrypted and plaintext pipelines.
        ckks_engine: Optional `CKKSEngine` to use for encrypt / compute /
            decrypt. Defaults to the process-wide singleton.
        encrypted_store: Optional `EncryptedStore` holding the
            pre-encrypted document embeddings. Defaults to the
            process-wide singleton.
        embedder: Optional `Embedder` used to embed ``query`` when no
            ``query_embedding`` is provided. Defaults to the
            process-wide singleton.
        plaintext_store: Optional `ChromaStore` used for the plaintext
            baseline. Defaults to a freshly constructed ``ChromaStore``
            using the configured persistence path.

    Returns:
        An ``EncryptedSearchResult`` with the encrypted top-k results,
        per-stage timings (in milliseconds), the plaintext baseline
        results, and the plaintext wall-clock timing.

    Raises:
        ValueError: If neither ``query`` nor ``query_embedding`` is
            provided.
    """
    # Deferred imports: keep this module importable even when TenSEAL or
    # ChromaDB are not yet installed (e.g. during static analysis or when
    # the HE backend is being source-built).
    from backend.defenses.he_search.ckks_engine import get_engine
    from backend.defenses.he_search.encrypted_store import get_encrypted_store
    from backend.embedding.embedder import get_embedder
    from backend.vectordb.chroma_store import ChromaStore

    # Touch settings so the call participates in the standard config flow
    # (and so future per-environment knobs land here without changing the
    # public signature).
    _ = get_settings()

    # ------------------------------------------------------------------
    # Resolve dependencies
    # ------------------------------------------------------------------
    ckks_engine = ckks_engine or get_engine()
    encrypted_store = encrypted_store or get_encrypted_store()
    embedder = embedder or get_embedder()
    plaintext_store = plaintext_store if plaintext_store is not None else ChromaStore()

    # ------------------------------------------------------------------
    # Step 1: resolve query embedding
    # ------------------------------------------------------------------
    if query_embedding is None:
        if query is None:
            raise ValueError(
                "encrypted_search requires either 'query' or 'query_embedding'"
            )
        query_embedding = embedder.encode(query)

    # ------------------------------------------------------------------
    # Step 2: encrypt query (timed independently)
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    enc_query = ckks_engine.encrypt_vector(query_embedding)
    encrypt_query_ms = (time.perf_counter() - t0) * 1000.0

    # ------------------------------------------------------------------
    # Step 3: encrypted dot products (compute only — no decrypt yet)
    # ------------------------------------------------------------------
    docs = encrypted_store.list_docs()

    t0 = time.perf_counter()
    enc_pairs: list[tuple[Any, Any]] = []
    for enc_doc in docs:
        enc_sim = ckks_engine.encrypted_dot_product(
            enc_query, enc_doc.encrypted_embedding
        )
        # Defer decryption until step 4 so the compute timing stays
        # pure encrypted-arithmetic time. Pairing the document with its
        # encrypted similarity lets us recover metadata after sorting.
        enc_pairs.append((enc_doc, enc_sim))
    compute_similarity_ms = (time.perf_counter() - t0) * 1000.0

    # ------------------------------------------------------------------
    # Step 4: decrypt similarity scalars (timed independently)
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    scored: list[tuple[Any, float]] = []
    for enc_doc, enc_sim in enc_pairs:
        score = ckks_engine.decrypt_scalar(enc_sim)
        scored.append((enc_doc, float(score)))
    decrypt_ms = (time.perf_counter() - t0) * 1000.0

    # ------------------------------------------------------------------
    # Step 5: sort + top-k
    # ------------------------------------------------------------------
    scored.sort(key=lambda pair: pair[1], reverse=True)
    top = scored[:top_k]

    results: list[dict] = [
        {
            "doc_id": enc_doc.doc_id,
            "similarity": score,
            "text": enc_doc.text,
            "security_level": enc_doc.security_level,
        }
        for enc_doc, score in top
    ]

    total_ms = encrypt_query_ms + compute_similarity_ms + decrypt_ms
    timing: dict = {
        "encrypt_query_ms": float(encrypt_query_ms),
        "compute_similarity_ms": float(compute_similarity_ms),
        "decrypt_ms": float(decrypt_ms),
        "total_ms": float(total_ms),
    }

    # ------------------------------------------------------------------
    # Step 6: plaintext baseline (timed separately)
    # ------------------------------------------------------------------
    t0 = time.perf_counter()
    plaintext_hits = plaintext_store.query(query_embedding, top_k=top_k)
    plaintext_timing_ms = (time.perf_counter() - t0) * 1000.0

    plaintext_results: list[dict] = [
        {
            "doc_id": hit.doc_id,
            "similarity": float(hit.similarity),
            "text": hit.text,
            "security_level": int(hit.security_level),
        }
        for hit in plaintext_hits
    ]

    return EncryptedSearchResult(
        results=results,
        timing=timing,
        plaintext_results=plaintext_results,
        plaintext_timing_ms=float(plaintext_timing_ms),
    )


__all__: list[str] = ["EncryptedSearchResult", "encrypted_search"]
