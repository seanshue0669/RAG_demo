"""RAG retriever for the Cloud RAG Security Demo.

This module encapsulates the "embed -> vector search -> optional access
control filter" pipeline used by the FastAPI query endpoint and by the
attack/defense modules.

Two modes are supported:

* ``use_filter=True`` (default, "defended" path): the caller's role is
  mapped to a `security_level` via :meth:`Settings.role_to_level`, and the
  ChromaDB query is restricted to documents at or below that level. Per
  ``CLAUDE.md`` and ``ChromaStore.query_with_filter``, the comparison is
  *downward-inclusive* (``<=``): a ``manager`` (level 2) sees levels 1 and
  2, an ``hr_admin`` (level 3) sees levels 1, 2 and 3.

* ``use_filter=False`` (Act 2 attack demo): the access-control predicate
  is intentionally bypassed so the demo can show how a vector store with
  no metadata filter leaks higher-tier documents to lower-tier roles.

Typical usage:

    from backend.rag.retriever import get_retriever

    retriever = get_retriever()
    docs = retriever.retrieve("年度業績報告", user_role="manager")
"""

from __future__ import annotations

from functools import lru_cache

from backend.config.settings import get_settings
from backend.embedding.embedder import Embedder, get_embedder
from backend.vectordb.chroma_store import ChromaStore, RetrievedDoc


class Retriever:
    """Encapsulates embed -> vector search -> optional access-control filter.

    The retriever owns references to an :class:`Embedder` and a
    :class:`ChromaStore`. Both dependencies can be injected (useful for
    tests and for the Act 2 attack module, which may want to swap stores);
    when omitted, defaults from :func:`get_embedder` and a freshly
    constructed :class:`ChromaStore` are used.

    Attributes:
        store: The vector store used for similarity search.
        embedder: The text -> embedding wrapper.
    """

    def __init__(
        self,
        store: ChromaStore | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        """Initialise the retriever with optional dependency injection.

        Args:
            store: Pre-built :class:`ChromaStore`. When ``None``, a default
                :class:`ChromaStore` is constructed using the global
                :class:`Settings`.
            embedder: Pre-built :class:`Embedder`. When ``None``, the
                module-level singleton from :func:`get_embedder` is used so
                the underlying sentence-transformers model is loaded at
                most once per process.
        """
        self.store: ChromaStore = store if store is not None else ChromaStore()
        self.embedder: Embedder = embedder if embedder is not None else get_embedder()
        self._settings = get_settings()

    def retrieve(
        self,
        query: str,
        user_role: str,
        use_filter: bool = True,
        top_k: int = 5,
    ) -> list[RetrievedDoc]:
        """Run the full retrieval pipeline for a single query.

        Steps:
          1. Encode ``query`` into an embedding via :meth:`Embedder.encode`.
          2. If ``use_filter`` is ``True``, resolve ``user_role`` to a
             ``max_security_level`` via :meth:`Settings.role_to_level` and
             call :meth:`ChromaStore.query_with_filter`.
          3. Otherwise call :meth:`ChromaStore.query` directly. This path
             intentionally has *no access control* and is used by the Act 2
             attack demo to illustrate the consequences of missing
             metadata filtering.
          4. Return the resulting list of :class:`RetrievedDoc` exactly as
             produced by :class:`ChromaStore` (ordered most-similar first).

        Args:
            query: Natural-language user query.
            user_role: Role name; must be a key of
                :attr:`Settings.ROLE_TO_LEVEL`
                (``"employee"`` / ``"manager"`` / ``"hr_admin"``). Only
                consulted when ``use_filter`` is ``True``.
            use_filter: When ``True`` (the default), apply the
                downward-inclusive ``security_level`` filter derived from
                ``user_role``. When ``False``, skip access control entirely
                -- used by the Act 2 attack module.
            top_k: Maximum number of documents to return.

        Returns:
            A list of :class:`RetrievedDoc`, ordered from most to least
            similar. When ``use_filter`` is ``True``, every entry satisfies
            ``security_level <= settings.role_to_level(user_role)``.

        Raises:
            KeyError: If ``use_filter`` is ``True`` and ``user_role`` is not
                a recognised role.
        """
        embedding = self.embedder.encode(query)

        if use_filter:
            max_level = self._settings.role_to_level(user_role)
            return self.store.query_with_filter(
                query_embedding=embedding,
                top_k=top_k,
                max_security_level=max_level,
            )

        # Act 2 attack path: deliberately no access control.
        return self.store.query(query_embedding=embedding, top_k=top_k)


@lru_cache(maxsize=1)
def get_retriever() -> Retriever:
    """Return a process-wide singleton :class:`Retriever` instance.

    The instance uses the default :class:`ChromaStore` and the shared
    :class:`Embedder` from :func:`get_embedder`. Subsequent calls return
    the same object, so the underlying model and ChromaDB collection are
    opened at most once per process.

    Returns:
        The shared :class:`Retriever` instance.
    """
    return Retriever()


__all__: list[str] = ["Retriever", "get_retriever"]
