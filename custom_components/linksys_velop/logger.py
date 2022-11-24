"""Logging."""

# region #-- imports --#
import inspect

# endregion


class Logger:
    """Provide functions for managing log messages."""

    def __init__(self, unique_id: str = "", prefix: str = ""):
        """Initialise."""
        self._unique_id: str = unique_id
        self._prefix: str = prefix

    def format(
        self, message: str, include_caller: bool = True, include_lineno: bool = False
    ) -> str:
        """Format a log message in the correct format."""
        caller: str = ""
        if include_caller:
            caller_frame: inspect.FrameInfo = inspect.stack()[1]
            caller = caller_frame.function
        line_no: str = f" --> line: {caller.lineno}" if include_lineno else ""
        unique_id: str = f" ({self._unique_id})" if self._unique_id else ""
        if any([self._prefix, caller, unique_id, line_no]):
            message = f" --> {message}"
        return f"{self._prefix}{caller}{unique_id}{line_no}{message}"
