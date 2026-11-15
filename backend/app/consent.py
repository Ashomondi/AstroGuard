"""Astronaut-owned privacy, consent matrix, redaction, and access audit log (F-26).

Enforces AstroGuard's privacy rules (FEATURES.md §3):
- Every personal data check runs through `check_access()` and appends an audit record.
- Crew Health Officer access follows each astronaut's normal switches, or a 2-hour
  emergency override when a deterministic critical rule is active AND emergency switch allows.
- Behavioral data can never be accessed for fitness-for-duty evaluation.
- Systems Engineer only sees anonymized habitat zone data (`Crew A`..`Crew D`), never raw vitals.
- Ground Support never sees raw personal crew health records or consent settings; ground summary
  sharing respects each astronaut's `ground_sharing` switch.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.schema import CREW_BY_ID, ConsentScope, Role
from app.store import AstraStore

VALID_SCOPES = {scope.value for scope in ConsentScope}

_ROLE_ALIASES: Dict[str, str] = {
    "astronaut": Role.ASTRONAUT.value,
    "crew": Role.ASTRONAUT.value,
    "crew health officer": Role.HEALTH_OFFICER.value,
    "health officer": Role.HEALTH_OFFICER.value,
    "health_officer": Role.HEALTH_OFFICER.value,
    "ho": Role.HEALTH_OFFICER.value,
    "systems engineer": Role.SYSTEMS_ENGINEER.value,
    "systems_engineer": Role.SYSTEMS_ENGINEER.value,
    "systems": Role.SYSTEMS_ENGINEER.value,
    "ground support": Role.GROUND_SUPPORT.value,
    "ground_support": Role.GROUND_SUPPORT.value,
    "ground": Role.GROUND_SUPPORT.value,
}

DEFAULT_CONSENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "ast-01": {
        "astronaut_id": "ast-01",
        "normal": {
            "physio": True,
            "cognitive": True,
            "behaviour": True,
            "habitat": True,
            "ground_sharing": True,
        },
        "emergency": {
            "physio": True,
            "cognitive": True,
            "behaviour": True,
            "habitat": True,
            "ground_sharing": True,
        },
        "override_duration_hours": 2,
    },
    "ast-02": {
        "astronaut_id": "ast-02",
        "normal": {
            "physio": True,
            "cognitive": True,
            "behaviour": False,
            "habitat": True,
            "ground_sharing": False,
        },
        "emergency": {
            "physio": True,
            "cognitive": True,
            "behaviour": False,
            "habitat": True,
            "ground_sharing": False,
        },
        "override_duration_hours": 2,
    },
    "ast-03": {
        "astronaut_id": "ast-03",
        "normal": {
            "physio": True,
            "cognitive": False,
            "behaviour": True,
            "habitat": True,
            "ground_sharing": True,
        },
        "emergency": {
            "physio": True,
            "cognitive": True,
            "behaviour": True,
            "habitat": True,
            "ground_sharing": True,
        },
        "override_duration_hours": 2,
    },
    "ast-04": {
        "astronaut_id": "ast-04",
        "normal": {
            "physio": True,
            "cognitive": True,
            "behaviour": True,
            "habitat": True,
            "ground_sharing": True,
        },
        "emergency": {
            "physio": True,
            "cognitive": True,
            "behaviour": True,
            "habitat": True,
            "ground_sharing": True,
        },
        "override_duration_hours": 2,
    },
}


def _unwrap_enum(value: Any) -> str:
    return value.value if isinstance(value, Enum) else str(value)


def _normalize_role(viewer_role: Any) -> str:
    raw = _unwrap_enum(viewer_role).strip()
    canonical = _ROLE_ALIASES.get(raw.lower())
    if canonical is None:
        raise ValueError(f"Unknown viewer_role: {viewer_role}")
    return canonical


def _normalize_scope(scope: Any) -> str:
    raw = _unwrap_enum(scope).strip().lower()
    if raw not in VALID_SCOPES:
        raise ValueError(f"Unknown consent scope: {scope}")
    return raw


def _anonymize_payload(payload: Any, target_astronaut_id: str) -> Any:
    crew = CREW_BY_ID.get(target_astronaut_id)
    anon_label = crew.anonymous_label if crew else "Crew"
    if isinstance(payload, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in payload.items():
            if k in ("astronaut_id", "target_astronaut_id"):
                cleaned[k] = anon_label
            elif k in ("name", "short_name", "initials"):
                cleaned[k] = anon_label
            else:
                cleaned[k] = _anonymize_payload(v, target_astronaut_id)
        return cleaned
    if isinstance(payload, list):
        return [_anonymize_payload(item, target_astronaut_id) for item in payload]
    return payload


class ConsentManager:
    """Enforces astronaut-owned consent policies and immutable access auditing."""

    def __init__(self, store: AstraStore) -> None:
        self.store = store
        self._init_default_profiles()

    def _init_default_profiles(self) -> None:
        for astronaut_id, default_profile in DEFAULT_CONSENT_PROFILES.items():
            if self.store.get_consent(astronaut_id) is None:
                self.store.set_consent(astronaut_id, deepcopy(default_profile))

    def get_profile(self, astronaut_id: str) -> Dict[str, Any]:
        profile = self.store.get_consent(astronaut_id)
        if profile is None:
            if astronaut_id in DEFAULT_CONSENT_PROFILES:
                profile = self.store.set_consent(
                    astronaut_id, deepcopy(DEFAULT_CONSENT_PROFILES[astronaut_id])
                )
            else:
                raise ValueError(f"Unknown astronaut_id: {astronaut_id}")
        return profile

    def update_profile(
        self,
        astronaut_id: str,
        normal_updates: Optional[Dict[str, bool]] = None,
        emergency_updates: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, Any]:
        profile = deepcopy(self.get_profile(astronaut_id))
        if normal_updates:
            for scope_key, enabled in normal_updates.items():
                norm_scope = _normalize_scope(scope_key)
                profile["normal"][norm_scope] = bool(enabled)
        if emergency_updates:
            for scope_key, enabled in emergency_updates.items():
                norm_scope = _normalize_scope(scope_key)
                profile["emergency"][norm_scope] = bool(enabled)
        return self.store.set_consent(astronaut_id, profile)

    def get_consent_matrix(self) -> Dict[str, Dict[str, Any]]:
        matrix: Dict[str, Dict[str, Any]] = {}
        for astronaut_id in CREW_BY_ID:
            matrix[astronaut_id] = self.get_profile(astronaut_id)
        return matrix

    def check_access(
        self,
        viewer_role: str,
        target_astronaut_id: str,
        scope: str,
        active_critical_rule: bool = False,
        reason: str = "routine view",
        viewer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        canonical_role = _normalize_role(viewer_role)
        norm_scope = _normalize_scope(scope)
        profile = self.get_profile(target_astronaut_id)

        allowed = False
        override_used = False
        access_mode = "denied"
        override_expires_at: Optional[str] = None
        policy_note = ""

        # Hard rule: behavioral data is never used for fitness-for-duty decisions.
        if norm_scope == ConsentScope.BEHAVIOUR.value and "fitness" in reason.lower():
            allowed = False
            access_mode = "denied"
            policy_note = "Behavioral data cannot be used for fitness-for-duty."
        elif canonical_role == Role.ASTRONAUT.value:
            if viewer_id is not None and viewer_id != target_astronaut_id and norm_scope != ConsentScope.HABITAT.value:
                allowed = False
                access_mode = "denied"
                policy_note = "Astronauts cannot view another astronaut's personal health data."
            else:
                allowed = True
                access_mode = "self"
                policy_note = "Astronaut owns and has full access to own data."
        elif canonical_role == Role.SYSTEMS_ENGINEER.value:
            if norm_scope == ConsentScope.HABITAT.value:
                allowed = True
                access_mode = "role_aggregate"
                policy_note = "Systems Engineer allowed anonymized habitat zone telemetry."
            else:
                allowed = False
                access_mode = "denied"
                policy_note = "Systems Engineer cannot access personal astronaut scopes."
        elif canonical_role == Role.GROUND_SUPPORT.value:
            if norm_scope == ConsentScope.HABITAT.value:
                allowed = True
                access_mode = "role_aggregate"
                policy_note = "Ground Support allowed anonymized shared habitat exposure alerts."
            elif norm_scope == ConsentScope.GROUND_SHARING.value:
                if profile["normal"].get(ConsentScope.GROUND_SHARING.value, False):
                    allowed = True
                    access_mode = "normal_consent"
                    policy_note = "Astronaut consented to ground summary sharing."
                elif active_critical_rule and profile["emergency"].get(ConsentScope.GROUND_SHARING.value, False):
                    allowed = True
                    override_used = True
                    access_mode = "emergency_override"
                    override_hours = int(profile.get("override_duration_hours", 2))
                    override_expires_at = (
                        datetime.now(timezone.utc) + timedelta(hours=override_hours)
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")
                    policy_note = "Emergency ground summary override active."
                else:
                    allowed = False
                    access_mode = "denied"
                    policy_note = "Astronaut disabled ground_sharing."
            else:
                allowed = False
                access_mode = "denied"
                policy_note = "Ground Support receives summaries only, never raw personal health records."
        elif canonical_role == Role.HEALTH_OFFICER.value:
            normal_ok = bool(profile["normal"].get(norm_scope, False))
            if normal_ok:
                allowed = True
                access_mode = "normal_consent"
                policy_note = "Allowed by astronaut normal consent profile."
            elif active_critical_rule and bool(profile["emergency"].get(norm_scope, False)):
                allowed = True
                override_used = True
                access_mode = "emergency_override"
                override_hours = int(profile.get("override_duration_hours", 2))
                override_expires_at = (
                    datetime.now(timezone.utc) + timedelta(hours=override_hours)
                ).strftime("%Y-%m-%dT%H:%M:%SZ")
                policy_note = "Time-limited emergency override active due to critical safety rule."
            else:
                allowed = False
                access_mode = "denied"
                policy_note = (
                    "Denied by astronaut emergency consent switch."
                    if active_critical_rule
                    else "Denied by astronaut normal consent switch."
                )

        log_entry = self.store.append_access_log(
            viewer_role=canonical_role,
            target_astronaut_id=target_astronaut_id,
            scope=norm_scope,
            allowed=allowed,
            override_used=override_used,
            active_critical_rule=bool(active_critical_rule),
            reason=reason,
            access_mode=access_mode,
            override_expires_at=override_expires_at,
            policy_note=policy_note,
        )
        return log_entry

    def redact_for_role(
        self,
        viewer_role: str,
        target_astronaut_id: str,
        data_by_scope: Dict[str, Any],
        active_critical_rule: bool = False,
        reason: str = "view",
        viewer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        canonical_role = _normalize_role(viewer_role)
        allowed_data: Dict[str, Any] = {}
        redacted_scopes: List[str] = []
        allowed_scopes: List[str] = []
        decisions: Dict[str, Dict[str, Any]] = {}

        anonymize_identity = canonical_role in (
            Role.SYSTEMS_ENGINEER.value,
            Role.GROUND_SUPPORT.value,
        )

        for scope_key, payload in data_by_scope.items():
            norm_scope = _normalize_scope(scope_key)
            decision = self.check_access(
                viewer_role=canonical_role,
                target_astronaut_id=target_astronaut_id,
                scope=norm_scope,
                active_critical_rule=active_critical_rule,
                reason=reason,
                viewer_id=viewer_id,
            )
            decisions[norm_scope] = decision
            if decision["allowed"]:
                allowed_scopes.append(norm_scope)
                allowed_data[norm_scope] = (
                    _anonymize_payload(payload, target_astronaut_id)
                    if anonymize_identity
                    else deepcopy(payload)
                )
            else:
                redacted_scopes.append(norm_scope)

        crew = CREW_BY_ID.get(target_astronaut_id)
        subject_label = (
            crew.anonymous_label if (anonymize_identity and crew is not None) else target_astronaut_id
        )

        return {
            "astronaut_id": subject_label,
            "viewer_role": canonical_role,
            "data": allowed_data,
            "allowed_scopes": allowed_scopes,
            "redacted_scopes": redacted_scopes,
            "override_active": any(d["override_used"] for d in decisions.values()),
            "decisions": decisions,
        }
