# AstroGuard — Features Document (DRAFT v0.2, condensed into repo)

> AstroGuard feature specification v0.2. All numbers are **illustrative, not validated**.

## 1. Overview
- **Problem:** long missions → immune change, bone loss, CV events, behavioral health problems; Earth link delayed/absent.
- **Vision:** find invisible *combined* changes in body, brain and shared environment before they become recognizable problems; give clear, actionable guidance.
- **Core:** per-astronaut Human Vulnerability Model (stress response/recovery, cognition vs sleep/workload, environment effects, cross-influences).
- **Safety boundary:** decision support, not diagnosis. Emergency detection is rule-based, never downgraded by AI.
- **Novelty (honest):** combination of (1) time-dependent stressor interactions, (2) mapping to recovery & cognitive readiness, (3) cross-crew linking to shared exposures, (4) intervention simulation, (5) offline plain-language explanation.

## 2. Team: ML (2), BE (2), FE (2).

## 3. Roles
| # | Role | Phase |
|---|------|-------|
| 1 | Astronaut — own readiness, trends, explanations, SOS, messaging | MVP |
| 2 | Crew health officer (not a physician) — crew status w/ consent, SOS notifications | MVP |
| 3 | Ground support — synced summaries, messages, SOS packets; never required | MVP (light) |
| 4 | Systems/environment — anonymized shared-exposure alerts | MVP |
| 5 | Commander — fit/needs-rest only | Later |
| 6 | Researcher/admin | Later |

**Privacy:** astronaut owns data; tiered sharing; emergency override logged; every access logged & visible; non-punitive; pre-mission consent profile (normal vs emergency).

## 4. Design principles
1 personal baselines · 2 missing data is a signal · 3 fewer better alerts (budget) · 4 astronauts may hide symptoms (cross-check, non-punitive) · 5 actionable plain language · 6 slow trends + combined signals · 7 behavioral health first-class · 8 environment as confounder · 9 offline-first · 10 validation is part of product · 11 explainable by default · 12 escalation ladder (self-care → health officer → ground; SOS always).

## 5. Data recording
**Sources:** wearable (HR, HRV, activity, skin temp, SpO2, resp, sleep); active tests (PVT, attention, working memory); self-report (daily/weekly); environment (CO2, temp, humidity, noise, pressure); radiation (cumulative, dose-rate); operational context (schedule, workload, exercise, EVA, zone); crew interaction metadata; voice (later, opt-in). MVP: simulator + public datasets through adapters.

**Pipeline:** device → source adapter → validation & quality gate → normalized event → local append-only store → feature extraction / sync queue → engines.

**5.3 Common schema:** `astronaut_id`, `timestamp_utc`, `mission_elapsed_time`, `signal_type`, `value`, `unit`, `source_device`, `firmware_version`, `quality` (`ok|suspect|sensor_off|missing|out_of_range`), `confidence` 0–1, `context_tags`, `consent_scope`.

**5.4 Sampling (illustrative):** HR per-minute; HRV 5-min + nightly; sleep per night; HR recovery per exercise; environment per-minute per zone; PVT daily short/weekly full; self-report daily/weekly.

**5.5 Quality rules (F-02):** sensor-off is its own state shown to astronaut; noisy = `suspect`, down-weighted; abnormal-valid goes to engines; gaps lower alert confidence and may prompt; clock drift/out-of-order fixed at ingestion.

**5.6 Baselines:** pre-flight or first stable weeks; slow in-flight updates guarded against absorbing problems; per context.

**5.7 Storage:** on-board is source of truth, encrypted at rest; store-and-forward sync priority SOS > critical > messages > summaries > raw. Retention TBD.

