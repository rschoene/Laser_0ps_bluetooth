const responseBox = document.getElementById("response");
const notificationsBox = document.getElementById("notifications");
const statusPill = document.getElementById("status-pill");
const errorsBand = document.getElementById("errors-band");
const errorsBox = document.getElementById("errors");
const clearErrorsButton = document.getElementById("btn-clear-errors");
const targetAddressInput = document.getElementById("target-address");
const liveStatePill = document.getElementById("live-state");
const liveStatusBody = document.getElementById("live-status-body");
const liveEventsBox = document.getElementById("live-events");
const scanButton = document.getElementById("btn-scan");
const enableBluetoothButton = document.getElementById("btn-enable-bluetooth");
const setupBody = document.getElementById("setup-body");
const rankingBody = document.getElementById("ranking-body");
const rankingStatePill = document.getElementById("ranking-state");
const roundStatsBody = document.getElementById("round-stats-body");
const gameSummaryPill = document.getElementById("game-summary");
const languageSelect = document.getElementById("language-select");
const SLOT_MIN = 2;
const SLOT_MAX = 5;

const SUPPORTED_LANGUAGES = ["en", "de"];
const DEFAULT_LANGUAGE = "en";
let currentLanguage = DEFAULT_LANGUAGE;
let translations = {
  "app.title": "LaserOps Control",
  "status.apiUnknown": "API: unknown",
  "status.liveOff": "Live stream: off",
  "error.enterTargetAddress": "Please enter a target address first.",
  "error.noTargetAddressSet": "No target address set.",
  "error.unknown": "Unknown error",
  "misc.empty": "-",
};

function detectLanguage() {
  const browserLang = String(navigator.language || "").toLowerCase();
  const short = browserLang.split("-")[0];
  return SUPPORTED_LANGUAGES.includes(short) ? short : DEFAULT_LANGUAGE;
}

function languageFileFor(lang) {
  return lang === "de" ? "german.json" : "english.json";
}

async function loadLanguage(lang) {
  const safeLang = SUPPORTED_LANGUAGES.includes(lang) ? lang : DEFAULT_LANGUAGE;
  const response = await fetch(`/assets/i18n/${languageFileFor(safeLang)}`);
  if (!response.ok) {
    throw new Error(`Failed to load translations for ${safeLang}`);
  }
  translations = await response.json();
  currentLanguage = safeLang;
  document.documentElement.lang = safeLang;
  if (languageSelect) {
    languageSelect.value = safeLang;
  }
}

function interpolate(template, vars = {}) {
  return String(template).replace(/\{(\w+)\}/g, (_, key) => String(vars[key] ?? ""));
}

function t(key, vars = {}) {
  const template = translations[key];
  if (typeof template !== "string") {
    return key;
  }
  return interpolate(template, vars);
}

function applyTranslations() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.setAttribute("placeholder", t(el.dataset.i18nPlaceholder));
  });
  document.title = t("app.title");
  renderErrors();
}

let liveSource = null;
const liveByAddress = new Map();
const liveLines = [];
const MAX_LIVE_LINES = 300;
const errorEntries = [];
const MAX_ERROR_LINES = 100;
const errorLastSeenByFingerprint = new Map();

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

function normalizeDetail(raw) {
  if (raw == null) return "";
  if (typeof raw === "string") return raw.trim();
  if (Array.isArray(raw)) {
    return raw
      .map((item) => normalizeDetail(item))
      .filter((item) => item.length > 0)
      .join("; ");
  }
  if (typeof raw === "object") {
    const loc = Array.isArray(raw.loc)
      ? raw.loc.filter((part) => part !== "body").join(".")
      : "";
    const msg = typeof raw.msg === "string" ? raw.msg.trim() : "";
    if (loc && msg) return `${loc}: ${msg}`;
    if (msg) return msg;
    if ("detail" in raw) return normalizeDetail(raw.detail);
    if ("error" in raw) return normalizeDetail(raw.error);
    try {
      return JSON.stringify(raw);
    } catch (_err) {
      return String(raw);
    }
  }
  return String(raw).trim();
}

