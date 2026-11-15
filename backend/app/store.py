"""Offline-first append-only SQLite store for AstroGuard (F-04).

Manages local persistence across 9 tables:
- `measurements` (strictly append-only via SQLite BEFORE UPDATE / BEFORE DELETE triggers)
- `checkins`
- `pvt_tests`
- `sos_events`
- `messages`
- `consent_profiles`
- `access_log`
- `sync_queue`
- `advisor_audit_log`
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from app.schema import MeasurementRecord


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _merge_payload(item: Optional[Dict[str, Any]], kwargs: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(item) if item is not None else {}
    merged.update(kwargs)
    return merged


class AstraStore:
    """Thread-safe local SQLite store with append-only measurement guarantees."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA foreign_keys = ON;")
            if db_path != ":memory:":
                self._conn.execute("PRAGMA journal_mode = WAL;")
            self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "AstraStore":
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS measurements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id TEXT NOT NULL,
                astronaut_id TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                mission_elapsed_time REAL NOT NULL,
                day INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                signal_type TEXT NOT NULL,
                value REAL,
                unit TEXT NOT NULL,
                source_device TEXT NOT NULL,
                firmware_version TEXT NOT NULL,
                quality TEXT NOT NULL,
                confidence REAL NOT NULL,
                context_tags_json TEXT NOT NULL,
                consent_scope TEXT NOT NULL,
                zone_id TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_measurements_lookup
                ON measurements (astronaut_id, signal_type, day, hour);

            CREATE TRIGGER IF NOT EXISTS trg_measurements_no_update
            BEFORE UPDATE ON measurements
            BEGIN
                SELECT RAISE(ABORT, 'measurements table is append-only');
            END;

            CREATE TRIGGER IF NOT EXISTS trg_measurements_no_delete
            BEFORE DELETE ON measurements
            BEGIN
                SELECT RAISE(ABORT, 'measurements table is append-only');
            END;

            CREATE TABLE IF NOT EXISTS checkins (
                checkin_id TEXT PRIMARY KEY,
                astronaut_id TEXT NOT NULL,
                day INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                timestamp_utc TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_checkins_astro_day
                ON checkins (astronaut_id, day);

            CREATE TABLE IF NOT EXISTS pvt_tests (
                pvt_id TEXT PRIMARY KEY,
                astronaut_id TEXT NOT NULL,
                day INTEGER NOT NULL,
                hour INTEGER NOT NULL,
                timestamp_utc TEXT NOT NULL,
                mean_rt_ms REAL,
                lapses INTEGER,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_pvt_astro_day
                ON pvt_tests (astronaut_id, day);

            CREATE TABLE IF NOT EXISTS sos_events (
                sos_id TEXT PRIMARY KEY,
                astronaut_id TEXT NOT NULL,
                sos_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                day INTEGER,
                hour INTEGER,
                note TEXT,
                override_active INTEGER NOT NULL DEFAULT 1,
                override_expires_at TEXT,
                packet_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                sender_id TEXT NOT NULL,
                recipient_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                urgency TEXT NOT NULL,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS consent_profiles (
                astronaut_id TEXT PRIMARY KEY,
                profile_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_id TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                viewer_role TEXT NOT NULL,
                target_astronaut_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                allowed INTEGER NOT NULL,
                override_used INTEGER NOT NULL DEFAULT 0,
                reason TEXT NOT NULL,
                details_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_access_log_target
                ON access_log (target_astronaut_id, id);

            CREATE TABLE IF NOT EXISTS sync_queue (
                item_id TEXT PRIMARY KEY,
                category TEXT NOT NULL,
                priority INTEGER NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                meta_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sync_queue_order
                ON sync_queue (priority, created_at);

            CREATE TABLE IF NOT EXISTS advisor_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                audit_id TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                astronaut_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                prompt TEXT NOT NULL,
                response TEXT NOT NULL,
                citations_json TEXT NOT NULL,
                meta_json TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Measurements (append-only)
    # ------------------------------------------------------------------
    def append_measurements(self, records: Iterable[MeasurementRecord | Dict[str, Any]]) -> int:
        now = _utc_now_iso()
        rows = []
        for item in records:
            rec = item if isinstance(item, MeasurementRecord) else MeasurementRecord.from_dict(item)
            rows.append(
                (
                    rec.record_id,
                    rec.astronaut_id,
                    rec.timestamp_utc,
                    float(rec.mission_elapsed_time),
                    int(rec.day),
                    int(rec.hour),
                    rec.signal_type,
                    None if rec.value is None else float(rec.value),
                    rec.unit,
                    rec.source_device,
                    rec.firmware_version,
                    rec.quality,
                    float(rec.confidence),
                    json.dumps(list(rec.context_tags)),
                    rec.consent_scope,
                    rec.zone_id,
                    now,
                )
            )
        if not rows:
            return 0
        with self._lock:
            self._conn.executemany(
                """
                INSERT INTO measurements (
                    record_id, astronaut_id, timestamp_utc, mission_elapsed_time,
                    day, hour, signal_type, value, unit, source_device,
                    firmware_version, quality, confidence, context_tags_json,
                    consent_scope, zone_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            self._conn.commit()
        return len(rows)

    def get_measurements(
        self,
        astronaut_id: Optional[str] = None,
        signal_type: Optional[str] = None,
        max_day: Optional[int] = None,
        min_day: Optional[int] = None,
        quality: Optional[str] = None,
        zone_id: Optional[str] = None,
    ) -> List[MeasurementRecord]:
        clauses: List[str] = []
        params: List[Any] = []
        if astronaut_id is not None:
            clauses.append("astronaut_id = ?")
            params.append(astronaut_id)
        if signal_type is not None:
            clauses.append("signal_type = ?")
            params.append(signal_type)
        if max_day is not None:
            clauses.append("day <= ?")
            params.append(int(max_day))
        if min_day is not None:
            clauses.append("day >= ?")
            params.append(int(min_day))
        if quality is not None:
            clauses.append("quality = ?")
            params.append(quality)
        if zone_id is not None:
            clauses.append("zone_id = ?")
            params.append(zone_id)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT * FROM measurements
            {where_sql}
            ORDER BY day ASC, hour ASC, timestamp_utc ASC, id ASC
        """
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()

        return [
            MeasurementRecord(
                record_id=row["record_id"],
                astronaut_id=row["astronaut_id"],
                timestamp_utc=row["timestamp_utc"],
                mission_elapsed_time=float(row["mission_elapsed_time"]),
                day=int(row["day"]),
                hour=int(row["hour"]),
                signal_type=row["signal_type"],
                value=None if row["value"] is None else float(row["value"]),
                unit=row["unit"],
                source_device=row["source_device"],
                firmware_version=row["firmware_version"],
                quality=row["quality"],
                confidence=float(row["confidence"]),
                context_tags=json.loads(row["context_tags_json"]),
                consent_scope=row["consent_scope"],
                zone_id=row["zone_id"],
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Check-ins
    # ------------------------------------------------------------------
    def insert_checkin(self, checkin: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        data = _merge_payload(checkin, kwargs)
        now = _utc_now_iso()
        checkin_id = str(data.get("checkin_id") or f"chk-{uuid.uuid4().hex[:10]}")
        astronaut_id = str(data["astronaut_id"])
        day = int(data.get("day", 1))
        hour = int(data.get("hour", 16))
        timestamp_utc = str(data.get("timestamp_utc") or now)

        stored = dict(data)
        stored["checkin_id"] = checkin_id
        stored["astronaut_id"] = astronaut_id
        stored["day"] = day
        stored["hour"] = hour
        stored["timestamp_utc"] = timestamp_utc

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO checkins (
                    checkin_id, astronaut_id, day, hour, timestamp_utc, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (checkin_id, astronaut_id, day, hour, timestamp_utc, json.dumps(stored), now),
            )
            self._conn.commit()
        stored["created_at"] = now
        return stored

    def get_checkins(
        self,
        astronaut_id: Optional[str] = None,
        max_day: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if astronaut_id is not None:
            clauses.append("astronaut_id = ?")
            params.append(astronaut_id)
        if max_day is not None:
            clauses.append("day <= ?")
            params.append(int(max_day))
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM checkins {where_sql} ORDER BY day ASC, hour ASC, created_at ASC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            item = json.loads(row["payload_json"])
            item["checkin_id"] = row["checkin_id"]
            item["created_at"] = row["created_at"]
            out.append(item)
        return out

    # ------------------------------------------------------------------
    # PVT tests
    # ------------------------------------------------------------------
    def insert_pvt(self, pvt: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        data = _merge_payload(pvt, kwargs)
        now = _utc_now_iso()
        pvt_id = str(data.get("pvt_id") or f"pvt-{uuid.uuid4().hex[:10]}")
        astronaut_id = str(data["astronaut_id"])
        day = int(data.get("day", 1))
        hour = int(data.get("hour", 16))
        timestamp_utc = str(data.get("timestamp_utc") or now)

        raw_rt = data.get("mean_rt_ms", data.get("pvt_mean_rt", data.get("mean_rt")))
        mean_rt_ms = None if raw_rt is None else float(raw_rt)
        raw_lapses = data.get("lapses", data.get("pvt_lapses"))
        lapses = None if raw_lapses is None else int(raw_lapses)

        stored = dict(data)
        stored["pvt_id"] = pvt_id
        stored["astronaut_id"] = astronaut_id
        stored["day"] = day
        stored["hour"] = hour
        stored["timestamp_utc"] = timestamp_utc
        if mean_rt_ms is not None:
            stored["mean_rt_ms"] = mean_rt_ms
        if lapses is not None:
            stored["lapses"] = lapses

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO pvt_tests (
                    pvt_id, astronaut_id, day, hour, timestamp_utc,
                    mean_rt_ms, lapses, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pvt_id,
                    astronaut_id,
                    day,
                    hour,
                    timestamp_utc,
                    mean_rt_ms,
                    lapses,
                    json.dumps(stored),
                    now,
                ),
            )
            self._conn.commit()
        stored["created_at"] = now
        return stored

    def get_pvts(
        self,
        astronaut_id: Optional[str] = None,
        max_day: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if astronaut_id is not None:
            clauses.append("astronaut_id = ?")
            params.append(astronaut_id)
        if max_day is not None:
            clauses.append("day <= ?")
            params.append(int(max_day))
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM pvt_tests {where_sql} ORDER BY day ASC, hour ASC, created_at ASC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            item = json.loads(row["payload_json"])
            item["pvt_id"] = row["pvt_id"]
            item["created_at"] = row["created_at"]
            out.append(item)
        return out

    # ------------------------------------------------------------------
    # SOS events
    # ------------------------------------------------------------------
    def _row_to_sos(self, row: sqlite3.Row) -> Dict[str, Any]:
        packet = json.loads(row["packet_json"])
        result = dict(packet)
        result.update(
            {
                "sos_id": row["sos_id"],
                "astronaut_id": row["astronaut_id"],
                "sos_type": row["sos_type"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "day": row["day"],
                "hour": row["hour"],
                "note": row["note"],
                "override_active": bool(row["override_active"]),
                "override_expires_at": row["override_expires_at"],
            }
        )
        return result

    def save_sos(self, sos: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        data = _merge_payload(sos, kwargs)
        now = _utc_now_iso()
        sos_id = str(data.get("sos_id") or f"sos-{uuid.uuid4().hex[:10]}")
        astronaut_id = str(data["astronaut_id"])
        sos_type = str(data.get("sos_type", data.get("type", "Medical")))
        status = str(data.get("status", "queued"))
        created_at = str(data.get("created_at") or now)
        updated_at = str(data.get("updated_at") or now)
        day = None if data.get("day") is None else int(data["day"])
        hour = None if data.get("hour") is None else int(data["hour"])
        note = data.get("note")
        override_active = 1 if data.get("override_active", True) else 0
        override_expires_at = data.get("override_expires_at")
        packet = dict(data)
        packet["sos_id"] = sos_id
        packet["astronaut_id"] = astronaut_id
        packet["sos_type"] = sos_type
        packet["status"] = status

        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO sos_events (
                    sos_id, astronaut_id, sos_type, status, created_at, updated_at,
                    day, hour, note, override_active, override_expires_at, packet_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    sos_id,
                    astronaut_id,
                    sos_type,
                    status,
                    created_at,
                    updated_at,
                    day,
                    hour,
                    note,
                    override_active,
                    override_expires_at,
                    json.dumps(packet),
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM sos_events WHERE sos_id = ?", (sos_id,)
            ).fetchone()
        return self._row_to_sos(row)

    def update_sos(
        self,
        sos_id: str,
        updates: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        patch = _merge_payload(updates, kwargs)
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sos_events WHERE sos_id = ?", (sos_id,)
            ).fetchone()
            if row is None:
                return None
            current = self._row_to_sos(row)
            current.update(patch)
            current["sos_id"] = sos_id
            current["updated_at"] = str(patch.get("updated_at") or _utc_now_iso())
            return self.save_sos(current)

    def get_sos_events(
        self,
        astronaut_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if astronaut_id is not None:
            clauses.append("astronaut_id = ?")
            params.append(astronaut_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM sos_events {where_sql} ORDER BY created_at DESC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_sos(r) for r in rows]

    # ------------------------------------------------------------------
    # Messages (content opaque)
    # ------------------------------------------------------------------
    def _row_to_message(self, row: sqlite3.Row) -> Dict[str, Any]:
        payload = json.loads(row["payload_json"])
        result = dict(payload)
        result.update(
            {
                "message_id": row["message_id"],
                "sender_id": row["sender_id"],
                "recipient_id": row["recipient_id"],
                "channel": row["channel"],
                "urgency": row["urgency"],
                "kind": row["kind"],
                "status": row["status"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )
        return result

    def save_message(self, message: Optional[Dict[str, Any]] = None, **kwargs: Any) -> Dict[str, Any]:
        data = _merge_payload(message, kwargs)
        now = _utc_now_iso()
        message_id = str(data.get("message_id") or f"msg-{uuid.uuid4().hex[:10]}")
        sender_id = str(data["sender_id"])
        recipient_id = str(data.get("recipient_id", "ground"))
        channel = str(data.get("channel", "ground"))
        urgency = str(data.get("urgency", "routine"))
        kind = str(data.get("kind", "text"))
        status = str(data.get("status", "queued"))
        created_at = str(data.get("created_at") or now)
        updated_at = str(data.get("updated_at") or now)

        payload = dict(data)
        payload["message_id"] = message_id

        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO messages (
                    message_id, sender_id, recipient_id, channel, urgency,
                    kind, status, created_at, updated_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    sender_id,
                    recipient_id,
                    channel,
                    urgency,
                    kind,
                    status,
                    created_at,
                    updated_at,
                    json.dumps(payload),
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM messages WHERE message_id = ?", (message_id,)
            ).fetchone()
        return self._row_to_message(row)

    def update_message_status(
        self,
        message_id: str,
        status: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM messages WHERE message_id = ?", (message_id,)
            ).fetchone()
            if row is None:
                return None
            current = self._row_to_message(row)
            if extra:
                current.update(extra)
            current["status"] = status
            current["updated_at"] = _utc_now_iso()
            return self.save_message(current)

    def get_messages(
        self,
        participant_id: Optional[str] = None,
        channel: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if participant_id is not None:
            clauses.append("(sender_id = ? OR recipient_id = ?)")
            params.extend([participant_id, participant_id])
        if channel is not None:
            clauses.append("channel = ?")
            params.append(channel)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM messages {where_sql} ORDER BY created_at ASC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_message(r) for r in rows]

    # ------------------------------------------------------------------
    # Consent profiles
    # ------------------------------------------------------------------
    def get_consent(self, astronaut_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM consent_profiles WHERE astronaut_id = ?", (astronaut_id,)
            ).fetchone()
        if row is None:
            return None
        profile = json.loads(row["profile_json"])
        profile["astronaut_id"] = row["astronaut_id"]
        profile["updated_at"] = row["updated_at"]
        return profile

    def set_consent(self, astronaut_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        now = _utc_now_iso()
        stored = dict(profile)
        stored["astronaut_id"] = astronaut_id
        stored["updated_at"] = now
        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO consent_profiles (astronaut_id, profile_json, updated_at)
                VALUES (?, ?, ?)
                """,
                (astronaut_id, json.dumps(stored), now),
            )
            self._conn.commit()
        return stored

    # ------------------------------------------------------------------
    # Access log
    # ------------------------------------------------------------------
    def append_access_log(
        self, entry: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        data = _merge_payload(entry, kwargs)
        now = _utc_now_iso()
        log_id = str(data.get("log_id") or f"acc-{uuid.uuid4().hex[:10]}")
        timestamp_utc = str(data.get("timestamp_utc") or now)
        viewer_role = str(data["viewer_role"])
        target_astronaut_id = str(data["target_astronaut_id"])
        scope = str(data["scope"])
        allowed = 1 if bool(data["allowed"]) else 0
        override_used = 1 if bool(data.get("override_used", False)) else 0
        reason = str(data.get("reason", "routine view"))

        stored = dict(data)
        stored["log_id"] = log_id
        stored["timestamp_utc"] = timestamp_utc
        stored["allowed"] = bool(allowed)
        stored["override_used"] = bool(override_used)

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO access_log (
                    log_id, timestamp_utc, viewer_role, target_astronaut_id,
                    scope, allowed, override_used, reason, details_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    timestamp_utc,
                    viewer_role,
                    target_astronaut_id,
                    scope,
                    allowed,
                    override_used,
                    reason,
                    json.dumps(stored),
                ),
            )
            self._conn.commit()
        return stored

    def get_access_log(
        self,
        astronaut_id: Optional[str] = None,
        viewer_role: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if astronaut_id is not None:
            clauses.append("target_astronaut_id = ?")
            params.append(astronaut_id)
        if viewer_role is not None:
            clauses.append("viewer_role = ?")
            params.append(viewer_role)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = f"LIMIT {int(limit)}" if limit is not None else ""
        sql = f"SELECT * FROM access_log {where_sql} ORDER BY id DESC {limit_sql}"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            item = json.loads(row["details_json"])
            item["id"] = row["id"]
            item["log_id"] = row["log_id"]
            item["timestamp_utc"] = row["timestamp_utc"]
            item["viewer_role"] = row["viewer_role"]
            item["target_astronaut_id"] = row["target_astronaut_id"]
            item["scope"] = row["scope"]
            item["allowed"] = bool(row["allowed"])
            item["override_used"] = bool(row["override_used"])
            item["reason"] = row["reason"]
            out.append(item)
        return out

    # ------------------------------------------------------------------
    # Sync queue
    # ------------------------------------------------------------------
    def _row_to_sync(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "item_id": row["item_id"],
            "category": row["category"],
            "priority": int(row["priority"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "payload": json.loads(row["payload_json"]),
            "meta": json.loads(row["meta_json"]),
        }

    def enqueue_sync(
        self, item: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        data = _merge_payload(item, kwargs)
        now = _utc_now_iso()
        item_id = str(data.get("item_id") or f"sync-{uuid.uuid4().hex[:10]}")
        category = str(data["category"])
        priority = int(data["priority"])
        status = str(data.get("status", "queued"))
        created_at = str(data.get("created_at") or now)
        updated_at = str(data.get("updated_at") or now)
        payload = data.get("payload", {})
        meta = data.get("meta") or {}

        with self._lock:
            self._conn.execute(
                """
                INSERT OR REPLACE INTO sync_queue (
                    item_id, category, priority, status, created_at, updated_at,
                    payload_json, meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_id,
                    category,
                    priority,
                    status,
                    created_at,
                    updated_at,
                    json.dumps(payload),
                    json.dumps(meta),
                ),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM sync_queue WHERE item_id = ?", (item_id,)
            ).fetchone()
        return self._row_to_sync(row)

    def get_sync_queue(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if category is not None:
            clauses.append("category = ?")
            params.append(category)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT * FROM sync_queue
            {where_sql}
            ORDER BY priority ASC, created_at ASC, rowid ASC
        """
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_sync(r) for r in rows]

    def update_sync_item(
        self,
        item_id: str,
        updates: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Optional[Dict[str, Any]]:
        patch = _merge_payload(updates, kwargs)
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM sync_queue WHERE item_id = ?", (item_id,)
            ).fetchone()
            if row is None:
                return None
            current = self._row_to_sync(row)
            status = str(patch.get("status", current["status"]))
            updated_at = str(patch.get("updated_at") or _utc_now_iso())
            payload = patch.get("payload", current["payload"])
            meta = patch.get("meta", current["meta"])
            self._conn.execute(
                """
                UPDATE sync_queue
                SET status = ?, updated_at = ?, payload_json = ?, meta_json = ?
                WHERE item_id = ?
                """,
                (status, updated_at, json.dumps(payload), json.dumps(meta), item_id),
            )
            self._conn.commit()
            updated = self._conn.execute(
                "SELECT * FROM sync_queue WHERE item_id = ?", (item_id,)
            ).fetchone()
        return self._row_to_sync(updated)

    # ------------------------------------------------------------------
    # Advisor audit log
    # ------------------------------------------------------------------
    def append_advisor_log(
        self, entry: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        data = _merge_payload(entry, kwargs)
        now = _utc_now_iso()
        audit_id = str(data.get("audit_id") or f"adv-{uuid.uuid4().hex[:10]}")
        timestamp_utc = str(data.get("timestamp_utc") or now)
        astronaut_id = str(data.get("astronaut_id", ""))
        mode = str(data.get("mode", "ask"))
        prompt = str(data.get("prompt", ""))
        response = str(data.get("response", ""))
        citations = list(data.get("citations", []))
        meta = dict(data.get("meta", {}))

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO advisor_audit_log (
                    audit_id, timestamp_utc, astronaut_id, mode, prompt,
                    response, citations_json, meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit_id,
                    timestamp_utc,
                    astronaut_id,
                    mode,
                    prompt,
                    response,
                    json.dumps(citations),
                    json.dumps(meta),
                ),
            )
            self._conn.commit()

        return {
            "audit_id": audit_id,
            "timestamp_utc": timestamp_utc,
            "astronaut_id": astronaut_id,
            "mode": mode,
            "prompt": prompt,
            "response": response,
            "citations": citations,
            "meta": meta,
        }

    def get_advisor_logs(self, astronaut_id: Optional[str] = None) -> List[Dict[str, Any]]:
        clauses: List[str] = []
        params: List[Any] = []
        if astronaut_id is not None:
            clauses.append("astronaut_id = ?")
            params.append(astronaut_id)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"SELECT * FROM advisor_audit_log {where_sql} ORDER BY id DESC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [
            {
                "id": row["id"],
                "audit_id": row["audit_id"],
                "timestamp_utc": row["timestamp_utc"],
                "astronaut_id": row["astronaut_id"],
                "mode": row["mode"],
                "prompt": row["prompt"],
                "response": row["response"],
                "citations": json.loads(row["citations_json"]),
                "meta": json.loads(row["meta_json"]),
            }
            for row in rows
        ]
