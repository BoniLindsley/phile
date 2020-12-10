#!/usr/bin/env python3
"""
--------------
Phile triggers
--------------
"""

# Standard libraries.
import dataclasses
import os
import pathlib
import typing
import warnings

# External dependencies.
import pathlib
import pathvalidate
import portalocker  # type: ignore[import]
import watchdog.events  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.data
import phile.watchdog_extras

Handler = typing.Callable[[str], None]
"""Signature of callables processing triggers."""


@dataclasses.dataclass(eq=False)
class File(phile.data.File):

    trigger_directory: dataclasses.InitVar[typing.Optional[pathlib.Path]
                                           ] = None

    @staticmethod
    def make_path(
        path_stem: str,
        *args,
        configuration: phile.configuration.Configuration,
        trigger_directory: pathlib.Path = pathlib.Path(),
        **kwargs
    ) -> pathlib.Path:
        return configuration.trigger_root / trigger_directory / (
            path_stem + configuration.trigger_suffix
        )


class PidLock:
    """
    Cooperative PID lock file.

    Similar to :class:`~portalocker.Lock`,
    but specialised for :mod:`~phile.trigger` PID file ownership.
    (There seems to be resource leak in :class:`~portalocker.Lock`
    when locking fails, as of 2020-10-12.)
    """

    def __init__(self, lock_path: pathlib.Path):
        """
        :param ~pathlib.Path lock_path:
            Path to file representing ownership.
        """
        self._file_handle: typing.Optional[typing.IO] = None
        """The lock file handle. Not :data:`None` if locked."""
        self._lock_path = lock_path
        """Path to file representing ownership."""

    def __del__(self):
        """Make sure the file was unlocked, and warn if not."""
        if self.locked():
            warnings.warn('File not unlocked before exiting.')
            self.release()

    def acquire(self) -> None:
        """
        Claim ownership of the PID file.

        :raises ~portalocker.LockException:
            If locking failed.
            For example, if already :meth:`locked`.
        """
        # Need the parent directory to exist before making the file.
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        # Open with "append" which creates the file if missing.
        file_handle = open(self._lock_path, 'a')
        try:
            portalocker.lock(
                file_handle, portalocker.LOCK_EX | portalocker.LOCK_NB
            )
        except portalocker.LockException:
            file_handle.close()
            raise
        # Acquiring the lock should not be possible
        # if the script already has a lock on it.
        # But checking anyway for logic issues.
        assert self._file_handle is None
        # Store the handle to close later.
        self._file_handle = file_handle
        # Write in the PID.
        file_handle.seek(0)
        file_handle.truncate()
        file_handle.writelines([str(os.getpid())])
        file_handle.flush()

    def release(self) -> None:
        """Release ownership of the PID file."""
        # If we did not lock the file,
        # unlocking would unlock someone else's lock.
        # So do not even attempt it if we do not have the handle.
        file_handle = self._file_handle
        if file_handle is None:
            return
        # Remove the PID first.
        file_handle.seek(0)
        file_handle.truncate()
        # Closing automatically unlocks.
        file_handle.close()
        # Mark as unlocked.
        self._file_handle = None

    def locked(self) -> bool:
        """:returns bool: Whether this object had obtained a lock."""
        return self._file_handle is not None


class EntryPoint:
    """
    Manages ownership of ``trigger_directory``.

    Different objects may try to use the same ``trigger_directory``
    to provide triggers for runtime interactions.
    For example, this can happen
    if the same application is launched multiple times.
    This :class:`EntryPoint` class uses cooperative locking
    to claim ownership of ``trigger_directory``.
    The claiming of ownership is called :meth:`bind`-ing here,
    as a parallel to port binding.
    By ensuring that an :class:`EntryPoint` :meth:`is_bound`
    before manipulating triggers,
    only one :class:`EntryPoint` can have ownership
    of a ``trigger_directory`` at a time,
    so different instances would not try to respond
    to the same trigger files at the same time.
    Note that this is `cooperative` locking,
    so other applications can still manipulate the ``trigger_directory``.
    It is up to implementations to check before doing so.
    """

    def __init__(
        self,
        *,
        configuration: phile.configuration.Configuration,
        trigger_directory: pathlib.Path,
    ) -> None:
        """
        :param ~phile.configuration.Configuration configuration:
            Information on where data are saved.
        :param ~pathlib.Path trigger_directory:
            Directory containing trigger files
            if it :meth:`~pathlib.PurePath.is_absolute`.
            Otherwise, it is relative to
            :attr:`~phile.configuration.Configuration.trigger_root`.
        """
        self.trigger_directory = (
            configuration.trigger_root / trigger_directory
        )
        """The directory containing trigger files."""
        self._trigger_suffix = configuration.trigger_suffix
        """Suffix that trigger files must end with."""
        self._pid_lock = PidLock(
            self.trigger_directory / configuration.pid_path
        )
        """Lock representing ownership of watched directory."""

    def add_trigger(self, trigger_name: str) -> None:
        """
        Create a trigger file to be activated.

        :param str trigger_name: Name of the trigger.
        :raises ResourceWarning:
            If ``self`` is not bound, as determined by :meth:`is_bound`.
        :raises ValueError: If the ``trigger_name`` is not valid.
        """
        if not self.is_bound():
            raise ResourceWarning(
                'Not adding trigger. Entry point not bound.'
            )
        trigger_path = self.get_trigger_path(trigger_name)
        trigger_path.touch()

    def remove_trigger(self, trigger_name: str) -> None:
        """
        Remove a trigger file.

        :param str trigger_name: Name of the trigger.
        :raises ResourceWarning:
            If ``self`` is not bound, as determined by :meth:`is_bound`.
        :raises ValueError: If the ``trigger_name`` is not valid.
        """
        if not self.is_bound():
            raise ResourceWarning(
                'Not removing trigger. Entry point not bound.'
            )
        trigger_path = self.get_trigger_path(trigger_name)
        try:
            trigger_path.unlink()
        except FileNotFoundError:
            pass

    def get_trigger_path(self, trigger_name: str) -> pathlib.Path:
        """
        :returns:
            File path representing the trigger
            with the given ``trigger_name``.
        :raises ValueError:
            If the ``trigger_name`` cannot be used as file name.
        """
        trigger_filename = pathlib.Path(
            trigger_name + self._trigger_suffix
        )
        pathvalidate.validate_filename(filename=trigger_filename)
        return self.trigger_directory / trigger_filename

    def bind(self) -> None:
        """
        Claim ownership of ``trigger_directory``.

        :raises ~portalocker.LockException:
            If the directory is already bound,
            by this instance or otherwise.
        """
        # This manages a resource,
        # so propagate the exception from the PID lock
        # if bind is already bound,
        # to detect resource leaks early.
        self._pid_lock.acquire()

    def is_bound(self) -> bool:
        """
        Whether the last :meth:`bind` succeeded
        without :meth:`unbind` being called after that.
        """
        return self._pid_lock.locked()

    def unbind(self) -> None:
        """
        Release ownership of ``trigger_directory``.

        Allow other :class:`EntryPoint`-s to :meth:`bind` to it.
        Only applicable if ``self`` :meth:`is_bound`.
        Does nothing if it is not.
        """
        if not self.is_bound():
            return
        for trigger_path in self.trigger_directory.glob(
            '*' + self._trigger_suffix
        ):
            # When Python 3.7 becomes deprecated,
            # replace with `trigger_path.unlink(missing_ok=True)`.
            try:
                trigger_path.unlink()
            except FileNotFoundError:  # pragma: no cover  # Defensive.
                pass
        self._pid_lock.release()
