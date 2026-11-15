# AstroGuard Model & Decision-Support Engine Cards

> [!NOTE]
> **Illustrative Status Notice:** Illustrative synthetic validation metrics generated on seeded simulator missions (simulator.py). Thresholds and synthetic curves are not empirical NASA astronaut data. None of the modules below perform clinical diagnosis, treatment prescribing, fitness-for-duty scoring, or autonomous clinical decisions.

---

## 1. Personal Baseline Engine (`backend/app/engines/baseline.py`)

- **Purpose & Scope:** Establishes per-astronaut, context-stratified personal physiological/behavioral reference distributions and detects sustained drifts or multivariate shifts rather than single Earth-norm threshold crossings.
- **Inputs:** `MeasurementRecord` stream (`astronaut_id`, `signal_type`, `value`, `quality`, `confidence`, `context_tags`, `source_device`, `firmware_version`, `day`, `hour`).
- **Outputs:** `AnomalyFlag` entries classified strictly into `contextual`, `drift`, `multivariate`, or `data_fault` with personal range `[lo, hi]`, observed value, contributors, data coverage, and calibrated confidence.
- **Method & Observed Parameters:**
  - Conjugate Normal-Normal Bayesian shrinkage (`baseline_days=10`, `prior_strength=4.0`, `min_personal_samples=5`) with slow EWMA adaptation (`slow_alpha=0.04`) frozen whenever standardized excursion exceeds `freeze_z_threshold=1.75`.
  - Stratified contexts (`sleep`, `exercise`, `post_exercise`, `rest`).
  - Metadata-aligned device/firmware step offset estimation (`detect_device_step`) so hardware swaps shift baseline reference instead of firing drift alarms.
  - Two-sided CUSUM drift accumulation (`cusum_k=0.5`, `cusum_h=3.8`) and Multivariate Mahalanobis covariance checks (`hr_recovery_1m`/`resting_hr`/`hrv_rmssd`/`sleep_duration` and cognitive clusters).
- **Observed Validation Snapshot (Synthetic):** Event recall `1.000`, mean lead time `6.67d`, null FA `0.167/30 crew-days`, artifact fault routing `1.000`.
- **Assumptions:** Early mission days (Days 1–10) or Bayesian priors approximate nominal baseline; hardware swaps update `source_device`/`firmware_version` metadata.
- **Limitations & Failure Modes:** Cannot distinguish unrecorded hardware sensor bias without firmware/device metadata changes; extended >50% missingness lowers statistical power and reduces confidence cleanly.
- **Safety & Privacy Boundary:** Hard-quarantines `suspect`, `out_of_range`, `sensor_off`, and `missing` records into `data_fault` (never imputed healthy). Never triggers/blocks deterministic safety rules (`SR-01..05`) or SOS.

---

## 2. Readiness & Recovery Scorer (`backend/app/engines/readiness.py`)

- **Purpose & Scope:** Synthesizes clean physiological, sleep, cognitive, radiation, and environmental confounder streams into interpretable Recovery Debt (`0–100`) and Cognitive Readiness (`0–100`) decision-support scores.
- **Inputs:** Clean telemetry records, active deterministic safety rules, environmental confounder summary, and data quality summary up to `up_to_day`.
- **Outputs:** Recovery Debt (`0–100`, lower healthier), Cognitive Readiness (`0–100`, higher healthier), Radiation dosimetry trend (`uSv/day` and cumulative `mSv`), per-signal observations vs personal reference, and coverage-scaled confidence.
- **Assumptions:** Baseline days reflect nominal resting/sleep/cognitive reference; higher Recovery Debt reflects multi-signal strain relative to personal norm.
- **Limitations & Failure Modes:** Illustrative composite weights tuned to simulator mission scales (`F-03`); high missingness widens uncertainty/lowers confidence without inventing missing points; never a fitness-for-duty gate.
- **Safety & Privacy Boundary:** Surfaces active deterministic safety rules (`SR-01..05`) prominently without altering or suppressing them; reads only numerical telemetry (`physio`/`sleep`/`cognitive`/`habitat`).

---

## 3. Crew-Environment Lag Correlator & MSIDE (`backend/app/engines/environment.py`, `mside.py`)

