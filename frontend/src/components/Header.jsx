import React, { useEffect, useRef, useState } from "react";
import { ROLES } from "../fallbackData.js";
import Icon from "./Icon.jsx";

const HOLD_DURATION_MS = 2000;

export default function Header({
  day = 23,
  hour = 16,
  role = "Astronaut",
  selectedCrewId = "ast-01",
  crewRoster = [],
  online = false,
  isLiveApi = false,
  isPlaying = false,
  activeSafetyRules = [],
  onChangeDay,
  onTogglePlay,
  onResetTimeline,
  onChangeRole,
  onChangeCrew,
  onToggleLink,
  onOpenSos,
  onReviewSafety,
}) {
  const [isHolding, setIsHolding] = useState(false);
  const [holdSecondsLeft, setHoldSecondsLeft] = useState(2);
  const [holdHint, setHoldHint] = useState("");
  const holdTimeoutRef = useRef(null);
  const tickTimeoutRef = useRef(null);
  const holdStartRef = useRef(0);
  const triggeredRef = useRef(false);
  const hintTimerRef = useRef(null);

  const clearHold = (showEarlyHint = false) => {
    if (holdTimeoutRef.current) {
      clearTimeout(holdTimeoutRef.current);
      holdTimeoutRef.current = null;
    }
    if (tickTimeoutRef.current) {
      clearTimeout(tickTimeoutRef.current);
      tickTimeoutRef.current = null;
    }
    const elapsed = holdStartRef.current ? Date.now() - holdStartRef.current : 0;
    if (showEarlyHint && !triggeredRef.current && elapsed > 80) {
      setHoldHint("Hold 2s for SOS");
      if (hintTimerRef.current) clearTimeout(hintTimerRef.current);
      hintTimerRef.current = setTimeout(() => setHoldHint(""), 1800);
    }
    holdStartRef.current = 0;
    setIsHolding(false);
    setHoldSecondsLeft(2);
  };

  useEffect(() => {
    return () => {
      if (holdTimeoutRef.current) clearTimeout(holdTimeoutRef.current);
      if (tickTimeoutRef.current) clearTimeout(tickTimeoutRef.current);
      if (hintTimerRef.current) clearTimeout(hintTimerRef.current);
    };
  }, []);

  const startHold = () => {
    if (holdTimeoutRef.current) return;
    triggeredRef.current = false;
    setHoldHint("");
    setHoldSecondsLeft(2);
    setIsHolding(true);
    holdStartRef.current = Date.now();
    tickTimeoutRef.current = setTimeout(() => {
      setHoldSecondsLeft(1);
    }, 1000);
    holdTimeoutRef.current = setTimeout(() => {
      triggeredRef.current = true;
      clearHold(false);
      if (onOpenSos) onOpenSos();
    }, HOLD_DURATION_MS);
  };

  const handleKeyDown = (e) => {
    if ((e.key === " " || e.key === "Enter") && !e.repeat) {
      e.preventDefault();
      startHold();
    }
  };

  const handleKeyUp = (e) => {
    if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      clearHold(true);
    }
  };

  const isAnonymisedRole =
    role === "Systems Engineer" || role === "Ground Support";

  const quickToggleTarget =
    role === "Astronaut" ? "Crew Health Officer" : "Astronaut";
  const quickToggleLabel =
    role === "Astronaut" ? "Health Officer view" : "Astronaut view";

  const primaryRule = activeSafetyRules?.[0];
  const primaryRuleText = primaryRule
    ? isAnonymisedRole && primaryRule.rule_id === "SR-05"
      ? `${activeSafetyRules.length} active safety event`
      : primaryRule.title || primaryRule.rule_id
    : "";

  return (
    <>
      <header className="topbar">
        {/* Top Row: Brand, Mission Clock, Link Status, Quick Role Switch, SOS */}
        <div className="topbar-row">
          <div className="topbar-left">
            <div className="brand-lockup">
              <span className="brand-mark" aria-hidden="true">
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <circle cx="12" cy="12" r="9" />
                  <circle cx="12" cy="12" r="2.6" fill="currentColor" />
                </svg>
              </span>
              <div>
                <div className="brand-title">AstroGuard</div>
                <div className="brand-subtitle">ON-BOARD INTELLIGENCE</div>
              </div>
            </div>

            <div className="topbar-divider" aria-hidden="true" />

            <div className="mission-clock">
              <span className="mission-clock-icon" aria-hidden="true">
                <svg
                  width="15"
                  height="15"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
                </svg>
              </span>
              <div>
                <div className="mission-clock-label">MISSION CLOCK</div>
                <div className="mission-clock-value">
                  Day {day} · {String(hour).padStart(2, "0")}:00
                </div>
              </div>
            </div>
          </div>

          <div className="topbar-right">
            <button
              type="button"
              className={`pill ${online ? "pill-teal" : "pill-amber"}`}
              onClick={() => onToggleLink && onToggleLink()}
              title={
                online
                  ? "Earth link online — click to simulate link drop"
                  : "Offline on-board mode — click to connect Earth link"
              }
              style={{ cursor: "pointer", minHeight: 36, padding: "5px 12px" }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: online ? "var(--teal)" : "var(--amber-deep)",
                  display: "inline-block",
                }}
              />
              {online ? (
                <svg
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="2" />
                  <path d="M16.24 7.76a6 6 0 0 1 0 8.49" />
                  <path d="M7.76 16.24a6 6 0 0 1 0-8.49" />
                </svg>
              ) : (
                <svg
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden="true"
                >
                  <line x1="2" y1="2" x2="22" y2="22" />
                  <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
                  <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
                  <line x1="12" y1="20" x2="12.01" y2="20" />
                </svg>
              )}
              <span>
                {online ? "Earth Link Online" : "Offline — On-Board Mode"}
              </span>
              {!isLiveApi ? (
                <span
                  style={{ fontSize: "0.68rem", opacity: 0.78, marginLeft: 2 }}
                  title="Running on local browser mirror (backend port 8000 offline)"
                >
                  · Local
                </span>
              ) : null}
            </button>

            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => onChangeRole && onChangeRole(quickToggleTarget)}
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                aria-hidden="true"
              >
                {role === "Astronaut" ? (
                  <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                ) : (
                  <>
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </>
                )}
              </svg>
              <span>{quickToggleLabel}</span>
            </button>

            <div style={{ position: "relative" }}>
              <button
                type="button"
                className="btn-sos"
                data-holding={isHolding ? "true" : "false"}
                aria-label="Emergency SOS — press and hold for 2 seconds"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={isHolding ? 50 : 0}
                onMouseDown={startHold}
                onMouseUp={() => clearHold(true)}
                onMouseLeave={() => clearHold(true)}
                onTouchStart={(e) => {
                  e.preventDefault();
                  startHold();
                }}
                onTouchEnd={() => clearHold(true)}
                onTouchCancel={() => clearHold(true)}
                onKeyDown={handleKeyDown}
                onKeyUp={handleKeyUp}
                data-testid="sos-hold-btn"
              >
                <span className="btn-sos-progress" aria-hidden="true" />
                <span
                  style={{
                    position: "relative",
                    zIndex: 1,
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 5,
                    fontSize: "0.82rem",
                    lineHeight: 1.1,
                  }}
                >
                  <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    aria-hidden="true"
                  >
                    <path d="M12 2v3M4.9 4.9l2.1 2.1M19.1 4.9l-2.1 2.1M6 17v-4a6 6 0 0 1 12 0v4M4 17h16v3H4z" />
                  </svg>
                  <span>SOS</span>
                </span>
                <span
                  className="btn-sos-sub"
                  style={{ position: "relative", zIndex: 1 }}
                >
                  {isHolding ? `${holdSecondsLeft}s HOLD` : <kbd className="keycap">Hold 2s</kbd>}
                </span>
              </button>
              {holdHint ? (
                <div
                  role="status"
                  style={{
                    position: "absolute",
                    right: 0,
                    top: "110%",
                    background: "var(--text-primary)",
                    color: "#fff",
                    fontSize: "0.72rem",
                    fontWeight: 600,
                    padding: "4px 9px",
                    borderRadius: 8,
                    whiteSpace: "nowrap",
                    zIndex: 60,
                    boxShadow: "var(--shadow-elevated)",
                  }}
                >
                  {holdHint}
                </div>
              ) : null}
            </div>
          </div>
        </div>

        {/* Second Row: Role selector, Crew selector / Anonymised pill, Timeline scrubber */}
        <div className="topbar-row">
          <div className="topbar-controls">
            <label className="topbar-select-group">
              <span className="topbar-select-label">VIEWING AS</span>
              <select
                value={role}
                aria-label="Viewing as role"
                onChange={(e) => onChangeRole && onChangeRole(e.target.value)}
              >
                {ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>

            {isAnonymisedRole ? (
              <span className="pill pill-purple" style={{ minHeight: 38, padding: "6px 12px" }}>
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden="true"
                >
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
                <span>Anonymised crew</span>
              </span>
            ) : (
              <label className="topbar-select-group">
                <span className="topbar-select-label">CREW</span>
                <select
                  value={selectedCrewId}
                  aria-label="Select crew member"
                  onChange={(e) => onChangeCrew && onChangeCrew(e.target.value)}
                >
                  {crewRoster.map((c) => (
                    <option key={c.astronaut_id} value={c.astronaut_id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>

          <div className="timeline-bar" aria-label="Mission day timeline scrubber">
            <button
              type="button"
              className="timeline-play-btn"
              onClick={() => onTogglePlay && onTogglePlay()}
              aria-label={isPlaying ? "Pause mission timeline" : "Play mission timeline"}
              title={isPlaying ? "Pause timeline" : "Play Days 1–30"}
            >
              {isPlaying ? (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <rect x="6" y="4" width="4" height="16" rx="1" />
                  <rect x="14" y="4" width="4" height="16" rx="1" />
                </svg>
              ) : (
                <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <polygon points="6 4 20 12 6 20 6 4" />
                </svg>
              )}
            </button>

            <div className="timeline-meta">
              <div className="timeline-meta-top">
                <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                  <svg
                    width="13"
                    height="13"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    aria-hidden="true"
                  >
                    <circle cx="12" cy="12" r="2" />
                    <path d="M16.24 7.76a6 6 0 0 1 0 8.49" />
                    <path d="M7.76 16.24a6 6 0 0 1 0-8.49" />
                  </svg>
                  <span>Timeline</span>
                </span>
                <strong>Day {day} · 16:00 ship time</strong>
              </div>
              <input
                type="range"
                min={1}
                max={30}
                value={day}
                aria-label="Mission day slider"
                onChange={(e) => onChangeDay && onChangeDay(Number(e.target.value))}
              />
            </div>

            <button
              type="button"
              className="timeline-reset-btn"
              onClick={() => onResetTimeline && onResetTimeline()}
              aria-label="Reset timeline to Day 23"
              title="Reset to Day 23 scenario"
            >
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <polyline points="1 4 1 10 7 10" />
                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {/* Deterministic Safety Banner — cannot be lowered or suppressed */}
      {activeSafetyRules.length > 0 ? (
        <div
          className={`safety-banner ${
            primaryRule?.rule_id === "SR-03" && activeSafetyRules.length === 1
              ? "amber"
              : ""
          }`}
          role="alert"
        >
          <div className="safety-banner-inner">
            <div className="safety-banner-text">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                aria-hidden="true"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <span>{primaryRuleText}</span>
              <span className="safety-banner-sub">
                <svg
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  aria-hidden="true"
                >
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                  <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
                <span>Deterministic · cannot be downgraded</span>
              </span>
            </div>
            <button
              type="button"
              className="btn btn-danger-soft btn-sm"
              onClick={() => onReviewSafety && onReviewSafety()}
            >
              <span>Review</span>
              <Icon name="chevron-right" size={14} />
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
