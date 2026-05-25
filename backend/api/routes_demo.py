"""Demo orchestration routes for the Cloud RAG Security Demo.

Implements `POST /api/demo/{act}` (spec section 4.7). Each act is a
hard-coded scenario whose query, user role, filter setting, and
generation mode live on the backend — the frontend only chooses the act
and renders the resulting `DemoResponse` plus narration.

Six acts are supported (see `DemoAct` in `backend.api.schemas`):
    * act1                — normal employee policy lookup
    * act2_no_filter      — access-control bypass (attack)
    * act2_with_filter    — metadata filter restored (defense)
    * act3                — prompt-injection via poisoned document
    * act4_attack         — Vec2Text inversion on plaintext embeddings
    * act4_defense        — CKKS-encrypted embeddings defeat inversion
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from backend.api.schemas import DemoResponse
from backend.rag.pipeline import get_pipeline

router = APIRouter(prefix="/api/demo", tags=["demo"])


# ---------------------------------------------------------------------------
# Per-act presets
# ---------------------------------------------------------------------------
# Acts 1-3 run through the RAG pipeline with the parameters below.
# Acts 4 attack/defense bypass the pipeline and instead return the
# pre-recorded embedding-inversion comparison from
# `backend.attacks.embedding_inversion`.
DEMO_PRESETS: dict[str, dict[str, Any]] = {
    "act1": {
        "query": "請問公司的請假規定？",
        "user_role": "employee",
        "use_filter": True,
        "gen_mode": "llm",
        "narration": (
            "第一幕：正常使用情境。一般員工查詢公開政策，"
            "系統回傳對應文件。"
        ),
    },
    "act2_no_filter": {
        "query": "張小明的薪資是多少？",
        "user_role": "employee",
        "use_filter": False,  # the attack: filter disabled
        "gen_mode": "scripted",
        "narration": (
            "第二幕（攻擊）：未啟用存取控制，"
            "一般員工的查詢直接觸及 Level 3 員工個資。"
        ),
    },
    "act2_with_filter": {
        "query": "張小明的薪資是多少？",
        "user_role": "employee",
        "use_filter": True,  # the defense: filter on
        "gen_mode": "scripted",
        "narration": (
            "第二幕（防禦）：啟用 metadata-based access control 後，"
            "同一查詢無法檢索到 Level 3 文件。"
        ),
    },
    "act3": {
        "query": "公司福利政策有哪些？",
        "user_role": "employee",
        "use_filter": True,
        "gen_mode": "llm",  # LLM is what gets fooled by the poisoned doc
        "narration": (
            "第三幕：Poisoned 文件雖然 Level 1 合法可見，"
            "但內含 prompt injection payload，LLM 被誘導洩漏 PII。"
        ),
    },
}

_PIPELINE_ACTS = frozenset(DEMO_PRESETS.keys())
_ACT4_ACTS = frozenset({"act4_attack", "act4_defense"})


@router.post("/{act}", response_model=DemoResponse)
async def demo_endpoint(act: str) -> DemoResponse:
    """Run the predefined scenario identified by `act`.

    Args:
        act: One of the six `DemoAct` literals (see module docstring).

    Returns:
        A `DemoResponse` whose `result` is either a `QueryResponse`
        (acts 1-3) or an act-specific dict payload (act 4 sub-flows).

    Raises:
        HTTPException: 404 if `act` is not a recognised demo identifier;
            500 if the underlying pipeline or attack module fails.
    """
    if act in _PIPELINE_ACTS:
        preset = DEMO_PRESETS[act]
        try:
            pipeline = get_pipeline()
            result = pipeline.run(
                query=preset["query"],
                user_role=preset["user_role"],
                use_filter=preset["use_filter"],
                gen_mode=preset["gen_mode"],
            )
        except KeyError as exc:
            raise HTTPException(
                status_code=400, detail=f"Invalid preset: {exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001 - surface as 500 for the demo
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        return DemoResponse(
            act=act,
            query=preset["query"],
            user_role=preset["user_role"],
            result=result,
            narration=preset["narration"],
        )

    if act in _ACT4_ACTS:
        # Imported lazily so the rest of the demo still serves even if
        # the Vec2Text / CKKS dependencies are not installed in dev.
        try:
            from backend.attacks.embedding_inversion import (
                get_inversion_comparison,
            )

            comparison = get_inversion_comparison()
        except Exception as exc:  # noqa: BLE001 - surface as 500 for the demo
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        if act == "act4_attack":
            return DemoResponse(
                act="act4_attack",
                query="(Vec2Text inversion against plaintext-stored embeddings)",
                user_role="hr_admin",  # placeholder — act4 doesn't use roles
                result=comparison,
                narration=(
                    "第四幕（攻擊）：攻擊者拿到明文 embedding，"
                    "使用 Vec2Text 還原原始 PII 文字。"
                ),
            )

        # act4_defense
        encrypted_only: dict[str, Any] = {
            "encrypted_inversion": comparison.get("encrypted_inversion", [])
            if isinstance(comparison, dict)
            else getattr(comparison, "encrypted_inversion", []),
        }
        return DemoResponse(
            act="act4_defense",
            query="(CKKS encrypted embeddings)",
            user_role="hr_admin",
            result=encrypted_only,
            narration=(
                "第四幕（防禦）：CKKS 加密後，攻擊者只看到密文，"
                "Vec2Text 還原失敗。同時，密文上仍可正確計算相似度。"
            ),
        )

    raise HTTPException(status_code=404, detail=f"Unknown act: {act}")
