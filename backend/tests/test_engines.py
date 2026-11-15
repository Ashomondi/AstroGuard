"""Comprehensive unit tests for AstroGuard intelligence engines (F-05, F-10..F-16, F-18, F-29, F-30).

Uses deterministic synthetic fixture streams generated in-module so these tests
remain completely independent of `simulator.py`.
"""

from __future__ import annotations

import math
import random
import unittest
from typing import Dict, List, Optional

from app.engines.advisor import answer_question, build_daily_briefing
from app.engines.baseline import PersonalBaselineEngine
from app.engines.behavioral import assess_behavioral_health
from app.engines.counterfactual import simulate_intervention
from app.engines.environment import analyze_crew_environment
from app.engines.mside import discover_interactions, run_negative_control
from app.engines.readiness import compute_readiness
from app.protocols import PROTOCOL_LIBRARY
from app.schema import (
    CREW_ROSTER,
    ConsentScope,
    MeasurementRecord,
    QualityState,
    SIGNAL_TO_SCOPE,
    SIGNAL_UNITS,
    SignalType,
)


def _make_record(
    astronaut_id: str,
    day: int,
    hour: int,
    signal_type: str,
    value: Optional[float],
    context_tags: Optional[List[str]] = None,
    quality: str = QualityState.OK.value,
    source_device: str = "wristband-v2",
    firmware_version: str = "2.4.1",
    zone_id: str = "LAB",
    confidence: float = 0.96,
) -> MeasurementRecord:
    return MeasurementRecord(
        astronaut_id=astronaut_id,
        timestamp_utc=f"2031-03-{day:02d}T{hour:02d}:00:00Z",
        mission_elapsed_time=float((day - 1) * 24 + hour),
        day=day,
        hour=hour,
        signal_type=signal_type,
        value=value,
        unit=SIGNAL_UNITS.get(signal_type, "unit"),
        source_device=source_device,
        firmware_version=firmware_version,
        quality=quality,
        confidence=confidence if quality == QualityState.OK.value else 0.2,
        context_tags=list(context_tags or []),
        consent_scope=SIGNAL_TO_SCOPE.get(signal_type, ConsentScope.PHYSIO.value),
        zone_id=zone_id,
    )


