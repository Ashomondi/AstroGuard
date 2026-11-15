/**
 * AstroGuard Deterministic Offline Mission Mirror (Days 1–30)
 *
 * Complete client-side mirror matching backend schema (`schema.py`), protocol library
 * (`protocols.py`), readiness/environment/MSIDE/behavioral/counterfactual engines,
 * consent boundaries, prioritized Earth sync queue, and local SOS persistence.
 *
 * All numbers are illustrative sample telemetry — decision support, not diagnosis.
 */

export const ROLES = [
  "Astronaut",
  "Crew Health Officer",
  "Systems Engineer",
  "Ground Support",
];

export const CREW_ROSTER = [
  {
    astronaut_id: "ast-01",
    name: "Cmdr. Elena Vasquez",
    short_name: "Elena",
    initials: "EV",
    title: "Mission Commander",
    age: 42,
    default_zone: "LAB",
    anonymous_label: "Crew A",
  },
  {
    astronaut_id: "ast-02",
    name: "Dr. Marcus Chen",
    short_name: "Marcus",
    initials: "MC",
    title: "Flight Engineer / Scientist",
    age: 38,
    default_zone: "CQ",
    anonymous_label: "Crew B",
  },
  {
    astronaut_id: "ast-03",
    name: "Yuki Tanaka",
    short_name: "Yuki",
    initials: "YT",
    title: "Pilot",
    age: 35,
    default_zone: "LAB",
    anonymous_label: "Crew C",
  },
  {
    astronaut_id: "ast-04",
    name: "Omar Haddad",
    short_name: "Omar",
    initials: "OH",
    title: "Mission Specialist",
    age: 36,
    default_zone: "LAB",
    anonymous_label: "Crew D",
  },
];

export const HABITAT_ZONES = [
  { zone_id: "N1", name: "Node 1", short_code: "N1", nominal_co2_ppm: 830 },
  { zone_id: "LAB", name: "US Lab", short_code: "LAB", nominal_co2_ppm: 880 },
  { zone_id: "CQ", name: "Crew Quarters", short_code: "CQ", nominal_co2_ppm: 780 },
  { zone_id: "AL", name: "Airlock", short_code: "AL", nominal_co2_ppm: 620 },
];

export const PROTOCOL_LIBRARY = {
  "PROT-REC-01": {
    protocol_id: "PROT-REC-01",
    title: "24-Hour Post-Exertion Recovery Block",
    category: "recovery",
    summary:
      "Reduce strenuous exercise load for 24 hours when post-exercise HR recovery lags personal baseline.",
    steps: [
      "Swap high-intensity resistance or VO2 work for light mobility and hydration.",
      "Log subjective energy and breathlessness in the 60-second check-in.",
      "Keep wristband snug overnight to ensure clean resting HR and HRV windows.",
    ],
    escalate_if:
      "Resting HR stays elevated >15 bpm above personal baseline, or chest tightness/dyspnea persists — trigger Crew Health Officer check or SOS.",
    note: "Illustrative flight wellness checklist — decision support, not diagnosis.",
  },
  "PROT-REC-02": {
    protocol_id: "PROT-REC-02",
    title: "Repeat 1-Minute Heart-Rate Recovery Check",
    category: "recovery",
    summary:
      "Verify whether reduced post-exercise HR drop reflects sustained strain or a transient measurement artifact.",
    steps: [
      "Confirm wearable strap contact and clean signal before starting light warm-up.",
      "Record seated/quiet heart rate exactly 60 seconds after stopping exertion.",
      "Compare against your early-mission personal reference rather than Earth tables.",
    ],
    escalate_if:
      "1-minute recovery drop stays >10 bpm below personal baseline on two consecutive sessions or dizziness occurs.",
    note: "Illustrative flight wellness checklist — decision support, not diagnosis.",
  },
  "PROT-SLP-01": {
    protocol_id: "PROT-SLP-01",
    title: "Protected 7.5-Hour Circadian Sleep Window",
    category: "sleep_cognitive",
    summary:
      "Protect an uninterrupted sleep block to reduce cognitive lapses and stabilize HRV.",
    steps: [
      "Dim cabin task lighting 45 minutes before scheduled sleep onset.",
      "Verify Crew Quarters acoustic and ventilation settings before sleep.",
      "Avoid non-essential operational alerts during the protected 7.5-hour window.",
    ],
    escalate_if:
      "Sleep fragmentation remains elevated for 3+ consecutive nights or PVT lapses exceed 3.",
    note: "Illustrative flight wellness checklist — decision support, not diagnosis.",
  },
  "PROT-SLP-02": {
    protocol_id: "PROT-SLP-02",
    title: "Standardized Ship-Clock PVT Re-Test",
    category: "sleep_cognitive",
    summary:
      "Confirm cognitive readiness trend at the same ship-clock time to remove circadian bias.",
    steps: [
      "Run the 1-minute PVT reaction test in quiet Crew Quarters lighting.",
      "Check data-quality badge afterward to confirm no distraction or gap.",
      "Defer precision robotics or EVA tasks if reaction time remains slowed with lapses.",
    ],
    escalate_if:
      "PVT mean reaction time stays >60 ms above personal baseline with lapses >= 3.",
    note: "Illustrative flight wellness checklist — decision support, not diagnosis.",
  },
  "PROT-ENV-01": {
    protocol_id: "PROT-ENV-01",
    title: "US Lab CO2 Scrubber & Ventilation Boost",
    category: "environment",
    summary:
      "Increase cabin airflow and inspect CO2 scrubber beds when zone CO2 correlates with crew symptoms.",
    steps: [
      "Increase US Lab ventilation flow to 130% nominal and check scrubber differential pressure.",
      "Inspect portable CO2 sensor calibration against fixed cabin sensors.",
      "Verify no packet loss on zone air-quality telemetry.",
    ],
    escalate_if:
      "Zone CO2 reaches >= 5,000 ppm (hard rule SR-03) or symptoms fail to improve after scrubber service.",
    note: "Illustrative flight wellness checklist — decision support, not diagnosis.",
  },
  "PROT-ENV-02": {
    protocol_id: "PROT-ENV-02",
    title: "Zone Rotation & Portable Air Quality Check",
    category: "environment",
    summary:
      "Temporarily redistribute non-essential tasks out of an elevated-CO2 zone while air is verified.",
    steps: [
      "Move extended desk or cognitive tasks from US Lab to Node 1 or Crew Quarters.",
      "Carry a portable CO2 monitor during transitional work blocks.",
      "Re-evaluate headache and fatigue scores 4 hours after changing zones.",
    ],
    escalate_if:
      "Symptoms worsen outside US Lab — treat as possible individual illness and consult Crew Health Officer.",
    note: "Illustrative flight wellness checklist — decision support, not diagnosis.",
  },
  "PROT-MED-01": {
    protocol_id: "PROT-MED-01",
    title: "Peer Health Officer Cardiopulmonary Check",
    category: "medical_support",
    summary:
      "Structured non-physician peer check following an active medical alert or SOS.",
    steps: [
      "Seat the crew member calmly and verify SpO2, resting pulse, and respiratory effort.",
      "Review emergency-scoped vitals timeline and note symptom onset.",
      "Prepare Earth medical summary packet in priority queue if symptoms persist.",
    ],
    escalate_if:
      "SpO2 < 90%, persistent chest pain, or worsening dyspnea — maintain SOS active and initiate Earth consult.",
    note: "Illustrative flight wellness checklist — decision support, not diagnosis.",
  },
  "PROT-RAD-01": {
    protocol_id: "PROT-RAD-01",
    title: "Cumulative Dosimetry & Shielded Zone Review",
    category: "radiation",
    summary:
      "Track long-term cumulative habitat radiation exposure and verify sleep-bay shielding.",
    steps: [
      "Confirm personal and habitat dosimeter logs show no sensor dropout.",
      "Keep sleep schedule anchored in higher-shielding Crew Quarters.",
      "Include cumulative dose curve in periodic Ground Support summary.",
    ],
    escalate_if:
      "Solar particle dose-rate spike exceeds operational threshold — follow storm shelter procedure.",
    note: "Illustrative flight wellness checklist — decision support, not diagnosis.",
  },
};

