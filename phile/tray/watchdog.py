#!/usr/bin/env python3

# Standard library.
import asyncio
import collections.abc
import contextlib
import io
import json
import logging
import pathlib
import shutil
import typing
import warnings

# External dependencies.
import watchdog.events

# Internal packages.
import phile.asyncio.pubsub
import phile.configuration
import phile.tray
import phile.watchdog.asyncio

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]
_logger = logging.getLogger(_loader_name)


def get_path(
    name: str, tray_directory: pathlib.Path, tray_suffix: str
) -> pathlib.Path:
    return tray_directory / (name + tray_suffix)


def load(path: pathlib.Path, tray_suffix: str) -> phile.tray.Entry:
    # Buffer the file content to reduce the chance of file changes
    # introducing a race condition.
    content_stream = io.StringIO(path.read_text())
    path_name = path.name
    name = path_name.removesuffix(tray_suffix)
    if name == path_name and tray_suffix:
        warnings.warn(
            'Expected file suffix "{tray_suffix}". File was "{path}"'.
            format(path=path, tray_suffix=tray_suffix)
        )
    entry = phile.tray.Entry(name=name)
    del name
    # First line is the text icon.
    entry.text_icon = content_stream.readline().rstrip('\r\n')
    # Make sure there are content to read by reading one byte
    # and then resetting the offset before decoding.
    current_offset = content_stream.tell()
    if content_stream.read(1):
        content_stream.seek(current_offset)
        json_content = json.load(content_stream)
        # Get properties from the decoded structure.
        entry.icon_name = json_content.get('icon_name')
        icon_path = json_content.get('icon_path')
        if icon_path is not None:
            entry.icon_path = pathlib.Path(icon_path)
    return entry


def save(
    entry: phile.tray.Entry,
    tray_directory: pathlib.Path,
    tray_suffix: str,
) -> None:
    # Buffer for data to be written.
    content_stream = io.StringIO()
    # First line is the text icon.
    if entry.text_icon is not None:
        content_stream.write(entry.text_icon)
    # Only copy over values that are filled in.
    json_content: typing.Dict[str, str] = {}
    for key in ['icon_name', 'icon_path']:
        value = getattr(entry, key, None)
        if value is not None:
            json_content[key] = str(value)
    # If there is content to write, end the text icon line
    # before writing the JSON string.
    if json_content:
        content_stream.write('\n')
        json.dump(json_content, content_stream)
    # Copy over the buffer.
    entry_path = get_path(entry.name, tray_directory, tray_suffix)
    entry_path.parent.mkdir(parents=True, exist_ok=True)
    with entry_path.open('w+') as file_stream:
        content_stream.seek(0)
        shutil.copyfileobj(content_stream, file_stream)


class Target:

    def __init__(
        self,
        *args: typing.Any,
        configuration: phile.configuration.Entries,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._current_names = set[str]()
        self._tray_directory = (
            configuration.state_directory_path /
            configuration.tray_directory
        )
        self._tray_suffix = configuration.tray_suffix

    def close(self) -> None:
        for name in self._current_names.copy():
            self.pop(name)

    def pop(self, name: str) -> None:
        entry_path = get_path(
            name, self._tray_directory, self._tray_suffix
        )
        entry_path.unlink(missing_ok=True)
        self._current_names.discard(name)

    def set(self, entry: phile.tray.Entry) -> None:
        save(
            entry=entry,
            tray_directory=self._tray_directory,
            tray_suffix=self._tray_suffix
        )
        self._current_names.add(entry.name)


class Source:

    def __init__(
        self,
        *args: typing.Any,
        tray_registry: phile.tray.Registry,
        tray_suffix: str,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._tray_registry = tray_registry
        self._tray_suffix = tray_suffix

    async def process_watchdog_event_queue(
        self,
        event_queue: phile.watchdog.asyncio.EventQueue,
    ) -> None:
        async for event in event_queue:
            self.process_watchdog_event(event)

    def process_watchdog_event(
        self, event: watchdog.events.FileSystemEvent
    ) -> None:
        if event.is_directory:
            return
        self.process_path(path=pathlib.Path(event.src_path))
        if event.event_type != watchdog.events.EVENT_TYPE_MOVED:
            return
        # Let type checker know `dest_path` is an attribute.
        assert isinstance(event, watchdog.events.FileMovedEvent)
        self.process_path(path=pathlib.Path(event.dest_path))

    def process_path(self, path: pathlib.Path) -> None:
        if path.name.endswith(self._tray_suffix):
            try:
                tray_entry = load(
                    path=path, tray_suffix=self._tray_suffix
                )
            except FileNotFoundError:
                return
            except json.decoder.JSONDecodeError:
                _logger.debug('Tray file JSON is ill-formed: %s', path)
                return
            self._tray_registry.set(tray_entry)


@contextlib.asynccontextmanager
async def async_open(
    configuration: phile.configuration.Entries,
    observer: phile.watchdog.asyncio.BaseObserver,
    tray_registry: phile.tray.Registry,
) -> collections.abc.AsyncIterator[Source]:
    tray_directory = (
        configuration.state_directory_path / configuration.tray_directory
    )
    tray_directory.mkdir(exist_ok=True)
    tray_source = Source(
        tray_suffix=configuration.tray_suffix,
        tray_registry=tray_registry,
    )
    watchdog_event_queue = await observer.schedule(str(tray_directory))
    try:
        worker_task = asyncio.create_task(
            tray_source.process_watchdog_event_queue(
                event_queue=watchdog_event_queue
            )
        )
        try:
            yield tray_source
        finally:
            await phile.asyncio.cancel_and_wait(worker_task)
    finally:
        await observer.unschedule(str(tray_directory))
