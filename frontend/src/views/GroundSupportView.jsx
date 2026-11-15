import React, { useMemo, useState } from 'react';

/**
 * Inline icon primitives for GroundSupportView (zero external icon packages).
 */
function Icon({ name, size = 14 }) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': 'true',
  };

  switch (name) {
    case 'alert-octagon':
      return (
        <svg {...common}>
          <polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      );
    case 'alert-triangle':
      return (
        <svg {...common}>
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
          <line x1="12" y1="9" x2="12" y2="13" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
      );
    case 'check-circle':
      return (
        <svg {...common}>
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
          <polyline points="22 4 12 14.01 9 11.01" />
        </svg>
      );
    case 'pulse':
      return (
        <svg {...common}>
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      );
    case 'wind':
      return (
        <svg {...common}>
          <path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2" />
        </svg>
      );
    case 'shield':
      return (
        <svg {...common}>
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        </svg>
      );
    case 'x-circle':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="10" />
          <line x1="15" y1="9" x2="9" y2="15" />
          <line x1="9" y1="9" x2="15" y2="15" />
        </svg>
      );
    case 'radio':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="2" />
          <path d="M16.24 7.76a6 6 0 0 1 0 8.49" />
          <path d="M7.76 16.24a6 6 0 0 1 0-8.49" />
          <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
          <path d="M4.93 19.07a10 10 0 0 1 0-14.14" />
        </svg>
      );
    case 'radio-off':
      return (
        <svg {...common}>
          <line x1="2" y1="2" x2="22" y2="22" />
          <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
          <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
          <line x1="12" y1="20" x2="12.01" y2="20" />
        </svg>
      );
    case 'users':
      return (
        <svg {...common}>
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
      );
    case 'clock':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
      );
    case 'send':
      return (
        <svg {...common}>
          <line x1="22" y1="2" x2="11" y2="13" />
          <polygon points="22 2 15 22 11 13 2 9 22 2" />
        </svg>
      );
    case 'lock':
      return (
        <svg {...common}>
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      );
    default:
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
        </svg>
      );
  }
}

const QUEUE_BUCKETS = [
  { priority: 0, category: 'sos', title: 'SOS', subtitle: 'Emergency beacon', defaultCount: 1 },
  {
    priority: 1,
    category: 'critical_alert',
    title: 'Critical alerts',
    subtitle: 'Deterministic safety rules',
    defaultCount: 1,
  },
  {
    priority: 2,
    category: 'message',
    title: 'Messages',
    subtitle: 'Crew and Earth traffic',
    defaultCount: 2,
  },
  {
    priority: 3,
    category: 'summary',
    title: 'Summaries',
    subtitle: 'Daily briefings and reports',
    defaultCount: 2,
  },
  {
    priority: 4,
    category: 'telemetry',
    title: 'Telemetry',
    subtitle: 'Bulk sensor batches',
    defaultCount: 1,
  },
];

const DEFAULT_EARTH_MESSAGES = [
  {
    message_id: 'msg-earth-01',
    from: 'On-board Crew (consented relay)',
    to: 'Home (Earth)',
    timestamp_label: 'Day 23, 13:45 · Earth light time 12.8 min',
    body: 'Attaching consented 7-day aggregate summary. Recovery block scheduled on board.',
    status: 'queued',
    attachment_label: 'Consented summary chart (metadata only)',
  },
  {
    message_id: 'msg-earth-02',
    from: 'Home (Earth)',
    to: 'All crew',
    timestamp_label: 'Day 20, 06:00 · Earth light time 12.8 min',
    body: 'Received Day 20 summary. Keep the daily check-ins coming, even short ones. Earth medical is reviewing aggregate trends; no new instructions until the next window.',
    status: 'delivered',
  },
];

function getSyncStateMeta(status) {
  const s = String(status || 'queued').toLowerCase();
  if (s === 'acknowledged' || s === 'delivered' || s === 'read') {
    return { pillClass: 'pill-teal', icon: 'check-circle', label: s };
  }
  if (s === 'transmitting' || s === 'sent') {
    return { pillClass: 'pill-purple', icon: 'radio', label: s };
  }
  return { pillClass: 'pill-amber', icon: 'clock', label: s };
}

