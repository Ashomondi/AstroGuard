"""Standalone Emergency SOS Service for AstroGuard (F-31).

CRITICAL ARCHITECTURAL BOUNDARY:
- MUST NOT import anything from `app.engines`, `simulator`, or `advisor`.
- Operates completely offline and survives analytics, ML engine, or Advisor failures.
- Packets enter the store-and-forward queue at Priority 0 (`"sos"`).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

VALID_SOS_TYPES = frozenset({"Medical", "Behavioral support", "Habitat hazard"})

_SOS_TYPE_TO_SCOPE: Dict[str, str] = {
    "Medical": "physio",
    "Behavioral support": "behaviour",
    "Habitat hazard": "habitat",
}

CANCEL_WINDOW_SECONDS = 10
EMERGENCY_OVERRIDE_HOURS = 2


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _override_expiry_iso(hours: int = EMERGENCY_OVERRIDE_HOURS) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_sos_packet(raw: Dict[str, Any]) -> Dict[str, Any]:
    packet = dict(raw)
    canonical_state = str(packet.get("status") or packet.get("state") or "queued")
    packet["state"] = canonical_state
    packet["status"] = canonical_state
    packet.setdefault("acknowledged_on_board", False)
    packet.setdefault("cancel_window_sec", CANCEL_WINDOW_SECONDS)
    packet.setdefault("vitals_snapshot", {})
    packet.setdefault("env_snapshot", {})
    packet.setdefault("priority", 0)
    return packet


class SOSService:
    """Independent SOS workflow (trigger, 10s cancel, on-board ack, list)."""

    def __init__(self, store: Any, consent_manager: Any, sync_manager: Any) -> None:
        self.store = store
        self.consent_manager = consent_manager
        self.sync_manager = sync_manager

    def _log_emergency_override(self, astronaut_id: str, sos_id: str, sos_type: str) -> Optional[Dict[str, Any]]:
        scope = _SOS_TYPE_TO_SCOPE[sos_type]
        reason = f"Emergency SOS ({sos_type}) override [{sos_id}]"

        if self.consent_manager is not None:
            if hasattr(self.consent_manager, "log_emergency_override"):
                return self.consent_manager.log_emergency_override(
                    astronaut_id=astronaut_id,
                    sos_id=sos_id,
                    sos_type=sos_type,
                    scope=scope,
                    reason=reason,
                )
            if hasattr(self.consent_manager, "check_access"):
                try:
                    return self.consent_manager.check_access(
                        viewer_role="Crew Health Officer",
                        target_astronaut_id=astronaut_id,
                        scope=scope,
                        active_critical_rule=True,
                        reason=reason,
                    )
                except ValueError:
                    # Fallback if astronaut_id lacks a pre-registered consent profile
                    pass

        if self.store is not None and hasattr(self.store, "append_access_log"):
            return self.store.append_access_log(
                viewer_role="Crew Health Officer",
                target_astronaut_id=astronaut_id,
                scope=scope,
                allowed=True,
                override_used=True,
                active_critical_rule=True,
                reason=reason,
                access_mode="emergency_override",
                override_expires_at=_override_expiry_iso(),
            )
        return None

    def _enqueue_sos_packet(self, packet: Dict[str, Any]) -> None:
        if self.sync_manager is None or not hasattr(self.sync_manager, "enqueue"):
            return
        sos_id = packet["sos_id"]
        meta = {
            "sos_id": sos_id,
            "astronaut_id": packet["astronaut_id"],
            "sos_type": packet["sos_type"],
            "priority": 0,
        }
        try:
            self.sync_manager.enqueue(
                category="sos",
                payload=dict(packet),
                item_id=sos_id,
                meta=meta,
            )
        except TypeError:
            self.sync_manager.enqueue("sos", dict(packet))

    def trigger_sos(
        self,
        astronaut_id: str,
        sos_type: str = "Medical",
        note: str = "",
        day: int = 23,
        hour: int = 16,
        vitals_snapshot: Optional[Dict[str, Any]] = None,
        env_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Validate SOS type, build & persist SOS packet, log override, and enqueue at P0."""
        if sos_type not in VALID_SOS_TYPES:
            valid_list = ", ".join(sorted(VALID_SOS_TYPES))
            raise ValueError(f"Invalid sos_type '{sos_type}'. Must be one of: {valid_list}")

        now = _utc_now_iso()
        sos_id = f"sos-{uuid.uuid4().hex[:10]}"
        override_expires_at = _override_expiry_iso()

        packet: Dict[str, Any] = {
            "sos_id": sos_id,
            "astronaut_id": str(astronaut_id),
            "sos_type": sos_type,
            "note": str(note or ""),
            "day": int(day),
            "hour": int(hour),
            "timestamp_utc": now,
            "created_at": now,
            "updated_at": now,
            "vitals_snapshot": dict(vitals_snapshot or {}),
            "env_snapshot": dict(env_snapshot or {}),
            "state": "queued",
            "status": "queued",
            "priority": 0,
            "acknowledged_on_board": False,
            "acknowledged_by": None,
            "acknowledged_at": None,
            "cancel_window_sec": CANCEL_WINDOW_SECONDS,
            "cancelled": False,
            "cancel_reason": None,
            "override_active": True,
            "override_expires_at": override_expires_at,
        }

        saved = self.store.save_sos(packet)
        self._log_emergency_override(astronaut_id=str(astronaut_id), sos_id=sos_id, sos_type=sos_type)
        self._enqueue_sos_packet(saved)
        return _normalize_sos_packet(saved)

    def _find_sos(self, sos_id: str) -> Dict[str, Any]:
        events = self.store.get_sos_events()
        for item in events:
            if item.get("sos_id") == sos_id:
                return _normalize_sos_packet(item)
        raise ValueError(f"Unknown sos_id: {sos_id}")

    def cancel_sos(self, sos_id: str, reason: str = "false_alarm") -> Dict[str, Any]:
        """Cancel an active/queued SOS within or after the 10-second cancel window."""
        self._find_sos(sos_id)
        now = _utc_now_iso()
        updated = self.store.update_sos(
            sos_id,
            {
                "state": "cancelled",
                "status": "cancelled",
                "cancelled": True,
                "cancel_reason": str(reason or "false_alarm"),
                "cancelled_at": now,
                "override_active": False,
                "override_expires_at": None,
                "updated_at": now,
            },
        )
        if updated is None:
            raise ValueError(f"Unknown sos_id: {sos_id}")
        return _normalize_sos_packet(updated)

    def acknowledge_sos(self, sos_id: str, actor: str = "Crew Health Officer") -> Dict[str, Any]:
        """Record on-board acknowledgement separately from Earth delivery state."""
        existing = self._find_sos(sos_id)
        if existing.get("state") == "cancelled" or existing.get("cancelled"):
            raise ValueError(f"Cannot acknowledge cancelled SOS event: {sos_id}")

        now = _utc_now_iso()
        updated = self.store.update_sos(
            sos_id,
            {
                "acknowledged_on_board": True,
                "acknowledged_by": str(actor),
                "acknowledged_at": now,
                "updated_at": now,
            },
        )
        if updated is None:
            raise ValueError(f"Unknown sos_id: {sos_id}")
        return _normalize_sos_packet(updated)

    def list_sos(self, astronaut_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List SOS events (optionally filtered by astronaut_id) with normalized state."""
        events = self.store.get_sos_events(astronaut_id=astronaut_id)
        return [_normalize_sos_packet(item) for item in events]