export const DEFAULT_CONSENT_PROFILES = {
  "ast-01": {
    astronaut_id: "ast-01",
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
    override_duration_hours: 2,
  },
  "ast-02": {
    astronaut_id: "ast-02",
    normal: {
      physio: true,
      cognitive: true,
      behaviour: false,
      habitat: true,
      ground_sharing: false,
    },
    emergency: {
      physio: true,
      cognitive: true,
      behaviour: false,
      habitat: true,
      ground_sharing: false,
    },
    override_duration_hours: 2,
  },
  "ast-03": {
    astronaut_id: "ast-03",
    normal: {
      physio: true,
      cognitive: false,
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
    override_duration_hours: 2,
  },
  "ast-04": {
    astronaut_id: "ast-04",
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
    override_duration_hours: 2,
  },
};

const STORAGE_KEY = "astroguard_offline_mirror_v1";
let memoryStore = null;

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

function round1(v) {
  return Math.round(v * 10) / 10;
}

function round2(v) {
  return Math.round(v * 100) / 100;
}

function createInitialMutableStore() {
  return {
    earth_link_online: false,
    consent_profiles: JSON.parse(JSON.stringify(DEFAULT_CONSENT_PROFILES)),
    access_log: [
      {
        log_id: "aud-01",
        actor_role: "Systems Engineer",
        target_astronaut_id: "anonymised",
        access_type: "environment access",
        timestamp_label: "Day 23, 16:00",
        mode: "Normal",
        scope: "habitat aggregate",
        emergency_override: false,
        reason: "Anonymised habitat aggregate requested.",
        fields: ["co2_ppm", "cabin_temp_c", "cabin_noise_db"],
      },
      {
        log_id: "aud-02",
        actor_role: "Systems Engineer",
        target_astronaut_id: "anonymised",
        access_type: "environment access",
        timestamp_label: "Day 19, 14:00",
        mode: "Normal",
        scope: "habitat aggregate",
        emergency_override: false,
        reason: "Routine scrubber inspection. Anonymised aggregate only.",
        fields: ["co2_ppm", "cabin_temp_c", "cabin_noise_db"],
      },
    ],
    sos_events: [
      {
        sos_id: "sos-seed-23",
        astronaut_id: "ast-01",
        astronaut_name: "Cmdr. Elena Vasquez",
        type: "medical",
        note: "Unusually winded after exercise block. Requesting guidance; comms are offline.",
        day: 23,
        hour: 14,
        minute: 20,
        timestamp_label: "Day 23 · 14:20 ship time",
        short_date: "Day 23, 14:20",
        status: "queued",
        onboard_acknowledged: true,
        priority: 0,
        vitals_snapshot: {
          hr_bpm: 73,
          resting_hr_bpm: 58.2,
          hrv_ms: 42.8,
          spo2_pct: 97,
        },
        env_snapshot: {
          zone_id: "LAB",
          co2_ppm: 1113,
        },
        active_alerts: ["SR-05"],
        override_logged: true,
      },
    ],
    messages: [
      {
        message_id: "msg-01",
        from_id: "ast-01",
        from_label: "Cmdr. Elena Vasquez",
        to_id: "earth",
        to_label: "Home (Earth)",
        channel: "earth",
        kind: "text",
        body: "Attaching my 7-day recovery chart with consent. Resting heart rate is creeping up; I'm taking a recovery block today.",
        audio_duration_s: 0,
        size_kb: 18,
        bandwidth_warning: true,
        attachment: {
          label: "Recovery trend — 7 days · consented health chart",
          detail: "Consented health attachment · adds transmit time on a narrow link",
          type: "recovery_chart_7d",
        },
        status: "queued",
        light_delay_min: 12.8,
        day: 23,
        timestamp_label: "Day 23, 13:45 · Earth light time 12.8 min",
        read_by: ["ast-01"],
      },
      {
        message_id: "msg-02",
        from_id: "ast-02",
        from_label: "Dr. Marcus Chen",
        to_id: "ast-01",
        to_label: "Cmdr. Elena Vasquez",
        channel: "crew",
        kind: "text",
        body: "Sleep was broken again but I'm fine. Might skip the morning science block and catch up later.",
        audio_duration_s: 0,
        size_kb: 1,
        bandwidth_warning: false,
        attachment: null,
        status: "delivered",
        light_delay_min: 0,
        day: 21,
        timestamp_label: "Day 21, 22:00 · on-board",
        read_by: ["ast-02"],
      },
      {
        message_id: "msg-03",
        from_id: "health_officer",
        from_label: "Crew Health Officer",
        to_id: "ast-01",
        to_label: "Cmdr. Elena Vasquez",
        channel: "crew",
        kind: "text",
        body: "I saw your recovery numbers. No need to push through the next exercise block — a 24-hour recovery block is on the protocol shelf. Tell me if you feel short of breath at rest.",
        audio_duration_s: 0,
        size_kb: 1,
        bandwidth_warning: false,
        attachment: null,
        status: "delivered",
        light_delay_min: 0,
        day: 21,
        timestamp_label: "Day 21, 10:00 · on-board",
        read_by: ["health_officer"],
      },
      {
        message_id: "msg-04",
        from_id: "earth",
        from_label: "Home (Earth)",
        to_id: "ast-01",
        to_label: "Cmdr. Elena Vasquez",
        channel: "earth",
        kind: "text",
        body: "Elena — we received your Day 20 summary. Keep the daily check-ins coming, even short ones. Earth medical is reviewing your recovery trend; no new instructions until the next window.",
        audio_duration_s: 0,
        size_kb: 2,
        bandwidth_warning: false,
        attachment: null,
        status: "read",
        light_delay_min: 12.1,
        day: 20,
        timestamp_label: "Day 20, 06:00 · Earth light time 12 min",
        read_by: ["earth", "ast-01"],
      },
      {
        message_id: "msg-05",
        from_id: "earth",
        from_label: "Home (Earth)",
        to_id: "all",
        to_label: "All crew",
        channel: "earth",
        kind: "text",
        body: "Resupply burn confirmed for Day 26. No changes to the science plan. Please continue water reclamation checks in the Lab.",
        audio_duration_s: 0,
        size_kb: 1,
        bandwidth_warning: false,
        attachment: null,
        status: "delivered",
        light_delay_min: 14.0,
        day: 19,
        timestamp_label: "Day 19, 06:00 · Earth light time 14 min",
        read_by: ["earth"],
      },
    ],
    sync_queue: [
      {
        item_id: "sync-sos-23",
        category: "sos",
        priority: 0,
        title: "SOS — Medical (ast-01)",
        detail: "Priority 0 emergency beacon packet",
        status: "queued",
        day: 23,
        size_kb: 4,
        ref_id: "sos-seed-23",
      },
      {
        item_id: "sync-crit-23",
        category: "critical_alert",
        priority: 1,
        title: "SR-05 deterministic emergency packet",
        detail: "Safety rule telemetry snapshot",
        status: "queued",
        day: 23,
        size_kb: 2,
      },
      {
        item_id: "sync-msg-01",
        category: "message",
        priority: 2,
        title: "Message to Home (Earth) + chart",
        detail: "ast-01 -> Earth · 18 KB",
        status: "queued",
        day: 23,
        size_kb: 18,
        ref_id: "msg-01",
      },
      {
        item_id: "sync-msg-06",
        category: "message",
        priority: 2,
        title: "Engineering air scrubber log note",
        detail: "Systems -> Earth · 2 KB",
        status: "queued",
        day: 22,
        size_kb: 2,
      },
      {
        item_id: "sync-sum-01",
        category: "summary",
        priority: 3,
        title: "Day 22 Mission Readiness Summary",
        detail: "Aggregate crew bands + zone CO2",
        status: "queued",
        day: 22,
        size_kb: 6,
      },
      {
        item_id: "sync-sum-02",
        category: "summary",
        priority: 3,
        title: "Day 23 Consented Recovery Summary",
        detail: "Encrypted summary bundle",
        status: "queued",
        day: 23,
        size_kb: 8,
      },
      {
        item_id: "sync-tel-01",
        category: "telemetry",
        priority: 4,
        title: "Bulk wearable + habitat telemetry batch",
        detail: "Days 20–23 clean records + gap markers",
        status: "queued",
        day: 23,
        size_kb: 140,
      },
    ],
    checkins: {},
    pvt_tests: {},
  };
}

function loadStore() {
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && parsed.consent_profiles && parsed.messages) {
          return parsed;
        }
      }
    } catch {
      // ignore parse errors
    }
    const init = createInitialMutableStore();
    saveStore(init);
    return init;
  }
  if (!memoryStore) {
    memoryStore = createInitialMutableStore();
  }
  return memoryStore;
}

function saveStore(store) {
  if (typeof window !== "undefined" && window.localStorage) {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
    } catch {
      // ignore quota errors
    }
  } else {
    memoryStore = store;
  }
}

export function resetFallbackStore() {
  const init = createInitialMutableStore();
  saveStore(init);
  return init;
}

// --- Deterministic 30-Day Telemetry Curves ---

function labCo2ForDay(day) {
  // Steady Day 1-14, rises Day 15-19 (peaks 5280 ppm on Day 19 -> SR-03!),
  // declines after scrubber service Day 22 (Day 23 = 1113 ppm)
  const table = [
    870, 880, 875, 890, 882, 878, 895, 884, 890, 885,
    892, 905, 898, 910, 960, 1280, 1950, 2850, 5280, 3420,
    2150, 1460, 1113, 980, 920, 895, 888, 882, 876, 875,
  ];
  return table[clamp(day, 1, 30) - 1];
}

function zoneCo2ForDay(zoneId, day) {
  if (zoneId === "LAB") return labCo2ForDay(day);
  if (zoneId === "N1") {
    const bump = day >= 17 && day <= 22 ? Math.round((labCo2ForDay(day) - 880) * 0.14) : 0;
    return 830 + ((day * 7) % 15) - 7 + (day === 23 ? 4 : bump);
  }
  if (zoneId === "CQ") {
    return 778 + ((day * 5) % 12) - 4 + (day === 23 ? 2 : 0);
  }
  return 620 + ((day * 3) % 9) - 3 + (day === 23 ? 2 : 0);
}

function radiationDailyUsv(day) {
  return 498 + ((day * 11) % 27);
}

function cumulativeRadiationMsv(day) {
  let sum = 1.24; // pre-transit / mission day 0 offset to align Day 23 = 12.82 mSv
  for (let d = 1; d <= day; d += 1) {
    sum += radiationDailyUsv(d) / 1000.0;
  }
  return round2(sum);
}