function stripTupleDetail(raw) {
  const text = normalizeDetail(raw);
  const tupleMatch = text.match(/^\(['"](.+?)['"],\s*<[^>]+>\)$/);
  return tupleMatch ? tupleMatch[1] : text;
}

function localizeErrorDetail(detail, status) {
  const clean = stripTupleDetail(detail);
  const lower = clean.toLowerCase();

  if (
    lower.includes("no powered bluetooth adapters") ||
    lower.includes("powered_off")
  ) {
    return t("error.bluetoothPoweredOff");
  }
  if (lower.includes("failed to enable bluetooth")) {
    return t("error.bluetoothEnableFailed");
  }
  if (lower.includes("only supported on linux hosts")) {
    return t("error.bluetoothUnsupportedHost");
  }
  if (lower.includes("no supported bluetooth control utility found")) {
    return t("error.bluetoothToolsMissing");
  }
  if (
    lower.includes("bluetooth discovery already running") ||
    lower.includes("scan already in progress")
  ) {
    return t("error.scanAlreadyRunning");
  }
  if (lower.includes("not connected")) {
    return t("error.deviceNotConnected");
  }
  if (lower.includes("not found")) {
    return t("error.deviceNotFound");
  }
  if (lower.includes("timeout")) {
    return t("error.timeout");
  }
  if (lower.includes("permission denied") || lower.includes("access denied")) {
    return t("error.permissionDenied");
  }
  if (lower.includes("failed to fetch")) {
    return t("error.network");
  }
  if (Number.isFinite(status) && status === 422) {
    return t("error.validationFailed", { status });
  }
  if (Number.isFinite(status) && status >= 500) {
    return t("error.serverFailure", { status });
  }
  if (Number.isFinite(status) && status >= 400) {
    return t("error.requestFailed", { status });
  }
  return clean || t("error.unknown");
}

function renderErrors() {
  if (!errorsBand || !errorsBox) return;
  if (errorEntries.length === 0) {
    errorsBox.textContent = "";
    errorsBand.classList.add("hidden");
    return;
  }
  errorsBand.classList.remove("hidden");
  const lines = errorEntries.map((entry) => {
    const context = t(entry.contextKey || "context.action");
    const summary = localizeErrorDetail(entry.detail, entry.status);
    const ts = new Date(entry.ts).toLocaleTimeString(currentLanguage);
    const header = `[${ts}] ${t("error.actionFailed", { context, message: summary })}`;
    if (entry.detail && stripTupleDetail(entry.detail) !== summary) {
      return `${header}\n${t("error.details")}: ${stripTupleDetail(entry.detail)}`;
    }
    return header;
  });
  errorsBox.textContent = lines.join("\n\n");
}

function clearErrors() {
  errorEntries.length = 0;
  errorLastSeenByFingerprint.clear();
  renderErrors();
}

function reportError(err, options = {}) {
  const status = Number(err?.status);
  const contextKey = options.contextKey || "context.action";
  const detail = stripTupleDetail(
    err?.detail ?? err?.message ?? (typeof err === "string" ? err : "")
  );
  const fingerprint = `${contextKey}|${Number.isFinite(status) ? status : ""}|${detail}`;
  const now = Date.now();
  const dedupeMs = Number(options.dedupeMs ?? 3000);
  const lastSeen = errorLastSeenByFingerprint.get(fingerprint) || 0;
  if (now - lastSeen < dedupeMs) {
    return;
  }
  errorLastSeenByFingerprint.set(fingerprint, now);
  errorEntries.push({
    ts: now,
    status: Number.isFinite(status) ? status : null,
    detail,
    contextKey,
  });
  if (errorEntries.length > MAX_ERROR_LINES) {
    errorEntries.splice(0, errorEntries.length - MAX_ERROR_LINES);
  }
  renderErrors();
}

function errorPayload(err, contextKey = "context.action") {
  const status = Number(err?.status);
  const detail = stripTupleDetail(
    err?.detail ?? err?.message ?? (typeof err === "string" ? err : "")
  );
  return {
    context: t(contextKey),
    status: Number.isFinite(status) ? status : null,
    error: localizeErrorDetail(detail, status),
    detail: detail || null,
  };
}

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
  let response;
  try {
    response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
  } catch (networkErr) {
    const err = new Error(networkErr?.message || "failed to fetch");
    err.status = 0;
    err.detail = networkErr?.message || "failed to fetch";
    err.path = path;
    throw err;
  }

  const contentType = String(response.headers.get("content-type") || "").toLowerCase();
  let data = null;
  let rawText = "";
  if (contentType.includes("application/json")) {
    data = await response.json().catch(() => null);
  } else {
    rawText = await response.text().catch(() => "");
  }

  if (!response.ok) {
    const candidateDetail = data?.detail ?? data?.error ?? rawText ?? response.statusText;
    const detail = stripTupleDetail(candidateDetail) || response.statusText || t("error.unknown");
    const err = new Error(detail);
    err.status = response.status;
    err.detail = detail;
    err.path = path;
    throw err;
  }
  return data ?? {};
}

function getTargetAddress() {
  return targetAddressInput.value.trim();
}

function mustTargetAddress() {
  const address = getTargetAddress();
  if (!address) {
    throw new Error(t("error.enterTargetAddress"));
  }
  return address;
}

function tsToLocal(ts) {
  if (!ts) return t("misc.empty");
  return new Date(ts * 1000).toLocaleString(currentLanguage);
}

function tsToClock(ts) {
  if (!ts) return t("misc.empty");
  return new Date(ts * 1000).toLocaleTimeString(currentLanguage);
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
  if (team === 0) return t("team.red");
  if (team === 1) return t("team.blue");
  if (team === 2) return t("team.violet");
  return t("team.generic", { team });
}

function formatTeam(slot, team) {
  if (slot == null || team == null) return t("misc.empty");
  return t("team.slotFormat", { slot, team: teamName(Number(team)) });
}

function formatPercent(value) {
  if (value == null || Number.isNaN(Number(value))) return t("misc.empty");
  return t("misc.percent", { value: Number(value).toFixed(1) });
}

function formatEndReason(reason) {
  if (!reason) return t("misc.empty");
  const key = `game.endReason.${reason}`;
  if (typeof translations[key] === "string") {
    return t(key);
  }
  return reason;
}

function displayName(entry) {
  return (
    entry.display_name ||
    entry.local_name ||
    entry.name ||
    entry.address ||
    t("state.unknown")
  );
}

function formatLinkState(entry) {
  const state = entry.connection_state || t("misc.empty");
  const reconnect = entry.reconnect_count ?? 0;
  if (entry.last_error) {
    return t("connection.reconnectsWithError", { state, count: reconnect });
  }
  return t("connection.reconnects", { state, count: reconnect });
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
        ? t("misc.empty")
        : `0x${Number(ls.last_ammo_counter).toString(16).padStart(2, "0")}`;
    const status =
      ls.last_status_word == null
        ? t("misc.empty")
        : `0x${Number(ls.last_status_word).toString(16).padStart(4, "0")}`;

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(displayName(item))}</td>
      <td>${escapeHtml(item.address || t("misc.empty"))}</td>
      <td>${escapeHtml(formatTeam(item.assigned_slot, item.assigned_team))}</td>
      <td>${escapeHtml(formatLinkState(item))}</td>
      <td>${ls.trigger_count ?? 0}</td>
      <td>${ls.reload_count ?? 0}</td>
      <td>${escapeHtml(ammo)}</td>
      <td>${escapeHtml(status)}</td>
      <td>${escapeHtml(ls.last_event || t("misc.empty"))}</td>
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
    const teamValue = conn.assigned_team == null ? 2 : Number(conn.assigned_team);
    const localNameValue = conn.local_name || "";

    tr.innerHTML = `
      <td><input class="setup-name-input" type="text" maxlength="32" value="${escapeHtml(localNameValue)}" placeholder="${escapeHtml(t("placeholder.localName"))}"></td>
      <td>${escapeHtml(conn.name || t("state.unknown"))}</td>
      <td>${escapeHtml(safeAddress)}</td>
      <td><input class="setup-slot-input" type="number" min="${SLOT_MIN}" max="${SLOT_MAX}" value="${slotValue}"></td>
      <td>
        <select>
          <option value="0"${teamValue === 0 ? " selected" : ""}>${escapeHtml(t("team.red"))}</option>
          <option value="1"${teamValue === 1 ? " selected" : ""}>${escapeHtml(t("team.blue"))}</option>
          <option value="2"${teamValue === 2 ? " selected" : ""}>${escapeHtml(t("team.violet"))}</option>
        </select>
      </td>
      <td>
        <button type="button" class="setup-name-save">${escapeHtml(t("button.saveName"))}</button>
        <button type="button" class="setup-team-save">${escapeHtml(t("button.saveTeam"))}</button>
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
        { button: saveNameButton, busyText: t("button.saving") }
      );
    });

    saveTeamButton.addEventListener("click", (event) => {
      event.stopPropagation();
      const slot = Number(slotInput.value);
      const team = Number(teamSelect.value);
      runAction(
        () => setTeamProfileByAddress(safeAddress, slot, team),
        { button: saveTeamButton, busyText: t("button.saving") }
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
      remaining == null
        ? t("misc.empty")
        : t("misc.secondsShort", { value: Math.max(0, Number(remaining) || 0) });
    setRankingState(
      t("ranking.running", {
        startedAt: tsToLocal(snapshot.started_at),
        remaining: remainingText,
        sessionId: snapshot.session_id,
      }),
      true
    );
  } else if (snapshot?.session_id != null) {
    setRankingState(
      t("ranking.ended", {
        reason: formatEndReason(snapshot.end_reason),
        endedAt: tsToLocal(snapshot.ended_at),
      }),
      false
    );
  } else {
    setRankingState(t("status.noActiveGame"), false);
  }
  for (const item of ranking) {
    const tr = document.createElement("tr");
    const name =
      item.display_name ||
      item.local_name ||
      item.name ||
      item.address ||
      t("misc.empty");
    tr.innerHTML = `
      <td>${item.rank ?? t("misc.empty")}</td>
      <td>${escapeHtml(name)}</td>
      <td>${escapeHtml(formatTeam(item.slot, item.team))}</td>
      <td>${item.shots ?? 0}</td>
      <td>${item.reloads ?? 0}</td>
      <td>${item.hits ?? t("misc.empty")}</td>
      <td>${item.kills ?? t("misc.empty")}</td>
      <td>${escapeHtml(formatPercent(item.accuracy_percent))}</td>
      <td>${escapeHtml(item.connection_state || t("misc.empty"))}</td>
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
    gameSummaryPill.textContent = t("status.noFinishedRound");
    gameSummaryPill.classList.add("error");
    return;
  }

  const totals = snapshot.totals || {};
  const totalsText = t("round.totals", {
    shots: totals.shots ?? 0,
    reloads: totals.reloads ?? 0,
    hits: totals.hits ?? t("misc.empty"),
    kills: totals.kills ?? t("misc.empty"),
  });

  if (snapshot.running) {
    gameSummaryPill.textContent = t("round.summary.running", { totals: totalsText });
  } else {
    const reason = formatEndReason(snapshot.end_reason);
    gameSummaryPill.textContent = t("round.summary.ended", {
      reason,
      totals: totalsText,
    });
  }
  gameSummaryPill.classList.remove("error");

  for (const item of slotStats) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.slot ?? t("misc.empty")}</td>
      <td>${escapeHtml(item.display_name || item.address || t("misc.empty"))}</td>
      <td>${escapeHtml(formatTeam(item.slot, item.team))}</td>
      <td>${item.hits ?? t("misc.empty")}</td>
      <td>${item.kills ?? t("misc.empty")}</td>
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
      <td>${escapeHtml(conn.display_name || conn.local_name || conn.name || t("state.unknown"))}</td>
      <td>${escapeHtml(conn.address)}</td>
      <td>${escapeHtml(formatTeam(conn.assigned_slot, conn.assigned_team))}</td>
      <td>${escapeHtml(formatLinkState(conn))}</td>
      <td>${escapeHtml(tsToLocal(conn.connected_at))}</td>
      <td><button type="button" data-address="${escapeHtml(conn.address)}">${escapeHtml(t("button.disconnect"))}</button></td>
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
    pushLiveLine(
      `${ts} ${t("live.connected", { address: conn.address || t("misc.empty") })}`
    );
    refreshConnections().catch((err) => {
      reportError(err, { contextKey: "context.liveConnection", dedupeMs: 10000 });
    });
    return;
  }

  if (payload.action === "disconnected") {
    removeLiveEntry(payload.address);
    pushLiveLine(
      `${ts} ${t("live.disconnected", { address: payload.address || t("misc.empty") })}`
    );
    refreshConnections().catch((err) => {
      reportError(err, { contextKey: "context.liveConnection", dedupeMs: 10000 });
    });
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
  pushLiveLine(
    `${ts} ${t("live.connectionAction", {
      address: payload.address || t("misc.empty"),
      action: payload.action || t("state.connectionActionFallback"),
    })}`
  );
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
    pushLiveLine(
      `${ts} ${t("live.notification", {
        address: payload.address || t("misc.empty"),
        raw: notif.raw || "",
        decoded: notif.decoded || "",
      })}`
    );
    return;
  }

  if (eventType === "connection") {
    handleConnectionEvent(payload, ts);
    return;
  }

  if (eventType === "game_session") {
    pushLiveLine(
      `${ts} ${t("live.roundAction", {
        action: payload.action || t("state.roundActionFallback"),
      })}`
    );
    refreshRanking().catch((err) => {
      reportError(err, { contextKey: "context.liveRanking", dedupeMs: 10000 });
    });
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
    refreshConnections().catch((err) => {
      reportError(err, { contextKey: "context.liveConnection", dedupeMs: 10000 });
    });
    pushLiveLine(
      `${ts} ${t("live.localNameUpdated", { address: conn.address || t("misc.empty") })}`
    );
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
    setStatus(t("status.apiReachable"), true);
  } catch (err) {
    setStatus(t("status.apiUnreachable"), false);
    reportError(err, { contextKey: "context.apiHealthcheck", dedupeMs: 15000 });
  }
}

