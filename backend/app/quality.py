"""Data quality gate, artifact classification, and gap preservation for AstroGuard (F-02).

Implements FEATURES.md §5.5 and docs/validation-plan.md §3:
- Validates incoming MeasurementRecord instances against plausible ranges and step bounds.
- Preserves explicit `sensor_off` and `missing` states; never imputes missing data as normal.
- Detects motion spikes, saturated readings, out-of-range values, and clock jumps,
  routing every fault with `anomaly_type="data_fault"` so they never raise health alerts.
- Normalizes timestamps and minor clock jitter chronologically without fabricating gaps.
- Summarizes explicit data quality gaps and lowers confidence multipliers accordingly.
"""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.schema import (
    SAMPLE_PLAUSIBLE_RANGES,
    MeasurementRecord,
    QualityState,
    SignalType,
)

# Illustrative single-step maximum plausible jumps per signal (non-clinical engineering bounds).
MAX_STEP_JUMP: Dict[str, float] = {
    SignalType.HEART_RATE.value: 60.0,
    SignalType.RESTING_HR.value: 25.0,
    SignalType.HRV_RMSSD.value: 55.0,
    SignalType.HR_RECOVERY_1M.value: 25.0,
    SignalType.SPO2.value: 8.0,
    SignalType.SLEEP_DURATION.value: 6.0,
    SignalType.SLEEP_FRAGMENTATION.value: 45.0,
    SignalType.PVT_MEAN_RT.value: 250.0,
    SignalType.PVT_LAPSES.value: 12.0,
    SignalType.SYMPTOM_HEADACHE.value: 2.5,
    SignalType.SYMPTOM_FATIGUE.value: 3.5,
    SignalType.MOOD_SCORE.value: 3.0,
    SignalType.ENERGY_SCORE.value: 3.0,
    SignalType.STRESS_SCORE.value: 3.0,
    SignalType.ACTIVITY_INDEX.value: 2.0,
    SignalType.CO2_PPM.value: 6500.0,
    SignalType.CABIN_TEMP_C.value: 8.0,
    SignalType.CABIN_HUMIDITY_PCT.value: 30.0,
    SignalType.CABIN_NOISE_DB.value: 35.0,
    SignalType.RADIATION_USV_DAY.value: 2500.0,
    SignalType.RADIATION_CUMULATIVE_MSV.value: 50.0,
}

# Continuous signals where repeated identical readings indicate sensor saturation/flatline.
CONTINUOUS_SATURATION_SIGNALS = {
    SignalType.HEART_RATE.value,
    SignalType.RESTING_HR.value,
    SignalType.HRV_RMSSD.value,
    SignalType.HR_RECOVERY_1M.value,
    SignalType.SPO2.value,
    SignalType.PVT_MEAN_RT.value,
    SignalType.CO2_PPM.value,
    SignalType.CABIN_TEMP_C.value,
    SignalType.CABIN_HUMIDITY_PCT.value,
    SignalType.CABIN_NOISE_DB.value,
}

WEARABLE_MOTION_SIGNALS = {
    SignalType.HEART_RATE.value,
    SignalType.RESTING_HR.value,
    SignalType.HRV_RMSSD.value,
    SignalType.HR_RECOVERY_1M.value,
    SignalType.SPO2.value,
    SignalType.ACTIVITY_INDEX.value,
}

MINOR_JITTER_SECONDS = 900.0  # 15 minutes


def _coerce_record(record: MeasurementRecord | Dict[str, Any]) -> MeasurementRecord:
    if isinstance(record, MeasurementRecord):
        return record
    return MeasurementRecord.from_dict(record)


def _clone_record(record: MeasurementRecord, **updates: Any) -> MeasurementRecord:
    copied = replace(record, context_tags=list(record.context_tags))
    if updates:
        copied = replace(copied, **updates)
    return copied


def _parse_utc(ts: str) -> Optional[datetime]:
    """Parse ISO-8601 UTC timestamps leniently into timezone-aware UTC datetimes."""
    if not ts:
        return None
    raw = ts.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _format_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _step_limit_for(record: MeasurementRecord) -> float:
    base = MAX_STEP_JUMP.get(record.signal_type, float("inf"))
    # Allow larger heart rate excursion when explicitly tagged as exercise.
    if record.signal_type == SignalType.HEART_RATE.value and "exercise" in record.context_tags:
        return 95.0
    return base


