"""Tests for Deterministic Safety Rules, Standalone SOS, Opaque Messaging & Alert Policy (F-20, F-21, F-27, F-28, F-31, F-32)."""

from __future__ import annotations

import ast
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from app.consent import ConsentManager
from app.engines.alerts import AlertPolicyEngine
from app.messaging import CONTENT_ANALYSIS_ENABLED, MessagingService
from app.safety import evaluate_safety_rules
from app.schema import AnomalyFlag, MeasurementRecord, QualityState, SignalType
from app.simulator import generate_mission
from app.sos import SOSService
from app.store import AstraStore
from app.sync import SyncManager

APP_DIR = Path(__file__).resolve().parents[1] / "app"


def _make_record(
    astronaut_id: str = "ast-01",
    day: int = 23,
    hour: int = 16,
    signal_type: str = SignalType.SPO2.value,
    value: float | None = 97.0,
    quality: str = QualityState.OK.value,
    zone_id: str = "LAB",
    context_tags: list[str] | None = None,
) -> MeasurementRecord:
    return MeasurementRecord(
        astronaut_id=astronaut_id,
        timestamp_utc=f"2031-03-{day:02d}T{hour:02d}:00:00Z",
        mission_elapsed_time=float((day - 1) * 24 + hour),
        day=day,
        hour=hour,
        signal_type=signal_type,
        value=value,
        unit="unit",
        source_device="test-sensor",
        firmware_version="1.0.0",
        quality=quality,
        confidence=1.0 if quality == QualityState.OK.value else 0.2,
        context_tags=context_tags or ["rest"],
        zone_id=zone_id,
    )


def _make_flag(
    signal: str = "hrv_rmssd",
    anomaly_type: str = "drift",
    score: float = 2.9,
    confidence: float = 0.88,
    astronaut_id: str = "ast-01",
    day: int = 23,
    protocol_refs: list[str] | None = None,
) -> AnomalyFlag:
    return AnomalyFlag(
        signal=signal,
        window=[f"Day {max(1, day - 3)} 16:00", f"Day {day} 16:00"],
        anomaly_type=anomaly_type,
        score=score,
        confidence=confidence,
        baseline_context="sleep",
        personal_range=[55.0, 68.0],
        observed=42.8,
        contributors=[signal],
        data_quality={"coverage": 0.99, "sensor_off_hours": 0},
        evidence_ref=f"ev-{astronaut_id}-{signal}-{anomaly_type}-d{day}",
        protocol_refs=protocol_refs if protocol_refs is not None else ["PROT-REC-01"],
        astronaut_id=astronaut_id,
        day=day,
    )


