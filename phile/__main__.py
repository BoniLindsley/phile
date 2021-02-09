#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import dataclasses
import functools
import os
import pathlib
import sys
import types
import typing

# External dependencies.
import keyring
import watchdog.observers

# Internal packages.
import phile
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
import phile.watchdog

Launcher = typing.Callable[[phile.Capabilities], typing.Coroutine]
LauncherEntry = tuple[Launcher, set[type]]

default_launchers: typing.Dict[str, LauncherEntry] = {
    'imap-idle': (
        phile.tray.publishers.imap_idle.run,
        {
            phile.Configuration,
            keyring.backend.KeyringBackend,
        },
    ),
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


class TriggerEntryPoint(phile.trigger.EntryPoint):
    """Provides triggers to start and stop tasks."""

    def __init__(
        self, *args: typing.Any, capabilities: phile.Capabilities,
        **kwargs: typing.Any
    ) -> None:
        super().__init__(
            *args,
            configuration=capabilities[phile.Configuration],
            **kwargs
        )
        self.task_registry = TaskRegistry(capabilities=capabilities)
        self.start_prefix = 'start-task_'
        self.stop_prefix = 'stop-task_'

    def __enter__(self) -> 'TriggerEntryPoint':
        super().__enter__()
        return self

    def add_all_triggers(self) -> None:
        usable_launchers = {
            name: launcher
            for (name, launcher) in self.task_registry.launchers.items()
            if name in self.task_registry.usable_launcher_names
        }
        for task_name in usable_launchers:
            self.callback_map[self.start_prefix + task_name] = (
                functools.partial(self.create_task, task_name)
            )
            self.callback_map[self.stop_prefix + task_name] = (
                functools.partial(
                    self.task_registry.cancel_task, task_name
                )
            )
            self.add_trigger(self.start_prefix + task_name)

    def create_task(self, task_name: str) -> asyncio.Task[typing.Any]:
        self.remove_trigger(self.start_prefix + task_name)
        self.add_trigger(self.stop_prefix + task_name)
        task = self.task_registry.create_task(name=task_name)
        task.add_done_callback(self.on_task_done)
        return task

    def on_task_done(self, task: asyncio.Task[typing.Any]) -> None:
        task_name = task.get_name()
        with contextlib.suppress(ResourceWarning):
            self.remove_trigger(self.stop_prefix + task_name)
            self.add_trigger(self.start_prefix + task_name)


async def run(capabilities: phile.Capabilities) -> None:
    loop = asyncio.get_running_loop()
    with TriggerEntryPoint(
        capabilities=capabilities,
        trigger_directory=pathlib.Path('phile')
    ) as entry_point, phile.watchdog.Scheduler(
        watched_path=entry_point.trigger_directory,
        watching_observer=capabilities[
            watchdog.observers.api.BaseObserver],
        path_filter=entry_point.check_path,
        path_handler=functools.partial(
            loop.call_soon_threadsafe, entry_point.activate_trigger
        )
    ):
        entry_point.add_all_triggers()
        for task_name in entry_point.task_registry.usable_launcher_names:
            entry_point.create_task(task_name)
        while True:
            await asyncio.sleep(3600)


async def async_main(argv: typing.List[str]) -> int:  # pragma: no cover
    capabilities = phile.Capabilities()
    capabilities.set(phile.Configuration())
    capabilities[keyring.backend.KeyringBackend] = (
        keyring.get_keyring()  # type: ignore[no-untyped-call]
    )
    async with contextlib.AsyncExitStack() as stack:
        capabilities[watchdog.observers.api.BaseObserver] = (
            await stack.enter_async_context(
                phile.watchdog.observers.async_open()
            )
        )
        busy_tasks = list[asyncio.Task[typing.Any]]()
        if 'TMUX' in os.environ:
            capabilities[
                phile.tmux.control_mode.Client] = control_mode = (
                    await stack.enter_async_context(
                        phile.tmux.control_mode.open(
                            control_mode_arguments=(
                                phile.tmux.control_mode.Arguments()
                            )
                        )
                    )
                )
            control_mode_task = await stack.enter_async_context(
                phile.asyncio.open_task(control_mode.run())
            )
            busy_tasks.append(control_mode_task)
        run_task = await stack.enter_async_context(
            phile.asyncio.open_task(run(capabilities=capabilities))
        )
        busy_tasks.append(run_task)
        stdin_task = await stack.enter_async_context(
            phile.asyncio.open_task(
                phile.tray.tmux.read_byte(sys.stdin)
            )
        )
        busy_tasks.append(stdin_task)
        done, pending = await asyncio.wait(
            busy_tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
    return 0


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(async_main(argv))
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
