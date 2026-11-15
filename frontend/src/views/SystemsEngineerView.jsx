import React, { useMemo, useState } from 'react';

/**
 * Shared inline icon primitives for SystemsEngineerView (zero external packages).
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
    case 'wind':
      return (
        <svg {...common}>
          <path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2" />
        </svg>
      );
    case 'check-circle':
      return (
        <svg {...common}>
          <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
          <polyline points="22 4 12 14.01 9 11.01" />
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
    case 'lock':
      return (
        <svg {...common}>
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
        </svg>
      );
    case 'link':
      return (
        <svg {...common}>
          <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
        </svg>
      );
    case 'pulse':
      return (
        <svg {...common}>
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
      );
    case 'book':
      return (
        <svg {...common}>
          <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
          <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
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
    case 'users':
      return (
        <svg {...common}>
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
        </svg>
      );
    case 'sensor-gap':
      return (
        <svg {...common}>
          <path d="M1 1l22 22" />
          <path d="M16.72 11.06A10.94 10.94 0 0 1 19 12.55" />
          <path d="M5 12.55a10.94 10.94 0 0 1 5.17-2.39" />
          <path d="M10.71 5.05A16 16 0 0 1 22.58 9" />
          <path d="M1.42 9a15.91 15.91 0 0 1 4.7-2.88" />
          <line x1="12" y1="20" x2="12.01" y2="20" />
        </svg>
      );
    case 'chevron-right':
      return (
        <svg {...common}>
          <polyline points="9 18 15 12 9 6" />
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

const DEFAULT_ZONES = [
  {
    zone_id: 'N1',
    name: 'Node 1',
    present_crew_count: 0,
    co2_ppm: 834,
    co2_7d_avg_ppm: 1240,
    trend_7d_pct: 41,
    status: 'Within normal band',
    sensor_status: 'clean',
  },
  {
    zone_id: 'LAB',
    name: 'US Lab',
    present_crew_count: 3,
    co2_ppm: 1113,
    co2_7d_avg_ppm: 2062,
    trend_7d_pct: 100,
    status: 'Above normal',
    sensor_status: 'clean',
  },
  {
    zone_id: 'CQ',
    name: 'Crew Quarters',
    present_crew_count: 1,
    co2_ppm: 780,
    co2_7d_avg_ppm: 902,
    trend_7d_pct: 14,
    status: 'Within normal band',
    sensor_status: 'clean',
  },
  {
    zone_id: 'AL',
    name: 'Airlock',
    present_crew_count: 0,
    co2_ppm: 622,
    co2_7d_avg_ppm: 706,
    trend_7d_pct: 9,
    status: 'Within normal band',
    sensor_status: 'clean',
  },
];

const DEFAULT_CORRELATIONS = [
  {
    crew_label: 'Crew A',
    r: 0.66,
    lag_days: 1,
    confidence: 0.77,
    linked: false,
    status: 'no clear link',
    summary: 'Daily CO2 exposure and symptom score move together (r=+0.66, 1-day lag).',
  },
  {
    crew_label: 'Crew B',
    r: 0.58,
    lag_days: 1,
    confidence: 0.75,
    linked: false,
    status: 'no clear link',
    summary: 'Daily CO2 exposure and symptom score move together (r=+0.58, 1-day lag).',
  },
  {
    crew_label: 'Crew C',
    r: 0.96,
    lag_days: 0,
    confidence: 0.91,
    linked: true,
    status: 'linked',
    summary: 'Daily CO2 exposure and symptom score move together (r=+0.96, same day).',
  },
  {
    crew_label: 'Crew D',
    r: 0.95,
    lag_days: 0,
    confidence: 0.9,
    linked: true,
    status: 'linked',
    summary: 'Daily CO2 exposure and symptom score move together (r=+0.95, same day).',
  },
];

const DEFAULT_CO2_SERIES = [
  { day: 10, value: 860 },
  { day: 11, value: 870 },
  { day: 12, value: 880 },
  { day: 13, value: 875 },
  { day: 14, value: 890 },
  { day: 15, value: 1180 },
  { day: 16, value: 1420 },
  { day: 17, value: 1690 },
  { day: 18, value: 1840, gap: true },
  { day: 19, value: 2150 },
  { day: 20, value: 1980 },
  { day: 21, value: 1810 },
  { day: 22, value: 1280 },
  { day: 23, value: 1010 },
];

const DEFAULT_SYMPTOM_SERIES = [
  { day: 10, value: 0.7 },
  { day: 11, value: 0.6 },
  { day: 12, value: 0.8 },
  { day: 13, value: 0.7 },
  { day: 14, value: 0.9 },
  { day: 15, value: 1.4 },
  { day: 16, value: 2.0 },
  { day: 17, value: 2.8 },
  { day: 18, value: 3.3 },
  { day: 19, value: 3.9 },
  { day: 20, value: 3.5 },
  { day: 21, value: 2.4 },
  { day: 22, value: 1.6 },
  { day: 23, value: 1.2 },
];

const DEFAULT_ENV_GAPS = [
  {
    zone_name: 'US Lab',
    day: 18,
    window: 'Day 18, 14:00–16:00 · 2h',
    detail: 'US Lab CO2 sensor packet loss (2 h). Correlation confidence is lowered; the missing values are not imputed.',
  },
];

/**
 * Reusable SVG area + line chart that explicitly preserves missing/null values as gaps.
 */
