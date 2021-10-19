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
import phile.data


class Entry(pydantic.BaseModel):  # pylint: disable=no-member
    name: str
    icon_name: typing.Optional[str] = None
    icon_path: typing.Optional[pathlib.Path] = None
    text_icon: typing.Optional[str] = None


def entries_to_text(entries: typing.List[Entry]) -> str:
    return "".join(
        tray_entry.text_icon
        for tray_entry in entries
        if tray_entry.text_icon is not None
    )


class Registry(phile.data.Registry[str, Entry]):
    def add_entry(self, entry: Entry) -> None:
        super().set(entry.name, entry)


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
            tray_registry.current_values
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
        tray_event_view: (
            phile.asyncio.pubsub.View[phile.data.Event[str, Entry]]
        ),
    ) -> None:
        async for event in tray_event_view:
            current_value = entries_to_text(event.current_values)
            if self.current_value != current_value:
                self.current_value = current_value
                self.event_queue.put(current_value)
