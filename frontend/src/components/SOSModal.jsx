import React, { useEffect, useRef, useState } from "react";
import Icon from "./Icon.jsx";

const SOS_TYPES = [
  {
    id: "medical",
    label: "Medical",
    desc: "Injury, breathing, chest pain, or a vitals concern.",
  },
  {
    id: "behavioral",
    label: "Behavioral support",
    desc: "Distress, panic, or you need a private human response.",
  },
  {
    id: "environment",
    label: "Habitat hazard",
    desc: "Air, fire, pressure, contamination, or a cabin emergency.",
  },
];

const DELIVERY_STEPS = ["queued", "transmitting", "delivered", "acknowledged"];

function playGentleChime() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(660, ctx.currentTime);
    gain.gain.setValueAtTime(0.06, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.36);
  } catch {
    // Audio playback optional; never block SOS
  }
}

function SosTypeIcon({ id }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
  };
  if (id === "medical") {
    return (
      <svg {...common}>
        <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
      </svg>
    );
  }
  if (id === "behavioral") {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="10" />
        <circle cx="12" cy="12" r="4" />
        <line x1="4.93" y1="4.93" x2="9.17" y2="9.17" />
        <line x1="14.83" y1="14.83" x2="19.07" y2="19.07" />
        <line x1="14.83" y1="9.17" x2="19.07" y2="4.93" />
        <line x1="4.93" y1="19.07" x2="9.17" y2="14.83" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2" />
    </svg>
  );
}

