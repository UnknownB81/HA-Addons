from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_TYPES
from .coordinator import NFLCoordinator


@dataclass(frozen=True, kw_only=True)
class NFLSensorDescription(SensorEntityDescription):
    data_key: str
    attribute_key: str


SENSOR_DESCRIPTIONS = tuple(
    NFLSensorDescription(
        key=key,
        name=name,
        unique_id=unique_id,
        data_key=key,
        attribute_key="teams" if "standings" in key else "games",
    )
    for key, name, unique_id in SENSOR_TYPES
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: NFLCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(NFLSensor(coordinator, description) for description in SENSOR_DESCRIPTIONS)


class NFLSensor(CoordinatorEntity[NFLCoordinator], SensorEntity):
    entity_description: NFLSensorDescription

    def __init__(self, coordinator: NFLCoordinator, description: NFLSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = description.unique_id
        self._attr_name = description.name
        self._attr_has_entity_name = False
        self._attr_icon = "mdi:football"

    @property
    def native_value(self) -> int:
        return len(self.coordinator.data.get(self.entity_description.data_key, []))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            self.entity_description.attribute_key: self.coordinator.data.get(
                self.entity_description.data_key, []
            )
        }