"""Crew-Environment Correlation and Confounder Adjustment Engine (F-13, F-18).

Summarizes habitat zones (N1, LAB, CQ, AL), preserves environmental sensor
gaps explicitly, joins hourly/daily crew zone occupancy with zone CO2 exposure,
and computes lagged Pearson correlations (lag 0-1 day) with max-lag permutation
p-values and Benjamini-Hochberg FDR control across anonymized Crew A..D labels.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.engines.baseline import clamp, coerce_records, is_clean_record
from app.schema import CREW_BY_ID, CREW_ROSTER, HABITAT_ZONES, MeasurementRecord, QualityState, SignalType

HABITAT_SIGNALS = {
    SignalType.CO2_PPM.value,
    SignalType.CABIN_TEMP_C.value,
    SignalType.CABIN_HUMIDITY_PCT.value,
    SignalType.CABIN_NOISE_DB.value,
}


def pearson_correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Compute sample Pearson correlation coefficient safely in pure Python."""
    n = len(xs)
    if n < 3 or n != len(ys):
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = 0.0
    den_x = 0.0
    den_y = 0.0
    for x, y in zip(xs, ys):
        dx = x - mean_x
        dy = y - mean_y
        num += dx * dy
        den_x += dx * dx
        den_y += dy * dy
    if den_x <= 1e-12 or den_y <= 1e-12:
        return 0.0
    return clamp(num / math.sqrt(den_x * den_y), -1.0, 1.0)


def benjamini_hochberg(p_values: Sequence[float]) -> List[float]:
    """Compute Benjamini-Hochberg FDR-adjusted q-values preserving input order."""
    m = len(p_values)
    if m == 0:
        return []
    indexed = sorted(enumerate(p_values), key=lambda pair: pair[1])
    raw_q = [0.0] * m
    min_running = 1.0
    for rank_rev in range(m, 0, -1):
        orig_idx, p_val = indexed[rank_rev - 1]
        cand = (p_val * m) / rank_rev
        min_running = min(min_running, cand)
        raw_q[orig_idx] = clamp(min_running, 0.0, 1.0)
    return raw_q


def resolve_zone_occupancy(
    records: Sequence[MeasurementRecord],
    zone_occupancy: Optional[Any] = None,
) -> Dict[Tuple[str, int, int], str]:
    """Build (astronaut_id, day, hour) -> zone_id lookup from explicit or record data."""
    occ: Dict[Tuple[str, int, int], str] = {}
    for rec in records:
        if rec.astronaut_id in CREW_BY_ID and rec.zone_id:
            occ[(rec.astronaut_id, rec.day, rec.hour)] = rec.zone_id

    if isinstance(zone_occupancy, dict):
        for key, val in zone_occupancy.items():
            if isinstance(key, tuple) and len(key) == 3:
                occ[(str(key[0]), int(key[1]), int(key[2]))] = str(val)
            elif isinstance(key, str) and isinstance(val, dict):
                for day_k, zone_v in val.items():
                    for h in range(24):
                        occ[(key, int(day_k), h)] = str(zone_v)
    elif isinstance(zone_occupancy, list):
        for item in zone_occupancy:
            if not isinstance(item, dict):
                continue
            aid = item.get("astronaut_id")
            day = item.get("day")
            zone = item.get("zone_id")
            if aid and day is not None and zone:
                if item.get("hour") is not None:
                    occ[(str(aid), int(day), int(item["hour"]))] = str(zone)
                else:
                    for h in range(24):
                        occ[(str(aid), int(day), h)] = str(zone)
    return occ


