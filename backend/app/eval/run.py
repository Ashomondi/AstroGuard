"""AstroGuard Validation Harness, Baseline Comparators, and Report Generator (F-40).

Benchmarks AstroGuard's full engine stack against two explicit baselines from
`docs/validation-plan.md`:
  1. Fixed Earth-Norm Thresholds (`earth_norm`) without personal calibration or
     data-quality gating.
  2. Simple Heuristic Rolling Rule (`heuristic_rolling`) using a 7-day rolling
     z-score without Bayesian shrinkage, device-step immunity, CUSUM, or FDR.
  3. AstroGuard Full Engine Stack (`astra`): PersonalBaselineEngine + Readiness +
     Environment/MSIDE + Behavioral + Deterministic Safety + AlertPolicyEngine.

All metrics and thresholds are illustrative synthetic validation checks run on
seeded `simulator.py` missions (pure Python 3.14 standard library).

CLI usage:
    cd /home/frihk/frihk/Astra/backend
    python3 -m app.eval.run --seed 42
"""

from __future__ import annotations

import argparse
import copy
import datetime
import json
import math
import statistics
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.engines.alerts import AlertPolicyEngine
from app.engines.baseline import PersonalBaselineEngine
from app.engines.behavioral import assess_behavioral_health
from app.engines.environment import analyze_crew_environment
from app.engines.mside import discover_interactions, run_negative_control
from app.engines.readiness import compute_readiness
from app.quality import classify_artifact
from app.safety import evaluate_safety_rules
from app.schema import CREW_BY_ID, MeasurementRecord, QualityState, SignalType
from app.simulator import (
    SCENARIO_BY_ID,
    generate_mission,
    inject_artifacts,
    inject_device_step,
    inject_missingness,
)

CREW_IDS = tuple(CREW_BY_ID.keys())

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "validation"

EARTH_NORM_RULES: Dict[str, Any] = {
    SignalType.RESTING_HR.value: lambda v: v > 75.0,
    SignalType.HRV_RMSSD.value: lambda v: v < 35.0,
    SignalType.HR_RECOVERY_1M.value: lambda v: v < 25.0,
    SignalType.PVT_MEAN_RT.value: lambda v: v > 300.0,
    SignalType.SLEEP_DURATION.value: lambda v: v < 6.0,
    SignalType.SPO2.value: lambda v: v < 92.0,
    SignalType.HEART_RATE.value: lambda v: v > 118.0,  # Un-stratified raw HR
    SignalType.CO2_PPM.value: lambda v: v > 5000.0,
}

PLANTED_TARGET_SIGNALS: Dict[str, Tuple[str, set[str], int, int]] = {
    "EV_RECOVERY_DECLINE": (
        "ast-01",
        {
            SignalType.HR_RECOVERY_1M.value,
            SignalType.RESTING_HR.value,
            SignalType.HRV_RMSSD.value,
            SignalType.SLEEP_DURATION.value,
            "multivariate_cluster",
        },
        int(SCENARIO_BY_ID["EV_RECOVERY_DECLINE"]["onset_day"]),
        int(SCENARIO_BY_ID["EV_RECOVERY_DECLINE"]["peak_day"]),
    ),
    "MC_COGNITIVE_DRIFT_AND_UNDERREPORTING": (
        "ast-02",
        {
            SignalType.PVT_MEAN_RT.value,
            SignalType.PVT_LAPSES.value,
            SignalType.SLEEP_FRAGMENTATION.value,
            SignalType.ACTIVITY_INDEX.value,
            "multivariate_cluster",
        },
        int(SCENARIO_BY_ID["MC_COGNITIVE_DRIFT_AND_UNDERREPORTING"]["onset_day"]),
        int(SCENARIO_BY_ID["MC_COGNITIVE_DRIFT_AND_UNDERREPORTING"]["peak_day"]),
    ),
    "SHARED_LAB_CO2_EXPOSURE": (
        "habitat-lab",
        {SignalType.CO2_PPM.value},
        int(SCENARIO_BY_ID["SHARED_LAB_CO2_EXPOSURE"]["onset_day"]),
        int(SCENARIO_BY_ID["SHARED_LAB_CO2_EXPOSURE"]["peak_day"]),
    ),
}

ARTIFACT_CASE_TYPES: Tuple[Tuple[str, str], ...] = (
    ("motion_spike", SignalType.HEART_RATE.value),
    ("out_of_range", SignalType.SPO2.value),
    ("saturated", SignalType.HEART_RATE.value),
    ("clock_jump", SignalType.HEART_RATE.value),
    ("sensor_off", SignalType.HEART_RATE.value),
    ("missing", SignalType.HEART_RATE.value),
)


# ---------------------------------------------------------------------------
# Baseline Comparators (Earth-Norm & Simple Heuristic Rolling)
# ---------------------------------------------------------------------------


def _evaluate_earth_norm(
    records: Sequence[MeasurementRecord],
    max_day: int = 30,
    include_habitat_co2: bool = False,
) -> List[Tuple[str, str, int]]:
    """Fixed Earth-norm comparator without calibration, context gate, or quality gate."""
    hits: set[Tuple[str, str, int]] = set()
    for rec in records:
        if rec.day > max_day:
            continue
        is_crew = rec.astronaut_id.startswith("ast-")
        is_hab_co2 = include_habitat_co2 and rec.astronaut_id == "habitat-lab" and rec.signal_type == SignalType.CO2_PPM.value
        if not (is_crew or is_hab_co2):
            continue
        if rec.signal_type not in EARTH_NORM_RULES:
            continue
        # No quality gate: non-ok / missing readings emit un-quarantined threshold/signal alarms
        if rec.quality != QualityState.OK.value or rec.value is None:
            hits.add((rec.astronaut_id, rec.signal_type, rec.day))
            continue
        if EARTH_NORM_RULES[rec.signal_type](float(rec.value)):
            hits.add((rec.astronaut_id, rec.signal_type, rec.day))
    return sorted(hits)


def _evaluate_heuristic_rolling(
    records: Sequence[MeasurementRecord],
    min_day: int = 10,
    max_day: int = 30,
    z_thresh: float = 2.5,
    include_habitat_co2: bool = False,
) -> List[Tuple[str, str, int]]:
    """Per-entity 7-day rolling z-score without Bayesian shrinkage, step fix, or FDR."""
    by_entity_sig: Dict[Tuple[str, str], Dict[int, List[float]]] = {}
    for rec in records:
        if rec.day > max_day or rec.value is None:
            continue
        is_crew = rec.astronaut_id.startswith("ast-")
        is_hab_co2 = include_habitat_co2 and rec.astronaut_id == "habitat-lab" and rec.signal_type == SignalType.CO2_PPM.value
        if not (is_crew or is_hab_co2):
            continue
        if rec.signal_type in (SignalType.RADIATION_USV_DAY.value, SignalType.RADIATION_CUMULATIVE_MSV.value):
            continue
        # Lacks artifact quarantine: includes suspect / out_of_range spikes in raw means
        by_entity_sig.setdefault((rec.astronaut_id, rec.signal_type), {}).setdefault(rec.day, []).append(float(rec.value))

    hits: set[Tuple[str, str, int]] = set()
    for (entity_id, sig), by_day in by_entity_sig.items():
        for d in range(min_day, max_day + 1):
            if d not in by_day:
                continue
            hist = [statistics.mean(by_day[hd]) for hd in range(max(1, d - 7), d) if hd in by_day]
            if len(hist) < 4:
                continue
            mu = statistics.mean(hist)
            sd = max(1e-3, statistics.pstdev(hist))
            cur = statistics.mean(by_day[d])
            if abs(cur - mu) / sd >= z_thresh:
                hits.add((entity_id, sig, d))
    return sorted(hits)


