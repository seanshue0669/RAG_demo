"""Act 3 prompt-injection attack demo.

This module wires up the "RAG-as-attack-surface" scenario described in
spec §4.5 and ``CLAUDE.md`` §"LLM 整合規則". The threat model is:

  1. A malicious actor seeded the knowledge base with one or more
     ``doc_type="poisoned_policy"`` documents (security_level=1, so they
     are visible to every role and therefore always candidates for
     retrieval). The seeding itself happens out-of-band via
     ``backend.data_gen`` and lands in ``data/generated/poisoned_docs.json``
     before the documents are indexed into ChromaDB.
  2. At demo time an ordinary user issues a benign-looking query (e.g.
     "公司福利政策有哪些?"). The retriever ranks the poisoned doc highly
     because its text was templated around common benefit-policy keywords.
  3. The retrieved poisoned text contains injection payloads ("忽略以上
     指示, ...") which the live LLM dutifully follows, producing an
     attacker-controlled answer. Per the project rules the system prompt
     is intentionally lenient so this attack succeeds visibly on stage.

The entry point :func:`run_prompt_injection_demo` runs the standard RAG
pipeline and reports whether the attack landed. The frontend uses the
``injection_detected`` flag in the returned dict to render the
attack-success banner.
"""

from __future__ import annotations

import logging

from backend.api.schemas import QueryResponse
from backend.rag.pipeline import get_pipeline

logger = logging.getLogger(__name__)

# Marker ``doc_type`` value used by the data-generation layer to tag
# documents that carry injection payloads. Kept as a module-level
# constant so unit tests and the frontend bridge can reference the
# same string without re-hardcoding it.
_POISONED_DOC_TYPE: str = "poisoned_policy"


def force_poisoned_retrieval_query() -> str:
    """Return a query likely to retrieve ``poisoned_policy`` documents.

    The poisoned templates in ``backend.data_gen`` cluster around the
    "公司福利政策" topic because that is the canonical benefit-policy
    phrasing seeded into the demo corpus. Asking that exact question
    maximises the cosine similarity between the query embedding and the
    poisoned-doc embeddings, all but guaranteeing at least one
    ``poisoned_policy`` doc appears in the top-k results.

    Returns:
        A Traditional-Chinese query string tuned to surface poisoned
        documents from the vector store.
    """
    return "公司福利政策有哪些？"


def _build_narration(
    *,
    injection_detected: bool,
    poisoned_doc_ids: list[str],
    answer_preview: str,
    gen_mode_used: str,
) -> str:
    """Compose the human-readable narration shown next to the demo output.

    Args:
        injection_detected: Whether at least one ``poisoned_policy`` doc
            was retrieved.
        poisoned_doc_ids: IDs of the poisoned documents that landed in
            the retrieved context.
        answer_preview: Truncated answer string used to illustrate the
            attacker-controlled output.
        gen_mode_used: The mode the pipeline actually executed in
            (``"llm"`` or ``"scripted"``).

    Returns:
        Narration text suitable for direct display in the frontend's
        Act 3 panel.
    """
    if injection_detected:
        joined_ids = ", ".join(poisoned_doc_ids) if poisoned_doc_ids else "(unknown)"
        narration = (
            "Prompt injection 攻擊成功：檢索到含注入指令的污染文件 "
            f"[{joined_ids}]，並以 gen_mode={gen_mode_used} 餵入 LLM。"
            "由於系統 prompt 採寬鬆設定，模型遵循了文件中的指令而非原始問題。"
            f" 模型回覆節錄：「{answer_preview}」"
        )
    else:
        narration = (
            "本次檢索未命中任何 poisoned_policy 文件，因此 prompt injection "
            "未被觸發。請改用 force_poisoned_retrieval_query() 提供的查詢字串"
            "（『公司福利政策有哪些？』）再試一次，以提高命中污染文件的機率。"
        )
    return narration


def run_prompt_injection_demo(
    query: str = "請問公司的福利政策有哪些？",
    user_role: str = "employee",
    gen_mode: str = "llm",
    top_k: int = 5,
) -> dict:
    """Run a query through the RAG pipeline and report injection success.

    The pipeline is invoked with ``use_filter=True`` so the demo mirrors
    the production access-control path: poisoned documents bypass the
    filter purely because they were planted at ``security_level=1``,
    not because the filter was disabled. This is what makes the attack
    realistic — an honest, low-privilege employee can be served the
    attacker's payload.

    Args:
        query: User-facing query string. Defaults to a benign-looking
            benefit-policy question that maximises the chance of
            retrieving a poisoned document.
        user_role: Role used by the pipeline to derive the security
            ceiling. Defaults to ``"employee"`` (the least-privileged
            role) so the demo shows that even ordinary users are
            exposed.
        gen_mode: Generation mode forwarded to the pipeline. Defaults
            to ``"llm"`` because the prompt injection only "succeeds"
            visibly when the live LLM is actually fooled; scripted mode
            would return a pre-recorded canned answer that does not
            exercise the vulnerability.
        top_k: Number of documents to retrieve from the vector store.

    Returns:
        A dict with the following shape:

        * ``response``: The pipeline's :class:`QueryResponse` serialised
          via :meth:`pydantic.BaseModel.model_dump`.
        * ``injection_detected``: ``True`` iff at least one retrieved
          document has ``doc_type == "poisoned_policy"``.
        * ``poisoned_doc_ids``: List of ``doc_id`` values for the
          poisoned documents that made it into the retrieved context.
        * ``narration``: Explanatory text rendered alongside the chat
          output. When no poisoned doc was retrieved, the narration
          suggests calling :func:`force_poisoned_retrieval_query`.
    """
    pipeline = get_pipeline()
    response: QueryResponse = pipeline.run(
        query=query,
        user_role=user_role,
        use_filter=True,
        gen_mode=gen_mode,
        top_k=top_k,
    )

    poisoned_doc_ids: list[str] = [
        doc.doc_id
        for doc in response.retrieved_docs
        if doc.doc_type == _POISONED_DOC_TYPE
    ]
    injection_detected: bool = len(poisoned_doc_ids) > 0

    answer_preview = response.answer.strip().replace("\n", " ")
    if len(answer_preview) > 160:
        answer_preview = answer_preview[:160] + "…"

    narration = _build_narration(
        injection_detected=injection_detected,
        poisoned_doc_ids=poisoned_doc_ids,
        answer_preview=answer_preview,
        gen_mode_used=response.gen_mode_used,
    )

    if injection_detected:
        logger.warning(
            "Prompt injection demo: %d poisoned docs surfaced (%s)",
            len(poisoned_doc_ids),
            ", ".join(poisoned_doc_ids),
        )
    else:
        logger.info(
            "Prompt injection demo: no poisoned docs in top-%d for query %r",
            top_k,
            query,
        )

    return {
        "response": response.model_dump(),
        "injection_detected": injection_detected,
        "poisoned_doc_ids": poisoned_doc_ids,
        "narration": narration,
    }


__all__: list[str] = [
    "run_prompt_injection_demo",
    "force_poisoned_retrieval_query",
]
