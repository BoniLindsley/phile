#!/usr/bin/env python3
"""
----------------------------------
Trigger for launcher manipulations
----------------------------------
"""

# Standard libraries.
import asyncio
import contextlib
import functools
import types
import typing

# Internal modules.
import phile.launcher
import phile.pubsub_event
import phile.trigger


class Producer:
    """Update registry according to launcher status."""

    # TODO[Python version 3.10]: Change string to identifier.
    # Annotations are stored as strings and evalated later in 3.10.
    __Self = typing.TypeVar('__Self', bound='Producer')

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
        self._event_processing_tasks: list[asyncio.Task[typing.Any]] = []
        self._launcher_registry = launcher_registry
        self._trigger_registry = trigger_registry

    async def __aenter__(self: __Self) -> __Self:
        """Not reentrant."""
        async with contextlib.AsyncExitStack() as stack:
            stack.push_async_exit(self)
            tasks = self._event_processing_tasks
            create_task = asyncio.get_running_loop().create_task
            tasks.append(create_task(self._database_event_loop()))
            tasks.append(create_task(self._state_machine_event_loop()))
            launcher_names = self._launcher_registry.database.type.copy()
            bind = self._bind
            is_running = self._launcher_registry.state_machine.is_running
            on_start = self._on_start
            on_stop = self._on_stop
            for name in launcher_names:
                bind(name)
                if is_running(name):
                    on_start(name)
                else:
                    on_stop(name)
            stack.pop_all()
        return self

    async def __aexit__(
        self, exc_type: typing.Optional[typing.Type[BaseException]],
        exc_value: typing.Optional[BaseException],
        traceback: typing.Optional[types.TracebackType]
    ) -> None:
        try:
            current_tasks = self._event_processing_tasks.copy()
            for task in current_tasks:
                task.cancel()
            for task in current_tasks:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            self._event_processing_tasks.clear()
        finally:
            bound_launchers = self._bound_launchers
            unbind = self._unbind
            for name in bound_launchers.copy():
                unbind(name)
            assert not bound_launchers

    async def _database_event_loop(self) -> None:
        subscriber = phile.pubsub_event.Subscriber(
            publisher=self._launcher_registry.database.event_publisher
        )
        while True:
            event = await subscriber.pull()
            entry_name = event.entry_name
            if event.type == phile.launcher.Database.add:
                self._bind(entry_name)
            else:
                self._unbind(entry_name)

    async def _state_machine_event_loop(self) -> None:
        subscriber = phile.pubsub_event.Subscriber(
            publisher=(
                self._launcher_registry.state_machine.event_publisher
            )
        )
        while True:
            event = await subscriber.pull()
            entry_name = event.entry_name
            if event.type == phile.launcher.StateMachine.start:
                self._on_start(entry_name)
            else:
                self._on_stop(entry_name)

    def _on_start(self, launcher_name: str) -> None:
        start_trigger, stop_trigger = self._trigger_names(launcher_name)
        trigger_registry = self._trigger_registry
        trigger_registry.hide(start_trigger)
        trigger_registry.show(stop_trigger)

    def _on_stop(self, launcher_name: str) -> None:
        start_trigger, stop_trigger = self._trigger_names(launcher_name)
        trigger_registry = self._trigger_registry
        trigger_registry.hide(stop_trigger)
        trigger_registry.show(start_trigger)

    def _bind(self, launcher_name: str) -> None:
        bound_launchers = self._bound_launchers
        if launcher_name not in bound_launchers:
            bind = self._trigger_registry.bind
            call_soon = asyncio.get_running_loop().call_soon_threadsafe
            start_trigger, stop_trigger = self._trigger_names(
                launcher_name
            )
            state_machine = self._launcher_registry.state_machine
            bound_launchers.add(launcher_name)
            bind(
                start_trigger,
                functools.partial(
                    call_soon, state_machine.start_soon, launcher_name
                ),
            )
            bind(
                stop_trigger,
                functools.partial(
                    call_soon, state_machine.stop_soon, launcher_name
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
        start_trigger = 'launcher_' + launcher_name + '_start'
        stop_trigger = 'launcher_' + launcher_name + '_stop'
        return start_trigger, stop_trigger