def extract_crew_daily_env_and_symptoms(
    records: Sequence[MeasurementRecord],
    zone_occupancy: Optional[Any],
    up_to_day: int,
) -> Tuple[
    Dict[str, Dict[int, Optional[float]]],
    Dict[str, Dict[int, Optional[float]]],
    Dict[str, Dict[int, str]],
    Dict[Tuple[str, int, int], float],
]:
    """Compute per-astronaut daily CO2 exposure, symptom index, primary zone, and clean zone hourly CO2."""
    occ = resolve_zone_occupancy(records, zone_occupancy)

    # Hourly clean CO2 per (zone_id, day, hour) and daily fallback per (zone_id, day)
    zone_hourly_co2: Dict[Tuple[str, int, int], List[float]] = {}
    zone_daily_co2: Dict[Tuple[str, int], List[float]] = {}
    for rec in records:
        if rec.signal_type == SignalType.CO2_PPM.value and is_clean_record(rec) and rec.value is not None:
            zone_hourly_co2.setdefault((rec.zone_id, rec.day, rec.hour), []).append(float(rec.value))
            zone_daily_co2.setdefault((rec.zone_id, rec.day), []).append(float(rec.value))

    hourly_co2_mean: Dict[Tuple[str, int, int], float] = {
        k: sum(v) / len(v) for k, v in zone_hourly_co2.items()
    }
    daily_co2_mean: Dict[Tuple[str, int], float] = {
        k: sum(v) / len(v) for k, v in zone_daily_co2.items()
    }

    # Per-astronaut daily clean symptom signals
    headache: Dict[Tuple[str, int], List[float]] = {}
    fatigue: Dict[Tuple[str, int], List[float]] = {}
    energy: Dict[Tuple[str, int], List[float]] = {}
    direct_co2: Dict[Tuple[str, int], List[float]] = {}
    for rec in records:
        if rec.astronaut_id not in CREW_BY_ID or not is_clean_record(rec) or rec.value is None:
            continue
        key = (rec.astronaut_id, rec.day)
        if rec.signal_type == SignalType.SYMPTOM_HEADACHE.value:
            headache.setdefault(key, []).append(float(rec.value))
        elif rec.signal_type == SignalType.SYMPTOM_FATIGUE.value:
            fatigue.setdefault(key, []).append(float(rec.value))
        elif rec.signal_type == SignalType.ENERGY_SCORE.value:
            energy.setdefault(key, []).append(float(rec.value))
        elif rec.signal_type == SignalType.CO2_PPM.value:
            direct_co2.setdefault(key, []).append(float(rec.value))

    daily_exposure: Dict[str, Dict[int, Optional[float]]] = {}
    daily_symptoms: Dict[str, Dict[int, Optional[float]]] = {}
    daily_primary_zone: Dict[str, Dict[int, str]] = {}

    for crew in CREW_ROSTER:
        aid = crew.astronaut_id
        daily_exposure[aid] = {}
        daily_symptoms[aid] = {}
        daily_primary_zone[aid] = {}

        for d in range(1, up_to_day + 1):
            # Wake-hour exposure (hours 7..21) preferred, falling back to any hour on day d
            wake_vals: List[float] = []
            all_day_vals: List[float] = []
            zone_counts: Dict[str, int] = {}
            for h in range(24):
                z = occ.get((aid, d, h))
                if z is None and 7 <= h <= 21:
                    z = crew.default_zone
                if z is not None:
                    if 7 <= h <= 21:
                        zone_counts[z] = zone_counts.get(z, 0) + 1
                    co2 = hourly_co2_mean.get((z, d, h))
                    if co2 is not None:
                        all_day_vals.append(co2)
                        if 7 <= h <= 21:
                            wake_vals.append(co2)

            if zone_counts:
                daily_primary_zone[aid][d] = max(zone_counts.items(), key=lambda item: item[1])[0]
            else:
                daily_primary_zone[aid][d] = crew.default_zone

            if wake_vals:
                daily_exposure[aid][d] = sum(wake_vals) / len(wake_vals)
            elif all_day_vals:
                daily_exposure[aid][d] = sum(all_day_vals) / len(all_day_vals)
            elif (aid, d) in direct_co2:
                vals = direct_co2[(aid, d)]
                daily_exposure[aid][d] = sum(vals) / len(vals)
            elif (daily_primary_zone[aid][d], d) in daily_co2_mean:
                daily_exposure[aid][d] = daily_co2_mean[(daily_primary_zone[aid][d], d)]
            else:
                daily_exposure[aid][d] = None

            # Symptom composite index (0-10)
            h_vals = headache.get((aid, d))
            f_vals = fatigue.get((aid, d))
            e_vals = energy.get((aid, d))
            if h_vals or f_vals:
                h_mean = sum(h_vals) / len(h_vals) if h_vals else 0.0
                f_mean = sum(f_vals) / len(f_vals) if f_vals else 0.0
                e_mean = sum(e_vals) / len(e_vals) if e_vals else 3.8
                idx = h_mean * 1.5 + f_mean * 0.8 + max(0.0, 4.0 - e_mean) * 0.5
                daily_symptoms[aid][d] = clamp(idx, 0.0, 10.0)
            else:
                daily_symptoms[aid][d] = None

    return daily_exposure, daily_symptoms, daily_primary_zone, hourly_co2_mean


