"""Generate fake internal performance reviews (security_level=2).

This module produces Traditional Chinese performance-review documents that
reference fictitious employees. These reviews are department-internal data
classified at security_level=2 (managers and HR admins should see them, but
not regular employees).

Each record returned by `generate()` matches the shared metadata schema
(doc_id, doc_type, department, security_level, text) and is intended for
serialization by `run_all.py`.
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


_DEPARTMENTS: list[str] = [
    "人資部",
    "財務部",
    "工程部",
    "行銷部",
    "法務部",
    "業務部",
]

_RATINGS: list[str] = ["優秀", "良好", "尚可", "待加強"]

_REVIEW_PERIODS: list[str] = [
    "2023 上半年",
    "2023 下半年",
    "2024 上半年",
    "2024 下半年",
    "2025 上半年",
]

_STRENGTHS: list[str] = [
    "主動承擔跨部門專案、溝通協調能力佳",
    "技術判斷準確、能在期限內完成關鍵交付",
    "對客戶需求敏感度高、能持續優化服務流程",
    "團隊合作意願強、積極分享知識與經驗",
    "問題解決能力突出、能獨立排除疑難",
    "對部門目標理解深入、主動規劃長期改善方案",
]

_IMPROVEMENTS: list[str] = [
    "在向上溝通與報告呈現上更為精煉",
    "對於新技術的學習速度可再加快",
    "需強化跨部門需求釐清與優先順序判斷",
    "在時間管理與多工處理上仍有提升空間",
    "建議多參與外部研討會、拓展產業視野",
    "在文件撰寫與會議紀錄上可更為完整",
]

_BONUS_RECOMMENDATIONS: list[str] = [
    "建議發放 1 個月績效獎金",
    "建議發放 1.5 個月績效獎金",
    "建議發放 2 個月績效獎金",
    "建議發放半個月績效獎金",
    "建議維持原獎金水準",
]

_PROMOTION_STATUSES: list[str] = [
    "暫不晉升，列入下半年觀察名單",
    "建議晉升一級",
    "維持現職",
    "建議列入接班人培育計畫",
]


def _build_record(
    fake: Faker,
    rng: random.Random,
    index: int,
    template: str,
) -> dict[str, Any]:
    """Build a single performance review record.

    Args:
        fake: Faker instance with zh_TW locale.
        rng: Seeded `random.Random` instance.
        index: 1-based counter used to form the document ID.
        template: Raw template string to `.format()` with field values.

    Returns:
        A record dict with the rendered Traditional Chinese review.
    """
    settings = get_settings()
    meta = settings.METADATA_KEYS

    doc_id = f"INT-{index:04d}"
    department = rng.choice(_DEPARTMENTS)

    fields = {
        "review_period": rng.choice(_REVIEW_PERIODS),
        "employee_name": fake.name(),
        "department": department,
        "reviewer_name": fake.name(),
        "rating": rng.choice(_RATINGS),
        "strengths": rng.choice(_STRENGTHS),
        "improvements": rng.choice(_IMPROVEMENTS),
        "bonus_recommendation": rng.choice(_BONUS_RECOMMENDATIONS),
        "promotion_status": rng.choice(_PROMOTION_STATUSES),
    }

    text = template.format(**fields)

    return {
        meta["doc_id"]: doc_id,
        meta["doc_type"]: "performance_review",
        meta["department"]: department,
        meta["security_level"]: 2,
        meta["text"]: text,
    }


def generate(n: int, seed: int | None = None) -> list[dict]:
    """Generate `n` performance-review records.

    Args:
        n: Number of records to produce.
        seed: Optional integer seed for deterministic output.

    Returns:
        A list of `n` performance-review record dicts.

    Raises:
        FileNotFoundError: If the performance_review template is missing.
    """
    settings = get_settings()
    template_path = settings.TEMPLATES_DIR / "performance_review.txt"
    template = template_path.read_text(encoding="utf-8")

    fake = Faker(locale="zh_TW")
    rng = random.Random(seed)
    if seed is not None:
        Faker.seed(seed)

    return [_build_record(fake, rng, i + 1, template) for i in range(n)]


__all__: list[str] = ["generate"]
