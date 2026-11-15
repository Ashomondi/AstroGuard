"""Offline Retrieval-Grounded AstroGuard Advisor Engine (F-30).

Assembles daily briefings and grounded answers strictly from verified engine
outputs (`readiness`, `behavioral`, `environment`, `mside`, `counterfactual`)
and the curated `PROTOCOL_LIBRARY`.

Hard operational boundaries:
- Never invents numbers; cites exact evidence windows and confidence scores.
- Says "I don't know" when overall coverage < 60% or a requested signal is missing.
- Refuses medical diagnosis or prescribing.
- States deterministic safety rules cannot be downgraded, delayed, or suppressed.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from app.engines.counterfactual import simulate_intervention
from app.protocols import PROTOCOL_LIBRARY, get_protocols
from app.schema import SignalType


def _collect_safety_rules(
    active_safety_rules: Optional[Iterable[Any]],
    readiness_data: Optional[Dict[str, Any]],
    behavioral_data: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Gather active deterministic safety rules across caller inputs and engine outputs."""
    rules: List[Dict[str, Any]] = []
    seen_ids = set()

    def _add(item: Any) -> None:
        if isinstance(item, str):
            rid = item
            entry = {"rule_id": rid, "title": rid, "active": True}
        elif isinstance(item, dict):
            if item.get("active", True) is False:
                return
            rid = str(item.get("rule_id") or item.get("id") or item.get("title") or "SR")
            entry = dict(item)
            entry.setdefault("rule_id", rid)
        else:
            return
        if rid not in seen_ids:
            seen_ids.add(rid)
            rules.append(entry)

    for src in (active_safety_rules or []):
        _add(src)
    if readiness_data:
        for src in readiness_data.get("active_safety_rules", []):
            _add(src)
    if behavioral_data and behavioral_data.get("safety_triggered"):
        _add(
            {
                "rule_id": "SR-BEH",
                "title": "Deterministic behavioral safety support",
                "active": True,
            }
        )
    return rules


def _valid_protocols(protocol_ids: Iterable[str]) -> List[str]:
    """Keep unique protocol IDs present in PROTOCOL_LIBRARY."""
    out: List[str] = []
    for pid in protocol_ids:
        if pid in PROTOCOL_LIBRARY and pid not in out:
            out.append(pid)
    return out


def _format_obs_phrase(obs: Dict[str, Any]) -> str:
    """Render a grounded observation delta string strictly from observed numbers."""
    label = obs.get("label") or obs.get("signal")
    delta = obs.get("delta")
    unit = obs.get("unit", "")
    observed = obs.get("observed")
    baseline = obs.get("baseline")
    if delta is not None:
        sign = "+" if float(delta) > 0 else ""
        return f"{label} is {observed} {unit} ({sign}{delta} {unit} vs personal reference {baseline} {unit})"
    return f"{label} is {observed} {unit}"


