"""Unit tests for Phase 0 common schema and protocol library (F-01, F-21)."""

import unittest

from app.protocols import PROTOCOL_LIBRARY, get_protocols
from app.schema import (
    CREW_BY_ID,
    CREW_ROSTER,
    HABITAT_ZONES,
    AnomalyFlag,
    ConsentScope,
    MeasurementRecord,
    QualityState,
    SignalType,
)


class TestSchemaAndProtocols(unittest.TestCase):
    def test_F01_crew_and_zones_match_spec(self) -> None:
        self.assertEqual(len(CREW_ROSTER), 4)
        self.assertIn("ast-01", CREW_BY_ID)
        self.assertEqual(CREW_BY_ID["ast-01"].name, "Cmdr. Elena Vasquez")
        self.assertEqual(CREW_BY_ID["ast-02"].name, "Dr. Marcus Chen")
        self.assertEqual(len(HABITAT_ZONES), 4)
        self.assertEqual({z.zone_id for z in HABITAT_ZONES}, {"N1", "LAB", "CQ", "AL"})

    def test_F01_measurement_record_roundtrip_and_validation(self) -> None:
        rec = MeasurementRecord(
            astronaut_id="ast-01",
            timestamp_utc="2031-03-23T16:00:00Z",
            mission_elapsed_time=538.0,
            day=23,
            hour=16,
            signal_type=SignalType.HEART_RATE.value,
            value=73.0,
            unit="bpm",
            source_device="wristband-v2",
            firmware_version="2.4.1",
            quality=QualityState.OK.value,
            confidence=0.98,
            context_tags=["rest"],
            consent_scope=ConsentScope.PHYSIO.value,
            zone_id="LAB",
        )
        restored = MeasurementRecord.from_dict(rec.to_dict())
        self.assertEqual(restored.astronaut_id, "ast-01")
        self.assertEqual(restored.value, 73.0)
        self.assertEqual(restored.quality, "ok")

        with self.assertRaises(ValueError):
            MeasurementRecord(
                astronaut_id="ast-01",
                timestamp_utc="2031-03-23T16:00:00Z",
                mission_elapsed_time=538.0,
                day=23,
                hour=16,
                signal_type=SignalType.HEART_RATE.value,
                value=None,
                unit="bpm",
                source_device="wristband-v2",
                firmware_version="2.4.1",
                quality="invalid_state",
            )

    def test_F21_protocols_present(self) -> None:
        required = {
            "PROT-REC-01",
            "PROT-REC-02",
            "PROT-SLP-01",
            "PROT-SLP-02",
            "PROT-ENV-01",
            "PROT-ENV-02",
            "PROT-MED-01",
            "PROT-RAD-01",
        }
        self.assertTrue(required.issubset(set(PROTOCOL_LIBRARY.keys())))
        fetched = get_protocols(["PROT-REC-01", "PROT-ENV-01"])
        self.assertEqual(len(fetched), 2)
        self.assertIn("escalate_if", fetched[0])

    def test_F10_anomaly_flag_contract(self) -> None:
        flag = AnomalyFlag(
            signal="hrv_rmssd",
            window=["Day 16 16:00", "Day 23 16:00"],
            anomaly_type="drift",
            score=2.9,
            confidence=0.89,
            baseline_context="sleep",
            personal_range=[55.0, 68.0],
            observed=42.8,
            contributors=["sleep_duration", "hr_recovery_1m"],
            data_quality={"coverage": 0.99, "sensor_off_hours": 0},
            evidence_ref="ev-01",
            protocol_refs=["PROT-REC-01"],
        )
        d = flag.to_dict()
        self.assertEqual(d["anomaly_type"], "drift")
        self.assertEqual(d["confidence"], 0.89)


if __name__ == "__main__":
    unittest.main()
