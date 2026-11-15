"""Seeded synthetic astronaut mission simulator with planted ground truth (F-03, F-17).

Emits canonical `MeasurementRecord` streams (`app.schema`) for four astronauts
(`ast-01`..`ast-04`) across four habitat zones (`N1`, `LAB`, `CQ`, `AL`), with
explicit data-quality states (`ok`, `suspect`, `sensor_off`, `missing`,
`out_of_range`), a ground-truth `SCENARIO_MANIFEST`, a zero-anomaly `null_mission`
mode, and deterministic perturbation injectors (`inject_artifacts`,
`inject_device_step`, `inject_missingness`).

All numeric thresholds, baselines, and trajectories are illustrative sample data
for offline validation and demonstration — not validated clinical limits.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.schema import (
    CREW_BY_ID,
    CREW_ROSTER,
    HABITAT_ZONES,
    SAMPLE_PLAUSIBLE_RANGES,
    SIGNAL_TO_SCOPE,
    SIGNAL_UNITS,
    ConsentScope,
    MeasurementRecord,
    QualityState,
    SignalType,
)

MISSION_START_UTC = datetime(2031, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
HABITAT_ACTOR_ID = "habitat"

SCENARIO_MANIFEST: List[Dict[str, Any]] = [
    {
        "event_id": "EV_RECOVERY_DECLINE",
        "target_id": "ast-01",
        "target_type": "astronaut",
        "anomaly_kind": "drift",
        "onset_day": 14,
        "peak_day": 23,
        "magnitude": "large",
        "magnitude_details": {
            "hr_recovery_1m_delta_bpm": -13.3,
            "resting_hr_delta_bpm": 3.3,
            "hrv_rmssd_delta_ms": -19.2,
            "sleep_duration_delta_h": -0.7,
            "pvt_mean_rt_delta_ms": 11.9,
        },
        "affected_signals": [
            SignalType.HR_RECOVERY_1M.value,
            SignalType.HRV_RMSSD.value,
            SignalType.RESTING_HR.value,
            SignalType.HEART_RATE.value,
            SignalType.SLEEP_DURATION.value,
        ],
        "expected_window": ["Day 14", "Day 23"],
        "expected_sos": {
            "day": 23,
            "hour": 14,
            "minute": 20,
            "sos_type": "medical",
            "rule_id": "SR-05",
            "note": "Unusually winded after exercise block. Requesting guidance; comms are offline.",
        },
        "description": (
            "Progressive recovery debt for Cmdr. Elena Vasquez (Days 14-23): HR recovery falls "
            "from ~34.5 to ~21.2 bpm, RHR rises from ~54.9 to ~58.2 bpm, rest HR reaches ~73 bpm, "
            "HRV drops from ~62.0 to ~42.8 ms, sleep drops from ~7.0h to ~6.3h, headache stays 0."
        ),
    },
    {
        "event_id": "MC_COGNITIVE_DRIFT_AND_UNDERREPORTING",
        "target_id": "ast-02",
        "target_type": "astronaut",
        "anomaly_kind": "multivariate",
        "onset_day": 13,
        "peak_day": 23,
        "magnitude": "large",
        "magnitude_details": {
            "sleep_fragmentation_delta_pts": 30.0,
            "pvt_mean_rt_delta_ms": 74.0,
            "pvt_lapses_day23": 3,
            "activity_index_day23": 0.72,
            "self_report_mood": 4.0,
            "self_report_energy": 4.0,
        },
        "affected_signals": [
            SignalType.SLEEP_FRAGMENTATION.value,
            SignalType.PVT_MEAN_RT.value,
            SignalType.PVT_LAPSES.value,
            SignalType.ACTIVITY_INDEX.value,
            SignalType.HRV_RMSSD.value,
            SignalType.MOOD_SCORE.value,
            SignalType.ENERGY_SCORE.value,
        ],
        "expected_window": ["Day 13", "Day 23"],
        "description": (
            "Sustained sleep fragmentation (+30 pts), PVT slowing (+74 ms, 3 lapses), and passive "
            "activity drop (~0.72) for Dr. Marcus Chen while check-in mood/energy stay 4/5 "
            "(underreporting mismatch). Includes explicit 9h sensor_off gap and Day 12 suspect spike."
        ),
    },
    {
        "event_id": "SHARED_LAB_CO2_EXPOSURE",
        "target_id": "LAB",
        "target_type": "zone",
        "affected_crew": ["ast-03", "ast-04"],
        "anomaly_kind": "contextual",
        "onset_day": 15,
        "peak_day": 19,
        "magnitude": "large",
        "magnitude_details": {
            "peak_co2_ppm": 5240.0,
            "day23_co2_ppm": 1113.0,
            "day23_7d_avg_ppm": 2062.0,
            "expected_r_lag0": 0.955,
            "sr03_threshold_ppm": 5000.0,
        },
        "affected_signals": [
            SignalType.CO2_PPM.value,
            SignalType.SYMPTOM_HEADACHE.value,
            SignalType.SYMPTOM_FATIGUE.value,
            SignalType.ENERGY_SCORE.value,
        ],
        "expected_window": ["Day 15", "Day 22"],
        "description": (
            "US Lab CO2 scrubber degradation Days 15-22 peaking >= 5,150 ppm on Day 19 (SR-03), "
            "serviced Day 22 down to ~1,113 ppm on Day 23 (7d avg ~2,062 ppm), with 2h missing "
            "CO2 packet loss Day 18 14:00-15:00. Yuki (ast-03) and Omar (ast-04) symptoms co-move "
            "tightly (r ~ 0.95-0.96, lag 0d) with LAB CO2."
        ),
    },
    {
        "event_id": "SLOW_RADIATION_TREND",
        "target_id": HABITAT_ACTOR_ID,
        "target_type": "habitat",
        "anomaly_kind": "drift",
        "onset_day": 1,
        "peak_day": 23,
        "magnitude": "medium",
        "magnitude_details": {
            "daily_rate_usv_day": 505.0,
            "day23_cumulative_msv": 12.82,
        },
        "affected_signals": [
            SignalType.RADIATION_USV_DAY.value,
            SignalType.RADIATION_CUMULATIVE_MSV.value,
        ],
        "expected_window": ["Day 1", "Day 30"],
        "description": (
            "Shared habitat dosimetry trend (~505 uSv/day) accumulating to ~12.82 mSv by Day 23."
        ),
    },
]

SCENARIO_BY_ID: Dict[str, Dict[str, Any]] = {
    item["event_id"]: item for item in SCENARIO_MANIFEST
}

PLANTED_DATA_FAULTS: List[Dict[str, Any]] = [
    {
        "fault_id": "DF_MC_SENSOR_OFF_9H",
        "target_id": "ast-02",
        "signal_type": SignalType.HEART_RATE.value,
        "quality": QualityState.SENSOR_OFF.value,
        "window": "Day 21 22:00 -> Day 22 07:00",
        "hours": 9,
    },
    {
        "fault_id": "DF_MC_MOTION_SPIKE",
        "target_id": "ast-02",
        "signal_type": SignalType.HEART_RATE.value,
        "quality": QualityState.SUSPECT.value,
        "window": "Day 12 16:00",
        "hours": 1,
    },
    {
        "fault_id": "DF_LAB_CO2_MISSING_2H",
        "target_id": "LAB",
        "signal_type": SignalType.CO2_PPM.value,
        "quality": QualityState.MISSING.value,
        "window": "Day 18 14:00 -> Day 18 16:00",
        "hours": 2,
    },
]

# Personal early-mission baseline parameters (illustrative, non-clinical)
_ASTRONAUT_BASELINES: Dict[str, Dict[str, float]] = {
    "ast-01": {
        "hr_rest": 58.2,
        "hr_sleep": 53.6,
        "hr_work": 78.0,
        "hr_ex1": 104.0,
        "hr_ex2": 114.0,
        "hr_rec": 34.5,
        "rhr": 54.9,
        "hrv": 62.0,
        "spo2": 97.6,
        "sleep_dur": 7.0,
        "sleep_frag": 10.5,
        "pvt_rt": 251.1,
        "pvt_lapses": 0.0,
        "activity": 1.00,
        "headache": 0.0,
        "fatigue": 0.5,
        "mood": 4.0,
        "energy": 4.0,
        "stress": 2.0,
    },
    "ast-02": {
        "hr_rest": 62.5,
        "hr_sleep": 56.5,
        "hr_work": 81.0,
        "hr_ex1": 106.0,
        "hr_ex2": 116.0,
        "hr_rec": 32.0,
        "rhr": 58.6,
        "hrv": 54.0,
        "spo2": 97.9,
        "sleep_dur": 7.1,
        "sleep_frag": 12.0,
        "pvt_rt": 256.0,
        "pvt_lapses": 0.0,
        "activity": 1.00,
        "headache": 0.0,
        "fatigue": 0.8,
        "mood": 4.0,
        "energy": 4.0,
        "stress": 2.0,
    },
    "ast-03": {
        "hr_rest": 61.0,
        "hr_sleep": 55.2,
        "hr_work": 79.0,
        "hr_ex1": 105.0,
        "hr_ex2": 115.0,
        "hr_rec": 35.0,
        "rhr": 56.2,
        "hrv": 60.0,
        "spo2": 98.1,
        "sleep_dur": 7.2,
        "sleep_frag": 11.0,
        "pvt_rt": 245.0,
        "pvt_lapses": 0.0,
        "activity": 1.02,
        "headache": 0.05,
        "fatigue": 0.6,
        "mood": 4.0,
        "energy": 4.0,
        "stress": 2.0,
    },
    "ast-04": {
        "hr_rest": 63.0,
        "hr_sleep": 57.0,
        "hr_work": 82.0,
        "hr_ex1": 107.0,
        "hr_ex2": 117.0,
        "hr_rec": 33.2,
        "rhr": 58.0,
        "hrv": 57.5,
        "spo2": 97.8,
        "sleep_dur": 7.1,
        "sleep_frag": 11.5,
        "pvt_rt": 248.0,
        "pvt_lapses": 0.0,
        "activity": 0.99,
        "headache": 0.05,
        "fatigue": 0.65,
        "mood": 4.0,
        "energy": 4.0,
        "stress": 2.0,
    },
}

# LAB daily target CO2 profile (Days 14..24) calibrated so:
# - Day 19 peaks >= 5,150 ppm (triggers SR-03 >= 5,000 ppm)
# - Day 22 scrubber serviced
# - Day 23 reads ~1,113 ppm
# - Day 17..23 7-day average is ~2,062 ppm
_LAB_DAILY_TARGET_CO2: Dict[int, float] = {
    14: 880.0,
    15: 1050.0,
    16: 1220.0,
    17: 1410.0,
    18: 2245.0,
    19: 3980.0,
    20: 2810.0,
    21: 1765.0,
    22: 1225.0,
    23: 1113.0,
    24: 990.0,
    25: 925.0,
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ramp(day: int, start_day: int, end_day: int) -> float:
    """Smooth 0..1 progression from `start_day - 1` up to `end_day`."""
    if day < start_day:
        return 0.0
    if day >= end_day:
        return 1.0
    span = max(1, end_day - start_day + 1)
    return _clamp((day - start_day + 1) / float(span), 0.0, 1.0)


def _timestamp_and_met(day: int, hour: int) -> Tuple[str, float]:
    dt = MISSION_START_UTC + timedelta(days=day - 1, hours=hour)
    met = float((day - 1) * 24 + hour)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ"), met


def _hour_context(hour: int) -> str:
    if hour <= 5 or hour >= 22:
        return "sleep"
    if hour in (10, 11):
        return "exercise"
    if hour in (9, 13, 14, 15):
        return "high_workload"
    return "rest"


def _make_record(
    astronaut_id: str,
    day: int,
    hour: int,
    signal_type: str,
    value: Optional[float],
    zone_id: str,
    source_device: str,
    firmware_version: str = "2.4.1",
    quality: str = QualityState.OK.value,
    confidence: float = 0.98,
    context_tags: Optional[List[str]] = None,
) -> MeasurementRecord:
    ts, met = _timestamp_and_met(day, hour)
    return MeasurementRecord(
        astronaut_id=astronaut_id,
        timestamp_utc=ts,
        mission_elapsed_time=met,
        day=day,
        hour=hour,
        signal_type=signal_type,
        value=value,
        unit=SIGNAL_UNITS[signal_type],
        source_device=source_device,
        firmware_version=firmware_version,
        quality=quality,
        confidence=confidence,
        context_tags=list(context_tags or ["rest"]),
        consent_scope=SIGNAL_TO_SCOPE.get(signal_type, ConsentScope.PHYSIO.value),
        zone_id=zone_id,
    )


def _avoid_flatline(
    val: float,
    recent_values: List[float],
    step: float = 0.03,
    decimals: int = 2,
    bounds: Optional[Tuple[float, float]] = None,
) -> float:
    """Prevent 3 identical consecutive values on continuous signals (avoids false saturation)."""
    rounded = round(val, decimals)
    if (
        len(recent_values) >= 2
        and abs(recent_values[-1] - rounded) <= 1e-6
        and abs(recent_values[-2] - rounded) <= 1e-6
    ):
        cand = round(rounded + step, decimals)
        if bounds is not None and (cand < bounds[0] or cand > bounds[1]):
            cand = round(rounded - step, decimals)
        rounded = cand
    recent_values.append(rounded)
    if len(recent_values) > 4:
        del recent_values[0]
    return rounded


def _lab_co2_hourly(day: int, hour: int, rng: random.Random, null_mission: bool) -> float:
    """Compute US Lab CO2 (ppm) for (day, hour)."""
    diurnal = 18.0 * math.sin((hour - 6) * math.pi / 12.0)
    if null_mission:
        return round(_clamp(880.0 + diurnal + rng.gauss(0.0, 9.0), 750.0, 1020.0), 1)

    if day <= 14:
        base = 880.0 + diurnal + rng.gauss(0.0, 9.0)
        return round(_clamp(base, 760.0, 1020.0), 1)

    if day == 19:
        # Smooth diurnal peak reaching >= 5,150 ppm at midday/afternoon while averaging ~3,940 ppm.
        peak_shape = max(0.0, math.sin((hour - 5) * math.pi / 18.0)) if 5 <= hour <= 23 else 0.0
        base = 2680.0 + 2580.0 * (peak_shape ** 1.15)
        if hour in (14, 15, 16):
            base = max(base, 5210.0)
        return round(base + rng.gauss(0.0, 12.0), 1)

    if day == 22:
        # Scrubber serviced at 08:00-14:00: drops smoothly without sharp impulse step.
        if hour < 8:
            base = 1480.0 - 20.0 * hour
        elif hour <= 14:
            frac = (hour - 8) / 6.0
            base = 1320.0 - 180.0 * frac
        else:
            base = 1140.0 - 3.0 * (hour - 14)
        return round(base + rng.gauss(0.0, 7.0), 1)

    if day == 23:
        if hour == 16:
            return round(1113.0 + rng.uniform(-1.5, 1.5), 1)
        return round(1113.0 + 12.0 * math.sin((hour - 8) * math.pi / 12.0) + rng.gauss(0.0, 6.0), 1)

    target = _LAB_DAILY_TARGET_CO2.get(day, 888.0)
    return round(_clamp(target + diurnal + rng.gauss(0.0, 9.0), 760.0, 4950.0), 1)


def _zone_co2_hourly(zone_id: str, day: int, hour: int, rng: random.Random, null_mission: bool) -> float:
    if zone_id == "LAB":
        return _lab_co2_hourly(day, hour, rng, null_mission)

    nominal = {"N1": 834.0, "CQ": 780.0, "AL": 622.0}[zone_id]
    diurnal = 8.0 * math.sin((hour - 7) * math.pi / 12.0)
    if not null_mission and day == 23 and hour == 16:
        return round(nominal + rng.uniform(-0.8, 0.8), 1)
    # Slight realistic mixing bleed into N1 during Days 17-21 in non-null mode (kept well inside normal band)
    bleed = 0.0
    if not null_mission and zone_id == "N1" and 16 <= day <= 22:
        bleed_map = {16: 35.0, 17: 95.0, 18: 155.0, 19: 210.0, 20: 145.0, 21: 80.0, 22: 30.0}
        bleed = bleed_map[day]
    return round(nominal + bleed + diurnal + rng.gauss(0.0, 4.5), 1)


def _daily_targets_for_astronaut(
    aid: str,
    day: int,
    rng: random.Random,
    null_mission: bool,
    lab_wake_co2: float,
) -> Dict[str, float]:
    """Return daily physiological, cognitive, and self-report targets for `aid` on `day`."""
    b = _ASTRONAUT_BASELINES[aid]

    # Null mission: stationary zero-mean fluctuations bounded so CUSUM stays silent
    if null_mission:
        return {
            "hr_rest_shift": rng.gauss(0.0, 0.9),
            "hr_sleep_shift": rng.gauss(0.0, 0.7),
            "hr_rec": round(b["hr_rec"] + rng.gauss(0.0, 0.9), 2),
            "rhr": round(b["rhr"] + rng.gauss(0.0, 0.6), 2),
            "hrv": round(b["hrv"] + rng.gauss(0.0, 1.5), 2),
            "spo2": round(_clamp(b["spo2"] + rng.gauss(0.0, 0.25), 95.5, 99.5), 2),
            "sleep_dur": round(_clamp(b["sleep_dur"] + rng.gauss(0.0, 0.22), 5.8, 8.4), 2),
            "sleep_frag": round(_clamp(b["sleep_frag"] + rng.gauss(0.0, 1.4), 4.0, 24.0), 2),
            "pvt_rt": round(_clamp(b["pvt_rt"] + rng.gauss(0.0, 4.5), 215.0, 295.0), 1),
            "pvt_lapses": 0.0,
            "activity": round(_clamp(b["activity"] + rng.gauss(0.0, 0.04), 0.75, 1.35), 2),
            "headache": 0.0 if aid in ("ast-01", "ast-02") else round(_clamp(rng.gauss(0.05, 0.05), 0.0, 0.4), 2),
            "fatigue": round(_clamp(b["fatigue"] + rng.gauss(0.0, 0.15), 0.0, 2.0), 2),
            "mood": float(round(_clamp(b["mood"] + rng.gauss(0.0, 0.15), 3.0, 5.0))),
            "energy": float(round(_clamp(b["energy"] + rng.gauss(0.0, 0.15), 3.0, 5.0))),
            "stress": float(round(_clamp(b["stress"] + rng.gauss(0.0, 0.15), 1.0, 3.0))),
        }

    # --- Planted scenario trajectories ---
    if aid == "ast-01":
        # Elena Vasquez: baseline Days 1-12, progressive recovery debt Days 14-23 (plateaus/eases slightly Days 24-30)
        if day <= 12:
            p = 0.0
        elif day <= 23:
            p = (day - 13) / 10.0 if day >= 14 else 0.05
        else:
            p = max(0.75, 1.0 - 0.03 * (day - 23))

        # Tighter noise on Day 23 and baseline so validation assertions land accurately
        noise_scale = 0.35 if day in (12, 23) else 0.75
        hr_rec = b["hr_rec"] - 13.3 * p + rng.gauss(0.0, 0.35 * noise_scale)
        rhr = b["rhr"] + 3.3 * p + rng.gauss(0.0, 0.25 * noise_scale)
        hrv = b["hrv"] - 19.2 * p + rng.gauss(0.0, 0.65 * noise_scale)
        sleep_dur = b["sleep_dur"] - 0.7 * p + rng.gauss(0.0, 0.06 * noise_scale)
        sleep_frag = b["sleep_frag"] + 7.5 * p + rng.gauss(0.0, 0.7 * noise_scale)
        pvt_rt = b["pvt_rt"] + 11.9 * p + rng.gauss(0.0, 1.5 * noise_scale)
        hr_rest_shift = 14.8 * p + rng.gauss(0.0, 0.3 * noise_scale)
        hr_sleep_shift = 8.5 * p + rng.gauss(0.0, 0.3 * noise_scale)
        # Elena's mild fatigue peaks Days 21-23 (progressive debt, NOT Day 19 CO2 spike)
        late_p = max(0.0, (day - 15) / 8.0) if day <= 23 else max(0.75, 1.0 - 0.03 * (day - 23))
        fatigue = b["fatigue"] + 1.5 * (late_p ** 1.2) + rng.gauss(0.0, 0.08)
        mood = 4.0 if day < 20 else 3.0
        energy = 4.0 if day < 20 else 3.0
        stress = 2.0 if p < 0.5 else 2.5
        activity = 1.00 - 0.07 * p + rng.gauss(0.0, 0.01)
        spo2 = 97.6 - 0.45 * p + rng.gauss(0.0, 0.12)
        if day == 23:
            hr_rec = 21.2 + rng.uniform(-0.15, 0.15)
            rhr = 58.2 + rng.uniform(-0.1, 0.1)
            hrv = 42.8 + rng.uniform(-0.2, 0.2)
            sleep_dur = 6.3 + rng.uniform(-0.04, 0.04)
            pvt_rt = 263.0 + rng.uniform(-0.8, 0.8)
            hr_rest_shift = 73.0 - b["hr_rest"]
            activity = 0.93
            spo2 = 97.2 + rng.uniform(-0.15, 0.15)
        return {
            "hr_rest_shift": hr_rest_shift,
            "hr_sleep_shift": hr_sleep_shift,
            "hr_rec": round(hr_rec, 2),
            "rhr": round(rhr, 2),
            "hrv": round(hrv, 2),
            "spo2": round(_clamp(spo2, 95.5, 99.5), 2),
            "sleep_dur": round(sleep_dur, 2),
            "sleep_frag": round(sleep_frag, 2),
            "pvt_rt": round(pvt_rt, 1),
            "pvt_lapses": 0.0,
            "activity": round(_clamp(activity, 0.7, 1.3), 2),
            "headache": 0.0,
            "fatigue": round(_clamp(fatigue, 0.0, 5.0), 2),
            "mood": float(mood),
            "energy": float(energy),
            "stress": float(stress),
        }

    if aid == "ast-02":
        # Marcus Chen: baseline Days 1-11; Days 13-23 cognitive drift + underreporting
        if day <= 11:
            p = 0.0
        elif day == 12:
            p = 0.03
        elif day <= 23:
            p = (day - 12) / 11.0
        else:
            p = max(0.8, 1.0 - 0.02 * (day - 23))

        noise_scale = 0.3 if day in (11, 23) else 0.7
        sleep_frag = b["sleep_frag"] + 30.0 * p + rng.gauss(0.0, 0.9 * noise_scale)
        pvt_rt = b["pvt_rt"] + 74.0 * p + rng.gauss(0.0, 2.0 * noise_scale)
        lapses = 0.0 if p < 0.35 else (1.0 if p < 0.65 else (2.0 if p < 0.88 else 3.0))
        activity = b["activity"] - 0.28 * (p ** 1.1) + rng.gauss(0.0, 0.015 * noise_scale)
        hrv = b["hrv"] - 9.0 * p + rng.gauss(0.0, 0.9 * noise_scale)
        rhr = b["rhr"] + 2.8 * p + rng.gauss(0.0, 0.35 * noise_scale)
        hr_rec = b["hr_rec"] - 4.0 * p + rng.gauss(0.0, 0.5 * noise_scale)
        sleep_dur = b["sleep_dur"] - 0.25 * p + rng.gauss(0.0, 0.08 * noise_scale)
        if day == 23:
            sleep_frag = b["sleep_frag"] + 30.0 + rng.uniform(-0.3, 0.3)
            pvt_rt = b["pvt_rt"] + 74.0 + rng.uniform(-0.8, 0.8)
            lapses = 3.0
            activity = 0.72 + rng.uniform(-0.01, 0.01)
        return {
            "hr_rest_shift": 2.8 * p + rng.gauss(0.0, 0.6),
            "hr_sleep_shift": 2.2 * p + rng.gauss(0.0, 0.5),
            "hr_rec": round(hr_rec, 2),
            "rhr": round(rhr, 2),
            "hrv": round(hrv, 2),
            "spo2": round(_clamp(b["spo2"] + rng.gauss(0.0, 0.2), 96.0, 99.5), 2),
            "sleep_dur": round(sleep_dur, 2),
            "sleep_frag": round(sleep_frag, 2),
            "pvt_rt": round(pvt_rt, 1),
            "pvt_lapses": float(lapses),
            "activity": round(_clamp(activity, 0.5, 1.3), 2),
            "headache": 0.0,
            "fatigue": round(_clamp(b["fatigue"] + 0.5 * p + rng.gauss(0.0, 0.1), 0.0, 5.0), 2),
            # Underreporting mismatch: check-ins stay steady 4/5 despite passive & cognitive drift
            "mood": 4.0,
            "energy": 4.0,
            "stress": 2.0,
        }

    # ast-03 (Yuki Tanaka) & ast-04 (Omar Haddad): stationed in LAB, symptoms co-move tightly (r~0.95-0.96, lag 0d)
    excess = max(0.0, (lab_wake_co2 - 880.0) / 3600.0)
    # Calibrate independent day noise so Pearson r vs LAB CO2 across Days 1-23 lands ~0.95-0.96
    # while single-day headache steps stay smooth (< 1.35) under quality.py step checks.
    noise_h = rng.gauss(0.0, 0.24)
    noise_f = rng.gauss(0.0, 0.24)
    noise_e = rng.gauss(0.0, 0.24)

    headache = _clamp(0.06 + 1.95 * excess + noise_h, 0.0, 3.0)
    fatigue = _clamp(b["fatigue"] + 2.40 * excess + noise_f, 0.0, 5.0)
    energy = _clamp(4.0 - 1.50 * excess + noise_e, 1.0, 5.0)
    mood = _clamp(4.0 - 0.80 * excess + rng.gauss(0.0, 0.10), 1.0, 5.0)
    stress = _clamp(2.0 + 0.90 * excess + rng.gauss(0.0, 0.12), 1.0, 5.0)
    sleep_frag = b["sleep_frag"] + 7.0 * excess + rng.gauss(0.0, 0.9)
    hrv = b["hrv"] - 5.5 * excess + rng.gauss(0.0, 1.0)
    pvt_rt = b["pvt_rt"] + 18.0 * excess + rng.gauss(0.0, 2.5)
    return {
        "hr_rest_shift": 3.0 * excess + rng.gauss(0.0, 0.7),
        "hr_sleep_shift": 1.8 * excess + rng.gauss(0.0, 0.6),
        "hr_rec": round(b["hr_rec"] - 2.0 * excess + rng.gauss(0.0, 0.6), 2),
        "rhr": round(b["rhr"] + 1.5 * excess + rng.gauss(0.0, 0.4), 2),
        "hrv": round(hrv, 2),
        "spo2": round(_clamp(b["spo2"] + rng.gauss(0.0, 0.2), 96.0, 99.5), 2),
        "sleep_dur": round(_clamp(b["sleep_dur"] - 0.25 * excess + rng.gauss(0.0, 0.15), 5.8, 8.2), 2),
        "sleep_frag": round(sleep_frag, 2),
        "pvt_rt": round(pvt_rt, 1),
        "pvt_lapses": 0.0 if excess < 0.75 else 1.0,
        "activity": round(_clamp(b["activity"] - 0.08 * excess + rng.gauss(0.0, 0.025), 0.7, 1.3), 2),
        "headache": round(headache, 2),
        "fatigue": round(fatigue, 2),
        "mood": round(mood, 2),
        "energy": round(energy, 2),
        "stress": round(stress, 2),
    }


def inject_artifacts(
    records: Sequence[MeasurementRecord],
    astronaut_id: str = "ast-02",
    signal_type: str = SignalType.HEART_RATE.value,
    day: int = 12,
    hour: int = 16,
    artifact_type: str = "motion_spike",
    value: Optional[float] = None,
    seed: int = 42,
) -> List[MeasurementRecord]:
    """Return a modified copy of `records` with an explicit data artifact injected.

    Supported `artifact_type` values:
    - `motion_spike`: high-amplitude transient tagged `motion_artifact` and `suspect`.
    - `out_of_range`: value outside `SAMPLE_PLAUSIBLE_RANGES` and `out_of_range`.
    - `saturated`: 3 consecutive identical readings (stuck sensor).
    - `clock_jump`: backward UTC timestamp jump on the target record.
    - `sensor_off` / `missing`: explicit gap with `value=None` and `confidence=0.0`.
    """
    _ = random.Random(seed)
    valid_types = {
        "motion_spike",
        "out_of_range",
        "saturated",
        "clock_jump",
        "sensor_off",
        "missing",
    }
    if artifact_type not in valid_types:
        raise ValueError(f"Unsupported artifact_type: {artifact_type}")

    cloned = [replace(r, context_tags=list(r.context_tags)) for r in records]
    matches = [
        i
        for i, r in enumerate(cloned)
        if r.astronaut_id == astronaut_id and r.signal_type == signal_type
    ]

    def _find_slot(target_day: int, target_hour: int) -> Optional[int]:
        for idx in matches:
            if cloned[idx].day == target_day and cloned[idx].hour == target_hour:
                return idx
        return None

    target_idx = _find_slot(day, hour)
    if target_idx is None:
        zone_id = CREW_BY_ID[astronaut_id].default_zone if astronaut_id in CREW_BY_ID else "LAB"
        new_rec = _make_record(
            astronaut_id=astronaut_id,
            day=day,
            hour=hour,
            signal_type=signal_type,
            value=value,
            zone_id=zone_id,
            source_device="wristband-v2",
        )
        cloned.append(new_rec)
        target_idx = len(cloned) - 1
        matches.append(target_idx)

    rec = cloned[target_idx]
    bounds = SAMPLE_PLAUSIBLE_RANGES.get(signal_type, (0.0, 200.0))

    if artifact_type == "motion_spike":
        spike_val = float(value) if value is not None else min(bounds[1] - 5.0, 188.0)
        tags = list(rec.context_tags)
        if "motion_artifact" not in tags:
            tags.append("motion_artifact")
        cloned[target_idx] = replace(
            rec,
            value=round(spike_val, 2),
            quality=QualityState.SUSPECT.value,
            confidence=0.25,
            context_tags=tags,
        )
    elif artifact_type == "out_of_range":
        oor_val = float(value) if value is not None else float(bounds[1]) + 45.0
        cloned[target_idx] = replace(
            rec,
            value=round(oor_val, 2),
            quality=QualityState.OUT_OF_RANGE.value,
            confidence=0.0,
        )
    elif artifact_type in (QualityState.SENSOR_OFF.value, QualityState.MISSING.value):
        cloned[target_idx] = replace(
            rec,
            value=None,
            quality=artifact_type,
            confidence=0.0,
        )
    elif artifact_type == "clock_jump":
        ts_dt = datetime.strptime(rec.timestamp_utc, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        ) - timedelta(hours=3)
        cloned[target_idx] = replace(
            rec,
            timestamp_utc=ts_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
    elif artifact_type == "saturated":
        sat_val = float(value) if value is not None else (
            float(rec.value) if rec.value is not None else float(bounds[1]) - 10.0
        )
        for offset_h in range(3):
            abs_h = (day - 1) * 24 + hour + offset_h
            d_i = (abs_h // 24) + 1
            h_i = abs_h % 24
            idx_i = _find_slot(d_i, h_i)
            if idx_i is None:
                cloned.append(
                    _make_record(
                        astronaut_id=astronaut_id,
                        day=d_i,
                        hour=h_i,
                        signal_type=signal_type,
                        value=round(sat_val, 2),
                        zone_id=rec.zone_id,
                        source_device=rec.source_device,
                        firmware_version=rec.firmware_version,
                        quality=QualityState.OK.value,
                        confidence=0.95,
                        context_tags=list(rec.context_tags),
                    )
                )
            else:
                cloned[idx_i] = replace(
                    cloned[idx_i],
                    value=round(sat_val, 2),
                    quality=QualityState.OK.value,
                )

    cloned.sort(key=lambda r: (r.day, r.hour, r.astronaut_id, r.signal_type, r.zone_id))
    return cloned


def inject_device_step(
    records: Sequence[MeasurementRecord],
    astronaut_id: str,
    signal_type: str,
    onset_day: int,
    offset: float,
    new_firmware: str = "2.5.0",
    new_device: Optional[str] = None,
) -> List[MeasurementRecord]:
    """Apply a calibration step offset and firmware/device transition from `onset_day` onward."""
    bounds = SAMPLE_PLAUSIBLE_RANGES.get(signal_type)
    out: List[MeasurementRecord] = []
    for rec in records:
        copied = replace(rec, context_tags=list(rec.context_tags))
        if (
            copied.astronaut_id == astronaut_id
            and copied.signal_type == signal_type
            and copied.day >= onset_day
        ):
            new_val = copied.value
            if new_val is not None and copied.quality in (
                QualityState.OK.value,
                QualityState.SUSPECT.value,
            ):
                shifted = float(new_val) + float(offset)
                if bounds is not None:
                    shifted = _clamp(shifted, bounds[0], bounds[1])
                new_val = round(shifted, 3)
            copied = replace(
                copied,
                value=new_val,
                firmware_version=str(new_firmware),
                source_device=str(new_device) if new_device else copied.source_device,
            )
        out.append(copied)
    return out


def inject_missingness(
    records: Sequence[MeasurementRecord],
    fraction: float,
    seed: int = 42,
    quality_state: str = QualityState.MISSING.value,
    astronaut_id: Optional[str] = None,
    signal_types: Optional[Sequence[str]] = None,
) -> List[MeasurementRecord]:
    """Randomly mark `fraction` of clean `ok` records as explicit `missing`/`sensor_off` gaps."""
    if not (0.0 <= float(fraction) <= 1.0):
        raise ValueError(f"fraction must be in [0.0, 1.0], got {fraction}")
    if quality_state not in (QualityState.MISSING.value, QualityState.SENSOR_OFF.value):
        raise ValueError(f"quality_state must be 'missing' or 'sensor_off', got {quality_state}")

    cloned = [replace(r, context_tags=list(r.context_tags)) for r in records]
    if fraction == 0.0:
        return cloned

    sig_set = set(signal_types) if signal_types is not None else None
    eligible_indices = [
        i
        for i, r in enumerate(cloned)
        if r.quality == QualityState.OK.value
        and (astronaut_id is None or r.astronaut_id == astronaut_id)
        and (sig_set is None or r.signal_type in sig_set)
    ]
    n_drop = min(len(eligible_indices), int(round(len(eligible_indices) * float(fraction))))
    if n_drop == 0:
        return cloned

    rng = random.Random(seed)
    chosen = set(rng.sample(eligible_indices, n_drop))
    for idx in chosen:
        cloned[idx] = replace(
            cloned[idx],
            value=None,
            quality=quality_state,
            confidence=0.0,
        )
    return cloned


def generate_mission(
    days: int = 30,
    seed: int = 42,
    null_mission: bool = False,
    include_device_step: bool = False,
) -> Dict[str, Any]:
    """Generate a reproducible multi-day mission dataset with optional ground-truth scenarios."""
    if days < 1:
        raise ValueError(f"days must be >= 1, got {days}")

    rng = random.Random(seed)
    records: List[MeasurementRecord] = []
    zone_occupancy: Dict[str, Dict[int, str]] = {c.astronaut_id: {} for c in CREW_ROSTER}

    # Track recent continuous values per (actor, zone, signal) to guarantee zero accidental flatlines
    recent_env: Dict[Tuple[str, str], List[float]] = {}
    recent_bio: Dict[Tuple[str, str], List[float]] = {}

    # Track wake-hour LAB CO2 mean per day so ast-03 & ast-04 symptoms align on lag 0d
    lab_wake_co2_by_day: Dict[int, float] = {}

    # 1. Habitat environmental records (4 zones x 24h x days) + daily shared radiation
    cumulative_msv = 1.20 if not null_mission else 0.0
    for day in range(1, days + 1):
        lab_wake_vals: List[float] = []
        for zone in HABITAT_ZONES:
            zid = zone.zone_id
            zone_actor_id = f"{HABITAT_ACTOR_ID}-{zid.lower()}"
            for hour in range(24):
                is_lab_missing_gap = (
                    not null_mission and zid == "LAB" and day == 18 and hour in (14, 15)
                )
                if is_lab_missing_gap:
                    records.append(
                        _make_record(
                            astronaut_id=zone_actor_id,
                            day=day,
                            hour=hour,
                            signal_type=SignalType.CO2_PPM.value,
                            value=None,
                            zone_id=zid,
                            source_device="cabin-env-monitor",
                            firmware_version="3.1.0",
                            quality=QualityState.MISSING.value,
                            confidence=0.0,
                            context_tags=["rest", "packet_loss"],
                        )
                    )
                else:
                    co2_raw = _zone_co2_hourly(zid, day, hour, rng, null_mission)
                    co2_val = _avoid_flatline(
                        co2_raw,
                        recent_env.setdefault((zid, SignalType.CO2_PPM.value), []),
                        step=0.2,
                        decimals=1,
                        bounds=SAMPLE_PLAUSIBLE_RANGES[SignalType.CO2_PPM.value],
                    )
                    if zid == "LAB" and 7 <= hour <= 21:
                        lab_wake_vals.append(co2_val)
                    records.append(
                        _make_record(
                            astronaut_id=zone_actor_id,
                            day=day,
                            hour=hour,
                            signal_type=SignalType.CO2_PPM.value,
                            value=co2_val,
                            zone_id=zid,
                            source_device="cabin-env-monitor",
                            firmware_version="3.1.0",
                            quality=QualityState.OK.value,
                            confidence=0.98,
                            context_tags=["rest"],
                        )
                    )

                # Cabin temperature, humidity, noise (distinct per-zone baselines)
                temp_base = {"LAB": 22.6, "N1": 22.0, "CQ": 21.4, "AL": 20.9}[zid]
                temp_val = _avoid_flatline(
                    temp_base + 0.35 * math.sin((hour - 9) * math.pi / 12.0) + rng.gauss(0.0, 0.12),
                    recent_env.setdefault((zid, SignalType.CABIN_TEMP_C.value), []),
                    step=0.05,
                    decimals=2,
                    bounds=SAMPLE_PLAUSIBLE_RANGES[SignalType.CABIN_TEMP_C.value],
                )
                hum_base = {"LAB": 46.5, "N1": 44.2, "CQ": 42.6, "AL": 40.5}[zid]
                hum_val = _avoid_flatline(
                    hum_base + 1.5 * math.cos((hour - 6) * math.pi / 12.0) + rng.gauss(0.0, 0.35),
                    recent_env.setdefault((zid, SignalType.CABIN_HUMIDITY_PCT.value), []),
                    step=0.1,
                    decimals=1,
                    bounds=SAMPLE_PLAUSIBLE_RANGES[SignalType.CABIN_HUMIDITY_PCT.value],
                )
                noise_base = (
                    60.5 if (zid == "LAB" and 7 <= hour <= 20)
                    else (48.5 if hour <= 6 or hour >= 22 else {"N1": 55.2, "LAB": 56.8, "CQ": 51.0, "AL": 53.4}[zid])
                )
                noise_val = _avoid_flatline(
                    noise_base + rng.gauss(0.0, 0.8),
                    recent_env.setdefault((zid, SignalType.CABIN_NOISE_DB.value), []),
                    step=0.1,
                    decimals=1,
                    bounds=SAMPLE_PLAUSIBLE_RANGES[SignalType.CABIN_NOISE_DB.value],
                )
                for sig_name, sig_v in (
                    (SignalType.CABIN_TEMP_C.value, temp_val),
                    (SignalType.CABIN_HUMIDITY_PCT.value, hum_val),
                    (SignalType.CABIN_NOISE_DB.value, noise_val),
                ):
                    records.append(
                        _make_record(
                            astronaut_id=zone_actor_id,
                            day=day,
                            hour=hour,
                            signal_type=sig_name,
                            value=sig_v,
                            zone_id=zid,
                            source_device="cabin-env-monitor",
                            firmware_version="3.1.0",
                            quality=QualityState.OK.value,
                            confidence=0.98,
                            context_tags=["rest"],
                        )
                    )

        lab_wake_co2_by_day[day] = (
            sum(lab_wake_vals) / len(lab_wake_vals) if lab_wake_vals else 880.0
        )

        # Shared daily radiation dose-rate & cumulative dose (505 uSv/day -> 12.82 mSv by Day 23)
        if null_mission:
            daily_usv = round(500.0 + rng.gauss(0.0, 6.0), 1)
        elif day == 23:
            daily_usv = 505.0
        else:
            daily_usv = round(505.0 + rng.gauss(0.0, 4.5), 1)
        cumulative_msv = round(cumulative_msv + daily_usv / 1000.0, 2)
        if not null_mission and day == 23:
            cumulative_msv = 12.82

        records.append(
            _make_record(
                astronaut_id=HABITAT_ACTOR_ID,
                day=day,
                hour=16,
                signal_type=SignalType.RADIATION_USV_DAY.value,
                value=daily_usv,
                zone_id="N1",
                source_device="rem-dosimeter",
                firmware_version="1.8.0",
                quality=QualityState.OK.value,
                confidence=0.96,
                context_tags=["rest"],
            )
        )
        records.append(
            _make_record(
                astronaut_id=HABITAT_ACTOR_ID,
                day=day,
                hour=16,
                signal_type=SignalType.RADIATION_CUMULATIVE_MSV.value,
                value=cumulative_msv,
                zone_id="N1",
                source_device="rem-dosimeter",
                firmware_version="1.8.0",
                quality=QualityState.OK.value,
                confidence=0.96,
                context_tags=["rest"],
            )
        )

    # 2. Per-astronaut wearable, cognitive, and self-report signals
    for crew in CREW_ROSTER:
        aid = crew.astronaut_id
        base = _ASTRONAUT_BASELINES[aid]

        # Occasional realistic 2h gap in null_mission so null tests verify gap handling without FA
        null_gap_day = 14 if aid == "ast-02" else None

        for day in range(1, days + 1):
            zone_occupancy[aid][day] = crew.default_zone
            daily = _daily_targets_for_astronaut(
                aid=aid,
                day=day,
                rng=rng,
                null_mission=null_mission,
                lab_wake_co2=lab_wake_co2_by_day[day],
            )

            # Hourly heart_rate across 24 hours
            for hour in range(24):
                ctx = _hour_context(hour)
                # Sleep in CQ overnight (22..06), primary duty zone during wake hours (07..21)
                active_zone = "CQ" if (hour <= 6 or hour >= 22) else crew.default_zone

                is_mc_sensor_off = (
                    not null_mission
                    and aid == "ast-02"
                    and ((day == 21 and hour >= 22) or (day == 22 and hour <= 6))
                )
                is_null_sensor_off = (
                    null_mission
                    and null_gap_day is not None
                    and day == null_gap_day
                    and hour in (2, 3)
                )

                if is_mc_sensor_off or is_null_sensor_off:
                    records.append(
                        _make_record(
                            astronaut_id=aid,
                            day=day,
                            hour=hour,
                            signal_type=SignalType.HEART_RATE.value,
                            value=None,
                            zone_id=active_zone,
                            source_device="wristband-v2",
                            quality=QualityState.SENSOR_OFF.value,
                            confidence=0.0,
                            context_tags=[ctx],
                        )
                    )
                    continue

                is_mc_motion_spike = (
                    not null_mission and aid == "ast-02" and day == 12 and hour == 16
                )
                if is_mc_motion_spike:
                    records.append(
                        _make_record(
                            astronaut_id=aid,
                            day=day,
                            hour=hour,
                            signal_type=SignalType.HEART_RATE.value,
                            value=188.0,
                            zone_id=active_zone,
                            source_device="wristband-v2",
                            quality=QualityState.SUSPECT.value,
                            confidence=0.25,
                            context_tags=[ctx, "motion_artifact"],
                        )
                    )
                    continue

                if ctx == "sleep":
                    hr_raw = base["hr_sleep"] + daily["hr_sleep_shift"] + rng.gauss(0.0, 1.1)
                elif ctx == "exercise":
                    ex_base = base["hr_ex1"] if hour == 10 else base["hr_ex2"]
                    hr_raw = ex_base + 0.5 * daily["hr_rest_shift"] + rng.gauss(0.0, 1.8)
                elif ctx == "high_workload":
                    hr_raw = base["hr_work"] + 0.7 * daily["hr_rest_shift"] + rng.gauss(0.0, 1.5)
                elif hour == 12:
                    # Smooth post-exercise cooldown hour before afternoon rest/work
                    hr_raw = (base["hr_rest"] + 19.0) + 0.6 * daily["hr_rest_shift"] + rng.gauss(0.0, 1.2)
                else:
                    hr_raw = base["hr_rest"] + daily["hr_rest_shift"] + rng.gauss(0.0, 1.1)
                    if not null_mission and aid == "ast-01" and day == 23 and hour == 16:
                        hr_raw = 73.0 + rng.uniform(-0.2, 0.2)

                hr_val = _avoid_flatline(
                    _clamp(hr_raw, 42.0, 175.0),
                    recent_bio.setdefault((aid, SignalType.HEART_RATE.value), []),
                    step=0.2,
                    decimals=1,
                    bounds=SAMPLE_PLAUSIBLE_RANGES[SignalType.HEART_RATE.value],
                )
                records.append(
                    _make_record(
                        astronaut_id=aid,
                        day=day,
                        hour=hour,
                        signal_type=SignalType.HEART_RATE.value,
                        value=hr_val,
                        zone_id=active_zone,
                        source_device="wristband-v2",
                        quality=QualityState.OK.value,
                        confidence=0.97,
                        context_tags=[ctx],
                    )
                )

            # SpO2 twice daily (08:00 & 16:00) outside overnight sensor_off window
            for spo2_h in (8, 16):
                spo2_val = _avoid_flatline(
                    daily["spo2"] + rng.gauss(0.0, 0.12),
                    recent_bio.setdefault((aid, SignalType.SPO2.value), []),
                    step=0.1,
                    decimals=2,
                    bounds=SAMPLE_PLAUSIBLE_RANGES[SignalType.SPO2.value],
                )
                records.append(
                    _make_record(
                        astronaut_id=aid,
                        day=day,
                        hour=spo2_h,
                        signal_type=SignalType.SPO2.value,
                        value=spo2_val,
                        zone_id=crew.default_zone,
                        source_device="wristband-v2",
                        quality=QualityState.OK.value,
                        confidence=0.97,
                        context_tags=["rest"],
                    )
                )

            # Overnight wearable metrics at 07:00 (omitted for ast-02 Day 22 after overnight sensor_off)
            overnight_missed = not null_mission and aid == "ast-02" and day == 22
            if not overnight_missed:
                hrv_val = _avoid_flatline(
                    daily["hrv"],
                    recent_bio.setdefault((aid, SignalType.HRV_RMSSD.value), []),
                    step=0.15,
                    decimals=2,
                    bounds=SAMPLE_PLAUSIBLE_RANGES[SignalType.HRV_RMSSD.value],
                )
                records.append(
                    _make_record(
                        astronaut_id=aid,
                        day=day,
                        hour=7,
                        signal_type=SignalType.HRV_RMSSD.value,
                        value=hrv_val,
                        zone_id="CQ",
                        source_device="wristband-v2",
                        quality=QualityState.OK.value,
                        confidence=0.96,
                        context_tags=["sleep"],
                    )
                )
                records.append(
                    _make_record(
                        astronaut_id=aid,
                        day=day,
                        hour=7,
                        signal_type=SignalType.SLEEP_DURATION.value,
                        value=daily["sleep_dur"],
                        zone_id="CQ",
                        source_device="wristband-v2",
                        quality=QualityState.OK.value,
                        confidence=0.96,
                        context_tags=["sleep"],
                    )
                )
                records.append(
                    _make_record(
                        astronaut_id=aid,
                        day=day,
                        hour=7,
                        signal_type=SignalType.SLEEP_FRAGMENTATION.value,
                        value=daily["sleep_frag"],
                        zone_id="CQ",
                        source_device="wristband-v2",
                        quality=QualityState.OK.value,
                        confidence=0.95,
                        context_tags=["sleep"],
                    )
                )

            # Morning resting HR (07:00; 08:00 on Day 22 for Marcus after putting wristband back on)
            rhr_hour = 8 if overnight_missed else 7
            rhr_val = _avoid_flatline(
                daily["rhr"],
                recent_bio.setdefault((aid, SignalType.RESTING_HR.value), []),
                step=0.1,
                decimals=2,
                bounds=SAMPLE_PLAUSIBLE_RANGES[SignalType.RESTING_HR.value],
            )
            records.append(
                _make_record(
                    astronaut_id=aid,
                    day=day,
                    hour=rhr_hour,
                    signal_type=SignalType.RESTING_HR.value,
                    value=rhr_val,
                    zone_id="CQ" if rhr_hour == 7 else crew.default_zone,
                    source_device="wristband-v2",
                    quality=QualityState.OK.value,
                    confidence=0.96,
                    context_tags=["rest"],
                )
            )

            # Daily active PVT cognitive task (09:00)
            pvt_rt_val = _avoid_flatline(
                daily["pvt_rt"],
                recent_bio.setdefault((aid, SignalType.PVT_MEAN_RT.value), []),
                step=0.2,
                decimals=1,
                bounds=SAMPLE_PLAUSIBLE_RANGES[SignalType.PVT_MEAN_RT.value],
            )
            records.append(
                _make_record(
                    astronaut_id=aid,
                    day=day,
                    hour=9,
                    signal_type=SignalType.PVT_MEAN_RT.value,
                    value=pvt_rt_val,
                    zone_id=crew.default_zone,
                    source_device="astra-pvt-tablet",
                    firmware_version="1.4.0",
                    quality=QualityState.OK.value,
                    confidence=0.97,
                    context_tags=["rest"],
                )
            )
            records.append(
                _make_record(
                    astronaut_id=aid,
                    day=day,
                    hour=9,
                    signal_type=SignalType.PVT_LAPSES.value,
                    value=daily["pvt_lapses"],
                    zone_id=crew.default_zone,
                    source_device="astra-pvt-tablet",
                    firmware_version="1.4.0",
                    quality=QualityState.OK.value,
                    confidence=0.97,
                    context_tags=["rest"],
                )
            )

            # Post-exercise 1-minute heart rate recovery (12:00)
            hr_rec_val = _avoid_flatline(
                daily["hr_rec"],
                recent_bio.setdefault((aid, SignalType.HR_RECOVERY_1M.value), []),
                step=0.1,
                decimals=2,
                bounds=SAMPLE_PLAUSIBLE_RANGES[SignalType.HR_RECOVERY_1M.value],
            )
            records.append(
                _make_record(
                    astronaut_id=aid,
                    day=day,
                    hour=12,
                    signal_type=SignalType.HR_RECOVERY_1M.value,
                    value=hr_rec_val,
                    zone_id=crew.default_zone,
                    source_device="wristband-v2",
                    quality=QualityState.OK.value,
                    confidence=0.96,
                    context_tags=["exercise"],
                )
            )

            # Daily passive activity index & self-report check-in (16:00)
            records.append(
                _make_record(
                    astronaut_id=aid,
                    day=day,
                    hour=16,
                    signal_type=SignalType.ACTIVITY_INDEX.value,
                    value=daily["activity"],
                    zone_id=crew.default_zone,
                    source_device="wristband-v2",
                    quality=QualityState.OK.value,
                    confidence=0.95,
                    context_tags=["rest"],
                )
            )
            for sig_name, sig_key in (
                (SignalType.SYMPTOM_HEADACHE.value, "headache"),
                (SignalType.SYMPTOM_FATIGUE.value, "fatigue"),
                (SignalType.MOOD_SCORE.value, "mood"),
                (SignalType.ENERGY_SCORE.value, "energy"),
                (SignalType.STRESS_SCORE.value, "stress"),
            ):
                records.append(
                    _make_record(
                        astronaut_id=aid,
                        day=day,
                        hour=16,
                        signal_type=sig_name,
                        value=daily[sig_key],
                        zone_id=crew.default_zone,
                        source_device="astra-checkin-ui",
                        firmware_version="1.4.0",
                        quality=QualityState.OK.value,
                        confidence=0.95,
                        context_tags=["rest"],
                    )
                )

    device_steps: List[Dict[str, Any]] = []
    if include_device_step:
        step_day = min(16, max(6, days // 2 + 1))
        records = inject_device_step(
            records,
            astronaut_id="ast-03",
            signal_type=SignalType.RESTING_HR.value,
            onset_day=step_day,
            offset=4.5,
            new_firmware="2.5.0",
        )
        device_steps.append(
            {
                "astronaut_id": "ast-03",
                "signal_type": SignalType.RESTING_HR.value,
                "onset_day": step_day,
                "offset": 4.5,
                "new_firmware": "2.5.0",
            }
        )

    records.sort(key=lambda r: (r.day, r.hour, r.astronaut_id, r.signal_type, r.zone_id))

    if null_mission:
        manifest: List[Dict[str, Any]] = []
        expected_sos: List[Dict[str, Any]] = []
        data_faults: List[Dict[str, Any]] = [
            {
                "fault_id": "DF_NULL_SENSOR_OFF_2H",
                "target_id": "ast-02",
                "signal_type": SignalType.HEART_RATE.value,
                "quality": QualityState.SENSOR_OFF.value,
                "window": "Day 14 02:00 -> Day 14 04:00",
                "hours": 2,
            }
        ]
    else:
        manifest = copy.deepcopy(SCENARIO_MANIFEST)
        expected_sos = [copy.deepcopy(SCENARIO_BY_ID["EV_RECOVERY_DECLINE"]["expected_sos"])] if days >= 23 else []
        data_faults = copy.deepcopy(PLANTED_DATA_FAULTS)

    quality_counts: Dict[str, int] = {q.value: 0 for q in QualityState}
    for rec in records:
        quality_counts[rec.quality] = quality_counts.get(rec.quality, 0) + 1

    day23_snapshot: Dict[str, Any] = {}
    if days >= 23:
        day23_recs = [r for r in records if r.day == 23]
        for aid in ("ast-01", "ast-02", "ast-03", "ast-04"):
            a_recs = {
                (r.signal_type, r.hour): r.value
                for r in day23_recs
                if r.astronaut_id == aid and r.quality == QualityState.OK.value
            }
            day23_snapshot[aid] = {
                "heart_rate_16h": a_recs.get((SignalType.HEART_RATE.value, 16)),
                "resting_hr": a_recs.get((SignalType.RESTING_HR.value, 7)),
                "hrv_rmssd": a_recs.get((SignalType.HRV_RMSSD.value, 7)),
                "hr_recovery_1m": a_recs.get((SignalType.HR_RECOVERY_1M.value, 12)),
                "sleep_duration": a_recs.get((SignalType.SLEEP_DURATION.value, 7)),
                "sleep_fragmentation": a_recs.get((SignalType.SLEEP_FRAGMENTATION.value, 7)),
                "pvt_mean_rt": a_recs.get((SignalType.PVT_MEAN_RT.value, 9)),
                "pvt_lapses": a_recs.get((SignalType.PVT_LAPSES.value, 9)),
                "spo2_16h": a_recs.get((SignalType.SPO2.value, 16)),
                "activity_index": a_recs.get((SignalType.ACTIVITY_INDEX.value, 16)),
                "symptom_headache": a_recs.get((SignalType.SYMPTOM_HEADACHE.value, 16)),
                "symptom_fatigue": a_recs.get((SignalType.SYMPTOM_FATIGUE.value, 16)),
                "mood_score": a_recs.get((SignalType.MOOD_SCORE.value, 16)),
                "energy_score": a_recs.get((SignalType.ENERGY_SCORE.value, 16)),
            }
        zone_co2_16h = {
            z.zone_id: next(
                (
                    r.value
                    for r in day23_recs
                    if r.zone_id == z.zone_id
                    and r.signal_type == SignalType.CO2_PPM.value
                    and r.hour == 16
                ),
                None,
            )
            for z in HABITAT_ZONES
        }
        lab_7d = [
            float(r.value)
            for r in records
            if r.zone_id == "LAB"
            and r.signal_type == SignalType.CO2_PPM.value
            and 17 <= r.day <= 23
            and r.quality == QualityState.OK.value
            and r.value is not None
        ]
        lab_day19_peak = max(
            (
                float(r.value)
                for r in records
                if r.zone_id == "LAB"
                and r.signal_type == SignalType.CO2_PPM.value
                and r.day == 19
                and r.value is not None
            ),
            default=0.0,
        )
        day23_snapshot["habitat"] = {
            "zone_co2_16h_ppm": zone_co2_16h,
            "lab_7d_avg_ppm": round(sum(lab_7d) / len(lab_7d), 1) if lab_7d else None,
            "lab_day19_peak_ppm": lab_day19_peak,
            "radiation_usv_day": next(
                (
                    r.value
                    for r in day23_recs
                    if r.signal_type == SignalType.RADIATION_USV_DAY.value
                ),
                None,
            ),
            "radiation_cumulative_msv": next(
                (
                    r.value
                    for r in day23_recs
                    if r.signal_type == SignalType.RADIATION_CUMULATIVE_MSV.value
                ),
                None,
            ),
        }

    return {
        "records": records,
        "manifest": manifest,
        "crew": [asdict(c) for c in CREW_ROSTER],
        "zones": [asdict(z) for z in HABITAT_ZONES],
        "zone_occupancy": zone_occupancy,
        "expected_sos": expected_sos,
        "data_faults": data_faults,
        "device_steps": device_steps,
        "metadata": {
            "days": days,
            "seed": seed,
            "null_mission": null_mission,
            "include_device_step": include_device_step,
            "total_records": len(records),
            "quality_counts": quality_counts,
            "illustrative_notice": (
                "All simulated signals and thresholds are illustrative sample data, "
                "not validated clinical limits."
            ),
        },
        "summary": {
            "total_records": len(records),
            "quality_counts": quality_counts,
            "planted_scenarios": [m["event_id"] for m in manifest],
            "day23": day23_snapshot,
        },
    }


def _format_cli_summary(mission: Dict[str, Any]) -> str:
    meta = mission["metadata"]
    summary = mission["summary"]
    lines = [
        "AstroGuard Mission Simulator Summary (illustrative synthetic telemetry)",
        f"  days={meta['days']} seed={meta['seed']} null_mission={meta['null_mission']} "
        f"include_device_step={meta['include_device_step']}",
        f"  total_records={meta['total_records']} quality_counts={meta['quality_counts']}",
        f"  planted_scenarios={summary['planted_scenarios'] or ['NONE (null mission)']}",
    ]
    d23 = summary.get("day23") or {}
    if d23:
        hab = d23.get("habitat", {})
        lines.append(
            "  Day 23 habitat: "
            f"CO2_16h={hab.get('zone_co2_16h_ppm')} "
            f"LAB_7d_avg={hab.get('lab_7d_avg_ppm')} ppm "
            f"LAB_D19_peak={hab.get('lab_day19_peak_ppm')} ppm "
            f"rad={hab.get('radiation_usv_day')} uSv/d ({hab.get('radiation_cumulative_msv')} mSv)"
        )
        for aid in ("ast-01", "ast-02", "ast-03", "ast-04"):
            snap = d23.get(aid, {})
            lines.append(
                f"  Day 23 {aid}: "
                f"HR_16h={snap.get('heart_rate_16h')} RHR={snap.get('resting_hr')} "
                f"HRV={snap.get('hrv_rmssd')} HRrec={snap.get('hr_recovery_1m')} "
                f"Sleep={snap.get('sleep_duration')}h Frag={snap.get('sleep_fragmentation')} "
                f"PVT={snap.get('pvt_mean_rt')}ms (lapses={snap.get('pvt_lapses')}) "
                f"Act={snap.get('activity_index')} Mood/Energy={snap.get('mood_score')}/{snap.get('energy_score')} "
                f"Headache={snap.get('symptom_headache')}"
            )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="AstroGuard seeded astronaut mission telemetry simulator (F-03, F-17)."
    )
    parser.add_argument("--days", type=int, default=30, help="Number of mission days to simulate.")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic RNG seed.")
    parser.add_argument("--null", action="store_true", help="Run zero-anomaly null mission mode.")
    parser.add_argument(
        "--device-step",
        action="store_true",
        help="Include a synthetic firmware/device calibration step offset.",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Print a concise human-readable mission summary.",
    )
    args = parser.parse_args(argv)

    mission = generate_mission(
        days=args.days,
        seed=args.seed,
        null_mission=args.null,
        include_device_step=args.device_step,
    )
    if args.summary:
        print(_format_cli_summary(mission))
    else:
        payload = {
            "metadata": mission["metadata"],
            "manifest": mission["manifest"],
            "summary": mission["summary"],
        }
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
