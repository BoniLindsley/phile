# Standard libraries.
import threading

# Internal modules.
from .. import events as _watchdog_events
from .. import utils as _watchdog_utils
from ..utils import bricks as _watchdog_utils_bricks

DEFAULT_EMITTER_TIMEOUT: float
DEFAULT_OBSERVER_TIMEOUT: float


class EventQueue(_watchdog_utils_bricks.SkipRepeatsQueue):
    ...


class ObservedWatch:

    def __init__(self, path: str, recursive: bool) -> None:
        ...

    @property
    def path(self) -> str:
        ...

    @property
    def is_recursive(self) -> bool:
        ...

    @property
    def key(self) -> tuple[str, bool]:
        ...

    def __eq__(self, watch: object) -> bool:
        ...

    def __ne__(self, watch: object) -> bool:
        ...

    def __hash__(self) -> int:
        ...


class EventEmitter(_watchdog_utils.BaseThread):

    def __init__(
        self,
        event_queue: EventQueue,
        watch: ObservedWatch,
        timeout: float = ...
    ) -> None:
        ...

    @property
    def timeout(self) -> float:
        ...

    @property
    def watch(self) -> ObservedWatch:
        ...

    def queue_event(
        self, event: _watchdog_events.FileSystemEvent
    ) -> None:
        ...

    def queue_events(self, timeout: float) -> None:
        ...

    def run(self) -> None:
        ...


class EventDispatcher(_watchdog_utils.BaseThread):

    def __init__(self, timeout: float = ...) -> None:
        ...

    @property
    def timeout(self) -> float:
        ...

    @property
    def event_queue(self) -> EventQueue:
        ...

    def dispatch_events(
        self, event_queue: EventQueue, timeout: float
    ) -> None:
        ...

    def run(self) -> None:
        ...


class BaseObserver(EventDispatcher):

    def __init__(
        self,
        emitter_class: type[EventEmitter],
        timeout: float = ...
    ) -> None:
        self._lock: threading.RLock
        self._watches: set[ObservedWatch]
        self._handlers: dict[
            ObservedWatch, set[_watchdog_events.FileSystemEventHandler]]
        self._emitter_for_watch: dict[ObservedWatch, EventEmitter]
        ...

    def _remove_emitter(self, emitter: EventEmitter) -> None:
        ...

    @property
    def emitters(self) -> set[EventEmitter]:
        ...

    def start(self) -> None:
        ...

    def schedule(
        self,
        event_handler: _watchdog_events.FileSystemEventHandler,
        path: str,
        recursive: bool = ...
    ) -> ObservedWatch:
        ...

    def add_handler_for_watch(
        self, event_handler: _watchdog_events.FileSystemEventHandler,
        watch: ObservedWatch
    ) -> None:
        ...

    def remove_handler_for_watch(
        self, event_handler: _watchdog_events.FileSystemEventHandler,
        watch: ObservedWatch
    ) -> None:
        ...

    def unschedule(self, watch: ObservedWatch) -> None:
        ...

    def unschedule_all(self) -> None:
        ...

    def on_thread_stop(self) -> None:
        ...

    def dispatch_events(
        self, event_queue: EventQueue, timeout: float
    ) -> None:
        ...
