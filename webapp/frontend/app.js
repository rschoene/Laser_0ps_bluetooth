const responseBox = document.getElementById("response");
const notificationsBox = document.getElementById("notifications");
const statusPill = document.getElementById("status-pill");
const targetAddressInput = document.getElementById("target-address");
const liveStatePill = document.getElementById("live-state");
const liveStatusBody = document.getElementById("live-status-body");
const liveEventsBox = document.getElementById("live-events");
const scanButton = document.getElementById("btn-scan");
const setupBody = document.getElementById("setup-body");
const rankingBody = document.getElementById("ranking-body");
const rankingStatePill = document.getElementById("ranking-state");
const roundStatsBody = document.getElementById("round-stats-body");
const gameSummaryPill = document.getElementById("game-summary");
const SLOT_MIN = 2;
const SLOT_MAX = 5;

let liveSource = null;
const liveByAddress = new Map();
const liveLines = [];
const MAX_LIVE_LINES = 300;

let currentView = "setup";
let lastRankingSnapshot = {
  running: false,
  session_state: "idle",
  session_id: null,
  started_at: null,
  planned_end_at: null,
  duration_seconds: null,
  remaining_seconds: null,
  ended_at: null,
  end_reason: null,
  participants: [],
  ranking: [],
  slot_stats: [],
  totals: { shots: 0, reloads: 0, hits: null, kills: null },
};

function setResponse(payload) {
  responseBox.textContent = JSON.stringify(payload, null, 2);
}

function setStatus(text, ok = true) {
  statusPill.textContent = text;
  statusPill.classList.toggle("error", !ok);
}

function setLiveState(text, ok = true) {
  liveStatePill.textContent = text;
  liveStatePill.classList.toggle("error", !ok);
}

function setRankingState(text, ok = true) {
  rankingStatePill.textContent = text;
  rankingStatePill.classList.toggle("error", !ok);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data?.detail || response.statusText;
    throw new Error(detail);
  }
  return data;
}

function getTargetAddress() {
  return targetAddressInput.value.trim();
}

function mustTargetAddress() {
  const address = getTargetAddress();
  if (!address) {
    throw new Error("Bitte zuerst eine Ziel-Adresse eintragen.");
  }
  return address;
}

function tsToLocal(ts) {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleString();
}

function tsToClock(ts) {
  if (!ts) return "-";
  return new Date(ts * 1000).toLocaleTimeString();
}

function normAddress(address) {
  return String(address || "").toLowerCase();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function teamName(team) {
  if (team === 0) return "Blau";
  if (team === 1) return "Rot";
  return `Team ${team}`;
}

function formatTeam(slot, team) {
  if (slot == null || team == null) return "-";
  return `S${slot} / ${teamName(Number(team))}`;
}

function formatPercent(value) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  return `${Number(value).toFixed(1)} %`;
}

function formatEndReason(reason) {
  if (!reason) return "-";
  if (reason === "duration_elapsed") return "Zeit abgelaufen";
  if (reason === "manual_stop") return "Manuell beendet";
  if (reason === "superseded_by_new_start") return "Durch neuen Start ersetzt";
  return reason;
}

function displayName(entry) {
  return (
    entry.display_name ||
    entry.local_name ||
    entry.name ||
    entry.address ||
    "unbekannt"
  );
}

function formatLinkState(entry) {
  const state = entry.connection_state || "-";
  const reconnect = entry.reconnect_count ?? 0;
  if (entry.last_error) {
    return `${state} (Reconnects: ${reconnect}, Fehler)`;
  }
  return `${state} (Reconnects: ${reconnect})`;
}

function pushLiveLine(line) {
  if (!liveEventsBox) return;
  liveLines.push(line);
  if (liveLines.length > MAX_LIVE_LINES) {
    liveLines.splice(0, liveLines.length - MAX_LIVE_LINES);
  }
  liveEventsBox.textContent = liveLines.join("\n");
  liveEventsBox.scrollTop = liveEventsBox.scrollHeight;
}

function upsertLiveEntry(entry) {
  const key = normAddress(entry.address);
  if (!key) return;
  const current = liveByAddress.get(key) || {};
  const merged = {
    ...current,
    ...entry,
  };
  if (entry.live_state == null && current.live_state != null) {
    merged.live_state = current.live_state;
  }
  merged.display_name = merged.display_name || merged.local_name || merged.name || merged.address;
  liveByAddress.set(key, merged);
}

