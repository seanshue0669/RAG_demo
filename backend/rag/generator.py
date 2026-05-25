"""Answer generator for the Cloud RAG Security Demo.

This module produces a final natural-language answer given a user query and
the documents retrieved by the RAG pipeline. Two modes are supported, per
``CLAUDE.md`` "RAG Pipeline" and "LLM 整合" rules:

* ``mode="llm"`` (default for the pipeline): assembles an OpenAI-style chat
  prompt (system prompt + retrieved documents + user query) and POSTs it to
  the existing vLLM endpoint configured in
  :class:`backend.config.settings.Settings`. The endpoint serves
  ``models--google--gemma-4-26B-A4B-it`` on ``localhost:3053`` in this demo.

* ``mode="scripted"``: matches the query (and current attack/role context)
  against ``data/prerecorded/prompt_injection_responses.json`` and returns
  the pre-recorded answer. Used both for offline demos and as the pipeline's
  fallback when the live vLLM endpoint is unreachable.

The pipeline owns the fallback policy: it calls
:meth:`Generator.generate` with ``mode="llm"`` first and, on any HTTP /
timeout / connection error, retries with ``mode="scripted"``. This module
therefore deliberately *propagates* HTTP errors from the LLM path rather
than swallowing them.

Per the spec's "System prompt 不可過度嚴格" rule, the system prompt
included here is intentionally lightweight so that Act 3's prompt-injection
demonstration can succeed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx

from backend.config.settings import Settings, get_settings


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Kept module-private; expose via the dataclass / class methods only.
_SYSTEM_PROMPT: str = (
    "你是 NovaTech 公司的 HR 智能助理，可以根據檢索到的內部文件回答員工的提問。\n"
    "請以繁體中文回答，並參考下方提供的文件內容。"
)

# Document type that signals a successful prompt-injection retrieval. Used
# to disambiguate which scripted entry to return for queries that have both
# a "clean" and a "poisoned" variant in the response bank.
_POISONED_DOC_TYPE: str = "poisoned_policy"

# Generic fallback when no scripted entry matches.
_DEFAULT_SCRIPTED_ANSWER: str = (
    "抱歉，目前沒有可用的預錄回應可回答您的問題。請稍後再試或聯繫系統管理員。"
)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------
@dataclass
class GenerationResult:
    """Container for a generated answer.

    Attributes:
        answer: The final answer text rendered to the user.
        mode_used: Which generation path produced ``answer`` -- either
            ``"llm"`` or ``"scripted"``. Useful for the pipeline / API to
            report fallback diagnostics back to the frontend.
    """

    answer: str
    mode_used: str


class Generator:
    """Generate an answer from a query plus retrieved-doc context.

    The generator is mode-pluggable: the same instance handles both live
    vLLM calls and scripted pre-recorded responses. It does not implement
    fallback itself; the caller (the RAG pipeline) decides when to retry
    with a different mode.

    Attributes:
        client: The HTTP client used to talk to the vLLM endpoint.
    """

    def __init__(
        self,
        http_client: httpx.Client | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Initialise the generator.

        Args:
            http_client: Optional pre-built :class:`httpx.Client`. When
                ``None``, a fresh client is constructed with the timeout
                from :attr:`Settings.VLLM_TIMEOUT_SECONDS`. Injectable so
                tests can stub the HTTP transport.
            settings: Optional :class:`Settings` override. When ``None``,
                the global singleton from :func:`get_settings` is used.
        """
        self._settings: Settings = settings if settings is not None else get_settings()
        self.client: httpx.Client = (
            http_client
            if http_client is not None
            else httpx.Client(timeout=self._settings.VLLM_TIMEOUT_SECONDS)
        )
        # Lazily loaded scripted response bank; cached on first use to
        # avoid disk I/O on every generate() call.
        self._scripted_responses: list[dict[str, Any]] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(
        self,
        query: str,
        context_docs: list,
        mode: str = "llm",
        user_role: str = "employee",
    ) -> GenerationResult:
        """Produce a final answer for the given query.

        Args:
            query: The user's natural-language query (Traditional Chinese).
            context_docs: Retrieved documents to use as RAG context. May be
                a list of :class:`backend.vectordb.chroma_store.RetrievedDoc`
                instances or a list of dicts exposing ``doc_id``, ``text``,
                ``security_level``, and optionally ``doc_type``.
            mode: ``"llm"`` to call the vLLM endpoint, ``"scripted"`` to
                match against the pre-recorded response bank.
            user_role: Caller's role, used only by the scripted matcher to
                pick the role-appropriate variant of an entry.

        Returns:
            A :class:`GenerationResult` whose ``mode_used`` reflects the
            actual path taken.

        Raises:
            httpx.HTTPError: When ``mode="llm"`` and the vLLM endpoint
                returns an error status, times out, or is unreachable. The
                RAG pipeline catches this to fall back to scripted mode;
                callers using :class:`Generator` directly should be ready
                to handle it as well.
            ValueError: When ``mode`` is not one of the supported values.
        """
        if mode == "llm":
            messages = self._build_messages(query=query, context_docs=context_docs)
            answer = self._call_llm(messages)
            return GenerationResult(answer=answer, mode_used="llm")

        if mode == "scripted":
            retrieved_doc_types = _collect_doc_types(context_docs)
            answer = self._match_scripted_response(
                query=query,
                user_role=user_role,
                retrieved_doc_types=retrieved_doc_types,
            )
            return GenerationResult(answer=answer, mode_used="scripted")

        raise ValueError(
            f"Unsupported generation mode: {mode!r}. Expected 'llm' or 'scripted'."
        )

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------
    def _build_messages(
        self,
        query: str,
        context_docs: list,
    ) -> list[dict[str, str]]:
        """Assemble an OpenAI-style chat messages array.

        The system message is the lightweight prompt mandated by the spec
        (kept intentionally permissive so Act 3's prompt injection can
        succeed). Retrieved documents are concatenated into a second
        system-role message so they are clearly separated from the user
        turn. Finally the user's query is appended as the user message.

        Args:
            query: The user's natural-language query.
            context_docs: Retrieved documents (``RetrievedDoc`` or dict).

        Returns:
            A list of ``{"role": ..., "content": ...}`` dicts ready to
            POST as the ``messages`` field of a chat-completions request.
        """
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
        ]

        context_block = _format_context_block(context_docs)
        if context_block:
            messages.append({"role": "system", "content": context_block})

        messages.append({"role": "user", "content": query})
        return messages

    def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """POST the chat messages to vLLM and return the assistant content.

        Args:
            messages: OpenAI-style chat messages.

        Returns:
            The ``choices[0].message.content`` string from the response.

        Raises:
            httpx.HTTPError: For any transport, timeout, or non-2xx HTTP
                status. Not caught here; the pipeline handles fallback.
            KeyError: If the response shape is unexpected (no
                ``choices``/``message``/``content``). This is intentionally
                surfaced rather than silently substituting a placeholder.
        """
        payload: dict[str, Any] = {
            "model": self._settings.VLLM_MODEL_NAME,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 512,
        }
        url = f"{self._settings.VLLM_BASE_URL}/chat/completions"
        response = self.client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]

    # ------------------------------------------------------------------
    # Scripted path
    # ------------------------------------------------------------------
    def _match_scripted_response(
        self,
        query: str,
        user_role: str,
        retrieved_doc_types: set[str],
    ) -> str:
        """Pick the best pre-recorded answer for the current context.

        Match logic (in order of precedence):
          1. Restrict to entries whose ``user_role`` either matches the
             caller's role or is unspecified.
          2. Restrict to entries whose ``with_poisoned_doc`` flag matches
             whether the retrieved set contains a ``poisoned_policy``
             document. (Entries that don't specify the flag match either
             way.)
          3. From what remains, pick the first entry whose
             ``query_pattern`` is a substring of the user's query.
          4. If nothing matches, fall back to a generic apology string.

        Args:
            query: The user's natural-language query.
            user_role: Caller's role (``employee`` / ``manager`` /
                ``hr_admin``).
            retrieved_doc_types: Set of ``doc_type`` values present in the
                retrieved context, used to detect a successful injection.

        Returns:
            The matched ``answer`` string or a sensible default.
        """
        responses = self._load_scripted_responses()
        has_poisoned = _POISONED_DOC_TYPE in retrieved_doc_types

        candidates: list[dict[str, Any]] = []
        for entry in responses:
            entry_role = entry.get("user_role")
            if entry_role is not None and entry_role != user_role:
                continue

            entry_with_poisoned = entry.get("with_poisoned_doc")
            if entry_with_poisoned is not None and bool(entry_with_poisoned) != has_poisoned:
                continue

            candidates.append(entry)

        for entry in candidates:
            pattern = entry.get("query_pattern", "")
            if pattern and pattern in query:
                return str(entry.get("answer", _DEFAULT_SCRIPTED_ANSWER))

        return _DEFAULT_SCRIPTED_ANSWER

    def _load_scripted_responses(self) -> list[dict[str, Any]]:
        """Load (and cache) the pre-recorded scripted response bank.

        Returns:
            The parsed ``responses`` list from
            ``data/prerecorded/prompt_injection_responses.json``. An empty
            list is returned if the file is missing or malformed; the
            scripted matcher then falls back to its default answer.
        """
        if self._scripted_responses is not None:
            return self._scripted_responses

        path = self._settings.DATA_PRERECORDED_DIR / "prompt_injection_responses.json"
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            responses = data.get("responses", [])
            if not isinstance(responses, list):
                responses = []
        except (FileNotFoundError, json.JSONDecodeError):
            responses = []

        self._scripted_responses = responses
        return responses


