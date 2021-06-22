#!/usr/bin/env python3
"""
.. automodule:: phile.notify.cli
.. automodule:: phile.notify.gui
"""

# Standard library.
import contextlib
import dataclasses
import datetime
import pathlib
import typing

# Internal packages.
import phile.configuration
import phile.data


@dataclasses.dataclass(eq=False)
class File(phile.data.File):
    modified_at: datetime.datetime = datetime.datetime.fromtimestamp(0)
    text: str = ''

    @staticmethod
    def make_path(
        path_stem: str,
        *args: typing.Any,
        configuration: phile.configuration.Entries,
        **kwargs: typing.Any,
    ) -> pathlib.Path:
        return (
            configuration.state_directory_path /
            configuration.notification_directory /
            (path_stem + configuration.notification_suffix)
        )

    def save(self) -> None:
        """Write content to file, and read new modified time."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.text)
        self.load_modified_at()

    def load(self) -> bool:
        """
        Loads content of :data:`~phile.data.File.path` as a notification.

        Sets :data:`~phile.data.File.loaded`
        depending on whether the load was successful
        even if exceptions are raised.
        """
        try:
            self.text = self.path.read_text()
            self.load_modified_at()
        except (FileNotFoundError, IsADirectoryError):
            return False
        else:
            return True

    def load_modified_at(self) -> None:
        """Update stored data to reflect modified time of file."""
        self.modified_at = datetime.datetime.fromtimestamp(
            self.path.stat().st_mtime
        )

    @property
    def title(self) -> str:
        return self.path.stem

    @title.setter
    def title(self, new_title: str) -> None:
        self.path = self.path.with_name(new_title + self.path.suffix)


# TODO(BoniLindsley): Manage notifications in a new `Registry` class.
