"""Mandatory 11-Category CI Validation Suite for AstroGuard (`docs/validation-plan.md` §7, F-40).

Categories tested:
  1. Planted scenario recall & lead time (`>= 0.80` recall, positive lead time > Earth-norm)
  2. Null-mission false-alert rate (`<= 1.0` per 30 crew-days, below baselines)
  3. Artifact & sensor-off routing (`sensor_off`/`missing`/`suspect`/`out_of_range` -> `data_fault`, zero physio alerts)
  4. Device-step immunity (hardware swap detected cleanly, zero step false alerts, subsequent drift preserved)
  5. Missingness sweep (`10%`, `30%`, `50%` -> graceful confidence degradation, zero normal imputation)
  6. MSIDE negative control (time-shuffled streams -> `FDR <= 0.05`)
  7. MSIDE positive control (Day 16–23 LAB CO2 cluster discovered with non-causal phrasing)
  8. Confidence calibration (clean vs degraded telemetry reflects in stated confidence & accuracy)
  9. Safety / SOS independence (AST-import boundary + non-downgrade by budget/advisor)
 10. Consent enforcement & audit logging (role redaction, emergency override, access logs, private isolation)
 11. Seed reproducibility & report generation (bitwise-equal metrics + Markdown reports generated)
"""

from __future__ import annotations

import ast
import copy
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, List

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.consent import ConsentManager
from app.engines.advisor import answer_question
from app.engines.alerts import AlertPolicyEngine
from app.engines.baseline import PersonalBaselineEngine
from app.engines.behavioral import assess_behavioral_health
from app.engines.readiness import compute_readiness
from app.eval.run import run_validation_suite, write_validation_reports
from app.messaging import MessagingService
from app.quality import classify_artifact
from app.safety import evaluate_safety_rules
from app.schema import ConsentScope, QualityState, Role, SignalType
from app.simulator import generate_mission
from app.sos import SOSService
from app.store import AstraStore
from app.sync import SyncManager