## 6. Behavioral health
Layers: (1) passive — sleep, activity, HRV/RHR, routine adherence, alone vs shared time, message metadata; (2) active — daily micro check-in, weekly questionnaire (TBD, clinician review), PVT, optional private on-device journal; (3) crew-level anonymized cohesion + optional anonymous climate check.
Detection: personal baseline + context; sustained drift; cross-layer agreement; self-report vs passive cross-check → gentle private prompt; environment first.
| Status | Action |
|---|---|
| Steady | nothing |
| Watch | private suggestion |
| Check-in suggested | guided Advisor conversation, option to talk to crew/HO |
| Support needed | guided support protocol, prompt to involve HO/ground per consent; SOS visible |
Safety handling: concerning answers (e.g. self-harm) → deterministic supportive protocol, clinician-reviewed, AI cannot soften. Will not: diagnose, read messages/journal, report without consent, penalize honesty.

## 7. AstroGuard Advisor
Offline, grounded in engine outputs + curated protocol library + consented data. Modes: daily briefing, ask, guided protocol, check-in support, scenario help (counterfactuals), handoff report. Rules: grounded only, shows evidence, says "I don't know", one next step first, adaptive verbosity, calm tone, never diagnoses/prescribes, respects autonomy & privacy, honest about being AI, escalates by rule. Hard rules: emergency criteria deterministic; LLM cannot lower/delay/cancel. Tech: templates first, small local LLM later; all outputs logged.

## 8. Frontend
**SOS:** on every screen; press-and-hold ~2 s; ~10 s cancel window; "I'm OK" closes; types Medical / Behavioral / Environment; on-board audible+visual alert; packet (id, time, type, vitals snapshot, active alerts, env snapshot, symptoms, last guidance, optional voice note); offline, top of queue, states `queued → transmitting → delivered → acknowledged`; triggers logged override; survives Advisor/analytics failure.
**Messaging:** crew, HO, home; text + audio; routine/urgent; store-and-forward statuses `queued/sent/delivered/read` with expected delay; attach health summary by choice; content never analyzed; bandwidth warnings.
**Views:** astronaut app; HO view; ground console; environment view. **UI:** large targets, low-light readable, link/sensor/sync indicators, color never sole signal.

## 9. Feature list
| ID | Feature | Track |
|----|---------|-------|
| F-01 | Ingestion adapters + common schema | BE |
| F-02 | Quality gate + sensor states | BE/ML |
| F-03 | Mission simulator with planted ground truth | ML |
| F-04 | Offline storage + prioritized store-and-forward sync | BE |
| F-05 | Baseline capture + slow update | ML |
| F-10 | Personal Baseline Engine | ML |
| F-11 | Recovery Debt | ML |
| F-12 | Cognitive Readiness Forecasting | ML |
| F-13 | Crew-Environment Correlation | ML |
| F-14 | MSIDE (centerpiece) | ML |
| F-15 | Counterfactual Simulation | ML |
| F-16 | Behavioral Health Engine | ML/BE |
| F-17 | Slow-trend tracker | ML |
| F-18 | Environment-confounder adjustment | ML |
| F-20 | Explainable alerts | BE/FE |
| F-21 | Escalation ladder + protocol library | BE/FE |
| F-27 | Deterministic emergency rules | BE |
| F-28 | Alert policy + budget | BE/ML |
| F-29 | Underreporting cross-check | ML |
| F-30 | AstroGuard Advisor | ML/BE/FE |
| F-22 | Astronaut app | FE |
| F-23 | Health officer view | FE |
| F-24 | Ground support view | FE |
| F-25 | Environment view | FE |
| F-26 | Consent + access log | BE/FE |
| F-31 | SOS | FE/BE |
| F-32 | Messaging text+audio | FE/BE |
| F-40 | Validation harness (planted interactions) | ML |
| F-41 | Public-dataset / analog replay | ML |

## 11. Demo scenario
Four simulated astronauts: one declining recovery, one cognitive change, two similar symptoms, environment reveals shared exposure (CO2). Plus: sensor-off gap handled, quiet behavioral drift caught, offline SOS delivered later, audio message queued home.

## 12–15
Validation: see `docs/validation-plan.md`. NFRs TBD. Out of scope: diagnosis, real hardware, commander/admin, message content analysis. Open: MVP signal list, phases, questionnaires, alert numbers.
