from typing import Any
from watchdog.events import DirCreatedEvent as DirCreatedEvent, DirDeletedEvent as DirDeletedEvent, DirModifiedEvent as DirModifiedEvent, DirMovedEvent as DirMovedEvent, FileCreatedEvent as FileCreatedEvent, FileDeletedEvent as FileDeletedEvent, FileModifiedEvent as FileModifiedEvent, FileMovedEvent as FileMovedEvent
from watchdog.observers.api import BaseObserver as BaseObserver, DEFAULT_EMITTER_TIMEOUT as DEFAULT_EMITTER_TIMEOUT, DEFAULT_OBSERVER_TIMEOUT as DEFAULT_OBSERVER_TIMEOUT, EventEmitter as EventEmitter
from watchdog.utils.dirsnapshot import DirectorySnapshot as DirectorySnapshot, DirectorySnapshotDiff as DirectorySnapshotDiff

class PollingEmitter(EventEmitter):
    def __init__(self, event_queue: Any, watch: Any, timeout: Any = ..., stat: Any = ..., listdir: Any = ...): ...
    def on_thread_start(self) -> None: ...
    def queue_events(self, timeout: Any) -> None: ...

class PollingObserver(BaseObserver):
    def __init__(self, timeout: Any = ...) -> None: ...

class PollingObserverVFS(BaseObserver):
    def __init__(self, stat: Any, listdir: Any, polling_interval: int = ...) -> None: ...
