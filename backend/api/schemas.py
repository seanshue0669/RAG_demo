"""Pydantic v2 request/response schemas for the Cloud RAG Security Demo API.

This module is the single source of truth for the JSON contract exchanged
between the FastAPI backend and the React frontend (see spec section 4.7).
All other backend modules and frontend clients must conform to the literal
unions and field names defined here.

The role / security-level mapping referenced by `UserRole` is owned by
`backend.config.settings.Settings.ROLE_TO_LEVEL` — the literal values below
must stay in sync with the keys of that mapping.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared literal types
# ---------------------------------------------------------------------------
# Keep these literals aligned with:
#   - `Settings.ROLE_TO_LEVEL` keys for UserRole
#   - `rag.generator` mode argument for GenMode
#   - data-generation `doc_type` field for DocType
UserRole = Literal["employee", "manager", "hr_admin"]
GenMode = Literal["llm", "scripted"]
DocType = Literal[
    "employee_record",
    "performance_review",
    "policy_document",
    "poisoned_policy",
]
DemoAct = Literal[
    "act1",
    "act2_no_filter",
    "act2_with_filter",
    "act3",
    "act4_attack",
    "act4_defense",
]


# ---------------------------------------------------------------------------
# Core RAG models
# ---------------------------------------------------------------------------
class Document(BaseModel):
    """A single retrieved document returned by the RAG pipeline.

    Per CLAUDE.md API rules, `retrieved_docs` items must always carry
    `doc_id`, `text`, `security_level`, and `similarity`. `doc_type` and
    `department` provide additional metadata for the SystemLog panel.

    Attributes:
        doc_id: Stable document identifier (e.g. "EMP-0042").
        text: Raw document text (Traditional Chinese).
        security_level: Integer level the role must meet or exceed
            (1=public, 2=internal, 3=confidential).
        similarity: Cosine similarity score from the retriever in [0, 1].
        doc_type: Category used for UI badges and filtering.
        department: Owning department string, or `None` for org-wide docs.
    """

    doc_id: str
    text: str
    security_level: int
    similarity: float
    doc_type: DocType
    department: str | None = None


class QueryRequest(BaseModel):
    """Request body for `POST /api/query`.

    All parameters are chosen by the frontend (see CLAUDE.md API rules).
    `use_filter` toggles ChromaDB metadata filtering by `security_level`,
    which is the core mechanism demonstrated in Act 2.

    Attributes:
        query: Natural-language user query (Traditional Chinese).
        user_role: Role used to derive the security level ceiling.
        use_filter: If True, apply `security_level <= role_level` filter.
        gen_mode: Choose between live LLM call or pre-recorded scripted
            response. Defaults to `"llm"`; pipeline falls back to
            `"scripted"` when vLLM is unreachable.
        top_k: Number of documents to retrieve from the vector store.
    """

    query: str
    user_role: UserRole
    use_filter: bool = True
    gen_mode: GenMode = "llm"
    top_k: int = 5


class QueryResponse(BaseModel):
    """Response body for `POST /api/query`.

    Attributes:
        answer: Generated answer string from the configured `gen_mode`.
        retrieved_docs: Ordered list of documents used as RAG context.
        filter_applied: Echoes whether `use_filter` was honoured (false
            when the request set it false, or when fallback disabled it).
        user_role: Echo of the requested role for client-side display.
        gen_mode_used: Actual mode that produced `answer` (may differ
            from the request when fallback kicks in).
    """

    answer: str
    retrieved_docs: list[Document]
    filter_applied: bool
    user_role: UserRole
    gen_mode_used: GenMode


# ---------------------------------------------------------------------------
# Demo orchestration models
# ---------------------------------------------------------------------------
class DemoResponse(BaseModel):
    """Response body for `POST /api/demo/{act}`.

    Each act has fixed query, role, and filter settings owned by the
    backend; the frontend simply renders the result and the narration.

    Attributes:
        act: Which act was executed.
        query: The hard-coded query used for this act.
        user_role: The hard-coded role used for this act.
        result: Either a fully-formed `QueryResponse` (Acts 1-3) or an
            arbitrary act-specific payload (Act 4 sub-flows return
            `HESearchResponse`, `Act4AttackResponse`, etc.).
        narration: Narration text rendered alongside the chat output
            to walk the audience through what just happened.
    """

    act: DemoAct
    query: str
    user_role: UserRole
    result: QueryResponse | dict
    narration: str


# ---------------------------------------------------------------------------
# Homomorphic-encryption search models
# ---------------------------------------------------------------------------
class HESearchRequest(BaseModel):
    """Request body for `POST /api/he/search`.

    Attributes:
        query: Natural-language query to encrypt and search against the
            pre-encrypted CKKS embedding store.
        top_k: Number of nearest neighbours to return.
    """

    query: str
    top_k: int = 5


class HETiming(BaseModel):
    """Per-stage timing breakdown for an encrypted search call.

    Per CLAUDE.md HE rules, each stage must be timed independently rather
    than reporting only a total.

    Attributes:
        encrypt_query_ms: Time spent CKKS-encrypting the query embedding.
        compute_similarity_ms: Time spent on encrypted dot products
            across the encrypted document store.
        decrypt_ms: Time spent decrypting the similarity scores.
        total_ms: Wall-clock total for the full encrypted search.
    """

    encrypt_query_ms: float
    compute_similarity_ms: float
    decrypt_ms: float
    total_ms: float


class HEResultItem(BaseModel):
    """A single result row from either encrypted or plaintext search.

    Attributes:
        doc_id: Stable document identifier.
        similarity: Cosine similarity score. CKKS results may differ
            slightly from plaintext due to approximate arithmetic.
        text: Raw document text (Traditional Chinese).
        security_level: Integer security level of the document.
    """

    doc_id: str
    similarity: float
    text: str
    security_level: int


class HESearchResponse(BaseModel):
    """Response body for `POST /api/he/search`.

    Returns both the encrypted-pipeline and plaintext-pipeline results so
    the frontend HEDashboard can render a side-by-side comparison.

    Attributes:
        results: Top-k results from the encrypted search pipeline.
        timing: Per-stage timing of the encrypted search.
        plaintext_results: Top-k results from the equivalent plaintext
            search, included for visual comparison.
        plaintext_timing_ms: Wall-clock total for plaintext search.
    """

    results: list[HEResultItem]
    timing: HETiming
    plaintext_results: list[HEResultItem]
    plaintext_timing_ms: float


# ---------------------------------------------------------------------------
# Act 4 attack / defense models
# ---------------------------------------------------------------------------
class InversionResult(BaseModel):
    """One pre-recorded embedding-inversion case for Act 4.

    Per CLAUDE.md Vec2Text rules these are loaded from pre-recorded JSON
    and never computed live during the demo.

    Attributes:
        doc_id: Document identifier the inversion attempt targets.
        original_text: Ground-truth source text used to build the
            embedding that was attacked.
        inverted_text: Text reconstructed by the Vec2Text attacker.
        similarity_score: Similarity between original and inverted text
            (typically embedding cosine or BLEU-style score).
        pii_match: Mapping of PII category to recovery outcome, e.g.
            `{"name": True, "department": False}`.
        pii_match_rate: Fraction of PII fields that were recovered,
            in [0, 1].
    """

    doc_id: str
    original_text: str
    inverted_text: str
    similarity_score: float
    pii_match: dict
    pii_match_rate: float


class Act4AttackResponse(BaseModel):
    """Response payload for the Act 4 embedding-inversion attack panel.

    Compares Vec2Text inversion success against plaintext embeddings vs
    CKKS-encrypted embeddings to motivate the HE defense.

    Attributes:
        plaintext_inversion: Inversion cases run against plaintext
            embeddings (attacker succeeds).
        encrypted_inversion: Inversion cases run against CKKS-encrypted
            embeddings (attacker fails / recovers nothing meaningful).
    """

    plaintext_inversion: list[InversionResult]
    encrypted_inversion: list[InversionResult]


class RetrievalBypassResponse(BaseModel):
    """Response payload for the Act 2 retrieval-bypass comparison.

    Runs the same query twice — once without the security filter and
    once with it — so the frontend can show what an employee can leak
    when access control at the retrieval layer is missing.

    Attributes:
        query: The shared query used for both runs.
        without_filter: Result with `use_filter=False` (vulnerable).
        with_filter: Result with `use_filter=True` (defended).
    """

    query: str
    without_filter: QueryResponse
    with_filter: QueryResponse


__all__: list[str] = [
    "UserRole",
    "GenMode",
    "DocType",
    "DemoAct",
    "Document",
    "QueryRequest",
    "QueryResponse",
    "DemoResponse",
    "HESearchRequest",
    "HETiming",
    "HEResultItem",
    "HESearchResponse",
    "InversionResult",
    "Act4AttackResponse",
    "RetrievalBypassResponse",
]


# `Field` is re-exported for downstream modules that wish to extend these
# schemas with additional constraints without re-importing from pydantic.
_ = Field
