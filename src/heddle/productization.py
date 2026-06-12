from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DOGFOOD_RESULTS = Path("/tmp/heddle-dogfood-results.json")
SOLO_THRESHOLD = 8
FEDERATION_THRESHOLD = 8


@dataclass(frozen=True)
class ProductizationDecision:
    allowed: bool
    recommendation: str
    reason: str


def read_productization_decision(
    report_path: Path = Path("spike/REPORT.md"),
    dogfood_results_path: Path = DEFAULT_DOGFOOD_RESULTS,
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
    if recommendation in {"no-go", "park-until-cutover"}:
        return ProductizationDecision(
            False,
            recommendation,
            f"spike recommendation is {recommendation}",
        )
    if recommendation == "go":
        return _dogfood_productization_decision(dogfood_results_path)
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


def _dogfood_productization_decision(path: Path) -> ProductizationDecision:
    if not path.exists():
        return ProductizationDecision(False, "dogfood-missing", "dogfood results not found")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ProductizationDecision(False, "dogfood-invalid", "dogfood results are invalid JSON")
    if not isinstance(payload, dict):
        return ProductizationDecision(False, "dogfood-invalid", "dogfood results are not an object")
    summary = payload.get("summary")
    thresholds = payload.get("thresholds")
    if not isinstance(summary, dict) or not isinstance(thresholds, dict):
        return ProductizationDecision(False, "dogfood-invalid", "dogfood summary missing")
    solo = summary.get("solo")
    federation = summary.get("federation")
    if not isinstance(solo, dict) or not isinstance(federation, dict):
        return ProductizationDecision(False, "dogfood-invalid", "dogfood lane summary missing")
    solo_threshold = _int_or_default(thresholds.get("solo_parity"), SOLO_THRESHOLD)
    federation_threshold = _int_or_default(
        thresholds.get("federation_uplift"),
        FEDERATION_THRESHOLD,
    )
    solo_parity = _int_or_default(solo.get("parity"), -1)
    federation_uplift = _int_or_default(federation.get("uplift"), -1)
    if (
        payload.get("ready") is not True
        or solo_parity < solo_threshold
        or federation_uplift < federation_threshold
    ):
        return ProductizationDecision(
            False,
            "dogfood-failed",
            "dogfood thresholds not met",
        )
    return ProductizationDecision(True, "go", "spike recommendation is go and dogfood passed")


def _int_or_default(value: object, default: int) -> int:
    return value if isinstance(value, int) else default
