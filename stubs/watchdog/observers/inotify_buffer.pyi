# Internal modules.
from .. import events as _watchdog_events
from .. import utils as _watchdog_utils
from . import api as _watchdog_observer_api
from . import inotify_c as _watchdog_observers_inotify_c


class InotifyBuffer(_watchdog_utils.BaseThread):
    delay: float = ...

    def __init__(self, path: str, recursive: bool = ...) -> None:
        ...

    def read_event(self) -> _watchdog_observers_inotify_c.InotifyEvent:
        ...

    def on_thread_stop(self) -> None:
        ...

    def close(self) -> None:
        ...

    def run(self) -> None:
        ...