function buildAstronautDayMetrics(astronautId, day, store) {
  const d = clamp(day, 1, 30);
  const userCheckin = store.checkins[`${astronautId}:${d}`];
  const userPvt = store.pvt_tests[`${astronautId}:${d}`];

  // Build 1..d series for recovery debt, cognitive readiness, radiation
  const recSeries = [];
  const cogSeries = [];
  const radSeries = [];

  for (let i = 1; i <= d; i += 1) {
    let rec = 20;
    let cog = 90;
    if (astronautId === "ast-01") {
      // Steady Days 1-14 (~18-24), gradual decline Days 15-23 (Day 23 = 61), gentle recovery 24-30
      if (i <= 14) rec = 18 + (i % 5);
      else if (i <= 23) rec = 22 + Math.round(((i - 14) / 9) * 39);
      else rec = Math.max(32, 61 - (i - 23) * 4);
      cog = i <= 16 ? 92 - (i % 3) : i <= 23 ? 91 - ((i - 16) % 2) : 91;
      if (i === 23) {
        rec = 61;
        cog = 90;
      }
    } else if (astronautId === "ast-02") {
      // Recovery modest (~32-40); cognitive drops Days 17-23 (Day 23 = 21) + 9h gap Day 21-22
      rec = i <= 15 ? 24 + (i % 4) : i <= 23 ? 28 + Math.round(((i - 15) / 8) * 12) : 34;
      if (i <= 15) cog = 86 - (i % 4);
      else if (i <= 23) cog = Math.max(21, Math.round(84 - ((i - 15) / 8) * 63));
      else cog = Math.min(76, 21 + (i - 23) * 8);
      if (i === 23) {
        rec = 40;
        cog = 21;
      }
    } else if (astronautId === "ast-03") {
      // Yuki: CO2-linked mild symptoms Days 18-23
      rec = 22 + (i >= 18 && i <= 23 ? Math.round((labCo2ForDay(i) - 900) / 280) : i % 4);
      rec = clamp(rec, 18, 42);
      cog = 88 - (i >= 18 && i <= 22 ? 8 : 0);
      if (i === 23) {
        rec = 28;
        cog = 84;
      }
    } else {
      // Omar: CO2-linked symptoms Days 18-23
      rec = 24 + (i >= 18 && i <= 23 ? Math.round((labCo2ForDay(i) - 900) / 240) : i % 4);
      rec = clamp(rec, 20, 44);
      cog = 86 - (i >= 18 && i <= 22 ? 9 : 0);
      if (i === 23) {
        rec = 31;
        cog = 80;
      }
    }

    const gapOnDay = astronautId === "ast-02" && (i === 21 || i === 22);
    recSeries.push({ day: i, value: rec, gap: gapOnDay });
    cogSeries.push({ day: i, value: cog, gap: gapOnDay });
    radSeries.push({
      day: i,
      daily_usv: radiationDailyUsv(i),
      cumulative_msv: cumulativeRadiationMsv(i),
      value: cumulativeRadiationMsv(i),
    });
  }

  const latestRec = recSeries[recSeries.length - 1].value;
  const latestCog = cogSeries[cogSeries.length - 1].value;
  const latestRad = radSeries[radSeries.length - 1].cumulative_msv;
  const latestDailyUsv = radSeries[radSeries.length - 1].daily_usv;

  // Zone & CO2 context
  const profile = CREW_ROSTER.find((c) => c.astronaut_id === astronautId) || CREW_ROSTER[0];
  const zoneCo2 = zoneCo2ForDay(profile.default_zone, d);
  const envScore =
    profile.default_zone === "LAB"
      ? clamp(Math.round(95 - Math.max(0, zoneCo2 - 880) / 14), 25, 95)
      : 92;
  // Day 23 Elena environment score matches reference (45) due to LAB 7-day average 2,062 ppm
  const envEffective =
    astronautId === "ast-01" && d === 23
      ? 45
      : profile.default_zone === "LAB" && d >= 18 && d <= 23
      ? clamp(Math.round(95 - Math.max(0, (zoneCo2 + 1200) / 48)), 38, 88)
      : envScore;

  // Defaults per astronaut for Day d
  const labLinkedSymp = d >= 18 && d <= 23 ? (d === 19 ? 2 : 1) : 0;
  let hr = 58 + (d % 4);
  let rhr = 55.0;
  let hrv = 62.0;
  let hrRec1m = 34.5;
  let spo2 = 98;
  let sleep = 7.1;
  let sleepFrag = 14;
  let pvtRt = 251;
  let pvtLapses = 0;
  let headache = 0;
  let fatigue = 1;
  let energy = 4;
  let mood = 4;
  let stress = 2;
  let activityRatio = 1.0;

  if (astronautId === "ast-01") {
    const strain = d <= 14 ? 0 : d <= 23 ? (d - 14) / 9 : Math.max(0.2, 1 - (d - 23) * 0.15);
    hr = Math.round(57 + strain * 16);
    rhr = round1(54.9 + strain * 3.3);
    hrv = round1(62.0 - strain * 19.2);
    hrRec1m = round1(34.5 - strain * 13.3);
    spo2 = d === 23 ? 97 : 98;
    sleep = round1(7.0 - strain * 0.7);
    sleepFrag = Math.round(14 + strain * 10);
    pvtRt = d === 23 ? 263 : Math.round(251 - strain * 4);
    pvtLapses = 0;
    headache = 0;
    fatigue = strain > 0.6 ? 2 : 1;
    energy = strain > 0.5 ? 3 : 4;
    mood = strain > 0.5 ? 3 : 4;
    stress = strain > 0.6 ? 3 : 2;
    activityRatio = round2(1.0 - strain * 0.07);
  } else if (astronautId === "ast-02") {
    const cogStrain = d <= 15 ? 0 : d <= 23 ? (d - 15) / 8 : Math.max(0.2, 1 - (d - 23) * 0.12);
    hr = Math.round(62 + cogStrain * 6);
    rhr = round1(58.5 + cogStrain * 3.1);
    hrv = round1(56.0 - cogStrain * 11.4);
    hrRec1m = round1(31.0 - cogStrain * 5.2);
    spo2 = 98;
    sleep = round1(7.2 - cogStrain * 1.6);
    sleepFrag = Math.round(16 + cogStrain * 30);
    pvtRt = Math.round(251 + cogStrain * 74);
    pvtLapses = cogStrain > 0.7 ? 3 : cogStrain > 0.4 ? 1 : 0;
    headache = cogStrain > 0.6 ? 1 : 0;
    fatigue = cogStrain > 0.5 ? 2 : 1;
    // Marcus reports fine (underreporting mismatch F-29) unless user entered check-in
    energy = 4;
    mood = 4;
    stress = 2;
    activityRatio = round2(1.0 - cogStrain * 0.24);
  } else if (astronautId === "ast-03") {
    hr = 61 + (d >= 18 && d <= 23 ? 5 : 0);
    rhr = 56.2 + (d >= 18 && d <= 23 ? 2.1 : 0);
    hrv = 60.4 - (d >= 18 && d <= 23 ? 6.2 : 0);
    hrRec1m = 33.2;
    spo2 = 98;
    sleep = 7.0;
    pvtRt = 248 + (d >= 18 && d <= 23 ? 18 : 0);
    pvtLapses = d === 19 ? 1 : 0;
    headache = labLinkedSymp;
    fatigue = labLinkedSymp > 0 ? 2 : 1;
    energy = labLinkedSymp > 0 ? 3 : 4;
    mood = 4;
    stress = 2;
    activityRatio = 0.98;
  } else {
    hr = 64 + (d >= 18 && d <= 23 ? 6 : 0);
    rhr = 58.0 + (d >= 18 && d <= 23 ? 2.4 : 0);
    hrv = 55.2 - (d >= 18 && d <= 23 ? 7.1 : 0);
    hrRec1m = 32.0;
    spo2 = 97;
    sleep = 6.9;
    pvtRt = 255 + (d >= 18 && d <= 23 ? 21 : 0);
    pvtLapses = d === 19 ? 1 : 0;
    headache = labLinkedSymp;
    fatigue = labLinkedSymp > 0 ? 2 : 1;
    energy = labLinkedSymp > 0 ? 3 : 4;
    mood = 4;
    stress = 2;
    activityRatio = 0.96;
  }

  // Apply user-submitted check-in / PVT if logged for this astronaut & day
  if (userCheckin) {
    energy = userCheckin.energy;
    mood = userCheckin.mood;
    stress = userCheckin.stress;
    headache = userCheckin.headache;
    fatigue = userCheckin.fatigue ?? fatigue;
  }
  if (userPvt) {
    pvtRt = Math.round(userPvt.mean_rt_ms);
    pvtLapses = userPvt.lapses;
  }

  const sympScore =
    astronautId === "ast-01" && d === 23 && !userCheckin
      ? 84
      : clamp(
          Math.round(
            96 -
              headache * 12 -
              fatigue * 6 -
              Math.max(0, 3.5 - energy) * 6 -
              Math.max(0, stress - 2.5) * 5
          ),
          20,
          100
        );

  const recoveryComponent = 100 - latestRec;
  const rawReadiness =
    0.4 * latestCog + 0.3 * recoveryComponent + 0.2 * envEffective + 0.1 * sympScore;
  const readinessScore = Math.round(rawReadiness);

  // Active safety rules for this astronaut & day
  const activeSosForAstro = store.sos_events.filter(
    (s) =>
      s.astronaut_id === astronautId &&
      s.day <= d &&
      !["cancelled", "resolved_ok"].includes(s.status)
  );
  const safetyRules = [];
  if (spo2 < 90) {
    safetyRules.push({
      rule_id: "SR-01",
      title: "SR-01 · Critical SpO2 (< 90%)",
      severity: "critical",
      astronaut_id: astronautId,
      deterministic: true,
    });
  }
  if (zoneCo2 >= 5000 && profile.default_zone === "LAB") {
    safetyRules.push({
      rule_id: "SR-03",
      title: "SR-03 · US Lab CO2 >= 5,000 ppm",
      severity: "critical",
      astronaut_id: astronautId,
      deterministic: true,
    });
  }
  if (userCheckin?.safety_concern) {
    safetyRules.push({
      rule_id: "SR-04",
      title: "SR-04 · Acute behavioral safety support",
      severity: "critical",
      astronaut_id: astronautId,
      deterministic: true,
    });
  }
  activeSosForAstro.forEach((s) => {
    const labelMap = {
      medical: "Medical",
      behavioral: "Behavioral support",
      environment: "Habitat hazard",
    };
    safetyRules.push({
      rule_id: "SR-05",
      title: `SR-05 · SOS — ${labelMap[s.type] || "Medical"}`,
      severity: "critical",
      astronaut_id: astronautId,
      sos_id: s.sos_id,
      deterministic: true,
    });
  });

  const safetyActive = safetyRules.length > 0;
  let band = "Steady";
  if (safetyActive) band = "Safety review";
  else if (readinessScore < 60) band = "Reduced";
  else if (readinessScore < 80) band = "Monitor";

  // Quality gaps (never silently imputed)
  const gaps = [];
  if (astronautId === "ast-02" && d >= 22) {
    gaps.push({
      id: "gap-mc-off",
      label: "Wristband off for 9h",
      window: "Day 21 22:00 -> Day 22 07:00",
      quality: "sensor_off",
    });
  }
  if (d >= 18) {
    gaps.push({
      id: "gap-lab-co2",
      label: "US Lab CO₂ missing 2h",
      window: "Day 18, 14:00–16:00",
      quality: "missing",
    });
  }
  if (d >= 12 && astronautId === "ast-02") {
    gaps.push({
      id: "gap-mc-noise",
      label: "1 reading flagged as motion noise",
      window: "Day 12, 16:00–17:00",
      quality: "suspect",
    });
  } else if (d >= 20 && astronautId === "ast-01") {
    gaps.push({
      id: "gap-el-oor",
      label: "1 reading out of range",
      window: "Day 20, 11:00",
      quality: "out_of_range",
    });
  }

  const coveragePct =
    astronautId === "ast-02" && d >= 22 ? 94 : gaps.length > 0 ? 99 : 100;
  const recConf = astronautId === "ast-02" && d >= 22 ? 0.79 : 0.95;
  const cogConf = astronautId === "ast-02" && d >= 22 ? 0.86 : 0.88;
  const overallConf = Math.round((0.48 * recConf + 0.42 * cogConf + 0.1 * (coveragePct / 100)) * 100);

  const sleepQuality =
    astronautId === "ast-02" && d === 22
      ? "sensor_off"
      : "ok";

  const latestReadings = {
    heart_rate: {
      label: "HR",
      value: hr,
      unit: "bpm",
      baseline: astronautId === "ast-01" ? 57.0 : 61.5,
      quality: "ok",
      subtitle: `baseline ${astronautId === "ast-01" ? "57.0" : "61.5"}`,
    },
    hrv_rmssd: {
      label: "HRV",
      value: hrv,
      unit: "ms",
      baseline: astronautId === "ast-01" ? 62.0 : 56.0,
      quality: "ok",
      subtitle: `baseline ${astronautId === "ast-01" ? "62.0" : "56.0"}`,
    },
    spo2: {
      label: "SpO₂",
      value: spo2,
      unit: "%",
      baseline: 98,
      quality: "ok",
      subtitle: `Day ${d} · 16:00 ship time`,
    },
    sleep_duration: {
      label: "Sleep",
      value: sleepQuality === "sensor_off" ? null : sleep,
      unit: "h",
      baseline: 7.0,
      quality: sleepQuality,
      subtitle: sleepQuality === "sensor_off" ? "Wristband off 9h (gap)" : "baseline 7.0",
    },
    pvt_mean_rt: {
      label: "Reaction time",
      value: pvtRt,
      unit: "ms",
      baseline: 251.1,
      quality: "ok",
      subtitle: "baseline 251.1",
    },
    symptom_headache: {
      label: "Headache",
      value: headache,
      unit: "0-3",
      baseline: 0,
      quality: "ok",
      subtitle: userCheckin ? `Day ${d} · check-in logged` : `Day ${Math.max(1, d - 1)} · 19:00 ship time`,
    },
  };

  // Behavioral layer + F-29 underreporting check
  const passiveDrift =
    (astronautId === "ast-02" && d >= 18 && d <= 25) ||
    (astronautId === "ast-01" && d >= 19 && d <= 24);
  const activeLooksFine = mood >= 3.5 && energy >= 3.5 && stress <= 2.5;
  const underreportingMismatch = Boolean(
    astronautId === "ast-02" && passiveDrift && activeLooksFine
  );
  const behavioralStatus = userCheckin?.safety_concern
    ? "Support needed"
    : underreportingMismatch
    ? "Watch"
    : astronautId === "ast-02" && d >= 19 && d <= 24
    ? "Check-in suggested"
    : "Steady";

  const behavioral = {
    astronaut_id: astronautId,
    up_to_day: d,
    status: behavioralStatus,
    confidence: 0.86,
    summary: underreportingMismatch
      ? "Passive telemetry and self-report layers show a gentle mismatch; private reflection suggested."
      : behavioralStatus === "Support needed"
      ? "Deterministic behavioral safety support triggered. Crew Health Officer and SOS remain accessible."
      : "Passive and self-report layers are consistent. No punitive score is computed.",
    passive_layer: {
      status: passiveDrift ? "drift" : "steady",
      activity_ratio: activityRatio,
      sleep_fragmentation: sleepFrag,
    },
    active_layer: {
      mood_score: mood,
      energy_score: energy,
      stress_score: stress,
      headache_score: headache,
      manual_logged: Boolean(userCheckin),
    },
    climate_layer: {
      score: 3.55,
      scale: 5.0,
      anonymized: true,
    },
    underreporting_mismatch: underreportingMismatch,
    mismatch_prompt: underreportingMismatch
      ? "Your recent wearable sleep and activity patterns look heavier than your baseline, even though your check-ins look steady. There is no judgment or score here — would you like a private check-in with AstroGuard or a quiet recovery block?"
      : "",
    safety_triggered: Boolean(userCheckin?.safety_concern),
    redacted: false,
  };

  const readiness = {
    astronaut_id: astronautId,
    up_to_day: d,
    readiness_score: readinessScore,
    band,
    safety_active: safetyActive,
    active_safety_rules: safetyRules,
    confidence: round2(overallConf / 100),
    components: {
      cognitive: latestCog,
      recovery: recoveryComponent,
      environment: envEffective,
      symptoms: sympScore,
      weights: { cognitive: 0.4, recovery: 0.3, environment: 0.2, symptoms: 0.1 },
    },
    recovery_debt: {
      score: latestRec,
      direction: "lower_is_better",
      status: latestRec >= 50 ? "caution" : latestRec >= 35 ? "watch" : "normal",
      confidence: recConf,
      personal_range: [10, 34],
      series: recSeries,
      protocol_refs: ["PROT-REC-01", "PROT-REC-02"],
      summary:
        latestRec > 34
          ? "Lower is better. Compared with your own HR recovery and sleep baseline."
          : "Recovery debt is within your personal early-mission range (10–34).",
      why_details:
        astronautId === "ast-01" && d >= 18
          ? `1-minute HR recovery dropped to ${hrRec1m} bpm (personal baseline 34.5 bpm), resting HR is +${round1(
              rhr - 54.9
            )} bpm (${rhr} vs 54.9 bpm), and sleep averaged ${sleep} h vs 7.0 h.`
          : `1-minute HR recovery (${hrRec1m} bpm) and resting HR (${rhr} bpm) track near your personal baseline.`,
    },
    cognitive_readiness: {
      score: latestCog,
      direction: "higher_is_better",
      status: latestCog < 45 ? "critical" : latestCog < 70 ? "watch" : "normal",
      confidence: cogConf,
      personal_range: [75, 95],
      series: cogSeries,
      protocol_refs: ["PROT-SLP-01", "PROT-SLP-02"],
      summary:
        latestCog < 75
          ? `Cognitive readiness is reduced: reaction time is ${Math.max(
              0,
              pvtRt - 251
            )} ms slower than your personal baseline, with ${pvtLapses.toFixed(1)} lapses and ${sleepFrag} pts sleep fragmentation.`
          : "Higher is better. PVT plus sleep fragmentation, not a generic IQ-style score.",
      why_details: `Mean PVT reaction time is ${pvtRt} ms (personal baseline 251 ms) with ${pvtLapses} lapse(s).`,
    },
    radiation_trend: {
      cumulative_msv: latestRad,
      daily_usv: latestDailyUsv,
      series: radSeries,
      confidence: 0.9,
      status: latestRad >= 12.0 ? "watch" : "normal",
      protocol_refs: ["PROT-RAD-01"],
      summary:
        "Cumulative habitat dose. Long-term operational trend, not an acute medical measure.",
      why_details: `Habitat dosimeters logged ~${latestDailyUsv} uSv/day over ${d} mission days without sensor dropout.`,
    },
    latest_readings: latestReadings,
    data_quality: {
      coverage: coveragePct / 100,
      coverage_pct: coveragePct,
      gap_count: gaps.length,
      gaps,
      summary:
        gaps.length > 0
          ? `${gaps.map((g) => g.label).join(" · ")}. Confidence is adjusted rather than filling gaps.`
          : "All wearable and cabin telemetry channels clean in this window.",
    },
    flags: [],
  };

  // Briefing copy
  let headline = "Baselines steady across body, cognition, and cabin.";
  let whatChanged = `All primary physiological and cognitive readings are within your personal early-mission ranges on Day ${d}.`;
  let howSureWhy = `Confidence is high (${overallConf}%) with consistent wearable and PVT coverage.`;
  let nextStep = "Maintain your normal sleep schedule and standard ship-clock check-ins.";
  let nextProtocols = ["PROT-SLP-01"];

  if (safetyActive) {
    headline = "Safety first, then the health signal.";
    whatChanged =
      astronautId === "ast-01" && activeSosForAstro.length > 0
        ? `Your SOS is queued for Earth and acknowledged on-board; separately, recovery debt is elevated: your 1-minute heart-rate recovery is ${round1(
            34.5 - hrRec1m
          )} bpm below your personal reference, resting heart rate is +${round1(
            rhr - 54.9
          )} bpm, and sleep debt is ${round1(Math.max(0, 7.0 - sleep))} h.`
        : `Deterministic safety rule ${safetyRules[0].rule_id} is active on Day ${d}. Follow the immediate safety checklist first.`;
    howSureWhy = `Confidence is high (${overallConf}%) because post-exercise and resting heart-rate signals agree.`;
    nextStep =
      "Take a 24-hour recovery block and repeat the heart-rate recovery reading after your next session.";
    nextProtocols = ["PROT-REC-01", "PROT-REC-02"];
  } else if (astronautId === "ast-02" && latestCog < 70) {
    headline = "Protect a full sleep window before precision work.";
    whatChanged = `Cognitive readiness is reduced (${latestCog}/100): PVT reaction time is +${
      pvtRt - 251
    } ms slower than baseline with ${pvtLapses} lapses and elevated sleep fragmentation.`;
    howSureWhy = `Confidence is ${Math.round(
      cogConf * 100
    )}% because sleep fragmentation and PVT agree, adjusted for the 9h wristband-off gap.`;
    nextStep =
      "Protect a 7.5-hour sleep window tonight and repeat the PVT at the same ship-clock time tomorrow.";
    nextProtocols = ["PROT-SLP-01", "PROT-SLP-02"];
  } else if (latestRec > 34) {
    headline = "Ease training load to clear rising recovery debt.";
    whatChanged = `Recovery debt rose to ${latestRec}/100 as 1-minute HR recovery softened to ${hrRec1m} bpm (baseline 34.5 bpm).`;
    howSureWhy = `Confidence is ${overallConf}% across resting HR, HRV, and post-exercise readings.`;
    nextStep =
      "Swap intense resistance work for a 24-hour recovery block and re-check 1-min HR recovery.";
    nextProtocols = ["PROT-REC-01", "PROT-REC-02"];
  } else if ((astronautId === "ast-03" || astronautId === "ast-04") && d >= 18 && d <= 23) {
    headline = "Monitor symptoms alongside US Lab air quality.";
    whatChanged = `Mild headache/fatigue scores co-move with recent US Lab CO₂ peaks (${zoneCo2} ppm today; 7d elevated).`;
    howSureWhy = `Confidence is ${overallConf}% across crew symptom logs and zone CO₂ sensors.`;
    nextStep =
      "Rotate extended desk work out of US Lab while cabin scrubber verification continues.";
    nextProtocols = ["PROT-ENV-01", "PROT-ENV-02"];
  }

  const briefing = {
    headline,
    what_changed: whatChanged,
    how_sure_why: howSureWhy,
    single_best_next_step: nextStep,
    protocol_refs: nextProtocols,
    confidence_pct: overallConf,
  };

  // Explainable alerts (used in HealthOfficerView & Advisor)
  const alerts = [];
  if (latestRec > 34) {
    alerts.push({
      alert_id: `al-rec-${astronautId}-${d}`,
      severity: "caution",
      scope: "physio",
      title: "Recovery debt above personal baseline",
      summary: `1-min HR recovery is ${hrRec1m} bpm (baseline 34.5) with resting HR ${rhr} bpm and HRV ${hrv} ms.`,
      protocol_refs: ["PROT-REC-01", "PROT-REC-02"],
    });
  }
  if (latestCog < 70) {
    alerts.push({
      alert_id: `al-cog-${astronautId}-${d}`,
      severity: "caution",
      scope: "cognitive",
      title: "Cognitive readiness below personal baseline",
      summary: `Cognitive readiness is reduced: reaction time is ${
        pvtRt - 251
      } ms slower than your personal baseline, with ${pvtLapses.toFixed(
        1
      )} lapses and ${sleepFrag - 16} points more sleep fragmentation.`,
      protocol_refs: ["PROT-SLP-01", "PROT-SLP-02"],
    });
  }
  if (underreportingMismatch) {
    alerts.push({
      alert_id: `al-beh-${astronautId}-${d}`,
      severity: "info",
      scope: "behaviour",
      title: "Self-report and passive signals disagree",
      summary:
        "Passive sleep/activity drift co-occurs with steady self-report scores. Gentle private check-in suggested.",
      protocol_refs: ["PROT-SLP-01"],
    });
  }
  if ((astronautId === "ast-03" || astronautId === "ast-04") && d >= 18 && d <= 23) {
    alerts.push({
      alert_id: `al-env-${astronautId}-${d}`,
      severity: "watch",
      scope: "habitat",
      title: "Symptoms co-moving with US Lab CO₂",
      summary:
        "Symptom pattern tracks US Lab CO₂ with 0-day lag. Verify cabin air before assuming individual illness.",
      protocol_refs: ["PROT-ENV-01", "PROT-ENV-02"],
    });
  }

  // MSIDE findings ("What AstroGuard is watching")
  const msideFindings = [];
  if (d >= 18) {
    msideFindings.push({
      finding_id: "mside-shared-LAB",
      scope: "cross_crew",
      title: "Shared habitat exposure across crew",
      confidence: 0.9,
      summary:
        "2 crew members show symptom scores co-moving with US Lab CO₂ (lag 0–1 day). Treat this as a shared environmental exposure until the air is verified; individual illness is not excluded.",
      tags: ["environment", "symptoms"],
      protocol_refs: ["PROT-ENV-01", "PROT-ENV-02", "PROT-MED-01"],
    });
  }
  msideFindings.push({
    finding_id: `mside-${astronautId}-hrv-sleep`,
    scope: "personal",
    title: "Lower HRV follows fragmented sleep",
    confidence: 0.86,
    summary:
      "HRV and sleep fragmentation co-vary in the expected direction. Recovery confidence depends on clean overnight data.",
    tags: ["physiology", "sleep"],
    protocol_refs: ["PROT-SLP-01", "PROT-REC-01"],
  });

  // Advisor contributing observations (4 cards)
  const observations = [
    {
      id: "obs-hrr",
      title: "1-min heart-rate recovery",
      window: `Day ${Math.max(1, d - 7)} 16:00 -> Day ${d} 16:00 · reference Days 1–9 personal reference`,
      quality: "ok",
      value: hrRec1m,
      unit: "bpm",
      baseline: "34.5",
      note: "Higher is better. A fall below your own early-mission reference is the signal.",
      confidence: 95,
      protocol_refs: ["PROT-REC-01", "PROT-REC-02"],
    },
    {
      id: "obs-rhr",
      title: "Resting heart rate",
      window: `Day ${Math.max(1, d - 7)} 16:00 -> Day ${d} 16:00 · reference Days 1–9 personal rest baseline`,
      quality: "ok",
      value: rhr,
      unit: "bpm",
      baseline: "54.9",
      note: "Elevated relative to your early-mission sleep rest window.",
      confidence: 89,
      protocol_refs: ["PROT-REC-02"],
    },
    {
      id: "obs-pvt-rt",
      title: "PVT mean reaction time",
      window: `Day ${Math.max(1, d - 4)} 16:00 -> Day ${d} 16:00 · reference Days 1–10 personal reference`,
      quality: "ok",
      value: astronautId === "ast-01" && !userPvt && d === 23 ? 244 : pvtRt,
      unit: "ms",
      baseline: "251",
      note: "Higher is slower. Raw means are sensitive to device and time of day.",
      confidence: Math.round(cogConf * 100) - 5,
      protocol_refs: ["PROT-SLP-02"],
    },
    {
      id: "obs-pvt-lapses",
      title: "PVT lapses",
      window: `Day ${Math.max(1, d - 4)} 16:00 -> Day ${d} 16:00`,
      quality: "ok",
      value: pvtLapses,
      unit: "count",
      baseline: "0",
      note: "Responses >= 500 ms during 1-minute psychomotor vigilance test.",
      confidence: Math.round(cogConf * 100) - 5,
      protocol_refs: ["PROT-SLP-01", "PROT-SLP-02"],
    },
  ];

  return {
    profile,
    readiness,
    briefing,
    behavioral,
    alerts,
    msideFindings,
    observations,
    userCheckin: userCheckin || null,
    userPvt: userPvt || null,
    withheldScopes: [],
  };
}

