import React, { useEffect, useId, useRef, useState } from "react";
import Icon from "../components/Icon.jsx";

function TrendSparkline({
  series = [],
  personalRange = null,
  color = "#0d7474",
  minY = 0,
  maxY = 100,
  unit = "",
}) {
  const hatchId = useId().replace(/:/g, "");
  const width = 220;
  const height = 78;
  const padL = 22;
  const padR = 8;
  const padT = 8;
  const padB = 18;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const pts = Array.isArray(series) && series.length > 0 ? series : [{ day: 1, value: minY }];
  const vals = pts.map((p) => Number(p?.value ?? 0));
  const lo = Math.min(minY, ...vals);
  const hi = Math.max(maxY, ...vals, lo + 1);

  const xFor = (i) =>
    pts.length === 1 ? padL + plotW / 2 : padL + (i / (pts.length - 1)) * plotW;
  const yFor = (v) => padT + plotH - ((v - lo) / (hi - lo)) * plotH;
  const stepW = pts.length > 1 ? Math.max(6, plotW / (pts.length - 1)) : 12;

  // Split around explicit sensor gaps so gaps stay visible
  const segments = [];
  let cur = [];
  const gapPts = [];
  pts.forEach((p, idx) => {
    if (p.gap || p.value == null) {
      gapPts.push({ x: xFor(idx), y: yFor(Number(p.value ?? lo)), day: p.day });
      if (cur.length > 0) {
        segments.push(cur);
        cur = [];
      }
    } else {
      cur.push({ x: xFor(idx), y: yFor(Number(p.value)), day: p.day, value: p.value });
    }
  });
  if (cur.length > 0) segments.push(cur);

  const firstDay = pts[0]?.day ?? 1;
  const lastDay = pts[pts.length - 1]?.day ?? pts.length;

  const bandTop =
    personalRange && personalRange.length === 2 ? yFor(Math.min(hi, personalRange[1])) : null;
  const bandBottom =
    personalRange && personalRange.length === 2 ? yFor(Math.max(lo, personalRange[0])) : null;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className="sparkline-svg"
      role="img"
      aria-label={`Trend from Day ${firstDay} to Day ${lastDay}`}
    >
      <defs>
        <pattern
          id={`gap-hatch-${hatchId}`}
          width="5"
          height="5"
          patternTransform="rotate(45 0 0)"
          patternUnits="userSpaceOnUse"
        >
          <rect width="5" height="5" fill="rgba(245, 158, 11, 0.08)" />
          <line x1="0" y1="0" x2="0" y2="5" stroke="rgba(180, 83, 9, 0.32)" strokeWidth="1.5" />
        </pattern>
      </defs>

      {bandTop != null && bandBottom != null ? (
        <g>
          <rect
            x={padL}
            y={bandTop}
            width={plotW}
            height={Math.max(2, bandBottom - bandTop)}
            fill="rgba(13, 116, 116, 0.09)"
            rx="2"
          />
          <line
            x1={padL}
            y1={bandTop}
            x2={width - padR}
            y2={bandTop}
            stroke="rgba(13, 116, 116, 0.28)"
            strokeWidth="0.8"
            strokeDasharray="2 2"
          />
          <line
            x1={padL}
            y1={bandBottom}
            x2={width - padR}
            y2={bandBottom}
            stroke="rgba(13, 116, 116, 0.28)"
            strokeWidth="0.8"
            strokeDasharray="2 2"
          />
        </g>
      ) : null}

      {[0, 0.5, 1].map((frac) => (
        <line
          key={frac}
          x1={padL}
          y1={padT + plotH - frac * plotH}
          x2={width - padR}
          y2={padT + plotH - frac * plotH}
          stroke="#e6eeee"
          strokeWidth="1"
        />
      ))}

      {gapPts.map((g, i) => (
        <rect
          key={`band-${i}`}
          x={Math.max(padL, g.x - stepW / 2)}
          y={padT}
          width={Math.min(stepW, width - padR - Math.max(padL, g.x - stepW / 2))}
          height={plotH}
          fill={`url(#gap-hatch-${hatchId})`}
          stroke="rgba(217, 119, 6, 0.45)"
          strokeWidth="0.7"
          strokeDasharray="2 2"
        >
          <title>{`Day ${g.day}: quarantined telemetry gap (not imputed)`}</title>
        </rect>
      ))}

      {segments.map((seg, sIdx) => {
        const lineD = seg
          .map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
          .join(" ");
        const areaD =
          seg.length > 1
            ? `${lineD} L ${seg[seg.length - 1].x.toFixed(1)} ${(
                padT + plotH
              ).toFixed(1)} L ${seg[0].x.toFixed(1)} ${(padT + plotH).toFixed(1)} Z`
            : "";
        return (
          <g key={sIdx}>
            {areaD ? <path d={areaD} fill={color} fillOpacity="0.1" /> : null}
            {seg.length > 1 ? (
              <path
                d={lineD}
                fill="none"
                stroke={color}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            ) : null}
            {seg.length > 0 ? (
              <circle
                cx={seg[seg.length - 1].x}
                cy={seg[seg.length - 1].y}
                r="2.8"
                fill="#ffffff"
                stroke={color}
                strokeWidth="2"
              />
            ) : null}
          </g>
        );
      })}

      {gapPts.map((g, i) => (
        <circle
          key={i}
          cx={g.x}
          cy={padT + plotH / 2}
          r="3"
          fill="#fff"
          stroke="#d97706"
          strokeWidth="1.8"
          strokeDasharray="2 1"
        >
          <title>{`Day ${g.day}: sensor gap (not imputed)`}</title>
        </circle>
      ))}

      <text x={padL - 4} y={padT + 4} textAnchor="end" fontSize="8" fill="#6c8080">
        {Math.round(hi)}
      </text>
      <text x={padL - 4} y={padT + plotH + 2} textAnchor="end" fontSize="8" fill="#6c8080">
        {Math.round(lo)}
      </text>
      <text x={padL} y={height - 3} textAnchor="start" fontSize="8" fill="#6c8080">
        D{firstDay}
      </text>
      <text x={width - padR} y={height - 3} textAnchor="end" fontSize="8" fill="#6c8080">
        D{lastDay}
        {unit ? ` (${unit})` : ""}
      </text>
    </svg>
  );
}

