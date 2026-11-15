import {
  acknowledgeFallbackSos,
  askFallbackAdvisor,
  cancelFallbackSos,
  fastForwardFallbackSync,
  getFallbackState,
  markFallbackMessageRead,
  PROTOCOL_LIBRARY,
  resetFallbackStore,
  resolveFallbackSos,
  runFallbackWhatIf,
  sendFallbackMessage,
  submitFallbackCheckin,
  submitFallbackPvt,
  toggleFallbackEarthLink,
  triggerFallbackSos,
  updateFallbackConsent,
} from "./fallbackData.js";

const API_BASE = "http://127.0.0.1:8000/api";
const REQUEST_TIMEOUT_MS = 2200;

async function requestJson(path, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
      signal: controller.signal,
      ...options,
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const payload = await res.json();
    return { ok: true, data: payload };
  } catch (err) {
    return { ok: false, error: err?.message || "offline" };
  } finally {
    clearTimeout(timer);
  }
}

function normalizeLiveState(live, fallbackParams) {
  const base = getFallbackState(fallbackParams);
  if (!live || typeof live !== "object") return base;
  const resolvedOnline = Boolean(
    live.online ?? live.earth_link_online ?? live.earth_link?.online ?? base.online
  );
  const resolvedQueue = Array.isArray(live.sync_queue)
    ? live.sync_queue
    : Array.isArray(live.sync_queue?.items)
    ? live.sync_queue.items
    : base.sync_queue;

  return {
    ...base,
    ...live,
    mode: "live",
    online: resolvedOnline,
    earth_link_online: resolvedOnline,
    protocols: {
      ...PROTOCOL_LIBRARY,
      ...(live.protocols || {}),
    },
    earth_link: {
      ...base.earth_link,
      ...(live.earth_link || {}),
      online: resolvedOnline,
    },
    safety: {
      ...base.safety,
      ...(live.safety || {}),
    },
    environment: live.environment
      ? { ...base.environment, ...live.environment }
      : base.environment,
    ground_summary: live.ground_summary
      ? { ...base.ground_summary, ...live.ground_summary }
      : base.ground_summary,
    sync_queue: resolvedQueue,
    sync_summary: {
      online: resolvedOnline,
      items: resolvedQueue,
      total_queued: resolvedQueue.filter((q) => q.status !== "acknowledged").length,
    },
    astronaut:
      live.astronaut === null
        ? null
        : live.astronaut
        ? {
            ...base.astronaut,
            ...live.astronaut,
            readiness: {
              ...(base.astronaut?.readiness || {}),
              ...(live.astronaut?.readiness || {}),
            },
            briefing: {
              ...(base.astronaut?.briefing || {}),
              ...(live.astronaut?.briefing || {}),
            },
            behavioral: live.astronaut.behavioral
              ? {
                  ...(base.astronaut?.behavioral || {}),
                  ...live.astronaut.behavioral,
                }
              : base.astronaut?.behavioral,
          }
        : base.astronaut,
    advisor:
      live.advisor === null
        ? null
        : live.advisor
        ? { ...base.advisor, ...live.advisor }
        : base.advisor,
  };
}

export async function fetchState({
  day = 23,
  role = "Astronaut",
  crewId = "ast-01",
} = {}) {
  const query = `?day=${encodeURIComponent(day)}&role=${encodeURIComponent(
    role
  )}&crew_id=${encodeURIComponent(crewId)}`;
  const res = await requestJson(`/state${query}`);
  if (res.ok) {
    return {
      state: normalizeLiveState(res.data, { day, role, crewId }),
      isLive: true,
    };
  }
  return {
    state: getFallbackState({ day, role, crewId }),
    isLive: false,
  };
}

export async function askAdvisor({ question, day, role, crewId }) {
  const res = await requestJson("/advisor/ask", {
    method: "POST",
    body: JSON.stringify({
      question,
      day,
      role,
      crew_id: crewId,
      astronaut_id: crewId,
    }),
  });
  if (res.ok && res.data) {
    return { reply: res.data, isLive: true };
  }
  return {
    reply: askFallbackAdvisor({ question, day, crewId, role }),
    isLive: false,
  };
}

export async function runWhatIf(params) {
  const res = await requestJson("/advisor/what-if", {
    method: "POST",
    body: JSON.stringify({
      astronaut_id: params.crewId,
      crew_id: params.crewId,
      day: params.day,
      sleep_per_night: params.sleep_per_night,
      workload_adjustment: params.workload_adjustment,
      cabin_ventilation_pct: params.cabin_ventilation_pct,
      recovery_blocks: params.recovery_blocks,
      horizon_days: params.horizon_days,
    }),
  });
  if (res.ok && res.data) {
    return { projection: res.data, isLive: true };
  }
  return {
    projection: runFallbackWhatIf(params),
    isLive: false,
  };
}

