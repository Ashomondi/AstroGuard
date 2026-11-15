import React, { useEffect, useState } from "react";
import Icon from "../components/Icon.jsx";

function ProjectionComparisonChart({
  title,
  badgeLabel,
  badgeClass,
  series = [],
  uncertaintyPts = 12,
  caption = "",
}) {
  const [hoverStep, setHoverStep] = useState(null);
  const width = 320;
  const height = 148;
  const padL = 28;
  const padR = 12;
  const padT = 14;
  const padB = 24;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const pts = Array.isArray(series) && series.length > 0 ? series : [];
  if (pts.length === 0) return null;

  const activeIdx =
    hoverStep != null && hoverStep >= 0 && hoverStep < pts.length
      ? hoverStep
      : pts.length - 1;
  const activePt = pts[activeIdx];
  const stepBand = (
    ((uncertaintyPts || 12) * Math.sqrt((activeIdx + 1) / Math.max(1, pts.length)))
  ).toFixed(1);
  const deltaVal = Number(
    (Number(activePt.intervention ?? 0) - Number(activePt.baseline ?? 0)).toFixed(1)
  );

  const allVals = pts.flatMap((p) => [
    Number(p.baseline ?? 0),
    Number(p.intervention ?? 0),
    Number(p.low ?? p.intervention ?? 0),
    Number(p.high ?? p.intervention ?? 0),
  ]);
  const lo = Math.max(0, Math.min(...allVals) - 6);
  const hi = Math.min(100, Math.max(...allVals, lo + 10) + 6);

  const xFor = (i) =>
    pts.length === 1 ? padL + plotW / 2 : padL + (i / (pts.length - 1)) * plotW;
  const yFor = (v) => padT + plotH - ((v - lo) / (hi - lo)) * plotH;
  const colW = pts.length > 1 ? plotW / (pts.length - 1) : plotW;

  const basePath = pts
    .map((p, i) => `${i === 0 ? "M" : "L"} ${xFor(i).toFixed(1)} ${yFor(p.baseline).toFixed(1)}`)
    .join(" ");
  const intPath = pts
    .map(
      (p, i) => `${i === 0 ? "M" : "L"} ${xFor(i).toFixed(1)} ${yFor(p.intervention).toFixed(1)}`
    )
    .join(" ");

  const upperBand = pts.map(
    (p, i) => `${xFor(i).toFixed(1)},${yFor(p.high ?? p.intervention).toFixed(1)}`
  );
  const lowerBand = [...pts]
    .reverse()
    .map((p, idx) => {
      const i = pts.length - 1 - idx;
      return `${xFor(i).toFixed(1)},${yFor(p.low ?? p.intervention).toFixed(1)}`;
    });
  const bandPoints = [...upperBand, ...lowerBand].join(" ");

  const firstDay = pts[0].day;
  const lastDay = pts[pts.length - 1].day;

  return (
    <div className="card">
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 8,
          marginBottom: 8,
          flexWrap: "wrap",
        }}
      >
        <strong style={{ fontSize: "0.94rem" }}>{title}</strong>
        <span className={`pill ${badgeClass}`}>{badgeLabel}</span>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="sparkline-svg"
        role="img"
        aria-label={`${title} Day ${firstDay} to Day ${lastDay}`}
        onMouseLeave={() => setHoverStep(null)}
      >
        {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
          const gy = padT + plotH - frac * plotH;
          return (
            <line
              key={frac}
              x1={padL}
              y1={gy}
              x2={width - padR}
              y2={gy}
              stroke="#e9efef"
              strokeWidth="1"
            />
          );
        })}

        <polygon points={bandPoints} fill="rgba(13, 116, 116, 0.11)" />

        <line
          x1={xFor(activeIdx)}
          y1={padT}
          x2={xFor(activeIdx)}
          y2={padT + plotH}
          stroke="rgba(13, 116, 116, 0.42)"
          strokeWidth="1.2"
          strokeDasharray="3 2"
        />

        <path
          d={basePath}
          fill="none"
          stroke="#94a3b8"
          strokeWidth="2"
          strokeDasharray="4 4"
        />
        <path
          d={intPath}
          fill="none"
          stroke="#0d7474"
          strokeWidth="2.4"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {pts.map((p, i) => {
          const isActive = i === activeIdx;
          return (
            <g key={p.day}>
              {isActive ? (
                <circle
                  cx={xFor(i)}
                  cy={yFor(p.baseline)}
                  r="3.2"
                  fill="#ffffff"
                  stroke="#64748b"
                  strokeWidth="1.6"
                />
              ) : null}
              <circle
                cx={xFor(i)}
                cy={yFor(p.intervention)}
                r={isActive ? "4.2" : "2.6"}
                fill={isActive ? "#0d7474" : "#ffffff"}
                stroke="#0d7474"
                strokeWidth="1.8"
              >
                <title>{`Day ${p.day}: baseline ${p.baseline} vs intervention ${p.intervention}`}</title>
              </circle>
              <rect
                x={Math.max(padL, xFor(i) - colW / 2)}
                y={padT}
                width={colW}
                height={plotH}
                fill="transparent"
                style={{ cursor: "ew-resize" }}
                onMouseEnter={() => setHoverStep(i)}
                onClick={() => setHoverStep(i)}
              />
            </g>
          );
        })}

        <text x={padL - 5} y={padT + 4} textAnchor="end" fontSize="8.5" fill="#6c8080">
          {Math.round(hi)}
        </text>
        <text x={padL - 5} y={padT + plotH + 3} textAnchor="end" fontSize="8.5" fill="#6c8080">
          {Math.round(lo)}
        </text>
        <text x={padL} y={height - 5} textAnchor="start" fontSize="9" fill="#6c8080">
          Day {firstDay}
        </text>
        <text x={width - padR} y={height - 5} textAnchor="end" fontSize="9" fill="#6c8080">
          Day {lastDay}
        </text>
      </svg>

      <div className="whatif-scrubber-bar" style={{ marginTop: 8 }}>
        <span>
          <strong>Day {activePt.day}</strong> (+{activeIdx + 1}d)
        </span>
        <span>
          Base <strong>{activePt.baseline}</strong> vs Int{" "}
          <strong style={{ color: "var(--teal)" }}>{activePt.intervention}</strong> (Δ{" "}
          {deltaVal >= 0 ? "+" : ""}
          {deltaVal}, ±{stepBand})
        </span>
      </div>

      <div
        style={{
          display: "flex",
          gap: 14,
          fontSize: "0.76rem",
          color: "var(--text-secondary)",
          marginTop: 6,
          alignItems: "center",
        }}
      >
        <span>
          <span style={{ color: "#94a3b8", fontWeight: 700 }}>- -</span> Current trajectory
        </span>
        <span>
          <span style={{ color: "var(--teal)", fontWeight: 700 }}>—</span> Intervention
        </span>
      </div>
      <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 4 }}>
        Uncertainty ±{uncertaintyPts} points by day {pts.length}. {caption}
      </div>
    </div>
  );
}

