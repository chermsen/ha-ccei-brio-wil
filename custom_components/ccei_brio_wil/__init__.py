"""The CCEI BRiO WiL Pool Light integration."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .wil import DEFAULT_PORT, BrioWil, BrioWilError, BrioWilStatus

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ccei_brio_wil"
PLATFORMS = [Platform.LIGHT]
SCAN_INTERVAL = timedelta(seconds=30)

# The controller accepts only one TCP connection at a time. While the vendor
# app is connected, polls will fail. Tolerate a few consecutive failures and
# keep the last known state before declaring the device unavailable.
_MAX_CONSECUTIVE_FAILURES = 3


class BrioWilCoordinator(DataUpdateCoordinator[BrioWilStatus]):
    """Polls the controller for its full state."""

    def __init__(self, hass: HomeAssistant, device: BrioWil) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.device = device
        self._failures = 0

    async def _async_update_data(self) -> BrioWilStatus:
        try:
            status = await self.device.async_get_status()
        except BrioWilError as err:
            self._failures += 1
            # Only surface as unavailable after several misses in a row.
            # This bridges the common case where the vendor app briefly
            # holds the device's single connection slot.
            if self._failures >= _MAX_CONSECUTIVE_FAILURES or self.data is None:
                raise UpdateFailed(str(err)) from err
            _LOGGER.debug(
                "Poll failed (%s/%s), keeping last known state: %s",
                self._failures,
                _MAX_CONSECUTIVE_FAILURES,
                err,
            )
            return self.data
        else:
            self._failures = 0
            return status


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    device = BrioWil(
        entry.data[CONF_HOST],
        entry.data.get(CONF_PORT, DEFAULT_PORT),
    )
    coordinator = BrioWilCoordinator(hass, device)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