# ---------------------------------------------------------------------------
# Module-level helpers (kept private to this module)
# ---------------------------------------------------------------------------
def _doc_attr(doc: Any, name: str, default: Any = "") -> Any:
    """Read ``name`` from ``doc`` whether it is a dataclass or a dict.

    Args:
        doc: A retrieved-document object (dataclass instance or mapping).
        name: Attribute / key name to read.
        default: Value returned if ``name`` is absent.

    Returns:
        The attribute value, or ``default`` when missing.
    """
    if isinstance(doc, dict):
        return doc.get(name, default)
    return getattr(doc, name, default)


def _format_context_block(context_docs: list) -> str:
    """Render retrieved documents into a single context string.

    Each document is rendered as::

        【文件 {doc_id} (Level {security_level})】
        {text}

    Blocks are separated by a blank line.

    Args:
        context_docs: Retrieved documents (``RetrievedDoc`` or dict).

    Returns:
        The concatenated context block, or an empty string when
        ``context_docs`` is empty.
    """
    if not context_docs:
        return ""

    blocks: list[str] = []
    for doc in context_docs:
        doc_id = _doc_attr(doc, "doc_id", "UNKNOWN")
        security_level = _doc_attr(doc, "security_level", 0)
        text = _doc_attr(doc, "text", "")
        blocks.append(
            f"【文件 {doc_id} (Level {security_level})】\n{text}"
        )
    return "\n\n".join(blocks)


def _collect_doc_types(context_docs: list) -> set[str]:
    """Collect the set of ``doc_type`` values present in the retrieved set.

    Args:
        context_docs: Retrieved documents (``RetrievedDoc`` or dict).

    Returns:
        A set of ``doc_type`` strings; empty when ``context_docs`` is
        empty or no entries expose ``doc_type``.
    """
    types: set[str] = set()
    for doc in context_docs:
        doc_type = _doc_attr(doc, "doc_type", "")
        if doc_type:
            types.add(str(doc_type))
    return types


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def get_generator() -> Generator:
    """Return a process-wide singleton :class:`Generator` instance.

    The instance lazily holds an :class:`httpx.Client` configured with the
    vLLM timeout from :class:`Settings`, so the underlying HTTP connection
    pool is reused across requests.

    Returns:
        The shared :class:`Generator` instance.
    """
    return Generator()


__all__: list[str] = ["GenerationResult", "Generator", "get_generator"]