def _collect_environmental_gaps(
    records: Sequence[MeasurementRecord],
    up_to_day: int,
) -> List[Dict[str, Any]]:
    """Collect explicit non-ok habitat sensor gaps without imputing."""
    zone_names = {z.zone_id: z.name for z in HABITAT_ZONES}
    env_faults = [
        r
        for r in records
        if r.signal_type in HABITAT_SIGNALS and r.day <= up_to_day and not is_clean_record(r)
    ]
    if not env_faults:
        return []

    env_faults.sort(key=lambda r: (r.zone_id, r.signal_type, r.quality, r.day, r.hour))
    gaps: List[Dict[str, Any]] = []
    cur: Optional[Dict[str, Any]] = None

    for rec in env_faults:
        abs_h = rec.day * 24 + rec.hour
        if (
            cur is not None
            and cur["zone_id"] == rec.zone_id
            and cur["signal_type"] == rec.signal_type
            and cur["quality"] == rec.quality
            and abs_h <= cur["_last_abs_h"] + 1
        ):
            cur["end_day"] = rec.day
            cur["end_hour"] = rec.hour
            cur["hours"] += 1
            cur["_last_abs_h"] = abs_h
        else:
            if cur is not None:
                cur.pop("_last_abs_h", None)
                gaps.append(cur)
            zname = zone_names.get(rec.zone_id, rec.zone_id)
            cur = {
                "zone_id": rec.zone_id,
                "zone_name": zname,
                "signal_type": rec.signal_type,
                "quality": rec.quality,
                "day": rec.day,
                "end_day": rec.day,
                "start_hour": rec.hour,
                "end_hour": rec.hour,
                "hours": 1,
                "_last_abs_h": abs_h,
                "message": (
                    f"{zname} · Day {rec.day}, {rec.hour:02d}:00 - {rec.signal_type} {rec.quality}. "
                    "Missing values are not imputed."
                ),
            }
    if cur is not None:
        cur.pop("_last_abs_h", None)
        gaps.append(cur)

    for g in gaps:
        if g["hours"] > 1:
            g["message"] = (
                f"{g['zone_name']} · Day {g['day']}, {g['start_hour']:02d}:00-{g['end_hour'] + 1:02d}:00 "
                f"({g['hours']}h) - {g['signal_type']} {g['quality']}. Missing values are not imputed."
            )
    return gaps


