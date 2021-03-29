#!/usr/bin/env python3
"""
-------------------------------------
Trigger manipulation using :mod:`cmd`
-------------------------------------

There are a few ways to use :class:`cmd.Cmd`
in an :class:`asyncio.AbstractEventLoop`.

-   The easiest way is to wrap :meth:`cmd.Cmd.cmdloop`
    in :func:`asyncio.to_thread`,
    or more generally :meth:`asyncio.loop.run_in_executor`.
    This runs an interactive "event loop"
    in a different execution context,
    and the :class:`asyncio.AbstractEventLoop` can wait on it exiting.

    -   This is easy to implement and maintain, and is cross-platform.
    -   The class :class:`cmd.Cmd` does not provide a natural way
        of stopping its event loop from a different thread.
        That is, there is no graceful way of terminating
        the event loop running in the thread or executor.

-   Run :meth:`cmd.Cmd.cmdloop` in a :class:`subprocess.Popen`
    with :data:`None` for the standard streams,
    forwarding the stream data to the subprocess.

    -   This allows the interactive loop to be stopped
        by forcefully terminating the subprocess.
    -   This has an overhead of launching a new Python process.

-   Implement an :mod:`asyncio` version of :meth:`cmd.Cmd.cmdloop`,
    which wraps the blocking :meth:`io.IOBase.readline`
    of :attr:`cmd.Cmd.stdin` in :func:`asyncio.to_thread`
    and feed the input from it to :meth:`cmd.Cmd.onecmd`.
    This allows the :class:`asyncio.AbstractEventLoop`
    to wait on data to be processed without blocking.

    -   This allows the interactive loop itself to be stopped,
        since the coroutine :func:`asyncio.to_thread` can be cancelled.
        However, the call :meth:`io.IOBase.readline`
        is blocking in :func:`asyncio.to_thread`,
        and there is no graceful way of stopping that,
        even if nothing is waiting on the thread anymore.

        -   This can be somewhat mitigated by creating a thread
            dedicated to reading the stream.

    -   Uses implementation detail that there are
        :attr:`cmd.Cmd.stdin` and :attr:`cmd.Cmd.stdout` members.
    -   If a thread is needed to wait on input,
        it might be better to run the interactive loop in the thread,
        which reduces the need for inter-thread communication.

-   Implement an :mod:`asyncio` version of :meth:`cmd.Cmd.cmdloop`
    that waits for input using the capability of :mod:`asyncio`.
    For example, instead of the blocking :meth:`io.IOBase.readline`,
    use :meth:`asyncio.loop.connect_read_pipe`
    to obtain input, and feed it to :meth:`cmd.Cmd.onecmd`.

    -   This API does not have Windows `asyncio platform support`_.
    -   I am unsure how to test this.
        I do not know how to create pipes or sockets in a way
        that does not interfere with :class:`asyncio.AbstractEventLoop`.

..  _asyncio platform support:
    https://docs.python.org/3/library/asyncio-platforms.html
"""

# Standard library.
import asyncio
import cmd
import contextlib
import functools
import shlex
import sys
import typing

# External dependencies.
import watchdog.observers

# Internal packages.
import phile
import phile.asyncio
import phile.capability.asyncio
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


def process_command(prompt: Prompt, command: str) -> bool:
    is_stopping: bool
    if command:
        command = prompt.precmd(command)
        is_stopping = prompt.onecmd(command)
        is_stopping = prompt.postcmd(is_stopping, command)
    else:
        is_stopping = True
    return is_stopping


# TODO(BoniLindsley): Add unit test.
# I am not sure how to test this.
# This API only works with pipes and sockets,
# but creating socket and pipes seem somehow block
# when there is an async loop,
# even if `asyncio.to_thread` is used to open them.
async def stdio_streams(
    stdin: typing.IO[str],
    stdout: typing.IO[str],
) -> tuple[asyncio.StreamReader,
           asyncio.StreamWriter]:  # pragma: no cover
    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(
        functools.partial(asyncio.StreamReaderProtocol, reader), stdin
    )
    writer = asyncio.StreamWriter(
        *(
            await loop.connect_write_pipe(
                asyncio.streams.FlowControlMixin, stdout
            )
        ), reader, loop
    )
    return reader, writer


# TODO(BoniLindsley): Add unit test.
# This will require `stdio_streams` to be testable,
# since they suffer the same problem of creating resource for testing.
async def async_cmdloop_with_streams(
    capability_registry: phile.capability.Registry
) -> None:  # pragma: no cover
    prompt = Prompt(capabilities=capability_registry)
    reader, writer = await stdio_streams(prompt.stdin, prompt.stdout)
    prompt.preloop()
    if prompt.intro:
        writer.write(prompt.intro)
    is_stopping = False
    while not is_stopping:
        writer.write(prompt.prompt.encode())
        next_command = (await reader.readline()).decode()
        is_stopping = process_command(prompt, next_command)
    prompt.postloop()


async def async_cmdloop_threaded_stdin(prompt: Prompt) -> None:
    prompt.preloop()
    if prompt.intro:
        await asyncio.to_thread(prompt.stdout.write, prompt.intro)
        await asyncio.to_thread(prompt.stdout.flush)
    is_stopping = False
    while not is_stopping:
        await asyncio.to_thread(prompt.stdout.write, prompt.prompt)
        await asyncio.to_thread(prompt.stdout.flush)
        next_command = await asyncio.to_thread(prompt.stdin.readline)
        is_stopping = process_command(prompt, next_command)
    prompt.postloop()


async def async_run(
    capability_registry: phile.capability.Registry
) -> None:  # pragma: no cover
    prompt = Prompt(capabilities=capability_registry)
    await async_cmdloop_threaded_stdin(prompt)


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
