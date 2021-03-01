#!/usr/bin/env python3
"""
-----------------------------------------
Trigger manipulation using :mod:`tkinter`
-----------------------------------------
"""

# Standard libraries.
import asyncio
import collections.abc
import contextlib
import functools
import pathlib
import sys
import types
import typing

# External dependencies.
# TODO[portalocker issue #60]: Remove type: ignore.
# Type hinting is not yet activated.
import portalocker  # type: ignore[import]
import watchdog.observers

# Internal modules.
import phile
import phile.trigger
import phile.watchdog

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]


class Producer:
    """Update registry according to trigger file existence."""

    # TODO[Python version 3.10]: Change string to identifier.
    # Annotations are stored as strings and evalated later in 3.10.
    __Self = typing.TypeVar('__Self', bound='Producer')

    def __init__(
        self, *args: typing.Any, capabilities: phile.Capabilities,
        **kwargs: typing.Any
    ) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        configuration = capabilities[phile.Configuration]
        observer = capabilities[watchdog.observers.api.BaseObserver]
        self._registry = capabilities[phile.trigger.Registry]
        self._trigger_root = configuration.trigger_root
        self._trigger_suffix = configuration.trigger_suffix
        self._bound_names = set[str]()
        self._scheduler = phile.watchdog.Scheduler(
            path_filter=self._is_trigger_path,
            path_handler=self._on_path_change,
            watched_path=self._trigger_root,
            watching_observer=observer,
        )

    def __enter__(self: __Self) -> __Self:
        """Not reentrant."""
        try:
            self._scheduler.__enter__()
            for trigger in sorted(
                self._trigger_root.glob('*' + self._trigger_suffix)
            ):
                self._on_path_change(trigger)
        except:  # pragma: no cover  # Defensive.
            self._scheduler.__exit__(None, None, None)
            raise
        return self

    def __exit__(
        self, exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType]
    ) -> None:
        for name in self._bound_names.copy():
            self._unbind(name)
        self._scheduler.__exit__(exc_type, exc_value, traceback)

    def _on_path_change(self, path: pathlib.Path) -> None:
        trigger_name = path.stem
        bound_names = self._bound_names
        if path.is_file():
            if trigger_name not in bound_names:
                self._registry.bind(
                    trigger_name,
                    functools.partial(path.unlink, missing_ok=True),
                )
                self._registry.show(trigger_name)
                bound_names.add(trigger_name)
        else:
            self._unbind(trigger_name)

    def _unbind(self, name: str) -> None:
        try:
            self._bound_names.remove(name)
        except KeyError:
            pass
        else:
            self._registry.unbind(name)

    def _is_trigger_path(self, path: pathlib.Path) -> bool:
        return path.suffix == self._trigger_suffix


