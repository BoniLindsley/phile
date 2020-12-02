#!/usr/bin/env python3

# Standard library.
import bisect
import contextlib
import dataclasses
import itertools
import pathlib
import typing


class SortableLoadData(typing.Protocol):
    """Requirements for use in :class:`~phile.data.SortedLoadCache`."""

    path: pathlib.Path
    """Path from which the data was loaded."""
    loaded: bool = False
    """Whether the data was successfully loaded from :data:`path`."""

    def __eq__(self, other) -> bool:
        ...

    def __lt__(self, other) -> bool:
        ...

    def load(self) -> None:
        self.loaded = self.path.is_file()


@dataclasses.dataclass
class File(SortableLoadData):
    """Initialisers are expected to use keyword arguments."""

    path: pathlib.Path
    """Path from which the data was loaded."""
    loaded: bool = False
    """Whether the data was successfully loaded from :data:`path`."""

    def __eq__(self, other) -> bool:
        pair = (self.path.name, self.path.parent)
        if isinstance(other, File):
            return pair == (other.path.name, other.path.parent)
        elif isinstance(other, pathlib.Path):
            return pair == (other.name, other.parent)
        else:
            return NotImplemented

    def __lt__(self, other) -> bool:
        pair = (self.path.name, self.path.parent)
        if isinstance(other, File):
            return pair < (other.path.name, other.path.parent)
        elif isinstance(other, pathlib.Path):
            return pair < (other.name, other.parent)
        else:
            return NotImplemented


_D = typing.TypeVar('_D', bound=SortableLoadData)
_D_co = typing.TypeVar('_D_co', bound=SortableLoadData, covariant=True)


class UpdateCallback(typing.Protocol[_D]):
    """
    Replacement for ``Callable[[int, _D, List[_D]], None]``.

    Calling a callable member is not handled correctly by mypy yet.
    Specifically, ``self.load(0)`` is treated as a two-argument call
    even if ``self.load`` is a callable variable.
    See: https://github.com/python/mypy/issues/708#issuecomment-667989040
    """

    def __call__(
        self, __index: int, __changed_data: _D,
        __tracked_data: typing.List[_D]
    ) -> None:
        ...


class CreateFile(typing.Protocol[_D_co]):
    """Replacement for ``Callable[[pathlib.Path], _D_co]``."""

    def __call__(self, __source_path: pathlib.Path) -> _D_co:
        ...


@dataclasses.dataclass
class SortedLoadCache(typing.Generic[_D]):
    """Collects loadable files into a sorted list."""

    @staticmethod
    def _noop_update(
        index: int, changed_data: _D, tracked_data: typing.List[_D]
    ) -> None:
        pass

    create_file: CreateFile[_D]
    """
    Called to create  a file object, possibly to be added to the cache.

    The ``loaded`` attribute of the returned ``_D`` data
    determines whether the ``load`` is successful.
    """
    on_insert: UpdateCallback[_D] = _noop_update
    """
    Called when an untracked file is found.

    :param index:
        The position at which the new data was inserted.
        So ``tracked_data[index] == changed_data``.
    :param changed_data:
        Content of the newly loaded data.
    :param tracked_data:
        The cache list after insertion.
    """
    on_pop: UpdateCallback[_D] = _noop_update
    """
    Called when a tracked notify file is deleted.

    :param index:
        The position at which the removed data was at.
        So ``tracked_data[index] != changed_data``.
    :param changed_data:
        Content of the removed data.
    :param tracked_data:
        The cache list after removal.
    """
    on_set: UpdateCallback[_D] = _noop_update
    """
    Called when a tracked notify file is modified.

    :param index:
        The position at which the update data was at.
        So ``tracked_data[index] != changed_data``.
    :param changed_data:
        Content of the updated data.
    :param tracked_data:
        The cache list after update.
    """
    tracked_data: typing.List[_D] = dataclasses.field(
        default_factory=list
    )
    """Keeps track of known data files."""

    def refresh(
        self, data_directory: pathlib.Path, data_file_suffix: str
    ) -> None:
        """
        Refresh :data:`tracked_data`
        to match the content of the given ``data_directory``.

        :param data_directory: The directory to search for files in.
        :param data_file_suffix:
            Files of the given suffix in ``data_directory`` are loaded.
        """
        tracked_paths = [data.path for data in self.tracked_data]
        globbed_paths = data_directory.glob('*' + data_file_suffix)
        self.update_paths(itertools.chain(tracked_paths, globbed_paths))

    def update_tracked(self) -> None:
        """Try to :meth:`update` every path of :data:`tracked_data`."""
        tracked_paths = [data.path for data in self.tracked_data]
        self.update_paths(tracked_paths)

    def update_paths(
        self, data_paths: typing.Iterable[pathlib.Path]
    ) -> None:
        """Try to :meth:`update` the given ``data_paths``."""
        for data_path in data_paths:
            self.update(data_path)

    def update(self, data_path: pathlib.Path) -> None:
        """
        Try to :data:`create` File` of ``data_path``
        and then load and add it to :data:`tracked_data`.

        :param data_path:
            Path of file to be loaded from.
            It is up to the :data:`create` callback
            to validate the name if necessary.

        Calls to :data:`on_insert`, :data:`on_pop` and :data:`on_set`
        depending on how :data:`tracked_data` is changed
        from the data load attempt.
        The :data:`tracked_data` is updated before the calls.
        """
        index = bisect.bisect_left(self.tracked_data, data_path)
        is_tracked = False
        file: _D
        try:
            file = self.tracked_data[index]
        except IndexError:
            file = self.create_file(data_path)
        else:
            is_tracked = True
        file.load()
        if not file.loaded:
            if is_tracked:
                file = self.tracked_data.pop(index)
                self.on_pop(index, file, self.tracked_data)
        elif is_tracked:
            self.tracked_data[index] = file
            self.on_set(index, file, self.tracked_data)
        else:
            self.tracked_data.insert(index, file)
            self.on_insert(index, file, self.tracked_data)
