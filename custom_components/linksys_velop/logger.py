"""Logging wrapper."""

# region #-- imports --#
import inspect
import logging
from typing import Any

# endregion


class Logger:
    """Wrapper for logging.Logger to inject caller context into messages."""

    def __init__(self, logger: logging.Logger) -> None:
        """Initialize the logger wrapper.

        :param logger: The underlying logging.Logger instance to be wrapped.
        """
        self._logger = logger

    def __getattr__(self, name: str) -> Any:
        """Proxy access to the underlying logging.Logger instance.

        :param name: The name of the attribute being accessed.
        :returns: The attribute from the underlying logger.
        """
        return getattr(self._logger, name)

    def _format_with_context(self, msg: str) -> str:
        """Injects function name and line number into the log message.

        :param msg: The raw log message string.
        :returns: The message prefixed with 'function:line:'.
        """
        # go back 2 frames: 1 for this method, 1 for the calling log method (e.g. debug)
        frame = inspect.currentframe()
        try:
            caller = frame.f_back.f_back if frame and frame.f_back else None
            if caller:
                info = inspect.getframeinfo(caller)
                return f"{info.function}:{info.lineno}:{msg}"
        finally:
            del frame
        return msg

    def debug(self, msg: str, *args: Any) -> None:
        """Log a debug message with caller context.

        :param msg: The message template to log.
        :param args: Arguments to be interpolated into the message template.
        """
        formatted_msg = msg % args if args else msg
        self._logger.debug(self._format_with_context(formatted_msg))

    def get_logger(self) -> logging.Logger:
        """Return the underlying logging.Logger instance.

        :returns: The original logging.Logger object.
        """
        return self._logger
