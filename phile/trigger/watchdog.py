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
import typing

# Internal modules.
import phile.configuration
import phile.trigger
import phile.watchdog.asyncio

# TODO[mypy issue #1422]: __loader__ not defined
_loader_name: str = __loader__.name  # type: ignore[name-defined]


class Producer:
    """Update registry according to trigger file existence."""

    # TODO[Python version 3.10]: Change string to identifier.
    # Annotations are stored as strings and evalated later in 3.10.
    __Self = typing.TypeVar("__Self", bound="Producer")

    def __init__(
        self,
        *args: typing.Any,
        configuration: phile.configuration.Entries,
        observer: phile.watchdog.asyncio.BaseObserver,
        trigger_registry: phile.trigger.Registry,
        **kwargs: typing.Any,
    ) -> None:
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._bound_names = set[str]()
        self._observer = observer
        self._registry = trigger_registry
        self._trigger_directory = (
            configuration.state_directory_path
            / configuration.trigger_directory
        )
        self._trigger_suffix = configuration.trigger_suffix

    async def run(self) -> None:
        await asyncio.to_thread(
            self._trigger_directory.mkdir, parents=True, exist_ok=True
        )
        async with await self._observer.schedule(
            self._trigger_directory
        ) as watchdog_view:
            await asyncio.to_thread(self._bind_existing_triggers)
            try:
                async for path, exists in (  # pragma: no branch
                    phile.watchdog.asyncio.monitor_file_existence(
                        directory_path=self._trigger_directory,
                        expected_suffix=self._trigger_suffix,
                        watchdog_view=watchdog_view,
                    )
                ):
                    self._on_path_change(path, exists)
            finally:
                await asyncio.to_thread(self._unbind_all_triggers)

    def _bind_existing_triggers(self) -> None:
        for trigger in sorted(
            self._trigger_directory.glob("*" + self._trigger_suffix)
        ):
            self._on_path_change(trigger, True)

    def _unbind_all_triggers(self) -> None:
        for name in self._bound_names.copy():
            self._unbind(name)

    def _on_path_change(
        self,
        path: pathlib.Path,
        is_file: bool,
    ) -> None:
        trigger_name = path.stem
        bound_names = self._bound_names
        if is_file:
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


class View:
    """Show available triggers as files in a directory."""

    def __init__(
        self,
        *args: typing.Any,
        configuration: phile.configuration.Entries,
        observer: phile.watchdog.asyncio.BaseObserver,
        trigger_registry: phile.trigger.Registry,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._created_file_paths = set[pathlib.Path]()
        self._loop = asyncio.get_event_loop()
        self._observer = observer
        self._trigger_directory = (
            configuration.state_directory_path
            / configuration.trigger_directory
        )
        self._trigger_registry = trigger_registry
        self._trigger_suffix = configuration.trigger_suffix

    async def run(self, ready: asyncio.Future[None]) -> None:
        """
        Update files in a directory using status of triggers.

        Files are created and deleted in the directory
        ``configuration.trigger_root``.
        as triggers are shown and hidden respectively as determined by
        ``trigger_registry``.
        When file is deleted by the user,
        the corresponding trigger is activated.

        Before files are created or in ``trigger_root`` directory,
        a PID file is created and locked in the directory.
        This ensures that the directory is not used twice.
        For example, this can happen if an application is launched twice
        and then single deletions may activate triggers twice.

        :raises portalocker.LockException:
            If ``trigger_root`` has a locked PID file already.
        """
        async with self._monitor_directory() as watchdog_view, self._monitor_registry_callback():
            ready.set_result(None)
            async for path, exists in (
                phile.watchdog.asyncio.monitor_file_existence(
                    directory_path=self._trigger_directory,
                    expected_suffix=self._trigger_suffix,
                    watchdog_view=watchdog_view,
                )
            ):
                trigger_name = path.stem
                if not exists:
                    with contextlib.suppress(
                        phile.trigger.Registry.NotBound,
                        phile.trigger.Registry.NotShown,
                    ):
                        self._trigger_registry.activate(trigger_name)

    @contextlib.asynccontextmanager
    async def _monitor_directory(
        self,
    ) -> collections.abc.AsyncIterator[phile.watchdog.asyncio.EventView]:
        await asyncio.to_thread(
            self._trigger_directory.mkdir, parents=True, exist_ok=True
        )
        pid_lock = phile.trigger.PidLock(self._trigger_directory / "pid")
        await asyncio.to_thread(pid_lock.acquire)
        try:
            yield await self._observer.schedule(self._trigger_directory)
        finally:
            try:

                def delete_created_files() -> None:
                    created_file_paths = self._created_file_paths
                    for path in created_file_paths.copy():
                        path.unlink(missing_ok=True)
                        created_file_paths.discard(path)

                await asyncio.to_thread(delete_created_files)
            finally:
                await asyncio.to_thread(pid_lock.release)

    @contextlib.asynccontextmanager
    async def _monitor_registry_callback(
        self,
    ) -> collections.abc.AsyncIterator[None]:
        trigger_registry = self._trigger_registry

        callback_map: (
            dict[
                collections.abc.Callable[..., typing.Any],
                collections.abc.Callable[
                    [str], collections.abc.Awaitable[typing.Any]
                ],
            ]
        ) = {
            phile.trigger.Registry.show: self._show,
            phile.trigger.Registry.hide: self._hide,
            phile.trigger.Registry.activate: self._hide,
        }

        def on_registry_update(
            event_type: collections.abc.Callable[..., typing.Any],
            registry: phile.trigger.Registry,
            name: str,
        ) -> None:
            del registry
            try:
                callback = callback_map[event_type]
            except KeyError:
                return
            asyncio.run_coroutine_threadsafe(callback(name), self._loop)

        trigger_registry.event_callback_map.append(on_registry_update)
        try:
            show = callback_map[phile.trigger.Registry.show]
            for name in trigger_registry.visible_triggers:
                await show(name)
            yield
        finally:
            trigger_registry.event_callback_map.remove(
                on_registry_update
            )
            callback_map.clear()

    async def _show(self, name: str) -> None:
        path = self._to_path(name)
        await asyncio.to_thread(path.touch, exist_ok=True)
        self._created_file_paths.add(path)

    async def _hide(self, name: str) -> None:
        path = self._to_path(name)
        await asyncio.to_thread(path.unlink, missing_ok=True)
        self._created_file_paths.discard(path)

    def _to_path(self, name: str) -> pathlib.Path:
        return self._trigger_directory / (name + self._trigger_suffix)
