from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN
from .utils.store import async_load_from_store
from .data_client import StateGridDataClient


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    config = await async_load_from_store(hass, "state_grid.config") or None
    hass.data[DOMAIN] = StateGridDataClient(hass=hass, config=config)
    
    # 修复：使用新的 API (HA 2024+)
    await hass.config_entries.async_forward_entry_setups(config_entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, [Platform.SENSOR])
