"""Dataset registry loader and fixture replay adapters for AstroGuard (F-41).

Pure Python 3.14 standard library implementation that loads `data/registry.yaml`
and adapts compact derived fixtures (such as `data/fixtures/sample_wearable.json`)
into canonical `MeasurementRecord` instances without ever fabricating normal values
for missing or sensor-off periods.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.schema import (
    SIGNAL_TO_SCOPE,
    SIGNAL_UNITS,
    ConsentScope,
    MeasurementRecord,
    QualityState,
    SignalType,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGISTRY_PATH = REPO_ROOT / "data" / "registry.yaml"
DEFAULT_FIXTURE_PATH = REPO_ROOT / "data" / "fixtures" / "sample_wearable.json"

ALLOWED_DATASET_ROLES = {
    "signal_priors",
    "realism_only",
    "external_validation_if_granted",
}

SIGNAL_ALIASES: Dict[str, str] = {
    "hr": SignalType.HEART_RATE.value,
    "heart_rate": SignalType.HEART_RATE.value,
    "rhr": SignalType.RESTING_HR.value,
    "resting_hr": SignalType.RESTING_HR.value,
    "hrv": SignalType.HRV_RMSSD.value,
    "hrv_rmssd": SignalType.HRV_RMSSD.value,
    "hr_recovery_1m": SignalType.HR_RECOVERY_1M.value,
    "spo2": SignalType.SPO2.value,
    "sleep_duration": SignalType.SLEEP_DURATION.value,
    "sleep_fragmentation": SignalType.SLEEP_FRAGMENTATION.value,
    "pvt_mean_rt": SignalType.PVT_MEAN_RT.value,
    "pvt_lapses": SignalType.PVT_LAPSES.value,
    "activity": SignalType.ACTIVITY_INDEX.value,
    "activity_index": SignalType.ACTIVITY_INDEX.value,
    "mood": SignalType.MOOD_SCORE.value,
    "mood_score": SignalType.MOOD_SCORE.value,
    "energy": SignalType.ENERGY_SCORE.value,
    "energy_score": SignalType.ENERGY_SCORE.value,
    "stress": SignalType.STRESS_SCORE.value,
    "stress_score": SignalType.STRESS_SCORE.value,
    "co2": SignalType.CO2_PPM.value,
    "co2_ppm": SignalType.CO2_PPM.value,
}


def _parse_yaml_scalar(raw: str) -> Any:
    val = raw.strip()
    if val in ("null", "Null", "NULL", "~", ""):
        return None
    if val in ("true", "True"):
        return True
    if val in ("false", "False"):
        return False
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        return val[1:-1]
    return val


def _parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Parse the constrained YAML subset used by `data/registry.yaml` in pure stdlib."""
    root: Dict[str, Any] = {}
    current_top_list: Optional[List[Any]] = None
    current_item: Optional[Dict[str, Any]] = None
    current_sublist: Optional[List[Any]] = None

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))

        if indent == 0:
            current_item = None
            current_sublist = None
            if ":" not in stripped:
                continue
            key, rest = stripped.split(":", 1)
            key = key.strip()
            rest = rest.strip()
            if rest == "":
                lst: List[Any] = []
                root[key] = lst
                current_top_list = lst
            else:
                root[key] = _parse_yaml_scalar(rest)
                current_top_list = None
        elif indent == 2 and stripped.startswith("- ") and current_top_list is not None:
            body = stripped[2:].strip()
            current_sublist = None
            item: Dict[str, Any] = {}
            if ":" in body:
                k, v = body.split(":", 1)
                item[k.strip()] = _parse_yaml_scalar(v)
            current_top_list.append(item)
            current_item = item
        elif indent == 4 and current_item is not None and ":" in stripped:
            current_sublist = None
            k, v = stripped.split(":", 1)
            k = k.strip()
            v = v.strip()
            if v == "":
                sub: List[Any] = []
                current_item[k] = sub
                current_sublist = sub
            else:
                current_item[k] = _parse_yaml_scalar(v)
        elif indent >= 6 and stripped.startswith("- ") and current_sublist is not None:
            current_sublist.append(_parse_yaml_scalar(stripped[2:]))

    return root


def load_dataset_registry(registry_path: Optional[Path | str] = None) -> Dict[str, Any]:
    """Load and validate `data/registry.yaml` dataset entries and honest roles."""
    path = Path(registry_path) if registry_path is not None else DEFAULT_REGISTRY_PATH
    if not path.exists():
        raise FileNotFoundError(f"Dataset registry not found: {path}")

    parsed = _parse_simple_yaml(path.read_text(encoding="utf-8"))
    datasets = parsed.get("datasets", [])
    if not isinstance(datasets, list) or not datasets:
        raise ValueError("Registry YAML must define a non-empty 'datasets' list")

    for ds in datasets:
        role = ds.get("role")
        if role not in ALLOWED_DATASET_ROLES:
            raise ValueError(
                f"Dataset '{ds.get('name', ds.get('id'))}' has invalid role '{role}'; "
                f"expected one of {sorted(ALLOWED_DATASET_ROLES)}"
            )
    return parsed


