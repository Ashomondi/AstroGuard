"""Personal Baseline Engine and anomaly detectors for AstroGuard (F-05, F-10).

Implements context-aware robust location/scale (median + MAD) with hierarchical
population-prior shrinkage on early cold-start days, guarded slow updates that
freeze during drift, firmware/device step-offset compensation, two-sided tabular
CUSUM drift detection, and shrinkage Mahalanobis multivariate detection.

Missing, sensor_off, suspect, and out_of_range records are never treated as
normal physiology; data faults are routed explicitly to `anomaly_type="data_fault"`.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.schema import AnomalyFlag, MeasurementRecord, QualityState, SignalType

CONTEXTS: Tuple[str, ...] = ("rest", "sleep", "exercise", "high_workload")

# Signal -> default context when context_tags does not specify one
DEFAULT_SIGNAL_CONTEXT: Dict[str, str] = {
    SignalType.HEART_RATE.value: "rest",
    SignalType.RESTING_HR.value: "rest",
    SignalType.HRV_RMSSD.value: "sleep",
    SignalType.HR_RECOVERY_1M.value: "exercise",
    SignalType.SPO2.value: "rest",
    SignalType.SLEEP_DURATION.value: "sleep",
    SignalType.SLEEP_FRAGMENTATION.value: "sleep",
    SignalType.PVT_MEAN_RT.value: "rest",
    SignalType.PVT_LAPSES.value: "rest",
    SignalType.SYMPTOM_HEADACHE.value: "rest",
    SignalType.SYMPTOM_FATIGUE.value: "rest",
    SignalType.MOOD_SCORE.value: "rest",
    SignalType.ENERGY_SCORE.value: "rest",
    SignalType.STRESS_SCORE.value: "rest",
    SignalType.ACTIVITY_INDEX.value: "rest",
    SignalType.CO2_PPM.value: "rest",
    SignalType.CABIN_TEMP_C.value: "rest",
    SignalType.CABIN_HUMIDITY_PCT.value: "rest",
    SignalType.CABIN_NOISE_DB.value: "rest",
    SignalType.RADIATION_USV_DAY.value: "rest",
    SignalType.RADIATION_CUMULATIVE_MSV.value: "rest",
}

# (prior_mean, prior_between_sigma, prior_within_sigma)
# Illustrative sample priors; not clinical thresholds.
POPULATION_PRIORS: Dict[Tuple[str, str], Tuple[float, float, float]] = {
    (SignalType.HEART_RATE.value, "rest"): (64.0, 8.0, 4.5),
    (SignalType.HEART_RATE.value, "sleep"): (57.0, 7.0, 3.8),
    (SignalType.HEART_RATE.value, "exercise"): (138.0, 14.0, 9.0),
    (SignalType.HEART_RATE.value, "high_workload"): (80.0, 10.0, 6.0),
    (SignalType.RESTING_HR.value, "rest"): (58.0, 7.0, 2.2),
    (SignalType.RESTING_HR.value, "sleep"): (56.0, 7.0, 2.0),
    (SignalType.HRV_RMSSD.value, "sleep"): (58.0, 14.0, 5.5),
    (SignalType.HRV_RMSSD.value, "rest"): (55.0, 14.0, 5.8),
    (SignalType.HR_RECOVERY_1M.value, "exercise"): (33.0, 7.0, 3.2),
    (SignalType.HR_RECOVERY_1M.value, "rest"): (33.0, 7.0, 3.2),
    (SignalType.SPO2.value, "rest"): (98.0, 1.0, 0.8),
    (SignalType.SPO2.value, "sleep"): (97.5, 1.0, 0.8),
    (SignalType.SLEEP_DURATION.value, "sleep"): (7.1, 0.7, 0.55),
    (SignalType.SLEEP_FRAGMENTATION.value, "sleep"): (12.0, 6.0, 4.2),
    (SignalType.PVT_MEAN_RT.value, "rest"): (252.0, 24.0, 14.0),
    (SignalType.PVT_MEAN_RT.value, "high_workload"): (262.0, 26.0, 16.0),
    (SignalType.PVT_LAPSES.value, "rest"): (0.4, 0.8, 0.7),
    (SignalType.PVT_LAPSES.value, "high_workload"): (0.6, 0.9, 0.8),
    (SignalType.SYMPTOM_HEADACHE.value, "rest"): (0.1, 0.3, 0.3),
    (SignalType.SYMPTOM_FATIGUE.value, "rest"): (0.8, 0.6, 0.5),
    (SignalType.MOOD_SCORE.value, "rest"): (4.0, 0.6, 0.45),
    (SignalType.ENERGY_SCORE.value, "rest"): (3.8, 0.6, 0.45),
    (SignalType.STRESS_SCORE.value, "rest"): (2.0, 0.7, 0.5),
    (SignalType.ACTIVITY_INDEX.value, "rest"): (1.0, 0.25, 0.14),
    (SignalType.CO2_PPM.value, "rest"): (820.0, 140.0, 90.0),
    (SignalType.CABIN_TEMP_C.value, "rest"): (22.0, 1.0, 0.7),
    (SignalType.CABIN_HUMIDITY_PCT.value, "rest"): (45.0, 5.0, 3.5),
    (SignalType.CABIN_NOISE_DB.value, "rest"): (56.0, 4.0, 3.0),
    (SignalType.RADIATION_USV_DAY.value, "rest"): (500.0, 55.0, 35.0),
    (SignalType.RADIATION_CUMULATIVE_MSV.value, "rest"): (5.0, 3.0, 1.0),
}

SIGNAL_PROTOCOLS: Dict[str, List[str]] = {
    SignalType.HEART_RATE.value: ["PROT-REC-01", "PROT-REC-02"],
    SignalType.RESTING_HR.value: ["PROT-REC-01", "PROT-REC-02"],
    SignalType.HRV_RMSSD.value: ["PROT-REC-01", "PROT-SLP-01"],
    SignalType.HR_RECOVERY_1M.value: ["PROT-REC-01", "PROT-REC-02"],
    SignalType.SPO2.value: ["PROT-MED-01"],
    SignalType.SLEEP_DURATION.value: ["PROT-SLP-01"],
    SignalType.SLEEP_FRAGMENTATION.value: ["PROT-SLP-01", "PROT-SLP-02"],
    SignalType.PVT_MEAN_RT.value: ["PROT-SLP-02", "PROT-SLP-01"],
    SignalType.PVT_LAPSES.value: ["PROT-SLP-02", "PROT-SLP-01"],
    SignalType.CO2_PPM.value: ["PROT-ENV-01", "PROT-ENV-02"],
    SignalType.RADIATION_USV_DAY.value: ["PROT-RAD-01"],
    SignalType.RADIATION_CUMULATIVE_MSV.value: ["PROT-RAD-01"],
}

DEFAULT_MULTIVARIATE_SIGNALS: Tuple[str, ...] = (
    SignalType.RESTING_HR.value,
    SignalType.HRV_RMSSD.value,
    SignalType.HR_RECOVERY_1M.value,
    SignalType.SLEEP_DURATION.value,
    SignalType.SLEEP_FRAGMENTATION.value,
    SignalType.PVT_MEAN_RT.value,
)

# Approximate chi-square 99% critical thresholds for df = 1..10
_CHI2_99: Dict[int, float] = {
    1: 6.63,
    2: 9.21,
    3: 11.34,
    4: 13.28,
    5: 15.09,
    6: 16.81,
    7: 18.48,
    8: 20.09,
    9: 21.67,
    10: 23.21,
}


def clamp(value: float, low: float, high: float) -> float:
    """Bound a floating-point value to [low, high]."""
    return max(low, min(high, value))


def coerce_records(
    records: Iterable[MeasurementRecord | Dict[str, Any]],
    astronaut_id: Optional[str] = None,
    up_to_day: Optional[int] = None,
) -> List[MeasurementRecord]:
    """Convert raw dicts or MeasurementRecords into chronologically sorted records."""
    parsed: List[MeasurementRecord] = []
    for item in records:
        rec = item if isinstance(item, MeasurementRecord) else MeasurementRecord.from_dict(item)
        if astronaut_id is not None and rec.astronaut_id != astronaut_id:
            continue
        if up_to_day is not None and rec.day > up_to_day:
            continue
        parsed.append(rec)
    parsed.sort(key=lambda r: (r.day, r.hour, r.mission_elapsed_time, r.timestamp_utc))
    return parsed


def is_clean_record(rec: MeasurementRecord) -> bool:
    """Return True only when quality is explicitly 'ok' and value is finite."""
    return (
        rec.quality == QualityState.OK.value
        and rec.value is not None
        and math.isfinite(float(rec.value))
    )


def infer_context(rec: MeasurementRecord) -> str:
    """Resolve a measurement's operational context from tags and signal defaults."""
    tags = {str(t).lower() for t in (rec.context_tags or [])}
    if "exercise" in tags or "post_exercise" in tags or "exertion" in tags:
        return "exercise"
    if "sleep" in tags or "overnight" in tags:
        return "sleep"
    if "high_workload" in tags or "eva" in tags or "workload" in tags:
        return "high_workload"
    if "rest" in tags or "quiet" in tags or "baseline" in tags:
        return "rest"
    return DEFAULT_SIGNAL_CONTEXT.get(rec.signal_type, "rest")


