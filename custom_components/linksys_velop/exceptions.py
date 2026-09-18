"""Exceptions."""

from homeassistant.exceptions import HomeAssistantError


class BlockingTaskRunning(HomeAssistantError):
    """Blocking task running whilst checking for state."""


class CoordinatorMeshException(HomeAssistantError):
    """MeshException raised."""


class CoordinatorTimeout(HomeAssistantError):
    """Gathering mesh data timed out."""


class GeneralException(HomeAssistantError):
    """A currently untracked exception was encountered."""


class InvalidInput(HomeAssistantError):
    """Invalid input when executing an action."""
