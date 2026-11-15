import React from "react";
import Icon from "../components/Icon.jsx";

const NORMAL_SWITCHES = [
  {
    key: "physio",
    title: "Physiological detail",
    desc: "Heart rate, HRV, SpO₂, sleep, symptoms, radiation dose.",
  },
  {
    key: "cognitive",
    title: "Cognitive detail",
    desc: "PVT reaction time, lapses, self-reported mood and energy.",
  },
  {
    key: "behaviour",
    title: "Behavioural signals",
    desc: "Passive activity, messaging cadence, under-reporting cross-check.",
  },
  {
    key: "habitat",
    title: "Environment context",
    desc: "Your zone exposure and habitat correlation context.",
  },
  {
    key: "ground_sharing",
    title: "Share summaries and consented charts with Ground",
    desc: "Ground Support still never gets raw crew health unless this is on and you explicitly attach a chart.",
  },
];

const EMERGENCY_SWITCHES = [
  {
    key: "physio",
    title: "Emergency physiological",
    desc: "Allowed only while a deterministic critical rule is active; expires in 2 hours.",
  },
  {
    key: "cognitive",
    title: "Emergency cognitive",
    desc: "Reveal PVT and mood/energy context during a critical safety event.",
  },
  {
    key: "behaviour",
    title: "Emergency behavioural",
    desc: "Reveal passive behavioural patterns during a critical safety event.",
  },
];

