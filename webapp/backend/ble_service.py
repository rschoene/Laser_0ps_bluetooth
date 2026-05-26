from __future__ import annotations

import asyncio
import copy
import json
import re
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine

from bleak import BleakScanner

from scripts.laserops import (
    LaserOpsDevice,
    RoundSlotStatsReply,
    decode_notification,
    scan_for_devices,
)

MAC_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$")
SAFE_LEVEL_MIN = 1
SAFE_LEVEL_MAX = 5
SAFE_NAME_INDEX_MIN = 0
SAFE_NAME_INDEX_MAX = 49
SAFE_SLOT_MIN = 2
SAFE_SLOT_MAX = 5
SAFE_TEAM_MIN = 0
SAFE_TEAM_MAX = 2
# Test 12 (all-vs-all) shows team id 0x02 for all participants.
SAFE_MULTIPLAYER_FFA_TEAM = 2
SAFE_GAME_DELAY_MIN = 0.00
SAFE_GAME_DELAY_MAX = 0.30
SAFE_MULTI_START_MAX_DEVICES = 4
SAFE_MULTI_RECONNECT_TIMEOUT = 8.0
SAFE_STARTUP_VOLUME_DEFAULT = 0
SAFE_GAME_DURATION_SECONDS_DEFAULT = 300
SAFE_GAME_DURATION_SECONDS_MIN = 30
SAFE_GAME_DURATION_SECONDS_MAX = 3600
LIVE_SUBSCRIBER_QUEUE_SIZE = 500
RECONNECT_SCAN_TIMEOUT = 15.0
RECONNECT_MAX_ATTEMPTS = 12
RECONNECT_BASE_DELAY = 1.0
RECONNECT_MAX_DELAY = 15.0
LOCAL_NAME_MAX_LENGTH = 32
LOCAL_NAME_STORE_FILENAME = "local_names.json"


def _snapshot_to_dict(snapshot: Any) -> dict[str, Any]:
    return {
        "level": snapshot.level,
        "name_a": snapshot.name_a,
        "name_b": snapshot.name_b,
        "raw": snapshot.raw.hex(),
    }


@dataclass
class ConnectionState:
    address: str
    name: str
    gun: LaserOpsDevice
    ble_device: Any
    connected_at: float = field(default_factory=time.time)
    notifications: deque[dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=250)
    )
    op_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_snapshot: dict[str, Any] | None = None
    last_game_start_at: float | None = None
    local_name: str | None = None
    assigned_slot: int | None = None
    assigned_team: int | None = None
    connection_state: str = "connected"
    desired_connected: bool = True
    auto_reconnect: bool = True
    reconnect_attempts: int = 0
    reconnect_count: int = 0
    disconnect_count: int = 0
    last_disconnect_at: float | None = None
    last_reconnect_at: float | None = None
    last_disconnect_reason: str | None = None
    last_error: str | None = None
    reconnect_task: asyncio.Task | None = None
    reconnect_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    live_state: dict[str, Any] = field(
        default_factory=lambda: {
            "last_event": None,
            "last_event_ts": None,
            "last_raw": None,
            "trigger_count": 0,
            "reload_count": 0,
            "stats_terminal_count": 0,
            "last_status_word": None,
            "last_ammo_family": None,
            "last_ammo_counter": None,
            "last_reload_variant": None,
            "last_stat_type": None,
            "last_stat_counter": None,
            "startup_level": None,
            "startup_name_a": None,
            "startup_name_b": None,
        }
    )

    def on_notification(self, payload: bytes) -> dict[str, Any]:
        ts = time.time()
        decoded = decode_notification(payload)
        item = {"ts": ts, "raw": payload.hex(), "decoded": decoded}
        self.notifications.append(item)
        self._update_live_state(payload=payload, decoded=decoded, ts=ts)
        return item

    def live_state_snapshot(self) -> dict[str, Any]:
        return copy.deepcopy(self.live_state)

    def _update_live_state(self, *, payload: bytes, decoded: str, ts: float) -> None:
        state = self.live_state
        state["last_event"] = decoded
        state["last_event_ts"] = ts
        state["last_raw"] = payload.hex()

        if payload == b"\x49":
            state["trigger_count"] += 1
            return
        if payload == b"\x52":
            state["reload_count"] += 1
            return
        if payload in (bytes.fromhex("310a"), bytes.fromhex("310d")):
            state["last_reload_variant"] = payload[1]
            return
        if len(payload) == 13 and payload[:1] == b"\x35":
            state["startup_level"] = payload[8]
            state["startup_name_a"] = payload[9]
            state["startup_name_b"] = payload[10]
            return
        if len(payload) == 3 and payload[:1] == b"\x51":
            state["last_status_word"] = (payload[1] << 8) | payload[2]
            return
        if len(payload) >= 2 and payload[:1] == b"\x32":
            state["last_ammo_family"] = payload[1]
            state["last_ammo_counter"] = payload[-1]
            return
        if len(payload) == 5 and payload[:3] == bytes([0x30, 0x01, 0x3F]):
            state["last_stat_type"] = payload[3]
            state["last_stat_counter"] = payload[4]
            return
        if payload == bytes([0x3E, 0x01, 0x00]):
            state["stats_terminal_count"] += 1
            return


@dataclass
class GameSessionState:
    session_id: int
    started_at: float
    duration_seconds: int
    planned_end_at: float
    participant_keys: list[str]
    baseline_triggers: dict[str, int]
    baseline_reloads: dict[str, int]
    status: str = "running"
    ended_at: float | None = None
    end_reason: str | None = None
    final_snapshot: dict[str, Any] | None = None
    final_slot_stats: dict[int, dict[str, int]] = field(default_factory=dict)