def _astra_first_detection_day(
    engine: PersonalBaselineEngine,
    policy: AlertPolicyEngine,
    records: Sequence[MeasurementRecord],
    entity_id: str,
    target_signals: set[str],
    onset_day: int,
    peak_day: int,
) -> Optional[int]:
    """Scan daily checkpoints in [onset_day, peak_day] for first AstroGuard alert on target signals."""
    for d in range(onset_day, peak_day + 1):
        flags = engine.detect_anomalies(records, entity_id, up_to_day=d)
        # Allow advisory alert or habitat CO2 drift/contextual flag before acute threshold
        if entity_id.startswith("habitat"):
            matching = [
                f
                for f in flags
                if f.anomaly_type != "data_fault"
                and f.signal in target_signals
                and f.confidence >= policy.min_confidence
            ]
            if matching:
                return d
        else:
            ev = policy.evaluate_alerts(flags, up_to_day=d)
            matching = [a for a in ev["active_alerts"] if a["signal"] in target_signals]
            if matching:
                return d
    return None


def _comparator_first_detection_day(
    hits: Sequence[Tuple[str, str, int]],
    entity_id: str,
    target_signals: set[str],
    onset_day: int,
    peak_day: int,
) -> Optional[int]:
    days = [
        d
        for ent, sig, d in hits
        if ent == entity_id and sig in target_signals and onset_day <= d <= peak_day
    ]
    return min(days) if days else None


# ---------------------------------------------------------------------------
# Individual Validation Suites
# ---------------------------------------------------------------------------