def _slot_index(day: int, hour: int) -> int:
    return (day - 1) * 24 + hour


def _slot_to_day_hour(slot: int) -> Tuple[int, int]:
    day = (slot // 24) + 1
    hour = slot % 24
    return day, hour


def _format_window(start_slot: int, end_slot: int) -> str:
    sd, sh = _slot_to_day_hour(start_slot)
    ed, eh = _slot_to_day_hour(end_slot)
    if start_slot == end_slot:
        return f"Day {sd} {sh:02d}:00"
    return f"Day {sd} {sh:02d}:00 – Day {ed} {eh:02d}:00"


def _make_fault_entry(
    record: MeasurementRecord,
    fault_kind: str,
    title: str,
    explanation: str,
    score: float = 1.0,
    confidence: float = 0.95,
) -> Dict[str, Any]:
    bounds = SAMPLE_PLAUSIBLE_RANGES.get(record.signal_type)
    personal_range = [float(bounds[0]), float(bounds[1])] if bounds else []
    context = record.context_tags[0] if record.context_tags else "rest"
    label = f"Day {record.day} {record.hour:02d}:00"
    return {
        "signal": record.signal_type,
        "window": [label, label],
        "anomaly_type": "data_fault",
        "fault_kind": fault_kind,
        "score": round(float(score), 3),
        "confidence": round(float(max(0.0, min(1.0, confidence))), 3),
        "baseline_context": context,
        "personal_range": personal_range,
        "observed": record.value,
        "contributors": [fault_kind, record.quality],
        "data_quality": {
            "quality": record.quality,
            "fault_kind": fault_kind,
            "source_device": record.source_device,
            "firmware_version": record.firmware_version,
        },
        "evidence_ref": f"fault-{record.record_id}-{fault_kind}",
        "protocol_refs": [],
        "astronaut_id": record.astronaut_id,
        "day": record.day,
        "hour": record.hour,
        "timestamp_utc": record.timestamp_utc,
        "record_id": record.record_id,
        "quality": record.quality,
        "title": title,
        "explanation": explanation,
    }


def validate_record(
    record: MeasurementRecord,
    prev_value: Optional[float] = None,
) -> MeasurementRecord:
    """Validate one measurement against quality state, plausible range, and step jump.

    - Preserves explicit `sensor_off` and `missing` states with confidence 0.0.
    - Marks non-finite or out-of-bounds readings as `out_of_range` (or `missing` if None/NaN).
    - Flags sudden impossible single-step jumps from `prev_value` as `suspect`.
    - Never imputes missing values as normal.
    """
    rec = _coerce_record(record)

    if rec.quality == QualityState.SENSOR_OFF.value:
        return _clone_record(rec, quality=QualityState.SENSOR_OFF.value, confidence=0.0)

    if rec.quality == QualityState.MISSING.value:
        return _clone_record(rec, quality=QualityState.MISSING.value, confidence=0.0)

    if rec.value is None:
        return _clone_record(rec, quality=QualityState.MISSING.value, value=None, confidence=0.0)

    val = float(rec.value)
    if math.isnan(val):
        return _clone_record(rec, quality=QualityState.MISSING.value, value=None, confidence=0.0)
    if math.isinf(val):
        return _clone_record(rec, quality=QualityState.OUT_OF_RANGE.value, confidence=0.0)

    bounds = SAMPLE_PLAUSIBLE_RANGES.get(rec.signal_type)
    if bounds is not None:
        low, high = bounds
        if val < low or val > high:
            return _clone_record(
                rec,
                quality=QualityState.OUT_OF_RANGE.value,
                confidence=0.0,
            )

    if rec.quality == QualityState.OUT_OF_RANGE.value:
        return _clone_record(rec, quality=QualityState.OUT_OF_RANGE.value, confidence=0.0)

    if rec.quality == QualityState.SUSPECT.value:
        return _clone_record(
            rec,
            quality=QualityState.SUSPECT.value,
            confidence=min(float(rec.confidence), 0.35),
        )

    if prev_value is not None and math.isfinite(float(prev_value)):
        delta = abs(val - float(prev_value))
        limit = _step_limit_for(rec)
        if delta > limit:
            return _clone_record(
                rec,
                quality=QualityState.SUSPECT.value,
                confidence=min(float(rec.confidence), 0.35),
            )

    return _clone_record(rec, quality=QualityState.OK.value)


def normalize_timestamps(records: Sequence[MeasurementRecord]) -> List[MeasurementRecord]:
    """Sort records chronologically by `(day, hour, timestamp_utc)` and smooth minor jitter.

    Only minor jitter (<= 15 min for hourly records, <= 15 s for sub-hourly buckets) is aligned;
    larger clock jumps are preserved so `classify_artifact` can detect them, and missing records
    are never fabricated.
    """
    if not records:
        return []

    coerced = [_coerce_record(r) for r in records]

    # Identify buckets with multiple distinct sub-hourly readings so we never collapse them.
    bucket_times: Dict[Tuple[str, str, int, int], List[datetime]] = {}
    for rec in coerced:
        dt = _parse_utc(rec.timestamp_utc)
        if dt is not None:
            key = (rec.astronaut_id, rec.signal_type, rec.day, rec.hour)
            bucket_times.setdefault(key, []).append(dt)

    subhourly_buckets = set()
    for key, dts in bucket_times.items():
        if len(dts) > 1:
            span = (max(dts) - min(dts)).total_seconds()
            if span > 60.0:
                subhourly_buckets.add(key)

    normalized: List[MeasurementRecord] = []
    for rec in coerced:
        dt = _parse_utc(rec.timestamp_utc)
        new_ts = rec.timestamp_utc
        if dt is not None:
            key = (rec.astronaut_id, rec.signal_type, rec.day, rec.hour)
            if key in subhourly_buckets:
                # Smooth sub-minute jitter (<= 15s) to nearest minute boundary.
                base_min = dt.replace(second=0, microsecond=0)
                candidates = [base_min, base_min + timedelta(minutes=1)]
                nearest = min(candidates, key=lambda c: abs((dt - c).total_seconds()))
                if abs((dt - nearest).total_seconds()) <= 15.0:
                    new_ts = _format_utc(nearest)
                else:
                    new_ts = _format_utc(dt)
            else:
                # Snap minor hourly clock jitter (<= 15 min) to exact hour mark matching `rec.hour`.
                base_day = dt.replace(hour=0, minute=0, second=0, microsecond=0)
                target_candidates = [
                    base_day + timedelta(days=offset, hours=rec.hour)
                    for offset in (-1, 0, 1)
                ]
                nearest = min(target_candidates, key=lambda c: abs((dt - c).total_seconds()))
                if abs((dt - nearest).total_seconds()) <= MINOR_JITTER_SECONDS:
                    new_ts = _format_utc(nearest)
                else:
                    new_ts = _format_utc(dt)

        normalized.append(_clone_record(rec, timestamp_utc=new_ts))

    def _sort_key(r: MeasurementRecord) -> Tuple[int, int, float, str, str, str, str]:
        parsed = _parse_utc(r.timestamp_utc)
        epoch = parsed.timestamp() if parsed is not None else float("inf")
        return (r.day, r.hour, epoch, r.astronaut_id, r.signal_type, r.zone_id, r.record_id)

    normalized.sort(key=_sort_key)
    return normalized


def classify_artifact(records: Sequence[MeasurementRecord]) -> List[Dict[str, Any]]:
    """Detect data faults and artifacts, routing all of them to `anomaly_type='data_fault'`.

    Detects:
    - `sensor_off`
    - `missing`
    - `out_of_range`
    - `clock_jump` (backward timestamps, missing/invalid UTC, or slot vs UTC divergence > 15m)
    - `saturated` (flatline >= 3 identical continuous samples or >= 2 pinned at rail)
    - `motion_spike` (impossible step jump, isolated impulse spike-and-return, or motion tag)
    """
    if not records:
        return []

    raw_records = [_coerce_record(r) for r in records]
    faults: List[Dict[str, Any]] = []
    seen_faults: set[Tuple[int, str]] = set()

    def _add_fault(idx: int, rec: MeasurementRecord, fault_kind: str, title: str, explanation: str, score: float = 1.0) -> None:
        key = (idx, fault_kind)
        if key in seen_faults:
            return
        seen_faults.add(key)
        faults.append(_make_fault_entry(rec, fault_kind, title, explanation, score=score))

    # 1. Check unparseable timestamps and direct record quality states
    for idx, rec in enumerate(raw_records):
        validated = validate_record(rec)
        dt = _parse_utc(rec.timestamp_utc)
        if dt is None:
            _add_fault(
                idx,
                validated,
                "clock_jump",
                f"Unparseable timestamp on {rec.signal_type}",
                f"Timestamp '{rec.timestamp_utc}' could not be parsed; routed as data_fault.",
                score=2.0,
            )

        # 2. Direct record quality states: sensor_off, missing, out_of_range
        if validated.quality == QualityState.SENSOR_OFF.value:
            _add_fault(
                idx,
                validated,
                "sensor_off",
                f"Sensor off for {rec.signal_type}",
                f"Device {rec.source_device} reported sensor_off at Day {rec.day} {rec.hour:02d}:00; gap preserved.",
                score=1.0,
            )
        elif validated.quality == QualityState.MISSING.value:
            _add_fault(
                idx,
                validated,
                "missing",
                f"Missing reading for {rec.signal_type}",
                f"Missing value at Day {rec.day} {rec.hour:02d}:00; never imputed as normal.",
                score=1.0,
            )
        elif validated.quality == QualityState.OUT_OF_RANGE.value:
            _add_fault(
                idx,
                validated,
                "out_of_range",
                f"Out-of-range reading for {rec.signal_type}",
                f"Observed {rec.value} {rec.unit} falls outside hardware plausible bounds; routed as data_fault.",
                score=3.0,
            )

    # 3. Chronological per-stream checks: clock jumps vs slot, saturation, and motion spikes
    streams: Dict[Tuple[str, str], List[Tuple[int, MeasurementRecord]]] = {}
    for idx, rec in enumerate(raw_records):
        streams.setdefault((rec.astronaut_id, rec.signal_type), []).append((idx, rec))

    for (_aid, sig), indexed_items in streams.items():
        indexed_items.sort(
            key=lambda pair: (
                pair[1].day,
                pair[1].hour,
                (_parse_utc(pair[1].timestamp_utc).timestamp() if _parse_utc(pair[1].timestamp_utc) else float("inf")),
                pair[0],
            )
        )

        # 3a. Chronological clock jump check against (day, hour) and mission_elapsed_time
        for pos in range(1, len(indexed_items)):
            prev_idx, prev_rec = indexed_items[pos - 1]
            curr_idx, curr_rec = indexed_items[pos]
            prev_dt = _parse_utc(prev_rec.timestamp_utc)
            curr_dt = _parse_utc(curr_rec.timestamp_utc)
            slot_diff_h = float(_slot_index(curr_rec.day, curr_rec.hour) - _slot_index(prev_rec.day, prev_rec.hour))
            met_diff_h = float(curr_rec.mission_elapsed_time - prev_rec.mission_elapsed_time)

            if prev_dt is not None and curr_dt is not None:
                dt_hours = (curr_dt - prev_dt).total_seconds() / 3600.0
                if curr_dt < prev_dt - timedelta(seconds=MINOR_JITTER_SECONDS):
                    _add_fault(
                        curr_idx,
                        validate_record(curr_rec),
                        "clock_jump",
                        f"Backward clock jump on {sig}",
                        f"Timestamp {curr_rec.timestamp_utc} precedes {prev_rec.timestamp_utc}; routed as data_fault.",
                        score=round(abs(dt_hours), 2),
                    )
                elif abs(dt_hours - slot_diff_h) > 0.25:
                    _add_fault(
                        curr_idx,
                        validate_record(curr_rec),
                        "clock_jump",
                        f"Clock offset jump on {sig}",
                        (
                            f"UTC step ({dt_hours:+.2f}h) diverges from ship-clock step ({slot_diff_h:+.2f}h); "
                            "routed as data_fault."
                        ),
                        score=round(abs(dt_hours - slot_diff_h), 2),
                    )

            if met_diff_h < -0.25 or (slot_diff_h > 0 and abs(met_diff_h - slot_diff_h) > 0.5):
                _add_fault(
                    curr_idx,
                    validate_record(curr_rec),
                    "clock_jump",
                    f"MET clock discontinuity on {sig}",
                    f"Mission elapsed time step ({met_diff_h:+.2f}h) diverges from slot step ({slot_diff_h:+.2f}h); routed as data_fault.",
                    score=round(abs(met_diff_h - slot_diff_h), 2),
                )

        # 3b. Saturation / stuck-sensor detection on numeric non-missing/non-out-of-range values
        bounds = SAMPLE_PLAUSIBLE_RANGES.get(sig)
        numeric_items: List[Tuple[int, MeasurementRecord, float]] = []
        for idx, rec in indexed_items:
            vrec = validate_record(rec)
            if vrec.quality in (QualityState.OK.value, QualityState.SUSPECT.value) and vrec.value is not None:
                numeric_items.append((idx, vrec, float(vrec.value)))

        saturated_indices: set[int] = set()
        if sig in CONTINUOUS_SATURATION_SIGNALS and len(numeric_items) >= 2:
            run_start = 0
            while run_start < len(numeric_items):
                run_end = run_start + 1
                base_val = numeric_items[run_start][2]
                while run_end < len(numeric_items) and abs(numeric_items[run_end][2] - base_val) <= 1e-6:
                    run_end += 1
                run_len = run_end - run_start
                at_rail = False
                if bounds is not None:
                    low, high = bounds
                    if sig == SignalType.SPO2.value:
                        at_rail = abs(base_val - low) <= 1e-6
                    else:
                        at_rail = abs(base_val - low) <= 1e-6 or abs(base_val - high) <= 1e-6

                is_integer_val = abs(base_val - round(base_val)) <= 1e-6
                is_flatline = False
                if sig == SignalType.SPO2.value:
                    # Healthy SpO2 frequently stays at integer 97-100%; only flag lower rail or non-integer/sub-95 flatlines.
                    if (not is_integer_val or base_val < 95.0) and run_len >= 4:
                        is_flatline = True
                elif sig == SignalType.RESTING_HR.value:
                    # Resting HR is sampled once daily and can repeat integer values across stable days.
                    if (not is_integer_val and run_len >= 4) or run_len >= 5:
                        is_flatline = True
                else:
                    if (not is_integer_val and run_len >= 3) or run_len >= 4:
                        is_flatline = True

                is_rail_stuck = run_len >= 2 and at_rail
                if is_flatline or is_rail_stuck:
                    for pos in range(run_start, run_end):
                        idx, vrec, val = numeric_items[pos]
                        saturated_indices.add(idx)
                        _add_fault(
                            idx,
                            vrec,
                            "saturated",
                            f"Saturated / stuck sensor on {sig}",
                            f"Repeated constant reading ({val} {vrec.unit} x{run_len}) indicates sensor saturation; routed as data_fault.",
                            score=float(run_len),
                        )
                run_start = run_end

        # 3c. Motion spikes & impossible single-step jumps
        for pos, (idx, vrec, val) in enumerate(numeric_items):
            if idx in saturated_indices:
                continue
            prev_val = numeric_items[pos - 1][2] if pos > 0 else None
            next_val = numeric_items[pos + 1][2] if pos + 1 < len(numeric_items) else None
            limit = _step_limit_for(vrec)

            has_motion_tag = "motion_artifact" in vrec.context_tags or "motion_spike" in vrec.context_tags
            step_validated = validate_record(vrec, prev_value=prev_val)
            is_impossible_jump = (
                prev_val is not None
                and step_validated.quality == QualityState.SUSPECT.value
                and abs(val - prev_val) > limit
            )
            is_impulse_spike = (
                prev_val is not None
                and next_val is not None
                and math.isfinite(limit)
                and abs(val - prev_val) >= 0.55 * limit
                and abs(val - next_val) >= 0.55 * limit
                and abs(next_val - prev_val) <= 0.35 * max(abs(val - prev_val), 1e-6)
            )

            if has_motion_tag or is_impossible_jump or is_impulse_spike:
                delta = abs(val - prev_val) if prev_val is not None else 1.0
                _add_fault(
                    idx,
                    step_validated,
                    "motion_spike",
                    f"Motion/impulse spike on {sig}",
                    (
                        f"Transient reading {val} {vrec.unit} flagged as motion/step artifact "
                        f"(delta={delta:.1f}); routed as data_fault."
                    ),
                    score=round(delta, 2),
                )
            elif vrec.quality == QualityState.SUSPECT.value:
                kind = "motion_spike" if sig in WEARABLE_MOTION_SIGNALS else "suspect_artifact"
                _add_fault(
                    idx,
                    vrec,
                    kind,
                    f"Suspect reading on {sig}",
                    f"Noisy or low-confidence reading ({val} {vrec.unit}) marked suspect; routed as data_fault.",
                    score=1.0,
                )

    faults.sort(key=lambda f: (f["day"], f["hour"], f["astronaut_id"], f["signal"], f["fault_kind"]))
    return faults


def summarize_data_quality(
    records: Sequence[MeasurementRecord],
    astronaut_id: Optional[str] = None,
    up_to_day: int = 23,
) -> Dict[str, Any]:
    """Compute data quality coverage, explicit gaps, and confidence multiplier.

    Never imputes or hides `sensor_off` or `missing` periods as healthy/normal.
    """
    coerced = [_coerce_record(r) for r in records]
    filtered = [
        r
        for r in coerced
        if (astronaut_id is None or r.astronaut_id == astronaut_id)
        and (up_to_day is None or r.day <= up_to_day)
    ]

    if not filtered:
        return {
            "astronaut_id": astronaut_id,
            "up_to_day": up_to_day,
            "total_records": 0,
            "ok_count": 0,
            "coverage_ratio": 0.0,
            "coverage_pct": 0.0,
            "sensor_off_hours": 0,
            "missing_count": 0,
            "suspect_count": 0,
            "out_of_range_count": 0,
            "gaps": [],
            "confidence_multiplier": 0.0,
            "last_clean_label": "No clean reading",
        }

    # Validate records chronologically per (astronaut_id, signal_type) so step jumps become suspect too.
    validated_records: List[MeasurementRecord] = []
    by_stream: Dict[Tuple[str, str], List[MeasurementRecord]] = {}
    for rec in filtered:
        by_stream.setdefault((rec.astronaut_id, rec.signal_type), []).append(rec)

    for stream_recs in by_stream.values():
        stream_recs.sort(key=lambda r: (r.day, r.hour, r.timestamp_utc))
        prev_val: Optional[float] = None
        for rec in stream_recs:
            vrec = validate_record(rec, prev_value=prev_val)
            validated_records.append(vrec)
            if vrec.quality == QualityState.OK.value and vrec.value is not None:
                prev_val = float(vrec.value)

    ok_records = [r for r in validated_records if r.quality == QualityState.OK.value]
    sensor_off_records = [r for r in validated_records if r.quality == QualityState.SENSOR_OFF.value]
    missing_records = [r for r in validated_records if r.quality == QualityState.MISSING.value]
    suspect_records = [r for r in validated_records if r.quality == QualityState.SUSPECT.value]
    oor_records = [r for r in validated_records if r.quality == QualityState.OUT_OF_RANGE.value]

    sensor_off_slots = {(_slot_index(r.day, r.hour), r.astronaut_id) for r in sensor_off_records}
    non_ok_slots = {
        (_slot_index(r.day, r.hour), r.astronaut_id)
        for r in validated_records
        if r.quality != QualityState.OK.value
    }

    # Detect implicit missing hours ONLY on signals with an established hourly cadence (>= 6 samples, median step <= 1.5h)
    implicit_missing_slots: Dict[Tuple[str, int], set[str]] = {}
    for (aid, sig), stream_recs in by_stream.items():
        if len(stream_recs) < 6:
            continue
        slots = sorted({_slot_index(r.day, r.hour) for r in stream_recs})
        diffs = [slots[i] - slots[i - 1] for i in range(1, len(slots)) if slots[i] > slots[i - 1]]
        if not diffs:
            continue
        diffs_sorted = sorted(diffs)
        median_step = diffs_sorted[len(diffs_sorted) // 2]
        if median_step <= 1.5:
            for i in range(1, len(slots)):
                gap = slots[i] - slots[i - 1] - 1
                if gap >= 1:
                    for missing_slot in range(slots[i - 1] + 1, slots[i]):
                        implicit_missing_slots.setdefault((aid, missing_slot), set()).add(sig)

    implicit_missing_count = sum(len(sigs) for sigs in implicit_missing_slots.values())
    total_expected = len(validated_records) + implicit_missing_count
    ok_count = len(ok_records)
    coverage_ratio = round(ok_count / total_expected, 4) if total_expected > 0 else 0.0
    coverage_pct = round(coverage_ratio * 100.0, 2)

    missing_count = len(missing_records) + implicit_missing_count
    suspect_count = len(suspect_records)
    out_of_range_count = len(oor_records)
    sensor_off_hours = len(sensor_off_slots)

    # Build explicit contiguous gaps grouped by (astronaut_id, state) across time slots.
    slot_state_signals: Dict[Tuple[str, str, int], set[str]] = {}
    for rec in validated_records:
        if rec.quality != QualityState.OK.value:
            slot_state_signals.setdefault(
                (rec.astronaut_id, rec.quality, _slot_index(rec.day, rec.hour)), set()
            ).add(rec.signal_type)
    for (aid, slot), sigs in implicit_missing_slots.items():
        slot_state_signals.setdefault((aid, QualityState.MISSING.value, slot), set()).update(sigs)

    by_aid_state: Dict[Tuple[str, str], Dict[int, set[str]]] = {}
    for (aid, state, slot), sigs in slot_state_signals.items():
        by_aid_state.setdefault((aid, state), {})[slot] = sigs

    gaps: List[Dict[str, Any]] = []
    state_labels = {
        QualityState.SENSOR_OFF.value: "Sensor off",
        QualityState.MISSING.value: "Missing data",
        QualityState.SUSPECT.value: "Suspect artifact",
        QualityState.OUT_OF_RANGE.value: "Out-of-range reading",
    }

    for (aid, state), slot_map in sorted(by_aid_state.items()):
        sorted_slots = sorted(slot_map.keys())
        run_start = sorted_slots[0]
        run_end = sorted_slots[0]
        run_sigs: set[str] = set(slot_map[run_start])

        def _flush_gap(s: int, e: int, sigs: Iterable[str]) -> None:
            hours = e - s + 1
            window = _format_window(s, e)
            sig_list = ", ".join(sorted(sigs))
            base_label = state_labels.get(state, state)
            gaps.append(
                {
                    "label": f"{base_label} ({hours}h)",
                    "window": window,
                    "hours": hours,
                    "state": state,
                    "detail": (
                        f"{hours}h {state} gap for {aid} on {sig_list} ({window}); "
                        "explicitly preserved and never filled as normal."
                    ),
                }
            )

        for slot in sorted_slots[1:]:
            if slot == run_end + 1:
                run_end = slot
                run_sigs.update(slot_map[slot])
            else:
                _flush_gap(run_start, run_end, run_sigs)
                run_start = slot
                run_end = slot
                run_sigs = set(slot_map[slot])
        _flush_gap(run_start, run_end, run_sigs)

    gaps.sort(key=lambda g: (g["window"], g["state"], g["label"]))

    # Lower confidence multiplier whenever gaps or non-ok readings exist.
    if ok_count == 0:
        confidence_multiplier = 0.0
    elif not gaps and coverage_ratio >= 1.0:
        confidence_multiplier = 1.0
    else:
        max_day_seen = max(r.day for r in validated_records)
        recent_cutoff = max(1, (up_to_day if up_to_day is not None else max_day_seen) - 3)
        recent_non_ok_slots = {
            slot for slot, _aid in non_ok_slots if _slot_to_day_hour(slot)[0] >= recent_cutoff
        }
        recent_implicit = {
            slot for (_aid, slot) in implicit_missing_slots if _slot_to_day_hour(slot)[0] >= recent_cutoff
        }
        recent_gap_hours = len(recent_non_ok_slots | recent_implicit)
        total_gap_hours = len({slot for slot, _aid in non_ok_slots} | {slot for (_aid, slot) in implicit_missing_slots})
        gap_penalty = min(0.30, 0.015 * recent_gap_hours + 0.005 * max(0, total_gap_hours - recent_gap_hours))
        raw_mult = coverage_ratio * (1.0 - gap_penalty)
        confidence_multiplier = round(max(0.1, min(0.98, raw_mult)), 3)

    if ok_records:
        latest_ok = max(ok_records, key=lambda r: (r.day, r.hour, r.timestamp_utc))
        last_clean_label = f"Day {latest_ok.day} {latest_ok.hour:02d}:00"
    else:
        last_clean_label = "No clean reading"

    return {
        "astronaut_id": astronaut_id,
        "up_to_day": up_to_day,
        "total_records": len(validated_records),
        "ok_count": ok_count,
        "coverage_ratio": coverage_ratio,
        "coverage_pct": coverage_pct,
        "sensor_off_hours": sensor_off_hours,
        "missing_count": missing_count,
        "suspect_count": suspect_count,
        "out_of_range_count": out_of_range_count,
        "gaps": gaps,
        "confidence_multiplier": confidence_multiplier,
        "last_clean_label": last_clean_label,
    }
