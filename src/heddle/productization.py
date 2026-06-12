from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProductizationDecision:
    allowed: bool
    recommendation: str
    reason: str


def read_productization_decision(
    report_path: Path = Path("spike/REPORT.md"),
) -> ProductizationDecision:
    if not report_path.exists():
        return ProductizationDecision(False, "missing", "spike report not found")
    text = report_path.read_text(encoding="utf-8")
    readiness_verdict = _readiness_verdict(text)
    if readiness_verdict in {"not-ready", "no-go", "park-until-cutover"}:
        return ProductizationDecision(
            False,
            readiness_verdict,
            f"readiness verdict is {readiness_verdict}",
        )
    recommendation = _recommendation(text)
    if recommendation == "go":
        return ProductizationDecision(True, recommendation, "spike recommendation is go")
    if recommendation in {"no-go", "park-until-cutover"}:
        return ProductizationDecision(
            False,
            recommendation,
            f"spike recommendation is {recommendation}",
        )
    return ProductizationDecision(False, "unknown", "spike report has no recognized recommendation")


def _readiness_verdict(text: str) -> str:
    for line in text.splitlines():
        normalized = line.strip().lower()
        if normalized.startswith("readiness verdict:"):
            return normalized.split(":", 1)[1].strip().split(maxsplit=1)[0]
    return "unknown"


def _recommendation(text: str) -> str:
    for line in text.splitlines():
        normalized = line.strip().lower()
        if normalized.startswith("recommendation:"):
            value = normalized.split(":", 1)[1].strip()
            for candidate in ("park-until-cutover", "no-go", "go"):
                if value.startswith(candidate):
                    return candidate
    return "unknown"
