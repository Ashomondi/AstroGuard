# AstroGuard — Validation & Data Plan (condensed from team doc)

**Honest picture:** NASA OSDR (Inspiration4/SOMA) is small, short, mostly biological, unlabeled → realism only. LSDA/HERA analog data by request → external validation if granted. HRP evidence reports → scenario design. Do **not** claim "trained on NASA astronaut data".

## Anomaly kinds
data fault → data-quality state, never health alert · contextual → context baseline · drift → CUSUM / change-point · multivariate/interaction → Mahalanobis (shrinkage) + MSIDE. Emergencies stay deterministic.

## Layers
0 quality gate (+ later artifact classifier P1-6) · 1 personal baselines (median/MAD, circadian, CUSUM, BOCPD, shrinkage Mahalanobis, isolation forest as second opinion only) · 2 population priors (hierarchical shrinkage) · 3 MSIDE with permutation tests, FDR, shuffled-time negative controls, non-causal language · 4 calibration (conformal / isotonic).

## Flag contract
`signal, window, anomaly_type (data_fault|contextual|drift|multivariate), score, confidence, baseline_context, personal_range, observed, contributors, data_quality{coverage,sensor_off_hours}, evidence_ref`.

## Data
Simulator with scenario manifest (P1-2), null missions (P1-3), public datasets (WESAD, Sleep-EDF, PPG-DaLiA, LifeSnaps — verify licenses), `data/registry.yaml`, `data/raw` & `data/harmonized` git-ignored, `data/fixtures` committed. Harmonize to common schema; gaps stay gaps.

## Labels
simulator ground truth · semi-synthetic injection into public recordings · natural dataset labels · expert review · null missions.

## Metrics
lead time, recall by magnitude, false alerts / astronaut-week on null missions, precision, data-fault routing accuracy, calibration error, missingness robustness, device-step robustness, MSIDE FDR & recall, stability, latency. Compare against fixed Earth-norm threshold and current heuristic.

## Proposed gates (freeze before final test)
FA ≤ 1/astronaut-week · recall ≥ 80% medium/large · median lead time > threshold baseline · fault routing ≥ 95% · MSIDE shuffled ≤ FDR · calibration within tolerance.

## CI tests (P1)
planted recall, null false-alert, artifact routing, device step, missingness sweep, MSIDE negative & positive control, calibration, safety independence, regression gate, reproducibility. Name with feature IDs.

## Runbook
1 freeze baseline metrics → 2 manifest → 3 null missions → 4 harness `python -m app.eval.run --detector <name> --suite validation` → 5 registry/adapters → 6 Layer-1 detectors → 7 artifacts → 8 MSIDE controls → 9 calibration → 10 hand review → 11 frozen final test → 12 model cards → 13 public/analog replay → 14 CI.
