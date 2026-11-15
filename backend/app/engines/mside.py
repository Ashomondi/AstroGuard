"""Multi-Signal Interaction Discovery Engine — MSIDE (F-14).

Discovers lagged cross-signal and cross-crew associations (lag 0-1 day) using
exact sequential Monte Carlo permutation tests (Besag-Clifford) combined with
Benjamini-Hochberg False Discovery Rate (FDR) control. Includes a shuffled-
timestamp negative control verifying empirical false discoveries <= fdr_alpha.

All generated descriptions strictly enforce non-causal association wording
('co-moving', 'follows', 'associated with') — never causal claims.
"""

from __future__ import annotations

import copy
import random
import statistics
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.engines.baseline import clamp, coerce_records, is_clean_record
from app.engines.environment import (
    benjamini_hochberg,
    extract_crew_daily_env_and_symptoms,
    pearson_correlation,
)
from app.schema import CREW_BY_ID, CREW_ROSTER, HABITAT_ZONES, MeasurementRecord, SignalType

# (source_signal, target_signal, expected_sign, title, relation_phrase, tags, protocol_refs)
CANDIDATE_INTERACTIONS: Tuple[Tuple[str, str, int, str, str, List[str], List[str]], ...] = (
    (
        SignalType.SLEEP_FRAGMENTATION.value,
        SignalType.HRV_RMSSD.value,
        -1,
        "Lower HRV follows fragmented sleep",
        "follows",
        ["physiology", "sleep"],
        ["PROT-REC-01", "PROT-SLP-01"],
    ),
    (
        SignalType.SLEEP_DURATION.value,
        SignalType.HRV_RMSSD.value,
        1,
        "HRV co-moves with sleep duration",
        "co-moving",
        ["physiology", "sleep"],
        ["PROT-REC-01", "PROT-SLP-01"],
    ),
    (
        SignalType.SLEEP_DURATION.value,
        SignalType.PVT_MEAN_RT.value,
        -1,
        "Slower PVT reaction follows shorter sleep",
        "follows",
        ["cognitive", "sleep"],
        ["PROT-SLP-01", "PROT-SLP-02"],
    ),
    (
        SignalType.SLEEP_FRAGMENTATION.value,
        SignalType.PVT_MEAN_RT.value,
        1,
        "PVT slowing associated with sleep fragmentation",
        "associated with",
        ["cognitive", "sleep"],
        ["PROT-SLP-01", "PROT-SLP-02"],
    ),
    (
        SignalType.SLEEP_DURATION.value,
        SignalType.HR_RECOVERY_1M.value,
        1,
        "Post-exercise HR recovery follows sleep duration",
        "follows",
        ["recovery", "sleep"],
        ["PROT-REC-01", "PROT-SLP-01"],
    ),
    (
        SignalType.RESTING_HR.value,
        SignalType.HRV_RMSSD.value,
        -1,
        "Resting HR and HRV co-vary inversely",
        "co-moving",
        ["physiology", "recovery"],
        ["PROT-REC-01", "PROT-REC-02"],
    ),
    (
        SignalType.HR_RECOVERY_1M.value,
        SignalType.HRV_RMSSD.value,
        1,
        "HR recovery and overnight HRV co-move",
        "co-moving",
        ["physiology", "recovery"],
        ["PROT-REC-01", "PROT-REC-02"],
    ),
    (
        SignalType.STRESS_SCORE.value,
        SignalType.SLEEP_FRAGMENTATION.value,
        1,
        "Sleep fragmentation associated with perceived stress",
        "associated with",
        ["behavioural", "sleep"],
        ["PROT-SLP-01"],
    ),
    (
        "co2_exposure",
        "symptom_index",
        1,
        "Symptom scores co-moving with zone CO2 exposure",
        "co-moving",
        ["environment", "symptoms"],
        ["PROT-ENV-01", "PROT-ENV-02"],
    ),
)

_FORBIDDEN_CAUSAL_TERMS = ("causes", "caused by", "diagnoses", "cures", "proves")


