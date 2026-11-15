"""End-to-end REST API and live HTTP/CORS tests for AstroGuard backend (F-22..F-32)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import AstraBackend, create_server, handle_request  # noqa: E402
from app.schema import CREW_ROSTER  # noqa: E402


class AstraAPITests(unittest.TestCase):
    """Comprehensive in-process and live HTTP tests for all AstroGuard endpoints."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.shared_ro_backend = AstraBackend(seed=42, days=30, db_path=":memory:")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.shared_ro_backend.close()

    def _fresh_backend(self) -> AstraBackend:
        backend = AstraBackend(seed=42, days=30, db_path=":memory:")
        self.addCleanup(backend.close)
        return backend

    def test_health_endpoint(self) -> None:
        status, data = handle_request("GET", "/api/health", backend=self.shared_ro_backend)
        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")
        self.assertFalse(data["online"])
        self.assertEqual(data["mission_days"], 30)

    def test_state_astronaut_role_and_query_param_aliases(self) -> None:
        status, state = handle_request(
            "GET",
            "/api/state",
            query_params={"day": "23", "role": "Astronaut", "astronaut_id": "ast-01"},
            backend=self.shared_ro_backend,
        )
        self.assertEqual(status, 200)
        self.assertEqual(state["day"], 23)
        self.assertEqual(state["role"], "Astronaut")
        self.assertEqual(state["selected_crew_id"], "ast-01")

        astro = state["astronaut"]
        self.assertIsNotNone(astro)
        self.assertEqual(astro["readiness"]["band"], "Safety review")
        self.assertTrue(astro["readiness"]["safety_active"])
        self.assertIn("coverage_pct", astro["readiness"]["data_quality"])
        self.assertIn("how_sure_why", astro["briefing"])
        self.assertIn("confidence_pct", astro["briefing"])
        self.assertTrue(len(astro["observations"]) >= 5)
        self.assertEqual(list(state["consent_matrix"].keys()), ["ast-01"])
        self.assertTrue(len(state["sos_events"]) >= 1)
        self.assertTrue(any(r["rule_id"] == "SR-05" and r["active"] for r in state["active_safety_rules"]))

    def test_state_crew_health_officer_consent_scoping_and_emergency_override(self) -> None:
        backend = self._fresh_backend()
        status, state = handle_request(
            "GET",
            "/api/state",
            query_params={"day": "23", "role": "health_officer", "crew_id": "ast-03"},
            backend=backend,
        )
        self.assertEqual(status, 200)
        self.assertEqual(state["role"], "Crew Health Officer")

        by_id = {entry["astronaut_id"]: entry for entry in state["crew_overview"]}
        self.assertEqual(set(by_id.keys()), {c.astronaut_id for c in CREW_ROSTER})

        # ast-01 has Day 23 SOS -> Safety review
        self.assertEqual(by_id["ast-01"]["band"], "Safety review")
        self.assertGreaterEqual(by_id["ast-01"]["safety_count"], 1)

        # ast-02 has normal.behaviour == False -> behavioral redacted without critical rule
        self.assertTrue(by_id["ast-02"]["behavioural"]["redacted"])

        # ast-03 has normal.cognitive == False -> Scoped & no raw readiness score
        self.assertEqual(by_id["ast-03"]["band"], "Scoped")
        self.assertIsNone(by_id["ast-03"]["readiness_score"])
        self.assertIn("cognitive", by_id["ast-03"]["withheld_scopes"])
        self.assertTrue(by_id["ast-03"]["cognitive"]["redacted"])
        self.assertEqual(state["astronaut"]["readiness"]["band"], "Scoped")
        self.assertIsNone(state["astronaut"]["readiness"]["readiness_score"])
        self.assertTrue(len(state["access_log"]) > 0)

        # Critical SOS on ast-03 activates 2-hour emergency override for denied cognitive scope
        handle_request(
            "POST",
            "/api/sos/trigger",
            body={"astronaut_id": "ast-03", "sos_type": "Medical", "day": 23},
            backend=backend,
        )
        _, state_override = handle_request(
            "GET",
            "/api/state",
            query_params={"day": "23", "role": "health_officer", "crew_id": "ast-03"},
            backend=backend,
        )
        by_id_override = {entry["astronaut_id"]: entry for entry in state_override["crew_overview"]}
        self.assertEqual(by_id_override["ast-03"]["band"], "Safety review")
        self.assertTrue(by_id_override["ast-03"]["override_active"])
        self.assertNotIn("cognitive", by_id_override["ast-03"]["withheld_scopes"])

    def test_state_systems_engineer_strict_anonymization(self) -> None:
        status, state = handle_request(
            "GET",
            "/api/state",
            query_params={"day": "23", "role": "Systems Engineer", "crew_id": "ast-01"},
            backend=self.shared_ro_backend,
        )
        self.assertEqual(status, 200)
        self.assertIsNone(state["astronaut"])
        self.assertIsNone(state["crew"])
        self.assertIsNone(state["crew_overview"])
        self.assertEqual(state["crew_roster"], [])
        self.assertEqual(state["consent_matrix"], {})
        self.assertEqual(state["access_log"], [])

        env = state["environment"]
        labels = [c["crew_label"] for c in env["crew_correlations"]]
        self.assertEqual(labels, ["Crew A", "Crew B", "Crew C", "Crew D"])
        for flag in env.get("confounder_flags", []):
            self.assertNotIn("astronaut_id", flag)
        for sos in state["sos_events"]:
            self.assertEqual(sos["astronaut_id"], "anonymised")
            self.assertIsNone(sos["vitals_snapshot"])

        serialized = json.dumps(state)
        for crew in CREW_ROSTER:
            self.assertNotIn(crew.astronaut_id, serialized)
            self.assertNotIn(crew.name, serialized)

    def test_state_ground_support_summary_only_anonymization(self) -> None:
        status, state = handle_request(
            "GET",
            "/api/state",
            query_params={"day": "23", "role": "ground", "crew_id": "ast-01"},
            backend=self.shared_ro_backend,
        )
        self.assertEqual(status, 200)
        self.assertEqual(state["role"], "Ground Support")
        self.assertIsNone(state["astronaut"])
        self.assertIsNone(state["crew"])
        self.assertIsNone(state["crew_overview"])
        self.assertIn("band_counts", state["ground_summary"])
        self.assertEqual(state["ground_summary"]["crew_count"], 4)
        self.assertTrue(len(state["sync_queue"]) >= 4)

        for rule in state["active_safety_rules"]:
            self.assertIn("as_of", rule)
            self.assertNotIn("ast-0", str(rule.get("astronaut_id", "")))
        for msg in state["messages"]:
            self.assertEqual(msg["channel"], "earth")

        serialized = json.dumps(state)
        for crew in CREW_ROSTER:
            self.assertNotIn(crew.astronaut_id, serialized)
            self.assertNotIn(crew.name, serialized)

    def test_advisor_ask_grounding_refusal_idk_and_safety_notice(self) -> None:
        # 1. Grounded readiness explanation
        status, reply = handle_request(
            "POST",
            "/api/advisor/ask",
            body={
                "question": "Why is my readiness flagged today?",
                "day": 23,
                "role": "Astronaut",
                "crew_id": "ast-01",
            },
            backend=self.shared_ro_backend,
        )
        self.assertEqual(status, 200)
        self.assertFalse(reply["refused"])
        self.assertTrue(reply["safety_active"])
        self.assertIsNotNone(reply["safety_non_downgrade_notice"])
        self.assertTrue(len(reply["protocol_refs"]) >= 1)
        self.assertGreater(reply["confidence_pct"], 0)
        self.assertTrue(reply["evidence_window"])

        # 2. Diagnosis refusal
        status, diag_reply = handle_request(
            "POST",
            "/api/advisor/ask",
            body={
                "question": "Can you diagnose whether I have heart disease?",
                "day": 23,
                "role": "Astronaut",
                "crew_id": "ast-01",
            },
            backend=self.shared_ro_backend,
        )
        self.assertEqual(status, 200)
        self.assertTrue(diag_reply["refused"])

        # 3. Missing signal "I don't know"
        status, idk_reply = handle_request(
            "POST",
            "/api/advisor/ask",
            body={
                "question": "What is my blood glucose cortisol panel value?",
                "day": 23,
                "role": "Astronaut",
                "crew_id": "ast-01",
            },
            backend=self.shared_ro_backend,
        )
        self.assertEqual(status, 200)
        self.assertTrue(idk_reply["idk"])

        # 4. Systems Engineer personal interrogation blocked
        status, se_reply = handle_request(
            "POST",
            "/api/advisor/ask",
            body={
                "question": "What is Elena Vasquez's heart rate today?",
                "day": 23,
                "role": "Systems Engineer",
                "crew_id": "ast-01",
            },
            backend=self.shared_ro_backend,
        )
        self.assertEqual(status, 200)
        self.assertTrue(se_reply["refused"])

    def test_advisor_what_if_counterfactual(self) -> None:
        status, low_sleep = handle_request(
            "POST",
            "/api/advisor/what-if",
            body={
                "astronaut_id": "ast-01",
                "day": 23,
                "sleep_per_night": 5.5,
                "workload_adjustment": 1.0,
                "cabin_ventilation_pct": 100.0,
                "recovery_blocks": 0,
                "horizon_days": 7,
            },
            backend=self.shared_ro_backend,
        )
        self.assertEqual(status, 200)
        status2, high_sleep = handle_request(
            "POST",
            "/api/advisor/what-if",
            body={
                "astronaut_id": "ast-01",
                "day": 23,
                "sleep_per_night": 8.5,
                "workload_adjustment": -2.0,
                "cabin_ventilation_pct": 140.0,
                "recovery_blocks": 2,
                "horizon_days": 7,
            },
            backend=self.shared_ro_backend,
        )
        self.assertEqual(status2, 200)
        self.assertGreater(high_sleep["projected_readiness"], low_sleep["projected_readiness"])
        self.assertEqual(len(high_sleep["projected_trajectory"]), 7)

    def test_checkin_triggers_sr04_when_safety_concern_or_crisis_text(self) -> None:
        backend = self._fresh_backend()
        status, normal = handle_request(
            "POST",
            "/api/checkin",
            body={
                "astronaut_id": "ast-04",
                "day": 23,
                "mood": 4,
                "energy": 4,
                "stress": 2,
                "headache": 0,
                "fatigue": 1,
                "note": "Slept fine and finished maintenance checklist.",
                "safety_concern": False,
            },
            backend=backend,
        )
        self.assertEqual(status, 200)
        self.assertTrue(normal["ok"])
        self.assertFalse(any(r["rule_id"] == "SR-04" for r in normal["active_safety_rules"]))

        status, crisis = handle_request(
            "POST",
            "/api/checkin",
            body={
                "astronaut_id": "ast-04",
                "day": 23,
                "mood": 1,
                "energy": 1,
                "stress": 5,
                "note": "Feeling overwhelmed and unsafe with myself right now.",
                "safety_concern": True,
            },
            backend=backend,
        )
        self.assertEqual(status, 200)
        self.assertTrue(crisis["safety_active"])
        sr04 = next((r for r in crisis["active_safety_rules"] if r["rule_id"] == "SR-04"), None)
        self.assertIsNotNone(sr04)
        self.assertTrue(sr04["cannot_downgrade"])
        self.assertTrue(sr04["calm_supportive_protocol"])
        self.assertTrue(sr04["human_contact_prompt"])

    def test_pvt_submission_triggers_sr02_on_severe_lapses(self) -> None:
        backend = self._fresh_backend()
        status, pvt_res = handle_request(
            "POST",
            "/api/pvt",
            body={
                "astronaut_id": "ast-02",
                "day": 23,
                "hour": 16,
                "mean_rt_ms": 485.0,
                "lapses": 9,
                "trials": 40,
            },
            backend=backend,
        )
        self.assertEqual(status, 200)
        self.assertTrue(pvt_res["ok"])
        self.assertTrue(pvt_res["elevated_lapses"])
        self.assertTrue(pvt_res["safety_active"])
        self.assertTrue(any(r["rule_id"] == "SR-02" and r["active"] for r in pvt_res["active_safety_rules"]))

        # Verify ast-02 now enters Safety review in /api/state
        st_code, st = handle_request(
            "GET",
            "/api/state",
            query_params={"day": "23", "role": "Astronaut", "crew_id": "ast-02"},
            backend=backend,
        )
        self.assertEqual(st_code, 200)
        self.assertEqual(st["astronaut"]["readiness"]["band"], "Safety review")

    def test_sos_lifecycle_trigger_ack_cancel_resolve_and_priority_zero(self) -> None:
        backend = self._fresh_backend()

        # Invalid type rejected cleanly
        bad_status, _ = handle_request(
            "POST",
            "/api/sos/trigger",
            body={"astronaut_id": "ast-02", "sos_type": "UnknownHazard"},
            backend=backend,
        )
        self.assertEqual(bad_status, 400)

        # Trigger normalized habitat hazard SOS
        status, trig = handle_request(
            "POST",
            "/api/sos/trigger",
            body={
                "astronaut_id": "ast-02",
                "sos_type": "environment",
                "note": "Smell of overheated insulation in Airlock.",
                "day": 23,
                "hour": 16,
            },
            backend=backend,
        )
        self.assertEqual(status, 200)
        sos_id = trig["sos"]["sos_id"]
        self.assertEqual(trig["sos"]["sos_type"], "Habitat hazard")
        self.assertEqual(trig["sos"]["priority"], 0)
        self.assertTrue(any(r["rule_id"] == "SR-05" and r.get("sos_id") == sos_id for r in trig["safety_rules"]))

        # Acknowledge onboard
        status, ack = handle_request(
            "POST",
            "/api/sos/acknowledge",
            body={"sos_id": sos_id, "actor_role": "Crew Health Officer"},
            backend=backend,
        )
        self.assertEqual(status, 200)
        self.assertTrue(ack["sos"]["acknowledged_on_board"])

        # Resolve clears override & SR-05
        status, res = handle_request(
            "POST",
            "/api/sos/resolve",
            body={"sos_id": sos_id, "note": "Breaker isolated and air verified clean."},
            backend=backend,
        )
        self.assertEqual(status, 200)
        self.assertEqual(res["sos"]["status"], "resolved_ok")
        self.assertFalse(res["sos"]["override_active"])

        # Trigger and cancel another SOS
        _, trig2 = handle_request(
            "POST",
            "/api/sos/trigger",
            body={"astronaut_id": "ast-04", "type": "behavioral", "day": 23},
            backend=backend,
        )
        sos_id2 = trig2["sos"]["sos_id"]
        self.assertEqual(trig2["sos"]["sos_type"], "Behavioral support")
        c_status, canc = handle_request(
            "POST",
            "/api/sos/cancel",
            body={"sos_id": sos_id2, "reason": "false_alarm"},
            backend=backend,
        )
        self.assertEqual(c_status, 200)
        self.assertTrue(canc["sos"]["cancelled"])
        self.assertEqual(canc["sos"]["status"], "cancelled")

    def test_messaging_opaque_bandwidth_consent_and_privacy(self) -> None:
        backend = self._fresh_backend()

        # Audio / chart over Earth link includes bandwidth warning
        status, sent = handle_request(
            "POST",
            "/api/messages/send",
            body={
                "from_id": "ast-01",
                "to_id": "earth",
                "kind": "audio",
                "body": "Private note text that must remain un-analyzed.",
                "audio_duration_s": 20,
                "attach_chart": True,
                "day": 23,
            },
            backend=backend,
        )
        self.assertEqual(status, 200)
        self.assertTrue(sent["bandwidth_warning"])
        self.assertEqual(sent["channel"], "earth")
        self.assertEqual(sent["status"], "queued")
        msg_id = sent["message_id"]

        # Mark read works cleanly
        r_status, read_res = handle_request(
            "POST",
            "/api/messages/read",
            body={"msg_id": msg_id},
            backend=backend,
        )
        self.assertEqual(r_status, 200)
        self.assertEqual(read_res["status"], "read")

        # Private peer message between ast-02 and ast-03 must NOT appear in ast-01 or Crew Health Officer views
        p_status, priv = handle_request(
            "POST",
            "/api/messages/send",
            body={
                "sender_id": "ast-02",
                "recipient": "ast-03",
                "body": "CONFIDENTIAL_PEER_CHECK_MARKER",
                "day": 23,
            },
            backend=backend,
        )
        self.assertEqual(p_status, 200)
        _, st_a1 = handle_request("GET", "/api/state", {"role": "Astronaut", "crew_id": "ast-01"}, backend=backend)
        _, st_ho = handle_request("GET", "/api/state", {"role": "Crew Health Officer", "crew_id": "ast-01"}, backend=backend)
        self.assertNotIn("CONFIDENTIAL_PEER_CHECK_MARKER", json.dumps(st_a1))
        self.assertNotIn("CONFIDENTIAL_PEER_CHECK_MARKER", json.dumps(st_ho))

        # Disable ground_sharing consent for ast-02 -> Earth health chart blocked with 403
        u_status, _ = handle_request(
            "POST",
            "/api/consent/update",
            body={"astronaut_id": "ast-02", "mode": "normal", "scope": "ground_sharing", "enabled": False},
            backend=backend,
        )
        self.assertEqual(u_status, 200)
        d_status, denied = handle_request(
            "POST",
            "/api/messages/send",
            body={
                "sender_id": "ast-02",
                "recipient": "Home (Earth)",
                "body": "Health snapshot",
                "attach_health_chart": True,
            },
            backend=backend,
        )
        self.assertEqual(d_status, 403)
        self.assertIn("Consent denied", denied["error"])

    def test_consent_update_toggles_health_officer_visibility(self) -> None:
        backend = self._fresh_backend()
        # Allow cognitive sharing for ast-03 -> changes from Scoped to active score
        u_status, updated = handle_request(
            "POST",
            "/api/consent/update",
            body={"astronaut_id": "ast-03", "mode": "normal", "scope": "cognitive", "enabled": True},
            backend=backend,
        )
        self.assertEqual(u_status, 200)
        self.assertTrue(updated["profile"]["normal"]["cognitive"])

        _, ho_state = handle_request(
            "GET",
            "/api/state",
            query_params={"day": "23", "role": "Crew Health Officer", "crew_id": "ast-03"},
            backend=backend,
        )
        by_id = {c["astronaut_id"]: c for c in ho_state["crew_overview"]}
        self.assertNotEqual(by_id["ast-03"]["band"], "Scoped")
        self.assertIsNotNone(by_id["ast-03"]["readiness_score"])

    def test_sync_offline_preservation_and_priority_fast_forward(self) -> None:
        backend = self._fresh_backend()

        # Cannot flush while link is offline
        s1, ff_offline = handle_request("POST", "/api/sync/fast-forward", body={}, backend=backend)
        self.assertEqual(s1, 200)
        self.assertFalse(ff_offline["online"])
        self.assertEqual(ff_offline["processed_count"], 0)

        # Toggle link online and fast-forward
        s2, linked = handle_request("POST", "/api/sync/toggle-link", body={"online": True}, backend=backend)
        self.assertEqual(s2, 200)
        self.assertTrue(linked["online"])

        s3, ff_online = handle_request("POST", "/api/sync/fast-forward", body={}, backend=backend)
        self.assertEqual(s3, 200)
        self.assertTrue(ff_online["online"])
        self.assertGreater(ff_online["processed_count"], 0)
        priorities = [t["priority"] for t in ff_online["transitions"] if t["to_status"] == "transmitting"]
        self.assertEqual(priorities, sorted(priorities))
        self.assertEqual(priorities[0], 0)

    def test_live_ephemeral_http_server_cors_and_json_roundtrip(self) -> None:
        backend = self._fresh_backend()
        server = create_server(host="127.0.0.1", port=0, backend=backend)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)

        base_url = f"http://127.0.0.1:{port}"

        # Preflight OPTIONS CORS check
        opt_req = Request(f"{base_url}/api/state", method="OPTIONS")
        with urlopen(opt_req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
            self.assertIn("POST", resp.headers.get("Access-Control-Allow-Methods", ""))
            self.assertIn("Content-Type", resp.headers.get("Access-Control-Allow-Headers", ""))

        # Live GET /api/health
        with urlopen(f"{base_url}/api/health", timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.headers.get("Access-Control-Allow-Origin"), "*")
            health = json.loads(resp.read().decode("utf-8"))
            self.assertEqual(health["status"], "ok")

        # Live POST /api/advisor/what-if
        post_req = Request(
            f"{base_url}/api/advisor/what-if",
            data=json.dumps({"astronaut_id": "ast-01", "day": 23, "sleep_per_night": 8.0}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(post_req, timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            cf = json.loads(resp.read().decode("utf-8"))
            self.assertIn("projected_readiness", cf)

        # Invalid endpoint returns 404 JSON
        with self.assertRaises(HTTPError) as ctx:
            urlopen(f"{base_url}/api/does-not-exist", timeout=3)
        self.assertEqual(ctx.exception.code, 404)
        ctx.exception.close()


if __name__ == "__main__":
    unittest.main()
