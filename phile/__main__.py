#!/usr/bin/env python3

# Standard library.
import argparse
import asyncio
import collections.abc
import contextlib
import dataclasses
import functools
import sys
import types
import typing

# External dependencies.
import keyring
import watchdog.observers

# Internal packages.
import phile
import phile.asyncio
import phile.capability
import phile.capability.asyncio
import phile.capability.pyside2
import phile.capability.tmux
import phile.tray.publishers.battery
import phile.tray.publishers.cpu
import phile.tray.publishers.datetime
import phile.tray.publishers.imap_idle
import phile.tray.publishers.memory
import phile.tray.publishers.network
import phile.tray.publishers.notify_monitor
import phile.tray.publishers.update
import phile.tray.tmux
import phile.trigger
import phile.trigger.cli
import phile.watchdog

NullaryCallable = typing.Callable[[], typing.Any]
Launcher = typing.Callable[[phile.Capabilities], typing.Coroutine]
LauncherEntry = tuple[Launcher, set[type]]

default_launchers: typing.Dict[str, LauncherEntry] = {
    #'imap-idle': (
    #    phile.tray.publishers.imap_idle.run,
    #    {
    #        phile.Configuration,
    #        keyring.backend.KeyringBackend,
    #    },
    #),
    'tray-battery':
        (phile.tray.publishers.battery.run, {
            phile.Configuration,
        }),
    'tray-cpu': (phile.tray.publishers.cpu.run, {
        phile.Configuration,
    }),
    'tray-datetime':
        (phile.tray.publishers.datetime.run, {
            phile.Configuration,
        }),
    'tray-memory':
        (phile.tray.publishers.memory.run, {
            phile.Configuration,
        }),
    'tray-network':
        (phile.tray.publishers.network.run, {
            phile.Configuration,
        }),
    'tray-notify': (
        phile.tray.publishers.notify_monitor.run,
        {
            phile.Configuration,
            watchdog.observers.api.BaseObserver,
        },
    ),
    'tray-tmux': (
        phile.tray.tmux.run,
        {
            phile.Configuration,
            phile.tmux.control_mode.Client,
            watchdog.observers.api.BaseObserver,
        },
    ),
}


@dataclasses.dataclass
class TaskRegistry:
    """Keeps track of existing tasks and how to start new tasks."""

    class MissingCapability(RuntimeError):
        pass

    capabilities: phile.Capabilities
    launchers: types.MappingProxyType[
        str, LauncherEntry] = types.MappingProxyType(default_launchers)

    def __post_init__(self) -> None:
        self.running_tasks: dict[str, asyncio.Task[typing.Any]] = {}
        capability_set = set(self.capabilities.keys())
        self.usable_launcher_names = {
            name
            for name, launcher_entry in self.launchers.items()
            if not launcher_entry[1].difference(capability_set)
        }

    def create_task(self, name: str) -> asyncio.Task[typing.Any]:
        assert name not in self.running_tasks
        launcher_entry = self.launchers[name]
        if name not in self.usable_launcher_names:
            required_launcher_capabilities = launcher_entry[1]
            missing_capabilities = (
                required_launcher_capabilities.difference(
                    self.capabilities
                )
            )
            raise TaskRegistry.MissingCapability(
                f"Launcher {name} requires {missing_capabilities}."
            )
        launcher = launcher_entry[0]
        self.running_tasks[name] = task = asyncio.create_task(
            launcher(self.capabilities), name=name
        )
        task.add_done_callback(self.on_task_done)
        return task

    def cancel_task(self, name: str) -> None:
        assert name in self.running_tasks
        self.running_tasks[name].cancel()

    def on_task_done(self, task: asyncio.Task[typing.Any]) -> None:
        self.running_tasks.pop(task.get_name())


class TriggerProvider(phile.trigger.Provider):
    """Provides triggers to start and stop tasks."""

    __Self = typing.TypeVar('__Self', bound='TriggerProvider')

    def __init__(
        self,
        *args: typing.Any,
        capabilities: phile.Capabilities,
        **kwargs: typing.Any,
    ) -> None:
        self._capabilities = capabilities
        self.start_prefix = 'start-task_'
        self.stop_prefix = 'stop-task_'
        self.task_registry = TaskRegistry(capabilities=capabilities)
        callbacks = self.get_triggers()
        trigger_registry = capabilities[phile.trigger.Registry]
        super().__init__(
            *args,
            callback_map=callbacks,
            registry=trigger_registry,
            **kwargs,
        )

    def __enter__(self: __Self) -> __Self:
        super().__enter__()
        for task_name in self.task_registry.usable_launcher_names:
            self.create_task(task_name)
        return self

    def get_triggers(self) -> dict[str, NullaryCallable]:
        callbacks: dict[str, NullaryCallable] = {}
        usable_launchers = {
            name: launcher
            for (name, launcher) in self.task_registry.launchers.items()
            if name in self.task_registry.usable_launcher_names
        }
        # TODO[mypy issue #4717]: Remove `ignore[misc]`.
        # Cannot use abstract class.
        loop = self._capabilities[
            asyncio.events.AbstractEventLoop  # type: ignore[misc]
        ]
        for task_name in usable_launchers:
            callbacks[self.start_prefix + task_name] = functools.partial(
                loop.call_soon_threadsafe,
                self.create_task,
                task_name,
            )
            callbacks[self.stop_prefix + task_name] = functools.partial(
                self.task_registry.cancel_task, task_name
            )
        return callbacks

    def create_task(self, task_name: str) -> asyncio.Task[typing.Any]:
        self.hide(self.start_prefix + task_name)
        self.show(self.stop_prefix + task_name)
        task = self.task_registry.create_task(name=task_name)
        task.add_done_callback(self.on_task_done)
        return task

    def on_task_done(self, task: asyncio.Task[typing.Any]) -> None:
        task_name = task.get_name()
        with contextlib.suppress(
            ResourceWarning, phile.trigger.Provider.NotBound
        ):
            self.hide(self.stop_prefix + task_name)
            self.show(self.start_prefix + task_name)


