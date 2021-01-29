# Standard libraries.
import collections.abc
import os


class DirectorySnapshotDiff:

    def __init__(
        self,
        ref: 'DirectorySnapshot',
        snapshot: 'DirectorySnapshot',
        ignore_device: bool = ...
    ) -> None:
        ...

    @property
    def files_created(self) -> set[str]:
        ...

    @property
    def files_deleted(self) -> set[str]:
        ...

    @property
    def files_modified(self) -> set[str]:
        ...

    @property
    def files_moved(self) -> set[str]:
        ...

    @property
    def dirs_modified(self) -> set[str]:
        ...

    @property
    def dirs_moved(self) -> set[str]:
        ...

    @property
    def dirs_deleted(self) -> set[str]:
        ...

    @property
    def dirs_created(self) -> set[str]:
        ...


class DirectorySnapshot:
    recursive: bool = ...
    stat: collections.abc.Callable[[str], os.stat_result] = ...
    listdir: collections.abc.Callable[[str], os.DirEntry[str]] = ...

    def __init__(
        self,
        path: str,
        recursive: bool = ...,
        stat: collections.abc.Callable[[str], os.stat_result] = ...,
        listdir: collections.abc.Callable[[str], os.DirEntry[str]] = ...
    ) -> None:
        ...

    def walk(self, root: str) -> None:
        ...

    @property
    def paths(self) -> set[str]:
        ...

    def path(self, id: int) -> str:
        ...

    def inode(self, path: str) -> int:
        ...

    def isdir(self, path: str) -> int:
        ...

    def mtime(self, path: str) -> int:
        ...

    def size(self, path: str) -> int:
        ...

    def stat_info(self, path: str) -> os.stat_result:
        ...

    def __sub__(
        self, previous_dirsnap: 'DirectorySnapshot'
    ) -> DirectorySnapshotDiff:
        ...


class EmptyDirectorySnapshot:

    @staticmethod
    def path(_: int) -> None:
        ...

    @property
    def paths(self) -> set[str]:
        ...