function openLiveStream() {
  if (liveSource) {
    liveSource.close();
    liveSource = null;
  }

  setLiveState(t("status.liveConnecting"), true);
  liveSource = new EventSource("/api/live/stream");

  liveSource.addEventListener("open", () => {
    setLiveState(t("status.liveConnected"), true);
  });

  liveSource.addEventListener("snapshot", (event) => {
    try {
      const payload = JSON.parse(event.data);
      handleLiveSnapshot(payload);
      pushLiveLine(`${tsToClock(payload.generated_at)} ${t("live.snapshot")}`);
      refreshRanking().catch((err) => {
        reportError(err, { contextKey: "context.liveRanking", dedupeMs: 10000 });
      });
    } catch (err) {
      reportError(err, { contextKey: "context.liveStream", dedupeMs: 10000 });
    }
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
      } catch (err) {
        reportError(err, { contextKey: "context.liveStream", dedupeMs: 10000 });
      }
    });
  }

  liveSource.onerror = () => {
    setLiveState(t("status.liveRetrying"), false);
    reportError(new Error(t("error.liveReconnectInProgress")), {
      contextKey: "context.liveStream",
      dedupeMs: 15000,
    });
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
      <td><button type="button" data-address="${escapeHtml(dev.address)}">${escapeHtml(t("button.connect"))}</button></td>
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

async function enableBluetooth() {
  return api("/api/bluetooth/enable", {
    method: "POST",
    body: JSON.stringify({}),
  });
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
  const requestedCount = Number(result?.result?.requested_count ?? 0);
  const startedCount = Number(result?.result?.started_count ?? 0);
  const failureCount = Number(result?.result?.failure_count ?? 0);
  if (requestedCount >= 2 && startedCount < 2 && failureCount > 0) {
    const failures = Array.isArray(result?.result?.failures) ? result.result.failures : [];
    const first = failures[0];
    const detail = first
      ? `${first.address || "?"}: ${first.error || t("error.unknown")}`
      : t("error.unknown");
    const err = new Error(detail);
    err.status = 409;
    err.detail = detail;
    throw err;
  }
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
  const delay = Number(document.getElementById("game-delay").value || 0);
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
    notificationsBox.textContent = t("error.noTargetAddressSet");
    return { items: [] };
  }
  const result = await api(`/api/notifications/${encodeURIComponent(address)}`);
  const lines = (result.items || []).map((item) => {
    const time = new Date(item.ts * 1000).toLocaleTimeString(currentLanguage);
    return `${time}  ${item.raw}  ${item.decoded}`;
  });
  notificationsBox.textContent = lines.join("\n");
  return result;
}

