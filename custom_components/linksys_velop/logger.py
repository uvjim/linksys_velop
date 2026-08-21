"""Logging wrapper."""

# region #-- imports --#
import inspect
import logging
from types import FrameType
from typing import Any

# endregion


class Logger:
    """Wrapper for logging.Logger class."""

    def __init__(self, logger: logging.Logger) -> None:
        """Initialise."""

        self._logger: logging.Logger = logger

    def __getattr__(self, name):
        """Pass through access to logging.Logger attributes."""

        return getattr(self._logger, name)

    def _format(self, msg: str) -> str:
        """Format the message using as required."""

        ret: str = msg
        caller_details: dict[str, Any] | None = None
        frame: FrameType | None = inspect.currentframe()
        try:
            if frame is not None:
                caller: FrameType | None = frame.f_back
                if caller is not None:
                    caller_class: Any = caller.f_locals.get("self")
                    if caller_class == self:  # go back again in the stack
                        caller = caller.f_back
                    if caller is not None:
                        caller_info: inspect.Traceback = inspect.getframeinfo(caller)
                        caller_details = {
                            "line_no": caller_info.lineno,
                            "func_name": caller_info.function,
                        }
        finally:
            del frame

        if caller_details is not None:
            ret = f"{caller_details.get("func_name")}:{caller_details.get("line_no")}:{msg}"

        return ret

    def debug(self, msg: str, *args: Any) -> None:
        """Passthrough for the debug logger."""

        self._logger.debug(self._format(msg % args))

    def get_logger(self) -> logging.Logger:
        """Return the logger that was initially passed in."""

        return self._logger