def robust_median_mad(
    values: Sequence[float],
    min_scale: float = 1e-3,
) -> Tuple[float, float]:
    """Compute sample median and 1.4826 * MAD scale estimate."""
    if not values:
        raise ValueError("Cannot compute median/MAD of empty sequence")
    med = float(statistics.median(values))
    deviations = [abs(float(v) - med) for v in values]
    mad = 1.4826 * float(statistics.median(deviations))
    return med, max(mad, min_scale)


def get_population_prior(signal_type: str, context: str) -> Tuple[float, float, float]:
    """Return (prior_mean, prior_between_sigma, prior_within_sigma) for signal+context."""
    if (signal_type, context) in POPULATION_PRIORS:
        return POPULATION_PRIORS[(signal_type, context)]
    default_ctx = DEFAULT_SIGNAL_CONTEXT.get(signal_type, "rest")
    if (signal_type, default_ctx) in POPULATION_PRIORS:
        return POPULATION_PRIORS[(signal_type, default_ctx)]
    for (sig, _), prior in POPULATION_PRIORS.items():
        if sig == signal_type:
            return prior
    return (0.0, 1.0, 1.0)


def _invert_matrix(matrix: List[List[float]]) -> List[List[float]]:
    """Invert a small symmetric positive-definite matrix using Gauss-Jordan elimination."""
    n = len(matrix)
    aug = [
        [float(matrix[i][j]) for j in range(n)] + [1.0 if i == j else 0.0 for j in range(n)]
        for i in range(n)
    ]
    for col in range(n):
        pivot_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot_row][col]) < 1e-12:
            raise ValueError("Singular matrix encountered during covariance inversion")
        if pivot_row != col:
            aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        pivot = aug[col][col]
        for j in range(2 * n):
            aug[col][j] /= pivot
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            if factor != 0.0:
                for j in range(2 * n):
                    aug[row][j] -= factor * aug[col][j]
    return [row[n:] for row in aug]


