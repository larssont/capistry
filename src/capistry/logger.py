"""
Enhanced logging utilities with rich formatting and extra field support.

Provides utilities for package-level logging with Rich's enhanced console output
and custom formatting that includes extra context fields.

Functions
---------
_get_pkg_logger : function
    Returns the root logger of the current top-level package.
init_logger : function
    Initializes logging with RichHandler and ExtraFormatter.

Classes
-------
ExtraFormatter : class
    Custom formatter that appends extra fields to the log message.

Examples
--------
Display logs using default level:
>>> init_logger()

Display minimum debug logs with custom date fomat:
>>> init_logger(level=logging.DEBUG, datefmt="%m/%d/%Y %I:%M:%S %p")
"""

import logging

from rich.logging import RichHandler

FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"


class ExtraFormatter(logging.Formatter):
    """
    Custom formatter that appends extra fields to the log message.

    Automatically detects and appends extra fields passed to log calls as
    key=value pairs separated by pipes.

    Parameters
    ----------
    fmt : str, optional
        Format string for the log message.
    datefmt : str, optional
        Date format string.
    style : str, default='%'
        Style of the format string.
    validate : bool, default=True
        Whether to validate the format string.
    """

    def format(self, record):
        """
        Format the log record with extra fields appended.

        Parameters
        ----------
        record : logging.LogRecord
            The log record to be formatted.

        Returns
        -------
        str
            Formatted log message with extra fields.
        """
        standard_attrs = set(vars(logging.makeLogRecord({})))
        extras = {
            k: v
            for k, v in vars(record).items()
            if k not in standard_attrs and not k.startswith("_")
        }
        extra_str = " | " + ", ".join(f"{k}={v}" for k, v in extras.items()) if extras else ""
        return super().format(record) + extra_str


def _get_pkg_logger():
    """
    Return the root logger of the current top-level package.

    Returns
    -------
    logging.Logger
        Logger instance for the top-level package.
    """
    parts = __name__.split(".")
    return logging.getLogger(parts[0] if parts else __name__)


def init_logger(level=logging.INFO, fmt: str = FORMAT, datefmt: str = DATEFMT) -> logging.Logger:
    """
    Initialize enhanced logging with RichHandler and ExtraFormatter.

    Sets up logging with Rich's colorized output and structured logging support.
    Not required but provides a simple way to add logging when using Capistry.

    Parameters
    ----------
    level : int, default=logging.INFO
        Logging level threshold.
    fmt : str, default=FORMAT
        Format string for the log message.
    datefmt : str, default=DATEFMT
        Date format string.
    """
    formatter = ExtraFormatter(fmt=fmt, datefmt=datefmt)
    handler = RichHandler(rich_tracebacks=True)
    handler.setFormatter(formatter)
    logger = _get_pkg_logger()
    logger.setLevel(level)
    logger.handlers.clear()
    logger.addHandler(handler)
    return logger
