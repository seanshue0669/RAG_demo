"""In-memory CKKS-encrypted embedding store for the Cloud RAG Security Demo.

This module owns the *encrypted* mirror of the document corpus used by the
homomorphic-encryption (Act 4) defence. Per the project's hard rule in
`CLAUDE.md` (§同態加密規則):

    "所有 embedding 在 seed 階段預先加密，加密後存在記憶體中"

Concretely, at seed time the caller hands a list of records (each carrying
a plaintext embedding plus its metadata) to `EncryptedStore.encrypt_all`,
which encrypts every embedding with a shared `CKKSEngine` and keeps the
resulting `CKKSVector` ciphertexts in process memory. Subsequent encrypted
search calls iterate these pre-encrypted vectors and never touch the
plaintext embeddings again.

TenSEAL is intentionally NOT imported at module top-level — see the same
lazy-import strategy used by `ckks_engine.py`. The encrypted embeddings
are typed as `object` / `Any` so this module can be imported in
environments where the native SEAL backend is not yet built.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from backend.config.settings import get_settings
from backend.defenses.he_search.ckks_engine import CKKSEngine

if TYPE_CHECKING:  # pragma: no cover - import only for type checking
    import tenseal as ts  # noqa: F401


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------
@dataclass
class EncryptedDoc:
    """A single document whose embedding has been CKKS-encrypted.

    Plaintext metadata (doc_id, text, security_level, department, doc_type)
    is retained alongside the ciphertext so the encrypted-search pipeline
    can return human-readable results once it has identified the top-k
    matches via encrypted similarity scores. Only the embedding itself is
    encrypted in memory.

    Attributes:
        doc_id: Stable document identifier.
        text: Original natural-language text of the document.
        security_level: Access tier (1 = public, 2 = internal, 3 = sensitive).
        department: Owning department code (e.g. "finance", "hr").
        doc_type: Logical document category (e.g. "employee_record").
        encrypted_embedding: TenSEAL `CKKSVector` ciphertext of the
            embedding. Typed as `object` so this module is importable
            without TenSEAL installed.
    """

    doc_id: str
    text: str
    security_level: int
    department: str
    doc_type: str
    encrypted_embedding: object = field(default=None)


# ---------------------------------------------------------------------------
# EncryptedStore
# ---------------------------------------------------------------------------
class EncryptedStore:
    """In-memory store of CKKS-encrypted document embeddings.

    Per CLAUDE.md, all embeddings are pre-encrypted at seed time and held
    in process memory for the lifetime of the demo. The store does not
    persist to disk: re-seeding the demo simply rebuilds the in-memory
    map.

    Attributes:
        ckks_engine: The `CKKSEngine` used to encrypt embeddings. All
            ciphertexts in this store are bound to its context, which is
            also the context the encrypted-search module uses to encrypt
            query vectors.
    """

    def __init__(self, ckks_engine: CKKSEngine | None = None) -> None:
        """Initialise an empty encrypted store.

        Args:
            ckks_engine: Optional pre-built `CKKSEngine`. When `None`, the
                module-level singleton from
                `backend.defenses.he_search.ckks_engine.get_engine` is
                used. Sharing one engine across the store and the
                encrypted-search module guarantees the query ciphertext
                and the stored ciphertexts share a CKKS context, which
                is required for encrypted dot products.
        """
        if ckks_engine is None:
            # Imported lazily so that constructing an EncryptedStore
            # without TenSEAL installed (e.g. during static analysis or
            # test collection) doesn't fail. The actual engine
            # construction inside `get_engine` will still require
            # TenSEAL.
            from backend.defenses.he_search.ckks_engine import get_engine

            ckks_engine = get_engine()
        self.ckks_engine: CKKSEngine = ckks_engine

        # Settings exposes the canonical metadata key names; we reuse them
        # so that records produced by the seed pipeline (which writes
        # ChromaDB metadata) can be consumed here verbatim.
        self._metadata_keys: dict[str, str] = get_settings().METADATA_KEYS

        self._docs: dict[str, EncryptedDoc] = {}
        self._ready: bool = False

    # ------------------------------------------------------------------
    # Bulk encryption
    # ------------------------------------------------------------------
    def encrypt_all(self, records: list[dict]) -> None:
        """Encrypt every record's embedding and store it in memory.

        The record shape accepted here is intentionally permissive so the
        same dicts written to `data/generated/*_with_emb.json` (and the
        in-memory records produced by the seed pipeline) can be passed
        directly. Each record must minimally contain:

            * ``doc_id``
            * ``text``
            * ``embedding`` (a list of floats, the plaintext embedding)
            * ``security_level``
            * ``department``
            * ``doc_type``

        Metadata fields (``security_level``, ``department``, ``doc_type``)
        may also live inside a nested ``metadata`` dict, mirroring the
        layout used by `ChromaStore.insert_many`; if a top-level key is
        absent, the nested ``metadata`` dict is consulted as a fallback.

        Progress is reported every 10 records so the operator can confirm
        the (relatively expensive) batch encryption is making progress.

        Args:
            records: List of record dicts as described above.

        Raises:
            KeyError: If a record is missing one of the required fields
                (``doc_id``, ``text``, or ``embedding``).
        """
        self._docs.clear()

        total = len(records)
        keys = self._metadata_keys

        for index, record in enumerate(records, start=1):
            metadata = record.get("metadata") or {}

            doc_id = record.get(keys["doc_id"], record.get("doc_id"))
            text = record.get(keys["text"], record.get("text"))
            embedding = record.get("embedding")

            if doc_id is None:
                raise KeyError("record is missing required field 'doc_id'")
            if text is None:
                raise KeyError(
                    f"record {doc_id!r} is missing required field 'text'"
                )
            if embedding is None:
                raise KeyError(
                    f"record {doc_id!r} is missing required field 'embedding'"
                )

            security_level = record.get(
                keys["security_level"],
                metadata.get(keys["security_level"], 0),
            )
            department = record.get(
                keys["department"],
                metadata.get(keys["department"], ""),
            )
            doc_type = record.get(
                keys["doc_type"],
                metadata.get(keys["doc_type"], ""),
            )

            encrypted_embedding = self.ckks_engine.encrypt_vector(embedding)

            self._docs[str(doc_id)] = EncryptedDoc(
                doc_id=str(doc_id),
                text=str(text),
                security_level=int(security_level),
                department=str(department),
                doc_type=str(doc_type),
                encrypted_embedding=encrypted_embedding,
            )

            if index % 10 == 0:
                print(f"Encrypted {index}/{total}...")

        # Always emit a final tally so the operator sees the completion
        # message even when `total` is not a multiple of 10.
        if total % 10 != 0:
            print(f"Encrypted {total}/{total}...")

        self._ready = True

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    def get_encrypted_embedding(self, doc_id: str) -> Any:
        """Return the CKKS-encrypted embedding for a document.

        Args:
            doc_id: Document identifier.

        Returns:
            The TenSEAL `CKKSVector` ciphertext bound to this store's
            CKKS context. Typed as `Any` so the call site does not need
            TenSEAL imported.

        Raises:
            KeyError: If no document with the given id is stored.
        """
        try:
            return self._docs[doc_id].encrypted_embedding
        except KeyError as exc:
            raise KeyError(
                f"No encrypted embedding for doc_id={doc_id!r}"
            ) from exc

    def list_docs(self) -> list[EncryptedDoc]:
        """Return all stored `EncryptedDoc` objects.

        The encrypted-search module iterates this list to compute an
        encrypted dot product against every document. Order is the
        insertion order from `encrypt_all`, which mirrors the order of
        the input records.

        Returns:
            A list of `EncryptedDoc`. Safe to iterate; callers should
            not mutate the returned list.
        """
        return list(self._docs.values())

    def count(self) -> int:
        """Return the number of encrypted documents currently stored.

        Returns:
            The document count.
        """
        return len(self._docs)

    def is_ready(self) -> bool:
        """Return whether `encrypt_all` has been called.

        Returns:
            `True` once `encrypt_all` has completed at least once on this
            instance, `False` otherwise. The encrypted-search endpoint
            uses this to short-circuit with a clear error if the seed
            step was skipped.
        """
        return self._ready


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
_store_singleton: EncryptedStore | None = None


def get_encrypted_store() -> EncryptedStore:
    """Return a process-wide singleton `EncryptedStore`.

    The first call constructs the store (sharing the singleton
    `CKKSEngine`); subsequent calls return the same instance. The
    singleton is intentionally a module-level variable, not
    `functools.lru_cache`, so tests can reset it by clearing
    `_store_singleton` for a fresh store.

    Returns:
        The shared `EncryptedStore` instance.
    """
    global _store_singleton
    if _store_singleton is None:
        _store_singleton = EncryptedStore()
    return _store_singleton


__all__: list[str] = [
    "EncryptedDoc",
    "EncryptedStore",
    "get_encrypted_store",
]
