"""ChromaDB persistence wrapper for the Cloud RAG Security Demo.

This module exposes a thin, typed facade around ChromaDB's PersistentClient.
Other backend modules (retriever, seed scripts, attack/defense modules) must
go through `ChromaStore` rather than touching ChromaDB directly so that
collection naming, persistence paths, distance/similarity conversion, and
metadata filter semantics stay centralized.

Per CLAUDE.md, `query_with_filter` uses a "downward-inclusive" comparison
on `security_level` (i.e. `<=`), not equality: a caller with
`max_security_level=2` may retrieve documents at levels 1 and 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection

from backend.config.settings import get_settings


@dataclass
class RetrievedDoc:
    """A single document returned from a vector search.

    Attributes:
        doc_id: Stable identifier for the document (also the ChromaDB id).
        text: Original natural-language text of the document.
        security_level: Access tier (1 = public, 2 = internal, 3 = sensitive).
        department: Owning department code (e.g. "finance", "hr").
        doc_type: Logical document category (e.g. "employee_record",
            "policy_document").
        similarity: Cosine similarity in [-1, 1], derived as `1 - distance`
            from ChromaDB's cosine distance.
    """

    doc_id: str
    text: str
    security_level: int
    department: str
    doc_type: str
    similarity: float


class ChromaStore:
    """Typed facade over a persistent ChromaDB collection.

    The collection is configured with cosine distance (`hnsw:space="cosine"`).
    Because ChromaDB returns *distances*, this wrapper converts each result to
    a similarity score via `similarity = 1 - distance` before handing it back
    to callers.
    """

    def __init__(
        self,
        persist_dir: str | None = None,
        collection_name: str | None = None,
    ) -> None:
        """Initialize the store and open (or create) the underlying collection.

        Args:
            persist_dir: Filesystem path used by ChromaDB's PersistentClient.
                Defaults to `Settings.CHROMA_PERSIST_DIR`.
            collection_name: Name of the ChromaDB collection. Defaults to
                `Settings.CHROMA_COLLECTION_NAME`.
        """
        settings = get_settings()
        self._settings = settings
        self._metadata_keys: dict[str, str] = settings.METADATA_KEYS

        resolved_persist_dir = (
            persist_dir if persist_dir is not None else str(settings.CHROMA_PERSIST_DIR)
        )
        resolved_collection_name = (
            collection_name
            if collection_name is not None
            else settings.CHROMA_COLLECTION_NAME
        )

        # PersistentClient writes the on-disk DB under `path`.
        self._client = chromadb.PersistentClient(path=resolved_persist_dir)

        # Cosine space is required so that `similarity = 1 - distance` is a
        # meaningful cosine similarity in [-1, 1].
        self._collection: Collection = self._client.get_or_create_collection(
            name=resolved_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Write APIs
    # ------------------------------------------------------------------
    def insert(
        self,
        doc_id: str,
        text: str,
        embedding: list[float],
        metadata: dict,
    ) -> None:
        """Insert (or upsert) a single document with its embedding and metadata.

        Args:
            doc_id: Stable document identifier; also used as the ChromaDB id.
            text: Raw document text. Stored both in ChromaDB's `documents`
                slot and inside metadata under `METADATA_KEYS["text"]` for
                convenience when filtering.
            embedding: Pre-computed embedding vector (list of floats).
            metadata: Arbitrary metadata dict. Must minimally contain
                `security_level`, `department`, and `doc_type`. The wrapper
                will copy `text` and `doc_id` in if missing.
        """
        merged_metadata = self._build_metadata(doc_id=doc_id, text=text, metadata=metadata)
        self._collection.upsert(
            ids=[doc_id],
            embeddings=[embedding],
            documents=[text],
            metadatas=[merged_metadata],
        )

    def insert_many(self, records: list[dict]) -> None:
        """Bulk insert (upsert) multiple documents in a single call.

        Args:
            records: A list of dicts; each entry must provide the keys
                `doc_id`, `text`, `embedding`, and `metadata`.
        """
        if not records:
            return

        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict[str, Any]] = []

        for record in records:
            doc_id = record["doc_id"]
            text = record["text"]
            embedding = record["embedding"]
            metadata = record.get("metadata", {})

            ids.append(doc_id)
            embeddings.append(embedding)
            documents.append(text)
            metadatas.append(
                self._build_metadata(doc_id=doc_id, text=text, metadata=metadata)
            )

        self._collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    # ------------------------------------------------------------------
    # Read APIs
    # ------------------------------------------------------------------
    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[RetrievedDoc]:
        """Run an unfiltered top-k nearest-neighbor query.

        Args:
            query_embedding: Embedding vector for the user query.
            top_k: Maximum number of documents to return.

        Returns:
            A list of `RetrievedDoc`, ordered from most to least similar.
        """
        raw = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
        )
        return self._parse_query_result(raw)

    def query_with_filter(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        max_security_level: int = 1,
    ) -> list[RetrievedDoc]:
        """Run a top-k query restricted to documents at or below a security level.

        Per CLAUDE.md the filter is *downward-inclusive*: a caller asking for
        `max_security_level=2` will see documents at levels 1 *and* 2, not
        only level 2.

        Args:
            query_embedding: Embedding vector for the user query.
            top_k: Maximum number of documents to return.
            max_security_level: Inclusive upper bound on
                `security_level`. Defaults to 1 (public tier only).

        Returns:
            A list of `RetrievedDoc`, ordered from most to least similar,
            all having `security_level <= max_security_level`.
        """
        security_level_key = self._metadata_keys["security_level"]
        where_clause: dict[str, Any] = {
            security_level_key: {"$lte": max_security_level}
        }
        raw = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_clause,
        )
        return self._parse_query_result(raw)

    def get_raw_embedding(self, doc_id: str) -> list[float]:
        """Fetch the stored embedding vector for a single document.

        Used by the embedding-inversion attack (Act 4) which needs the raw
        plaintext embedding to feed into Vec2Text.

        Args:
            doc_id: Document identifier.

        Returns:
            The embedding as a list of Python floats.

        Raises:
            KeyError: If no document with the given id exists.
        """
        result = self._collection.get(ids=[doc_id], include=["embeddings"])
        embeddings = result.get("embeddings")
        if not embeddings or len(embeddings) == 0:
            raise KeyError(f"No embedding found for doc_id={doc_id!r}")

        embedding = embeddings[0]
        # ChromaDB may return a numpy array; normalize to list[float].
        return [float(x) for x in embedding]

    def count(self) -> int:
        """Return the number of documents currently in the collection."""
        return self._collection.count()

    def reset(self) -> None:
        """Drop and recreate the collection.

        Useful for re-seeding the demo. The on-disk persistence directory is
        left intact; only the collection contents are cleared.
        """
        collection_name = self._collection.name
        self._client.delete_collection(name=collection_name)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_metadata(
        self,
        doc_id: str,
        text: str,
        metadata: dict,
    ) -> dict[str, Any]:
        """Normalize a caller-provided metadata dict for ChromaDB storage.

        Ensures the canonical metadata keys (defined in `Settings.METADATA_KEYS`)
        are present and populates `doc_id` / `text` from the explicit args
        when they're missing.

        Args:
            doc_id: Document identifier.
            text: Raw document text.
            metadata: Caller-provided metadata dict.

        Returns:
            A new dict safe to pass to ChromaDB's `metadatas` parameter.
        """
        keys = self._metadata_keys
        merged: dict[str, Any] = dict(metadata) if metadata else {}
        merged.setdefault(keys["doc_id"], doc_id)
        merged.setdefault(keys["text"], text)
        return merged

    def _parse_query_result(self, raw: dict[str, Any]) -> list[RetrievedDoc]:
        """Convert ChromaDB's nested query response into `RetrievedDoc`s.

        ChromaDB's `query` returns each field as a list of lists (outer
        list = one entry per query embedding). We always submit a single
        query embedding, so we unwrap the first inner list. The
        `distance -> similarity` conversion (`similarity = 1 - distance`) is
        applied here.

        Args:
            raw: Raw response dict from `collection.query(...)`.

        Returns:
            Ordered list of `RetrievedDoc` (most to least similar).
        """
        keys = self._metadata_keys

        ids_outer = raw.get("ids") or [[]]
        distances_outer = raw.get("distances") or [[]]
        documents_outer = raw.get("documents") or [[]]
        metadatas_outer = raw.get("metadatas") or [[]]

        ids = ids_outer[0] if ids_outer else []
        distances = distances_outer[0] if distances_outer else []
        documents = documents_outer[0] if documents_outer else []
        metadatas = metadatas_outer[0] if metadatas_outer else []

        results: list[RetrievedDoc] = []
        for index, doc_id in enumerate(ids):
            distance = distances[index] if index < len(distances) else 0.0
            document_text = documents[index] if index < len(documents) else ""
            metadata = metadatas[index] if index < len(metadatas) else {}
            metadata = metadata or {}

            # ChromaDB returns cosine *distance*; convert to *similarity*.
            # With `hnsw:space="cosine"`, distance is in [0, 2] and
            # similarity = 1 - distance falls back into [-1, 1].
            similarity = 1.0 - float(distance)

            results.append(
                RetrievedDoc(
                    doc_id=str(doc_id),
                    text=str(document_text or metadata.get(keys["text"], "")),
                    security_level=int(metadata.get(keys["security_level"], 0)),
                    department=str(metadata.get(keys["department"], "")),
                    doc_type=str(metadata.get(keys["doc_type"], "")),
                    similarity=similarity,
                )
            )

        return results


__all__ = ["ChromaStore", "RetrievedDoc"]
