"""Light platform for the CCEI BRiO WiL pool light."""

from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import DOMAIN, BrioWilCoordinator
from .wil import (
    COLORS,
    EFFECT_LIST,
    BrioWilError,
    ha_brightness_to_step,
    step_to_ha_brightness,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the light from a config entry."""
    coordinator: BrioWilCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BrioWilLight(coordinator, entry)])


class BrioWilLight(CoordinatorEntity[BrioWilCoordinator], LightEntity):
    """Pool light: on/off, brightness, and colour/sequence choices as effects."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "pool_light"
    _attr_icon = "mdi:light-flood-down"
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = EFFECT_LIST

    def __init__(self, coordinator: BrioWilCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Pool Light",
            manufacturer="CCEI",
            model="BRiO WiL",
        )

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.is_on

    @property
    def brightness(self) -> int | None:
        step = self.coordinator.data.brightness_step
        if step is None:
            return None
        return step_to_ha_brightness(step)

    @property
    def effect(self) -> str | None:
        current = self.coordinator.data.effect
        return current if current in EFFECT_LIST else None

    async def async_turn_on(self, **kwargs: Any) -> None:
        device = self.coordinator.device
        try:
            if not self.is_on:
                await device.async_turn_on()

            if ATTR_EFFECT in kwargs:
                await device.async_set_effect(kwargs[ATTR_EFFECT])

            if ATTR_BRIGHTNESS in kwargs:
                step = ha_brightness_to_step(kwargs[ATTR_BRIGHTNESS])
                await device.async_set_brightness_step(step)
                # Known quirk: a brightness change on a solid colour can snap
                # the colour back to white. Re-assert the colour to stay in sync
                # (sequences and the favorite are unaffected).
                current = self.coordinator.data.effect
                if current in COLORS:
                    await asyncio.sleep(0.2)
                    await device.async_set_effect(current)
        except BrioWilError:
            return

        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.device.async_turn_off()
        except BrioWilError:
            return
        await self.coordinator.async_request_refresh()
