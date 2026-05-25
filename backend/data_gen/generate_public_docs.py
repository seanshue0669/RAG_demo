"""Generate fake public policy documents (security_level=1).

These are company-wide policies that any employee can access. They are
classified at security_level=1 and assigned to the special "全公司" scope.
Each record returned by `generate()` matches the shared metadata schema
(doc_id, doc_type, department, security_level, text).
"""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any

# Make `backend.config.settings` importable from both module and script entry.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from faker import Faker  # noqa: E402

from backend.config.settings import get_settings  # noqa: E402


# Policy topics required by the agent prompt. Each topic maps to a small
# pool of plausible Traditional-Chinese policy bodies.
_POLICY_TOPICS: list[str] = [
    "請假規定",
    "出勤管理",
    "福利政策",
    "培訓制度",
    "加班費計算",
    "差旅費規定",
    "退休制度",
    "健保補助",
    "年終獎金",
    "績效獎金",
    "員工協助方案",
    "性平政策",
    "反騷擾政策",
    "資訊安全規範",
    "個資保護",
]

# A pool of plausible 2-3 sentence bodies. The generator picks one at random
# per record and may concatenate two snippets for variety.
_BODY_SNIPPETS: list[str] = [
    "員工應依公司規範辦理相關事宜，並於指定期限內完成申請程序。",
    "申請流程須經直屬主管核可後送交人資部門備查，相關紀錄將留存於人事系統。",
    "本辦法之適用範圍涵蓋全體正職員工，特約人員及實習生另依其合約規範辦理。",
    "公司將依勞動基準法及相關法令調整實施細節，並於每年度檢討一次。",
    "違反本規定者，將依公司內部獎懲辦法予以處置，情節重大者得終止勞動契約。",
    "員工如對辦法內容有疑問，得逕洽人資部門福利窗口尋求協助。",
    "為兼顧工作效率與員工福祉，公司鼓勵同仁妥善運用本辦法所提供之資源。",
    "相關補助標準將依物價水準與市場行情每年度檢視一次，必要時公告調整。",
    "本辦法之解釋權歸人資部門所有，未盡事宜悉依法令與既有規章辦理。",
    "為落實資訊安全與個資保護，員工應遵守最低權限原則並妥善保管帳號密碼。",
]

_CONTACT_DEPTS: list[str] = [
    "人資部門福利窗口",
    "人資部門出勤管理窗口",
    "人資部門教育訓練窗口",
    "資安暨個資保護辦公室",
    "員工關係課",
]


def _build_record(
    fake: Faker,
    rng: random.Random,
    index: int,
    template: str,
    topic: str,
) -> dict[str, Any]:
    """Build a single public policy record.

    Args:
        fake: Faker instance (used for the effective date).
        rng: Seeded `random.Random` instance.
        index: 1-based counter used to form the document ID.
        template: Raw template string to `.format()`.
        topic: The policy topic that drives the `policy_title`.

    Returns:
        A public policy record dict.
    """
    settings = get_settings()
    meta = settings.METADATA_KEYS

    doc_id = f"PUB-{index:04d}"
    body_parts = rng.sample(_BODY_SNIPPETS, k=rng.randint(2, 3))
    body = "".join(body_parts)

    fields = {
        "policy_title": topic,
        "policy_id": f"POL-{rng.randint(1000, 9999)}",
        "effective_date": fake.date_between(start_date="-3y", end_date="today").isoformat(),
        "scope": "全公司員工",
        "body": body,
        "contact_dept": rng.choice(_CONTACT_DEPTS),
    }

    text = template.format(**fields)

    return {
        meta["doc_id"]: doc_id,
        meta["doc_type"]: "policy_document",
        meta["department"]: "全公司",
        meta["security_level"]: 1,
        meta["text"]: text,
    }


def generate(n: int, seed: int | None = None) -> list[dict]:
    """Generate `n` public policy records.

    If `n` exceeds the number of available topics, topics are reused in
    round-robin order so each requested record still receives a topic.

    Args:
        n: Number of records to produce.
        seed: Optional integer seed for deterministic output.

    Returns:
        A list of `n` policy record dicts.

    Raises:
        FileNotFoundError: If the policy_document template is missing.
    """
    settings = get_settings()
    template_path = settings.TEMPLATES_DIR / "policy_document.txt"
    template = template_path.read_text(encoding="utf-8")

    fake = Faker(locale="zh_TW")
    rng = random.Random(seed)
    if seed is not None:
        Faker.seed(seed)

    # Shuffle topics for variety; cycle if n > len(topics).
    topics = list(_POLICY_TOPICS)
    rng.shuffle(topics)
    assigned_topics = [topics[i % len(topics)] for i in range(n)]

    return [
        _build_record(fake, rng, i + 1, template, topic)
        for i, topic in enumerate(assigned_topics)
    ]


__all__: list[str] = ["generate"]