async def open_prompt(capabilities: phile.Capabilities) -> None:
    # TODO[mypy issue #4717]: Remove `ignore[misc]`.
    # Cannot use abstract class.
    loop = capabilities[asyncio.AbstractEventLoop]  # type: ignore[misc]
    prompt = phile.trigger.cli.Prompt(capabilities=capabilities)
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(
        functools.partial(asyncio.StreamReaderProtocol, reader),
        prompt.stdin
    )
    writer = asyncio.StreamWriter(
        *(
            await loop.connect_write_pipe(
                asyncio.streams.FlowControlMixin, prompt.stdout
            )
        ), reader, loop
    )
    prompt.preloop()
    if prompt.intro:
        writer.write(prompt.intro)
    is_stopping = False
    while not is_stopping:
        writer.write(prompt.prompt.encode())
        next_command = (await reader.readline()).decode()
        next_command = prompt.precmd(next_command)
        is_stopping = prompt.onecmd(next_command)
        is_stopping = prompt.postcmd(is_stopping, next_command)
    prompt.postloop()


async def run(capability_registry: phile.capability.Registry) -> int:
    with TriggerProvider(capabilities=capability_registry):
        await open_prompt(capabilities=capability_registry)
    return 0


class CleanUps:

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.callbacks = set[NullaryCallable]()

    @contextlib.contextmanager
    def connect(
        self, callback: NullaryCallable
    ) -> collections.abc.Iterator[None]:
        try:
            self.callbacks.add(callback)
            yield
        finally:
            self.callbacks.discard(callback)

    def run(self) -> None:
        for callback in self.callbacks.copy():
            callback()


def main(
    argv: typing.Optional[list[str]] = None
) -> int:  # pragma: no cover
    capability_registry = phile.capability.Registry()
    with contextlib.ExitStack() as stack:
        stack.enter_context(contextlib.suppress(KeyboardInterrupt))

        if argv is None:
            argv = sys.argv
        parser = argparse.ArgumentParser()
        parser.add_argument(
            '--gui', action=argparse.BooleanOptionalAction
        )
        args = parser.parse_args(argv[1:])

        stack.enter_context(
            capability_registry.provide(phile.Configuration())
        )
        stack.enter_context(
            capability_registry.provide(
                trigger_registry := phile.trigger.Registry()
            )
        )
        stack.enter_context(
            capability_registry.provide(clean_ups := CleanUps())
        )
        stack.enter_context(
            quit_trigger_provider := phile.trigger.Provider(
                callback_map={'quit': clean_ups.run},
                registry=trigger_registry,
            )
        )
        quit_trigger_provider.show_all()
        stack.enter_context(
            capability_registry.provide(
                stack.enter_context(phile.watchdog.observers.open()),
                watchdog.observers.api.BaseObserver,
            )
        )
        stack.enter_context(
            capability_registry.provide(
                keyring.get_keyring(), keyring.backend.KeyringBackend
            )
        )
        stack.enter_context(
            phile.trigger.watchdog.View(
                capabilities=capability_registry
            )
        )
        stack.enter_context(
            phile.capability.asyncio.provide(
                capability_registry=capability_registry
            )
        )
        loop = phile.capability.asyncio.get_instance(
            capability_registry=capability_registry
        )
        stack.enter_context(
            clean_ups.connect(
                functools.partial(
                    phile.capability.asyncio.stop, capability_registry
                )
            )
        )
        stack.enter_context(
            phile.capability.tmux.provide_async_tmux_client(
                capability_registry=capability_registry,
            )
        )
        loop.call_soon_threadsafe(
            asyncio.create_task,
            run(capability_registry=capability_registry),
        )
        use_pyside_2: bool
        if args.gui is None:
            use_pyside_2 = phile.capability.pyside2.is_available()
        else:
            use_pyside_2 = args.gui

        if use_pyside_2:
            stack.enter_context(
                phile.capability.asyncio.start(capability_registry)
            )
            stack.enter_context(
                phile.capability.pyside2.provide_qapplication_in(
                    capability_registry=capability_registry,
                )
            )
            stack.enter_context(
                clean_ups.connect(phile.capability.pyside2.stop)
            )
            phile.capability.pyside2.run(capability_registry)
            trigger_registry.activate_if_shown('quit')
        else:
            phile.capability.asyncio.run(capability_registry)
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
