#!/usr/bin/env python3
"""
.. automodule:: phile.notify.cli
.. automodule:: phile.notify.pyside2
.. automodule:: phile.notify.watchdog
"""

# Standard library.
import dataclasses
import datetime
import typing

# Internal packages.
import phile.data


@dataclasses.dataclass
class Entry:
    name: str
    text: str = ''
    modified_at: typing.Optional[datetime.datetime] = None


class Registry(phile.data.Registry[str, Entry]):

    def add_entry(self, entry: Entry) -> None:
        super().set(entry.name, entry)
