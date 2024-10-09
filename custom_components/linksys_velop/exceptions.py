from homeassistant.exceptions import HomeAssistantError


class CoordinatorMeshTimeout(HomeAssistantError):
    """Gathering mesh data timed out."""


class GeneralException(HomeAssistantError):
    """A currently untracked exception was encountered."""


class IntensiveTaskRunning(HomeAssistantError):
    """Intensive task running whilst checking for state."""