class BleHub:
    def __init__(self) -> None:
        self._connections: dict[str, ConnectionState] = {}
        self._connections_lock = asyncio.Lock()
        self._discovery_lock = asyncio.Lock()
        self._bulk_game_start_lock = asyncio.Lock()
        self._local_name_store_path = (
            Path(__file__).resolve().parent / "state" / LOCAL_NAME_STORE_FILENAME
        )
        self._local_names: dict[str, str] = self._load_local_name_store()
        self._local_names_lock = asyncio.Lock()
        self._game_session_lock = asyncio.Lock()
        self._game_session: GameSessionState | None = None
        self._game_session_counter = 0
        self._game_end_task: asyncio.Task | None = None
        self._game_end_session_id: int | None = None
        self._event_seq = 0
        self._next_subscriber_id = 1
        self._subscribers: dict[int, asyncio.Queue[dict[str, Any]]] = {}
        self._subscribers_lock = asyncio.Lock()
        self._background_tasks: set[asyncio.Task] = set()

    async def scan(
        self,
        *,
        timeout: float,
        by_name: bool,
        name: str,
        expected_count: int,
    ) -> list[dict[str, Any]]:
        if self._discovery_lock.locked():
            raise ValueError("bluetooth discovery already running; please wait")
        async with self._discovery_lock:
            try:
                devices = await scan_for_devices(
                    timeout=timeout,
                    name_filter=name,
                    use_service_uuid=not by_name,
                    expected_count=expected_count if expected_count > 0 else None,
                )
            except Exception as exc:
                text = str(exc)
                if (
                    "org.bluez.Error.InProgress" in text
                    or "Operation already in progress" in text
                ):
                    raise ValueError(
                        "bluetooth scan already in progress on host; wait and retry"
                    ) from exc
                raise
        result: list[dict[str, Any]] = []
        for dev in devices:
            result.append(
                {
                    "address": dev.address,
                    "name": dev.name or "unknown",
                    "rssi": getattr(dev, "rssi", None),
                }
            )
        return result

    async def connect(self, address: str, timeout: float) -> dict[str, Any]:
        normalized = self._normalize_address(address)
        key = normalized.lower()
        async with self._connections_lock:
            if key in self._connections:
                raise ValueError(f"device already connected: {address}")

        async with self._discovery_lock:
            ble_dev = await BleakScanner.find_device_by_address(
                normalized, timeout=timeout
            )
        if ble_dev is None:
            raise LookupError(f"device not found: {address}")

        placeholder = ConnectionState(
            address=ble_dev.address,
            name=ble_dev.name or "unknown",
            gun=None,  # type: ignore[arg-type]
            ble_device=ble_dev,
        )
        async with self._local_names_lock:
            placeholder.local_name = self._local_names.get(key)
        notification_cb, disconnected_cb = self._build_device_callbacks(placeholder)
        gun = LaserOpsDevice(
            ble_dev,
            notification_callback=notification_cb,
            disconnected_callback=disconnected_cb,
        )
        await gun.__aenter__()
        placeholder.gun = gun
        placeholder.connection_state = "connected"
        placeholder.desired_connected = True
        placeholder.last_reconnect_at = time.time()
        placeholder.last_error = None

        async with self._connections_lock:
            used_slots = {
                conn.assigned_slot
                for conn in self._connections.values()
                if conn.assigned_slot is not None
            }
            slot = SAFE_SLOT_MIN
            while slot in used_slots and slot <= SAFE_SLOT_MAX:
                slot += 1
            if slot > SAFE_SLOT_MAX:
                slot = SAFE_SLOT_MIN
            placeholder.assigned_slot = slot
            placeholder.assigned_team = self._default_team_for_slot(slot)
            self._connections[key] = placeholder

        self._schedule_event(
            "connection",
            {
                "action": "connected",
                "connection": self.connection_summary(placeholder),
            },
        )
        return self.connection_summary(placeholder)

    async def disconnect(self, address: str) -> None:
        key = self._normalize_address(address).lower()
        async with self._connections_lock:
            conn = self._connections.pop(key, None)
        if conn is None:
            raise LookupError(f"device is not connected: {address}")
        conn.desired_connected = False
        conn.connection_state = "disconnected"
        conn.last_disconnect_reason = "manual_disconnect"
        conn.last_disconnect_at = time.time()
        self._cancel_reconnect_task(conn)
        await conn.gun.__aexit__(None, None, None)
        self._schedule_event(
            "connection",
            {
                "action": "disconnected",
                "address": conn.address,
                "name": conn.name,
                "local_name": conn.local_name,
                "display_name": self._display_name(conn),
            },
        )

    async def disconnect_all(self) -> None:
        async with self._connections_lock:
            items = list(self._connections.items())
            self._connections.clear()
        async with self._game_session_lock:
            self._game_session = None
        self._cancel_game_end_task()
        self._schedule_event(
            "ranking",
            self._empty_ranking_snapshot(),
        )
        for _key, conn in items:
            conn.desired_connected = False
            conn.connection_state = "disconnected"
            conn.last_disconnect_reason = "manual_disconnect_all"
            conn.last_disconnect_at = time.time()
            self._cancel_reconnect_task(conn)
            try:
                await conn.gun.__aexit__(None, None, None)
            except Exception:
                pass
            self._schedule_event(
                "connection",
                {
                    "action": "disconnected",
                    "address": conn.address,
                    "name": conn.name,
                    "local_name": conn.local_name,
                    "display_name": self._display_name(conn),
                },
            )

    async def startup(self, address: str, volume: int) -> dict[str, Any]:
        async with self._bulk_game_start_lock:
            conn = await self._get(address)
            await self._ensure_connected(conn)
            async with conn.op_lock:
                snapshot = await conn.gun.startup(volume=volume)
                conn.last_snapshot = _snapshot_to_dict(snapshot)
                self._schedule_event(
                    "startup",
                    {
                        "address": conn.address,
                        "name": conn.name,
                        "volume": volume,
                        "snapshot": conn.last_snapshot,
                        "live_state": conn.live_state_snapshot(),
                    },
                )
                return conn.last_snapshot

    async def set_volume(self, address: str, volume: int) -> None:
        async with self._bulk_game_start_lock:
            conn = await self._get(address)
            await self._ensure_connected(conn)
            async with conn.op_lock:
                await conn.gun.set_volume(volume)
                self._schedule_event(
                    "volume",
                    {"address": conn.address, "name": conn.name, "volume": volume},
                )

    async def write_config(
        self, address: str, level: int, name_a: int, name_b: int
    ) -> None:
        self._validate_safe_config(level=level, name_a=name_a, name_b=name_b)
        async with self._bulk_game_start_lock:
            conn = await self._get(address)
            await self._ensure_connected(conn)
            # Mirror assign_device.py behavior: UI/API provide 0-based indices,
            # payload uses (index + 1) bytes.
            name_a_byte = name_a + 1
            name_b_byte = name_b + 1
            async with conn.op_lock:
                await conn.gun.write_config(
                    level=level,
                    name_a=name_a_byte,
                    name_b=name_b_byte,
                )
                self._schedule_event(
                    "config",
                    {
                        "address": conn.address,
                        "name": conn.name,
                        "level": level,
                        "name_a": name_a,
                        "name_b": name_b,
                    },
                )

    async def set_team_profile(self, address: str, slot: int, team: int) -> dict[str, Any]:
        safe_slot, safe_team = self._validate_safe_team(slot=slot, team=team)
        async with self._bulk_game_start_lock:
            conn = await self._get(address)
            async with self._connections_lock:
                for key, other in self._connections.items():
                    if key == conn.address.lower():
                        continue
                    if other.assigned_slot == safe_slot:
                        raise ValueError(
                            f"slot {safe_slot} already assigned to {other.address}"
                        )
            conn.assigned_slot = safe_slot
            conn.assigned_team = safe_team
            summary = self.connection_summary(conn)
            self._schedule_event(
                "team_profile",
                {
                    "address": conn.address,
                    "name": conn.name,
                    "slot": safe_slot,
                    "team": safe_team,
                },
            )
            return summary

    async def set_local_name(self, address: str, local_name: str | None) -> dict[str, Any]:
        safe_local_name = self._normalize_local_name(local_name)
        async with self._bulk_game_start_lock:
            conn = await self._get(address)
            previous_local_name = conn.local_name
            conn.local_name = safe_local_name
            key = self._normalize_address(conn.address).lower()
            async with self._local_names_lock:
                previous_stored_name = self._local_names.get(key)
                if safe_local_name is None:
                    self._local_names.pop(key, None)
                else:
                    self._local_names[key] = safe_local_name
                try:
                    self._save_local_name_store()
                except Exception:
                    if previous_stored_name is None:
                        self._local_names.pop(key, None)
                    else:
                        self._local_names[key] = previous_stored_name
                    conn.local_name = previous_local_name
                    raise
            summary = self.connection_summary(conn)
            self._schedule_event(
                "local_name",
                {
                    "address": conn.address,
                    "name": conn.name,
                    "local_name": conn.local_name,
                    "display_name": self._display_name(conn),
                    "connection": summary,
                },
            )
            return summary

    async def start_game(
        self,
        address: str,
        delay: float,
        *,
        startup_volume: int = SAFE_STARTUP_VOLUME_DEFAULT,
        force_startup: bool = True,
        duration_seconds: int = SAFE_GAME_DURATION_SECONDS_DEFAULT,
        slot: int | None = None,
        team: int | None = None,
    ) -> dict[str, Any]:
        safe_delay = self._validate_safe_game_delay(delay)
        safe_duration_seconds = self._validate_game_duration(duration_seconds)
        async with self._bulk_game_start_lock:
            conn = await self._get(address)
            await self._ensure_connected(conn)
            await self._finalize_game_session(
                reason="superseded_by_new_start",
                send_close=True,
                collect_slot_stats=False,
            )
            selected_slot, selected_team = self._resolve_team_for_start(
                conn=conn,
                slot=slot,
                team=team,
            )
            snapshot, recovery_used = await self._run_multiplayer_start_sequence(
                conn=conn,
                slot=selected_slot,
                team=selected_team,
                startup_volume=startup_volume,
                delay=safe_delay,
                duration_seconds=safe_duration_seconds,
            )
            conn.last_snapshot = _snapshot_to_dict(snapshot)
            startup_performed = True
            conn.last_game_start_at = time.time()
            self._schedule_event(
                "game_start",
                {
                    "address": conn.address,
                    "name": conn.name,
                    "startup_performed": startup_performed,
                    "force_startup": force_startup,
                    "delay": safe_delay,
                    "duration_seconds": safe_duration_seconds,
                    "slot": selected_slot,
                    "team": selected_team,
                    "local_name": conn.local_name,
                    "display_name": self._display_name(conn),
                    "game_start_at": conn.last_game_start_at,
                    "recovery_used": recovery_used,
                },
            )
            ranking_snapshot = await self._start_game_session(
                [conn],
                duration_seconds=safe_duration_seconds,
            )
            return {
                "address": conn.address,
                "name": conn.name,
                "local_name": conn.local_name,
                "display_name": self._display_name(conn),
                "startup_performed": startup_performed,
                "last_snapshot": conn.last_snapshot,
                "slot": selected_slot,
                "team": selected_team,
                "duration_seconds": safe_duration_seconds,
                "game_start_at": conn.last_game_start_at,
                "recovery_used": recovery_used,
                "ranking": ranking_snapshot,
            }

    async def start_game_multi(
        self,
        *,
        addresses: list[str] | None,
        startup_volume: int,
        delay: float,
        force_startup: bool,
        duration_seconds: int = SAFE_GAME_DURATION_SECONDS_DEFAULT,
    ) -> dict[str, Any]:
        safe_delay = self._validate_safe_game_delay(delay)
        safe_duration_seconds = self._validate_game_duration(duration_seconds)
        async with self._bulk_game_start_lock:
            requested_conns = await self._resolve_connections(addresses)
            if len(requested_conns) < 2:
                raise ValueError("multiplayer start requires at least 2 connected blasters")
            reconnect_errors: dict[str, str] = {}
            for conn in requested_conns:
                if conn.gun.is_connected or not conn.desired_connected:
                    continue
                try:
                    await self._ensure_connected(
                        conn,
                        timeout=SAFE_MULTI_RECONNECT_TIMEOUT,
                    )
                except Exception as exc:
                    reconnect_errors[conn.address.lower()] = self._format_error(exc)

            connected_for_start = [conn for conn in requested_conns if conn.gun.is_connected]
            disconnected_conns = [conn for conn in requested_conns if not conn.gun.is_connected]
            await self._finalize_game_session(
                reason="superseded_by_new_start",
                send_close=True,
                collect_slot_stats=False,
            )

            if len(requested_conns) > SAFE_MULTI_START_MAX_DEVICES:
                raise ValueError(
                    f"too many devices for one synchronized start "
                    f"({len(requested_conns)} > {SAFE_MULTI_START_MAX_DEVICES})"
                )
            busy = [conn.address for conn in requested_conns if conn.op_lock.locked()]
            if busy:
                raise ValueError(
                    "devices are busy; retry after current operation: "
                    + ", ".join(busy)
                )

            team_profiles = self._resolve_multi_team_profiles(requested_conns)
            prepared = [
                {
                    "address": conn.address,
                    "startup_performed": True,
                    "force_startup": bool(force_startup),
                    "slot": team_profiles[conn.address.lower()][0],
                    "team": team_profiles[conn.address.lower()][1],
                }
                for conn in requested_conns
            ]

            failures: list[dict[str, str]] = [
                {
                    "address": conn.address,
                    "error": reconnect_errors.get(
                        conn.address.lower(),
                        (
                            "ConnectionError: device not connected at multi-start "
                            f"(state={conn.connection_state})"
                        ),
                    ),
                }
                for conn in disconnected_conns
            ]
            started: list[dict[str, Any]] = []
            # Match observed multiplayer sequence per blaster:
            # 49 -> 4a -> 5b -> 35(snapshot) -> 58
            # Run each blaster sequence concurrently so all devices are ready quickly.
            tasks = [
                asyncio.create_task(
                    self._start_one_multi_connection(
                        conn=conn,
                        slot=team_profiles[conn.address.lower()][0],
                        team=team_profiles[conn.address.lower()][1],
                        startup_volume=startup_volume,
                        delay=safe_delay,
                        duration_seconds=safe_duration_seconds,
                        force_startup=force_startup,
                    )
                )
                for conn in connected_for_start
            ]
            if tasks:
                results = await asyncio.gather(*tasks)
                for started_item, failure_item in results:
                    if failure_item is not None:
                        failures.append(failure_item)
                        continue
                    if started_item is not None:
                        started.append(started_item)

            ranking_snapshot: dict[str, Any] | None = None
            if len(started) >= 2:
                started_keys = {item["address"].lower() for item in started}
                started_conns = [
                    conn
                    for conn in requested_conns
                    if conn.address.lower() in started_keys
                ]
                ranking_snapshot = await self._start_game_session(
                    started_conns,
                    duration_seconds=safe_duration_seconds,
                )
            else:
                ranking_snapshot = await self.game_ranking()

            return {
                "requested_count": len(requested_conns),
                "prepared_count": len(prepared),
                "started_count": len(started),
                "failure_count": len(failures),
                "aborted": bool((len(started) < 2) and failures),
                "duration_seconds": safe_duration_seconds,
                "prepared": prepared,
                "started": started,
                "failures": failures,
                "ranking": ranking_snapshot,
            }

    async def poll_status(self, address: str) -> str:
        async with self._bulk_game_start_lock:
            conn = await self._get(address)
            await self._ensure_connected(conn)
            async with conn.op_lock:
                payload = await conn.gun.poll_status()
                return payload.hex()

    async def collect_stats(self, address: str) -> list[dict[str, Any]]:
        raise ValueError(
            "legacy stats command is disabled in safe mode "
            "(uses damage-related protocol traffic)"
        )

    async def close_session(self, address: str) -> None:
        async with self._bulk_game_start_lock:
            conn = await self._get(address)
            await self._ensure_connected(conn)
            async with conn.op_lock:
                await conn.gun.close_session()

    async def end_game(self, reason: str = "manual_stop") -> dict[str, Any]:
        async with self._bulk_game_start_lock:
            return await self._finalize_game_session(
                reason=self._sanitize_end_reason(reason),
                send_close=True,
            )

    async def reconnect(
        self, address: str, timeout: float = RECONNECT_SCAN_TIMEOUT
    ) -> dict[str, Any]:
        async with self._bulk_game_start_lock:
            conn = await self._get(address)
            conn.desired_connected = True
            await self._reconnect_once(conn, timeout=timeout)
            return self.connection_summary(conn)

    async def set_auto_reconnect(self, address: str, enabled: bool) -> dict[str, Any]:
        async with self._bulk_game_start_lock:
            conn = await self._get(address)
            conn.auto_reconnect = bool(enabled)
            if not conn.auto_reconnect:
                self._cancel_reconnect_task(conn)
            elif conn.desired_connected and not conn.gun.is_connected:
                self._start_reconnect_task(conn)
            self._schedule_event(
                "connection",
                {
                    "action": "auto_reconnect_changed",
                    "address": conn.address,
                    "name": conn.name,
                    "local_name": conn.local_name,
                    "display_name": self._display_name(conn),
                    "enabled": conn.auto_reconnect,
                },
            )
            return self.connection_summary(conn)

    async def game_ranking(self) -> dict[str, Any]:
        async with self._game_session_lock:
            session = self._game_session
            if session is None:
                return self._empty_ranking_snapshot()
            if session.final_snapshot is not None:
                return copy.deepcopy(session.final_snapshot)
            session_copy = copy.deepcopy(session)

        async with self._connections_lock:
            active_connections = dict(self._connections)
        return self._build_session_snapshot(
            session=session_copy,
            active_connections=active_connections,
            running=session_copy.status == "running",
        )

    async def notifications(self, address: str) -> list[dict[str, Any]]:
        conn = await self._get(address)
        return list(conn.notifications)

    async def list_connections(self) -> list[dict[str, Any]]:
        async with self._connections_lock:
            conns = list(self._connections.values())
        return [self.connection_summary(conn) for conn in conns]

    def connection_summary(self, conn: ConnectionState) -> dict[str, Any]:
        return {
            "address": conn.address,
            "name": conn.name,
            "local_name": conn.local_name,
            "display_name": self._display_name(conn),
            "connected_at": conn.connected_at,
            "last_snapshot": conn.last_snapshot,
            "last_game_start_at": conn.last_game_start_at,
            "assigned_slot": conn.assigned_slot,
            "assigned_team": conn.assigned_team,
            "connection_state": conn.connection_state,
            "auto_reconnect": conn.auto_reconnect,
            "reconnect_attempts": conn.reconnect_attempts,
            "reconnect_count": conn.reconnect_count,
            "disconnect_count": conn.disconnect_count,
            "last_disconnect_at": conn.last_disconnect_at,
            "last_reconnect_at": conn.last_reconnect_at,
            "last_disconnect_reason": conn.last_disconnect_reason,
            "last_error": conn.last_error,
            "notification_count": len(conn.notifications),
            "live_state": conn.live_state_snapshot(),
        }

    async def shutdown(self) -> None:
        await self.disconnect_all()
        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()

    async def _get(self, address: str) -> ConnectionState:
        key = self._normalize_address(address).lower()
        async with self._connections_lock:
            conn = self._connections.get(key)
        if conn is None:
            raise LookupError(f"device is not connected: {address}")
        return conn

    async def _resolve_connections(
        self, addresses: list[str] | None
    ) -> list[ConnectionState]:
        if addresses:
            normalized = [self._normalize_address(addr).lower() for addr in addresses]
            if len(normalized) != len(set(normalized)):
                raise ValueError("duplicate addresses in multi-start request")
            selected = []
            async with self._connections_lock:
                for key in normalized:
                    conn = self._connections.get(key)
                    if conn is None:
                        raise LookupError(f"device is not connected: {key}")
                    selected.append(conn)
            return sorted(selected, key=lambda x: x.address.lower())

        async with self._connections_lock:
            selected = list(self._connections.values())
        if not selected:
            raise LookupError("no connected devices")
        return sorted(selected, key=lambda x: x.address.lower())

    def _normalize_address(self, address: str) -> str:
        normalized = address.strip()
        if not MAC_RE.fullmatch(normalized):
            raise ValueError(f"invalid BLE address format: {address}")
        return normalized.replace("-", ":").lower()

    def _build_device_callbacks(
        self, conn: ConnectionState
    ) -> tuple[Callable[[bytes], None], Callable[[], None]]:
        def _on_notification(payload: bytes) -> None:
            item = conn.on_notification(payload)
            self._schedule_event(
                "notification",
                {
                    "address": conn.address,
                    "name": conn.name,
                    "local_name": conn.local_name,
                    "display_name": self._display_name(conn),
                    "notification": item,
                    "live_state": conn.live_state_snapshot(),
                },
            )
            if payload in (b"\x49", b"\x52"):
                self._spawn_background(
                    self._publish_ranking_if_running(conn.address.lower())
                )

        def _on_disconnected() -> None:
            self._spawn_background(
                self._handle_unexpected_disconnect(
                    conn=conn,
                    reason="link_lost",
                )
            )

        return _on_notification, _on_disconnected

    async def _handle_unexpected_disconnect(
        self, *, conn: ConnectionState, reason: str
    ) -> None:
        if not conn.desired_connected:
            return
        conn.connection_state = "disconnected"
        conn.disconnect_count += 1
        conn.last_disconnect_at = time.time()
        conn.last_disconnect_reason = reason
        self._schedule_event(
            "connection",
            {
                "action": "lost",
                "address": conn.address,
                "name": conn.name,
                "local_name": conn.local_name,
                "display_name": self._display_name(conn),
                "connection_state": conn.connection_state,
                "reason": reason,
                "disconnect_count": conn.disconnect_count,
            },
        )
        if not conn.auto_reconnect:
            return
        self._start_reconnect_task(conn)

    def _start_reconnect_task(self, conn: ConnectionState) -> None:
        task = conn.reconnect_task
        if task is not None and not task.done():
            return
        conn.reconnect_task = self._spawn_background(self._reconnect_loop(conn))

    def _cancel_reconnect_task(self, conn: ConnectionState) -> None:
        task = conn.reconnect_task
        conn.reconnect_task = None
        if task is not None and not task.done():
            task.cancel()

    async def _reconnect_loop(self, conn: ConnectionState) -> None:
        delay = RECONNECT_BASE_DELAY
        attempts = 0
        while conn.desired_connected and conn.auto_reconnect:
            if conn.gun.is_connected:
                conn.connection_state = "connected"
                return
            attempts += 1
            if attempts > RECONNECT_MAX_ATTEMPTS:
                conn.last_error = "reconnect attempts exceeded"
                self._schedule_event(
                    "connection",
                    {
                        "action": "reconnect_giveup",
                        "address": conn.address,
                        "name": conn.name,
                        "local_name": conn.local_name,
                        "display_name": self._display_name(conn),
                        "attempts": attempts - 1,
                    },
                )
                return
            try:
                await self._reconnect_once(conn, timeout=RECONNECT_SCAN_TIMEOUT)
                return
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                conn.last_error = str(exc)
                self._schedule_event(
                    "connection",
                    {
                        "action": "reconnect_failed",
                        "address": conn.address,
                        "name": conn.name,
                        "local_name": conn.local_name,
                        "display_name": self._display_name(conn),
                        "attempt": attempts,
                        "error": str(exc),
                    },
                )
            await asyncio.sleep(delay)
            delay = min(RECONNECT_MAX_DELAY, max(RECONNECT_BASE_DELAY, delay * 1.8))

    async def _ensure_connected(
        self,
        conn: ConnectionState,
        *,
        timeout: float = RECONNECT_SCAN_TIMEOUT,
    ) -> None:
        if conn.gun.is_connected:
            conn.connection_state = "connected"
            return
        if not conn.desired_connected:
            raise ConnectionError("device is disconnected by user request")
        await self._reconnect_once(conn, timeout=timeout)

    async def _reconnect_once(self, conn: ConnectionState, timeout: float) -> None:
        async with conn.reconnect_lock:
            if not conn.desired_connected:
                raise ConnectionError("reconnect blocked: desired_connected is false")
            if conn.gun.is_connected:
                conn.connection_state = "connected"
                return
            conn.connection_state = "reconnecting"
            conn.reconnect_attempts += 1
            self._schedule_event(
                "connection",
                {
                    "action": "reconnect_attempt",
                    "address": conn.address,
                    "name": conn.name,
                    "local_name": conn.local_name,
                    "display_name": self._display_name(conn),
                    "attempt": conn.reconnect_attempts,
                },
            )

            reconnect_candidates: list[Any] = []
            if conn.ble_device is not None:
                reconnect_candidates.append(conn.ble_device)

            scanned_device = None
            async with self._discovery_lock:
                scanned_device = await BleakScanner.find_device_by_address(
                    conn.address,
                    timeout=timeout,
                )
            if scanned_device is not None:
                reconnect_candidates.append(scanned_device)

            if not reconnect_candidates:
                conn.connection_state = "disconnected"
                conn.last_error = f"device not found during reconnect: {conn.address}"
                raise LookupError(conn.last_error)

            old_gun = conn.gun
            notification_cb, disconnected_cb = self._build_device_callbacks(conn)
            new_gun = None
            last_exc: Exception | None = None
            used_device = None
            for candidate in reconnect_candidates:
                trial_gun = LaserOpsDevice(
                    candidate,
                    notification_callback=notification_cb,
                    disconnected_callback=disconnected_cb,
                )
                try:
                    await trial_gun.__aenter__()
                except Exception as exc:
                    last_exc = exc
                    try:
                        await trial_gun.__aexit__(None, None, None)
                    except Exception:
                        pass
                    continue
                new_gun = trial_gun
                used_device = candidate
                break

            if new_gun is None:
                conn.connection_state = "disconnected"
                conn.last_error = str(last_exc) if last_exc is not None else (
                    f"reconnect failed: {conn.address}"
                )
                if last_exc is not None:
                    raise last_exc
                raise ConnectionError(conn.last_error)

            conn.gun = new_gun
            conn.ble_device = used_device
            conn.connection_state = "connected"
            conn.last_reconnect_at = time.time()
            conn.reconnect_count += 1
            conn.last_error = None
            self._cancel_reconnect_task(conn)
            try:
                await old_gun.__aexit__(None, None, None)
            except Exception:
                pass
            self._schedule_event(
                "connection",
                {
                    "action": "reconnected",
                    "address": conn.address,
                    "name": conn.name,
                    "local_name": conn.local_name,
                    "display_name": self._display_name(conn),
                    "connection_state": conn.connection_state,
                    "reconnect_count": conn.reconnect_count,
                },
            )

    async def _start_game_session(
        self,
        participants: list[ConnectionState],
        *,
        duration_seconds: int,
    ) -> dict[str, Any]:
        safe_duration = self._validate_game_duration(duration_seconds)
        participant_keys = sorted({conn.address.lower() for conn in participants})
        baseline_triggers: dict[str, int] = {}
        baseline_reloads: dict[str, int] = {}
        for conn in participants:
            key = conn.address.lower()
            baseline_triggers[key] = int(conn.live_state.get("trigger_count", 0) or 0)
            baseline_reloads[key] = int(conn.live_state.get("reload_count", 0) or 0)

        started_at = time.time()
        planned_end_at = started_at + float(safe_duration)

        self._cancel_game_end_task()
        async with self._game_session_lock:
            self._game_session_counter += 1
            session_id = self._game_session_counter
            self._game_session = GameSessionState(
                session_id=session_id,
                started_at=started_at,
                duration_seconds=safe_duration,
                planned_end_at=planned_end_at,
                participant_keys=participant_keys,
                baseline_triggers=baseline_triggers,
                baseline_reloads=baseline_reloads,
            )

        self._arm_game_end_task(session_id=session_id, planned_end_at=planned_end_at)
        ranking_snapshot = await self.game_ranking()
        self._schedule_event("ranking", ranking_snapshot)
        self._schedule_event(
            "game_session",
            {
                "action": "started",
                "session_id": session_id,
                "started_at": started_at,
                "duration_seconds": safe_duration,
                "planned_end_at": planned_end_at,
                "participants": ranking_snapshot.get("participants", []),
            },
        )
        return ranking_snapshot

    async def _publish_ranking_if_running(self, address_key: str) -> None:
        snapshot = await self.game_ranking()
        if not snapshot.get("running"):
            return
        participants = {str(item).lower() for item in snapshot.get("participants", [])}
        if address_key not in participants:
            return
        await self._publish_event(event_type="ranking", payload=snapshot)

    def _arm_game_end_task(self, *, session_id: int, planned_end_at: float) -> None:
        self._cancel_game_end_task()
        self._game_end_session_id = session_id
        self._game_end_task = self._spawn_background(
            self._auto_end_game_session(
                session_id=session_id,
                planned_end_at=planned_end_at,
            )
        )

    def _cancel_game_end_task(self) -> None:
        task = self._game_end_task
        self._game_end_task = None
        self._game_end_session_id = None
        if task is not None and not task.done():
            task.cancel()

    async def _auto_end_game_session(
        self,
        *,
        session_id: int,
        planned_end_at: float,
    ) -> None:
        delay = max(0.0, float(planned_end_at - time.time()))
        if delay > 0:
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                return
        try:
            async with self._bulk_game_start_lock:
                await self._finalize_game_session(
                    reason="duration_elapsed",
                    send_close=True,
                    expected_session_id=session_id,
                )
        except asyncio.CancelledError:
            return
        except Exception:
            # Keep timer failures isolated; live gameplay must continue.
            return

    async def _finalize_game_session(
        self,
        *,
        reason: str,
        send_close: bool,
        collect_slot_stats: bool = True,
        expected_session_id: int | None = None,
    ) -> dict[str, Any]:
        async with self._game_session_lock:
            session = self._game_session
            if session is None:
                return self._empty_ranking_snapshot()
            if (
                expected_session_id is not None
                and session.session_id != expected_session_id
            ):
                if session.final_snapshot is not None:
                    return copy.deepcopy(session.final_snapshot)
                return copy.deepcopy(self._empty_ranking_snapshot())
            if session.final_snapshot is not None:
                return copy.deepcopy(session.final_snapshot)
            session.status = "ending"
            session_copy = copy.deepcopy(session)

        async with self._connections_lock:
            active_connections = dict(self._connections)
        participant_connections = [
            active_connections[key]
            for key in session_copy.participant_keys
            if key in active_connections
        ]

        close_failures: list[dict[str, str]] = []
        if send_close:
            for conn in participant_connections:
                if not conn.gun.is_connected:
                    continue
                try:
                    async with conn.op_lock:
                        await conn.gun.close_session()
                except Exception as exc:
                    close_failures.append(
                        {
                            "address": conn.address,
                            "error": str(exc),
                        }
                    )

        slot_stats_map: dict[int, dict[str, int]] = {}
        stats_source_address: str | None = None
        stats_error: str | None = None
        slots = sorted(
            {
                int(conn.assigned_slot)
                for conn in participant_connections
                if conn.assigned_slot is not None
            }
        )
        if collect_slot_stats and slots:
            slot_stats_map, stats_source_address, stats_error = (
                await self._collect_round_slot_stats(
                    participant_connections=participant_connections,
                    slots=tuple(slots),
                )
            )

        ended_at = time.time()
        session_copy.status = "ended"
        session_copy.ended_at = ended_at
        session_copy.end_reason = reason
        session_copy.final_slot_stats = slot_stats_map
        final_snapshot = self._build_session_snapshot(
            session=session_copy,
            active_connections=active_connections,
            running=False,
            close_failures=close_failures,
            stats_source_address=stats_source_address,
            stats_error=stats_error,
        )

        async with self._game_session_lock:
            live_session = self._game_session
            if (
                live_session is not None
                and live_session.session_id == session_copy.session_id
                and live_session.final_snapshot is None
            ):
                live_session.status = "ended"
                live_session.ended_at = ended_at
                live_session.end_reason = reason
                live_session.final_slot_stats = dict(slot_stats_map)
                live_session.final_snapshot = copy.deepcopy(final_snapshot)
                final_snapshot = copy.deepcopy(live_session.final_snapshot)
            elif live_session is not None and live_session.final_snapshot is not None:
                final_snapshot = copy.deepcopy(live_session.final_snapshot)

        if expected_session_id is None or expected_session_id == session_copy.session_id:
            self._cancel_game_end_task()
        self._schedule_event("ranking", final_snapshot)
        self._schedule_event(
            "game_session",
            {
                "action": "ended",
                "session_id": final_snapshot.get("session_id"),
                "started_at": final_snapshot.get("started_at"),
                "ended_at": final_snapshot.get("ended_at"),
                "end_reason": final_snapshot.get("end_reason"),
                "duration_seconds": final_snapshot.get("duration_seconds"),
                "participants": final_snapshot.get("participants", []),
            },
        )
        return final_snapshot

    async def _collect_round_slot_stats(
        self,
        *,
        participant_connections: list[ConnectionState],
        slots: tuple[int, ...],
    ) -> tuple[dict[int, dict[str, int]], str | None, str | None]:
        last_error: str | None = None
        for conn in participant_connections:
            if not conn.gun.is_connected:
                continue
            try:
                async with conn.op_lock:
                    replies = await conn.gun.collect_round_slot_stats(
                        slots=slots,
                        per_slot_timeout=2.5,
                    )
            except Exception as exc:
                last_error = str(exc)
                continue
            stats: dict[int, dict[str, int]] = {}
            for reply in replies:
                if not isinstance(reply, RoundSlotStatsReply):
                    continue
                stats[int(reply.slot)] = {
                    "hits": int(reply.hits),
                    "kills": int(reply.kills),
                }
            return stats, conn.address, None
        return {}, None, last_error

    def _empty_ranking_snapshot(self) -> dict[str, Any]:
        return {
            "running": False,
            "session_state": "idle",
            "session_id": None,
            "started_at": None,
            "planned_end_at": None,
            "duration_seconds": None,
            "remaining_seconds": None,
            "ended_at": None,
            "end_reason": None,
            "participants": [],
            "ranking": [],
            "slot_stats": [],
            "totals": {"shots": 0, "reloads": 0, "hits": None, "kills": None},
            "stats_source_address": None,
            "stats_error": None,
            "close_failures": [],
        }

    def _build_session_snapshot(
        self,
        *,
        session: GameSessionState,
        active_connections: dict[str, ConnectionState],
        running: bool,
        close_failures: list[dict[str, str]] | None = None,
        stats_source_address: str | None = None,
        stats_error: str | None = None,
    ) -> dict[str, Any]:
        ranking = self._build_ranking_entries(
            session=session,
            active_connections=active_connections,
        )
        totals_shots = sum(int(item.get("shots", 0) or 0) for item in ranking)
        totals_reloads = sum(int(item.get("reloads", 0) or 0) for item in ranking)
        has_hits = any(item.get("hits") is not None for item in ranking)
        has_kills = any(item.get("kills") is not None for item in ranking)
        totals_hits = (
            sum(int(item.get("hits", 0) or 0) for item in ranking) if has_hits else None
        )
        totals_kills = (
            sum(int(item.get("kills", 0) or 0) for item in ranking)
            if has_kills
            else None
        )
        slot_stats_rows: list[dict[str, Any]] = []
        if session.final_slot_stats:
            for slot in sorted(session.final_slot_stats):
                stats = session.final_slot_stats[slot]
                mapped_conn: ConnectionState | None = None
                for key in session.participant_keys:
                    conn = active_connections.get(key)
                    if conn is None:
                        continue
                    if conn.assigned_slot == slot:
                        mapped_conn = conn
                        break
                slot_stats_rows.append(
                    {
                        "slot": int(slot),
                        "hits": int(stats.get("hits", 0)),
                        "kills": int(stats.get("kills", 0)),
                        "address": mapped_conn.address if mapped_conn else None,
                        "display_name": self._display_name(mapped_conn)
                        if mapped_conn is not None
                        else None,
                        "team": mapped_conn.assigned_team if mapped_conn else None,
                    }
                )
        participants = [
            active_connections[key].address
            for key in session.participant_keys
            if key in active_connections
        ]
        remaining_seconds = None
        if running:
            remaining_seconds = max(
                0,
                int(round(float(session.planned_end_at - time.time()))),
            )
        return {
            "running": bool(running),
            "session_state": "running" if running else "ended",
            "session_id": session.session_id,
            "started_at": session.started_at,
            "planned_end_at": session.planned_end_at,
            "duration_seconds": session.duration_seconds,
            "remaining_seconds": remaining_seconds,
            "ended_at": session.ended_at,
            "end_reason": session.end_reason,
            "participants": participants,
            "ranking": ranking,
            "slot_stats": slot_stats_rows,
            "totals": {
                "shots": totals_shots,
                "reloads": totals_reloads,
                "hits": totals_hits,
                "kills": totals_kills,
            },
            "stats_source_address": stats_source_address,
            "stats_error": stats_error,
            "close_failures": close_failures or [],
        }

    def _build_ranking_entries(
        self,
        *,
        session: GameSessionState,
        active_connections: dict[str, ConnectionState],
    ) -> list[dict[str, Any]]:
        ranking: list[dict[str, Any]] = []
        slot_stats = session.final_slot_stats or {}

        for key in session.participant_keys:
            conn = active_connections.get(key)
            if conn is None:
                continue
            trigger_now = int(conn.live_state.get("trigger_count", 0) or 0)
            reload_now = int(conn.live_state.get("reload_count", 0) or 0)
            shots = max(0, trigger_now - int(session.baseline_triggers.get(key, 0)))
            reloads = max(0, reload_now - int(session.baseline_reloads.get(key, 0)))
            slot = conn.assigned_slot
            slot_stat = (
                slot_stats.get(int(slot)) if slot is not None else None
            )
            hits = None
            kills = None
            accuracy = None
            if slot_stat is not None:
                hits = int(slot_stat.get("hits", 0))
                kills = int(slot_stat.get("kills", 0))
                if shots > 0:
                    accuracy = round((hits / shots) * 100.0, 1)
            ranking.append(
                {
                    "address": conn.address,
                    "name": conn.name,
                    "local_name": conn.local_name,
                    "display_name": self._display_name(conn),
                    "slot": conn.assigned_slot,
                    "team": conn.assigned_team,
                    "shots": shots,
                    "reloads": reloads,
                    "hits": hits,
                    "kills": kills,
                    "accuracy_percent": accuracy,
                    "connection_state": conn.connection_state,
                }
            )

        use_slot_stats = any(item.get("kills") is not None for item in ranking)
        if use_slot_stats:
            ranking.sort(
                key=lambda item: (
                    -int(item["kills"] if item["kills"] is not None else -1),
                    -int(item["hits"] if item["hits"] is not None else -1),
                    -int(item["shots"]),
                    int(item["reloads"]),
                    str(item["display_name"]).lower(),
                    str(item["address"]).lower(),
                )
            )
        else:
            ranking.sort(
                key=lambda item: (
                    -int(item["shots"]),
                    int(item["reloads"]),
                    str(item["display_name"]).lower(),
                    str(item["address"]).lower(),
                )
            )
        for idx, item in enumerate(ranking, start=1):
            item["rank"] = idx
        return ranking

    def _display_name(self, conn: ConnectionState) -> str:
        if conn.local_name:
            return conn.local_name
        if conn.name:
            return conn.name
        return conn.address

    def _normalize_local_name(self, local_name: str | None) -> str | None:
        if local_name is None:
            return None
        value = str(local_name).strip()
        if not value:
            return None
        if "\n" in value or "\r" in value or "\t" in value:
            raise ValueError("local name contains invalid control characters")
        if len(value) > LOCAL_NAME_MAX_LENGTH:
            raise ValueError(
                f"local name too long ({len(value)} > {LOCAL_NAME_MAX_LENGTH})"
            )
        return value

    def _load_local_name_store(self) -> dict[str, str]:
        if not self._local_name_store_path.exists():
            return {}
        try:
            payload = json.loads(self._local_name_store_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(payload, dict):
            return {}

        names: dict[str, str] = {}
        for raw_address, raw_name in payload.items():
            if not isinstance(raw_address, str):
                continue
            if not isinstance(raw_name, str):
                continue
            try:
                key = self._normalize_address(raw_address).lower()
            except Exception:
                continue
            safe_name = self._normalize_local_name(raw_name)
            if safe_name is None:
                continue
            names[key] = safe_name
        return names

    def _save_local_name_store(self) -> None:
        path = self._local_name_store_path
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        payload_map = {
            str(address): str(name)
            for address, name in sorted(self._local_names.items())
            if name
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(
                payload_map,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ) + "\n"
            tmp_path.write_text(payload, encoding="utf-8")
            tmp_path.replace(path)
        except Exception as exc:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception:
                pass
            raise RuntimeError(f"failed to persist local names: {exc}") from exc

    def _validate_safe_config(self, level: int, name_a: int, name_b: int) -> None:
        if level < SAFE_LEVEL_MIN or level > SAFE_LEVEL_MAX:
            raise ValueError(
                f"unsafe level: {level}. allowed range is "
                f"{SAFE_LEVEL_MIN}..{SAFE_LEVEL_MAX}"
            )
        if name_a < SAFE_NAME_INDEX_MIN or name_a > SAFE_NAME_INDEX_MAX:
            raise ValueError(
                f"unsafe name_a index: {name_a}. allowed range is "
                f"{SAFE_NAME_INDEX_MIN}..{SAFE_NAME_INDEX_MAX}"
            )
        if name_b < SAFE_NAME_INDEX_MIN or name_b > SAFE_NAME_INDEX_MAX:
            raise ValueError(
                f"unsafe name_b index: {name_b}. allowed range is "
                f"{SAFE_NAME_INDEX_MIN}..{SAFE_NAME_INDEX_MAX}"
            )

    def _validate_safe_team(self, *, slot: int, team: int) -> tuple[int, int]:
        if slot < SAFE_SLOT_MIN or slot > SAFE_SLOT_MAX:
            raise ValueError(
                f"unsafe slot: {slot}. allowed range is "
                f"{SAFE_SLOT_MIN}..{SAFE_SLOT_MAX}"
            )
        if team < SAFE_TEAM_MIN or team > SAFE_TEAM_MAX:
            raise ValueError(
                f"unsafe team: {team}. allowed range is "
                f"{SAFE_TEAM_MIN}..{SAFE_TEAM_MAX}"
            )
        return int(slot), int(team)

    def _resolve_team_for_start(
        self,
        *,
        conn: ConnectionState,
        slot: int | None,
        team: int | None,
    ) -> tuple[int, int]:
        selected_slot = conn.assigned_slot if slot is None else slot
        selected_team = conn.assigned_team if team is None else team
        if selected_slot is None:
            selected_slot = SAFE_SLOT_MIN
        if selected_team is None:
            selected_team = self._default_team_for_slot(selected_slot)
        elif selected_team < SAFE_TEAM_MIN or selected_team > SAFE_TEAM_MAX:
            # Migrate stale assignments from older UI versions.
            selected_team = self._default_team_for_slot(selected_slot)
        safe_slot, safe_team = self._validate_safe_team(
            slot=selected_slot, team=selected_team
        )
        conn.assigned_slot = safe_slot
        conn.assigned_team = safe_team
        return safe_slot, safe_team

    def _resolve_multi_team_profiles(
        self, conns: list[ConnectionState]
    ) -> dict[str, tuple[int, int]]:
        used: set[int] = set()
        profiles: dict[str, tuple[int, int]] = {}

        for conn in conns:
            if conn.assigned_slot is None or conn.assigned_team is None:
                continue
            raw_slot = int(conn.assigned_slot)
            raw_team = int(conn.assigned_team)
            if raw_slot < SAFE_SLOT_MIN or raw_slot > SAFE_SLOT_MAX:
                continue
            if raw_team < SAFE_TEAM_MIN or raw_team > SAFE_TEAM_MAX:
                safe_slot = raw_slot
                safe_team = SAFE_MULTIPLAYER_FFA_TEAM
            else:
                safe_slot = raw_slot
                safe_team = raw_team
            if safe_slot in used:
                raise ValueError(
                    "duplicate slot assignment in connected set: "
                    f"slot {safe_slot} (including {conn.address})"
                )
            profiles[conn.address.lower()] = (safe_slot, safe_team)
            used.add(safe_slot)

        next_slot = SAFE_SLOT_MIN
        for conn in conns:
            key = conn.address.lower()
            if key in profiles:
                continue
            while next_slot in used and next_slot <= SAFE_SLOT_MAX:
                next_slot += 1
            if next_slot > SAFE_SLOT_MAX:
                next_slot = SAFE_SLOT_MIN
                while next_slot in used and next_slot <= SAFE_SLOT_MAX:
                    next_slot += 1
            if next_slot > SAFE_SLOT_MAX:
                next_slot = SAFE_SLOT_MIN
            slot = next_slot
            team = SAFE_MULTIPLAYER_FFA_TEAM
            profiles[key] = (slot, team)
            conn.assigned_slot = slot
            conn.assigned_team = team
            used.add(slot)
            next_slot += 1
        return profiles

    def _default_team_for_slot(self, slot: int) -> int:
        # Keep a stable 0/1 rotation independent of absolute slot numbers.
        return int((int(slot) - SAFE_SLOT_MIN) % 2)

    def _validate_safe_game_delay(self, delay: float) -> float:
        if delay < SAFE_GAME_DELAY_MIN or delay > SAFE_GAME_DELAY_MAX:
            raise ValueError(
                f"unsafe game delay: {delay}. allowed range is "
                f"{SAFE_GAME_DELAY_MIN:.2f}..{SAFE_GAME_DELAY_MAX:.2f} s"
            )
        return float(delay)

    def _validate_game_duration(self, duration_seconds: int) -> int:
        value = int(duration_seconds)
        if (
            value < SAFE_GAME_DURATION_SECONDS_MIN
            or value > SAFE_GAME_DURATION_SECONDS_MAX
        ):
            raise ValueError(
                f"unsafe game duration: {value}. allowed range is "
                f"{SAFE_GAME_DURATION_SECONDS_MIN}..{SAFE_GAME_DURATION_SECONDS_MAX} s"
            )
        return value

    def _sanitize_end_reason(self, reason: str) -> str:
        value = str(reason or "").strip().lower().replace(" ", "_")
        if not value:
            return "manual_stop"
        safe = "".join(ch for ch in value if ch.isalnum() or ch in ("_", "-", "."))
        if not safe:
            return "manual_stop"
        return safe[:64]

    def _format_error(self, exc: Exception) -> str:
        name = exc.__class__.__name__
        text = str(exc).strip()
        if not text:
            text = repr(exc).strip()
        if not text:
            return name
        if text.startswith(name):
            return text
        return f"{name}: {text}"

    async def _start_one_multi_connection(
        self,
        *,
        conn: ConnectionState,
        slot: int,
        team: int,
        startup_volume: int,
        delay: float,
        duration_seconds: int,
        force_startup: bool,
    ) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
        try:
            snapshot, recovery_used = await self._run_multiplayer_start_sequence(
                conn=conn,
                slot=slot,
                team=team,
                startup_volume=startup_volume,
                delay=delay,
                duration_seconds=duration_seconds,
                allow_reconnect=True,
                reconnect_timeout=SAFE_MULTI_RECONNECT_TIMEOUT,
            )
            conn.last_snapshot = _snapshot_to_dict(snapshot)
            conn.last_game_start_at = time.time()
        except Exception as exc:
            return None, {
                "address": conn.address,
                "error": self._format_error(exc),
            }

        self._schedule_event(
            "game_start",
            {
                "address": conn.address,
                "name": conn.name,
                "startup_performed": True,
                "force_startup": force_startup,
                "delay": delay,
                "duration_seconds": duration_seconds,
                "slot": slot,
                "team": team,
                "game_start_at": conn.last_game_start_at,
                "multi": True,
                "recovery_used": recovery_used,
            },
        )
        return {
            "address": conn.address,
            "startup_performed": True,
            "last_snapshot": conn.last_snapshot,
            "slot": slot,
            "team": team,
            "duration_seconds": duration_seconds,
            "game_start_at": conn.last_game_start_at,
            "recovery_used": recovery_used,
        }, None

    async def _run_multiplayer_start_sequence(
        self,
        *,
        conn: ConnectionState,
        slot: int,
        team: int,
        startup_volume: int,
        delay: float,
        duration_seconds: int,
        allow_reconnect: bool = True,
        reconnect_timeout: float = RECONNECT_SCAN_TIMEOUT,
    ) -> tuple[Any, bool]:
        """
        Run multiplayer start sequence with one guarded recovery retry.

        Recovery path:
          1) ensure connection
          2) run confirmed startup exchange (35/5b)
          3) retry multiplayer setup sequence
        """
        last_error: Exception | None = None
        for attempt in (1, 2):
            try:
                if allow_reconnect:
                    await self._ensure_connected(conn, timeout=reconnect_timeout)
                elif not conn.gun.is_connected:
                    raise ConnectionError(
                        f"device not connected for multiplayer start: {conn.address}"
                    )
                async with conn.op_lock:
                    if attempt == 2:
                        await conn.gun.startup(volume=startup_volume)
                    snapshot = await conn.gun.send_multiplayer_game_setup(
                        delay=delay,
                        slot=slot,
                        team=team,
                        volume=startup_volume,
                        duration_seconds=duration_seconds,
                    )
                    # Some blasters return an all-zero startup profile during
                    # game setup and then stay in blinking pre-start state.
                    # Bootstrap a minimal profile and retry once in-session.
                    if (
                        int(getattr(snapshot, "level", 0) or 0) == 0
                        and int(getattr(snapshot, "name_a", 0) or 0) == 0
                        and int(getattr(snapshot, "name_b", 0) or 0) == 0
                    ):
                        await conn.gun.write_config(level=1, name_a=1, name_b=1)
                        snapshot = await conn.gun.send_multiplayer_game_setup(
                            delay=delay,
                            slot=slot,
                            team=team,
                            volume=startup_volume,
                            duration_seconds=duration_seconds,
                        )
                return snapshot, (attempt == 2)
            except Exception as exc:
                last_error = exc
                if attempt == 1:
                    continue
                break
        assert last_error is not None
        raise last_error

    async def subscribe_events(
        self, *, max_queue_size: int = LIVE_SUBSCRIBER_QUEUE_SIZE
    ) -> tuple[int, asyncio.Queue[dict[str, Any]]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=max_queue_size)
        async with self._subscribers_lock:
            subscriber_id = self._next_subscriber_id
            self._next_subscriber_id += 1
            self._subscribers[subscriber_id] = queue
        return subscriber_id, queue

    async def unsubscribe_events(self, subscriber_id: int) -> None:
        async with self._subscribers_lock:
            self._subscribers.pop(subscriber_id, None)

    async def live_snapshot(self) -> dict[str, Any]:
        return {
            "generated_at": time.time(),
            "connections": await self.list_connections(),
        }

    def _spawn_background(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    def _schedule_event(self, event_type: str, payload: dict[str, Any]) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return
        self._spawn_background(
            self._publish_event(event_type=event_type, payload=payload)
        )

    async def _publish_event(self, *, event_type: str, payload: dict[str, Any]) -> None:
        event = self._build_event(event_type=event_type, payload=payload)
        async with self._subscribers_lock:
            queues = list(self._subscribers.values())
        for queue in queues:
            self._queue_put_drop_oldest(queue, event)

    def _build_event(self, *, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._event_seq += 1
        return {
            "seq": self._event_seq,
            "ts": time.time(),
            "type": event_type,
            "payload": payload,
        }

    def _queue_put_drop_oldest(
        self, queue: asyncio.Queue[dict[str, Any]], event: dict[str, Any]
    ) -> None:
        try:
            queue.put_nowait(event)
            return
        except asyncio.QueueFull:
            pass
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass
