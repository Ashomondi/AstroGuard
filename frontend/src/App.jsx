import React, { useCallback, useEffect, useState } from "react";
import {
  acknowledgeSos,
  askAdvisor,
  cancelSos,
  fastForwardSync,
  fetchState,
  markMessageRead,
  resolveSos,
  runWhatIf,
  sendMessage,
  submitCheckin,
  submitPvt,
  toggleEarthLink,
  triggerSos,
  updateConsent,
} from "./api.js";
import { getFallbackState, PROTOCOL_LIBRARY } from "./fallbackData.js";
import Header from "./components/Header.jsx";
import Icon from "./components/Icon.jsx";
import SOSModal from "./components/SOSModal.jsx";
import AstronautBriefing from "./views/AstronautBriefing.jsx";
import AdvisorView from "./views/AdvisorView.jsx";
import MessagesView from "./views/MessagesView.jsx";
import PrivacyConsentView from "./views/PrivacyConsentView.jsx";
import HealthOfficerView from "./views/HealthOfficerView.jsx";
import SystemsEngineerView from "./views/SystemsEngineerView.jsx";
import GroundSupportView from "./views/GroundSupportView.jsx";

function NavIcon({ id }) {
  const common = {
    width: 17,
    height: 17,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
  };
  switch (id) {
    case "briefing":
    case "summary":
      return (
        <svg {...common}>
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
          <polyline points="9 22 9 12 15 12 15 22" />
        </svg>
      );
    case "overview":
      return (
        <svg {...common}>
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      );
    case "advisor":
      return (
        <svg {...common}>
          <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
        </svg>
      );
    case "messages":
    case "comms":
    case "relay":
      return (
        <svg {...common}>
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      );
    case "habitat":
      return (
        <svg {...common}>
          <path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      );
  }
}

const WORKSPACE_NAV = {
  Astronaut: {
    eyebrow: "ASTRONAUT WORKSPACE",
    defaultTab: "briefing",
    items: [
      { id: "briefing", shortLabel: "Briefing", label: "Daily briefing", sub: "Your readiness and next step" },
      { id: "advisor", shortLabel: "Advisor", label: "AstroGuard Advisor", sub: "Grounded answers and what-if" },
      { id: "messages", shortLabel: "Messages", label: "Messages", sub: "Delay-tolerant crew and Earth" },
      { id: "privacy", shortLabel: "Privacy", label: "Privacy & consent", sub: "Your data, your switches" },
    ],
  },
  "Crew Health Officer": {
    eyebrow: "HEALTH OFFICER WORKSPACE",
    defaultTab: "overview",
    items: [
      { id: "overview", shortLabel: "Crew", label: "Crew overview", sub: "Consented health and SOS" },
      { id: "habitat", shortLabel: "Habitat", label: "Habitat signals", sub: "Environment correlation" },
      { id: "advisor", shortLabel: "Advisor", label: "AstroGuard Advisor", sub: "Grounded clinical context" },
      { id: "messages", shortLabel: "Messages", label: "Messages", sub: "Crew and Earth traffic" },
      { id: "privacy", shortLabel: "Consent", label: "Access & consent", sub: "Consent and audit trail" },
    ],
  },
  "Systems Engineer": {
    eyebrow: "SYSTEMS ENGINEER WORKSPACE",
    defaultTab: "habitat",
    items: [
      { id: "habitat", shortLabel: "Habitat", label: "Habitat map", sub: "Anonymised zone signals" },
      { id: "comms", shortLabel: "Comms", label: "Engineering comms", sub: "Habitat operations" },
      { id: "scope", shortLabel: "Scope", label: "Access scope", sub: "What this role can see" },
    ],
  },
  "Ground Support": {
    eyebrow: "GROUND SUPPORT WORKSPACE",
    defaultTab: "summary",
    items: [
      { id: "summary", shortLabel: "Summary", label: "Mission summary", sub: "Aggregate readiness and sync" },
      { id: "relay", shortLabel: "Relay", label: "Earth relay", sub: "Delay-tolerant traffic" },
      { id: "scope", shortLabel: "Scope", label: "Access scope", sub: "What this role can see" },
    ],
  },
};

