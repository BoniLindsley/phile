#!/usr/bin/env python3
"""
.. automodule:: phile.notify.cli
.. automodule:: phile.notify.gui
"""

# Standard library.
import contextlib
import dataclasses
import datetime
import pathlib
import typing

# Internal packages.
import phile.configuration
import phile.data


@dataclasses.dataclass(eq=False)
class File(phile.data.File):
    modified_at: datetime.datetime = datetime.datetime.fromtimestamp(0)
    text: str = ''

    def __hash__(self):
        return hash(self.path)

    @property
    def creation_datetime(self) -> datetime.datetime:
        return self.modified_at

    @property
    def name(self) -> str:
        return self.title

    @classmethod
    def from_path_stem(
        cls,
        path_stem: str,
        *args,
        configuration: phile.configuration.Configuration,
        **kwargs,
    ) -> 'File':
        """Dataclasses do not allow keyword-only arguments."""
        assert 'path' not in kwargs
        kwargs['path'] = cls.make_path(
            configuration=configuration, path_stem=path_stem
        )
        return cls(*args, **kwargs)

    @staticmethod
    def make_path(
        *,
        configuration: phile.configuration.Configuration,
        path_stem: str,
    ) -> pathlib.Path:
        return configuration.notification_directory / (
            path_stem + configuration.notification_suffix
        )

    @staticmethod
    def check_path(
        *,
        configuration: phile.configuration.Configuration,
        path: pathlib.Path,
    ) -> bool:
        return (
            path.parent == configuration.notification_directory
            and path.suffix == configuration.notification_suffix
        )

    def read(self) -> str:
        self.load()
        return self.text

    def write(self, new_content: str) -> None:
        self.text = new_content + '\n'
        self.save()

    def append(self, additional_content: str) -> None:
        self.load()
        self.text += additional_content + '\n'
        self.save()

    def save(self) -> None:
        """Write content to file, and read new modified time."""
        self.path.write_text(self.text)
        self.load_modified_at()

    def load(self) -> None:
        """
        Loads content of :data:`~phile.data.File.path` as a notification.

        :raises FileNotFoundError:
            If :data:`~phile.data.File.path` does not exist.
        :raises IsADirectoryError:
            If :data:`~phile.data.File.path` resolves to a directory.

        Sets :data:`~phile.data.File.loaded`
        depending on whether the load was successful
        even if exceptions are raised.
        """
        self.loaded = False
        self.text = self.path.read_text()
        self.load_modified_at()
        self.loaded = True

    def load_modified_at(self) -> None:
        """Update stored data to reflect modified time of file."""
        self.modified_at = datetime.datetime.fromtimestamp(
            self.path.stat().st_mtime
        )

    def remove(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            self.path.unlink()

    @property
    def title(self) -> str:
        return self.path.stem

    @title.setter
    def title(self, new_title: str) -> None:
        self.path = self.path.with_name(new_title + self.path.suffix)


_D_contra = typing.TypeVar('_D_contra', contravariant=True)


class SingleParameterCallback(typing.Protocol[_D_contra]):
    """
    Replacement for ``Callable[[_D_contra], None]``.

    Calling a callable member is not handled correctly by mypy yet.
    Specifically, ``self.load(0)`` is treated as a two-argument call
    even if ``self.load`` is a callable variable.
    See: https://github.com/python/mypy/issues/708#issuecomment-667989040
    """

    def __call__(self, __arg_1: _D_contra) -> None:
        ...


PathsHandler = SingleParameterCallback[typing.Iterator[pathlib.Path]]
"""
Signature of callables for processing multiple :class:`~pathlib.Path`-s.
"""
