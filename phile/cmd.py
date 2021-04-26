#!/usr/bin/env python3
"""
---------------------------------
Using standard library :mod:`cmd`
---------------------------------

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
import functools
import typing


def process_command(processor_cmd: cmd.Cmd, command: str) -> bool:
    is_stopping: bool
    if command:
        command = processor_cmd.precmd(command)
        is_stopping = processor_cmd.onecmd(command)
        is_stopping = processor_cmd.postcmd(is_stopping, command)
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
    looping_cmd: cmd.Cmd,
) -> None:  # pragma: no cover
    reader, writer = await stdio_streams(
        looping_cmd.stdin, looping_cmd.stdout
    )
    looping_cmd.preloop()
    if looping_cmd.intro:
        writer.write(looping_cmd.intro)
    is_stopping = False
    while not is_stopping:
        writer.write(looping_cmd.prompt.encode())
        next_command = (await reader.readline()).decode()
        is_stopping = process_command(looping_cmd, next_command)
    looping_cmd.postloop()


async def async_cmdloop_threaded_stdin(looping_cmd: cmd.Cmd) -> None:
    stdin = looping_cmd.stdin
    stdout = looping_cmd.stdout
    looping_cmd.preloop()
    if looping_cmd.intro:
        await asyncio.to_thread(stdout.write, looping_cmd.intro)
        await asyncio.to_thread(stdout.flush)
    is_stopping = False
    while not is_stopping:
        await asyncio.to_thread(stdout.write, looping_cmd.prompt)
        await asyncio.to_thread(stdout.flush)
        next_command = await asyncio.to_thread(stdin.readline)
        is_stopping = process_command(looping_cmd, next_command)
    looping_cmd.postloop()