def adapt_wearable_record(
    raw: Dict[str, Any],
    default_astronaut_id: str = "ast-sim-01",
    default_zone_id: str = "LAB",
) -> MeasurementRecord:
    """Convert a single raw wearable fixture dictionary into a `MeasurementRecord`."""
    raw_sig = str(raw.get("signal_type") or raw.get("signal") or "").strip().lower()
    signal_type = SIGNAL_ALIASES.get(raw_sig, raw_sig)
    if signal_type not in SIGNAL_UNITS:
        raise ValueError(f"Unknown wearable signal_type '{raw_sig}' in fixture")

    day = int(raw.get("day", 1))
    hour = int(raw.get("hour", 0))
    met = float(raw.get("mission_elapsed_time", raw.get("met_hours", (day - 1) * 24 + hour)))
    ts_utc = str(raw.get("timestamp_utc") or raw.get("ts_utc") or f"2031-03-{day:02d}T{hour:02d}:00:00Z")

    quality = str(raw.get("quality") or raw.get("sensor_status") or QualityState.OK.value)
    raw_val = raw.get("value")
    if quality in (QualityState.SENSOR_OFF.value, QualityState.MISSING.value):
        value: Optional[float] = None
        confidence = 0.0
    else:
        value = None if raw_val is None else float(raw_val)
        if value is None:
            quality = QualityState.MISSING.value
            confidence = 0.0
        else:
            default_conf = 0.3 if quality == QualityState.SUSPECT.value else 0.95
            confidence = float(raw.get("confidence", default_conf))

    tags = raw.get("context_tags") or raw.get("context") or ["rest"]
    if isinstance(tags, str):
        tags_list = [tags]
    else:
        tags_list = [str(t) for t in tags]

    return MeasurementRecord(
        astronaut_id=str(raw.get("astronaut_id", default_astronaut_id)),
        timestamp_utc=ts_utc,
        mission_elapsed_time=met,
        day=day,
        hour=hour,
        signal_type=signal_type,
        value=value,
        unit=str(raw.get("unit") or SIGNAL_UNITS[signal_type]),
        source_device=str(raw.get("source_device") or raw.get("device") or "wearable-fixture"),
        firmware_version=str(raw.get("firmware_version") or raw.get("firmware") or "1.0.0"),
        quality=quality,
        confidence=confidence,
        context_tags=tags_list,
        consent_scope=str(
            raw.get("consent_scope") or SIGNAL_TO_SCOPE.get(signal_type, ConsentScope.PHYSIO.value)
        ),
        zone_id=str(raw.get("zone_id") or default_zone_id),
    )


def load_wearable_fixture(
    fixture_path: Optional[Path | str] = None,
    astronaut_id: Optional[str] = None,
) -> List[MeasurementRecord]:
    """Load a derived wearable JSON fixture and convert every item into `MeasurementRecord`."""
    path = Path(fixture_path) if fixture_path is not None else DEFAULT_FIXTURE_PATH
    if not path.exists():
        raise FileNotFoundError(f"Wearable fixture not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contains_real_personal_data") is True:
        raise ValueError("Fixture flagged contains_real_personal_data=True; disallowed by repo policy.")

    default_aid = astronaut_id or str(payload.get("default_astronaut_id", "ast-sim-01"))
    default_zone = str(payload.get("default_zone_id", "LAB"))
    raw_records = payload.get("records", [])
    records = [
        adapt_wearable_record(item, default_astronaut_id=default_aid, default_zone_id=default_zone)
        for item in raw_records
    ]
    records.sort(key=lambda r: (r.day, r.hour, r.astronaut_id, r.signal_type))
    return records


def summarize_fixture(records: Sequence[MeasurementRecord]) -> Dict[str, Any]:
    """Return a concise summary of adapted fixture records and explicit quality states."""
    quality_counts: Dict[str, int] = {q.value: 0 for q in QualityState}
    signals = sorted({r.signal_type for r in records})
    for rec in records:
        quality_counts[rec.quality] = quality_counts.get(rec.quality, 0) + 1
    return {
        "total_records": len(records),
        "signals": signals,
        "quality_counts": quality_counts,
        "astronaut_ids": sorted({r.astronaut_id for r in records}),
    }