function removeLiveEntry(address) {
  liveByAddress.delete(normAddress(address));
}

function renderLiveStatus() {
  liveStatusBody.innerHTML = "";
  const items = Array.from(liveByAddress.values()).sort((a, b) =>
    (a.address || "").localeCompare(b.address || "")
  );
  for (const item of items) {
    const ls = item.live_state || {};
    const ammo =
      ls.last_ammo_counter == null
        ? "-"
        : `0x${Number(ls.last_ammo_counter).toString(16).padStart(2, "0")}`;
    const status =
      ls.last_status_word == null
        ? "-"
        : `0x${Number(ls.last_status_word).toString(16).padStart(4, "0")}`;

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(displayName(item))}</td>
      <td>${escapeHtml(item.address || "-")}</td>
      <td>${escapeHtml(formatTeam(item.assigned_slot, item.assigned_team))}</td>
      <td>${escapeHtml(formatLinkState(item))}</td>
      <td>${ls.trigger_count ?? 0}</td>
      <td>${ls.reload_count ?? 0}</td>
      <td>${escapeHtml(ammo)}</td>
      <td>${escapeHtml(status)}</td>
      <td>${escapeHtml(ls.last_event || "-")}</td>
    `;
    tr.addEventListener("click", () => {
      if (item.address) targetAddressInput.value = item.address;
      if (item.assigned_slot != null) {
        document.getElementById("team-slot").value = String(item.assigned_slot);
      }
      if (item.assigned_team != null) {
        document.getElementById("team-team").value = String(item.assigned_team);
      }
      if (item.auto_reconnect != null) {
        document.getElementById("auto-reconnect-enabled").checked = Boolean(
          item.auto_reconnect
        );
      }
    });
    liveStatusBody.appendChild(tr);
  }
}

function renderSetupTable(connections) {
  setupBody.innerHTML = "";
  const sorted = [...connections].sort((a, b) =>
    (a.address || "").localeCompare(b.address || "")
  );
  for (const conn of sorted) {
    const tr = document.createElement("tr");
    const safeAddress = conn.address || "";
    const slotValue =
      conn.assigned_slot == null ? SLOT_MIN : Number(conn.assigned_slot);
    const teamValue = conn.assigned_team == null ? 0 : Number(conn.assigned_team);
    const localNameValue = conn.local_name || "";

    tr.innerHTML = `
      <td><input class="setup-name-input" type="text" maxlength="32" value="${escapeHtml(localNameValue)}" placeholder="z. B. Delta 1"></td>
      <td>${escapeHtml(conn.name || "unbekannt")}</td>
      <td>${escapeHtml(safeAddress)}</td>
      <td><input class="setup-slot-input" type="number" min="${SLOT_MIN}" max="${SLOT_MAX}" value="${slotValue}"></td>
      <td>
        <select>
          <option value="0"${teamValue === 0 ? " selected" : ""}>Rot</option>
          <option value="1"${teamValue === 1 ? " selected" : ""}>Blau</option>
        </select>
      </td>
      <td>
        <button type="button" class="setup-name-save">Name speichern</button>
        <button type="button" class="setup-team-save">Team speichern</button>
      </td>
    `;

    const nameInput = tr.querySelector(".setup-name-input");
    const slotInput = tr.querySelector(".setup-slot-input");
    const teamSelect = tr.querySelector("select");
    const saveNameButton = tr.querySelector(".setup-name-save");
    const saveTeamButton = tr.querySelector(".setup-team-save");

    saveNameButton.addEventListener("click", (event) => {
      event.stopPropagation();
      runAction(
        () => setLocalNameForAddress(safeAddress, nameInput.value),
        { button: saveNameButton, busyText: "Speichere..." }
      );
    });

    saveTeamButton.addEventListener("click", (event) => {
      event.stopPropagation();
      const slot = Number(slotInput.value);
      const team = Number(teamSelect.value);
      runAction(
        () => setTeamProfileByAddress(safeAddress, slot, team),
        { button: saveTeamButton, busyText: "Speichere..." }
      );
    });

    tr.addEventListener("click", () => {
      targetAddressInput.value = safeAddress;
      document.getElementById("team-slot").value = String(slotInput.value);
      document.getElementById("team-team").value = String(teamSelect.value);
    });

    setupBody.appendChild(tr);
  }
}

function renderRanking(snapshot) {
  rankingBody.innerHTML = "";
  const ranking = snapshot?.ranking || [];
  if (snapshot?.running) {
    const remaining = snapshot?.remaining_seconds;
    const remainingText =
      remaining == null ? "-" : `${Math.max(0, Number(remaining) || 0)} s`;
    setRankingState(
      `Runde läuft seit ${tsToLocal(snapshot.started_at)} (Rest: ${remainingText}, Session ${snapshot.session_id})`,
      true
    );
  } else if (snapshot?.session_id != null) {
    setRankingState(
      `Runde beendet (${formatEndReason(snapshot.end_reason)}) um ${tsToLocal(snapshot.ended_at)}`,
      false
    );
  } else {
    setRankingState("Kein aktives Spiel", false);
  }
  for (const item of ranking) {
    const tr = document.createElement("tr");
    const name = item.display_name || item.local_name || item.name || item.address || "-";
    tr.innerHTML = `
      <td>${item.rank ?? "-"}</td>
      <td>${escapeHtml(name)}</td>
      <td>${escapeHtml(formatTeam(item.slot, item.team))}</td>
      <td>${item.shots ?? 0}</td>
      <td>${item.reloads ?? 0}</td>
      <td>${item.hits ?? "-"}</td>
      <td>${item.kills ?? "-"}</td>
      <td>${escapeHtml(formatPercent(item.accuracy_percent))}</td>
      <td>${escapeHtml(item.connection_state || "-")}</td>
    `;
    tr.addEventListener("click", () => {
      if (item.address) {
        targetAddressInput.value = item.address;
      }
    });
    rankingBody.appendChild(tr);
  }
}

function renderRoundStats(snapshot) {
  if (!roundStatsBody || !gameSummaryPill) return;
  roundStatsBody.innerHTML = "";
  const slotStats = snapshot?.slot_stats || [];
  if (!snapshot || snapshot.session_id == null) {
    gameSummaryPill.textContent = "Noch keine abgeschlossene Runde";
    gameSummaryPill.classList.add("error");
    return;
  }

  const totals = snapshot.totals || {};
  const totalsText = [
    `Schüsse: ${totals.shots ?? 0}`,
    `Nachladen: ${totals.reloads ?? 0}`,
    `Treffer: ${totals.hits ?? "-"}`,
    `Kills: ${totals.kills ?? "-"}`,
  ].join(" | ");

  if (snapshot.running) {
    gameSummaryPill.textContent = `Runde aktiv | ${totalsText}`;
  } else {
    const reason = formatEndReason(snapshot.end_reason);
    gameSummaryPill.textContent = `Runde beendet (${reason}) | ${totalsText}`;
  }
  gameSummaryPill.classList.remove("error");

  for (const item of slotStats) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.slot ?? "-"}</td>
      <td>${escapeHtml(item.display_name || item.address || "-")}</td>
      <td>${escapeHtml(formatTeam(item.slot, item.team))}</td>
      <td>${item.hits ?? "-"}</td>
      <td>${item.kills ?? "-"}</td>
    `;
    tr.addEventListener("click", () => {
      if (item.address) {
        targetAddressInput.value = item.address;
      }
    });
    roundStatsBody.appendChild(tr);
  }
}

function applyRankingSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") return;
  lastRankingSnapshot = snapshot;
  renderRanking(snapshot);
  renderRoundStats(snapshot);
}

function applyConnectionList(connections) {
  const present = new Set();
  for (const conn of connections) {
    present.add(normAddress(conn.address));
    upsertLiveEntry({
      address: conn.address,
      name: conn.name,
      local_name: conn.local_name,
      display_name: conn.display_name,
      live_state: conn.live_state || {},
      assigned_slot: conn.assigned_slot,
      assigned_team: conn.assigned_team,
      connection_state: conn.connection_state,
      auto_reconnect: conn.auto_reconnect,
      reconnect_count: conn.reconnect_count,
      disconnect_count: conn.disconnect_count,
      last_error: conn.last_error,
      connected_at: conn.connected_at,
    });
  }
  for (const key of Array.from(liveByAddress.keys())) {
    if (!present.has(key)) {
      liveByAddress.delete(key);
    }
  }
  renderConnections(connections);
  renderSetupTable(connections);
  renderLiveStatus();
}

function renderConnections(connections) {
  const body = document.getElementById("connections-body");
  body.innerHTML = "";
  const sorted = [...connections].sort((a, b) =>
    (a.address || "").localeCompare(b.address || "")
  );
  for (const conn of sorted) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(conn.display_name || conn.local_name || conn.name || "unbekannt")}</td>
      <td>${escapeHtml(conn.address)}</td>
      <td>${escapeHtml(formatTeam(conn.assigned_slot, conn.assigned_team))}</td>
      <td>${escapeHtml(formatLinkState(conn))}</td>
      <td>${escapeHtml(tsToLocal(conn.connected_at))}</td>
      <td><button type="button" data-address="${escapeHtml(conn.address)}">Trennen</button></td>
    `;
    const button = tr.querySelector("button");
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      runAction(() => disconnectDevice(conn.address));
    });
    tr.addEventListener("click", () => {
      targetAddressInput.value = conn.address;
      if (conn.assigned_slot != null) {
        document.getElementById("team-slot").value = String(conn.assigned_slot);
      }
      if (conn.assigned_team != null) {
        document.getElementById("team-team").value = String(conn.assigned_team);
      }
      if (conn.auto_reconnect != null) {
        document.getElementById("auto-reconnect-enabled").checked = Boolean(
          conn.auto_reconnect
        );
      }
    });
    body.appendChild(tr);
  }
}

function handleLiveSnapshot(snapshot) {
  const conns = snapshot?.connections || [];
  liveByAddress.clear();
  applyConnectionList(conns);
}

function handleConnectionEvent(payload, ts) {
  if (payload.action === "connected" && payload.connection) {
    const conn = payload.connection;
    upsertLiveEntry({
      address: conn.address,
      name: conn.name,
      local_name: conn.local_name,
      display_name: conn.display_name,
      live_state: conn.live_state || {},
      assigned_slot: conn.assigned_slot,
      assigned_team: conn.assigned_team,
      connection_state: conn.connection_state,
      auto_reconnect: conn.auto_reconnect,
      reconnect_count: conn.reconnect_count,
      disconnect_count: conn.disconnect_count,
      last_error: conn.last_error,
      connected_at: conn.connected_at,
    });
    pushLiveLine(`${ts} [${conn.address}] verbunden`);
    refreshConnections().catch(() => {});
    return;
  }

  if (payload.action === "disconnected") {
    removeLiveEntry(payload.address);
    pushLiveLine(`${ts} [${payload.address}] getrennt`);
    refreshConnections().catch(() => {});
    return;
  }

  if (!payload.address) {
    return;
  }

  const key = normAddress(payload.address);
  const existing = liveByAddress.get(key) || {};
  const derivedState =
    payload.connection_state != null
      ? payload.connection_state
      : payload.action === "lost"
        ? "disconnected"
        : payload.action === "reconnect_attempt"
          ? "reconnecting"
          : payload.action === "reconnected"
            ? "connected"
            : existing.connection_state ?? null;
  const derivedError =
    payload.error != null
      ? payload.error
      : payload.reason != null
        ? payload.reason
        : existing.last_error ?? null;

  upsertLiveEntry({
    address: payload.address,
    name: payload.name || existing.name,
    local_name: payload.local_name ?? existing.local_name ?? null,
    display_name: payload.display_name ?? existing.display_name ?? null,
    live_state: payload.live_state || existing.live_state || {},
    assigned_slot: payload.slot ?? existing.assigned_slot ?? null,
    assigned_team: payload.team ?? existing.assigned_team ?? null,
    connection_state: derivedState,
    auto_reconnect:
      payload.auto_reconnect ?? payload.enabled ?? existing.auto_reconnect ?? null,
    reconnect_count: payload.reconnect_count ?? existing.reconnect_count ?? null,
    disconnect_count: payload.disconnect_count ?? existing.disconnect_count ?? null,
    last_error: derivedError,
  });
  pushLiveLine(`${ts} [${payload.address}] ${payload.action || "verbindung"}`);
  renderLiveStatus();
}

function handleLiveEvent(eventEnvelope) {
  const eventType = eventEnvelope?.type;
  const payload = eventEnvelope?.payload || {};
  const ts = tsToClock(eventEnvelope?.ts);

  if (eventType === "ranking") {
    applyRankingSnapshot(payload);
    return;
  }

  if (eventType === "notification") {
    const notif = payload.notification || {};
    upsertLiveEntry({
      address: payload.address,
      name: payload.name,
      local_name: payload.local_name,
      display_name: payload.display_name,
      live_state: payload.live_state || {},
    });
    renderLiveStatus();
    pushLiveLine(`${ts} [${payload.address}] ${notif.raw || ""} ${notif.decoded || ""}`);
    return;
  }

  if (eventType === "connection") {
    handleConnectionEvent(payload, ts);
    return;
  }

  if (eventType === "game_session") {
    pushLiveLine(`${ts} [runde] ${payload.action || "update"}`);
    refreshRanking().catch(() => {});
    return;
  }

  if (eventType === "local_name" && payload.connection) {
    const conn = payload.connection;
    upsertLiveEntry({
      address: conn.address,
      name: conn.name,
      local_name: conn.local_name,
      display_name: conn.display_name,
      live_state: conn.live_state || {},
      assigned_slot: conn.assigned_slot,
      assigned_team: conn.assigned_team,
      connection_state: conn.connection_state,
      auto_reconnect: conn.auto_reconnect,
      reconnect_count: conn.reconnect_count,
      disconnect_count: conn.disconnect_count,
      last_error: conn.last_error,
      connected_at: conn.connected_at,
    });
    renderLiveStatus();
    refreshConnections().catch(() => {});
    pushLiveLine(`${ts} [${conn.address}] lokaler Name aktualisiert`);
    return;
  }

  if (payload.address) {
    const existing = liveByAddress.get(normAddress(payload.address)) || {};
    upsertLiveEntry({
      address: payload.address,
      name: payload.name || existing.name,
      local_name: payload.local_name ?? existing.local_name ?? null,
      display_name: payload.display_name ?? existing.display_name ?? null,
      live_state: payload.live_state || existing.live_state || {},
      assigned_slot: payload.slot ?? existing.assigned_slot ?? null,
      assigned_team: payload.team ?? existing.assigned_team ?? null,
    });
    renderLiveStatus();
    pushLiveLine(`${ts} [${payload.address}] ${eventType}`);
  }
}

async function refreshHealth() {
  try {
    await api("/api/health");
    setStatus("API: erreichbar", true);
  } catch (_err) {
    setStatus("API: nicht erreichbar", false);
  }
}

function openLiveStream() {
  if (liveSource) {
    liveSource.close();
    liveSource = null;
  }

  setLiveState("Live-Stream: verbinde...", true);
  liveSource = new EventSource("/api/live/stream");

  liveSource.addEventListener("open", () => {
    setLiveState("Live-Stream: verbunden", true);
  });

  liveSource.addEventListener("snapshot", (event) => {
    try {
      const payload = JSON.parse(event.data);
      handleLiveSnapshot(payload);
      pushLiveLine(`${tsToClock(payload.generated_at)} [system] Schnappschuss`);
      refreshRanking().catch(() => {});
    } catch (_err) {}
  });

  const eventTypes = [
    "notification",
    "connection",
    "game_session",
    "startup",
    "volume",
    "config",
    "game_start",
    "team_profile",
    "local_name",
    "ranking",
  ];
  for (const eventType of eventTypes) {
    liveSource.addEventListener(eventType, (event) => {
      try {
        const envelope = JSON.parse(event.data);
        handleLiveEvent(envelope);
      } catch (_err) {}
    });
  }

  liveSource.onerror = () => {
    setLiveState("Live-Stream: Verbindung unterbrochen, erneuter Versuch...", false);
  };
}

function renderDevices(devices) {
  const body = document.getElementById("devices-body");
  body.innerHTML = "";
  for (const dev of devices) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(dev.name)}</td>
      <td>${escapeHtml(dev.address)}</td>
      <td>${escapeHtml(dev.rssi ?? "?")}</td>
      <td><button type="button" data-address="${escapeHtml(dev.address)}">Verbinden</button></td>
    `;
    const button = tr.querySelector("button");
    button.addEventListener("click", () => runAction(() => connectDevice(dev.address)));
    body.appendChild(tr);
  }
}