function normalizeSubTab(raw) {
  const key = String(raw || 'summary').toLowerCase();
  if (key.includes('relay') || key.includes('comm') || key.includes('msg')) return 'relay';
  if (key.includes('scope') || key.includes('access')) return 'scope';
  return 'summary';
}

function normalizeGroundModel(state) {
  const safeState = state || {};
  const day = safeState.day ?? safeState.mission_day ?? safeState.currentDay ?? 23;
  const hour = safeState.hour ?? 16;
  const isOnline = Boolean(
    safeState.earth_link?.online ??
      safeState.sync_queue?.online ??
      safeState.online ??
      safeState.earth_link_online ??
      false
  );
  const lightDelayMin =
    safeState.earth_delay_min ?? safeState.earth_link?.delay_minutes ?? 12.8;

  // Compute mission-level band counts WITHOUT exposing names
  const ground = safeState.ground_summary || safeState.groundSummary || {};
  const bandCounts = ground.band_counts || ground.bands || null;
  const crewList = Array.isArray(safeState.crew_overview)
    ? safeState.crew_overview
    : Array.isArray(safeState.crew)
    ? safeState.crew
    : [];

  let safetyReviewCount;
  let reducedCount;
  let monitorCount;

  if (bandCounts) {
    safetyReviewCount = bandCounts.safety_review ?? 1;
    reducedCount = bandCounts.reduced ?? 1;
    monitorCount = (bandCounts.monitor ?? 0) + (bandCounts.steady ?? 0);
  } else if (crewList.length > 0) {
    safetyReviewCount = 0;
    reducedCount = 0;
    monitorCount = 0;
    for (const c of crewList) {
      const st = String(c.band || c.status || '').toLowerCase();
      if (st.includes('safety') || st.includes('support') || c.safety_count > 0) {
        safetyReviewCount += 1;
      } else if (st.includes('reduced') || st.includes('check-in')) {
        reducedCount += 1;
      } else {
        monitorCount += 1;
      }
    }
  } else {
    safetyReviewCount = 1;
    reducedCount = 1;
    monitorCount = 2;
  }

  const crewOnBoard = ground.crew_count ?? (crewList.length || 4);
  const safetyEventsCount =
    ground.safety_events_count ??
    (Array.isArray(safeState.safety?.active_rules)
      ? safeState.safety.active_rules.length
      : null) ??
    1;
  const advisoryAlertsCount = ground.advisory_alerts_count ?? 4;

  // Normalize Earth sync queue (handles `{ items: [...] }` from fallbackData OR `[...]` from live API)
  const rawQueue = Array.isArray(safeState.sync_queue)
    ? safeState.sync_queue
    : Array.isArray(safeState.sync_queue?.items)
    ? safeState.sync_queue.items
    : Array.isArray(safeState.earth_queue)
    ? safeState.earth_queue
    : [];
  const hasExplicitQueue = rawQueue.length > 0;

  const queueRows = QUEUE_BUCKETS.map((bucket) => {
    if (!hasExplicitQueue) {
      return {
        ...bucket,
        count: bucket.defaultCount,
        status: isOnline ? 'acknowledged' : 'queued',
      };
    }

    const matching = rawQueue.filter((item) => {
      const cat = String(item.category || '').toLowerCase();
      return item.priority === bucket.priority || cat === bucket.category;
    });

    let dominantStatus = 'queued';
    if (matching.length === 0) {
      dominantStatus = 'acknowledged';
    } else if (matching.some((m) => m.status === 'queued')) {
      dominantStatus = 'queued';
    } else if (matching.some((m) => m.status === 'transmitting')) {
      dominantStatus = 'transmitting';
    } else if (matching.some((m) => m.status === 'delivered')) {
      dominantStatus = 'delivered';
    } else {
      dominantStatus = 'acknowledged';
    }

    return {
      ...bucket,
      count: matching.length,
      status: dominantStatus,
    };
  });

  const totalQueueCount = queueRows.reduce((sum, r) => sum + r.count, 0);

  // Aggregate ground-sharing consent counts ONLY (no astronaut identities!)
  const consentMatrix =
    safeState.consent_matrix || safeState.consentMatrix || safeState.consents || {};
  const consentEntries = Object.values(consentMatrix || {});
  const sharedConsentCount =
    consentEntries.length > 0
      ? consentEntries.filter((p) => Boolean(p?.normal?.ground_sharing ?? p?.normal?.ground))
          .length
      : 3;

  // Filter Earth-bound / Ground-visible messages (anonymizing individual crew senders)
  const rawMsgs = Array.isArray(safeState.messages) ? safeState.messages : [];
  const earthMsgs =
    rawMsgs.length > 0
      ? rawMsgs
          .filter((m) => {
            const to = String(m.to_id || m.to_label || m.to || m.recipient || '').toLowerCase();
            const from = String(m.from_id || m.from_label || m.from || m.sender || '').toLowerCase();
            return (
              m.channel === 'earth' ||
              to.includes('earth') ||
              to.includes('ground') ||
              to.includes('home') ||
              to.includes('all') ||
              from.includes('earth') ||
              from.includes('ground') ||
              from.includes('home')
            );
          })
          .map((m) => {
            const fromRaw = String(m.from_id || m.from_label || m.from || m.sender || '').toLowerCase();
            const fromIsEarth =
              fromRaw.includes('earth') || fromRaw.includes('ground') || fromRaw.includes('home');
            return {
              message_id: m.message_id || m.id,
              from: fromIsEarth ? 'Home (Earth)' : 'On-board Crew (consented relay)',
              to: m.to_label || m.to || m.recipient || 'Home (Earth)',
              timestamp_label:
                m.timestamp_label ||
                m.created_at ||
                `Day ${day}, ${String(hour).padStart(2, '0')}:00 · Earth light time ${lightDelayMin} min`,
              body: m.body || m.text || m.content || '',
              status: m.status || (isOnline ? 'delivered' : 'queued'),
              attachment_label:
                m.attachment?.label ||
                m.attachment_label ||
                (m.attach_summary ? 'Consented summary chart' : ''),
            };
          })
      : DEFAULT_EARTH_MESSAGES;

  const sharedEnvCount =
    ground.shared_exposure_signal?.affected_crew_count ??
    safeState.environment?.shared_exposure_alert?.affected_crew_count ??
    2;

  return {
    day,
    hour,
    isOnline,
    lightDelayMin,
    safetyReviewCount,
    reducedCount,
    monitorCount,
    crewOnBoard,
    safetyEventsCount,
    advisoryAlertsCount,
    sharedEnvCount,
    queueRows,
    totalQueueCount,
    sharedConsentCount,
    totalCrew: consentEntries.length || crewOnBoard,
    earthMsgs,
  };
}

