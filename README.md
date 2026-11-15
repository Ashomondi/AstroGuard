# AstroGuard — On-Board Crew Health, Readiness & Habitat Telemetry

AstroGuard is an offline-first, delay-tolerant crew health, cognitive readiness, and habitat telemetry decision-support system built for long-duration spaceflight missions.

> **Decision Support Only:** AstroGuard surfaces personalized baselines, multi-signal associations, and deterministic safety rules (`SR-01..SR-05`). It is not a medical diagnosis tool and never replaces flight surgeon or crew clinical review.

---

## Core Architecture

- **Backend & Intelligence Engines (`backend/app/`):**
  - **Data Quality & Append-Only Storage (`quality.py`, `store.py`, `sync.py`):** Quarantines `sensor_off`, `missing`, `suspect`, and `out_of_range` samples cleanly without fake normal imputation; persists events in an append-only SQLite store with priority store-and-forward queuing (`SOS -> critical -> messages -> summaries`).
  - **Consent & Role Scoping (`consent.py`, `main.py`):** Crew-owned tiered normal vs. 2-hour logged emergency override switches (`Astronaut`, `Crew Health Officer`, `Systems Engineer`, `Ground Support`).
  - **Deterministic Safety & SOS (`safety.py`, `sos.py`, `messaging.py`, `engines/alerts.py`):** Independent deterministic rule evaluation (`SR-01`..`SR-05`) that cannot be downgraded or delayed by ML outputs, paired with a Priority-0 Emergency SOS lifecycle.
  - **Intelligence Engines (`engines/`):** Personal cold-start Bayesian shrinkage & CUSUM drift baselines (`baseline.py`), weighted readiness scoring (`readiness.py`), anonymized habitat CO₂/thermal correlations (`environment.py`), Multi-Signal Interaction Discovery Engine (`mside.py`), behavioral cross-checking (`behavioral.py`), counterfactual trajectory modeling (`counterfactual.py`), and grounded Q&A advisor (`advisor.py`).
  - **Mission Simulator & Validation (`simulator.py`, `eval/`):** 30-day reproducible multi-crew mission generator, anomaly/gap injectors, and 11-category automated validation harness.

- **Frontend Flight Deck (`frontend/src/`):**
  - React + Vite clinical telemetry interface with unified `1.5px`-stroke SVG iconography (`Icon.jsx`), compositor-accelerated motion (`index.css`), GPU `clip-path` 2-second SOS press-and-hold (`Header.jsx`), baseline corridor & `sensor_off` hatched gap sparklines (`AstronautBriefing.jsx`), interactive counterfactual day scrubber (`AdvisorView.jsx`), and interactive habitat hull schematic (`SystemsEngineerView.jsx`).

---

## Quickstart

### 1. Run Backend API Server
```bash
cd backend
python3 -m app.main --host 127.0.0.1 --port 8000
```

### 2. Run Frontend Dev Server
```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

### 3. Production Build, Tests & Validation
```bash
# Backend unit, API, and 11-category validation suite
cd backend
python3 -m unittest discover -s tests -v

# Generate validation report & model cards
python3 -m app.eval.run

# Frontend production bundle
cd ../frontend
npm run build
```

---

## Contributors

- **Brownajuoga** (`Broaaron45@gmail.com`) — Mission Simulator, Dataset Registry & Validation Harness
- **Sospeter-57** (`sospeterkinyanjui57@gmail.com`) — Baselines, Readiness, MSIDE, Counterfactual & Advisor Engines
- **Ejao-000** (`odhiamboemmaculatejaneakinyi@gmail.com`) — Schema, Quality Gate, Append-Only SQLite Store & Consent
- **Eojuma** (`evansjuma1e@gmail.com`) — Deterministic Safety Rules, SOS, Delay-Tolerant Messaging & HTTP API
- **ashomondi** (`adhiamboa745@gmail.com`) — Clinical Telemetry Design System & Ops / Engineer / Ground Views
- **Frihk** (`Frihkian05@gmail.com`) — Core App Shell, SVG Iconography, SOS Modal & Astronaut Workspace
