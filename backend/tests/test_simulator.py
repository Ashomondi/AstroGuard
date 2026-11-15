"""Unit tests for mission simulator, scenario manifest, injectors, and dataset adapters (F-03, F-17, F-41)."""

from __future__ import annotations

import contextlib
import io
import statistics
import unittest

from app.engines.baseline import PersonalBaselineEngine
from app.engines.behavioral import assess_behavioral_health
from app.engines.environment import analyze_crew_environment
from app.eval.adapters import (
    load_dataset_registry,
    load_wearable_fixture,
    summarize_fixture,
)
from app.quality import classify_artifact, summarize_data_quality
from app.schema import QualityState, SignalType
from app.simulator import (
    SCENARIO_BY_ID,
    SCENARIO_MANIFEST,
    generate_mission,
    inject_artifacts,
    inject_device_step,
    inject_missingness,
    main as simulator_main,
)


def _mean_for(records, astronaut_id: str, signal_type: str, start_day: int, end_day: int) -> float:
    vals = [
        float(r.value)
        for r in records
        if r.astronaut_id == astronaut_id
        and r.signal_type == signal_type
        and start_day <= r.day <= end_day
        and r.quality == QualityState.OK.value
        and r.value is not None
    ]
    if not vals:
        raise AssertionError(f"No clean values for {astronaut_id} {signal_type} days {start_day}..{end_day}")
    return statistics.mean(vals)


def _day_hour_record(records, astronaut_id: str, signal_type: str, day: int, hour: int | None = None):
    matches = [
        r
        for r in records
        if r.astronaut_id == astronaut_id
        and r.signal_type == signal_type
        and r.day == day
        and (hour is None or r.hour == hour)
    ]
    if not matches:
        raise AssertionError(f"Missing record for {astronaut_id} {signal_type} day={day} hour={hour}")
    return matches[-1]


