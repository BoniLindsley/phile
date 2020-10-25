#!/usr/bin/env python3
"""
--------------------
Common configuration
--------------------
"""

# Standard library.
import pathlib
from pathlib import Path as _Path

# External dependencies.
import appdirs  # type: ignore[import]

_app_meta_data = {'appname': 'phile', 'appauthor': 'BoniLindsley'}
"""
Descriptions of app. Used for forming directory paths.

Functions to use it on:

* `appdirs.site_config_dir(**_app_meta_data)`
* `appdirs.site_data_dir`
* `appdirs.user_cache_dir`
* `appdirs.user_config_dir`
* `appdirs.user_data_dir`
* `appdirs.user_log_dir`
* `appdirs.user_state_dir`
"""


class Configuration:

    def __init__(
        self,
        *,
        notification_directory: _Path = _Path("notification"),
        notification_suffix: str = '.notify',
        tray_directory: _Path = _Path("tray"),
        tray_icon_name: str = 'phile-tray-empty',
        tray_suffix: str = '.tray',
        user_state_directory: _Path = _Path(
            appdirs.user_state_dir(**_app_meta_data)
        ),
    ) -> None:
        self.user_state_directory = user_state_directory
        """Directory to contain default state directories."""
        if not notification_directory.is_absolute():
            notification_directory = (
                self.user_state_directory / notification_directory
            )
        self.notification_directory = notification_directory
        """
        Directory containing files representing notification requests.
        """
        self.notification_suffix = notification_suffix
        """Filename suffix that notification files should have."""
        if not tray_directory.is_absolute():
            tray_directory = (self.user_state_directory / tray_directory)
        self.tray_directory = tray_directory
        """Directory containing files representing tray requests."""
        self.tray_icon_name = tray_icon_name
        """Name of default tray icon."""
        self.tray_suffix = tray_suffix
        """Filename suffix that tray files should have."""