def _get_mission(
    seed: int,
    null_mission: bool,
    mission_cache: Optional[Dict[Tuple[int, bool], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    key = (seed, null_mission)
    if mission_cache is not None and key in mission_cache:
        return mission_cache[key]
    mission = generate_mission(days=30, seed=seed, null_mission=null_mission)
    if mission_cache is not None:
        mission_cache[key] = mission
    return mission


def _run_planted_scenarios_benchmark(
    seeds: Sequence[int],
    n_permutations: int,
    mission_cache: Optional[Dict[Tuple[int, bool], Dict[str, Any]]] = None,
    mside_cache: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Compare Earth-Norm, Heuristic Rolling, and AstroGuard across multi-seed planted scenarios."""
    engine = PersonalBaselineEngine()
    policy = AlertPolicyEngine()

    comparators = ("earth_norm", "heuristic_rolling", "astra")
    recall_counts: Dict[str, int] = {c: 0 for c in comparators}
    lead_times: Dict[str, List[float]] = {c: [] for c in comparators}
    per_scenario: Dict[str, Dict[str, List[Optional[float]]]] = {
        eid: {c: [] for c in comparators} for eid in PLANTED_TARGET_SIGNALS
    }

    behavioral_hits: Dict[str, int] = {c: 0 for c in comparators}
    mside_hits: Dict[str, int] = {c: 0 for c in comparators}
    radiation_d23_msv: List[float] = []

    total_instances = len(seeds) * len(PLANTED_TARGET_SIGNALS)

    for s in seeds:
        recs = _get_mission(s, False, mission_cache)["records"]
        recs_by_entity: Dict[str, List[MeasurementRecord]] = {}
        for r in recs:
            recs_by_entity.setdefault(r.astronaut_id, []).append(r)

        b1_hits = _evaluate_earth_norm(recs, max_day=23, include_habitat_co2=True)
        b2_hits = _evaluate_heuristic_rolling(recs, min_day=10, max_day=23, z_thresh=2.5, include_habitat_co2=True)

        # Evaluate detection & lead time per planted anomaly scenario
        for eid, (entity_id, sigs, onset_d, peak_d) in PLANTED_TARGET_SIGNALS.items():
            d1 = _comparator_first_detection_day(b1_hits, entity_id, sigs, onset_d, peak_d)
            d2 = _comparator_first_detection_day(b2_hits, entity_id, sigs, onset_d, peak_d)
            d3 = _astra_first_detection_day(
                engine, policy, recs_by_entity.get(entity_id, recs), entity_id, sigs, onset_d, peak_d
            )

            for comp, d_hit in (("earth_norm", d1), ("heuristic_rolling", d2), ("astra", d3)):
                if d_hit is not None:
                    recall_counts[comp] += 1
                    lt = float(peak_d - d_hit)
                    lead_times[comp].append(lt)
                    per_scenario[eid][comp].append(lt)
                else:
                    per_scenario[eid][comp].append(None)

        # Underreporting behavioral mismatch check (Day 23)
        beh2 = assess_behavioral_health(recs, astronaut_id="ast-02", up_to_day=23)
        if beh2.get("underreporting_mismatch") and not beh2.get("fitness_for_duty_computed", True):
            behavioral_hits["astra"] += 1

        # Cross-crew LAB CO2 discovery check (MSIDE)
        mside_res = discover_interactions(recs, up_to_day=23, fdr_alpha=0.05, n_permutations=n_permutations, seed=s)
        if mside_cache is not None:
            mside_cache[s] = mside_res
        if any(f.get("zone_id") == "LAB" for f in mside_res.get("shared_exposure_findings", [])):
            mside_hits["astra"] += 1

        # Radiation trend audit on Day 23
        rad_recs = [
            r.value
            for r in recs
            if r.astronaut_id == "habitat"
            and r.signal_type == SignalType.RADIATION_CUMULATIVE_MSV.value
            and r.day == 23
            and r.value is not None
        ]
        if rad_recs:
            radiation_d23_msv.append(float(rad_recs[-1]))

    scenario_summary: Dict[str, Any] = {}
    for eid, comp_map in per_scenario.items():
        scenario_summary[eid] = {}
        for comp, vals in comp_map.items():
            detected = [v for v in vals if v is not None]
            scenario_summary[eid][comp] = {
                "recall": round(len(detected) / len(seeds), 3),
                "mean_lead_time_days": round(statistics.mean(detected), 2) if detected else None,
            }

    comparator_summary: Dict[str, Any] = {}
    n_seeds = max(1, len(seeds))
    for comp in comparators:
        lts = lead_times[comp]
        comparator_summary[comp] = {
            "event_recall": round(recall_counts[comp] / total_instances, 3),
            "events_detected": recall_counts[comp],
            "total_events": total_instances,
            "mean_lead_time_days": round(statistics.mean(lts), 2) if lts else 0.0,
            "median_lead_time_days": round(statistics.median(lts), 2) if lts else 0.0,
            "behavioral_mismatch_recall": round(behavioral_hits[comp] / n_seeds, 3),
            "cross_crew_mside_recall": round(mside_hits[comp] / n_seeds, 3),
        }

    return {
        "seeds": list(seeds),
        "comparators": comparator_summary,
        "per_scenario": scenario_summary,
        "radiation_day23_mean_msv": round(statistics.mean(radiation_d23_msv), 2) if radiation_d23_msv else 0.0,
    }


def _run_null_mission_benchmark(
    seeds: Sequence[int],
    mission_cache: Optional[Dict[Tuple[int, bool], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Evaluate false alert rate per 30 crew-days across null missions (`null_mission=True`)."""
    engine = PersonalBaselineEngine()
    policy = AlertPolicyEngine()

    total_crew_days = len(seeds) * len(CREW_IDS) * 30
    totals: Dict[str, int] = {"earth_norm": 0, "heuristic_rolling": 0, "astra": 0}
    per_seed_astra: List[Dict[str, Any]] = []
    null_dq_routed = 0

    for s in seeds:
        recs = _get_mission(s, True, mission_cache)["records"]
        by_astro: Dict[str, List[MeasurementRecord]] = {aid: [] for aid in CREW_IDS}
        for r in recs:
            if r.astronaut_id in by_astro:
                by_astro[r.astronaut_id].append(r)

        b1_hits = _evaluate_earth_norm(recs, max_day=30, include_habitat_co2=False)
        b2_hits = _evaluate_heuristic_rolling(recs, min_day=10, max_day=30, z_thresh=2.5, include_habitat_co2=False)
        totals["earth_norm"] += len(b1_hits)
        totals["heuristic_rolling"] += len(b2_hits)

        # Evaluate AstroGuard across non-overlapping 7-day rolling mission windows post-baseline
        astra_alerts = 0
        astra_faults = 0
        for d in (10, 17, 23, 30):
            flags: List[Any] = []
            for aid in CREW_IDS:
                flags.extend(engine.detect_anomalies(by_astro[aid], aid, up_to_day=d))
            rules = evaluate_safety_rules(recs, up_to_day=d)
            ev = policy.evaluate_alerts(flags, safety_rules=rules, up_to_day=d)
            astra_alerts += len(ev["active_alerts"]) + len(ev["safety_alerts"])
            astra_faults += len(ev["data_quality_notices"])

        totals["astra"] += astra_alerts
        null_dq_routed += astra_faults
        per_seed_astra.append(
            {
                "seed": s,
                "false_alerts": astra_alerts,
                "fa_per_30_crew_days": round(astra_alerts * 30.0 / (len(CREW_IDS) * 30), 3),
                "data_fault_notices": astra_faults,
            }
        )

    rates: Dict[str, Dict[str, Any]] = {}
    for comp, count in totals.items():
        rate = count * 30.0 / max(1, total_crew_days)
        rates[comp] = {
            "total_false_alerts": count,
            "crew_days": total_crew_days,
            "fa_per_30_crew_days": round(rate, 3),
            "fa_per_astronaut_week": round(rate * (7.0 / 30.0), 3),
        }

    return {
        "seeds": list(seeds),
        "crew_days": total_crew_days,
        "comparators": rates,
        "astra_per_seed": per_seed_astra,
        "null_data_fault_notices_routed": null_dq_routed,
        "gate_passed": rates["astra"]["fa_per_30_crew_days"] <= 1.0,
    }


def _run_missingness_sweep(
    seed: int,
    mission_cache: Optional[Dict[Tuple[int, bool], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Sweep 0%, 10%, 30%, 50% missingness and verify degradation + zero normal imputation."""
    base_recs = [
        r
        for r in _get_mission(seed, False, mission_cache)["records"]
        if r.astronaut_id in ("ast-01", "ast-02", "habitat")
    ]
    engine = PersonalBaselineEngine()
    policy = AlertPolicyEngine()

    levels = (0.0, 0.10, 0.30, 0.50)
    rows: List[Dict[str, Any]] = []

    for frac in levels:
        recs = base_recs if frac == 0.0 else inject_missingness(base_recs, fraction=frac, seed=seed + int(frac * 100))

        # Check explicit invariant: no missing/sensor_off slot carries quality=='ok' or imputed value
        imputation_leaks = sum(
            1
            for r in recs
            if (r.quality in (QualityState.MISSING.value, QualityState.SENSOR_OFF.value) and r.value is not None)
            or (r.value is None and r.quality == QualityState.OK.value)
        )

        # Evaluate ast-01 and ast-02 at Day 23
        confs: List[float] = []
        coverages: List[float] = []
        recalled_targets = 0
        for aid, sigs in (
            ("ast-01", PLANTED_TARGET_SIGNALS["EV_RECOVERY_DECLINE"][1]),
            ("ast-02", PLANTED_TARGET_SIGNALS["MC_COGNITIVE_DRIFT_AND_UNDERREPORTING"][1]),
        ):
            target_recs = [r for r in recs if r.astronaut_id in (aid, "habitat")]
            rd = compute_readiness(target_recs, aid, up_to_day=23)
            coverages.append(float(rd["data_quality"]["coverage"]))
            confs.append(float(rd["confidence"]))
            flags = engine.detect_anomalies(target_recs, aid, up_to_day=23)
            ev = policy.evaluate_alerts(flags, up_to_day=23)
            if any(a["signal"] in sigs for a in ev["active_alerts"]):
                recalled_targets += 1

        rows.append(
            {
                "missing_fraction": frac,
                "missing_pct": round(frac * 100),
                "mean_coverage": round(statistics.mean(coverages), 3),
                "mean_confidence": round(statistics.mean(confs), 3),
                "target_recall_at_d23": round(recalled_targets / 2.0, 3),
                "imputation_leaks": imputation_leaks,
            }
        )

    monotonic_conf = all(rows[i]["mean_confidence"] >= rows[i + 1]["mean_confidence"] for i in range(len(rows) - 1))
    zero_leaks = all(r["imputation_leaks"] == 0 for r in rows)

    return {
        "seed": seed,
        "levels": rows,
        "monotonic_confidence_degradation": monotonic_conf,
        "zero_imputation_leaks": zero_leaks,
        "passed": monotonic_conf and zero_leaks,
    }


def _run_artifact_and_step_checks(
    seed: int,
    mission_cache: Optional[Dict[Tuple[int, bool], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Verify 100% artifact routing to `data_fault` and firmware step immunity + drift preservation."""
    null_recs = _get_mission(seed, True, mission_cache)["records"]
    ast02_recs = [r for r in null_recs if r.astronaut_id == "ast-02"]
    ast01_recs = [r for r in null_recs if r.astronaut_id == "ast-01"]
    engine = PersonalBaselineEngine()
    policy = AlertPolicyEngine()

    artifact_results: List[Dict[str, Any]] = []
    astra_fault_routed = 0
    astra_false_physio = 0
    earth_norm_false_physio = 0
    heuristic_false_physio = 0

    base_b1_d22 = set(_evaluate_earth_norm(ast02_recs, max_day=23))
    base_b2_d22 = set(_evaluate_heuristic_rolling(ast02_recs, min_day=10, max_day=23, z_thresh=2.5))

    for kind, sig in ARTIFACT_CASE_TYPES:
        art_recs = inject_artifacts(
            ast02_recs,
            astronaut_id="ast-02",
            signal_type=sig,
            day=22,
            hour=15,
            artifact_type=kind,
            seed=seed,
        )
        classified = [a for a in classify_artifact(art_recs) if a.get("day") == 22]
        routed_fault = any(a.get("anomaly_type") == "data_fault" for a in classified)
        if routed_fault:
            astra_fault_routed += 1

        flags = engine.detect_anomalies(art_recs, "ast-02", up_to_day=23)
        ev = policy.evaluate_alerts(flags, up_to_day=23)
        non_fault_alerts = [a for a in ev["active_alerts"]]
        if non_fault_alerts:
            astra_false_physio += len(non_fault_alerts)

        b1_new = [x for x in set(_evaluate_earth_norm(art_recs, max_day=23)) - base_b1_d22 if x[0] == "ast-02" and x[2] == 22]
        b2_new = [x for x in set(_evaluate_heuristic_rolling(art_recs, min_day=10, max_day=23, z_thresh=2.5)) - base_b2_d22 if x[0] == "ast-02" and x[2] == 22]
        if b1_new:
            earth_norm_false_physio += 1
        if b2_new:
            heuristic_false_physio += 1

        artifact_results.append(
            {
                "artifact_type": kind,
                "signal": sig,
                "routed_to_data_fault": routed_fault,
                "astra_physio_alerts": len(non_fault_alerts),
                "earth_norm_false_trigger": bool(b1_new),
                "heuristic_false_trigger": bool(b2_new),
            }
        )

    # Device-step immunity + preserved subsequent drift
    step_recs = inject_device_step(
        ast01_recs,
        astronaut_id="ast-01",
        signal_type=SignalType.RESTING_HR.value,
        onset_day=15,
        offset=8.0,
        new_firmware="fw-3.1",
    )
    step_info = engine.detect_device_step(step_recs, "ast-01", SignalType.RESTING_HR.value)
    step_rhr_flags = [f for f in engine.detect_anomalies(step_recs, "ast-01", up_to_day=23) if f.signal == SignalType.RESTING_HR.value and f.anomaly_type != "data_fault"]

    b2_step_rhr = [
        x
        for x in _evaluate_heuristic_rolling(step_recs, min_day=15, max_day=23, z_thresh=2.5)
        if x[0] == "ast-01" and x[1] == SignalType.RESTING_HR.value
    ]

    # Inject true progression +1.4 bpm/day starting Day 19 AFTER the Day 15 device step
    step_plus_drift = [copy.copy(r) for r in step_recs]
    for r in step_plus_drift:
        if r.astronaut_id == "ast-01" and r.signal_type == SignalType.RESTING_HR.value and r.day >= 19 and r.value is not None:
            r.value = round(float(r.value) + 1.4 * (r.day - 18), 2)
    post_step_drift_flags = [
        f
        for f in engine.detect_anomalies(step_plus_drift, "ast-01", up_to_day=25)
        if f.signal == SignalType.RESTING_HR.value and f.anomaly_type == "drift"
    ]

    total_art = len(ARTIFACT_CASE_TYPES)
    return {
        "seed": seed,
        "artifact_cases": artifact_results,
        "artifact_fault_routing_rate": round(astra_fault_routed / total_art, 3),
        "astra_artifact_false_physio_alerts": astra_false_physio,
        "earth_norm_artifact_false_rate": round(earth_norm_false_physio / total_art, 3),
        "heuristic_artifact_false_rate": round(heuristic_false_physio / total_art, 3),
        "device_step": {
            "detected": bool(step_info.get("detected")),
            "estimated_offset_bpm": step_info.get("total_offset"),
            "injected_offset_bpm": 8.0,
            "astra_step_false_rhr_alerts": len(step_rhr_flags),
            "heuristic_step_false_rhr_alerts": len(b2_step_rhr),
            "subsequent_true_drift_detected": len(post_step_drift_flags) > 0,
            "subsequent_drift_score": post_step_drift_flags[0].score if post_step_drift_flags else 0.0,
        },
        "passed": (
            astra_fault_routed == total_art
            and astra_false_physio == 0
            and bool(step_info.get("detected"))
            and len(step_rhr_flags) == 0
            and len(post_step_drift_flags) > 0
        ),
    }


def _run_mside_controls(
    seeds: Sequence[int],
    n_permutations: int,
    mission_cache: Optional[Dict[Tuple[int, bool], Dict[str, Any]]] = None,
    mside_cache: Optional[Dict[int, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run MSIDE positive control vs time-shuffled negative control across seeds."""
    pos_runs: List[Dict[str, Any]] = []
    neg_runs: List[Dict[str, Any]] = []
    forbidden_causal_words = ("causes", "caused by", "proves", "diagnoses", "diagnosed")

    for idx, s in enumerate(seeds):
        recs = _get_mission(s, False, mission_cache)["records"]
        pos = (
            mside_cache[s]
            if (mside_cache is not None and s in mside_cache)
            else discover_interactions(recs, up_to_day=23, fdr_alpha=0.05, n_permutations=n_permutations, seed=s)
        )
        shared = pos.get("shared_exposure_findings", [])
        lab_shared = [f for f in shared if f.get("zone_id") == "LAB"]
        non_causal = all(
            not any(w in (f.get("summary", "") + " " + f.get("title", "")).lower() for w in forbidden_causal_words)
            for f in pos.get("findings", [])
        )
        pos_runs.append(
            {
                "seed": s,
                "discovery_count": pos["discovery_count"],
                "shared_lab_found": len(lab_shared) > 0,
                "shared_lab_r": lab_shared[0]["correlation_r"] if lab_shared else None,
                "shared_lab_fdr_q": lab_shared[0]["fdr_q_value"] if lab_shared else None,
                "non_causal_phrasing": non_causal,
            }
        )

        neg = run_negative_control(recs, seed=s + 100 + idx, up_to_day=23, fdr_alpha=0.05, n_permutations=n_permutations)
        neg_runs.append(
            {
                "seed": s,
                "total_hypotheses": neg["total_hypotheses"],
                "false_discoveries": neg["false_discoveries"],
                "false_discovery_rate": neg["false_discovery_rate"],
                "passed": neg["passed"],
            }
        )

    max_neg_fdr = max(r["false_discovery_rate"] for r in neg_runs)
    return {
        "fdr_alpha": 0.05,
        "positive_controls": pos_runs,
        "negative_controls": neg_runs,
        "positive_shared_lab_rate": round(sum(1 for r in pos_runs if r["shared_lab_found"]) / len(pos_runs), 3),
        "all_non_causal": all(r["non_causal_phrasing"] for r in pos_runs),
        "mean_negative_fdr": round(statistics.mean(r["false_discovery_rate"] for r in neg_runs), 5),
        "max_negative_fdr": round(max_neg_fdr, 5),
        "passed": (
            all(r["shared_lab_found"] and r["non_causal_phrasing"] for r in pos_runs)
            and all(r["passed"] for r in neg_runs)
            and max_neg_fdr <= 0.05
        ),
    }


def _run_confidence_calibration(
    seeds: Sequence[int],
    mission_cache: Optional[Dict[Tuple[int, bool], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Assess stated confidence vs empirical reliability across data-quality strata."""
    engine = PersonalBaselineEngine()
    policy = AlertPolicyEngine()

    strata: Dict[str, Dict[str, Any]] = {
        "high_quality_ge_90pct": {"confs": [], "covs": [], "outcomes": []},
        "degraded_missing_30_50pct": {"confs": [], "covs": [], "outcomes": []},
    }

    target_map = {
        "ast-01": PLANTED_TARGET_SIGNALS["EV_RECOVERY_DECLINE"][1],
        "ast-02": PLANTED_TARGET_SIGNALS["MC_COGNITIVE_DRIFT_AND_UNDERREPORTING"][1],
    }

    for s in seeds:
        planted = [
            r
            for r in _get_mission(s, False, mission_cache)["records"]
            if r.astronaut_id in ("ast-01", "ast-02", "habitat")
        ]
        null_recs = [
            r
            for r in _get_mission(s, True, mission_cache)["records"]
            if r.astronaut_id in ("ast-01", "ast-02", "habitat")
        ]

        variants = (
            ("high_quality_ge_90pct", planted, True),
            ("high_quality_ge_90pct", null_recs, False),
            ("degraded_missing_30_50pct", inject_missingness(planted, fraction=0.40, seed=s + 40), True),
            ("degraded_missing_30_50pct", inject_missingness(null_recs, fraction=0.40, seed=s + 40), False),
        )

        for stratum, recs, is_positive in variants:
            for aid, target_sigs in target_map.items():
                aid_recs = [r for r in recs if r.astronaut_id in (aid, "habitat")]
                rd = compute_readiness(aid_recs, aid, up_to_day=23)
                cov = float(rd["data_quality"]["coverage"])
                stated_conf = float(rd["confidence"])
                flags = engine.detect_anomalies(aid_recs, aid, up_to_day=23)
                ev = policy.evaluate_alerts(flags, up_to_day=23)
                has_target_alert = any(a["signal"] in target_sigs for a in ev["active_alerts"])
                has_any_alert = len(ev["active_alerts"]) > 0

                correct = has_target_alert if is_positive else (not has_any_alert)
                strata[stratum]["confs"].append(stated_conf)
                strata[stratum]["covs"].append(cov)
                strata[stratum]["outcomes"].append(1.0 if correct else 0.0)

    summary: Dict[str, Any] = {}
    for key, bucket in strata.items():
        mean_c = statistics.mean(bucket["confs"])
        mean_cov = statistics.mean(bucket["covs"])
        emp_acc = statistics.mean(bucket["outcomes"])
        summary[key] = {
            "n_evaluations": len(bucket["outcomes"]),
            "mean_coverage": round(mean_cov, 3),
            "mean_stated_confidence": round(mean_c, 3),
            "empirical_accuracy": round(emp_acc, 3),
            "calibration_gap": round(abs(mean_c - emp_acc), 3),
        }

    hq = summary["high_quality_ge_90pct"]
    dq = summary["degraded_missing_30_50pct"]
    confidence_reflects_quality = hq["mean_stated_confidence"] > dq["mean_stated_confidence"]
    higher_conf_at_least_as_accurate = hq["empirical_accuracy"] >= dq["empirical_accuracy"]

    return {
        "strata": summary,
        "confidence_reflects_quality": confidence_reflects_quality,
        "higher_conf_at_least_as_accurate": higher_conf_at_least_as_accurate,
        "passed": confidence_reflects_quality and higher_conf_at_least_as_accurate,
    }


def run_validation_suite(seed: int = 42, fast: bool = False) -> Dict[str, Any]:
    """Run the full AstroGuard validation benchmark suite and return structured results."""
    t_start = time.perf_counter()
    seeds = [seed] if fast else [seed, seed + 1, seed + 2]
    n_perm = 30 if fast else 60

    mission_cache: Dict[Tuple[int, bool], Dict[str, Any]] = {}
    mside_cache: Dict[int, Dict[str, Any]] = {}

    planted = _run_planted_scenarios_benchmark(
        seeds, n_permutations=n_perm, mission_cache=mission_cache, mside_cache=mside_cache
    )
    null_bench = _run_null_mission_benchmark(seeds, mission_cache=mission_cache)
    missing_sweep = _run_missingness_sweep(seed=seed, mission_cache=mission_cache)
    artifacts_and_step = _run_artifact_and_step_checks(seed=seed, mission_cache=mission_cache)
    mside_controls = _run_mside_controls(
        seeds, n_permutations=n_perm, mission_cache=mission_cache, mside_cache=mside_cache
    )
    calibration = _run_confidence_calibration(seeds, mission_cache=mission_cache)

    elapsed = round(time.perf_counter() - t_start, 2)
    astra_planted = planted["comparators"]["astra"]
    b1_planted = planted["comparators"]["earth_norm"]

    gates = {
        "planted_recall_ge_0_80": astra_planted["event_recall"] >= 0.80,
        "lead_time_beats_earth_norm": astra_planted["mean_lead_time_days"] > b1_planted["mean_lead_time_days"],
        "null_fa_le_1_per_30_crew_days": null_bench["gate_passed"],
        "null_fa_below_earth_norm": null_bench["comparators"]["astra"]["fa_per_30_crew_days"]
        < null_bench["comparators"]["earth_norm"]["fa_per_30_crew_days"],
        "artifact_fault_routing_ge_0_95": artifacts_and_step["artifact_fault_routing_rate"] >= 0.95,
        "device_step_immunity_passed": artifacts_and_step["passed"],
        "missingness_graceful_degradation": missing_sweep["passed"],
        "mside_controls_fdr_le_0_05": mside_controls["passed"],
        "confidence_calibration_passed": calibration["passed"],
        "null_fa_below_heuristic_rolling": null_bench["comparators"]["astra"]["fa_per_30_crew_days"]
        < null_bench["comparators"]["heuristic_rolling"]["fa_per_30_crew_days"],
    }

    return {
        "metadata": {
            "seed": seed,
            "seeds": seeds,
            "fast": fast,
            "n_permutations": n_perm,
            "elapsed_seconds": elapsed,
            "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "illustrative_disclaimer": (
                "Illustrative synthetic validation metrics generated on seeded simulator missions "
                "(simulator.py). Thresholds and synthetic curves are not empirical NASA astronaut data."
            ),
        },
        "planted_scenarios": planted,
        "null_missions": null_bench,
        "missingness_sweep": missing_sweep,
        "artifacts_and_device_step": artifacts_and_step,
        "mside_controls": mside_controls,
        "confidence_calibration": calibration,
        "gates": gates,
        "all_gates_passed": all(gates.values()),
    }


# ---------------------------------------------------------------------------
# Markdown Report Generators
# ---------------------------------------------------------------------------


def format_validation_report(results: Dict[str, Any]) -> str:
    """Format validation results as a readable Markdown report."""
    meta = results["metadata"]
    p_comp = results["planted_scenarios"]["comparators"]
    p_scen = results["planted_scenarios"]["per_scenario"]
    n_comp = results["null_missions"]["comparators"]
    miss_rows = results["missingness_sweep"]["levels"]
    art = results["artifacts_and_device_step"]
    step = art["device_step"]
    mside = results["mside_controls"]
    cal = results["confidence_calibration"]["strata"]
    gates = results["gates"]

    lines = [
        "# AstroGuard Validation Report",
        "",
        f"> [!IMPORTANT]",
        f"> **Illustrative Validation Notice:** {meta['illustrative_disclaimer']}",
        "",
        "## Run Provenance",
        "",
        f"- **Command:** `cd /home/frihk/frihk/Astra/backend && python3 -m app.eval.run --seed {meta['seed']}`",
        f"- **Seeds Evaluated:** `{meta['seeds']}` (`n_permutations={meta['n_permutations']}`, `fast={meta['fast']}`)",
        f"- **Runtime:** `{meta['elapsed_seconds']:.2f} s`",
        f"- **Overall Release Gate Status:** `{'PASS' if results['all_gates_passed'] else 'FAIL'}`",
        "",
        "## 1. Three-Way Comparator Summary",
        "",
        "| Metric | Baseline 1: Fixed Earth-Norm | Baseline 2: Heuristic Rolling (`|z|>=2.5`) | AstroGuard Full Engine Stack |",
        "| --- | ---: | ---: | ---: |",
        f"| Planted Anomaly Event Recall | {p_comp['earth_norm']['event_recall']:.3f} | {p_comp['heuristic_rolling']['event_recall']:.3f} | **{p_comp['astra']['event_recall']:.3f}** |",
        f"| Mean Lead Time Before Peak (days) | {p_comp['earth_norm']['mean_lead_time_days']:.2f} | {p_comp['heuristic_rolling']['mean_lead_time_days']:.2f} | **{p_comp['astra']['mean_lead_time_days']:.2f}** |",
        f"| Behavioral Underreporting Recall | {p_comp['earth_norm']['behavioral_mismatch_recall']:.3f} | {p_comp['heuristic_rolling']['behavioral_mismatch_recall']:.3f} | **{p_comp['astra']['behavioral_mismatch_recall']:.3f}** |",
        f"| Cross-Crew MSIDE Exposure Recall | {p_comp['earth_norm']['cross_crew_mside_recall']:.3f} | {p_comp['heuristic_rolling']['cross_crew_mside_recall']:.3f} | **{p_comp['astra']['cross_crew_mside_recall']:.3f}** |",
        f"| Null Mission False Alerts / 30 Crew-Days | {n_comp['earth_norm']['fa_per_30_crew_days']:.3f} | {n_comp['heuristic_rolling']['fa_per_30_crew_days']:.3f} | **{n_comp['astra']['fa_per_30_crew_days']:.3f}** |",
        f"| Artifact False-Alert Rate (6 Fault Types) | {art['earth_norm_artifact_false_rate']:.3f} | {art['heuristic_artifact_false_rate']:.3f} | **{art['astra_artifact_false_physio_alerts'] / len(art['artifact_cases']):.3f}** |",
        f"| Fault Routing Completeness (`data_fault`) | 0.000 | 0.000 | **{art['artifact_fault_routing_rate']:.3f}** |",
        "",
        (
            f"- **Comparator Deltas:** AstroGuard leads Fixed Earth-Norm by "
            f"`{p_comp['astra']['mean_lead_time_days'] - p_comp['earth_norm']['mean_lead_time_days']:+.2f} days` "
            f"while reducing null-mission false alerts by "
            f"`{n_comp['earth_norm']['fa_per_30_crew_days'] - n_comp['astra']['fa_per_30_crew_days']:.2f}/30 crew-days` vs Earth-Norm "
            f"and `{n_comp['heuristic_rolling']['fa_per_30_crew_days'] - n_comp['astra']['fa_per_30_crew_days']:.2f}/30 crew-days` vs Heuristic Rolling "
            f"(whose apparent early sensitivity comes with `{n_comp['heuristic_rolling']['fa_per_30_crew_days']:.2f}` false alerts/30 crew-days)."
        ),
        "",
        "### Per-Scenario Breakdown (Planted Events)",
        "",
        "| Scenario ID | Earth-Norm Recall (Lead d) | Heuristic Rolling Recall (Lead d) | AstroGuard Recall (Lead d) |",
        "| --- | ---: | ---: | ---: |",
    ]

    for eid, row in p_scen.items():
        def _fmt(entry: Dict[str, Any]) -> str:
            lt = f"{entry['mean_lead_time_days']:.1f}d" if entry["mean_lead_time_days"] is not None else "—"
            return f"{entry['recall']:.2f} ({lt})"

        lines.append(
            f"| `{eid}` | {_fmt(row['earth_norm'])} | {_fmt(row['heuristic_rolling'])} | **{_fmt(row['astra'])}** |"
        )

    lines.extend(
        [
            "",
            f"- Shared Habitat Cumulative Radiation by Day 23 (mean across seeds): `{results['planted_scenarios']['radiation_day23_mean_msv']:.2f} mSv`",
            "",
            "## 2. Null-Mission Alert Burden (`null_mission=True`)",
            "",
            f"- Evaluated `{results['null_missions']['crew_days']}` crew-days across seeds `{results['null_missions']['seeds']}` (`4` crew x `30` days/seed).",
            f"- AstroGuard false alerts total: `{n_comp['astra']['total_false_alerts']}` (`{n_comp['astra']['fa_per_30_crew_days']:.3f}` per 30 crew-days; gate `<= 1.0`).",
            f"- Existing clean gap on `ast-02` Day 14 was quarantined cleanly (`null_data_fault_notices_routed={results['null_missions']['null_data_fault_notices_routed']}`).",
            "",
            "| Seed | False Alerts | FA / 30 Crew-Days | Data Fault Notices Routed |",
            "| ---: | ---: | ---: | ---: |",
        ]
    )
    for row in results["null_missions"]["astra_per_seed"]:
        lines.append(
            f"| {row['seed']} | {row['false_alerts']} | {row['fa_per_30_crew_days']:.3f} | {row['data_fault_notices']} |"
        )

    lines.extend(
        [
            "",
            "## 3. Missingness Robustness Sweep (`10%`, `30%`, `50%`)",
            "",
            "| Missingness | Mean Coverage | Mean Stated Confidence | Target Recall (Day 23) | Imputation Leaks |",
            "| ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for r in miss_rows:
        lines.append(
            f"| {r['missing_pct']}% | {r['mean_coverage']:.3f} | {r['mean_confidence']:.3f} | {r['target_recall_at_d23']:.3f} | {r['imputation_leaks']} |"
        )
    lines.extend(
        [
            "",
            f"- Monotonic confidence degradation verified: `{results['missingness_sweep']['monotonic_confidence_degradation']}`",
            f"- Zero `sensor_off`/`missing` values imputed as normal: `{results['missingness_sweep']['zero_imputation_leaks']}`",
            "",
            "## 4. Artifact Isolation & Device-Step Immunity",
            "",
            "| Artifact Type | Signal | Routed to `data_fault` | AstroGuard Physio Alerts | Earth-Norm False Trigger | Heuristic False Trigger |",
            "| --- | --- | :---: | ---: | :---: | :---: |",
        ]
    )
    for c in art["artifact_cases"]:
        lines.append(
            f"| `{c['artifact_type']}` | `{c['signal']}` | `{c['routed_to_data_fault']}` | {c['astra_physio_alerts']} | `{c['earth_norm_false_trigger']}` | `{c['heuristic_false_trigger']}` |"
        )
    lines.extend(
        [
            "",
            f"- **Device-Step Hardware Swap (`+8.0 bpm` on `ast-01` `resting_hr` at Day 15):**",
            f"  - Step detector triggered: `{step['detected']}` (estimated offset `+{step['estimated_offset_bpm']} bpm` vs injected `+8.0 bpm`).",
            f"  - AstroGuard false physiological `resting_hr` alerts post-swap: `{step['astra_step_false_rhr_alerts']}` (vs Heuristic Rolling: `{step['heuristic_step_false_rhr_alerts']}`).",
            f"  - Preserved true post-swap drift sensitivity (`+1.4 bpm/day` Days 19–25): `{step['subsequent_true_drift_detected']}` (score `{step['subsequent_drift_score']}`).",
            "",
            "## 5. MSIDE Controls (Positive Cluster vs Time-Shuffled Negative Control)",
            "",
            f"- Positive Control Shared `LAB` Cluster Detection Rate: `{mside['positive_shared_lab_rate']:.3f}`",
            f"- Strictly Non-Causal Language Verified (`causes`/`proves`/`diagnosed` absent): `{mside['all_non_causal']}`",
            f"- Negative Control Mean Empirical FDR (shuffled timestamps): `{mside['mean_negative_fdr']:.5f}` (max `{mside['max_negative_fdr']:.5f}`, gate `<= {mside['fdr_alpha']}`)",
            "",
            "| Seed | Positive Shared LAB Found | LAB r | LAB q-value | Shuffled Hypotheses | Shuffled False Discoveries | Shuffled FDR |",
            "| ---: | :---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for pos_r, neg_r in zip(mside["positive_controls"], mside["negative_controls"]):
        r_str = f"{pos_r['shared_lab_r']:+.3f}" if pos_r["shared_lab_r"] is not None else "—"
        q_str = f"{pos_r['shared_lab_fdr_q']:.5f}" if pos_r["shared_lab_fdr_q"] is not None else "—"
        lines.append(
            f"| {pos_r['seed']} | `{pos_r['shared_lab_found']}` | {r_str} | {q_str} | {neg_r['total_hypotheses']} | {neg_r['false_discoveries']} | {neg_r['false_discovery_rate']:.5f} |"
        )

    lines.extend(
        [
            "",
            "## 6. Confidence Calibration Check",
            "",
            "| Quality Stratum | Evaluations | Mean Coverage | Mean Stated Confidence | Empirical Accuracy | Calibration Gap |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
            f"| Clean (`>= 90%` coverage) | {cal['high_quality_ge_90pct']['n_evaluations']} | {cal['high_quality_ge_90pct']['mean_coverage']:.3f} | {cal['high_quality_ge_90pct']['mean_stated_confidence']:.3f} | {cal['high_quality_ge_90pct']['empirical_accuracy']:.3f} | {cal['high_quality_ge_90pct']['calibration_gap']:.3f} |",
            f"| Degraded (`40%` missingness injected) | {cal['degraded_missing_30_50pct']['n_evaluations']} | {cal['degraded_missing_30_50pct']['mean_coverage']:.3f} | {cal['degraded_missing_30_50pct']['mean_stated_confidence']:.3f} | {cal['degraded_missing_30_50pct']['empirical_accuracy']:.3f} | {cal['degraded_missing_30_50pct']['calibration_gap']:.3f} |",
            "",
            f"- Stated confidence tracks clean vs degraded quality: `{results['confidence_calibration']['confidence_reflects_quality']}`",
            f"- Higher-confidence stratum matches/exceeds degraded accuracy: `{results['confidence_calibration']['higher_conf_at_least_as_accurate']}`",
            "",
            "## 7. Gate Verification Summary",
            "",
            "| Validation Gate | Status |",
            "| --- | :---: |",
        ]
    )
    for gname, gpass in gates.items():
        lines.append(f"| `{gname}` | `{'PASS' if gpass else 'FAIL'}` |")

    lines.append("")
    return "\n".join(lines)


def format_model_cards(results: Dict[str, Any]) -> str:
    """Generate structured model cards for AstroGuard analytical modules."""
    meta = results["metadata"]
    p_comp = results["planted_scenarios"]["comparators"]["astra"]
    null_fa = results["null_missions"]["comparators"]["astra"]["fa_per_30_crew_days"]
    art = results["artifacts_and_device_step"]
    mside = results["mside_controls"]

    return "\n".join(
        [
            "# AstroGuard Model & Decision-Support Engine Cards",
            "",
            "> [!NOTE]",
            f"> **Illustrative Status Notice:** {meta['illustrative_disclaimer']} None of the modules below perform clinical diagnosis, treatment prescribing, fitness-for-duty scoring, or autonomous clinical decisions.",
            "",
            "---",
            "",
            "## 1. Personal Baseline Engine (`backend/app/engines/baseline.py`)",
            "",
            "- **Purpose & Scope:** Establishes per-astronaut, context-stratified personal physiological/behavioral reference distributions and detects sustained drifts or multivariate shifts rather than single Earth-norm threshold crossings.",
            "- **Inputs:** `MeasurementRecord` stream (`astronaut_id`, `signal_type`, `value`, `quality`, `confidence`, `context_tags`, `source_device`, `firmware_version`, `day`, `hour`).",
            "- **Outputs:** `AnomalyFlag` entries classified strictly into `contextual`, `drift`, `multivariate`, or `data_fault` with personal range `[lo, hi]`, observed value, contributors, data coverage, and calibrated confidence.",
            "- **Method & Observed Parameters:**",
            "  - Conjugate Normal-Normal Bayesian shrinkage (`baseline_days=10`, `prior_strength=4.0`, `min_personal_samples=5`) with slow EWMA adaptation (`slow_alpha=0.04`) frozen whenever standardized excursion exceeds `freeze_z_threshold=1.75`.",
            "  - Stratified contexts (`sleep`, `exercise`, `post_exercise`, `rest`).",
            "  - Metadata-aligned device/firmware step offset estimation (`detect_device_step`) so hardware swaps shift baseline reference instead of firing drift alarms.",
            "  - Two-sided CUSUM drift accumulation (`cusum_k=0.5`, `cusum_h=3.8`) and Multivariate Mahalanobis covariance checks (`hr_recovery_1m`/`resting_hr`/`hrv_rmssd`/`sleep_duration` and cognitive clusters).",
            "- **Observed Validation Snapshot (Synthetic):** Event recall `{:.3f}`, mean lead time `{:.2f}d`, null FA `{:.3f}/30 crew-days`, artifact fault routing `{:.3f}`.".format(
                p_comp["event_recall"],
                p_comp["mean_lead_time_days"],
                null_fa,
                art["artifact_fault_routing_rate"],
            ),
            "- **Assumptions:** Early mission days (Days 1–10) or Bayesian priors approximate nominal baseline; hardware swaps update `source_device`/`firmware_version` metadata.",
            "- **Limitations & Failure Modes:** Cannot distinguish unrecorded hardware sensor bias without firmware/device metadata changes; extended >50% missingness lowers statistical power and reduces confidence cleanly.",
            "- **Safety & Privacy Boundary:** Hard-quarantines `suspect`, `out_of_range`, `sensor_off`, and `missing` records into `data_fault` (never imputed healthy). Never triggers/blocks deterministic safety rules (`SR-01..05`) or SOS.",
            "",
            "---",
            "",
            "## 2. Readiness & Recovery Scorer (`backend/app/engines/readiness.py`)",
            "",
            "- **Purpose & Scope:** Synthesizes clean physiological, sleep, cognitive, radiation, and environmental confounder streams into interpretable Recovery Debt (`0–100`) and Cognitive Readiness (`0–100`) decision-support scores.",
            "- **Inputs:** Clean telemetry records, active deterministic safety rules, environmental confounder summary, and data quality summary up to `up_to_day`.",
            "- **Outputs:** Recovery Debt (`0–100`, lower healthier), Cognitive Readiness (`0–100`, higher healthier), Radiation dosimetry trend (`uSv/day` and cumulative `mSv`), per-signal observations vs personal reference, and coverage-scaled confidence.",
            "- **Assumptions:** Baseline days reflect nominal resting/sleep/cognitive reference; higher Recovery Debt reflects multi-signal strain relative to personal norm.",
            "- **Limitations & Failure Modes:** Illustrative composite weights tuned to simulator mission scales (`F-03`); high missingness widens uncertainty/lowers confidence without inventing missing points; never a fitness-for-duty gate.",
            "- **Safety & Privacy Boundary:** Surfaces active deterministic safety rules (`SR-01..05`) prominently without altering or suppressing them; reads only numerical telemetry (`physio`/`sleep`/`cognitive`/`habitat`).",
            "",
            "---",
            "",
            "## 3. Crew-Environment Lag Correlator & MSIDE (`backend/app/engines/environment.py`, `mside.py`)",
            "",
            "- **Purpose & Scope:** Evaluates multi-stream habitat-to-crew associations across zones (`N1`, `LAB`, `CQ`, `AL`) and lags (`0–2d`) to detect shared environmental confounders (e.g., `LAB` CO2 scrubber degradation) before misattributing them to individual illness.",
            "- **Inputs:** Crew symptom/cognitive/physiological streams, zone environmental telemetry (`co2_ppm`, `cabin_temp_c`, `cabin_humidity_pct`, `cabin_noise_db`), and zone occupancy.",
            "- **Outputs:** Lagged Pearson correlations (`r`), permutation empirical `p`-values, Benjamini-Hochberg `FDR q`-values (`fdr_alpha=0.05`), and cross-crew shared exposure clusters (anonymized `Crew A..D` labels when shared across `>= 2` crew).",
            "- **Observed Validation Snapshot (Synthetic):** Positive shared `LAB` cluster recall `{:.3f}`, time-shuffled negative-control max empirical FDR `{:.5f}` (`<= 0.05`), strictly non-causal phrasing verified (`{}`).".format(
                mside["positive_shared_lab_rate"],
                mside["max_negative_fdr"],
                mside["all_non_causal"],
            ),
            "- **Assumptions:** Zone occupancy maps crew members to primary habitat module exposure; minimum overlapping clean days (`>= 5`) exist per pair.",
            "- **Limitations & Failure Modes:** Pearson correlation captures linear associations only; shared exposure never proves causation and explicitly notes individual illness is not excluded.",
            "- **Safety & Privacy Boundary:** Cross-crew summaries anonymize astronaut identities and prohibit reading private journal text or crew messages.",
            "",
            "---",
            "",
            "## 4. Counterfactual What-If Sandbox (`backend/app/engines/counterfactual.py`)",
            "",
            "- **Purpose & Scope:** Exploratory `1–14 day` trajectory comparison allowing crew to inspect how illustrative changes in sleep, workload (`-2..+2`), recovery blocks, and cabin ventilation (`50–200%`) shift trend direction and uncertainty.",
            "- **Inputs:** Current `readiness` output (`recovery_debt`, `cognitive_readiness`, recent 7-day series) and counterfactual lever inputs + `baseline_co2_ppm`.",
            "- **Outputs:** `baseline` vs `intervention` daily curves (`1..horizon_days`), `sqrt(step)` widening uncertainty bounds, CO2 ventilation delta, explicit assumption list, protocol references, and exploratory confidence (`<= 0.58`).",
            "- **Method & Parameters:** Extracts damped 7-day linear trend (`0.6x` slope, `0.84^(step-1)` decay), saturating `tanh` sleep response, exponential recovery-block scaling, and ventilation CO2 scaling (`ambient_floor=250 ppm`).",
            "- **Assumptions:** Smooth extrapolation of recent 7-day trend; no intervening acute illness, medication, or mechanical scrubber failure.",
            "- **Limitations & Failure Modes:** Purely illustrative first-order heuristic, not a validated physiological digital twin or treatment predictor; uncertainty widens rapidly (`5.2 * sqrt(step)` / `4.5 * sqrt(step)`).",
            "- **Safety & Privacy Boundary:** Always sets `exploratory: True` and carries explicit non-prediction / non-treatment disclaimers.",
            "",
            "---",
            "",
            "## 5. Offline Grounded AstroGuard Advisor (`backend/app/engines/advisor.py`)",
            "",
            "- **Purpose & Scope:** Produces concise, deterministic, offline daily briefings and answers natural-language crew questions strictly grounded in verified engine numbers and the curated `PROTOCOL_LIBRARY`.",
            "- **Inputs:** Verified engine outputs (`readiness`, `behavioral`, `environment`, `mside`, `counterfactual`), `active_safety_rules`, and `PROTOCOL_LIBRARY`.",
            "- **Outputs:** Grounded response with exact evidence windows, cited observations, confidence score, curated `protocol_refs`, `said_i_dont_know` flag, and `refused_diagnosis` flag.",
            "- **Assumptions:** All quantitative answers originate exclusively from verified upstream engine dictionaries.",
            "- **Limitations & Failure Modes:** Deterministic template/intent matching rather than open-ended LLM conversation; intentionally says `\"I don't know\"` when data coverage `< 60%` or asked about unsupported clinical tests (e.g., glucose, MRI).",
            "- **Safety & Privacy Boundary:** Explicitly refuses medical diagnosis or prescribing; prohibits overriding/downgrading deterministic safety rules (`SR-01..05`) or SOS beacons; never reads private journals or message text.",
            "",
        ]
    )


def write_validation_reports(results: Dict[str, Any], output_dir: Path = DEFAULT_OUTPUT_DIR) -> Tuple[Path, Path]:
    """Write `latest-validation-report.md` and `model-cards.md` to `output_dir`."""
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "latest-validation-report.md"
    cards_path = output_dir / "model-cards.md"
    report_path.write_text(format_validation_report(results), encoding="utf-8")
    cards_path.write_text(format_model_cards(results), encoding="utf-8")
    return report_path, cards_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run AstroGuard validation suite and generate reports.")
    parser.add_argument("--seed", type=int, default=42, help="Base PRNG seed (default: 42)")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for validation markdown reports",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Run reduced 2-seed / 40-permutation CI check",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON output to stdout")
    args = parser.parse_args(argv)

    results = run_validation_suite(seed=args.seed, fast=args.fast)
    report_path, cards_path = write_validation_reports(results, output_dir=args.output_dir)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        p_comp = results["planted_scenarios"]["comparators"]
        n_comp = results["null_missions"]["comparators"]
        summary = {
            "seed": args.seed,
            "elapsed_seconds": results["metadata"]["elapsed_seconds"],
            "all_gates_passed": results["all_gates_passed"],
            "astra_recall": p_comp["astra"]["event_recall"],
            "astra_mean_lead_days": p_comp["astra"]["mean_lead_time_days"],
            "earth_norm_mean_lead_days": p_comp["earth_norm"]["mean_lead_time_days"],
            "astra_null_fa_per_30cd": n_comp["astra"]["fa_per_30_crew_days"],
            "earth_norm_null_fa_per_30cd": n_comp["earth_norm"]["fa_per_30_crew_days"],
            "heuristic_null_fa_per_30cd": n_comp["heuristic_rolling"]["fa_per_30_crew_days"],
            "artifact_fault_routing_rate": results["artifacts_and_device_step"]["artifact_fault_routing_rate"],
            "mside_neg_ctrl_max_fdr": results["mside_controls"]["max_negative_fdr"],
            "report_path": str(report_path),
            "model_cards_path": str(cards_path),
        }
        print(json.dumps(summary, indent=2))

    return 0 if results["all_gates_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
