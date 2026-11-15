"""Curated offline protocol library for AstroGuard (FEATURES.md §7.1 & F-21).

Owned by ML-2. Protocols provide safe, non-diagnostic decision-support guidance
with explicit stop-and-escalate criteria. All numeric references are illustrative.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Protocol:
    protocol_id: str
    title: str
    category: str
    summary: str
    steps: List[str]
    escalate_if: str
    note: str = "Illustrative flight wellness checklist — decision support, not diagnosis."

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


PROTOCOL_LIBRARY: Dict[str, Protocol] = {
    "PROT-REC-01": Protocol(
        protocol_id="PROT-REC-01",
        title="24-Hour Post-Exertion Recovery Block",
        category="recovery",
        summary="Reduce strenuous exercise load for 24 hours when post-exercise HR recovery lags personal baseline.",
        steps=[
            "Swap high-intensity resistance or VO2 work for light mobility and hydration.",
            "Log subjective energy and breathlessness in the 60-second check-in.",
            "Keep wristband snug overnight to ensure clean resting HR and HRV windows.",
        ],
        escalate_if="Resting HR stays elevated >15 bpm above personal baseline, or chest tightness/dyspnea persists — trigger Crew Health Officer check or SOS.",
    ),
    "PROT-REC-02": Protocol(
        protocol_id="PROT-REC-02",
        title="Repeat 1-Minute Heart-Rate Recovery Check",
        category="recovery",
        summary="Verify whether reduced post-exercise HR drop reflects sustained strain or a transient measurement artifact.",
        steps=[
            "Confirm wearable strap contact and clean signal before starting light warm-up.",
            "Record seated/quiet heart rate exactly 60 seconds after stopping exertion.",
            "Compare against your early-mission personal reference rather than Earth tables.",
        ],
        escalate_if="1-minute recovery drop stays >10 bpm below personal baseline on two consecutive sessions or dizziness occurs.",
    ),
    "PROT-SLP-01": Protocol(
        protocol_id="PROT-SLP-01",
        title="Protected 7.5-Hour Circadian Sleep Window",
        category="sleep_cognitive",
        summary="Protect an uninterrupted sleep block to reduce cognitive lapses and stabilize HRV.",
        steps=[
            "Dim cabin task lighting 45 minutes before scheduled sleep onset.",
            "Verify Crew Quarters acoustic and ventilation settings before sleep.",
            "Avoid non-essential operational alerts during the protected 7.5-hour window.",
        ],
        escalate_if="Sleep fragmentation remains elevated for 3+ consecutive nights or PVT lapses exceed 3.",
    ),
    "PROT-SLP-02": Protocol(
        protocol_id="PROT-SLP-02",
        title="Standardized Ship-Clock PVT Re-Test",
        category="sleep_cognitive",
        summary="Confirm cognitive readiness trend at the same ship-clock time to remove circadian bias.",
        steps=[
            "Run the 1-minute PVT reaction test in quiet Crew Quarters lighting.",
            "Check data-quality badge afterward to confirm no distraction or gap.",
            "Defer precision robotics or EVA tasks if reaction time remains slowed with lapses.",
        ],
        escalate_if="PVT mean reaction time stays >60 ms above personal baseline with lapses >= 3.",
    ),
    "PROT-ENV-01": Protocol(
        protocol_id="PROT-ENV-01",
        title="US Lab CO2 Scrubber & Ventilation Boost",
        category="environment",
        summary="Increase cabin airflow and inspect CO2 scrubber beds when zone CO2 correlates with crew symptoms.",
        steps=[
            "Increase US Lab ventilation flow to 130% nominal and check scrubber differential pressure.",
            "Inspect portable CO2 sensor calibration against fixed cabin sensors.",
            "Verify no packet loss on zone air-quality telemetry.",
        ],
        escalate_if="Zone CO2 reaches >= 5,000 ppm (hard rule SR-03) or symptoms fail to improve after scrubber service.",
    ),
    "PROT-ENV-02": Protocol(
        protocol_id="PROT-ENV-02",
        title="Zone Rotation & Portable Air Quality Check",
        category="environment",
        summary="Temporarily redistribute non-essential tasks out of an elevated-CO2 zone while air is verified.",
        steps=[
            "Move extended desk or cognitive tasks from US Lab to Node 1 or Crew Quarters.",
            "Carry a portable CO2 monitor during transitional work blocks.",
            "Re-evaluate headache and fatigue scores 4 hours after changing zones.",
        ],
        escalate_if="Symptoms worsen outside US Lab — treat as possible individual illness and consult Crew Health Officer.",
    ),
    "PROT-MED-01": Protocol(
        protocol_id="PROT-MED-01",
        title="Peer Health Officer Cardiopulmonary Check",
        category="medical_support",
        summary="Structured non-physician peer check following an active medical alert or SOS.",
        steps=[
            "Seat the crew member calmly and verify SpO2, resting pulse, and respiratory effort.",
            "Review emergency-scoped vitals timeline and note symptom onset.",
            "Prepare Earth medical summary packet in priority queue if symptoms persist.",
        ],
        escalate_if="SpO2 < 90%, persistent chest pain, or worsening dyspnea — maintain SOS active and initiate Earth consult.",
    ),
    "PROT-RAD-01": Protocol(
        protocol_id="PROT-RAD-01",
        title="Cumulative Dosimetry & Shielded Zone Review",
        category="radiation",
        summary="Track long-term cumulative habitat radiation exposure and verify sleep-bay shielding.",
        steps=[
            "Confirm personal and habitat dosimeter logs show no sensor dropout.",
            "Keep sleep schedule anchored in higher-shielding Crew Quarters.",
            "Include cumulative dose curve in periodic Ground Support summary.",
        ],
        escalate_if="Solar particle dose-rate spike exceeds operational threshold — follow storm shelter procedure.",
    ),
}


def get_protocols(protocol_ids: List[str]) -> List[Dict[str, object]]:
    return [PROTOCOL_LIBRARY[pid].to_dict() for pid in protocol_ids if pid in PROTOCOL_LIBRARY]
