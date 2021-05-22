# Standard libraries.
from collections import abc as _collections_abc
import pathlib as _pathlib
import select as _select
import typing as _typing

# Internal modules.
from .. import events as _watchdog_events
from . import api as _watchdog_observer_api

MAX_EVENTS: int
O_EVTONLY: int
WATCHDOG_OS_OPEN_FLAGS: int
WATCHDOG_KQ_FILTER: int
WATCHDOG_KQ_EV_FLAGS: int
WATCHDOG_KQ_FFLAGS: int


def absolute_path(path: _pathlib.Path) -> _pathlib.Path:
    ...


def is_deleted(
    kev: _select.kevent,  # type: ignore[name-defined]
) -> bool:
    ...


def is_modified(
    kev: _select.kevent,  # type: ignore[name-defined]
) -> bool:
    ...


def is_attrib_modified(
    kev: _select.kevent,  # type: ignore[name-defined]
) -> bool:
    ...


def is_renamed(
    kev: _select.kevent,  # type: ignore[name-defined]
) -> bool:
    ...


class KeventDescriptorSet:

    def __init__(self) -> None:
        ...

    @property
    def kevents(
        self
    ) -> list[_select.kevent]:  # type: ignore[name-defined]
        ...

    @property
    def paths(self) -> list[_pathlib.Path]:
        ...

    def get_for_fd(self, fd: int) -> KeventDescriptor:
        ...

    def get(self, path: str) -> KeventDescriptor:
        ...

    def __contains__(self, path: str) -> bool:
        ...

    def add(self, path: str, is_directory: bool) -> None:
        ...

    def remove(self, path: str) -> None:
        ...

    def clear(self) -> None:
        ...


class KeventDescriptor:

    def __init__(self, path: str, is_directory: bool) -> None:
        ...

    @property
    def fd(self) -> int:
        ...

    @property
    def path(self) -> _pathlib.Path:
        ...

    @property
    def kevent(self) -> _select.kevent:  # type: ignore[name-defined]
        ...

    @property
    def is_directory(self) -> bool:
        ...

    def close(self) -> None:
        ...

    @property
    def key(self) -> tuple[_pathlib.Path, bool]:
        ...

    def __eq__(self, descriptor: _typing.Any) -> _typing.Any:
        ...

    def __ne__(self, descriptor: _typing.Any) -> _typing.Any:
        ...

    def __hash__(self) -> _typing.Any:
        ...


class KqueueEmitter(_watchdog_observer_api.EventEmitter):

    def __init__(
        self,
        event_queue: _watchdog_observer_api.EventEmitter,
        watch: _watchdog_observer_api.ObservedWatch,
        timeout: float = ...,
        stat: _collections_abc.Callable[[str], _typing.Any] = ...,
    ) -> None:
        ...

    def queue_event(
        self, event: _watchdog_events.FileSystemEvent
    ) -> None:
        ...

    def queue_events(self, timeout: float) -> None:
        ...

    def on_thread_stop(self) -> None:
        ...


class KqueueObserver(_watchdog_observer_api.BaseObserver):

    def __init__(self, timeout: float = ...) -> None:
        ...
