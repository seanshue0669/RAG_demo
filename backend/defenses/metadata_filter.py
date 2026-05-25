"""Role-based metadata filter contract for the Act 2 retrieval-bypass demo.

This module is a thin documentation / enforcement layer over the metadata
filter that is *implemented* in `backend.vectordb.chroma_store.ChromaStore`
(specifically `query_with_filter`, which uses a downward-inclusive `<=`
comparison on `security_level`).

The retriever and the Act 2 attack/defense flow should call into the helpers
defined here so that:

  * The role -> max security level mapping has exactly one source of truth
    (`Settings.ROLE_TO_LEVEL` via `Settings.role_to_level`).
  * The "filter on / off" toggle that drives the Act 2 demo has a clear,
    documented contract: `None` means "no filter", an integer means
    "filter to that ceiling".
  * The frontend SystemLog panel can render a human-readable summary of
    what the currently-selected role is allowed to see.

Per CLAUDE.md the mapping is::

    employee  -> 1   (public policy docs)
    manager   -> 2   (public + internal department docs)
    hr_admin  -> 3   (everything, including employee PII)
"""

from __future__ import annotations

from backend.config.settings import get_settings


def role_to_max_level(role: str) -> int:
    """Return the maximum accessible security level for a given role.

    Thin wrapper around `Settings.role_to_level` so callers in the
    defenses / retriever / API layers can depend on this module instead
    of reaching directly into settings.

    Args:
        role: One of the role identifiers defined in
            `Settings.ROLE_TO_LEVEL` (currently `"employee"`,
            `"manager"`, `"hr_admin"`).

    Returns:
        The integer security level ceiling for the role. A role with
        level `N` is permitted to see all documents whose
        `security_level <= N`.

    Raises:
        KeyError: If `role` is not present in `Settings.ROLE_TO_LEVEL`.
    """
    settings = get_settings()
    return settings.role_to_level(role)


def applies_filter(user_role: str, use_filter: bool) -> int | None:
    """Resolve the `max_security_level` argument for `query_with_filter`.

    This helper encodes the Act 2 toggle semantics:

      * `use_filter=True`  -> return the role's security ceiling so the
        caller can pass it straight into
        `ChromaStore.query_with_filter(..., max_security_level=...)`.
      * `use_filter=False` -> return `None`, signalling that the caller
        should bypass `query_with_filter` and use the unfiltered
        `ChromaStore.query` instead (the "vulnerable" branch shown in
        Act 2).

    Args:
        user_role: Role identifier from
            `Settings.ROLE_TO_LEVEL` (e.g. `"employee"`).
        use_filter: When `True`, derive the security ceiling from the
            role. When `False`, disable filtering entirely.

    Returns:
        The integer security level ceiling, or `None` if filtering is
        disabled.

    Raises:
        KeyError: If `use_filter=True` and `user_role` is not present in
            `Settings.ROLE_TO_LEVEL`.
    """
    if not use_filter:
        return None
    return role_to_max_level(user_role)


def filter_summary(role: str) -> dict:
    """Build a human-readable summary of a role's document access scope.

    Used by the frontend SystemLog panel to render what level of
    documents the currently-selected role is allowed to retrieve, and
    by Act 2 narration text.

    Args:
        role: Role identifier from `Settings.ROLE_TO_LEVEL`.

    Returns:
        A dict with the following keys:

          * ``role`` (str): Echo of the input role.
          * ``max_security_level`` (int): The role's security ceiling.
          * ``accessible_levels`` (list[int]): All levels the role can
            access, inclusive of the ceiling.
          * ``description`` (str): Traditional-Chinese description of
            the role's access scope, or an empty string for unknown
            roles.

    Raises:
        KeyError: If `role` is not present in `Settings.ROLE_TO_LEVEL`.
    """
    level = role_to_max_level(role)
    return {
        "role": role,
        "max_security_level": level,
        "accessible_levels": list(range(1, level + 1)),
        "description": {
            "employee": "可存取公開政策文件 (L1)",
            "manager": "可存取公開政策 (L1) 與部門內部文件 (L2)",
            "hr_admin": "可存取所有文件 (L1, L2, L3)，包含員工個資",
        }.get(role, ""),
    }


__all__: list[str] = [
    "role_to_max_level",
    "applies_filter",
    "filter_summary",
]