function buildEnvironmentSummary(day) {
  const d = clamp(day, 1, 30);
  const zones = {};
  const occupancy = {
    N1: 0,
    LAB: 3,
    CQ: 1,
    AL: 0,
  };

  HABITAT_ZONES.forEach((z) => {
    const series = [];
    for (let i = Math.max(1, d - 6); i <= d; i += 1) {
      series.push(zoneCo2ForDay(z.zone_id, i));
    }
    const current = series[series.length - 1];
    const avg7d = Math.round(series.reduce((a, b) => a + b, 0) / series.length);
    const pctVsNominal = Math.round(((current - z.nominal_co2_ppm) / z.nominal_co2_ppm) * 100);
    const trendPct =
      z.zone_id === "LAB"
        ? d === 23
          ? 100
          : clamp(Math.round(((avg7d - 880) / 880) * 100), 5, 140)
        : z.zone_id === "N1" && d === 23
        ? 41
        : z.zone_id === "CQ" && d === 23
        ? 14
        : Math.max(4, Math.abs(pctVsNominal));

    zones[z.zone_id] = {
      zone_id: z.zone_id,
      name: z.name,
      short_code: z.short_code,
      crew_present: occupancy[z.zone_id],
      present_crew_count: occupancy[z.zone_id],
      co2_ppm: current,
      avg_7d_ppm: avg7d,
      co2_7d_avg_ppm: avg7d,
      trend_pct: trendPct,
      trend_7d_pct: trendPct,
      status: current >= 5000 ? "Critical" : current > 1050 ? "Above normal" : "Within normal band",
      sensor_status: "clean",
    };
  });

  const startDay = Math.max(1, d - 13);
  const aggregateCo2Series = [];
  const aggregateSymptomSeries = [];
  for (let i = startDay; i <= d; i += 1) {
    const lab = labCo2ForDay(i);
    const aggCo2 = Math.round(lab * 0.72 + 810 * 0.28);
    const sym =
      i < 16
        ? 0.4
        : i <= 23
        ? round2(clamp((lab - 850) / 900, 0.4, 4.1))
        : 0.7;
    aggregateCo2Series.push({ day: i, value: aggCo2, gap: i === 18 });
    aggregateSymptomSeries.push({ day: i, value: sym });
  }

  const sharedActive = d >= 18;
  const crewCorrelations = [
    {
      crew_label: "Crew A",
      zone_id: "LAB",
      r: d >= 18 ? 0.66 : 0.21,
      lag_days: 1,
      p_value: 0.19,
      fdr_q_value: 0.24,
      confidence: 0.77,
      linked: false,
      status: "no clear link",
      summary: `Daily CO2 exposure and symptom score move together (r=${d >= 18 ? "+0.66" : "+0.21"}, 1-day lag).`,
    },
    {
      crew_label: "Crew B",
      zone_id: "CQ",
      r: d >= 18 ? 0.58 : 0.18,
      lag_days: 1,
      p_value: 0.27,
      fdr_q_value: 0.27,
      confidence: 0.75,
      linked: false,
      status: "no clear link",
      summary: `Daily CO2 exposure and symptom score move together (r=${d >= 18 ? "+0.58" : "+0.18"}, 1-day lag).`,
    },
    {
      crew_label: "Crew C",
      zone_id: "LAB",
      r: d >= 18 ? 0.96 : 0.25,
      lag_days: 0,
      p_value: d >= 18 ? 0.002 : 0.41,
      fdr_q_value: d >= 18 ? 0.004 : 0.45,
      confidence: d >= 18 ? 0.91 : 0.64,
      linked: sharedActive,
      status: sharedActive ? "linked" : "no clear link",
      summary: `Daily CO2 exposure and symptom score move together (r=${d >= 18 ? "+0.96" : "+0.25"}, same day).`,
    },
    {
      crew_label: "Crew D",
      zone_id: "LAB",
      r: d >= 18 ? 0.95 : 0.24,
      lag_days: 0,
      p_value: d >= 18 ? 0.003 : 0.44,
      fdr_q_value: d >= 18 ? 0.005 : 0.45,
      confidence: d >= 18 ? 0.9 : 0.63,
      linked: sharedActive,
      status: sharedActive ? "linked" : "no clear link",
      summary: `Daily CO2 exposure and symptom score move together (r=${d >= 18 ? "+0.95" : "+0.24"}, same day).`,
    },
  ];

  return {
    up_to_day: d,
    zones,
    crew_correlations: crewCorrelations,
    shared_exposure_alert: sharedActive
      ? {
          active: true,
          zone_id: "LAB",
          zone_name: "US Lab",
          affected_crew_count: 2,
          affected_anonymous_labels: ["Crew C", "Crew D"],
          lag_range: "0-1 day",
          confidence: 0.9,
          headline: "Shared habitat exposure signal",
          summary:
            "2 crew members show symptom scores co-moving with US Lab CO₂ (lag 0–1 day). Treat this as a shared environmental exposure until the air is verified; individual illness is not excluded.",
          prevent_misattribution:
            "Do not label a crew member as sick when the same symptom pattern follows a shared zone exposure. Individual illness is not excluded.",
          protocol_refs: ["PROT-ENV-01", "PROT-ENV-02", "PROT-MED-01"],
        }
      : {
          active: false,
          zone_id: null,
          zone_name: null,
          affected_crew_count: 0,
          affected_anonymous_labels: [],
          lag_range: "0-1 day",
          confidence: 0.0,
          headline: "No shared habitat exposure cluster detected",
          summary: "All cabin zones remain within nominal CO₂ band with no multi-crew symptom linkage.",
          prevent_misattribution: "Environmental and personal baselines are monitored independently.",
          protocol_refs: [],
        },
    aggregate_co2_series: aggregateCo2Series,
    aggregate_symptom_series: aggregateSymptomSeries,
    radiation_daily_usv: radiationDailyUsv(d),
    radiation_usv_day: radiationDailyUsv(d),
    radiation_cumulative_msv: cumulativeRadiationMsv(d),
    environmental_gaps:
      d >= 18
        ? [
            {
              zone_id: "LAB",
              zone_name: "US Lab",
              day: 18,
              window: "Day 18, 14:00–16:00 · 2h",
              message:
                "US Lab · Day 18, 14:00–16:00 · 2h - US Lab CO2 sensor packet loss (2 h).",
              detail: "US Lab CO₂ sensor packet loss (2 h). Correlation confidence is lowered; the missing values are not imputed.",
            },
          ]
        : [],
    method_guardrails: {
      method:
        "Hourly location joined to zone CO₂; daily means correlated with symptom score (Pearson, lag 0–1 day). Association, not causation.",
      disclaimer:
        "Shared exposure is a hypothesis to verify with cabin-air measurements. It does not rule out individual illness.",
      daily_points: aggregateCo2Series.length,
    },
    sr03_note:
      d >= 19
        ? "Hard rule SR-03 fires at 5,000 ppm and bypasses the alert budget. The 5,000+ ppm exceedance appeared on Day 19 in US Lab; the scrubber was serviced on Day 22."
        : "Hard rule SR-03 fires deterministically at 5,000 ppm and bypasses the alert budget.",
  };
}

