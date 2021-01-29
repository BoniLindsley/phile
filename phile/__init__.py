#!/usr/bin/env python3
"""
.. automodule:: phile.PySide2
.. automodule:: phile.asyncio
.. automodule:: phile.data
.. automodule:: phile.datetime
.. automodule:: phile.notify
.. automodule:: phile.os
.. automodule:: phile.tmux
.. automodule:: phile.tray
.. automodule:: phile.trigger
.. automodule:: phile.watchdog

--------------------
Common configuration
--------------------
"""

# Standard library.
import dataclasses as _dataclasses
import pathlib as _pathlib
import typing as _typing

# External dependencies.
import appdirs as _appdirs  # type: ignore[import]

# TODO[python/mypy#9761]: Replace with `Capabilities = dict[str,Any]`
Capabilities: _typing.Type[_typing.Dict[str, _typing.Any]] = dict

_app_meta_data = {'appname': 'phile', 'appauthor': 'BoniLindsley'}
"""Descriptions of app. Used for forming directory paths."""

default_notification_directory = _pathlib.Path("notification")
default_notification_suffix = '.notify'
default_pid_path = _pathlib.Path('pid')
default_tray_directory = _pathlib.Path("tray")
default_tray_icon_name = 'phile-tray-empty'
default_tray_suffix = '.tray'
default_trigger_root = _pathlib.Path("trigger")
default_trigger_suffix = '.trigger'
default_user_state_directory = _pathlib.Path(
    _appdirs.user_state_dir(**_app_meta_data)
)


@_dataclasses.dataclass
class Configuration:

    notification_directory: _pathlib.Path = default_notification_directory
    notification_suffix: str = default_notification_suffix
    pid_path: _pathlib.Path = default_pid_path
    tray_directory: _pathlib.Path = default_tray_directory
    tray_icon_name: str = default_tray_icon_name
    tray_suffix: str = default_tray_suffix
    trigger_root: _pathlib.Path = default_trigger_root
    trigger_suffix: str = default_trigger_suffix
    user_state_directory: _pathlib.Path = default_user_state_directory

    def __post_init__(
        self, *args: _typing.Any, **kwargs: _typing.Any
    ) -> None:
        getattr(
            super(), "__post_init__",
            lambda _self, *_args, **_kwargs: None
        )(self, *args, **kwargs)
        user_state_directory = self.user_state_directory
        self.notification_directory = (
            user_state_directory / self.notification_directory
        )
        self.tray_directory = user_state_directory / self.tray_directory
        self.trigger_root = user_state_directory / self.trigger_root
