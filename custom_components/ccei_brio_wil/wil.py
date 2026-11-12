"""Minimal async TCP client for the CCEI BRiO WiL pool light controller.

The controller listens on TCP port 30302 and speaks a simple protocol:
- Connecting and reading returns a 160-char hex status frame.
- Sending a JSON command controls the device.

Commands
--------
    {"sprj":1} / {"sprj":0}   power on / off
    {"prcn":N}                colour / sequence  (see COLORS / SEQUENCES)
    {"plum":N}                brightness   (0..3  -> Low/Medium/Strong/Maximum)

Note: the app's "pspd" value is not a clean speed control (it also changes
the running sequence), so speed is deliberately not implemented here.

Status frame (verified against a real device)
---------------------------------------------
    pos 33        power state           0 = off, 2 = on
    pos 64:66     colour / mode         hex byte
    pos 70:72     level byte            low nibble = brightness (0/4/8/C)
                                        high nibble is device-internal, not
                                        used as a reliable speed indicator
"""

from __future__ import annotations

import asyncio
import json

DEFAULT_PORT = 30302
_TIMEOUT = 5.0

# The controller allows only one TCP connection at a time; commands may need
# a brief retry if the vendor app is momentarily connected.
_SEND_RETRIES = 3
_SEND_RETRY_DELAY = 0.6

# --- Status-frame field positions -------------------------------------------
_POWER_POS = 33
_POWER_ON_VALUE = 2
_COLOR_POS = slice(64, 66)
_LEVEL_POS = slice(70, 72)  # combined speed(high nibble) + brightness(low nibble)

# --- Colour / sequence mapping ----------------------------------------------
# name -> prcn command value == status-frame hex code
COLORS: dict[str, int] = {
    "warm_white": 0x00,
    "white": 0x01,
    "blue": 0x02,
    "lagoon": 0x03,
    "cyan": 0x04,
    "purple": 0x05,
    "magenta": 0x06,
    "pink": 0x07,
    "red": 0x08,
    "orange": 0x09,
    "green": 0x0A,
}
SEQUENCES: dict[str, int] = {
    "gradient": 0x10,
    "rainbow": 0x11,
    "parade": 0x12,
    "techno": 0x13,
    "horizon": 0x14,
    "hazard": 0x15,
    "magical": 0x16,
}

# "Favorite" (code 0x0B) is a device-side stored scene: it can be *recalled*
# via {"prcn":11} but can only be *defined* from the vendor app.
FAVORITE_NAME = "favorite"
FAVORITE_CODE = 0x0B

# Everything selectable is exposed via the effect list: solid colours first,
# then the favorite scene, then the sequences. The device only supports these
# fixed choices (no free RGB), so a named list is the honest representation.
EFFECT_LIST: list[str] = list(COLORS) + [FAVORITE_NAME] + list(SEQUENCES)

# Reverse lookup: frame code -> name (all colours, sequences and favorite).
_CODE_TO_EFFECT: dict[int, str] = {
    code: name for name, code in {**COLORS, **SEQUENCES}.items()
}
_CODE_TO_EFFECT[FAVORITE_CODE] = FAVORITE_NAME

# --- Sequence speed: intentionally not implemented --------------------------
# The vendor "pspd" command does NOT behave as a pure speed control on this
# device: sending it while a sequence runs also *changes the sequence itself*
# (verified: Rainbow + pspd:2 -> device switched to Techno). The real speed
# command used by the app is unknown, so speed control is omitted for now.

_BRIGHTNESS_STEPS = 4
# Low nibble of the level byte -> device step index.
_NIBBLE_TO_STEP = {0x0: 0, 0x4: 1, 0x8: 2, 0xC: 3}

# A single status frame is 160 hex characters long.
_FRAME_LEN = 160


def _last_complete_frame(raw: str) -> str | None:
    """Return the last complete 160-char frame from a raw response.

    The controller answers commands with several concatenated frames
    (the state before and after the change). The last one is authoritative.
    """
    if len(raw) < _FRAME_LEN:
        return None
    count = len(raw) // _FRAME_LEN
    return raw[(count - 1) * _FRAME_LEN : count * _FRAME_LEN]


class BrioWilError(Exception):
    """Raised when communication with the controller fails."""


