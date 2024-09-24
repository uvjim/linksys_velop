from homeassistant.exceptions import HomeAssistantError


class IntensiveTaskRunning(HomeAssistantError):
    """Intensive task running whilst checking for state."""