export default function PrivacyConsentView({
  state,
  onUpdateConsent,
  readOnly = false,
}) {
  const crewId = state?.selected_crew_id || "ast-01";
  const crewMember =
    (state?.crew_roster || []).find((c) => c.astronaut_id === crewId) ||
    { name: "Cmdr. Elena Vasquez", astronaut_id: crewId };

  const profiles = state?.consent_matrix || {};
  const profile = profiles[crewId] || {
    normal: {
      physio: true,
      cognitive: true,
      behaviour: true,
      habitat: true,
      ground_sharing: true,
    },
    emergency: {
      physio: true,
      cognitive: true,
      behaviour: true,
      habitat: true,
      ground_sharing: true,
    },
  };

  const accessLog = Array.isArray(state?.access_log) ? state.access_log : [];
  const isOwner = state?.viewer_role === "Astronaut" && !readOnly;

  const handleToggle = (mode, scope, currentVal) => {
    if (!isOwner || !onUpdateConsent) return;
    onUpdateConsent({
      astronautId: crewId,
      mode,
      scope,
      enabled: !currentVal,
    });
  };

  return (
    <div className="stack-col" data-testid="privacy-consent-view">
      <header className="page-header">
        <div>
          <div className="page-eyebrow">YOU OWN YOUR DATA</div>
          <h1>Privacy &amp; consent</h1>
          <p className="page-subtitle">
            {isOwner
              ? "You own these switches. Changes apply immediately and are logged."
              : `Viewing ${crewMember.name}'s consent profile (read-only). Only the astronaut can change these switches.`}
          </p>
        </div>
        <div className="page-header-pills">
          <span className="pill pill-teal">
            <Icon name="shield" size={12} />
            <span>Astronaut-owned</span>
          </span>
          <span className="pill pill-neutral">
            <Icon name="clipboard" size={12} />
            <span>Every access logged</span>
          </span>
        </div>
      </header>

      <div className="split-main-aside">
        {/* Left Main Column */}
        <div className="stack-col">
          {/* Normal Sharing */}
          <section className="card" aria-label="Normal sharing">
            <div className="card-header">
              <div>
                <h2 className="card-title">Normal sharing</h2>
                <p className="card-subtitle">
                  Health Officer routine access. Changes apply immediately and are logged.
                </p>
              </div>
              <span className="pill pill-teal">
                <Icon name="lock" size={12} />
                <span>You own this</span>
              </span>
            </div>

            <div className="stack-col" style={{ gap: 10 }}>
              {NORMAL_SWITCHES.map((sw) => {
                const isOn = Boolean(profile.normal?.[sw.key]);
                return (
                  <div
                    key={sw.key}
                    className="card-muted"
                    style={{
                      background: "#ffffff",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 14,
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>{sw.title}</div>
                      <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: 2 }}>
                        {sw.desc}
                      </div>
                    </div>

                    <button
                      type="button"
                      role="switch"
                      aria-checked={isOn}
                      aria-label={`${sw.title} (${isOn ? "On" : "Off"})`}
                      disabled={!isOwner}
                      className={`switch has-knob ${isOn ? "on" : ""}`}
                      onClick={() => handleToggle("normal", sw.key, isOn)}
                      data-testid={`consent-normal-${sw.key}`}
                      style={{
                        opacity: isOwner ? 1 : 0.65,
                        cursor: isOwner ? "pointer" : "not-allowed",
                      }}
                    >
                      <span className="switch-knob" />
                    </button>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Emergency Sharing */}
          <section className="card card-red" aria-label="Emergency sharing">
            <div className="card-header">
              <div>
                <h2 className="card-title">Emergency sharing</h2>
                <p className="card-subtitle">
                  Only usable while a deterministic critical safety rule is active. The override
                  expires in 2 hours and is visible to you.
                </p>
              </div>
              <span className="pill pill-red">
                <Icon name="clock" size={12} />
                <span>Time-limited</span>
              </span>
            </div>

            <div className="stack-col" style={{ gap: 10 }}>
              {EMERGENCY_SWITCHES.map((sw) => {
                const isOn = Boolean(profile.emergency?.[sw.key]);
                return (
                  <div
                    key={sw.key}
                    className="card-muted"
                    style={{
                      background: "#ffffff",
                      borderColor: "var(--red-border)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 14,
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700, fontSize: "0.9rem" }}>{sw.title}</div>
                      <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)", marginTop: 2 }}>
                        {sw.desc}
                      </div>
                    </div>

                    <button
                      type="button"
                      role="switch"
                      aria-checked={isOn}
                      aria-label={`${sw.title} (${isOn ? "On" : "Off"})`}
                      disabled={!isOwner}
                      className={`switch has-knob emergency ${isOn ? "on" : ""}`}
                      onClick={() => handleToggle("emergency", sw.key, isOn)}
                      data-testid={`consent-emergency-${sw.key}`}
                      style={{
                        opacity: isOwner ? 1 : 0.65,
                        cursor: isOwner ? "pointer" : "not-allowed",
                      }}
                    >
                      <span className="switch-knob" />
                    </button>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Plain-language promise */}
          <div className="card-muted" style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
            <strong>Plain-language promise:</strong> turning off a category lowers what other
            people can see. It does not turn off emergency safety rules, and it never causes your
            own data to be deleted or scored against you.
          </div>

          {/* What stays on board */}
          <section className="card">
            <div className="card-header">
              <div className="card-title-group">
                <span className="card-icon-badge" aria-hidden="true">
                  <Icon name="archive" size={16} />
                </span>
                <div>
                  <h2 className="card-title">What stays on board</h2>
                  <p className="card-subtitle">
                    The append-only mission store, engine outputs, check-ins, messages and SOS
                    packets stay in the local database. The Earth link only receives the packets you
                    or the safety rules create. Gaps are transmitted as gaps — never as normal
                    values.
                  </p>
                </div>
              </div>
            </div>

            <div className="grid-3">
              <div className="card-muted">
                <div style={{ fontWeight: 700, fontSize: "0.83rem", marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
                  <Icon name="database" size={14} style={{ color: "var(--teal)" }} />
                  <span>Append-only store</span>
                </div>
                <div style={{ fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                  Sensors and actions are never overwritten in place.
                </div>
              </div>
              <div className="card-muted">
                <div style={{ fontWeight: 700, fontSize: "0.83rem", marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
                  <Icon name="users" size={14} style={{ color: "var(--teal)" }} />
                  <span>Tiered roles</span>
                </div>
                <div style={{ fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                  Health Officer, Systems Engineer, Ground Support each get a different scope.
                </div>
              </div>
              <div className="card-muted">
                <div style={{ fontWeight: 700, fontSize: "0.83rem", marginBottom: 4, display: "flex", alignItems: "center", gap: 6 }}>
                  <Icon name="clipboard" size={14} style={{ color: "var(--teal)" }} />
                  <span>Audit</span>
                </div>
                <div style={{ fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                  Access, scope, emergency flag, reason and time are recorded.
                </div>
              </div>
            </div>
          </section>

          {/* Access log */}
          <section className="card" aria-label="Access log">
            <div className="card-header">
              <div>
                <h2 className="card-title">Access log</h2>
                <p className="card-subtitle">
                  Complete access log for your records. Anonymised habitat aggregates are included
                  but do not identify you.
                </p>
              </div>
              <span className="pill pill-neutral tabular-nums">
                {accessLog.length} entries
              </span>
            </div>

            <div className="stack-col" style={{ gap: 10 }}>
              {accessLog.map((entry) => (
                <div
                  key={entry.log_id}
                  className="card-muted"
                  style={{
                    background: entry.emergency_override ? "var(--red-card-bg)" : "var(--bg-muted)",
                    borderColor: entry.emergency_override
                      ? "var(--red-border)"
                      : "var(--border-subtle)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      gap: 10,
                      flexWrap: "wrap",
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700, fontSize: "0.86rem" }}>
                        {entry.actor_role} ·{" "}
                        <span style={{ fontWeight: 500, color: "var(--text-secondary)" }}>
                          {entry.access_type}
                        </span>
                      </div>
                      <div style={{ fontSize: "0.74rem", color: "var(--text-muted)", marginTop: 2 }}>
                        {entry.timestamp_label} · {entry.target_astronaut_id} · scope {entry.scope}
                      </div>
                    </div>

                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <span
                        className={`pill ${
                          entry.emergency_override ? "pill-red" : "pill-neutral"
                        }`}
                      >
                        {entry.mode}
                      </span>
                      <span className="pill pill-neutral">{entry.scope}</span>
                    </div>
                  </div>
                  <p style={{ margin: "6px 0 4px", fontSize: "0.81rem", color: "var(--text-secondary)" }}>
                    {entry.reason}
                  </p>
                  {Array.isArray(entry.fields) && entry.fields.length > 0 ? (
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                      Fields: {entry.fields.join(", ")}
                    </div>
                  ) : null}
                </div>
              ))}
            </div>
          </section>
        </div>

        {/* Right Aside Column */}
        <aside className="stack-col">
          <section className="card">
            <div className="card-header">
              <div className="card-title-group">
                <span className="card-icon-badge purple" aria-hidden="true">
                  <Icon name="shield" size={16} />
                </span>
                <div>
                  <h2 className="card-title">Your privacy in one screen</h2>
                  <p className="card-subtitle">
                    Consent is tiered and reversible. Turning off normal sharing never disables
                    deterministic safety monitoring; it changes who can see raw detail and when an
                    emergency override is available.
                  </p>
                </div>
              </div>
            </div>

            <div className="stack-col" style={{ gap: 8 }}>
              <div
                className="card-teal"
                style={{ border: "1px solid var(--mint-border)", borderRadius: 10, padding: "10px 12px" }}
              >
                <strong style={{ fontSize: "0.84rem" }}>Astronaut</strong>
                <div style={{ fontSize: "0.77rem", color: "var(--text-secondary)" }}>
                  Full detail for your own device only.
                </div>
              </div>

              <div
                className="card-amber"
                style={{ border: "1px solid var(--amber-border)", borderRadius: 10, padding: "10px 12px" }}
              >
                <strong style={{ fontSize: "0.84rem" }}>Crew Health Officer</strong>
                <div style={{ fontSize: "0.77rem", color: "var(--text-secondary)" }}>
                  Consented clinical detail + logged emergency access during critical rules.
                </div>
              </div>

              <div
                className="card-purple"
                style={{ border: "1px solid var(--purple-border)", borderRadius: 10, padding: "10px 12px" }}
              >
                <strong style={{ fontSize: "0.84rem" }}>Systems Engineer</strong>
                <div style={{ fontSize: "0.77rem", color: "var(--text-secondary)" }}>
                  Anonymised habitat signals only — no names, no personal health.
                </div>
              </div>

              <div className="card-muted">
                <strong style={{ fontSize: "0.84rem" }}>Ground Support</strong>
                <div style={{ fontSize: "0.77rem", color: "var(--text-secondary)" }}>
                  Mission-level summaries and Earth relay. No raw crew health.
                </div>
              </div>
            </div>
          </section>

          <section className="card card-purple">
            <strong style={{ fontSize: "0.9rem", display: "inline-flex", alignItems: "center", gap: 6 }}>
              <Icon name="shield" size={14} style={{ color: "var(--purple)" }} />
              <span>Consent does not block safety</span>
            </strong>
            <p style={{ margin: "6px 0 0", fontSize: "0.81rem", color: "var(--text-secondary)", lineHeight: 1.48 }}>
              Deterministic rules still evaluate critical vitals, cabin air and severe
              self-reports. The AI never receives a broader scope than the human role viewing it.
            </p>
          </section>
        </aside>
      </div>
    </div>
  );
}