export default function AdvisorView({
  state,
  onAskAdvisor,
  onRunWhatIf,
  onOpenProtocol,
}) {
  const [activeTab, setActiveTab] = useState("ask"); // ask | whatif
  const [questionInput, setQuestionInput] = useState("");
  const [qaHistory, setQaHistory] = useState([]);
  const [asking, setAsking] = useState(false);

  // What-If Sandbox default intervention baseline
  const [sleepPerNight, setSleepPerNight] = useState(7.5);
  const [workloadAdj, setWorkloadAdj] = useState(-1.0);
  const [ventilationPct, setVentilationPct] = useState(130);
  const [recoveryBlocks, setRecoveryBlocks] = useState(2);
  const [horizonDays, setHorizonDays] = useState(7);
  const [projection, setProjection] = useState(null);

  const day = state?.day ?? 23;
  const crewId = state?.selected_crew_id ?? "ast-01";
  const advisor = state?.advisor;
  const safetyActive = Boolean(
    state?.astronaut?.readiness?.safety_active || state?.safety?.has_critical
  );

  // Recompute What-If projection whenever sliders, day, or crew change
  useEffect(() => {
    let active = true;
    const timer = setTimeout(async () => {
      if (!onRunWhatIf) return;
      const res = await onRunWhatIf({
        sleep_per_night: sleepPerNight,
        workload_adjustment: workloadAdj,
        cabin_ventilation_pct: ventilationPct,
        recovery_blocks: recoveryBlocks,
        horizon_days: horizonDays,
        day,
        crewId,
      });
      if (active && res) setProjection(res);
    }, 60);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [sleepPerNight, workloadAdj, ventilationPct, recoveryBlocks, horizonDays, day, crewId, onRunWhatIf]);

  const handleSubmitQuestion = async (rawQ) => {
    const q = String(rawQ ?? questionInput).trim();
    if (!q || asking) return;
    setAsking(true);
    if (rawQ === undefined) setQuestionInput("");
    try {
      const reply = await onAskAdvisor?.(q);
      if (reply) {
        setQaHistory((prev) => [
          ...prev,
          {
            id: `qa-${Date.now()}`,
            question: q,
            reply,
          },
        ]);
      }
    } finally {
      setAsking(false);
    }
  };

  const observations = advisor?.observations || [];
  const suggestedQuestions = advisor?.suggested_questions || [
    "Why am I feeling more tired after exercise?",
    "Is the Lab air affecting the crew?",
    "What should I do next?",
    "How confident are you in this?",
    "What if I sleep 5 hours for the next 5 days?",
    "Could this be a medical diagnosis?",
  ];
  const hardBoundaries = advisor?.hard_boundaries || [
    "Never diagnoses or prescribes.",
    "Never downgrades a deterministic alert.",
    "Never fills a sensor gap with a normal value.",
    "Cites only approved protocols.",
  ];

  return (
    <div className="stack-col" data-testid="advisor-view">
      <header className="page-header">
        <div>
          <div className="page-eyebrow">GROUNDED OFFLINE INTELLIGENCE</div>
          <h1>AstroGuard Advisor</h1>
          <p className="page-subtitle">
            Answers are assembled only from engine outputs and the approved in-flight protocol
            library. It says &ldquo;I don&apos;t know&rdquo; when data is missing and never
            diagnoses or prescribes.
          </p>
        </div>
        <div className="page-header-pills">
          <span className="pill pill-purple">Offline-first</span>
          <span className="pill pill-neutral">No generative cloud model</span>
        </div>
      </header>

      {/* Sub-tabs */}
      <div className="subtabs" role="tablist" aria-label="AstroGuard Advisor modes">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "ask"}
          className={`subtab ${activeTab === "ask" ? "active" : ""}`}
          onClick={() => setActiveTab("ask")}
          data-testid="tab-ask-astroguard"
        >
          <Icon name="message" size={15} />
          <span>Ask AstroGuard</span>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "whatif"}
          className={`subtab ${activeTab === "whatif" ? "active" : ""}`}
          onClick={() => setActiveTab("whatif")}
          data-testid="tab-what-if"
        >
          <Icon name="sliders" size={15} />
          <span>What-if sandbox</span>
        </button>
      </div>

      {activeTab === "ask" ? (
        <div className="split-main-aside">
          {/* Main Q&A & Briefing Column */}
          <div className="stack-col">
            <section className="card">
              <div className="card-header">
                <div className="card-title-group">
                  <span className="card-icon-badge purple" aria-hidden="true">
                    <Icon name="cpu" size={16} />
                  </span>
                  <div>
                    <h2 className="card-title">Proactive briefing</h2>
                    <p className="card-subtitle">
                      Offline deterministic retrieval over engine outputs and approved protocol
                      library.
                    </p>
                  </div>
                </div>
                <span className="pill pill-teal">
                  High confidence · {advisor?.confidence_pct ?? 95}%
                </span>
              </div>

              {safetyActive ? (
                <div
                  className="card-red"
                  style={{
                    border: "1px solid var(--red-border)",
                    borderRadius: 10,
                    padding: "10px 13px",
                    fontSize: "0.83rem",
                    color: "var(--red-text)",
                    marginBottom: 14,
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <Icon name="shield" size={15} />
                  <span>
                    Deterministic safety alerts cannot be downgraded, delayed, or overridden by
                    the Advisor.
                  </span>
                </div>
              ) : null}

              <p style={{ margin: "0 0 16px", fontSize: "0.93rem", lineHeight: 1.55 }}>
                {advisor?.briefing?.what_changed}{" "}
                {advisor?.briefing?.how_sure_why}{" "}
                <strong>Next:</strong> {advisor?.briefing?.single_best_next_step}
              </p>

              {/* 4 Contributing Observations */}
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: 10,
                }}
              >
                <span
                  style={{
                    fontSize: "0.7rem",
                    fontWeight: 700,
                    letterSpacing: "0.08em",
                    color: "var(--text-muted)",
                  }}
                >
                  CONTRIBUTING OBSERVATIONS
                </span>
                <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                  {observations.length} cards
                </span>
              </div>

              <div className="grid-2" style={{ gap: 12 }}>
                {observations.map((obs) => (
                  <div
                    key={obs.id}
                    className="card-muted"
                    style={{
                      background: "#ffffff",
                      display: "flex",
                      flexDirection: "column",
                      gap: 8,
                    }}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 6, flexWrap: "wrap" }}>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: "0.88rem" }}>{obs.title}</div>
                        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: 2, display: "inline-flex", alignItems: "center", gap: 4 }}>
                          <Icon name="clock" size={12} />
                          <span>{obs.window}</span>
                        </div>
                      </div>
                      <span className="pill pill-teal">
                        <Icon name="check" size={12} />
                        <span>Good data</span>
                      </span>
                    </div>

                    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
                      <span className="metric-big" style={{ fontSize: "1.35rem" }}>
                        {obs.value ?? "Gap"}
                      </span>
                      <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                        {obs.unit} · personal baseline {obs.baseline}
                      </span>
                    </div>

                    <p style={{ margin: 0, fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                      {obs.note}
                    </p>

                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span
                        style={{
                          fontSize: "0.7rem",
                          fontWeight: 600,
                          color: "var(--text-muted)",
                        }}
                      >
                        Confidence
                      </span>
                      <div className="confidence-bar">
                        <div
                          className="confidence-fill"
                          style={{
                            width: "100%",
                            transform: `scaleX(${Math.max(0, Math.min(1, (obs.confidence ?? 85) / 100))})`,
                          }}
                        />
                      </div>
                      <span className="tabular-nums" style={{ fontSize: "0.75rem", fontWeight: 700 }}>
                        {obs.confidence ?? 85}%
                      </span>
                    </div>

                    <div style={{ display: "flex", gap: 5, flexWrap: "wrap" }}>
                      {(obs.protocol_refs || []).map((pid) => (
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
                ))}
              </div>

              {/* Approved Next Steps Strip */}
              <div
                className="card-muted"
                style={{
                  marginTop: 14,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 10,
                  flexWrap: "wrap",
                }}
              >
                <div>
                  <div
                    style={{
                      fontSize: "0.72rem",
                      fontWeight: 600,
                      color: "var(--text-muted)",
                      marginBottom: 6,
                    }}
                  >
                    Approved next steps
                  </div>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                    {(advisor?.protocol_refs || ["PROT-REC-01", "PROT-REC-02"]).map((pid) => (
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
                <span className="pill pill-teal">Protocol library</span>
              </div>

              <div
                style={{
                  marginTop: 12,
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  gap: 8,
                  flexWrap: "wrap",
                  fontSize: "0.73rem",
                  color: "var(--text-muted)",
                }}
              >
                <span>Decision support only. Not a diagnosis. Not a prescription.</span>
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  <span className="pill pill-neutral">post-exercise adapter</span>
                  <span className="pill pill-neutral">wristband</span>
                  <span className="pill pill-neutral">1-minute daily test</span>
                </div>
              </div>
            </section>

            {/* Q&A Conversation Replies */}
            {qaHistory.map((item) => (
              <section
                key={item.id}
                className="card"
                style={{ borderColor: "var(--purple-border)" }}
                data-testid="advisor-qa-reply"
              >
                <div style={{ fontSize: "0.78rem", fontWeight: 700, color: "var(--purple-text)" }}>
                  YOU ASKED
                </div>
                <div style={{ fontWeight: 600, fontSize: "0.94rem", margin: "2px 0 10px" }}>
                  {item.question}
                </div>
                <div
                  className="card-muted"
                  style={{ background: "var(--purple-soft)", borderColor: "var(--purple-border)" }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 6,
                      flexWrap: "wrap",
                    }}
                  >
                    <strong style={{ fontSize: "0.84rem", color: "var(--purple-text)" }}>
                      AstroGuard Grounded Reply
                    </strong>
                    <span className="pill pill-teal tabular-nums">
                      {Math.round((item.reply.confidence ?? 0.8) * 100)}% confidence
                    </span>
                  </div>
                  <p style={{ margin: "0 0 8px", fontSize: "0.88rem", lineHeight: 1.5 }}>
                    {item.reply.answer}
                  </p>
                  <div
                    style={{
                      display: "flex",
                      gap: 6,
                      flexWrap: "wrap",
                      alignItems: "center",
                      justifyContent: "space-between",
                    }}
                  >
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      {(item.reply.protocol_refs || []).map((pid) => (
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
                    <span style={{ fontSize: "0.73rem", color: "var(--text-muted)" }}>
                      Window: {item.reply.evidence_window}
                    </span>
                  </div>
                </div>
              </section>
            ))}

            {/* Ask Input Box */}
            <form
              className="card"
              onSubmit={(e) => {
                e.preventDefault();
                handleSubmitQuestion();
              }}
            >
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <input
                  type="text"
                  value={questionInput}
                  onChange={(e) => setQuestionInput(e.target.value)}
                  placeholder="Ask about sleep, recovery, the Lab air, symptoms, confidence, or what to do next..."
                  aria-label="Ask AstroGuard Advisor"
                  style={{
                    flex: 1,
                    minHeight: 44,
                    border: "1px solid var(--border-subtle)",
                    borderRadius: 10,
                    padding: "8px 12px",
                    fontSize: "0.88rem",
                  }}
                />
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={!questionInput.trim() || asking}
                  aria-label="Send question"
                >
                  {asking ? <span>…</span> : <Icon name="send" size={15} />}
                </button>
              </div>
              <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginTop: 8 }}>
                Every reply carries evidence windows, confidence, and protocol citations. Not a
                diagnosis.
              </div>
            </form>
          </div>

          {/* Right Column */}
          <aside className="stack-col">
            <section className="card">
              <div className="card-header">
                <div className="card-title-group">
                  <span className="card-icon-badge purple" aria-hidden="true">
                    ?
                  </span>
                  <div>
                    <h2 className="card-title">Suggested questions</h2>
                    <p className="card-subtitle">
                      Try one. The answer will cite the exact engine window.
                    </p>
                  </div>
                </div>
              </div>

              <div className="stack-col" style={{ gap: 8 }}>
                {suggestedQuestions.map((q) => (
                  <button
                    key={q}
                    type="button"
                    className="btn btn-secondary"
                    style={{
                      width: "100%",
                      justifyContent: "flex-start",
                      textAlign: "left",
                      fontWeight: 500,
                      fontSize: "0.82rem",
                      padding: "9px 12px",
                    }}
                    onClick={() => handleSubmitQuestion(q)}
                  >
                    <Icon name="chevron-right" size={14} style={{ color: "var(--purple)" }} />
                    <span>{q}</span>
                  </button>
                ))}
              </div>
            </section>

            <section className="card card-purple">
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                <Icon name="alert" size={15} style={{ color: "var(--purple)" }} />
                <strong style={{ fontSize: "0.92rem" }}>Hard boundaries</strong>
              </div>
              <ul
                style={{
                  margin: 0,
                  paddingLeft: 18,
                  fontSize: "0.81rem",
                  color: "var(--text-secondary)",
                  display: "flex",
                  flexDirection: "column",
                  gap: 6,
                }}
              >
                {hardBoundaries.map((b) => (
                  <li key={b}>{b}</li>
                ))}
              </ul>
            </section>

            <section className="card">
              <strong style={{ fontSize: "0.92rem" }}>Current evidence window</strong>
              <p
                style={{
                  margin: "6px 0 12px",
                  fontSize: "0.81rem",
                  color: "var(--text-secondary)",
                  lineHeight: 1.48,
                }}
              >
                Day {day} · 16:00 ship time. Recovery, cognition, habitat and behavioural outputs are
                recomputed as-of this mission time. Confidence reflects data coverage.
              </p>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <span className="pill pill-neutral tabular-nums">
                  {advisor?.confidence_pct ?? 91}% overall data confidence
                </span>
                <span className="pill pill-amber tabular-nums">
                  {advisor?.gap_count ?? 1} recent gaps
                </span>
              </div>
            </section>
          </aside>
        </div>
      ) : (
        /* What-If Sandbox Tab */
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: 18,
            alignItems: "flex-start",
          }}
        >
          {/* Left Control Sliders */}
          <section className="card" style={{ flex: "1 1 290px", maxWidth: "100%" }}>
            <div className="card-header">
              <div className="card-title-group">
                <span className="card-icon-badge purple" aria-hidden="true">
                  <Icon name="sliders" size={16} />
                </span>
                <div>
                  <h2 className="card-title">What-if intervention</h2>
                  <p className="card-subtitle">
                    Compare the current trajectory with a transparent {horizonDays}-day projection.
                  </p>
                </div>
              </div>
            </div>

            <div className="slider-row">
              <div className="slider-row-head">
                <span>Sleep per night</span>
                <span className="slider-row-value">{sleepPerNight.toFixed(1)} h</span>
              </div>
              <input
                type="range"
                min={4}
                max={10}
                step={0.5}
                value={sleepPerNight}
                aria-label="Sleep per night hours"
                onChange={(e) => setSleepPerNight(Number(e.target.value))}
              />
            </div>

            <div className="slider-row">
              <div className="slider-row-head">
                <span>Workload adjustment</span>
                <span className="slider-row-value">
                  {workloadAdj > 0 ? `+${workloadAdj}` : workloadAdj}
                </span>
              </div>
              <input
                type="range"
                min={-2}
                max={2}
                step={0.5}
                value={workloadAdj}
                aria-label="Workload adjustment"
                onChange={(e) => setWorkloadAdj(Number(e.target.value))}
              />
              <span className="slider-row-hint">-2 = much lighter, +2 = heavier</span>
            </div>

            <div className="slider-row">
              <div className="slider-row-head">
                <span>Cabin ventilation</span>
                <span className="slider-row-value">{ventilationPct} %</span>
              </div>
              <input
                type="range"
                min={50}
                max={200}
                step={10}
                value={ventilationPct}
                aria-label="Cabin ventilation percent"
                onChange={(e) => setVentilationPct(Number(e.target.value))}
              />
              <span className="slider-row-hint">Affects projected CO₂ exposure only</span>
            </div>

            <div className="slider-row">
              <div className="slider-row-head">
                <span>Recovery blocks</span>
                <span className="slider-row-value">{recoveryBlocks} /week</span>
              </div>
              <input
                type="range"
                min={0}
                max={7}
                step={1}
                value={recoveryBlocks}
                aria-label="Recovery blocks per week"
                onChange={(e) => setRecoveryBlocks(Number(e.target.value))}
              />
            </div>

            <div className="slider-row">
              <div className="slider-row-head">
                <span>Horizon</span>
                <span className="slider-row-value">{horizonDays} days</span>
              </div>
              <input
                type="range"
                min={1}
                max={14}
                step={1}
                value={horizonDays}
                aria-label="Projection horizon days"
                onChange={(e) => setHorizonDays(Number(e.target.value))}
              />
            </div>

            <div
              className="card-purple"
              style={{
                border: "1px solid var(--purple-border)",
                borderRadius: 12,
                padding: "12px 14px",
                marginTop: 10,
                fontSize: "0.78rem",
                color: "var(--text-secondary)",
              }}
            >
              <strong style={{ display: "inline-flex", alignItems: "center", gap: 6, color: "var(--purple-text)", marginBottom: 4 }}>
                <Icon name="compass" size={14} />
                <span>Not a prediction</span>
              </strong>
              <div>
                A transparent extrapolation of your own trend plus explicitly labelled effects.
                Uncertainty is shown; clinical review is still required.
              </div>
            </div>
          </section>

          {/* Right Projections & Charts */}
          <div className="stack-col" style={{ flex: "2 1 460px", minWidth: 0 }}>
            {projection ? (
              <>
                <section className="card">
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                    <span className="pill pill-purple">
                      <Icon name="sliders" size={12} />
                      <span>Exploratory projection</span>
                    </span>
                    <span className="pill pill-neutral tabular-nums">
                      {Math.round((projection.confidence ?? 0.44) * 100)}% confidence
                    </span>
                  </div>
                  <p style={{ margin: "0 0 14px", fontSize: "0.93rem", lineHeight: 1.5 }}>
                    {projection.summary}
                  </p>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                    <div className="card-muted" style={{ minWidth: 118, textAlign: "center" }}>
                      <div style={{ fontSize: "0.66rem", fontWeight: 700, color: "var(--text-muted)" }}>
                        RECOVERY DEBT
                      </div>
                      <div className="tabular-nums" style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--teal)" }}>
                        {projection.deltas?.recovery_debt > 0 ? "+" : ""}
                        {projection.deltas?.recovery_debt}
                      </div>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>pts</div>
                    </div>

                    <div className="card-muted" style={{ minWidth: 118, textAlign: "center" }}>
                      <div style={{ fontSize: "0.66rem", fontWeight: 700, color: "var(--text-muted)" }}>
                        COGNITIVE
                      </div>
                      <div className="tabular-nums" style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--teal)" }}>
                        {projection.deltas?.cognitive_readiness >= 0 ? "+" : ""}
                        {projection.deltas?.cognitive_readiness}
                      </div>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>pts</div>
                    </div>

                    <div className="card-muted" style={{ minWidth: 118, textAlign: "center" }}>
                      <div style={{ fontSize: "0.66rem", fontWeight: 700, color: "var(--text-muted)" }}>
                        CO₂ EXPOSURE
                      </div>
                      <div className="tabular-nums" style={{ fontSize: "1.25rem", fontWeight: 700, color: "var(--teal)" }}>
                        {projection.deltas?.co2_exposure > 0 ? "+" : ""}
                        {projection.deltas?.co2_exposure}
                      </div>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>ppm</div>
                    </div>
                  </div>
                </section>

                <div className="grid-2">
                  <ProjectionComparisonChart
                    title="Recovery debt projection"
                    badgeLabel="Lower is better"
                    badgeClass="pill-amber"
                    series={projection.recovery_series}
                    uncertaintyPts={projection.uncertainty?.recovery_debt_pts ?? 13.7}
                    caption={`Inputs: ${sleepPerNight}h sleep, workload ${workloadAdj}, ${recoveryBlocks} blocks/week.`}
                  />
                  <ProjectionComparisonChart
                    title="Cognitive readiness projection"
                    badgeLabel="Higher is better"
                    badgeClass="pill-purple"
                    series={projection.cognitive_series}
                    uncertaintyPts={projection.uncertainty?.cognitive_readiness_pts ?? 12}
                    caption="A PVT re-test after the intervention is the only way to confirm."
                  />
                </div>

                <section className="card">
                  <h3 style={{ margin: "0 0 10px", fontSize: "0.95rem" }}>
                    Assumptions shown, not hidden
                  </h3>
                  <ul
                    style={{
                      margin: "0 0 12px",
                      paddingLeft: 18,
                      fontSize: "0.82rem",
                      color: "var(--text-secondary)",
                      display: "flex",
                      flexDirection: "column",
                      gap: 5,
                    }}
                  >
                    {(projection.assumptions || []).map((a) => (
                      <li key={a}>{a}</li>
                    ))}
                  </ul>
                  <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
                    {(projection.protocol_refs || []).map((pid) => (
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
                    <span className="pill pill-amber">
                      <Icon name="wind" size={12} />
                      <span>{ventilationPct}% ventilation</span>
                    </span>
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                    {projection.disclaimer}
                  </div>
                </section>
              </>
            ) : (
              <div className="card">Computing counterfactual projection…</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