class TestSimulatorAndAdapters(unittest.TestCase):
    def test_F03_seed_reproducibility_and_manifest(self) -> None:
        m1 = generate_mission(days=30, seed=42)
        m2 = generate_mission(days=30, seed=42)
        m3 = generate_mission(days=30, seed=99)

        self.assertEqual(len(m1["records"]), len(m2["records"]))
        self.assertEqual([r.to_dict() for r in m1["records"]], [r.to_dict() for r in m2["records"]])
        self.assertNotEqual([r.value for r in m1["records"][:200]], [r.value for r in m3["records"][:200]])

        expected_events = {
            "EV_RECOVERY_DECLINE",
            "MC_COGNITIVE_DRIFT_AND_UNDERREPORTING",
            "SHARED_LAB_CO2_EXPOSURE",
            "SLOW_RADIATION_TREND",
        }
        self.assertEqual({e["event_id"] for e in SCENARIO_MANIFEST}, expected_events)
        self.assertEqual({e["event_id"] for e in m1["manifest"]}, expected_events)

        required_fields = {
            "event_id",
            "target_id",
            "onset_day",
            "peak_day",
            "magnitude",
            "affected_signals",
            "expected_window",
        }
        for entry in SCENARIO_MANIFEST:
            self.assertTrue(required_fields.issubset(entry.keys()))
            self.assertIn(entry["event_id"], SCENARIO_BY_ID)

    def test_F03_day23_elena_recovery_decline(self) -> None:
        mission = generate_mission(days=30, seed=42)
        recs = mission["records"]

        # Baseline Days 1-12
        self.assertAlmostEqual(_mean_for(recs, "ast-01", SignalType.HR_RECOVERY_1M.value, 1, 12), 34.5, delta=0.6)
        self.assertAlmostEqual(_mean_for(recs, "ast-01", SignalType.RESTING_HR.value, 1, 12), 54.9, delta=0.5)
        self.assertAlmostEqual(_mean_for(recs, "ast-01", SignalType.HRV_RMSSD.value, 1, 12), 62.0, delta=0.8)
        self.assertAlmostEqual(_mean_for(recs, "ast-01", SignalType.SLEEP_DURATION.value, 1, 12), 7.0, delta=0.15)
        self.assertAlmostEqual(_mean_for(recs, "ast-01", SignalType.PVT_MEAN_RT.value, 1, 12), 251.1, delta=1.5)

        # Day 23 progressive recovery debt
        hr_rec_23 = _day_hour_record(recs, "ast-01", SignalType.HR_RECOVERY_1M.value, 23).value
        rhr_23 = _day_hour_record(recs, "ast-01", SignalType.RESTING_HR.value, 23).value
        hr_16_23 = _day_hour_record(recs, "ast-01", SignalType.HEART_RATE.value, 23, hour=16).value
        hrv_23 = _day_hour_record(recs, "ast-01", SignalType.HRV_RMSSD.value, 23).value
        sleep_23 = _day_hour_record(recs, "ast-01", SignalType.SLEEP_DURATION.value, 23).value
        pvt_23 = _day_hour_record(recs, "ast-01", SignalType.PVT_MEAN_RT.value, 23).value
        lapses_23 = _day_hour_record(recs, "ast-01", SignalType.PVT_LAPSES.value, 23).value
        spo2_23 = _day_hour_record(recs, "ast-01", SignalType.SPO2.value, 23, hour=16).value
        headache_23 = _day_hour_record(recs, "ast-01", SignalType.SYMPTOM_HEADACHE.value, 23).value

        self.assertAlmostEqual(hr_rec_23, 21.2, delta=0.4)
        self.assertAlmostEqual(rhr_23, 58.2, delta=0.4)
        self.assertAlmostEqual(hr_16_23, 73.0, delta=0.6)
        self.assertAlmostEqual(hrv_23, 42.8, delta=0.6)
        self.assertAlmostEqual(sleep_23, 6.3, delta=0.12)
        self.assertAlmostEqual(pvt_23, 263.0, delta=1.5)
        self.assertEqual(lapses_23, 0.0)
        self.assertAlmostEqual(spo2_23, 97.0, delta=0.6)
        self.assertEqual(headache_23, 0.0)

    def test_F03_day23_marcus_cognitive_drift_underreporting_and_gaps(self) -> None:
        mission = generate_mission(days=30, seed=42)
        recs = mission["records"]

        base_frag = _mean_for(recs, "ast-02", SignalType.SLEEP_FRAGMENTATION.value, 1, 11)
        base_pvt = _mean_for(recs, "ast-02", SignalType.PVT_MEAN_RT.value, 1, 11)
        frag_23 = _day_hour_record(recs, "ast-02", SignalType.SLEEP_FRAGMENTATION.value, 23).value
        pvt_23 = _day_hour_record(recs, "ast-02", SignalType.PVT_MEAN_RT.value, 23).value
        lapses_23 = _day_hour_record(recs, "ast-02", SignalType.PVT_LAPSES.value, 23).value
        act_23 = _day_hour_record(recs, "ast-02", SignalType.ACTIVITY_INDEX.value, 23).value
        mood_23 = _day_hour_record(recs, "ast-02", SignalType.MOOD_SCORE.value, 23).value
        energy_23 = _day_hour_record(recs, "ast-02", SignalType.ENERGY_SCORE.value, 23).value

        self.assertAlmostEqual(frag_23 - base_frag, 30.0, delta=1.5)
        self.assertAlmostEqual(pvt_23 - base_pvt, 74.0, delta=2.5)
        self.assertEqual(lapses_23, 3.0)
        self.assertAlmostEqual(act_23, 0.72, delta=0.03)
        self.assertEqual(mood_23, 4.0)
        self.assertEqual(energy_23, 4.0)

        # Explicit 9h sensor_off gap Day 21 22:00 -> Day 22 07:00
        sensor_off_slots = [
            (r.day, r.hour, r.value, r.quality)
            for r in recs
            if r.astronaut_id == "ast-02"
            and r.signal_type == SignalType.HEART_RATE.value
            and ((r.day == 21 and r.hour >= 22) or (r.day == 22 and r.hour <= 6))
        ]
        self.assertEqual(len(sensor_off_slots), 9)
        for _d, _h, val, qual in sensor_off_slots:
            self.assertIsNone(val)
            self.assertEqual(qual, QualityState.SENSOR_OFF.value)
        resumed = _day_hour_record(recs, "ast-02", SignalType.HEART_RATE.value, 22, hour=7)
        self.assertEqual(resumed.quality, QualityState.OK.value)
        self.assertIsNotNone(resumed.value)

        # Motion noise spike Day 12 16:00
        spike = _day_hour_record(recs, "ast-02", SignalType.HEART_RATE.value, 12, hour=16)
        self.assertEqual(spike.quality, QualityState.SUSPECT.value)

        # Underreporting mismatch & quality summary checks
        behav = assess_behavioral_health(recs, astronaut_id="ast-02", up_to_day=23)
        self.assertTrue(behav["underreporting_mismatch"])
        dq = summarize_data_quality(recs, astronaut_id="ast-02", up_to_day=23)
        self.assertEqual(dq["sensor_off_hours"], 9)
        self.assertEqual(dq["suspect_count"], 1)

    def test_F03_lab_co2_exposure_and_crew_correlation(self) -> None:
        mission = generate_mission(days=30, seed=42)
        recs = mission["records"]

        lab_d19_vals = [
            float(r.value)
            for r in recs
            if r.zone_id == "LAB"
            and r.signal_type == SignalType.CO2_PPM.value
            and r.day == 19
            and r.value is not None
        ]
        self.assertGreaterEqual(max(lab_d19_vals), 5150.0)

        lab_23 = _day_hour_record(recs, "habitat-lab", SignalType.CO2_PPM.value, 23, hour=16).value
        n1_23 = _day_hour_record(recs, "habitat-n1", SignalType.CO2_PPM.value, 23, hour=16).value
        cq_23 = _day_hour_record(recs, "habitat-cq", SignalType.CO2_PPM.value, 23, hour=16).value
        al_23 = _day_hour_record(recs, "habitat-al", SignalType.CO2_PPM.value, 23, hour=16).value
        self.assertAlmostEqual(lab_23, 1113.0, delta=8.0)
        self.assertAlmostEqual(n1_23, 834.0, delta=6.0)
        self.assertAlmostEqual(cq_23, 780.0, delta=6.0)
        self.assertAlmostEqual(al_23, 622.0, delta=6.0)

        lab_7d = [
            float(r.value)
            for r in recs
            if r.zone_id == "LAB"
            and r.signal_type == SignalType.CO2_PPM.value
            and 17 <= r.day <= 23
            and r.quality == QualityState.OK.value
            and r.value is not None
        ]
        self.assertAlmostEqual(statistics.mean(lab_7d), 2062.0, delta=35.0)

        # 2h missing CO2 packet loss Day 18 14:00-15:00
        for h in (14, 15):
            miss = _day_hour_record(recs, "habitat-lab", SignalType.CO2_PPM.value, 18, hour=h)
            self.assertIsNone(miss.value)
            self.assertEqual(miss.quality, QualityState.MISSING.value)

        # Yuki (ast-03 / Crew C) and Omar (ast-04 / Crew D) co-move tightly (r~0.95-0.96, lag 0d)
        env = analyze_crew_environment(recs, up_to_day=23, seed=42)
        self.assertTrue(env["shared_exposure_alert"]["active"])
        self.assertEqual(env["shared_exposure_alert"]["zone_id"], "LAB")
        by_label = {c["crew_label"]: c for c in env["crew_correlations"]}
        self.assertFalse(by_label["Crew A"]["linked"])
        self.assertFalse(by_label["Crew B"]["linked"])
        for label in ("Crew C", "Crew D"):
            self.assertTrue(by_label[label]["linked"])
            self.assertEqual(by_label[label]["lag_days"], 0)
            self.assertGreaterEqual(by_label[label]["r"], 0.92)
            self.assertLessEqual(by_label[label]["r"], 0.98)

    def test_F17_shared_radiation_trend(self) -> None:
        mission = generate_mission(days=30, seed=42)
        recs = mission["records"]
        rad_daily = _day_hour_record(recs, "habitat", SignalType.RADIATION_USV_DAY.value, 23).value
        rad_cum = _day_hour_record(recs, "habitat", SignalType.RADIATION_CUMULATIVE_MSV.value, 23).value
        self.assertAlmostEqual(rad_daily, 505.0, delta=1.0)
        self.assertAlmostEqual(rad_cum, 12.82, delta=0.05)

    def test_F03_F17_null_mission_zero_planted_anomalies(self) -> None:
        null_m = generate_mission(days=30, seed=42, null_mission=True)
        self.assertEqual(null_m["manifest"], [])
        self.assertEqual(null_m["expected_sos"], [])
        nrecs = null_m["records"]

        # No CO2 spike or shared exposure cluster
        lab_max = max(
            float(r.value)
            for r in nrecs
            if r.zone_id == "LAB" and r.signal_type == SignalType.CO2_PPM.value and r.value is not None
        )
        self.assertLess(lab_max, 1100.0)
        env = analyze_crew_environment(nrecs, up_to_day=30, seed=42)
        self.assertFalse(env["shared_exposure_alert"]["active"])

        # Zero non-fault health flags across all 4 astronauts
        engine = PersonalBaselineEngine()
        for aid in ("ast-01", "ast-02", "ast-03", "ast-04"):
            flags = [f for f in engine.detect_anomalies(nrecs, aid, up_to_day=30) if f.anomaly_type != "data_fault"]
            self.assertEqual(flags, [], f"Expected zero false health alerts on null mission for {aid}")

    def test_F17_injectors_and_quality_routing(self) -> None:
        null_m = generate_mission(days=25, seed=7, null_mission=True)
        base_recs = null_m["records"]
        orig_len = len(base_recs)

        # 1. inject_artifacts does not mutate input and routes cleanly to data_fault
        with_spike = inject_artifacts(
            base_recs,
            astronaut_id="ast-01",
            signal_type=SignalType.HEART_RATE.value,
            day=15,
            hour=16,
            artifact_type="motion_spike",
            value=195.0,
        )
        self.assertEqual(len(base_recs), orig_len)
        self.assertEqual(
            _day_hour_record(base_recs, "ast-01", SignalType.HEART_RATE.value, 15, hour=16).quality,
            QualityState.OK.value,
        )
        self.assertEqual(
            _day_hour_record(with_spike, "ast-01", SignalType.HEART_RATE.value, 15, hour=16).quality,
            QualityState.SUSPECT.value,
        )

        with_oor = inject_artifacts(
            base_recs,
            astronaut_id="ast-03",
            signal_type=SignalType.SPO2.value,
            day=10,
            hour=16,
            artifact_type="out_of_range",
            value=115.0,
        )
        faults = classify_artifact(with_oor)
        self.assertTrue(
            any(
                f["anomaly_type"] == "data_fault"
                and f["fault_kind"] == "out_of_range"
                and f["astronaut_id"] == "ast-03"
                and f["day"] == 10
                for f in faults
            )
        )

        # 2. inject_device_step & include_device_step=True
        stepped = inject_device_step(
            base_recs,
            astronaut_id="ast-01",
            signal_type=SignalType.RESTING_HR.value,
            onset_day=14,
            offset=5.0,
            new_firmware="2.5.0",
        )
        engine = PersonalBaselineEngine()
        step_info = engine.detect_device_step(stepped, "ast-01", SignalType.RESTING_HR.value)
        self.assertTrue(step_info["detected"])
        self.assertAlmostEqual(step_info["total_offset"], 5.0, delta=1.2)

        m_step = generate_mission(days=25, seed=42, include_device_step=True)
        self.assertEqual(len(m_step["device_steps"]), 1)
        step_info2 = engine.detect_device_step(m_step["records"], "ast-03", SignalType.RESTING_HR.value)
        self.assertTrue(step_info2["detected"])

        # 3. inject_missingness preserves explicit missing gaps deterministically
        drop_1 = inject_missingness(
            base_recs,
            fraction=0.2,
            seed=42,
            astronaut_id="ast-04",
            signal_types=[SignalType.HEART_RATE.value],
        )
        drop_2 = inject_missingness(
            base_recs,
            fraction=0.2,
            seed=42,
            astronaut_id="ast-04",
            signal_types=[SignalType.HEART_RATE.value],
        )
        ast4_hr_1 = [
            r for r in drop_1 if r.astronaut_id == "ast-04" and r.signal_type == SignalType.HEART_RATE.value
        ]
        ast4_hr_2 = [
            r for r in drop_2 if r.astronaut_id == "ast-04" and r.signal_type == SignalType.HEART_RATE.value
        ]
        self.assertEqual([r.quality for r in ast4_hr_1], [r.quality for r in ast4_hr_2])
        miss_count = sum(1 for r in ast4_hr_1 if r.quality == QualityState.MISSING.value and r.value is None)
        self.assertAlmostEqual(miss_count / len(ast4_hr_1), 0.2, delta=0.02)

    def test_F41_dataset_registry_and_fixture_adapter(self) -> None:
        registry = load_dataset_registry()
        datasets = registry["datasets"]
        names = {d["name"]: d["role"] for d in datasets}
        expected_roles = {
            "WESAD": "signal_priors",
            "Sleep-EDF": "signal_priors",
            "PPG-DaLiA": "signal_priors",
            "LifeSnaps": "signal_priors",
            "NASA OSDR Inspiration4/SOMA": "realism_only",
            "NASA LSDA HERA": "external_validation_if_granted",
        }
        for ds_name, expected_role in expected_roles.items():
            self.assertIn(ds_name, names)
            self.assertEqual(names[ds_name], expected_role)

        fixture_recs = load_wearable_fixture()
        self.assertGreaterEqual(len(fixture_recs), 10)
        summary = summarize_fixture(fixture_recs)
        self.assertGreater(summary["quality_counts"]["ok"], 0)
        self.assertEqual(summary["quality_counts"]["suspect"], 1)
        self.assertEqual(summary["quality_counts"]["sensor_off"], 1)

        off_recs = [r for r in fixture_recs if r.quality == QualityState.SENSOR_OFF.value]
        self.assertIsNone(off_recs[0].value)
        self.assertEqual(off_recs[0].confidence, 0.0)

    def test_F03_cli_summary_execution(self) -> None:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = simulator_main(["--days", "30", "--seed", "42", "--summary"])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("EV_RECOVERY_DECLINE", out)
        self.assertIn("SHARED_LAB_CO2_EXPOSURE", out)
        self.assertIn("12.82 mSv", out)

        buf_null = io.StringIO()
        with contextlib.redirect_stdout(buf_null):
            rc_null = simulator_main(["--days", "15", "--seed", "42", "--null", "--summary"])
        self.assertEqual(rc_null, 0)
        self.assertIn("NONE (null mission)", buf_null.getvalue())


if __name__ == "__main__":
    unittest.main()