/**
 * Ground Support view (F-24) — Mission-level aggregate readiness bands,
 * anonymized shared exposure alert, privacy boundary checklist,
 * prioritized store-and-forward Earth queue, and delay-tolerant Earth relay.
 */
export default function GroundSupportView({
  state,
  activeSubTab,
  onToggleLink,
  onFastForward,
  onSendMessage,
  onMarkMessageRead,
}) {
  const subTab = normalizeSubTab(activeSubTab);
  const model = useMemo(() => normalizeGroundModel(state), [state]);

  const [draftRecipient, setDraftRecipient] = useState('All crew');
  const [draftUrgency, setDraftUrgency] = useState('routine');
  const [draftBody, setDraftBody] = useState('');
  const [relayNotice, setRelayNotice] = useState('');

  const asOfLabel = `As of Day ${model.day} · ${String(model.hour).padStart(2, '0')}:00 ship time`;

  const handleSendGroundMessage = (e) => {
    e.preventDefault();
    const trimmed = draftBody.trim();
    if (!trimmed) return;
    if (onSendMessage) {
      onSendMessage({
        fromId: 'earth',
        toId: draftRecipient === 'Crew Health Officer' ? 'health_officer' : 'all',
        kind: 'text',
        from: 'Home (Earth)',
        sender: 'Home (Earth)',
        to: draftRecipient,
        recipient: draftRecipient,
        body: trimmed,
        text: trimmed,
        urgency: draftUrgency,
        priority: draftUrgency,
        message_type: 'text',
        attachChart: false,
        attach_summary: false,
        day: model.day,
      });
    }
    setDraftBody('');
    setRelayNotice(
      model.isOnline
        ? `Advisory queued for ${draftRecipient} (~${model.lightDelayMin} min one-way delay).`
        : 'Link offline — advisory stored in Priority 2 queue and never dropped.'
    );
  };

  if (subTab === 'relay') {
    return (
      <div className="stack-col" data-testid="ground-support-relay">
        <header className="page-header">
          <div>
            <div className="page-eyebrow">Delay-Tolerant Earth Comms</div>
            <h1>Earth relay</h1>
            <p className="page-subtitle">
              Ground advises, never controls. Messages queue locally across link drops with ~
              {model.lightDelayMin} min one-way light delay. {asOfLabel}.
            </p>
          </div>
          <div className="page-header-pills">
            <span className={`pill ${model.isOnline ? 'pill-teal' : 'pill-amber'}`}>
              <Icon name={model.isOnline ? 'radio' : 'radio-off'} size={12} />
              <span>{model.isOnline ? 'Earth link online' : 'On-board mode'}</span>
            </span>
            <span className="pill pill-neutral">Queue {model.totalQueueCount}</span>
          </div>
        </header>

        <div
          className="card"
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            flexWrap: 'wrap',
          }}
        >
          <div style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
            <strong>Store-and-forward link control:</strong>{' '}
            {model.isOnline
              ? 'Earth link connected. Priority packets can transmit in strict order.'
              : 'Earth link offline. Packets remain safely queued at priority 0–4.'}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => onToggleLink && onToggleLink()}
            >
              <Icon name={model.isOnline ? 'radio-off' : 'radio'} size={14} />
              <span>{model.isOnline ? 'Disconnect Earth link' : 'Connect Earth link'}</span>
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!model.isOnline}
              onClick={() => onFastForward && onFastForward()}
            >
              <span>Fast-forward sync</span>
            </button>
          </div>
        </div>

        <div className="split-main-aside">
          <section className="card" aria-label="Earth message traffic">
            <div className="card-header">
              <div>
                <h2 className="card-title">Earth relay traffic</h2>
                <p className="card-subtitle">
                  Opaque store-and-forward packets; content is never analyzed for behavioural
                  scoring.
                </p>
              </div>
              <span className="pill pill-neutral tabular-nums">{model.earthMsgs.length} packets</span>
            </div>

            <div className="stack-col" style={{ gap: 10 }}>
              {model.earthMsgs.map((msg, idx) => {
                const msgId = msg.message_id || `earth-msg-${idx}`;
                const stMeta = getSyncStateMeta(msg.status);
                const isRead = String(msg.status).toLowerCase() === 'read';

                return (
                  <div key={msgId} className="card-muted">
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        gap: 8,
                        flexWrap: 'wrap',
                      }}
                    >
                      <div>
                        <strong style={{ fontSize: '0.88rem' }}>
                          {msg.from} → {msg.to}
                        </strong>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {msg.timestamp_label}
                        </div>
                      </div>
                      <span className={`pill ${stMeta.pillClass}`}>
                        <Icon name={stMeta.icon} size={12} />
                        <span>{stMeta.label}</span>
                      </span>
                    </div>

                    <p style={{ margin: '8px 0 0', fontSize: '0.84rem', color: 'var(--text-primary)' }}>
                      {msg.body}
                    </p>

                    {msg.attachment_label ? (
                      <div className="pill pill-teal" style={{ marginTop: 8 }}>
                        <Icon name="check-circle" size={12} />
                        <span>{msg.attachment_label}</span>
                      </div>
                    ) : null}

                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 8 }}>
                      <button
                        type="button"
                        className="btn btn-sm btn-ghost"
                        disabled={isRead}
                        onClick={() => onMarkMessageRead && onMarkMessageRead(msgId)}
                      >
                        <Icon name="check-circle" size={13} />
                        <span>{isRead ? 'Read' : 'Mark read'}</span>
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="card" aria-label="Compose Earth advisory">
            <div className="card-header">
              <div>
                <h2 className="card-title">Send Ground advisory</h2>
                <p className="card-subtitle">
                  Advisory guidance only — flight crew retains all onboard authority.
                </p>
              </div>
            </div>

            <form className="stack-col" style={{ gap: 12 }} onSubmit={handleSendGroundMessage}>
              <div>
                <label
                  htmlFor="ground-recipient"
                  className="page-eyebrow"
                  style={{ display: 'block', marginBottom: 6 }}
                >
                  Destination
                </label>
                <select
                  id="ground-recipient"
                  className="topbar-select-group select-input"
                  style={{ width: '100%' }}
                  value={draftRecipient}
                  onChange={(e) => setDraftRecipient(e.target.value)}
                >
                  <option value="All crew">All crew (mission advisory)</option>
                  <option value="Crew Health Officer">Crew Health Officer</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="ground-urgency"
                  className="page-eyebrow"
                  style={{ display: 'block', marginBottom: 6 }}
                >
                  Priority tier
                </label>
                <select
                  id="ground-urgency"
                  className="topbar-select-group select-input"
                  style={{ width: '100%' }}
                  value={draftUrgency}
                  onChange={(e) => setDraftUrgency(e.target.value)}
                >
                  <option value="routine">Routine (Priority 2)</option>
                  <option value="urgent">Urgent advisory (Priority 2)</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="ground-body"
                  className="page-eyebrow"
                  style={{ display: 'block', marginBottom: 6 }}
                >
                  Advisory message
                </label>
                <textarea
                  id="ground-body"
                  rows={4}
                  placeholder="Write mission-level guidance for crew or Health Officer..."
                  value={draftBody}
                  onChange={(e) => setDraftBody(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 10,
                    border: '1px solid var(--border-strong)',
                    background: 'var(--bg-surface)',
                    resize: 'vertical',
                  }}
                />
              </div>

              <button type="submit" className="btn btn-primary" disabled={!draftBody.trim()}>
                <Icon name="send" size={14} />
                <span>Queue Earth message</span>
              </button>

              {relayNotice ? (
                <div className="card-muted" style={{ fontSize: '0.79rem', color: 'var(--teal)' }}>
                  {relayNotice}
                </div>
              ) : null}
            </form>
          </section>
        </div>
      </div>
    );
  }

  if (subTab === 'scope') {
    return (
      <div className="stack-col" data-testid="ground-support-scope">
        <header className="page-header">
          <div>
            <div className="page-eyebrow">Privacy &amp; Authority Boundary</div>
            <h1>Access scope</h1>
            <p className="page-subtitle">
              Ground advises, never controls. Individual crew names, raw vitals, private journals,
              and per-astronaut consent switches never leave the ship unconsented.
            </p>
          </div>
          <span className="pill pill-purple">
            <Icon name="lock" size={12} />
            <span>Mission-level only</span>
          </span>
        </header>

        <div className="grid-2">
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">What Ground Support receives</h2>
              <span className="pill pill-teal">
                <Icon name="check-circle" size={12} />
                <span>Permitted</span>
              </span>
            </div>
            <div className="stack-col" style={{ gap: 8 }}>
              <div className="boundary-item">
                <span style={{ color: 'var(--teal)' }}>
                  <Icon name="check-circle" size={15} />
                </span>
                <span>Aggregate crew readiness counts (Safety review / Reduced / Monitor)</span>
              </div>
              <div className="boundary-item">
                <span style={{ color: 'var(--teal)' }}>
                  <Icon name="check-circle" size={15} />
                </span>
                <span>Anonymised habitat shared-exposure cluster counts</span>
              </div>
              <div className="boundary-item">
                <span style={{ color: 'var(--teal)' }}>
                  <Icon name="check-circle" size={15} />
                </span>
                <span>
                  Consented summary charts ({model.sharedConsentCount} of {model.totalCrew} crew
                  currently enable routine ground summary sharing)
                </span>
              </div>
              <div className="boundary-item">
                <span style={{ color: 'var(--teal)' }}>
                  <Icon name="check-circle" size={15} />
                </span>
                <span>Store-and-forward queue depth &amp; SOS emergency beacons</span>
              </div>
            </div>
          </section>

          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Withheld on board</h2>
              <span className="pill pill-neutral">
                <Icon name="lock" size={12} />
                <span>Protected</span>
              </span>
            </div>
            <div className="stack-col" style={{ gap: 8 }}>
              {[
                'Individual astronaut names, initials, or per-crew clinical cards',
                'Raw heart rate, HRV, SpO2, sleep, or PVT latency records',
                'Private 60-second check-in notes or on-device journal entries',
                'Per-astronaut normal/emergency consent toggle configuration',
              ].map((txt) => (
                <div key={txt} className="boundary-item blocked">
                  <Icon name="x-circle" size={15} />
                  <span>{txt}</span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    );
  }

  // Default: Mission summary workspace
  return (
    <div className="stack-col" data-testid="ground-support-view">
      {/* Page Header */}
      <header className="page-header">
        <div>
          <div className="page-eyebrow">Mission-Level · No Individual Identity</div>
          <h1>Ground summary</h1>
          <p className="page-subtitle">
            No identities or raw health records are exposed to Ground Support. {asOfLabel}.
          </p>
        </div>
        <div className="page-header-pills">
          <span className={`pill ${model.isOnline ? 'pill-teal' : 'pill-amber'}`}>
            <Icon name={model.isOnline ? 'radio' : 'radio-off'} size={13} />
            <span>{model.isOnline ? 'Earth link online' : 'On-board mode'}</span>
          </span>
          <span className="pill pill-neutral">
            <Icon name="radio" size={13} />
            <span>Queue {model.totalQueueCount}</span>
          </span>
        </div>
      </header>

      {/* 3 Readiness Band Counter Cards */}
      <section className="grid-3" aria-label="Mission readiness bands">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
            <div className="page-eyebrow" style={{ margin: 0 }}>
              Safety Review
            </div>
            <span className="pill pill-red">
              <Icon name="alert-octagon" size={12} />
              <span>Safety review</span>
            </span>
          </div>
          <div className="metric-big" style={{ margin: '10px 0 4px' }}>
            {model.safetyReviewCount}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            crew {model.safetyReviewCount === 1 ? 'member' : 'members'}
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
            <div className="page-eyebrow" style={{ margin: 0 }}>
              Reduced
            </div>
            <span className="pill pill-amber">
              <Icon name="alert-triangle" size={12} />
              <span>Reduced</span>
            </span>
          </div>
          <div className="metric-big" style={{ margin: '10px 0 4px' }}>
            {model.reducedCount}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            crew {model.reducedCount === 1 ? 'member' : 'members'}
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
            <div className="page-eyebrow" style={{ margin: 0 }}>
              Monitor
            </div>
            <span className="pill pill-teal">
              <Icon name="check-circle" size={12} />
              <span>Monitor</span>
            </span>
          </div>
          <div className="metric-big" style={{ margin: '10px 0 4px' }}>
            {model.monitorCount}
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            crew {model.monitorCount === 1 ? 'member' : 'members'}
          </div>
        </div>
      </section>

      {/* Main Split: Aggregate mission picture + Earth queue | Privacy boundary */}
      <div className="split-main-aside">
        <div className="stack-col">
          {/* Aggregate mission picture */}
          <section className="card" aria-label="Aggregate mission picture">
            <div className="card-header">
              <div className="card-title-group">
                <span className="card-icon-badge">
                  <Icon name="pulse" size={17} />
                </span>
                <div>
                  <h2 className="card-title">Aggregate mission picture</h2>
                  <p className="card-subtitle">
                    Counts, not names. Ground never receives raw health records in this view.{' '}
                    <span className="tabular-nums">({asOfLabel})</span>
                  </p>
                </div>
              </div>
            </div>

            <div className="grid-3">
              <div className="card-muted card-red">
                <div className="page-eyebrow" style={{ color: 'var(--red-text)' }}>
                  Safety Events
                </div>
                <div className="metric-big" style={{ fontSize: '1.65rem' }}>
                  {model.safetyEventsCount}
                </div>
              </div>
              <div className="card-muted card-amber">
                <div className="page-eyebrow" style={{ color: 'var(--amber-text)' }}>
                  Advisory Alerts
                </div>
                <div className="metric-big" style={{ fontSize: '1.65rem' }}>
                  {model.advisoryAlertsCount}
                </div>
              </div>
              <div className="card-muted">
                <div className="page-eyebrow">Crew On Board</div>
                <div className="metric-big" style={{ fontSize: '1.65rem' }}>
                  {model.crewOnBoard}
                </div>
              </div>
            </div>

            <div
              className="card-muted"
              style={{
                marginTop: 12,
                display: 'flex',
                alignItems: 'flex-start',
                gap: 10,
              }}
            >
              <span style={{ color: 'var(--teal)', marginTop: 2 }}>
                <Icon name="wind" size={16} />
              </span>
              <div>
                <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>
                  Shared habitat exposure signal
                </div>
                <div style={{ fontSize: '0.81rem', color: 'var(--text-secondary)', marginTop: 2 }}>
                  {model.sharedEnvCount} anonymous crew members co-moving with US Lab CO2. The
                  Systems Engineer owns the hardware response.
                </div>
              </div>
            </div>
          </section>

          {/* Earth Queue */}
          <section className="card" aria-label="Earth store-and-forward queue">
            <div className="card-header" style={{ marginBottom: 10 }}>
              <div>
                <h2 className="card-title">Earth queue</h2>
                <p className="card-subtitle">
                  Store-and-forward order is fixed: SOS → critical alerts → messages → summaries →
                  telemetry.
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 14 }}>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => onToggleLink && onToggleLink()}
              >
                <Icon name={model.isOnline ? 'radio-off' : 'radio'} size={14} />
                <span>{model.isOnline ? 'Disconnect Earth link' : 'Connect Earth link'}</span>
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={!model.isOnline}
                title={
                  model.isOnline
                    ? 'Advance queued packets in strict priority order'
                    : 'Connect Earth link first to transmit queued packets'
                }
                onClick={() => onFastForward && onFastForward()}
              >
                <span>Fast-forward sync</span>
              </button>
            </div>

            <div className="stack-col" style={{ gap: 8 }}>
              {model.queueRows.map((row) => {
                const stMeta = getSyncStateMeta(row.status);
                return (
                  <div key={row.priority} className="queue-row">
                    <div className="queue-row-left">
                      <span className="queue-priority-idx">{row.priority}</span>
                      <div>
                        <div className="queue-row-title">{row.title}</div>
                        <div className="queue-row-sub">{row.subtitle}</div>
                      </div>
                    </div>
                    <div className="queue-row-right">
                      <span className="pill pill-neutral tabular-nums">
                        {row.count} {row.count === 1 ? 'item' : 'items'}
                      </span>
                      <span className={`pill ${stMeta.pillClass}`}>
                        <Icon name={stMeta.icon} size={12} />
                        <span>{stMeta.label}</span>
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        </div>

        {/* Right Aside: Privacy boundary + Onboard decision callout */}
        <aside className="stack-col" aria-label="Privacy boundary">
          <section className="card">
            <div className="card-header" style={{ marginBottom: 10 }}>
              <div className="card-title-group">
                <span className="card-icon-badge purple">
                  <Icon name="shield" size={16} />
                </span>
                <div>
                  <h2 className="card-title">Privacy boundary</h2>
                </div>
              </div>
            </div>
            <p className="card-subtitle" style={{ margin: '0 0 12px' }}>
              Ground Support receives mission summaries, anonymised environment aggregates and
              Earth-bound message traffic. It does not see identities, raw vitals, check-in notes or
              consent records.
            </p>

            <div className="stack-col" style={{ gap: 8 }}>
              {[
                { label: 'Mission-level readiness bands', allowed: true },
                { label: 'Anonymised environment cluster', allowed: true },
                { label: 'Delay-tolerant Earth relay', allowed: true },
                { label: 'Crew names or identifiers', allowed: false },
                { label: 'Raw physiology or PVT', allowed: false },
                { label: 'Private check-in notes', allowed: false },
                { label: 'Consent records', allowed: false },
              ].map((item) => (
                <div
                  key={item.label}
                  className={`boundary-item ${item.allowed ? '' : 'blocked'}`}
                >
                  <span style={{ color: item.allowed ? 'var(--teal)' : 'var(--text-muted)' }}>
                    <Icon name={item.allowed ? 'check-circle' : 'x-circle'} size={15} />
                  </span>
                  <span>{item.label}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="card card-teal" style={{ fontSize: '0.82rem', color: 'var(--mint-text)' }}>
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
              <Icon name="users" size={17} />
              <div>
                <p style={{ margin: 0 }}>
                  If ground medical needs detail, the Crew Health Officer requests it through the
                  astronaut&apos;s consent or a logged emergency override. The decision stays on
                  board.
                </p>
                <p style={{ margin: '8px 0 0', fontSize: '0.76rem', opacity: 0.9 }}>
                  Ground advises, never controls · ~{model.lightDelayMin} min one-way light time.
                </p>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
