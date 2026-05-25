"""Generate fake employee records (security_level=3, doc_type=employee_record).

This module produces Traditional Chinese employee profile documents using
Faker's `zh_TW` locale. Each record contains highly sensitive PII (national
ID, salary, address, etc.) and MUST be tagged with security_level=3 per the
project's data-layer rules in CLAUDE.md.

The records returned by `generate()` are dicts conforming to the shared
metadata schema (doc_id, doc_type, department, security_level, text) and are
intended to be consumed by `run_all.py` for serialization to JSON.
"""

from __future__ import annotations

import random
import string
import sys
from pathlib import Path
from typing import Any

# Make `backend.config.settings` importable when this file is executed both as
# a module (`python -m backend.data_gen.generate_employees`) and as a script.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from faker import Faker  # noqa: E402

from backend.config.settings import get_settings  # noqa: E402


# Traditional-Chinese department list shared across all generators.
_DEPARTMENTS: list[str] = [
    "人資部",
    "財務部",
    "工程部",
    "行銷部",
    "法務部",
    "業務部",
]

# A small pool of plausible Taiwanese job titles.
_TITLES: list[str] = [
    "資深工程師",
    "軟體工程師",
    "專案經理",
    "產品經理",
    "資深經理",
    "行銷專員",
    "業務代表",
    "財務分析師",
    "人資專員",
    "法務專員",
    "助理工程師",
    "資深顧問",
]

# Educational backgrounds.
_EDUCATION: list[str] = [
    "國立臺灣大學資訊工程學系學士",
    "國立清華大學電機工程學系碩士",
    "國立交通大學資訊管理學系學士",
    "國立政治大學企業管理學系碩士",
    "國立成功大學工業管理學系學士",
    "私立輔仁大學法律學系學士",
    "私立淡江大學財務金融學系學士",
]

# Common Taiwanese family relationships for emergency contacts.
_RELATIONS: list[str] = ["配偶", "父親", "母親", "兄長", "姊姊", "弟弟", "妹妹"]


def _generate_taiwan_id(rng: random.Random) -> str:
    """Generate a plausible Taiwanese national ID string.

    The format is one uppercase ASCII letter followed by nine digits. The
    check digit logic is not enforced — these are synthetic identifiers used
    only for demo purposes and should never resemble real IDs.

    Args:
        rng: A seeded `random.Random` instance for deterministic output.

    Returns:
        A 10-character string such as "A123456789".
    """
    letter = rng.choice(string.ascii_uppercase)
    digits = "".join(rng.choices(string.digits, k=9))
    return f"{letter}{digits}"


def _build_record(
    fake: Faker,
    rng: random.Random,
    index: int,
    template: str,
) -> dict[str, Any]:
    """Build a single employee record dict.

    Args:
        fake: A configured Faker instance (locale zh_TW).
        rng: A seeded `random.Random` for non-Faker randomization.
        index: 1-based counter used to form the employee/document ID.
        template: The raw template string to be `.format()`ed.

    Returns:
        A record dict with metadata keys plus the rendered `text` field.
    """
    settings = get_settings()
    meta = settings.METADATA_KEYS

    emp_id = f"EMP-{index:04d}"
    department = rng.choice(_DEPARTMENTS)
    name = fake.name()

    # Salary expressed in 10,000-NT-dollar units (per the spec: 萬元).
    # We render this as the actual NT-dollar amount in the template so the
    # number looks natural; the metadata stores the rendered text only.
    salary_man = rng.randint(50, 200)
    salary_ntd = f"{salary_man * 10000:,}"

    fields = {
        "name": name,
        "emp_id": emp_id,
        "department": department,
        "title": rng.choice(_TITLES),
        "start_date": fake.date_between(start_date="-10y", end_date="-1y").isoformat(),
        "birth_date": fake.date_of_birth(minimum_age=22, maximum_age=60).isoformat(),
        "education": rng.choice(_EDUCATION),
        "salary": salary_ntd,
        "bank_account": fake.bban(),
        "ssn": _generate_taiwan_id(rng),
        "phone": fake.phone_number(),
        "email": fake.company_email(),
        "address": fake.address().replace("\n", " "),
        "emergency_name": fake.name(),
        "emergency_relation": rng.choice(_RELATIONS),
        "emergency_phone": fake.phone_number(),
    }

    text = template.format(**fields)

    return {
        meta["doc_id"]: emp_id,
        meta["doc_type"]: "employee_record",
        meta["department"]: department,
        meta["security_level"]: 3,
        meta["text"]: text,
    }


def generate(n: int, seed: int | None = None) -> list[dict]:
    """Generate `n` employee records.

    Args:
        n: The number of employee records to produce.
        seed: Optional integer seed. When provided, both Faker and the random
            number generator are seeded so output is fully deterministic.

    Returns:
        A list of `n` record dicts conforming to the shared metadata schema.

    Raises:
        FileNotFoundError: If the employee_profile template is missing.
    """
    settings = get_settings()
    template_path = settings.TEMPLATES_DIR / "employee_profile.txt"
    template = template_path.read_text(encoding="utf-8")

    fake = Faker(locale="zh_TW")
    rng = random.Random(seed)
    if seed is not None:
        Faker.seed(seed)

    return [_build_record(fake, rng, i + 1, template) for i in range(n)]


__all__: list[str] = ["generate"]