def _summarize_zones(
    records: Sequence[MeasurementRecord],
    occ: Dict[Tuple[str, int, int], str],
    env_gaps: Sequence[Dict[str, Any]],
    up_to_day: int,
) -> Dict[str, Dict[str, Any]]:
    """Summarize N1, LAB, CQ, AL habitat status up to `up_to_day`."""
    zones_out: Dict[str, Dict[str, Any]] = {}
    recent_start = max(1, up_to_day - 6)
    latest_hour_by_zone: Dict[str, int] = {}

    for zone in HABITAT_ZONES:
        zid = zone.zone_id
        co2_recs = [
            r for r in records if r.zone_id == zid and r.signal_type == SignalType.CO2_PPM.value
        ]
        clean_co2 = [r for r in co2_recs if is_clean_record(r) and r.value is not None]
        latest_rec = co2_recs[-1] if co2_recs else None
        latest_hour = latest_rec.hour if latest_rec else 16
        latest_hour_by_zone[zid] = latest_hour

        current_is_gap = latest_rec is not None and not is_clean_record(latest_rec)
        current_co2 = (
            None
            if (latest_rec is None or current_is_gap)
            else round(float(latest_rec.value), 1)
        )
        last_clean_co2 = round(float(clean_co2[-1].value), 1) if clean_co2 else None

        win7 = [float(r.value) for r in clean_co2 if recent_start <= r.day <= up_to_day and r.value is not None]
        avg_7d = round(sum(win7) / len(win7), 1) if win7 else None

        base_co2 = [float(r.value) for r in clean_co2 if r.day <= min(10, up_to_day) and r.value is not None]
        ref_ppm = sum(base_co2) / len(base_co2) if base_co2 else zone.nominal_co2_ppm
        trend_pct = (
            round(((avg_7d - ref_ppm) / max(1.0, ref_ppm)) * 100.0, 1)
            if avg_7d is not None
            else 0.0
        )

        # Latest non-CO2 env metrics
        other_vals: Dict[str, Optional[float]] = {}
        for sig in (
            SignalType.CABIN_TEMP_C.value,
            SignalType.CABIN_HUMIDITY_PCT.value,
            SignalType.CABIN_NOISE_DB.value,
        ):
            s_clean = [
                float(r.value)
                for r in records
                if r.zone_id == zid and r.signal_type == sig and is_clean_record(r) and r.value is not None
            ]
            other_vals[sig] = round(s_clean[-1], 1) if s_clean else None

        zone_gaps = [g for g in env_gaps if g["zone_id"] == zid and g["day"] >= recent_start]
        # Present crew count on latest day/hour
        present = sum(
            1
            for crew in CREW_ROSTER
            if occ.get((crew.astronaut_id, up_to_day, latest_hour), crew.default_zone) == zid
        )

        effective_co2 = current_co2 if current_co2 is not None else (last_clean_co2 or zone.nominal_co2_ppm)
        if current_is_gap:
            status = "Data gap"
        elif effective_co2 >= 5000.0 or (avg_7d is not None and avg_7d >= 1500.0) or effective_co2 > 1000.0:
            status = "Above normal"
        else:
            status = "Within normal band"

        zones_out[zid] = {
            "zone_id": zid,
            "name": zone.name,
            "nominal_co2_ppm": zone.nominal_co2_ppm,
            "co2_ppm": current_co2,
            "last_clean_co2_ppm": last_clean_co2,
            "co2_7d_avg_ppm": avg_7d,
            "trend_7d_pct": trend_pct,
            "present_crew_count": present,
            "status": status,
            "sensor_status": "gap" if zone_gaps or current_is_gap else "clean",
            "temp_c": other_vals[SignalType.CABIN_TEMP_C.value],
            "humidity_pct": other_vals[SignalType.CABIN_HUMIDITY_PCT.value],
            "noise_db": other_vals[SignalType.CABIN_NOISE_DB.value],
            "quality": latest_rec.quality if latest_rec else QualityState.MISSING.value,
        }
    return zones_out


def _lagged_pair_vectors(
    exp_map: Dict[int, Optional[float]],
    sym_map: Dict[int, Optional[float]],
    up_to_day: int,
    lag: int,
) -> Tuple[List[float], List[float]]:
    """Build aligned (exposure_{d-lag}, symptom_d) pairs skipping any missing days."""
    xs: List[float] = []
    ys: List[float] = []
    for d in range(1 + lag, up_to_day + 1):
        x_val = exp_map.get(d - lag)
        y_val = sym_map.get(d)
        if x_val is not None and y_val is not None:
            xs.append(x_val)
            ys.append(y_val)
    return xs, ys