function ProtocolModal({ protocol, onClose }) {
  useEffect(() => {
    if (!protocol) return undefined;
    const onKeyDown = (e) => {
      if (e.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [protocol, onClose]);

  if (!protocol) return null;
  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="protocol-modal-title"
      data-testid="protocol-modal"
    >
      <div className="modal-card">
        <div className="modal-header">
          <div>
            <span className="pill pill-teal" style={{ marginBottom: 6 }}>
              <Icon name="book" size={13} />
              <span>
                {protocol.protocol_id} · {protocol.category}
              </span>
            </span>
            <h2 id="protocol-modal-title" style={{ margin: 0, fontSize: "1.2rem" }}>
              {protocol.title}
            </h2>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            aria-label="Close protocol details"
            onClick={onClose}
            style={{ gap: 6 }}
          >
            <kbd className="keycap">Esc</kbd>
            <Icon name="x" size={16} />
          </button>
        </div>

        <p style={{ margin: 0, fontSize: "0.9rem", color: "var(--text-secondary)" }}>
          {protocol.summary}
        </p>

        <div className="card-muted">
          <div
            style={{
              fontSize: "0.7rem",
              fontWeight: 700,
              letterSpacing: "0.08em",
              color: "var(--text-muted)",
              marginBottom: 8,
            }}
          >
            ACTION CHECKLIST
          </div>
          <ol
            style={{
              margin: 0,
              paddingLeft: 18,
              display: "flex",
              flexDirection: "column",
              gap: 6,
              fontSize: "0.86rem",
            }}
          >
            {(protocol.steps || []).map((st) => (
              <li key={st}>{st}</li>
            ))}
          </ol>
        </div>

        <div
          className="card-red"
          style={{
            border: "1px solid var(--red-border)",
            borderRadius: 10,
            padding: "10px 13px",
            fontSize: "0.82rem",
            color: "var(--red-text)",
          }}
        >
          <strong>Stop &amp; escalate if:</strong> {protocol.escalate_if}
        </div>

        <div className="modal-footer">
          <span style={{ fontSize: "0.74rem", color: "var(--text-muted)" }}>
            {protocol.note || "Decision support only, not a diagnosis."}
          </span>
          <button type="button" className="btn btn-primary btn-sm" onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [day, setDay] = useState(23);
  const [role, setRole] = useState("Astronaut");
  const [selectedCrewId, setSelectedCrewId] = useState("ast-01");
  const [activeTab, setActiveTab] = useState("briefing");
  const [isPlaying, setIsPlaying] = useState(false);

  const [state, setState] = useState(() =>
    getFallbackState({ day: 23, role: "Astronaut", crewId: "ast-01" })
  );
  const [isLiveApi, setIsLiveApi] = useState(false);

  const [sosModalOpen, setSosModalOpen] = useState(false);
  const [sosModalMode, setSosModalMode] = useState("compose");
  const [activeProtocolId, setActiveProtocolId] = useState(null);

  const refreshState = useCallback(
    async (opts = {}) => {
      const targetDay = opts.day ?? day;
      const targetRole = opts.role ?? role;
      const targetCrew = opts.crewId ?? selectedCrewId;
      const { state: nextState, isLive } = await fetchState({
        day: targetDay,
        role: targetRole,
        crewId: targetCrew,
      });
      setState(nextState);
      setIsLiveApi(isLive);
    },
    [day, role, selectedCrewId]
  );

  useEffect(() => {
    refreshState();
  }, [refreshState]);

  // Mission timeline Play/Pause loop
  useEffect(() => {
    if (!isPlaying) return undefined;
    const id = setInterval(() => {
      setDay((prev) => {
        if (prev >= 30) {
          setIsPlaying(false);
          return 30;
        }
        return prev + 1;
      });
    }, 1300);
    return () => clearInterval(id);
  }, [isPlaying]);

  const handleChangeRole = (nextRole) => {
    setRole(nextRole);
    const navCfg = WORKSPACE_NAV[nextRole] || WORKSPACE_NAV.Astronaut;
    setActiveTab(navCfg.defaultTab);
  };

  const handleToggleLink = async () => {
    const nextOnline = !(state?.online || state?.earth_link?.online);
    await toggleEarthLink({ online: nextOnline });
    await refreshState();
  };

  const handleFastForward = async () => {
    await fastForwardSync();
    await refreshState();
  };

  const handleTriggerSos = async ({ astronautId, sosType, note }) => {
    const { packet } = await triggerSos({
      astronautId: astronautId || selectedCrewId,
      sosType,
      note,
      day,
      hour: state?.hour ?? 16,
    });
    await refreshState();
    return packet;
  };

  const handleCancelSos = async ({ sosId, reason }) => {
    await cancelSos({ sosId, reason });
    await refreshState();
  };

  const handleAcknowledgeSos = async (arg) => {
    const sosId = typeof arg === "string" ? arg : arg?.sosId || arg?.sos_id;
    if (!sosId) return;
    await acknowledgeSos({ sosId, actorRole: role });
    await refreshState();
  };

  const handleResolveSos = async (sosId) => {
    await resolveSos({ sosId });
    await refreshState();
  };

  const handleSubmitCheckin = async (payload) => {
    await submitCheckin({
      ...payload,
      astronautId: selectedCrewId,
      day,
    });
    await refreshState();
  };

  const handleSubmitPvt = async (payload) => {
    await submitPvt({
      ...payload,
      astronautId: selectedCrewId,
      day,
    });
    await refreshState();
  };

  const handleSendMessage = async (rawPayload) => {
    // Supports both MessagesView ({ fromId, toId, ... }) and GroundSupportView ({ from, to, text, ... })
    const toRaw = rawPayload.toId || rawPayload.to || rawPayload.recipient || "earth";
    const toLower = String(toRaw).toLowerCase();
    const mappedTo = toLower.includes("all")
      ? "all"
      : toLower.includes("earth") || toLower.includes("home")
      ? "earth"
      : toLower.includes("health")
      ? "health_officer"
      : toRaw;

    const fromRaw = rawPayload.fromId || rawPayload.from || rawPayload.sender || selectedCrewId;
    const fromLower = String(fromRaw).toLowerCase();
    const mappedFrom = fromLower.includes("earth") || fromLower.includes("home")
      ? "earth"
      : fromRaw;

    await sendMessage({
      fromId: mappedFrom,
      toId: mappedTo,
      kind: rawPayload.kind || rawPayload.message_type || "text",
      body: rawPayload.body || rawPayload.text || "",
      audioDurationS: rawPayload.audioDurationS || 0,
      sizeKb: rawPayload.sizeKb || 2,
      attachChart: Boolean(rawPayload.attachChart || rawPayload.attach_summary),
      day,
    });
    await refreshState();
  };

  const handleMarkMessageRead = async (arg) => {
    const messageId = typeof arg === "string" ? arg : arg?.messageId || arg?.message_id;
    if (!messageId) return;
    await markMessageRead({ messageId, readerRole: role });
    await refreshState();
  };

  const handleUpdateConsent = async ({ astronautId, mode, scope, enabled }) => {
    await updateConsent({ astronautId, mode, scope, enabled });
    await refreshState();
  };

  const handleAskAdvisor = async (question) => {
    const { reply } = await askAdvisor({
      question,
      day,
      role,
      crewId: selectedCrewId,
    });
    return reply;
  };

  const handleRunWhatIf = useCallback(async (params) => {
    const { projection } = await runWhatIf(params);
    return projection;
  }, []);

  const handleReviewSafety = () => {
    if (role === "Crew Health Officer") {
      setActiveTab("overview");
      return;
    }
    setSosModalMode("status");
    setSosModalOpen(true);
  };

  const navConfig = WORKSPACE_NAV[role] || WORKSPACE_NAV.Astronaut;
  const currentCrew =
    (state?.crew_roster || []).find((c) => c.astronaut_id === selectedCrewId) ||
    state?.crew_roster?.[0];

  const isOnline = Boolean(state?.online || state?.earth_link?.online);
  const metHours = state?.met_hours ?? day * 24 - 14;
  const earthDelay = state?.earth_delay_min ?? 12.8;

  const activeProtocol =
    activeProtocolId &&
    (state?.protocols?.[activeProtocolId] || PROTOCOL_LIBRARY[activeProtocolId]);

  const sharedFe2Props = {
    state,
    selectedCrewId,
    onSelectCrew: (cid) => setSelectedCrewId(cid),
    onAcknowledgeSos: handleAcknowledgeSos,
    onOpenProtocol: (pid) => setActiveProtocolId(pid),
    activeSubTab: activeTab,
    onToggleLink: handleToggleLink,
    onFastForward: handleFastForward,
    onSendMessage: handleSendMessage,
    onMarkMessageRead: handleMarkMessageRead,
  };

  const renderMainView = () => {
    if (role === "Astronaut") {
      if (activeTab === "advisor") {
        return (
          <AdvisorView
            state={state}
            onAskAdvisor={handleAskAdvisor}
            onRunWhatIf={handleRunWhatIf}
            onOpenProtocol={(pid) => setActiveProtocolId(pid)}
          />
        );
      }
      if (activeTab === "messages") {
        return (
          <MessagesView
            state={state}
            onSendMessage={handleSendMessage}
            onMarkMessageRead={handleMarkMessageRead}
          />
        );
      }
      if (activeTab === "privacy") {
        return (
          <PrivacyConsentView
            state={state}
            onUpdateConsent={handleUpdateConsent}
            readOnly={false}
          />
        );
      }
      return (
        <AstronautBriefing
          state={state}
          onNavigate={(tab) => setActiveTab(tab)}
          onOpenProtocol={(pid) => setActiveProtocolId(pid)}
          onSubmitCheckin={handleSubmitCheckin}
          onSubmitPvt={handleSubmitPvt}
        />
      );
    }

    if (role === "Crew Health Officer") {
      if (activeTab === "habitat") {
        return <SystemsEngineerView {...sharedFe2Props} activeSubTab="habitat" />;
      }
      if (activeTab === "advisor") {
        return (
          <AdvisorView
            state={state}
            onAskAdvisor={handleAskAdvisor}
            onRunWhatIf={handleRunWhatIf}
            onOpenProtocol={(pid) => setActiveProtocolId(pid)}
          />
        );
      }
      if (activeTab === "messages") {
        return (
          <MessagesView
            state={state}
            onSendMessage={handleSendMessage}
            onMarkMessageRead={handleMarkMessageRead}
          />
        );
      }
      if (activeTab === "privacy") {
        return (
          <PrivacyConsentView
            state={state}
            onUpdateConsent={handleUpdateConsent}
            readOnly={true}
          />
        );
      }
      return <HealthOfficerView {...sharedFe2Props} />;
    }

    if (role === "Systems Engineer") {
      return <SystemsEngineerView {...sharedFe2Props} />;
    }

    return <GroundSupportView {...sharedFe2Props} />;
  };

  return (
    <div className="astra-shell">
      <Header
        day={day}
        hour={state?.hour ?? 16}
        role={role}
        selectedCrewId={selectedCrewId}
        crewRoster={state?.crew_roster || []}
        online={isOnline}
        isLiveApi={isLiveApi}
        isPlaying={isPlaying}
        activeSafetyRules={state?.safety?.active_rules || state?.active_safety_rules || []}
        onChangeDay={(d) => {
          setIsPlaying(false);
          setDay(d);
        }}
        onTogglePlay={() => setIsPlaying((p) => !p)}
        onResetTimeline={() => {
          setIsPlaying(false);
          setDay(23);
        }}
        onChangeRole={handleChangeRole}
        onChangeCrew={(cid) => setSelectedCrewId(cid)}
        onToggleLink={handleToggleLink}
        onOpenSos={() => {
          setSosModalMode("compose");
          setSosModalOpen(true);
        }}
        onReviewSafety={handleReviewSafety}
      />

      <div className="workspace-layout">
        {/* Left Navigation Sidebar */}
        <aside className="sidebar" aria-label="Workspace navigation">
          <nav className="sidebar-nav">
            <div className="sidebar-eyebrow">{navConfig.eyebrow}</div>
            {navConfig.items.map((item) => {
              const active = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`nav-item ${active ? "active" : ""}`}
                  aria-current={active ? "page" : undefined}
                  onClick={() => setActiveTab(item.id)}
                >
                  <span className="nav-item-icon">
                    <NavIcon id={item.id} />
                  </span>
                  <span>
                    <span className="nav-item-label">{item.label}</span>
                    <span className="nav-item-sub">{item.sub}</span>
                  </span>
                </button>
              );
            })}
          </nav>

          <div className="onboard-card">
            <div className="onboard-card-title">
              {isOnline ? <Icon name="radio" size={15} /> : <Icon name="zap" size={15} />}
              <span>{isOnline ? "EARTH LINK ONLINE" : "ON-BOARD MODE"}</span>
            </div>
            <p className="onboard-card-body">
              {isOnline
                ? "Store-and-forward queue is syncing in strict priority order: SOS → critical → messages → summaries."
                : "Everything continues locally. Actions are queued and never silently dropped."}
            </p>
            <div className="onboard-card-meta">
              MET {metHours}h · ~{earthDelay} min one-way Earth delay
            </div>
          </div>

          <div className="sidebar-footnote">
            {role} scope · ~{earthDelay} min one-way light time
          </div>
        </aside>

        {/* Active View Content */}
        <main className="main-content">{renderMainView()}</main>
      </div>

      {/* Mobile Bottom Navigation Bar */}
      <nav className="mobile-nav" aria-label="Mobile navigation">
        {navConfig.items.map((item) => {
          const active = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              className={`mobile-nav-item ${active ? "active" : ""}`}
              onClick={() => setActiveTab(item.id)}
            >
              <span className="mobile-nav-icon">
                <NavIcon id={item.id} />
              </span>
              <span>{item.shortLabel}</span>
            </button>
          );
        })}
      </nav>

      {/* Emergency SOS Modal */}
      <SOSModal
        isOpen={sosModalOpen}
        initialMode={sosModalMode}
        astronautId={selectedCrewId}
        astronautName={currentCrew?.name || "Cmdr. Elena Vasquez"}
        sosEvents={state?.sos_events || []}
        onClose={() => setSosModalOpen(false)}
        onTriggerSos={handleTriggerSos}
        onCancelSos={handleCancelSos}
        onAcknowledgeSos={handleAcknowledgeSos}
        onResolveSos={handleResolveSos}
      />

      {/* Protocol Detail Modal */}
      <ProtocolModal
        protocol={activeProtocol}
        onClose={() => setActiveProtocolId(null)}
      />
    </div>
  );
}
