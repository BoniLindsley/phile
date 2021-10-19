#!/usr/bin/env python3
"""
----------------------------------
Trigger for launcher manipulations
----------------------------------
"""

# Standard libraries.
import asyncio
import collections.abc
import contextlib
import functools
import types
import typing

# Internal modules.
import phile.launcher
import phile.asyncio.pubsub
import phile.trigger


class Producer:
    """Update registry according to launcher status."""

    # TODO[Python version 3.10]: Change string to identifier.
    # Annotations are stored as strings and evalated later in 3.10.
    __Self = typing.TypeVar("__Self", bound="Producer")

    def __init__(
        self,
        *args: typing.Any,
        launcher_registry: phile.launcher.Registry,
        trigger_registry: phile.trigger.Registry,
        **kwargs: typing.Any,
    ) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self._bound_launchers = set[str]()
        self._launcher_registry = launcher_registry
        self._registry_event_processing_tasks: asyncio.Task[typing.Any]
        self._trigger_registry = trigger_registry

    async def __aenter__(self: __Self) -> __Self:
        """Not reentrant."""
        try:
            self._registry_event_processing_tasks = (
                asyncio.get_running_loop().create_task(
                    self._process_registry_events()
                )
            )
            for name in self._launcher_registry.database.type.copy():
                self._bind(name)
                if self._launcher_registry.is_running(name):
                    self._on_start(name)
                else:
                    self._on_stop(name)
        except:  # pragma: no cover  # Defensive.
            await self.__aexit__(None, None, None)
            raise
        return self

    async def __aexit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType],
    ) -> None:
        try:
            await phile.asyncio.cancel_and_wait(
                self._registry_event_processing_tasks
            )
        finally:
            bound_launchers = self._bound_launchers
            unbind = self._unbind
            for name in bound_launchers.copy():
                unbind(name)
            assert not bound_launchers

    async def _process_registry_events(self) -> None:
        known_handlers: (
            dict[
                phile.launcher.EventType,
                collections.abc.Callable[[str], typing.Any],
            ]
        ) = {
            phile.launcher.EventType.START: self._on_start,
            phile.launcher.EventType.STOP: self._on_stop,
            phile.launcher.EventType.ADD: self._bind,
            phile.launcher.EventType.REMOVE: self._unbind,
        }
        async for event in (self._launcher_registry.event_queue):
            try:
                handler = known_handlers[event.type]
            except KeyError:  # pragma: no cover  # Defensive.
                continue
            handler(event.entry_name)

    def _on_start(self, launcher_name: str) -> None:
        start_trigger, stop_trigger = self._trigger_names(launcher_name)
        trigger_registry = self._trigger_registry
        trigger_registry.hide(start_trigger)
        with contextlib.suppress(phile.trigger.Registry.NotBound):
            trigger_registry.show(stop_trigger)

    def _on_stop(self, launcher_name: str) -> None:
        start_trigger, stop_trigger = self._trigger_names(launcher_name)
        trigger_registry = self._trigger_registry
        trigger_registry.hide(stop_trigger)
        with contextlib.suppress(phile.trigger.Registry.NotBound):
            trigger_registry.show(start_trigger)

    def _bind(self, launcher_name: str) -> None:
        bound_launchers = self._bound_launchers
        if launcher_name not in bound_launchers:
            bind = self._trigger_registry.bind
            call_soon = asyncio.get_running_loop().call_soon_threadsafe
            start_trigger, stop_trigger = self._trigger_names(
                launcher_name
            )
            launcher_registry = self._launcher_registry
            bound_launchers.add(launcher_name)
            bind(
                start_trigger,
                functools.partial(
                    call_soon, launcher_registry.start, launcher_name
                ),
            )
            bind(
                stop_trigger,
                functools.partial(
                    call_soon, launcher_registry.stop, launcher_name
                ),
            )
        else:  # pragma: no cover  # Defensive.
            pass

    def _unbind(self, launcher_name: str) -> None:
        try:
            self._bound_launchers.remove(launcher_name)
        except KeyError:  # pragma: no cover  # Defensive.
            return
        for trigger_name in self._trigger_names(launcher_name):
            # The `unbind` call triggers event callbacks
            # before the unbinding occurs.
            # In particular, event processing of the `unbind` call
            # sees that the trigger is still bound,
            # and even as shown if it was shown before unbinding.
            # This `remove` call ensures that callback for `unbind`
            # at least sees the trigger as hidden.
            self._trigger_registry.hide(trigger_name)
            self._trigger_registry.unbind(trigger_name)

    def _trigger_names(self, launcher_name: str) -> tuple[str, str]:
        start_trigger = "launcher_" + launcher_name + "_start"
        stop_trigger = "launcher_" + launcher_name + "_stop"
        return start_trigger, stop_trigger
