# Standard libraries.
from collections import abc as _collections_abc
import ctypes as _ctypes
from ctypes import wintypes as _ctypes_wintypes

LPVOID = _ctypes_wintypes.LPVOID

INVALID_HANDLE_VALUE: int
FILE_NOTIFY_CHANGE_FILE_NAME: int
FILE_NOTIFY_CHANGE_DIR_NAME: int
FILE_NOTIFY_CHANGE_ATTRIBUTES: int
FILE_NOTIFY_CHANGE_SIZE: int
FILE_NOTIFY_CHANGE_LAST_WRITE: int
FILE_NOTIFY_CHANGE_LAST_ACCESS: int
FILE_NOTIFY_CHANGE_CREATION: int
FILE_NOTIFY_CHANGE_SECURITY: int
FILE_FLAG_BACKUP_SEMANTICS: int
FILE_FLAG_OVERLAPPED: int
FILE_LIST_DIRECTORY: int
FILE_SHARE_READ: int
FILE_SHARE_WRITE: int
FILE_SHARE_DELETE: int
OPEN_EXISTING: int
VOLUME_NAME_NT: int
FILE_ACTION_CREATED: int
FILE_ACTION_DELETED: int
FILE_ACTION_MODIFIED: int
FILE_ACTION_RENAMED_OLD_NAME: int
FILE_ACTION_RENAMED_NEW_NAME: int
FILE_ACTION_DELETED_SELF: int
FILE_ACTION_OVERFLOW: int
FILE_ACTION_ADDED = FILE_ACTION_CREATED
FILE_ACTION_REMOVED = FILE_ACTION_DELETED
FILE_ACTION_REMOVED_SELF = FILE_ACTION_DELETED_SELF
THREAD_TERMINATE: int
WAIT_ABANDONED: int
WAIT_IO_COMPLETION: int
WAIT_OBJECT_0: int
WAIT_TIMEOUT: int
ERROR_OPERATION_ABORTED: int


class OVERLAPPED(_ctypes.Structure):
    ...


kernel32: _ctypes.WinDLL  # type: ignore[name-defined]
ReadDirectoryChangesW: _collections_abc.Callable[[
    _ctypes_wintypes.HANDLE,
    _ctypes_wintypes.LPVOID,
    _ctypes_wintypes.DWORD,
    _ctypes_wintypes.BOOL,
    _ctypes_wintypes.DWORD,
    _ctypes_wintypes.LPDWORD,
    _ctypes.pointer[OVERLAPPED],
    _ctypes_wintypes.LPVOID,
], _ctypes_wintypes.BOOL]
CreateFileW: _collections_abc.Callable[[
    _ctypes_wintypes.LPCWSTR,
    _ctypes_wintypes.DWORD,
    _ctypes_wintypes.DWORD,
    _ctypes_wintypes.LPVOID,
    _ctypes_wintypes.DWORD,
    _ctypes_wintypes.DWORD,
    _ctypes_wintypes.HANDLE,
], _ctypes_wintypes.HANDLE]
CloseHandle: _collections_abc.Callable[[
    _ctypes_wintypes.HANDLE,
], _ctypes_wintypes.BOOL]
CancelIoEx: _collections_abc.Callable[[
    _ctypes_wintypes.HANDLE,
    _ctypes.pointer[OVERLAPPED],
], _ctypes_wintypes.BOOL]
CreateEvent: _collections_abc.Callable[[
    LPVOID,
    _ctypes_wintypes.BOOL,
    _ctypes_wintypes.BOOL,
    _ctypes_wintypes.LPCWSTR,
], _ctypes_wintypes.HANDLE]
SetEvent: _collections_abc.Callable[[
    _ctypes_wintypes.HANDLE,
], _ctypes_wintypes.BOOL]
WaitForSingleObjectEx: _collections_abc.Callable[[
    _ctypes_wintypes.HANDLE,
    _ctypes_wintypes.DWORD,
    _ctypes_wintypes.BOOL,
], _ctypes_wintypes.DWORD]
CreateIoCompletionPort: _collections_abc.Callable[[
    _ctypes_wintypes.HANDLE,
    _ctypes_wintypes.HANDLE,
    _ctypes_wintypes.LPVOID,
    _ctypes_wintypes.DWORD,
], _ctypes_wintypes.HANDLE]
GetQueuedCompletionStatus: _collections_abc.Callable[[
    _ctypes_wintypes.HANDLE,
    _ctypes_wintypes.LPVOID,
    _ctypes_wintypes.LPVOID,
    _ctypes.pointer[OVERLAPPED],
    _ctypes_wintypes.DWORD,
], _ctypes_wintypes.BOOL]
PostQueuedCompletionStatus: _collections_abc.Callable[[
    _ctypes_wintypes.HANDLE,
    _ctypes_wintypes.DWORD,
    _ctypes_wintypes.DWORD,
    _ctypes.pointer[OVERLAPPED],
], _ctypes_wintypes.BOOL]
GetFinalPathNameByHandleW: _collections_abc.Callable[[
    _ctypes_wintypes.HANDLE,
    _ctypes_wintypes.LPWSTR,
    _ctypes_wintypes.DWORD,
    _ctypes_wintypes.DWORD,
], _ctypes_wintypes.DWORD]


class FILE_NOTIFY_INFORMATION(_ctypes.Structure):
    ...


LPFNI = _ctypes.pointer[FILE_NOTIFY_INFORMATION]
WATCHDOG_FILE_FLAGS = FILE_FLAG_BACKUP_SEMANTICS
WATCHDOG_FILE_SHARE_FLAGS: int
WATCHDOG_FILE_NOTIFY_FLAGS: int
BUFFER_SIZE: int
PATH_BUFFER_SIZE: int


def get_directory_handle(path: str) -> _ctypes_wintypes.HANDLE:
    ...


def close_directory_handle(handle: _ctypes_wintypes.HANDLE) -> None:
    ...


def read_directory_changes(
    handle: _ctypes_wintypes.HANDLE,
    path: str,
    recursive: bool,
) -> tuple[list[bytes], int]:
    ...


class WinAPINativeEvent:
    action: _ctypes_wintypes.DWORD = ...
    src_path: str = ...

    def __init__(
        self,
        action: _ctypes_wintypes.DWORD,
        src_path: str,
    ) -> None:
        ...

    @property
    def is_added(self) -> bool:
        ...

    @property
    def is_removed(self) -> bool:
        ...

    @property
    def is_modified(self) -> bool:
        ...

    @property
    def is_renamed_old(self) -> bool:
        ...

    @property
    def is_renamed_new(self) -> bool:
        ...

    @property
    def is_removed_self(self) -> bool:
        ...


def read_events(
    handle: _ctypes_wintypes.HANDLE,
    path: str,
    recursive: bool,
) -> list[WinAPINativeEvent]:
    ...