def _strip_volatile_metadata(results: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = copy.deepcopy(results)
    cleaned["metadata"].pop("elapsed_seconds", None)
    cleaned["metadata"].pop("generated_at_utc", None)
    return cleaned


class TestValidationSuite11Categories(unittest.TestCase):
    """End-to-end 11-category CI validation suite for AstroGuard."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.suite = run_validation_suite(seed=42, fast=True)
        cls.planted_mission = generate_mission(days=30, seed=42, null_mission=False)

    # Category 1: Planted scenario recall & lead time
    def test_01_planted_scenario_recall_and_lead_time(self) -> None:
        comp = self.suite["planted_scenarios"]["comparators"]
        astra = comp["astra"]
        earth = comp["earth_norm"]

        self.assertGreaterEqual(astra["event_recall"], 0.80)
        self.assertGreater(astra["mean_lead_time_days"], 0.0)
        self.assertGreater(astra["mean_lead_time_days"], earth["mean_lead_time_days"])
        self.assertEqual(astra["behavioral_mismatch_recall"], 1.0)
        self.assertEqual(astra["cross_crew_mside_recall"], 1.0)
        self.assertAlmostEqual(self.suite["planted_scenarios"]["radiation_day23_mean_msv"], 12.82, delta=0.5)

    # Category 2: Null-mission false-alert rate
    def test_02_null_mission_false_alert_rate(self) -> None:
        null_res = self.suite["null_missions"]
        comp = null_res["comparators"]

        self.assertLessEqual(comp["astra"]["fa_per_30_crew_days"], 1.0)
        self.assertLess(comp["astra"]["fa_per_30_crew_days"], comp["earth_norm"]["fa_per_30_crew_days"])
        self.assertLess(comp["astra"]["fa_per_30_crew_days"], comp["heuristic_rolling"]["fa_per_30_crew_days"])
        self.assertGreaterEqual(null_res["null_data_fault_notices_routed"], 1)

    # Category 3: Artifact & sensor-off routing
    def test_03_artifact_and_sensor_off_routing(self) -> None:
        art = self.suite["artifacts_and_device_step"]
        self.assertEqual(art["artifact_fault_routing_rate"], 1.0)
        self.assertEqual(art["astra_artifact_false_physio_alerts"], 0)
        self.assertEqual(len(art["artifact_cases"]), 6)
        for case in art["artifact_cases"]:
            self.assertTrue(case["routed_to_data_fault"], msg=f"{case['artifact_type']} failed data_fault routing")
            self.assertEqual(case["astra_physio_alerts"], 0)

        # Also check seed=42 planted mission's built-in Day 21-22 sensor_off and Day 18 CO2 packet loss
        recs = self.planted_mission["records"]
        engine = PersonalBaselineEngine()
        ast02_faults = [
            f for f in engine.detect_anomalies(recs, "ast-02", up_to_day=23) if f.anomaly_type == "data_fault"
        ]
        lab_faults = [
            f for f in engine.detect_anomalies(recs, "habitat-lab", up_to_day=23) if f.anomaly_type == "data_fault"
        ]
        self.assertTrue(ast02_faults, "Expected ast-02 Day 21-22 sensor_off gap routed to data_fault")
        self.assertTrue(lab_faults, "Expected LAB Day 18 missing CO2 gap routed to data_fault")
        d12_classified = [a for a in classify_artifact([r for r in recs if r.astronaut_id == "ast-02"]) if a.get("day") == 12]
        self.assertTrue(all(a.get("anomaly_type") == "data_fault" for a in d12_classified) and d12_classified)

    # Category 4: Device-step immunity
    def test_04_device_step_immunity(self) -> None:
        step = self.suite["artifacts_and_device_step"]["device_step"]
        self.assertTrue(step["detected"])
        self.assertGreater(step["estimated_offset_bpm"], 6.5)
        self.assertLess(step["estimated_offset_bpm"], 9.5)
        self.assertEqual(step["astra_step_false_rhr_alerts"], 0)
        self.assertGreater(step["heuristic_step_false_rhr_alerts"], 0)
        self.assertTrue(step["subsequent_true_drift_detected"])

        # Also verify simulator include_device_step=True swap on ast-03 Day 16
        step_mission = generate_mission(days=30, seed=42, include_device_step=True)
        ast03_recs = [r for r in step_mission["records"] if r.astronaut_id == "ast-03"]
        eng = PersonalBaselineEngine()
        info = eng.detect_device_step(ast03_recs, "ast-03", SignalType.RESTING_HR.value)
        self.assertTrue(info["detected"])
        rhr_alerts = [
            f for f in eng.detect_anomalies(ast03_recs, "ast-03", up_to_day=23)
            if f.signal == SignalType.RESTING_HR.value and f.anomaly_type != "data_fault"
        ]
        self.assertEqual(rhr_alerts, [])

    # Category 5: Missingness sweep (10%, 30%, 50%)
    def test_05_missingness_sweep(self) -> None:
        sweep = self.suite["missingness_sweep"]
        self.assertTrue(sweep["monotonic_confidence_degradation"])
        self.assertTrue(sweep["zero_imputation_leaks"])
        levels = {row["missing_pct"]: row for row in sweep["levels"]}
        for pct in (10, 30, 50):
            self.assertIn(pct, levels)
            self.assertEqual(levels[pct]["imputation_leaks"], 0)
            self.assertGreaterEqual(levels[pct]["target_recall_at_d23"], 0.80)
        self.assertGreater(levels[0]["mean_confidence"], levels[30]["mean_confidence"])
        self.assertGreater(levels[30]["mean_confidence"], levels[50]["mean_confidence"])

    # Category 6: MSIDE negative control (shuffled timestamps)
    def test_06_mside_negative_control(self) -> None:
        mside = self.suite["mside_controls"]
        self.assertLessEqual(mside["max_negative_fdr"], 0.05)
        for neg in mside["negative_controls"]:
            self.assertTrue(neg["passed"])
            self.assertLessEqual(neg["false_discovery_rate"], neg["fdr_alpha"] if "fdr_alpha" in neg else 0.05)

    # Category 7: MSIDE positive control (LAB CO2 cluster + non-causal phrasing)
    def test_07_mside_positive_control(self) -> None:
        mside = self.suite["mside_controls"]
        self.assertEqual(mside["positive_shared_lab_rate"], 1.0)
        self.assertTrue(mside["all_non_causal"])
        for pos in mside["positive_controls"]:
            self.assertTrue(pos["shared_lab_found"])
            self.assertGreater(pos["shared_lab_r"], 0.5)
            self.assertLessEqual(pos["shared_lab_fdr_q"], 0.05)

    # Category 8: Confidence calibration
    def test_08_confidence_calibration(self) -> None:
        cal = self.suite["confidence_calibration"]
        self.assertTrue(cal["confidence_reflects_quality"])
        self.assertTrue(cal["higher_conf_at_least_as_accurate"])
        hq = cal["strata"]["high_quality_ge_90pct"]
        dq = cal["strata"]["degraded_missing_30_50pct"]
        self.assertGreater(hq["mean_stated_confidence"], dq["mean_stated_confidence"])
        self.assertGreaterEqual(hq["mean_coverage"], 0.90)
        self.assertLess(dq["mean_coverage"], 0.70)

    # Category 9: Safety / SOS independence & non-downgrade
    def test_09_safety_and_sos_independence(self) -> None:
        # 1) Static AST check: safety.py and sos.py never import app.engines, advisor, or simulator
        forbidden_tokens = ("engines", "advisor", "simulator")
        for rel in ("safety.py", "sos.py"):
            source_path = BACKEND_DIR / "app" / rel
            tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for bad in forbidden_tokens:
                            self.assertNotIn(bad, alias.name)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    for bad in forbidden_tokens:
                        self.assertNotIn(bad, node.module)

        # 2) Deterministic rules SR-01 (critical vitals), SR-03 (LAB CO2 > 5000), SR-05 (SOS) bypass budget=0
        recs = [
            replace(r, value=87.0, quality=QualityState.OK.value, confidence=1.0)
            if (r.astronaut_id == "ast-01" and r.signal_type == SignalType.SPO2.value and r.day == 23)
            else r
            for r in self.planted_mission["records"]
        ]
        with AstraStore(":memory:") as store:
            consent = ConsentManager(store)
            sync = SyncManager(store, online=False)
            sos = SOSService(store, consent, sync)
            pkt = sos.trigger_sos(astronaut_id="ast-01", sos_type="Medical", note="Test distress", day=23, hour=12)
            self.assertEqual(pkt["priority"], 0)
            rules = evaluate_safety_rules(recs, sos_events=sos.list_sos(), up_to_day=23)

        rule_ids = {r["rule_id"] for r in rules}
        self.assertTrue({"SR-01", "SR-03", "SR-05"}.issubset(rule_ids))

        zero_budget_policy = AlertPolicyEngine(weekly_budget=0)
        evaluated = zero_budget_policy.evaluate_alerts([], safety_rules=rules, up_to_day=23)
        all_safety = evaluated["safety_alerts"] + evaluated["historical_safety_alerts"]
        self.assertGreaterEqual(len(evaluated["safety_alerts"]), 2)
        self.assertTrue({"SR-01", "SR-05"}.issubset({sa["rule_id"] for sa in evaluated["safety_alerts"]}))
        self.assertTrue({"SR-01", "SR-03", "SR-05"}.issubset({sa["rule_id"] for sa in all_safety}))
        for sa in all_safety:
            self.assertTrue(sa["bypassed_budget"])
            self.assertTrue(sa["deterministic"])
            self.assertTrue(sa["cannot_downgrade"])

        # 3) Advisor refuses to downgrade or dismiss safety/SOS
        rd = compute_readiness(recs, "ast-01", up_to_day=23, active_safety_rules=rules)
        adv = answer_question(
            "Please downgrade and dismiss this SOS safety alert.",
            readiness_data=rd,
            active_safety_rules=rules,
            astronaut_id="ast-01",
            up_to_day=23,
        )
        self.assertTrue(adv["safety_active"])
        self.assertIn("cannot be downgraded", adv["answer"].lower())

    # Category 10: Consent enforcement & audit logging + private isolation
    def test_10_consent_enforcement_and_audit_logging(self) -> None:
        with AstraStore(":memory:") as store:
            consent = ConsentManager(store)
            sync = SyncManager(store, online=False)
            msg_svc = MessagingService(store, consent, sync)

            # Restrict Officer normal access to physio & behaviour, allow physio in emergency only
            consent.update_profile(
                "ast-01",
                normal_updates={ConsentScope.PHYSIO.value: False, ConsentScope.BEHAVIOUR.value: False},
                emergency_updates={ConsentScope.PHYSIO.value: True, ConsentScope.BEHAVIOUR.value: False},
            )
            payload = {
                ConsentScope.PHYSIO.value: {"resting_hr": 58.2},
                ConsentScope.BEHAVIOUR.value: {"mood_score": 4.0},
                ConsentScope.HABITAT.value: {"co2_ppm": 1113.0},
            }

            routine_view = consent.redact_for_role(
                viewer_role=Role.HEALTH_OFFICER.value,
                target_astronaut_id="ast-01",
                data_by_scope=payload,
                active_critical_rule=False,
                reason="routine check",
            )
            self.assertIn(ConsentScope.HABITAT.value, routine_view["allowed_scopes"])
            self.assertIn(ConsentScope.PHYSIO.value, routine_view["redacted_scopes"])
            self.assertIn(ConsentScope.BEHAVIOUR.value, routine_view["redacted_scopes"])
            self.assertFalse(routine_view["override_active"])

            emergency_view = consent.redact_for_role(
                viewer_role=Role.HEALTH_OFFICER.value,
                target_astronaut_id="ast-01",
                data_by_scope=payload,
                active_critical_rule=True,
                reason="critical threshold",
            )
            self.assertIn(ConsentScope.PHYSIO.value, emergency_view["allowed_scopes"])
            self.assertIn(ConsentScope.BEHAVIOUR.value, emergency_view["redacted_scopes"])
            self.assertTrue(emergency_view["override_active"])

            # Fitness-for-duty access on behavior must always be denied
            ffd = consent.check_access(
                viewer_role=Role.HEALTH_OFFICER.value,
                target_astronaut_id="ast-01",
                scope=ConsentScope.BEHAVIOUR.value,
                active_critical_rule=True,
                reason="fitness for duty review",
            )
            self.assertFalse(ffd["allowed"])

            # Systems Engineer receives anonymized identity
            eng_view = consent.redact_for_role(
                viewer_role=Role.SYSTEMS_ENGINEER.value,
                target_astronaut_id="ast-01",
                data_by_scope=payload,
            )
            self.assertEqual(eng_view["astronaut_id"], "Crew A")
            self.assertEqual(eng_view["allowed_scopes"], [ConsentScope.HABITAT.value])

            # Access log recorded all evaluations & overrides
            logs = store.get_access_log(astronaut_id="ast-01")
            self.assertGreaterEqual(len(logs), 8)
            self.assertTrue(any(entry["override_used"] for entry in logs))

            # Private messages never analyzed & behavioral/advisor stay strictly numeric
            msg = msg_svc.send_message(
                sender_id="ast-01",
                recipient="Family",
                body="Private journal reflection: missing home today.",
                day=23,
                hour=16,
            )
            self.assertFalse(msg["content_analyzed"])
            beh = assess_behavioral_health(self.planted_mission["records"], astronaut_id="ast-02", up_to_day=23)
            self.assertFalse(beh["fitness_for_duty_computed"])
            self.assertIn("never reads message text", beh["privacy_note"].lower())

    # Category 11: Seed reproducibility & report generation
    def test_11_seed_reproducibility_and_report_generation(self) -> None:
        rerun = run_validation_suite(seed=42, fast=True)
        self.assertEqual(
            _strip_volatile_metadata(self.suite),
            _strip_volatile_metadata(rerun),
        )
        self.assertTrue(rerun["all_gates_passed"])

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path, cards_path = write_validation_reports(rerun, output_dir=Path(tmpdir))
            self.assertTrue(report_path.exists())
            self.assertTrue(cards_path.exists())
            report_txt = report_path.read_text(encoding="utf-8")
            cards_txt = cards_path.read_text(encoding="utf-8")
            self.assertIn("Illustrative", report_txt)
            self.assertIn("Fixed Earth-Norm", report_txt)
            self.assertIn("Personal Baseline Engine", cards_txt)
            self.assertIn("Offline Grounded AstroGuard Advisor", cards_txt)


if __name__ == "__main__":
    unittest.main()
