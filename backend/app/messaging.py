"""Delay-Tolerant Crew & Earth Messaging Service for AstroGuard (F-32).

Privacy & architecture guarantees:
- Message body text is strictly OPAQUE (`CONTENT_ANALYSIS_ENABLED = False`).
  AstroGuard NEVER analyzes message content for mood, distress, or behavioral scoring.
- Attaching a health chart to `Home (Earth)` verifies astronaut consent
  (`ground_sharing` scope) via `ConsentManager` and logs the access check.
- Audio clips or health chart attachments over the narrow `2.4 kbps` Earth link
  carry explicit bandwidth and light-time delay warnings.
- Earth-bound traffic enters the store-and-forward sync queue at Priority 2 (`"message"`).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

CONTENT_ANALYSIS_ENABLED = False
EARTH_LINK_BANDWIDTH_KBPS = 2.4
EARTH_LIGHT_TIME_MIN = 12.8

VALID_MSG_TYPES = frozenset({"text", "audio"})
VALID_PRIORITIES = frozenset({"routine", "urgent"})
VALID_FILTER_SCOPES = frozenset({"all", "earth", "crew"})

_EARTH_RECIPIENTS = frozenset({"home (earth)", "home", "earth", "ground", "ground support"})
_BROADCAST_RECIPIENTS = frozenset({"all crew", "all_crew", "all"})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_earth_recipient(recipient: str) -> bool:
    norm = recipient.strip().lower()
    return norm in _EARTH_RECIPIENTS or "earth" in norm or norm.startswith("home")


def _normalize_message(raw: Dict[str, Any]) -> Dict[str, Any]:
    msg = dict(raw)
    msg_id = str(msg.get("message_id") or msg.get("msg_id") or "")
    msg["message_id"] = msg_id
    msg["msg_id"] = msg_id
    recipient = str(msg.get("recipient") or msg.get("recipient_id") or "")
    msg["recipient_id"] = recipient
    msg["recipient"] = recipient
    kind = str(msg.get("kind") or msg.get("msg_type") or "text")
    msg["kind"] = kind
    msg["msg_type"] = kind
    urgency = str(msg.get("urgency") or msg.get("priority") or "routine")
    msg["urgency"] = urgency
    msg["priority"] = urgency
    msg.setdefault("bandwidth_warning", False)
    msg.setdefault("bandwidth_warning_text", "")
    msg.setdefault("attach_health_chart", False)
    msg.setdefault("audio_duration_sec", 0)
    return msg


class MessagingService:
    """Delay-tolerant text and audio messaging service with opaque content."""

    def __init__(self, store: Any, consent_manager: Any, sync_manager: Any) -> None:
        self.store = store
        self.consent_manager = consent_manager
        self.sync_manager = sync_manager

    def _verify_chart_consent(self, sender_id: str, is_earth: bool, recipient: str) -> None:
        if self.consent_manager is None:
            raise PermissionError("Consent manager unavailable; cannot attach health chart.")

        if is_earth:
            if hasattr(self.consent_manager, "check_access"):
                try:
                    decision = self.consent_manager.check_access(
                        viewer_role="Ground Support",
                        target_astronaut_id=sender_id,
                        scope="ground_sharing",
                        active_critical_rule=False,
                        reason="Attach consented health chart to Earth message",
                    )
                except ValueError as exc:
                    raise PermissionError(
                        f"Consent denied for sender '{sender_id}': no ground_sharing profile."
                    ) from exc
                if not decision.get("allowed", False):
                    raise PermissionError(
                        f"Consent denied: astronaut '{sender_id}' has disabled ground_sharing for Earth charts."
                    )
                return
            if hasattr(self.consent_manager, "can_share_with_ground"):
                if not self.consent_manager.can_share_with_ground(sender_id):
                    raise PermissionError(
                        f"Consent denied: astronaut '{sender_id}' has disabled ground_sharing."
                    )
                return
            raise PermissionError("Consent manager does not support ground_sharing verification.")

        # On-board chart sharing with Crew Health Officer checks physio scope when available
        norm_rec = recipient.strip().lower()
        if ("health officer" in norm_rec or norm_rec == "ho") and hasattr(
            self.consent_manager, "check_access"
        ):
            try:
                decision = self.consent_manager.check_access(
                    viewer_role="Crew Health Officer",
                    target_astronaut_id=sender_id,
                    scope="physio",
                    active_critical_rule=False,
                    reason="Attach consented health chart to Crew Health Officer message",
                )
            except ValueError:
                return
            if not decision.get("allowed", False):
                raise PermissionError(
                    f"Consent denied: astronaut '{sender_id}' has disabled physio sharing."
                )

    def _compute_bandwidth_metadata(
        self,
        is_earth: bool,
        msg_type: str,
        body: str,
        attach_health_chart: bool,
        audio_duration_sec: int,
    ) -> Dict[str, Any]:
        # Transport sizing uses byte length only; message text is never inspected.
        text_bytes = len(body.encode("utf-8"))
        chart_bytes = 4500 if attach_health_chart else 0
        audio_bytes = max(0, int(audio_duration_sec)) * 1000 if (msg_type == "audio" or audio_duration_sec > 0) else 0
        total_bytes = max(64, text_bytes + chart_bytes + audio_bytes)
        bytes_per_sec = (EARTH_LINK_BANDWIDTH_KBPS * 1000.0) / 8.0  # 300 B/s
        estimated_transit_sec = round(total_bytes / bytes_per_sec, 1)

        has_heavy_payload = (msg_type == "audio") or (audio_duration_sec > 0) or attach_health_chart
        warning = bool(is_earth and has_heavy_payload)

        warning_text = ""
        if warning:
            parts: List[str] = []
            if msg_type == "audio" or audio_duration_sec > 0:
                parts.append(f"audio clip ({int(audio_duration_sec)}s)")
            if attach_health_chart:
                parts.append("consented 7-day health chart")
            payload_desc = " + ".join(parts)
            warning_text = (
                f"Bandwidth warning: {payload_desc} adds ~{estimated_transit_sec:.1f}s transit time "
                f"over the narrow {EARTH_LINK_BANDWIDTH_KBPS:.1f} kbps Earth link "
                f"(plus ~{EARTH_LIGHT_TIME_MIN:.1f} min one-way light delay)."
            )

        return {
            "bandwidth_warning": warning,
            "bandwidth_warning_text": warning_text,
            "bandwidth_kbps": EARTH_LINK_BANDWIDTH_KBPS if is_earth else None,
            "estimated_transit_sec": estimated_transit_sec if is_earth else 0.0,
            "expected_light_time_min": EARTH_LIGHT_TIME_MIN if is_earth else 0.0,
            "payload_bytes": total_bytes,
        }

    def _enqueue_earth_message(self, msg: Dict[str, Any]) -> None:
        if self.sync_manager is None or not hasattr(self.sync_manager, "enqueue"):
            return
        message_id = msg["message_id"]
        meta = {
            "message_id": message_id,
            "priority": 2,
            "urgency": msg["urgency"],
            "channel": msg["channel"],
            "bandwidth_warning": msg["bandwidth_warning"],
        }
        try:
            self.sync_manager.enqueue(
                category="message",
                payload=dict(msg),
                item_id=message_id,
                meta=meta,
            )
        except TypeError:
            self.sync_manager.enqueue("message", dict(msg))

    def send_message(
        self,
        sender_id: str,
        recipient: str,
        body: str,
        msg_type: str = "text",
        priority: str = "routine",
        attach_health_chart: bool = False,
        audio_duration_sec: int = 0,
        day: int = 23,
        hour: int = 16,
    ) -> Dict[str, Any]:
        """Store an opaque crew or Earth message and enqueue Earth traffic at Priority 2."""
        if msg_type not in VALID_MSG_TYPES:
            raise ValueError(f"Invalid msg_type '{msg_type}'. Must be one of: text, audio")
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority '{priority}'. Must be one of: routine, urgent")
        if int(audio_duration_sec) < 0:
            raise ValueError("audio_duration_sec must be non-negative")

        is_earth = _is_earth_recipient(recipient)
        if attach_health_chart:
            self._verify_chart_consent(sender_id=str(sender_id), is_earth=is_earth, recipient=recipient)

        bw = self._compute_bandwidth_metadata(
            is_earth=is_earth,
            msg_type=msg_type,
            body=str(body),
            attach_health_chart=bool(attach_health_chart),
            audio_duration_sec=int(audio_duration_sec),
        )

        link_online = bool(getattr(self.sync_manager, "online", False)) if self.sync_manager is not None else False
        status = "delivered" if (not is_earth or link_online) else "queued"
        channel = "earth" if is_earth else "crew"
        scope = "Earth" if is_earth else "Crew"
        now = _utc_now_iso()
        message_id = f"msg-{uuid.uuid4().hex[:10]}"

        record: Dict[str, Any] = {
            "message_id": message_id,
            "msg_id": message_id,
            "sender_id": str(sender_id),
            "recipient_id": str(recipient),
            "recipient": str(recipient),
            "channel": channel,
            "scope": scope,
            "urgency": priority,
            "priority": priority,
            "kind": msg_type,
            "msg_type": msg_type,
            "body": str(body),
            "attach_health_chart": bool(attach_health_chart),
            "chart_summary": (
                "Recovery trend — 7 days · consented health chart" if attach_health_chart else None
            ),
            "audio_duration_sec": int(audio_duration_sec),
            "day": int(day),
            "hour": int(hour),
            "status": status,
            "created_at": now,
            "updated_at": now,
            "content_analyzed": False,
            **bw,
        }

        saved = self.store.save_message(record)
        normalized = _normalize_message(saved)

        if is_earth:
            self._enqueue_earth_message(normalized)

        return normalized

    def mark_read(self, msg_id: str) -> Dict[str, Any]:
        """Mark a message as read."""
        updated = self.store.update_message_status(
            msg_id,
            status="read",
            extra={"read_at": _utc_now_iso()},
        )
        if updated is None:
            raise ValueError(f"Unknown message_id: {msg_id}")
        return _normalize_message(updated)

    def list_messages(
        self,
        filter_scope: str = "All",
        astronaut_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List messages filtered by scope (`All`, `Earth`, `Crew`) and optional astronaut_id."""
        norm_scope = (filter_scope or "All").strip().lower()
        if norm_scope not in VALID_FILTER_SCOPES:
            raise ValueError(f"Invalid filter_scope '{filter_scope}'. Expected one of: All, Earth, Crew")

        all_msgs = self.store.get_messages()
        filtered: List[Dict[str, Any]] = []
        for raw in all_msgs:
            msg = _normalize_message(raw)
            channel_lower = str(msg.get("channel", "")).lower()
            is_earth_msg = channel_lower in ("earth", "ground") or _is_earth_recipient(
                str(msg.get("recipient_id", ""))
            )

            if norm_scope == "earth" and not is_earth_msg:
                continue
            if norm_scope == "crew" and is_earth_msg:
                continue

            if astronaut_id is not None:
                sender = str(msg.get("sender_id", ""))
                recipient = str(msg.get("recipient_id", ""))
                if (
                    sender != astronaut_id
                    and recipient != astronaut_id
                    and recipient.strip().lower() not in _BROADCAST_RECIPIENTS
                ):
                    continue

            filtered.append(msg)
        return filtered