def _extract_daily_signal_maps(
    records: Sequence[MeasurementRecord],
    up_to_day: int,
) -> Dict[Tuple[str, str], Dict[int, float]]:
    """Aggregate clean records into daily medians per (astronaut_id, signal_type)."""
    grouped: Dict[Tuple[str, str, int], List[float]] = {}
    for rec in records:
        if rec.astronaut_id in CREW_BY_ID and rec.day <= up_to_day and is_clean_record(rec) and rec.value is not None:
            grouped.setdefault((rec.astronaut_id, rec.signal_type, rec.day), []).append(float(rec.value))

    out: Dict[Tuple[str, str], Dict[int, float]] = {}
    for (aid, sig, d), vals in grouped.items():
        out.setdefault((aid, sig), {})[d] = float(statistics.median(vals))
    return out


def _paired_series(
    src_map: Dict[int, Optional[float]],
    tgt_map: Dict[int, Optional[float]],
    up_to_day: int,
    lag: int,
) -> Tuple[List[float], List[float]]:
    """Collect aligned (src_{d-lag}, tgt_d) pairs with no imputation."""
    xs: List[float] = []
    ys: List[float] = []
    for d in range(1 + lag, up_to_day + 1):
        xv = src_map.get(d - lag)
        yv = tgt_map.get(d)
        if xv is not None and yv is not None:
            xs.append(float(xv))
            ys.append(float(yv))
    return xs, ys


def _besag_clifford_pvalue(
    src_map: Dict[int, Optional[float]],
    tgt_map: Dict[int, Optional[float]],
    expected_sign: int,
    observed_signed_r: float,
    up_to_day: int,
    max_permutations: int,
    rng: random.Random,
    stop_hits: int = 4,
) -> Tuple[float, int]:
    """Exact sequential Monte Carlo permutation p-value (Besag & Clifford, 1991)."""
    valid_days = [d for d in range(1, up_to_day + 1) if tgt_map.get(d) is not None]
    tgt_vals = [float(tgt_map[d]) for d in valid_days if tgt_map[d] is not None]
    if len(tgt_vals) < 7:
        return 1.0, 0

    hits = 0
    perms_run = 0
    shuffled = list(tgt_vals)
    for t in range(1, max_permutations + 1):
        perms_run = t
        rng.shuffle(shuffled)
        perm_tgt = {d: val for d, val in zip(valid_days, shuffled)}
        px0, py0 = _paired_series(src_map, perm_tgt, up_to_day, lag=0)
        px1, py1 = _paired_series(src_map, perm_tgt, up_to_day, lag=1)
        r0_p = pearson_correlation(px0, py0) * expected_sign
        r1_p = pearson_correlation(px1, py1) * expected_sign
        if max(r0_p, r1_p) >= observed_signed_r:
            hits += 1
            if hits >= stop_hits:
                return hits / t, perms_run
    return (hits + 1.0) / (max_permutations + 1.0), perms_run


def _assert_non_causal(text: str) -> str:
    """Guardrail ensuring no causal claims slip into MSIDE summaries."""
    lower = text.lower()
    for term in _FORBIDDEN_CAUSAL_TERMS:
        if term in lower:
            raise ValueError(f"Forbidden causal phrasing detected in MSIDE text: {term}")
    return text


def discover_interactions(
    records: Iterable[MeasurementRecord | Dict[str, Any]],
    zone_occupancy: Optional[Any] = None,
    up_to_day: int = 23,
    fdr_alpha: float = 0.05,
    n_permutations: int = 80,
    seed: int = 42,
) -> Dict[str, Any]:
    """Discover lagged cross-signal & cross-crew associations under BH-FDR control."""
    parsed = coerce_records(records, up_to_day=up_to_day)
    daily_maps = _extract_daily_signal_maps(parsed, up_to_day)
    daily_exp, daily_sym, daily_zone, _ = extract_crew_daily_env_and_symptoms(
        parsed, zone_occupancy, up_to_day
    )

    astronaut_ids = sorted({r.astronaut_id for r in parsed if r.astronaut_id in CREW_BY_ID})
    if not astronaut_ids:
        astronaut_ids = [c.astronaut_id for c in CREW_ROSTER]

    # Collect viable candidate hypotheses
    candidates: List[Dict[str, Any]] = []
    for aid in astronaut_ids:
        for src_sig, tgt_sig, exp_sign, title, rel_phrase, tags, protos in CANDIDATE_INTERACTIONS:
            if src_sig == "co2_exposure":
                src_map: Dict[int, Optional[float]] = dict(daily_exp.get(aid, {}))
            else:
                src_map = {d: v for d, v in daily_maps.get((aid, src_sig), {}).items()}

            if tgt_sig == "symptom_index":
                tgt_map: Dict[int, Optional[float]] = dict(daily_sym.get(aid, {}))
            else:
                tgt_map = {d: v for d, v in daily_maps.get((aid, tgt_sig), {}).items()}

            xs0, ys0 = _paired_series(src_map, tgt_map, up_to_day, lag=0)
            xs1, ys1 = _paired_series(src_map, tgt_map, up_to_day, lag=1)
            if max(len(xs0), len(xs1)) < 7:
                continue

            r0 = pearson_correlation(xs0, ys0)
            r1 = pearson_correlation(xs1, ys1)
            s0 = r0 * exp_sign
            s1 = r1 * exp_sign
            if s0 >= s1:
                best_lag, best_r, best_signed, n_pairs = 0, r0, s0, len(xs0)
            else:
                best_lag, best_r, best_signed, n_pairs = 1, r1, s1, len(xs1)

            candidates.append(
                {
                    "astronaut_id": aid,
                    "src_sig": src_sig,
                    "tgt_sig": tgt_sig,
                    "exp_sign": exp_sign,
                    "title": title,
                    "relation_phrase": rel_phrase,
                    "tags": list(tags),
                    "protocol_refs": list(protos),
                    "src_map": src_map,
                    "tgt_map": tgt_map,
                    "best_lag": best_lag,
                    "best_r": best_r,
                    "best_signed": best_signed,
                    "n_pairs": n_pairs,
                }
            )

    m = len(candidates)
    max_perms = min(1500, max(n_permutations, m * 40)) if m > 0 else n_permutations

    p_values: List[float] = []
    for idx, cand in enumerate(candidates):
        if cand["best_signed"] < 0.55 or cand["n_pairs"] < 7:
            p_val = 1.0
            perms_run = 0
        else:
            rng = random.Random(seed + idx * 37)
            p_val, perms_run = _besag_clifford_pvalue(
                src_map=cand["src_map"],
                tgt_map=cand["tgt_map"],
                expected_sign=cand["exp_sign"],
                observed_signed_r=cand["best_signed"],
                up_to_day=up_to_day,
                max_permutations=max_perms,
                rng=rng,
            )
        cand["p_value"] = round(p_val, 5)
        cand["permutations_run"] = perms_run
        p_values.append(p_val)

    q_values = benjamini_hochberg(p_values)
    zone_names = {z.zone_id: z.name for z in HABITAT_ZONES}

    personal_findings: List[Dict[str, Any]] = []
    env_cluster_members: Dict[str, List[Dict[str, Any]]] = {}
    evaluated_summary: List[Dict[str, Any]] = []

    for cand, q_val in zip(candidates, q_values):
        significant = q_val <= fdr_alpha and cand["best_signed"] >= 0.55
        aid = cand["astronaut_id"]
        crew = CREW_BY_ID.get(aid)
        anon_label = crew.anonymous_label if crew else aid
        conf = round(clamp(0.55 + 0.35 * abs(cand["best_r"]) + (0.06 if significant else 0.0), 0.1, 0.96), 2)
        lag_phrase = "same day" if cand["best_lag"] == 0 else "1-day lag"

        summary_entry = {
            "astronaut_id": aid,
            "anonymous_label": anon_label,
            "source_signal": cand["src_sig"],
            "target_signal": cand["tgt_sig"],
            "lag_days": cand["best_lag"],
            "correlation_r": round(cand["best_r"], 3),
            "p_value": cand["p_value"],
            "fdr_q_value": round(q_val, 5),
            "significant": significant,
            "n_pairs": cand["n_pairs"],
        }
        evaluated_summary.append(summary_entry)

        if not significant:
            continue

        if cand["src_sig"] == "co2_exposure":
            # Track zone for cross-crew shared exposure grouping
            z_hist: Dict[str, int] = {}
            for d in range(max(1, up_to_day - 6), up_to_day + 1):
                z = daily_zone.get(aid, {}).get(d, crew.default_zone if crew else "LAB")
                z_hist[z] = z_hist.get(z, 0) + 1
            primary_zone = max(z_hist.items(), key=lambda x: x[1])[0] if z_hist else "LAB"
            env_cluster_members.setdefault(primary_zone, []).append(
                {
                    "astronaut_id": aid,
                    "anonymous_label": anon_label,
                    "zone_id": primary_zone,
                    "r": round(cand["best_r"], 3),
                    "lag_days": cand["best_lag"],
                    "p_value": cand["p_value"],
                    "fdr_q_value": round(q_val, 5),
                    "confidence": conf,
                }
            )
        else:
            desc = _assert_non_causal(
                f"{cand['src_sig']} and {cand['tgt_sig']} co-vary in the expected direction "
                f"(r={cand['best_r']:+.2f}, {lag_phrase}, q={q_val:.3f}). Association only; review alongside clean data coverage."
            )
            personal_findings.append(
                {
                    "finding_id": f"mside-{aid}-{cand['src_sig']}-{cand['tgt_sig']}",
                    "scope": "personal",
                    "astronaut_id": aid,
                    "anonymous_label": anon_label,
                    "source_signal": cand["src_sig"],
                    "target_signal": cand["tgt_sig"],
                    "lag_days": cand["best_lag"],
                    "correlation_r": round(cand["best_r"], 3),
                    "p_value": cand["p_value"],
                    "fdr_q_value": round(q_val, 5),
                    "confidence": conf,
                    "relation_phrase": cand["relation_phrase"],
                    "title": _assert_non_causal(cand["title"]),
                    "summary": desc,
                    "tags": cand["tags"],
                    "protocol_refs": cand["protocol_refs"],
                }
            )

    shared_exposure_findings: List[Dict[str, Any]] = []
    for zid, members in env_cluster_members.items():
        if len(members) >= 2:
            z_name = zone_names.get(zid, zid)
            avg_r = round(sum(x["r"] for x in members) / len(members), 3)
            max_q = round(max(x["fdr_q_value"] for x in members), 5)
            avg_conf = round(sum(x["confidence"] for x in members) / len(members), 2)
            summary_txt = _assert_non_causal(
                f"{len(members)} crew members show symptom scores co-moving with {z_name} CO2 (lag 0-1 day). "
                "Treat this as a shared environmental exposure until the air is verified; individual illness is not excluded."
            )
            shared_exposure_findings.append(
                {
                    "finding_id": f"mside-shared-{zid}",
                    "scope": "cross_crew",
                    "astronaut_id": None,
                    "anonymous_labels": [x["anonymous_label"] for x in members],
                    "zone_id": zid,
                    "zone_name": z_name,
                    "source_signal": "co2_ppm",
                    "target_signal": "symptom_index",
                    "lag_days": sorted({x["lag_days"] for x in members}),
                    "correlation_r": avg_r,
                    "fdr_q_value": max_q,
                    "confidence": avg_conf,
                    "relation_phrase": "co-moving",
                    "title": "Shared habitat exposure across crew",
                    "summary": summary_txt,
                    "tags": ["environment", "symptoms"],
                    "protocol_refs": ["PROT-ENV-01", "PROT-ENV-02", "PROT-MED-01"],
                }
            )
        else:
            # Single crew member environment association
            m_one = members[0]
            z_name = zone_names.get(zid, zid)
            personal_findings.append(
                {
                    "finding_id": f"mside-{m_one['astronaut_id']}-co2-symptom",
                    "scope": "personal",
                    "astronaut_id": m_one["astronaut_id"],
                    "anonymous_label": m_one["anonymous_label"],
                    "source_signal": "co2_ppm",
                    "target_signal": "symptom_index",
                    "lag_days": m_one["lag_days"],
                    "correlation_r": m_one["r"],
                    "p_value": m_one["p_value"],
                    "fdr_q_value": m_one["fdr_q_value"],
                    "confidence": m_one["confidence"],
                    "relation_phrase": "co-moving",
                    "title": f"Symptoms associated with {z_name} CO2",
                    "summary": _assert_non_causal(
                        f"Symptom index is associated with {z_name} CO2 (r={m_one['r']:+.2f}, lag {m_one['lag_days']}d)."
                    ),
                    "tags": ["environment", "symptoms"],
                    "protocol_refs": ["PROT-ENV-01", "PROT-ENV-02"],
                }
            )

    all_findings = shared_exposure_findings + sorted(
        personal_findings, key=lambda f: (-f["confidence"], f["fdr_q_value"])
    )

    return {
        "up_to_day": up_to_day,
        "fdr_alpha": fdr_alpha,
        "total_hypotheses": m,
        "discovery_count": len(all_findings),
        "findings": all_findings,
        "shared_exposure_findings": shared_exposure_findings,
        "personal_findings": personal_findings,
        "all_candidates": sorted(evaluated_summary, key=lambda c: (c["fdr_q_value"], -abs(c["correlation_r"]))),
        "disclaimer": (
            "Correlation is not causation. Personal findings require human review; "
            "environmental findings require cabin-air confirmation."
        ),
    }