class View:
    """Show available triggers as files in a directory."""

    # TODO[Python version 3.10]: Change string to identifier.
    # Annotations are stored as strings and evalated later in 3.10.
    __Self = typing.TypeVar('__Self', bound='View')

    # TODO[portalocker issue #60]: Remove type: ignore.
    # Type hinting is not yet activated.
    class DirectoryInUse(
        portalocker.LockException  # type: ignore[misc]
    ):
        pass

    def __init__(
        self, *args: typing.Any, capabilities: phile.Capabilities,
        **kwargs: typing.Any
    ) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        configuration = capabilities[phile.Configuration]
        self._registry = capabilities[phile.trigger.Registry]
        self._observer = (
            capabilities[watchdog.observers.api.BaseObserver]
        )
        self._trigger_root = configuration.trigger_root
        self._trigger_suffix = configuration.trigger_suffix
        self._callback_map: (
            dict[collections.abc.Callable[..., typing.Any],
                 collections.abc.Callable[[str], typing.Any],
                 ]
        ) = {
            phile.trigger.Registry.show: self._show,
            phile.trigger.Registry.hide: self._hide,
            phile.trigger.Registry.activate: self._hide,
        }

        self._exit_stack = contextlib.ExitStack()

    def __enter__(self: __Self) -> __Self:
        """
        Update files in a directory using status of triggers.

        Files are created and deleted in the directory
        ``capabilities[phile.Configuration].trigger_root``.
        as triggers are shown and hidden respectively as determined by
        ``capabilities[phile.trigger.Registry]``.
        When file is deleted by the user,
        the corresponding trigger is activated.

        Before files are created or in ``trigger_root`` directory,
        a PID file is created and locked in the directory.
        This ensures that the directory is not used twice.
        For example, this can happen if an application is launched twice
        and then single deletions may activate triggers twice.

        :raises DirectoryInUse:
            If ``trigger_root`` has a locked PID file already.
        """
        registry = self._registry
        pid_lock = phile.trigger.PidLock(self._trigger_root / 'pid')
        with contextlib.ExitStack() as exit_stack:
            try:
                pid_lock.acquire()
                exit_stack.callback(pid_lock.release)
                exit_stack.enter_context(
                    phile.watchdog.Scheduler(
                        path_filter=self._is_trigger_path,
                        path_handler=self._on_path_change,
                        watched_path=self._trigger_root,
                        watching_observer=self._observer,
                    )
                )
                registry.event_callback_map.append(
                    self._on_registry_update
                )
                exit_stack.callback(
                    registry.event_callback_map.remove,
                    self._on_registry_update,
                )
                for name in registry.visible_triggers:
                    self._on_registry_update(
                        phile.trigger.Registry.show, registry, name
                    )
            except portalocker.LockException as error:
                raise self.DirectoryInUse(
                    'Trigger root has a locked PID file.'
                ) from error
            self._exit_stack = exit_stack.pop_all()
        return self

    def __exit__(
        self, exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType]
    ) -> None:
        self._exit_stack.close()

    def _on_registry_update(
        self, event_type: collections.abc.Callable[..., typing.Any],
        _registry: phile.trigger.Registry, name: str
    ) -> None:
        try:
            callback = self._callback_map[event_type]
        except KeyError:
            return
        callback(name)

    def _show(self, name: str) -> None:
        path = self._trigger_root / (name + self._trigger_suffix)
        path.touch(exist_ok=True)

    def _hide(self, name: str) -> None:
        path = self._trigger_root / (name + self._trigger_suffix)
        path.unlink(missing_ok=True)

    def _on_path_change(self, path: pathlib.Path) -> None:
        # When a trigger is activated from inside the application,
        # an instance of this class handles such an event
        # by deleting the trigger file corresponding to the trigger.
        # This is to let the user know that the trigger is activated
        # and is no longer available.
        # This deletion is detected for watchdog observer
        # after some unspecified time.
        # When that happens, this method is called
        # to handle the trigger file deletion event.
        #
        # When a trigger file is deleted,
        # this callback assumes that it is an attempt
        # to activate its corresponding trigger.
        # Since activation hides the trigger in internal bookkeeping,
        # in the situation described above,
        # the trigger would be set to hidden.
        # And so by checking that the trigger is shown
        # before activating it,
        # this avoids the double activation situation.
        trigger_name = path.stem
        if not path.is_file():
            self._registry.activate_if_shown(trigger_name)

    def _is_trigger_path(self, path: pathlib.Path) -> bool:
        return path.suffix == self._trigger_suffix


async def run(capabilities: phile.Capabilities) -> int:
    stop = asyncio.Event()
    trigger_registry = capabilities[phile.trigger.Registry]
    with phile.trigger.Provider(
        callback_map={
            _loader_name + '.stop':
                functools.partial(
                    asyncio.get_running_loop().call_soon_threadsafe,
                    stop.set
                )
        },
        registry=trigger_registry,
    ) as provider, View(capabilities=capabilities):
        provider.show_all()
        await stop.wait()
    return 0


def main(
    argv: typing.Optional[list[str]] = None
) -> int:  # pragma: no cover
    if argv is None:
        argv = sys.argv
    capabilities = phile.Capabilities()
    capabilities.set(phile.Configuration())
    capabilities.set(phile.trigger.Registry())
    with phile.watchdog.observers.open() as observer:
        capabilities[watchdog.observers.api.BaseObserver] = observer
        asyncio.run(run(capabilities))
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
