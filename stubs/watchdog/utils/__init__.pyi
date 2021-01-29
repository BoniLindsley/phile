# Standard libraries.
import threading
import types


class UnsupportedLibc(Exception):
    ...


class WatchdogShutdown(Exception):
    ...


class BaseThread(threading.Thread):
    daemon: bool = ...

    def __init__(self) -> None:
        ...

    @property
    def stopped_event(self) -> threading.Event:
        ...

    def should_keep_running(self) -> bool:
        ...

    def on_thread_stop(self) -> None:
        ...

    def stop(self) -> None:
        ...

    def on_thread_start(self) -> None:
        ...

    def start(self) -> None:
        ...


def load_module(module_name: str) -> types.ModuleType:
    ...


def load_class(dotted_path: str) -> type:
    ...
