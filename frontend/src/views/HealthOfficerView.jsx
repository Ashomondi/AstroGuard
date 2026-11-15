import React, { useMemo, useState } from 'react';

/**
 * Shared inline icon primitives (zero third-party icon dependencies).
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
    case 'lock':
      return (
        <svg {...common}>
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      );
    case 'eye':
      return (
        <svg {...common}>
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      );
    case 'pulse':
      return (
        <svg {...common}>
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      );
    case 'heart':
      return (
        <svg {...common}>
          <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
        </svg>
      );
    case 'sparkle':
      return (
        <svg {...common}>
          <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />
        </svg>
      );
    case 'message':
      return (
        <svg {...common}>
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      );
    case 'shield':
      return (
        <svg {...common}>
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
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
    case 'book':
      return (
        <svg {...common}>
          <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
          <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
        </svg>
      );
    case 'chevron':
      return (
        <svg {...common}>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      );
    case 'chevron-right':
      return (
        <svg {...common}>
          <polyline points="9 18 15 12 9 6" />
        </svg>
      );
    case 'info':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="16" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12.01" y2="8" />
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

const ZONE_LABELS = {
  N1: 'Node 1',
  LAB: 'US Lab',
  CQ: 'Crew Quarters',
  AL: 'Airlock',
};

const DEFAULT_CREW_PROFILES = [
  {
    astronaut_id: 'ast-01',
    name: 'Cmdr. Elena Vasquez',
    initials: 'EV',
    title: 'Mission Commander',
    age: 42,
    zone: 'US Lab',
    readiness: 67,
    status: 'Safety review',
    safetyCount: 1,
    alertCount: 2,
    coveragePct: 99,
    clusterTag: 'No shared cluster',
    summary:
      'Recovery debt is elevated: your 1-minute heart-rate recovery is 13 bpm below your personal reference, resting heart rate is +3 bpm, and sleep debt is 0.5 h.',
    briefing: [
      'Your SOS is queued for Earth and acknowledged on-board; separately, recovery debt is elevated relative to your early-mission reference.',
      'Confidence is high (94%) because post-exercise and resting heart-rate signals agree.',
      'Next: Protect a 24-hour recovery block and repeat the heart-rate recovery check after your next session.',
    ],
    protocols: ['PROT-REC-01', 'PROT-REC-02', 'PROT-MED-01'],
    recovery: {
      score: 61,
      status: 'caution',
      confidence: 95,
      summary: 'Recovery debt is elevated relative to your personal early-mission baseline.',
      observations: [
        { label: '1-min heart-rate recovery', observed: '21.2 bpm', baseline: '34.5 bpm', delta: '-13.3 bpm', window: 'Day 16–23' },
        { label: 'Resting heart rate', observed: '58.2 bpm', baseline: '54.9 bpm', delta: '+3.3 bpm', window: 'Day 16–23' },
        { label: 'Sleep duration', observed: '6.3 h', baseline: '7.0 h', delta: '-0.7 h', window: 'Day 22–23' },
      ],
    },
    cognitive: {
      score: 90,
      status: 'normal',
      confidence: 88,
      summary: 'Cognitive readiness remains within your early-mission personal range.',
      observations: [
        { label: 'PVT mean reaction time', observed: '263 ms', baseline: '251 ms', delta: '+12 ms', window: 'Day 23' },
        { label: 'PVT lapses', observed: '0 count', baseline: '0 count', delta: '0', window: 'Day 23' },
      ],
    },
    behavioural: {
      status: 'Steady',
      summary: 'Passive and self-report layers are consistent. No punitive score is computed.',
      layers: { passive: 'Steady', active: 'Mood 3/5 · Energy 3/5', climate: '3.55/5 (anonymised)' },
    },
    gaps: [
      { label: 'US Lab CO2 missing 2h', window: 'Day 18, 14:00–16:00' },
      { label: '1 reading out of range', window: 'Day 20, 11:00' },
    ],
    alerts: [
      {
        id: 'al-ev-sr05',
        severity: 'safety',
        title: 'SR-05 · SOS — Medical',
        summary: 'Deterministic SOS active; cannot be downgraded or delayed by Advisor.',
        scope: 'physio',
      },
      {
        id: 'al-ev-rec',
        severity: 'caution',
        title: 'Recovery debt above personal early-mission range',
        summary: '1-minute HR recovery dropped 13.3 bpm below baseline alongside +3.3 bpm RHR.',
        scope: 'physio',
        protocols: ['PROT-REC-01', 'PROT-REC-02'],
      },
    ],
    groupedVariations: ['Minor HRV nocturnal fluctuation within personal MAD band (Day 20)'],
    consent: {
      normal: { physio: true, cognitive: true, behaviour: true, habitat: true, ground_sharing: true },
      emergency: { physio: true, cognitive: true, behaviour: true, habitat: true, ground_sharing: true },
    },
  },
  {
    astronaut_id: 'ast-02',
    name: 'Dr. Marcus Chen',
    initials: 'MC',
    title: 'Flight Engineer / Scientist',
    age: 38,
    zone: 'Crew Quarters',
    readiness: 51,
    status: 'Reduced',
    safetyCount: 0,
    alertCount: 2,
    coveragePct: 94,
    clusterTag: 'No shared cluster',
    summary:
      'Cognitive readiness is reduced: reaction time is 74 ms slower than your personal baseline, with 3.0 lapses and 30 points more sleep fragmentation.',
    briefing: [
      'Cognitive readiness is reduced: reaction time is 74 ms slower than your personal baseline, with 3.0 lapses and 30 points more sleep fragmentation.',
      'Confidence is high (86%) because sleep fragmentation and PVT results agree, but the wristband was off for 9h.',
      'Next: Protect a 7.5-hour sleep window tonight and repeat the PVT at the same ship-clock time tomorrow.',
    ],
    protocols: ['PROT-SLP-01', 'PROT-SLP-02'],
    recovery: {
      score: 40,
      status: 'watch',
      confidence: 79,
      summary: 'Recovery is within your personal early-mission range.',
      observations: [
        { label: 'Resting heart rate', observed: '60.4 bpm', baseline: '59.0 bpm', delta: '+1.4 bpm', window: 'Day 22–23' },
        { label: 'HRV RMSSD', observed: '51.0 ms', baseline: '54.2 ms', delta: '-3.2 ms', window: 'Day 22–23' },
      ],
    },
    cognitive: {
      score: 21,
      status: 'critical',
      confidence: 86,
      summary:
        'Cognitive readiness is reduced: reaction time is 74 ms slower than your personal baseline, with 3.0 lapses and 30 points more sleep fragmentation.',
      observations: [
        { label: 'PVT mean reaction time', observed: '332 ms', baseline: '258 ms', delta: '+74 ms', window: 'Day 23' },
        { label: 'PVT lapses', observed: '3.0 count', baseline: '0.0 count', delta: '+3.0', window: 'Day 23' },
        { label: 'Sleep fragmentation', observed: '48 pts', baseline: '18 pts', delta: '+30 pts', window: 'Day 22–23' },
      ],
    },
    behavioural: {
      status: 'Watch',
      summary: 'Passive telemetry and self-report layers show a gentle mismatch.',
      layers: { passive: 'Drift', active: 'Mood 4/5 · Energy 4/5', climate: '3.55/5 (anonymised)' },
    },
    gaps: [
      { label: 'Wristband off for 9h', window: 'Day 21 22:00 → Day 22 07:00' },
      { label: 'US Lab CO2 missing 2h', window: 'Day 18, 14:00–16:00' },
      { label: '1 reading flagged as motion noise', window: 'Day 12, 16:00–17:00' },
    ],
    alerts: [
      {
        id: 'al-mc-cog',
        severity: 'caution',
        title: 'Cognitive readiness below personal baseline',
        summary:
          'Cognitive readiness is reduced: reaction time is 74 ms slower than your personal baseline, with 3.0 lapses and 30 points more sleep fragmentation.',
        scope: 'cognitive',
        protocols: ['PROT-SLP-01', 'PROT-SLP-02'],
      },
      {
        id: 'al-mc-beh',
        severity: 'info',
        title: 'Self-report and passive signals disagree',
        summary: 'Passive activity and sleep metrics diverged from steady self-report ratings.',
        scope: 'behaviour',
      },
    ],
    groupedVariations: ['1 single-hour heart rate step offset routed to data_fault (Day 12)'],
    consent: {
      normal: { physio: true, cognitive: true, behaviour: false, habitat: true, ground_sharing: false },
      emergency: { physio: true, cognitive: true, behaviour: false, habitat: true, ground_sharing: false },
    },
  },
  {
    astronaut_id: 'ast-03',
    name: 'Yuki Tanaka',
    initials: 'YT',
    title: 'Pilot',
    age: 35,
    zone: 'US Lab',
    readiness: null,
    status: 'Scoped',
    safetyCount: 0,
    alertCount: 1,
    coveragePct: 99,
    clusterTag: 'Habitat cluster',
    summary: 'Daily CO2 exposure and symptom score move together (r=+0.96, same day).',
    briefing: [
      'Shared habitat exposure pattern detected: symptom index co-moves with US Lab CO2 (r=+0.96, same day).',
      'Cognitive scope is withheld under normal sharing; routine readiness composite is scoped until consented or emergency override.',
      'Next: Verify US Lab air quality and rotate non-essential desk blocks to Node 1 if symptoms persist.',
    ],
    protocols: ['PROT-ENV-01', 'PROT-ENV-02'],
    recovery: {
      score: 24,
      status: 'normal',
      confidence: 92,
      summary: 'Recovery debt is within your personal early-mission range.',
      observations: [
        { label: 'Resting heart rate', observed: '57.1 bpm', baseline: '56.4 bpm', delta: '+0.7 bpm', window: 'Day 23' },
        { label: 'HRV RMSSD', observed: '64.0 ms', baseline: '66.0 ms', delta: '-2.0 ms', window: 'Day 23' },
      ],
    },
    cognitive: {
      score: 82,
      status: 'normal',
      confidence: 85,
      summary: 'Cognitive readiness within personal band.',
      observations: [{ label: 'PVT mean reaction time', observed: '248 ms', baseline: '244 ms', delta: '+4 ms', window: 'Day 23' }],
    },
    behavioural: {
      status: 'Steady',
      summary: 'Passive and self-report layers are consistent. No punitive score is computed.',
      layers: { passive: 'Steady', active: 'Steady', climate: '3.55/5 (anonymised)' },
    },
    gaps: [{ label: 'US Lab CO2 missing 2h', window: 'Day 18, 14:00–16:00' }],
    alerts: [
      {
        id: 'al-yt-env',
        severity: 'caution',
        title: 'Symptoms co-move with US Lab CO2 exposure',
        summary: 'Treat as a shared habitat confounder first; individual illness is not excluded.',
        scope: 'habitat',
        protocols: ['PROT-ENV-01', 'PROT-ENV-02'],
      },
    ],
    groupedVariations: ['1 transient post-EVA sleep shift within normal range'],
    consent: {
      normal: { physio: true, cognitive: false, behaviour: true, habitat: true, ground_sharing: true },
      emergency: { physio: true, cognitive: true, behaviour: true, habitat: true, ground_sharing: true },
    },
  },
  {
    astronaut_id: 'ast-04',
    name: 'Omar Haddad',
    initials: 'OH',
    title: 'Mission Specialist',
    age: 36,
    zone: 'US Lab',
    readiness: 70,
    status: 'Monitor',
    safetyCount: 0,
    alertCount: 1,
    coveragePct: 99,
    clusterTag: 'Habitat cluster',
    summary: 'Daily CO2 exposure and symptom score move together (r=+0.95, same day).',
    briefing: [
      'Symptom score co-moves closely with US Lab CO2 (r=+0.95, same day) alongside one peer crew member.',
      'Confidence is high (91%) with 99% clean sensor coverage.',
      'Next: Confirm US Lab scrubber telemetry and re-check headache/fatigue 4 hours after zone rotation.',
    ],
    protocols: ['PROT-ENV-01', 'PROT-ENV-02'],
    recovery: {
      score: 28,
      status: 'normal',
      confidence: 91,
      summary: 'Recovery is within your personal early-mission range.',
      observations: [
        { label: '1-min heart-rate recovery', observed: '33.0 bpm', baseline: '34.2 bpm', delta: '-1.2 bpm', window: 'Day 23' },
      ],
    },
    cognitive: {
      score: 84,
      status: 'normal',
      confidence: 90,
      summary: 'Cognitive readiness is within your personal early-mission range.',
      observations: [
        { label: 'PVT mean reaction time', observed: '252 ms', baseline: '249 ms', delta: '+3 ms', window: 'Day 23' },
      ],
    },
    behavioural: {
      status: 'Steady',
      summary: 'Passive and self-report layers are consistent. No punitive score is computed.',
      layers: { passive: 'Steady', active: 'Mood 4/5 · Energy 3/5', climate: '3.55/5 (anonymised)' },
    },
    gaps: [{ label: 'US Lab CO2 missing 2h', window: 'Day 18, 14:00–16:00' }],
    alerts: [
      {
        id: 'al-oh-env',
        severity: 'caution',
        title: 'Symptoms co-move with US Lab CO2 exposure',
        summary: 'Shared habitat CO2 cluster active; verify cabin air before attributing personal illness.',
        scope: 'habitat',
        protocols: ['PROT-ENV-01', 'PROT-ENV-02'],
      },
    ],
    groupedVariations: ['1 mild evening fatigue drift attributed to Lab CO2 confounder'],
    consent: {
      normal: { physio: true, cognitive: true, behaviour: true, habitat: true, ground_sharing: true },
      emergency: { physio: true, cognitive: true, behaviour: true, habitat: true, ground_sharing: true },
    },
  },
];

const DEFAULT_SOS_LIST = [
  {
    sos_id: 'sos-day23-01',
    astronaut_id: 'ast-01',
    astronaut_name: 'Cmdr. Elena Vasquez',
    type: 'medical',
    short_date: 'Day 23, 14:20',
    status: 'queued',
    onboard_acknowledged: true,
    note: 'Unusually winded after exercise block. Requesting guidance; comms are offline.',
  },
];

function formatConfPct(raw, fallback = 85) {
  if (raw == null || Number.isNaN(Number(raw))) return fallback;
  const num = Number(raw);
  return num <= 1 ? Math.round(num * 100) : Math.round(num);
}

function capitalizeWord(str) {
  const s = String(str || '').trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

function getStatusMeta(statusText) {
  const raw = String(statusText || 'Steady').trim();
  const key = raw.toLowerCase();
  if (key.includes('safety') || key.includes('support') || key === 'critical') {
    return { pillClass: 'pill-red', icon: 'alert-octagon', label: raw, ringColor: '#b91c1c' };
  }
  if (key.includes('reduced') || key.includes('caution') || key.includes('check-in')) {
    return { pillClass: 'pill-amber', icon: 'alert-triangle', label: raw, ringColor: '#d97706' };
  }
  if (key.includes('watch') || key.includes('monitor')) {
    return { pillClass: 'pill-amber', icon: 'alert-triangle', label: raw, ringColor: '#d97706' };
  }
  if (key.includes('scoped') || key.includes('withheld')) {
    return { pillClass: 'pill-purple', icon: 'lock', label: raw, ringColor: '#6d28d9' };
  }
  return { pillClass: 'pill-teal', icon: 'check-circle', label: raw, ringColor: '#0d7474' };
}

function StatusPill({ status, className = '' }) {
  const meta = getStatusMeta(status);
  return (
    <span className={`pill ${meta.pillClass} ${className}`.trim()}>
      <Icon name={meta.icon} size={13} />
      <span>{meta.label}</span>
    </span>
  );
}

function ReadinessRing({ score, color = '#0d7474', size = 52 }) {
  const strokeWidth = 5;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, Number(score || 0)));
  const offset = circumference - (clamped / 100) * circumference;

  return (
    <div className="ring-wrap" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e6eeee"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="ring-center">
        <span className="ring-score">{Math.round(clamped)}</span>
      </div>
    </div>
  );
}

/**
 * Evaluate scope access for Crew Health Officer:
 * normal sharing OR (active critical safety rule AND astronaut's emergency switch).
 */