- **Purpose & Scope:** Evaluates multi-stream habitat-to-crew associations across zones (`N1`, `LAB`, `CQ`, `AL`) and lags (`0–2d`) to detect shared environmental confounders (e.g., `LAB` CO2 scrubber degradation) before misattributing them to individual illness.
- **Inputs:** Crew symptom/cognitive/physiological streams, zone environmental telemetry (`co2_ppm`, `cabin_temp_c`, `cabin_humidity_pct`, `cabin_noise_db`), and zone occupancy.
- **Outputs:** Lagged Pearson correlations (`r`), permutation empirical `p`-values, Benjamini-Hochberg `FDR q`-values (`fdr_alpha=0.05`), and cross-crew shared exposure clusters (anonymized `Crew A..D` labels when shared across `>= 2` crew).
- **Observed Validation Snapshot (Synthetic):** Positive shared `LAB` cluster recall `1.000`, time-shuffled negative-control max empirical FDR `0.00000` (`<= 0.05`), strictly non-causal phrasing verified (`True`).
- **Assumptions:** Zone occupancy maps crew members to primary habitat module exposure; minimum overlapping clean days (`>= 5`) exist per pair.
- **Limitations & Failure Modes:** Pearson correlation captures linear associations only; shared exposure never proves causation and explicitly notes individual illness is not excluded.
- **Safety & Privacy Boundary:** Cross-crew summaries anonymize astronaut identities and prohibit reading private journal text or crew messages.

---

## 4. Counterfactual What-If Sandbox (`backend/app/engines/counterfactual.py`)

- **Purpose & Scope:** Exploratory `1–14 day` trajectory comparison allowing crew to inspect how illustrative changes in sleep, workload (`-2..+2`), recovery blocks, and cabin ventilation (`50–200%`) shift trend direction and uncertainty.
- **Inputs:** Current `readiness` output (`recovery_debt`, `cognitive_readiness`, recent 7-day series) and counterfactual lever inputs + `baseline_co2_ppm`.
- **Outputs:** `baseline` vs `intervention` daily curves (`1..horizon_days`), `sqrt(step)` widening uncertainty bounds, CO2 ventilation delta, explicit assumption list, protocol references, and exploratory confidence (`<= 0.58`).
- **Method & Parameters:** Extracts damped 7-day linear trend (`0.6x` slope, `0.84^(step-1)` decay), saturating `tanh` sleep response, exponential recovery-block scaling, and ventilation CO2 scaling (`ambient_floor=250 ppm`).
- **Assumptions:** Smooth extrapolation of recent 7-day trend; no intervening acute illness, medication, or mechanical scrubber failure.
- **Limitations & Failure Modes:** Purely illustrative first-order heuristic, not a validated physiological digital twin or treatment predictor; uncertainty widens rapidly (`5.2 * sqrt(step)` / `4.5 * sqrt(step)`).
- **Safety & Privacy Boundary:** Always sets `exploratory: True` and carries explicit non-prediction / non-treatment disclaimers.

---

## 5. Offline Grounded AstroGuard Advisor (`backend/app/engines/advisor.py`)

- **Purpose & Scope:** Produces concise, deterministic, offline daily briefings and answers natural-language crew questions strictly grounded in verified engine numbers and the curated `PROTOCOL_LIBRARY`.
- **Inputs:** Verified engine outputs (`readiness`, `behavioral`, `environment`, `mside`, `counterfactual`), `active_safety_rules`, and `PROTOCOL_LIBRARY`.
- **Outputs:** Grounded response with exact evidence windows, cited observations, confidence score, curated `protocol_refs`, `said_i_dont_know` flag, and `refused_diagnosis` flag.
- **Assumptions:** All quantitative answers originate exclusively from verified upstream engine dictionaries.
- **Limitations & Failure Modes:** Deterministic template/intent matching rather than open-ended LLM conversation; intentionally says `"I don't know"` when data coverage `< 60%` or asked about unsupported clinical tests (e.g., glucose, MRI).
- **Safety & Privacy Boundary:** Explicitly refuses medical diagnosis or prescribing; prohibits overriding/downgrading deterministic safety rules (`SR-01..05`) or SOS beacons; never reads private journals or message text.
