"""Common data contracts for AstroGuard (FEATURES.md §5.3 & docs/validation-plan.md §3).

Owned by BE-1 (Tech Lead). Changes require coordinator review.
All thresholds and ranges are illustrative sample bounds, not validated medical limits.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class QualityState(str, Enum):
    """Distinct sensor and data-quality states; missing is never silently normal."""

    OK = "ok"
    SUSPECT = "suspect"
    SENSOR_OFF = "sensor_off"
    MISSING = "missing"
    OUT_OF_RANGE = "out_of_range"


class SignalType(str, Enum):
    """Canonical signal identifiers across wearables, cognitive tasks, self-report, and habitat."""

    HEART_RATE = "heart_rate"
    RESTING_HR = "resting_hr"
    HRV_RMSSD = "hrv_rmssd"
    HR_RECOVERY_1M = "hr_recovery_1m"
    SPO2 = "spo2"
    SLEEP_DURATION = "sleep_duration"
    SLEEP_FRAGMENTATION = "sleep_fragmentation"
    PVT_MEAN_RT = "pvt_mean_rt"
    PVT_LAPSES = "pvt_lapses"
    SYMPTOM_HEADACHE = "symptom_headache"
    SYMPTOM_FATIGUE = "symptom_fatigue"
    MOOD_SCORE = "mood_score"
    ENERGY_SCORE = "energy_score"
    STRESS_SCORE = "stress_score"
    ACTIVITY_INDEX = "activity_index"
    CO2_PPM = "co2_ppm"
    CABIN_TEMP_C = "cabin_temp_c"
    CABIN_HUMIDITY_PCT = "cabin_humidity_pct"
    CABIN_NOISE_DB = "cabin_noise_db"
    RADIATION_USV_DAY = "radiation_usv_day"
    RADIATION_CUMULATIVE_MSV = "radiation_cumulative_msv"


class ConsentScope(str, Enum):
    """Astronaut-owned sharing scopes."""

    PHYSIO = "physio"
    COGNITIVE = "cognitive"
    BEHAVIOUR = "behaviour"
    HABITAT = "habitat"
    GROUND_SHARING = "ground_sharing"


class Role(str, Enum):
    """Active MVP mission roles."""

    ASTRONAUT = "Astronaut"
    HEALTH_OFFICER = "Crew Health Officer"
    SYSTEMS_ENGINEER = "Systems Engineer"
    GROUND_SUPPORT = "Ground Support"


# Signal-to-consent-scope mapping
SIGNAL_TO_SCOPE: Dict[str, str] = {
    SignalType.HEART_RATE.value: ConsentScope.PHYSIO.value,
    SignalType.RESTING_HR.value: ConsentScope.PHYSIO.value,
    SignalType.HRV_RMSSD.value: ConsentScope.PHYSIO.value,
    SignalType.HR_RECOVERY_1M.value: ConsentScope.PHYSIO.value,
    SignalType.SPO2.value: ConsentScope.PHYSIO.value,
    SignalType.SLEEP_DURATION.value: ConsentScope.PHYSIO.value,
    SignalType.SLEEP_FRAGMENTATION.value: ConsentScope.COGNITIVE.value,
    SignalType.PVT_MEAN_RT.value: ConsentScope.COGNITIVE.value,
    SignalType.PVT_LAPSES.value: ConsentScope.COGNITIVE.value,
    SignalType.SYMPTOM_HEADACHE.value: ConsentScope.PHYSIO.value,
    SignalType.SYMPTOM_FATIGUE.value: ConsentScope.PHYSIO.value,
    SignalType.MOOD_SCORE.value: ConsentScope.BEHAVIOUR.value,
    SignalType.ENERGY_SCORE.value: ConsentScope.BEHAVIOUR.value,
    SignalType.STRESS_SCORE.value: ConsentScope.BEHAVIOUR.value,
    SignalType.ACTIVITY_INDEX.value: ConsentScope.BEHAVIOUR.value,
    SignalType.CO2_PPM.value: ConsentScope.HABITAT.value,
    SignalType.CABIN_TEMP_C.value: ConsentScope.HABITAT.value,
    SignalType.CABIN_HUMIDITY_PCT.value: ConsentScope.HABITAT.value,
    SignalType.CABIN_NOISE_DB.value: ConsentScope.HABITAT.value,
    SignalType.RADIATION_USV_DAY.value: ConsentScope.HABITAT.value,
    SignalType.RADIATION_CUMULATIVE_MSV.value: ConsentScope.PHYSIO.value,
}

# Illustrative hardware / plausibility bounds (configurable; NOT clinical norms)
SAMPLE_PLAUSIBLE_RANGES: Dict[str, tuple[float, float]] = {
    SignalType.HEART_RATE.value: (30.0, 220.0),
    SignalType.RESTING_HR.value: (32.0, 160.0),
    SignalType.HRV_RMSSD.value: (5.0, 180.0),
    SignalType.HR_RECOVERY_1M.value: (2.0, 80.0),
    SignalType.SPO2.value: (60.0, 100.0),
    SignalType.SLEEP_DURATION.value: (0.0, 16.0),
    SignalType.SLEEP_FRAGMENTATION.value: (0.0, 100.0),
    SignalType.PVT_MEAN_RT.value: (120.0, 1500.0),
    SignalType.PVT_LAPSES.value: (0.0, 50.0),
    SignalType.SYMPTOM_HEADACHE.value: (0.0, 3.0),
    SignalType.SYMPTOM_FATIGUE.value: (0.0, 5.0),
    SignalType.MOOD_SCORE.value: (1.0, 5.0),
    SignalType.ENERGY_SCORE.value: (1.0, 5.0),
    SignalType.STRESS_SCORE.value: (1.0, 5.0),
    SignalType.ACTIVITY_INDEX.value: (0.0, 3.0),
    SignalType.CO2_PPM.value: (200.0, 15000.0),
    SignalType.CABIN_TEMP_C.value: (10.0, 40.0),
    SignalType.CABIN_HUMIDITY_PCT.value: (10.0, 95.0),
    SignalType.CABIN_NOISE_DB.value: (25.0, 110.0),
    SignalType.RADIATION_USV_DAY.value: (0.0, 10000.0),
    SignalType.RADIATION_CUMULATIVE_MSV.value: (0.0, 2000.0),
}

SIGNAL_UNITS: Dict[str, str] = {
    SignalType.HEART_RATE.value: "bpm",
    SignalType.RESTING_HR.value: "bpm",
    SignalType.HRV_RMSSD.value: "ms",
    SignalType.HR_RECOVERY_1M.value: "bpm",
    SignalType.SPO2.value: "%",
    SignalType.SLEEP_DURATION.value: "h",
    SignalType.SLEEP_FRAGMENTATION.value: "pts",
    SignalType.PVT_MEAN_RT.value: "ms",
    SignalType.PVT_LAPSES.value: "count",
    SignalType.SYMPTOM_HEADACHE.value: "0-3",
    SignalType.SYMPTOM_FATIGUE.value: "0-5",
    SignalType.MOOD_SCORE.value: "1-5",
    SignalType.ENERGY_SCORE.value: "1-5",
    SignalType.STRESS_SCORE.value: "1-5",
    SignalType.ACTIVITY_INDEX.value: "idx",
    SignalType.CO2_PPM.value: "ppm",
    SignalType.CABIN_TEMP_C.value: "C",
    SignalType.CABIN_HUMIDITY_PCT.value: "%",
    SignalType.CABIN_NOISE_DB.value: "dBA",
    SignalType.RADIATION_USV_DAY.value: "uSv/day",
    SignalType.RADIATION_CUMULATIVE_MSV.value: "mSv",
}


@dataclass
class CrewMember:
    astronaut_id: str
    name: str
    short_name: str
    initials: str
    title: str
    age: int
    default_zone: str
    anonymous_label: str


CREW_ROSTER: List[CrewMember] = [
    CrewMember(
        astronaut_id="ast-01",
        name="Cmdr. Elena Vasquez",
        short_name="Elena",
        initials="EV",
        title="Mission Commander",
        age=42,
        default_zone="LAB",
        anonymous_label="Crew A",
    ),
    CrewMember(
        astronaut_id="ast-02",
        name="Dr. Marcus Chen",
        short_name="Marcus",
        initials="MC",
        title="Flight Engineer / Scientist",
        age=38,
        default_zone="CQ",
        anonymous_label="Crew B",
    ),
    CrewMember(
        astronaut_id="ast-03",
        name="Yuki Tanaka",
        short_name="Yuki",
        initials="YT",
        title="Pilot",
        age=35,
        default_zone="LAB",
        anonymous_label="Crew C",
    ),
    CrewMember(
        astronaut_id="ast-04",
        name="Omar Haddad",
        short_name="Omar",
        initials="OH",
        title="Mission Specialist",
        age=36,
        default_zone="LAB",
        anonymous_label="Crew D",
    ),
]

CREW_BY_ID: Dict[str, CrewMember] = {c.astronaut_id: c for c in CREW_ROSTER}


@dataclass(frozen=True)
class HabitatZone:
    zone_id: str
    name: str
    short_code: str
    nominal_co2_ppm: float


HABITAT_ZONES: List[HabitatZone] = [
    HabitatZone(zone_id="N1", name="Node 1", short_code="N1", nominal_co2_ppm=830.0),
    HabitatZone(zone_id="LAB", name="US Lab", short_code="LAB", nominal_co2_ppm=880.0),
    HabitatZone(zone_id="CQ", name="Crew Quarters", short_code="CQ", nominal_co2_ppm=780.0),
    HabitatZone(zone_id="AL", name="Airlock", short_code="AL", nominal_co2_ppm=620.0),
]

ZONE_BY_ID: Dict[str, HabitatZone] = {z.zone_id: z for z in HABITAT_ZONES}


@dataclass
class MeasurementRecord:
    """Common schema record matching FEATURES.md §5.3."""

    astronaut_id: str
    timestamp_utc: str
    mission_elapsed_time: float
    day: int
    hour: int
    signal_type: str
    value: Optional[float]
    unit: str
    source_device: str
    firmware_version: str
    quality: str = QualityState.OK.value
    confidence: float = 1.0
    context_tags: List[str] = field(default_factory=list)
    consent_scope: str = ConsentScope.PHYSIO.value
    zone_id: str = "LAB"
    record_id: str = ""

    def __post_init__(self) -> None:
        if self.quality not in {q.value for q in QualityState}:
            raise ValueError(f"Invalid quality state: {self.quality}")
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence}")
        if not self.record_id:
            self.record_id = (
                f"{self.astronaut_id}:{self.signal_type}:d{self.day:02d}h{self.hour:02d}:{self.zone_id}"
            )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "MeasurementRecord":
        return cls(
            astronaut_id=str(raw["astronaut_id"]),
            timestamp_utc=str(raw["timestamp_utc"]),
            mission_elapsed_time=float(raw["mission_elapsed_time"]),
            day=int(raw["day"]),
            hour=int(raw["hour"]),
            signal_type=str(raw["signal_type"]),
            value=None if raw.get("value") is None else float(raw["value"]),
            unit=str(raw["unit"]),
            source_device=str(raw["source_device"]),
            firmware_version=str(raw["firmware_version"]),
            quality=str(raw.get("quality", QualityState.OK.value)),
            confidence=float(raw.get("confidence", 1.0)),
            context_tags=list(raw.get("context_tags", [])),
            consent_scope=str(raw.get("consent_scope", ConsentScope.PHYSIO.value)),
            zone_id=str(raw.get("zone_id", "LAB")),
            record_id=str(raw.get("record_id", "")),
        )


@dataclass
class AnomalyFlag:
    """Unified detector output contract matching docs/validation-plan.md §3."""

    signal: str
    window: List[str]
    anomaly_type: str  # data_fault | contextual | drift | multivariate
    score: float
    confidence: float
    baseline_context: str
    personal_range: List[float]
    observed: Optional[float]
    contributors: List[str]
    data_quality: Dict[str, Any]
    evidence_ref: str
    protocol_refs: List[str] = field(default_factory=list)
    astronaut_id: str = ""
    day: int = 23
    title: str = ""
    explanation: str = ""

    def __post_init__(self) -> None:
        valid_types = {"data_fault", "contextual", "drift", "multivariate"}
        if self.anomaly_type not in valid_types:
            raise ValueError(f"Invalid anomaly_type: {self.anomaly_type}")
        if not (0.0 <= float(self.confidence) <= 1.0):
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence}")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