def _build_healthy_astronaut_stream(
    astronaut_id: str = "ast-01",
    days: int = 23,
    seed: int = 101,
    zone_id: str = "CQ",
) -> List[MeasurementRecord]:
    rng = random.Random(seed)
    recs: List[MeasurementRecord] = []
    cum_msv = 0.0
    for d in range(1, days + 1):
        recs.append(_make_record(astronaut_id, d, 7, SignalType.RESTING_HR.value, 56.0 + rng.gauss(0, 1.0), ["rest"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 7, SignalType.HRV_RMSSD.value, 62.0 + rng.gauss(0, 2.2), ["sleep"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 7, SignalType.SLEEP_DURATION.value, 7.2 + rng.gauss(0, 0.2), ["sleep"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 7, SignalType.SLEEP_FRAGMENTATION.value, 10.0 + rng.gauss(0, 1.5), ["sleep"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 10, SignalType.HR_RECOVERY_1M.value, 35.0 + rng.gauss(0, 1.4), ["exercise"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 12, SignalType.HEART_RATE.value, 64.0 + rng.gauss(0, 2.0), ["rest"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 16, SignalType.HEART_RATE.value, 142.0 + rng.gauss(0, 4.0), ["exercise"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 14, SignalType.PVT_MEAN_RT.value, 248.0 + rng.gauss(0, 5.0), ["rest"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 14, SignalType.PVT_LAPSES.value, 0.0, ["rest"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 16, SignalType.SPO2.value, 98.0, ["rest"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 19, SignalType.SYMPTOM_HEADACHE.value, 0.0, ["rest"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 19, SignalType.SYMPTOM_FATIGUE.value, 0.5, ["rest"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 19, SignalType.MOOD_SCORE.value, 4.2, ["rest"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 19, SignalType.ENERGY_SCORE.value, 4.0, ["rest"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 19, SignalType.STRESS_SCORE.value, 1.8, ["rest"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 15, SignalType.ACTIVITY_INDEX.value, 1.0 + rng.gauss(0, 0.04), ["rest"], zone_id=zone_id))
        daily_u = 505.0
        cum_msv += daily_u / 1000.0
        recs.append(_make_record(astronaut_id, d, 20, SignalType.RADIATION_USV_DAY.value, daily_u, ["rest"], zone_id=zone_id))
        recs.append(_make_record(astronaut_id, d, 20, SignalType.RADIATION_CUMULATIVE_MSV.value, round(cum_msv, 2), ["rest"], zone_id=zone_id))
    return recs


class TestBaselineEngine(unittest.TestCase):
    def test_F05_cold_start_bayesian_shrinkage(self) -> None:
        recs = [
            _make_record("ast-01", 1, 7, SignalType.RESTING_HR.value, 50.0, ["rest"]),
            _make_record("ast-01", 2, 7, SignalType.RESTING_HR.value, 50.0, ["rest"]),
        ]
        engine = PersonalBaselineEngine()
        state = engine.fit_signal_context(recs, "ast-01", SignalType.RESTING_HR.value, "rest", up_to_day=2)
        self.assertTrue(state.cold_start)
        # Population prior is 58.0; with 2 samples at 50.0 and prior_strength=4, center shrinks between 50 and 58
        self.assertGreater(state.center, 50.5)
        self.assertLess(state.center, 57.5)

        full_recs = _build_healthy_astronaut_stream("ast-01", days=10)
        full_state = engine.fit_signal_context(full_recs, "ast-01", SignalType.RESTING_HR.value, "rest", up_to_day=10)
        self.assertFalse(full_state.cold_start)
        self.assertAlmostEqual(full_state.center, 56.0, delta=2.0)

    def test_F10_context_aware_baselines(self) -> None:
        recs = _build_healthy_astronaut_stream("ast-01", days=16)
        # Day 16 has normal exercise HR ~142; add an abnormal resting HR spike of 92 bpm on Day 16
        recs.append(_make_record("ast-01", 16, 21, SignalType.HEART_RATE.value, 92.0, ["rest"]))
        engine = PersonalBaselineEngine()
        flags = engine.detect_anomalies(recs, "ast-01", up_to_day=16)

        rest_flags = [f for f in flags if f.signal == SignalType.HEART_RATE.value and f.baseline_context == "rest"]
        ex_flags = [f for f in flags if f.signal == SignalType.HEART_RATE.value and f.baseline_context == "exercise"]
        self.assertTrue(any(f.anomaly_type == "contextual" for f in rest_flags))
        self.assertEqual(len(ex_flags), 0)

    def test_F05_guarded_slow_update_freezes_on_drift(self) -> None:
        recs = _build_healthy_astronaut_stream("ast-01", days=12, seed=7)
        # Inject strong persistent RHR elevation Days 13..23 (56 -> 68 bpm)
        for d in range(13, 24):
            recs.append(_make_record("ast-01", d, 7, SignalType.RESTING_HR.value, 68.0, ["rest"]))

        engine = PersonalBaselineEngine()
        state = engine.fit_signal_context(recs, "ast-01", SignalType.RESTING_HR.value, "rest", up_to_day=23)
        self.assertTrue(state.frozen)
        self.assertIn("frozen", state.freeze_reason.lower())
        # Baseline must remain near early-mission 56 bpm, not absorb 68 bpm
        self.assertLess(state.center, 59.0)

    def test_F10_device_step_immunity(self) -> None:
        recs: List[MeasurementRecord] = []
        rng = random.Random(19)
        for d in range(1, 24):
            if d < 14:
                dev, fw, offset = "wristband-v1", "1.0.0", 0.0
            else:
                dev, fw, offset = "wristband-v2", "2.1.0", 12.0
            recs.append(
                _make_record(
                    "ast-01",
                    d,
                    7,
                    SignalType.RESTING_HR.value,
                    58.0 + offset + rng.gauss(0, 0.8),
                    ["rest"],
                    source_device=dev,
                    firmware_version=fw,
                )
            )

        engine = PersonalBaselineEngine()
        step = engine.detect_device_step(recs, "ast-01", SignalType.RESTING_HR.value)
        self.assertTrue(step["detected"])
        self.assertAlmostEqual(step["total_offset"], 12.0, delta=2.0)

        flags = engine.detect_anomalies(recs, "ast-01", up_to_day=23)
        physio_flags = [f for f in flags if f.anomaly_type != "data_fault"]
        self.assertEqual(physio_flags, [])

    def test_F10_cusum_drift_and_multivariate_mahalanobis(self) -> None:
        recs = _build_healthy_astronaut_stream("ast-01", days=14, seed=11)
        # Days 15..23: coordinated physiological strain (RHR up, HRV down, HR recovery down, sleep down)
        for d in range(15, 24):
            shift = d - 14
            recs.append(_make_record("ast-01", d, 7, SignalType.RESTING_HR.value, 56.0 + 0.8 * shift, ["rest"]))
            recs.append(_make_record("ast-01", d, 7, SignalType.HRV_RMSSD.value, 62.0 - 2.3 * shift, ["sleep"]))
            recs.append(_make_record("ast-01", d, 10, SignalType.HR_RECOVERY_1M.value, 35.0 - 1.5 * shift, ["exercise"]))
            recs.append(_make_record("ast-01", d, 7, SignalType.SLEEP_DURATION.value, 7.2 - 0.15 * shift, ["sleep"]))
            recs.append(_make_record("ast-01", d, 7, SignalType.SLEEP_FRAGMENTATION.value, 10.0 + 1.5 * shift, ["sleep"]))
            recs.append(_make_record("ast-01", d, 14, SignalType.PVT_MEAN_RT.value, 248.0 + 3.0 * shift, ["rest"]))

        engine = PersonalBaselineEngine()
        cusum = engine.detect_cusum_drift(recs, "ast-01", SignalType.HRV_RMSSD.value, "sleep", up_to_day=23)
        self.assertTrue(cusum["detected"])
        self.assertEqual(cusum["direction"], "down")

        maha = engine.detect_multivariate_mahalanobis(recs, "ast-01", up_to_day=23)
        self.assertTrue(maha["detected"])
        self.assertGreater(maha["mahalanobis_d2"], maha["threshold_d2"])
        self.assertTrue(len(maha["contributors"]) >= 2)

    def test_F02_F10_dirty_and_missing_routed_to_data_fault_only(self) -> None:
        recs = _build_healthy_astronaut_stream("ast-01", days=20, seed=5)
        # Inject sensor_off, missing, suspect, and out_of_range on Days 21..23
        for d in range(21, 24):
            recs.append(_make_record("ast-01", d, 7, SignalType.HEART_RATE.value, None, ["rest"], quality=QualityState.SENSOR_OFF.value))
            recs.append(_make_record("ast-01", d, 8, SignalType.SPO2.value, None, ["rest"], quality=QualityState.MISSING.value))
            recs.append(_make_record("ast-01", d, 9, SignalType.RESTING_HR.value, 195.0, ["rest"], quality=QualityState.OUT_OF_RANGE.value))
            recs.append(_make_record("ast-01", d, 10, SignalType.HRV_RMSSD.value, 15.0, ["sleep"], quality=QualityState.SUSPECT.value))

        engine = PersonalBaselineEngine()
        flags = engine.detect_anomalies(recs, "ast-01", up_to_day=23)
        self.assertTrue(all(f.anomaly_type == "data_fault" for f in flags))
        self.assertGreaterEqual(len(flags), 3)


class TestReadinessEngine(unittest.TestCase):
    def test_F11_F12_recovery_cognitive_radiation_and_safety_override(self) -> None:
        recs = _build_healthy_astronaut_stream("ast-01", days=15, seed=31)
        # Days 16..23: Elena-like post-exertion recovery decline
        for d in range(16, 24):
            recs.append(_make_record("ast-01", d, 7, SignalType.RESTING_HR.value, 59.0, ["rest"]))
            recs.append(_make_record("ast-01", d, 7, SignalType.HRV_RMSSD.value, 42.8, ["sleep"]))
            recs.append(_make_record("ast-01", d, 10, SignalType.HR_RECOVERY_1M.value, 21.2, ["exercise"]))
            recs.append(_make_record("ast-01", d, 7, SignalType.SLEEP_DURATION.value, 6.4, ["sleep"]))
            recs.append(_make_record("ast-01", d, 14, SignalType.PVT_MEAN_RT.value, 255.0, ["rest"]))
            recs.append(_make_record("ast-01", d, 14, SignalType.PVT_LAPSES.value, 0.0, ["rest"]))
            recs.append(_make_record("ast-01", d, 7, SignalType.SLEEP_FRAGMENTATION.value, 11.0, ["sleep"]))

        res = compute_readiness(recs, "ast-01", up_to_day=23)
        self.assertGreater(res["recovery_debt"]["score"], 45.0)
        self.assertGreater(res["cognitive_readiness"]["score"], 75.0)
        self.assertGreater(res["radiation_trend"]["cumulative_msv"], 7.0)

        # Verify 40/30/20/10 weights exactly
        c = res["components"]
        expected = 0.40 * c["cognitive"] + 0.30 * c["recovery"] + 0.20 * c["environment"] + 0.10 * c["symptoms"]
        self.assertAlmostEqual(res["readiness_score"], round(expected, 1), delta=0.2)

        # Deterministic safety rule overrides band to Safety review
        res_safety = compute_readiness(
            recs,
            "ast-01",
            up_to_day=23,
            active_safety_rules=[{"rule_id": "SR-05", "astronaut_id": "ast-01", "active": True}],
        )
        self.assertEqual(res_safety["band"], "Safety review")
        self.assertTrue(res_safety["safety_active"])

    def test_F12_gap_preserves_state_and_penalizes_confidence(self) -> None:
        clean_recs = _build_healthy_astronaut_stream("ast-02", days=23, seed=41)
        clean_res = compute_readiness(clean_recs, "ast-02", up_to_day=23)

        gapped_recs = list(clean_recs)
        for h in range(0, 9):
            gapped_recs.append(
                _make_record("ast-02", 22, h, SignalType.HEART_RATE.value, None, ["rest"], quality=QualityState.SENSOR_OFF.value)
            )
        gapped_recs.append(
            _make_record("ast-02", 23, 16, SignalType.SPO2.value, None, ["rest"], quality=QualityState.MISSING.value)
        )
        gapped_recs.append(
            _make_record("ast-02", 23, 16, SignalType.SLEEP_DURATION.value, None, ["sleep"], quality=QualityState.SENSOR_OFF.value)
        )
        gapped_res = compute_readiness(gapped_recs, "ast-02", up_to_day=23)

        self.assertTrue(gapped_res["latest_readings"][SignalType.SPO2.value]["is_gap"])
        self.assertIsNone(gapped_res["latest_readings"][SignalType.SPO2.value]["value"])
        self.assertEqual(gapped_res["latest_readings"][SignalType.SPO2.value]["quality"], "missing")
        self.assertLess(
            gapped_res["cognitive_readiness"]["confidence"],
            clean_res["cognitive_readiness"]["confidence"],
        )


class TestEnvironmentAndMSIDE(unittest.TestCase):
    def _build_crew_env_stream(self) -> List[MeasurementRecord]:
        rng = random.Random(77)
        recs: List[MeasurementRecord] = []
        for d in range(1, 24):
            # US Lab CO2 rises sharply Days 14..21, then falls after scrubber service Day 22
            if 14 <= d <= 21:
                lab_co2 = 1200.0 + 480.0 * (d - 13) + (120.0 if d == 19 else 0.0)
            elif d >= 22:
                lab_co2 = 1400.0 - 250.0 * (d - 21)
            else:
                lab_co2 = 860.0 + rng.gauss(0, 20.0)

            for h in (8, 12, 16, 20):
                recs.append(_make_record("habitat", d, h, SignalType.CO2_PPM.value, 830.0 + rng.gauss(0, 12), zone_id="N1"))
                recs.append(_make_record("habitat", d, h, SignalType.CO2_PPM.value, 780.0 + rng.gauss(0, 10), zone_id="CQ"))
                recs.append(_make_record("habitat", d, h, SignalType.CO2_PPM.value, 620.0 + rng.gauss(0, 8), zone_id="AL"))
                if d == 18 and h in (14, 16):
                    recs.append(
                        _make_record("habitat", d, h, SignalType.CO2_PPM.value, None, quality=QualityState.MISSING.value, zone_id="LAB")
                    )
                else:
                    recs.append(_make_record("habitat", d, h, SignalType.CO2_PPM.value, lab_co2, zone_id="LAB"))

            # Crew C (ast-03) and Crew D (ast-04) work in LAB and co-move with LAB CO2
            for aid in ("ast-03", "ast-04"):
                excess = max(0.0, (lab_co2 - 900.0) / 1500.0)
                headache = min(3.0, round(excess * 1.1 + abs(rng.gauss(0, 0.1)), 2))
                fatigue = min(5.0, round(0.5 + excess * 1.6 + abs(rng.gauss(0, 0.1)), 2))
                energy = max(1.0, round(4.2 - excess * 1.1, 2))
                recs.append(_make_record(aid, d, 12, SignalType.HEART_RATE.value, 66.0, ["rest"], zone_id="LAB"))
                recs.append(_make_record(aid, d, 19, SignalType.SYMPTOM_HEADACHE.value, headache, ["rest"], zone_id="LAB"))
                recs.append(_make_record(aid, d, 19, SignalType.SYMPTOM_FATIGUE.value, fatigue, ["rest"], zone_id="LAB"))
                recs.append(_make_record(aid, d, 19, SignalType.ENERGY_SCORE.value, energy, ["rest"], zone_id="LAB"))

            # Crew A (ast-01) and Crew B (ast-02) work in CQ/N1 with steady uncorrelated low symptoms
            for aid, z in (("ast-01", "N1"), ("ast-02", "CQ")):
                recs.append(_make_record(aid, d, 12, SignalType.HEART_RATE.value, 64.0, ["rest"], zone_id=z))
                recs.append(_make_record(aid, d, 19, SignalType.SYMPTOM_HEADACHE.value, 0.0, ["rest"], zone_id=z))
                recs.append(_make_record(aid, d, 19, SignalType.SYMPTOM_FATIGUE.value, 0.8 + rng.uniform(-0.2, 0.2), ["rest"], zone_id=z))
                recs.append(_make_record(aid, d, 19, SignalType.ENERGY_SCORE.value, 3.8 + rng.uniform(-0.2, 0.2), ["rest"], zone_id=z))

            # Planted personal interaction for ast-02: sleep fragmentation -> lower HRV next day
            frag = 10.0 + (25.0 if d >= 14 else 0.0) + rng.gauss(0, 1.5)
            hrv = 65.0 - 0.65 * (frag - 10.0) + rng.gauss(0, 1.2)
            recs.append(_make_record("ast-02", d, 7, SignalType.SLEEP_FRAGMENTATION.value, frag, ["sleep"], zone_id="CQ"))
            recs.append(_make_record("ast-02", d, 7, SignalType.HRV_RMSSD.value, hrv, ["sleep"], zone_id="CQ"))
        return recs

    def test_F13_F18_environment_correlation_anonymized_and_gaps(self) -> None:
        recs = self._build_crew_env_stream()
        env = analyze_crew_environment(recs, up_to_day=23, n_permutations=80, seed=42)

        self.assertEqual(set(env["zones"].keys()), {"N1", "LAB", "CQ", "AL"})
        self.assertTrue(len(env["environmental_gaps"]) >= 1)
        self.assertTrue(env["shared_exposure_alert"]["active"])
        self.assertEqual(env["shared_exposure_alert"]["zone_id"], "LAB")

        corr_by_label = {c["crew_label"]: c for c in env["crew_correlations"]}
        self.assertEqual(set(corr_by_label.keys()), {"Crew A", "Crew B", "Crew C", "Crew D"})
        self.assertTrue(corr_by_label["Crew C"]["linked"])
        self.assertTrue(corr_by_label["Crew D"]["linked"])
        self.assertFalse(corr_by_label["Crew A"]["linked"])
        # Ensure anonymized crew_correlations never exposes astronaut_id or full names
        for c in env["crew_correlations"]:
            self.assertNotIn("astronaut_id", c)
            self.assertNotIn("name", c)
        self.assertTrue(len(env["confounder_flags"]) >= 2)

    def test_F14_mside_positive_and_shuffled_negative_control(self) -> None:
        recs = self._build_crew_env_stream()
        pos = discover_interactions(recs, up_to_day=23, fdr_alpha=0.05, n_permutations=80, seed=42)
        self.assertGreaterEqual(pos["discovery_count"], 2)
        self.assertTrue(len(pos["shared_exposure_findings"]) >= 1)
        self.assertTrue(
            any(
                f["source_signal"] == SignalType.SLEEP_FRAGMENTATION.value
                and f["target_signal"] == SignalType.HRV_RMSSD.value
                for f in pos["personal_findings"]
            )
        )
        # Strictly non-causal wording check
        for finding in pos["findings"]:
            txt = (finding["title"] + " " + finding["summary"]).lower()
            self.assertNotIn("causes", txt)
            self.assertNotIn("caused by", txt)
            self.assertTrue(
                any(w in txt for w in ("co-moving", "follows", "associated with", "co-vary"))
            )

        neg = run_negative_control(recs, seed=42, up_to_day=23, fdr_alpha=0.05, n_permutations=80)
        self.assertTrue(neg["passed"])
        self.assertLessEqual(neg["false_discovery_rate"], 0.05)


class TestBehavioralCounterfactualAdvisor(unittest.TestCase):
    def test_F16_F29_behavioral_layers_underreporting_and_safety(self) -> None:
        recs = _build_healthy_astronaut_stream("ast-02", days=14, seed=9)
        # Days 15..23: strong passive drift (short fragmented sleep, low HRV, low activity)
        # while self-report still looks upbeat (mood=4.3, energy=4.0, stress=2.0)
        for d in range(15, 24):
            recs.append(_make_record("ast-02", d, 7, SignalType.SLEEP_DURATION.value, 5.2, ["sleep"]))
            recs.append(_make_record("ast-02", d, 7, SignalType.SLEEP_FRAGMENTATION.value, 38.0, ["sleep"]))
            recs.append(_make_record("ast-02", d, 7, SignalType.HRV_RMSSD.value, 44.0, ["sleep"]))
            recs.append(_make_record("ast-02", d, 15, SignalType.ACTIVITY_INDEX.value, 0.68, ["rest"]))
            recs.append(_make_record("ast-02", d, 19, SignalType.MOOD_SCORE.value, 4.3, ["rest"]))
            recs.append(_make_record("ast-02", d, 19, SignalType.ENERGY_SCORE.value, 4.0, ["rest"]))
            recs.append(_make_record("ast-02", d, 19, SignalType.STRESS_SCORE.value, 2.0, ["rest"]))

        beh = assess_behavioral_health(recs, astronaut_id="ast-02", up_to_day=23)
        self.assertFalse(beh["fitness_for_duty_computed"])
        self.assertNotIn("fitness_score", beh)
        self.assertTrue(beh["underreporting_mismatch"])
        self.assertTrue(len(beh["mismatch_prompt"]) > 10)
        self.assertIn(beh["status"], {"Watch", "Check-in suggested"})

        # Deterministic safety screen forces Support needed
        beh_safe = assess_behavioral_health(
            recs,
            checkins=[{"astronaut_id": "ast-02", "day": 23, "safety_flag": True, "mood_score": 2}],
            astronaut_id="ast-02",
            up_to_day=23,
        )
        self.assertTrue(beh_safe["safety_triggered"])
        self.assertEqual(beh_safe["status"], "Support needed")

    def test_F15_counterfactual_deltas_and_assumptions(self) -> None:
        readiness_stub = {
            "up_to_day": 23,
            "confidence": 0.90,
            "recovery_debt": {"score": 61.0, "series": [{"day": d, "value": 45.0 + d * 0.5} for d in range(17, 24)]},
            "cognitive_readiness": {"score": 82.0, "series": [{"day": d, "value": 85.0 - (d - 17) * 0.4} for d in range(17, 24)]},
            "latest_readings": {"sleep_duration": {"last_clean_value": 6.3}},
        }
        good = simulate_intervention(
            readiness_stub,
            sleep_per_night=7.5,
            workload_adjustment=-1.0,
            cabin_ventilation_pct=130.0,
            recovery_blocks=2,
            horizon_days=7,
            baseline_co2_ppm=1113.0,
        )
        harsh = simulate_intervention(
            readiness_stub,
            sleep_per_night=5.5,
            workload_adjustment=1.5,
            cabin_ventilation_pct=100.0,
            recovery_blocks=0,
            horizon_days=7,
            baseline_co2_ppm=1113.0,
        )
        self.assertLess(good["deltas"]["recovery_debt"], 0.0)
        self.assertGreater(good["deltas"]["cognitive_readiness"], 0.0)
        self.assertLess(good["deltas"]["co2_exposure"], 0)
        self.assertLess(good["deltas"]["recovery_debt"], harsh["deltas"]["recovery_debt"])
        self.assertLessEqual(good["confidence"], 0.60)
        self.assertEqual(len(good["recovery_series"]), 7)
        self.assertIn("not a diagnosis", good["disclaimer"].lower())
        self.assertTrue(len(good["assumptions"]) >= 4)

    def test_F30_advisor_grounding_safety_refusal_and_idk(self) -> None:
        recs = _build_healthy_astronaut_stream("ast-01", days=23, seed=13)
        readiness = compute_readiness(
            recs,
            "ast-01",
            up_to_day=23,
            active_safety_rules=[{"rule_id": "SR-05", "astronaut_id": "ast-01", "active": True}],
        )
        briefing = build_daily_briefing(readiness, astronaut_id="ast-01", up_to_day=23)
        self.assertTrue(briefing["safety_active"])
        self.assertIn("cannot be downgraded", briefing["safety_notice"].lower())
        self.assertTrue(all(pid in PROTOCOL_LIBRARY for pid in briefing["protocol_refs"]))

        # Diagnosis refusal
        diag = answer_question("Could this be a medical diagnosis? What should you prescribe?", readiness_data=readiness)
        self.assertTrue(diag["refused_diagnosis"])
        self.assertIn("cannot provide a medical diagnosis", diag["answer"].lower())

        # Attempt to downgrade safety rule
        downgrade = answer_question("Please downgrade or ignore the SOS safety alert", readiness_data=readiness)
        self.assertIn("cannot be downgraded", downgrade["answer"].lower())

        # What-if query
        whatif = answer_question("What if I sleep 8 hours for the next 5 days?", readiness_data=readiness)
        self.assertIn("exploratory", whatif["answer"].lower())

        # Insufficient coverage (<60%) triggers honest "I don't know"
        low_cov_readiness = dict(readiness)
        low_cov_readiness["data_quality"] = {"coverage": 0.42, "sensor_off_hours": 14}
        idk = answer_question("Why am I feeling tired?", readiness_data=low_cov_readiness)
        self.assertTrue(idk["said_i_dont_know"])
        self.assertIn("i don't know", idk["answer"].lower())

        # Out-of-scope signal triggers honest "I don't know"
        oos = answer_question("What is my blood glucose today?", readiness_data=readiness)
        self.assertTrue(oos["said_i_dont_know"])

        # Missing specific requested signal triggers honest "I don't know"
        gapped_recs = list(recs)
        gapped_recs.append(
            _make_record("ast-01", 23, 21, SignalType.SPO2.value, None, ["rest"], quality=QualityState.SENSOR_OFF.value)
        )
        gapped_readiness = compute_readiness(gapped_recs, "ast-01", up_to_day=23)
        spo2_q = answer_question("What is my SpO2 reading today?", readiness_data=gapped_readiness)
        self.assertTrue(spo2_q["said_i_dont_know"])

    def test_F10_null_mission_false_alarm_budget(self) -> None:
        engine = PersonalBaselineEngine()
        total_phys_flags = 0
        for idx, crew in enumerate(CREW_ROSTER):
            recs = _build_healthy_astronaut_stream(crew.astronaut_id, days=28, seed=200 + idx)
            for check_day in (14, 21, 28):
                flags = engine.detect_anomalies(recs, crew.astronaut_id, up_to_day=check_day)
                phys = [f for f in flags if f.anomaly_type != "data_fault"]
                total_phys_flags += len(phys)
        # 4 astronauts x 4 weeks = 16 astronaut-weeks; gate requires <= 1.0 false alert / astronaut-week
        false_alerts_per_week = total_phys_flags / 16.0
        self.assertLessEqual(false_alerts_per_week, 1.0)

    def test_F10_device_step_then_subsequent_real_drift(self) -> None:
        recs: List[MeasurementRecord] = []
        for d in range(1, 24):
            if d < 12:
                dev, fw, val = "wristband-v1", "1.0.0", 58.0
            elif d < 18:
                dev, fw, val = "wristband-v2", "2.0.0", 68.0  # +10 bpm hardware step only
            else:
                dev, fw, val = "wristband-v2", "2.0.0", 78.0 + (d - 18) * 1.0  # real +10..+15 bpm drift after step
            recs.append(
                _make_record(
                    "ast-01",
                    d,
                    7,
                    SignalType.RESTING_HR.value,
                    val,
                    ["rest"],
                    source_device=dev,
                    firmware_version=fw,
                )
            )
        engine = PersonalBaselineEngine()
        # Day 16 (after step, before drift): no physiological alert
        flags_pre_drift = [f for f in engine.detect_anomalies(recs, "ast-01", up_to_day=16) if f.anomaly_type != "data_fault"]
        self.assertEqual(flags_pre_drift, [])
        # Day 23 (after real physiological drift): drift IS still detected
        flags_post_drift = [f for f in engine.detect_anomalies(recs, "ast-01", up_to_day=23) if f.anomaly_type == "drift"]
        self.assertTrue(len(flags_post_drift) >= 1)


if __name__ == "__main__":
    unittest.main()