function applyConsentRedaction(astroMetrics, consentProfile, role) {
  if (role === "Astronaut") {
    return astroMetrics;
  }
  if (role !== "Crew Health Officer") {
    return null;
  }

  const safetyActive = astroMetrics.readiness.safety_active;
  const checkScope = (scope) => {
    if (consentProfile.normal[scope]) return { allowed: true, via: "normal" };
    if (safetyActive && consentProfile.emergency[scope]) {
      return { allowed: true, via: "emergency_override" };
    }
    return { allowed: false, via: "withheld" };
  };

  const cloned = JSON.parse(JSON.stringify(astroMetrics));
  const withheld = [];

  const physio = checkScope("physio");
  const cognitive = checkScope("cognitive");
  const behaviour = checkScope("behaviour");
  const habitat = checkScope("habitat");

  if (!physio.allowed) {
    withheld.push("physio");
    cloned.readiness.recovery_debt.redacted = true;
    cloned.readiness.latest_readings.heart_rate.value = null;
    cloned.readiness.latest_readings.hrv_rmssd.value = null;
    cloned.readiness.latest_readings.spo2.value = null;
    cloned.readiness.latest_readings.sleep_duration.value = null;
  }
  if (!cognitive.allowed) {
    withheld.push("cognitive");
    cloned.readiness.cognitive_readiness.redacted = true;
    cloned.readiness.latest_readings.pvt_mean_rt.value = null;
  }
  if (!behaviour.allowed) {
    withheld.push("behaviour");
    cloned.behavioral = {
      ...cloned.behavioral,
      redacted: true,
      summary:
        "Behavioural signals are withheld by this astronaut's consent. The Health Officer sees only that a scope is withheld, not the values.",
      passive_layer: null,
      active_layer: null,
      mismatch_prompt: "",
    };
  }
  if (!habitat.allowed) {
    withheld.push("habitat");
  }

  cloned.alerts = cloned.alerts.map((al) => {
    if (withheld.includes(al.scope)) {
      return {
        ...al,
        redacted: true,
        summary: "Details withheld by the astronaut's consent settings.",
      };
    }
    return al;
  });

  cloned.withheldScopes = withheld;
  return cloned;
}

