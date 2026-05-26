"""Knowledge-base integrity scanner — Defense #4 (KB data governance).

This script is the demo artefact for Slide 7's "資料治理 / 知識庫完整性掃描"
defense. The presenter runs it on stage immediately after Act 3 (the prompt-
injection exfiltration scene) to show the audience that an automated content
scan, executed at ingest time, would have flagged and quarantined every
poisoned document BEFORE it reached ChromaDB.

What the script does:

* Iterates over every JSON file in ``data/generated/`` that the demo
  pipeline would normally ingest (``employees.json``, ``internal_docs.json``,
  ``public_docs.json``, ``poisoned_docs.json``).
* For each document, applies a battery of regular expressions that match
  well-known prompt-injection markers (system-note banners, ``ignore previous
  instructions``-style directives, HTML comment payloads, etc.).
* Emits a human-readable report (default) or a machine-readable JSON report
  (``--json``).
* Optionally moves suspicious documents into ``data/generated/quarantine/``
  when ``--quarantine`` is supplied. The default is REPORT-ONLY; we never
  mutate the dataset implicitly.

Exit-code policy (CI-friendly):

* Without ``--strict``: always exits ``0``. This is the safe default so a
  presenter's live ``Ctrl-C`` muscle-memory never produces a confusing
  non-zero return on stage.
* With ``--strict``: exits ``1`` whenever at least one suspicious document
  is detected. Wire this into pre-commit / CI to block poisoned content
  from being merged.

Usage:

    # As a module (preferred):
    python -m backend.scripts.check_kb_integrity

    # Direct invocation also works thanks to the sys.path shim below.
    python backend/scripts/check_kb_integrity.py

    # Strict mode for CI:
    python -m backend.scripts.check_kb_integrity --strict

    # Machine-readable output:
    python -m backend.scripts.check_kb_integrity --json

    # Actually quarantine the offending files (writes to data/generated/quarantine/):
    python -m backend.scripts.check_kb_integrity --quarantine
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# sys.path shim
# ---------------------------------------------------------------------------
# Support both `python -m backend.scripts.check_kb_integrity` and
# `python backend/scripts/check_kb_integrity.py` by inserting the project root
# into sys.path when this file is executed directly.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.config.settings import get_settings  # noqa: E402  (after path shim)


# ---------------------------------------------------------------------------
# Injection patterns
# ---------------------------------------------------------------------------
# Compiled once at module import. Each tuple is (compiled_pattern, label).
# The label is what appears in the report — keep it short and demo-readable.
_INJECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"【\s*系統內部備註\s*】"), "【系統內部備註】 marker"),
    (re.compile(r"\[\s*INTERNAL\s*\]"), "[INTERNAL] marker"),
    (
        re.compile(r"SYSTEM\s+(?:OVERRIDE|NOTE)", re.IGNORECASE),
        "SYSTEM OVERRIDE/NOTE",
    ),
    (
        re.compile(
            r"ignore\s+(?:previous|all|above|prior)\s+instructions",
            re.IGNORECASE,
        ),
        "ignore-previous-instructions style",
    ),
    (
        re.compile(r"請忽略(?:上述|前述|先前|所有)"),
        "請忽略 directive (zh-TW)",
    ),
    (re.compile(r"reveal\s+all\s+PII", re.IGNORECASE), "reveal PII directive"),
    (re.compile(r"<!--.*?-->", re.DOTALL), "HTML comment block"),
]

# Canonical filenames the demo's seed pipeline ingests. Order matches the
# expected presentation order on stage.
_DATASET_FILES: tuple[str, ...] = (
    "employees.json",
    "internal_docs.json",
    "public_docs.json",
    "poisoned_docs.json",
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class DocFinding:
    """Result of scanning a single document.

    Attributes:
        doc_id: The document identifier as carried in its JSON record.
        source_file: Filename (basename) the document came from.
        matched_labels: Human-readable labels of every pattern that matched.
    """

    doc_id: str
    source_file: str
    matched_labels: list[str] = field(default_factory=list)

    @property
    def is_suspicious(self) -> bool:
        """Whether this document triggered at least one injection pattern."""
        return bool(self.matched_labels)


@dataclass
class FileReport:
    """Aggregated scan result for a single dataset file.

    Attributes:
        path: Absolute path to the scanned JSON file.
        doc_count: Total number of documents read from the file.
        findings: One ``DocFinding`` per document that matched any pattern.
                  Clean documents are intentionally omitted to keep the
                  report focused.
    """

    path: Path
    doc_count: int
    findings: list[DocFinding] = field(default_factory=list)

    @property
    def suspicious_count(self) -> int:
        """Number of suspicious documents in this file."""
        return len(self.findings)


# ---------------------------------------------------------------------------
# Scanning logic
# ---------------------------------------------------------------------------
def scan_text(text: str) -> list[str]:
    """Return the labels of every injection pattern matched in ``text``.

    Args:
        text: The document body to scan.

    Returns:
        A list of pattern labels (preserves the declaration order of
        ``_INJECTION_PATTERNS``). Empty if the text is clean.
    """
    matched: list[str] = []
    for pattern, label in _INJECTION_PATTERNS:
        if pattern.search(text):
            matched.append(label)
    return matched


def scan_file(path: Path) -> FileReport:
    """Scan every document in a single JSON dataset file.

    Args:
        path: Absolute path to a JSON file whose top-level value is a list
              of dicts, each carrying at least ``doc_id`` and ``text``.

    Returns:
        A :class:`FileReport` summarising the scan.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the JSON payload is not a list of dicts.
    """
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    if not isinstance(payload, list):
        raise ValueError(
            f"Expected a JSON list at top level of {path.name}, "
            f"got {type(payload).__name__}"
        )

    report = FileReport(path=path, doc_count=len(payload))

    for record in payload:
        if not isinstance(record, dict):
            # Defensive: skip non-dict entries but do not crash the scan.
            continue
        doc_id = str(record.get("doc_id", "<missing doc_id>"))
        text = str(record.get("text", ""))
        matched = scan_text(text)
        if matched:
            report.findings.append(
                DocFinding(
                    doc_id=doc_id,
                    source_file=path.name,
                    matched_labels=matched,
                )
            )

    return report


def scan_generated_dir(generated_dir: Path) -> list[FileReport]:
    """Scan every known dataset file under ``generated_dir``.

    Files that do not exist are silently skipped — the demo may legitimately
    run before ``seed.py`` has produced all four datasets.

    Args:
        generated_dir: The ``data/generated`` directory from settings.

    Returns:
        One :class:`FileReport` per dataset file that was found.
    """
    reports: list[FileReport] = []
    for name in _DATASET_FILES:
        path = generated_dir / name
        if not path.exists():
            continue
        reports.append(scan_file(path))
    return reports


# ---------------------------------------------------------------------------
# Quarantine
# ---------------------------------------------------------------------------
def quarantine_suspicious(
    reports: list[FileReport],
    generated_dir: Path,
) -> Path | None:
    """Move the JSON files that contain suspicious docs into a quarantine dir.

    The strategy is intentionally coarse: an entire file is moved if it
    contains any suspicious document. The demo's poisoned dataset is the
    only file we expect to trip this in practice, so per-document surgery
    would be overkill and risks silently dropping clean records.

    Args:
        reports: The scan results returned by :func:`scan_generated_dir`.
        generated_dir: Same path that was scanned.

    Returns:
        The quarantine directory (created if needed) when at least one file
        was moved; ``None`` if nothing needed quarantining.
    """
    suspicious_files = [r.path for r in reports if r.suspicious_count]
    if not suspicious_files:
        return None

    quarantine_dir = generated_dir / "quarantine"
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    for src in suspicious_files:
        dest = quarantine_dir / src.name
        # If a previous quarantine run already placed a file here, overwrite
        # it — the latest scan is the source of truth.
        if dest.exists():
            dest.unlink()
        shutil.move(str(src), str(dest))

    return quarantine_dir


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
_RULE = "=" * 64


def render_text_report(
    reports: list[FileReport],
    generated_dir: Path,
) -> str:
    """Render the human-readable scan report.

    Args:
        reports: The scan results returned by :func:`scan_generated_dir`.
        generated_dir: The directory those reports came from. Used to
                       render relative paths in the output for readability.

    Returns:
        The full multi-line report as a single string.
    """
    lines: list[str] = []
    lines.append(_RULE)
    lines.append("NovaTech Knowledge Base Integrity Scan")
    lines.append(_RULE)

    total_docs = 0
    total_suspicious = 0
    suspicious_ids: list[str] = []
    suspicious_files: list[str] = []

    for report in reports:
        rel = report.path.relative_to(generated_dir.parent.parent)
        lines.append(
            f"Scanning: {rel} ({report.doc_count} docs)"
        )
        total_docs += report.doc_count

        if not report.findings:
            lines.append("  ✓ Clean")
        else:
            total_suspicious += report.suspicious_count
            suspicious_files.append(report.path.name)
            for finding in report.findings:
                suspicious_ids.append(finding.doc_id)
                count = len(finding.matched_labels)
                lines.append(
                    f"  ⚠ {finding.doc_id}: {count} injection "
                    f"marker{'s' if count != 1 else ''} detected"
                )
                for label in finding.matched_labels:
                    lines.append(f"      • Pattern \"{label}\" matched")
                lines.append(
                    "      ➜ Recommended action: QUARANTINE — "
                    "do not ingest into vector DB"
                )
        lines.append("")

    lines.append(_RULE)
    lines.append("Summary")
    lines.append(_RULE)
    lines.append(f"  Total documents scanned: {total_docs}")
    lines.append(f"  Clean: {total_docs - total_suspicious}")

    if total_suspicious == 0:
        lines.append("  Suspicious: 0")
    else:
        files_phrase = ", ".join(suspicious_files)
        lines.append(
            f"  Suspicious: {total_suspicious} (all in {files_phrase})"
        )
        lines.append("")
        lines.append("  Quarantine list:")
        # Two-space indent, doc_ids separated by two spaces.
        lines.append("    " + "  ".join(suspicious_ids))

    lines.append("")
    lines.append(
        "  In a production pipeline these documents would be blocked before"
    )
    lines.append(
        "  they reach ChromaDB. The Act 3 demo intentionally bypasses this"
    )
    lines.append("  step to demonstrate what happens without governance.")
    lines.append(_RULE)
    return "\n".join(lines)


def render_json_report(
    reports: list[FileReport],
    generated_dir: Path,
) -> str:
    """Render the machine-readable JSON report.

    Args:
        reports: The scan results returned by :func:`scan_generated_dir`.
        generated_dir: The directory those reports came from. Used to
                       compute relative paths in the JSON payload.

    Returns:
        A JSON string with ``indent=2`` and ``ensure_ascii=False`` so the
        Traditional-Chinese pattern labels stay readable in the output.
    """
    total_docs = sum(r.doc_count for r in reports)
    suspicious: list[dict[str, Any]] = []
    for report in reports:
        for finding in report.findings:
            suspicious.append(asdict(finding))

    payload: dict[str, Any] = {
        "files": [
            {
                "path": str(r.path.relative_to(generated_dir.parent.parent)),
                "doc_count": r.doc_count,
                "suspicious_count": r.suspicious_count,
            }
            for r in reports
        ],
        "totals": {
            "documents_scanned": total_docs,
            "suspicious_documents": len(suspicious),
            "clean_documents": total_docs - len(suspicious),
        },
        "suspicious": suspicious,
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _build_arg_parser() -> argparse.ArgumentParser:
    """Construct the :mod:`argparse` parser for this CLI.

    Returns:
        A configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="check_kb_integrity",
        description=(
            "Scan data/generated/*.json for prompt-injection markers. "
            "Defense #4 demo artefact."
        ),
    )
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="Emit a machine-readable JSON report instead of the text report.",
    )
    parser.add_argument(
        "--quarantine",
        action="store_true",
        help=(
            "Move JSON files containing suspicious documents into "
            "data/generated/quarantine/ instead of merely reporting on them. "
            "Default is REPORT-ONLY."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Return a non-zero exit code (1) when suspicious documents are "
            "found. Default is to always return 0 so live demos never "
            "surface a misleading non-zero status."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for both module and direct execution.

    Args:
        argv: Optional argument vector; defaults to :data:`sys.argv` slice.

    Returns:
        Process exit code (``0`` for clean / non-strict, ``1`` for strict
        mode with detected suspicious documents).
    """
    args = _build_arg_parser().parse_args(argv)

    settings = get_settings()
    generated_dir: Path = settings.DATA_GENERATED_DIR

    if not generated_dir.exists():
        sys.stderr.write(
            f"ERROR: generated data directory not found: {generated_dir}\n"
            "Run `python -m backend.scripts.seed` (or the generator) first.\n"
        )
        return 1

    reports = scan_generated_dir(generated_dir)

    if args.emit_json:
        print(render_json_report(reports, generated_dir))
    else:
        print(render_text_report(reports, generated_dir))

    suspicious_total = sum(r.suspicious_count for r in reports)

    if args.quarantine and suspicious_total:
        moved_to = quarantine_suspicious(reports, generated_dir)
        if moved_to is not None and not args.emit_json:
            print(f"\nQuarantined offending files into: {moved_to}")

    # Exit-code policy: only non-zero when --strict AND something was found.
    if args.strict and suspicious_total:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