async function scan() {
  const timeout = Number(document.getElementById("scan-timeout").value);
  const byName = document.getElementById("scan-by-name").checked;
  const name = document.getElementById("scan-name").value.trim() || "NerfV";
  const result = await api("/api/scan", {
    method: "POST",
    body: JSON.stringify({
      timeout,
      by_name: byName,
      name,
      expected_count: 0,
    }),
  });
  renderDevices(result.devices || []);
  return result;
}

async function refreshConnections() {
  const result = await api("/api/connections");
  const connections = result.connections || [];
  applyConnectionList(connections);
  return result;
}

async function refreshRanking() {
  const result = await api("/api/game/ranking");
  applyRankingSnapshot(result);
  return result;
}

async function connectDevice(address) {
  const result = await api("/api/connect", {
    method: "POST",
    body: JSON.stringify({ address, timeout: 15.0 }),
  });
  targetAddressInput.value = address;
  await refreshConnections();
  return result;
}

async function disconnectDevice(address) {
  const result = await api(`/api/disconnect/${encodeURIComponent(address)}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
  await refreshConnections();
  await refreshRanking();
  return result;
}

async function setLocalNameForAddress(address, localNameValue) {
  const localName = String(localNameValue || "").trim();
  const payload = localName.length === 0 ? { local_name: null } : { local_name: localName };
  const result = await api(`/api/local-name/${encodeURIComponent(address)}`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
  await refreshConnections();
  return result;
}

async function setAutoReconnect() {
  const address = mustTargetAddress();
  const enabled = document.getElementById("auto-reconnect-enabled").checked;
  const result = await api(`/api/reconnect/auto/${encodeURIComponent(address)}`, {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
  await refreshConnections();
  return result;
}

async function reconnectNow() {
  const address = mustTargetAddress();
  const result = await api(`/api/reconnect/${encodeURIComponent(address)}`, {
    method: "POST",
    body: JSON.stringify({ timeout: 15.0 }),
  });
  await refreshConnections();
  return result;
}

async function startup() {
  const address = mustTargetAddress();
  const volume = Number(document.getElementById("startup-volume").value);
  return api(`/api/startup/${encodeURIComponent(address)}`, {
    method: "POST",
    body: JSON.stringify({ volume }),
  });
}

async function setVolume() {
  const address = mustTargetAddress();
  const volume = Number(document.getElementById("set-volume").value);
  return api(`/api/volume/${encodeURIComponent(address)}`, {
    method: "POST",
    body: JSON.stringify({ volume }),
  });
}

async function setTeamProfileByAddress(address, slot, team) {
  const result = await api(`/api/team/${encodeURIComponent(address)}`, {
    method: "POST",
    body: JSON.stringify({ slot, team }),
  });
  await refreshConnections();
  return result;
}

async function setTeamProfile() {
  const address = mustTargetAddress();
  const slot = Number(document.getElementById("team-slot").value);
  const team = Number(document.getElementById("team-team").value);
  return setTeamProfileByAddress(address, slot, team);
}

async function startGame() {
  const address = mustTargetAddress();
  const delay = Number(document.getElementById("game-delay").value);
  const durationSeconds = Number(document.getElementById("game-duration").value);
  const startupVolume = Number(document.getElementById("game-startup-volume").value);
  const forceStartup = document.getElementById("force-startup").checked;
  const result = await api(`/api/game/start/${encodeURIComponent(address)}`, {
    method: "POST",
    body: JSON.stringify({
      delay,
      duration_seconds: durationSeconds,
      startup_volume: startupVolume,
      force_startup: forceStartup,
    }),
  });
  if (result?.result?.ranking) {
    applyRankingSnapshot(result.result.ranking);
  } else {
    await refreshRanking();
  }
  return result;
}

async function startGameMulti(body) {
  const result = await api("/api/game/start-multi", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (result?.result?.ranking) {
    applyRankingSnapshot(result.result.ranking);
  } else {
    await refreshRanking();
  }
  return result;
}

async function startGameMultiAdmin() {
  const raw = document.getElementById("multi-addresses").value.trim();
  const addresses = raw
    ? raw.split(",").map((x) => x.trim()).filter((x) => x.length > 0)
    : [];
  const delay = Number(document.getElementById("game-delay").value);
  const durationSeconds = Number(document.getElementById("game-duration").value);
  const startupVolume = Number(document.getElementById("game-startup-volume").value);
  const forceStartup = document.getElementById("force-startup").checked;
  return startGameMulti({
    addresses,
    delay,
    duration_seconds: durationSeconds,
    startup_volume: startupVolume,
    force_startup: forceStartup,
  });
}

async function startGameMultiSetup() {
  const delay = Number(document.getElementById("game-delay").value || 0.12);
  const durationSeconds = Number(document.getElementById("setup-game-duration").value);
  const startupVolume = Number(document.getElementById("setup-game-startup-volume").value);
  const forceStartup = document.getElementById("setup-force-startup").checked;
  return startGameMulti({
    addresses: [],
    delay,
    duration_seconds: durationSeconds,
    startup_volume: startupVolume,
    force_startup: forceStartup,
  });
}

async function pollStatus() {
  const address = mustTargetAddress();
  return api(`/api/status/poll/${encodeURIComponent(address)}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

async function collectStats() {
  const address = mustTargetAddress();
  return api(`/api/stats/${encodeURIComponent(address)}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

async function closeSession() {
  const address = mustTargetAddress();
  return api(`/api/session/close/${encodeURIComponent(address)}`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

async function endGame() {
  const result = await api("/api/game/end", {
    method: "POST",
    body: JSON.stringify({ reason: "manual_stop" }),
  });
  if (result?.result) {
    applyRankingSnapshot(result.result);
  } else {
    await refreshRanking();
  }
  return result;
}

async function refreshNotifications() {
  const address = getTargetAddress();
  if (!address) {
    notificationsBox.textContent = "Keine Ziel-Adresse gesetzt.";
    return { items: [] };
  }
  const result = await api(`/api/notifications/${encodeURIComponent(address)}`);
  const lines = (result.items || []).map((item) => {
    const t = new Date(item.ts * 1000).toLocaleTimeString();
    return `${t}  ${item.raw}  ${item.decoded}`;
  });
  notificationsBox.textContent = lines.join("\n");
  return result;
}

async function runAction(fn, options = {}) {
  const button = options.button || null;
  const busyText = options.busyText || null;
  const originalText = button ? button.textContent : null;
  if (button) {
    button.disabled = true;
    if (busyText) {
      button.textContent = busyText;
    }
  }
  try {
    const result = await fn();
    setResponse(result);
  } catch (err) {
    setResponse({ error: err.message });
  } finally {
    if (button) {
      button.disabled = false;
      if (busyText && originalText != null) {
        button.textContent = originalText;
      }
    }
  }
}

function activateView(view) {
  currentView = view;
  for (const btn of document.querySelectorAll(".tab-btn")) {
    btn.classList.toggle("active", btn.dataset.viewTarget === view);
  }
  for (const pane of document.querySelectorAll(".view-pane")) {
    const isVisible = pane.dataset.view === view;
    pane.classList.toggle("hidden", !isVisible);
  }
  if (view === "setup") {
    refreshConnections().catch(() => {});
  }
  if (view === "game") {
    refreshRanking().catch(() => {});
  }
}

function bindClick(id, handler) {
  const el = document.getElementById(id);
  if (!el) return;
  el.addEventListener("click", handler);
}

if (scanButton) {
  scanButton.addEventListener("click", () => {
    runAction(scan, { button: scanButton, busyText: "Suche läuft..." });
  });
}
bindClick("btn-refresh-connections", () => runAction(refreshConnections));
bindClick("btn-setup-start-multi", () => runAction(startGameMultiSetup));
bindClick("btn-refresh-ranking", () => runAction(refreshRanking));
bindClick("btn-game-end", () => runAction(endGame));
bindClick("btn-set-auto-reconnect", () => runAction(setAutoReconnect));
bindClick("btn-reconnect", () => runAction(reconnectNow));
bindClick("btn-startup", () => runAction(startup));
bindClick("btn-set-volume", () => runAction(setVolume));
bindClick("btn-set-team", () => runAction(setTeamProfile));
bindClick("btn-game-start", () => runAction(startGame));
bindClick("btn-game-start-multi", () => runAction(startGameMultiAdmin));
bindClick("btn-game-end-admin", () => runAction(endGame));
bindClick("btn-poll-status", () => runAction(pollStatus));
bindClick("btn-close-session", () => runAction(closeSession));
bindClick("btn-refresh-notifications", () => runAction(refreshNotifications));

for (const viewButton of document.querySelectorAll(".tab-btn")) {
  viewButton.addEventListener("click", () => {
    activateView(viewButton.dataset.viewTarget);
  });
}

setInterval(() => {
  const auto = document.getElementById("auto-refresh")?.checked;
  if (!auto) return;
  refreshNotifications().catch(() => {});
}, 2000);

setInterval(() => {
  if (currentView !== "game") return;
  refreshRanking().catch(() => {});
}, 1500);

refreshHealth();
runAction(refreshConnections);
runAction(refreshRanking);
openLiveStream();
activateView("setup");

window.addEventListener("beforeunload", () => {
  if (liveSource) liveSource.close();
});