export function getFallbackState({
  day = 23,
  role = "Astronaut",
  crewId = "ast-01",
} = {}) {
  const d = clamp(Number(day) || 23, 1, 30);
  const validRole = ROLES.includes(role) ? role : "Astronaut";
  const validCrewId = CREW_ROSTER.some((c) => c.astronaut_id === crewId)
    ? crewId
    : "ast-01";
  const store = loadStore();

  const earthDelayMin = round1(10.8 + (d / 30) * 2.6);
  const allAstroMetrics = {};
  CREW_ROSTER.forEach((c) => {
    allAstroMetrics[c.astronaut_id] = buildAstronautDayMetrics(c.astronaut_id, d, store);
  });

  const env = buildEnvironmentSummary(d);
  const activeSos = store.sos_events.filter(
    (s) => s.day <= d && !["cancelled", "resolved_ok"].includes(s.status)
  );

  // Collect global deterministic safety rules across crew & habitat
  const globalSafetyRules = [];
  CREW_ROSTER.forEach((c) => {
    allAstroMetrics[c.astronaut_id].readiness.active_safety_rules.forEach((r) => {
      const isDuplicateHabitatRule =
        r.rule_id === "SR-03" &&
        globalSafetyRules.some((x) => x.rule_id === "SR-03");
      const isDuplicatePersonalRule = globalSafetyRules.some(
        (x) => x.rule_id === r.rule_id && x.astronaut_id === r.astronaut_id
      );
      if (!isDuplicateHabitatRule && !isDuplicatePersonalRule) {
        globalSafetyRules.push(r);
      }
    });
  });

  // Crew overview for HealthOfficerView & GroundSupportView
  const zoneNameMap = { N1: "Node 1", LAB: "US Lab", CQ: "Crew Quarters", AL: "Airlock" };
  const bandCounts = { safety_review: 0, reduced: 0, monitor: 0, steady: 0 };
  const readinessByCrew = {};
  const behavioralByCrew = {};

  const crewOverview = CREW_ROSTER.map((c) => {
    const rawM = allAstroMetrics[c.astronaut_id];
    const consent = store.consent_profiles[c.astronaut_id];
    const m =
      validRole === "Crew Health Officer"
        ? applyConsentRedaction(rawM, consent, "Crew Health Officer")
        : rawM;

    const band = rawM.readiness.band;
    if (band === "Safety review") bandCounts.safety_review += 1;
    else if (band === "Reduced") bandCounts.reduced += 1;
    else if (band === "Monitor") bandCounts.monitor += 1;
    else bandCounts.steady += 1;

    const scopesWithheld = ["physio", "cognitive", "behaviour", "habitat"].filter(
      (s) => !consent.normal[s] && !(rawM.readiness.safety_active && consent.emergency[s])
    ).length;

    const isCognitiveScoped = !consent.normal.cognitive && !rawM.readiness.safety_active;
    const displayBand = isCognitiveScoped ? "Scoped" : band;
    const displayScore = isCognitiveScoped ? null : rawM.readiness.readiness_score;

    readinessByCrew[c.astronaut_id] = m.readiness;
    behavioralByCrew[c.astronaut_id] = m.behavioral;

    return {
      astronaut_id: c.astronaut_id,
      name: c.name,
      short_name: c.short_name,
      initials: c.initials,
      title: c.title,
      age: c.age,
      default_zone: c.default_zone,
      zone: zoneNameMap[c.default_zone] || c.default_zone,
      readiness: displayScore,
      readiness_score: displayScore,
      band: displayBand,
      status: displayBand,
      safety_active: rawM.readiness.safety_active,
      safetyCount: rawM.readiness.active_safety_rules.length,
      safety_count: rawM.readiness.active_safety_rules.length,
      alertCount: m.alerts.length,
      alert_count: m.alerts.length,
      summary: m.briefing.what_changed,
      briefing: [
        m.briefing.what_changed,
        m.briefing.how_sure_why,
        `Next: ${m.briefing.single_best_next_step}`,
      ],
      protocols: m.briefing.protocol_refs,
      recovery: {
        score: m.readiness.recovery_debt.score,
        status: m.readiness.recovery_debt.status,
        confidence: Math.round(m.readiness.recovery_debt.confidence * 100),
        summary: m.readiness.recovery_debt.summary,
        observations: [
          {
            label: "1-min heart-rate recovery",
            observed: `${m.observations[0]?.value} bpm`,
            baseline: "34.5 bpm",
            delta: `${round1((m.observations[0]?.value ?? 34.5) - 34.5)} bpm`,
            window: `Day ${d}`,
          },
          {
            label: "Resting heart rate",
            observed: `${m.observations[1]?.value ?? "—"} bpm`,
            baseline: "54.9 bpm",
            delta: `${round1((m.observations[1]?.value ?? 54.9) - 54.9)} bpm`,
            window: `Day ${d}`,
          },
        ],
      },
      cognitive: {
        score: m.readiness.cognitive_readiness.score,
        status: m.readiness.cognitive_readiness.status,
        confidence: Math.round(m.readiness.cognitive_readiness.confidence * 100),
        summary: m.readiness.cognitive_readiness.summary,
        observations: [
          {
            label: "PVT mean reaction time",
            observed: `${m.observations[2]?.value ?? "—"} ms`,
            baseline: "251 ms",
            delta: `${Math.round((m.observations[2]?.value ?? 251) - 251)} ms`,
            window: `Day ${d}`,
          },
          {
            label: "PVT lapses",
            observed: `${m.observations[3]?.value ?? 0} count`,
            baseline: "0.0 count",
            delta: `+${m.observations[3]?.value ?? 0}`,
            window: `Day ${d}`,
          },
        ],
      },
      behavioural: m.behavioral,
      gaps: m.readiness.data_quality.gaps,
      alerts: m.alerts,
      scopes: { ...consent.normal },
      emergency_scopes: { ...consent.emergency },
      consent,
      coveragePct: m.readiness.data_quality.coverage_pct,
      data_coverage_pct: m.readiness.data_quality.coverage_pct,
      shared_cluster: c.astronaut_id === "ast-03" || c.astronaut_id === "ast-04",
      clusterTag:
        c.astronaut_id === "ast-03" || c.astronaut_id === "ast-04"
          ? "Habitat cluster"
          : "No shared cluster",
      withheld_count: scopesWithheld,
    };
  });

  const selectedRaw = allAstroMetrics[validCrewId];
  const selectedConsent = store.consent_profiles[validCrewId];
  const scopedAstronaut = applyConsentRedaction(selectedRaw, selectedConsent, validRole);

  // Messages visible to role
  const visibleMessages = store.messages
    .filter((m) => {
      if (m.day > d) return false;
      if (validRole === "Ground Support") return m.channel === "earth";
      if (validRole === "Systems Engineer") {
        return (
          m.from_id === "systems" ||
          m.to_id === "systems" ||
          m.to_id === "all" ||
          m.channel === "earth"
        );
      }
      return true;
    })
    .map((m) => ({
      ...m,
      from: m.from_label,
      to: m.to_label,
      attachment_label: m.attachment?.label || "",
    }))
    .sort((a, b) => b.day - a.day);

  const visibleSos = store.sos_events
    .filter((s) => s.day <= d)
    .map((s) => {
      const typeLabelMap = {
        medical: "Medical",
        behavioral: "Behavioral support",
        environment: "Habitat hazard",
      };
      const baseSos = {
        ...s,
        crew_name: s.astronaut_name,
        sos_type: typeLabelMap[s.type] || s.type || "Medical",
        time_label: s.short_date || s.timestamp_label,
        acknowledged_onboard: Boolean(s.onboard_acknowledged),
      };
      if (validRole === "Ground Support" || validRole === "Systems Engineer") {
        return {
          ...baseSos,
          astronaut_name: "Crew member (anonymised)",
          crew_name: "Crew member (anonymised)",
          astronaut_id: "anonymised",
          vitals_snapshot: undefined,
        };
      }
      return baseSos;
    });

  const queueItems = store.sync_queue.filter((q) => (q.day || 1) <= d);
  const queuedCount = queueItems.filter((q) => q.status !== "acknowledged").length;
  const scopedSafetyRules = globalSafetyRules.map((r) =>
    validRole === "Ground Support" || validRole === "Systems Engineer"
      ? {
          ...r,
          astronaut_id: "anonymised",
          title: r.rule_id === "SR-05" ? "1 active safety event" : r.title,
        }
      : r
  );

  return {
    mode: "offline-fallback",
    day: d,
    hour: 16,
    online: Boolean(store.earth_link_online),
    earth_link_online: Boolean(store.earth_link_online),
    ship_time_label: `Day ${d} · 16:00 ship time`,
    met_hours: d * 24 - 14,
    earth_delay_min: earthDelayMin,
    earth_link: {
      online: Boolean(store.earth_link_online),
      delay_minutes: earthDelayMin,
      bandwidth_kbps: 2.4,
    },
    viewer_role: validRole,
    selected_crew_id: validCrewId,
    crew_roster: CREW_ROSTER,
    protocols: PROTOCOL_LIBRARY,
    active_safety_rules: scopedSafetyRules,
    safety: {
      active_rules: scopedSafetyRules,
      has_critical: globalSafetyRules.length > 0,
      sos_active_count: activeSos.length,
      timeline: visibleSos,
    },
    astronaut: scopedAstronaut,
    crew:
      validRole === "Crew Health Officer" || validRole === "Astronaut"
        ? crewOverview
        : null,
    crew_summaries:
      validRole === "Crew Health Officer" || validRole === "Astronaut"
        ? crewOverview
        : null,
    crew_overview:
      validRole === "Crew Health Officer" || validRole === "Astronaut"
        ? crewOverview
        : null,
    readiness_by_crew:
      validRole === "Crew Health Officer" ? readinessByCrew : null,
    behavioral_by_crew:
      validRole === "Crew Health Officer" ? behavioralByCrew : null,
    consent_matrix:
      validRole === "Astronaut"
        ? { [validCrewId]: selectedConsent }
        : validRole === "Crew Health Officer"
        ? store.consent_profiles
        : null,
    access_log:
      validRole === "Astronaut" || validRole === "Crew Health Officer"
        ? store.access_log
        : [],
    environment: env,
    ground_summary: {
      bands: bandCounts,
      band_counts: bandCounts,
      safety_events_count: globalSafetyRules.length,
      advisory_alerts_count: crewOverview.reduce((acc, c) => acc + c.alert_count, 0),
      crew_count: CREW_ROSTER.length,
      shared_exposure_signal: env.shared_exposure_alert,
    },
    sync_queue: queueItems,
    sync_summary: {
      online: Boolean(store.earth_link_online),
      items: queueItems,
      total_queued: queuedCount,
    },
    sos_events: visibleSos,
    messages: visibleMessages,
    advisor:
      scopedAstronaut
        ? {
            briefing: scopedAstronaut.briefing,
            observations: scopedAstronaut.observations,
            protocol_refs: scopedAstronaut.briefing.protocol_refs,
            evidence_window: `Day ${d} · 16:00 ship time`,
            confidence_pct: scopedAstronaut.briefing.confidence_pct,
            gap_count: scopedAstronaut.readiness.data_quality.gap_count,
            suggested_questions: [
              "Why am I feeling more tired after exercise?",
              "Is the Lab air affecting the crew?",
              "What should I do next?",
              "How confident are you in this?",
              "What if I sleep 5 hours for the next 5 days?",
              "Could this be a medical diagnosis?",
            ],
            hard_boundaries: [
              "Never diagnoses or prescribes.",
              "Never downgrades a deterministic alert.",
              "Never fills a sensor gap with a normal value.",
              "Cites only approved protocols.",
            ],
          }
        : null,
  };
}

// --- Offline Mutation Handlers ---

export function triggerFallbackSos({
  astronautId = "ast-01",
  sosType = "medical",
  note = "",
  day = 23,
  hour = 16,
}) {
  const store = loadStore();
  const profile = CREW_ROSTER.find((c) => c.astronaut_id === astronautId) || CREW_ROSTER[0];
  const metrics = buildAstronautDayMetrics(profile.astronaut_id, day, store);
  const sosId = `sos-${Date.now().toString(36)}`;
  const minute = new Date().getMinutes();
  const minStr = String(minute).padStart(2, "0");

  const packet = {
    sos_id: sosId,
    astronaut_id: profile.astronaut_id,
    astronaut_name: profile.name,
    type: sosType,
    note: note.trim() || "Emergency SOS triggered on board.",
    day,
    hour,
    minute,
    timestamp_label: `Day ${day} · ${String(hour).padStart(2, "0")}:${minStr} ship time`,
    short_date: `Day ${day}, ${String(hour).padStart(2, "0")}:${minStr}`,
    status: store.earth_link_online ? "transmitting" : "queued",
    onboard_acknowledged: false,
    priority: 0,
    vitals_snapshot: {
      hr_bpm: metrics.readiness.latest_readings.heart_rate.value,
      hrv_ms: metrics.readiness.latest_readings.hrv_rmssd.value,
      spo2_pct: metrics.readiness.latest_readings.spo2.value,
    },
    env_snapshot: {
      zone_id: profile.default_zone,
      co2_ppm: zoneCo2ForDay(profile.default_zone, day),
    },
    active_alerts: ["SR-05"],
    override_logged: true,
  };

  store.sos_events.unshift(packet);
  store.sync_queue.unshift({
    item_id: `sync-${sosId}`,
    category: "sos",
    priority: 0,
    title: `SOS — ${sosType} (${profile.astronaut_id})`,
    detail: "Priority 0 emergency packet",
    status: packet.status,
    day,
    size_kb: 4,
    ref_id: sosId,
  });
  store.access_log.unshift({
    log_id: `aud-${Date.now().toString(36)}`,
    actor_role: "Emergency Safety Rule SR-05",
    target_astronaut_id: profile.astronaut_id,
    access_type: "emergency SOS packet",
    timestamp_label: `Day ${day}, ${String(hour).padStart(2, "0")}:${minStr}`,
    mode: "Emergency Override",
    scope: "physio + env snapshot",
    emergency_override: true,
    reason: `SOS (${sosType}) triggered; expires in 2h.`,
    fields: ["heart_rate", "hrv_rmssd", "spo2", "co2_ppm"],
  });
  saveStore(store);
  return packet;
}

