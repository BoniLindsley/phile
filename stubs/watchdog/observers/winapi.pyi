import ctypes.wintypes
from typing import Any

LPVOID: Any
INVALID_HANDLE_VALUE: Any
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

class OVERLAPPED(ctypes.Structure): ...

kernel32: Any
ReadDirectoryChangesW: Any
CreateFileW: Any
CloseHandle: Any
CancelIoEx: Any
CreateEvent: Any
SetEvent: Any
WaitForSingleObjectEx: Any
CreateIoCompletionPort: Any
GetQueuedCompletionStatus: Any
PostQueuedCompletionStatus: Any
GetFinalPathNameByHandleW: Any

class FILE_NOTIFY_INFORMATION(ctypes.Structure): ...

LPFNI: Any
WATCHDOG_FILE_FLAGS = FILE_FLAG_BACKUP_SEMANTICS
WATCHDOG_FILE_SHARE_FLAGS: Any
WATCHDOG_FILE_NOTIFY_FLAGS: Any
BUFFER_SIZE: int
PATH_BUFFER_SIZE: int

def get_directory_handle(path: Any): ...
def close_directory_handle(handle: Any) -> None: ...
def read_directory_changes(handle: Any, path: Any, recursive: Any): ...

class WinAPINativeEvent:
    action: Any = ...
    src_path: Any = ...
    def __init__(self, action: Any, src_path: Any) -> None: ...
    @property
    def is_added(self): ...
    @property
    def is_removed(self): ...
    @property
    def is_modified(self): ...
    @property
    def is_renamed_old(self): ...
    @property
    def is_renamed_new(self): ...
    @property
    def is_removed_self(self): ...

def read_events(handle: Any, path: Any, recursive: Any): ...