@dataclass
class BaselineState:
    """Context-specific personal baseline state for one astronaut & signal."""

    astronaut_id: str
    signal_type: str
    context: str
    center: float
    scale: float
    sample_median: Optional[float]
    sample_mad: Optional[float]
    n_samples: int
    n_days: int
    cold_start: bool
    frozen: bool
    freeze_reason: str
    personal_range: List[float]
    baseline_days_used: int
    slow_updates_applied: int = 0
    step_offsets: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "astronaut_id": self.astronaut_id,
            "signal_type": self.signal_type,
            "context": self.context,
            "center": round(self.center, 3),
            "scale": round(self.scale, 3),
            "sample_median": None if self.sample_median is None else round(self.sample_median, 3),
            "sample_mad": None if self.sample_mad is None else round(self.sample_mad, 3),
            "n_samples": self.n_samples,
            "n_days": self.n_days,
            "cold_start": self.cold_start,
            "frozen": self.frozen,
            "freeze_reason": self.freeze_reason,
            "personal_range": [round(self.personal_range[0], 2), round(self.personal_range[1], 2)],
            "baseline_days_used": self.baseline_days_used,
            "slow_updates_applied": self.slow_updates_applied,
            "step_offsets": list(self.step_offsets),
        }


class PersonalBaselineEngine:
    """Context-aware personal baseline, guarded update, and multi-detector engine."""

    def __init__(
        self,
        baseline_days: int = 10,
        prior_strength: float = 4.0,
        min_personal_samples: int = 5,
        slow_alpha: float = 0.04,
        freeze_z_threshold: float = 1.75,
        cusum_k: float = 0.5,
        cusum_h: float = 3.8,
        contextual_z_threshold: float = 3.0,
    ) -> None:
        self.baseline_days = baseline_days
        self.prior_strength = prior_strength
        self.min_personal_samples = min_personal_samples
        self.slow_alpha = slow_alpha
        self.freeze_z_threshold = freeze_z_threshold
        self.cusum_k = cusum_k
        self.cusum_h = cusum_h
        self.contextual_z_threshold = contextual_z_threshold
        self._baselines: Dict[Tuple[str, str, str], BaselineState] = {}
        self._step_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def detect_device_step(
        self,
        records: Iterable[MeasurementRecord | Dict[str, Any]],
        astronaut_id: str,
        signal_type: str,
    ) -> Dict[str, Any]:
        """Detect calibration step offsets across device or firmware transitions."""
        clean = [
            r
            for r in coerce_records(records, astronaut_id=astronaut_id)
            if r.signal_type == signal_type and is_clean_record(r)
        ]
        if len(clean) < 4:
            result = {
                "detected": False,
                "astronaut_id": astronaut_id,
                "signal_type": signal_type,
                "steps": [],
                "total_offset": 0.0,
                "reason": "Fewer than 4 clean records; no transition evaluated.",
            }
            self._step_cache[(astronaut_id, signal_type)] = result
            return result

        # Segment contiguous (source_device, firmware_version) spans
        segments: List[Dict[str, Any]] = []
        for rec in clean:
            key = (rec.source_device, rec.firmware_version)
            if not segments or segments[-1]["key"] != key:
                segments.append({"key": key, "records": [rec]})
            else:
                segments[-1]["records"].append(rec)

        if len(segments) < 2:
            result = {
                "detected": False,
                "astronaut_id": astronaut_id,
                "signal_type": signal_type,
                "steps": [],
                "total_offset": 0.0,
                "reason": "Single source device and firmware version across window.",
            }
            self._step_cache[(astronaut_id, signal_type)] = result
            return result

        _, _, prior_within = get_population_prior(signal_type, DEFAULT_SIGNAL_CONTEXT.get(signal_type, "rest"))
        steps: List[Dict[str, Any]] = []
        cumulative_offset = 0.0

        for idx in range(1, len(segments)):
            prev_recs: List[MeasurementRecord] = segments[idx - 1]["records"]
            curr_recs: List[MeasurementRecord] = segments[idx]["records"]
            transition_day = curr_recs[0].day

            # Compare up to 5 days before transition with immediate 4-day post-transition window
            pre_window = [r for r in prev_recs if r.day >= transition_day - 5] or prev_recs
            post_window = [r for r in curr_recs if r.day <= transition_day + 3] or curr_recs

            context_offsets: Dict[str, float] = {}
            context_weights: Dict[str, int] = {}
            for ctx in CONTEXTS:
                pre_vals = [float(r.value) for r in pre_window if infer_context(r) == ctx and r.value is not None]
                post_vals = [float(r.value) for r in post_window if infer_context(r) == ctx and r.value is not None]
                if len(pre_vals) >= 2 and len(post_vals) >= 2:
                    context_offsets[ctx] = float(statistics.median(post_vals)) - float(statistics.median(pre_vals))
                    context_weights[ctx] = min(len(pre_vals), len(post_vals))

            if context_offsets:
                total_w = sum(context_weights.values())
                step_offset = sum(context_offsets[c] * context_weights[c] for c in context_offsets) / total_w
                pre_all = [float(r.value) for r in pre_window if infer_context(r) in context_offsets and r.value is not None]
                post_all = [float(r.value) for r in post_window if infer_context(r) in context_offsets and r.value is not None]
            else:
                pre_all = [float(r.value) for r in pre_window if r.value is not None]
                post_all = [float(r.value) for r in post_window if r.value is not None]
                if len(pre_all) < 2 or len(post_all) < 2:
                    continue
                step_offset = float(statistics.median(post_all)) - float(statistics.median(pre_all))

            _, pre_mad = robust_median_mad(pre_all, min_scale=max(0.25 * prior_within, 0.25))
            _, post_mad = robust_median_mad(post_all, min_scale=max(0.25 * prior_within, 0.25))
            pooled_scale = max(pre_mad, post_mad, 0.5 * prior_within)

            # Confirm step-change abruptness at boundary vs slow physiological slope
            if abs(step_offset) >= max(0.9 * pooled_scale, 0.5 * prior_within):
                prev_key = segments[idx - 1]["key"]
                curr_key = segments[idx]["key"]
                cumulative_offset += step_offset
                conf = clamp(0.65 + 0.08 * (abs(step_offset) / pooled_scale), 0.0, 0.98)
                steps.append(
                    {
                        "from_device": prev_key[0],
                        "from_firmware": prev_key[1],
                        "to_device": curr_key[0],
                        "to_firmware": curr_key[1],
                        "transition_day": transition_day,
                        "transition_index": len(prev_recs),
                        "offset": round(step_offset, 3),
                        "cumulative_offset": round(cumulative_offset, 3),
                        "context_offsets": {k: round(v, 3) for k, v in context_offsets.items()},
                        "confidence": round(conf, 3),
                    }
                )

        result = {
            "detected": len(steps) > 0,
            "astronaut_id": astronaut_id,
            "signal_type": signal_type,
            "steps": steps,
            "total_offset": round(cumulative_offset, 3),
            "reason": (
                f"Detected {len(steps)} device/firmware step offset(s) aligned with hardware transition."
                if steps
                else "Device/firmware transition had negligible offset relative to baseline variance."
            ),
        }
        self._step_cache[(astronaut_id, signal_type)] = result
        return result

    def _step_adjusted_value(
        self,
        rec: MeasurementRecord,
        step_info: Dict[str, Any],
    ) -> float:
        """Subtract cumulative device/firmware step offset applicable to `rec`."""
        val = float(rec.value)  # caller guarantees clean record
        for step in step_info.get("steps", []):
            if (rec.day > step["transition_day"]) or (
                rec.day == step["transition_day"]
                and rec.source_device == step["to_device"]
                and rec.firmware_version == step["to_firmware"]
            ):
                val -= float(step["offset"])
        return val

    def fit_signal_context(
        self,
        records: Iterable[MeasurementRecord | Dict[str, Any]],
        astronaut_id: str,
        signal_type: str,
        context: str,
        up_to_day: Optional[int] = None,
    ) -> BaselineState:
        """Estimate and guardedly update a personal baseline for (astronaut, signal, context)."""
        parsed = coerce_records(records, astronaut_id=astronaut_id, up_to_day=up_to_day)
        step_info = self.detect_device_step(parsed, astronaut_id, signal_type)

        clean = [
            r
            for r in parsed
            if r.signal_type == signal_type and infer_context(r) == context and is_clean_record(r)
        ]

        prior_mean, prior_between, prior_within = get_population_prior(signal_type, context)
        if not clean:
            state = BaselineState(
                astronaut_id=astronaut_id,
                signal_type=signal_type,
                context=context,
                center=prior_mean,
                scale=prior_within,
                sample_median=None,
                sample_mad=None,
                n_samples=0,
                n_days=0,
                cold_start=True,
                frozen=False,
                freeze_reason="",
                personal_range=[prior_mean - 1.5 * prior_within, prior_mean + 1.5 * prior_within],
                baseline_days_used=0,
                step_offsets=list(step_info.get("steps", [])),
            )
            self._baselines[(astronaut_id, signal_type, context)] = state
            return state

        max_day = max(r.day for r in clean)
        effective_base_days = min(self.baseline_days, max(4, max_day)) if max_day > self.baseline_days else max_day
        init_recs = [r for r in clean if r.day <= effective_base_days]
        if not init_recs:
            init_recs = clean[: min(len(clean), self.min_personal_samples)]

        init_vals = [self._step_adjusted_value(r, step_info) for r in init_recs]
        n_init = len(init_vals)
        init_days = sorted({r.day for r in init_recs})
        sample_med, sample_mad = robust_median_mad(init_vals, min_scale=max(0.25 * prior_within, 0.1))

        # Hierarchical Bayesian shrinkage toward population prior during cold start
        w_loc = n_init / (n_init + self.prior_strength)
        # Weight scale toward within-person prior when few samples exist
        w_scale = n_init / (n_init + self.prior_strength)
        center = w_loc * sample_med + (1.0 - w_loc) * prior_mean
        scale = math.sqrt(w_scale * (sample_mad ** 2) + (1.0 - w_scale) * (prior_within ** 2))
        scale = max(scale, 0.25 * prior_within, 0.05)

        cold_start = n_init < self.min_personal_samples or len(init_days) < 4
        frozen = False
        freeze_reason = ""
        updates_applied = 0

        # Guarded slow update on days strictly after the baseline window
        if not cold_start and max_day > self.baseline_days:
            post_by_day: Dict[int, List[float]] = {}
            for r in clean:
                if r.day > self.baseline_days:
                    post_by_day.setdefault(r.day, []).append(self._step_adjusted_value(r, step_info))

            s_pos = 0.0
            s_neg = 0.0
            consecutive_deviant = 0
            for d in sorted(post_by_day):
                day_med = float(statistics.median(post_by_day[d]))
                z_d = (day_med - center) / scale
                s_pos = max(0.0, s_pos + z_d - self.cusum_k)
                s_neg = max(0.0, s_neg - z_d - self.cusum_k)

                if abs(z_d) > self.freeze_z_threshold:
                    consecutive_deviant += 1
                else:
                    consecutive_deviant = 0

                if (
                    abs(z_d) > self.freeze_z_threshold
                    or max(s_pos, s_neg) >= self.cusum_h * 0.65
                    or consecutive_deviant >= 2
                ):
                    frozen = True
                    freeze_reason = (
                        f"Guarded update frozen at Day {d}: drift (|z|={abs(z_d):.2f}, "
                        f"CUSUM={max(s_pos, s_neg):.2f}) exceeded threshold."
                    )
                    continue

                if not frozen:
                    center = (1.0 - self.slow_alpha) * center + self.slow_alpha * day_med
                    day_dev = max(abs(day_med - center) * 1.4826, 0.3 * prior_within)
                    scale = (1.0 - self.slow_alpha * 0.5) * scale + (self.slow_alpha * 0.5) * day_dev
                    scale = max(scale, 0.25 * prior_within, 0.05)
                    updates_applied += 1

        # Keep personal range non-negative for inherently non-negative physiological signals
        low_bound = center - 1.5 * scale
        if signal_type not in {SignalType.CABIN_TEMP_C.value}:
            low_bound = max(0.0, low_bound)
        high_bound = center + 1.5 * scale

        all_days = sorted({r.day for r in clean})
        state = BaselineState(
            astronaut_id=astronaut_id,
            signal_type=signal_type,
            context=context,
            center=center,
            scale=scale,
            sample_median=sample_med,
            sample_mad=sample_mad,
            n_samples=len(clean),
            n_days=len(all_days),
            cold_start=cold_start,
            frozen=frozen,
            freeze_reason=freeze_reason,
            personal_range=[low_bound, high_bound],
            baseline_days_used=len(init_days),
            slow_updates_applied=updates_applied,
            step_offsets=list(step_info.get("steps", [])),
        )
        self._baselines[(astronaut_id, signal_type, context)] = state
        return state

    def fit(
        self,
        records: Iterable[MeasurementRecord | Dict[str, Any]],
        astronaut_id: str,
        up_to_day: Optional[int] = None,
    ) -> Dict[Tuple[str, str], BaselineState]:
        """Fit baselines across all observed (signal_type, context) pairs for one astronaut."""
        parsed = coerce_records(records, astronaut_id=astronaut_id, up_to_day=up_to_day)
        pairs = sorted({(r.signal_type, infer_context(r)) for r in parsed if is_clean_record(r)})
        fitted: Dict[Tuple[str, str], BaselineState] = {}
        for sig, ctx in pairs:
            fitted[(sig, ctx)] = self.fit_signal_context(
                parsed, astronaut_id=astronaut_id, signal_type=sig, context=ctx, up_to_day=up_to_day
            )
        return fitted

    def get_baseline(
        self,
        astronaut_id: str,
        signal_type: str,
        context: Optional[str] = None,
    ) -> Optional[BaselineState]:
        """Retrieve a previously fitted baseline state."""
        ctx = context or DEFAULT_SIGNAL_CONTEXT.get(signal_type, "rest")
        return self._baselines.get((astronaut_id, signal_type, ctx))

    def detect_cusum_drift(
        self,
        records: Iterable[MeasurementRecord | Dict[str, Any]],
        astronaut_id: str,
        signal_type: str,
        context: Optional[str] = None,
        up_to_day: Optional[int] = None,
        k_sigma: Optional[float] = None,
        h_sigma: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run two-sided tabular CUSUM drift detection on step-adjusted clean daily medians."""
        ctx = context or DEFAULT_SIGNAL_CONTEXT.get(signal_type, "rest")
        k = self.cusum_k if k_sigma is None else float(k_sigma)
        h = self.cusum_h if h_sigma is None else float(h_sigma)

        parsed = coerce_records(records, astronaut_id=astronaut_id, up_to_day=up_to_day)
        baseline = self.fit_signal_context(
            parsed, astronaut_id=astronaut_id, signal_type=signal_type, context=ctx, up_to_day=up_to_day
        )
        step_info = self._step_cache.get((astronaut_id, signal_type), {"steps": []})

        clean = [
            r
            for r in parsed
            if r.signal_type == signal_type and infer_context(r) == ctx and is_clean_record(r)
        ]
        by_day: Dict[int, List[float]] = {}
        for r in clean:
            by_day.setdefault(r.day, []).append(self._step_adjusted_value(r, step_info))

        if len(by_day) < 4:
            return {
                "detected": False,
                "astronaut_id": astronaut_id,
                "signal_type": signal_type,
                "context": ctx,
                "direction": "none",
                "cusum_pos": 0.0,
                "cusum_neg": 0.0,
                "max_cusum": 0.0,
                "threshold": h,
                "onset_day": None,
                "latest_day": max(by_day) if by_day else None,
                "latest_value": None,
                "baseline_center": round(baseline.center, 3),
                "baseline_scale": round(baseline.scale, 3),
                "personal_range": [round(x, 2) for x in baseline.personal_range],
                "z_score": 0.0,
                "confidence": 0.0,
                "reason": "Insufficient clean daily observations for CUSUM drift detection.",
            }

        s_pos = 0.0
        s_neg = 0.0
        pos_start: Optional[int] = None
        neg_start: Optional[int] = None
        max_pos = 0.0
        max_neg = 0.0
        latest_day = 0
        latest_val = 0.0
        latest_z = 0.0

        # Evaluate CUSUM sequentially over post-baseline days (or all days if short series)
        sorted_days = sorted(by_day)
        start_eval_day = min(self.baseline_days, sorted_days[max(0, len(sorted_days) // 2 - 1)])
        for d in sorted_days:
            if d <= start_eval_day and len(sorted_days) > self.baseline_days:
                continue
            med = float(statistics.median(by_day[d]))
            z = (med - baseline.center) / baseline.scale
            # Huberize single-day z so a transient 1-day spike triggers contextual, not drift
            z_step = clamp(z, -2.5, 2.5)
            s_pos = max(0.0, s_pos + z_step - k)
            s_neg = max(0.0, s_neg - z_step - k)
            if s_pos > 0.0 and pos_start is None:
                pos_start = d
            elif s_pos == 0.0:
                pos_start = None
            if s_neg > 0.0 and neg_start is None:
                neg_start = d
            elif s_neg == 0.0:
                neg_start = None
            max_pos = max(max_pos, s_pos)
            max_neg = max(max_neg, s_neg)
            latest_day = d
            latest_val = med
            latest_z = z

        if s_pos >= s_neg:
            onset_cand = pos_start
            active_cusum = s_pos
            cand_dir = "up"
        else:
            onset_cand = neg_start
            active_cusum = s_neg
            cand_dir = "down"

        sustained_days = (latest_day - onset_cand) if onset_cand is not None else 0
        detected = active_cusum >= h and abs(latest_z) >= 0.8 and sustained_days >= 1
        direction = cand_dir if detected else "none"
        onset_day = onset_cand if detected else None

        conf = clamp(0.55 + 0.08 * min(active_cusum, 6.0), 0.0, 0.96) if detected else 0.2
        return {
            "detected": detected,
            "astronaut_id": astronaut_id,
            "signal_type": signal_type,
            "context": ctx,
            "direction": direction,
            "cusum_pos": round(s_pos, 3),
            "cusum_neg": round(s_neg, 3),
            "max_cusum": round(max(s_pos, s_neg), 3),
            "threshold": h,
            "onset_day": onset_day if detected else None,
            "latest_day": latest_day,
            "latest_value": round(latest_val, 3),
            "baseline_center": round(baseline.center, 3),
            "baseline_scale": round(baseline.scale, 3),
            "personal_range": [round(x, 2) for x in baseline.personal_range],
            "z_score": round(latest_z, 3),
            "confidence": round(conf, 3),
            "frozen_baseline": baseline.frozen,
            "window": [f"Day {onset_day or latest_day}", f"Day {latest_day}"],
        }

    def detect_multivariate_mahalanobis(
        self,
        records: Iterable[MeasurementRecord | Dict[str, Any]],
        astronaut_id: str,
        signal_types: Optional[Sequence[str]] = None,
        up_to_day: Optional[int] = None,
        shrinkage: float = 0.25,
    ) -> Dict[str, Any]:
        """Compute shrinkage Mahalanobis distance across clean daily physiological signals."""
        parsed = coerce_records(records, astronaut_id=astronaut_id, up_to_day=up_to_day)
        target_signals = list(signal_types or DEFAULT_MULTIVARIATE_SIGNALS)

        # Build step-adjusted daily clean medians per signal
        daily_by_sig: Dict[str, Dict[int, float]] = {}
        baselines: Dict[str, BaselineState] = {}
        for sig in target_signals:
            ctx = DEFAULT_SIGNAL_CONTEXT.get(sig, "rest")
            b_state = self.fit_signal_context(
                parsed, astronaut_id=astronaut_id, signal_type=sig, context=ctx, up_to_day=up_to_day
            )
            step_info = self._step_cache.get((astronaut_id, sig), {"steps": []})
            day_map: Dict[int, List[float]] = {}
            for r in parsed:
                if r.signal_type == sig and infer_context(r) == ctx and is_clean_record(r):
                    day_map.setdefault(r.day, []).append(self._step_adjusted_value(r, step_info))
            if day_map:
                daily_by_sig[sig] = {d: float(statistics.median(vals)) for d, vals in day_map.items()}
                baselines[sig] = b_state

        all_days = sorted({d for m in daily_by_sig.values() for d in m})
        if not all_days:
            return {
                "detected": False,
                "astronaut_id": astronaut_id,
                "signals_used": [],
                "mahalanobis_d2": 0.0,
                "mahalanobis_d": 0.0,
                "threshold_d2": 0.0,
                "contributors": [],
                "confidence": 0.0,
                "reason": "No clean daily signals available.",
            }

        latest_day = up_to_day if up_to_day in all_days else all_days[-1]
        active_sigs = [
            s for s in target_signals if s in daily_by_sig and latest_day in daily_by_sig[s]
        ]
        # Keep only signals with at least 4 baseline days
        base_cutoff = min(self.baseline_days, max(4, latest_day - 3))
        active_sigs = [
            s
            for s in active_sigs
            if sum(1 for d in daily_by_sig[s] if d <= base_cutoff) >= 4
        ]
        if len(active_sigs) < 2:
            return {
                "detected": False,
                "astronaut_id": astronaut_id,
                "signals_used": active_sigs,
                "mahalanobis_d2": 0.0,
                "mahalanobis_d": 0.0,
                "threshold_d2": 0.0,
                "contributors": [],
                "confidence": 0.0,
                "reason": "Fewer than 2 concurrently clean signals on evaluation day.",
            }

        # Collect joint clean baseline vectors (never impute missing dimensions)
        joint_base_days = [
            d for d in range(1, base_cutoff + 1) if all(d in daily_by_sig[s] for s in active_sigs)
        ]
        if len(joint_base_days) < 3:
            return {
                "detected": False,
                "astronaut_id": astronaut_id,
                "signals_used": active_sigs,
                "mahalanobis_d2": 0.0,
                "mahalanobis_d": 0.0,
                "threshold_d2": 0.0,
                "contributors": [],
                "confidence": 0.0,
                "reason": "Insufficient jointly clean baseline days for covariance estimation.",
            }

        p = len(active_sigs)
        z_rows: List[List[float]] = []
        for d in joint_base_days:
            row = [
                (daily_by_sig[s][d] - baselines[s].center) / baselines[s].scale
                for s in active_sigs
            ]
            z_rows.append(row)

        # Empirical covariance of standardized baseline vectors + shrinkage toward Identity
        n_b = len(z_rows)
        means = [sum(row[j] for row in z_rows) / n_b for j in range(p)]
        cov = [[0.0 for _ in range(p)] for _ in range(p)]
        denom = max(1, n_b - 1)
        for row in z_rows:
            for i in range(p):
                di = row[i] - means[i]
                for j in range(p):
                    cov[i][j] += di * (row[j] - means[j]) / denom

        lam = clamp(shrinkage, 0.05, 0.95)
        shrunk_cov = [
            [(1.0 - lam) * cov[i][j] + (lam if i == j else 0.0) for j in range(p)]
            for i in range(p)
        ]
        inv_cov = _invert_matrix(shrunk_cov)

        z_latest = [
            (daily_by_sig[s][latest_day] - baselines[s].center) / baselines[s].scale
            for s in active_sigs
        ]
        inv_times_z = [sum(inv_cov[i][j] * z_latest[j] for j in range(p)) for i in range(p)]
        d2 = max(0.0, sum(z_latest[i] * inv_times_z[i] for i in range(p)))
        dist = math.sqrt(d2)
        threshold_d2 = _CHI2_99.get(p, p + 2.5 * math.sqrt(2.0 * p))

        # Rank contributing signals by absolute directional contribution
        contrib_scores = [
            (abs(z_latest[i] * inv_times_z[i]), abs(z_latest[i]), active_sigs[i], z_latest[i])
            for i in range(p)
        ]
        contrib_scores.sort(reverse=True)
        contributors = [item[2] for item in contrib_scores if item[1] >= 0.75][:3]
        if not contributors:
            contributors = [item[2] for item in contrib_scores[:2]]

        detected = d2 >= threshold_d2
        conf = clamp(0.60 + 0.04 * (d2 - threshold_d2), 0.0, 0.95) if detected else 0.25
        return {
            "detected": detected,
            "astronaut_id": astronaut_id,
            "day": latest_day,
            "signals_used": active_sigs,
            "mahalanobis_d2": round(d2, 3),
            "mahalanobis_d": round(dist, 3),
            "threshold_d2": round(threshold_d2, 3),
            "contributors": contributors,
            "z_scores": {active_sigs[i]: round(z_latest[i], 3) for i in range(p)},
            "confidence": round(conf, 3),
            "window": [f"Day {max(1, latest_day - 2)}", f"Day {latest_day}"],
        }

    def _signal_quality_stats(
        self,
        recs: Sequence[MeasurementRecord],
        window_start_day: int,
        up_to_day: int,
    ) -> Dict[str, Any]:
        """Compute explicit coverage and fault counts without imputing missing values."""
        win = [r for r in recs if window_start_day <= r.day <= up_to_day]
        if not win:
            win = list(recs)
        total = len(win)
        ok_count = sum(1 for r in win if is_clean_record(r))
        sensor_off = sum(1 for r in win if r.quality == QualityState.SENSOR_OFF.value)
        missing = sum(1 for r in win if r.quality == QualityState.MISSING.value)
        suspect = sum(1 for r in win if r.quality == QualityState.SUSPECT.value)
        out_of_range = sum(1 for r in win if r.quality == QualityState.OUT_OF_RANGE.value)
        coverage = ok_count / total if total else 0.0
        return {
            "coverage": round(coverage, 3),
            "total_records": total,
            "ok_count": ok_count,
            "sensor_off_hours": sensor_off,
            "missing_hours": missing,
            "suspect_count": suspect,
            "out_of_range_count": out_of_range,
        }

    def detect_anomalies(
        self,
        records: Iterable[MeasurementRecord | Dict[str, Any]],
        astronaut_id: str,
        up_to_day: int = 23,
    ) -> List[AnomalyFlag]:
        """Detect data faults, contextual outliers, CUSUM drift, and multivariate shifts."""
        parsed = coerce_records(records, astronaut_id=astronaut_id, up_to_day=up_to_day)
        if not parsed:
            return []

        flags: List[AnomalyFlag] = []
        recent_start = max(1, up_to_day - 6)
        by_signal: Dict[str, List[MeasurementRecord]] = {}
        for rec in parsed:
            by_signal.setdefault(rec.signal_type, []).append(rec)

        # 1. Explicit data-fault routing (never emit health alerts for dirty/missing data)
        for sig, sig_recs in sorted(by_signal.items()):
            qstats = self._signal_quality_stats(sig_recs, recent_start, up_to_day)
            fault_recs = [
                r
                for r in sig_recs
                if recent_start <= r.day <= up_to_day and not is_clean_record(r)
            ]
            if not fault_recs:
                continue

            fault_count = len(fault_recs)
            # Route single artifacts (suspect/out_of_range) or sustained gaps (>=2h) as data_fault
            has_artifact = (qstats["suspect_count"] + qstats["out_of_range_count"]) > 0
            has_gap = (qstats["sensor_off_hours"] + qstats["missing_hours"]) >= 1
            if has_artifact or has_gap:
                fault_kinds = sorted({r.quality for r in fault_recs})
                first_f = fault_recs[0]
                last_f = fault_recs[-1]
                flags.append(
                    AnomalyFlag(
                        signal=sig,
                        window=[
                            f"Day {first_f.day} {first_f.hour:02d}:00",
                            f"Day {last_f.day} {last_f.hour:02d}:00",
                        ],
                        anomaly_type="data_fault",
                        score=round(float(fault_count), 2),
                        confidence=0.95,
                        baseline_context=infer_context(first_f),
                        personal_range=[],
                        observed=None,
                        contributors=fault_kinds,
                        data_quality=qstats,
                        evidence_ref=f"fault-{astronaut_id}-{sig}-d{up_to_day}",
                        protocol_refs=[],
                        astronaut_id=astronaut_id,
                        day=up_to_day,
                        title=f"Data quality gap/artifact on {sig}",
                        explanation=(
                            f"Detected {fault_count} non-ok reading(s) ({', '.join(fault_kinds)}) for {sig}. "
                            "Routed as a data fault; missing/artifact readings are never treated as normal."
                        ),
                    )
                )

        # 2. Contextual and CUSUM drift checks on clean, step-adjusted records
        for sig, sig_recs in sorted(by_signal.items()):
            qstats = self._signal_quality_stats(sig_recs, recent_start, up_to_day)
            clean_recs = [r for r in sig_recs if is_clean_record(r)]
            if not clean_recs:
                continue

            step_info = self.detect_device_step(parsed, astronaut_id, sig)
            contexts_present = sorted({infer_context(r) for r in clean_recs})

            for ctx in contexts_present:
                baseline = self.fit_signal_context(
                    parsed, astronaut_id=astronaut_id, signal_type=sig, context=ctx, up_to_day=up_to_day
                )
                ctx_clean = [r for r in clean_recs if infer_context(r) == ctx]
                recent_ctx = [r for r in ctx_clean if r.day >= max(1, up_to_day - 1)]
                if not recent_ctx or baseline.n_days < 4:
                    continue

                cusum = self.detect_cusum_drift(
                    parsed, astronaut_id=astronaut_id, signal_type=sig, context=ctx, up_to_day=up_to_day
                )
                latest_rec = recent_ctx[-1]
                adj_latest = self._step_adjusted_value(latest_rec, step_info)
                latest_z = abs(adj_latest - baseline.center) / baseline.scale

                # Penalize physiological confidence if recent window has data quality gaps
                cov_factor = clamp(qstats["coverage"], 0.35, 1.0)
                proto = SIGNAL_PROTOCOLS.get(sig, [])

                if cusum["detected"]:
                    conf = round(clamp(cusum["confidence"] * (0.5 + 0.5 * cov_factor), 0.1, 0.96), 3)
                    flags.append(
                        AnomalyFlag(
                            signal=sig,
                            window=cusum["window"],
                            anomaly_type="drift",
                            score=round(float(cusum["max_cusum"]), 2),
                            confidence=conf,
                            baseline_context=ctx,
                            personal_range=[round(x, 2) for x in baseline.personal_range],
                            observed=round(adj_latest, 2),
                            contributors=[sig],
                            data_quality=qstats,
                            evidence_ref=f"drift-{astronaut_id}-{sig}-{ctx}-d{up_to_day}",
                            protocol_refs=proto,
                            astronaut_id=astronaut_id,
                            day=up_to_day,
                            title=f"Sustained {cusum['direction']} drift in {sig} ({ctx})",
                            explanation=(
                                f"{sig} in '{ctx}' context shifted {cusum['direction']} to {adj_latest:.2f} "
                                f"versus personal baseline {baseline.center:.2f} (CUSUM {cusum['max_cusum']:.2f})."
                            ),
                        )
                    )
                elif latest_z >= self.contextual_z_threshold and len(ctx_clean) >= 6:
                    conf = round(clamp((0.68 + 0.05 * (latest_z - self.contextual_z_threshold)) * cov_factor, 0.2, 0.94), 3)
                    flags.append(
                        AnomalyFlag(
                            signal=sig,
                            window=[
                                f"Day {latest_rec.day} {latest_rec.hour:02d}:00",
                                f"Day {latest_rec.day} {latest_rec.hour:02d}:00",
                            ],
                            anomaly_type="contextual",
                            score=round(latest_z, 2),
                            confidence=conf,
                            baseline_context=ctx,
                            personal_range=[round(x, 2) for x in baseline.personal_range],
                            observed=round(adj_latest, 2),
                            contributors=[sig],
                            data_quality=qstats,
                            evidence_ref=f"ctx-{astronaut_id}-{sig}-{ctx}-d{up_to_day}",
                            protocol_refs=proto,
                            astronaut_id=astronaut_id,
                            day=up_to_day,
                            title=f"Contextual deviation in {sig} during {ctx}",
                            explanation=(
                                f"{sig} observed at {adj_latest:.2f} during '{ctx}' context "
                                f"(z={latest_z:.2f} from personal baseline {baseline.center:.2f})."
                            ),
                        )
                    )

        # 3. Multivariate Mahalanobis check across clean physiological dimensions
        maha = self.detect_multivariate_mahalanobis(
            parsed, astronaut_id=astronaut_id, up_to_day=up_to_day
        )
        if maha["detected"]:
            overall_q = self._signal_quality_stats(parsed, recent_start, up_to_day)
            flags.append(
                AnomalyFlag(
                    signal="multivariate_cluster",
                    window=maha["window"],
                    anomaly_type="multivariate",
                    score=round(float(maha["mahalanobis_d"]), 2),
                    confidence=round(float(maha["confidence"]), 3),
                    baseline_context="multi_signal",
                    personal_range=[0.0, round(math.sqrt(maha["threshold_d2"]), 2)],
                    observed=round(float(maha["mahalanobis_d"]), 2),
                    contributors=list(maha["contributors"]),
                    data_quality=overall_q,
                    evidence_ref=f"maha-{astronaut_id}-d{up_to_day}",
                    protocol_refs=["PROT-REC-01", "PROT-SLP-01"],
                    astronaut_id=astronaut_id,
                    day=up_to_day,
                    title="Combined multi-signal physiological shift",
                    explanation=(
                        f"Joint Mahalanobis distance ({maha['mahalanobis_d']:.2f}) exceeded personal multi-signal "
                        f"threshold; primary contributors: {', '.join(maha['contributors'])}."
                    ),
                )
            )

        severity_order = {"multivariate": 0, "drift": 1, "contextual": 2, "data_fault": 3}
        flags.sort(key=lambda f: (severity_order.get(f.anomaly_type, 9), -f.score))
        return flags
