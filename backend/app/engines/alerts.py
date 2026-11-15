"""Budgeted Explainable Alert Policy Engine for AstroGuard (F-20, F-21, F-28).

Policy guarantees:
1. Deterministic hard safety rules (`SR-01`..`SR-05`) ALWAYS bypass weekly budget,
   cooldown, and deduplication.
2. Data faults (`anomaly_type == "data_fault"`) NEVER raise a health alert; they are
   routed cleanly to `data_quality_notices`.
3. Non-critical advisory alerts enforce a confidence floor (`min_confidence`),
   per-signal cooldown (`cooldown_days`), and per-astronaut-week budget (`weekly_budget`).
4. Every surviving alert includes a structured Why Card (`what_changed`,
   `how_sure_and_why`, `single_best_next_step`) and curated `protocols`.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.protocols import get_protocols
from app.schema import AnomalyFlag

_ANOMALY_TYPE_RANK: Dict[str, int] = {
    "multivariate": 3,
    "drift": 2,
    "contextual": 1,
    "data_fault": 0,
}

_SIGNAL_DEFAULT_PROTOCOLS: Dict[str, List[str]] = {
    "hr_recovery_1m": ["PROT-REC-01", "PROT-REC-02"],
    "resting_hr": ["PROT-REC-01", "PROT-REC-02"],
    "heart_rate": ["PROT-REC-01", "PROT-REC-02"],
    "hrv_rmssd": ["PROT-REC-01", "PROT-SLP-01"],
    "sleep_duration": ["PROT-SLP-01"],
    "sleep_fragmentation": ["PROT-SLP-01", "PROT-SLP-02"],
    "pvt_mean_rt": ["PROT-SLP-02", "PROT-SLP-01"],
    "pvt_lapses": ["PROT-SLP-02", "PROT-SLP-01"],
    "co2_ppm": ["PROT-ENV-01", "PROT-ENV-02"],
    "symptom_headache": ["PROT-ENV-02", "PROT-ENV-01"],
    "symptom_fatigue": ["PROT-ENV-02", "PROT-REC-01"],
    "radiation_usv_day": ["PROT-RAD-01"],
    "radiation_cumulative_msv": ["PROT-RAD-01"],
}


def _coerce_flag(item: AnomalyFlag | Dict[str, Any]) -> AnomalyFlag:
    if isinstance(item, AnomalyFlag):
        return item
    return AnomalyFlag(
        signal=str(item["signal"]),
        window=list(item.get("window", [])),
        anomaly_type=str(item["anomaly_type"]),
        score=float(item.get("score", 0.0)),
        confidence=float(item.get("confidence", 0.0)),
        baseline_context=str(item.get("baseline_context", "rest")),
        personal_range=list(item.get("personal_range", [])),
        observed=item.get("observed"),
        contributors=list(item.get("contributors", [])),
        data_quality=dict(item.get("data_quality", {})),
        evidence_ref=str(item.get("evidence_ref", "")),
        protocol_refs=list(item.get("protocol_refs", [])),
        astronaut_id=str(item.get("astronaut_id", "")),
        day=int(item.get("day", 23)),
        title=str(item.get("title", "")),
        explanation=str(item.get("explanation", "")),
    )


def _resolve_protocol_refs(flag: AnomalyFlag) -> List[str]:
    if flag.protocol_refs:
        return list(flag.protocol_refs)
    if flag.signal in _SIGNAL_DEFAULT_PROTOCOLS:
        return list(_SIGNAL_DEFAULT_PROTOCOLS[flag.signal])
    for contrib in flag.contributors:
        if contrib in _SIGNAL_DEFAULT_PROTOCOLS:
            return list(_SIGNAL_DEFAULT_PROTOCOLS[contrib])
    if flag.anomaly_type == "multivariate":
        return ["PROT-REC-01", "PROT-SLP-01"]
    return ["PROT-MED-01"]


def _severity_for_flag(flag: AnomalyFlag) -> Tuple[str, str]:
    impact = float(flag.score) * float(flag.confidence)
    if flag.anomaly_type == "multivariate" or impact >= 2.2 or float(flag.score) >= 2.8:
        return "caution", "Check-in suggested"
    return "watch", "Watch"


def _build_advisory_why_card(
    flag: AnomalyFlag,
    protocols: Sequence[Dict[str, object]],
    grouped_variants: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    conf_pct = round(float(flag.confidence) * 100)
    window_str = " -> ".join(flag.window) if flag.window else f"Day {flag.day}"

    what_changed = flag.explanation.strip() if flag.explanation else ""
    if not what_changed:
        obs_part = f" (observed {flag.observed})" if flag.observed is not None else ""
        range_part = (
            f" vs personal early-mission range {flag.personal_range[0]}..{flag.personal_range[1]}"
            if len(flag.personal_range) == 2
            else ""
        )
        what_changed = (
            f"{flag.signal} showed a {flag.anomaly_type} shift in {flag.baseline_context} "
            f"context{obs_part}{range_part}; this may reflect accumulated strain or an environmental confounder."
        )

    contributors_text = ", ".join(flag.contributors) if flag.contributors else flag.signal
    coverage = flag.data_quality.get("coverage")
    cov_text = f" Data coverage {round(float(coverage) * 100)}%." if coverage is not None else ""
    grouped_text = (
        f" Grouped {len(grouped_variants)} related lower-priority variation(s)."
        if grouped_variants
        else ""
    )
    how_sure_and_why = (
        f"Confidence is {conf_pct}% over {window_str} (contributors: {contributors_text})."
        f"{cov_text}{grouped_text}"
    )

    if protocols:
        first_proto = protocols[0]
        steps = first_proto.get("steps") or []
        first_step = str(steps[0]) if steps else str(first_proto.get("summary", ""))
        next_step = f"{first_proto.get('protocol_id')}: {first_proto.get('title')} — {first_step}"
    else:
        next_step = "Complete a 1-minute check-in and review recent sleep, recovery, and habitat CO2 context."

    return {
        "what_changed": what_changed,
        "how_sure_and_why": how_sure_and_why,
        "single_best_next_step": next_step,
        "evidence_window": list(flag.window),
        "confidence_pct": conf_pct,
        "non_diagnostic_note": "Decision support only, not a diagnosis. Cause language uses association ('may'/'possible').",
    }


def _build_safety_alert(rule: Dict[str, Any]) -> Dict[str, Any]:
    protocol_refs = list(rule.get("protocol_refs") or ["PROT-MED-01"])
    protocols = get_protocols(protocol_refs)
    first_step = ""
    if protocols:
        steps = protocols[0].get("steps") or []
        first_step = str(steps[0]) if steps else str(protocols[0].get("summary", ""))

    summary = str(rule.get("summary") or rule.get("title") or "Deterministic safety rule triggered.")
    human_prompt = str(rule.get("human_contact_prompt") or "").strip()
    next_step = human_prompt or (
        f"{protocols[0]['protocol_id']}: {first_step}"
        if protocols
        else "Follow deterministic safety checklist and alert Crew Health Officer."
    )

    alert = dict(rule)
    alert["bypassed_budget"] = True
    alert["deterministic"] = True
    alert["cannot_downgrade"] = True
    alert["protocol_refs"] = protocol_refs
    alert["protocols"] = protocols
    alert["why_card"] = {
        "what_changed": summary,
        "how_sure_and_why": "Deterministic rule threshold met directly on verified telemetry/beacon; AI cannot downgrade or suppress.",
        "single_best_next_step": next_step,
        "evidence_window": [str(rule.get("timestamp") or f"Day {rule.get('day', 23)}")],
        "confidence_pct": 100,
        "non_diagnostic_note": "Deterministic safety protocol — immediate human review required.",
    }
    return alert


class AlertPolicyEngine:
    """Enforces alert budget, cooldown, deduplication, confidence floor, and safety bypass."""

    def __init__(
        self,
        weekly_budget: int = 3,
        cooldown_days: int = 2,
        min_confidence: float = 0.65,
    ) -> None:
        if weekly_budget < 0:
            raise ValueError("weekly_budget must be >= 0")
        if cooldown_days < 0:
            raise ValueError("cooldown_days must be >= 0")
        if not (0.0 <= float(min_confidence) <= 1.0):
            raise ValueError("min_confidence must be in [0, 1]")
        self.weekly_budget = int(weekly_budget)
        self.cooldown_days = int(cooldown_days)
        self.min_confidence = float(min_confidence)

    def evaluate_alerts(
        self,
        flags: Iterable[AnomalyFlag | Dict[str, Any]],
        safety_rules: Optional[Iterable[Dict[str, Any]]] = None,
        up_to_day: int = 23,
    ) -> Dict[str, Any]:
        """Evaluate anomaly flags and deterministic safety rules up to `up_to_day`."""
        safety_alerts: List[Dict[str, Any]] = []
        historical_safety_alerts: List[Dict[str, Any]] = []
        for rule in safety_rules or []:
            if not isinstance(rule, dict):
                continue
            built = _build_safety_alert(rule)
            if bool(rule.get("active", True)):
                safety_alerts.append(built)
            else:
                historical_safety_alerts.append(built)

        data_quality_notices: List[Dict[str, Any]] = []
        qualified_flags: List[AnomalyFlag] = []
        suppressed_by_reason: Dict[str, int] = {
            "low_confidence": 0,
            "cooldown": 0,
            "weekly_budget": 0,
        }
        suppressed_grouped_count = 0

        for raw in flags:
            flag = _coerce_flag(raw)
            if flag.day > up_to_day:
                continue
            if flag.anomaly_type == "data_fault":
                data_quality_notices.append(
                    {
                        "astronaut_id": flag.astronaut_id,
                        "signal": flag.signal,
                        "day": flag.day,
                        "window": list(flag.window),
                        "contributors": list(flag.contributors),
                        "data_quality": dict(flag.data_quality),
                        "evidence_ref": flag.evidence_ref,
                        "title": flag.title or f"Data quality notice: {flag.signal}",
                        "explanation": flag.explanation,
                        "routed_to": "data_quality_state",
                    }
                )
                continue
            if float(flag.confidence) < self.min_confidence:
                suppressed_by_reason["low_confidence"] += 1
                suppressed_grouped_count += 1
                continue
            qualified_flags.append(flag)

        # Deduplication & cooldown per (astronaut_id, signal), chronologically
        by_astro_signal: Dict[Tuple[str, str], List[AnomalyFlag]] = {}
        for flag in qualified_flags:
            by_astro_signal.setdefault((flag.astronaut_id, flag.signal), []).append(flag)

        post_cooldown: List[Tuple[AnomalyFlag, List[Dict[str, Any]]]] = []
        for (_, _), group in sorted(by_astro_signal.items()):
            group.sort(
                key=lambda f: (
                    f.day,
                    -_ANOMALY_TYPE_RANK.get(f.anomaly_type, 0),
                    -(float(f.score) * float(f.confidence)),
                    -float(f.score),
                    f.evidence_ref,
                )
            )
            last_emitted_day: Optional[int] = None
            current_variants: Optional[List[Dict[str, Any]]] = None

            for flag in group:
                if last_emitted_day is not None and (flag.day - last_emitted_day) <= self.cooldown_days:
                    suppressed_by_reason["cooldown"] += 1
                    suppressed_grouped_count += 1
                    if current_variants is not None:
                        current_variants.append(
                            {
                                "day": flag.day,
                                "anomaly_type": flag.anomaly_type,
                                "signal": flag.signal,
                                "score": flag.score,
                                "confidence": flag.confidence,
                                "reason": "cooldown_or_duplicate",
                                "evidence_ref": flag.evidence_ref,
                            }
                        )
                    continue
                variants_list: List[Dict[str, Any]] = []
                post_cooldown.append((flag, variants_list))
                last_emitted_day = flag.day
                current_variants = variants_list

        # Rolling 7-day budget window ending at up_to_day
        window_start = max(1, up_to_day - 6)
        in_window = [(f, v) for (f, v) in post_cooldown if window_start <= f.day <= up_to_day]

        by_astro_window: Dict[str, List[Tuple[AnomalyFlag, List[Dict[str, Any]]]]] = {}
        for flag, variants in in_window:
            by_astro_window.setdefault(flag.astronaut_id, []).append((flag, variants))

        active_alerts: List[Dict[str, Any]] = []
        used_by_astronaut: Dict[str, int] = {}
        remaining_by_astronaut: Dict[str, int] = {}

        for astro_id in sorted(by_astro_window):
            candidates = by_astro_window[astro_id]
            candidates.sort(
                key=lambda item: (
                    _ANOMALY_TYPE_RANK.get(item[0].anomaly_type, 0),
                    float(item[0].score) * float(item[0].confidence),
                    float(item[0].score),
                    float(item[0].confidence),
                    int(item[0].day),
                ),
                reverse=True,
            )
            kept = candidates[: self.weekly_budget]
            dropped = candidates[self.weekly_budget :]

            if dropped:
                suppressed_by_reason["weekly_budget"] += len(dropped)
                suppressed_grouped_count += len(dropped)

            used_by_astronaut[astro_id] = len(kept)
            remaining_by_astronaut[astro_id] = max(0, self.weekly_budget - len(kept))

            for flag, variants in kept:
                proto_refs = _resolve_protocol_refs(flag)
                protocols = get_protocols(proto_refs)
                severity, status_label = _severity_for_flag(flag)
                why_card = _build_advisory_why_card(flag, protocols, variants)
                title = flag.title or f"{flag.signal} ({flag.anomaly_type})"

                active_alerts.append(
                    {
                        "alert_id": f"alert-{flag.astronaut_id or 'crew'}-{flag.signal}-{flag.anomaly_type}-d{flag.day}",
                        "astronaut_id": flag.astronaut_id,
                        "day": flag.day,
                        "signal": flag.signal,
                        "anomaly_type": flag.anomaly_type,
                        "severity": severity,
                        "status_label": status_label,
                        "title": title,
                        "score": round(float(flag.score), 3),
                        "confidence": round(float(flag.confidence), 3),
                        "baseline_context": flag.baseline_context,
                        "personal_range": list(flag.personal_range),
                        "observed": flag.observed,
                        "window": list(flag.window),
                        "contributors": list(flag.contributors),
                        "data_quality": dict(flag.data_quality),
                        "evidence_ref": flag.evidence_ref,
                        "why_card": why_card,
                        "summary": why_card["what_changed"],
                        "protocol_refs": proto_refs,
                        "protocols": protocols,
                        "grouped_count": len(variants),
                        "grouped_variants": variants,
                        "deterministic": False,
                        "cannot_downgrade": False,
                    }
                )

        active_alerts.sort(
            key=lambda a: (
                float(a["score"]) * float(a["confidence"]),
                float(a["score"]),
                int(a["day"]),
            ),
            reverse=True,
        )

        budget_status = {
            "weekly_budget_per_astronaut": self.weekly_budget,
            "cooldown_days": self.cooldown_days,
            "min_confidence": self.min_confidence,
            "window_days": [window_start, up_to_day],
            "used_by_astronaut": used_by_astronaut,
            "remaining_by_astronaut": remaining_by_astronaut,
            "total_active_advisory": len(active_alerts),
            "total_active_safety": len(safety_alerts),
            "safety_bypass_count": len(safety_alerts),
            "suppressed_grouped_count": suppressed_grouped_count,
            "suppressed_by_reason": suppressed_by_reason,
            "data_fault_filtered_count": len(data_quality_notices),
        }

        return {
            "active_alerts": active_alerts,
            "suppressed_grouped_count": suppressed_grouped_count,
            "safety_alerts": safety_alerts,
            "historical_safety_alerts": historical_safety_alerts,
            "data_quality_notices": data_quality_notices,
            "budget_status": budget_status,
        }