export function cancelFallbackSos({ sosId, reason = "false_alarm" }) {
  const store = loadStore();
  const item = store.sos_events.find((s) => s.sos_id === sosId);
  if (item) {
    item.status = reason === "false_alarm" ? "cancelled" : "resolved_ok";
    item.resolved_note = "Cancelled within 10s window — I'm OK / false alarm.";
  }
  const syncItem = store.sync_queue.find((q) => q.ref_id === sosId);
  if (syncItem) {
    syncItem.status = "acknowledged";
    syncItem.title = `${syncItem.title} (cancelled)`;
  }
  saveStore(store);
  return item || { sos_id: sosId, status: "cancelled" };
}

export function acknowledgeFallbackSos({ sosId, actorRole = "Crew Health Officer" }) {
  const store = loadStore();
  const item = store.sos_events.find((s) => s.sos_id === sosId);
  if (item) {
    item.onboard_acknowledged = true;
    item.acknowledged_by = actorRole;
    if (store.earth_link_online) {
      item.status = "acknowledged";
    }
  }
  saveStore(store);
  return item;
}

export function resolveFallbackSos({ sosId }) {
  const store = loadStore();
  const item = store.sos_events.find((s) => s.sos_id === sosId);
  if (item) {
    item.status = "resolved_ok";
    item.onboard_acknowledged = true;
  }
  saveStore(store);
  return item;
}

export function submitFallbackCheckin({
  astronautId = "ast-01",
  day = 23,
  energy = 3,
  mood = 3,
  stress = 2,
  headache = 0,
  fatigue = 1,
  note = "",
  safetyConcern = false,
}) {
  const store = loadStore();
  store.checkins[`${astronautId}:${day}`] = {
    astronaut_id: astronautId,
    day,
    energy: Number(energy),
    mood: Number(mood),
    stress: Number(stress),
    headache: Number(headache),
    fatigue: Number(fatigue),
    note: String(note || ""),
    safety_concern: Boolean(safetyConcern),
    logged_at: new Date().toISOString(),
  };
  saveStore(store);
  return store.checkins[`${astronautId}:${day}`];
}

export function submitFallbackPvt({
  astronautId = "ast-01",
  day = 23,
  meanRtMs = 250,
  lapses = 0,
  trials = 5,
}) {
  const store = loadStore();
  store.pvt_tests[`${astronautId}:${day}`] = {
    astronaut_id: astronautId,
    day,
    mean_rt_ms: Math.round(Number(meanRtMs)),
    lapses: Number(lapses),
    trials: Number(trials),
    logged_at: new Date().toISOString(),
  };
  saveStore(store);
  return store.pvt_tests[`${astronautId}:${day}`];
}

export function sendFallbackMessage({
  fromId = "ast-01",
  toId = "earth",
  kind = "text",
  body = "",
  audioDurationS = 0,
  sizeKb = 2,
  attachChart = false,
  day = 23,
}) {
  const store = loadStore();
  const sender =
    CREW_ROSTER.find((c) => c.astronaut_id === fromId)?.name ||
    (fromId === "health_officer"
      ? "Crew Health Officer"
      : fromId === "systems"
      ? "Systems Engineer"
      : fromId === "earth"
      ? "Home (Earth)"
      : "Cmdr. Elena Vasquez");

  const recipientMap = {
    earth: "Home (Earth)",
    health_officer: "Crew Health Officer",
    systems: "Systems Engineer",
    all: "All crew",
  };
  const toLabel =
    recipientMap[toId] ||
    CREW_ROSTER.find((c) => c.astronaut_id === toId)?.name ||
    toId;

  const isEarth = toId === "earth" || fromId === "earth";
  const delayMin = isEarth ? round1(10.8 + (day / 30) * 2.6) : 0;
  const computedSize =
    kind === "audio"
      ? Math.max(12, Math.round((audioDurationS || 8) * 3.2))
      : attachChart
      ? Math.max(18, Math.round(sizeKb))
      : Math.max(1, Math.round(body.length / 180));
  const bwWarning = (isEarth && (kind === "audio" || attachChart || computedSize > 12));
  const status = !isEarth
    ? "delivered"
    : store.earth_link_online
    ? "sent"
    : "queued";

  const msgId = `msg-${Date.now().toString(36)}`;
  const msg = {
    message_id: msgId,
    from_id: fromId,
    from_label: sender,
    to_id: toId,
    to_label: toLabel,
    channel: isEarth ? "earth" : "crew",
    kind,
    body:
      kind === "audio"
        ? body || `Audio voice note (${audioDurationS || 8}s, ${computedSize} KB)`
        : body,
    audio_duration_s: audioDurationS || 0,
    size_kb: computedSize,
    bandwidth_warning: bwWarning,
    attachment: attachChart
      ? {
          label: "Recovery trend — 7 days · consented health chart",
          detail: "Consented health attachment · adds transmit time on a narrow link",
          type: "recovery_chart_7d",
        }
      : null,
    status,
    light_delay_min: delayMin,
    day,
    timestamp_label: isEarth
      ? `Day ${day}, 16:05 · Earth light time ${delayMin} min`
      : `Day ${day}, 16:05 · on-board`,
    read_by: [fromId],
  };

  store.messages.unshift(msg);
  if (isEarth) {
    store.sync_queue.push({
      item_id: `sync-${msgId}`,
      category: "message",
      priority: 2,
      title: `${kind === "audio" ? "Audio" : "Text"} message to ${toLabel}`,
      detail: `${sender} -> ${toLabel} · ${computedSize} KB`,
      status: store.earth_link_online ? "transmitting" : "queued",
      day,
      size_kb: computedSize,
      ref_id: msgId,
    });
  }
  saveStore(store);
  return msg;
}

export function markFallbackMessageRead({ messageId, readerRole = "ast-01" }) {
  const store = loadStore();
  const msg = store.messages.find((m) => m.message_id === messageId);
  if (msg) {
    msg.status = "read";
    if (!msg.read_by.includes(readerRole)) {
      msg.read_by.push(readerRole);
    }
  }
  saveStore(store);
  return msg;
}

export function updateFallbackConsent({
  astronautId = "ast-01",
  mode = "normal",
  scope = "physio",
  enabled = true,
}) {
  const store = loadStore();
  if (!store.consent_profiles[astronautId]) {
    store.consent_profiles[astronautId] = JSON.parse(
      JSON.stringify(DEFAULT_CONSENT_PROFILES[astronautId] || DEFAULT_CONSENT_PROFILES["ast-01"])
    );
  }
  if (mode === "normal" || mode === "emergency") {
    store.consent_profiles[astronautId][mode][scope] = Boolean(enabled);
    store.access_log.unshift({
      log_id: `aud-${Date.now().toString(36)}`,
      actor_role: "Astronaut (Owner)",
      target_astronaut_id: astronautId,
      access_type: "consent switch update",
      timestamp_label: "Just now",
      mode: mode === "emergency" ? "Emergency Scope" : "Normal",
      scope,
      emergency_override: false,
      reason: `${mode} sharing for '${scope}' set to ${enabled ? "ON" : "OFF"}.`,
      fields: [scope],
    });
  }
  saveStore(store);
  return store.consent_profiles[astronautId];
}

export function toggleFallbackEarthLink({ online }) {
  const store = loadStore();
  store.earth_link_online = Boolean(online);
  saveStore(store);
  return { online: store.earth_link_online };
}

export function fastForwardFallbackSync() {
  const store = loadStore();
  if (!store.earth_link_online) {
    return {
      online: false,
      processed_count: 0,
      reason: "Earth link is offline. Packets stay queued in priority order.",
    };
  }
  let processed = 0;
  const sorted = [...store.sync_queue].sort((a, b) => a.priority - b.priority);
  sorted.forEach((item) => {
    if (item.status !== "acknowledged") {
      item.status = "acknowledged";
      processed += 1;
      if (item.ref_id) {
        const sos = store.sos_events.find((s) => s.sos_id === item.ref_id);
        if (sos && !["cancelled", "resolved_ok"].includes(sos.status)) {
          sos.status = "acknowledged";
          sos.onboard_acknowledged = true;
        }
        const msg = store.messages.find((m) => m.message_id === item.ref_id);
        if (msg && msg.status !== "read") {
          msg.status = "delivered";
        }
      }
    }
  });
  saveStore(store);
  return { online: true, processed_count: processed };
}

// --- Grounded Offline Advisor Q&A & Counterfactual What-If ---