export async function triggerSos({
  astronautId,
  sosType,
  note,
  day,
  hour = 16,
}) {
  const localPacket = triggerFallbackSos({
    astronautId,
    sosType,
    note,
    day,
    hour,
  });
  const res = await requestJson("/sos/trigger", {
    method: "POST",
    body: JSON.stringify({
      astronaut_id: astronautId,
      sos_type: sosType,
      type: sosType,
      note,
      day,
      hour,
    }),
  });
  return {
    packet: res.ok && res.data ? { ...localPacket, ...res.data } : localPacket,
    isLive: res.ok,
  };
}

export async function cancelSos({ sosId, reason = "false_alarm" }) {
  const local = cancelFallbackSos({ sosId, reason });
  const res = await requestJson("/sos/cancel", {
    method: "POST",
    body: JSON.stringify({ sos_id: sosId, reason }),
  });
  return {
    packet: res.ok && res.data ? res.data : local,
    isLive: res.ok,
  };
}

export async function acknowledgeSos({ sosId, actorRole = "Crew Health Officer" }) {
  const local = acknowledgeFallbackSos({ sosId, actorRole });
  const res = await requestJson("/sos/acknowledge", {
    method: "POST",
    body: JSON.stringify({ sos_id: sosId, actor_role: actorRole }),
  });
  return {
    packet: res.ok && res.data ? res.data : local,
    isLive: res.ok,
  };
}

export async function resolveSos({ sosId, note = "" }) {
  const local = resolveFallbackSos({ sosId, note });
  const res = await requestJson("/sos/resolve", {
    method: "POST",
    body: JSON.stringify({ sos_id: sosId, note }),
  });
  return {
    packet: res.ok && res.data ? res.data : local,
    isLive: res.ok,
  };
}

export async function submitCheckin(payload) {
  const local = submitFallbackCheckin(payload);
  const res = await requestJson("/checkin", {
    method: "POST",
    body: JSON.stringify({
      astronaut_id: payload.astronautId,
      day: payload.day,
      energy: payload.energy,
      mood: payload.mood,
      stress: payload.stress,
      headache: payload.headache,
      fatigue: payload.fatigue,
      note: payload.note,
      safety_concern: payload.safetyConcern,
    }),
  });
  return { result: res.ok ? res.data : local, isLive: res.ok };
}

export async function submitPvt(payload) {
  const local = submitFallbackPvt(payload);
  const res = await requestJson("/pvt", {
    method: "POST",
    body: JSON.stringify({
      astronaut_id: payload.astronautId,
      day: payload.day,
      mean_rt_ms: payload.meanRtMs,
      lapses: payload.lapses,
      trials: payload.trials,
    }),
  });
  return { result: res.ok ? res.data : local, isLive: res.ok };
}

export async function sendMessage(payload) {
  const local = sendFallbackMessage(payload);
  const res = await requestJson("/messages/send", {
    method: "POST",
    body: JSON.stringify({
      from_id: payload.fromId,
      to_id: payload.toId,
      kind: payload.kind,
      body: payload.body,
      audio_duration_s: payload.audioDurationS,
      size_kb: payload.sizeKb,
      attach_chart: payload.attachChart,
      day: payload.day,
    }),
  });
  return { message: res.ok ? res.data : local, isLive: res.ok };
}

export async function markMessageRead({ messageId, readerRole }) {
  const local = markFallbackMessageRead({ messageId, readerRole });
  const res = await requestJson("/messages/read", {
    method: "POST",
    body: JSON.stringify({
      message_id: messageId,
      reader_role: readerRole,
    }),
  });
  return { message: res.ok ? res.data : local, isLive: res.ok };
}

export async function updateConsent({ astronautId, mode, scope, enabled }) {
  const local = updateFallbackConsent({ astronautId, mode, scope, enabled });
  const res = await requestJson("/consent/update", {
    method: "POST",
    body: JSON.stringify({
      astronaut_id: astronautId,
      mode,
      scope,
      enabled,
    }),
  });
  return { consent: res.ok ? res.data : local, isLive: res.ok };
}

export async function toggleEarthLink({ online }) {
  const local = toggleFallbackEarthLink({ online });
  const res = await requestJson("/sync/link", {
    method: "POST",
    body: JSON.stringify({ online }),
  });
  return { link: res.ok ? res.data : local, isLive: res.ok };
}

export async function fastForwardSync() {
  const local = fastForwardFallbackSync();
  const res = await requestJson("/sync/fast-forward", {
    method: "POST",
    body: JSON.stringify({}),
  });
  return { sync: res.ok ? res.data : local, isLive: res.ok };
}

export function resetDemoState() {
  return resetFallbackStore();
}
