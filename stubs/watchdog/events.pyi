# Standard libraries.
import collections.abc
import logging
import re
import typing

EVENT_TYPE_MOVED: str
EVENT_TYPE_DELETED: str
EVENT_TYPE_CREATED: str
EVENT_TYPE_MODIFIED: str


class FileSystemEvent:
    event_type: str = ...
    is_directory: bool = ...
    is_synthetic: bool = ...

    def __init__(self, src_path: str) -> None:
        ...

    @property
    def src_path(self) -> str:
        ...

    @property
    def key(self) -> tuple[str, str, bool]:
        ...

    def __eq__(self, event: object) -> bool:
        ...

    def __ne__(self, event: object) -> bool:
        ...

    def __hash__(self) -> int:
        ...


class FileSystemMovedEvent(FileSystemEvent):
    event_type: str = ...

    def __init__(self, src_path: str, dest_path: str) -> None:
        ...

    @property
    def dest_path(self) -> str:
        ...

    @property
    def key(  # type: ignore[override]
        self
    ) -> tuple[str, str, str, bool]:
        ...


class FileDeletedEvent(FileSystemEvent):
    event_type: str = ...


class FileModifiedEvent(FileSystemEvent):
    event_type: str = ...


class FileCreatedEvent(FileSystemEvent):
    event_type: str = ...


class FileMovedEvent(FileSystemMovedEvent):
    ...


class DirDeletedEvent(FileSystemEvent):
    event_type: str = ...
    is_directory: bool = ...


class DirModifiedEvent(FileSystemEvent):
    event_type: str = ...
    is_directory: bool = ...


class DirCreatedEvent(FileSystemEvent):
    event_type: str = ...
    is_directory: bool = ...


class DirMovedEvent(FileSystemMovedEvent):
    is_directory: bool = ...


class FileSystemEventHandler:

    def dispatch(self, event: FileSystemEvent) -> None:
        ...

    def on_any_event(self, event: FileSystemEvent) -> None:
        ...

    def on_moved(
        self, event: typing.Union[DirMovedEvent, FileMovedEvent]
    ) -> None:
        ...

    def on_created(
        self, event: typing.Union[DirCreatedEvent, FileCreatedEvent]
    ) -> None:
        ...

    def on_deleted(
        self, event: typing.Union[DirDeletedEvent, FileDeletedEvent]
    ) -> None:
        ...

    def on_modified(
        self, event: typing.Union[DirModifiedEvent, FileModifiedEvent]
    ) -> None:
        ...


class PatternMatchingEventHandler(FileSystemEventHandler):

    def __init__(
        self,
        patterns: typing.Optional[list[str]] = ...,
        ignore_patterns: typing.Optional[list[str]] = ...,
        ignore_directories: bool = ...,
        case_sensitive: bool = ...
    ) -> None:
        ...

    @property
    def patterns(self) -> list[str]:
        ...

    @property
    def ignore_patterns(self) -> list[str]:
        ...

    @property
    def ignore_directories(self) -> bool:
        ...

    @property
    def case_sensitive(self) -> bool:
        ...

    def dispatch(self, event: FileSystemEvent) -> None:
        ...


class RegexMatchingEventHandler(FileSystemEventHandler):

    def __init__(
        self,
        regexes: typing.Optional[list[str]] = ...,
        ignore_regexes: typing.Optional[list[str]] = ...,
        ignore_directories: bool = ...,
        case_sensitive: bool = ...
    ) -> None:
        ...

    @property
    def regexes(self) -> list[re.Pattern[str]]:
        ...

    @property
    def ignore_regexes(self) -> list[re.Pattern[str]]:
        ...

    @property
    def ignore_directories(self) -> bool:
        ...

    @property
    def case_sensitive(self) -> bool:
        ...

    def dispatch(self, event: FileSystemEvent) -> None:
        ...


class LoggingEventHandler(FileSystemEventHandler):
    logger: logging.Logger = ...

    def __init__(
        self, logger: typing.Optional[logging.Logger] = ...
    ) -> None:
        ...

    def on_moved(
        self, event: typing.Union[DirMovedEvent, FileMovedEvent]
    ) -> None:
        ...

    def on_created(
        self, event: typing.Union[DirCreatedEvent, FileCreatedEvent]
    ) -> None:
        ...

    def on_deleted(
        self, event: typing.Union[DirDeletedEvent, FileDeletedEvent]
    ) -> None:
        ...

    def on_modified(
        self, event: typing.Union[DirModifiedEvent, FileModifiedEvent]
    ) -> None:
        ...


def generate_sub_moved_events(
    src_dir_path: str, dest_dir_path: str
) -> collections.abc.Iterator[typing.Union[DirMovedEvent, FileMovedEvent]
                              ]:
    ...


def generate_sub_created_events(
    src_dir_path: str
) -> collections.abc.Iterator[typing.Union[DirCreatedEvent,
                                           FileCreatedEvent]]:
    ...