def analyze_crew_environment(
    records: Iterable[MeasurementRecord | Dict[str, Any]],
    zone_occupancy: Optional[Any] = None,
    up_to_day: int = 23,
    n_permutations: int = 80,
    seed: int = 42,
) -> Dict[str, Any]:
    """Summarize habitat zones and detect anonymized lagged CO2-symptom correlations."""
    parsed = coerce_records(records, up_to_day=up_to_day)
    occ = resolve_zone_occupancy(parsed, zone_occupancy)
    env_gaps = _collect_environmental_gaps(parsed, up_to_day)
    zones = _summarize_zones(parsed, occ, env_gaps, up_to_day)
    daily_exp, daily_sym, daily_zone, _ = extract_crew_daily_env_and_symptoms(
        parsed, zone_occupancy, up_to_day
    )

    # Aggregate daily CO2 exposure and symptom index across crew (Day 1..up_to_day)
    agg_co2_series: List[Dict[str, Any]] = []
    agg_symptom_series: List[Dict[str, Any]] = []
    for d in range(1, up_to_day + 1):
        exp_vals = [daily_exp[c.astronaut_id][d] for c in CREW_ROSTER if daily_exp[c.astronaut_id].get(d) is not None]
        sym_vals = [daily_sym[c.astronaut_id][d] for c in CREW_ROSTER if daily_sym[c.astronaut_id].get(d) is not None]
        agg_co2_series.append(
            {
                "day": d,
                "value": round(sum(exp_vals) / len(exp_vals), 1) if exp_vals else None,
            }
        )
        agg_symptom_series.append(
            {
                "day": d,
                "value": round(sum(sym_vals) / len(sym_vals), 2) if sym_vals else None,
            }
        )

    # Max-lag (lag 0 or 1 day) permutation test per anonymized crew member
    raw_results: List[Dict[str, Any]] = []
    p_values: List[float] = []
    recent_gaps = [g for g in env_gaps if g["day"] >= max(1, up_to_day - 7)]
    gap_penalty = min(0.12, 0.03 * sum(g["hours"] for g in recent_gaps))

    for crew_idx, crew in enumerate(CREW_ROSTER):
        aid = crew.astronaut_id
        exp_map = daily_exp[aid]
        sym_map = daily_sym[aid]

        xs0, ys0 = _lagged_pair_vectors(exp_map, sym_map, up_to_day, lag=0)
        xs1, ys1 = _lagged_pair_vectors(exp_map, sym_map, up_to_day, lag=1)

        r0 = pearson_correlation(xs0, ys0)
        r1 = pearson_correlation(xs1, ys1)
        if r0 >= r1:
            best_lag = 0
            best_r = r0
            n_pairs = len(xs0)
        else:
            best_lag = 1
            best_r = r1
            n_pairs = len(xs1)

        # Dominant occupied zone in recent window
        zone_hist: Dict[str, int] = {}
        for d in range(max(1, up_to_day - 6), up_to_day + 1):
            z = daily_zone[aid].get(d, crew.default_zone)
            zone_hist[z] = zone_hist.get(z, 0) + 1
        primary_zone = max(zone_hist.items(), key=lambda item: item[1])[0]

        if n_pairs < 6 or best_r <= 0.15:
            p_val = 1.0
        else:
            rng = random.Random(seed + crew_idx * 101)
            valid_days = [d for d in range(1, up_to_day + 1) if sym_map.get(d) is not None]
            sym_vals = [float(sym_map[d]) for d in valid_days]
            exceed = 0
            for _ in range(n_permutations):
                shuffled = list(sym_vals)
                rng.shuffle(shuffled)
                perm_sym = {d: val for d, val in zip(valid_days, shuffled)}
                px0, py0 = _lagged_pair_vectors(exp_map, perm_sym, up_to_day, lag=0)
                px1, py1 = _lagged_pair_vectors(exp_map, perm_sym, up_to_day, lag=1)
                r_perm = max(pearson_correlation(px0, py0), pearson_correlation(px1, py1))
                if r_perm >= best_r:
                    exceed += 1
            p_val = (1.0 + exceed) / (1.0 + n_permutations)

        p_values.append(p_val)
        raw_results.append(
            {
                "astronaut_id": aid,
                "crew_label": crew.anonymous_label,
                "zone_id": primary_zone,
                "r": round(best_r, 3),
                "lag_days": best_lag,
                "p_value": round(p_val, 4),
                "n_pairs": n_pairs,
            }
        )

    q_values = benjamini_hochberg(p_values)
    crew_correlations: List[Dict[str, Any]] = []
    confounder_flags: List[Dict[str, Any]] = []

    for item, q_val in zip(raw_results, q_values):
        linked = q_val <= 0.05 and item["r"] >= 0.72
        base_conf = 0.55 + 0.35 * max(0.0, item["r"]) + (0.08 if linked else 0.0)
        conf = round(clamp(base_conf - gap_penalty, 0.25, 0.96), 2)
        lag_phrase = "same day" if item["lag_days"] == 0 else "1-day lag"

        # Strictly anonymized for Systems Engineer view
        crew_correlations.append(
            {
                "crew_label": item["crew_label"],
                "zone_id": item["zone_id"],
                "r": item["r"],
                "lag_days": item["lag_days"],
                "p_value": item["p_value"],
                "fdr_q_value": round(q_val, 4),
                "confidence": conf,
                "linked": linked,
                "status": "linked" if linked else "no clear link",
                "summary": (
                    f"Daily CO2 exposure and symptom score co-move (r={item['r']:+.2f}, {lag_phrase})."
                ),
            }
        )

        if linked:
            z_name = zones.get(item["zone_id"], {}).get("name", item["zone_id"])
            confounder_flags.append(
                {
                    "crew_label": item["crew_label"],
                    "astronaut_id": item["astronaut_id"],
                    "zone_id": item["zone_id"],
                    "zone_name": z_name,
                    "signal": SignalType.CO2_PPM.value,
                    "lag_days": item["lag_days"],
                    "r": item["r"],
                    "p_value": item["p_value"],
                    "fdr_q_value": round(q_val, 4),
                    "confidence": conf,
                    "message": (
                        f"Symptoms for {item['crew_label']} co-move with {z_name} CO2 "
                        f"(r={item['r']:.2f}, lag {item['lag_days']}d). Treat as a potential "
                        "environmental confounder until cabin air is verified; individual illness is not excluded."
                    ),
                }
            )

    # Group linked crew by zone to construct shared_exposure_alert
    linked_by_zone: Dict[str, List[Dict[str, Any]]] = {}
    for cf in confounder_flags:
        linked_by_zone.setdefault(cf["zone_id"], []).append(cf)

    shared_zone_id: Optional[str] = None
    shared_group: List[Dict[str, Any]] = []
    for zid, grp in linked_by_zone.items():
        if len(grp) > len(shared_group):
            shared_zone_id = zid
            shared_group = grp

    shared_active = len(shared_group) >= 2
    if shared_active and shared_zone_id is not None:
        z_name = zones.get(shared_zone_id, {}).get("name", shared_zone_id)
        avg_conf = round(sum(g["confidence"] for g in shared_group) / len(shared_group), 2)
        lags = sorted({int(g["lag_days"]) for g in shared_group})
        lag_text = f"{lags[0]} day" if len(lags) == 1 else f"{lags[0]}-{lags[-1]} day"
        shared_exposure_alert: Dict[str, Any] = {
            "active": True,
            "zone_id": shared_zone_id,
            "zone_name": z_name,
            "affected_crew_count": len(shared_group),
            "affected_anonymous_labels": [g["crew_label"] for g in shared_group],
            "lag_range": "0-1 day",
            "lag_observed": lag_text,
            "confidence": avg_conf,
            "headline": "Shared habitat exposure signal",
            "summary": (
                f"{len(shared_group)} crew members show symptom scores co-moving with {z_name} CO2 "
                f"(lag 0-1 day). Treat this as a shared environmental exposure until the air is verified; "
                "individual illness is not excluded."
            ),
            "prevent_misattribution": (
                "Do not label a crew member as sick when the same symptom pattern follows a shared zone "
                "exposure. Individual illness is not excluded."
            ),
            "protocol_refs": ["PROT-ENV-01", "PROT-ENV-02", "PROT-MED-01"],
        }
    else:
        shared_exposure_alert = {
            "active": False,
            "zone_id": None,
            "zone_name": None,
            "affected_crew_count": 0,
            "affected_anonymous_labels": [],
            "lag_range": "0-1 day",
            "confidence": 0.0,
            "headline": "No shared habitat exposure cluster detected",
            "summary": "No statistically significant multi-crew CO2-symptom cluster passed FDR control.",
            "prevent_misattribution": "Environmental and personal baselines are monitored independently.",
            "protocol_refs": [],
        }

    return {
        "up_to_day": up_to_day,
        "zones": zones,
        "crew_correlations": crew_correlations,
        "shared_exposure_alert": shared_exposure_alert,
        "aggregate_co2_series": agg_co2_series,
        "aggregate_symptom_series": agg_symptom_series,
        "environmental_gaps": env_gaps,
        "confounder_flags": confounder_flags,
        "method_guardrails": {
            "method": "Lagged Pearson correlation (0-1 day) with max-lag permutation p-values and Benjamini-Hochberg FDR control.",
            "disclaimer": "Association, not causation. Shared exposure is a hypothesis to verify with cabin-air measurements; it does not rule out individual illness.",
            "daily_points": up_to_day,
        },
    }