async function runAction(fn, options = {}) {
  const button = options.button || null;
  const busyText = options.busyText || null;
  const contextKey = options.contextKey || "context.action";
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
    reportError(err, { contextKey });
    setResponse(errorPayload(err, contextKey));
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
    refreshConnections().catch((err) => {
      reportError(err, { contextKey: "context.viewSetup", dedupeMs: 10000 });
    });
  }
  if (view === "game") {
    refreshRanking().catch((err) => {
      reportError(err, { contextKey: "context.viewGame", dedupeMs: 10000 });
    });
  }
}

function bindClick(id, handler) {
  const el = document.getElementById(id);
  if (!el) return;
  el.addEventListener("click", handler);
}

if (scanButton) {
  scanButton.addEventListener("click", () => {
    runAction(scan, {
      button: scanButton,
      busyText: t("button.scanning"),
      contextKey: "context.deviceScan",
    });
  });
}
if (enableBluetoothButton) {
  enableBluetoothButton.addEventListener("click", () => {
    runAction(enableBluetooth, {
      button: enableBluetoothButton,
      busyText: t("button.enablingBluetooth"),
      contextKey: "context.bluetoothControl",
    });
  });
}
bindClick("btn-refresh-connections", () =>
  runAction(refreshConnections, { contextKey: "context.viewSetup" })
);
bindClick("btn-setup-start-multi", () =>
  runAction(startGameMultiSetup, { contextKey: "context.start" })
);
bindClick("btn-refresh-ranking", () =>
  runAction(refreshRanking, { contextKey: "context.liveRanking" })
);
bindClick("btn-game-end", () => runAction(endGame, { contextKey: "context.action" }));
bindClick("btn-set-auto-reconnect", () =>
  runAction(setAutoReconnect, { contextKey: "context.liveConnection" })
);
bindClick("btn-reconnect", () =>
  runAction(reconnectNow, { contextKey: "context.liveConnection" })
);
bindClick("btn-startup", () => runAction(startup, { contextKey: "context.start" }));
bindClick("btn-set-volume", () =>
  runAction(setVolume, { contextKey: "context.action" })
);
bindClick("btn-set-team", () =>
  runAction(setTeamProfile, { contextKey: "context.action" })
);
bindClick("btn-game-start", () => runAction(startGame, { contextKey: "context.start" }));
bindClick("btn-game-start-multi", () =>
  runAction(startGameMultiAdmin, { contextKey: "context.start" })
);
bindClick("btn-game-end-admin", () =>
  runAction(endGame, { contextKey: "context.action" })
);
bindClick("btn-poll-status", () =>
  runAction(pollStatus, { contextKey: "context.action" })
);
bindClick("btn-close-session", () =>
  runAction(closeSession, { contextKey: "context.action" })
);
bindClick("btn-refresh-notifications", () =>
  runAction(refreshNotifications, { contextKey: "context.notifications" })
);
if (clearErrorsButton) {
  clearErrorsButton.addEventListener("click", () => clearErrors());
}

