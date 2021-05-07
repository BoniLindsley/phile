#!/usr/bin/env python3
"""
------------------------
Configuration management
------------------------
"""

# Standard library.
import json
import pathlib
import typing

# External dependencies.
import appdirs  # type: ignore[import]
import pydantic

_app_meta_data = {'appname': 'phile', 'appauthor': 'BoniLindsley'}
"""Descriptions of app. Used to form directory paths."""


class Entries(pydantic.BaseSettings):
    configuration_path = pathlib.Path(
        appdirs.user_config_dir(**_app_meta_data)
    ) / 'config.json'
    notification_directory = pathlib.Path('notify')
    notification_suffix = '.notify'
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
        extra = pydantic.Extra.allow


def load() -> Entries:
    settings = Entries()
    configuration_path = settings.configuration_path
    if configuration_path.exists():
        settings = Entries.parse_file(configuration_path)
    return settings
