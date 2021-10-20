#!/usr/bin/env python3
"""
------------------------
Configuration management
------------------------
"""

# Standard library.
import datetime
import importlib.metadata
import json
import pathlib
import typing

# External dependencies.
import pydantic

# Internal modules.
import phile.phill.appdirs


# TODO[mypy issue 4145]: Missing global `__spec__` in stub.
_app_paths = phile.phill.appdirs.AppPaths.from_module_spec(
    __spec__  # type: ignore[name-defined]
)


class ImapEntries(pydantic.BaseModel):
    folder: str
    host: str
    idle_refresh_timeout = datetime.timedelta(minutes=24)
    maximum_reconnect_delay = datetime.timedelta(minutes=16)
    minimum_reconnect_delay = datetime.timedelta(seconds=15)
    password: typing.Optional[str] = None
    connect_timeout = datetime.timedelta(minutes=1)
    username: typing.Optional[str] = None


class Entries(pydantic.BaseSettings):
    configuration_path = _app_paths.user_config / "config.json"
    hotkey_global_map: dict[str, str] = {}
    hotkey_map: dict[str, str] = {}
    imap: typing.Optional[ImapEntries] = None
    log_file_level = 30
    log_file_path = pathlib.Path("phile.log")
    log_stderr_level = 30
    main_autostart = set[str]()
    notify_directory = pathlib.Path("notify")
    notify_suffix = ".notify"
    pid_path = pathlib.Path("pid")
    state_directory_path = _app_paths.user_state
    tray_icon_name = "phile-tray-empty"
    tray_directory = pathlib.Path("tray")
    tray_suffix = ".tray"
    trigger_directory = pathlib.Path("trigger")
    trigger_suffix = ".trigger"

    class Config:
        case_sensitive = False
        env_prefix = "PHILE_"
        # Pylint is unable to find Extra.
        extra = pydantic.Extra.allow  # pylint: disable=no-member


def load() -> Entries:
    settings = Entries()
    configuration_path = settings.configuration_path
    if configuration_path.exists():
        settings = Entries.parse_file(configuration_path)
    return settings
