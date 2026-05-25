"""Act 4 embedding-inversion attack: pre-recorded Vec2Text result loader.

Per CLAUDE.md Vec2Text rules, the inversion itself is **not** computed at
demo time. The heavy lifting happens out-of-band in
`scripts/prepare_vec2text.py`, which writes two JSON files into
`data/prerecorded/`:

  * ``vec2text_attack_results.json`` — successful inversions against
    plaintext-stored embeddings. This is the attacker's view of a
    cloud-hosted vector DB without HE protection.
  * ``vec2text_encrypted_fail.json`` — same Vec2Text pipeline applied to
    CKKS-encrypted embeddings; the inverter only sees noise and emits
    gibberish. This motivates the HE defense.

This module is a thin loader / formatter that the FastAPI layer can use to
populate an `Act4AttackResponse`. It also exposes a helper for the optional
"live attacker view" — fetching the raw plaintext embedding for a doc from
ChromaDB. That helper does **not** run inversion; it simply demonstrates
what an attacker who breached a non-HE-protected vector DB would walk away
with.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from backend.config.settings import get_settings

if TYPE_CHECKING:
    # Only used for type hints — avoids importing ChromaStore (and Chroma)
    # at module import time for callers that just need the JSON loaders.
    from backend.vectordb.chroma_store import ChromaStore


# Filenames of the pre-recorded result bundles inside
# `Settings.DATA_PRERECORDED_DIR`. Kept as module-level constants so other
# modules (e.g. preparation scripts) can reference the same names.
_PLAINTEXT_RESULTS_FILE: str = "vec2text_attack_results.json"
_ENCRYPTED_FAIL_RESULTS_FILE: str = "vec2text_encrypted_fail.json"


def _load_results(filename: str) -> list[dict]:
    """Load and return the ``results`` list from a pre-recorded JSON file.

    Args:
        filename: Bare filename (no directory) under
            `Settings.DATA_PRERECORDED_DIR`.

    Returns:
        The ``results`` list embedded in the JSON document. Returns an
        empty list if the key is missing.

    Raises:
        FileNotFoundError: If the pre-recorded file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    settings = get_settings()
    path = settings.DATA_PRERECORDED_DIR / filename
    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise ValueError(
            f"Pre-recorded file {filename!r} has non-list 'results' field: "
            f"{type(results).__name__}"
        )
    return results


def load_attack_results() -> list[dict]:
    """Load successful Vec2Text inversions against plaintext embeddings.

    These cases represent the attacker's success scenario in Act 4:
    embeddings stored in plaintext can be inverted back to readable
    text, leaking PII (names, departments, titles, employee IDs).

    Returns:
        List of inversion result dicts shaped like `InversionResult`
        (see `backend.api.schemas.InversionResult`): each entry has
        ``doc_id``, ``original_text``, ``inverted_text``,
        ``similarity_score``, ``pii_match``, ``pii_match_rate``.

    Raises:
        FileNotFoundError: If the pre-recorded JSON is missing. Run
            `scripts/prepare_vec2text.py` to generate it.
    """
    return _load_results(_PLAINTEXT_RESULTS_FILE)


def load_encrypted_fail_results() -> list[dict]:
    """Load failed Vec2Text inversions against CKKS-encrypted embeddings.

    These cases represent the defense scenario in Act 4: the attacker
    only sees ciphertext, so the inverter recovers nothing useful —
    typically gibberish stopword salads with PII match rate near zero.

    Returns:
        List of inversion result dicts shaped like `InversionResult`,
        with most/all `pii_match` entries marked `false`.

    Raises:
        FileNotFoundError: If the pre-recorded JSON is missing. Run
            `scripts/prepare_vec2text.py` to generate it.
    """
    return _load_results(_ENCRYPTED_FAIL_RESULTS_FILE)


def get_inversion_comparison() -> dict:
    """Build the Act 4 attack/defense comparison payload.

    The returned dict's keys and value shapes match
    `backend.api.schemas.Act4AttackResponse` so the API layer can pass
    it straight into the Pydantic model.

    Returns:
        A dict with two keys:

          * ``plaintext_inversion``: Result list from
            `load_attack_results()` (attacker succeeds).
          * ``encrypted_inversion``: Result list from
            `load_encrypted_fail_results()` (attacker fails).
    """
    return {
        "plaintext_inversion": load_attack_results(),
        "encrypted_inversion": load_encrypted_fail_results(),
    }


def get_embedding_for_inversion(
    doc_id: str,
    store: "ChromaStore | None" = None,
) -> list[float]:
    """Fetch the raw plaintext embedding for a document from ChromaDB.

    This is the "stolen embedding" that an attacker would feed into a
    Vec2Text inverter in a real breach of a non-HE-protected vector DB.
    The function intentionally does **not** invoke Vec2Text itself —
    per CLAUDE.md, all inversion output is pre-recorded.

    Args:
        doc_id: The target document's stable identifier (e.g.
            ``"EMP-0042"``).
        store: Optional pre-existing `ChromaStore` instance. If `None`,
            a fresh one is constructed with default settings. Reusing
            an existing store avoids re-opening the ChromaDB client.

    Returns:
        The raw embedding vector as a list of Python floats. This is
        what `Settings.EMBEDDING_DIM` floats look like in plaintext —
        exactly what HE is designed to hide.

    Raises:
        KeyError: If no document with the given id exists in the store.
    """
    if store is None:
        # Imported lazily so loader-only callers don't pay the cost of
        # spinning up ChromaDB.
        from backend.vectordb.chroma_store import ChromaStore

        store = ChromaStore()
    return store.get_raw_embedding(doc_id)


__all__: list[str] = [
    "load_attack_results",
    "load_encrypted_fail_results",
    "get_inversion_comparison",
    "get_embedding_for_inversion",
]
