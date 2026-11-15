"""Unit tests for BE-1 foundation modules: quality (F-02), store & sync (F-04), consent (F-26)."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.consent import ConsentManager
from app.quality import (
    classify_artifact,
    normalize_timestamps,
    summarize_data_quality,
    validate_record,
)
from app.schema import (
    ConsentScope,
    MeasurementRecord,
    QualityState,
    Role,
    SignalType,
)
from app.store import AstraStore
from app.sync import PRIORITY_ORDER, SyncManager


def _make_record(
    *,
    astronaut_id: str = "ast-01",
    day: int = 20,
    hour: int = 10,
    signal_type: str = SignalType.HEART_RATE.value,
    value: float | None = 68.0,
    unit: str = "bpm",
    quality: str = QualityState.OK.value,
    confidence: float = 0.98,
    timestamp_utc: str | None = None,
    mission_elapsed_time: float | None = None,
    context_tags: list[str] | None = None,
    zone_id: str = "LAB",
) -> MeasurementRecord:
    ts = timestamp_utc or f"2031-03-{day:02d}T{hour:02d}:00:00Z"
    met = float((day - 1) * 24 + hour) if mission_elapsed_time is None else float(mission_elapsed_time)
    return MeasurementRecord(
        astronaut_id=astronaut_id,
        timestamp_utc=ts,
        mission_elapsed_time=met,
        day=day,
        hour=hour,
        signal_type=signal_type,
        value=value,
        unit=unit,
        source_device="wristband-v2",
        firmware_version="2.4.1",
        quality=quality,
        confidence=confidence,
        context_tags=list(context_tags or ["rest"]),
        consent_scope=ConsentScope.PHYSIO.value,
        zone_id=zone_id,
    )


class TestQualityGateF02(unittest.TestCase):
    def test_F02_validate_record_bounds_states_and_jumps(self) -> None:
        # Normal valid record stays ok
        ok_rec = _make_record(value=72.0)
        res_ok = validate_record(ok_rec, prev_value=68.0)
        self.assertEqual(res_ok.quality, QualityState.OK.value)
        self.assertAlmostEqual(res_ok.confidence, 0.98)

        # Out-of-bounds below and above SAMPLE_PLAUSIBLE_RANGES -> out_of_range
        low_rec = _make_record(value=12.0)
        self.assertEqual(validate_record(low_rec).quality, QualityState.OUT_OF_RANGE.value)
        self.assertEqual(validate_record(low_rec).confidence, 0.0)

        high_rec = _make_record(value=260.0)
        self.assertEqual(validate_record(high_rec).quality, QualityState.OUT_OF_RANGE.value)

        # Preserves sensor_off and missing explicitly
        off_rec = _make_record(value=None, quality=QualityState.SENSOR_OFF.value)
        res_off = validate_record(off_rec, prev_value=68.0)
        self.assertEqual(res_off.quality, QualityState.SENSOR_OFF.value)
        self.assertEqual(res_off.confidence, 0.0)

        miss_rec = _make_record(value=None, quality=QualityState.MISSING.value)
        res_miss = validate_record(miss_rec)
        self.assertEqual(res_miss.quality, QualityState.MISSING.value)
        self.assertEqual(res_miss.confidence, 0.0)

        # Sudden impossible jump -> suspect and down-weighted
        jump_rec = _make_record(value=165.0, context_tags=["rest"])
        res_jump = validate_record(jump_rec, prev_value=65.0)
        self.assertEqual(res_jump.quality, QualityState.SUSPECT.value)
        self.assertLessEqual(res_jump.confidence, 0.35)

        # Exercise-tagged HR step within exercise allowance stays ok
        ex_rec = _make_record(value=145.0, context_tags=["exercise"])
        res_ex = validate_record(ex_rec, prev_value=70.0)
        self.assertEqual(res_ex.quality, QualityState.OK.value)

    def test_F02_classify_artifact_routes_all_faults_to_data_fault(self) -> None:
        records = [
            _make_record(hour=1, value=64.0),
            # Motion impulse spike & return (64 -> 130 -> 65)
            _make_record(hour=2, value=130.0),
            _make_record(hour=3, value=65.0),
            # Sensor off and missing
            _make_record(hour=4, value=None, quality=QualityState.SENSOR_OFF.value),
            _make_record(hour=5, value=None, quality=QualityState.MISSING.value),
            # Out of range
            _make_record(hour=6, value=245.0),
            # Saturated flatline (3 identical readings)
            _make_record(hour=7, value=82.5),
            _make_record(hour=8, value=82.5),
            _make_record(hour=9, value=82.5),
            # Clock jump (timestamp jumps forward 6h while slot moves 1h)
            _make_record(hour=10, value=66.0, timestamp_utc="2031-03-20T16:00:00Z"),
        ]
        faults = classify_artifact(records)
        kinds = {f["fault_kind"] for f in faults}
        self.assertIn("motion_spike", kinds)
        self.assertIn("sensor_off", kinds)
        self.assertIn("missing", kinds)
        self.assertIn("out_of_range", kinds)
        self.assertIn("saturated", kinds)
        self.assertIn("clock_jump", kinds)

        # CRITICAL invariant: every classified artifact uses anomaly_type="data_fault"
        self.assertTrue(all(f["anomaly_type"] == "data_fault" for f in faults))

        # Spo2 at 98.0% or 100.0% and daily resting_hr at 58.0 bpm should NOT falsely trigger saturation
        spo2_clean = [
            _make_record(hour=h, signal_type=SignalType.SPO2.value, value=98.0, unit="%")
            for h in range(1, 5)
        ]
        rhr_clean = [
            _make_record(day=d, hour=7, signal_type=SignalType.RESTING_HR.value, value=58.0, unit="bpm")
            for d in range(1, 4)
        ]
        self.assertEqual(classify_artifact(spo2_clean), [])
        self.assertEqual(classify_artifact(rhr_clean), [])

        # Rail-pinned HR (220.0 twice) DOES trigger saturation
        rail_hr = [_make_record(hour=1, value=220.0), _make_record(hour=2, value=220.0)]
        rail_faults = classify_artifact(rail_hr)
        self.assertTrue(any(f["fault_kind"] == "saturated" for f in rail_faults))

    def test_F02_normalize_timestamps_sorts_and_fixes_minor_jitter_without_imputing(self) -> None:
        out_of_order = [
            _make_record(day=20, hour=12, value=70.0, timestamp_utc="2031-03-20T12:04:10Z"),
            _make_record(day=20, hour=0, value=60.0, timestamp_utc="2031-03-19T23:57:30Z"),
            _make_record(day=20, hour=8, value=64.0, timestamp_utc="2031-03-20T07:56:00Z"),
        ]
        norm = normalize_timestamps(out_of_order)
        # Never fabricates missing hours between 0, 8, 12
        self.assertEqual(len(norm), 3)
        self.assertEqual([(r.day, r.hour) for r in norm], [(20, 0), (20, 8), (20, 12)])
        self.assertEqual(
            [r.timestamp_utc for r in norm],
            [
                "2031-03-20T00:00:00Z",
                "2031-03-20T08:00:00Z",
                "2031-03-20T12:00:00Z",
            ],
        )
        # Clean out-of-order batches do NOT trigger clock_jump
        self.assertEqual(classify_artifact(norm), [])

    def test_F02_summarize_data_quality_gaps_and_confidence(self) -> None:
        # 24 hours on Day 20 for ast-02: 15 ok + 9 sensor_off (08:00..16:00)
        recs = []
        for h in range(24):
            if 8 <= h <= 16:
                recs.append(_make_record(astronaut_id="ast-02", day=20, hour=h, value=None, quality=QualityState.SENSOR_OFF.value))
            else:
                recs.append(_make_record(astronaut_id="ast-02", day=20, hour=h, value=66.0))
        # Add 1 suspect and 1 out_of_range on Day 21
        recs.append(_make_record(astronaut_id="ast-02", day=21, hour=0, value=66.0))
        recs.append(_make_record(astronaut_id="ast-02", day=21, hour=1, value=66.0, quality=QualityState.SUSPECT.value))
        recs.append(_make_record(astronaut_id="ast-02", day=21, hour=2, value=300.0))
        # Future Day 25 record excluded by up_to_day=23
        recs.append(_make_record(astronaut_id="ast-02", day=25, hour=0, value=65.0))

        summary = summarize_data_quality(recs, astronaut_id="ast-02", up_to_day=23)
        self.assertEqual(summary["total_records"], 27)
        self.assertEqual(summary["ok_count"], 16)
        self.assertEqual(summary["sensor_off_hours"], 9)
        self.assertEqual(summary["suspect_count"], 1)
        self.assertEqual(summary["out_of_range_count"], 1)
        self.assertAlmostEqual(summary["coverage_ratio"], 16 / 27, places=3)
        self.assertAlmostEqual(summary["coverage_pct"], round((16 / 27) * 100, 2), places=1)
        self.assertLess(summary["confidence_multiplier"], 1.0)
        self.assertEqual(summary["last_clean_label"], "Day 21 00:00")

        sensor_off_gaps = [g for g in summary["gaps"] if g["state"] == "sensor_off"]
        self.assertEqual(len(sensor_off_gaps), 1)
        gap = sensor_off_gaps[0]
        self.assertEqual(gap["hours"], 9)
        self.assertIn("Day 20 08:00", gap["window"])
        self.assertIn("Day 20 16:00", gap["window"])
        self.assertIn("detail", gap)
        self.assertIn("label", gap)

        # Daily signals (once per day) should not report omitted hourly gaps
        daily_sleep = [
            _make_record(
                astronaut_id="ast-01",
                day=d,
                hour=7,
                signal_type=SignalType.SLEEP_DURATION.value,
                value=7.2,
                unit="h",
            )
            for d in range(1, 10)
        ]
        sleep_summary = summarize_data_quality(daily_sleep, astronaut_id="ast-01", up_to_day=10)
        self.assertEqual(sleep_summary["coverage_pct"], 100.0)
        self.assertEqual(sleep_summary["confidence_multiplier"], 1.0)
        self.assertEqual(sleep_summary["gaps"], [])


class TestStoreAndSyncF04(unittest.TestCase):
    def test_F04_append_only_measurements_and_all_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "astra.db")
            store = AstraStore(db_path)

            # Verify all 9 required tables exist
            tables = {
                row[0]
                for row in store._conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            expected_tables = {
                "measurements",
                "checkins",
                "pvt_tests",
                "sos_events",
                "messages",
                "consent_profiles",
                "access_log",
                "sync_queue",
                "advisor_audit_log",
            }
            self.assertTrue(expected_tables.issubset(tables))

            # Append measurements and query back
            recs = [_make_record(day=20, hour=10, value=68.0), _make_record(day=21, hour=10, value=71.0)]
            self.assertEqual(store.append_measurements(recs), 2)
            fetched = store.get_measurements(astronaut_id="ast-01", signal_type="heart_rate", max_day=20)
            self.assertEqual(len(fetched), 1)
            self.assertEqual(fetched[0].value, 68.0)

            # Enforce SQLite append-only triggers on measurements
            with self.assertRaises(sqlite3.IntegrityError) as upd_err:
                store._conn.execute("UPDATE measurements SET value = 999.0")
            self.assertIn("measurements table is append-only", str(upd_err.exception))

            with self.assertRaises(sqlite3.IntegrityError) as del_err:
                store._conn.execute("DELETE FROM measurements")
            self.assertIn("measurements table is append-only", str(del_err.exception))

            # Check-ins, PVT, SOS, Messages, Consent, Access log, Sync, Advisor log
            chk = store.insert_checkin(astronaut_id="ast-01", day=23, mood_score=3, energy_score=2)
            self.assertEqual(store.get_checkins("ast-01")[0]["checkin_id"], chk["checkin_id"])

            pvt = store.insert_pvt(astronaut_id="ast-02", day=23, mean_rt_ms=312.5, lapses=2)
            self.assertEqual(store.get_pvts("ast-02")[0]["mean_rt_ms"], 312.5)

            sos = store.save_sos(sos_id="sos-01", astronaut_id="ast-01", sos_type="Medical", status="queued", day=23, hour=16)
            self.assertEqual(sos["status"], "queued")
            store.update_sos("sos-01", status="transmitting")
            self.assertEqual(store.get_sos_events("ast-01")[0]["status"], "transmitting")

            msg = store.save_message(message_id="msg-01", sender_id="ast-02", recipient_id="ground", channel="home", urgency="routine", kind="audio", status="queued", duration_s=42)
            self.assertEqual(msg["status"], "queued")
            store.update_message_status("msg-01", "delivered")
            self.assertEqual(store.get_messages("ast-02")[0]["status"], "delivered")

            store.set_consent("ast-01", {"normal": {"physio": True}, "emergency": {"physio": True}})
            self.assertTrue(store.get_consent("ast-01")["normal"]["physio"])

            store.append_access_log(viewer_role="Crew Health Officer", target_astronaut_id="ast-01", scope="physio", allowed=True, reason="briefing")
            self.assertEqual(len(store.get_access_log("ast-01")), 1)

            store.enqueue_sync(item_id="q-1", category="summary", priority=3, payload={"day": 23})
            self.assertEqual(len(store.get_sync_queue()), 1)
            store.update_sync_item("q-1", status="delivered")
            self.assertEqual(store.get_sync_queue()[0]["status"], "delivered")

            store.append_advisor_log(astronaut_id="ast-01", mode="briefing", prompt="summary", response="grounded", citations=["PROT-REC-01"])
            self.assertEqual(store.get_advisor_logs("ast-01")[0]["citations"], ["PROT-REC-01"])

            store.close()

            # Re-open from disk and confirm durability
            reopened = AstraStore(db_path)
            self.assertEqual(len(reopened.get_measurements(astronaut_id="ast-01")), 2)
            self.assertEqual(reopened.get_sos_events("ast-01")[0]["status"], "transmitting")
            reopened.close()

    def test_F04_sync_manager_priority_offline_and_state_progression(self) -> None:
        self.assertEqual(
            PRIORITY_ORDER,
            {"sos": 0, "critical_alert": 1, "message": 2, "summary": 3, "telemetry": 4},
        )
        store = AstraStore(":memory:")
        sync = SyncManager(store)
        self.assertFalse(sync.online)

        # Save linked SOS & Message records
        store.save_sos(sos_id="sos-ev-23", astronaut_id="ast-01", sos_type="Medical", status="queued", day=23, hour=16)
        store.save_message(message_id="msg-mc-23", sender_id="ast-02", recipient_id="home", channel="home", kind="audio", status="queued")

        # Enqueue out of priority order (telemetry first, SOS last)
        sync.enqueue("telemetry", {"records": 24}, item_id="item-tel")
        sync.enqueue("summary", {"day": 23}, item_id="item-sum")
        sync.enqueue("message", {"message_id": "msg-mc-23"}, item_id="item-msg")
        sync.enqueue("critical_alert", {"rule": "SR-03"}, item_id="item-crit")
        sync.enqueue("sos", {"sos_id": "sos-ev-23"}, item_id="item-sos")

        # Offline: fast_forward_sync preserves queued items
        offline_res = sync.fast_forward_sync()
        self.assertFalse(offline_res["online"])
        self.assertEqual(offline_res["processed_count"], 0)
        self.assertTrue(all(x["status"] == "queued" for x in sync.list_queue()))

        # Queue sorted strictly by (priority, created_at)
        ordered_cats = [x["category"] for x in sync.list_queue()]
        self.assertEqual(ordered_cats, ["sos", "critical_alert", "message", "summary", "telemetry"])

        # Go online and fast-forward
        sync.set_link_status(True)
        res = sync.fast_forward_sync()
        self.assertTrue(res["online"])
        self.assertEqual(res["processed_count"], 5)

        # Verify strict priority order in transitions and full state progression per item
        transitions = res["transitions"]
        item_order = []
        for t in transitions:
            if not item_order or item_order[-1] != t["item_id"]:
                item_order.append(t["item_id"])
        self.assertEqual(item_order, ["item-sos", "item-crit", "item-msg", "item-sum", "item-tel"])

        for item_id in item_order:
            seq = [(t["from_status"], t["to_status"]) for t in transitions if t["item_id"] == item_id]
            self.assertEqual(
                seq,
                [
                    ("queued", "transmitting"),
                    ("transmitting", "delivered"),
                    ("delivered", "acknowledged"),
                ],
            )

        # Verify linked SOS and Message rows updated in AstraStore
        self.assertEqual(store.get_sos_events("ast-01")[0]["status"], "acknowledged")
        self.assertEqual(store.get_messages("ast-02")[0]["status"], "delivered")
        self.assertEqual(store.get_messages("ast-02")[0]["sync_status"], "acknowledged")

        # Cancelled SOS must remain cancelled even if sync runs
        store.save_sos(sos_id="sos-cancelled", astronaut_id="ast-04", sos_type="Environment", status="cancelled")
        sync.enqueue("sos", {"sos_id": "sos-cancelled"}, item_id="item-sos-cancel")
        sync.fast_forward_sync()
        self.assertEqual(store.get_sos_events("ast-04")[0]["status"], "cancelled")

        with self.assertRaises(ValueError):
            sync.enqueue("unknown_bucket", {})


class TestConsentAndAccessF26(unittest.TestCase):
    def test_F26_default_crew_matrix_and_updates(self) -> None:
        store = AstraStore(":memory:")
        consent = ConsentManager(store)
        matrix = consent.get_consent_matrix()

        self.assertEqual(set(matrix.keys()), {"ast-01", "ast-02", "ast-03", "ast-04"})
        # ast-01 Elena & ast-04 Omar all ON
        self.assertTrue(all(matrix["ast-01"]["normal"].values()))
        self.assertTrue(all(matrix["ast-04"]["normal"].values()))
        # ast-02 Marcus behaviour=False, emergency behaviour=False, ground_sharing=False
        self.assertFalse(matrix["ast-02"]["normal"]["behaviour"])
        self.assertFalse(matrix["ast-02"]["emergency"]["behaviour"])
        self.assertFalse(matrix["ast-02"]["normal"]["ground_sharing"])
        # ast-03 Yuki cognitive=False, emergency cognitive=True
        self.assertFalse(matrix["ast-03"]["normal"]["cognitive"])
        self.assertTrue(matrix["ast-03"]["emergency"]["cognitive"])

        # Update profile and confirm persistence across new ConsentManager instance
        consent.update_profile("ast-03", normal_updates={"cognitive": True})
        reloaded = ConsentManager(store)
        self.assertTrue(reloaded.get_profile("ast-03")["normal"]["cognitive"])

        with self.assertRaises(ValueError):
            consent.update_profile("ast-03", normal_updates={"invalid_scope": True})
        with self.assertRaises(ValueError):
            consent.get_profile("ast-99")

    def test_F26_access_enforcement_override_redaction_and_logging(self) -> None:
        store = AstraStore(":memory:")
        consent = ConsentManager(store)

        # 1. Health Officer blocked from Yuki cognitive normally, allowed during active critical rule
        norm_check = consent.check_access(
            Role.HEALTH_OFFICER.value, "ast-03", ConsentScope.COGNITIVE.value, active_critical_rule=False
        )
        self.assertFalse(norm_check["allowed"])
        self.assertFalse(norm_check["override_used"])

        emerg_check = consent.check_access(
            Role.HEALTH_OFFICER.value,
            "ast-03",
            ConsentScope.COGNITIVE.value,
            active_critical_rule=True,
            reason="SR-05 SOS active",
        )
        self.assertTrue(emerg_check["allowed"])
        self.assertTrue(emerg_check["override_used"])
        self.assertIsNotNone(emerg_check["override_expires_at"])

        # 2. Health Officer still blocked from Marcus behaviour even in emergency
        marcus_beh_emerg = consent.check_access(
            Role.HEALTH_OFFICER.value, "ast-02", ConsentScope.BEHAVIOUR.value, active_critical_rule=True
        )
        self.assertFalse(marcus_beh_emerg["allowed"])
        self.assertFalse(marcus_beh_emerg["override_used"])

        # 3. Behavioral data NEVER allowed for fitness-for-duty even when behaviour=True (Elena)
        fitness_check = consent.check_access(
            Role.HEALTH_OFFICER.value,
            "ast-01",
            ConsentScope.BEHAVIOUR.value,
            reason="fitness-for-duty evaluation",
        )
        self.assertFalse(fitness_check["allowed"])

        # 4. Astronaut owns own data, cannot read another astronaut's personal data
        self.assertTrue(
            consent.check_access(Role.ASTRONAUT.value, "ast-02", "behaviour", viewer_id="ast-02")["allowed"]
        )
        self.assertFalse(
            consent.check_access(Role.ASTRONAUT.value, "ast-02", "physio", viewer_id="ast-01")["allowed"]
        )

        # 5. Systems Engineer sees habitat only, anonymized
        sys_redacted = consent.redact_for_role(
            Role.SYSTEMS_ENGINEER.value,
            "ast-03",
            {
                "physio": {"astronaut_id": "ast-03", "hr": 68},
                "habitat": {"astronaut_id": "ast-03", "zone": "LAB", "co2_ppm": 5120},
            },
        )
        self.assertEqual(sys_redacted["astronaut_id"], "Crew C")
        self.assertIn("physio", sys_redacted["redacted_scopes"])
        self.assertNotIn("physio", sys_redacted["data"])
        self.assertEqual(sys_redacted["data"]["habitat"]["astronaut_id"], "Crew C")

        # 6. Ground Support cannot access raw physio, and respects ground_sharing=False for Marcus
        gnd_marcus = consent.redact_for_role(
            Role.GROUND_SUPPORT.value,
            "ast-02",
            {
                "physio": {"hr": 65},
                "ground_sharing": {"summary_band": "Watch"},
                "habitat": {"zone": "CQ", "co2_ppm": 790},
            },
        )
        self.assertIn("physio", gnd_marcus["redacted_scopes"])
        self.assertIn("ground_sharing", gnd_marcus["redacted_scopes"])
        self.assertIn("habitat", gnd_marcus["data"])

        # 7. Every single check logged to store.access_log
        logs = store.get_access_log()
        self.assertGreaterEqual(len(logs), 11)
        yuki_logs = store.get_access_log(astronaut_id="ast-03")
        self.assertEqual(len(yuki_logs), 4)
        self.assertTrue(any(entry["override_used"] and entry["allowed"] for entry in yuki_logs))


if __name__ == "__main__":
    unittest.main()
