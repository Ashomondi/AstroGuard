"""Prioritized offline-first store-and-forward Earth sync queue for AstroGuard (F-04).

Priority order (strictly ascending numeric priority):
  0: sos
  1: critical_alert
  2: message
  3: summary
  4: telemetry

Queue items start as `queued` while offline (`online=False` by default) and step
through `queued -> transmitting -> delivered -> acknowledged` in strict priority order
when the Earth link is online.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.store import AstraStore

PRIORITY_ORDER: Dict[str, int] = {
    "sos": 0,
    "critical_alert": 1,
    "message": 2,
    "summary": 3,
    "telemetry": 4,
}

SYNC_STATES: Tuple[str, ...] = ("queued", "transmitting", "delivered", "acknowledged")

# Map link sync states onto message lifecycle statuses (FEATURES.md §8: queued/sent/delivered/read).
_SYNC_TO_MESSAGE_STATUS: Dict[str, str] = {
    "queued": "queued",
    "transmitting": "sent",
    "delivered": "delivered",
    "acknowledged": "delivered",
}


class SyncManager:
    """Offline-first store-and-forward queue manager backed by AstraStore."""

    def __init__(self, store: AstraStore, online: bool = False) -> None:
        self.store = store
        self.online: bool = bool(online)
        self._last_ts: Optional[datetime] = None
        self.sync_history: List[Dict[str, Any]] = []

    def _next_timestamp_iso(self) -> str:
        now = datetime.now(timezone.utc)
        if self._last_ts is not None and now <= self._last_ts:
            now = self._last_ts + timedelta(microseconds=1)
        self._last_ts = now
        return now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def enqueue(
        self,
        category: str,
        payload: Dict[str, Any],
        item_id: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if category not in PRIORITY_ORDER:
            valid = ", ".join(sorted(PRIORITY_ORDER))
            raise ValueError(f"Unknown sync category '{category}'. Expected one of: {valid}")

        priority = PRIORITY_ORDER[category]
        created_at = self._next_timestamp_iso()
        resolved_id = item_id or f"sync-{category}-{uuid.uuid4().hex[:8]}"
        return self.store.enqueue_sync(
            item_id=resolved_id,
            category=category,
            priority=priority,
            status="queued",
            created_at=created_at,
            updated_at=created_at,
            payload=dict(payload),
            meta=dict(meta or {}),
        )

    def list_queue(self, include_acknowledged: bool = True) -> List[Dict[str, Any]]:
        items = self.store.get_sync_queue()
        if not include_acknowledged:
            items = [item for item in items if item["status"] != "acknowledged"]
        items.sort(key=lambda item: (item["priority"], item["created_at"], item["item_id"]))
        return items

    def set_link_status(self, online: bool) -> Dict[str, Any]:
        self.online = bool(online)
        pending = [i for i in self.list_queue() if i["status"] != "acknowledged"]
        return {
            "online": self.online,
            "pending_count": len(pending),
            "next_priority_category": pending[0]["category"] if pending else None,
        }

    def _sync_linked_record(self, item: Dict[str, Any], target_status: str) -> None:
        category = item["category"]
        payload = item.get("payload") or {}
        meta = item.get("meta") or {}

        if category == "sos":
            sos_id = payload.get("sos_id") or meta.get("sos_id") or item["item_id"]
            existing = next(
                (s for s in self.store.get_sos_events() if s["sos_id"] == sos_id), None
            )
            if (
                existing is not None
                and not existing.get("cancelled")
                and existing.get("status") not in ("cancelled", "resolved_ok")
                and existing.get("state") not in ("cancelled", "resolved_ok")
            ):
                self.store.update_sos(sos_id, status=target_status, state=target_status)

        elif category == "message":
            message_id = payload.get("message_id") or meta.get("message_id") or item["item_id"]
            existing = next(
                (m for m in self.store.get_messages() if m["message_id"] == message_id), None
            )
            if existing is not None and existing["status"] != "read":
                msg_status = _SYNC_TO_MESSAGE_STATUS.get(target_status, target_status)
                self.store.update_message_status(
                    message_id,
                    status=msg_status,
                    extra={"sync_status": target_status},
                )

    def fast_forward_sync(self) -> Dict[str, Any]:
        """Step all pending queue items through queued->transmitting->delivered->acknowledged.

        Items remain queued if the link is currently offline (`online=False`).
        When online, items are processed strictly by `(priority, created_at)`.
        """
        if not self.online:
            pending = self.list_queue(include_acknowledged=False)
            return {
                "online": False,
                "processed_count": 0,
                "pending_count": len(pending),
                "items": [],
                "transitions": [],
                "reason": "Earth link offline; queued packets preserved for store-and-forward.",
            }

        pending = self.list_queue(include_acknowledged=False)
        transitions: List[Dict[str, Any]] = []
        processed_items: List[Dict[str, Any]] = []

        for item in pending:
            current_status = item["status"]
            if current_status not in SYNC_STATES:
                start_idx = 0
            else:
                start_idx = SYNC_STATES.index(current_status)

            updated_item = item
            for next_idx in range(start_idx + 1, len(SYNC_STATES)):
                prev_state = updated_item["status"]
                next_state = SYNC_STATES[next_idx]
                ts = self._next_timestamp_iso()
                updated_item = self.store.update_sync_item(
                    item["item_id"],
                    status=next_state,
                    updated_at=ts,
                ) or updated_item
                self._sync_linked_record(updated_item, next_state)
                transition = {
                    "item_id": item["item_id"],
                    "category": item["category"],
                    "priority": item["priority"],
                    "from_status": prev_state,
                    "to_status": next_state,
                    "timestamp_utc": ts,
                }
                transitions.append(transition)
                self.sync_history.append(transition)

            processed_items.append(updated_item)

        return {
            "online": True,
            "processed_count": len(processed_items),
            "pending_count": 0,
            "items": processed_items,
            "transitions": transitions,
        }
