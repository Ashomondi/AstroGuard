"""AstroGuard Offline-First Mission Backend Server and In-Process Router.

Provides a zero-external-dependency Python 3.14 HTTP server (`ThreadingHTTPServer`
on `127.0.0.1:8000`) plus a shared in-process `AstraBackend` / `handle_request()`
interface used by both HTTP handlers, automated API tests, and an optional
FastAPI wrapper when FastAPI is installed.
"""

from __future__ import annotations

import argparse
import copy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import statistics
import threading
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, urlparse

from app.consent import (
    ConsentManager,
    _normalize_role,
    _normalize_scope,
)
from app.engines.advisor import answer_question, build_daily_briefing
from app.engines.alerts import AlertPolicyEngine
from app.engines.behavioral import assess_behavioral_health
from app.engines.counterfactual import simulate_intervention
from app.engines.environment import analyze_crew_environment
from app.engines.mside import discover_interactions
from app.engines.readiness import compute_readiness
from app.messaging import MessagingService
from app.protocols import get_protocols
from app.safety import evaluate_safety_rules
from app.schema import (
    CREW_BY_ID,
    CREW_ROSTER,
    ConsentScope,
    HABITAT_ZONES,
    MeasurementRecord,
    QualityState,
    Role,
    SIGNAL_TO_SCOPE,
    SIGNAL_UNITS,
    SignalType,
    ZONE_BY_ID,
)
from app.simulator import MISSION_START_UTC, generate_mission
from app.sos import SOSService, VALID_SOS_TYPES
from app.store import AstraStore
from app.sync import SyncManager

CORS_HEADERS: Dict[str, str] = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
}

LIGHT_DELAY_MINUTES = 12.8

_ANON_CREW_LABELS: Dict[str, str] = {
    "ast-01": "Crew A",
    "ast-02": "Crew B",
    "ast-03": "Crew C",
    "ast-04": "Crew D",
}

_SOS_TYPE_MAP: Dict[str, str] = {
    "medical": "Medical",
    "behavioral": "Behavioral support",
    "behavioural": "Behavioral support",
    "behavioral support": "Behavioral support",
    "behavioral_support": "Behavioral support",
    "environment": "Habitat hazard",
    "habitat": "Habitat hazard",
    "habitat hazard": "Habitat hazard",
    "habitat_hazard": "Habitat hazard",
    "hazard": "Habitat hazard",
}

_RECIPIENT_ALIASES: Dict[str, str] = {
    "earth": "Home (Earth)",
    "home": "Home (Earth)",
    "home (earth)": "Home (Earth)",
    "ground": "Home (Earth)",
    "ground support": "Home (Earth)",
    "ground_support": "Home (Earth)",
    "health_officer": "Crew Health Officer",
    "health officer": "Crew Health Officer",
    "crew health officer": "Crew Health Officer",
    "ho": "Crew Health Officer",
    "systems": "Systems Engineer",
    "systems engineer": "Systems Engineer",
    "systems_engineer": "Systems Engineer",
    "all": "All crew",
    "all crew": "All crew",
}

_ENTITY_TO_ID: Dict[str, str] = {
    "home (earth)": "earth",
    "earth": "earth",
    "ground support": "earth",
    "crew health officer": "health_officer",
    "health_officer": "health_officer",
    "systems engineer": "systems",
    "systems": "systems",
    "all crew": "all",
    "all": "all",
}
for _crew in CREW_ROSTER:
    _ENTITY_TO_ID[_crew.astronaut_id.lower()] = _crew.astronaut_id
    _ENTITY_TO_ID[_crew.name.lower()] = _crew.astronaut_id

_DEFAULT_OBSERVATION_SPECS: Tuple[Tuple[str, str, str], ...] = (
    (SignalType.HR_RECOVERY_1M.value, "1-min HR recovery", "Post-exercise parasympathetic rebound"),
    (SignalType.RESTING_HR.value, "Resting heart rate", "Morning rest baseline"),
    (SignalType.HRV_RMSSD.value, "HRV (RMSSD)", "Overnight vagal tone"),
    (SignalType.SLEEP_DURATION.value, "Sleep duration", "Nightly sleep hours"),
    (SignalType.SLEEP_FRAGMENTATION.value, "Sleep fragmentation", "Awakenings per hour"),
    (SignalType.PVT_MEAN_RT.value, "PVT mean reaction time", "3-min psychomotor vigilance"),
    (SignalType.PVT_LAPSES.value, "PVT lapses", "RT > 500 ms count"),
    (SignalType.SPO2.value, "SpO2", "Peripheral oxygen saturation"),
    (SignalType.SYMPTOM_HEADACHE.value, "Headache check-in", "Self-reported 0-5 scale"),
    (SignalType.SYMPTOM_FATIGUE.value, "Fatigue check-in", "Self-reported 0-5 scale"),
)

_SUGGESTED_QUESTIONS: List[str] = [
    "Why is my readiness flagged today?",
    "Could CO2 explain my headache?",
    "What changes if I sleep 8 hours for the next 3 nights?",
    "Should I stop working out or diagnose this?",
]

_HARD_BOUNDARIES: List[str] = [
    "Decision support only — never medical diagnosis or fitness-for-duty clearance.",
    "Deterministic hard safety rules (SR-01..SR-05) cannot be downgraded by analytics or chat.",
    "Always distinguishes sensor gaps or artifacts from personal change.",
    "Says 'I don't know' when required signals or consent permissions are unavailable.",
]


def _normalize_crew_id(raw: Optional[str], default: str = "ast-01") -> str:
    if raw is None or not str(raw).strip():
        return default
    cid = str(raw).strip()
    if cid not in CREW_BY_ID:
        raise ValueError(f"Unknown astronaut_id/crew_id: {cid}")
    return cid


def _normalize_sos_type(raw: Optional[str]) -> str:
    if raw is None or not str(raw).strip():
        return "Medical"
    text = str(raw).strip()
    if text in VALID_SOS_TYPES:
        return text
    mapped = _SOS_TYPE_MAP.get(text.lower())
    if mapped is not None:
        return mapped
    raise ValueError(f"Invalid sos_type '{text}'. Allowed: {sorted(VALID_SOS_TYPES)}")


def _normalize_recipient(raw: Optional[str]) -> str:
    if raw is None or not str(raw).strip():
        raise ValueError("Recipient is required.")
    text = str(raw).strip()
    mapped = _RECIPIENT_ALIASES.get(text.lower())
    if mapped is not None:
        return mapped
    if text in CREW_BY_ID:
        return text
    return text


def _entity_id_and_label(raw: Optional[str]) -> Tuple[str, str]:
    text = str(raw or "").strip()
    if not text:
        return "unknown", "Unknown"
    low = text.lower()
    if text in CREW_BY_ID:
        return text, CREW_BY_ID[text].name
    if low in _ENTITY_TO_ID:
        eid = _ENTITY_TO_ID[low]
        if eid in CREW_BY_ID:
            return eid, CREW_BY_ID[eid].name
        label_map = {
            "earth": "Home (Earth)",
            "health_officer": "Crew Health Officer",
            "systems": "Systems Engineer",
            "all": "All crew",
        }
        return eid, label_map.get(eid, text)
    return low, text


def _mission_iso(day: int, hour: int = 16, minute: int = 0) -> str:
    dt = MISSION_START_UTC + timedelta(days=max(0, int(day) - 1), hours=int(hour), minutes=int(minute))
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _strip_identity_from_text(text: str) -> str:
    out = str(text or "")
    for crew in CREW_ROSTER:
        out = out.replace(crew.astronaut_id, crew.anonymous_label)
        out = out.replace(crew.name, crew.anonymous_label)
        first_name = crew.name.split()[-1] if len(crew.name.split()) >= 2 else crew.name
        if first_name and len(first_name) > 2:
            out = out.replace(first_name, crew.anonymous_label)
    return out


