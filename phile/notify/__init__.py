#!/usr/bin/env python3
"""
.. automodule:: phile.notify.cli
.. automodule:: phile.notify.gui
"""

# Standard library.
import datetime
import pathlib

# Internal packages.
import phile.configuration


class File:

    class ParentError(ValueError):
        pass

    class SuffixError(ValueError):
        pass

    def __init__(
        self,
        *,
        configuration: phile.configuration.Configuration = None,
        name: str = None,
        path: pathlib.Path = None
    ) -> None:
        if path is None:
            if configuration is None or name is None:
                raise ValueError(
                    'Notification is constructed from path'
                    ' or from both configuration and name'
                )
            path = configuration.notification_directory / (
                name + configuration.notification_suffix
            )
        else:
            if configuration is not None:
                path_parent = path.parent
                directory = configuration.notification_directory
                if path_parent != directory:
                    raise File.ParentError(
                        'Path parent ({}) is not {}'.format(
                            path_parent, directory
                        )
                    )
                path_suffix = path.suffix
                notification_suffix = configuration.notification_suffix
                if path_suffix != notification_suffix:
                    raise File.SuffixError(
                        'Path suffix ({}) is not {}'.format(
                            path_suffix, notification_suffix
                        )
                    )
        self.path = path

    def __hash__(self):
        return hash(self.path)

    def __eq__(self, other):
        return self.path == other.path

    def __lt__(self, other):
        return self.path < other.path

    def append(self, additional_content: str):
        with self.path.open('a') as notification_file:
            # End with a new line
            # so that appending again would not jumble up the text.
            notification_file.write(additional_content + '\n')

    @property
    def creation_datetime(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self.path.stat().st_mtime)

    @property
    def name(self) -> str:
        return self.path.stem

    def read(self) -> str:
        return self.path.read_text()

    def remove(self):
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def write(self, new_content: str):
        # End with a new line
        # so that appending would not jumble up the text.
        self.path.write_text(new_content + '\n')