function MetricAreaChart({
  series,
  maxY,
  strokeColor,
  fillColor,
  baselineY,
  unit,
  emptyLabel = 'No readings in window',
}) {
  const [hoverIdx, setHoverIdx] = useState(null);

  const width = 320;
  const height = 112;
  const padL = 28;
  const padR = 10;
  const padT = 10;
  const padB = 20;
  const plotW = width - padL - padR;
  const plotH = height - padT - padB;

  const points = Array.isArray(series) ? series : [];
  if (points.length === 0) {
    return (
      <div className="card-muted" style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
        {emptyLabel}
      </div>
    );
  }

  const xFor = (i) =>
    points.length === 1 ? padL + plotW / 2 : padL + (i / (points.length - 1)) * plotW;
  const yFor = (val) => {
    const ratio = Math.max(0, Math.min(1, Number(val) / maxY));
    return padT + plotH - ratio * plotH;
  };

  // Split contiguous non-null runs so missing days stay visible as breaks
  const segments = [];
  let currentSeg = [];
  points.forEach((pt, idx) => {
    if (pt && pt.value !== null && pt.value !== undefined && !Number.isNaN(Number(pt.value))) {
      currentSeg.push({
        idx,
        day: pt.day ?? idx + 1,
        value: Number(pt.value),
        hasGapNote: Boolean(pt.gap),
        x: xFor(idx),
        y: yFor(Number(pt.value)),
      });
    } else if (currentSeg.length > 0) {
      segments.push(currentSeg);
      currentSeg = [];
    }
  });
  if (currentSeg.length > 0) segments.push(currentSeg);

  const firstDay = points[0]?.day ?? 1;
  const lastDay = points[points.length - 1]?.day ?? points.length;
  const baseLinePx = baselineY != null ? yFor(baselineY) : null;
  const activePt =
    hoverIdx != null && points[hoverIdx]
      ? {
          day: points[hoverIdx].day ?? hoverIdx + 1,
          value: points[hoverIdx].value,
          hasGapNote: Boolean(points[hoverIdx].gap),
        }
      : null;

  return (
    <div>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="sparkline-svg"
        role="img"
        aria-label={`Trend chart from Day ${firstDay} to Day ${lastDay}`}
      >
        {[0, 0.5, 1].map((frac) => {
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

        {baseLinePx != null ? (
          <line
            x1={padL}
            y1={baseLinePx}
            x2={width - padR}
            y2={baseLinePx}
            stroke="#cbd5e1"
            strokeWidth="1"
            strokeDasharray="3 3"
          />
        ) : null}

        {segments.map((seg, sIdx) => {
          const lineD = seg
            .map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`)
            .join(' ');
          const areaD =
            seg.length > 1
              ? `${lineD} L ${seg[seg.length - 1].x.toFixed(1)} ${(padT + plotH).toFixed(1)} L ${seg[0].x.toFixed(1)} ${(padT + plotH).toFixed(1)} Z`
              : '';

          return (
            <g key={sIdx}>
              {areaD ? <path d={areaD} fill={fillColor} /> : null}
              {seg.length > 1 ? (
                <path
                  d={lineD}
                  fill="none"
                  stroke={strokeColor}
                  strokeWidth="2"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              ) : null}
              {seg.map((p) => (
                <circle
                  key={p.idx}
                  cx={p.x}
                  cy={p.y}
                  r={hoverIdx === p.idx ? 4.4 : p.hasGapNote ? 3.5 : 2.6}
                  fill={p.hasGapNote ? '#fef7e6' : '#ffffff'}
                  stroke={p.hasGapNote ? '#b45309' : strokeColor}
                  strokeWidth="2"
                  style={{ cursor: 'pointer' }}
                  onMouseEnter={() => setHoverIdx(p.idx)}
                  onMouseLeave={() => setHoverIdx(null)}
                />
              ))}
            </g>
          );
        })}

        <text x={padL - 5} y={padT + 4} textAnchor="end" fontSize="9" fill="#6c8080">
          {maxY}
        </text>
        <text x={padL - 5} y={padT + plotH + 3} textAnchor="end" fontSize="9" fill="#6c8080">
          0
        </text>
        <text x={padL} y={height - 4} textAnchor="start" fontSize="9" fill="#6c8080">
          D{firstDay}
        </text>
        <text x={width - padR} y={height - 4} textAnchor="end" fontSize="9" fill="#6c8080">
          D{lastDay}
        </text>
      </svg>

      {activePt ? (
        <div
          className="tabular-nums"
          style={{ fontSize: '0.73rem', color: 'var(--text-secondary)', marginTop: 2 }}
        >
          Day {activePt.day}:{' '}
          {activePt.value == null
            ? 'Gap (not imputed)'
            : `${activePt.value} ${unit}${activePt.hasGapNote ? ' (partial 2h gap)' : ''}`}
        </div>
      ) : null}
    </div>
  );
}

function normalizeSubTab(raw) {
  const key = String(raw || 'habitat').toLowerCase();
  if (key.includes('comm') || key.includes('ops') || key.includes('eng')) return 'comms';
  if (key.includes('scope') || key.includes('access')) return 'scope';
  return 'habitat';
}

function formatGapText(gap) {
  if (typeof gap === 'string') return gap;
  if (gap.message) return gap.message;
  const prefix = [gap.zone_name, gap.window].filter(Boolean).join(' · ');
  return prefix && gap.detail ? `${prefix} - ${gap.detail}` : gap.detail || prefix || 'Sensor gap';
}

function normalizeEnvState(state) {
  const safeState = state || {};
  const day = safeState.day ?? safeState.mission_day ?? safeState.currentDay ?? 23;
  const env = safeState.environment || safeState.env || {};

  const rawZones = env.zones || safeState.zones || DEFAULT_ZONES;
  const zoneOrder = ['N1', 'LAB', 'CQ', 'AL'];
  let zoneList;
  if (Array.isArray(rawZones)) {
    zoneList = rawZones;
  } else {
    zoneList = zoneOrder.map((zid) => rawZones[zid]).filter(Boolean);
    if (zoneList.length === 0) zoneList = DEFAULT_ZONES;
  }

  const zones = zoneList.map((z) => ({
    zone_id: z.zone_id,
    name: z.name,
    present_crew_count: z.present_crew_count ?? z.crew_present ?? 0,
    co2_ppm: z.co2_ppm,
    co2_7d_avg_ppm: z.co2_7d_avg_ppm ?? z.avg_7d_ppm ?? null,
    trend_7d_pct: z.trend_7d_pct ?? z.trend_pct ?? 0,
    status: z.status || 'Within normal band',
    sensor_status: z.sensor_status || 'clean',
  }));

  const rawCorrs =
    env.crew_correlations || env.crewCorrelations || safeState.crew_correlations || DEFAULT_CORRELATIONS;
  const crewCorrelations = (Array.isArray(rawCorrs) ? rawCorrs : DEFAULT_CORRELATIONS).map(
    (c, idx) => ({
      crew_label: c.crew_label || c.label || `Crew ${String.fromCharCode(65 + idx)}`,
      r: Number(c.r ?? 0),
      lag_days: Number(c.lag_days ?? c.lag ?? 0),
      confidence: Number(c.confidence ?? 0.8),
      linked: Boolean(c.linked || String(c.status).toLowerCase() === 'linked'),
      status: c.status || (c.linked ? 'linked' : 'no clear link'),
      summary: c.summary || '',
    })
  );

  const sharedAlert = env.shared_exposure_alert ||
    safeState.shared_exposure_alert || {
      active: true,
      confidence: 0.9,
      lag_range: '0–1 day',
      affected_crew_count: 2,
      headline: 'Shared habitat exposure signal',
      summary:
        '2 crew members show symptom scores co-moving with US Lab CO2 (lag 0–1 day). Treat this as a shared environmental exposure until the air is verified; individual illness is not excluded.',
      prevent_misattribution:
        'do not label a crew member as "sick" when the same symptom pattern follows a shared zone exposure. Individual illness is not excluded.',
      protocol_refs: ['PROT-ENV-01', 'PROT-ENV-02', 'PROT-MED-01'],
    };

  const co2SeriesRaw =
    env.aggregate_co2_series || env.aggregateCo2Series || DEFAULT_CO2_SERIES;
  const symSeriesRaw =
    env.aggregate_symptom_series || env.aggregateSymptomSeries || DEFAULT_SYMPTOM_SERIES;

  const co2Series = co2SeriesRaw.slice(-14);
  const symptomSeries = symSeriesRaw.slice(-14);

  const envGaps = env.environmental_gaps || env.gaps || (day >= 18 ? DEFAULT_ENV_GAPS : []);
  const radDaily =
    env.radiation_daily_usv ??
    env.radiation_usv_day ??
    safeState.radiation?.daily_usv ??
    505;
  const radCum =
    env.radiation_cumulative_msv ?? safeState.radiation?.cumulative_msv ?? 12.82;

  const msideFindingsRaw =
    safeState.mside?.shared_exposure_findings ||
    env.mside_findings ||
    (sharedAlert.active
      ? [
          {
            finding_id: 'mside-shared-LAB',
            title: 'Shared habitat exposure across crew',
            confidence: sharedAlert.confidence ?? 0.9,
            correlation_r: 0.95,
            summary: sharedAlert.summary,
            protocol_refs: sharedAlert.protocol_refs || ['PROT-ENV-01', 'PROT-ENV-02', 'PROT-MED-01'],
          },
        ]
      : []);

  const messages = Array.isArray(safeState.messages) ? safeState.messages : [];

  return {
    day,
    zones,
    crewCorrelations,
    sharedAlert,
    co2Series,
    symptomSeries,
    envGaps: Array.isArray(envGaps) ? envGaps : [],
    radDaily,
    radCum,
    msideFindings: msideFindingsRaw,
    dailyPoints: env.method_guardrails?.daily_points || co2Series.length || 14,
    sr03Note:
      env.sr03_note ||
      (day >= 19
        ? 'Hard rule SR-03 fires at 5,000 ppm and bypasses the alert budget. The 5,000+ ppm exceedance appeared on Day 19 in US Lab; the scrubber was serviced on Day 22.'
        : 'Hard rule SR-03 fires at 5,000 ppm and bypasses the alert budget.'),
    messages,
  };
}

/**
 * Interactive SVG schematic of pressurized habitat modules, airflow paths, and US Lab drift.
 */
function HabitatHullSchematic({ zones = [], selectedZoneId, onSelectZone }) {
  const byId = Object.fromEntries((zones || []).map((z) => [z.zone_id, z]));
  const layout = [
    { id: 'N1', label: 'Node 1', x: 18, y: 34, w: 148, h: 112 },
    { id: 'LAB', label: 'US Lab', x: 204, y: 26, w: 174, h: 128 },
    { id: 'CQ', label: 'Crew Quarters', x: 416, y: 18, w: 152, h: 66 },
    { id: 'AL', label: 'Airlock', x: 416, y: 98, w: 152, h: 64 },
  ];

  const getTone = (z) => {
    if (!z) return { stroke: '#94a3b8', fill: '#f8fafc', text: '#475569', tag: 'OFFLINE' };
    const statusLow = String(z.status || '').toLowerCase();
    const co2 = Number(z.co2_ppm ?? 0);
    if (z.co2_ppm == null || statusLow.includes('gap')) {
      return { stroke: '#b91c1c', fill: '#fff8f8', text: '#7f1d1d', tag: 'GAP' };
    }
    if (co2 >= 5000 || statusLow.includes('critical')) {
      return { stroke: '#b91c1c', fill: '#fdecec', text: '#7f1d1d', tag: 'CRITICAL' };
    }
    if (co2 > 1050 || statusLow.includes('above') || Number(z.co2_7d_avg_ppm || 0) >= 1500) {
      return { stroke: '#d97706', fill: '#fffcf3', text: '#854d0e', tag: 'DRIFT' };
    }
    return { stroke: '#0d7474', fill: '#f4fbfa', text: '#074747', tag: 'NOMINAL' };
  };

  const labZone = byId.LAB;
  const labElevated = labZone && (Number(labZone.co2_ppm ?? 0) > 1050 || Number(labZone.co2_7d_avg_ppm ?? 0) >= 1500);

  return (
    <section className="habitat-schematic-card" aria-label="Spacecraft habitat hull schematic">
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 10,
          flexWrap: 'wrap',
          marginBottom: 10,
        }}
      >
        <div>
          <h2 className="card-title">Habitat pressurised hull schematic</h2>
          <p className="card-subtitle">
            Click a module to focus its telemetry. Airflow arrows show closed-loop cabin circulation.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {labElevated ? (
            <span className="pill pill-amber tabular-nums">
              <Icon name="alert-triangle" size={12} />
              <span>US Lab CO₂ scrubber drift · r = 0.86, q = 0.009</span>
            </span>
          ) : null}
          {selectedZoneId ? (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => onSelectZone(null)}
            >
              Show all modules
            </button>
          ) : null}
        </div>
      </div>

      <svg
        viewBox="0 0 740 182"
        className="sparkline-svg"
        role="img"
        aria-label="Habitat modules schematic: Node 1 connected to US Lab, Crew Quarters, and Airlock"
      >
        {/* Outer hull spine */}
        <line x1="12" y1="90" x2="578" y2="90" stroke="#cbd5e1" strokeWidth="6" strokeLinecap="round" />

        {/* Bulkhead connectors & airflow vectors */}
        <g stroke="#0d7474" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round">
          <rect x="166" y="76" width="38" height="28" rx="4" fill="#eef6f6" stroke="#c8d4d4" />
          <line x1="173" y1="90" x2="195" y2="90" />
          <polyline points="190 86 196 90 190 94" />

          <path d="M 378 52 L 416 52" />
          <polyline points="410 48 416 52 410 56" />

          <path d="M 378 130 L 416 130" />
          <polyline points="410 126 416 130 410 134" />
        </g>

        {layout.map((mod) => {
          const z = byId[mod.id] || { zone_id: mod.id, name: mod.label };
          const tone = getTone(z);
          const isSelected = selectedZoneId === mod.id;
          const co2Text = z.co2_ppm != null ? `${Number(z.co2_ppm).toLocaleString()} ppm` : 'Gap';
          return (
            <g
              key={mod.id}
              role="button"
              tabIndex={0}
              aria-pressed={isSelected}
              aria-label={`${z.name}: ${co2Text}, ${z.present_crew_count ?? 0} crew`}
              onClick={() => onSelectZone(isSelected ? null : mod.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectZone(isSelected ? null : mod.id);
                }
              }}
              style={{ cursor: 'pointer', outline: 'none' }}
            >
              {isSelected ? (
                <rect
                  x={mod.x - 4}
                  y={mod.y - 4}
                  width={mod.w + 8}
                  height={mod.h + 8}
                  rx="14"
                  fill="none"
                  stroke="#0d7474"
                  strokeWidth="2.5"
                  strokeDasharray="5 3"
                />
              ) : null}
              <rect
                x={mod.x}
                y={mod.y}
                width={mod.w}
                height={mod.h}
                rx="11"
                fill={tone.fill}
                stroke={tone.stroke}
                strokeWidth={isSelected ? '2.4' : '1.6'}
              />
              <text x={mod.x + 12} y={mod.y + 20} fontSize="10.5" fontWeight="700" fill={tone.text}>
                {z.zone_id} · {z.name}
              </text>
              <text
                x={mod.x + mod.w - 10}
                y={mod.y + 19}
                textAnchor="end"
                fontSize="8.5"
                fontWeight="700"
                fill={tone.stroke}
              >
                {tone.tag}
              </text>
              <text
                x={mod.x + 12}
                y={mod.y + (mod.h > 80 ? 52 : 41)}
                fontSize={mod.h > 80 ? '16' : '13'}
                fontWeight="700"
                fontFamily="var(--font-mono)"
                fill="#102424"
              >
                {co2Text}
              </text>
              <text
                x={mod.x + 12}
                y={mod.y + mod.h - 12}
                fontSize="9.5"
                fill="#4a5f5f"
              >
                {z.present_crew_count ?? 0} crew · 7d avg{' '}
                {z.co2_7d_avg_ppm != null ? `${Math.round(z.co2_7d_avg_ppm)} ppm` : '—'}
              </text>
            </g>
          );
        })}

        {/* Telemetry Schematic Key Box */}
        <g transform="translate(584, 22)">
          <rect x="0" y="0" width="144" height="138" rx="10" fill="#f8fafa" stroke="#e1e8e8" strokeWidth="1.2" />
          <text x="12" y="20" fontSize="9.5" fontWeight="700" fill="#4a5f5f">
            HULL LOOP KEY
          </text>
          <circle cx="18" cy="40" r="4.5" fill="#0d7474" />
          <text x="30" y="43" fontSize="9.5" fill="#102424">Nominal band</text>
          <circle cx="18" cy="60" r="4.5" fill="#d97706" />
          <text x="30" y="63" fontSize="9.5" fill="#102424">Scrubber drift</text>
          <circle cx="18" cy="80" r="4.5" fill="#b91c1c" />
          <text x="30" y="83" fontSize="9.5" fill="#102424">SR-03 / Sensor gap</text>
          <line x1="12" y1="98" x2="132" y2="98" stroke="#e1e8e8" strokeWidth="1" />
          <text x="12" y="114" fontSize="8.8" fill="#6c8080">Primary trigger:</text>
          <text x="12" y="128" fontSize="9.2" fontWeight="700" fontFamily="var(--font-mono)" fill="#102424">
            SR-03 @ 5,000 ppm
          </text>
        </g>
      </svg>
    </section>
  );
}

/**
 * Systems Engineer view (F-25) — Strictly anonymized habitat zone telemetry,
 * Crew A..D lagged CO2-symptom correlations, MSIDE environmental findings,
 * sensor quality gaps, and engineering operations guidance.
 */
export default function SystemsEngineerView({ state, activeSubTab, onOpenProtocol }) {
  const subTab = normalizeSubTab(activeSubTab);
  const model = useMemo(() => normalizeEnvState(state), [state]);
  const [selectedZoneId, setSelectedZoneId] = useState(null);
  const [checklist, setChecklist] = useState({
    scrubberCheck: true,
    ventilationBoost: false,
    portableCalibration: false,
  });

  const co2MaxY = Math.max(
    2250,
    ...model.co2Series.map((d) => (d?.value != null ? Number(d.value) : 0))
  );
  const symMaxY = Math.max(
    5,
    ...model.symptomSeries.map((d) => (d?.value != null ? Number(d.value) : 0))
  );

  if (subTab === 'comms') {
    const habitatOpsNotes = model.messages.filter((m) => {
      const toId = String(m.to_id || m.to || '').toLowerCase();
      const fromId = String(m.from_id || m.from || '').toLowerCase();
      return toId.includes('systems') || fromId.includes('systems') || m.channel === 'earth';
    });

    return (
      <div className="stack-col" data-testid="systems-engineer-comms">
        <header className="page-header">
          <div>
            <div className="page-eyebrow">Anonymised Habitat Operations</div>
            <h1>Engineering comms</h1>
            <p className="page-subtitle">
              Air-quality verification checklist and anonymised scrubber action log. No personal
              crew vitals or private crew messages are visible here.
            </p>
          </div>
          <div className="page-header-pills">
            <span className="pill pill-purple">
              <Icon name="lock" size={12} />
              <span>No identities</span>
            </span>
            <span className="pill pill-teal">
              <Icon name="wind" size={12} />
              <span>Habitat ops</span>
            </span>
          </div>
        </header>

        <div className="grid-2">
          <section className="card">
            <div className="card-header">
              <div>
                <h2 className="card-title">US Lab air verification checklist</h2>
                <p className="card-subtitle">
                  Confirm cabin air independently before attributing crew symptoms.
                </p>
              </div>
              <span className="pill pill-amber">
                <Icon name="alert-triangle" size={12} />
                <span>Action window</span>
              </span>
            </div>

            <div className="stack-col" style={{ gap: 10 }}>
              {[
                {
                  key: 'scrubberCheck',
                  title: 'Inspect US Lab CO2 scrubber bed & differential pressure',
                  detail: 'Day 19 exceeded 5,000 ppm (SR-03); post-service reading Day 23 is 1,113 ppm.',
                },
                {
                  key: 'ventilationBoost',
                  title: 'Hold US Lab ventilation at 130% nominal during multi-crew work',
                  detail: 'Counterfactual projection indicates ~245 ppm reduction across occupied blocks.',
                },
                {
                  key: 'portableCalibration',
                  title: 'Cross-check portable CO2 sensor against fixed Lab rack',
                  detail: 'Resolve Day 18 2h packet-loss window and confirm sensor agreement.',
                },
              ].map((item) => {
                const done = checklist[item.key];
                return (
                  <button
                    key={item.key}
                    type="button"
                    className="boundary-item"
                    style={{ width: '100%', textAlign: 'left', justifyContent: 'space-between' }}
                    onClick={() =>
                      setChecklist((prev) => ({ ...prev, [item.key]: !prev[item.key] }))
                    }
                  >
                    <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                      <span style={{ color: done ? 'var(--teal)' : 'var(--text-muted)', marginTop: 2 }}>
                        <Icon name={done ? 'check-circle' : 'alert-triangle'} size={15} />
                      </span>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{item.title}</div>
                        <div style={{ fontSize: '0.76rem', color: 'var(--text-muted)', marginTop: 2 }}>
                          {item.detail}
                        </div>
                      </div>
                    </div>
                    <span className={`pill ${done ? 'pill-teal' : 'pill-neutral'}`}>
                      {done ? 'Verified' : 'Pending'}
                    </span>
                  </button>
                );
              })}
            </div>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 14 }}>
              {['PROT-ENV-01', 'PROT-ENV-02'].map((pid) => (
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
          </section>

          <section className="card">
            <div className="card-header">
              <div>
                <h2 className="card-title">Habitat operations log</h2>
                <p className="card-subtitle">Anonymised telemetry and scrubber maintenance events.</p>
              </div>
              <span className="pill pill-neutral">Day {model.day}</span>
            </div>

            <div className="stack-col" style={{ gap: 10 }}>
              <div className="card-muted">
                <div style={{ fontWeight: 700, fontSize: '0.84rem' }}>
                  Day 22 · US Lab scrubber cartridge serviced
                </div>
                <p style={{ margin: '4px 0 0', fontSize: '0.79rem', color: 'var(--text-secondary)' }}>
                  Zone CO2 stepped down from &gt;5,000 ppm peak (Day 19 SR-03) toward 1,113 ppm on
                  Day 23.
                </p>
              </div>
              <div className="card-muted">
                <div style={{ fontWeight: 700, fontSize: '0.84rem' }}>
                  Day 18 · US Lab CO2 sensor packet loss (2h)
                </div>
                <p style={{ margin: '4px 0 0', fontSize: '0.79rem', color: 'var(--text-secondary)' }}>
                  14:00–16:00 preserved as an explicit gap. Not filled or smoothed as normal.
                </p>
              </div>
              {habitatOpsNotes.slice(0, 3).map((msg, i) => (
                <div key={msg.message_id || i} className="card-muted">
                  <div style={{ fontWeight: 600, fontSize: '0.83rem' }}>
                    {msg.to_label || 'Mission dispatch'} · {msg.status || 'queued'}
                  </div>
                  <p style={{ margin: '4px 0 0', fontSize: '0.79rem', color: 'var(--text-secondary)' }}>
                    {msg.body || msg.text}
                  </p>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    );
  }

  if (subTab === 'scope') {
    return (
      <div className="stack-col" data-testid="systems-engineer-scope">
        <header className="page-header">
          <div>
            <div className="page-eyebrow">Privacy &amp; Role Boundary</div>
            <h1>Access scope</h1>
            <p className="page-subtitle">
              Systems Engineers inspect cabin zones and anonymised Crew A–D statistical coupling
              without exposing astronaut identities or personal health records.
            </p>
          </div>
          <span className="pill pill-purple">
            <Icon name="lock" size={12} />
            <span>Anonymised role</span>
          </span>
        </header>

        <div className="grid-2">
          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Allowed in Systems Engineer scope</h2>
              <span className="pill pill-teal">
                <Icon name="check-circle" size={12} />
                <span>Permitted</span>
              </span>
            </div>
            <div className="stack-col" style={{ gap: 8 }}>
              {[
                'Zone CO2, temperature, humidity, acoustic & occupancy counts (N1, LAB, CQ, AL)',
                'Anonymised Crew A–D lagged correlation indices (r, lag, FDR q, confidence)',
                'Shared habitat exposure clusters & MSIDE cross-crew environmental findings',
                'Explicit environmental sensor gaps and shared habitat radiation dose rate',
              ].map((text) => (
                <div key={text} className="boundary-item">
                  <span style={{ color: 'var(--teal)' }}>
                    <Icon name="check-circle" size={15} />
                  </span>
                  <span>{text}</span>
                </div>
              ))}
            </div>
          </section>

          <section className="card">
            <div className="card-header">
              <h2 className="card-title">Blocked from Systems Engineer scope</h2>
              <span className="pill pill-neutral">
                <Icon name="lock" size={12} />
                <span>Withheld</span>
              </span>
            </div>
            <div className="stack-col" style={{ gap: 8 }}>
              {[
                'Crew names, initials, ages, or personal identifiers',
                'Individual HRV, resting HR, SpO2, sleep, or cognitive PVT metrics',
                'Behavioural telemetry, check-in notes, or private on-device journals',
                'Crew message contents or individual SOS health snapshots',
              ].map((text) => (
                <div key={text} className="boundary-item blocked">
                  <Icon name="lock" size={15} />
                  <span>{text}</span>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    );
  }

  // Default: Habitat map workspace
  return (
    <div className="stack-col" data-testid="systems-engineer-view">
      {/* Page Header */}
      <header className="page-header">
        <div>
          <div className="page-eyebrow">Anonymised Habitat View</div>
          <h1>Habitat signals</h1>
          <p className="page-subtitle">
            Cabin sensors are joined to crew location by zone. Shared exposure is a hypothesis to
            verify, not a diagnosis of an individual.
          </p>
        </div>
        <div className="page-header-pills">
          <span className="pill pill-teal">
            <Icon name="wind" size={13} />
            <span>CO2 · thermal · acoustic</span>
          </span>
          <span className="pill pill-purple">
            <Icon name="users" size={13} />
            <span>No identities</span>
          </span>
          <span className={`pill ${model.envGaps.length > 0 ? 'pill-amber' : 'pill-teal'}`}>
            <Icon name={model.envGaps.length > 0 ? 'sensor-gap' : 'check-circle'} size={13} />
            <span>
              {model.envGaps.length} sensor gap{model.envGaps.length === 1 ? '' : 's'}
            </span>
          </span>
        </div>
      </header>

      <HabitatHullSchematic
        zones={model.zones}
        selectedZoneId={selectedZoneId}
        onSelectZone={setSelectedZoneId}
      />

      {/* Shared habitat exposure signal banner */}
      <section
        className={`card ${model.sharedAlert.active ? 'card-amber' : 'card-teal'}`}
        aria-label="Shared habitat exposure signal"
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
          <span className={`card-icon-badge ${model.sharedAlert.active ? 'amber' : ''}`}>
            <Icon name="wind" size={18} />
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
              <h2 className="card-title">{model.sharedAlert.headline || 'Shared habitat exposure signal'}</h2>
              <span className={`pill ${model.sharedAlert.active ? 'pill-amber' : 'pill-teal'}`}>
                <Icon name={model.sharedAlert.active ? 'alert-triangle' : 'check-circle'} size={12} />
                <span>{Math.round(Number(model.sharedAlert.confidence || 0.9) * 100)}% confidence</span>
              </span>
              <span className="pill pill-neutral">
                Lag {model.sharedAlert.lag_range || '0–1 day'}
              </span>
            </div>

            <p style={{ margin: '0 0 8px', fontSize: '0.88rem', color: 'var(--text-primary)' }}>
              {model.sharedAlert.summary}
            </p>

            <div
              className="card-muted"
              style={{
                padding: '8px 12px',
                fontSize: '0.79rem',
                color: 'var(--text-secondary)',
                marginBottom: 10,
              }}
            >
              <strong>Prevent misattribution:</strong>{' '}
              {model.sharedAlert.prevent_misattribution ||
                'do not label a crew member as "sick" when the same symptom pattern follows a shared zone exposure. Individual illness is not excluded.'}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              {(model.sharedAlert.protocol_refs || ['PROT-ENV-01', 'PROT-ENV-02', 'PROT-MED-01']).map(
                (pid) => (
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
                )
              )}
              <span className="pill pill-neutral">
                <Icon name="users" size={12} />
                <span>
                  {model.sharedAlert.affected_crew_count ?? 0} crew · anonymous labels only
                </span>
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Main Split: 2x2 Habitat Zone Map + Crew <-> Zone Correlations */}
      <div className="split-main-aside">
        <section className="card" aria-label="Habitat zone map">
          <div className="card-header">
            <div>
              <h2 className="card-title">Habitat zone map</h2>
              <p className="card-subtitle">Anonymised occupancy and environmental signals.</p>
            </div>
            <span className="pill pill-neutral">
              <Icon name="wind" size={12} />
              <span>CO2 primary</span>
            </span>
          </div>

          <div className="grid-2">
            {model.zones.map((zone) => {
              const isAbove =
                String(zone.status).toLowerCase().includes('above') ||
                String(zone.status).toLowerCase().includes('critical') ||
                Number(zone.co2_ppm || 0) > 1050 ||
                Number(zone.co2_7d_avg_ppm || 0) >= 1500;
              const isGap = zone.co2_ppm == null || String(zone.status).toLowerCase().includes('gap');
              const co2Val = zone.co2_ppm != null ? Number(zone.co2_ppm) : null;
              const fillPct = co2Val != null ? Math.min(100, Math.max(12, (co2Val / 2500) * 100)) : 0;
              const trendPct = Math.round(Number(zone.trend_7d_pct ?? 0));
              const sensorClean = (zone.sensor_status || 'clean') === 'clean';
              const isFocused = !selectedZoneId || selectedZoneId === zone.zone_id;

              return (
                <div
                  key={zone.zone_id}
                  className={`zone-card ${isAbove ? 'elevated' : ''}`}
                  style={{
                    opacity: isFocused ? 1 : 0.48,
                    outline: selectedZoneId === zone.zone_id ? '2px solid var(--teal)' : 'none',
                    transition: 'opacity 180ms var(--ease-out)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '0.94rem' }}>{zone.name}</div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {zone.present_crew_count} crew present · {zone.zone_id}
                      </div>
                    </div>
                    <span className={`pill ${isGap ? 'pill-red' : isAbove ? 'pill-amber' : 'pill-teal'}`}>
                      <Icon
                        name={isGap ? 'sensor-gap' : isAbove ? 'alert-triangle' : 'check-circle'}
                        size={12}
                      />
                      <span>{zone.status}</span>
                    </span>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
                    <div>
                      <span className="metric-big" style={{ fontSize: '1.6rem' }}>
                        {co2Val != null ? co2Val.toLocaleString() : 'Gap'}
                      </span>
                      <span className="metric-unit">{co2Val != null ? 'ppm' : '(not imputed)'}</span>
                    </div>
                    <div style={{ textAlign: 'right', fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                      <div className="tabular-nums" style={{ fontWeight: 600 }}>
                        {trendPct >= 0 ? '↗' : '↘'} {Math.abs(trendPct)}%
                      </div>
                      <div style={{ color: 'var(--text-muted)' }}>7-day trend</div>
                    </div>
                  </div>

                  <div className="zone-meter-track" aria-hidden="true">
                    <div
                      className={`zone-meter-fill ${
                        co2Val >= 5000 ? 'critical' : isAbove ? 'elevated' : ''
                      }`}
                      style={{
                        width: '100%',
                        transform: `scaleX(${Math.max(0, Math.min(1, fillPct / 100))})`,
                      }}
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                    <span className="tabular-nums">
                      7d avg {zone.co2_7d_avg_ppm != null ? `${Math.round(zone.co2_7d_avg_ppm).toLocaleString()} ppm` : '—'}
                    </span>
                    <span className={`pill ${sensorClean ? 'pill-teal' : 'pill-amber'}`}>
                      <Icon name={sensorClean ? 'check-circle' : 'alert-triangle'} size={11} />
                      <span>{sensorClean ? 'clean' : 'gap'}</span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <div
            className="card-muted"
            style={{
              marginTop: 14,
              display: 'flex',
              alignItems: 'flex-start',
              gap: 8,
              fontSize: '0.79rem',
              color: 'var(--text-secondary)',
            }}
          >
            <Icon name="info" size={15} />
            <span>{model.sr03Note}</span>
          </div>
        </section>

        {/* Crew <-> zone correlations (Strictly Anonymised Crew A..D) */}
        <section className="card" aria-label="Anonymised crew and zone correlations">
          <div className="card-header">
            <div>
              <h2 className="card-title">Crew ↔ zone correlations</h2>
              <p className="card-subtitle">
                Lagged Pearson on daily means. Association, not causation.
              </p>
            </div>
            <span className="pill pill-purple">Anonymised</span>
          </div>

          <div className="stack-col" style={{ gap: 10 }}>
            {model.crewCorrelations.map((item) => (
              <div key={item.crew_label} className={`corr-card ${item.linked ? 'linked' : ''}`}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <strong style={{ fontSize: '0.89rem' }}>{item.crew_label}</strong>
                  <span className={`pill ${item.linked ? 'pill-amber' : 'pill-neutral'}`}>
                    <Icon name={item.linked ? 'link' : 'info'} size={11} />
                    <span>{item.linked ? 'linked' : 'no clear link'}</span>
                  </span>
                </div>

                <div className="corr-stats">
                  <div>
                    <div className="corr-stat-label">R</div>
                    <div className="corr-stat-val">{item.r.toFixed(2)}</div>
                  </div>
                  <div>
                    <div className="corr-stat-label">Lag</div>
                    <div className="corr-stat-val">{item.lag_days}d</div>
                  </div>
                  <div>
                    <div className="corr-stat-label">Conf</div>
                    <div className="corr-stat-val">{Math.round(item.confidence * 100)}%</div>
                  </div>
                </div>

                <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                  {item.summary}
                </p>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* Lower Split: Dual SVG Charts + Radiation & Environmental Sensor Gaps */}
      <div className="split-main-aside">
        <div className="grid-2">
          <section className="card">
            <div className="card-header" style={{ marginBottom: 8 }}>
              <h2 className="card-title">Aggregate CO2 exposure</h2>
              <span className="pill pill-neutral">ppm</span>
            </div>
            <MetricAreaChart
              series={model.co2Series}
              maxY={Math.ceil(co2MaxY / 50) * 50}
              strokeColor="#b45309"
              fillColor="rgba(245, 158, 11, 0.14)"
              baselineY={880}
              unit="ppm"
            />
            <p className="card-subtitle" style={{ marginTop: 8 }}>
              Wake-hour exposure joined to each crew member&apos;s zone assignment.
            </p>
          </section>

          <section className="card">
            <div className="card-header" style={{ marginBottom: 8 }}>
              <h2 className="card-title">Aggregate symptom index</h2>
              <span className="pill pill-purple">0–10</span>
            </div>
            <MetricAreaChart
              series={model.symptomSeries}
              maxY={Math.ceil(symMaxY)}
              strokeColor="#5b21b6"
              fillColor="rgba(109, 40, 217, 0.12)"
              baselineY={1.0}
              unit="pts"
            />
            <p className="card-subtitle" style={{ marginTop: 8 }}>
              Headache, fatigue, breathing and energy deficit. Anonymised aggregate; not an
              individual score.
            </p>
          </section>
        </div>

        <div className="stack-col">
          <section className="card">
            <div className="card-header" style={{ marginBottom: 8 }}>
              <h2 className="card-title">Radiation · long-term</h2>
              <span className="pill pill-neutral">Shared habitat dose</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
              <div>
                <span className="metric-big">{Math.round(model.radDaily)}</span>
                <span className="metric-unit">µSv/day</span>
              </div>
              <span className="pill pill-teal">
                <Icon name="check-circle" size={12} />
                <span>normal</span>
              </span>
            </div>
            <p className="card-subtitle" style={{ marginTop: 8 }}>
              Cumulative dose ({Number(model.radCum).toFixed(2)} mSv) appears on each
              astronaut&apos;s long-term trend card. Radiation is a shared habitat signal, not a
              personal diagnosis.
            </p>
          </section>

          <section className="card card-amber">
            <div className="card-header" style={{ marginBottom: 8 }}>
              <div className="card-title-group">
                <Icon name="sensor-gap" size={17} />
                <h2 className="card-title">Environmental sensor gaps</h2>
              </div>
            </div>
            {model.envGaps.length === 0 ? (
              <p className="card-subtitle" style={{ margin: 0 }}>
                No environmental sensor gaps recorded in this window.
              </p>
            ) : (
              <div className="stack-col" style={{ gap: 6 }}>
                {model.envGaps.map((gap, idx) => (
                  <p key={idx} style={{ margin: 0, fontSize: '0.8rem', color: 'var(--amber-text)' }}>
                    {formatGapText(gap)}
                  </p>
                ))}
                <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                  Correlation confidence is lowered; the missing values are not imputed.
                </p>
              </div>
            )}
          </section>
        </div>
      </div>

      {/* MSIDE environmental findings */}
      <section className="card" aria-label="MSIDE environmental findings">
        <div className="page-eyebrow" style={{ marginBottom: 10 }}>
          MSIDE Environmental Findings
        </div>
        {model.msideFindings.length === 0 ? (
          <div className="card-muted" style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            No cross-crew environmental coupling clusters above FDR control at this mission clock.
          </div>
        ) : (
          <div className="stack-col" style={{ gap: 10 }}>
            {model.msideFindings.map((finding, idx) => (
              <div key={finding.finding_id || idx} className="alert-item purple">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <strong style={{ fontSize: '0.92rem' }}>{finding.title}</strong>
                  <span className="pill pill-purple">
                    {Math.round(Number(finding.confidence || 0.9) * 100)}%
                  </span>
                  <span className="pill pill-neutral tabular-nums">
                    r {Number(finding.correlation_r ?? 0.95).toFixed(2)}
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                  {finding.summary}
                </p>
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
                  {(finding.protocol_refs || ['PROT-ENV-01', 'PROT-ENV-02', 'PROT-MED-01']).map(
                    (pid) => (
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
                    )
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        <p style={{ margin: '10px 0 0', fontSize: '0.76rem', color: 'var(--text-muted)' }}>
          Correlation is not causation. Environmental findings must be confirmed with cabin-air
          measurements; personal findings require human review.
        </p>
      </section>

      {/* Method & guardrails */}
      <section className="card" aria-label="Method and guardrails">
        <div className="card-header" style={{ marginBottom: 8 }}>
          <div>
            <h2 className="card-title">Method &amp; guardrails</h2>
            <p className="card-subtitle">
              Hourly location joined to zone CO2; daily means correlated with symptom score
              (Pearson, lag 0–1 day). Association, not causation.
            </p>
          </div>
          <span className="pill pill-neutral">
            <Icon name="pulse" size={12} />
            <span>{model.dailyPoints} daily points</span>
          </span>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
          {model.zones.map((z) => {
            const clean = (z.sensor_status || 'clean') === 'clean';
            return (
              <span key={z.zone_id} className={`pill ${clean ? 'pill-neutral' : 'pill-amber'}`}>
                {z.name}: sensor {clean ? 'clean' : 'gap'}
              </span>
            );
          })}
        </div>

        <p style={{ margin: 0, fontSize: '0.79rem', color: 'var(--text-secondary)' }}>
          Shared exposure is a hypothesis to verify with cabin-air measurements. It does not rule
          out individual illness.
        </p>
      </section>
    </div>
  );
}
