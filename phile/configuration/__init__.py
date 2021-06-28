#!/usr/bin/env python3
"""
------------------------
Configuration management
------------------------
"""

# Standard library.
import datetime
import json
import pathlib
import typing

# External dependencies.
import appdirs  # type: ignore[import]
import pydantic

_app_meta_data = {'appname': 'phile', 'appauthor': 'BoniLindsley'}
"""Descriptions of app. Used to form directory paths."""


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
    configuration_path = pathlib.Path(
        appdirs.user_config_dir(**_app_meta_data)
    ) / 'config.json'
    hotkey_global_map: dict[str, str] = {}
    hotkey_map: dict[str, str] = {}
    imap: typing.Optional[ImapEntries] = None
    log_file_level = 30
    log_file_path = pathlib.Path('phile.log')
    log_stderr_level = 30
    main_autostart = set[str]()
    notify_directory = pathlib.Path('notify')
    notify_suffix = '.notify'
    pid_path = pathlib.Path('pid')
    state_directory_path = pathlib.Path(
        appdirs.user_state_dir(**_app_meta_data)
    )
    tray_icon_name = 'phile-tray-empty'
    tray_directory = pathlib.Path('tray')
    tray_suffix = '.tray'
    trigger_directory = pathlib.Path('trigger')
    trigger_suffix = '.trigger'

    class Config:
        case_sensitive = False
        env_prefix = 'PHILE_'
        # Pylint is unable to find Extra.
        extra = pydantic.Extra.allow  # pylint: disable=no-member


def load() -> Entries:
    settings = Entries()
    configuration_path = settings.configuration_path
    if configuration_path.exists():
        settings = Entries.parse_file(configuration_path)
    return settings
