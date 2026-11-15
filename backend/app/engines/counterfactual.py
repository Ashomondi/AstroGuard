"""Counterfactual What-If Intervention Sandbox Engine (F-15).

Produces transparent, exploratory 1-to-14-day projections comparing the current
trajectory against explicit sleep, workload, recovery-block, and cabin
ventilation adjustments, with growing uncertainty intervals, explicit
assumptions, protocol references, and a non-prediction disclaimer.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence

from app.engines.baseline import clamp


def _estimate_trend_slope(series: Sequence[Dict[str, Any]], max_abs_slope: float = 1.2) -> float:
    """Estimate damped daily linear slope over the last up to 7 points."""
    vals = [float(pt["value"]) for pt in series[-7:] if isinstance(pt, dict) and pt.get("value") is not None]
    if len(vals) < 3:
        return 0.0
    n = len(vals)
    xs = list(range(n))
    mean_x = (n - 1) / 2.0
    mean_y = sum(vals) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, vals))
    den = sum((x - mean_x) ** 2 for x in xs)
    raw = num / den if den > 1e-9 else 0.0
    return clamp(raw * 0.6, -max_abs_slope, max_abs_slope)


def simulate_intervention(
    readiness_data: Optional[Dict[str, Any]],
    sleep_per_night: float = 7.5,
    workload_adjustment: float = -1.0,
    cabin_ventilation_pct: float = 130.0,
    recovery_blocks: int = 2,
    horizon_days: int = 7,
    baseline_co2_ppm: float = 1113.0,
) -> Dict[str, Any]:
    """Run an exploratory counterfactual intervention projection over `horizon_days`."""
    data = readiness_data or {}
    current_day = int(data.get("up_to_day", 23))

    rec_block = data.get("recovery_debt", {})
    cog_block = data.get("cognitive_readiness", {})
    start_debt = float(rec_block.get("score", 45.0))
    start_cog = float(cog_block.get("score", 82.0))

    rec_slope = _estimate_trend_slope(rec_block.get("series", []), max_abs_slope=1.3)
    cog_slope = _estimate_trend_slope(cog_block.get("series", []), max_abs_slope=1.3)

    latest_readings = data.get("latest_readings", {})
    sleep_info = latest_readings.get("sleep_duration", {}) if isinstance(latest_readings, dict) else {}
    current_sleep = float(
        sleep_info.get("last_clean_value")
        or sleep_info.get("value")
        or sleep_info.get("baseline")
        or 6.6
    )

    sleep_h = clamp(float(sleep_per_night), 4.0, 10.0)
    workload = clamp(float(workload_adjustment), -2.0, 2.0)
    vent_pct = clamp(float(cabin_ventilation_pct), 50.0, 200.0)
    rec_blocks = int(clamp(float(recovery_blocks), 0.0, 7.0))
    horizon = int(clamp(float(horizon_days), 1.0, 14.0))
    base_co2 = max(250.0, float(baseline_co2_ppm))

    # Diminishing-returns sleep gain relative to recent sleep
    raw_sleep_delta = sleep_h - current_sleep
    effective_sleep_gain = 1.6 * math.tanh(raw_sleep_delta / 1.4)

    # Total 7-day-normalized intervention effects
    # More sleep, lighter workload (<0), and recovery blocks lower debt and improve cognition
    total_debt_effect = (
        -5.8 * effective_sleep_gain
        + 2.6 * workload
        - 3.8 * (1.0 - math.exp(-rec_blocks / 2.2))
    )
    total_cog_effect = (
        6.2 * effective_sleep_gain
        - 1.8 * workload
        + 1.6 * (1.0 - math.exp(-rec_blocks / 2.5))
    )

    # Ventilation changes habitat CO2 exposure only (not physiology directly)
    ambient_floor = 250.0
    projected_co2 = max(
        ambient_floor,
        ambient_floor + (base_co2 - ambient_floor) * ((100.0 / vent_pct) ** 1.25),
    )
    co2_delta = projected_co2 - base_co2

    base_conf = float(data.get("confidence", 0.85))
    exploratory_conf = round(clamp(base_conf * 0.48, 0.22, 0.58), 2)

    recovery_series: List[Dict[str, Any]] = []
    cognitive_series: List[Dict[str, Any]] = []
    base_debt_val = start_debt
    base_cog_val = start_cog

    for step in range(1, horizon + 1):
        d = current_day + step
        damp = 0.84 ** (step - 1)
        base_debt_val = clamp(base_debt_val + rec_slope * damp, 0.0, 100.0)
        base_cog_val = clamp(base_cog_val + cog_slope * damp, 0.0, 100.0)

        # Cumulative intervention effect ramps smoothly over selected horizon
        ramp = 1.0 - math.exp(-step / max(2.2, horizon * 0.45))
        norm_ramp = ramp / (1.0 - math.exp(-horizon / max(2.2, horizon * 0.45)))
        scale_h = 0.70 + 0.30 * (horizon / 7.0)

        int_debt_val = clamp(base_debt_val + total_debt_effect * scale_h * norm_ramp, 0.0, 100.0)
        int_cog_val = clamp(base_cog_val + total_cog_effect * scale_h * norm_ramp, 0.0, 100.0)

        rec_unc = round(5.2 * math.sqrt(step), 1)
        cog_unc = round(4.5 * math.sqrt(step), 1)

        recovery_series.append(
            {
                "day": d,
                "baseline": round(base_debt_val, 1),
                "intervention": round(int_debt_val, 1),
                "uncertainty": rec_unc,
                "low": round(clamp(int_debt_val - rec_unc, 0.0, 100.0), 1),
                "high": round(clamp(int_debt_val + rec_unc, 0.0, 100.0), 1),
            }
        )
        cognitive_series.append(
            {
                "day": d,
                "baseline": round(base_cog_val, 1),
                "intervention": round(int_cog_val, 1),
                "uncertainty": cog_unc,
                "low": round(clamp(int_cog_val - cog_unc, 0.0, 100.0), 1),
                "high": round(clamp(int_cog_val + cog_unc, 0.0, 100.0), 1),
            }
        )

    final_debt_delta = round(recovery_series[-1]["intervention"] - recovery_series[-1]["baseline"], 1)
    final_cog_delta = round(cognitive_series[-1]["intervention"] - cognitive_series[-1]["baseline"], 1)
    final_co2_delta = round(co2_delta, 0)

    protocols: List[str] = []
    if rec_blocks > 0 or workload < 0:
        protocols.append("PROT-REC-01")
    if sleep_h >= 7.0:
        protocols.append("PROT-SLP-01")
    if vent_pct > 100.0:
        protocols.extend(["PROT-ENV-01", "PROT-ENV-02"])
    if not protocols:
        protocols = ["PROT-REC-01", "PROT-SLP-01"]

    assumptions = [
        "Projection extrapolates your last 7 days; it does not model new illness or medication.",
        "Sleep effect is spread over the selected days with diminishing returns.",
        "Workload is an abstract -2...+2 adjustment, not a specific schedule.",
        "Ventilation changes habitat CO2 exposure, not an individual's physiology directly.",
        "Recovery blocks reduce planned physical load; they do not replace clinical review.",
    ]

    debt_dir = "lower" if final_debt_delta <= 0 else "higher"
    summary = (
        f"With {sleep_h:.1f} h sleep, workload {workload:+.1f}, {rec_blocks} recovery block(s)/week "
        f"and ventilation at {vent_pct:.0f}%, projected recovery debt is {abs(final_debt_delta):.1f} points "
        f"{debt_dir} by day {horizon}, and cognitive readiness is {final_cog_delta:+.1f} points. "
        "Confidence is exploratory."
    )

    return {
        "exploratory": True,
        "confidence": exploratory_conf,
        "horizon_days": horizon,
        "inputs": {
            "sleep_per_night": round(sleep_h, 2),
            "workload_adjustment": round(workload, 2),
            "cabin_ventilation_pct": round(vent_pct, 1),
            "recovery_blocks": rec_blocks,
            "horizon_days": horizon,
            "baseline_co2_ppm": round(base_co2, 1),
        },
        "deltas": {
            "recovery_debt": final_debt_delta,
            "cognitive_readiness": final_cog_delta,
            "co2_exposure": int(final_co2_delta),
        },
        "recovery_series": recovery_series,
        "cognitive_series": cognitive_series,
        "uncertainty": {
            "recovery_debt_pts": recovery_series[-1]["uncertainty"],
            "cognitive_readiness_pts": cognitive_series[-1]["uncertainty"],
        },
        "assumptions": assumptions,
        "protocol_refs": protocols,
        "summary": summary,
        "disclaimer": "Exploratory what-if projection. Not a diagnosis, treatment plan, or guarantee.",
    }
