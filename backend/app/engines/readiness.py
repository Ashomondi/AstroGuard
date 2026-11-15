"""Recovery Debt, Cognitive Readiness, and Composite Readiness Engine (F-11, F-12).

Computes context-aware personal readiness indices strictly against each astronaut's
early-mission personal baseline (never fixed Earth clinical tables), penalizes
confidence explicitly for sensor gaps and quality artifacts, and preserves gap
states in `latest_readings`. Deterministic safety rules override readiness bands
to 'Safety review' and can never be downgraded.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.engines.baseline import (
    DEFAULT_SIGNAL_CONTEXT,
    PersonalBaselineEngine,
    clamp,
    coerce_records,
    infer_context,
    is_clean_record,
)
from app.schema import CREW_BY_ID, MeasurementRecord, QualityState, SIGNAL_UNITS, SignalType

KEY_LATEST_SIGNALS: Tuple[str, ...] = (
    SignalType.HEART_RATE.value,
    SignalType.RESTING_HR.value,
    SignalType.HRV_RMSSD.value,
    SignalType.HR_RECOVERY_1M.value,
    SignalType.SPO2.value,
    SignalType.SLEEP_DURATION.value,
    SignalType.SLEEP_FRAGMENTATION.value,
    SignalType.PVT_MEAN_RT.value,
    SignalType.PVT_LAPSES.value,
    SignalType.SYMPTOM_HEADACHE.value,
    SignalType.SYMPTOM_FATIGUE.value,
    SignalType.MOOD_SCORE.value,
    SignalType.ENERGY_SCORE.value,
    SignalType.STRESS_SCORE.value,
    SignalType.ACTIVITY_INDEX.value,
    SignalType.CO2_PPM.value,
    SignalType.RADIATION_USV_DAY.value,
    SignalType.RADIATION_CUMULATIVE_MSV.value,
)


def _daily_clean_series(
    records: Sequence[MeasurementRecord],
    signal_type: str,
    engine: PersonalBaselineEngine,
    astronaut_id: str,
    context: Optional[str] = None,
) -> Dict[int, float]:
    """Return step-adjusted clean daily medians keyed by day."""
    ctx = context or DEFAULT_SIGNAL_CONTEXT.get(signal_type, "rest")
    step_info = engine._step_cache.get((astronaut_id, signal_type))
    if step_info is None:
        step_info = engine.detect_device_step(records, astronaut_id, signal_type)

    by_day: Dict[int, List[float]] = {}
    for rec in records:
        if rec.signal_type == signal_type and is_clean_record(rec):
            if context is None or infer_context(rec) == ctx:
                by_day.setdefault(rec.day, []).append(engine._step_adjusted_value(rec, step_info))
    return {d: float(statistics.median(vals)) for d, vals in sorted(by_day.items())}


def _signal_gap_ratio(
    records: Sequence[MeasurementRecord],
    signal_types: Sequence[str],
    start_day: int,
    up_to_day: int,
) -> Tuple[float, int, int]:
    """Return (clean_coverage_ratio, gap_count, total_count) across target signals."""
    relevant = [
        r
        for r in records
        if r.signal_type in signal_types and start_day <= r.day <= up_to_day
    ]
    if not relevant:
        return 0.0, 0, 0
    ok_count = sum(1 for r in relevant if is_clean_record(r))
    gap_count = len(relevant) - ok_count
    return ok_count / len(relevant), gap_count, len(relevant)


def _latest_known(daily_map: Dict[int, float], day: int) -> Optional[float]:
    """Return value on `day` or most recent clean day before `day` (for series context)."""
    if day in daily_map:
        return daily_map[day]
    prior = [d for d in daily_map if d < day]
    return daily_map[prior[-1]] if prior else None


def _build_latest_readings(
    astro_records: Sequence[MeasurementRecord],
    all_records: Sequence[MeasurementRecord],
    engine: PersonalBaselineEngine,
    astronaut_id: str,
    up_to_day: int,
) -> Dict[str, Dict[str, Any]]:
    """Summarize latest reading per signal while keeping gaps explicitly visible."""
    latest: Dict[str, Dict[str, Any]] = {}
    recent_start = max(1, up_to_day - 2)
    default_zone = CREW_BY_ID[astronaut_id].default_zone if astronaut_id in CREW_BY_ID else "LAB"

    for sig in KEY_LATEST_SIGNALS:
        sig_recs = [r for r in astro_records if r.signal_type == sig]
        if not sig_recs and sig in {
            SignalType.CO2_PPM.value,
            SignalType.RADIATION_USV_DAY.value,
            SignalType.RADIATION_CUMULATIVE_MSV.value,
        }:
            # Fall back to habitat/shared records in astronaut's zone when not duplicated per-person
            zone_recs = [r for r in all_records if r.signal_type == sig and r.zone_id == default_zone]
            sig_recs = zone_recs or [r for r in all_records if r.signal_type == sig]

        if not sig_recs:
            latest[sig] = {
                "signal_type": sig,
                "value": None,
                "unit": SIGNAL_UNITS.get(sig, ""),
                "quality": QualityState.MISSING.value,
                "is_gap": True,
                "day": up_to_day,
                "hour": None,
                "timestamp_utc": None,
                "baseline": None,
                "personal_range": None,
                "last_clean_value": None,
                "last_clean_day": None,
                "gap_hours": 0,
            }
            continue

        last_rec = sig_recs[-1]
        clean_recs = [r for r in sig_recs if is_clean_record(r)]
        ctx = infer_context(last_rec)
        base = engine.get_baseline(astronaut_id, sig, ctx) or engine.get_baseline(
            astronaut_id, sig, DEFAULT_SIGNAL_CONTEXT.get(sig, "rest")
        )
        step_info = engine._step_cache.get((astronaut_id, sig), {"steps": []})

        last_clean_val = (
            round(engine._step_adjusted_value(clean_recs[-1], step_info), 2) if clean_recs else None
        )
        last_clean_day = clean_recs[-1].day if clean_recs else None
        gap_hours = sum(
            1 for r in sig_recs if recent_start <= r.day <= up_to_day and not is_clean_record(r)
        )
        is_gap = not is_clean_record(last_rec)

        if is_gap:
            display_val: Optional[float] = (
                None
                if last_rec.quality in {QualityState.SENSOR_OFF.value, QualityState.MISSING.value}
                else last_rec.value
            )
        else:
            display_val = round(engine._step_adjusted_value(last_rec, step_info), 2)

        latest[sig] = {
            "signal_type": sig,
            "value": display_val,
            "unit": last_rec.unit or SIGNAL_UNITS.get(sig, ""),
            "quality": last_rec.quality,
            "is_gap": is_gap,
            "day": last_rec.day,
            "hour": last_rec.hour,
            "timestamp_utc": last_rec.timestamp_utc,
            "baseline": None if base is None else round(base.center, 2),
            "personal_range": None
            if base is None
            else [round(base.personal_range[0], 2), round(base.personal_range[1], 2)],
            "last_clean_value": last_clean_val,
            "last_clean_day": last_clean_day,
            "gap_hours": gap_hours,
        }

    return latest


def _active_rules_for_astronaut(
    active_safety_rules: Optional[Iterable[Any]],
    astronaut_id: str,
) -> List[Dict[str, Any]]:
    """Normalize active deterministic safety rules affecting `astronaut_id`."""
    if not active_safety_rules:
        return []
    matched: List[Dict[str, Any]] = []
    for item in active_safety_rules:
        if isinstance(item, str):
            matched.append({"rule_id": item, "active": True, "astronaut_id": astronaut_id})
        elif isinstance(item, dict):
            if item.get("active", True) is False:
                continue
            target = item.get("astronaut_id")
            if target in (None, "", "all", astronaut_id):
                matched.append(dict(item))
    return matched


def _band_from_score(score: float, safety_active: bool) -> str:
    """Map composite score and deterministic safety state to readiness band."""
    if safety_active:
        return "Safety review"
    if score < 58.0:
        return "Reduced"
    if score < 72.0:
        return "Monitor"
    if score < 84.0:
        return "Watch"
    return "Steady"


def compute_readiness(
    records: Iterable[MeasurementRecord | Dict[str, Any]],
    astronaut_id: str,
    up_to_day: int = 23,
    active_safety_rules: Optional[Iterable[Any]] = None,
    env_confounders: Optional[Any] = None,
    quality_summary: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Compute personal recovery debt, cognitive readiness, radiation trend, and composite readiness."""
    all_records = coerce_records(records, up_to_day=up_to_day)
    astro_records = [r for r in all_records if r.astronaut_id == astronaut_id]

    engine = PersonalBaselineEngine()
    engine.fit(astro_records, astronaut_id=astronaut_id, up_to_day=up_to_day)
    flags = engine.detect_anomalies(astro_records, astronaut_id=astronaut_id, up_to_day=up_to_day)

    recent_start = max(1, up_to_day - 6)
    last_48h_start = max(1, up_to_day - 1)

    # Daily clean step-adjusted series per signal
    hr_rec_daily = _daily_clean_series(astro_records, SignalType.HR_RECOVERY_1M.value, engine, astronaut_id)
    rhr_daily = _daily_clean_series(astro_records, SignalType.RESTING_HR.value, engine, astronaut_id)
    hrv_daily = _daily_clean_series(astro_records, SignalType.HRV_RMSSD.value, engine, astronaut_id)
    sleep_dur_daily = _daily_clean_series(astro_records, SignalType.SLEEP_DURATION.value, engine, astronaut_id)
    sleep_frag_daily = _daily_clean_series(
        astro_records, SignalType.SLEEP_FRAGMENTATION.value, engine, astronaut_id
    )
    pvt_rt_daily = _daily_clean_series(astro_records, SignalType.PVT_MEAN_RT.value, engine, astronaut_id)
    pvt_lapses_daily = _daily_clean_series(astro_records, SignalType.PVT_LAPSES.value, engine, astronaut_id)

    # Baselines for personal comparison (fall back to population prior via fit_signal_context)
    b_hr_rec = engine.fit_signal_context(
        astro_records, astronaut_id, SignalType.HR_RECOVERY_1M.value, "exercise", up_to_day
    )
    b_rhr = engine.fit_signal_context(
        astro_records, astronaut_id, SignalType.RESTING_HR.value, "rest", up_to_day
    )
    b_hrv = engine.fit_signal_context(
        astro_records, astronaut_id, SignalType.HRV_RMSSD.value, "sleep", up_to_day
    )
    b_sleep_dur = engine.fit_signal_context(
        astro_records, astronaut_id, SignalType.SLEEP_DURATION.value, "sleep", up_to_day
    )
    b_sleep_frag = engine.fit_signal_context(
        astro_records, astronaut_id, SignalType.SLEEP_FRAGMENTATION.value, "sleep", up_to_day
    )
    b_pvt_rt = engine.fit_signal_context(
        astro_records, astronaut_id, SignalType.PVT_MEAN_RT.value, "rest", up_to_day
    )
    b_pvt_lapses = engine.fit_signal_context(
        astro_records, astronaut_id, SignalType.PVT_LAPSES.value, "rest", up_to_day
    )

    all_days = sorted({r.day for r in astro_records} | {up_to_day})
    all_days = [d for d in all_days if 1 <= d <= up_to_day]

    # --- 1. Recovery Debt (0-100, lower is better) ---
    rec_series: List[Dict[str, Any]] = []
    for d in all_days:
        hr_rec_v = _latest_known(hr_rec_daily, d)
        rhr_v = _latest_known(rhr_daily, d)
        hrv_v = _latest_known(hrv_daily, d)
        sleep_v = _latest_known(sleep_dur_daily, d)

        rec_drop = max(0.0, b_hr_rec.center - hr_rec_v) if hr_rec_v is not None else 0.0
        rhr_rise = max(0.0, rhr_v - b_rhr.center) if rhr_v is not None else 0.0
        hrv_drop_pct = (
            max(0.0, (b_hrv.center - hrv_v) / max(1.0, b_hrv.center)) if hrv_v is not None else 0.0
        )
        sleep_def = max(0.0, b_sleep_dur.center - sleep_v) if sleep_v is not None else 0.0

        day_debt = clamp(
            12.0
            + min(34.0, rec_drop * 2.0)
            + min(20.0, rhr_rise * 2.0)
            + min(24.0, hrv_drop_pct * 45.0)
            + min(15.0, sleep_def * 10.0),
            0.0,
            100.0,
        )
        day_has_data = any(d in m for m in (hr_rec_daily, rhr_daily, hrv_daily, sleep_dur_daily))
        rec_series.append({"day": d, "value": round(day_debt, 1), "observed_day": day_has_data})

    base_rec_vals = [pt["value"] for pt in rec_series if pt["day"] <= min(10, up_to_day)]
    if base_rec_vals:
        rec_range = [round(min(base_rec_vals), 1), round(max(max(base_rec_vals), min(base_rec_vals) + 12.0), 1)]
    else:
        rec_range = [10.0, 34.0]

    latest_rec_debt = rec_series[-1]["value"] if rec_series else 20.0
    rec_signals = (
        SignalType.HR_RECOVERY_1M.value,
        SignalType.RESTING_HR.value,
        SignalType.HRV_RMSSD.value,
        SignalType.SLEEP_DURATION.value,
    )
    rec_cov_win, rec_gaps_win, rec_tot_win = _signal_gap_ratio(
        astro_records, rec_signals, recent_start, up_to_day
    )
    rec_cov_48, _, rec_tot_48 = _signal_gap_ratio(
        astro_records, rec_signals, last_48h_start, up_to_day
    )
    rec_sig_present = sum(1 for m in (hr_rec_daily, rhr_daily, hrv_daily, sleep_dur_daily) if m) / 4.0
    if rec_tot_win == 0:
        rec_conf = 0.0
    else:
        recent_factor = rec_cov_48 if rec_tot_48 > 0 else rec_cov_win
        rec_conf = clamp(0.95 * (0.45 * rec_cov_win + 0.35 * recent_factor + 0.20 * rec_sig_present), 0.1, 0.98)

    rec_observations: List[Dict[str, Any]] = []
    if hr_rec_daily:
        val = hr_rec_daily[max(hr_rec_daily)]
        rec_observations.append(
            {
                "signal": SignalType.HR_RECOVERY_1M.value,
                "label": "1-min heart-rate recovery",
                "observed": round(val, 1),
                "baseline": round(b_hr_rec.center, 1),
                "delta": round(val - b_hr_rec.center, 1),
                "unit": "bpm",
                "window": f"Day {max(hr_rec_daily)}",
                "confidence": round(rec_conf, 2),
            }
        )
    if rhr_daily:
        val = rhr_daily[max(rhr_daily)]
        rec_observations.append(
            {
                "signal": SignalType.RESTING_HR.value,
                "label": "Resting heart rate",
                "observed": round(val, 1),
                "baseline": round(b_rhr.center, 1),
                "delta": round(val - b_rhr.center, 1),
                "unit": "bpm",
                "window": f"Day {max(rhr_daily)}",
                "confidence": round(rec_conf, 2),
            }
        )
    if hrv_daily:
        val = hrv_daily[max(hrv_daily)]
        rec_observations.append(
            {
                "signal": SignalType.HRV_RMSSD.value,
                "label": "HRV (RMSSD)",
                "observed": round(val, 1),
                "baseline": round(b_hrv.center, 1),
                "delta": round(val - b_hrv.center, 1),
                "unit": "ms",
                "window": f"Day {max(hrv_daily)}",
                "confidence": round(rec_conf, 2),
            }
        )
    if sleep_dur_daily:
        val = sleep_dur_daily[max(sleep_dur_daily)]
        rec_observations.append(
            {
                "signal": SignalType.SLEEP_DURATION.value,
                "label": "Sleep duration",
                "observed": round(val, 2),
                "baseline": round(b_sleep_dur.center, 2),
                "delta": round(val - b_sleep_dur.center, 2),
                "unit": "h",
                "window": f"Day {max(sleep_dur_daily)}",
                "confidence": round(rec_conf, 2),
            }
        )

    rec_status = (
        "critical"
        if latest_rec_debt >= 65.0
        else "caution"
        if latest_rec_debt >= 48.0
        else "watch"
        if latest_rec_debt > rec_range[1]
        else "normal"
    )

    # --- 2. Cognitive Readiness (0-100, higher is better) ---
    cog_series: List[Dict[str, Any]] = []
    for d in all_days:
        rt_v = _latest_known(pvt_rt_daily, d)
        lapses_v = _latest_known(pvt_lapses_daily, d)
        frag_v = _latest_known(sleep_frag_daily, d)
        sleep_v = _latest_known(sleep_dur_daily, d)

        rt_slow = max(0.0, rt_v - b_pvt_rt.center) if rt_v is not None else 0.0
        lapses_inc = max(0.0, lapses_v - b_pvt_lapses.center) if lapses_v is not None else 0.0
        frag_rise = max(0.0, frag_v - b_sleep_frag.center) if frag_v is not None else 0.0
        sleep_def = max(0.0, b_sleep_dur.center - sleep_v) if sleep_v is not None else 0.0

        day_cog = clamp(
            93.0
            - min(44.0, rt_slow * 0.45)
            - min(28.0, lapses_inc * 6.0)
            - min(24.0, frag_rise * 0.65)
            - min(18.0, sleep_def * 8.0),
            0.0,
            100.0,
        )
        day_has_data = any(d in m for m in (pvt_rt_daily, pvt_lapses_daily, sleep_frag_daily, sleep_dur_daily))
        cog_series.append({"day": d, "value": round(day_cog, 1), "observed_day": day_has_data})

    base_cog_vals = [pt["value"] for pt in cog_series if pt["day"] <= min(10, up_to_day)]
    if base_cog_vals:
        cog_range = [
            round(min(min(base_cog_vals), max(base_cog_vals) - 12.0), 1),
            round(max(base_cog_vals), 1),
        ]
    else:
        cog_range = [75.0, 95.0]

    latest_cog = cog_series[-1]["value"] if cog_series else 88.0
    cog_signals = (
        SignalType.PVT_MEAN_RT.value,
        SignalType.PVT_LAPSES.value,
        SignalType.SLEEP_FRAGMENTATION.value,
        SignalType.SLEEP_DURATION.value,
    )
    cog_cov_win, cog_gaps_win, cog_tot_win = _signal_gap_ratio(
        astro_records, cog_signals, recent_start, up_to_day
    )
    # Wearable gaps also affect overnight sleep confidence
    wear_cov_48, _, wear_tot_48 = _signal_gap_ratio(
        astro_records,
        (SignalType.HEART_RATE.value, SignalType.SLEEP_DURATION.value, SignalType.SLEEP_FRAGMENTATION.value),
        last_48h_start,
        up_to_day,
    )
    cog_sig_present = sum(
        1 for m in (pvt_rt_daily, pvt_lapses_daily, sleep_frag_daily, sleep_dur_daily) if m
    ) / 4.0
    if cog_tot_win == 0:
        cog_conf = 0.0
    else:
        wear_factor = wear_cov_48 if wear_tot_48 > 0 else 1.0
        cog_conf = clamp(
            0.94 * (0.50 * cog_cov_win + 0.25 * wear_factor + 0.25 * cog_sig_present), 0.1, 0.97
        )

    cog_observations: List[Dict[str, Any]] = []
    if pvt_rt_daily:
        val = pvt_rt_daily[max(pvt_rt_daily)]
        cog_observations.append(
            {
                "signal": SignalType.PVT_MEAN_RT.value,
                "label": "PVT mean reaction time",
                "observed": round(val, 1),
                "baseline": round(b_pvt_rt.center, 1),
                "delta": round(val - b_pvt_rt.center, 1),
                "unit": "ms",
                "window": f"Day {max(pvt_rt_daily)}",
                "confidence": round(cog_conf, 2),
            }
        )
    if pvt_lapses_daily:
        val = pvt_lapses_daily[max(pvt_lapses_daily)]
        cog_observations.append(
            {
                "signal": SignalType.PVT_LAPSES.value,
                "label": "PVT lapses",
                "observed": round(val, 1),
                "baseline": round(b_pvt_lapses.center, 1),
                "delta": round(val - b_pvt_lapses.center, 1),
                "unit": "count",
                "window": f"Day {max(pvt_lapses_daily)}",
                "confidence": round(cog_conf, 2),
            }
        )
    if sleep_frag_daily:
        val = sleep_frag_daily[max(sleep_frag_daily)]
        cog_observations.append(
            {
                "signal": SignalType.SLEEP_FRAGMENTATION.value,
                "label": "Sleep fragmentation",
                "observed": round(val, 1),
                "baseline": round(b_sleep_frag.center, 1),
                "delta": round(val - b_sleep_frag.center, 1),
                "unit": "pts",
                "window": f"Day {max(sleep_frag_daily)}",
                "confidence": round(cog_conf, 2),
            }
        )

    cog_status = (
        "critical"
        if latest_cog < 50.0
        else "caution"
        if latest_cog < 68.0
        else "watch"
        if latest_cog < cog_range[0]
        else "normal"
    )

    # --- 3. Environment Component (0-100, higher is better) ---
    astro_zones = {
        (r.day, r.hour): r.zone_id for r in astro_records if r.zone_id
    }
    default_zone = CREW_BY_ID[astronaut_id].default_zone if astronaut_id in CREW_BY_ID else "LAB"
    recent_co2_vals: List[float] = []
    recent_noise_vals: List[float] = []
    recent_temp_vals: List[float] = []

    for r in all_records:
        if recent_start <= r.day <= up_to_day and is_clean_record(r) and r.value is not None:
            occupied_zone = astro_zones.get((r.day, r.hour), default_zone)
            is_local = r.astronaut_id == astronaut_id or (
                r.astronaut_id in {"habitat", "env", "system", astronaut_id} and r.zone_id == occupied_zone
            ) or (r.zone_id == occupied_zone and r.signal_type in {
                SignalType.CO2_PPM.value,
                SignalType.CABIN_NOISE_DB.value,
                SignalType.CABIN_TEMP_C.value,
            })
            if not is_local:
                continue
            if r.signal_type == SignalType.CO2_PPM.value:
                recent_co2_vals.append(float(r.value))
            elif r.signal_type == SignalType.CABIN_NOISE_DB.value:
                recent_noise_vals.append(float(r.value))
            elif r.signal_type == SignalType.CABIN_TEMP_C.value:
                recent_temp_vals.append(float(r.value))

    avg_co2 = sum(recent_co2_vals) / len(recent_co2_vals) if recent_co2_vals else 830.0
    avg_noise = sum(recent_noise_vals) / len(recent_noise_vals) if recent_noise_vals else 56.0
    avg_temp = sum(recent_temp_vals) / len(recent_temp_vals) if recent_temp_vals else 22.0

    co2_excess = max(0.0, avg_co2 - 880.0)
    noise_excess = max(0.0, avg_noise - 62.0)
    temp_excess = max(0.0, abs(avg_temp - 22.0) - 3.0)
    env_score = clamp(95.0 - min(65.0, co2_excess / 42.0) - min(15.0, noise_excess) - min(15.0, temp_excess * 3.0), 0.0, 100.0)

    # --- 4. Symptoms Component (0-100, higher is better) ---
    headache_daily = _daily_clean_series(astro_records, SignalType.SYMPTOM_HEADACHE.value, engine, astronaut_id)
    fatigue_daily = _daily_clean_series(astro_records, SignalType.SYMPTOM_FATIGUE.value, engine, astronaut_id)
    energy_daily = _daily_clean_series(astro_records, SignalType.ENERGY_SCORE.value, engine, astronaut_id)
    stress_daily = _daily_clean_series(astro_records, SignalType.STRESS_SCORE.value, engine, astronaut_id)

    h_val = headache_daily[max(headache_daily)] if headache_daily else 0.0
    f_val = fatigue_daily[max(fatigue_daily)] if fatigue_daily else 0.5
    e_val = energy_daily[max(energy_daily)] if energy_daily else 3.8
    st_val = stress_daily[max(stress_daily)] if stress_daily else 2.0
    symptoms_score = clamp(
        96.0
        - h_val * 12.0
        - f_val * 6.0
        - max(0.0, 3.5 - e_val) * 6.0
        - max(0.0, st_val - 2.5) * 5.0,
        0.0,
        100.0,
    )

    # --- 5. Radiation Trend ---
    rad_source = [
        r
        for r in all_records
        if r.signal_type in {SignalType.RADIATION_USV_DAY.value, SignalType.RADIATION_CUMULATIVE_MSV.value}
        and (r.astronaut_id == astronaut_id or r.astronaut_id in {"habitat", "env", "system"})
    ]
    if not rad_source:
        rad_source = [
            r
            for r in all_records
            if r.signal_type in {SignalType.RADIATION_USV_DAY.value, SignalType.RADIATION_CUMULATIVE_MSV.value}
        ]

    rad_daily_map: Dict[int, float] = {}
    rad_cum_map: Dict[int, float] = {}
    for r in rad_source:
        if is_clean_record(r) and r.value is not None:
            if r.signal_type == SignalType.RADIATION_USV_DAY.value:
                rad_daily_map[r.day] = float(r.value)
            elif r.signal_type == SignalType.RADIATION_CUMULATIVE_MSV.value:
                rad_cum_map[r.day] = float(r.value)

    rad_series: List[Dict[str, Any]] = []
    running_msv = 0.0
    for d in all_days:
        daily_u = rad_daily_map.get(d, 500.0 if rad_daily_map else 0.0)
        if d in rad_cum_map:
            running_msv = rad_cum_map[d]
        elif d in rad_daily_map:
            running_msv += daily_u / 1000.0
        rad_series.append(
            {
                "day": d,
                "daily_usv": round(daily_u, 1),
                "cumulative_msv": round(running_msv, 2),
            }
        )

    latest_daily_usv = rad_daily_map[max(rad_daily_map)] if rad_daily_map else 0.0
    latest_cum_msv = (
        rad_cum_map[max(rad_cum_map)]
        if rad_cum_map
        else (rad_series[-1]["cumulative_msv"] if rad_series else 0.0)
    )
    rad_cov, _, rad_tot = _signal_gap_ratio(
        rad_source,
        (SignalType.RADIATION_USV_DAY.value, SignalType.RADIATION_CUMULATIVE_MSV.value),
        recent_start,
        up_to_day,
    )
    rad_conf = round(clamp(0.92 * rad_cov, 0.0, 0.96), 3) if rad_tot > 0 else 0.0

    # --- 6. Composite Readiness & Safety Override ---
    recovery_component = 100.0 - latest_rec_debt
    composite_score = (
        0.40 * latest_cog
        + 0.30 * recovery_component
        + 0.20 * env_score
        + 0.10 * symptoms_score
    )
    matched_rules = _active_rules_for_astronaut(active_safety_rules, astronaut_id)
    safety_active = len(matched_rules) > 0
    band = _band_from_score(composite_score, safety_active=safety_active)

    # Overall data quality summary
    cov_recent, gap_recent, tot_recent = _signal_gap_ratio(
        astro_records, KEY_LATEST_SIGNALS, recent_start, up_to_day
    )
    sensor_off_h = sum(
        1
        for r in astro_records
        if recent_start <= r.day <= up_to_day and r.quality == QualityState.SENSOR_OFF.value
    )
    missing_h = sum(
        1
        for r in astro_records
        if recent_start <= r.day <= up_to_day and r.quality == QualityState.MISSING.value
    )
    suspect_c = sum(
        1
        for r in astro_records
        if recent_start <= r.day <= up_to_day and r.quality == QualityState.SUSPECT.value
    )
    oor_c = sum(
        1
        for r in astro_records
        if recent_start <= r.day <= up_to_day and r.quality == QualityState.OUT_OF_RANGE.value
    )

    dq_summary: Dict[str, Any] = {
        "coverage": round(cov_recent, 3),
        "total_records": tot_recent,
        "gap_count": gap_recent,
        "sensor_off_hours": sensor_off_h,
        "missing_hours": missing_h,
        "suspect_count": suspect_c,
        "out_of_range_count": oor_c,
    }
    if quality_summary:
        dq_summary["external_quality_summary"] = dict(quality_summary)
        if "coverage" in quality_summary and tot_recent == 0:
            dq_summary["coverage"] = float(quality_summary["coverage"])

    # Filter environmental confounders relevant to this astronaut
    relevant_confounders: List[Dict[str, Any]] = []
    if isinstance(env_confounders, list):
        for item in env_confounders:
            if isinstance(item, dict) and item.get("astronaut_id") in (None, astronaut_id):
                relevant_confounders.append(item)
    elif isinstance(env_confounders, dict):
        for item in env_confounders.get("confounder_flags", []):
            if isinstance(item, dict) and item.get("astronaut_id") in (None, astronaut_id):
                relevant_confounders.append(item)

    overall_conf = round(
        clamp(
            0.45 * rec_conf + 0.45 * cog_conf + 0.10 * dq_summary["coverage"],
            0.0,
            0.97,
        ),
        3,
    )

    return {
        "astronaut_id": astronaut_id,
        "up_to_day": up_to_day,
        "readiness_score": round(composite_score, 1),
        "band": band,
        "safety_active": safety_active,
        "active_safety_rules": matched_rules,
        "confidence": overall_conf,
        "components": {
            "cognitive": round(latest_cog, 1),
            "recovery": round(recovery_component, 1),
            "environment": round(env_score, 1),
            "symptoms": round(symptoms_score, 1),
            "weights": {
                "cognitive": 0.40,
                "recovery": 0.30,
                "environment": 0.20,
                "symptoms": 0.10,
            },
        },
        "recovery_debt": {
            "score": round(latest_rec_debt, 1),
            "direction": "lower_is_better",
            "status": rec_status,
            "confidence": round(rec_conf, 3),
            "personal_range": rec_range,
            "series": rec_series,
            "observations": rec_observations,
            "protocol_refs": ["PROT-REC-01", "PROT-REC-02"],
            "summary": (
                "Recovery debt is elevated relative to early-mission baseline."
                if latest_rec_debt > rec_range[1]
                else "Recovery is within your personal early-mission range."
            ),
        },
        "cognitive_readiness": {
            "score": round(latest_cog, 1),
            "direction": "higher_is_better",
            "status": cog_status,
            "confidence": round(cog_conf, 3),
            "personal_range": cog_range,
            "series": cog_series,
            "observations": cog_observations,
            "protocol_refs": ["PROT-SLP-01", "PROT-SLP-02"],
            "summary": (
                "Cognitive readiness is reduced relative to personal PVT and sleep baseline."
                if latest_cog < cog_range[0]
                else "Cognitive readiness is within your personal early-mission range."
            ),
        },
        "radiation_trend": {
            "cumulative_msv": round(latest_cum_msv, 2),
            "daily_usv": round(latest_daily_usv, 1),
            "series": rad_series,
            "confidence": rad_conf,
            "status": "watch" if latest_cum_msv >= 12.0 else "normal",
            "protocol_refs": ["PROT-RAD-01"],
        },
        "latest_readings": _build_latest_readings(
            astro_records, all_records, engine, astronaut_id, up_to_day
        ),
        "data_quality": dq_summary,
        "env_confounders": relevant_confounders,
        "flags": [f.to_dict() for f in flags],
    }
