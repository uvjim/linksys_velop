"""Exceptions."""

from homeassistant.exceptions import HomeAssistantError


class CoordinatorMeshException(HomeAssistantError):
    """MeshException raised."""


class CoordinatorMeshTimeout(HomeAssistantError):
    """Gathering mesh data timed out."""


class DeviceTrackerMeshTimeout(HomeAssistantError):
    """Gathering device tracker data timed out."""


class GeneralException(HomeAssistantError):
    """A currently untracked exception was encountered."""


class IntensiveTaskRunning(HomeAssistantError):
    """Intensive task running whilst checking for state."""


class InvalidInput(HomeAssistantError):
    """Invalid input when executing an action."""
