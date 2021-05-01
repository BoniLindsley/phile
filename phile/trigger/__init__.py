#!/usr/bin/env python3
"""
.. automodule:: phile.trigger.cli
.. automodule:: phile.trigger.tkinter
.. automodule:: phile.trigger.watchdog

--------------
Phile triggers
--------------
"""

# Standard libraries.
import collections.abc
import contextlib
import dataclasses
import functools
import logging
import os
import pathlib
import types
import typing
import warnings

# External dependencies.
import portalocker

# Internal packages.
import phile
import phile.data

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]
_logger = logging.getLogger(_loader_name)
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

    def __init__(self, lock_path: pathlib.Path) -> None:
        """
        :param ~pathlib.Path lock_path:
            Path to file representing ownership.
        """
        self._file_handle: typing.Optional[typing.IO[str]] = None
        """The lock file handle. Not :data:`None` if locked."""
        self._lock_path = lock_path
        """Path to file representing ownership."""

    def __del__(self) -> None:
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
        configuration: phile.Configuration,
        trigger_directory: pathlib.Path,
    ) -> None:
        """
        :param available_triggers:
            Triggers to add.
            This must be empty if `bind` is `False`.
        :parm bind: Whether to bind immediately.
        :param ~phile.Configuration configuration:
            Information on where data are saved.
        :param ~pathlib.Path trigger_directory:
            Directory containing trigger files
            if it :meth:`~pathlib.PurePath.is_absolute`.
            Otherwise, it is relative to
            :attr:`~phile.Configuration.trigger_root`.
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
        return path == self.get_trigger_path(path.stem)

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


_Decorated = typing.TypeVar(
    '_Decorated', bound=collections.abc.Callable[..., None]
)


def _dispatch_registry_event(method: _Decorated) -> _Decorated:

    @functools.wraps(method)
    def dispatch_and_call(
        registry: 'Registry', name: str, *args: typing.Any,
        **kwargs: typing.Any
    ) -> None:
        for callback in registry.event_callback_map:
            callback(dispatch_and_call, registry, name)
        method(registry, name, *args, **kwargs)

    return typing.cast(_Decorated, dispatch_and_call)


class Registry:

    # TODO[Python 3.10]: Change string to identifier.
    # Annotations are stored as strings and evalated later in 3.10.
    __Self = typing.TypeVar('__Self', bound='Registry')

    class AlreadyBound(ValueError):
        """A trigger was expected to not be bound."""

    class NotBound(ValueError):
        """A trigger was expected to be bound."""

    class NotShown(ValueError):
        """A trigger was expected to be shown."""

    # TODO[Python 3.10]: Change string to identifier.
    # Annotations are stored as strings and evalated later in 3.10.
    EventHandler = collections.abc.Callable[
        [collections.abc.Callable[..., typing.Any], 'Registry', str],
        typing.Any,
    ]

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.event_callback_map: list[Registry.EventHandler] = []
        self._callback_map: dict[str, NullaryCallable] = {}
        self.visible_triggers = set[str]()
        """Associates callbacks to each triggers."""

    @_dispatch_registry_event
    def bind(self, name: str, callback: NullaryCallable) -> None:
        actual_callback = self._callback_map.setdefault(name, callback)
        if actual_callback is not callback:
            raise self.AlreadyBound('Unable to bind trigger: ' + name)

    @_dispatch_registry_event
    def unbind(self, name: str) -> None:
        with contextlib.suppress(KeyError):
            self.visible_triggers.remove(name)
        with contextlib.suppress(KeyError):
            self._callback_map.pop(name)

    def is_bound(self, name: str) -> bool:
        return name in self._callback_map

    @_dispatch_registry_event
    def show(self, name: str) -> None:
        if name not in self._callback_map:
            raise self.NotBound(
                'Unable to show unbound trigger: ' + name
            )
        self.visible_triggers.add(name)

    @_dispatch_registry_event
    def hide(self, name: str) -> None:
        with contextlib.suppress(KeyError):
            self.visible_triggers.remove(name)

    def is_shown(self, name: str) -> bool:
        return name in self.visible_triggers

    def activate_if_shown(self, name: str) -> None:
        with contextlib.suppress(self.NotShown):
            self.activate(name)

    @_dispatch_registry_event
    def activate(self, name: str) -> None:
        try:
            callback = self._callback_map[name]
        except KeyError as error:
            raise self.NotBound(
                'Unable to activate unbound trigger: ' + name
            ) from error
        try:
            self.visible_triggers.remove(name)
        except KeyError as error:
            raise self.NotShown(
                'Unable to activate hidden trigger: ' + name
            ) from error
        callback()


class Provider:

    class NotBound(ValueError):
        """A trigger was expected to be bound by a specific provider."""

    # TODO[Python 3.10]: Change string to identifier.
    # Annotations are stored as strings and evalated later in 3.10.
    __Self = typing.TypeVar('__Self', bound='Provider')

    def __init__(
        self,
        *args: typing.Any,
        callback_map: dict[str, NullaryCallable],
        registry: Registry,
        **kwargs: typing.Any,
    ) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._bound_names = set[str]()
        self._callback_map = callback_map
        self._registry = registry

    def __enter__(self: __Self) -> __Self:
        self.bind()
        return self

    def __exit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType],
    ) -> typing.Optional[bool]:
        del exc_type
        del exc_value
        del traceback
        self.unbind()
        return None

    def bind(self) -> None:
        try:
            for name, callback in self._callback_map.items():
                self._registry.bind(name=name, callback=callback)
                self._bound_names.add(name)
        except:
            self.unbind()
            raise

    def unbind(self) -> None:
        try:
            unbound_names = set[str]()
            for name in self._bound_names:
                self._registry.unbind(name)
                unbound_names.add(name)
        finally:
            self._bound_names.difference_update(unbound_names)

    def is_bound(self) -> bool:
        assert not self._bound_names or (
            len(self._bound_names) == len(self._callback_map)
        ), 'Provider callbacks are partially bound.'
        return len(self._bound_names) == len(self._callback_map)

    def show_all(self) -> None:
        for name in self._bound_names:
            self._registry.show(name)

    def show(self, name: str) -> None:
        if name not in self._bound_names:
            raise self.NotBound(
                'Unable to show trigger not bound by provider: ' + name
            )
        self._registry.show(name)

    def hide(self, name: str) -> None:
        if name not in self._bound_names:
            raise self.NotBound(
                'Unable to hide trigger not bound by provider: ' + name
            )
        self._registry.hide(name)