class BrioWilStatus:
    """Parsed snapshot of the controller state."""

    def __init__(
        self,
        is_on: bool,
        effect: str | None,
        brightness_step: int | None,
    ):
        self.is_on = is_on
        # The active choice as a name: a colour, a sequence, or the favorite.
        # All are surfaced through the effect list.
        self.effect = effect
        self.brightness_step = brightness_step


def ha_brightness_to_step(brightness: int) -> int:
    """Map HA brightness (1..255) to a device step 0..3."""
    step = round((brightness - 1) / 255 * (_BRIGHTNESS_STEPS - 1))
    return max(0, min(_BRIGHTNESS_STEPS - 1, step))


def step_to_ha_brightness(step: int) -> int:
    """Map a device step 0..3 to HA brightness 1..255."""
    return round(step / (_BRIGHTNESS_STEPS - 1) * 255) or 1


class BrioWil:
    """Talks to a single BRiO WiL controller over TCP."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self._host = host
        self._port = port

    async def _open(self):
        try:
            return await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), _TIMEOUT
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise BrioWilError(f"Cannot connect to {self._host}:{self._port}") from err

    async def _read_status_raw(self) -> str:
        reader, writer = await self._open()
        try:
            data = await asyncio.wait_for(reader.read(256), _TIMEOUT)
        except (OSError, asyncio.TimeoutError) as err:
            raise BrioWilError("No status response from controller") from err
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
        return data.decode(errors="ignore").strip()

    async def _send(self, payload: dict) -> None:
        """Send a command, retrying briefly if the single connection slot is busy.

        The controller allows only one TCP connection at a time. If the vendor
        app is momentarily connected, the first attempt may fail; a short retry
        usually succeeds once the app's connection is released.
        """
        last_err: Exception | None = None
        for attempt in range(_SEND_RETRIES):
            try:
                reader, writer = await self._open()
            except BrioWilError as err:
                last_err = err
                await asyncio.sleep(_SEND_RETRY_DELAY)
                continue
            try:
                writer.write(json.dumps(payload, separators=(",", ":")).encode())
                await asyncio.wait_for(writer.drain(), _TIMEOUT)
                return
            except (OSError, asyncio.TimeoutError) as err:
                last_err = err
                await asyncio.sleep(_SEND_RETRY_DELAY)
            finally:
                writer.close()
                try:
                    await writer.wait_closed()
                except OSError:
                    pass
        raise BrioWilError("Failed to send command") from last_err

    async def async_get_status(self) -> BrioWilStatus:
        raw = await self._read_status_raw()
        # The controller may return several concatenated 160-char frames
        # (e.g. a "before" and "after" frame in response to a command).
        # Always evaluate the last complete frame.
        frame = _last_complete_frame(raw)
        if frame is None or len(frame) < 72:
            raise BrioWilError(f"Unexpected status frame: {raw!r}")

        try:
            power = int(frame[_POWER_POS], 16)
        except ValueError as err:
            raise BrioWilError(f"Cannot parse power from {frame!r}") from err
        is_on = power == _POWER_ON_VALUE

        effect: str | None = None
        try:
            effect = _CODE_TO_EFFECT.get(int(frame[_COLOR_POS], 16))
        except ValueError:
            effect = None

        brightness_step: int | None = None
        try:
            level = int(frame[_LEVEL_POS], 16)
            brightness_step = _NIBBLE_TO_STEP.get(level & 0x0F)
        except ValueError:
            pass

        return BrioWilStatus(is_on, effect, brightness_step)

    async def async_is_on(self) -> bool:
        return (await self.async_get_status()).is_on

    async def async_turn_on(self) -> None:
        await self._send({"sprj": 1})

    async def async_turn_off(self) -> None:
        await self._send({"sprj": 0})

    async def async_set_effect(self, effect: str) -> None:
        """Set any choice: a solid colour, a sequence, or the favorite scene."""
        if effect in COLORS:
            code = COLORS[effect]
        elif effect in SEQUENCES:
            code = SEQUENCES[effect]
        elif effect == FAVORITE_NAME:
            code = FAVORITE_CODE
        else:
            raise BrioWilError(f"Unknown effect: {effect}")
        await self._send({"prcn": code})

    async def async_set_brightness_step(self, step: int) -> None:
        step = max(0, min(_BRIGHTNESS_STEPS - 1, step))
        await self._send({"plum": step})

    async def async_test_connection(self) -> bool:
        await self._read_status_raw()
        return True
