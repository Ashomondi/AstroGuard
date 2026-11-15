# AstroGuard Validation Report

> [!IMPORTANT]
> **Illustrative Validation Notice:** Illustrative synthetic validation metrics generated on seeded simulator missions (simulator.py). Thresholds and synthetic curves are not empirical NASA astronaut data.

## Run Provenance

- **Command:** `cd /home/frihk/frihk/Astra/backend && python3 -m app.eval.run --seed 42`
- **Seeds Evaluated:** `[42, 43, 44]` (`n_permutations=60`, `fast=False`)
- **Runtime:** `15.15 s`
- **Overall Release Gate Status:** `PASS`

## 1. Three-Way Comparator Summary

| Metric | Baseline 1: Fixed Earth-Norm | Baseline 2: Heuristic Rolling (`|z|>=2.5`) | AstroGuard Full Engine Stack |
| --- | ---: | ---: | ---: |
| Planted Anomaly Event Recall | 1.000 | 1.000 | **1.000** |
| Mean Lead Time Before Peak (days) | 2.33 | 7.67 | **6.67** |
| Behavioral Underreporting Recall | 0.000 | 0.000 | **1.000** |
| Cross-Crew MSIDE Exposure Recall | 0.000 | 0.000 | **1.000** |
| Null Mission False Alerts / 30 Crew-Days | 3.667 | 15.750 | **0.167** |
| Artifact False-Alert Rate (6 Fault Types) | 0.667 | 0.500 | **0.000** |
| Fault Routing Completeness (`data_fault`) | 0.000 | 0.000 | **1.000** |

- **Comparator Deltas:** AstroGuard leads Fixed Earth-Norm by `+4.34 days` while reducing null-mission false alerts by `3.50/30 crew-days` vs Earth-Norm and `15.58/30 crew-days` vs Heuristic Rolling (whose apparent early sensitivity comes with `15.75` false alerts/30 crew-days).

### Per-Scenario Breakdown (Planted Events)

| Scenario ID | Earth-Norm Recall (Lead d) | Heuristic Rolling Recall (Lead d) | AstroGuard Recall (Lead d) |
| --- | ---: | ---: | ---: |
| `EV_RECOVERY_DECLINE` | 1.00 (2.0d) | 1.00 (9.0d) | **1.00 (7.0d)** |
| `MC_COGNITIVE_DRIFT_AND_UNDERREPORTING` | 1.00 (4.0d) | 1.00 (10.0d) | **1.00 (9.0d)** |
| `SHARED_LAB_CO2_EXPOSURE` | 1.00 (1.0d) | 1.00 (4.0d) | **1.00 (4.0d)** |

- Shared Habitat Cumulative Radiation by Day 23 (mean across seeds): `12.82 mSv`

## 2. Null-Mission Alert Burden (`null_mission=True`)

- Evaluated `360` crew-days across seeds `[42, 43, 44]` (`4` crew x `30` days/seed).
- AstroGuard false alerts total: `2` (`0.167` per 30 crew-days; gate `<= 1.0`).
- Existing clean gap on `ast-02` Day 14 was quarantined cleanly (`null_data_fault_notices_routed=3`).

| Seed | False Alerts | FA / 30 Crew-Days | Data Fault Notices Routed |
| ---: | ---: | ---: | ---: |
| 42 | 2 | 0.500 | 1 |
| 43 | 0 | 0.000 | 1 |
| 44 | 0 | 0.000 | 1 |

## 3. Missingness Robustness Sweep (`10%`, `30%`, `50%`)

| Missingness | Mean Coverage | Mean Stated Confidence | Target Recall (Day 23) | Imputation Leaks |
| ---: | ---: | ---: | ---: | ---: |
| 0% | 0.984 | 0.942 | 1.000 | 0 |
| 10% | 0.899 | 0.881 | 1.000 | 0 |
| 30% | 0.683 | 0.709 | 1.000 | 0 |
| 50% | 0.504 | 0.578 | 1.000 | 0 |

- Monotonic confidence degradation verified: `True`
- Zero `sensor_off`/`missing` values imputed as normal: `True`

## 4. Artifact Isolation & Device-Step Immunity

| Artifact Type | Signal | Routed to `data_fault` | AstroGuard Physio Alerts | Earth-Norm False Trigger | Heuristic False Trigger |
| --- | --- | :---: | ---: | :---: | :---: |
| `motion_spike` | `heart_rate` | `True` | 0 | `True` | `True` |
| `out_of_range` | `spo2` | `True` | 0 | `True` | `True` |
| `saturated` | `heart_rate` | `True` | 0 | `False` | `True` |
| `clock_jump` | `heart_rate` | `True` | 0 | `False` | `False` |
| `sensor_off` | `heart_rate` | `True` | 0 | `True` | `False` |
| `missing` | `heart_rate` | `True` | 0 | `True` | `False` |

- **Device-Step Hardware Swap (`+8.0 bpm` on `ast-01` `resting_hr` at Day 15):**
  - Step detector triggered: `True` (estimated offset `+8.29 bpm` vs injected `+8.0 bpm`).
  - AstroGuard false physiological `resting_hr` alerts post-swap: `0` (vs Heuristic Rolling: `2`).
  - Preserved true post-swap drift sensitivity (`+1.4 bpm/day` Days 19–25): `True` (score `10.41`).

## 5. MSIDE Controls (Positive Cluster vs Time-Shuffled Negative Control)

- Positive Control Shared `LAB` Cluster Detection Rate: `1.000`
- Strictly Non-Causal Language Verified (`causes`/`proves`/`diagnosed` absent): `True`
- Negative Control Mean Empirical FDR (shuffled timestamps): `0.00000` (max `0.00000`, gate `<= 0.05`)

| Seed | Positive Shared LAB Found | LAB r | LAB q-value | Shuffled Hypotheses | Shuffled False Discoveries | Shuffled FDR |
| ---: | :---: | ---: | ---: | ---: | ---: | ---: |
| 42 | `True` | +0.864 | 0.01193 | 36 | 0 | 0.00000 |
| 43 | `True` | +0.847 | 0.01522 | 36 | 0 | 0.00000 |
| 44 | `True` | +0.860 | 0.00838 | 36 | 0 | 0.00000 |

## 6. Confidence Calibration Check

| Quality Stratum | Evaluations | Mean Coverage | Mean Stated Confidence | Empirical Accuracy | Calibration Gap |
| --- | ---: | ---: | ---: | ---: | ---: |
| Clean (`>= 90%` coverage) | 12 | 0.992 | 0.946 | 0.917 | 0.030 |
| Degraded (`40%` missingness injected) | 12 | 0.589 | 0.642 | 0.750 | 0.108 |

- Stated confidence tracks clean vs degraded quality: `True`
- Higher-confidence stratum matches/exceeds degraded accuracy: `True`

## 7. Gate Verification Summary

| Validation Gate | Status |
| --- | :---: |
| `planted_recall_ge_0_80` | `PASS` |
| `lead_time_beats_earth_norm` | `PASS` |
| `null_fa_le_1_per_30_crew_days` | `PASS` |
| `null_fa_below_earth_norm` | `PASS` |
| `artifact_fault_routing_ge_0_95` | `PASS` |
| `device_step_immunity_passed` | `PASS` |
| `missingness_graceful_degradation` | `PASS` |
| `mside_controls_fdr_le_0_05` | `PASS` |
| `confidence_calibration_passed` | `PASS` |
| `null_fa_below_heuristic_rolling` | `PASS` |
