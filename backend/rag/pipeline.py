"""End-to-end RAG pipeline for the Cloud RAG Security Demo.

This module composes the two building blocks of the demo's question
answering flow:

1. :class:`backend.rag.retriever.Retriever` -- embeds the query, runs a
   vector search against ChromaDB, and (optionally) applies the
   downward-inclusive ``security_level`` filter derived from the caller's
   role.
2. :class:`backend.rag.generator.Generator` -- turns the retrieved
   documents into a natural-language answer, either by calling the
   external vLLM endpoint (``mode="llm"``) or by returning a pre-recorded
   scripted response (``mode="scripted"``).

Per ``CLAUDE.md`` §"RAG Pipeline 規則", the pipeline must transparently
fall back from ``"llm"`` to ``"scripted"`` whenever the live LLM call
fails (network error, timeout, unexpected runtime exception). The actual
mode used is echoed back to the caller through
:attr:`schemas.QueryResponse.gen_mode_used` so the frontend can surface
the fallback to the audience.

Typical usage:

    from backend.rag.pipeline import get_pipeline

    pipeline = get_pipeline()
    response = pipeline.run(
        query="今年的休假政策是什麼?",
        user_role="employee",
        use_filter=True,
        gen_mode="llm",
        top_k=5,
    )
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

from backend.api.schemas import Document, GenMode, QueryResponse, UserRole
from backend.config.settings import get_settings

if TYPE_CHECKING:  # pragma: no cover - import-time-only typing aid
    from backend.rag.generator import Generator, GenerationResult
    from backend.rag.retriever import Retriever
    from backend.vectordb.chroma_store import RetrievedDoc


logger = logging.getLogger(__name__)


# Exceptions that should trigger an automatic fallback from ``"llm"`` to
# ``"scripted"``. The spec is intentionally broad here: any failure to
# reach or parse a response from vLLM should degrade gracefully rather
# than propagate a 500 to the frontend.
_LLM_FALLBACK_EXCEPTIONS: tuple[type[BaseException], ...]
try:  # ``httpx`` is the canonical client used by the generator.
    import httpx  # type: ignore[import-not-found]

    _LLM_FALLBACK_EXCEPTIONS = (
        httpx.HTTPError,
        httpx.TimeoutException,
        httpx.ConnectError,
        ConnectionError,
        TimeoutError,
        RuntimeError,
        ValueError,
    )
except ImportError:  # pragma: no cover - fallback when httpx is absent.
    _LLM_FALLBACK_EXCEPTIONS = (
        ConnectionError,
        TimeoutError,
        RuntimeError,
        ValueError,
    )


class RAGPipeline:
    """Full RAG pipeline: query -> retrieve -> generate.

    The pipeline owns references to a :class:`Retriever` and a
    :class:`Generator`. Both dependencies can be injected to support unit
    testing and the Act 2 attack flow, which may want to swap in
    alternative stores or generators; when omitted, the module-level
    singletons from :func:`backend.rag.retriever.get_retriever` and
    :func:`backend.rag.generator.get_generator` are used.

    Attributes:
        retriever: The retriever responsible for embedding the query and
            returning a ranked list of documents.
        generator: The generator responsible for turning the retrieved
            context into a final answer string.
    """

    def __init__(
        self,
        retriever: "Retriever | None" = None,
        generator: "Generator | None" = None,
    ) -> None:
        """Initialise the pipeline with optional dependency injection.

        Args:
            retriever: Pre-built :class:`Retriever`. When ``None``, the
                shared singleton from
                :func:`backend.rag.retriever.get_retriever` is used so the
                underlying embedder model is loaded at most once per
                process.
            generator: Pre-built :class:`Generator`. When ``None``, the
                shared singleton from
                :func:`backend.rag.generator.get_generator` is used.
        """
        if retriever is None:
            from backend.rag.retriever import get_retriever

            retriever = get_retriever()
        if generator is None:
            # Imported lazily so that pipeline imports do not require the
            # generator module to be fully initialised at import time --
            # useful while the two modules are being built in parallel.
            from backend.rag.generator import get_generator

            generator = get_generator()

        self.retriever = retriever
        self.generator = generator
        self._settings = get_settings()

    def run(
        self,
        query: str,
        user_role: str,
        use_filter: bool = True,
        gen_mode: str = "llm",
        top_k: int = 5,
    ) -> QueryResponse:
        """Execute the full retrieve-then-generate pipeline for one query.

        Steps:
          1. Call :meth:`Retriever.retrieve` to obtain a ranked list of
             :class:`RetrievedDoc` objects, honouring ``use_filter`` and
             ``user_role``.
          2. Call :meth:`Generator.generate` with the requested
             ``gen_mode``. If the request was ``"llm"`` and the call
             raises one of the vLLM-related exceptions in
             :data:`_LLM_FALLBACK_EXCEPTIONS`, a warning is logged and
             the generator is retried with ``mode="scripted"``.
          3. Convert each :class:`RetrievedDoc` into a
             :class:`schemas.Document` for the API response.
          4. Assemble a :class:`schemas.QueryResponse`, reporting the
             mode that was *actually* used (which may differ from
             ``gen_mode`` after a fallback).

        Args:
            query: Natural-language user query (Traditional Chinese in
                the demo, but otherwise unconstrained).
            user_role: Role name used to derive the access-control
                ceiling; must be one of ``"employee"`` / ``"manager"`` /
                ``"hr_admin"``.
            use_filter: When ``True`` (the default), apply the
                downward-inclusive ``security_level`` filter. When
                ``False``, bypass access control entirely (Act 2 attack
                path).
            gen_mode: Requested generation mode, ``"llm"`` or
                ``"scripted"``. The pipeline may transparently downgrade
                ``"llm"`` to ``"scripted"`` if the live call fails.
            top_k: Maximum number of documents to retrieve.

        Returns:
            A :class:`schemas.QueryResponse` with the generated answer,
            the retrieved documents, the requested ``user_role``, the
            value of ``use_filter`` actually honoured, and the
            ``gen_mode`` that produced the answer.
        """
        retrieved_docs = self.retriever.retrieve(
            query=query,
            user_role=user_role,
            use_filter=use_filter,
            top_k=top_k,
        )

        generation = self._generate_with_fallback(
            query=query,
            context_docs=retrieved_docs,
            requested_mode=gen_mode,
            user_role=user_role,
        )

        api_docs = [self._to_api_document(doc) for doc in retrieved_docs]

        return QueryResponse(
            answer=generation.answer,
            retrieved_docs=api_docs,
            filter_applied=use_filter,
            user_role=self._coerce_user_role(user_role),
            gen_mode_used=self._coerce_gen_mode(generation.mode_used),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _generate_with_fallback(
        self,
        query: str,
        context_docs: list["RetrievedDoc"],
        requested_mode: str,
        user_role: str,
    ) -> "GenerationResult":
        """Invoke the generator, falling back from ``"llm"`` to ``"scripted"``.

        When ``requested_mode`` is ``"llm"`` and the underlying call
        raises one of :data:`_LLM_FALLBACK_EXCEPTIONS`, a warning is
        logged and the generator is retried in ``"scripted"`` mode. Any
        other request, or any exception from the scripted retry itself,
        is propagated to the caller.

        Args:
            query: User query forwarded to the generator.
            context_docs: Retrieved documents to use as RAG context.
            requested_mode: Mode requested by the caller of
                :meth:`run` -- typically ``"llm"`` or ``"scripted"``.
            user_role: Role name forwarded to the generator (used by
                scripted mode to pick the appropriate canned response).

        Returns:
            The :class:`GenerationResult` produced by either the
            originally requested mode or the scripted fallback.
        """
        try:
            return self.generator.generate(
                query=query,
                context_docs=context_docs,
                mode=requested_mode,
                user_role=user_role,
            )
        except _LLM_FALLBACK_EXCEPTIONS as exc:
            if requested_mode != "llm":
                # Only the ``llm`` path has a documented fallback. Any
                # other failure is treated as a genuine bug.
                raise
            logger.warning(
                "LLM mode failed (%s), falling back to scripted mode", exc
            )
            return self.generator.generate(
                query=query,
                context_docs=context_docs,
                mode="scripted",
                user_role=user_role,
            )

    @staticmethod
    def _to_api_document(doc: "RetrievedDoc") -> Document:
        """Convert a :class:`RetrievedDoc` into an API :class:`Document`.

        The two dataclasses share the same field names, so the conversion
        is a straightforward attribute copy. Defined as a static method
        so it can be reused (and unit-tested) without a pipeline
        instance.

        Args:
            doc: The retrieved document from the vector store.

        Returns:
            A pydantic :class:`schemas.Document` with the same field
            values as ``doc``.
        """
        return Document(
            doc_id=doc.doc_id,
            text=doc.text,
            security_level=doc.security_level,
            similarity=doc.similarity,
            doc_type=doc.doc_type,
            department=doc.department,
        )

    @staticmethod
    def _coerce_user_role(user_role: str) -> UserRole:
        """Cast a raw role string to the :data:`UserRole` literal type.

        Pydantic validates the literal at construction time, so this
        helper exists purely to satisfy static type checkers without
        introducing duplicate runtime validation.

        Args:
            user_role: Raw role string supplied by the caller.

        Returns:
            The same string, typed as :data:`UserRole`.
        """
        return user_role  # type: ignore[return-value]

    @staticmethod
    def _coerce_gen_mode(mode_used: str) -> GenMode:
        """Cast the generator's mode string to the :data:`GenMode` literal.

        Args:
            mode_used: Mode string reported by
                :class:`GenerationResult`.

        Returns:
            The same string, typed as :data:`GenMode`.
        """
        return mode_used  # type: ignore[return-value]


@lru_cache(maxsize=1)
def get_pipeline() -> RAGPipeline:
    """Return a process-wide singleton :class:`RAGPipeline` instance.

    The instance is constructed with the default retriever and generator
    singletons, so the underlying embedder model and ChromaDB collection
    are opened at most once per process. Subsequent calls return the same
    object.

    Returns:
        The shared :class:`RAGPipeline` instance.
    """
    return RAGPipeline()


__all__: list[str] = ["RAGPipeline", "get_pipeline"]
