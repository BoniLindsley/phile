#!/usr/bin/env python3
"""
.. automodule:: phile.tray.datetime
.. automodule:: phile.tray.imapclient
.. automodule:: phile.tray.notify
.. automodule:: phile.tray.psutil
.. automodule:: phile.tray.pyside2_window
.. automodule:: phile.tray.tmux
.. automodule:: phile.tray.watchdog
"""

# Standard library.
import asyncio
import bisect
import dataclasses
import enum
import pathlib
import typing
import warnings

# External dependencies.
import pydantic

# Internal packages.
import phile.asyncio
import phile.asyncio.pubsub


class Entry(pydantic.BaseModel):  # pylint: disable=no-member
    name: str
    icon_name: typing.Optional[str] = None
    icon_path: typing.Optional[pathlib.Path] = None
    text_icon: typing.Optional[str] = None


def entries_to_text(entries: typing.List[Entry]) -> str:
    return ''.join(
        tray_entry.text_icon for tray_entry in entries
        if tray_entry.text_icon is not None
    )


class EventType(enum.Enum):
    INSERT = enum.auto()
    POP = enum.auto()
    SET = enum.auto()


@dataclasses.dataclass
class Event:
    type: EventType
    index: int
    changed_entry: Entry
    current_entries: list[Entry]


class Registry:

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.current_entries: list[Entry] = []
        self.current_names: list[str] = []
        """Sorted cache, tracking names of entries."""
        self.event_queue = phile.asyncio.pubsub.Queue[Event]()

    def close(self) -> None:
        self.event_queue.close()

    def pop(self, name: str) -> None:
        index = bisect.bisect_left(self.current_names, name)
        try:
            if self.current_names[index] != name:
                return
        except IndexError:
            return
        old_entry = self.current_entries.pop(index)
        self.current_names.pop(index)
        self._put_event(
            Event(
                type=EventType.POP,
                index=index,
                changed_entry=old_entry,
                current_entries=self.current_entries.copy(),
            ),
        )

    def set(self, new_entry: Entry) -> None:
        new_entry = new_entry.copy()
        index = bisect.bisect_left(self.current_names, new_entry.name)
        try:
            old_entry = self.current_entries[index]
        except IndexError:
            self._insert(index, new_entry)
            return
        if old_entry.name != new_entry.name:
            self._insert(index, new_entry)
            return
        if new_entry == old_entry:
            return
        del old_entry
        self.current_entries[index] = new_entry
        self._put_event(
            Event(
                type=EventType.SET,
                index=index,
                changed_entry=new_entry,
                current_entries=self.current_entries.copy(),
            ),
        )

    def _insert(self, index: int, new_entry: Entry) -> None:
        self.current_entries.insert(index, new_entry)
        self.current_names.insert(index, new_entry.name)
        self._put_event(
            Event(
                type=EventType.INSERT,
                index=index,
                changed_entry=new_entry,
                current_entries=self.current_entries.copy(),
            ),
        )

    def _put_event(self, event: Event) -> None:
        try:
            self.event_queue.put(event)
        except phile.asyncio.pubsub.Node.AlreadySet:
            warnings.warn(
                'Registry should not be changed after closing.'
            )


class TextIcons:

    def __init__(
        self,
        *args: typing.Any,
        tray_registry: Registry,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.current_value = entries_to_text(
            tray_registry.current_entries
        )
        self.event_queue = phile.asyncio.pubsub.Queue[str]()
        self._worker_task = asyncio.create_task(
            self._run_tray_event_loop(
                tray_registry.event_queue.__aiter__()
            )
        )

    async def aclose(self) -> None:
        try:
            await phile.asyncio.cancel_and_wait(self._worker_task)
        finally:
            self.event_queue.close()

    async def _run_tray_event_loop(
        self,
        tray_event_view: phile.asyncio.pubsub.View[Event],
    ) -> None:
        async for event in tray_event_view:
            current_value = entries_to_text(event.current_entries)
            if self.current_value != current_value:
                self.current_value = current_value
                self.event_queue.put(current_value)
