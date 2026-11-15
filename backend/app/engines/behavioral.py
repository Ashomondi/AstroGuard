"""Three-Layer Behavioral Health and Underreporting Cross-Check Engine (F-16, F-29).

Combines:
1. Passive telemetry layer (sleep duration/fragmentation, HRV, resting HR, activity index)
2. Active self-report layer (explicit check-in mood/energy/stress scores)
3. Anonymized crew climate aggregate (never exposing peer identities)

Detects passive-vs-self-report mismatches with gentle, private, non-punitive
prompts (F-29), enforces deterministic safety screening (`safety_triggered`),
checks environment confounders first (F-18), and NEVER computes fitness-for-duty.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.engines.baseline import (
    PersonalBaselineEngine,
    clamp,
    coerce_records,
    is_clean_record,
)
from app.schema import CREW_BY_ID, MeasurementRecord, SignalType

_SAFETY_KEYWORDS = (
    "self-harm",
    "self harm",
    "hurt myself",
    "harm myself",
    "suicidal",
    "suicide",
    "want to die",
    "end my life",
    "cannot go on",
)


def _recent_daily_values(
    records: Sequence[MeasurementRecord],
    signal_type: str,
    start_day: int,
    up_to_day: int,
) -> List[float]:
    """Collect clean daily medians within [start_day, up_to_day]."""
    by_day: Dict[int, List[float]] = {}
    for rec in records:
        if (
            rec.signal_type == signal_type
            and start_day <= rec.day <= up_to_day
            and is_clean_record(rec)
            and rec.value is not None
        ):
            by_day.setdefault(rec.day, []).append(float(rec.value))
    return [float(statistics.median(by_day[d])) for d in sorted(by_day)]


def _normalize_checkins(
    checkins: Optional[Iterable[Dict[str, Any]]],
    astronaut_id: str,
    up_to_day: int,
) -> List[Dict[str, Any]]:
    """Filter explicit check-ins for `astronaut_id` up to `up_to_day`."""
    if not checkins:
        return []
    out: List[Dict[str, Any]] = []
    for item in checkins:
        if not isinstance(item, dict):
            continue
        target = item.get("astronaut_id")
        if target not in (None, "", astronaut_id):
            continue
        day = int(item.get("day", up_to_day))
        if day <= up_to_day:
            out.append(dict(item))
    out.sort(key=lambda c: int(c.get("day", 0)))
    return out


def _evaluate_safety_screen(
    checkins: Sequence[Dict[str, Any]],
    mood_vals: Sequence[float],
    stress_vals: Sequence[float],
) -> Dict[str, Any]:
    """Deterministic behavioral safety screen (non-overridable by ML/AI)."""
    reasons: List[str] = []
    for ck in checkins:
        if ck.get("safety_flag") or ck.get("self_harm_risk") or ck.get("distress_critical"):
            reasons.append("Explicit safety screen flag raised during check-in.")
        # Inspect explicit check-in text fields (never private_journal, journal, or message_body)
        resp_parts = [
            str(ck.get(k, "") or "")
            for k in (
                "safety_response",
                "checkin_note",
                "note",
                "response",
                "concerns",
                "free_text",
                "distress_note",
            )
        ]
        resp_text = " ".join(resp_parts).lower()
        if any(kw in resp_text for kw in _SAFETY_KEYWORDS):
            reasons.append("Concerning distress wording detected in structured check-in response.")

    if len(mood_vals) >= 2 and len(stress_vals) >= 2:
        if all(m <= 1.2 for m in mood_vals[-2:]) and all(s >= 4.8 for s in stress_vals[-2:]):
            reasons.append("Persistent critical distress across consecutive check-in scores.")

    triggered = len(reasons) > 0
    return {
        "safety_triggered": triggered,
        "reasons": reasons,
        "protocol_refs": ["PROT-MED-01"] if triggered else [],
        "notice": (
            "Deterministic safety protocol active — AI cannot soften or downgrade. Prompt to involve Crew Health Officer per consent; SOS stays visible."
            if triggered
            else "No deterministic behavioral safety threshold triggered."
        ),
    }


def assess_behavioral_health(
    records: Iterable[MeasurementRecord | Dict[str, Any]],
    checkins: Optional[Iterable[Dict[str, Any]]] = None,
    crew_climate: Optional[Any] = None,
    astronaut_id: str = "ast-01",
    up_to_day: int = 23,
    env_confounders: Optional[Any] = None,
) -> Dict[str, Any]:
    """Evaluate 3-layer behavioral health, F-29 cross-check, and deterministic safety screen."""
    all_records = coerce_records(records, up_to_day=up_to_day)
    astro_records = [r for r in all_records if r.astronaut_id == astronaut_id]
    recent_start = max(1, up_to_day - 4)

    engine = PersonalBaselineEngine()
    engine.fit(astro_records, astronaut_id=astronaut_id, up_to_day=up_to_day)

    # --- Layer 1: Passive Telemetry ---
    b_act = engine.fit_signal_context(
        astro_records, astronaut_id, SignalType.ACTIVITY_INDEX.value, "rest", up_to_day
    )
    b_sleep = engine.fit_signal_context(
        astro_records, astronaut_id, SignalType.SLEEP_DURATION.value, "sleep", up_to_day
    )
    b_frag = engine.fit_signal_context(
        astro_records, astronaut_id, SignalType.SLEEP_FRAGMENTATION.value, "sleep", up_to_day
    )
    b_hrv = engine.fit_signal_context(
        astro_records, astronaut_id, SignalType.HRV_RMSSD.value, "sleep", up_to_day
    )
    b_rhr = engine.fit_signal_context(
        astro_records, astronaut_id, SignalType.RESTING_HR.value, "rest", up_to_day
    )

    act_recent = _recent_daily_values(astro_records, SignalType.ACTIVITY_INDEX.value, recent_start, up_to_day)
    sleep_recent = _recent_daily_values(astro_records, SignalType.SLEEP_DURATION.value, recent_start, up_to_day)
    frag_recent = _recent_daily_values(
        astro_records, SignalType.SLEEP_FRAGMENTATION.value, recent_start, up_to_day
    )
    hrv_recent = _recent_daily_values(astro_records, SignalType.HRV_RMSSD.value, recent_start, up_to_day)
    rhr_recent = _recent_daily_values(astro_records, SignalType.RESTING_HR.value, recent_start, up_to_day)

    passive_indicators: List[str] = []
    passive_signals_checked = 0
    passive_strain_parts: List[float] = []

    activity_ratio: Optional[float] = None
    if act_recent:
        passive_signals_checked += 1
        act_mean = sum(act_recent) / len(act_recent)
        activity_ratio = round(act_mean / max(0.1, b_act.center), 2)
        if activity_ratio < 0.80:
            passive_indicators.append("activity_drop")
            passive_strain_parts.append(clamp((0.85 - activity_ratio) / 0.25, 0.2, 1.0))

    if sleep_recent:
        passive_signals_checked += 1
        sleep_mean = sum(sleep_recent) / len(sleep_recent)
        if b_sleep.center - sleep_mean >= 0.7:
            passive_indicators.append("short_sleep")
            passive_strain_parts.append(clamp((b_sleep.center - sleep_mean) / 2.0, 0.2, 1.0))

    if frag_recent:
        passive_signals_checked += 1
        frag_mean = sum(frag_recent) / len(frag_recent)
        if frag_mean - b_frag.center >= 10.0:
            passive_indicators.append("sleep_fragmentation")
            passive_strain_parts.append(clamp((frag_mean - b_frag.center) / 30.0, 0.2, 1.0))

    if hrv_recent:
        passive_signals_checked += 1
        hrv_mean = sum(hrv_recent) / len(hrv_recent)
        if (b_hrv.center - hrv_mean) / max(1.0, b_hrv.center) >= 0.14:
            passive_indicators.append("hrv_suppression")
            passive_strain_parts.append(
                clamp(((b_hrv.center - hrv_mean) / max(1.0, b_hrv.center)) / 0.30, 0.2, 1.0)
            )

    if rhr_recent:
        passive_signals_checked += 1
        rhr_mean = sum(rhr_recent) / len(rhr_recent)
        if rhr_mean - b_rhr.center >= 4.0:
            passive_indicators.append("resting_hr_elevation")
            passive_strain_parts.append(clamp((rhr_mean - b_rhr.center) / 10.0, 0.2, 1.0))

    passive_drift_score = (
        round(
            clamp(
                (sum(passive_strain_parts) / max(1, len(passive_strain_parts)))
                * (0.5 + 0.25 * min(2, len(passive_indicators))),
                0.0,
                1.0,
            ),
            3,
        )
        if passive_strain_parts
        else 0.0
    )
    passive_coverage = round(passive_signals_checked / 5.0, 2)
    passive_drifting = len(passive_indicators) >= 2 or passive_drift_score >= 0.50

    # --- Layer 2: Active Self-Report ---
    norm_checkins = _normalize_checkins(checkins, astronaut_id, up_to_day)
    mood_vals = _recent_daily_values(astro_records, SignalType.MOOD_SCORE.value, recent_start, up_to_day)
    energy_vals = _recent_daily_values(astro_records, SignalType.ENERGY_SCORE.value, recent_start, up_to_day)
    stress_vals = _recent_daily_values(astro_records, SignalType.STRESS_SCORE.value, recent_start, up_to_day)

    for ck in norm_checkins:
        if ck.get("mood_score") is not None:
            mood_vals.append(float(ck["mood_score"]))
        if ck.get("energy_score") is not None:
            energy_vals.append(float(ck["energy_score"]))
        if ck.get("stress_score") is not None:
            stress_vals.append(float(ck["stress_score"]))

    latest_mood = round(mood_vals[-1], 2) if mood_vals else None
    latest_energy = round(energy_vals[-1], 2) if energy_vals else None
    latest_stress = round(stress_vals[-1], 2) if stress_vals else None

    active_strain_parts: List[float] = []
    if latest_mood is not None and latest_mood < 3.2:
        active_strain_parts.append(clamp((3.5 - latest_mood) / 2.0, 0.1, 1.0))
    if latest_energy is not None and latest_energy < 3.0:
        active_strain_parts.append(clamp((3.5 - latest_energy) / 2.0, 0.1, 1.0))
    if latest_stress is not None and latest_stress > 3.2:
        active_strain_parts.append(clamp((latest_stress - 2.8) / 2.0, 0.1, 1.0))

    active_strain_score = round(
        clamp(sum(active_strain_parts) / max(1, len(active_strain_parts)), 0.0, 1.0)
        if active_strain_parts
        else 0.0,
        3,
    )
    active_looks_fine = (
        (latest_mood is None or latest_mood >= 3.5)
        and (latest_energy is None or latest_energy >= 3.3)
        and (latest_stress is None or latest_stress <= 2.8)
    ) and (latest_mood is not None or latest_energy is not None or len(norm_checkins) > 0)

    # --- Layer 3: Anonymized Crew Climate ---
    climate_score: Optional[float] = None
    if isinstance(crew_climate, dict) and crew_climate.get("score") is not None:
        climate_score = round(float(crew_climate["score"]), 2)
    elif isinstance(crew_climate, (int, float)):
        climate_score = round(float(crew_climate), 2)
    else:
        peer_moods: List[float] = []
        for aid in CREW_BY_ID:
            m_list = _recent_daily_values(
                [r for r in all_records if r.astronaut_id == aid],
                SignalType.MOOD_SCORE.value,
                recent_start,
                up_to_day,
            )
            if m_list:
                peer_moods.append(m_list[-1])
        if peer_moods:
            climate_score = round(sum(peer_moods) / len(peer_moods), 2)

    climate_low = climate_score is not None and climate_score < 2.8

    # --- Environment Confounder First Check (F-18) ---
    matched_confounders: List[Dict[str, Any]] = []
    if isinstance(env_confounders, list):
        matched_confounders = [
            c for c in env_confounders if isinstance(c, dict) and c.get("astronaut_id") in (None, astronaut_id)
        ]
    elif isinstance(env_confounders, dict):
        matched_confounders = [
            c
            for c in env_confounders.get("confounder_flags", [])
            if isinstance(c, dict) and c.get("astronaut_id") in (None, astronaut_id)
        ]
    env_confounder_active = len(matched_confounders) > 0

    # --- Gentle Non-Punitive Underreporting Cross-Check (F-29) ---
    underreporting_mismatch = bool(passive_drifting and active_looks_fine)
    if underreporting_mismatch:
        mismatch_prompt = (
            "Your recent wearable sleep and activity patterns look heavier than your baseline, "
            "even though your check-ins look steady. There is no judgment or score here — "
            "would you like a private check-in with AstroGuard or a quiet recovery block?"
        )
    else:
        mismatch_prompt = ""

    # --- Deterministic Safety Screen ---
    safety = _evaluate_safety_screen(norm_checkins, mood_vals, stress_vals)
    safety_triggered = bool(safety["safety_triggered"])

    # --- Status Ladder: Steady | Watch | Check-in suggested | Support needed ---
    if safety_triggered or (passive_drift_score >= 0.72 and active_strain_score >= 0.65):
        status = "Support needed"
    elif (
        (passive_drifting and active_strain_score >= 0.35)
        or (underreporting_mismatch and len(passive_indicators) >= 2 and not env_confounder_active)
        or active_strain_score >= 0.60
    ):
        status = "Check-in suggested"
    elif passive_drifting or active_strain_score >= 0.25 or underreporting_mismatch or climate_low:
        status = "Watch"
    else:
        status = "Steady"

    # Build plain-language, non-punitive summary
    if safety_triggered:
        summary = (
            "Deterministic behavioral safety support triggered. Prompt to involve Crew Health Officer "
            "per consent; SOS remains immediately accessible."
        )
    elif underreporting_mismatch:
        summary = (
            "Passive telemetry and self-report layers show a gentle mismatch; private reflection suggested."
        )
    elif env_confounder_active and status in {"Watch", "Steady"}:
        summary = (
            "Shared habitat CO2 confounder is active; environmental air check is prioritized before attributing individual behavioral drift."
        )
    elif status == "Steady":
        summary = "Passive and self-report layers are consistent. No punitive score is computed."
    else:
        summary = "Mild sustained strain across monitored behavioral layers; private self-care check-in suggested."

    conf = round(clamp(0.45 + 0.35 * passive_coverage + (0.15 if norm_checkins or mood_vals else 0.0), 0.2, 0.95), 2)

    return {
        "astronaut_id": astronaut_id,
        "up_to_day": up_to_day,
        "status": status,
        "confidence": conf,
        "summary": summary,
        "passive_layer": {
            "status": "drift" if passive_drifting else "steady",
            "drift_score": passive_drift_score,
            "indicators": passive_indicators,
            "activity_ratio": activity_ratio,
            "coverage": passive_coverage,
        },
        "active_layer": {
            "status": "elevated_strain" if active_strain_score >= 0.5 else ("mild_strain" if active_strain_score > 0.0 else "steady"),
            "strain_score": active_strain_score,
            "mood_score": latest_mood,
            "energy_score": latest_energy,
            "stress_score": latest_stress,
            "checkin_count": len(norm_checkins),
        },
        "climate_layer": {
            "score": climate_score,
            "scale": 5.0,
            "anonymized": True,
            "note": "Crew climate is shown only as an anonymous aggregate.",
        },
        "underreporting_mismatch": underreporting_mismatch,
        "mismatch_prompt": mismatch_prompt,
        "env_confounder_active": env_confounder_active,
        "env_confounders": matched_confounders,
        "safety_triggered": safety_triggered,
        "safety_details": safety,
        "protocol_refs": (
            ["PROT-MED-01"]
            if safety_triggered
            else (["PROT-SLP-01", "PROT-REC-01"] if status != "Steady" else [])
        ),
        "fitness_for_duty_computed": False,
        "privacy_note": (
            "Private by default. Behavioral telemetry is never used for fitness-for-duty scoring "
            "and never reads message text or private journal entries."
        ),
    }
