# Standard libraries.
import typing as _typing

# Internal modules.
from .. import events as _watchdog_events
from . import api as _watchdog_observer_api


class FSEventsEmitter(_watchdog_observer_api.EventEmitter):

    def __init__(
        self,
        event_queue: _watchdog_observer_api.EventQueue,
        watch: _watchdog_observer_api.ObservedWatch,
        timeout: float = ...,
    ) -> None:
        ...

    def on_thread_stop(self) -> None:
        ...

    def queue_events(  # type: ignore[override]
        self, timeout: float, events: list[_typing.Any]
    ) -> None:
        ...

    def run(self) -> None:
        ...


class FSEventsObserver(_watchdog_observer_api.BaseObserver):

    def __init__(self, timeout: float = ...) -> None:
        ...

    def schedule(
        self,
        event_handler: _watchdog_events.FileSystemEventHandler,
        path: str,
        recursive: bool = ...,
    ) -> _watchdog_observer_api.ObservedWatch:
        ...
