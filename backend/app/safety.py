"""Deterministic Emergency Safety Rules for AstroGuard (F-27).

CRITICAL ARCHITECTURAL BOUNDARY:
- MUST NOT import anything from `app.engines`, `advisor`, or `simulator`.
- Deterministic rule checks only; no ML model or LLM can lower, delay,
  suppress, or downgrade these rules (`deterministic=True`, `cannot_downgrade=True`).
- All numeric thresholds are illustrative mission safety bounds, not clinical norms.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.schema import ZONE_BY_ID, MeasurementRecord, QualityState, SignalType

SPO2_CRITICAL_THRESHOLD = 90.0
RESTING_HR_CRITICAL_THRESHOLD = 130.0
PVT_LAPSES_CRITICAL_THRESHOLD = 8.0
CO2_HAZARD_THRESHOLD_PPM = 5000.0

_CRISIS_KEYWORDS: Tuple[str, ...] = (
    "self-harm",
    "self harm",
    "selfharm",
    "hurt myself",
    "harm myself",
    "kill myself",
    "suicidal",
    "suicide",
    "want to die",
    "end my life",
    "end it all",
    "cannot go on",
    "can't go on",
    "no reason to live",
    "unsafe with myself",
)

# Structured self-report check-in text keys ONLY; never inspect private_journal or messages.
_CHECKIN_TEXT_KEYS: Tuple[str, ...] = (
    "safety_response",
    "checkin_note",
    "note",
    "response",
    "concerns",
    "free_text",
    "distress_note",
)

_CANCELLED_SOS_STATES = {"cancelled", "canceled", "resolved_ok", "false_alarm", "closed"}

_SOS_TYPE_DISPLAY: Dict[str, str] = {
    "medical": "Medical",
    "behavioral support": "Behavioral support",
    "behavioral": "Behavioral support",
    "habitat hazard": "Habitat hazard",
    "environment": "Habitat hazard",
}


def _coerce_records(
    records: Iterable[MeasurementRecord | Dict[str, Any]],
    up_to_day: int,
) -> List[MeasurementRecord]:
    out: List[MeasurementRecord] = []
    for item in records:
        rec = item if isinstance(item, MeasurementRecord) else MeasurementRecord.from_dict(item)
        if rec.day <= up_to_day:
            out.append(rec)
    out.sort(key=lambda r: (r.day, r.hour, r.timestamp_utc))
    return out


def _zone_display_name(zone_id: str) -> str:
    zone = ZONE_BY_ID.get(zone_id)
    return zone.name if zone is not None else zone_id


def _format_sos_type(raw_type: Any) -> str:
    text = str(raw_type or "Medical").strip()
    return _SOS_TYPE_DISPLAY.get(text.lower(), text)


def _evaluate_sr01_critical_vitals(clean_records: Sequence[MeasurementRecord]) -> List[Dict[str, Any]]:
    """SR-01: Critical vitals (SpO2 < 90% OR resting_hr > 130 with quality == 'ok')."""
    rules: List[Dict[str, Any]] = []
    by_astro: Dict[str, List[MeasurementRecord]] = {}
    for rec in clean_records:
        if rec.signal_type in (SignalType.SPO2.value, SignalType.RESTING_HR.value) and rec.value is not None:
            by_astro.setdefault(rec.astronaut_id, []).append(rec)

    for astro_id in sorted(by_astro):
        astro_recs = by_astro[astro_id]
        spo2_recs = [r for r in astro_recs if r.signal_type == SignalType.SPO2.value]
        rhr_recs = [r for r in astro_recs if r.signal_type == SignalType.RESTING_HR.value]

        spo2_hits = [r for r in spo2_recs if float(r.value) < SPO2_CRITICAL_THRESHOLD]
        rhr_hits = [r for r in rhr_recs if float(r.value) > RESTING_HR_CRITICAL_THRESHOLD]

        if not spo2_hits and not rhr_hits:
            continue

        triggers: List[Tuple[MeasurementRecord, str, bool]] = []
        if spo2_hits:
            latest_spo2_day = max(r.day for r in spo2_recs)
            latest_hit = spo2_hits[-1]
            triggers.append(
                (
                    latest_hit,
                    f"SpO2 {float(latest_hit.value):.1f}% (< {SPO2_CRITICAL_THRESHOLD:.0f}%)",
                    latest_hit.day == latest_spo2_day,
                )
            )
        if rhr_hits:
            latest_rhr_day = max(r.day for r in rhr_recs)
            latest_hit = rhr_hits[-1]
            triggers.append(
                (
                    latest_hit,
                    f"resting HR {float(latest_hit.value):.0f} bpm (> {RESTING_HR_CRITICAL_THRESHOLD:.0f} bpm)",
                    latest_hit.day == latest_rhr_day,
                )
            )

        # Pick most recent / active trigger for this astronaut
        triggers.sort(key=lambda item: (item[2], item[0].day, item[0].hour, item[0].timestamp_utc))
        primary_rec, _, _ = triggers[-1]
        any_active = any(t[2] for t in triggers)
        desc = " and ".join(t[1] for t in triggers)

        rules.append(
            {
                "rule_id": "SR-01",
                "title": "Critical vitals threshold",
                "severity": "critical",
                "active": any_active,
                "historical": not any_active,
                "status": "active" if any_active else "historical",
                "deterministic": True,
                "cannot_downgrade": True,
                "astronaut_id": astro_id,
                "signal": primary_rec.signal_type,
                "observed": float(primary_rec.value) if primary_rec.value is not None else None,
                "summary": (
                    f"{astro_id}: {desc} on Day {primary_rec.day} ({primary_rec.hour:02d}:00). "
                    "Deterministic cardiopulmonary safety review required; AI cannot downgrade."
                ),
                "protocol_refs": ["PROT-MED-01"],
                "day": primary_rec.day,
                "timestamp": primary_rec.timestamp_utc,
            }
        )
    return rules


def _evaluate_sr02_cognitive_syncope(
    clean_records: Sequence[MeasurementRecord],
    checkins: Sequence[Dict[str, Any]],
    up_to_day: int,
) -> List[Dict[str, Any]]:
    """SR-02: Severe cognitive/syncope threshold (pvt_lapses >= 8 or acute collapse indicator)."""
    rules: List[Dict[str, Any]] = []
    by_astro_pvt: Dict[str, List[MeasurementRecord]] = {}
    collapse_by_astro: Dict[str, List[Tuple[int, str, str]]] = {}

    for rec in clean_records:
        if rec.signal_type == SignalType.PVT_LAPSES.value and rec.value is not None:
            by_astro_pvt.setdefault(rec.astronaut_id, []).append(rec)
        tags_lower = {str(tag).strip().lower() for tag in rec.context_tags}
        is_collapse_signal = rec.signal_type.lower() in {"acute_collapse", "syncope", "collapse"} and (
            rec.value is None or float(rec.value) >= 1.0
        )
        is_collapse_tag = bool(tags_lower & {"acute_collapse", "syncope", "collapse"})
        if is_collapse_signal or is_collapse_tag:
            collapse_by_astro.setdefault(rec.astronaut_id, []).append(
                (rec.day, rec.timestamp_utc, "Acute collapse / syncope telemetry indicator")
            )

    for ck in checkins:
        ck_day = int(ck.get("day", up_to_day))
        if ck_day > up_to_day:
            continue
        astro_id = str(ck.get("astronaut_id") or "")
        if not astro_id:
            continue
        symptom_ev = str(ck.get("symptom_event", "")).lower()
        if (
            ck.get("acute_collapse")
            or ck.get("syncope")
            or ck.get("fainted")
            or "collapse" in symptom_ev
            or "syncope" in symptom_ev
        ):
            ts = str(ck.get("timestamp_utc") or f"Day {ck_day:02d} {int(ck.get('hour', 16)):02d}:00")
            collapse_by_astro.setdefault(astro_id, []).append(
                (ck_day, ts, "Acute collapse / syncope reported")
            )

    all_astros = sorted(set(by_astro_pvt.keys()) | set(collapse_by_astro.keys()))
    for astro_id in all_astros:
        pvt_recs = by_astro_pvt.get(astro_id, [])
        pvt_hits = [r for r in pvt_recs if float(r.value) >= PVT_LAPSES_CRITICAL_THRESHOLD]
        collapse_hits = collapse_by_astro.get(astro_id, [])

        if not pvt_hits and not collapse_hits:
            continue

        latest_observed_day = max(
            [r.day for r in pvt_recs] + [c[0] for c in collapse_hits]
        )

        candidates: List[Tuple[int, str, str, bool, Optional[float]]] = []
        if pvt_hits:
            last_pvt = pvt_hits[-1]
            candidates.append(
                (
                    last_pvt.day,
                    last_pvt.timestamp_utc,
                    f"PVT lapses {int(round(float(last_pvt.value)))} (>= {int(PVT_LAPSES_CRITICAL_THRESHOLD)})",
                    last_pvt.day == latest_observed_day,
                    float(last_pvt.value),
                )
            )
        if collapse_hits:
            collapse_hits_sorted = sorted(collapse_hits, key=lambda c: (c[0], c[1]))
            c_day, c_ts, c_msg = collapse_hits_sorted[-1]
            candidates.append(
                (
                    c_day,
                    c_ts,
                    c_msg,
                    c_day == latest_observed_day,
                    None,
                )
            )

        candidates.sort(key=lambda item: (item[3], item[0], item[1]))
        day, ts, desc, _, observed_val = candidates[-1]
        any_active = any(c[3] for c in candidates)

        rules.append(
            {
                "rule_id": "SR-02",
                "title": "Severe cognitive or syncope threshold",
                "severity": "critical",
                "active": any_active,
                "historical": not any_active,
                "status": "active" if any_active else "historical",
                "deterministic": True,
                "cannot_downgrade": True,
                "astronaut_id": astro_id,
                "signal": SignalType.PVT_LAPSES.value if pvt_hits else "acute_collapse",
                "observed": observed_val,
                "summary": (
                    f"{astro_id}: {desc} on Day {day}. "
                    "Halt precision/EVA duties and perform immediate Crew Health Officer safety check."
                ),
                "protocol_refs": ["PROT-MED-01", "PROT-SLP-02"],
                "day": day,
                "timestamp": ts,
            }
        )
    return rules


def _evaluate_sr03_hazardous_co2(clean_records: Sequence[MeasurementRecord]) -> List[Dict[str, Any]]:
    """SR-03: Hazardous cabin CO2 >= 5,000 ppm in any habitat zone (active vs historical)."""
    rules: List[Dict[str, Any]] = []
    co2_by_zone: Dict[str, List[MeasurementRecord]] = {}
    for rec in clean_records:
        if rec.signal_type == SignalType.CO2_PPM.value and rec.value is not None:
            co2_by_zone.setdefault(rec.zone_id, []).append(rec)

    for zone_id in sorted(co2_by_zone):
        zone_recs = co2_by_zone[zone_id]
        exceedances = [r for r in zone_recs if float(r.value) >= CO2_HAZARD_THRESHOLD_PPM]
        if not exceedances:
            continue

        latest_zone_day = max(r.day for r in zone_recs)
        latest_day_recs = [r for r in zone_recs if r.day == latest_zone_day]
        latest_val = float(latest_day_recs[-1].value)  # type: ignore[arg-type]
        max_exceed_day = max(r.day for r in exceedances)
        active = max_exceed_day == latest_zone_day

        # Representative peak exceedance on the most recent exceedance day
        recent_exceedances = [r for r in exceedances if r.day == max_exceed_day]
        peak_rec = max(recent_exceedances, key=lambda r: (float(r.value or 0.0), r.hour, r.timestamp_utc))
        peak_ppm = float(peak_rec.value or 0.0)
        zone_name = _zone_display_name(zone_id)

        if active:
            summary = (
                f"Active hazardous CO2 >= {CO2_HAZARD_THRESHOLD_PPM:,.0f} ppm in {zone_name} ({zone_id}): "
                f"peak {peak_ppm:,.0f} ppm on Day {peak_rec.day} ({peak_rec.hour:02d}:00). "
                "Immediate ventilation & scrubber verification required."
            )
        else:
            summary = (
                f"Historical Day {peak_rec.day} CO2 exceedance in {zone_name} ({zone_id}): "
                f"peaked at {peak_ppm:,.0f} ppm (>= {CO2_HAZARD_THRESHOLD_PPM:,.0f} ppm); "
                f"returned below threshold by Day {latest_zone_day} ({latest_val:,.0f} ppm)."
            )

        rules.append(
            {
                "rule_id": "SR-03",
                "title": f"Hazardous cabin CO2 in {zone_name}",
                "severity": "critical",
                "active": active,
                "historical": not active,
                "status": "active" if active else "historical",
                "deterministic": True,
                "cannot_downgrade": True,
                "zone_id": zone_id,
                "zone_name": zone_name,
                "signal": SignalType.CO2_PPM.value,
                "observed": round(peak_ppm, 1),
                "latest_observed": round(latest_val, 1),
                "latest_day": latest_zone_day,
                "summary": summary,
                "protocol_refs": ["PROT-ENV-01", "PROT-ENV-02"],
                "day": peak_rec.day,
                "timestamp": peak_rec.timestamp_utc,
            }
        )
    return rules


def _evaluate_sr04_behavioral_safety(
    clean_records: Sequence[MeasurementRecord],
    checkins: Sequence[Dict[str, Any]],
    up_to_day: int,
) -> List[Dict[str, Any]]:
    """SR-04: Behavioral safety screen (crisis text/flag -> calm supportive protocol + human prompt)."""
    rules: List[Dict[str, Any]] = []
    checkins_by_astro: Dict[str, List[Dict[str, Any]]] = {}
    for ck in checkins:
        if not isinstance(ck, dict):
            continue
        ck_day = int(ck.get("day", up_to_day))
        if ck_day > up_to_day:
            continue
        astro_id = str(ck.get("astronaut_id") or "unknown")
        checkins_by_astro.setdefault(astro_id, []).append(ck)

    mood_stress_by_astro: Dict[str, Dict[int, Dict[str, float]]] = {}
    for rec in clean_records:
        if rec.signal_type in (SignalType.MOOD_SCORE.value, SignalType.STRESS_SCORE.value) and rec.value is not None:
            day_map = mood_stress_by_astro.setdefault(rec.astronaut_id, {}).setdefault(rec.day, {})
            day_map[rec.signal_type] = float(rec.value)

    all_astros = sorted(set(checkins_by_astro.keys()) | set(mood_stress_by_astro.keys()))
    for astro_id in all_astros:
        astro_cks = sorted(checkins_by_astro.get(astro_id, []), key=lambda c: (int(c.get("day", 0)), int(c.get("hour", 0))))
        reasons: List[str] = []
        trigger_day = up_to_day
        trigger_ts = f"Day {up_to_day:02d} 16:00"

        for ck in astro_cks:
            ck_day = int(ck.get("day", up_to_day))
            ck_hour = int(ck.get("hour", 16))
            ck_ts = str(ck.get("timestamp_utc") or f"Day {ck_day:02d} {ck_hour:02d}:00")

            if (
                ck.get("safety_flag")
                or ck.get("self_harm_risk")
                or ck.get("distress_critical")
                or ck.get("crisis_flag")
                or ck.get("self_harm_flag")
                or ck.get("immediate_support_needed")
            ):
                reasons.append("Extreme behavioral crisis flag raised in structured check-in")
                trigger_day = ck_day
                trigger_ts = ck_ts

            # Inspect explicit structured check-in keys only; never private journals or messages.
            for text_key in _CHECKIN_TEXT_KEYS:
                val = ck.get(text_key)
                if isinstance(val, str) and val.strip():
                    lowered = val.lower()
                    if any(kw in lowered for kw in _CRISIS_KEYWORDS):
                        reasons.append("Concerning self-harm or crisis wording in check-in response")
                        trigger_day = ck_day
                        trigger_ts = ck_ts
                        break

        # Check consecutive extreme distress check-in scores if not already triggered
        day_scores = mood_stress_by_astro.get(astro_id, {})
        extreme_days = [
            d
            for d in sorted(day_scores)
            if day_scores[d].get(SignalType.MOOD_SCORE.value, 5.0) <= 1.2
            and day_scores[d].get(SignalType.STRESS_SCORE.value, 1.0) >= 4.8
        ]
        if len(extreme_days) >= 2 and (extreme_days[-1] - extreme_days[-2]) <= 2:
            reasons.append("Sustained critical distress scores across consecutive check-ins")
            trigger_day = extreme_days[-1]
            trigger_ts = f"Day {trigger_day:02d} 16:00"

        if not reasons:
            continue

        human_prompt = (
            "You do not have to carry this alone. Please reach out right now to your Crew Health Officer, "
            "a trusted crewmate, or Ground medical support, or hold the SOS button for immediate human contact."
        )
        rules.append(
            {
                "rule_id": "SR-04",
                "title": "Behavioral safety support protocol",
                "severity": "critical",
                "active": True,
                "historical": False,
                "status": "active",
                "deterministic": True,
                "cannot_downgrade": True,
                "astronaut_id": astro_id,
                "signal": "behavioral_safety_screen",
                "observed": None,
                "summary": (
                    f"{astro_id}: {'; '.join(dict.fromkeys(reasons))}. "
                    f"Immediate calm, non-punitive support activated. {human_prompt}"
                ),
                "calm_supportive_protocol": (
                    "Pause non-essential tasks, take slow steady breaths in a quiet space, and connect with a "
                    "human supporter right away. Sharing is non-punitive and never scored as fitness-for-duty."
                ),
                "human_contact_prompt": human_prompt,
                "protocol_refs": ["PROT-MED-01"],
                "day": trigger_day,
                "timestamp": trigger_ts,
            }
        )
    return rules


def _evaluate_sr05_active_sos(
    sos_events: Sequence[Dict[str, Any]],
    up_to_day: int,
) -> List[Dict[str, Any]]:
    """SR-05: Active SOS beacon (un-cancelled SOS event)."""
    rules: List[Dict[str, Any]] = []
    for sos in sos_events:
        if not isinstance(sos, dict):
            continue
        sos_day = sos.get("day")
        if sos_day is not None and int(sos_day) > up_to_day:
            continue

        status_raw = str(sos.get("status") or sos.get("state") or "queued").strip().lower()
        is_cancelled = bool(sos.get("cancelled", False)) or status_raw in _CANCELLED_SOS_STATES
        if is_cancelled:
            continue

        day_val = int(sos_day) if sos_day is not None else up_to_day
        hour_val = int(sos.get("hour", 16))
        minute_val = int(sos.get("minute", 0))
        sos_type_display = _format_sos_type(sos.get("sos_type") or sos.get("type") or "Medical")
        astro_id = str(sos.get("astronaut_id") or "")
        note = str(sos.get("note") or "").strip()
        ack_flag = bool(sos.get("acknowledged_on_board", False))
        timestamp = str(
            sos.get("timestamp_utc")
            or sos.get("created_at")
            or f"Day {day_val:02d} {hour_val:02d}:{minute_val:02d}"
        )

        proto_refs = (
            ["PROT-ENV-01", "PROT-MED-01"]
            if sos_type_display == "Habitat hazard"
            else ["PROT-MED-01"]
        )
        ack_text = "acknowledged on-board" if ack_flag else "awaiting on-board acknowledgement"
        note_suffix = f" Note: {note}" if note else ""

        rules.append(
            {
                "rule_id": "SR-05",
                "title": f"SOS — {sos_type_display}",
                "severity": "critical",
                "active": True,
                "historical": False,
                "status": "active",
                "deterministic": True,
                "cannot_downgrade": True,
                "sos_id": sos.get("sos_id"),
                "astronaut_id": astro_id,
                "sos_type": sos_type_display,
                "sos_delivery_state": status_raw,
                "acknowledged_on_board": ack_flag,
                "signal": "sos_beacon",
                "observed": 1.0,
                "summary": (
                    f"{astro_id or 'Crew'} active {sos_type_display} SOS beacon on Day {day_val} "
                    f"(link state: {status_raw}; {ack_text}).{note_suffix}"
                ),
                "protocol_refs": proto_refs,
                "day": day_val,
                "timestamp": timestamp,
            }
        )
    return rules


def evaluate_safety_rules(
    records: List[MeasurementRecord],
    sos_events: Optional[List[Dict[str, Any]]] = None,
    checkins: Optional[List[Dict[str, Any]]] = None,
    up_to_day: int = 23,
) -> List[Dict[str, Any]]:
    """Evaluate deterministic hard safety rules SR-01 through SR-05 up to `up_to_day`.

    Never calls ML engines or the Advisor; outputs are immutable by AI and cannot
    be downgraded, delayed, or suppressed.
    """
    coerced = _coerce_records(records, up_to_day=up_to_day)
    clean_records = [r for r in coerced if r.quality == QualityState.OK.value]

    rules: List[Dict[str, Any]] = []
    rules.extend(_evaluate_sr01_critical_vitals(clean_records))
    rules.extend(_evaluate_sr02_cognitive_syncope(clean_records, checkins or [], up_to_day=up_to_day))
    rules.extend(_evaluate_sr03_hazardous_co2(clean_records))
    rules.extend(_evaluate_sr04_behavioral_safety(clean_records, checkins or [], up_to_day=up_to_day))
    rules.extend(_evaluate_sr05_active_sos(sos_events or [], up_to_day=up_to_day))

    rules.sort(key=lambda r: (not bool(r["active"]), r["rule_id"], -int(r["day"])))
    return rules
