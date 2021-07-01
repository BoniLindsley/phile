#!/usr/bin/env python3

# TODO(BoniLindsley): Write unittest.
# TODO(BoniLindsley): Separate non-watchdog content.

# Standard library.
import asyncio
import collections.abc
import contextlib
import datetime
import logging
import pathlib
import typing

# External dependencies.
import watchdog.events

# Internal packages.
import phile.asyncio.pubsub
import phile.configuration
import phile.notify
import phile.watchdog.asyncio

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]
_logger = logging.getLogger(_loader_name)


def get_directory(
    configuration: phile.configuration.Entries,
) -> pathlib.Path:
    return (
        configuration.state_directory_path /
        configuration.notify_directory
    )


def get_path(
    name: str,
    configuration: phile.configuration.Entries,
) -> pathlib.Path:
    return (
        get_directory(configuration=configuration) /
        (name + configuration.notify_suffix)
    )


def load_from_path(
    path: pathlib.Path,
    configuration: phile.configuration.Entries,
) -> phile.notify.Entry:
    return phile.notify.Entry(
        name=path.name.removesuffix(configuration.notify_suffix),
        text=path.read_text(),
        modified_at=datetime.datetime.fromtimestamp(
            path.stat().st_mtime
        ),
    )


def load(
    name: str,
    configuration: phile.configuration.Entries,
) -> phile.notify.Entry:
    return load_from_path(
        path=get_path(name=name, configuration=configuration),
        configuration=configuration,
    )


def save(
    entry: phile.notify.Entry,
    configuration: phile.configuration.Entries,
) -> None:
    # Does not save modified at times.
    entry_path = get_path(
        name=entry.name,
        configuration=configuration,
    )
    entry_path.parent.mkdir(parents=True, exist_ok=True)
    entry_path.write_text(entry.text)


# TODO(BoniLindsley): Refactor common writing functionality?
# They are used in notify, tray, and to an extent triggers.
# They likely should subclass from a common base?
# But they might also be simple enough to not be worth refactoring.
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
        self._configuration = configuration

    def close(self) -> None:
        for name in self._current_names.copy():
            self.pop(name)

    def pop(self, name: str) -> None:
        entry_path = get_path(
            name=name, configuration=self._configuration
        )
        entry_path.unlink(missing_ok=True)
        self._current_names.discard(name)

    def set(self, entry: phile.notify.Entry) -> None:
        save(entry=entry, configuration=self._configuration)
        self._current_names.add(entry.name)


async def update_path(
    *,
    configuration: phile.configuration.Entries,
    notify_registry: phile.notify.Registry,
    path: pathlib.Path,
) -> bool:
    notify_entry: typing.Optional[phile.notify.Entry] = None
    try:
        notify_entry = await asyncio.to_thread(
            load_from_path, path=path, configuration=configuration
        )
    except FileNotFoundError:
        pass
    entry_name = path.name.removesuffix(configuration.notify_suffix)
    if notify_entry is None:
        _logger.debug('Lost notification %s', entry_name)
        notify_registry.discard(entry_name)
        return False
    _logger.debug('Found notification %s', entry_name)
    notify_registry.add_entry(notify_entry)
    return True


async def update_existing_paths(
    configuration: phile.configuration.Entries,
    notify_registry: phile.notify.Registry,
) -> set[pathlib.Path]:
    paths_found = set[pathlib.Path]()
    notify_directory = get_directory(configuration=configuration)
    notify_suffix = configuration.notify_suffix
    for path in notify_directory.glob('*' + notify_suffix):
        try:
            added = await update_path(
                configuration=configuration,
                notify_registry=notify_registry,
                path=path,
            )
        except IsADirectoryError:
            continue
        paths_found.add(path)
    return paths_found


async def process_watchdog_view(
    *,
    configuration: phile.configuration.Entries,
    notify_registry: phile.notify.Registry,
    ready: asyncio.Event,
    watchdog_view: collections.abc.AsyncIterable[
        watchdog.events.FileSystemEvent,
    ],
) -> None:
    notify_directory = get_directory(configuration=configuration)
    notify_suffix = configuration.notify_suffix
    current_names = set[str]()
    try:
        added_paths = await update_existing_paths(
            configuration=configuration, notify_registry=notify_registry
        )
        for path in added_paths:
            entry_name = path.name.removesuffix(notify_suffix)
            current_names.add(entry_name)
        ready.set()
        # Branch exiting into finally.
        # Covered in test_gracefully_stop_if_watchdog_queue_done
        # Not sure why it was not detected.
        async for path, exists in (  # pragma: no branch
            phile.watchdog.asyncio.monitor_file_existence(
                directory_path=notify_directory,
                expected_suffix=notify_suffix,
                watchdog_view=watchdog_view,
            )
        ):
            del exists
            added = await update_path(
                configuration=configuration,
                notify_registry=notify_registry,
                path=path,
            )
            entry_name = path.name.removesuffix(notify_suffix)
            if added:
                current_names.add(entry_name)
            else:
                current_names.discard(entry_name)
    finally:
        for entry_name in current_names:
            notify_registry.discard(entry_name)


@contextlib.asynccontextmanager
async def async_open(
    *,
    configuration: phile.configuration.Entries,
    notify_registry: phile.notify.Registry,
    observer: phile.watchdog.asyncio.BaseObserver,
) -> collections.abc.AsyncIterator[Target]:
    watchdog_view = await observer.schedule(
        get_directory(configuration=configuration)
    )
    try:
        ready = asyncio.Event()
        worker_task = asyncio.create_task(
            process_watchdog_view(
                configuration=configuration,
                notify_registry=notify_registry,
                ready=ready,
                watchdog_view=watchdog_view,
            )
        )
        try:
            await ready.wait()
            yield Target(configuration=configuration)
        finally:
            await phile.asyncio.cancel_and_wait(worker_task)
    finally:
        await watchdog_view.aclose()
