#!/usr/bin/env python3
"""
--------------
Phile triggers
--------------
"""

# Standard libraries.
import dataclasses
import logging
import os
import pathlib
import types
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

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""

NullaryCallable = typing.Callable[[], typing.Any]


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
        available_triggers: typing.Set[str] = set(),
        bind: bool = False,
        callback_map: typing.Dict[str, NullaryCallable] = {},
        configuration: phile.configuration.Configuration,
        trigger_directory: pathlib.Path,
    ) -> None:
        """
        :param available_triggers:
            Triggers to add.
            This must be empty if `bind` is `False`.
        :parm bind: Whether to bind immediately.
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
        self.callback_map: typing.Dict[
            str,
            NullaryCallable] = (callback_map if callback_map else {})
        """Keeps track which callback handles which trigger."""
        self.available_triggers: typing.Set[str] = set()
        """Triggers that has been added and not removed nor used."""
        if bind:
            self.bind()
            for trigger_name in available_triggers:
                self.add_trigger(trigger_name)

    def __enter__(self) -> 'EntryPoint':
        self.bind()
        return self

    def __exit__(
        self, exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType]
    ) -> typing.Optional[bool]:
        self.unbind()
        return None

    def activate_trigger(self, trigger_path: pathlib.Path) -> None:
        """
        Calls callback associated with the given ``trigger_path``.

        :param trigger_path:
            Must be a trigger path, as determined by :meth:`check_path`.

        It is only activated if the path does not exist anymore,
        if the trigger is available,
        and if there is an associated callback.
        The trigger becomes unavailable after activation.
        """
        if trigger_path.exists():
            return
        trigger_name = trigger_path.stem
        try:
            self.available_triggers.remove(trigger_name)
            trigger_callback = self.callback_map[trigger_name]
        except KeyError:
            return
        trigger_callback()

    def add_trigger(self, trigger_name: str) -> None:
        """
        Create a trigger file to be activated.

        :param str trigger_name: Name of the trigger.
        :raises ResourceWarning:
            If ``self`` is not bound, as determined by :meth:`is_bound`.
        :raises ValueError: If the ``trigger_name`` is not valid.

        The trigger added must already have a callback.
        """
        if not self.is_bound():
            raise ResourceWarning(
                'Not adding trigger. Entry point not bound.'
            )
        assert trigger_name in self.callback_map
        self.available_triggers.add(trigger_name)
        self.get_trigger_path(trigger_name).touch()

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
        self.available_triggers.discard(trigger_name)
        self.get_trigger_path(trigger_name).unlink(missing_ok=True)

    def check_path(self, path: pathlib.Path) -> bool:
        try:
            valid_trigger_path = self.get_trigger_path(path.stem)
        except ValueError:
            return False
        return valid_trigger_path == path

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
            trigger_path.unlink(missing_ok=True)
        self._pid_lock.release()