export default function SOSModal({
  isOpen,
  initialMode = "compose",
  astronautId = "ast-01",
  astronautName = "Cmdr. Elena Vasquez",
  sosEvents = [],
  onClose,
  onTriggerSos,
  onCancelSos,
  onAcknowledgeSos,
  onResolveSos,
}) {
  const [stage, setStage] = useState(initialMode);
  const [sosType, setSosType] = useState("medical");
  const [note, setNote] = useState("");
  const [secondsLeft, setSecondsLeft] = useState(10);
  const [pendingPacket, setPendingPacket] = useState(null);
  const timerRef = useRef(null);
  const committedRef = useRef(false);

  useEffect(() => {
    if (isOpen) {
      setStage(initialMode || "compose");
      setSecondsLeft(10);
      setPendingPacket(null);
      committedRef.current = false;
    } else if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, [isOpen, initialMode]);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  if (!isOpen) return null;

  const activeSosList = (sosEvents || []).filter(
    (s) => s.status !== "cancelled" && s.status !== "resolved_ok"
  );

  const commitSosNow = async () => {
    if (committedRef.current) return;
    committedRef.current = true;
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    const packet = await onTriggerSos?.({
      astronautId,
      sosType,
      note,
    });
    setPendingPacket(packet || null);
    setStage("status");
    setNote("");
  };

  const handleStartCountdown = () => {
    playGentleChime();
    setStage("countdown");
    setSecondsLeft(10);
    committedRef.current = false;
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setSecondsLeft((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current);
          timerRef.current = null;
          commitSosNow();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  const handleFalseAlarmCancel = async () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    committedRef.current = true;
    if (pendingPacket?.sos_id && onCancelSos) {
      await onCancelSos({ sosId: pendingPacket.sos_id, reason: "false_alarm" });
    }
    setStage("compose");
    onClose?.();
  };

  const displayPackets = pendingPacket
    ? [
        pendingPacket,
        ...activeSosList.filter((s) => s.sos_id !== pendingPacket.sos_id),
      ]
    : activeSosList;

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="sos-modal-title"
      data-testid="sos-modal"
    >
      <div className="modal-card">
        <div className="modal-header">
          <div>
            <h2
              id="sos-modal-title"
              style={{ margin: 0, fontSize: "1.25rem", fontWeight: 700 }}
            >
              Emergency SOS
            </h2>
            <p
              style={{
                margin: "3px 0 0",
                fontSize: "0.84rem",
                color: "var(--text-secondary)",
              }}
            >
              Choose the type that fits best. If you are unsure, Medical is the safe default.
            </p>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            aria-label="Close SOS modal"
            onClick={() => {
              if (stage === "countdown") handleFalseAlarmCancel();
              else onClose?.();
            }}
            style={{ gap: 6 }}
          >
            <kbd className="keycap">Esc</kbd>
            <Icon name="x" size={16} />
          </button>
        </div>

        {/* Optional quick switch between triggering new SOS and viewing active packets */}
        {activeSosList.length > 0 && stage !== "countdown" ? (
          <div className="subtabs">
            <button
              type="button"
              className={`subtab ${stage === "compose" ? "active" : ""}`}
              onClick={() => setStage("compose")}
            >
              New SOS packet
            </button>
            <button
              type="button"
              className={`subtab ${stage === "status" ? "active" : ""}`}
              onClick={() => setStage("status")}
            >
              Active SOS ({activeSosList.length})
            </button>
          </div>
        ) : null}

        {stage === "compose" ? (
          <>
            <div
              className="card-red"
              style={{
                border: "1px solid var(--red-border)",
                borderRadius: 12,
                padding: "12px 14px",
                display: "flex",
                gap: 10,
                alignItems: "flex-start",
              }}
            >
              <span style={{ color: "var(--red)", marginTop: 2 }}>
                <svg
                  width="17"
                  height="17"
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
              </span>
              <div style={{ fontSize: "0.83rem", lineHeight: 1.45 }}>
                <div style={{ fontWeight: 700, color: "var(--red-text)" }}>
                  This alerts a human immediately
                </div>
                <div style={{ color: "var(--red-text)", opacity: 0.9 }}>
                  Use for a real or suspected emergency. The Advisor cannot cancel, delay, or
                  downgrade this packet.
                </div>
              </div>
            </div>

            <div
              className="grid-3"
              role="radiogroup"
              aria-label="Emergency SOS type"
            >
              {SOS_TYPES.map((item) => {
                const selected = sosType === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setSosType(item.id)}
                    style={{
                      textAlign: "left",
                      padding: "12px",
                      borderRadius: 12,
                      border: selected
                        ? "1.5px solid var(--red)"
                        : "1px solid var(--border-subtle)",
                      background: selected ? "var(--red-card-bg)" : "var(--bg-surface)",
                      display: "flex",
                      flexDirection: "column",
                      gap: 6,
                    }}
                  >
                    <span
                      style={{
                        color: selected ? "var(--red)" : "var(--text-secondary)",
                      }}
                    >
                      <SosTypeIcon id={item.id} />
                    </span>
                    <span
                      style={{
                        fontWeight: 700,
                        fontSize: "0.86rem",
                        color: "var(--text-primary)",
                      }}
                    >
                      {item.label}
                    </span>
                    <span
                      style={{
                        fontSize: "0.75rem",
                        color: "var(--text-secondary)",
                        lineHeight: 1.38,
                      }}
                    >
                      {item.desc}
                    </span>
                  </button>
                );
              })}
            </div>

            <div>
              <label
                htmlFor="sos-note-input"
                style={{
                  display: "block",
                  fontSize: "0.82rem",
                  fontWeight: 600,
                  marginBottom: 6,
                }}
              >
                Short note (optional)
              </label>
              <textarea
                id="sos-note-input"
                rows={3}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="What is happening right now? Plain language is enough."
                style={{
                  width: "100%",
                  borderRadius: 10,
                  border: "1px solid var(--border-strong)",
                  padding: "10px 12px",
                  fontSize: "0.86rem",
                  resize: "vertical",
                }}
              />
            </div>

            <div
              className="card-muted"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                gap: 10,
                fontSize: "0.76rem",
                color: "var(--text-secondary)",
              }}
            >
              <div style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
                <Icon name="shield" size={14} style={{ marginTop: 2 }} />
                <span>On-board rules fire immediately</span>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
                <Icon name="radio" size={14} style={{ marginTop: 2 }} />
                <span>Queued at priority 0</span>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "flex-start" }}>
                <Icon name="clock" size={14} style={{ marginTop: 2 }} />
                <span>10-second cancel window</span>
              </div>
            </div>

            <div className="modal-footer">
              <span style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
                Opened by a 2-second press-and-hold on the header SOS button.
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => onClose?.()}
                >
                  Back
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={handleStartCountdown}
                  data-testid="trigger-sos-btn"
                >
                  <svg
                    width="15"
                    height="15"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.2"
                    aria-hidden="true"
                  >
                    <path d="M12 2v3M4.9 4.9l2.1 2.1M19.1 4.9l-2.1 2.1M6 17v-4a6 6 0 0 1 12 0v4M4 17h16v3H4z" />
                  </svg>
                  <span>Trigger SOS</span>
                </button>
              </div>
            </div>
          </>
        ) : null}

        {stage === "countdown" ? (
          <div className="stack-col" style={{ gap: 14 }}>
            <div
              className="card-red"
              style={{
                border: "1.5px solid var(--red)",
                borderRadius: 14,
                padding: 18,
                textAlign: "center",
              }}
            >
              <div className="pill pill-red" style={{ marginBottom: 10 }}>
                10-SECOND CANCEL WINDOW
              </div>
              <div
                className="tabular-nums"
                style={{
                  fontSize: "2.6rem",
                  fontWeight: 600,
                  color: "var(--red)",
                  lineHeight: 1.05,
                }}
              >
                {secondsLeft}s
              </div>
              <p
                style={{
                  margin: "8px 0 12px",
                  fontSize: "0.86rem",
                  color: "var(--red-text)",
                }}
              >
                Preparing Priority 0 <strong>{sosType}</strong> SOS packet for{" "}
                <strong>{astronautName}</strong> with vitals &amp; habitat snapshot.
              </p>
              <div
                style={{
                  height: 7,
                  borderRadius: 999,
                  background: "#f9d6d6",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    width: "100%",
                    height: "100%",
                    background: "var(--red)",
                    transformOrigin: "left center",
                    transform: `scaleX(${Math.max(0, Math.min(1, (10 - secondsLeft) / 10))})`,
                    transition: "transform 350ms linear",
                  }}
                />
              </div>
            </div>

            <div className="modal-footer">
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleFalseAlarmCancel}
                data-testid="cancel-sos-ok-btn"
              >
                I&apos;m OK / false alarm
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={commitSosNow}
              >
                Dispatch now
              </button>
            </div>
          </div>
        ) : null}

        {stage === "status" ? (
          <div className="stack-col" style={{ gap: 12 }}>
            {displayPackets.length === 0 ? (
              <div className="card-muted" style={{ fontSize: "0.85rem" }}>
                No active SOS packets in queue.
              </div>
            ) : (
              displayPackets.map((pkt) => {
                const statusIdx = Math.max(
                  0,
                  DELIVERY_STEPS.indexOf(String(pkt.status || "queued").toLowerCase())
                );
                return (
                  <div
                    key={pkt.sos_id}
                    className="sos-inbox-item"
                    style={{ gap: 10 }}
                  >
                    <div className="sos-inbox-head">
                      <div>
                        <div className="sos-inbox-title">
                          {pkt.crew_name || pkt.astronaut_name || astronautName} ·{" "}
                          {pkt.sos_type || pkt.type || "Medical"}
                        </div>
                        <div
                          style={{
                            fontSize: "0.76rem",
                            color: "var(--text-secondary)",
                          }}
                        >
                          {pkt.timestamp_label || pkt.time_label} · Priority 0 ·{" "}
                          {pkt.override_logged
                            ? "Emergency override logged"
                            : "Deterministic SR-05"}
                        </div>
                      </div>
                      <span className="pill pill-red">
                        {pkt.status || "queued"}
                      </span>
                    </div>

                    {pkt.note ? (
                      <p style={{ margin: 0, fontSize: "0.84rem" }}>{pkt.note}</p>
                    ) : null}

                    {/* 4-step store-and-forward status timeline */}
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(4, minmax(0, 1fr))",
                        gap: 6,
                      }}
                    >
                      {DELIVERY_STEPS.map((stepName, idx) => {
                        const reached = idx <= statusIdx;
                        return (
                          <div
                            key={stepName}
                            style={{
                              padding: "6px 8px",
                              borderRadius: 8,
                              border: reached
                                ? "1px solid var(--red-border)"
                                : "1px solid var(--border-subtle)",
                              background: reached ? "#ffffff" : "var(--bg-muted)",
                              fontSize: "0.73rem",
                              fontWeight: reached ? 700 : 500,
                              color: reached
                                ? "var(--red-text)"
                                : "var(--text-muted)",
                              display: "inline-flex",
                              alignItems: "center",
                              justifyContent: "center",
                              gap: 4,
                            }}
                          >
                            {reached ? <Icon name="check" size={12} /> : null}
                            <span>{stepName}</span>
                          </div>
                        );
                      })}
                    </div>

                    <div
                      style={{
                        display: "flex",
                        justifyContent: "flex-end",
                        gap: 8,
                        flexWrap: "wrap",
                      }}
                    >
                      {!pkt.onboard_acknowledged && onAcknowledgeSos ? (
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => onAcknowledgeSos(pkt.sos_id)}
                        >
                          Acknowledge on-board
                        </button>
                      ) : (
                        <span className="pill pill-teal">On-board acknowledged</span>
                      )}
                      {onResolveSos ? (
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() => onResolveSos(pkt.sos_id)}
                        >
                          I&apos;m OK / resolve
                        </button>
                      ) : null}
                    </div>
                  </div>
                );
              })
            )}

            <div className="modal-footer">
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                Works offline; survives Advisor or analytics failure.
              </span>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => onClose?.()}
              >
                Close
              </button>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
