#!/usr/bin/env python3
"""
.. automodule:: phile.PySide2
.. automodule:: phile.asyncio
.. automodule:: phile.builtins
.. automodule:: phile.cmd
.. automodule:: phile.configuration
.. automodule:: phile.data
.. automodule:: phile.datetime
.. automodule:: phile.hotkey
.. automodule:: phile.imapclient
.. automodule:: phile.keyring
.. automodule:: phile.launcher
.. automodule:: phile.main
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
import dataclasses
import io
import json
import pathlib
import typing

# External dependencies.
import appdirs  # type: ignore[import]

_T_co = typing.TypeVar('_T_co')


# TODO[mypy issue #4717]: Remove `ignore[misc]` from uses of this class.
# The `type` type hint does not accept abstract types.
# So an ignore is necessary on all uses with abstract types.
class Capabilities(dict[type, typing.Any]):

    def __getitem__(self, capability: type[_T_co]) -> _T_co:
        return typing.cast(_T_co, super().__getitem__(capability))

    def __setitem__(self, key: type[_T_co], value: _T_co) -> None:
        super().__setitem__(key, value)

    def set(self, value: _T_co) -> None:
        self.__setitem__(type(value), value)


_app_meta_data = {'appname': 'phile', 'appauthor': 'BoniLindsley'}
"""Descriptions of app. Used for forming directory paths."""

default_configuration_path = pathlib.Path(
    appdirs.user_config_dir(**_app_meta_data)
) / 'config.json'
default_notification_directory = pathlib.Path("notification")
default_notification_suffix = '.notify'
default_pid_path = pathlib.Path('pid')
default_tray_directory = pathlib.Path("tray")
default_tray_icon_name = 'phile-tray-empty'
default_tray_suffix = '.tray'
default_trigger_root = pathlib.Path("trigger")
default_trigger_suffix = '.trigger'
default_user_state_directory = pathlib.Path(
    appdirs.user_state_dir(**_app_meta_data)
)


@dataclasses.dataclass
class Configuration:

    configuration_path: pathlib.Path = default_configuration_path
    notification_directory: pathlib.Path = default_notification_directory
    notification_suffix: str = default_notification_suffix
    pid_path: pathlib.Path = default_pid_path
    tray_directory: pathlib.Path = default_tray_directory
    tray_icon_name: str = default_tray_icon_name
    tray_suffix: str = default_tray_suffix
    trigger_root: pathlib.Path = default_trigger_root
    trigger_suffix: str = default_trigger_suffix
    user_state_directory: pathlib.Path = default_user_state_directory

    def __post_init__(
        self, *args: typing.Any, **kwargs: typing.Any
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
        self.load()

    def load(self) -> bool:
        self.data = {}
        # Buffer the file content to reduce the chance of file changes
        # introducing a race condition.
        try:
            content_stream = io.StringIO(
                self.configuration_path.read_text()
            )
        except (FileNotFoundError, IsADirectoryError):
            return False
        try:
            self.data = json.load(content_stream)
        except json.decoder.JSONDecodeError:
            return False
        return True
