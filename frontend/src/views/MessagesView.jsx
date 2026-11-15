import React, { useEffect, useRef, useState } from "react";
import Icon from "../components/Icon.jsx";

function getDeliveryMeta(status) {
  const s = String(status || "queued").toLowerCase();
  if (s === "read") {
    return { cls: "pill-teal", iconName: "check-double", label: "Read", topLabel: "Read" };
  }
  if (s === "delivered") {
    return { cls: "pill-teal", iconName: "check-double", label: "Delivered", topLabel: "Delivered" };
  }
  if (s === "sent" || s === "transmitting") {
    return { cls: "pill-purple", iconName: "send", label: "Sent", topLabel: "Sent" };
  }
  return {
    cls: "pill-amber",
    iconName: "clock",
    label: "Queued",
    topLabel: "Queued — on-board",
  };
}

function formatDuration(secs) {
  const s = Math.max(0, Math.round(secs || 0));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${String(rem).padStart(2, "0")}`;
}

export default function MessagesView({
  state,
  onSendMessage,
  onMarkMessageRead,
}) {
  const [filter, setFilter] = useState("all"); // all | earth | crew
  const [toId, setToId] = useState("earth");
  const [kind, setKind] = useState("text"); // text | audio
  const [body, setBody] = useState("");
  const [attachChart, setAttachChart] = useState(false);

  // Simulated audio voice-note recorder state
  const [recording, setRecording] = useState(false);
  const [recordedSeconds, setRecordedSeconds] = useState(0);
  const [playingMsgId, setPlayingMsgId] = useState(null);
  const recTimerRef = useRef(null);

  useEffect(() => {
    return () => {
      if (recTimerRef.current) clearInterval(recTimerRef.current);
    };
  }, []);

  const role = state?.viewer_role || "Astronaut";
  const currentCrewId = state?.selected_crew_id || "ast-01";
  const senderId =
    role === "Crew Health Officer" ? "health_officer" : currentCrewId;
  const crewRoster = state?.crew_roster || [];
  const online = Boolean(state?.online || state?.earth_link?.online);
  const delayMin = state?.earth_delay_min ?? 12.8;
  const day = state?.day ?? 23;

  const consentProfiles = state?.consent_matrix || {};
  const myGroundSharing =
    consentProfiles[currentCrewId]?.normal?.ground_sharing ?? true;

  const allMessages = Array.isArray(state?.messages) ? state.messages : [];
  const filtered = allMessages.filter((m) => {
    if (filter === "earth") return m.channel === "earth";
    if (filter === "crew") return m.channel !== "earth";
    return true;
  });
  const queuedCount = allMessages.filter((m) => m.status === "queued").length;

  const startRecording = () => {
    setRecordedSeconds(1);
    setRecording(true);
    if (recTimerRef.current) clearInterval(recTimerRef.current);
    recTimerRef.current = setInterval(() => {
      setRecordedSeconds((s) => Math.min(120, s + 1));
    }, 1000);
  };

  const stopRecording = () => {
    setRecording(false);
    if (recTimerRef.current) {
      clearInterval(recTimerRef.current);
      recTimerRef.current = null;
    }
  };

  const audioSizeKb = Math.max(0, Math.round(recordedSeconds * 3.2));
  const chartSizeKb = attachChart ? 18 : 0;
  const textSizeKb = Math.max(1, Math.round(body.trim().length / 180));
  const totalSizeKb = (kind === "audio" ? audioSizeKb : textSizeKb) + chartSizeKb;
  const isEarthDest = toId === "earth";
  const showBandwidthWarn =
    isEarthDest && (attachChart || (kind === "audio" && audioSizeKb > 12));

  const canSend =
    kind === "text"
      ? body.trim().length > 0
      : recordedSeconds > 0 && !recording;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSend || !onSendMessage) return;
    await onSendMessage({
      fromId: senderId,
      toId,
      kind,
      body:
        kind === "audio"
          ? body.trim() || `Audio voice note (${formatDuration(recordedSeconds)} · ${audioSizeKb} KB)`
          : body.trim(),
      audioDurationS: kind === "audio" ? recordedSeconds : 0,
      sizeKb: totalSizeKb,
      attachChart,
      day,
    });
    setBody("");
    setAttachChart(false);
    setRecordedSeconds(0);
    setRecording(false);
  };

  const recipientOptions = [
    { id: "earth", label: "Home (Earth)" },
    { id: "health_officer", label: "Crew Health Officer" },
    { id: "all", label: "All crew" },
    ...crewRoster
      .filter((c) => c.astronaut_id !== senderId)
      .map((c) => ({ id: c.astronaut_id, label: c.name })),
  ];

  return (
    <div className="stack-col" data-testid="messages-view">
      <header className="page-header">
        <div>
          <div className="page-eyebrow">STORE-AND-FORWARD COMMS</div>
          <h1>Messages</h1>
          <p className="page-subtitle">
            Text or audio to crew or Earth. Packets queue by priority and retry across link drops.
            Expected light time is about ~{delayMin} min.
          </p>
        </div>
        <div className="page-header-pills">
          <span className={`pill ${online ? "pill-teal" : "pill-amber"}`}>
            <Icon name={online ? "radio" : "zap"} size={12} />
            <span>{online ? "Earth link online" : "On-board mode"}</span>
          </span>
          <span className="pill pill-neutral tabular-nums">
            <Icon name="clock" size={12} />
            <span>~{delayMin} min light time</span>
          </span>
          <span className="pill pill-neutral tabular-nums">
            <Icon name="radio" size={12} />
            <span>2.4 kbps</span>
          </span>
        </div>
      </header>

      <div className="split-main-aside">
        {/* Left Thread Column */}
        <div className="stack-col">
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              gap: 10,
              flexWrap: "wrap",
            }}
          >
            <div className="subtabs" role="tablist" aria-label="Filter messages">
              {[
                { id: "all", label: "All" },
                { id: "earth", label: "Earth" },
                { id: "crew", label: "Crew" },
              ].map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="tab"
                  aria-selected={filter === t.id}
                  className={`subtab ${filter === t.id ? "active" : ""}`}
                  onClick={() => setFilter(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>
            <span style={{ fontSize: "0.78rem", color: "var(--text-muted)" }} className="tabular-nums">
              {filtered.length} messages · {queuedCount} queued
            </span>
          </div>

          <div className="stack-col" style={{ gap: 12 }}>
            {filtered.map((msg) => {
              const outbound = msg.from_id === senderId;
              const delMeta = getDeliveryMeta(msg.status);
              const isRead = String(msg.status).toLowerCase() === "read";
              const isPlaying = playingMsgId === msg.message_id;

              return (
                <article key={msg.message_id} className="card" style={{ padding: 16 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      gap: 10,
                      flexWrap: "wrap",
                    }}
                  >
                    <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                      <span
                        aria-hidden="true"
                        style={{
                          width: 32,
                          height: 32,
                          borderRadius: 10,
                          background: outbound ? "var(--mint)" : "var(--purple-bg)",
                          color: outbound ? "var(--teal)" : "var(--purple)",
                          display: "inline-flex",
                          alignItems: "center",
                          justifyContent: "center",
                          fontWeight: 700,
                        }}
                      >
                        <Icon
                          name={outbound ? "send" : "radio"}
                          size={14}
                        />
                      </span>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: "0.88rem" }}>
                          {msg.from_label || msg.from} → {msg.to_label || msg.to}
                        </div>
                        <div style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
                          {msg.timestamp_label}
                        </div>
                      </div>
                    </div>

                    <span className={`pill ${delMeta.cls}`}>
                      <Icon name={delMeta.iconName} size={12} />
                      <span>{delMeta.topLabel}</span>
                    </span>
                  </div>

                  {msg.kind === "audio" ? (
                    <div
                      className="card-muted"
                      style={{
                        marginTop: 10,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 10,
                        flexWrap: "wrap",
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <button
                          type="button"
                          className="btn btn-primary btn-sm"
                          onClick={() =>
                            setPlayingMsgId(isPlaying ? null : msg.message_id)
                          }
                        >
                          <Icon name={isPlaying ? "pause" : "play"} size={13} />
                          <span>{isPlaying ? "Pause" : "Play"}</span>
                        </button>
                        <div>
                          <div style={{ fontWeight: 600, fontSize: "0.83rem" }}>
                            Audio clip · {formatDuration(msg.audio_duration_s)}
                          </div>
                          <div style={{ fontSize: "0.73rem", color: "var(--text-muted)" }}>
                            {msg.size_kb || 24} KB · {msg.body}
                          </div>
                        </div>
                      </div>
                      {isPlaying ? (
                        <span className="pill pill-teal">Playing locally…</span>
                      ) : null}
                    </div>
                  ) : (
                    <p style={{ margin: "10px 0 0", fontSize: "0.89rem", lineHeight: 1.5 }}>
                      {msg.body}
                    </p>
                  )}

                  {msg.attachment ? (
                    <div
                      className="card-teal"
                      style={{
                        marginTop: 10,
                        border: "1px solid var(--mint-border)",
                        borderRadius: 10,
                        padding: "9px 12px",
                        display: "flex",
                        alignItems: "center",
                        gap: 8,
                      }}
                    >
                      <Icon name="trending-up" size={16} style={{ color: "var(--teal-dark)" }} />
                      <div>
                        <div style={{ fontWeight: 600, fontSize: "0.81rem", color: "var(--teal-dark)" }}>
                          {msg.attachment.label}
                        </div>
                        <div style={{ fontSize: "0.72rem", color: "var(--text-secondary)" }}>
                          {msg.attachment.detail}
                        </div>
                      </div>
                    </div>
                  ) : null}

                  <div
                    style={{
                      marginTop: 12,
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      gap: 8,
                      flexWrap: "wrap",
                    }}
                  >
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                      <span className="pill pill-neutral">
                        <Icon name={delMeta.iconName} size={12} />
                        <span>{delMeta.label}</span>
                      </span>
                      {msg.bandwidth_warning ? (
                        <span className="pill pill-amber">
                          <Icon name="alert" size={12} />
                          <span>Bandwidth warning</span>
                        </span>
                      ) : null}
                    </div>

                    {!outbound && !isRead ? (
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => onMarkMessageRead && onMarkMessageRead(msg.message_id)}
                      >
                        Mark read
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>

          <section className="card card-teal">
            <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
              <span aria-hidden="true" style={{ marginTop: 2, color: "var(--teal-dark)" }}>
                <Icon name="clock" size={16} />
              </span>
              <div>
                <strong style={{ fontSize: "0.88rem" }}>How the queue behaves</strong>
                <p style={{ margin: "4px 0 0", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                  Priority order is fixed: SOS → critical alerts → messages → summaries →
                  telemetry. When the Earth link is offline, the packet stays on-board at its
                  original priority. It is never silently dropped.
                </p>
              </div>
            </div>
          </section>
        </div>

        {/* Right Compose Column */}
        <aside className="card" aria-label="Compose message">
          <div className="card-header">
            <div className="card-title-group">
              <span className="card-icon-badge" aria-hidden="true">
                <Icon name="send" size={15} />
              </span>
              <div>
                <h2 className="card-title">Compose</h2>
                <p className="card-subtitle">
                  Stored on-board first, then queued for the selected destination.
                </p>
              </div>
            </div>
          </div>

          <form className="stack-col" style={{ gap: 12 }} onSubmit={handleSubmit}>
            <div>
              <label
                htmlFor="msg-to-select"
                style={{
                  display: "block",
                  fontSize: "0.68rem",
                  fontWeight: 700,
                  letterSpacing: "0.08em",
                  color: "var(--text-muted)",
                  marginBottom: 5,
                }}
              >
                TO
              </label>
              <select
                id="msg-to-select"
                className="select-input"
                value={toId}
                onChange={(e) => setToId(e.target.value)}
                style={{
                  width: "100%",
                  border: "1px solid var(--border-strong)",
                  borderRadius: 10,
                  padding: "9px 12px",
                  background: "#fff",
                }}
              >
                {recipientOptions.map((opt) => (
                  <option key={opt.id} value={opt.id}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="subtabs" style={{ width: "100%" }}>
              <button
                type="button"
                className={`subtab ${kind === "text" ? "active" : ""}`}
                style={{ flex: 1, justifyContent: "center" }}
                onClick={() => {
                  setKind("text");
                  if (recording) stopRecording();
                }}
              >
                <Icon name="message" size={14} />
                <span>Text</span>
              </button>
              <button
                type="button"
                className={`subtab ${kind === "audio" ? "active" : ""}`}
                style={{ flex: 1, justifyContent: "center" }}
                onClick={() => setKind("audio")}
                data-testid="compose-audio-tab"
              >
                <Icon name="mic" size={14} />
                <span>Audio</span>
              </button>
            </div>

            {kind === "text" ? (
              <textarea
                rows={4}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Write to crew or Home. Plain language is fine."
                aria-label="Message text"
                style={{
                  width: "100%",
                  borderRadius: 10,
                  border: "1px solid var(--border-strong)",
                  padding: "10px 12px",
                  fontSize: "0.86rem",
                  resize: "vertical",
                }}
              />
            ) : (
              <div className="card-muted" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <strong style={{ fontSize: "0.84rem" }}>Voice note recorder</strong>
                  <span className="pill pill-neutral tabular-nums">
                    {formatDuration(recordedSeconds)} · {audioSizeKb} KB
                  </span>
                </div>
                <div style={{ display: "flex", gap: 8 }}>
                  {!recording ? (
                    <button
                      type="button"
                      className="btn btn-primary btn-sm"
                      style={{ flex: 1 }}
                      onClick={startRecording}
                      data-testid="record-audio-btn"
                    >
                      <Icon name="mic" size={14} />
                      <span>{recordedSeconds > 0 ? "Re-record clip" : "Start recording"}</span>
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
                      style={{ flex: 1 }}
                      onClick={stopRecording}
                      data-testid="stop-audio-btn"
                    >
                      <Icon name="pause" size={14} />
                      <span>Stop recording ({formatDuration(recordedSeconds)})</span>
                    </button>
                  )}
                  {recordedSeconds > 0 && !recording ? (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => setRecordedSeconds(0)}
                    >
                      Clear
                    </button>
                  ) : null}
                </div>
                <input
                  type="text"
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  placeholder="Optional audio note label..."
                  style={{
                    width: "100%",
                    borderRadius: 8,
                    border: "1px solid var(--border-subtle)",
                    padding: "6px 10px",
                    fontSize: "0.8rem",
                    background: "#fff",
                  }}
                />
              </div>
            )}

            <label
              className="card-muted"
              style={{
                display: "flex",
                gap: 10,
                alignItems: "flex-start",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={attachChart}
                onChange={(e) => setAttachChart(e.target.checked)}
                style={{ marginTop: 3 }}
              />
              <div>
                <div style={{ fontWeight: 600, fontSize: "0.83rem" }}>
                  Attach consented health chart
                </div>
                <div style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
                  Recovery trend · 7 days. Adds transit time on the narrow Earth link.
                </div>
              </div>
            </label>

            {isEarthDest && attachChart && !myGroundSharing ? (
              <div className="gap-item">
                <span>
                  Note: your Ground summary sharing switch is currently OFF; only this explicit
                  consented chart will be included.
                </span>
              </div>
            ) : null}

            {showBandwidthWarn ? (
              <div className="gap-item" data-testid="bandwidth-warning">
                <span>
                  <strong>Bandwidth warning ({totalSizeKb} KB):</strong> on a 2.4 kbps Earth link
                  this attachment adds ~{Math.max(10, Math.round((totalSizeKb * 8) / 2.4))}s
                  transmit time behind Priority 0–1 packets.
                </span>
              </div>
            ) : null}

            <div
              className="card-amber"
              style={{
                border: "1px solid var(--amber-border)",
                borderRadius: 10,
                padding: "9px 12px",
                fontSize: "0.78rem",
                color: "var(--amber-text)",
                display: "flex",
                alignItems: "flex-start",
                gap: 7,
              }}
            >
              <Icon name="alert" size={14} style={{ marginTop: 2 }} />
              <span>
                {isEarthDest
                  ? `Expected delay ~${delayMin} min. Packets are never dropped; they retry after a link drop.`
                  : "On-board delivery to crew is immediate; stored locally first."}
              </span>
            </div>

            <button
              type="submit"
              className="btn btn-primary"
              disabled={!canSend}
              style={{ width: "100%" }}
              data-testid="send-message-btn"
            >
              <Icon name="send" size={15} />
              <span>Send message</span>
            </button>

            <div
              style={{
                textAlign: "center",
                fontSize: "0.72rem",
                color: "var(--text-muted)",
              }}
            >
              Text and audio stay inside your consent scope. Life-support data is never attached
              silently.
            </div>
          </form>
        </aside>
      </div>
    </div>
  );
}