function resolveScopeAccess(consentProfile, hasActiveCritical) {
  const normal = consentProfile?.normal || consentProfile?.scopes || {};
  const emergency = consentProfile?.emergency || consentProfile?.emergency_scopes || {};
  const scopes = ['physio', 'cognitive', 'behaviour', 'habitat'];
  const result = {};

  for (const sc of scopes) {
    const isNormal = normal[sc] !== false;
    const isEmergencyOverride = !isNormal && hasActiveCritical && Boolean(emergency[sc]);
    result[sc] = {
      allowed: isNormal || isEmergencyOverride,
      normal: isNormal,
      emergency: Boolean(emergency[sc]),
      overrideUsed: isEmergencyOverride,
    };
  }
  result.ground_sharing = {
    allowed: Boolean(normal.ground_sharing ?? normal.ground ?? true),
    normal: Boolean(normal.ground_sharing ?? normal.ground ?? true),
    emergency: Boolean(emergency.ground_sharing ?? emergency.ground ?? true),
  };
  return result;
}

function formatGapWindow(gap) {
  if (typeof gap === 'string') return { label: gap, window: '' };
  return {
    label: gap.label || gap.title || 'Data gap',
    window: gap.window || gap.detail || '',
  };
}

function extractObservations(indexObj, allObs, kind, fallbackObs) {
  if (Array.isArray(indexObj?.observations) && indexObj.observations.length > 0) {
    return indexObj.observations;
  }
  if (Array.isArray(allObs) && allObs.length > 0) {
    const filtered = allObs.filter((o) => {
      const t = String(o.title || o.label || '').toLowerCase();
      return kind === 'recovery'
        ? t.includes('heart') || t.includes('sleep duration')
        : t.includes('pvt') || t.includes('reaction') || t.includes('fragmentation');
    });
    if (filtered.length > 0) {
      return filtered.map((o) => ({
        label: o.title || o.label,
        observed: `${o.value} ${o.unit || ''}`.trim(),
        baseline: `${o.baseline} ${o.unit || ''}`.trim(),
        delta: o.delta != null ? String(o.delta) : 'vs ref',
        window: o.window || 'recent',
      }));
    }
  }
  if (indexObj?.why_details) {
    return [{ label: 'Summary evidence', observed: indexObj.why_details, baseline: 'Personal ref', delta: 'Observed', window: 'Current window' }];
  }
  return fallbackObs || [];
}