def run_negative_control(
    records: Iterable[MeasurementRecord | Dict[str, Any]],
    seed: int = 42,
    up_to_day: int = 23,
    fdr_alpha: float = 0.05,
    n_permutations: int = 80,
) -> Dict[str, Any]:
    """Shuffle timestamps per (stream, signal) to destroy temporal coupling and verify FDR control."""
    parsed = coerce_records(records, up_to_day=up_to_day)
    rng = random.Random(seed)

    # Group record indices by (astronaut_id, zone_id, signal_type) and shuffle values across timestamps
    cloned = [copy.copy(r) for r in parsed]
    buckets: Dict[Tuple[str, str, str], List[int]] = {}
    for idx, rec in enumerate(cloned):
        buckets.setdefault((rec.astronaut_id, rec.zone_id, rec.signal_type), []).append(idx)

    for key in sorted(buckets):
        indices = buckets[key]
        if len(indices) < 2:
            continue
        vals_and_qual = [(cloned[i].value, cloned[i].quality, cloned[i].confidence) for i in indices]
        rng.shuffle(vals_and_qual)
        for idx, (val, qual, conf) in zip(indices, vals_and_qual):
            cloned[idx].value = val
            cloned[idx].quality = qual
            cloned[idx].confidence = conf

    res = discover_interactions(
        cloned,
        up_to_day=up_to_day,
        fdr_alpha=fdr_alpha,
        n_permutations=n_permutations,
        seed=seed + 999,
    )
    total_h = max(1, res["total_hypotheses"])
    false_discoveries = sum(
        1 for c in res["all_candidates"] if c["significant"]
    )
    false_discovery_rate = false_discoveries / total_h

    return {
        "seed": seed,
        "fdr_alpha": fdr_alpha,
        "total_hypotheses": res["total_hypotheses"],
        "false_discoveries": false_discoveries,
        "discovery_count": res["discovery_count"],
        "false_discovery_rate": round(false_discovery_rate, 5),
        "passed": false_discovery_rate <= fdr_alpha,
        "findings": res["findings"],
    }
