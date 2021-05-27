#!/usr/bin/env python3
"""
.. automodule:: phile.tray.gui
.. automodule:: phile.tray.publishers
.. automodule:: phile.tray.tmux
"""

# Standard library.
import asyncio
import bisect
import collections.abc
import contextlib
import dataclasses
import enum
import functools
import io
import json
import pathlib
import shutil
import typing
import warnings

# External dependencies.
import watchdog.events

# Internal packages.
import phile
import phile.configuration
import phile.data
import phile.pubsub_event
import phile.watchdog.asyncio


@dataclasses.dataclass(eq=False)
class File(phile.data.File):
    icon_name: typing.Optional[str] = None
    icon_path: typing.Optional[pathlib.Path] = None
    text_icon: typing.Optional[str] = None

    @staticmethod
    def make_path(
        path_stem: str,
        *args: typing.Any,
        configuration: phile.Configuration,
        **kwargs: typing.Any,
    ) -> pathlib.Path:
        return configuration.tray_directory / (
            path_stem + configuration.tray_suffix
        )

    def load(self) -> bool:
        """
        Parse tray file for a tray icon to be displayed.

        The input file should start with a single line
        that can be displayed in a text tray environment such as `tmux`.

        The remaining lines should describe the request in json format.
        It should contain the following keys:

        * `icon_path` or `icon_name`: The latter is searched for
          from the underlying theme setup.

        It should not contan any other keys,
        and may be ignored, subject to implementation details.
        """

        # Buffer the file content to reduce the chance of file changes
        # introducing a race condition.
        try:
            content_stream = io.StringIO(self.path.read_text())
        except (FileNotFoundError, IsADirectoryError):
            return False
        # First line is the text icon.
        # Do not write content yet in case JSON decoding fails.
        text_icon = content_stream.readline().rstrip('\r\n')
        # Make sure there are content to read by reading one byte
        # and then resetting the offset before decoding.
        current_offset = content_stream.tell()
        if content_stream.read(1):
            content_stream.seek(current_offset)
            try:
                json_content = json.load(content_stream)
            except json.decoder.JSONDecodeError:
                return False
        else:
            json_content = {}
        # Get properties from the decoded structure.
        self.text_icon = text_icon
        self.icon_name = json_content.get('icon_name')
        icon_path = json_content.get('icon_path')
        if icon_path is not None:
            self.icon_path = pathlib.Path(icon_path)
        else:
            self.icon_path = None
        return True

    def save(self) -> None:
        # Buffer for data to be written.
        content_stream = io.StringIO()
        # First line is the text icon.
        if self.text_icon is not None:
            content_stream.write(self.text_icon)
        # Only copy over values that are filled in.
        json_content: typing.Dict[str, str] = {}
        for key in ['icon_name', 'icon_path']:
            value = getattr(self, key, None)
            if value is not None:
                json_content[key] = str(value)
        # If there is content to write, end the text icon line
        # before writing the JSON string.
        if json_content:
            content_stream.write('\n')
            json.dump(json_content, content_stream)
        # Copy over the buffer.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('w+') as file_stream:
            content_stream.seek(0)
            shutil.copyfileobj(content_stream, file_stream)


def files_to_text(files: typing.List[File]) -> str:
    return ''.join(
        tray_file.text_icon for tray_file in files
        if tray_file.text_icon is not None
    )


Entry = File


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
        self.event_publisher = phile.pubsub_event.Publisher[Event]()

    def update(self, data_path: pathlib.Path) -> None:
        index = bisect.bisect_left(self.current_entries, data_path)
        is_tracked = False
        entry: Entry
        event_type: EventType
        try:
            entry = self.current_entries[index]
        except IndexError:
            pass
        else:
            is_tracked = (entry.path == data_path)
        if not is_tracked:
            entry = Entry(data_path)
        if not entry.load():
            if is_tracked:
                entry = self.current_entries.pop(index)
                event_type = EventType.POP
            else:
                return
        elif is_tracked:
            self.current_entries[index] = entry
            event_type = EventType.SET
        else:
            self.current_entries.insert(index, entry)
            event_type = EventType.INSERT
        self.event_publisher.push(
            Event(
                type=event_type,
                index=index,
                changed_entry=entry,
                current_entries=self.current_entries.copy(),
            ),
        )


@contextlib.asynccontextmanager
async def provide_registry(
    configuration: phile.configuration.Entries,
    observer: phile.watchdog.asyncio.BaseObserver,
) -> collections.abc.AsyncIterator[Registry]:
    tray_directory = (
        configuration.state_directory_path / configuration.tray_directory
    )
    tray_suffix = configuration.tray_suffix
    tray_registry = Registry()
    ready = asyncio.get_running_loop().create_future()
    try:

        async def propagate_tray_events() -> None:
            async with observer.open(
                tray_directory
            ) as observer_event_publisher:
                observer_event_subscriber = (
                    phile.pubsub_event.Subscriber(
                        publisher=observer_event_publisher,
                    )
                )
                ready.set_result(None)
                FileMovedEvent = watchdog.events.FileMovedEvent
                EVENT_TYPE_MOVED = (  # pylint: disable=invalid-name
                    watchdog.events.EVENT_TYPE_MOVED
                )
                while event := await observer_event_subscriber.pull():
                    if event.is_directory:
                        continue
                    path = pathlib.Path(event.src_path)
                    if path.suffix == tray_suffix:
                        tray_registry.update(path)
                    if event.event_type != EVENT_TYPE_MOVED:
                        continue
                    # Let type checker know `dest_path` is an attribute.
                    assert isinstance(event, FileMovedEvent)
                    path = pathlib.Path(event.dest_path)
                    if path.suffix == tray_suffix:
                        tray_registry.update(path)

        publisher_task = asyncio.create_task(propagate_tray_events())
        try:
            # Ensure the task is ready to not miss events.
            await ready
            yield tray_registry
        finally:
            # Defensive.
            # It should always cancel because no one else has the task.
            if publisher_task.cancel():  # pragma: no branch
                with contextlib.suppress(asyncio.CancelledError):
                    await publisher_task
    finally:
        tray_registry.event_publisher.stop()


class FullTextPublisher(phile.pubsub_event.Publisher[str]):
    pass


@contextlib.asynccontextmanager
async def provide_full_text(
    tray_registry: Registry,
) -> collections.abc.AsyncIterator[FullTextPublisher]:
    event_publisher = FullTextPublisher()
    ready = asyncio.get_running_loop().create_future()
    try:

        async def propagate_tray_events() -> None:
            registry_event_subscriber = phile.pubsub_event.Subscriber(
                publisher=tray_registry.event_publisher,
            )
            ready.set_result(None)
            while True:
                event = await registry_event_subscriber.pull()
                event_publisher.push(
                    files_to_text(event.current_entries)
                )

        publisher_task = asyncio.create_task(propagate_tray_events())
        try:
            # Ensure the task is ready to not miss events.
            await ready
            yield event_publisher
        finally:
            # Defensive.
            # It should always cancel because no one else has the task.
            if publisher_task.cancel():  # pragma: no branch
                with contextlib.suppress(asyncio.CancelledError):
                    await publisher_task
    finally:
        event_publisher.stop()