function normalizeViewModel(state) {
  const safeState = state || {};
  const day = safeState.day ?? safeState.mission_day ?? safeState.currentDay ?? 23;
  const hour = safeState.hour ?? 16;

  // Normalize SOS events from fallbackData (`sos_events`) or live API
  const rawSos =
    safeState.sos_events ||
    safeState.sosEvents ||
    safeState.safety?.timeline ||
    safeState.sos_inbox ||
    [];
  const sosList = (Array.isArray(rawSos) && rawSos.length > 0 ? rawSos : DEFAULT_SOS_LIST).filter(
    (s) => s && s.status !== 'cancelled' && s.status !== 'resolved_ok'
  );

  const consentSource =
    safeState.consent_matrix || safeState.consentMatrix || safeState.consents || {};
  const safetyRules =
    safeState.safety?.active_rules ||
    safeState.active_safety_rules ||
    safeState.activeSafetyRules ||
    safeState.safety_rules ||
    [];

  // Crew overview list from fallbackData (`crew_overview`) or generic (`crew` / `crew_summaries`)
  const crewInput = Array.isArray(safeState.crew_overview)
    ? safeState.crew_overview
    : Array.isArray(safeState.crew)
    ? safeState.crew
    : Array.isArray(safeState.crew_summaries)
    ? safeState.crew_summaries
    : [];

  const crewMap = {};
  for (const item of crewInput) {
    if (item && item.astronaut_id) crewMap[item.astronaut_id] = item;
  }

  // Live selected crew detail from `state.astronaut` (when matching `selected_crew_id`)
  const activeScoped = safeState.astronaut || null;
  const activeScopedId = activeScoped?.profile?.astronaut_id;

  const crewProfiles = DEFAULT_CREW_PROFILES.map((fallback) => {
    const aid = fallback.astronaut_id;
    const ext = crewMap[aid] || {};
    const scopedMatch = activeScopedId === aid ? activeScoped : null;
    const rExt = scopedMatch?.readiness || {};
    const bExt = scopedMatch?.behavioral || {};
    const cExt =
      consentSource[aid] ||
      (ext.scopes ? { normal: ext.scopes, emergency: ext.emergency_scopes || fallback.consent.emergency } : null) ||
      ext.consent ||
      fallback.consent;

    const crewSos = sosList.filter((s) => (s.astronaut_id || s.astronautId) === aid);
    const crewRules = Array.isArray(safetyRules)
      ? safetyRules.filter(
          (r) =>
            !r.astronaut_id ||
            r.astronaut_id === aid ||
            (r.rule_id === 'SR-05' && crewSos.length > 0)
        )
      : [];
    const hasCritical =
      Boolean(rExt.safety_active) ||
      (ext.safety_count != null && ext.safety_count > 0) ||
      crewSos.length > 0 ||
      crewRules.some((r) => r.astronaut_id === aid);

    const access = resolveScopeAccess(cExt, hasCritical);

    const recRaw = rExt.recovery_debt || ext.recovery || fallback.recovery;
    const cogRaw = rExt.cognitive_readiness || ext.cognitive || fallback.cognitive;
    const recObs = extractObservations(recRaw, scopedMatch?.observations, 'recovery', fallback.recovery.observations);
    const cogObs = extractObservations(cogRaw, scopedMatch?.observations, 'cognitive', fallback.cognitive.observations);

    const covPct =
      ext.data_coverage_pct ??
      ext.coveragePct ??
      rExt.data_quality?.coverage_pct ??
      (rExt.data_quality?.coverage != null ? Math.round(rExt.data_quality.coverage * 100) : fallback.coveragePct);

    const gapsRaw =
      rExt.data_quality?.gaps ||
      ext.gaps ||
      safeState.data_quality_by_crew?.[aid]?.gaps ||
      fallback.gaps;

    const rawAlerts = scopedMatch?.alerts || ext.alerts || fallback.alerts;
    const normalizedAlerts = (Array.isArray(rawAlerts) ? rawAlerts : fallback.alerts).map((a, idx) => ({
      id: a.alert_id || a.id || `al-${aid}-${idx}`,
      severity: a.severity || 'caution',
      scope: a.scope,
      title: a.title || 'Health advisory',
      summary: a.summary || '',
      protocols: a.protocol_refs || a.protocols || [],
      redacted: Boolean(a.redacted),
    }));

    // Merge active critical safety rule into alert list if not already listed
    if (hasCritical && !normalizedAlerts.some((a) => a.severity === 'safety' || a.severity === 'critical')) {
      const ruleTitle = crewRules[0]?.title || 'SR-05 · SOS — Medical';
      normalizedAlerts.unshift({
        id: `al-safety-${aid}`,
        severity: 'safety',
        title: ruleTitle,
        summary: 'Deterministic safety rule active; bypasses alert budget and cannot be downgraded.',
        scope: 'physio',
        protocols: ['PROT-MED-01'],
      });
    }

    const briefingObj = scopedMatch?.briefing;
    const briefingLines = briefingObj
      ? [
          briefingObj.what_changed,
          briefingObj.how_sure_why,
          briefingObj.single_best_next_step ? `Next: ${briefingObj.single_best_next_step}` : '',
        ].filter(Boolean)
      : ext.briefing || fallback.briefing;

    const behavioralNormalized = {
      status: bExt.status || fallback.behavioural.status,
      summary: bExt.summary || fallback.behavioural.summary,
      redacted: Boolean(bExt.redacted),
      layers: bExt.passive_layer
        ? {
            passive: capitalizeWord(bExt.passive_layer.status || 'Steady'),
            active: bExt.active_layer
              ? `Mood ${bExt.active_layer.mood_score ?? '—'}/5 · Energy ${bExt.active_layer.energy_score ?? '—'}/5`
              : fallback.behavioural.layers.active,
            climate: bExt.climate_layer?.score
              ? `${bExt.climate_layer.score}/5 (anonymised)`
              : fallback.behavioural.layers.climate,
          }
        : fallback.behavioural.layers,
    };

    const readinessVal =
      ext.readiness_score !== undefined
        ? ext.readiness_score
        : rExt.readiness_score !== undefined
        ? Math.round(rExt.readiness_score)
        : fallback.readiness;

    const withheldScopes = ['physio', 'cognitive', 'behaviour', 'habitat'].filter(
      (s) => !access[s].allowed
    );

    const isCogScoped = withheldScopes.includes('cognitive');
    const isPhysioScoped = withheldScopes.includes('physio');

    const derivedStatus =
      hasCritical
        ? 'Safety review'
        : isCogScoped || isPhysioScoped
        ? 'Scoped'
        : ext.band || ext.status || rExt.band || fallback.status;

    const zoneCode = ext.default_zone || scopedMatch?.profile?.default_zone;
    const zoneLabel = (zoneCode && ZONE_LABELS[zoneCode]) || ext.zone || fallback.zone;

    const clusterLabel =
      typeof ext.shared_cluster === 'boolean'
        ? ext.shared_cluster
          ? 'Habitat cluster'
          : 'No shared cluster'
        : ext.clusterTag || fallback.clusterTag;

    return {
      ...fallback,
      ...ext,
      name: ext.name || fallback.name,
      initials: ext.initials || fallback.initials,
      title: ext.title || fallback.title,
      age: ext.age || fallback.age,
      zone: zoneLabel,
      readiness: isCogScoped || isPhysioScoped ? null : readinessVal,
      status: derivedStatus,
      safetyCount: hasCritical ? Math.max(1, crewSos.length || crewRules.length) : ext.safety_count ?? 0,
      alertCount: ext.alert_count ?? normalizedAlerts.length,
      coveragePct: covPct,
      clusterTag: clusterLabel,
      summary: ext.summary || fallback.summary,
      briefing: briefingLines,
      protocols: briefingObj?.protocol_refs || ext.protocols || fallback.protocols,
      briefingConfPct:
        briefingObj?.confidence_pct ??
        Math.round(
          (formatConfPct(recRaw.confidence, 85) + formatConfPct(cogRaw.confidence, 85)) / 2
        ),
      recovery: {
        score: Math.round(recRaw.score ?? fallback.recovery.score),
        status: recRaw.status || fallback.recovery.status,
        confidence: formatConfPct(recRaw.confidence, fallback.recovery.confidence),
        summary: recRaw.summary || fallback.recovery.summary,
        observations: recObs,
        redacted: Boolean(recRaw.redacted),
      },
      cognitive: {
        score: Math.round(cogRaw.score ?? fallback.cognitive.score),
        status: cogRaw.status || fallback.cognitive.status,
        confidence: formatConfPct(cogRaw.confidence, fallback.cognitive.confidence),
        summary: cogRaw.summary || fallback.cognitive.summary,
        observations: cogObs,
        redacted: Boolean(cogRaw.redacted),
      },
      behavioural: behavioralNormalized,
      gaps: Array.isArray(gapsRaw) ? gapsRaw : fallback.gaps,
      alerts: normalizedAlerts,
      groupedVariations:
        ext.groupedVariations || ext.grouped_variations || fallback.groupedVariations,
      consent: cExt,
      access,
      withheldScopes,
      hasCritical,
      overrideActive: Object.values(access).some((a) => a && a.overrideUsed),
    };
  });

  return { day, hour, sosList, crewProfiles };
}

