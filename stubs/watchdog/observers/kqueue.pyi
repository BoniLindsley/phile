from typing import Any
from watchdog.events import DirCreatedEvent as DirCreatedEvent, DirDeletedEvent as DirDeletedEvent, DirModifiedEvent as DirModifiedEvent, DirMovedEvent as DirMovedEvent, EVENT_TYPE_CREATED as EVENT_TYPE_CREATED, EVENT_TYPE_DELETED as EVENT_TYPE_DELETED, EVENT_TYPE_MOVED as EVENT_TYPE_MOVED, FileCreatedEvent as FileCreatedEvent, FileDeletedEvent as FileDeletedEvent, FileModifiedEvent as FileModifiedEvent, FileMovedEvent as FileMovedEvent, generate_sub_moved_events as generate_sub_moved_events
from watchdog.observers.api import BaseObserver as BaseObserver, DEFAULT_EMITTER_TIMEOUT as DEFAULT_EMITTER_TIMEOUT, DEFAULT_OBSERVER_TIMEOUT as DEFAULT_OBSERVER_TIMEOUT, EventEmitter as EventEmitter
from watchdog.utils import platform as platform
from watchdog.utils.dirsnapshot import DirectorySnapshot as DirectorySnapshot

MAX_EVENTS: int
O_EVTONLY: int
WATCHDOG_OS_OPEN_FLAGS = O_EVTONLY
WATCHDOG_KQ_FILTER: Any
WATCHDOG_KQ_EV_FLAGS: Any
WATCHDOG_KQ_FFLAGS: Any

def absolute_path(path: Any): ...
def is_deleted(kev: Any): ...
def is_modified(kev: Any): ...
def is_attrib_modified(kev: Any): ...
def is_renamed(kev: Any): ...

class KeventDescriptorSet:
    def __init__(self) -> None: ...
    @property
    def kevents(self): ...
    @property
    def paths(self): ...
    def get_for_fd(self, fd: Any): ...
    def get(self, path: Any): ...
    def __contains__(self, path: Any): ...
    def add(self, path: Any, is_directory: Any) -> None: ...
    def remove(self, path: Any) -> None: ...
    def clear(self) -> None: ...

class KeventDescriptor:
    def __init__(self, path: Any, is_directory: Any) -> None: ...
    @property
    def fd(self): ...
    @property
    def path(self): ...
    @property
    def kevent(self): ...
    @property
    def is_directory(self): ...
    def close(self) -> None: ...
    @property
    def key(self): ...
    def __eq__(self, descriptor: Any) -> Any: ...
    def __ne__(self, descriptor: Any) -> Any: ...
    def __hash__(self) -> Any: ...

class KqueueEmitter(EventEmitter):
    def __init__(self, event_queue: Any, watch: Any, timeout: Any = ..., stat: Any = ...): ...
    def queue_event(self, event: Any) -> None: ...
    def queue_events(self, timeout: Any) -> None: ...
    def on_thread_stop(self) -> None: ...

class KqueueObserver(BaseObserver):
    def __init__(self, timeout: Any = ...) -> None: ...
