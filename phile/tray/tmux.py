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
import bisect
import datetime
import json
import logging
import os
import pathlib
import pty
import select
import shlex
import subprocess
import sys
import typing
import warnings

# External dependencies.
import watchdog.events  # type: ignore[import]

# Internal packages.
from phile.configuration import Configuration
from phile.tray.tray_file import TrayFile
import phile.watchdog_extras

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""


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


def timedelta_to_seconds(
    timedelta: typing.Optional[datetime.timedelta] = None
) -> typing.Optional[float]:
    """Convert timedelta to seconds, preserving :data:`None`."""
    if timedelta is None:
        return None
    else:
        return timedelta.total_seconds()


def get_server_pid(
    *, timeout: typing.Optional[datetime.timedelta] = None
) -> int:
    """
    Returns the PID of the default tmux server.

    Same parameters and exception
    as :func:`~phile.tray.tmux.kill_server`.
    """
    # Fetch tmux server information.
    _logger.debug('Get server PID started.')
    pid_process = subprocess.run(
        args=['tmux', 'display-message', '-pF', '#{pid}'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timedelta_to_seconds(timeout),
    )
    pid_process.check_returncode()
    pid = int(pid_process.stdout)
    _logger.debug('Get server PID done: %s', pid)
    return pid


def kill_server(
    *, timeout: typing.Optional[datetime.timedelta] = None
) -> None:
    """
    Sends a ``kill-server`` command to the default tmux server.

    :param timeout:
        Duration to wait for the command to return
        unless it is :data:`None`,
        in which case block until it returns.
    :type timeout: :class:`~datetime.timedelta` or :data:`None`
    :raises ~subprocess.CalledProcessError:
        If the the command fails.
        This can happen, for example, no tmux server is found.
    """
    # Fetch tmux server information.
    _logger.debug('Kill server started.')
    pid_process = subprocess.run(
        args=['tmux', 'kill-server'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timedelta_to_seconds(timeout),
    )
    pid_process.check_returncode()
    _logger.debug('Kill server completed.')
    _logger.debug('Kill server stdout: %s', pid_process.stdout)
    _logger.debug('Kill server stderr: %s', pid_process.stderr)


class ControlMode:
    """A tmux control mode client for sending commands."""

    def __init__(
        self,
        *,
        configuration_file_path: typing.Optional[pathlib.Path] = None,
        session_name: typing.Optional[str] = None,
        timeout: typing.Optional[datetime.timedelta] = None,
    ):
        """
        :param configuration_file_path:
            Configuration file to give to the control mode client.
            This is used if the tmux command starts a tmux server.
            If :data:`None`,
            let tmux determine the default file(s) to use.
        :type configuration_file_path:
            :class:`~pathlib.Path` or :data:`None`
        :param session_name:
            If :data:`None`, create a new session to connect to,
            and let the tmux server determine the new session name.
            Otherwise, it indicates the session to connect to.
            If there are no session of the given name,
            create a new session of the given name.
        :type session_name: :class:`str` or :data:`None`
        :param timeout:
            The time duration to wait for a server response.
            If :data:`None`, waits block indefinitely.
        :type timeout: :class:`~datetime.timedelta` or :data:`None`
        """
        self.timeout_seconds = timedelta_to_seconds(timeout)
        """Time to wait for when reading stdout from the tmux client."""
        _logger.debug(
            'Control mode using timeout: %s', self.timeout_seconds
        )
        subprocess_args = ['tmux', '-CC', '-u']
        """Command arguments for creating control mode client."""
        if configuration_file_path:
            _logger.debug(
                'Control mode using configuration: %s',
                configuration_file_path
            )
            subprocess_args.extend(['-f', str(configuration_file_path)])
        if session_name is not None:
            subprocess_args.extend([
                'new-session',
                '-A',
                '-s',
                session_name,
            ])
        _logger.debug(
            'Control mode creating tmux client: %s.', subprocess_args
        )
        self.tty_fd, tmux_tty_fd = pty.openpty()
        """
        File to comminucate with the control mode client.

        A terminal is required for communicating with tmux.
        So the default pipes are not enough.
        """
        self.tmux_client = subprocess.Popen(
            subprocess_args,
            stdin=tmux_tty_fd,
            stdout=tmux_tty_fd,
            stderr=subprocess.PIPE,
            encoding='utf-8',
        )
        """
        The control mode client process.

        The ``stderr`` stream is separated from the ``stdout`` stream
        since outputs from ``tmux`` will be parsed.
        """
        _logger.debug('Control mode closing terminal fd given to tmux.')
        os.close(tmux_tty_fd)
        _logger.debug('Control mode creating file objects from pty fd.')
        self.stdin = os.fdopen(self.tty_fd, buffering=0, mode='wb')
        """
        Control mode client stdin stream.

        Wraps the terminal stream so that file object API can be used.
        Uses binary stream since tmux sometimes sends DSC control codes.
        Buffering is disabled to detect whether further read is possible.
        """
        self.stdout = os.fdopen(
            self.tty_fd, buffering=0, mode='rb', closefd=False
        )
        """
        Control mode client stdout stream.

        Wraps the terminal stream so that file object API can be used.
        Uses binary stream since tmux cares about line ending.
        For example, a lone ``\\n`` ends the client connection.
        """
        _logger.debug('Control mode waiting for startup response.')
        startup_output_block = self.read_block()
        _logger.debug('Control mode client started.')

    def __del__(self):
        _logger.debug('Control mode finalising.')
        self.terminate()

    def send_command(self, command_string: str) -> None:
        """Send a command to the attached tmux client."""
        _logger.debug(
            'Control mode sending command: %s.', command_string
        )
        self.stdin.writelines([command_string.encode(), b'\n'])

    def terminate(self) -> None:
        """
        Exit client and terminate the control mode client process.

        :raises TimeoutError:
            If the tmux server does not respond to the exit request.

        Exits the client by sending an exit request to the server
        and then wait for the client process to exit.
        If it fails to exit, a kill signal is sent to it.
        """
        _logger.debug('Control mode terminating.')
        return_code = self.tmux_client.returncode
        if return_code is not None:
            _logger.debug(
                'Control mode already terminated. Return code: %s.',
                return_code
            )
            return
        _logger.debug('Control mode sending exit request.')
        self.send_command(CommandBuilder.exit_client())
        self.readline_until_starts_with(stop_prefix=('%exit'))
        _logger.debug('Control mode process clean-up.')
        try:
            return_code = self.tmux_client.wait(
                timeout=self.timeout_seconds
            )
        except subprocess.TimeoutExpired:
            _logger.debug('Control client did not exit. Killing.')
            self.tmux_client.kill()
            return_code = self.tmux_client.wait()
        _logger.debug('Control mode return code: %s.', return_code)
        # Print out errors if any.
        # This drains and closes automatically created pipes.
        # For us, stderr is closed.
        _, errors = self.tmux_client.communicate()
        _logger.debug('Control mode errors: %s.', errors)
        # With this, all pty fd are closed.
        _logger.debug('Control mode closing pty fd.')
        self.stdin.close()

    def read_block(self, *, rstrip_newline: bool = False) -> str:
        """
        Returns the next output block from the :data:`stdout` stream.

        :param rstrip_newline:
            Whether the returned string
            should include any trailing newline.
        :type rstrip_newline: :class:`bool`
        :raises TimeoutError:
            If no data is available from the stream
            as determined by :meth:`is_stdout_ready()`
            before the end of a block is found.

        Data between the start of the stream
        and the start of the block are discarded.
        The guard lines ``%begin``, ``%end`` and ``%error``
        are not included in the returned string.
        """
        _logger.debug('Control mode reading a block.')
        self.readline_until_starts_with(
            stop_prefix=('%begin ', '\x1bP1000p%begin')
        )
        _logger.debug('Control mode found begin block.')
        block_content = self.readline_until_starts_with(
            stop_prefix=('%end ', '%error '),
            preserve_content=True,
        )
        _logger.debug('Control mode found end block.')
        if rstrip_newline:
            return block_content.rstrip('\n\r')
        else:
            return block_content

    def readline_until_starts_with(
        self,
        *,
        stop_prefix: typing.Union[str, typing.Tuple[str, ...]],
        preserve_content: bool = False,
    ) -> str:
        prefix_found = False
        content = ''
        next_line = ''
        while not prefix_found:
            if preserve_content:
                content += next_line
            next_line = self.readline(rstrip_newline=False)
            prefix_found = next_line.startswith(stop_prefix)
        return content

    def readline(self, *, rstrip_newline: bool = False) -> str:
        """
        Reads a single line of data from the :data:`stdout` stream.

        :param rstrip_newline:
            Whether the returned string
            should include any trailing newline.
        :type rstrip_newline: :class:`bool`
        :raises TimeoutError:
            If no data is available from the stream
            as determined by :meth:`is_stdout_ready()`.
        """
        if not self.is_stdout_ready():
            raise TimeoutError('Control mode reading timeout.')
        next_line = self.stdout.readline().decode()
        stripped_next_line = next_line.rstrip('\n\r')
        _logger.debug('Control mode stdout: %s.', stripped_next_line)
        return stripped_next_line if rstrip_newline else next_line

    def is_stdout_ready(self) -> bool:
        """
        Returns whether the ``stdout`` stream from the client has data.

        If :data:`timeout_seconds` is :data:`None`,
        this blocks until there is data, and returns :data:`True`.
        If not :data:`None`, returns :data:`True`
        if data becomes available within :data:`timeout_seconds`.
        Returns :data:`False`
        if no data is available within that time frame.
        """
        timeout = self.timeout_seconds
        ready_list, _, _ = select.select([self.tty_fd], [], [], timeout)
        return bool(ready_list)


class IconList:

    def __init__(
        self,
        *,
        configuration: Configuration,
        watching_observer: watchdog.observers.Observer,
    ) -> None:
        self._configuration = configuration
        """Information on where tray files are."""
        self._tray_files: typing.List[TrayFile] = []
        """Keeps track of known tray files."""
        self._control_mode = ControlMode()
        """Control mode client for communicating with tmux."""
        # The status line cannot contain new lines.
        # This forces the initial attempt to refresh
        # to always set the status line.
        self._status_right = '\n'
        """Current status right string for tmux."""
        # Set up tray directory monitoring.
        self._set_up_tray_event_handler(
            watching_observer=watching_observer
        )

    def _set_up_tray_event_handler(
        self, *, watching_observer: watchdog.observers.Observer
    ):
        # Make sure the directory to be monitored exists.
        watched_path = self._configuration.tray_directory
        watched_path.mkdir(exist_ok=True, parents=True)
        # Set up how to handle the events.
        dispatcher = phile.watchdog_extras.Dispatcher(
            event_handler=self.process_tray_event
        )
        # Use a scheduler to toggle the event handling on and off.
        self._tray_scheduler = phile.watchdog_extras.Scheduler(
            watchdog_handler=dispatcher,
            watched_path=watched_path,
            watching_observer=watching_observer,
        )

    def run(self) -> None:
        """
        Start updating ``status-right`` with tray file changes.

        Implementation detail:
        This calls `show` do the monitoring
        and then blocks to drain tmux client stdout stream
        until an exit response is detected.
        """
        # Start draining control mode output.
        # Can be expanded to an event loop later.
        control_mode = self._control_mode
        block_started = False
        exit_found = False
        while not exit_found:
            next_line = control_mode.readline(rstrip_newline=True)
            if block_started:
                block_started = not next_line.startswith(
                    ('%end ', '%error '),
                )
            else:
                block_started = next_line.startswith(
                    ('%begin ', '\x1bP1000p%begin')
                )
                if not block_started:
                    exit_found = next_line.startswith(('%exit'))

    def close(self) -> None:
        self.hide()
        self._control_mode.send_command(CommandBuilder.exit_client())
        self._tray_scheduler.unschedule()

    def hide(self) -> None:
        """Stop updating and reset ``status-right``."""
        if self.is_hidden():
            return
        self._tray_scheduler.unschedule()
        self._tray_files.clear()
        # Reset status line.
        self._control_mode.send_command(
            CommandBuilder.unset_global_status_right()
        )

    def show(self) -> None:
        """
        Start updating ``status-right`` with tray file changes.

        This is non-blocking.
        Starts thread(s) to monitor for tray file changes.
        """
        if not self.is_hidden():
            return
        # Start monitoring to not miss file events.
        self._tray_scheduler.schedule()
        # Update all existing tray files.
        configuration = self._configuration
        tray_directory = configuration.tray_directory
        for tray_file_path in tray_directory.iterdir():
            if tray_file_path.is_file():
                self.process_tray_event(
                    watchdog.events.FileCreatedEvent(tray_file_path)
                )
        # Refresh the status line even if there are no tray files.
        self.refresh_status_line()

    def is_hidden(self) -> bool:
        """Returns whether the tray icon is hidden."""
        return not self._tray_scheduler.is_scheduled()

    def process_tray_event(
        self, watchdog_event: watchdog.events.FileSystemEvent
    ) -> None:
        """
        Responds to file changes.

        :param ~watchdog.events.FileSystemEvent watchdog_event:
            The detected file changes in the tray directory.
        """
        _logger.debug('Watchdog event received.')
        # Notifications are files. Directory changes do not matter.
        if watchdog_event.is_directory:
            _logger.debug('Watchdog event: not using directory events.')
            return
        # Consider a move event as a delete and create.
        event_type = watchdog_event.event_type
        if event_type == watchdog.events.EVENT_TYPE_MOVED:
            _logger.debug('Watchdog event: tray file moved.')
            for new_event in [
                watchdog.events.FileDeletedEvent(
                    watchdog_event.src_path
                ),
                watchdog.events.FileCreatedEvent(
                    watchdog_event.dest_path
                )
            ]:
                self.process_tray_event(new_event)
            return
        # Only files of a specific extension is a tray file.
        try:
            tray_file = TrayFile(
                configuration=self._configuration,
                path=pathlib.Path(watchdog_event.src_path)
            )
        except TrayFile.SuffixError as error:
            _logger.debug('Watchdog event: %s', error)
            return
        # Determine what to do base on existence of the actual file.
        # There might be a delay between the file operation
        # and the event being received here.
        # If the `load` fails, there is not much we can do about it.
        # So just ignore.
        # JSON string decoding error is likely to be
        # a tray file modification in the middle of a read.
        # In that case, a future file modification event is expected
        # and this method will receive it, and we can handle it then.
        # So ignoring is okay in that case.
        try:
            self.load(tray_file)
        except json.decoder.JSONDecodeError:
            warnings.warn(
                'Unable to decode a tray file: {}'.format(
                    tray_file.path
                )
            )
            return

    def load(self, tray_file: TrayFile) -> None:
        """
        Update changes in the given tray file in tmux status line.

        :param ~phile.tray.gui.TrayFile tray_file:
            The tray file in the tray directory to update.
        """
        # Figure out the position of the tray icon is in
        # in the tracked tray icons, if it is tracked at all.
        index = bisect.bisect_left(self._tray_files, tray_file)
        try:
            is_tracked = self._tray_files[index] == tray_file
        except IndexError:
            is_tracked = False
        if is_tracked:
            _logger.debug(
                "Loading tray file in position %s of %s.", index + 1,
                len(self._tray_files)
            )
        else:
            _logger.debug("Loading tray file that was untracked.")
        # Try to load the tray file.
        tray_file_exists = True
        try:
            tray_file.load()
        except FileNotFoundError:
            tray_file_exists = False
        # If the tray file does not exist,
        # either remove the tray icon or there is nothing to do.
        if not tray_file_exists:
            if not is_tracked:
                _logger.debug(
                    "Tray file does not exist nor tracked."
                    " Nothing to do."
                )
                return
            else:
                self.remove(index)
                return
        # Can assume from here that the tray file is loaded.
        if is_tracked:
            self.set(index, tray_file)
        else:
            self.insert(index, tray_file)

    def insert(self, index: int, tray_file: TrayFile) -> None:
        """
        Insert the content of given tray file into tmux status line.

        :param int index: The zero-based position to put the content.
        :param ~phile.tray.gui.TrayFile tray_file:
            The tray file whose content to insert.
        """
        _logger.debug(
            "Inserting tray file into position %s of %s", index + 1,
            len(self._tray_files) + 1
        )
        self._tray_files.insert(index, tray_file)
        self.refresh_status_line()

    def set(self, index: int, tray_file: TrayFile) -> None:
        """
        Update content at position `index` to the given tray file.

        :param int index: The zero-based position at which to change.
        :param ~phile.tray.gui.TrayFile tray_file:
            The tray file whose content to update to.
        """
        _logger.debug(
            "Setting tray file in position %s of %s", index + 1,
            len(self._tray_files)
        )
        self._tray_files[index] = tray_file
        self.refresh_status_line()

    def remove(self, index: int) -> None:
        """
        Remove the content at the given position.

        :param int index: The zero-based position at which to remove.
        """
        _logger.debug(
            "Removing tray file in position %s of %s", index + 1,
            len(self._tray_files)
        )
        self._tray_files.pop(index)
        self.refresh_status_line()

    def refresh_status_line(self) -> None:
        """
        Update tmux `status-right` to reflect current tracked contents.
        """
        _logger.debug('Icon list refreshing status line.')
        new_status_right = ''.join(
            tray_file.text_icon for tray_file in self._tray_files
            if tray_file.text_icon is not None
        )
        if self._status_right != new_status_right:
            self._status_right = new_status_right
            self._control_mode.send_command(
                CommandBuilder.set_global_status_right(new_status_right)
            )
        else:
            _logger.debug('Icon list has no visible changes.')


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    """Take over tmux ``status-right`` to display tray icons."""
    configuration = Configuration()
    watching_observer = phile.watchdog_extras.Observer()
    watching_observer.start()
    icon_list = IconList(
        configuration=configuration,
        watching_observer=watching_observer,
    )
    icon_list.show()
    icon_list.run()
    return 0


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
