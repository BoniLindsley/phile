#!/usr/bin/env python3
"""
-------------------------------------
Trigger manipulation using :mod:`cmd`
-------------------------------------
"""

# Standard library.
import cmd
import contextlib
import shlex
import sys
import typing

# External dependencies.
import watchdog.observers

# Internal packages.
import phile
import phile.asyncio
import phile.capability.asyncio
import phile.cmd
import phile.notify
import phile.trigger.watchdog
import phile.watchdog


class Prompt(cmd.Cmd):

    def __init__(
        self, *args: typing.Any, capabilities: phile.Capabilities,
        **kwargs: typing.Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self._registry = capabilities[phile.trigger.Registry]
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


async def async_run(
    capability_registry: phile.capability.Registry
) -> None:  # pragma: no cover
    prompt = Prompt(capabilities=capability_registry)
    await phile.cmd.async_cmdloop_threaded_stdin(prompt)


def main(
    argv: typing.Optional[list[str]] = None
) -> int:  # pragma: no cover
    del argv
    capability_registry = phile.capability.Registry()
    with contextlib.ExitStack() as stack:
        stack.enter_context(contextlib.suppress(KeyboardInterrupt))
        stack.enter_context(
            capability_registry.provide(phile.Configuration())
        )
        stack.enter_context(
            capability_registry.provide(phile.trigger.Registry())
        )
        stack.enter_context(
            capability_registry.provide(
                stack.enter_context(phile.watchdog.observers.open()),
                watchdog.observers.api.BaseObserver,
            )
        )
        stack.enter_context(
            phile.trigger.watchdog.Producer(
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
        cli_task = loop.create_task(
            async_run(capability_registry=capability_registry),
        )
        cli_task.add_done_callback(lambda _future: loop.stop())
        phile.capability.asyncio.run(capability_registry)
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