def build_daily_briefing(
    readiness_data: Optional[Dict[str, Any]],
    behavioral_data: Optional[Dict[str, Any]] = None,
    env_data: Optional[Dict[str, Any]] = None,
    mside_data: Optional[Dict[str, Any]] = None,
    active_safety_rules: Optional[Iterable[Any]] = None,
    astronaut_id: str = "ast-01",
    up_to_day: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a structured, grounded daily briefing strictly from engine outputs and protocols."""
    day = int(up_to_day if up_to_day is not None else (readiness_data or {}).get("up_to_day", 23))
    rules = _collect_safety_rules(active_safety_rules, readiness_data, behavioral_data)
    safety_active = len(rules) > 0
    safety_notice = (
        "Deterministic safety alerts cannot be downgraded, delayed, or overridden by the Advisor."
    )

    dq = (readiness_data or {}).get("data_quality", {})
    coverage = float(dq.get("coverage", 0.0)) if readiness_data else 0.0
    overall_conf = float((readiness_data or {}).get("confidence", 0.0))

    # Insufficient data guard (<60% coverage or missing readiness state)
    if not readiness_data or coverage < 0.60:
        cov_pct = round(coverage * 100.0, 0)
        headline = (
            "Safety first, then verify missing telemetry."
            if safety_active
            else "I don't know — insufficient clean telemetry."
        )
        what_changed = (
            f"I don't know enough to interpret today's readiness trend reliably: clean data coverage "
            f"is {cov_pct:.0f}% (below the 60% minimum threshold). Missing or sensor-off periods are "
            "never imputed as normal."
        )
        if safety_active:
            rule_labels = ", ".join(r.get("rule_id", "SR") for r in rules)
            what_changed = f"Active deterministic safety rule(s) ({rule_labels}) require immediate review. {what_changed}"

        how_sure = (
            f"Confidence is insufficient ({round(overall_conf * 100.0):.0f}%) due to {cov_pct:.0f}% coverage."
        )
        proto_ids = _valid_protocols(["PROT-MED-01"] if safety_active else ["PROT-REC-02", "PROT-SLP-02"])
        protocols = get_protocols(proto_ids)
        next_step = (
            protocols[0]["steps"][0]
            if protocols
            else "Check wearable contact and run a fresh standardized check-in before acting on trend scores."
        )
        return {
            "astronaut_id": astronaut_id,
            "day": day,
            "headline": headline,
            "safety_active": safety_active,
            "active_safety_rules": rules,
            "safety_notice": safety_notice,
            "what_changed": what_changed,
            "how_sure_and_why": how_sure,
            "single_best_next_step": next_step,
            "protocol_refs": proto_ids,
            "protocols": protocols,
            "contributing_observations": [],
            "evidence_windows": [f"Day {day}"],
            "confidence": round(overall_conf, 3),
            "coverage": round(coverage, 3),
            "insufficient_data": True,
            "said_i_dont_know": True,
            "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
            "offline_mode": True,
            "text": f"{what_changed} {how_sure} Next: {next_step}",
        }

    rec = readiness_data.get("recovery_debt", {})
    cog = readiness_data.get("cognitive_readiness", {})
    rec_obs = rec.get("observations", [])
    cog_obs = cog.get("observations", [])
    band = readiness_data.get("band", "Monitor")

    # Select primary health driver strictly from engine observations
    rec_elevated = rec.get("status") in {"watch", "caution", "critical"}
    cog_reduced = cog.get("status") in {"watch", "caution", "critical"}

    change_parts: List[str] = []
    if safety_active:
        rule_labels = ", ".join(r.get("rule_id", "SR") for r in rules)
        change_parts.append(f"Active deterministic rule(s): {rule_labels}.")
    if rec_elevated and rec_obs:
        obs_txt = "; ".join(_format_obs_phrase(o) for o in rec_obs[:3])
        change_parts.append(f"Recovery debt is {rec.get('score')}/100: {obs_txt}.")
    if cog_reduced and cog_obs:
        obs_txt = "; ".join(_format_obs_phrase(o) for o in cog_obs[:3])
        change_parts.append(f"Cognitive readiness is {cog.get('score')}/100: {obs_txt}.")
    if env_data and env_data.get("shared_exposure_alert", {}).get("active"):
        change_parts.append(env_data["shared_exposure_alert"]["summary"])
    if behavioral_data and behavioral_data.get("underreporting_mismatch"):
        change_parts.append(behavioral_data.get("mismatch_prompt", ""))
    if not change_parts:
        change_parts.append(
            f"Recovery debt ({rec.get('score')}/100) and cognitive readiness ({cog.get('score')}/100) "
            "are within your personal early-mission range."
        )

    what_changed = " ".join(p for p in change_parts if p).strip()

    gap_notes: List[str] = []
    if dq.get("sensor_off_hours", 0) > 0:
        gap_notes.append(f"{dq['sensor_off_hours']}h sensor-off")
    if dq.get("missing_hours", 0) > 0:
        gap_notes.append(f"{dq['missing_hours']}h missing")
    if dq.get("suspect_count", 0) > 0:
        gap_notes.append(f"{dq['suspect_count']} suspect reading(s)")
    if dq.get("out_of_range_count", 0) > 0:
        gap_notes.append(f"{dq['out_of_range_count']} out-of-range reading(s)")
    gap_suffix = (
        f" Data caveats: {', '.join(gap_notes)} (gaps are preserved, not imputed)."
        if gap_notes
        else f" Data coverage is {coverage * 100:.0f}%."
    )
    how_sure = (
        f"Confidence is {overall_conf * 100:.0f}% (recovery {float(rec.get('confidence', overall_conf)) * 100:.0f}%, "
        f"cognitive {float(cog.get('confidence', overall_conf)) * 100:.0f}%).{gap_suffix}"
    )

    proto_candidates: List[str] = []
    if safety_active:
        proto_candidates.append("PROT-MED-01")
    if rec_elevated:
        proto_candidates.extend(rec.get("protocol_refs", ["PROT-REC-01", "PROT-REC-02"]))
    if cog_reduced:
        proto_candidates.extend(cog.get("protocol_refs", ["PROT-SLP-01", "PROT-SLP-02"]))
    if env_data and env_data.get("shared_exposure_alert", {}).get("active"):
        proto_candidates.extend(env_data["shared_exposure_alert"].get("protocol_refs", []))
    if not proto_candidates:
        proto_candidates = ["PROT-REC-02", "PROT-SLP-02"]

    proto_ids = _valid_protocols(proto_candidates)
    protocols = get_protocols(proto_ids)
    single_next = (
        f"{protocols[0]['title']}: {protocols[0]['steps'][0]}"
        if protocols
        else "Maintain standard sleep and wearable check-in windows."
    )

    if safety_active:
        headline = "Safety first, then the health signal."
    elif band == "Reduced":
        headline = "Readiness is reduced — prioritize recovery or rest."
    elif band in {"Monitor", "Watch"}:
        headline = "Watch personal trend changes."
    else:
        headline = "Signals are steady within personal baseline."

    contributing = list(rec_obs[:2]) + list(cog_obs[:2])
    evidence_windows = sorted(
        {str(o.get("window")) for o in contributing if o.get("window")}
        | {str(w) for fl in readiness_data.get("flags", []) for w in fl.get("window", [])}
    )
    if not evidence_windows:
        evidence_windows = [f"Day {day}"]

    return {
        "astronaut_id": astronaut_id,
        "day": day,
        "headline": headline,
        "safety_active": safety_active,
        "active_safety_rules": rules,
        "safety_notice": safety_notice,
        "what_changed": what_changed,
        "how_sure_and_why": how_sure,
        "single_best_next_step": single_next,
        "protocol_refs": proto_ids,
        "protocols": protocols,
        "contributing_observations": contributing,
        "evidence_windows": evidence_windows,
        "confidence": round(overall_conf, 3),
        "coverage": round(coverage, 3),
        "insufficient_data": False,
        "said_i_dont_know": False,
        "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
        "offline_mode": True,
        "text": f"{what_changed} {how_sure} Next: {single_next}",
    }


def _requested_signal_missing(
    q_lower: str,
    readiness_data: Optional[Dict[str, Any]],
    env_data: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Identify if the question specifically asks about a signal that is currently missing/unclean."""
    if not readiness_data:
        return "readiness telemetry"
    if "what if" in q_lower or "simulate" in q_lower:
        return None
    latest = readiness_data.get("latest_readings", {})
    checks = [
        (("hrv", "variability"), SignalType.HRV_RMSSD.value, "HRV"),
        (("resting hr", "resting heart", "heart rate", "pulse"), SignalType.RESTING_HR.value, "heart rate"),
        (("recovery", "exercise"), SignalType.HR_RECOVERY_1M.value, "1-min heart-rate recovery"),
        (("sleep",), SignalType.SLEEP_DURATION.value, "sleep"),
        (("pvt", "reaction"), SignalType.PVT_MEAN_RT.value, "PVT reaction time"),
        (("spo2", "oxygen"), SignalType.SPO2.value, "SpO2"),
        (("radiation", "dosim", "msv"), SignalType.RADIATION_CUMULATIVE_MSV.value, "radiation dosimetry"),
    ]
    for keywords, sig_key, label in checks:
        if any(kw in q_lower for kw in keywords):
            entry = latest.get(sig_key)
            if entry is None:
                return label
            if entry.get("is_gap") and (
                entry.get("last_clean_value") is None
                or entry.get("gap_hours", 0) >= 3
                or any(t in q_lower for t in ("current", "now", "today", "latest"))
            ):
                return label
    if any(kw in q_lower for kw in ("lab air", "co2", "cabin air", "scrubber")) and env_data is None:
        return "habitat CO2 telemetry"
    return None


def _parse_what_if_params(q_lower: str) -> Dict[str, Any]:
    """Extract optional sleep hours, days, and ventilation percentage from a what-if question."""
    params: Dict[str, Any] = {}
    m_sleep = re.search(r"(\d+(?:\.\d+)?)\s*(?:h|hr|hrs|hour|hours)\b", q_lower)
    if m_sleep:
        params["sleep_per_night"] = float(m_sleep.group(1))
    m_days = re.search(r"(\d+)\s*days?\b", q_lower)
    if m_days:
        params["horizon_days"] = int(m_days.group(1))
    m_vent = re.search(r"(\d+(?:\.\d+)?)\s*%", q_lower)
    if m_vent:
        params["cabin_ventilation_pct"] = float(m_vent.group(1))
    return params


def answer_question(
    question: str,
    readiness_data: Optional[Dict[str, Any]] = None,
    behavioral_data: Optional[Dict[str, Any]] = None,
    env_data: Optional[Dict[str, Any]] = None,
    mside_data: Optional[Dict[str, Any]] = None,
    active_safety_rules: Optional[Iterable[Any]] = None,
    counterfactual_data: Optional[Dict[str, Any]] = None,
    astronaut_id: str = "ast-01",
    up_to_day: Optional[int] = None,
) -> Dict[str, Any]:
    """Answer an astronaut/crew question strictly grounded in engine outputs and protocols."""
    q_text = (question or "").strip()
    q_lower = q_text.lower()
    day = int(up_to_day if up_to_day is not None else (readiness_data or {}).get("up_to_day", 23))

    rules = _collect_safety_rules(active_safety_rules, readiness_data, behavioral_data)
    safety_active = len(rules) > 0
    safety_notice = (
        "Deterministic safety rules and SOS alerts cannot be downgraded, delayed, suppressed, or overridden by the Advisor."
    )

    dq = (readiness_data or {}).get("data_quality", {})
    coverage = float(dq.get("coverage", 0.0)) if readiness_data else 0.0
    base_conf = float((readiness_data or {}).get("confidence", 0.0))

    # 1. Deterministic safety override protection
    if any(
        kw in q_lower
        for kw in ("downgrade", "dismiss", "cancel sos", "override safety", "ignore alert", "suppress alert")
    ):
        proto_ids = _valid_protocols(["PROT-MED-01" if safety_active else "PROT-ENV-01"])
        return {
            "question": q_text,
            "answer": (
                f"{safety_notice} Deterministic rules operate independently of AI and require explicit human/protocol resolution."
            ),
            "confidence": round(base_conf, 3),
            "evidence_windows": [f"Day {day}"],
            "cited_observations": [],
            "protocol_refs": proto_ids,
            "protocols": get_protocols(proto_ids),
            "said_i_dont_know": False,
            "refused_diagnosis": False,
            "safety_active": safety_active,
            "safety_notice": safety_notice,
            "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
            "offline_mode": True,
        }

    # 2. Refusal of medical diagnosis or prescribing
    if any(
        kw in q_lower
        for kw in (
            "diagnos",
            "prescrib",
            "prescription",
            "medication",
            "medicine",
            "antibiotic",
            "what disease",
            "do i have",
            "am i sick",
        )
    ):
        rec = (readiness_data or {}).get("recovery_debt", {})
        obs_list = rec.get("observations", [])
        obs_note = (
            f" Observed telemetry shows {_format_obs_phrase(obs_list[0])} (confidence {base_conf * 100:.0f}%)."
            if obs_list
            else ""
        )
        proto_ids = _valid_protocols(["PROT-MED-01", "PROT-REC-01"])
        ans = (
            "I cannot provide a medical diagnosis or prescribe medication or treatment. "
            "AstroGuard is an offline decision-support tool, not a physician."
            f"{obs_note} Please review these observations with the Crew Health Officer or Earth medical support."
        )
        if safety_active:
            ans = f"{safety_notice} {ans}"
        return {
            "question": q_text,
            "answer": ans,
            "confidence": round(base_conf, 3),
            "evidence_windows": [o.get("window", f"Day {day}") for o in obs_list[:2]] or [f"Day {day}"],
            "cited_observations": obs_list[:2],
            "protocol_refs": proto_ids,
            "protocols": get_protocols(proto_ids),
            "said_i_dont_know": False,
            "refused_diagnosis": True,
            "safety_active": safety_active,
            "safety_notice": safety_notice,
            "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
            "offline_mode": True,
        }

    # 3. Unsupported / out-of-scope biomedical metric or insufficient data (<60% or missing signal)
    unsupported_terms = ("glucose", "cholesterol", "mri", "x-ray", "blood pressure", "white blood cell")
    if any(term in q_lower for term in unsupported_terms):
        return {
            "question": q_text,
            "answer": (
                "I don't know. That metric is not part of AstroGuard's onboard telemetry streams, and I will not invent values."
            ),
            "confidence": 0.0,
            "evidence_windows": [f"Day {day}"],
            "cited_observations": [],
            "protocol_refs": [],
            "protocols": [],
            "said_i_dont_know": True,
            "refused_diagnosis": False,
            "safety_active": safety_active,
            "safety_notice": safety_notice,
            "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
            "offline_mode": True,
        }

    missing_target = _requested_signal_missing(q_lower, readiness_data, env_data)
    if readiness_data is None or coverage < 0.60 or missing_target is not None:
        reason = (
            f"requested {missing_target} telemetry is missing or has an active gap"
            if missing_target and readiness_data is not None and coverage >= 0.60
            else f"clean telemetry coverage is {coverage * 100:.0f}% (below the 60% minimum threshold)"
        )
        ans = (
            f"I don't know — {reason}. Missing or sensor-off periods are preserved as gaps and never imputed as normal."
        )
        if safety_active:
            ans = f"{safety_notice} {ans}"
        proto_ids = _valid_protocols(["PROT-MED-01"] if safety_active else ["PROT-REC-02", "PROT-SLP-02"])
        return {
            "question": q_text,
            "answer": ans,
            "confidence": round(min(base_conf, coverage), 3),
            "evidence_windows": [f"Day {day}"],
            "cited_observations": [],
            "protocol_refs": proto_ids,
            "protocols": get_protocols(proto_ids),
            "said_i_dont_know": True,
            "refused_diagnosis": False,
            "safety_active": safety_active,
            "safety_notice": safety_notice,
            "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
            "offline_mode": True,
        }

    # 4. Counterfactual What-If inquiry
    if "what if" in q_lower or "simulate" in q_lower or counterfactual_data is not None and "if " in q_lower:
        params = _parse_what_if_params(q_lower)
        sim = counterfactual_data if (counterfactual_data and not params) else simulate_intervention(
            readiness_data, **params
        )
        proto_ids = _valid_protocols(sim.get("protocol_refs", ["PROT-SLP-01", "PROT-REC-01"]))
        ans = f"{sim['summary']} {sim['disclaimer']}"
        if safety_active:
            ans = f"{safety_notice} {ans}"
        return {
            "question": q_text,
            "answer": ans,
            "confidence": float(sim.get("confidence", 0.44)),
            "evidence_windows": [f"Day {day + 1}..Day {day + sim.get('horizon_days', 7)}"],
            "cited_observations": [],
            "protocol_refs": proto_ids,
            "protocols": get_protocols(proto_ids),
            "said_i_dont_know": False,
            "refused_diagnosis": False,
            "safety_active": safety_active,
            "safety_notice": safety_notice,
            "disclaimer": sim.get("disclaimer", "Exploratory what-if projection."),
            "offline_mode": True,
        }

    # 5. Environment / Lab Air / Crew CO2
    if any(kw in q_lower for kw in ("lab", "air", "co2", "cabin", "environment", "scrubber", "crew")):
        if not env_data:
            return {
                "question": q_text,
                "answer": "I don't know — habitat environmental correlation output is not available.",
                "confidence": 0.0,
                "evidence_windows": [f"Day {day}"],
                "cited_observations": [],
                "protocol_refs": [],
                "protocols": [],
                "said_i_dont_know": True,
                "refused_diagnosis": False,
                "safety_active": safety_active,
                "safety_notice": safety_notice,
                "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
                "offline_mode": True,
            }
        alert = env_data.get("shared_exposure_alert", {})
        lab = env_data.get("zones", {}).get("LAB", {})
        env_gaps = env_data.get("environmental_gaps", [])
        linked = [c for c in env_data.get("crew_correlations", []) if c.get("linked")]
        gap_txt = f" Note: {len(env_gaps)} environmental sensor gap(s) logged." if env_gaps else ""
        if alert.get("active"):
            corr_txt = ", ".join(
                f"{c['crew_label']} (r={c['r']:.2f}, lag {c['lag_days']}d, conf {c['confidence']*100:.0f}%)"
                for c in linked
            )
            ans = (
                f"{alert['summary']} US Lab current CO2 is {lab.get('co2_ppm')} ppm "
                f"(7-day avg {lab.get('co2_7d_avg_ppm')} ppm). Linked anonymized crew: {corr_txt}.{gap_txt}"
            )
            env_conf = float(alert.get("confidence", 0.85))
            proto_ids = _valid_protocols(alert.get("protocol_refs", ["PROT-ENV-01", "PROT-ENV-02"]))
        else:
            ans = (
                f"No shared CO2-symptom cluster passed FDR control up to Day {day}. "
                f"US Lab current CO2 is {lab.get('co2_ppm')} ppm (7-day avg {lab.get('co2_7d_avg_ppm')} ppm).{gap_txt}"
            )
            env_conf = 0.78
            proto_ids = _valid_protocols(["PROT-ENV-01"])
        if safety_active:
            ans = f"{safety_notice} {ans}"
        return {
            "question": q_text,
            "answer": ans,
            "confidence": round(env_conf, 3),
            "evidence_windows": [f"Day 1..Day {day}"],
            "cited_observations": linked,
            "protocol_refs": proto_ids,
            "protocols": get_protocols(proto_ids),
            "said_i_dont_know": False,
            "refused_diagnosis": False,
            "safety_active": safety_active,
            "safety_notice": safety_notice,
            "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
            "offline_mode": True,
        }

    # 6. Confidence / data quality inquiry
    if any(kw in q_lower for kw in ("confident", "confidence", "sure", "quality", "gap", "sensor")):
        rec = readiness_data.get("recovery_debt", {})
        cog = readiness_data.get("cognitive_readiness", {})
        ans = (
            f"Overall readiness confidence is {base_conf * 100:.0f}% based on {coverage * 100:.0f}% clean coverage "
            f"(recovery confidence {float(rec.get('confidence', 0.0)) * 100:.0f}%, "
            f"cognitive confidence {float(cog.get('confidence', 0.0)) * 100:.0f}%). "
            f"Recorded quality caveats: {dq.get('sensor_off_hours', 0)}h sensor-off, "
            f"{dq.get('missing_hours', 0)}h missing, {dq.get('suspect_count', 0)} suspect, "
            f"{dq.get('out_of_range_count', 0)} out-of-range."
        )
        if safety_active:
            ans = f"{safety_notice} {ans}"
        return {
            "question": q_text,
            "answer": ans,
            "confidence": round(base_conf, 3),
            "evidence_windows": [f"Day {max(1, day - 6)}..Day {day}"],
            "cited_observations": [],
            "protocol_refs": _valid_protocols(["PROT-REC-02", "PROT-SLP-02"]),
            "protocols": get_protocols(_valid_protocols(["PROT-REC-02", "PROT-SLP-02"])),
            "said_i_dont_know": False,
            "refused_diagnosis": False,
            "safety_active": safety_active,
            "safety_notice": safety_notice,
            "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
            "offline_mode": True,
        }

    # 7. Recovery / exercise / fatigue
    if any(kw in q_lower for kw in ("tired", "exercise", "recovery", "hrv", "heart", "winded")):
        rec = readiness_data.get("recovery_debt", {})
        obs = rec.get("observations", [])
        obs_txt = "; ".join(_format_obs_phrase(o) for o in obs) or rec.get("summary", "")
        proto_ids = _valid_protocols(rec.get("protocol_refs", ["PROT-REC-01", "PROT-REC-02"]))
        protocols = get_protocols(proto_ids)
        next_step = protocols[0]["steps"][0] if protocols else ""
        rec_conf = float(rec.get("confidence", base_conf))
        ans = (
            f"Recovery debt is {rec.get('score')}/100 (early-mission personal range {rec.get('personal_range')}, "
            f"confidence {rec_conf * 100:.0f}%). Contributing observations: {obs_txt}. Next step: {next_step}"
        )
        if safety_active:
            ans = f"{safety_notice} {ans}"
        return {
            "question": q_text,
            "answer": ans,
            "confidence": round(rec_conf, 3),
            "evidence_windows": sorted({str(o.get("window")) for o in obs if o.get("window")}) or [f"Day {day}"],
            "cited_observations": obs,
            "protocol_refs": proto_ids,
            "protocols": protocols,
            "said_i_dont_know": False,
            "refused_diagnosis": False,
            "safety_active": safety_active,
            "safety_notice": safety_notice,
            "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
            "offline_mode": True,
        }

    # 8. Cognitive / sleep / PVT
    if any(kw in q_lower for kw in ("cognitive", "sleep", "pvt", "reaction", "focus", "lapse")):
        cog = readiness_data.get("cognitive_readiness", {})
        obs = cog.get("observations", [])
        obs_txt = "; ".join(_format_obs_phrase(o) for o in obs) or cog.get("summary", "")
        proto_ids = _valid_protocols(cog.get("protocol_refs", ["PROT-SLP-01", "PROT-SLP-02"]))
        protocols = get_protocols(proto_ids)
        next_step = protocols[0]["steps"][0] if protocols else ""
        cog_conf = float(cog.get("confidence", base_conf))
        ans = (
            f"Cognitive readiness is {cog.get('score')}/100 (personal range {cog.get('personal_range')}, "
            f"confidence {cog_conf * 100:.0f}%). Contributing observations: {obs_txt}. Next step: {next_step}"
        )
        if safety_active:
            ans = f"{safety_notice} {ans}"
        return {
            "question": q_text,
            "answer": ans,
            "confidence": round(cog_conf, 3),
            "evidence_windows": sorted({str(o.get("window")) for o in obs if o.get("window")}) or [f"Day {day}"],
            "cited_observations": obs,
            "protocol_refs": proto_ids,
            "protocols": protocols,
            "said_i_dont_know": False,
            "refused_diagnosis": False,
            "safety_active": safety_active,
            "safety_notice": safety_notice,
            "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
            "offline_mode": True,
        }

    # 9. Behavioral layers
    if behavioral_data and any(kw in q_lower for kw in ("mood", "stress", "behav", "check-in", "checkin")):
        beh_conf = float(behavioral_data.get("confidence", base_conf))
        proto_ids = _valid_protocols(behavioral_data.get("protocol_refs", ["PROT-SLP-01"]))
        ans = (
            f"Behavioral status is '{behavioral_data.get('status')}' (confidence {beh_conf * 100:.0f}%). "
            f"{behavioral_data.get('summary', '')} {behavioral_data.get('mismatch_prompt', '')} "
            "No fitness-for-duty score is ever computed."
        ).strip()
        if safety_active:
            ans = f"{safety_notice} {ans}"
        return {
            "question": q_text,
            "answer": ans,
            "confidence": round(beh_conf, 3),
            "evidence_windows": [f"Day {max(1, day - 4)}..Day {day}"],
            "cited_observations": [],
            "protocol_refs": proto_ids,
            "protocols": get_protocols(proto_ids),
            "said_i_dont_know": False,
            "refused_diagnosis": False,
            "safety_active": safety_active,
            "safety_notice": safety_notice,
            "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
            "offline_mode": True,
        }

    # 10. Radiation dosimetry
    if any(kw in q_lower for kw in ("radiation", "dose", "dosim", "msv", "usv")):
        rad = readiness_data.get("radiation_trend", {})
        rad_conf = float(rad.get("confidence", base_conf))
        proto_ids = _valid_protocols(rad.get("protocol_refs", ["PROT-RAD-01"]))
        ans = (
            f"Cumulative habitat radiation dose is {rad.get('cumulative_msv')} mSv "
            f"(latest daily rate {rad.get('daily_usv')} uSv/day, confidence {rad_conf * 100:.0f}%). "
            "This is a shared long-term habitat metric, not an acute diagnosis."
        )
        if safety_active:
            ans = f"{safety_notice} {ans}"
        return {
            "question": q_text,
            "answer": ans,
            "confidence": round(rad_conf, 3),
            "evidence_windows": [f"Day 1..Day {day}"],
            "cited_observations": [],
            "protocol_refs": proto_ids,
            "protocols": get_protocols(proto_ids),
            "said_i_dont_know": False,
            "refused_diagnosis": False,
            "safety_active": safety_active,
            "safety_notice": safety_notice,
            "disclaimer": "Decision support only. Not a diagnosis. Not a prescription.",
            "offline_mode": True,
        }

    # 11. Default: assemble grounded next-step briefing
    briefing = build_daily_briefing(
        readiness_data=readiness_data,
        behavioral_data=behavioral_data,
        env_data=env_data,
        mside_data=mside_data,
        active_safety_rules=rules,
        astronaut_id=astronaut_id,
        up_to_day=day,
    )
    ans = briefing["text"]
    if safety_active:
        ans = f"{safety_notice} {ans}"
    return {
        "question": q_text,
        "answer": ans,
        "confidence": briefing["confidence"],
        "evidence_windows": briefing["evidence_windows"],
        "cited_observations": briefing["contributing_observations"],
        "protocol_refs": briefing["protocol_refs"],
        "protocols": briefing["protocols"],
        "said_i_dont_know": briefing["said_i_dont_know"],
        "refused_diagnosis": False,
        "safety_active": safety_active,
        "safety_notice": safety_notice,
        "disclaimer": briefing["disclaimer"],
        "offline_mode": True,
    }
