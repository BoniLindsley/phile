#!/usr/bin/env python3
"""
-------------------------------------
Trigger manipulation using :mod:`cmd`
-------------------------------------
"""

# Standard library.
import asyncio
import cmd
import contextlib
import logging
import shlex
import sys
import typing

# Internal packages.
import phile.asyncio
import phile.cmd
import phile.launcher
import phile.main


class Prompt(cmd.Cmd):

    def __init__(
        self,
        *args: typing.Any,
        trigger_registry: phile.trigger.Registry,
        **kwargs: typing.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._registry = trigger_registry
        self.known_triggers: list[str] = []
        self.trigger_ids: dict[str, int] = {}

    def do_EOF(self, arg: str) -> typing.Literal[True]:
        del arg
        return True

    def do_reset(self, arg: str) -> None:
        del arg
        self.known_triggers.clear()
        self.trigger_ids.clear()
        self.do_list('')

    def do_exe(self, arg: str) -> None:
        self.do_execute(arg)

    def do_execute(self, arg: str) -> None:
        argv = shlex.split(arg)
        trigger_ids: list[int] = []
        for entry in argv:
            try:
                trigger_id = int(entry)
            except ValueError:
                self.stdout.write(
                    'Unable to parse given trigger: {entry}\n'.format(
                        entry=entry
                    )
                )
                return
            trigger_ids.append(trigger_id)
        known_trigger_count = len(self.known_triggers)
        for trigger_id in trigger_ids:
            if trigger_id >= known_trigger_count:
                self.stdout.write(
                    'Unknown_trigger ID {trigger_id}.\n'.format(
                        trigger_id=trigger_id
                    )
                )
                return
        failed_trigger_count = 0
        for trigger_id in trigger_ids:
            trigger_name = self.known_triggers[trigger_id]
            try:
                self._registry.activate(trigger_name)
            except (
                phile.trigger.Registry.NotBound,
                phile.trigger.Registry.NotShown,
            ):
                failed_trigger_count += 1
                self.stdout.write(
                    'Failed to activate trigger'
                    ' {trigger_id} {trigger_name}\n'.format(
                        trigger_id=trigger_id,
                        trigger_name=trigger_name,
                    )
                )
        self.stdout.write(
            'Activated {count} triggers.\n'.format(
                count=len(trigger_ids) - failed_trigger_count
            )
        )

    def do_list(self, arg: str) -> None:
        del arg
        visible_triggers = self._registry.visible_triggers.copy()
        for name in sorted(visible_triggers):
            self._assign_id(name)
        self.stdout.write(
            'Listing IDs of {count} available triggers.\n'.format(
                count=len(visible_triggers)
            )
        )
        for trigger_id, name in enumerate(self.known_triggers):
            if name in visible_triggers:
                self.stdout.write(
                    'Trigger {trigger_id} is {name}\n'.format(
                        trigger_id=trigger_id, name=name
                    )
                )

    def _assign_id(self, trigger: str) -> None:
        new_id = len(self.known_triggers)
        trigger_id = self.trigger_ids.setdefault(trigger, new_id)
        if trigger_id == new_id:
            self.known_triggers.append(trigger)
            assert self.known_triggers.index(trigger) == trigger_id


async def add_trigger_cmd(
    launcher_registry: phile.launcher.Registry,
) -> None:  # pragma: no cover

    async def run() -> None:
        import phile.trigger
        import phile.cmd
        capability_registry = launcher_registry.capability_registry
        await phile.cmd.async_cmdloop_threaded_stdin(
            Prompt(
                trigger_registry=capability_registry[
                    phile.trigger.Registry]
            )
        )

    launcher_registry.add_nowait(
        'phile.trigger.cmd',
        phile.launcher.Descriptor(
            after={'phile.trigger.watchdog.producer'},
            before={'phile_shutdown.target'},
            binds_to={'phile.trigger.watchdog.producer'},
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


async def add_trigger_watchdog_producer(
    launcher_registry: phile.launcher.Registry,
) -> None:  # pragma: no cover

    async def run() -> None:
        import phile.configuration
        import phile.trigger
        import phile.trigger.watchdog
        import phile.watchdog.asyncio
        capability_registry = launcher_registry.capability_registry
        configuration = capability_registry[phile.configuration.Entries]
        trigger_registry = capability_registry[phile.trigger.Registry]
        observer = (
            capability_registry[phile.watchdog.asyncio.BaseObserver]
        )
        producer = phile.trigger.watchdog.Producer(
            configuration=configuration,
            observer=observer,
            trigger_registry=trigger_registry,
        )
        await producer.run()

    launcher_registry.add_nowait(
        'phile.trigger.watchdog.producer',
        phile.launcher.Descriptor(
            after={
                'phile.configuration',
                'phile.trigger',
                'watchdog.asyncio.observer',
            },
            before={'phile_shutdown.target'},
            binds_to={
                'phile.configuration',
                'phile.trigger',
                'watchdog.asyncio.observer',
            },
            conflicts={'phile_shutdown.target'},
            exec_start=[run],
        )
    )


async def async_run(
    launcher_registry: phile.launcher.Registry,
) -> int:  # pragma: no cover
    await add_trigger_cmd(launcher_registry=launcher_registry)
    await add_trigger_watchdog_producer(
        launcher_registry=launcher_registry
    )
    event_view = launcher_registry.event_queue.__aiter__()
    await launcher_registry.start(cmd_name := 'phile.trigger.cmd')
    if not launcher_registry.is_running(cmd_name):
        return 1
    expected_event = phile.launcher.Event(
        type=phile.launcher.EventType.STOP, entry_name=cmd_name
    )
    async for event in event_view:
        if event == expected_event:
            break
    return 0


def main(
    argv: typing.Optional[list[str]] = None
) -> int:  # pragma: no cover
    del argv
    try:
        return phile.main.run(async_run)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    return 0


if __name__ == '__main__':  # pragma: no cover
    if __debug__:
        log_level = logging.DEBUG
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelno)03d] %(name)s:'
            ' %(message)s',
        )
        handler.setFormatter(formatter)
        handler.setLevel(log_level)
        package_logger = logging.getLogger('phile')
        package_logger.addHandler(handler)
        package_logger.setLevel(1)
    sys.exit(main())