function getBandMeta(band) {
  const key = String(band || "Steady").toLowerCase();
  if (key.includes("safety")) {
    return { pillClass: "pill-red", ringColor: "#b91c1c", iconName: "alert" };
  }
  if (key.includes("reduced") || key.includes("caution") || key.includes("watch")) {
    return { pillClass: "pill-amber", ringColor: "#d97706", iconName: "alert" };
  }
  return { pillClass: "pill-teal", ringColor: "#0d7474", iconName: "check" };
}

function getStatusPillProps(status) {
  const s = String(status || "normal").toLowerCase();
  if (s === "critical" || s === "support needed") {
    return { cls: "pill-red", iconName: "alert", label: status };
  }
  if (s === "caution" || s === "watch" || s === "check-in suggested") {
    return { cls: "pill-amber", iconName: "alert", label: status };
  }
  return { cls: "pill-teal", iconName: "check", label: status };
}

function PvtReactionModal({ isOpen, baselineMs = 251, onClose, onSave }) {
  const TOTAL_TRIALS = 5;
  const [phase, setPhase] = useState("idle"); // idle | waiting | go | early | done
  const [trialTimes, setTrialTimes] = useState([]);
  const [lastRt, setLastRt] = useState(null);
  const startTimeRef = useRef(0);
  const waitTimerRef = useRef(null);

  useEffect(() => {
    if (!isOpen) {
      if (waitTimerRef.current) clearTimeout(waitTimerRef.current);
      setPhase("idle");
      setTrialTimes([]);
      setLastRt(null);
    }
    return () => {
      if (waitTimerRef.current) clearTimeout(waitTimerRef.current);
    };
  }, [isOpen]);

  const scheduleNextTrial = () => {
    if (waitTimerRef.current) clearTimeout(waitTimerRef.current);
    setPhase("waiting");
    const delayMs = 1100 + Math.floor(Math.random() * 1900);
    waitTimerRef.current = setTimeout(() => {
      startTimeRef.current = performance.now();
      setPhase("go");
    }, delayMs);
  };

  const handlePadAction = () => {
    if (phase === "idle") {
      setTrialTimes([]);
      setLastRt(null);
      scheduleNextTrial();
      return;
    }
    if (phase === "waiting") {
      if (waitTimerRef.current) clearTimeout(waitTimerRef.current);
      setPhase("early");
      return;
    }
    if (phase === "early") {
      scheduleNextTrial();
      return;
    }
    if (phase === "go") {
      const rt = Math.max(120, Math.round(performance.now() - startTimeRef.current));
      const nextList = [...trialTimes, rt];
      setTrialTimes(nextList);
      setLastRt(rt);
      if (nextList.length >= TOTAL_TRIALS) {
        setPhase("done");
      } else {
        scheduleNextTrial();
      }
    }
  };

  useEffect(() => {
    if (!isOpen) return undefined;
    const onKey = (e) => {
      if (e.code === "Space" && phase !== "done") {
        e.preventDefault();
        handlePadAction();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  if (!isOpen) return null;

  const meanRt =
    trialTimes.length > 0
      ? Math.round(trialTimes.reduce((a, b) => a + b, 0) / trialTimes.length)
      : 0;
  const lapses = trialTimes.filter((t) => t >= 500).length;

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="pvt-modal-title"
      data-testid="pvt-modal"
    >
      <div className="modal-card">
        <div className="modal-header">
          <div>
            <h2 id="pvt-modal-title" style={{ margin: 0, fontSize: "1.2rem" }}>
              Reaction test (PVT)
            </h2>
            <p style={{ margin: "3px 0 0", fontSize: "0.83rem", color: "var(--text-secondary)" }}>
              5-trial Psychomotor Vigilance Task · Personal baseline {Math.round(baselineMs)} ms
            </p>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} style={{ gap: 6 }}>
            <kbd className="keycap">Esc</kbd>
            <Icon name="x" size={16} />
          </button>
        </div>

        <button
          type="button"
          onClick={handlePadAction}
          disabled={phase === "done"}
          data-testid="pvt-stimulus-pad"
          style={{
            width: "100%",
            minHeight: 190,
            borderRadius: 16,
            border:
              phase === "go"
                ? "2px solid #047857"
                : phase === "early"
                ? "2px solid var(--amber)"
                : "1.5px solid var(--border-strong)",
            background:
              phase === "go"
                ? "#0d7474"
                : phase === "early"
                ? "var(--amber-bg)"
                : phase === "waiting"
                ? "#eef4f4"
                : "var(--bg-muted)",
            color: phase === "go" ? "#ffffff" : "var(--text-primary)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 8,
            padding: 20,
            transition: "background-color 0.08s ease",
          }}
        >
          <span style={{ fontSize: "1.18rem", fontWeight: 700, display: "inline-flex", alignItems: "center", gap: 6, flexWrap: "wrap", justifyContent: "center" }}>
            {phase === "idle" && (
              <>
                <span>Tap or press</span>
                <kbd className="keycap">Space</kbd>
                <span>to start Trial 1 of 5</span>
              </>
            )}
            {phase === "waiting" && `Wait for green target… (Trial ${trialTimes.length + 1}/${TOTAL_TRIALS})`}
            {phase === "go" && "TAP NOW!"}
            {phase === "early" && "Too early — wait for the green target. Tap to retry."}
            {phase === "done" && `Complete · Mean ${meanRt} ms (${lapses} lapse${lapses === 1 ? "" : "s"})`}
          </span>
          <span style={{ fontSize: "0.82rem", opacity: 0.86 }}>
            {lastRt != null && phase !== "done"
              ? `Last trial: ${lastRt} ms`
              : phase === "done"
              ? `Delta vs personal baseline: ${meanRt - Math.round(baselineMs) >= 0 ? "+" : ""}${
                  meanRt - Math.round(baselineMs)
                } ms`
              : "Responses >= 500 ms count as a lapse."}
          </span>
        </button>

        {trialTimes.length > 0 ? (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {trialTimes.map((ms, i) => (
              <span
                key={i}
                className={`pill ${ms >= 500 ? "pill-amber" : "pill-teal"} tabular-nums`}
              >
                T{i + 1}: {ms} ms
              </span>
            ))}
          </div>
        ) : null}

        <div className="modal-footer">
          <button
            type="button"
            className="btn btn-ghost"
            onClick={() => {
              if (waitTimerRef.current) clearTimeout(waitTimerRef.current);
              setPhase("idle");
              setTrialTimes([]);
              setLastRt(null);
            }}
          >
            Restart
          </button>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={phase !== "done"}
              onClick={async () => {
                await onSave?.({ meanRtMs: meanRt, lapses, trials: trialTimes.length });
                onClose?.();
              }}
              data-testid="pvt-save-btn"
            >
              Save PVT result
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function CheckinModal({ isOpen, initialValues, onClose, onSave }) {
  const [energy, setEnergy] = useState(initialValues?.energy ?? 3);
  const [mood, setMood] = useState(initialValues?.mood ?? 3);
  const [stress, setStress] = useState(initialValues?.stress ?? 2);
  const [fatigue, setFatigue] = useState(initialValues?.fatigue ?? 1);
  const [headache, setHeadache] = useState(initialValues?.headache ?? 0);
  const [note, setNote] = useState(initialValues?.note ?? "");
  const [safetyConcern, setSafetyConcern] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setEnergy(initialValues?.energy ?? 3);
      setMood(initialValues?.mood ?? 3);
      setStress(initialValues?.stress ?? 2);
      setFatigue(initialValues?.fatigue ?? 1);
      setHeadache(initialValues?.headache ?? 0);
      setNote(initialValues?.note ?? "");
      setSafetyConcern(false);
    }
  }, [isOpen, initialValues]);

  if (!isOpen) return null;

  const ScaleRow = ({ label, min, max, value, onChange, hint }) => (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.84rem" }}>
        <strong>{label}</strong>
        <span className="pill pill-neutral tabular-nums">
          {value}/{max}
        </span>
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        {Array.from({ length: max - min + 1 }, (_, i) => min + i).map((val) => (
          <button
            key={val}
            type="button"
            className={`btn btn-sm ${value === val ? "btn-primary" : "btn-secondary"}`}
            style={{ flex: 1 }}
            onClick={() => onChange(val)}
          >
            {val}
          </button>
        ))}
      </div>
      {hint ? (
        <span style={{ fontSize: "0.73rem", color: "var(--text-muted)" }}>{hint}</span>
      ) : null}
    </div>
  );

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="checkin-modal-title"
      data-testid="checkin-modal"
    >
      <div className="modal-card">
        <div className="modal-header">
          <div>
            <h2 id="checkin-modal-title" style={{ margin: 0, fontSize: "1.2rem" }}>
              60-second check-in
            </h2>
            <p style={{ margin: "3px 0 0", fontSize: "0.83rem", color: "var(--text-secondary)" }}>
              Private by default. Never used for fitness-for-duty scoring.
            </p>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={onClose} style={{ gap: 6 }}>
            <kbd className="keycap">Esc</kbd>
            <Icon name="x" size={16} />
          </button>
        </div>

        <ScaleRow
          label="Energy"
          min={1}
          max={5}
          value={energy}
          onChange={setEnergy}
          hint="1 = very depleted · 5 = rested"
        />
        <ScaleRow
          label="Mood"
          min={1}
          max={5}
          value={mood}
          onChange={setMood}
          hint="1 = low · 5 = steady"
        />
        <ScaleRow
          label="Workload stress"
          min={1}
          max={5}
          value={stress}
          onChange={setStress}
          hint="1 = calm · 5 = overloaded"
        />
        <ScaleRow
          label="Headache"
          min={0}
          max={3}
          value={headache}
          onChange={setHeadache}
          hint="0 = none · 3 = severe"
        />

        <div>
          <label
            htmlFor="checkin-note"
            style={{ display: "block", fontSize: "0.83rem", fontWeight: 600, marginBottom: 5 }}
          >
            Private note (stays on your device)
          </label>
          <textarea
            id="checkin-note"
            rows={2}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Optional context (sleep quality, cabin comfort, fatigue)..."
            style={{
              width: "100%",
              borderRadius: 10,
              border: "1px solid var(--border-strong)",
              padding: "8px 10px",
              fontSize: "0.84rem",
            }}
          />
        </div>

        <label
          style={{
            display: "flex",
            gap: 10,
            alignItems: "flex-start",
            padding: "10px 12px",
            borderRadius: 10,
            border: "1px solid var(--red-border)",
            background: "var(--red-card-bg)",
            fontSize: "0.8rem",
            cursor: "pointer",
          }}
        >
          <input
            type="checkbox"
            checked={safetyConcern}
            onChange={(e) => setSafetyConcern(e.target.checked)}
            style={{ marginTop: 3 }}
          />
          <span>
            <strong>Need immediate human safety support:</strong> triggers deterministic rule SR-04
            (never softened by AI) and surfaces Crew Health Officer &amp; SOS options.
          </span>
        </label>

        <div className="modal-footer">
          <span style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
            Gaps never filled silently.
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="button" className="btn btn-secondary" onClick={onClose}>
              Cancel
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={async () => {
                await onSave?.({
                  energy,
                  mood,
                  stress,
                  fatigue,
                  headache,
                  note,
                  safetyConcern,
                });
                onClose?.();
              }}
              data-testid="checkin-submit-btn"
            >
              Save check-in
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AstronautBriefing({
  state,
  onNavigate,
  onOpenProtocol,
  onSubmitCheckin,
  onSubmitPvt,
}) {
  const [showQualityWhy, setShowQualityWhy] = useState(false);
  const [openTrendWhy, setOpenTrendWhy] = useState({
    recovery: false,
    cognitive: false,
    radiation: false,
  });
  const [checkinOpen, setCheckinOpen] = useState(false);
  const [pvtOpen, setPvtOpen] = useState(false);

  const astro = state?.astronaut;
  if (!astro) {
    return (
      <div className="card">
        <h2 className="card-title">Astronaut workspace unavailable</h2>
        <p className="card-subtitle">
          Switch to an Astronaut scope to inspect personal readiness telemetry.
        </p>
      </div>
    );
  }

  const { profile, readiness, briefing, behavioral, msideFindings, userCheckin } = astro;
  const day = state.day ?? 23;
  const earthDelay = state.earth_delay_min ?? 12.8;
  const bandMeta = getBandMeta(readiness.band);
  const score = Math.round(readiness.readiness_score ?? 0);

  // Readiness SVG Ring geometry
  const ringSize = 86;
  const ringStroke = 7;
  const ringRadius = (ringSize - ringStroke) / 2;
  const ringCirc = 2 * Math.PI * ringRadius;
  const ringOffset = ringCirc - (Math.max(0, Math.min(100, score)) / 100) * ringCirc;

  const rec = readiness.recovery_debt;
  const cog = readiness.cognitive_readiness;
  const rad = readiness.radiation_trend;
  const dq = readiness.data_quality;
  const readings = readiness.latest_readings || {};
  const readingOrder = [
    "heart_rate",
    "hrv_rmssd",
    "spo2",
    "sleep_duration",
    "pvt_mean_rt",
    "symptom_headache",
  ];

  const activeSos = (state.sos_events || []).filter(
    (s) => s.astronaut_id === profile.astronaut_id || s.astronaut_id === "anonymised"
  );

  const energyVal = behavioral?.active_layer?.energy_score ?? 3;
  const moodVal = behavioral?.active_layer?.mood_score ?? 3;
  const headacheVal = readings.symptom_headache?.value ?? 0;

  return (
    <div className="stack-col" data-testid="astronaut-briefing-view">
      {/* Page Header */}
      <header className="page-header">
        <div>
          <div className="page-eyebrow">
            Astronaut flight deck · {profile.title}
          </div>
          <h1>{profile.name || profile.short_name} · Day {day} Readiness Briefing</h1>
          <p className="page-subtitle">
            Day {day} · 16:00 ship time · Astronaut scope · ~{earthDelay} min one-way Earth delay
          </p>
        </div>
        <div className="page-header-pills">
          <span className="pill pill-teal">
            <Icon name="shield" size={13} />
            <span>On-board intelligence</span>
          </span>
          <span className="pill pill-neutral">
            <Icon name="lock" size={13} />
            <span>Private by default</span>
          </span>
        </div>
      </header>

      {/* Telemetry Provenance & Confidence Strip */}
      <div className="provenance-strip" aria-label="Telemetry provenance summary">
        <span className="provenance-pill">
          <Icon name="clock" size={12} />
          <span>MET D{String(day).padStart(2, "0")}</span>
        </span>
        <span className="provenance-pill">
          <Icon name="activity" size={12} />
          <span>Coverage {dq.coverage_pct}%</span>
        </span>
        <span className="provenance-pill">
          <Icon name="sliders" size={12} />
          <span>Confidence {briefing.confidence_pct}%</span>
        </span>
        <span className="provenance-pill">
          <Icon name="layers" size={12} />
          <span>Baseline D01–D14</span>
        </span>
        <span className="provenance-pill">
          <Icon name="lock" size={12} />
          <span>Scope {profile.astronaut_id}</span>
        </span>
      </div>

      {/* Hero Daily Briefing Card */}
      <section className="card" aria-label="Your daily briefing">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 16,
            flexWrap: "wrap",
          }}
        >
          <div style={{ flex: 1, minWidth: 260 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
              <span
                style={{
                  fontSize: "0.72rem",
                  fontWeight: 700,
                  letterSpacing: "0.06em",
                  color: "var(--text-muted)",
                }}
              >
                Daily flight briefing
              </span>
              <span className={`pill ${bandMeta.pillClass}`}>
                <Icon name={bandMeta.iconName} size={12} />
                <span>{readiness.band}</span>
              </span>
              {readiness.safety_active ? (
                <span className="pill pill-red">
                  <Icon name="alert" size={12} />
                  <span>Safety rule active</span>
                </span>
              ) : null}
            </div>
            <h2
              style={{
                margin: "10px 0 0",
                fontSize: "1.6rem",
                fontWeight: 700,
                letterSpacing: "-0.02em",
                lineHeight: 1.2,
              }}
            >
              {briefing.headline}
            </h2>
          </div>

          {/* Readiness Gauge */}
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{ textAlign: "right", maxWidth: 185 }}>
              <div
                style={{
                  fontSize: "0.68rem",
                  fontWeight: 700,
                  letterSpacing: "0.09em",
                  color: "var(--text-muted)",
                }}
              >
                READINESS
              </div>
              <div style={{ fontSize: "0.76rem", color: "var(--text-secondary)", marginTop: 2 }}>
                {readiness.safety_active
                  ? "Safety rules are active — follow the deterministic alert."
                  : "Weighted composite summary vs personal baseline."}
              </div>
            </div>
            <div className="ring-wrap" style={{ width: ringSize, height: ringSize }}>
              <svg width={ringSize} height={ringSize} viewBox={`0 0 ${ringSize} ${ringSize}`}>
                <circle
                  cx={ringSize / 2}
                  cy={ringSize / 2}
                  r={ringRadius}
                  fill="none"
                  stroke="#e6eeee"
                  strokeWidth={ringStroke}
                />
                <circle
                  cx={ringSize / 2}
                  cy={ringSize / 2}
                  r={ringRadius}
                  fill="none"
                  stroke={bandMeta.ringColor}
                  strokeWidth={ringStroke}
                  strokeLinecap="round"
                  strokeDasharray={ringCirc}
                  strokeDashoffset={ringOffset}
                />
              </svg>
              <div className="ring-center">
                <span className="ring-score" style={{ fontSize: "1.35rem" }}>
                  {score}
                </span>
                <span className="ring-caption">SUMMARY</span>
              </div>
            </div>
          </div>
        </div>

        {/* 3-Step Plain-Language Guidance */}
        <div className="stack-col" style={{ gap: 12, marginTop: 18 }}>
          <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
            <span
              style={{
                width: 22,
                height: 22,
                borderRadius: "50%",
                background: "var(--teal)",
                color: "#fff",
                fontSize: "0.74rem",
                fontWeight: 700,
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                marginTop: 2,
              }}
            >
              1
            </span>
            <div>
                <div
                  style={{
                    fontSize: "0.72rem",
                    fontWeight: 600,
                    letterSpacing: "0.02em",
                    color: "var(--text-muted)",
                  }}
                >
                  Step 1 · What changed
                </div>
                <p style={{ margin: "2px 0 0", fontSize: "0.9rem", color: "var(--text-primary)" }}>
                  {briefing.what_changed}
                </p>
              </div>
            </div>

            <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
              <span
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: "50%",
                  background: "var(--purple-bg)",
                  color: "var(--purple)",
                  fontSize: "0.74rem",
                  fontWeight: 700,
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                  marginTop: 2,
                }}
              >
                2
              </span>
              <div>
                <div
                  style={{
                    fontSize: "0.72rem",
                    fontWeight: 600,
                    letterSpacing: "0.02em",
                    color: "var(--text-muted)",
                  }}
                >
                  Step 2 · How sure, and why
                </div>
                <p style={{ margin: "2px 0 0", fontSize: "0.9rem", color: "var(--text-primary)" }}>
                  {briefing.how_sure_why}
                </p>
              </div>
            </div>

            <div
              className="card-teal"
              style={{
                border: "1px solid var(--mint-border)",
                borderRadius: 12,
                padding: "13px 15px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 14,
                flexWrap: "wrap",
              }}
            >
              <div style={{ display: "flex", gap: 12, alignItems: "flex-start", flex: 1, minWidth: 240 }}>
                <span
                  style={{
                    width: 22,
                    height: 22,
                    borderRadius: "50%",
                    background: "var(--bg-surface)",
                    border: "1px solid var(--mint-border)",
                    color: "var(--teal)",
                    fontSize: "0.74rem",
                    fontWeight: 700,
                    display: "inline-flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  3
                </span>
                <div>
                  <div
                    style={{
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      letterSpacing: "0.02em",
                      color: "var(--teal-dark)",
                    }}
                  >
                    Step 3 · Single best next step
                  </div>
                  <p style={{ margin: "2px 0 8px", fontSize: "0.9rem", fontWeight: 500 }}>
                    {briefing.single_best_next_step}
                  </p>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {(briefing.protocol_refs || []).map((pid) => (
                      <button
                        key={pid}
                        type="button"
                        className="protocol-chip"
                        onClick={() => onOpenProtocol && onOpenProtocol(pid)}
                      >
                        <Icon name="book" size={12} />
                        <span>{pid}</span>
                        <Icon name="chevron-right" size={12} />
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={() => setCheckinOpen(true)}
                >
                  <Icon name="clipboard" size={14} />
                  <span>Check in</span>
                </button>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{
                    background: "var(--purple-soft)",
                    borderColor: "var(--purple-border)",
                    color: "var(--purple-text)",
                  }}
                  onClick={() => onNavigate && onNavigate("advisor")}
                >
                  <Icon name="cpu" size={14} />
                  <span>Ask why</span>
                </button>
              </div>
            </div>
          </div>

          {/* 6-Signal Vitals Instrument Strip */}
          <div className="vitals-instrument-strip" aria-label="Vitals instrument strip">
            {readingOrder.map((key) => {
              const r = readings[key];
              if (!r) return null;
              const isGap = r.value == null || r.quality !== "ok";
              return (
                <div key={key} className="vital-cell">
                  <div className="vital-cell-label">
                    <Icon
                      name={isGap ? "alert" : key.includes("heart") || key.includes("hrv") ? "heart" : "activity"}
                      size={11}
                      style={{ color: isGap ? "var(--amber-deep)" : "var(--teal)" }}
                    />
                    <span>{r.label}</span>
                  </div>
                  <div className="vital-cell-value">
                    {r.value == null ? "Gap" : `${r.value}${r.unit ? ` ${r.unit}` : ""}`}
                  </div>
                  <div className="vital-cell-baseline">
                    {r.baseline != null
                      ? `Base ${r.baseline}${r.unit ? ` ${r.unit}` : ""}`
                      : isGap
                      ? r.quality
                      : "Baseline ok"}
                  </div>
                </div>
              );
            })}
          </div>

        {/* Footer metadata & weighted components */}
        <div
          style={{
            marginTop: 14,
            paddingTop: 12,
            borderTop: "1px solid var(--border-subtle)",
            display: "flex",
            flexDirection: "column",
            gap: 10,
          }}
        >
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
            <span className="pill pill-teal">
              High confidence · {briefing.confidence_pct}%
            </span>
            <span className="pill pill-neutral">Personal baseline, not an Earth norm</span>
            <span className="pill pill-neutral">Private by default</span>
          </div>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 12,
              flexWrap: "wrap",
              fontSize: "0.78rem",
              color: "var(--text-secondary)",
            }}
          >
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
              <span
                style={{
                  fontSize: "0.72rem",
                  fontWeight: 600,
                  color: "var(--text-muted)",
                }}
              >
                Readiness summary components
              </span>
              <span>
                cognitive <strong>{readiness.components?.cognitive}</strong> · 40%
              </span>
              <span>
                recovery <strong>{readiness.components?.recovery}</strong> · 30%
              </span>
              <span>
                environment <strong>{readiness.components?.environment}</strong> · 20%
              </span>
              <span>
                symptoms <strong>{readiness.components?.symptoms}</strong> · 10%
              </span>
            </div>
            <span style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
              Navigation aid — not a total health score.
            </span>
          </div>
        </div>
      </section>

      {/* Transparent Data Quality Banner */}
      <section className="card card-amber" aria-label="Transparent data quality">
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
            <span className="card-icon-badge amber" aria-hidden="true">
              <Icon name="activity" size={16} />
            </span>
            <div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <strong style={{ fontSize: "0.95rem" }}>Transparent data quality</strong>
                <span className="pill pill-teal tabular-nums">
                  <Icon name="check" size={12} />
                  <span>{dq.coverage_pct}% coverage</span>
                </span>
                <span style={{ fontSize: "0.76rem", color: "var(--text-muted)" }}>
                  Last clean Day {day} · 16:00 ship time
                </span>
              </div>
              <p style={{ margin: "4px 0 0", fontSize: "0.84rem", color: "var(--text-secondary)" }}>
                {dq.summary}
              </p>
            </div>
          </div>

          <button
            type="button"
            className="btn btn-secondary btn-sm"
            aria-expanded={showQualityWhy}
            onClick={() => setShowQualityWhy((v) => !v)}
          >
            <span>Why?</span>
            <Icon
              name="chevron-down"
              size={14}
              style={{
                transform: showQualityWhy ? "rotate(180deg)" : "rotate(0deg)",
                transition: "transform 180ms var(--ease-out)",
              }}
            />
          </button>
        </div>

        {(dq.gaps || []).length > 0 ? (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
            {dq.gaps.map((g) => (
              <span key={g.id || g.label} className="pill pill-amber">
                <Icon name="alert" size={12} />
                <span>{g.label}</span>
              </span>
            ))}
          </div>
        ) : null}

        {showQualityWhy ? (
          <div className="collapsible-body why-drawer" style={{ marginTop: 12, fontSize: "0.81rem" }}>
            <div>
              <strong>Missing data is treated as a signal:</strong> AstroGuard classifies gaps into{" "}
              <code>sensor_off</code>, <code>missing</code>, <code>suspect</code>, or{" "}
              <code>out_of_range</code> and lowers confidence rather than imputing fake normal
              readings.
            </div>
            {(dq.gaps || []).map((g) => (
              <div key={g.id || g.label} className="gap-item">
                <span>
                  <strong>{g.label}</strong> ({g.quality})
                </span>
                <span>{g.window}</span>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      {/* Main Split Workspace: Left Trends & Readings, Right Check-in, Behavioural, MSIDE */}
      <div className="split-main-aside">
        <div className="stack-col">
          {/* Explainable Trends (3 Cards) */}
          <section className="card">
            <div className="card-header">
              <div>
                <h2 className="card-title">Explainable trends</h2>
                <p className="card-subtitle">
                  Compared with your own context-aware baseline, with confidence and gaps shown.
                </p>
              </div>
            </div>

            <div className="grid-3">
              {/* Recovery debt */}
              <div className="card-muted" style={{ background: "#fff" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 6, flexWrap: "wrap" }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>Recovery debt</div>
                    <div style={{ fontSize: "0.66rem", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.06em" }}>
                      PERSONAL INDEX
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    {(() => {
                      const p = getStatusPillProps(rec.status);
                      return (
                        <span className={`pill ${p.cls}`}>
                          <Icon name={p.iconName} size={12} />
                          <span>{p.label}</span>
                        </span>
                      );
                    })()}
                    <div style={{ fontSize: "0.64rem", color: "var(--text-muted)", marginTop: 3 }}>
                      DERIVED
                    </div>
                  </div>
                </div>

                <div className="metric-hero">
                  <div>
                    <span className="metric-big">{Math.round(rec.score)}</span>
                    <span className="metric-unit">/100</span>
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    {Math.round(rec.confidence * 100)}% confidence
                  </span>
                </div>

                <TrendSparkline
                  series={rec.series}
                  personalRange={rec.personal_range}
                  color="#d97706"
                  minY={0}
                  maxY={70}
                />

                <p style={{ margin: "8px 0 4px", fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                  {rec.summary}
                </p>
                <div style={{ fontSize: "0.73rem", color: "var(--text-muted)", marginBottom: 8 }}>
                  Band: Personal early-mission range (10–34)
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {(rec.protocol_refs || []).map((pid) => (
                      <button
                        key={pid}
                        type="button"
                        className="protocol-chip"
                        onClick={() => onOpenProtocol && onOpenProtocol(pid)}
                      >
                        <Icon name="book" size={12} />
                        <span>{pid}</span>
                        <Icon name="chevron-right" size={12} />
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => setOpenTrendWhy((prev) => ({ ...prev, recovery: !prev.recovery }))}
                  >
                    <span>Why</span>
                    <Icon
                      name="chevron-down"
                      size={13}
                      style={{
                        transform: openTrendWhy.recovery ? "rotate(180deg)" : "rotate(0deg)",
                        transition: "transform 180ms var(--ease-out)",
                      }}
                    />
                  </button>
                </div>
                {openTrendWhy.recovery ? (
                  <div className="collapsible-body why-drawer" style={{ fontSize: "0.76rem" }}>
                    {rec.why_details}
                  </div>
                ) : null}
              </div>

              {/* Cognitive readiness */}
              <div className="card-muted" style={{ background: "#fff" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 6, flexWrap: "wrap" }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>Cognitive readiness</div>
                    <div style={{ fontSize: "0.66rem", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.06em" }}>
                      PERSONAL INDEX
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    {(() => {
                      const p = getStatusPillProps(cog.status);
                      return (
                        <span className={`pill ${p.cls}`}>
                          <Icon name={p.iconName} size={12} />
                          <span>{p.label}</span>
                        </span>
                      );
                    })()}
                    <div style={{ fontSize: "0.64rem", color: "var(--text-muted)", marginTop: 3 }}>
                      DERIVED
                    </div>
                  </div>
                </div>

                <div className="metric-hero">
                  <div>
                    <span className="metric-big">{Math.round(cog.score)}</span>
                    <span className="metric-unit">/100</span>
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    {Math.round(cog.confidence * 100)}% confidence
                  </span>
                </div>

                <TrendSparkline
                  series={cog.series}
                  personalRange={cog.personal_range}
                  color="#6d28d9"
                  minY={20}
                  maxY={100}
                />

                <p style={{ margin: "8px 0 4px", fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                  {cog.summary}
                </p>
                <div style={{ fontSize: "0.73rem", color: "var(--text-muted)", marginBottom: 8 }}>
                  Band: Personal early-mission range (75–95)
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {(cog.protocol_refs || []).map((pid) => (
                      <button
                        key={pid}
                        type="button"
                        className="protocol-chip"
                        onClick={() => onOpenProtocol && onOpenProtocol(pid)}
                      >
                        <Icon name="book" size={12} />
                        <span>{pid}</span>
                        <Icon name="chevron-right" size={12} />
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => setOpenTrendWhy((prev) => ({ ...prev, cognitive: !prev.cognitive }))}
                  >
                    <span>Why</span>
                    <Icon
                      name="chevron-down"
                      size={13}
                      style={{
                        transform: openTrendWhy.cognitive ? "rotate(180deg)" : "rotate(0deg)",
                        transition: "transform 180ms var(--ease-out)",
                      }}
                    />
                  </button>
                </div>
                {openTrendWhy.cognitive ? (
                  <div className="collapsible-body why-drawer" style={{ fontSize: "0.76rem" }}>
                    {cog.why_details}
                  </div>
                ) : null}
              </div>

              {/* Radiation · long-term */}
              <div className="card-muted" style={{ background: "#fff" }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 6, flexWrap: "wrap" }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>
                      Radiation · long-term
                    </div>
                    <div style={{ fontSize: "0.66rem", fontWeight: 700, color: "var(--text-muted)", letterSpacing: "0.06em" }}>
                      CUMULATIVE
                    </div>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    {(() => {
                      const p = getStatusPillProps(rad.status);
                      return (
                        <span className={`pill ${p.cls}`}>
                          <Icon name={p.iconName} size={12} />
                          <span>{p.label}</span>
                        </span>
                      );
                    })()}
                    <div style={{ fontSize: "0.64rem", color: "var(--text-muted)", marginTop: 3 }}>
                      MEASURED + DERIVED
                    </div>
                  </div>
                </div>

                <div className="metric-hero">
                  <div>
                    <span className="metric-big">{rad.cumulative_msv}</span>
                    <span className="metric-unit">mSv</span>
                  </div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    {Math.round(rad.confidence * 100)}% confidence
                  </span>
                </div>

                <TrendSparkline
                  series={rad.series}
                  color="#0d7474"
                  minY={0}
                  maxY={18}
                  unit="mSv"
                />

                <p style={{ margin: "8px 0 10px", fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                  {rad.summary}
                </p>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {(rad.protocol_refs || []).map((pid) => (
                      <button
                        key={pid}
                        type="button"
                        className="protocol-chip"
                        onClick={() => onOpenProtocol && onOpenProtocol(pid)}
                      >
                        <Icon name="book" size={12} />
                        <span>{pid}</span>
                        <Icon name="chevron-right" size={12} />
                      </button>
                    ))}
                  </div>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={() => setOpenTrendWhy((prev) => ({ ...prev, radiation: !prev.radiation }))}
                  >
                    <span>Why</span>
                    <Icon
                      name="chevron-down"
                      size={13}
                      style={{
                        transform: openTrendWhy.radiation ? "rotate(180deg)" : "rotate(0deg)",
                        transition: "transform 180ms var(--ease-out)",
                      }}
                    />
                  </button>
                </div>
                {openTrendWhy.radiation ? (
                  <div className="collapsible-body why-drawer" style={{ fontSize: "0.76rem" }}>
                    {rad.why_details}
                  </div>
                ) : null}
              </div>
            </div>
          </section>

          {/* Latest clean readings (6-card grid) */}
          <section className="card">
            <div className="card-header">
              <div>
                <h2 className="card-title">Latest clean readings</h2>
                <p className="card-subtitle">
                  Gaps stay visible as gaps. They are never filled with &ldquo;normal&rdquo;.
                </p>
              </div>
              <span className="pill pill-neutral">6 current</span>
            </div>

            <div className="grid-3">
              {readingOrder.map((key) => {
                const r = readings[key];
                if (!r) return null;
                const isGap = r.value == null || r.quality !== "ok";
                return (
                  <div
                    key={key}
                    className="card-muted"
                    style={{
                      background: isGap ? "var(--amber-card-bg)" : "var(--bg-muted)",
                      borderColor: isGap ? "var(--amber-border)" : "var(--border-subtle)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 6,
                        marginBottom: 8,
                      }}
                    >
                      <span style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-secondary)" }}>
                        {r.label}
                      </span>
                      <span className={`pill ${isGap ? "pill-amber" : "pill-teal"}`}>
                        <Icon name={isGap ? "alert" : "check"} size={12} />
                        <span>{isGap ? r.quality : "Good data"}</span>
                      </span>
                    </div>
                    <div>
                      <span className="metric-big" style={{ fontSize: "1.45rem" }}>
                        {r.value == null ? "Gap" : r.value}
                      </span>
                      {r.value != null ? (
                        <span className="metric-unit">{r.unit}</span>
                      ) : null}
                    </div>
                    <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginTop: 4 }}>
                      {r.subtitle}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Safety Timeline & Delay-tolerant Messaging */}
          <div className="grid-2">
            <section className="card">
              <div className="card-header">
                <h2 className="card-title">Safety timeline</h2>
                <span className="pill pill-neutral">Immutable rules</span>
              </div>
              {activeSos.length === 0 ? (
                <div className="card-muted" style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                  No SOS events up to Day {day}. Deterministic safety rules SR-01..SR-05 remain armed.
                </div>
              ) : (
                <div className="stack-col" style={{ gap: 8 }}>
                  {activeSos.map((s) => (
                    <div
                      key={s.sos_id}
                      className="card-red"
                      style={{
                        border: "1px solid var(--red-border)",
                        borderRadius: 10,
                        padding: "10px 12px",
                      }}
                    >
                      <div style={{ fontWeight: 700, fontSize: "0.84rem", color: "var(--red-text)", display: "flex", alignItems: "center", gap: 6 }}>
                        <Icon name="alert" size={13} />
                        <span>SOS · {s.type || s.sos_type || "medical"}</span>
                      </div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>
                        {s.timestamp_label || s.time_label} ·{" "}
                        {s.onboard_acknowledged ? "acknowledged" : s.status}
                      </div>
                      {s.note ? (
                        <div style={{ fontSize: "0.8rem", marginTop: 4 }}>{s.note}</div>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </section>

            <section className="card">
              <div className="card-header">
                <div>
                  <h2 className="card-title">Delay-tolerant messaging</h2>
                  <p className="card-subtitle">
                    Your message waits safely in the priority queue when Earth is offline.
                  </p>
                </div>
              </div>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ width: "100%" }}
                onClick={() => onNavigate && onNavigate("messages")}
              >
                Open messages
              </button>
              <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginTop: 10 }}>
                Expected light time: ~{earthDelay} min one-way. Audio and charts add transmit time.
              </div>
            </section>
          </div>
        </div>

        {/* Right Aside Column */}
        <aside className="stack-col">
          {/* 1-Minute Check-In Card */}
          <section className="card">
            <div className="card-header">
              <div className="card-title-group">
                <span className="card-icon-badge" aria-hidden="true">
                  <Icon name="clipboard" size={16} />
                </span>
                <div>
                  <h2 className="card-title">1-minute check-in</h2>
                  <p className="card-subtitle">Private by default. Never scored punitively.</p>
                </div>
              </div>
            </div>

            <div className="grid-3" style={{ gap: 8, marginBottom: 12 }}>
              <div className="card-muted" style={{ padding: "10px 8px", textAlign: "center" }}>
                <div style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)" }}>
                  ENERGY
                </div>
                <div className="tabular-nums" style={{ fontSize: "1.1rem", fontWeight: 700 }}>
                  {energyVal}
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>/5</span>
                </div>
              </div>
              <div className="card-muted" style={{ padding: "10px 8px", textAlign: "center" }}>
                <div style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)" }}>
                  MOOD
                </div>
                <div className="tabular-nums" style={{ fontSize: "1.1rem", fontWeight: 700 }}>
                  {moodVal}
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>/5</span>
                </div>
              </div>
              <div className="card-muted" style={{ padding: "10px 8px", textAlign: "center" }}>
                <div style={{ fontSize: "0.65rem", fontWeight: 700, color: "var(--text-muted)" }}>
                  HEADACHE
                </div>
                <div className="tabular-nums" style={{ fontSize: "1.1rem", fontWeight: 700 }}>
                  {headacheVal}
                  <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>/3</span>
                </div>
              </div>
            </div>

            <div className="stack-col" style={{ gap: 8 }}>
              <button
                type="button"
                className="btn btn-primary"
                style={{ width: "100%" }}
                onClick={() => setCheckinOpen(true)}
                data-testid="open-checkin-btn"
              >
                <span>Start 60-second check-in</span>
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                style={{
                  width: "100%",
                  background: "var(--purple-soft)",
                  borderColor: "var(--purple-border)",
                  color: "var(--purple-text)",
                }}
                onClick={() => setPvtOpen(true)}
                data-testid="open-pvt-btn"
              >
                <Icon name="clock" size={14} />
                <span>Reaction test (PVT)</span>
              </button>
            </div>

            <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginTop: 10 }}>
              {userCheckin
                ? `Manual check-in logged for Day ${day}.`
                : "No manual check-in yet in this window. Simulated daily sample shown."}
            </div>
          </section>

          {/* Behavioural Layers */}
          <section className="card">
            <div className="card-header">
              <div className="card-title-group">
                <span className="card-icon-badge" aria-hidden="true">
                  <Icon name="users" size={16} />
                </span>
                <div>
                  <h2 className="card-title">Behavioural layers</h2>
                  <p className="card-subtitle">
                    Passive telemetry, active check-ins, anonymised crew climate.
                  </p>
                </div>
              </div>
            </div>

            <div className="grid-3" style={{ gap: 8, marginBottom: 10 }}>
              <div className="card-muted" style={{ padding: "10px 8px", textAlign: "center" }}>
                <div style={{ fontSize: "0.64rem", fontWeight: 700, color: "var(--text-muted)" }}>
                  ACTIVITY
                </div>
                <div className="tabular-nums" style={{ fontSize: "1.02rem", fontWeight: 700 }}>
                  {behavioral.passive_layer?.activity_ratio ?? 0.93}×
                </div>
              </div>
              <div className="card-muted" style={{ padding: "10px 8px", textAlign: "center" }}>
                <div style={{ fontSize: "0.64rem", fontWeight: 700, color: "var(--text-muted)" }}>
                  ENERGY
                </div>
                <div className="tabular-nums" style={{ fontSize: "1.02rem", fontWeight: 700 }}>
                  {energyVal}/5
                </div>
              </div>
              <div className="card-muted" style={{ padding: "10px 8px", textAlign: "center" }}>
                <div style={{ fontSize: "0.64rem", fontWeight: 700, color: "var(--text-muted)" }}>
                  CLIMATE
                </div>
                <div className="tabular-nums" style={{ fontSize: "1.02rem", fontWeight: 700 }}>
                  {behavioral.climate_layer?.score ?? 3.55}/5
                </div>
              </div>
            </div>

            {behavioral.underreporting_mismatch && behavioral.mismatch_prompt ? (
              <div
                className="card-purple"
                style={{
                  border: "1px solid var(--purple-border)",
                  borderRadius: 10,
                  padding: "10px 12px",
                  marginBottom: 8,
                  fontSize: "0.8rem",
                }}
              >
                <strong style={{ color: "var(--purple-text)" }}>
                  Gentle private check-in prompt:
                </strong>
                <p style={{ margin: "4px 0 8px", color: "var(--text-primary)" }}>
                  {behavioral.mismatch_prompt}
                </p>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => setCheckinOpen(true)}
                >
                  Open private check-in
                </button>
              </div>
            ) : (
              <p style={{ margin: "0 0 6px", fontSize: "0.81rem", color: "var(--text-secondary)" }}>
                {behavioral.summary}
              </p>
            )}
            <div style={{ fontSize: "0.73rem", color: "var(--text-muted)" }}>
              Crew climate is shown only as an anonymous aggregate.
            </div>
          </section>

          {/* What AstroGuard is watching (MSIDE) */}
          <section className="card">
            <div className="card-header">
              <div className="card-title-group">
                <span className="card-icon-badge purple" aria-hidden="true">
                  <Icon name="cpu" size={16} />
                </span>
                <div>
                  <h2 className="card-title">What AstroGuard is watching</h2>
                  <p className="card-subtitle">
                    Multi-signal interactions, with association language only.
                  </p>
                </div>
              </div>
            </div>

            <div className="stack-col" style={{ gap: 10 }}>
              {(msideFindings || []).map((f) => (
                <div key={f.finding_id} className="card-muted">
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 4,
                    }}
                  >
                    <strong style={{ fontSize: "0.84rem" }}>{f.title}</strong>
                    <span className="pill pill-purple tabular-nums">
                      {Math.round((f.confidence ?? 0.85) * 100)}%
                    </span>
                  </div>
                  <p style={{ margin: "0 0 8px", fontSize: "0.79rem", color: "var(--text-secondary)" }}>
                    {f.summary}
                  </p>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {(f.tags || []).map((t) => (
                      <span key={t} className="pill pill-neutral">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <button
              type="button"
              className="btn btn-secondary"
              style={{
                width: "100%",
                marginTop: 12,
                background: "var(--purple-soft)",
                borderColor: "var(--purple-border)",
                color: "var(--purple-text)",
              }}
              onClick={() => onNavigate && onNavigate("advisor")}
            >
              <Icon name="cpu" size={15} />
              <span>Open grounded Advisor</span>
              <Icon name="chevron-right" size={14} />
            </button>
            <div style={{ fontSize: "0.73rem", color: "var(--text-muted)", marginTop: 8 }}>
              Correlation is not causation. Personal findings require human review; environment
              findings require cabin-air confirmation.
            </div>
          </section>
        </aside>
      </div>

      <footer
        style={{
          textAlign: "center",
          fontSize: "0.76rem",
          color: "var(--text-muted)",
          paddingTop: 4,
        }}
      >
        Astronaut self-view is device-scoped to {profile.astronaut_id}. It never exposes another
        crew member&apos;s health detail.
      </footer>

      <CheckinModal
        isOpen={checkinOpen}
        initialValues={userCheckin || { energy: energyVal, mood: moodVal, headache: headacheVal }}
        onClose={() => setCheckinOpen(false)}
        onSave={onSubmitCheckin}
      />
      <PvtReactionModal
        isOpen={pvtOpen}
        baselineMs={readings.pvt_mean_rt?.baseline ?? 251}
        onClose={() => setPvtOpen(false)}
        onSave={onSubmitPvt}
      />
    </div>
  );
}