if (languageSelect) {
  languageSelect.addEventListener("change", async () => {
    try {
      await loadLanguage(languageSelect.value);
    } catch (_err) {
      try {
        await loadLanguage(DEFAULT_LANGUAGE);
      } catch (__err) {}
    }
    applyTranslations();
    refreshHealth().catch((err) => {
      reportError(err, { contextKey: "context.apiHealthcheck", dedupeMs: 10000 });
    });
    refreshConnections().catch((err) => {
      reportError(err, { contextKey: "context.viewSetup", dedupeMs: 10000 });
    });
    refreshRanking().catch((err) => {
      reportError(err, { contextKey: "context.liveRanking", dedupeMs: 10000 });
    });
    refreshNotifications().catch((err) => {
      reportError(err, { contextKey: "context.notifications", dedupeMs: 10000 });
    });
  });
}

for (const viewButton of document.querySelectorAll(".tab-btn")) {
  viewButton.addEventListener("click", () => {
    activateView(viewButton.dataset.viewTarget);
  });
}

setInterval(() => {
  const auto = document.getElementById("auto-refresh")?.checked;
  if (!auto) return;
  refreshNotifications().catch((err) => {
    reportError(err, { contextKey: "context.autoRefreshNotifications", dedupeMs: 15000 });
  });
}, 2000);

setInterval(() => {
  if (currentView !== "game") return;
  refreshRanking().catch((err) => {
    reportError(err, { contextKey: "context.autoRefreshRanking", dedupeMs: 15000 });
  });
}, 1500);

async function bootstrap() {
  const preferredLanguage = detectLanguage();
  try {
    await loadLanguage(preferredLanguage);
  } catch (_err) {
    try {
      await loadLanguage(DEFAULT_LANGUAGE);
    } catch (__err) {}
  }
  applyTranslations();
  setStatus(t("status.apiUnknown"), true);
  setLiveState(t("status.liveOff"), true);
  refreshHealth().catch((err) => {
    reportError(err, { contextKey: "context.apiHealthcheck", dedupeMs: 10000 });
  });
  runAction(refreshConnections, { contextKey: "context.viewSetup" });
  runAction(refreshRanking, { contextKey: "context.liveRanking" });
  openLiveStream();
  activateView("setup");
}

bootstrap().catch((err) => {
  reportError(err, { contextKey: "context.action" });
  setResponse(errorPayload(err, "context.action"));
});

window.addEventListener("beforeunload", () => {
  if (liveSource) liveSource.close();
});
