"""Act 2 retrieval-bypass attack: side-by-side filter vs no-filter comparison.

This module implements the Act 2 demo flow described in spec section 4.5.
The attack premise is simple but striking: a RAG system that performs
vector similarity search **without** enforcing access control at the
retrieval layer will happily return high-similarity documents regardless
of the caller's clearance. An ``employee`` querying for confidential
HR information should be denied; without a ``security_level`` filter the
retriever leaks the documents straight back, and the generator then
echoes their contents in the answer.

To make this concrete for the audience, :func:`run_retrieval_bypass_demo`
runs the **same** query through the shared
:class:`backend.rag.pipeline.RAGPipeline` twice:

1. ``use_filter=False`` -- the vulnerable path. Retrieval returns the
   global top-k, including documents above the caller's clearance.
2. ``use_filter=True`` -- the defended path. ChromaDB applies the
   downward-inclusive ``security_level <= role_level`` filter so the
   leaked documents disappear from the result set.

Both runs are wrapped in a single :class:`RetrievalBypassResponse` so the
FastAPI layer can return one payload and the frontend can render the
two :class:`QueryResponse` objects side-by-side.

Per CLAUDE.md "RAG Pipeline 規則", the default ``gen_mode`` here is
``"scripted"`` rather than ``"llm"``. Act 2 is about the *retrieval*
layer; pinning generation to the deterministic scripted responses keeps
the on-stage comparison stable and avoids accidentally turning Act 2 into
a live-LLM demonstration.
"""

from __future__ import annotations

from backend.api.schemas import RetrievalBypassResponse
from backend.rag.pipeline import get_pipeline


def run_retrieval_bypass_demo(
    query: str,
    user_role: str = "employee",
    gen_mode: str = "scripted",
    top_k: int = 5,
) -> RetrievalBypassResponse:
    """Run the Act 2 retrieval-bypass comparison for a single query.

    Executes ``query`` against the shared RAG pipeline twice -- once with
    the ``security_level`` filter disabled (attack path) and once with it
    enabled (defense path) -- and returns both results in a single
    :class:`RetrievalBypassResponse` for side-by-side rendering.

    The default ``user_role`` is ``"employee"`` because the contrast is
    most visible when the caller has the lowest clearance: without the
    filter they see ``manager`` and ``hr_admin`` documents, with the
    filter they see only level-1 documents.

    The default ``gen_mode`` is ``"scripted"`` so the comparison stays
    deterministic on stage. Act 2 is about the retrieval layer, not the
    generator; using scripted mode also avoids spurious differences
    between the two answers caused by LLM sampling noise.

    Args:
        query: Natural-language user query (Traditional Chinese in the
            demo). Identical for both runs so the only varying input is
            ``use_filter``.
        user_role: Role name used to derive the access-control ceiling
            for the defended run. Must be one of ``"employee"``,
            ``"manager"`` or ``"hr_admin"``. Has no effect on the
            attack run because filtering is disabled there. Defaults to
            ``"employee"`` to maximise the demonstrated gap.
        gen_mode: Requested generation mode forwarded to the pipeline.
            Defaults to ``"scripted"`` to keep the Act 2 comparison
            deterministic; callers may pass ``"llm"`` to also surface
            the answer-layer difference.
        top_k: Maximum number of documents to retrieve per run.

    Returns:
        A :class:`RetrievalBypassResponse` containing the shared
        ``query``, the ``without_filter`` :class:`QueryResponse`
        (vulnerable path), and the ``with_filter`` :class:`QueryResponse`
        (defended path).
    """
    pipeline = get_pipeline()
    without_filter = pipeline.run(
        query=query,
        user_role=user_role,
        use_filter=False,
        gen_mode=gen_mode,
        top_k=top_k,
    )
    with_filter = pipeline.run(
        query=query,
        user_role=user_role,
        use_filter=True,
        gen_mode=gen_mode,
        top_k=top_k,
    )
    return RetrievalBypassResponse(
        query=query,
        without_filter=without_filter,
        with_filter=with_filter,
    )


__all__: list[str] = ["run_retrieval_bypass_demo"]