def _extract_imported_modules(py_path: Path) -> set[str]:
    tree = ast.parse(py_path.read_text(encoding="utf-8"), filename=str(py_path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
    return imported


class TestModuleIsolationAndSafety(unittest.TestCase):
    def test_F27_F31_zero_engine_or_advisor_imports_in_safety_and_sos(self) -> None:
        forbidden_tokens = ("engines", "advisor", "simulator")
        for filename in ("safety.py", "sos.py"):
            mods = _extract_imported_modules(APP_DIR / filename)
            for mod in mods:
                for token in forbidden_tokens:
                    self.assertNotIn(
                        token,
                        mod.lower(),
                        f"{filename} must never import {mod} (contains {token})",
                    )

        msg_mods = _extract_imported_modules(APP_DIR / "messaging.py")
        for mod in msg_mods:
            for token in ("engines", "behavioral", "advisor", "simulator"):
                self.assertNotIn(token, mod.lower())
        self.assertFalse(CONTENT_ANALYSIS_ENABLED)

    def test_F27_safety_rules_deterministic_and_sr01_critical_vitals(self) -> None:
        # Clean critical SpO2 (< 90%) and clean resting_hr (> 130)
        recs = [
            _make_record(astronaut_id="ast-01", day=23, signal_type=SignalType.SPO2.value, value=88.5),
            _make_record(astronaut_id="ast-02", day=23, signal_type=SignalType.RESTING_HR.value, value=134.0),
            # Exact boundaries must NOT trigger
            _make_record(astronaut_id="ast-03", day=23, signal_type=SignalType.SPO2.value, value=90.0),
            _make_record(astronaut_id="ast-03", day=23, signal_type=SignalType.RESTING_HR.value, value=130.0),
            # Suspect / out_of_range artifacts must NOT trigger SR-01
            _make_record(
                astronaut_id="ast-04",
                day=23,
                signal_type=SignalType.SPO2.value,
                value=72.0,
                quality=QualityState.SUSPECT.value,
            ),
            _make_record(
                astronaut_id="ast-04",
                day=23,
                signal_type=SignalType.RESTING_HR.value,
                value=155.0,
                quality=QualityState.OUT_OF_RANGE.value,
            ),
        ]
        res1 = evaluate_safety_rules(recs, up_to_day=23)
        res2 = evaluate_safety_rules(recs, up_to_day=23)
        self.assertEqual(res1, res2)

        sr01 = [r for r in res1 if r["rule_id"] == "SR-01"]
        self.assertEqual({r["astronaut_id"] for r in sr01}, {"ast-01", "ast-02"})
        for rule in sr01:
            self.assertTrue(rule["active"])
            self.assertTrue(rule["deterministic"])
            self.assertTrue(rule["cannot_downgrade"])
            self.assertEqual(rule["severity"], "critical")
            for key in (
                "rule_id",
                "title",
                "severity",
                "active",
                "deterministic",
                "cannot_downgrade",
                "summary",
                "protocol_refs",
                "day",
                "timestamp",
            ):
                self.assertIn(key, rule)

    def test_F27_sr02_pvt_lapses_and_acute_collapse(self) -> None:
        recs = [
            _make_record(astronaut_id="ast-02", day=23, signal_type=SignalType.PVT_LAPSES.value, value=8.0),
            _make_record(astronaut_id="ast-03", day=23, signal_type=SignalType.PVT_LAPSES.value, value=7.0),
            _make_record(
                astronaut_id="ast-04",
                day=23,
                signal_type=SignalType.HEART_RATE.value,
                value=55.0,
                context_tags=["acute_collapse"],
            ),
        ]
        rules = evaluate_safety_rules(recs, up_to_day=23)
        sr02 = [r for r in rules if r["rule_id"] == "SR-02"]
        self.assertEqual({r["astronaut_id"] for r in sr02}, {"ast-02", "ast-04"})
        self.assertTrue(all(r["active"] for r in sr02))

    def test_F27_sr03_co2_active_vs_historical_day19_exceedance(self) -> None:
        recs = [
            _make_record(astronaut_id="env", day=18, hour=14, signal_type=SignalType.CO2_PPM.value, value=3200.0, zone_id="LAB"),
            _make_record(astronaut_id="env", day=19, hour=15, signal_type=SignalType.CO2_PPM.value, value=5230.0, zone_id="LAB"),
            _make_record(astronaut_id="env", day=19, hour=16, signal_type=SignalType.CO2_PPM.value, value=5210.0, zone_id="LAB"),
            _make_record(astronaut_id="env", day=23, hour=16, signal_type=SignalType.CO2_PPM.value, value=1113.0, zone_id="LAB"),
            # Suspect spike in N1 must NOT trigger SR-03
            _make_record(
                astronaut_id="env",
                day=23,
                hour=16,
                signal_type=SignalType.CO2_PPM.value,
                value=6500.0,
                quality=QualityState.SUSPECT.value,
                zone_id="N1",
            ),
        ]

        rules_d19 = evaluate_safety_rules(recs, up_to_day=19)
        sr03_d19 = [r for r in rules_d19 if r["rule_id"] == "SR-03"]
        self.assertEqual(len(sr03_d19), 1)
        self.assertTrue(sr03_d19[0]["active"])
        self.assertEqual(sr03_d19[0]["zone_id"], "LAB")
        self.assertEqual(sr03_d19[0]["day"], 19)

        rules_d23 = evaluate_safety_rules(recs, up_to_day=23)
        sr03_d23 = [r for r in rules_d23 if r["rule_id"] == "SR-03"]
        self.assertEqual(len(sr03_d23), 1)
        self.assertFalse(sr03_d23[0]["active"])
        self.assertEqual(sr03_d23[0]["status"], "historical")
        self.assertEqual(sr03_d23[0]["day"], 19)
        self.assertIn("Historical Day 19", sr03_d23[0]["summary"])

    def test_F27_sr04_behavioral_safety_and_private_journal_isolation(self) -> None:
        # Private journal/message keys must NEVER trigger SR-04
        ignored_checkins = [
            {
                "astronaut_id": "ast-02",
                "day": 23,
                "private_journal": "I feel hopeless and want to hurt myself",
                "message_body": "suicidal thoughts",
            }
        ]
        self.assertEqual(
            [r for r in evaluate_safety_rules([], checkins=ignored_checkins, up_to_day=23) if r["rule_id"] == "SR-04"],
            [],
        )

        # Structured check-in crisis text or flag MUST trigger SR-04
        crisis_checkins = [
            {
                "astronaut_id": "ast-02",
                "day": 23,
                "hour": 16,
                "safety_response": "I am having thoughts of self-harm today.",
            },
            {
                "astronaut_id": "ast-04",
                "day": 23,
                "hour": 16,
                "safety_flag": True,
            },
        ]
        rules = evaluate_safety_rules([], checkins=crisis_checkins, up_to_day=23)
        sr04 = [r for r in rules if r["rule_id"] == "SR-04"]
        self.assertEqual({r["astronaut_id"] for r in sr04}, {"ast-02", "ast-04"})
        for rule in sr04:
            self.assertTrue(rule["active"])
            self.assertTrue(rule["cannot_downgrade"])
            self.assertIn("human", rule["human_contact_prompt"].lower())
            self.assertIn("PROT-MED-01", rule["protocol_refs"])

    def test_F27_sr05_active_vs_cancelled_sos(self) -> None:
        sos_events = [
            {"sos_id": "sos-1", "astronaut_id": "ast-01", "sos_type": "Medical", "status": "queued", "day": 23, "hour": 14},
            {"sos_id": "sos-2", "astronaut_id": "ast-02", "sos_type": "Habitat hazard", "status": "cancelled", "day": 23, "hour": 15},
            {"sos_id": "sos-future", "astronaut_id": "ast-03", "sos_type": "Medical", "status": "queued", "day": 25, "hour": 10},
        ]
        rules = evaluate_safety_rules([], sos_events=sos_events, up_to_day=23)
        sr05 = [r for r in rules if r["rule_id"] == "SR-05"]
        self.assertEqual(len(sr05), 1)
        self.assertEqual(sr05[0]["sos_id"], "sos-1")
        self.assertTrue(sr05[0]["active"])


class TestSOSAndMessaging(unittest.TestCase):
    def setUp(self) -> None:
        self.store = AstraStore(":memory:")
        self.consent = ConsentManager(self.store)
        self.sync = SyncManager(self.store, online=False)
        self.sos = SOSService(self.store, self.consent, self.sync)
        self.msg = MessagingService(self.store, self.consent, self.sync)

    def tearDown(self) -> None:
        self.store.close()

    def test_F31_sos_validation_p0_queue_ack_cancel_and_sync(self) -> None:
        with self.assertRaises(ValueError):
            self.sos.trigger_sos("ast-01", sos_type="InvalidCategory")

        # Enqueue a priority 2 message first to verify SOS jumps ahead at P0
        self.msg.send_message("ast-01", "Home (Earth)", "Routine check-in", priority="routine")

        packet = self.sos.trigger_sos(
            astronaut_id="ast-01",
            sos_type="Medical",
            note="Unusually winded after exercise block.",
            day=23,
            hour=14,
            vitals_snapshot={"hr": 73, "spo2": 97},
            env_snapshot={"zone_id": "LAB", "co2_ppm": 1113},
        )
        self.assertEqual(packet["state"], "queued")
        self.assertEqual(packet["cancel_window_sec"], 10)
        self.assertFalse(packet["acknowledged_on_board"])

        # Priority 0 SOS sits ahead of Priority 2 message in sync queue
        queue = self.sync.list_queue()
        self.assertEqual(queue[0]["category"], "sos")
        self.assertEqual(queue[0]["priority"], 0)
        self.assertEqual(queue[1]["category"], "message")
        self.assertEqual(queue[1]["priority"], 2)

        # Emergency override access log recorded
        logs = self.store.get_access_log(astronaut_id="ast-01")
        self.assertTrue(any(entry["active_critical_rule"] and "SOS" in entry["reason"] for entry in logs))

        # On-board acknowledgement keeps Earth delivery state queued while offline
        acked = self.sos.acknowledge_sos(packet["sos_id"], actor="Crew Health Officer")
        self.assertTrue(acked["acknowledged_on_board"])
        self.assertEqual(acked["state"], "queued")

        # SR-05 fires on active un-cancelled SOS
        sr05_active = evaluate_safety_rules([], sos_events=self.sos.list_sos(), up_to_day=23)
        self.assertEqual(len(sr05_active), 1)

        # Trigger & cancel a second Behavioral support SOS
        false_alarm = self.sos.trigger_sos("ast-02", sos_type="Behavioral support", note="Accidental hold")
        cancelled = self.sos.cancel_sos(false_alarm["sos_id"], reason="false_alarm")
        self.assertEqual(cancelled["state"], "cancelled")
        self.assertFalse(cancelled["override_active"])

        # SR-05 still only sees the un-cancelled Medical SOS
        sr05_after_cancel = evaluate_safety_rules([], sos_events=self.sos.list_sos(), up_to_day=23)
        self.assertEqual(len(sr05_after_cancel), 1)
        self.assertEqual(sr05_after_cancel[0]["sos_id"], packet["sos_id"])

        # When Earth link comes online, fast_forward_sync delivers & acknowledges un-cancelled SOS
        self.sync.set_link_status(True)
        self.sync.fast_forward_sync()
        listed = {item["sos_id"]: item for item in self.sos.list_sos()}
        self.assertEqual(listed[packet["sos_id"]]["state"], "acknowledged")
        self.assertEqual(listed[false_alarm["sos_id"]]["state"], "cancelled")

    def test_F32_messaging_consent_bandwidth_opaque_and_filtering(self) -> None:
        # ast-02 has ground_sharing=False by default -> attaching chart to Home (Earth) must be rejected
        with self.assertRaises(PermissionError):
            self.msg.send_message(
                sender_id="ast-02",
                recipient="Home (Earth)",
                body="Sending my chart",
                attach_health_chart=True,
            )

        # ast-01 has ground_sharing=True -> attaching chart succeeds with 2.4 kbps bandwidth warning
        earth_chart = self.msg.send_message(
            sender_id="ast-01",
            recipient="Home (Earth)",
            body="Attaching 7-day recovery chart. Also feeling overwhelmed / self-harm test string.",
            msg_type="text",
            priority="routine",
            attach_health_chart=True,
        )
        self.assertEqual(earth_chart["status"], "queued")
        self.assertTrue(earth_chart["bandwidth_warning"])
        self.assertIn("2.4 kbps", earth_chart["bandwidth_warning_text"])
        self.assertFalse(earth_chart["content_analyzed"])

        # Plain text to Home (Earth) has no bandwidth warning
        earth_text = self.msg.send_message(
            sender_id="ast-01",
            recipient="Home (Earth)",
            body="Nominal station update.",
            msg_type="text",
        )
        self.assertFalse(earth_text["bandwidth_warning"])

        # Audio clip to Home (Earth) triggers bandwidth warning
        earth_audio = self.msg.send_message(
            sender_id="ast-01",
            recipient="Home (Earth)",
            body="Voice note metadata",
            msg_type="audio",
            audio_duration_sec=30,
        )
        self.assertTrue(earth_audio["bandwidth_warning"])
        self.assertIn("2.4 kbps", earth_audio["bandwidth_warning_text"])

        # On-board crew message delivers immediately and is NOT queued for Earth sync
        crew_msg = self.msg.send_message(
            sender_id="ast-02",
            recipient="ast-01",
            body="Sleep was broken again.",
            msg_type="text",
        )
        self.assertEqual(crew_msg["status"], "delivered")
        self.assertFalse(crew_msg["bandwidth_warning"])

        # Private crew message between ast-03 and ast-04 should not leak to ast-01
        self.msg.send_message(sender_id="ast-03", recipient="ast-04", body="Lab filter swap done.")

        all_ast01 = self.msg.list_messages(filter_scope="All", astronaut_id="ast-01")
        self.assertEqual(len(all_ast01), 4)
        earth_ast01 = self.msg.list_messages(filter_scope="Earth", astronaut_id="ast-01")
        self.assertEqual(len(earth_ast01), 3)
        crew_ast01 = self.msg.list_messages(filter_scope="Crew", astronaut_id="ast-01")
        self.assertEqual(len(crew_ast01), 1)

        read_msg = self.msg.mark_read(crew_msg["message_id"])
        self.assertEqual(read_msg["status"], "read")


class TestAlertPolicyEngine(unittest.TestCase):
    def test_F20_F21_F28_data_fault_filtering_confidence_cooldown_budget_and_safety_bypass(self) -> None:
        engine = AlertPolicyEngine(weekly_budget=3, cooldown_days=2, min_confidence=0.65)

        flags = [
            # Data fault must NEVER raise a health alert
            _make_flag(signal="heart_rate", anomaly_type="data_fault", score=9.0, confidence=0.95, day=23),
            # Below confidence floor (0.64 < 0.65)
            _make_flag(signal="sleep_duration", anomaly_type="contextual", score=3.1, confidence=0.64, day=23),
            # Cooldown pair on same signal (Day 21 + Day 22 <= 2 days) -> Day 22 suppressed
            _make_flag(signal="hrv_rmssd", anomaly_type="drift", score=2.9, confidence=0.89, day=21),
            _make_flag(signal="hrv_rmssd", anomaly_type="drift", score=3.2, confidence=0.91, day=22),
            # Distinct signals competing for weekly_budget=3 on ast-01
            _make_flag(signal="hr_recovery_1m", anomaly_type="drift", score=3.4, confidence=0.94, day=23, protocol_refs=["PROT-REC-01", "PROT-REC-02"]),
            _make_flag(signal="multivariate_cluster", anomaly_type="multivariate", score=3.8, confidence=0.92, day=23, protocol_refs=["PROT-REC-01", "PROT-SLP-01"]),
            _make_flag(signal="resting_hr", anomaly_type="contextual", score=2.1, confidence=0.80, day=23, protocol_refs=["PROT-REC-02"]),
            _make_flag(signal="symptom_fatigue", anomaly_type="contextual", score=1.8, confidence=0.75, day=23, protocol_refs=["PROT-ENV-02"]),
        ]

        safety_rules = [
            {
                "rule_id": "SR-05",
                "title": "SOS — Medical",
                "severity": "critical",
                "active": True,
                "deterministic": True,
                "cannot_downgrade": True,
                "summary": "ast-01 active Medical SOS beacon on Day 23.",
                "protocol_refs": ["PROT-MED-01"],
                "day": 23,
                "timestamp": "2031-03-23T14:20:00Z",
            },
            {
                "rule_id": "SR-03",
                "title": "Hazardous cabin CO2 in US Lab",
                "severity": "critical",
                "active": False,
                "deterministic": True,
                "cannot_downgrade": True,
                "summary": "Historical Day 19 CO2 exceedance in LAB.",
                "protocol_refs": ["PROT-ENV-01", "PROT-ENV-02"],
                "day": 19,
                "timestamp": "2031-03-19T15:00:00Z",
            },
        ]

        result = engine.evaluate_alerts(flags, safety_rules, up_to_day=23)

        # Data fault excluded from active_alerts and routed to data_quality_notices
        self.assertEqual(len(result["data_quality_notices"]), 1)
        self.assertTrue(all(a["anomaly_type"] != "data_fault" for a in result["active_alerts"]))

        # Weekly budget caps ast-01 advisory alerts at 3 (from 5 post-cooldown candidates)
        self.assertEqual(len(result["active_alerts"]), 3)
        # Suppressed: 1 low confidence + 1 cooldown + 2 budget overflow = 4
        self.assertEqual(result["suppressed_grouped_count"], 4)
        self.assertEqual(result["budget_status"]["suppressed_by_reason"]["low_confidence"], 1)
        self.assertEqual(result["budget_status"]["suppressed_by_reason"]["cooldown"], 1)
        self.assertEqual(result["budget_status"]["suppressed_by_reason"]["weekly_budget"], 2)

        # Surviving alerts contain Why Card and protocols
        for alert in result["active_alerts"]:
            self.assertIn("why_card", alert)
            self.assertIn("what_changed", alert["why_card"])
            self.assertIn("how_sure_and_why", alert["why_card"])
            self.assertIn("single_best_next_step", alert["why_card"])
            self.assertGreater(len(alert["protocols"]), 0)

        # Active safety rule bypassed budget; historical SR-03 separated cleanly
        self.assertEqual(len(result["safety_alerts"]), 1)
        self.assertEqual(result["safety_alerts"][0]["rule_id"], "SR-05")
        self.assertTrue(result["safety_alerts"][0]["bypassed_budget"])
        self.assertEqual(len(result["historical_safety_alerts"]), 1)

        # Even with weekly_budget=0, deterministic safety_rules STILL fire
        zero_budget = AlertPolicyEngine(weekly_budget=0, cooldown_days=10, min_confidence=0.99)
        zero_res = zero_budget.evaluate_alerts(flags, safety_rules, up_to_day=23)
        self.assertEqual(len(zero_res["active_alerts"]), 0)
        self.assertEqual(len(zero_res["safety_alerts"]), 1)
        self.assertEqual(zero_res["safety_alerts"][0]["rule_id"], "SR-05")

    def test_F28_cooldown_expiry_same_day_grouping_and_safety_no_dedupe(self) -> None:
        engine = AlertPolicyEngine(weekly_budget=3, cooldown_days=2, min_confidence=0.65)
        flags = [
            # Day 20 and Day 23 are 3 days apart (> cooldown_days=2) -> both pass cooldown
            _make_flag(signal="hrv_rmssd", anomaly_type="drift", score=2.7, confidence=0.85, day=20),
            _make_flag(signal="hrv_rmssd", anomaly_type="drift", score=3.1, confidence=0.90, day=23),
            # Same-day contextual variation on same signal groups under drift
            _make_flag(signal="hrv_rmssd", anomaly_type="contextual", score=2.0, confidence=0.80, day=23),
        ]
        # Multiple identical safety rule IDs must NEVER be deduped or dropped
        dup_safety = [
            {
                "rule_id": "SR-01",
                "title": "Critical vitals threshold",
                "severity": "critical",
                "active": True,
                "summary": "ast-01 SpO2 < 90%",
                "protocol_refs": ["PROT-MED-01"],
                "day": 23,
                "timestamp": "2031-03-23T16:00:00Z",
            },
            {
                "rule_id": "SR-01",
                "title": "Critical vitals threshold",
                "severity": "critical",
                "active": True,
                "summary": "ast-02 resting HR > 130",
                "protocol_refs": ["PROT-MED-01"],
                "day": 23,
                "timestamp": "2031-03-23T16:00:00Z",
            },
        ]
        res = engine.evaluate_alerts(flags, dup_safety, up_to_day=23)
        self.assertEqual(len(res["active_alerts"]), 2)
        self.assertEqual(res["suppressed_grouped_count"], 1)
        self.assertEqual(len(res["safety_alerts"]), 2)

    def test_F27_F31_simulator_integration_and_sos_outage_resilience(self) -> None:
        mission = generate_mission(days=23, seed=42, null_mission=False)
        d19_rules = evaluate_safety_rules(mission["records"], up_to_day=19)
        self.assertEqual([r["rule_id"] for r in d19_rules], ["SR-03"])
        self.assertTrue(d19_rules[0]["active"])

        d23_rules = evaluate_safety_rules(mission["records"], up_to_day=23)
        self.assertEqual([r["rule_id"] for r in d23_rules], ["SR-03"])
        self.assertFalse(d23_rules[0]["active"])
        self.assertEqual(d23_rules[0]["day"], 19)

        null_mission = generate_mission(days=23, seed=42, null_mission=True)
        self.assertEqual(evaluate_safety_rules(null_mission["records"], up_to_day=23), [])

        # SOS must still work even if engines/advisor modules are disabled/broken
        with patch.dict(sys.modules, {"app.engines.advisor": None, "app.engines.baseline": None}):
            store = AstraStore(":memory:")
            try:
                consent = ConsentManager(store)
                sync = SyncManager(store, online=False)
                sos = SOSService(store, consent, sync)
                pkt = sos.trigger_sos("ast-01", sos_type="Habitat hazard", note="Scrubber alarm")
                self.assertEqual(pkt["state"], "queued")
                self.assertEqual(sync.list_queue()[0]["priority"], 0)
            finally:
                store.close()


if __name__ == "__main__":
    unittest.main()