export function askFallbackAdvisor({
  question = "",
  day = 23,
  crewId = "ast-01",
  role = "Astronaut",
}) {
  const state = getFallbackState({ day, role, crewId });
  const astro = state.astronaut;
  const q = String(question || "").trim().toLowerCase();
  const win = `Day ${Math.max(1, day - 7)}..Day ${day} · 16:00 ship time`;

  if (!astro) {
    return {
      answer:
        "I don't know personal crew details in this anonymised role view. I can only reference anonymised habitat telemetry and approved environmental protocols (PROT-ENV-01, PROT-ENV-02).",
      confidence: 0.78,
      evidence_window: win,
      protocol_refs: ["PROT-ENV-01", "PROT-ENV-02"],
      disclaimer: "Decision support only. Not a diagnosis.",
    };
  }

  const rhr = astro.readiness.latest_readings.heart_rate.value;
  const hrv = astro.readiness.latest_readings.hrv_rmssd.value;
  const sleep = astro.readiness.latest_readings.sleep_duration.value;
  const pvt = astro.readiness.latest_readings.pvt_mean_rt.value;
  const obsHrr = astro.observations[0]?.value;
  const labCo2 = state.environment.zones.LAB.co2_ppm;

  if (q.includes("diagnos") || q.includes("prescrib") || q.includes("sick") || q.includes("illness")) {
    return {
      answer:
        "I cannot make a medical diagnosis or prescribe treatment. I only compare your recent clean telemetry against your personal early-mission baseline and cite approved flight checklists. Because an active signal or safety review is present, please confirm symptoms with the Crew Health Officer or Earth medical.",
      confidence: astro.briefing.confidence_pct / 100,
      evidence_window: win,
      protocol_refs: ["PROT-MED-01", "PROT-REC-01"],
      disclaimer: "Decision support only — never a diagnosis or prescription.",
    };
  }

  if (q.includes("tired") || q.includes("exercise") || q.includes("recovery") || q.includes("winded")) {
    return {
      answer: `In your ${win} evidence window, recovery debt is ${astro.readiness.recovery_debt.score}/100 (personal range 10–34). Your 1-minute heart-rate recovery is ${obsHrr} bpm vs personal reference 34.5 bpm, HRV is ${hrv ?? "withheld"} ms, and HR is ${rhr ?? "withheld"} bpm. This may reflect accumulated exertion and shortened sleep (${sleep ?? "gap"} h), though clinical review is required if breathlessness persists. Next step: take a 24-hour recovery block and repeat the 1-minute HR recovery check.`,
      confidence: astro.readiness.recovery_debt.confidence,
      evidence_window: win,
      protocol_refs: ["PROT-REC-01", "PROT-REC-02"],
      disclaimer: "Association and baseline delta only — not a medical diagnosis.",
    };
  }

  if (q.includes("lab") || q.includes("air") || q.includes("co2") || q.includes("scrubber")) {
    return {
      answer: `US Lab CO₂ is currently ${labCo2} ppm (peaked >5,000 ppm on Day 19 triggering deterministic rule SR-03 before scrubber service on Day 22). Two anonymised crew members show headache/fatigue scores co-moving with US Lab CO₂ (r=0.95–0.96, 0-day lag). Treat this as a possible shared environmental confounder until portable air checks verify the cabin; individual illness is not excluded.`,
      confidence: 0.9,
      evidence_window: `Day ${Math.max(1, day - 13)}..Day ${day}`,
      protocol_refs: ["PROT-ENV-01", "PROT-ENV-02"],
      disclaimer: "Correlation is not causation; verify cabin air directly.",
    };
  }

  if (q.includes("what should i do") || q.includes("next step") || q.includes("next")) {
    return {
      answer: `${
        astro.readiness.safety_active
          ? "Deterministic safety rules remain active and cannot be lowered. "
          : ""
      }Single best next step: ${astro.briefing.single_best_next_step}`,
      confidence: astro.briefing.confidence_pct / 100,
      evidence_window: win,
      protocol_refs: astro.briefing.protocol_refs,
      disclaimer: "Follow escalation criteria if resting symptoms worsen.",
    };
  }

  if (q.includes("confident") || q.includes("confidence") || q.includes("gap") || q.includes("missing")) {
    return {
      answer: `Overall data confidence is ${astro.briefing.confidence_pct}% (${astro.readiness.data_quality.coverage_pct}% recent coverage). ${astro.readiness.data_quality.summary} Missing or sensor-off windows are preserved as explicit gaps rather than imputed as normal.`,
      confidence: astro.briefing.confidence_pct / 100,
      evidence_window: win,
      protocol_refs: ["PROT-REC-02", "PROT-SLP-02"],
      disclaimer: "Confidence reflects sensor coverage and cross-signal agreement.",
    };
  }

  if (q.includes("5 hour") || q.includes("what if") || q.includes("sleep")) {
    const sim = runFallbackWhatIf({
      sleep_per_night: q.includes("5 hour") ? 5.0 : 7.5,
      workload_adjustment: q.includes("5 hour") ? 0.0 : -1.0,
      cabin_ventilation_pct: 100,
      recovery_blocks: q.includes("5 hour") ? 0 : 2,
      horizon_days: q.includes("5 day") ? 5 : 7,
      day,
      crewId,
    });
    return {
      answer: `Exploratory what-if projection (${Math.round(
        sim.confidence * 100
      )}% exploratory confidence): ${sim.summary} Use the What-if sandbox tab to adjust sleep, workload, ventilation, and recovery blocks interactively.`,
      confidence: sim.confidence,
      evidence_window: `Next ${sim.horizon_days} days (extrapolated from last 7 days)`,
      protocol_refs: sim.protocol_refs,
      disclaimer: sim.disclaimer,
    };
  }

  return {
    answer: `I don't know beyond the recorded mission signals for ${astro.profile.short_name} on Day ${day}. Current readings show recovery debt ${astro.readiness.recovery_debt.score}/100, cognitive readiness ${astro.readiness.cognitive_readiness.score}/100 (PVT ${pvt ?? "withheld"} ms), and US Lab CO₂ ${labCo2} ppm. Ask about recovery, sleep, Lab air, data confidence, or try a What-if simulation.`,
    confidence: 0.42,
    evidence_window: win,
    protocol_refs: astro.briefing.protocol_refs,
    disclaimer: "AstroGuard Advisor only answers from verified engine outputs and approved protocols.",
  };
}

// Exact port of backend/app/engines/counterfactual.py
function estimateTrendSlope(series, maxAbsSlope = 1.3) {
  const vals = (series || [])
    .slice(-7)
    .map((p) => Number(p?.value))
    .filter((v) => !Number.isNaN(v));
  if (vals.length < 3) return 0.0;
  const n = vals.length;
  const meanX = (n - 1) / 2.0;
  const meanY = vals.reduce((a, b) => a + b, 0) / n;
  let num = 0;
  let den = 0;
  for (let i = 0; i < n; i += 1) {
    num += (i - meanX) * (vals[i] - meanY);
    den += (i - meanX) * (i - meanX);
  }
  const raw = den > 1e-9 ? num / den : 0.0;
  return clamp(raw * 0.6, -maxAbsSlope, maxAbsSlope);
}

export function runFallbackWhatIf({
  sleep_per_night = 7.5,
  workload_adjustment = -1.0,
  cabin_ventilation_pct = 130.0,
  recovery_blocks = 2,
  horizon_days = 7,
  day = 23,
  crewId = "ast-01",
} = {}) {
  const state = getFallbackState({ day, role: "Astronaut", crewId });
  const readiness = state.astronaut?.readiness;
  const currentDay = Number(readiness?.up_to_day || day || 23);

  const startDebt = Number(readiness?.recovery_debt?.score ?? 61.0);
  const startCog = Number(readiness?.cognitive_readiness?.score ?? 90.0);
  const recSlope = estimateTrendSlope(readiness?.recovery_debt?.series, 1.3);
  const cogSlope = estimateTrendSlope(readiness?.cognitive_readiness?.series, 1.3);

  const currentSleep = Number(
    readiness?.latest_readings?.sleep_duration?.value ??
      readiness?.latest_readings?.sleep_duration?.baseline ??
      6.3
  );
  const baseCo2 = Number(state.environment?.zones?.LAB?.co2_ppm ?? 1113.0);

  const sleepH = clamp(Number(sleep_per_night), 4.0, 10.0);
  const workload = clamp(Number(workload_adjustment), -2.0, 2.0);
  const ventPct = clamp(Number(cabin_ventilation_pct), 50.0, 200.0);
  const recBlocks = Math.round(clamp(Number(recovery_blocks), 0, 7));
  const horizon = Math.round(clamp(Number(horizon_days), 1, 14));

  const rawSleepDelta = sleepH - currentSleep;
  const effectiveSleepGain = 1.6 * Math.tanh(rawSleepDelta / 1.4);

  const totalDebtEffect =
    -5.8 * effectiveSleepGain +
    2.6 * workload -
    3.8 * (1.0 - Math.exp(-recBlocks / 2.2));
  const totalCogEffect =
    6.2 * effectiveSleepGain -
    1.8 * workload +
    1.6 * (1.0 - Math.exp(-recBlocks / 2.5));

  const ambientFloor = 250.0;
  const projectedCo2 = Math.max(
    ambientFloor,
    ambientFloor + (baseCo2 - ambientFloor) * Math.pow(100.0 / ventPct, 1.25)
  );
  const co2Delta = Math.round(projectedCo2 - baseCo2);

  const baseConf = Number(readiness?.confidence ?? 0.91);
  const exploratoryConf = round2(clamp(baseConf * 0.48, 0.22, 0.58));

  const recoverySeries = [];
  const cognitiveSeries = [];
  let baseDebtVal = startDebt;
  let baseCogVal = startCog;

  for (let step = 1; step <= horizon; step += 1) {
    const projDay = currentDay + step;
    const damp = Math.pow(0.84, step - 1);
    baseDebtVal = clamp(baseDebtVal + recSlope * damp, 0, 100);
    baseCogVal = clamp(baseCogVal + cogSlope * damp, 0, 100);

    const denom = Math.max(2.2, horizon * 0.45);
    const ramp = 1.0 - Math.exp(-step / denom);
    const normRamp = ramp / (1.0 - Math.exp(-horizon / denom));
    const scaleH = 0.7 + 0.3 * (horizon / 7.0);

    const intDebtVal = clamp(
      baseDebtVal + totalDebtEffect * scaleH * normRamp,
      0,
      100
    );
    const intCogVal = clamp(
      baseCogVal + totalCogEffect * scaleH * normRamp,
      0,
      100
    );

    const recUnc = round1(5.2 * Math.sqrt(step));
    const cogUnc = round1(4.5 * Math.sqrt(step));

    recoverySeries.push({
      day: projDay,
      baseline: round1(baseDebtVal),
      intervention: round1(intDebtVal),
      uncertainty: recUnc,
      low: round1(clamp(intDebtVal - recUnc, 0, 100)),
      high: round1(clamp(intDebtVal + recUnc, 0, 100)),
    });
    cognitiveSeries.push({
      day: projDay,
      baseline: round1(baseCogVal),
      intervention: round1(intCogVal),
      uncertainty: cogUnc,
      low: round1(clamp(intCogVal - cogUnc, 0, 100)),
      high: round1(clamp(intCogVal + cogUnc, 0, 100)),
    });
  }

  const finalDebtDelta = round1(
    recoverySeries[recoverySeries.length - 1].intervention -
      recoverySeries[recoverySeries.length - 1].baseline
  );
  const finalCogDelta = round1(
    cognitiveSeries[cognitiveSeries.length - 1].intervention -
      cognitiveSeries[cognitiveSeries.length - 1].baseline
  );

  const protocols = [];
  if (recBlocks > 0 || workload < 0) protocols.push("PROT-REC-01");
  if (sleepH >= 7.0) protocols.push("PROT-SLP-01");
  if (ventPct > 100) protocols.push("PROT-ENV-01", "PROT-ENV-02");
  if (protocols.length === 0) protocols.push("PROT-REC-01", "PROT-SLP-01");

  const debtDir = finalDebtDelta <= 0 ? "lower" : "higher";
  const summary = `With ${sleepH.toFixed(1)} h sleep, workload ${
    workload >= 0 ? `+${workload.toFixed(1)}` : workload.toFixed(1)
  }, ${recBlocks} recovery block(s)/week and ventilation at ${Math.round(
    ventPct
  )}%, projected recovery debt is ${Math.abs(finalDebtDelta).toFixed(
    0
  )} points ${debtDir} by day ${horizon}, and cognitive readiness is ${
    finalCogDelta >= 0 ? `+${Math.round(finalCogDelta)}` : Math.round(finalCogDelta)
  } points. Confidence is exploratory.`;

  return {
    exploratory: true,
    confidence: exploratoryConf,
    horizon_days: horizon,
    inputs: {
      sleep_per_night: round2(sleepH),
      workload_adjustment: round2(workload),
      cabin_ventilation_pct: round1(ventPct),
      recovery_blocks: recBlocks,
      horizon_days: horizon,
      baseline_co2_ppm: round1(baseCo2),
    },
    deltas: {
      recovery_debt: finalDebtDelta,
      cognitive_readiness: finalCogDelta,
      co2_exposure: co2Delta,
    },
    recovery_series: recoverySeries,
    cognitive_series: cognitiveSeries,
    uncertainty: {
      recovery_debt_pts: recoverySeries[recoverySeries.length - 1].uncertainty,
      cognitive_readiness_pts: cognitiveSeries[cognitiveSeries.length - 1].uncertainty,
    },
    assumptions: [
      "Projection extrapolates your last 7 days; it does not model new illness or medication.",
      "Sleep effect is spread over the selected days with diminishing returns.",
      "Workload is an abstract -2...+2 adjustment, not a specific schedule.",
      "Ventilation changes habitat CO₂ exposure, not an individual's physiology directly.",
      "Recovery blocks reduce planned physical load; they do not replace clinical review.",
    ],
    protocol_refs: protocols,
    summary,
    disclaimer: "Exploratory what-if projection. Not a diagnosis, treatment plan, or guarantee.",
  };
}