def _enrich_readiness(readiness: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(readiness)
    dq = dict(out.get("data_quality") or {})
    cov = float(dq.get("coverage", 1.0))
    cov_pct = int(round(cov * 100)) if cov <= 1.0 else int(round(cov))
    dq["coverage_pct"] = cov_pct
    if "summary" not in dq:
        gap_count = int(dq.get("gap_count", len(dq.get("gaps", []))))
        dq["summary"] = (
            f"{cov_pct}% clean telemetry coverage ({gap_count} gap(s) flagged explicitly)."
            if gap_count
            else f"{cov_pct}% clean telemetry coverage; no recent gaps."
        )
    out["data_quality"] = dq

    latest = dict(out.get("latest_readings") or {})
    for sig, label, subtitle in _DEFAULT_OBSERVATION_SPECS:
        entry = latest.get(sig)
        if isinstance(entry, dict):
            entry.setdefault("label", label)
            entry.setdefault("subtitle", subtitle)
    out["latest_readings"] = latest
    return out


def _build_observations(readiness: Dict[str, Any]) -> List[Dict[str, Any]]:
    observations: List[Dict[str, Any]] = []
    latest = readiness.get("latest_readings") or {}
    for sig, label, subtitle in _DEFAULT_OBSERVATION_SPECS:
        entry = latest.get(sig)
        if not isinstance(entry, dict):
            continue
        scope = SIGNAL_TO_SCOPE.get(sig, ConsentScope.PHYSIO.value)
        if sig in (SignalType.PVT_MEAN_RT.value, SignalType.PVT_LAPSES.value):
            domain = "cognitive"
        elif scope == ConsentScope.BEHAVIOUR.value:
            domain = "behaviour"
        else:
            domain = "recovery"

        val = entry.get("value")
        unit = entry.get("unit") or ""
        baseline = entry.get("baseline")
        delta = entry.get("delta")
        quality = entry.get("quality", QualityState.MISSING.value)
        obs_str = (
            f"{round(float(val), 1)} {unit}".strip()
            if val is not None
            else f"Gap ({quality})"
        )
        base_str = f"{round(float(baseline), 1)} {unit}".strip() if baseline is not None else "Personal ref"
        delta_str = (
            f"{float(delta):+.1f} {unit}".strip()
            if isinstance(delta, (int, float))
            else "Gaps kept visible"
        )
        observations.append(
            {
                "signal": sig,
                "label": label,
                "subtitle": subtitle,
                "domain": domain,
                "scope": scope,
                "observed": obs_str,
                "baseline": base_str,
                "delta": delta_str,
                "quality": quality,
                "window": f"Day {entry.get('day', readiness.get('up_to_day', 23))}",
            }
        )
    return observations


def _enrich_briefing(
    briefing: Dict[str, Any],
    readiness: Dict[str, Any],
    safety_rules: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    out = copy.deepcopy(briefing)
    conf = float(out.get("confidence", readiness.get("confidence", 0.85)))
    conf_pct = int(round(conf * 100)) if conf <= 1.0 else int(round(conf))
    out["confidence_pct"] = conf_pct
    if "how_sure_why" not in out:
        out["how_sure_why"] = out.get("how_sure_and_why", "")
    if "how_sure_and_why" not in out:
        out["how_sure_and_why"] = out.get("how_sure_why", "")

    active_rules = [r for r in safety_rules if r.get("active")]
    if "headline" not in out:
        band = readiness.get("band", "Steady")
        if active_rules:
            out["headline"] = f"{band} · {active_rules[0].get('title', 'Safety protocol active')}"
        else:
            out["headline"] = f"{band} readiness · {round(float(readiness.get('readiness_score', 0)))}/100"
    if not out.get("protocols") and out.get("protocol_refs"):
        out["protocols"] = get_protocols(out["protocol_refs"])
    return out


def _format_sos_event(pkt: Dict[str, Any], *, anonymize: bool = False) -> Dict[str, Any]:
    out = copy.deepcopy(pkt)
    aid = str(out.get("astronaut_id", ""))
    crew = CREW_BY_ID.get(aid)
    status = str(out.get("status") or out.get("state") or "queued")
    out["status"] = status
    out["state"] = status
    ack = bool(out.get("acknowledged_on_board") or out.get("onboard_acknowledged"))
    out["acknowledged_on_board"] = ack
    out["onboard_acknowledged"] = ack
    out.setdefault("priority", 0)
    if anonymize:
        out["astronaut_id"] = "anonymised"
        out["astronaut_label"] = "Crew member (anonymised)"
        out["vitals_snapshot"] = None
        if out.get("sos_type") != "Habitat hazard":
            out["note"] = "Crew safety beacon active; personal details scoped per privacy role."
        else:
            out["note"] = _strip_identity_from_text(str(out.get("note") or ""))
    else:
        out["astronaut_label"] = crew.name if crew else aid
    return out


def _format_message(
    msg: Dict[str, Any],
    *,
    anonymize_crew_sender: bool = False,
) -> Dict[str, Any]:
    out = copy.deepcopy(msg)
    from_raw = out.get("sender_id") or out.get("from_id")
    to_raw = out.get("recipient") or out.get("to_id")
    from_id, from_label = _entity_id_and_label(from_raw)
    to_id, to_label = _entity_id_and_label(to_raw)

    if anonymize_crew_sender and from_id in CREW_BY_ID:
        from_id = "crew-relay"
        from_label = "On-board Crew (consented relay)"
        out["sender_id"] = "crew-relay"
        out["sender_label"] = from_label

    day = int(out.get("day", 23))
    hour = int(out.get("hour", 16))
    channel = out.get("channel") or ("earth" if to_id == "earth" or from_id == "earth" else "onboard")
    msg_type = out.get("msg_type") or out.get("kind") or "text"
    audio_sec = int(out.get("audio_duration_sec") or out.get("audio_duration_s") or 0)
    attach_chart = bool(out.get("attach_health_chart") or out.get("attach_chart"))

    out["message_id"] = out.get("message_id") or out.get("msg_id")
    out["msg_id"] = out["message_id"]
    out["from_id"] = from_id
    out["from_label"] = from_label
    out["to_id"] = to_id
    out["to_label"] = to_label
    out["channel"] = channel
    out["kind"] = msg_type
    out["msg_type"] = msg_type
    out["audio_duration_s"] = audio_sec
    out["audio_duration_sec"] = audio_sec
    out["attach_chart"] = attach_chart
    out["attach_health_chart"] = attach_chart
    if attach_chart and not out.get("attachment"):
        out["attachment"] = {"type": "health_chart", "label": "Consented readiness trend snapshot"}
    delay_suffix = f" · Earth light time {LIGHT_DELAY_MINUTES} min" if channel == "earth" else ""
    out["timestamp_label"] = f"Day {day}, {hour:02d}:00{delay_suffix}"
    out.setdefault("light_delay_min", LIGHT_DELAY_MINUTES if channel == "earth" else 0.0)
    return out


def _sanitize_safety_rule(rule: Dict[str, Any], *, anonymize: bool) -> Dict[str, Any]:
    out = copy.deepcopy(rule)
    if not anonymize:
        return out
    aid = str(out.get("astronaut_id") or "")
    if aid and aid in CREW_BY_ID:
        out["astronaut_id"] = "anonymised"
        out["crew_name"] = "Crew member (anonymised)"
    out["summary"] = _strip_identity_from_text(str(out.get("summary") or ""))
    return out


def _get_zone_co2(env_data: Dict[str, Any], zone_id: str = "LAB", default: float = 1113.0) -> float:
    """Safely extract current CO2 ppm whether `env_data['zones']` is a dict or list."""
    zones = env_data.get("zones")
    if isinstance(zones, dict):
        zone = zones.get(zone_id) or {}
        if isinstance(zone, dict) and zone.get("co2_ppm") is not None:
            return float(zone["co2_ppm"])
    elif isinstance(zones, list):
        for zone in zones:
            if isinstance(zone, dict) and zone.get("zone_id") == zone_id and zone.get("co2_ppm") is not None:
                return float(zone["co2_ppm"])
    return float(default)


def _sanitize_sync_queue(queue_items: Sequence[Dict[str, Any]], *, anonymize: bool) -> List[Dict[str, Any]]:
    """Strip personal identifiers and clinical snapshots from sync payloads for non-medical roles."""
    items = copy.deepcopy(list(queue_items))
    if not anonymize:
        return items
    for item in items:
        if not isinstance(item, dict):
            continue
        meta = item.get("meta")
        if isinstance(meta, dict):
            if meta.get("astronaut_id") in CREW_BY_ID:
                meta["astronaut_id"] = "anonymised"
            if meta.get("sender_id") in CREW_BY_ID:
                meta["sender_id"] = "crew-relay"
        payload = item.get("payload")
        if isinstance(payload, dict):
            if payload.get("astronaut_id") in CREW_BY_ID:
                payload["astronaut_id"] = "anonymised"
            if payload.get("sender_id") in CREW_BY_ID:
                payload["sender_id"] = "crew-relay"
            if "vitals_snapshot" in payload:
                payload["vitals_snapshot"] = None
            if payload.get("note"):
                payload["note"] = "Crew priority packet (anonymised per role)."
            if payload.get("summary"):
                payload["summary"] = _strip_identity_from_text(str(payload["summary"]))
            if item.get("category") == "message" and "body" in payload:
                payload["body"] = _strip_identity_from_text(str(payload["body"]))
    return items


class AstraBackend:
    """Thread-safe stateful AstroGuard backend orchestrating store, engines, and policy layers."""

    def __init__(self, seed: int = 42, days: int = 30, db_path: str = ":memory:") -> None:
        self.seed = int(seed)
        self.days = int(days)
        self.db_path = db_path
        self._lock = threading.RLock()
        self.store = AstraStore(db_path=db_path)
        self.consent = ConsentManager(self.store)
        self.sync_manager = SyncManager(self.store, online=False)
        self.sos = SOSService(self.store, self.consent, self.sync_manager)
        self.messaging = MessagingService(self.store, self.consent, self.sync_manager)
        self.alert_engine = AlertPolicyEngine(weekly_budget=3, cooldown_days=2, min_confidence=0.65)
        self.zone_occupancy: Dict[str, Dict[int, str]] = {}
        self.manifest: List[Dict[str, Any]] = []
        self._analytics_version = 0
        self._analytics_cache: Dict[Tuple[int, int], Dict[str, Any]] = {}

        self._seed_mission(seed=self.seed, days=self.days)
        # Pre-warm default mission day so live UI polls respond well within 2.2s timeout.
        self._get_day_analytics(min(23, self.days))

    def close(self) -> None:
        """Close underlying SQLite connections cleanly."""
        with self._lock:
            self.store.close()

    def _seed_mission(self, seed: int, days: int) -> None:
        mission = generate_mission(days=days, seed=seed)
        records: List[MeasurementRecord] = mission["records"]
        self.store.append_measurements(records)
        self.zone_occupancy = mission["zone_occupancy"]
        self.manifest = mission["manifest"]

        self._seed_checkins_and_pvts(records, max_day=min(23, days))
        self._seed_expected_sos(mission.get("expected_sos", []), records, max_day=days)
        self._seed_messages_and_queue(max_day=min(23, days))

    def _seed_checkins_and_pvts(self, records: Sequence[MeasurementRecord], max_day: int) -> None:
        by_crew_day: Dict[Tuple[str, int], Dict[str, float]] = {}
        for rec in records:
            if rec.day > max_day or rec.astronaut_id not in CREW_BY_ID or rec.value is None:
                continue
            if rec.quality != QualityState.OK.value:
                continue
            bucket = by_crew_day.setdefault((rec.astronaut_id, rec.day), {})
            if rec.signal_type in (
                SignalType.MOOD_SCORE.value,
                SignalType.ENERGY_SCORE.value,
                SignalType.STRESS_SCORE.value,
                SignalType.SYMPTOM_HEADACHE.value,
                SignalType.SYMPTOM_FATIGUE.value,
                SignalType.PVT_MEAN_RT.value,
                SignalType.PVT_LAPSES.value,
            ):
                bucket[rec.signal_type] = float(rec.value)

        for crew in CREW_ROSTER:
            aid = crew.astronaut_id
            for day in range(1, max_day + 1):
                vals = by_crew_day.get((aid, day), {})
                self.store.insert_checkin(
                    astronaut_id=aid,
                    day=day,
                    hour=16,
                    timestamp_utc=_mission_iso(day, 16),
                    mood=round(vals.get(SignalType.MOOD_SCORE.value, 4.0), 1),
                    energy=round(vals.get(SignalType.ENERGY_SCORE.value, 4.0), 1),
                    stress=round(vals.get(SignalType.STRESS_SCORE.value, 2.0), 1),
                    headache=round(vals.get(SignalType.SYMPTOM_HEADACHE.value, 0.0), 1),
                    fatigue=round(vals.get(SignalType.SYMPTOM_FATIGUE.value, 1.0), 1),
                    note="",
                    safety_flag=False,
                    safety_concern=False,
                )
                if SignalType.PVT_MEAN_RT.value in vals or SignalType.PVT_LAPSES.value in vals:
                    self.store.insert_pvt(
                        astronaut_id=aid,
                        day=day,
                        hour=9,
                        timestamp_utc=_mission_iso(day, 9),
                        mean_rt_ms=round(vals.get(SignalType.PVT_MEAN_RT.value, 250.0), 1),
                        lapses=int(round(vals.get(SignalType.PVT_LAPSES.value, 0.0))),
                        trials=40,
                    )

    def _snapshot_for_sos(
        self,
        records: Sequence[MeasurementRecord],
        astronaut_id: str,
        day: int,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        vitals: Dict[str, Any] = {}
        target_sigs = {
            SignalType.HEART_RATE.value,
            SignalType.RESTING_HR.value,
            SignalType.HRV_RMSSD.value,
            SignalType.HR_RECOVERY_1M.value,
            SignalType.SPO2.value,
            SignalType.SLEEP_DURATION.value,
        }
        zone_co2: Dict[str, float] = {}
        for rec in records:
            if rec.day > day or rec.value is None or rec.quality != QualityState.OK.value:
                continue
            if rec.astronaut_id == astronaut_id and rec.signal_type in target_sigs:
                vitals[rec.signal_type] = round(float(rec.value), 2)
            elif rec.signal_type == SignalType.CO2_PPM.value and rec.zone_id:
                zone_co2[rec.zone_id] = round(float(rec.value), 1)
        env_snap = {"zone_co2_ppm": zone_co2, "zone_id": self.zone_occupancy.get(astronaut_id, {}).get(day, "LAB")}
        return vitals, env_snap

    def _seed_expected_sos(
        self,
        expected_sos: Sequence[Dict[str, Any]],
        records: Sequence[MeasurementRecord],
        max_day: int,
    ) -> None:
        for exp in expected_sos:
            sos_day = int(exp.get("day", 23))
            if sos_day > max_day:
                continue
            aid = str(exp.get("astronaut_id") or "ast-01")
            sos_type = _normalize_sos_type(exp.get("sos_type", "medical"))
            hour = int(exp.get("hour", 14))
            vitals, env_snap = self._snapshot_for_sos(records, aid, sos_day)
            pkt = self.sos.trigger_sos(
                astronaut_id=aid,
                sos_type=sos_type,
                note=str(exp.get("note") or ""),
                day=sos_day,
                hour=hour,
                vitals_snapshot=vitals,
                env_snapshot=env_snap,
            )
            self.sos.acknowledge_sos(pkt["sos_id"], actor="Crew Health Officer")

    def _seed_messages_and_queue(self, max_day: int) -> None:
        if max_day >= 22:
            self.messaging.send_message(
                sender_id="ast-01",
                recipient="Crew Health Officer",
                body="Evening recovery block complete. Heart rate took longer than usual to settle; keeping hydration up.",
                msg_type="text",
                priority="routine",
                day=22,
                hour=20,
            )
            self.messaging.send_message(
                sender_id="systems",
                recipient="All crew",
                body="US Lab CO2 scrubber service complete on Day 22; post-service reading near 1,113 ppm with portable monitor running.",
                msg_type="text",
                priority="routine",
                day=22,
                hour=21,
            )
        self.messaging.send_message(
            sender_id="health_officer",
            recipient="ast-01",
            body="On-board SOS acknowledged. Rest block scheduled; follow PROT-MED-01 and PROT-REC-01 until recovery steadies.",
            msg_type="text",
            priority="urgent",
            day=max_day,
            hour=14,
        )
        self.messaging.send_message(
            sender_id="ast-01",
            recipient="Home (Earth)",
            body="Crew mission day update: prioritizing structured rest and ventilation verification while downlink is offline.",
            msg_type="text",
            priority="routine",
            attach_health_chart=False,
            day=max_day,
            hour=15,
        )
        self.sync_manager.enqueue(
            category="critical_alert",
            item_id=f"sync-crit-d{max_day}",
            payload={
                "rule_id": "SR-05",
                "summary": "Anonymized safety protocol summary queued for ground review.",
                "day": max_day,
            },
            meta={"priority": 1, "day": max_day},
        )
        self.sync_manager.enqueue(
            category="summary",
            item_id=f"sync-sum-d{max_day}",
            payload={
                "day": max_day,
                "crew_count": len(CREW_ROSTER),
                "summary_note": "Consented daily readiness band rollup.",
            },
            meta={"priority": 3, "day": max_day},
        )
        self.sync_manager.enqueue(
            category="telemetry",
            item_id=f"sync-tel-d{max_day}",
            payload={
                "day": max_day,
                "packet_type": "compact_habitat_rollup",
                "zones": ["N1", "LAB", "CQ", "AL"],
            },
            meta={"priority": 4, "day": max_day},
        )

    def _compute_day_analytics(self, up_to_day: int) -> Dict[str, Any]:
        records = self.store.get_measurements(max_day=up_to_day)
        checkins = self.store.get_checkins(max_day=up_to_day)

        env_data = analyze_crew_environment(
            records,
            zone_occupancy=self.zone_occupancy,
            up_to_day=up_to_day,
            n_permutations=40,
            seed=self.seed,
        )
        rad_daily_vals = [
            float(r.value)
            for r in records
            if r.day == up_to_day
            and r.signal_type == SignalType.RADIATION_USV_DAY.value
            and r.quality == QualityState.OK.value
            and r.value is not None
        ]
        rad_cum_vals = [
            float(r.value)
            for r in records
            if r.day <= up_to_day
            and r.signal_type == SignalType.RADIATION_CUMULATIVE_MSV.value
            and r.quality == QualityState.OK.value
            and r.value is not None
        ]
        if rad_daily_vals:
            env_data["radiation_daily_usv"] = round(rad_daily_vals[-1], 1)
        if rad_cum_vals:
            env_data["radiation_cumulative_msv"] = round(rad_cum_vals[-1], 2)

        mside_data = discover_interactions(
            records,
            zone_occupancy=self.zone_occupancy,
            up_to_day=up_to_day,
            n_permutations=40,
            seed=self.seed,
        )

        # Aggregate anonymized crew climate score for behavioral layer 3
        mood_vals = [float(c["mood"]) for c in checkins if c.get("mood") is not None and int(c.get("day", 0)) >= max(1, up_to_day - 2)]
        climate_score = round(sum(mood_vals) / len(mood_vals), 2) if mood_vals else None
        crew_climate = {"score": climate_score} if climate_score is not None else None

        readiness_by_crew: Dict[str, Dict[str, Any]] = {}
        behavioral_by_crew: Dict[str, Dict[str, Any]] = {}
        flags_by_crew: Dict[str, List[Dict[str, Any]]] = {}

        for crew in CREW_ROSTER:
            aid = crew.astronaut_id
            aid_checkins = [c for c in checkins if c.get("astronaut_id") == aid]
            r_raw = compute_readiness(
                records,
                aid,
                up_to_day=up_to_day,
                active_safety_rules=None,
                env_confounders=env_data,
            )
            b_raw = assess_behavioral_health(
                records,
                checkins=aid_checkins,
                crew_climate=crew_climate,
                astronaut_id=aid,
                up_to_day=up_to_day,
                env_confounders=env_data,
            )
            readiness_by_crew[aid] = _enrich_readiness(r_raw)
            behavioral_by_crew[aid] = b_raw
            flags_by_crew[aid] = list(r_raw.get("flags", []))

        return {
            "up_to_day": up_to_day,
            "records": records,
            "checkins": checkins,
            "env_data": env_data,
            "mside_data": mside_data,
            "readiness_by_crew": readiness_by_crew,
            "behavioral_by_crew": behavioral_by_crew,
            "flags_by_crew": flags_by_crew,
        }

    def _get_day_analytics(self, up_to_day: int) -> Dict[str, Any]:
        day = max(1, min(int(up_to_day), self.days))
        with self._lock:
            key = (self._analytics_version, day)
            cached = self._analytics_cache.get(key)
            if cached is not None:
                return cached
            computed = self._compute_day_analytics(day)
            self._analytics_cache[key] = computed
            return computed

    def _evaluate_live_safety(self, analytics: Dict[str, Any], up_to_day: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        sos_events = self.sos.list_sos()
        safety_rules = evaluate_safety_rules(
            analytics["records"],
            sos_events=sos_events,
            checkins=analytics["checkins"],
            up_to_day=up_to_day,
        )
        return safety_rules, sos_events

    def _apply_live_safety_to_readiness(
        self,
        readiness: Dict[str, Any],
        safety_rules_for_aid: Sequence[Dict[str, Any]],
    ) -> Dict[str, Any]:
        out = copy.deepcopy(readiness)
        active_rules = [r for r in safety_rules_for_aid if r.get("active")]
        out["active_safety_rules"] = active_rules
        out["safety_active"] = len(active_rules) > 0
        if active_rules:
            out["band"] = "Safety review"
        return out

    def _safety_for_astronaut(
        self,
        safety_rules: Sequence[Dict[str, Any]],
        astronaut_id: str,
    ) -> List[Dict[str, Any]]:
        matched: List[Dict[str, Any]] = []
        crew_zone = self.zone_occupancy.get(astronaut_id, {})
        for rule in safety_rules:
            r_aid = rule.get("astronaut_id")
            if r_aid == astronaut_id:
                matched.append(rule)
            elif rule.get("rule_id") == "SR-03" and rule.get("active"):
                r_zone = rule.get("zone_id")
                if not r_zone or r_zone in crew_zone.values():
                    matched.append(rule)
        return matched

    def _sanitize_env_for_role(self, env_data: Dict[str, Any], *, anonymize_confounders: bool) -> Dict[str, Any]:
        out = copy.deepcopy(env_data)
        if anonymize_confounders:
            cleaned_flags: List[Dict[str, Any]] = []
            for flag in out.get("confounder_flags", []):
                if not isinstance(flag, dict):
                    continue
                item = dict(flag)
                aid = str(item.get("astronaut_id") or "")
                if aid in _ANON_CREW_LABELS:
                    item["crew_label"] = _ANON_CREW_LABELS[aid]
                item.pop("astronaut_id", None)
                item["reason"] = _strip_identity_from_text(str(item.get("reason") or ""))
                item["summary"] = _strip_identity_from_text(str(item.get("summary") or ""))
                cleaned_flags.append(item)
            out["confounder_flags"] = cleaned_flags
            for corr in out.get("crew_correlations", []):
                if isinstance(corr, dict):
                    corr.pop("astronaut_id", None)
                    corr["summary"] = _strip_identity_from_text(str(corr.get("summary") or ""))
        return out

    def _sanitize_mside_for_role(self, mside_data: Dict[str, Any], *, shared_only: bool) -> Dict[str, Any]:
        out = copy.deepcopy(mside_data)
        shared_findings: List[Dict[str, Any]] = []
        for f in out.get("shared_exposure_findings", []):
            item = dict(f)
            aid = str(item.get("astronaut_id") or "")
            if aid in _ANON_CREW_LABELS:
                item["crew_label"] = _ANON_CREW_LABELS[aid]
            item.pop("astronaut_id", None)
            item["summary"] = _strip_identity_from_text(str(item.get("summary") or ""))
            shared_findings.append(item)
        out["shared_exposure_findings"] = shared_findings
        if shared_only:
            out["personal_findings"] = []
            out["findings"] = shared_findings
            out["all_candidates"] = []
        return out

    def _earth_link_status(self) -> Dict[str, Any]:
        queue_items = self.sync_manager.list_queue(include_acknowledged=True)
        pending = [q for q in queue_items if q.get("status") != "acknowledged"]
        return {
            "online": bool(self.sync_manager.online),
            "delay_minutes": LIGHT_DELAY_MINUTES,
            "bandwidth_kbps": 2.4,
            "pending_count": len(pending),
            "total_count": len(queue_items),
        }

    def get_state(
        self,
        day: int = 23,
        role: str = Role.ASTRONAUT.value,
        crew_id: str = "ast-01",
    ) -> Dict[str, Any]:
        with self._lock:
            target_day = max(1, min(int(day), self.days))
            canonical_role = _normalize_role(role or Role.ASTRONAUT.value)
            selected_id = _normalize_crew_id(crew_id, default="ast-01")
            analytics = self._get_day_analytics(target_day)
            safety_rules, sos_events = self._evaluate_live_safety(analytics, target_day)

            env_raw = analytics["env_data"]
            mside_raw = analytics["mside_data"]
            queue_items = self.sync_manager.list_queue(include_acknowledged=True)
            earth_link = self._earth_link_status()
            active_safety_all = [r for r in safety_rules if r.get("active")]
            all_messages = self.messaging.list_messages(filter_scope="All")

            if canonical_role == Role.SYSTEMS_ENGINEER.value:
                return self._build_systems_engineer_state(
                    day=target_day,
                    safety_rules=safety_rules,
                    active_safety_all=active_safety_all,
                    sos_events=sos_events,
                    env_raw=env_raw,
                    mside_raw=mside_raw,
                    messages=all_messages,
                    queue_items=queue_items,
                    earth_link=earth_link,
                )

            if canonical_role == Role.GROUND_SUPPORT.value:
                return self._build_ground_support_state(
                    day=target_day,
                    analytics=analytics,
                    safety_rules=safety_rules,
                    active_safety_all=active_safety_all,
                    sos_events=sos_events,
                    env_raw=env_raw,
                    messages=all_messages,
                    queue_items=queue_items,
                    earth_link=earth_link,
                )

            if canonical_role == Role.HEALTH_OFFICER.value:
                return self._build_health_officer_state(
                    day=target_day,
                    selected_id=selected_id,
                    analytics=analytics,
                    safety_rules=safety_rules,
                    active_safety_all=active_safety_all,
                    sos_events=sos_events,
                    env_raw=env_raw,
                    mside_raw=mside_raw,
                    messages=all_messages,
                    queue_items=queue_items,
                    earth_link=earth_link,
                )

            return self._build_astronaut_state(
                day=target_day,
                selected_id=selected_id,
                analytics=analytics,
                safety_rules=safety_rules,
                active_safety_all=active_safety_all,
                sos_events=sos_events,
                env_raw=env_raw,
                mside_raw=mside_raw,
                messages=all_messages,
                queue_items=queue_items,
                earth_link=earth_link,
            )

    def _build_systems_engineer_state(
        self,
        *,
        day: int,
        safety_rules: List[Dict[str, Any]],
        active_safety_all: List[Dict[str, Any]],
        sos_events: List[Dict[str, Any]],
        env_raw: Dict[str, Any],
        mside_raw: Dict[str, Any],
        messages: List[Dict[str, Any]],
        queue_items: List[Dict[str, Any]],
        earth_link: Dict[str, Any],
    ) -> Dict[str, Any]:
        for crew in CREW_ROSTER:
            self.consent.check_access(
                viewer_role=Role.SYSTEMS_ENGINEER.value,
                target_astronaut_id=crew.astronaut_id,
                scope=ConsentScope.HABITAT.value,
                active_critical_rule=False,
                reason="anonymized habitat environmental telemetry",
            )
        sanitized_env = self._sanitize_env_for_role(env_raw, anonymize_confounders=True)
        sanitized_mside = self._sanitize_mside_for_role(mside_raw, shared_only=True)
        anonymized_rules = [_sanitize_safety_rule(r, anonymize=True) for r in safety_rules]
        anonymized_active = [r for r in anonymized_rules if r.get("active")]
        anonymized_sos = [_format_sos_event(s, anonymize=True) for s in sos_events]
        ops_msgs = [
            _format_message(m, anonymize_crew_sender=True)
            for m in messages
            if (
                "systems" in str(m.get("sender_id", "")).lower()
                or "systems" in str(m.get("recipient", "")).lower()
                or m.get("channel") == "earth"
            )
        ]

        return {
            "day": day,
            "hour": 16,
            "role": Role.SYSTEMS_ENGINEER.value,
            "selected_crew_id": None,
            "crew_roster": [],
            "astronaut": None,
            "crew": None,
            "crew_overview": None,
            "environment": sanitized_env,
            "mside": sanitized_mside,
            "safety": {
                "active_rules": anonymized_active,
                "all_rules": anonymized_rules,
                "timeline": anonymized_sos,
                "active": len(anonymized_active) > 0,
            },
            "active_safety_rules": anonymized_active,
            "sos_events": anonymized_sos,
            "consent_matrix": {},
            "access_log": [],
            "messages": ops_msgs,
            "earth_link": earth_link,
            "sync_queue": _sanitize_sync_queue(queue_items, anonymize=True),
            "sync_summary": earth_link,
            "advisor": {
                "confidence": 0.88,
                "confidence_pct": 88,
                "gap_count": len(sanitized_env.get("environmental_gaps", [])),
                "suggested_questions": [
                    "Does US Lab CO2 explain the shared crew symptom signal?",
                    "Which environmental sensor gaps remain open?",
                ],
                "hard_boundaries": _HARD_BOUNDARIES,
            },
        }

    def _build_ground_support_state(
        self,
        *,
        day: int,
        analytics: Dict[str, Any],
        safety_rules: List[Dict[str, Any]],
        active_safety_all: List[Dict[str, Any]],
        sos_events: List[Dict[str, Any]],
        env_raw: Dict[str, Any],
        messages: List[Dict[str, Any]],
        queue_items: List[Dict[str, Any]],
        earth_link: Dict[str, Any],
    ) -> Dict[str, Any]:
        band_counts = {"safety_review": 0, "reduced": 0, "monitor": 0, "steady": 0}
        advisory_total = 0
        consented_count = 0
        withheld_count = 0
        anonymized_consent_counts: Dict[str, Dict[str, Any]] = {}

        for crew in CREW_ROSTER:
            aid = crew.astronaut_id
            aid_rules = self._safety_for_astronaut(safety_rules, aid)
            has_crit = any(r.get("active") for r in aid_rules)
            decision = self.consent.check_access(
                viewer_role=Role.GROUND_SUPPORT.value,
                target_astronaut_id=aid,
                scope=ConsentScope.GROUND_SHARING.value,
                active_critical_rule=has_crit,
                reason="ground support aggregate band summary",
            )
            allowed = bool(decision.get("allowed", False))
            anonymized_consent_counts[crew.anonymous_label] = {
                "normal": {"ground_sharing": allowed},
            }
            if allowed:
                consented_count += 1
            else:
                withheld_count += 1

            r_aid = self._apply_live_safety_to_readiness(analytics["readiness_by_crew"][aid], aid_rules)
            band = str(r_aid.get("band", "Steady")).lower()
            if "safety" in band or has_crit:
                band_counts["safety_review"] += 1
            elif "reduced" in band:
                band_counts["reduced"] += 1
            elif "watch" in band or "monitor" in band:
                band_counts["monitor"] += 1
            else:
                band_counts["steady"] += 1

            eval_res = self.alert_engine.evaluate_alerts(
                analytics["flags_by_crew"][aid],
                aid_rules,
                up_to_day=day,
            )
            advisory_total += len(eval_res.get("active_alerts", []))

        anonymized_rules = []
        for rule in safety_rules:
            s_rule = _sanitize_safety_rule(rule, anonymize=True)
            s_rule["as_of"] = f"Day {day} 16:00 UTC · sync {'live' if earth_link['online'] else 'offline cached'}"
            anonymized_rules.append(s_rule)
        anonymized_active = [r for r in anonymized_rules if r.get("active")]
        anonymized_sos = []
        for pkt in sos_events:
            s_pkt = _format_sos_event(pkt, anonymize=True)
            s_pkt["as_of"] = f"Day {day} · priority 0 relay"
            anonymized_sos.append(s_pkt)

        earth_msgs = [
            _format_message(m, anonymize_crew_sender=True)
            for m in messages
            if (
                m.get("channel") == "earth"
                or "earth" in str(m.get("recipient", "")).lower()
                or "home" in str(m.get("recipient", "")).lower()
            )
        ]

        shared_signal = copy.deepcopy(env_raw.get("shared_exposure_alert", {}))
        if isinstance(shared_signal, dict) and shared_signal.get("summary"):
            shared_signal["summary"] = _strip_identity_from_text(str(shared_signal["summary"]))

        ground_summary = {
            "crew_count": len(CREW_ROSTER),
            "band_counts": band_counts,
            "safety_events_count": len(anonymized_active),
            "advisory_alerts_count": advisory_total,
            "consented_summary_count": consented_count,
            "withheld_ground_sharing_count": withheld_count,
            "shared_exposure_signal": shared_signal,
            "as_of_day": day,
            "sync_lag_note": (
                "Link online — telemetry relay synchronized."
                if earth_link["online"]
                else f"Earth link offline · {earth_link['pending_count']} priority packet(s) queued onboard."
            ),
        }

        return {
            "day": day,
            "hour": 16,
            "role": Role.GROUND_SUPPORT.value,
            "selected_crew_id": None,
            "crew_roster": [],
            "astronaut": None,
            "crew": None,
            "crew_overview": None,
            "ground_summary": ground_summary,
            "environment": {
                "shared_exposure_alert": shared_signal,
                "radiation_daily_usv": env_raw.get("radiation_daily_usv"),
                "radiation_cumulative_msv": env_raw.get("radiation_cumulative_msv"),
            },
            "safety": {
                "active_rules": anonymized_active,
                "all_rules": anonymized_rules,
                "timeline": anonymized_sos,
                "active": len(anonymized_active) > 0,
            },
            "active_safety_rules": anonymized_active,
            "sos_events": anonymized_sos,
            "consent_matrix": anonymized_consent_counts,
            "access_log": [],
            "messages": earth_msgs,
            "earth_link": earth_link,
            "sync_queue": _sanitize_sync_queue(queue_items, anonymize=True),
            "sync_summary": earth_link,
            "advisor": {
                "confidence": 0.85,
                "confidence_pct": 85,
                "gap_count": 0,
                "suggested_questions": ["Summarize mission readiness bands without identities."],
                "hard_boundaries": _HARD_BOUNDARIES,
            },
        }

    def _build_health_officer_state(
        self,
        *,
        day: int,
        selected_id: str,
        analytics: Dict[str, Any],
        safety_rules: List[Dict[str, Any]],
        active_safety_all: List[Dict[str, Any]],
        sos_events: List[Dict[str, Any]],
        env_raw: Dict[str, Any],
        mside_raw: Dict[str, Any],
        messages: List[Dict[str, Any]],
        queue_items: List[Dict[str, Any]],
        earth_link: Dict[str, Any],
    ) -> Dict[str, Any]:
        consent_matrix = self.consent.get_consent_matrix()
        crew_overview: List[Dict[str, Any]] = []
        selected_astronaut_payload: Optional[Dict[str, Any]] = None
        top_alerts: List[Dict[str, Any]] = []

        crew_allowed_map: Dict[str, set[str]] = {}
        crew_has_crit_map: Dict[str, bool] = {}

        for crew in CREW_ROSTER:
            aid = crew.astronaut_id
            aid_rules = self._safety_for_astronaut(safety_rules, aid)
            has_crit = any(r.get("active") for r in aid_rules)
            crew_has_crit_map[aid] = has_crit
            r_live = self._apply_live_safety_to_readiness(analytics["readiness_by_crew"][aid], aid_rules)
            b_live = copy.deepcopy(analytics["behavioral_by_crew"][aid])
            eval_alerts = self.alert_engine.evaluate_alerts(
                analytics["flags_by_crew"][aid],
                aid_rules,
                up_to_day=day,
            )
            briefing = _enrich_briefing(
                build_daily_briefing(
                    r_live,
                    behavioral_data=b_live,
                    env_data=env_raw,
                    mside_data=mside_raw,
                    active_safety_rules=[r for r in aid_rules if r.get("active")],
                    astronaut_id=aid,
                    up_to_day=day,
                ),
                r_live,
                aid_rules,
            )

            data_by_scope = {
                ConsentScope.PHYSIO.value: {
                    "recovery_debt": r_live.get("recovery_debt"),
                    "latest_readings": r_live.get("latest_readings"),
                },
                ConsentScope.COGNITIVE.value: {
                    "cognitive_readiness": r_live.get("cognitive_readiness"),
                },
                ConsentScope.BEHAVIOUR.value: b_live,
                ConsentScope.HABITAT.value: {
                    "zone_id": self.zone_occupancy.get(aid, {}).get(day, crew.default_zone),
                    "env_confounders": r_live.get("env_confounders", []),
                },
                ConsentScope.GROUND_SHARING.value: {"band": r_live.get("band")},
            }
            redacted = self.consent.redact_for_role(
                viewer_role=Role.HEALTH_OFFICER.value,
                target_astronaut_id=aid,
                data_by_scope=data_by_scope,
                active_critical_rule=has_crit,
                reason="crew health officer overview",
            )
            allowed_scopes = set(redacted["allowed_scopes"])
            crew_allowed_map[aid] = allowed_scopes
            withheld_scopes = list(redacted["redacted_scopes"])

            rec_payload = (
                r_live.get("recovery_debt", {})
                if ConsentScope.PHYSIO.value in allowed_scopes
                else {
                    "score": None,
                    "status": "Redacted by consent",
                    "confidence": 0.0,
                    "summary": "Physiological recovery withheld by astronaut consent switch.",
                    "redacted": True,
                }
            )
            cog_payload = (
                r_live.get("cognitive_readiness", {})
                if ConsentScope.COGNITIVE.value in allowed_scopes
                else {
                    "score": None,
                    "status": "Scoped (consent off)",
                    "confidence": 0.0,
                    "summary": "Cognitive readiness withheld by astronaut normal consent switch.",
                    "redacted": True,
                }
            )
            beh_payload = (
                b_live
                if ConsentScope.BEHAVIOUR.value in allowed_scopes
                else {
                    "status": "Redacted by astronaut privacy switch",
                    "summary": "Personal behavioral check-in notes withheld unless astronaut enables consent.",
                    "redacted": True,
                }
            )

            cog_withheld = ConsentScope.COGNITIVE.value not in allowed_scopes
            phys_withheld = ConsentScope.PHYSIO.value not in allowed_scopes
            scoped = cog_withheld or phys_withheld
            band_display = (
                "Safety review"
                if has_crit
                else "Scoped"
                if scoped
                else r_live.get("band", "Steady")
            )
            readiness_score_display = None if scoped else round(float(r_live.get("readiness_score", 0.0)))

            # Filter advisory alerts cleanly against withheld scopes while never hiding deterministic safety alerts
            visible_alerts: List[Dict[str, Any]] = []
            for sa in eval_alerts.get("safety_alerts", []):
                visible_alerts.append(sa)
            for al in eval_alerts.get("active_alerts", []):
                sig = str(al.get("signal", ""))
                sig_scope = SIGNAL_TO_SCOPE.get(sig, ConsentScope.PHYSIO.value)
                if sig_scope in allowed_scopes or has_crit:
                    visible_alerts.append(al)
                else:
                    visible_alerts.append(
                        {
                            **al,
                            "summary": "Details scoped by astronaut consent switch.",
                            "redacted": True,
                        }
                    )

            if aid == selected_id:
                top_alerts = visible_alerts
                redacted_readiness = copy.deepcopy(r_live)
                redacted_readiness["band"] = band_display
                redacted_readiness["readiness_score"] = readiness_score_display
                redacted_readiness["recovery_debt"] = rec_payload
                redacted_readiness["cognitive_readiness"] = cog_payload
                if scoped:
                    redacted_readiness["data_quality"]["summary"] = (
                        "Partial telemetry scoped by astronaut consent settings."
                    )
                selected_astronaut_payload = {
                    "profile": asdict(crew),
                    "readiness": redacted_readiness,
                    "behavioral": beh_payload,
                    "briefing": briefing,
                    "alerts": visible_alerts,
                    "alert_policy": eval_alerts,
                    "consent": consent_matrix.get(aid),
                    "observations": _build_observations(r_live) if not scoped else [],
                    "withheld_scopes": withheld_scopes,
                    "override_active": redacted["override_active"],
                }

            crew_overview.append(
                {
                    "astronaut_id": aid,
                    "name": crew.name,
                    "role": crew.title,
                    "title": crew.title,
                    "initials": "".join(part[0] for part in crew.name.split()[-2:]),
                    "default_zone": crew.default_zone,
                    "readiness_score": readiness_score_display,
                    "band": band_display,
                    "status": band_display,
                    "confidence": r_live.get("confidence", 0.85),
                    "data_coverage_pct": r_live["data_quality"]["coverage_pct"],
                    "recovery": rec_payload,
                    "cognitive": cog_payload,
                    "behavioural": beh_payload,
                    "behavioral": beh_payload,
                    "alerts": visible_alerts,
                    "alert_count": len(eval_alerts.get("active_alerts", [])),
                    "safety_count": len([r for r in aid_rules if r.get("active")]),
                    "briefing": [
                        briefing.get("what_changed", ""),
                        briefing.get("how_sure_why", ""),
                        f"Next: {briefing.get('single_best_next_step', '')}",
                    ],
                    "protocols": briefing.get("protocol_refs", []),
                    "withheld_scopes": withheld_scopes,
                    "allowed_scopes": sorted(allowed_scopes),
                    "override_active": redacted["override_active"],
                    "shared_cluster": bool(r_live.get("env_confounders")),
                }
            )

        ho_msgs = [
            _format_message(m)
            for m in messages
            if (
                "health" in str(m.get("sender_id", "")).lower()
                or "health" in str(m.get("recipient", "")).lower()
                or "systems" in str(m.get("sender_id", "")).lower()
                or str(m.get("recipient", "")).lower() in ("all", "all crew")
            )
        ]

        mside_ho = self._sanitize_mside_for_role(mside_raw, shared_only=False)
        filtered_personal: List[Dict[str, Any]] = []
        for item in mside_ho.get("personal_findings", []):
            if not isinstance(item, dict):
                continue
            target_aid = str(item.get("astronaut_id") or "")
            allowed = crew_allowed_map.get(target_aid, set())
            if crew_has_crit_map.get(target_aid) or (
                ConsentScope.PHYSIO.value in allowed and ConsentScope.COGNITIVE.value in allowed
            ):
                filtered_personal.append(item)
        mside_ho["personal_findings"] = filtered_personal

        return {
            "day": day,
            "hour": 16,
            "role": Role.HEALTH_OFFICER.value,
            "selected_crew_id": selected_id,
            "crew_roster": [asdict(c) for c in CREW_ROSTER],
            "astronaut": selected_astronaut_payload,
            "crew": selected_astronaut_payload,
            "crew_overview": crew_overview,
            "environment": self._sanitize_env_for_role(env_raw, anonymize_confounders=True),
            "mside": mside_ho,
            "safety": {
                "active_rules": active_safety_all,
                "all_rules": safety_rules,
                "timeline": [_format_sos_event(s) for s in sos_events],
                "active": len(active_safety_all) > 0,
            },
            "active_safety_rules": active_safety_all,
            "sos_events": [_format_sos_event(s) for s in sos_events],
            "alerts": top_alerts,
            "consent_matrix": consent_matrix,
            "access_log": self.store.get_access_log(limit=120),
            "messages": ho_msgs,
            "earth_link": earth_link,
            "sync_queue": queue_items,
            "sync_summary": earth_link,
            "advisor": {
                "confidence": selected_astronaut_payload["readiness"].get("confidence", 0.85)
                if selected_astronaut_payload
                else 0.85,
                "confidence_pct": round(
                    float(
                        (selected_astronaut_payload or {})
                        .get("readiness", {})
                        .get("confidence", 0.85)
                    )
                    * 100
                ),
                "gap_count": len(env_raw.get("environmental_gaps", [])),
                "suggested_questions": _SUGGESTED_QUESTIONS,
                "hard_boundaries": _HARD_BOUNDARIES,
            },
        }

    def _build_astronaut_state(
        self,
        *,
        day: int,
        selected_id: str,
        analytics: Dict[str, Any],
        safety_rules: List[Dict[str, Any]],
        active_safety_all: List[Dict[str, Any]],
        sos_events: List[Dict[str, Any]],
        env_raw: Dict[str, Any],
        mside_raw: Dict[str, Any],
        messages: List[Dict[str, Any]],
        queue_items: List[Dict[str, Any]],
        earth_link: Dict[str, Any],
    ) -> Dict[str, Any]:
        crew = CREW_BY_ID[selected_id]
        aid_rules = self._safety_for_astronaut(safety_rules, selected_id)
        has_crit = any(r.get("active") for r in aid_rules)

        self.consent.check_access(
            viewer_role=Role.ASTRONAUT.value,
            target_astronaut_id=selected_id,
            scope=ConsentScope.PHYSIO.value,
            active_critical_rule=has_crit,
            reason="astronaut self daily briefing",
            viewer_id=selected_id,
        )

        r_live = self._apply_live_safety_to_readiness(analytics["readiness_by_crew"][selected_id], aid_rules)
        b_live = analytics["behavioral_by_crew"][selected_id]
        eval_alerts = self.alert_engine.evaluate_alerts(
            analytics["flags_by_crew"][selected_id],
            aid_rules,
            up_to_day=day,
        )
        briefing = _enrich_briefing(
            build_daily_briefing(
                r_live,
                behavioral_data=b_live,
                env_data=env_raw,
                mside_data=mside_raw,
                active_safety_rules=[r for r in aid_rules if r.get("active")],
                astronaut_id=selected_id,
                up_to_day=day,
            ),
            r_live,
            aid_rules,
        )

        own_consent = self.consent.get_profile(selected_id)
        astronaut_alerts = list(eval_alerts.get("safety_alerts", [])) + list(eval_alerts.get("active_alerts", []))
        astronaut_payload = {
            "profile": asdict(crew),
            "readiness": r_live,
            "behavioral": b_live,
            "briefing": briefing,
            "alerts": astronaut_alerts,
            "alert_policy": eval_alerts,
            "consent": own_consent,
            "observations": _build_observations(r_live),
        }

        visible_msgs = [
            _format_message(m)
            for m in messages
            if (
                str(m.get("sender_id", "")).lower() == selected_id
                or str(m.get("recipient", "")).lower() in (selected_id, crew.name.lower(), "all", "all crew")
            )
        ]

        # Lightweight non-private team header cards (no peer behavioral/diary notes exposed)
        crew_summary_cards = []
        for member in CREW_ROSTER:
            mid = member.astronaut_id
            m_rules = self._safety_for_astronaut(safety_rules, mid)
            m_readiness = self._apply_live_safety_to_readiness(analytics["readiness_by_crew"][mid], m_rules)
            crew_summary_cards.append(
                {
                    "astronaut_id": mid,
                    "name": member.name,
                    "role": member.title,
                    "title": member.title,
                    "default_zone": member.default_zone,
                    "band": m_readiness.get("band", "Steady"),
                }
            )

        selected_sos = [_format_sos_event(s) for s in sos_events]
        return {
            "day": day,
            "hour": 16,
            "role": Role.ASTRONAUT.value,
            "selected_crew_id": selected_id,
            "crew_roster": [asdict(c) for c in CREW_ROSTER],
            "astronaut": astronaut_payload,
            "crew": astronaut_payload,
            "crew_overview": crew_summary_cards,
            "environment": self._sanitize_env_for_role(env_raw, anonymize_confounders=True),
            "mside": self._sanitize_mside_for_role(mside_raw, shared_only=False),
            "safety": {
                "active_rules": [r for r in aid_rules if r.get("active")],
                "all_rules": aid_rules,
                "global_active_rules": active_safety_all,
                "timeline": selected_sos,
                "active": has_crit,
            },
            "active_safety_rules": [r for r in aid_rules if r.get("active")],
            "sos_events": selected_sos,
            "alerts": astronaut_alerts,
            "alert_policy": eval_alerts,
            "consent_matrix": {selected_id: own_consent},
            "access_log": self.store.get_access_log(astronaut_id=selected_id, limit=80),
            "messages": visible_msgs,
            "earth_link": earth_link,
            "sync_queue": queue_items,
            "sync_summary": earth_link,
            "advisor": {
                "confidence": r_live.get("confidence", 0.85),
                "confidence_pct": round(float(r_live.get("confidence", 0.85)) * 100),
                "gap_count": len(r_live.get("data_quality", {}).get("gaps", [])),
                "suggested_questions": _SUGGESTED_QUESTIONS,
                "hard_boundaries": _HARD_BOUNDARIES,
            },
        }

    def ask_advisor(self, body: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            question = str(body.get("question") or "").strip()
            if not question:
                raise ValueError("Question is required.")
            day = max(1, min(int(body.get("day", 23)), self.days))
            canonical_role = _normalize_role(str(body.get("role") or Role.ASTRONAUT.value))
            crew_id = _normalize_crew_id(body.get("crew_id") or body.get("astronaut_id"), default="ast-01")

            if canonical_role == Role.SYSTEMS_ENGINEER.value:
                q_low = question.lower()
                personal_terms = ("elena", "marcus", "jordan", "hana", "ast-0", "diagnos", "fitness", "heart rate", "mood")
                if any(t in q_low for t in personal_terms):
                    return {
                        "question": question,
                        "answer": (
                            "Access scoped: Systems Engineer can inspect anonymized Crew A..D habitat correlations "
                            "and CO2/radiation telemetry, but cannot view personal astronaut vitals or health assessments."
                        ),
                        "evidence": ["Privacy boundary: Systems Engineer role scoped to habitat telemetry"],
                        "evidence_window": f"Day 1-{day}",
                        "evidence_windows": [f"Day 1-{day}"],
                        "citations": [],
                        "cited_observations": [],
                        "protocol_refs": ["PROT-ENV-01"],
                        "protocols": get_protocols(["PROT-ENV-01"]),
                        "confidence": 0.9,
                        "confidence_pct": 90,
                        "refused": True,
                        "refused_diagnosis": True,
                        "idk": False,
                        "said_i_dont_know": False,
                        "safety_active": False,
                        "safety_notice": None,
                        "safety_non_downgrade_notice": None,
                        "offline_mode": True,
                    }

            analytics = self._get_day_analytics(day)
            safety_rules, _ = self._evaluate_live_safety(analytics, day)
            aid_rules = self._safety_for_astronaut(safety_rules, crew_id)
            r_live = self._apply_live_safety_to_readiness(analytics["readiness_by_crew"][crew_id], aid_rules)
            b_live = analytics["behavioral_by_crew"][crew_id]
            env_raw = analytics["env_data"]
            mside_raw = analytics["mside_data"]

            lab_co2 = _get_zone_co2(env_raw, "LAB", 1113.0)
            cf_preview = simulate_intervention(
                r_live,
                sleep_per_night=8.0,
                workload_adjustment=-1.0,
                cabin_ventilation_pct=130.0,
                recovery_blocks=2,
                horizon_days=3,
                baseline_co2_ppm=lab_co2,
            )

            raw = answer_question(
                question=question,
                readiness_data=r_live,
                behavioral_data=b_live,
                env_data=env_raw,
                mside_data=mside_raw,
                active_safety_rules=[r for r in aid_rules if r.get("active")],
                counterfactual_data=cf_preview,
                astronaut_id=crew_id,
                up_to_day=day,
            )
            conf = float(raw.get("confidence", 0.75))
            conf_pct = int(round(conf * 100)) if conf <= 1.0 else int(round(conf))
            windows = list(raw.get("evidence_windows", []))
            cited = list(raw.get("cited_observations", []))
            safety_notice = raw.get("safety_notice")

            self.store.append_advisor_log(
                astronaut_id=crew_id,
                mode="ask",
                prompt=question,
                response=raw.get("answer", ""),
                citations=cited,
                meta={
                    "role": canonical_role,
                    "day": day,
                    "refused": bool(raw.get("refused_diagnosis")),
                    "idk": bool(raw.get("said_i_dont_know")),
                },
            )

            return {
                **raw,
                "astronaut_id": crew_id,
                "day": day,
                "role": canonical_role,
                "evidence": cited or windows,
                "evidence_window": ", ".join(windows) if windows else f"Day 1-{day}",
                "citations": cited,
                "confidence_pct": conf_pct,
                "refused": bool(raw.get("refused_diagnosis", False)),
                "idk": bool(raw.get("said_i_dont_know", False)),
                "safety_non_downgrade_notice": safety_notice,
            }

    def run_what_if(self, body: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            day = max(1, min(int(body.get("day", 23)), self.days))
            crew_id = _normalize_crew_id(body.get("astronaut_id") or body.get("crew_id"), default="ast-01")
            analytics = self._get_day_analytics(day)
            safety_rules, _ = self._evaluate_live_safety(analytics, day)
            aid_rules = self._safety_for_astronaut(safety_rules, crew_id)
            r_live = self._apply_live_safety_to_readiness(analytics["readiness_by_crew"][crew_id], aid_rules)
            env_raw = analytics["env_data"]
            lab_co2 = _get_zone_co2(env_raw, "LAB", 1113.0)

            sleep_h = float(body.get("sleep_per_night", body.get("sleep_hours", 7.5)))
            workload_adj = float(body.get("workload_adjustment", body.get("workload_delta", -1.0)))
            vent_pct = float(body.get("cabin_ventilation_pct", body.get("ventilation_pct", 130.0)))
            rec_blocks = int(body.get("recovery_blocks", 2))
            horizon = int(body.get("horizon_days", 7))

            sim = simulate_intervention(
                r_live,
                sleep_per_night=sleep_h,
                workload_adjustment=workload_adj,
                cabin_ventilation_pct=vent_pct,
                recovery_blocks=rec_blocks,
                horizon_days=horizon,
                baseline_co2_ppm=lab_co2,
            )

            base_readiness = round(float(r_live.get("readiness_score", 70.0)), 1)
            rec_series = sim.get("recovery_series") or []
            cog_series = sim.get("cognitive_series") or []
            projected_trajectory: List[Dict[str, Any]] = []
            for rec_pt, cog_pt in zip(rec_series, cog_series):
                debt_gain = (float(rec_pt["baseline"]) - float(rec_pt["intervention"])) * 0.55
                cog_gain = (float(cog_pt["intervention"]) - float(cog_pt["baseline"])) * 0.45
                proj_val = round(max(0.0, min(100.0, base_readiness + debt_gain + cog_gain)), 1)
                unc = round(float(rec_pt.get("uncertainty", 4.0)) * 0.6, 1)
                projected_trajectory.append(
                    {
                        "day": rec_pt["day"],
                        "baseline": base_readiness,
                        "projected": proj_val,
                        "low": round(max(0.0, proj_val - unc), 1),
                        "high": round(min(100.0, proj_val + unc), 1),
                    }
                )
            proj_terminal = (
                projected_trajectory[-1]["projected"]
                if projected_trajectory
                else base_readiness
            )

            self.store.append_advisor_log(
                astronaut_id=crew_id,
                mode="what_if",
                prompt=json.dumps(
                    {
                        "sleep_per_night": sleep_h,
                        "workload_adjustment": workload_adj,
                        "cabin_ventilation_pct": vent_pct,
                        "recovery_blocks": rec_blocks,
                        "horizon_days": horizon,
                    }
                ),
                response=sim.get("summary", ""),
                citations=[f"Day {day} personal baseline"],
                meta={"day": day},
            )
            return {
                **sim,
                "astronaut_id": crew_id,
                "day": day,
                "baseline_readiness": base_readiness,
                "projected_readiness": proj_terminal,
                "delta": round(proj_terminal - base_readiness, 1),
                "projected_trajectory": projected_trajectory,
            }

    def submit_checkin(self, body: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            crew_id = _normalize_crew_id(body.get("astronaut_id") or body.get("crew_id"), default="ast-01")
            day = max(1, int(body.get("day", 23)))
            hour = int(body.get("hour", 16))
            note = str(body.get("note") or body.get("safety_response") or "")
            safety_flag = bool(
                body.get("safety_flag")
                or body.get("safety_concern")
                or body.get("crisis_flag")
                or body.get("self_harm_risk")
                or body.get("immediate_support_needed")
            )
            ts = _mission_iso(day, hour)

            payload = {
                "astronaut_id": crew_id,
                "day": day,
                "hour": hour,
                "timestamp_utc": ts,
                "mood": float(body.get("mood", 3.5)),
                "energy": float(body.get("energy", 3.5)),
                "stress": float(body.get("stress", 2.5)),
                "headache": float(body.get("headache", 0.0)),
                "fatigue": float(body.get("fatigue", 1.0)),
                "note": note,
                "safety_response": note,
                "safety_concern": safety_flag,
                "safety_flag": safety_flag,
            }
            saved = self.store.insert_checkin(payload)

            zone_id = self.zone_occupancy.get(crew_id, {}).get(day, CREW_BY_ID[crew_id].default_zone)
            signal_values = [
                (SignalType.MOOD_SCORE, payload["mood"]),
                (SignalType.ENERGY_SCORE, payload["energy"]),
                (SignalType.STRESS_SCORE, payload["stress"]),
                (SignalType.SYMPTOM_HEADACHE, payload["headache"]),
                (SignalType.SYMPTOM_FATIGUE, payload["fatigue"]),
            ]
            recs = [
                MeasurementRecord(
                    record_id=f"rec-chk-{saved['checkin_id']}-{sig.value}",
                    astronaut_id=crew_id,
                    timestamp_utc=ts,
                    mission_elapsed_time=float((day - 1) * 24 + hour),
                    day=day,
                    hour=hour,
                    signal_type=sig.value,
                    value=float(val),
                    unit=SIGNAL_UNITS[sig.value],
                    source_device="Crew Check-In",
                    firmware_version="astra-ui-1.0",
                    quality=QualityState.OK.value,
                    confidence=1.0,
                    context_tags=["self_report"],
                    consent_scope=SIGNAL_TO_SCOPE[sig.value],
                    zone_id=zone_id,
                )
                for sig, val in signal_values
            ]
            self.store.append_measurements(recs)
            self._analytics_version += 1

            analytics = self._get_day_analytics(day)
            safety_rules, _ = self._evaluate_live_safety(analytics, day)
            aid_rules = self._safety_for_astronaut(safety_rules, crew_id)
            active_rules = [r for r in aid_rules if r.get("active")]
            return {
                "ok": True,
                "checkin": saved,
                "safety_rules": aid_rules,
                "active_safety_rules": active_rules,
                "safety_active": len(active_rules) > 0,
            }

    def submit_pvt(self, body: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            crew_id = _normalize_crew_id(body.get("astronaut_id") or body.get("crew_id"), default="ast-01")
            day = max(1, int(body.get("day", 23)))
            hour = int(body.get("hour", 16))
            mean_rt = float(body.get("mean_rt_ms", body.get("pvt_mean_rt", 260.0)))
            lapses = int(body.get("lapses", body.get("pvt_lapses", 0)))
            trials = int(body.get("trials", 40))
            ts = _mission_iso(day, hour)

            saved = self.store.insert_pvt(
                astronaut_id=crew_id,
                day=day,
                hour=hour,
                timestamp_utc=ts,
                mean_rt_ms=mean_rt,
                lapses=lapses,
                trials=trials,
            )
            zone_id = self.zone_occupancy.get(crew_id, {}).get(day, CREW_BY_ID[crew_id].default_zone)
            recs = [
                MeasurementRecord(
                    record_id=f"rec-pvt-{saved['pvt_id']}-rt",
                    astronaut_id=crew_id,
                    timestamp_utc=ts,
                    mission_elapsed_time=float((day - 1) * 24 + hour),
                    day=day,
                    hour=hour,
                    signal_type=SignalType.PVT_MEAN_RT.value,
                    value=mean_rt,
                    unit=SIGNAL_UNITS[SignalType.PVT_MEAN_RT.value],
                    source_device="Onboard PVT",
                    firmware_version="astra-pvt-1.0",
                    quality=QualityState.OK.value,
                    confidence=1.0,
                    context_tags=["cognitive_test"],
                    consent_scope=ConsentScope.COGNITIVE.value,
                    zone_id=zone_id,
                ),
                MeasurementRecord(
                    record_id=f"rec-pvt-{saved['pvt_id']}-lapses",
                    astronaut_id=crew_id,
                    timestamp_utc=ts,
                    mission_elapsed_time=float((day - 1) * 24 + hour),
                    day=day,
                    hour=hour,
                    signal_type=SignalType.PVT_LAPSES.value,
                    value=float(lapses),
                    unit=SIGNAL_UNITS[SignalType.PVT_LAPSES.value],
                    source_device="Onboard PVT",
                    firmware_version="astra-pvt-1.0",
                    quality=QualityState.OK.value,
                    confidence=1.0,
                    context_tags=["cognitive_test"],
                    consent_scope=ConsentScope.COGNITIVE.value,
                    zone_id=zone_id,
                ),
            ]
            self.store.append_measurements(recs)
            self._analytics_version += 1

            analytics = self._get_day_analytics(day)
            safety_rules, _ = self._evaluate_live_safety(analytics, day)
            aid_rules = self._safety_for_astronaut(safety_rules, crew_id)
            active_rules = [r for r in aid_rules if r.get("active")]
            return {
                "ok": True,
                "pvt": saved,
                "elevated_lapses": lapses >= 5,
                "safety_rules": aid_rules,
                "active_safety_rules": active_rules,
                "safety_active": len(active_rules) > 0,
            }

    def trigger_sos(self, body: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            crew_id = _normalize_crew_id(body.get("astronaut_id") or body.get("crew_id"), default="ast-01")
            sos_type = _normalize_sos_type(body.get("sos_type") or body.get("type") or "Medical")
            note = str(body.get("note") or "")
            day = max(1, int(body.get("day", 23)))
            hour = int(body.get("hour", 16))
            records = self.store.get_measurements(max_day=day)
            vitals, env_snap = self._snapshot_for_sos(records, crew_id, day)
            if isinstance(body.get("vitals_snapshot"), dict):
                vitals.update(body["vitals_snapshot"])
            if isinstance(body.get("env_snapshot"), dict):
                env_snap.update(body["env_snapshot"])

            pkt = self.sos.trigger_sos(
                astronaut_id=crew_id,
                sos_type=sos_type,
                note=note,
                day=day,
                hour=hour,
                vitals_snapshot=vitals,
                env_snapshot=env_snap,
            )
            formatted = _format_sos_event(pkt)
            analytics = self._get_day_analytics(day)
            safety_rules, _ = self._evaluate_live_safety(analytics, day)
            return {
                "ok": True,
                "sos": formatted,
                **formatted,
                "safety_rules": self._safety_for_astronaut(safety_rules, crew_id),
            }

    def cancel_sos(self, body: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            sos_id = str(body.get("sos_id") or "").strip()
            if not sos_id:
                raise ValueError("sos_id is required.")
            reason = str(body.get("reason") or "false_alarm")
            pkt = self.sos.cancel_sos(sos_id, reason=reason)
            formatted = _format_sos_event(pkt)
            return {"ok": True, "sos": formatted, **formatted}

    def acknowledge_sos(self, body: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            sos_id = str(body.get("sos_id") or "").strip()
            if not sos_id:
                raise ValueError("sos_id is required.")
            actor = str(body.get("actor") or body.get("actor_role") or "Crew Health Officer")
            pkt = self.sos.acknowledge_sos(sos_id, actor=actor)
            formatted = _format_sos_event(pkt)
            return {"ok": True, "sos": formatted, **formatted}

    def resolve_sos(self, body: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            sos_id = str(body.get("sos_id") or "").strip()
            if not sos_id:
                raise ValueError("sos_id is required.")
            existing = next((s for s in self.store.get_sos_events() if s.get("sos_id") == sos_id), None)
            if existing is None:
                raise KeyError(f"Unknown sos_id: {sos_id}")
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            note = str(body.get("note") or body.get("reason") or "Crew confirmed OK; safety event resolved.")
            actor = str(body.get("actor") or body.get("actor_role") or "Crew Health Officer")
            updated = self.store.update_sos(
                sos_id,
                {
                    "status": "resolved_ok",
                    "state": "resolved_ok",
                    "override_active": False,
                    "override_expires_at": None,
                    "resolved_note": note,
                    "resolved_by": actor,
                    "resolved_at": now,
                    "updated_at": now,
                },
            )
            formatted = _format_sos_event(updated or existing)
            return {"ok": True, "sos": formatted, **formatted}

    def send_message(self, body: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            sender_raw = str(body.get("sender_id") or body.get("from_id") or "ast-01").strip()
            recipient_raw = body.get("recipient") or body.get("to_id")
            recipient = _normalize_recipient(recipient_raw)
            msg_body = str(body.get("body") or "")
            msg_type = str(body.get("msg_type") or body.get("kind") or "text")
            raw_prio = str(body.get("priority") or "routine").strip().lower()
            priority = "urgent" if raw_prio == "priority" else raw_prio
            attach_chart = bool(body.get("attach_health_chart") or body.get("attach_chart"))
            audio_sec = int(body.get("audio_duration_sec") or body.get("audio_duration_s") or 0)
            day = max(1, int(body.get("day", 23)))
            hour = int(body.get("hour", 16))

            msg = self.messaging.send_message(
                sender_id=sender_raw,
                recipient=recipient,
                body=msg_body,
                msg_type=msg_type,
                priority=priority,
                attach_health_chart=attach_chart,
                audio_duration_sec=audio_sec,
                day=day,
                hour=hour,
            )
            formatted = _format_message(msg)
            return {"ok": True, "message": formatted, **formatted}

    def mark_message_read(self, body: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            msg_id = str(body.get("msg_id") or body.get("message_id") or "").strip()
            if not msg_id:
                raise ValueError("msg_id is required.")
            updated = self.messaging.mark_read(msg_id)
            formatted = _format_message(updated)
            return {"ok": True, "message": formatted, **formatted}

    def update_consent(self, body: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            crew_id = _normalize_crew_id(body.get("astronaut_id") or body.get("crew_id"), default="ast-01")
            normal_updates = dict(body.get("normal_updates") or {})
            emergency_updates = dict(body.get("emergency_updates") or {})

            scope = body.get("scope")
            if scope is not None:
                norm_scope = _normalize_scope(str(scope))
                mode = str(body.get("mode") or "normal").strip().lower()
                enabled = bool(body.get("enabled", True))
                if mode == "emergency":
                    emergency_updates[norm_scope] = enabled
                else:
                    normal_updates[norm_scope] = enabled

            updated = self.consent.update_profile(
                crew_id,
                normal_updates=normal_updates or None,
                emergency_updates=emergency_updates or None,
            )
            self.store.append_access_log(
                viewer_role=Role.ASTRONAUT.value,
                target_astronaut_id=crew_id,
                scope=str(scope or "consent_profile"),
                allowed=True,
                override_used=False,
                active_critical_rule=False,
                reason="astronaut updated consent setting",
                access_mode="self",
                policy_note="Astronaut modified own data-sharing consent configuration.",
            )
            return {
                "ok": True,
                "astronaut_id": crew_id,
                "profile": updated,
                "consent_matrix": self.consent.get_consent_matrix(),
            }

    def set_sync_link(self, body: Dict[str, Any]) -> Dict[str, Any]:
        with self._lock:
            if "online" in body and body["online"] is not None:
                online = bool(body["online"])
            else:
                online = not bool(self.sync_manager.online)
            status = self.sync_manager.set_link_status(online)
            return {
                "ok": True,
                **status,
                "earth_link": self._earth_link_status(),
                "sync_queue": self.sync_manager.list_queue(include_acknowledged=True),
            }

    def fast_forward_sync(self, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        with self._lock:
            payload = body or {}
            if payload.get("online") is True or payload.get("connect") is True:
                self.sync_manager.set_link_status(True)
            result = self.sync_manager.fast_forward_sync()
            return {
                "ok": True,
                **result,
                "earth_link": self._earth_link_status(),
                "sync_queue": self.sync_manager.list_queue(include_acknowledged=True),
            }


_DEFAULT_BACKEND: Optional[AstraBackend] = None
_DEFAULT_BACKEND_LOCK = threading.Lock()


def get_default_backend() -> AstraBackend:
    """Return the lazily initialized singleton backend instance."""
    global _DEFAULT_BACKEND
    if _DEFAULT_BACKEND is None:
        with _DEFAULT_BACKEND_LOCK:
            if _DEFAULT_BACKEND is None:
                _DEFAULT_BACKEND = AstraBackend(seed=42, days=30, db_path=":memory:")
    return _DEFAULT_BACKEND


def _extract_param(query_params: Optional[Dict[str, Any]], *names: str, default: Any = None) -> Any:
    if not query_params:
        return default
    for name in names:
        if name in query_params:
            val = query_params[name]
            if isinstance(val, (list, tuple)):
                return val[0] if val else default
            return val
    return default


def handle_request(
    method: str,
    path: str,
    query_params: Optional[Dict[str, Any]] = None,
    body: Optional[Dict[str, Any]] = None,
    backend: Optional[AstraBackend] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Route a REST request in-process and return `(status_code, json_payload)`."""
    verb = str(method or "GET").upper()
    parsed = urlparse(path or "/")
    clean_path = parsed.path.rstrip("/") or "/"
    merged_query: Dict[str, Any] = dict(parse_qs(parsed.query))
    if query_params:
        merged_query.update(query_params)

    if verb == "OPTIONS":
        return 200, {"ok": True}

    engine = backend or get_default_backend()
    payload = body if isinstance(body, dict) else {}

    try:
        if verb == "GET" and clean_path == "/api/health":
            return 200, {
                "status": "ok",
                "service": "astroguard-backend",
                "version": "0.2.0",
                "online": bool(engine.sync_manager.online),
                "mission_days": engine.days,
            }

        if verb == "GET" and clean_path == "/api/state":
            day_raw = _extract_param(merged_query, "day", default=23)
            role_raw = _extract_param(merged_query, "role", default=Role.ASTRONAUT.value)
            crew_raw = _extract_param(merged_query, "crew_id", "astronaut_id", default="ast-01")
            return 200, engine.get_state(
                day=int(day_raw),
                role=str(role_raw),
                crew_id=str(crew_raw),
            )

        if verb == "POST" and clean_path == "/api/advisor/ask":
            return 200, engine.ask_advisor(payload)

        if verb == "POST" and clean_path == "/api/advisor/what-if":
            return 200, engine.run_what_if(payload)

        if verb == "POST" and clean_path == "/api/checkin":
            return 200, engine.submit_checkin(payload)

        if verb == "POST" and clean_path == "/api/pvt":
            return 200, engine.submit_pvt(payload)

        if verb == "POST" and clean_path == "/api/sos/trigger":
            return 200, engine.trigger_sos(payload)

        if verb == "POST" and clean_path == "/api/sos/cancel":
            return 200, engine.cancel_sos(payload)

        if verb == "POST" and clean_path == "/api/sos/acknowledge":
            return 200, engine.acknowledge_sos(payload)

        if verb == "POST" and clean_path == "/api/sos/resolve":
            return 200, engine.resolve_sos(payload)

        if verb == "POST" and clean_path == "/api/messages/send":
            return 200, engine.send_message(payload)

        if verb == "POST" and clean_path == "/api/messages/read":
            return 200, engine.mark_message_read(payload)

        if verb == "POST" and clean_path == "/api/consent/update":
            return 200, engine.update_consent(payload)

        if verb == "POST" and clean_path in ("/api/sync/link", "/api/sync/toggle-link"):
            return 200, engine.set_sync_link(payload)

        if verb == "POST" and clean_path == "/api/sync/fast-forward":
            return 200, engine.fast_forward_sync(payload)

        return 404, {"error": f"Unknown endpoint: {verb} {clean_path}"}

    except PermissionError as exc:
        return 403, {"error": str(exc)}
    except KeyError as exc:
        return 404, {"error": str(exc)}
    except ValueError as exc:
        msg = str(exc)
        if "Unknown sos_id" in msg or "Unknown msg_id" in msg:
            return 404, {"error": msg}
        return 400, {"error": msg}


def make_http_handler(backend: Optional[AstraBackend] = None) -> type[BaseHTTPRequestHandler]:
    """Build a stdlib `BaseHTTPRequestHandler` bound to `backend`."""
    bound_backend = backend

    class AstraHTTPRequestHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send_json(self, status_code: int, data: Dict[str, Any]) -> None:
            encoded = json.dumps(data, default=str).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            for k, v in CORS_HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(encoded)

        def _read_json_body(self) -> Dict[str, Any]:
            length_hdr = self.headers.get("Content-Length")
            if not length_hdr:
                return {}
            length = int(length_hdr)
            if length <= 0:
                return {}
            raw = self.rfile.read(length)
            if not raw:
                return {}
            parsed = json.loads(raw.decode("utf-8"))
            if not isinstance(parsed, dict):
                raise ValueError("JSON request body must be an object.")
            return parsed

        def do_OPTIONS(self) -> None:
            try:
                status_code, data = handle_request("OPTIONS", self.path, backend=bound_backend)
                self._send_json(status_code, data)
            except Exception as exc:  # pragma: no cover
                self._send_json(500, {"error": f"Internal server error: {exc}"})

        def do_GET(self) -> None:
            try:
                status_code, data = handle_request("GET", self.path, backend=bound_backend)
                self._send_json(status_code, data)
            except Exception as exc:  # pragma: no cover
                self._send_json(500, {"error": f"Internal server error: {exc}"})

        def do_POST(self) -> None:
            try:
                body = self._read_json_body()
            except (json.JSONDecodeError, ValueError) as exc:
                self._send_json(400, {"error": f"Invalid JSON payload: {exc}"})
                return
            try:
                status_code, data = handle_request("POST", self.path, body=body, backend=bound_backend)
                self._send_json(status_code, data)
            except Exception as exc:  # pragma: no cover
                self._send_json(500, {"error": f"Internal server error: {exc}"})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    return AstraHTTPRequestHandler


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    backend: Optional[AstraBackend] = None,
) -> ThreadingHTTPServer:
    """Create a configured `ThreadingHTTPServer` serving AstroGuard REST endpoints."""
    active_backend = backend or get_default_backend()
    handler_cls = make_http_handler(active_backend)
    return ThreadingHTTPServer((host, port), handler_cls)


# Optional FastAPI ASGI wrapper when FastAPI is available in the environment.
try:
    from fastapi import FastAPI, Request
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse

    fastapi_app = FastAPI(title="AstroGuard Offline-First Crew Health Backend", version="0.2.0")
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    @fastapi_app.api_route("/api/{rest_of_path:path}", methods=["GET", "POST", "OPTIONS"])
    async def _fastapi_proxy(rest_of_path: str, request: Request) -> JSONResponse:
        body: Dict[str, Any] = {}
        if request.method == "POST":
            raw_bytes = await request.body()
            if raw_bytes:
                body = json.loads(raw_bytes.decode("utf-8"))
        status_code, payload = handle_request(
            request.method,
            f"/api/{rest_of_path}",
            query_params=dict(request.query_params),
            body=body,
        )
        return JSONResponse(status_code=status_code, content=payload)

except ImportError:  # pragma: no cover - pure stdlib environment
    fastapi_app = None  # type: ignore[assignment]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the AstroGuard offline-first backend server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    backend = get_default_backend()
    server = create_server(host=args.host, port=args.port, backend=backend)
    print(f"AstroGuard backend listening on http://{args.host}:{args.port} (offline-first mission ready)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        backend.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
