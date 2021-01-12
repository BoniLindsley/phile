#!/usr/bin/env python3
"""
-----------------------
Communicating with tmux
-----------------------

There is a control mode in tmux.
It allows communicating with the tmux server
using client ``stdin`` and ``stdout`` streams.
This avoids the need to start a new tmux process for each tmux command.
The :class:`ControlMode` class wraps basic communication needs
in control mode.
"""

# Standard libraries.
import asyncio
import datetime
import functools
import shlex
import typing

# Internal packages.
import phile.datetime


class CommandBuilder:
    """
    Construct tmux command strings based on commands of interest.

    All construction methods are class methods
    since tmux state is not necessary.
    And if they are, they can be passed in from the parameters.
    The provided methods are added as necessary.
    They are not meant to be exhaustive.
    """

    @classmethod
    def exit_client(cls) -> str:
        """Let the server know the current client wants to exit."""
        return ''

    @classmethod
    def refresh_client(
        cls, *, no_output: typing.Optional[bool] = None
    ) -> str:
        """
        Send a client refresh request.

        :param no_output:
            If not :class:`None`,
            determines whether the tmux server
            should send ``%output`` messages.
            Otherwise, the current setting is left alone.
        :type no_output: :class:`bool` or :class:`None`
        """
        if no_output is None:
            flags = ''
        elif no_output:
            flags = ' -F no-output'
        else:
            flags = ' -F \'\''
        return '{command}{flags}'.format(
            command='refresh-client', flags=flags
        )

    @classmethod
    def set_destroy_unattached(cls, to_destroy: bool) -> str:
        """
        Set whether the current session exit when not attached.

        In particular, the session exits
        when the created subprocess is destroyed,
        or when it switches to a new session.

        It is not a good idea to use this on the control mode session,
        since iterating through session from a different client
        can cause the control mode session to become terminated.
        This can in turn crash the parent of the control mode process,
        and that is likely this Python interpreter,
        and then its parent which can be the tmux server
        if this script is launched from the tmux configuration script.
        """
        return 'set-option destroy-unattached {}'.format(
            'on' if to_destroy else 'off'
        )

    @classmethod
    def set_global_status_right(cls, new_status_string: str) -> str:
        """Change the tmux status line value to the given string."""
        return 'set-option -g status-right {}'.format(
            shlex.quote(new_status_string)
        )

    @classmethod
    def unset_global_status_right(cls) -> str:
        """Change the tmux status line value to the default."""
        return 'set-option -gu status-right'


async def kill_server() -> asyncio.subprocess.Process:
    """Sends a ``kill-server`` command to the default tmux server."""
    return await asyncio.create_subprocess_exec(
        'tmux',
        '-u',
        'kill-server',
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