/**
 * Crew Health Officer view (F-23) — Consent-gated crew overview, SOS inbox,
 * data quality transparency, behavioural cross-check, explainable alerts,
 * and full crew consent matrix.
 */
export default function HealthOfficerView({
  state,
  selectedCrewId,
  onSelectCrew,
  onAcknowledgeSos,
  onOpenProtocol,
}) {
  const [expandedObs, setExpandedObs] = useState({ recovery: false, cognitive: false });
  const [showGroupedAlerts, setShowGroupedAlerts] = useState(false);

  const { day, hour, sosList, crewProfiles } = useMemo(() => normalizeViewModel(state), [state]);

  const activeCrewId = selectedCrewId || state?.selected_crew_id || 'ast-02';
  const selectedCrew =
    crewProfiles.find((c) => c.astronaut_id === activeCrewId) || crewProfiles[0];

  const openSosCount = sosList.filter(
    (s) => !(s.onboard_acknowledged || s.acknowledged_onboard || s.status === 'acknowledged')
  ).length;

  const toggleObs = (key) => setExpandedObs((prev) => ({ ...prev, [key]: !prev[key] }));

  return (
    <div className="stack-col" data-testid="health-officer-view">
      {/* Page Header */}
      <header className="page-header">
        <div>
          <div className="page-eyebrow">Consent-Aware Clinical Overview</div>
          <h1>Crew</h1>
          <p className="page-subtitle">
            Every card respects the astronaut&apos;s own consent profile. Safety alerts are always
            visible; raw values need consent or a logged emergency override.
          </p>
        </div>
        <div className="page-header-pills">
          <span className={`pill ${sosList.length > 0 ? 'pill-red' : 'pill-neutral'}`}>
            <Icon name="alert-octagon" size={13} />
            <span>
              {sosList.length} {openSosCount > 0 ? 'open' : 'active'} SOS
            </span>
          </span>
          <span className="pill pill-neutral">
            <Icon name="users" size={13} />
            <span>{crewProfiles.length} crew</span>
          </span>
          <span className="pill pill-teal">
            <Icon name="shield" size={13} />
            <span>Audited</span>
          </span>
        </div>
      </header>

      {/* SOS Inbox — Priority 0, deterministic & non-downgradable */}
      <section className="card" aria-label="SOS inbox">
        <div className="card-header">
          <div className="card-title-group">
            <span className="card-icon-badge">
              <Icon name="pulse" size={17} />
            </span>
            <div>
              <h2 className="card-title">SOS inbox</h2>
              <p className="card-subtitle">
                On-board acknowledgement is separate from Earth delivery. Nothing here can be
                downgraded by the Advisor.
              </p>
            </div>
          </div>
          <span className="pill pill-red">Priority 0</span>
        </div>

        {sosList.length === 0 ? (
          <div className="card-muted" style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
            No active SOS beacons. Deterministic safety monitoring remains continuously active.
          </div>
        ) : (
          <div className="stack-col" style={{ gap: 10 }}>
            {sosList.map((sos) => {
              const sosId = sos.sos_id || sos.id || 'sos-active';
              const isAck = Boolean(
                sos.onboard_acknowledged ||
                  sos.acknowledged_onboard ||
                  sos.acknowledged ||
                  sos.status === 'acknowledged'
              );
              const crewLabel =
                sos.astronaut_name ||
                sos.crew_name ||
                crewProfiles.find((c) => c.astronaut_id === sos.astronaut_id)?.name ||
                sos.astronaut_id ||
                'Crew member';
              const sosType = capitalizeWord(sos.type || sos.sos_type || 'Medical');
              const syncState = sos.status || 'queued';
              const timeText =
                sos.short_date ||
                sos.time_label ||
                sos.timestamp_label ||
                `Day ${day}, ${String(hour).padStart(2, '0')}:00`;

              return (
                <div key={sosId} className="sos-inbox-item">
                  <div className="sos-inbox-head">
                    <div>
                      <div className="sos-inbox-title">
                        {crewLabel} · {sosType}
                      </div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: 2 }}>
                        {timeText} · state {syncState}
                        {isAck ? ' · on-board acknowledged' : ' · awaiting on-board acknowledgement'}
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="pill pill-red">
                        <Icon name="alert-octagon" size={12} />
                        <span>{syncState}</span>
                      </span>
                      <button
                        type="button"
                        className={`btn btn-sm ${isAck ? 'btn-secondary' : 'btn-danger'}`}
                        disabled={isAck}
                        onClick={() => onAcknowledgeSos && onAcknowledgeSos(sosId)}
                      >
                        <Icon name={isAck ? 'check-circle' : 'alert-octagon'} size={14} />
                        <span>{isAck ? 'Acknowledged on-board' : 'Acknowledge on-board'}</span>
                      </button>
                    </div>
                  </div>
                  {sos.note ? (
                    <p style={{ margin: 0, fontSize: '0.84rem', color: 'var(--text-primary)' }}>
                      {sos.note}
                    </p>
                  ) : null}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* 4 Crew Summary Cards */}
      <section className="crew-grid" aria-label="Crew status summary">
        {crewProfiles.map((crew) => {
          const isSelected = crew.astronaut_id === selectedCrew.astronaut_id;
          const statusMeta = getStatusMeta(crew.status);
          const scopeTags = [
            { key: 'physio', label: 'Physio' },
            { key: 'cognitive', label: 'Cognitive' },
            { key: 'behaviour', label: 'Behaviour' },
            { key: 'habitat', label: 'Habitat' },
          ];

          return (
            <button
              key={crew.astronaut_id}
              type="button"
              className={`crew-card ${isSelected ? 'selected' : ''}`}
              onClick={() => onSelectCrew && onSelectCrew(crew.astronaut_id)}
              aria-pressed={isSelected}
            >
              <div className="crew-card-top">
                <div className="crew-identity">
                  <span
                    className={`crew-avatar ${
                      crew.astronaut_id === 'ast-03'
                        ? 'purple'
                        : crew.astronaut_id === 'ast-04'
                        ? 'amber'
                        : ''
                    }`}
                  >
                    {crew.initials}
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <div className="crew-name">{crew.name}</div>
                    <div className="crew-role">{crew.title}</div>
                  </div>
                </div>
                {crew.readiness != null ? (
                  <ReadinessRing score={crew.readiness} color={statusMeta.ringColor} size={48} />
                ) : (
                  <span className="pill pill-purple" title="Composite score withheld by scope">
                    <Icon name="lock" size={12} />
                    <span>Scoped</span>
                  </span>
                )}
              </div>

              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                <StatusPill status={crew.status} />
                {crew.safetyCount > 0 ? (
                  <span className="pill pill-red">
                    <Icon name="alert-octagon" size={12} />
                    <span>{crew.safetyCount} safety</span>
                  </span>
                ) : null}
                <span className="pill pill-amber">
                  <Icon name="alert-triangle" size={12} />
                  <span>{crew.alertCount} alerts</span>
                </span>
              </div>

              <p className="crew-summary-text">{crew.summary}</p>

              <div className="scope-chip-row">
                {scopeTags.map((tag) => {
                  const allowed = crew.access[tag.key]?.allowed;
                  return (
                    <span
                      key={tag.key}
                      className={`scope-chip ${allowed ? '' : 'withheld'}`}
                      title={allowed ? `${tag.label} shared` : `${tag.label} withheld`}
                    >
                      <Icon name={allowed ? 'eye' : 'lock'} size={11} />
                      <span>{tag.label}</span>
                    </span>
                  );
                })}
              </div>

              <div className="crew-card-footer">
                <span>{crew.coveragePct}% data</span>
                <span>{crew.clusterTag}</span>
              </div>
            </button>
          );
        })}
      </section>

      {/* Selected Crew Detail Split */}
      <section className="split-main-aside" aria-label={`Selected crew detail: ${selectedCrew.name}`}>
        {/* Left Primary Column */}
        <div className="stack-col">
          {/* Consented Briefing Hero Card */}
          <div className="card">
            <div className="card-header">
              <div className="crew-identity">
                <span className="crew-avatar lg">{selectedCrew.initials}</span>
                <div>
                  <h2 className="card-title" style={{ fontSize: '1.12rem' }}>
                    {selectedCrew.name}
                  </h2>
                  <p className="card-subtitle">
                    {selectedCrew.title} · {selectedCrew.zone} · {selectedCrew.age}
                  </p>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <StatusPill status={selectedCrew.status} />
                {selectedCrew.withheldScopes.length > 0 ? (
                  <span className="pill pill-purple">
                    <Icon name="lock" size={12} />
                    <span>
                      {selectedCrew.withheldScopes.length} scope
                      {selectedCrew.withheldScopes.length > 1 ? 's' : ''} withheld
                    </span>
                  </span>
                ) : (
                  <span className="pill pill-teal">
                    <Icon name="check-circle" size={12} />
                    <span>All 4 onboard scopes shared</span>
                  </span>
                )}
              </div>
            </div>

            <div className="card-muted">
              <div className="page-eyebrow" style={{ marginBottom: 8 }}>
                Consented Briefing
              </div>
              <ol
                style={{
                  margin: 0,
                  paddingLeft: 18,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 6,
                  fontSize: '0.86rem',
                  color: 'var(--text-primary)',
                }}
              >
                {selectedCrew.briefing.map((line, idx) => (
                  <li key={idx}>{line}</li>
                ))}
              </ol>
              {selectedCrew.protocols?.length > 0 ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
                  {selectedCrew.protocols.map((pid) => (
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
              ) : null}
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
              <span className="pill pill-teal">
                <Icon name="pulse" size={12} />
                <span>
                  {selectedCrew.briefingConfPct >= 80 ? 'High' : 'Moderate'} confidence ·{' '}
                  {selectedCrew.briefingConfPct}%
                </span>
              </span>
              <span className="pill pill-neutral">
                <Icon name="lock" size={12} />
                <span>
                  {selectedCrew.overrideActive
                    ? 'Emergency override active (2h window)'
                    : 'Override requires active critical alert'}
                </span>
              </span>
            </div>

            {selectedCrew.withheldScopes.length > 0 ? (
              <div
                className="card-muted"
                style={{
                  marginTop: 12,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: '0.8rem',
                  color: 'var(--text-secondary)',
                }}
              >
                <Icon name="lock" size={14} />
                <span>
                  <strong>
                    {selectedCrew.withheldScopes
                      .map((s) => `${capitalizeWord(s)} signals`)
                      .join(', ')}
                  </strong>{' '}
                  — Routine sharing is off for this scope.
                  {!selectedCrew.consent?.emergency?.[selectedCrew.withheldScopes[0]]
                    ? ' Emergency scope is also off.'
                    : ' Emergency override unlocks only during an active critical safety rule.'}
                </span>
              </div>
            ) : null}
          </div>

          {/* Recovery debt & Cognitive readiness */}
          <div className="grid-2">
            {/* Recovery debt */}
            <div className="card">
              <div className="card-header" style={{ marginBottom: 8 }}>
                <div className="card-title-group">
                  <span className="card-icon-badge amber">
                    <Icon name="heart" size={16} />
                  </span>
                  <div>
                    <h3 className="card-title">Recovery debt</h3>
                    <div className="page-eyebrow" style={{ margin: 0 }}>
                      Personal Index
                    </div>
                  </div>
                </div>
                {selectedCrew.access.physio.allowed && !selectedCrew.recovery.redacted ? (
                  <StatusPill status={selectedCrew.recovery.status} />
                ) : (
                  <StatusPill status="Scoped" />
                )}
              </div>

              {selectedCrew.access.physio.allowed && !selectedCrew.recovery.redacted ? (
                <>
                  <div className="metric-hero">
                    <div>
                      <span className="metric-big">{selectedCrew.recovery.score}</span>
                      <span className="metric-unit">/100</span>
                    </div>
                    <span className="tabular-nums" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {selectedCrew.recovery.confidence}% confidence
                    </span>
                  </div>
                  <p className="card-subtitle" style={{ marginTop: 0 }}>
                    {selectedCrew.recovery.summary}
                  </p>
                  <button
                    type="button"
                    className="collapsible-btn"
                    aria-expanded={expandedObs.recovery}
                    onClick={() => toggleObs('recovery')}
                  >
                    <span>Contributing observations</span>
                    <Icon name="chevron" size={14} />
                  </button>
                  {expandedObs.recovery ? (
                    <div className="collapsible-body">
                      {(selectedCrew.recovery.observations || []).map((obs, idx) => (
                        <div
                          key={idx}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            gap: 8,
                            fontSize: '0.78rem',
                          }}
                        >
                          <span>
                            <strong>{obs.label}</strong> ({obs.window || 'recent'})
                          </span>
                          <span className="tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                            {obs.observed} vs {obs.baseline} ({obs.delta})
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                <div
                  className="card-muted card-purple"
                  style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.82rem', color: 'var(--purple-text)' }}
                >
                  <Icon name="lock" size={15} />
                  <span>Physiological signals are withheld by this astronaut&apos;s consent profile.</span>
                </div>
              )}
            </div>

            {/* Cognitive readiness */}
            <div className="card">
              <div className="card-header" style={{ marginBottom: 8 }}>
                <div className="card-title-group">
                  <span className="card-icon-badge purple">
                    <Icon name="sparkle" size={16} />
                  </span>
                  <div>
                    <h3 className="card-title">Cognitive readiness</h3>
                    <div className="page-eyebrow" style={{ margin: 0 }}>
                      Personal Index
                    </div>
                  </div>
                </div>
                {selectedCrew.access.cognitive.allowed && !selectedCrew.cognitive.redacted ? (
                  <StatusPill status={selectedCrew.cognitive.status} />
                ) : (
                  <StatusPill status="Scoped" />
                )}
              </div>

              {selectedCrew.access.cognitive.allowed && !selectedCrew.cognitive.redacted ? (
                <>
                  <div className="metric-hero">
                    <div>
                      <span className="metric-big">{selectedCrew.cognitive.score}</span>
                      <span className="metric-unit">/100</span>
                    </div>
                    <span className="tabular-nums" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {selectedCrew.cognitive.confidence}% confidence
                    </span>
                  </div>
                  <p className="card-subtitle" style={{ marginTop: 0 }}>
                    {selectedCrew.cognitive.summary}
                  </p>
                  <button
                    type="button"
                    className="collapsible-btn"
                    aria-expanded={expandedObs.cognitive}
                    onClick={() => toggleObs('cognitive')}
                  >
                    <span>Contributing observations</span>
                    <Icon name="chevron" size={14} />
                  </button>
                  {expandedObs.cognitive ? (
                    <div className="collapsible-body">
                      {(selectedCrew.cognitive.observations || []).map((obs, idx) => (
                        <div
                          key={idx}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            gap: 8,
                            fontSize: '0.78rem',
                          }}
                        >
                          <span>
                            <strong>{obs.label}</strong> ({obs.window || 'recent'})
                          </span>
                          <span className="tabular-nums" style={{ color: 'var(--text-secondary)' }}>
                            {obs.observed} vs {obs.baseline} ({obs.delta})
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </>
              ) : (
                <div
                  className="card-muted card-purple"
                  style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '0.82rem', color: 'var(--purple-text)' }}
                >
                  <Icon name="lock" size={15} />
                  <span>
                    Cognitive signals are withheld by this astronaut&apos;s consent. The Health Officer
                    sees only that a scope is withheld, not the values.
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Behavioural cross-check */}
          <div className="card">
            <div className="card-header">
              <div className="card-title-group">
                <span className="card-icon-badge">
                  <Icon name="message" size={16} />
                </span>
                <div>
                  <h3 className="card-title">Behavioural cross-check</h3>
                  <p className="card-subtitle">
                    Three layers: passive telemetry, active check-ins, anonymised crew climate.
                  </p>
                </div>
              </div>
              {selectedCrew.access.behaviour.allowed && !selectedCrew.behavioural.redacted ? (
                <StatusPill status={selectedCrew.behavioural.status || 'Steady'} />
              ) : (
                <span className="pill pill-purple">
                  <Icon name="lock" size={12} />
                  <span>Withheld</span>
                </span>
              )}
            </div>

            {selectedCrew.access.behaviour.allowed && !selectedCrew.behavioural.redacted ? (
              <div className="stack-col" style={{ gap: 10 }}>
                <div className="grid-3">
                  <div className="card-muted">
                    <div className="page-eyebrow">Passive Layer</div>
                    <strong style={{ fontSize: '0.86rem' }}>
                      {selectedCrew.behavioural.layers?.passive || 'Steady'}
                    </strong>
                  </div>
                  <div className="card-muted">
                    <div className="page-eyebrow">Active Check-in</div>
                    <strong style={{ fontSize: '0.86rem' }}>
                      {selectedCrew.behavioural.layers?.active || 'Consistent'}
                    </strong>
                  </div>
                  <div className="card-muted">
                    <div className="page-eyebrow">Crew Climate</div>
                    <strong style={{ fontSize: '0.86rem' }}>
                      {selectedCrew.behavioural.layers?.climate || '3.55/5 (anonymised)'}
                    </strong>
                  </div>
                </div>
                <p className="card-subtitle" style={{ margin: 0 }}>
                  {selectedCrew.behavioural.summary} Non-punitive decision support only — never
                  scored as fitness-for-duty; message and journal content are never read.
                </p>
              </div>
            ) : (
              <div
                className="card-muted card-purple"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  color: 'var(--purple-text)',
                  fontSize: '0.84rem',
                }}
              >
                <Icon name="lock" size={16} />
                <span>
                  Behavioural signals are withheld by this astronaut&apos;s consent. The Health
                  Officer sees only that a scope is withheld, not the values.
                </span>
              </div>
            )}
          </div>

          {/* Explainable alerts */}
          <div className="card">
            <div className="card-header">
              <div>
                <h3 className="card-title">Explainable alerts</h3>
                <p className="card-subtitle">
                  Hard safety rules bypass the alert budget. Advisory noise is deduplicated and
                  grouped.
                </p>
              </div>
              <span className="pill pill-amber">
                <Icon name="alert-triangle" size={12} />
                <span>Budget protected</span>
              </span>
            </div>

            <div className="stack-col" style={{ gap: 10 }}>
              {selectedCrew.alerts.map((alert) => {
                const isSafety = alert.severity === 'safety' || alert.severity === 'critical';
                const scopeAllowed =
                  isSafety ||
                  (!alert.redacted && (!alert.scope || selectedCrew.access[alert.scope]?.allowed));

                if (!scopeAllowed) {
                  return (
                    <div key={alert.id} className="alert-item purple">
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                        <span className="pill pill-neutral">
                          <Icon name="info" size={12} />
                          <span>Info</span>
                        </span>
                        <span className="pill pill-purple">
                          <Icon name="lock" size={12} />
                          <span>Consent-redacted</span>
                        </span>
                      </div>
                      <strong style={{ fontSize: '0.88rem' }}>{alert.title}</strong>
                      <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        Details withheld by the astronaut&apos;s consent settings.
                      </p>
                    </div>
                  );
                }

                const toneClass = isSafety
                  ? 'red'
                  : alert.severity === 'caution' || alert.severity === 'watch'
                  ? 'amber'
                  : '';
                return (
                  <div key={alert.id} className={`alert-item ${toneClass}`.trim()}>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 8,
                        flexWrap: 'wrap',
                      }}
                    >
                      <StatusPill
                        status={
                          isSafety
                            ? 'Safety rule'
                            : alert.severity === 'caution'
                            ? 'caution'
                            : alert.severity === 'watch'
                            ? 'watch'
                            : 'info'
                        }
                      />
                      {isSafety ? (
                        <span className="pill pill-red">
                          <Icon name="lock" size={11} />
                          <span>Bypasses budget</span>
                        </span>
                      ) : null}
                    </div>
                    <strong style={{ fontSize: '0.89rem' }}>{alert.title}</strong>
                    <p style={{ margin: 0, fontSize: '0.81rem', color: 'var(--text-secondary)' }}>
                      {alert.summary}
                    </p>
                    {alert.protocols?.length > 0 ? (
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                        {alert.protocols.map((pid) => (
                          <button
                            key={pid}
                            type="button"
                            className="protocol-chip"
                            onClick={() => onOpenProtocol && onOpenProtocol(pid)}
                          >
                            <Icon name="book" size={11} />
                            <span>{pid}</span>
                            <Icon name="chevron-right" size={11} />
                          </button>
                        ))}
                      </div>
                    ) : null}
                  </div>
                );
              })}

              {(selectedCrew.groupedVariations || []).length > 0 ? (
                <div>
                  <button
                    type="button"
                    className="collapsible-btn"
                    style={{ marginTop: 2 }}
                    aria-expanded={showGroupedAlerts}
                    onClick={() => setShowGroupedAlerts((prev) => !prev)}
                  >
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                      <Icon name="alert-triangle" size={13} />
                      <span>
                        {selectedCrew.groupedVariations.length} background variations grouped
                      </span>
                    </span>
                    <Icon name="chevron" size={14} />
                  </button>
                  {showGroupedAlerts ? (
                    <div className="collapsible-body">
                      {selectedCrew.groupedVariations.map((item, idx) => (
                        <div key={idx} style={{ fontSize: '0.79rem', color: 'var(--text-secondary)' }}>
                          • {item}
                        </div>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
        </div>

        {/* Right Aside Column: Data Quality + Safety Timeline + Audit Notice */}
        <aside className="stack-col" aria-label="Data quality and audit status">
          <div className="card">
            <div className="card-header" style={{ marginBottom: 6 }}>
              <div className="page-eyebrow" style={{ margin: 0 }}>
                Data Quality
              </div>
              <span className={`pill ${selectedCrew.gaps.length > 0 ? 'pill-amber' : 'pill-teal'}`}>
                <Icon
                  name={selectedCrew.gaps.length > 0 ? 'alert-triangle' : 'check-circle'}
                  size={12}
                />
                <span>
                  {selectedCrew.gaps.length} gap{selectedCrew.gaps.length === 1 ? '' : 's'}
                </span>
              </span>
            </div>

            <div className="metric-big" style={{ marginBottom: 6 }}>
              {selectedCrew.coveragePct}%
            </div>
            <p className="card-subtitle" style={{ margin: '0 0 12px' }}>
              Missing and sensor-off intervals remain explicit gaps. Confidence is adjusted rather
              than filling gaps as normal.
            </p>

            <div className="stack-col" style={{ gap: 8 }}>
              {selectedCrew.gaps.map((g, idx) => {
                const { label, window } = formatGapWindow(g);
                return (
                  <div key={idx} className="gap-item">
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 600 }}>
                      <Icon name="alert-triangle" size={13} />
                      <span>{label}</span>
                    </span>
                    {window ? <span className="tabular-nums">{window}</span> : null}
                  </div>
                );
              })}
            </div>
          </div>

          <div className="card">
            <div className="page-eyebrow" style={{ marginBottom: 10 }}>
              Safety Timeline
            </div>
            <div className="stack-col" style={{ gap: 8 }}>
              {sosList.map((sos) => (
                <div key={sos.sos_id || 'sos'} className="card-muted">
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      fontWeight: 700,
                      fontSize: '0.84rem',
                      color: 'var(--red)',
                    }}
                  >
                    <Icon name="alert-triangle" size={13} />
                    <span>SOS · {String(sos.type || sos.sos_type || 'medical').toLowerCase()}</span>
                  </div>
                  <div
                    className="tabular-nums"
                    style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: 2 }}
                  >
                    {sos.timestamp_label ||
                      sos.short_date ||
                      `Day ${day} · ${String(hour).padStart(2, '0')}:00 ship time`}{' '}
                    · {sos.status || 'queued'}
                  </div>
                </div>
              ))}
              <div className="card-muted" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Deterministic rules SR-01..SR-05 evaluated continuously independent of Advisor state.
              </div>
            </div>
          </div>

          <div className="card card-teal" style={{ fontSize: '0.81rem', color: 'var(--mint-text)' }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
              <Icon name="shield" size={16} />
              <span>
                Every access on this screen is logged with your role, scope, time and any emergency
                override. The astronaut can see it in their own privacy panel.
              </span>
            </div>
          </div>
        </aside>
      </section>

      {/* Full Crew Consent Matrix */}
      <section className="card" aria-label="Consent matrix">
        <div className="card-header">
          <div>
            <h2 className="card-title">Consent matrix</h2>
            <p className="card-subtitle">
              Normal sharing vs emergency scope. Only the astronaut can change these switches.
            </p>
          </div>
          <span className="pill pill-purple">
            <Icon name="lock" size={12} />
            <span>Astronaut-owned</span>
          </span>
        </div>

        <div className="table-scroll">
          <table className="consent-table">
            <thead>
              <tr>
                <th>Crew</th>
                <th>Physio</th>
                <th>Cognitive</th>
                <th>Behaviour</th>
                <th>Habitat</th>
                <th>Ground</th>
              </tr>
            </thead>
            <tbody>
              {crewProfiles.map((crew) => {
                const scopes = ['physio', 'cognitive', 'behaviour', 'habitat'];
                return (
                  <tr
                    key={crew.astronaut_id}
                    className="clickable-row"
                    onClick={() => onSelectCrew && onSelectCrew(crew.astronaut_id)}
                  >
                    <td style={{ fontWeight: 600 }}>{crew.name}</td>
                    {scopes.map((sc) => {
                      const info = crew.access[sc];
                      return (
                        <td key={sc}>
                          <div className="consent-cell-badges">
                            <span className={`mini-badge ${info.normal ? 'normal-on' : 'off'}`}>
                              <Icon name={info.normal ? 'eye' : 'lock'} size={11} />
                              <span>{info.normal ? 'normal' : 'off'}</span>
                            </span>
                            <span className={`mini-badge ${info.emergency ? 'em-on' : 'off'}`}>
                              <span>{info.emergency ? 'em' : 'em off'}</span>
                            </span>
                          </div>
                        </td>
                      );
                    })}
                    <td>
                      <span
                        className={`mini-badge ${
                          crew.access.ground_sharing.normal ? 'normal-on' : 'off'
                        }`}
                      >
                        <Icon
                          name={crew.access.ground_sharing.normal ? 'eye' : 'lock'}
                          size={11}
                        />
                        <span>{crew.access.ground_sharing.normal ? 'shared' : 'withheld'}</span>
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
