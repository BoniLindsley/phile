#!/usr/bin/env python3
"""
--------------------
Test phile.tray.tmux
--------------------
"""

# Standard library.
import datetime
import logging
import os
import pathlib
import psutil  # type: ignore
import signal
import subprocess
import tempfile
import time
import unittest
import unittest.mock

# External dependencies.
import watchdog.events  # type: ignore

# Internal packages.
from phile.configuration import Configuration
from phile.PySide2_extras.watchdog_wrapper import Observer
from phile.tray.tmux import (
    CommandBuilder, ControlMode, get_server_pid, IconList, kill_server,
    timedelta_to_seconds
)
from phile.tray.gui import TrayFile
from test_phile.pyside2_test_tools import EnvironBackup
from test_phile.watchdog_test_tools import EventSetter

_logger = logging.getLogger(
    __loader__.name  # type: ignore  # mypy issue #1422
)
"""Logger whose name is the module name."""

wait_time = datetime.timedelta(seconds=2)


class TestCommandBuilder(unittest.TestCase):
    """
    Unit test for :class:`~phile.tray.tmux.CommandBuilder`.

    Ensures the tmux command string returned from the class methods
    are as expected.
    """

    def __init__(self, *args, **kwargs) -> None:
        """"""
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def test_exit_client(self) -> None:
        self.assertEqual(CommandBuilder.exit_client(), '')

    def test_refresh_client(self) -> None:
        self.assertEqual(
            CommandBuilder.refresh_client(), 'refresh-client'
        )
        self.assertEqual(
            CommandBuilder.refresh_client(no_output=False),
            'refresh-client -F \'\''
        )
        self.assertEqual(
            CommandBuilder.refresh_client(no_output=True),
            'refresh-client -F no-output'
        )

    def test_set_destroy_unattached(self) -> None:
        self.assertEqual(
            CommandBuilder.set_destroy_unattached(False),
            'set-option destroy-unattached off'
        )
        self.assertEqual(
            CommandBuilder.set_destroy_unattached(True),
            'set-option destroy-unattached on'
        )

    def test_set_global_status_right(self) -> None:
        self.assertEqual(
            CommandBuilder.set_global_status_right(''),
            "set-option -g status-right ''"
        )
        self.assertEqual(
            CommandBuilder.set_global_status_right("'"),
            (
                'set-option -g status-right '
                # Not quite what I want,
                # but it is what `shlex.quote` gives and it is valid.
                # Empty  open  char  close  empty
                # `''     "     '     "     ''`
                + "''" + '"' + "'" + '"' + "''"
            )
        )


class TestTimedeltaToSeconds(unittest.TestCase):
    """Unit test for :class:`~phile.tray.tmux.timedelta_to_seconds`."""

    def __init__(self, *args, **kwargs) -> None:
        """"""
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def test_timedelta(self) -> None:
        """Convert :class:`~datetime.timedelta` to seconds."""
        timedelta = datetime.timedelta(hours=2)
        result = timedelta_to_seconds(timedelta)
        self.assertEqual(result, 2 * 60 * 60)
        self.assertIsInstance(result, float)

    def test_none(self) -> None:
        """Keep :data:`None` as is."""
        self.assertEqual(timedelta_to_seconds(None), None)


class TestControlMode(unittest.TestCase):
    """
    Unit test for :class:`~phile.tray.tmux.ControlMode`.

    Also tests the functions :meth:`~phile.tray.tmux.get_server_pid`
    and :meth:`~phile.tray.tmux.kill_server`,
    since their tests would require
    creating a :class:`~phile.tray.tmux.ControlMode`
    or mimicking many of its functionalities to create a server,
    such as waiting for the server to start up
    and then cleaning it up.
    So instead of duplicating the set up code,
    tests for them are implicitly done
    in :meth:`~TestControlMode.test_initialisation` as well.
    """

    def __init__(self, *args, **kwargs) -> None:
        """"""
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        """
        Create a tmux server instance before each method test.

        It has to be created in order for the control mode client
        to connect to it for testing purposes.
        A new one is created for each test
        to make sure no server state information
        would interfere with each other.

        The tmux server creates a socket file
        inside the directory ``$TMUX_TMPDIR``.
        We use a temporary directory so it is guaranteed
        to not interfere with other tests
        or any running tmux servers.

        Also creates an empty configuration file
        so that tmux does not use the OS default nor the user one.
        """
        _logger.debug('Creating $TMUX_TMPDIR directory.')
        self.tmux_tmpdir = tempfile.TemporaryDirectory()
        self.tmux_tmpdir_path = pathlib.Path(self.tmux_tmpdir.name)
        _logger.debug('Creating tmux.conf.')
        tmux_config_path = self.tmux_tmpdir_path / 'tmux.conf'
        tmux_config_path.touch()
        _logger.debug('Setting environment variables.')
        self.environ_backup = EnvironBackup()
        self.environ_backup.backup_and_set(
            TMUX=None,
            TMUX_TMPDIR=str(self.tmux_tmpdir_path),
        )
        _logger.debug('Creating control mode.')
        self.control_mode = ControlMode(
            configuration_file_path=tmux_config_path,
            timeout=wait_time,
        )
        _logger.debug('Determining tmux server PID.')
        self.tmux_server_pid = get_server_pid()
        _logger.debug('Got tmux server PID as %s.', self.tmux_server_pid)

    def tearDown(self) -> None:
        """Shut down the tmux server after each method test."""
        _logger.debug('Shutting down control mode.')
        self.control_mode.terminate()
        _logger.debug('Sending kill-server command.')
        try:
            kill_server()
        except subprocess.CalledProcessError as e:
            _logger.debug(
                'The kill-server command failed.\n'
                'stdout: {stdout}\n'
                'stderr: {stderr}'.format(
                    stdout=e.stdout.decode().rstrip('\r\n'),
                    stderr=e.stderr.decode().rstrip('\r\n'),
                )
            )
            tmux_server_pid = self.tmux_server_pid
            if tmux_server_pid != 0:
                if psutil.pid_exists(tmux_server_pid):
                    _logger.debug(
                        'Killing tmux server (PID: %s).\n',
                        tmux_server_pid
                    )
                    os.kill(tmux_server_pid, signal.SIGKILL)
                if psutil.pid_exists(tmux_server_pid):
                    _logger.error(
                        'Unable to kill tmux server (PID: %s).\n',
                        tmux_server_pid
                    )
        _logger.debug('Restoring environment variables.')
        self.environ_backup.restore()
        _logger.debug('Removing $TMUX_TMPDIR directory.')
        self.tmux_tmpdir.cleanup()

    def test_initialisation(self) -> None:
        """
        Create a :class:`phile.tray.tmux.ControlMode`.

        It is created in :meth:`setUp`.
        This test flags up initialisation errors
        that would likely affect all other tests.
        """

    def test_initialisation_with_session_name(self) -> None:
        """
        Create a control mode and connect to a given session.

        A session name can be given
        to :class:`phile.tray.tmux.ControlMode`
        indicating the session to connect to,
        and creating the session of the given name
        if it does not exist already.
        This tests asks the tmux server
        for the currently connected session,
        and checks that it is the requested session.
        """
        session_name = 'control'
        new_control_mode = ControlMode(
            session_name=session_name, timeout=wait_time
        )
        new_control_mode.send_command(
            'display-message -p '
            "'#{session_name}'"
        )
        self.assertEqual(
            new_control_mode.read_block(rstrip_newline=True),
            session_name
        )

    def test_read_block(self) -> None:
        """
        Read a block message.

        Send a command to ask the server for its PID.
        The response is wrapped in a block.
        So :meth:`~phile.tray.tmux.read_block` should return the PID
        after the command is sent.
        """
        self.control_mode.send_command('display-message -p ' "'#{pid}'")
        self.assertEqual(
            int(self.control_mode.read_block(rstrip_newline=True)),
            self.tmux_server_pid
        )

    def test_readline_with_timeout(self) -> None:
        """
        Read a line should throw after timeout.

        Tells the server to not send over display data.
        Server starts a shell and then sends over what to display.
        Turning on `no-output` tells server to not send them over.
        This is necessary here because the server
        takes a while to create the shell.
        So we do not want to wait for it in a unit test.
        If it is not turned on, then the initial display data
        can be sent at any time,
        and that stops us from testing a timeout from not having data.
        """
        self.control_mode.send_command(
            CommandBuilder.refresh_client(no_output=True)
        )
        self.control_mode.read_block()
        original_timeout_seconds = self.control_mode.timeout_seconds
        self.control_mode.timeout_seconds = 0
        with self.assertRaises(TimeoutError):
            self.control_mode.readline()
        self.control_mode.timeout_seconds = original_timeout_seconds

    def test_terminate_fails_to_exit(self) -> None:
        """
        Kill client if the server does not provide a normal exit.

        It is possible the server does not process a client exit request
        as an actual exit request,
        possibly due to lingering data in the ``stdin`` stream
        or the server is busy.
        Regardless of the reason, the client process may not exit.
        This tests ensures that :class:`~phile.tray.tmux.ControlMode`
        falls back to killing the process when that happens.

        Forcing the exit to fail is done
        by writing a command to the ``stdin`` stream
        without the terminating new line.
        When :meth:`~phile.tray.tmux.ControlMode.terminate`
        tries to send an exit request,
        it sends just a newline ``\\n`` on its own.
        This terminates the prepared command,
        turning the exit request into a different command,
        and the server does not know the client wants to exit.
        Neither, then, does the client process.
        In particular, the client does not exit.
        This means, when :class:`~phile.tray.tmux.ControlMode`
        waits for the process to exit, it times out,
        forcing the exit to fail.

        The unterminated message prepared
        requests the server to send back a line
        starting with ``'%exit'``.
        That line is sent by the tmux server
        after it process an exit request.
        So the prepared message when sent
        asks the server to say it knows the client is exiting
        without actually acknowledging it.
        This stops the client process from exiting
        as desired for the test.
        """
        _logger.debug('Adding lingering data in the stdin stream.')
        self.control_mode.stdin.writelines([
            'display-message -p \'%%exit\''.encode()
        ])
        original_timeout_seconds = self.control_mode.timeout_seconds
        self.control_mode.timeout_seconds = 0
        with unittest.mock.patch(
            'phile.tray.tmux.ControlMode.readline_until_starts_with'
        ):
            self.control_mode.terminate()
        self.control_mode.timeout_seconds = original_timeout_seconds

    def test_function_kill_server_failing(self) -> None:
        """
        The :meth:`~phile.tray.tmux.kill_server` function
        fails by raising an exception.

        Calls the function twice.
        The first one should succeed, killing the server.
        The second call tries to stop a server that has been killed,
        and should then raise an exception.
        """
        kill_server()
        with self.assertRaises(subprocess.CalledProcessError):
            kill_server()


class TestIconList(unittest.TestCase):
    """Unit test for :class:`~phile.tray.tmux.IconList`."""

    def __init__(self, *args, **kwargs) -> None:
        """"""
        # This method is created purely to overwrite default docstring.
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        """
        Create a directory for storing tray files.

        This will be used to test for file change responses.
        """
        _logger.debug('Creating tray file directory.')
        self.tray_dir = tempfile.TemporaryDirectory()
        self.tray_dir_path = pathlib.Path(self.tray_dir.name)
        _logger.debug('Creating icon list.')
        self.configuration = Configuration(
            tray_directory=self.tray_dir_path
        )
        self.control_mode = unittest.mock.Mock()
        self.observer = Observer()
        self.icon_list = IconList(
            configuration=self.configuration,
            control_mode=self.control_mode,
            observer=self.observer,
        )
        self.observer.start()

    def tearDown(self) -> None:
        """Clean up the created tray file directory."""
        _logger.debug('Removing $TMUX_TMPDIR directory.')
        self.observer.stop()
        self.assertTrue(self.observer.was_stop_called())
        self.tray_dir.cleanup()

    def test_initialisation(self) -> None:
        """Creates a :class:`~phile.tray.tmux.IconList`."""

    def test_refresh_status_line_with_no_tray_files(self) -> None:
        """Change tmux status line to reflect currently tracked files."""
        self.icon_list.refresh_status_line()
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right(''),
        )

    def test_insert_set_and_remove(self) -> None:
        """Telling icon list of tray file changes updates status line."""
        _logger.debug('Inserting year tray file.')
        year_tray_file = TrayFile(
            configuration=self.configuration, name='year'
        )
        year_tray_file.text_icon = '2345'
        self.icon_list.insert(0, year_tray_file)
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right(
                year_tray_file.text_icon
            )
        )
        _logger.debug('Setting year tray file.')
        year_tray_file.text_icon = '1234'
        self.icon_list.set(0, year_tray_file)
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right(
                year_tray_file.text_icon
            )
        )
        _logger.debug('Inserting month tray file.')
        month_tray_file = TrayFile(
            configuration=self.configuration, name='month'
        )
        month_tray_file.text_icon = '01'
        self.icon_list.insert(0, month_tray_file)
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right(
                month_tray_file.text_icon + year_tray_file.text_icon
            )
        )
        _logger.debug('Removing year tray file.')
        self.icon_list.remove(1)
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right(
                month_tray_file.text_icon
            )
        )
        _logger.debug('Removing month tray file.')
        self.icon_list.remove(0)
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right(''),
        )

    def test_load(self) -> None:
        """
        Load decides what to do based on existence of files.

        It should handle add and removing
        both tracked and untracked files.
        So four sets of operations.
        """
        _logger.debug('Adding year tray file.')
        year_tray_file = TrayFile(
            configuration=self.configuration, name='year'
        )
        year_tray_file.text_icon = '2345'
        year_tray_file.save()
        self.icon_list.load(year_tray_file)
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right('2345'),
        )
        self.control_mode.send_command.reset_mock()
        _logger.debug('Adding month tray file.')
        month_tray_file = TrayFile(
            configuration=self.configuration, name='month'
        )
        month_tray_file.text_icon = '01'
        month_tray_file.save()
        self.icon_list.load(month_tray_file)
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right('012345'),
        )
        self.control_mode.send_command.reset_mock()
        _logger.debug('Setting month tray file.')
        month_tray_file.text_icon = '12'
        month_tray_file.save()
        self.icon_list.load(month_tray_file)
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right('122345'),
        )
        self.control_mode.send_command.reset_mock()
        _logger.debug('Removing month tray file.')
        month_tray_file.remove()
        self.icon_list.load(month_tray_file)
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right('2345'),
        )
        self.control_mode.send_command.reset_mock()
        _logger.debug('Removing year tray file.')
        year_tray_file.remove()
        self.icon_list.load(year_tray_file)
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right(''),
        )
        self.control_mode.send_command.reset_mock()
        _logger.debug('Pretend to remov year tray file again.')
        self.icon_list.load(year_tray_file)
        self.control_mode.send_command.assert_not_called()

    def test_dispatch_with_bad_file(self) -> None:
        """
        Dispatch ignores badly structured files.

        There is not much we can do about it as a reader.
        """
        tray_file = TrayFile(
            configuration=self.configuration, name='month'
        )
        tray_file.text_icon = 'ABC'
        tray_file.save()
        with tray_file.path.open('a+') as file_stream:
            file_stream.write('\nNot JSON.')
        with self.assertWarns(UserWarning):
            self.icon_list.dispatch(
                watchdog.events.FileCreatedEvent(tray_file.path)
            )

    def test_show_with_existing_files(self) -> None:
        """
        Showing should display existing tray files.

        Directory changes should be ignored.
        Wrong suffix should be ignored.
        Moves are treated as delete and create.
        """
        _logger.debug('Inserting event setter to monitor events.')
        event_setter = EventSetter()
        self.icon_list._observer.add_handler(
            event_setter, self.configuration.tray_directory
        )
        _logger.debug('Adding a tray file.')
        year_tray_file = TrayFile(
            configuration=self.configuration, name='year'
        )
        year_tray_file.text_icon = '2345'
        year_tray_file.save()
        _logger.debug('Adding a second tray file.')
        month_tray_file = TrayFile(
            configuration=self.configuration, name='month'
        )
        month_tray_file.text_icon = '12/'
        month_tray_file.save()
        _logger.debug('Creating subdirectory in tray file directory.')
        subdirectory = self.configuration.tray_directory / (
            'subdir' + self.configuration.tray_suffix
        )
        subdirectory.mkdir()
        _logger.debug('Creating file with wrong suffix.')
        wrong_tray_file = self.configuration.tray_directory / (
            'wrong' + self.configuration.tray_suffix + '_wrong'
        )
        wrong_tray_file.touch()
        _logger.debug('Showing tray.')
        self.icon_list.show()
        expected_status_right = CommandBuilder.set_global_status_right(
            month_tray_file.text_icon + year_tray_file.text_icon
        )
        while event_setter.wait(wait_time.total_seconds()):
            event_setter.clear()
            call_args = self.control_mode.send_command.call_args
            if call_args == unittest.mock.call(expected_status_right):
                break
        else:
            event_setter.clear()
            self.control_mode.send_command.assert_called_with(
                expected_status_right
            )

    def test_file_changes_after_show_and_then_hide(self) -> None:
        """
        Calling show and then hide. Modify file trays in the middle.

        File trays are created, renamed and deleted.
        The tray file may be truncated before writing the real content.
        So this test allows for other changes before the expected one.
        """
        _logger.debug('Showing empty tray.')
        self.icon_list.show()
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right('')
        )
        self.assertIsNotNone(self.icon_list._watchdog_watch)
        _logger.debug('Inserting event setter to monitor events.')
        event_setter = EventSetter()
        self.icon_list._observer.add_handler(
            event_setter, self.configuration.tray_directory
        )
        _logger.debug('Adding a tray file.')
        year_tray_file = TrayFile(
            configuration=self.configuration, name='year'
        )
        year_tray_file.text_icon = '2345'
        year_tray_file.save()
        expected_status_right = CommandBuilder.set_global_status_right(
            year_tray_file.text_icon
        )
        while event_setter.wait(wait_time.total_seconds()):
            event_setter.clear()
            call_args = self.control_mode.send_command.call_args
            if call_args == unittest.mock.call(expected_status_right):
                break
        else:
            event_setter.clear()
            self.control_mode.send_command.assert_called_with(
                expected_status_right
            )
        _logger.debug('Adding a second tray file.')
        month_tray_file = TrayFile(
            configuration=self.configuration, name='month'
        )
        month_tray_file.text_icon = '12/'
        month_tray_file.save()
        expected_status_right = CommandBuilder.set_global_status_right(
            month_tray_file.text_icon + year_tray_file.text_icon
        )
        while event_setter.wait(wait_time.total_seconds()):
            event_setter.clear()
            call_args = self.control_mode.send_command.call_args
            if call_args == unittest.mock.call(expected_status_right):
                break
        else:
            event_setter.clear()
            self.control_mode.send_command.assert_called_with(
                expected_status_right
            )
        _logger.debug('Changing a tray file.')
        year_tray_file.text_icon = '1234'
        year_tray_file.save()
        expected_status_right = CommandBuilder.set_global_status_right(
            month_tray_file.text_icon + year_tray_file.text_icon
        )
        while event_setter.wait(wait_time.total_seconds()):
            event_setter.clear()
            call_args = self.control_mode.send_command.call_args
            if call_args == unittest.mock.call(expected_status_right):
                break
        else:
            event_setter.clear()
            self.control_mode.send_command.assert_called_with(
                expected_status_right
            )
        _logger.debug('Moving a tray file.')
        new_year_tray_file = TrayFile(
            configuration=self.configuration, name='new_year'
        )
        year_tray_file.path.rename(new_year_tray_file.path)
        year_tray_file.path = new_year_tray_file.path
        expected_status_right = CommandBuilder.set_global_status_right(
            month_tray_file.text_icon + year_tray_file.text_icon
        )
        while event_setter.wait(wait_time.total_seconds()):
            event_setter.clear()
            call_args = self.control_mode.send_command.call_args
            if call_args == unittest.mock.call(expected_status_right):
                break
        else:
            event_setter.clear()
            self.control_mode.send_command.assert_called_with(
                expected_status_right
            )
        _logger.debug('Removing a tray file.')
        year_tray_file.text_icon = ''
        year_tray_file.remove()
        expected_call_args = unittest.mock.call(
            CommandBuilder.set_global_status_right(
                month_tray_file.text_icon
            )
        )
        send_command = self.control_mode.send_command
        while send_command.call_args != expected_call_args:
            self.assertTrue(event_setter.wait(wait_time.total_seconds()))
            event_setter.clear()
        _logger.debug('Hiding system tray.')
        self.icon_list.hide()
        self.assertIsNone(self.icon_list._watchdog_watch)
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right('')
        )

    def test_hide_without_show(self) -> None:
        """Hiding without showing first does nothing."""
        _logger.debug('Hiding  empty tray.')
        self.icon_list.hide()
        self.assertIsNone(self.icon_list._watchdog_watch)
        self.control_mode.send_command.assert_not_called()

    def test_double_show(self) -> None:
        """Double show does nothing."""
        _logger.debug('Hiding  empty tray.')
        self.icon_list.show()
        self.assertIsNotNone(self.icon_list._watchdog_watch)
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.set_global_status_right('')
        )
        self.control_mode.send_command.reset_mock()
        self.icon_list.show()
        self.assertIsNotNone(self.icon_list._watchdog_watch)
        self.control_mode.send_command.assert_not_called()

    def test_run_with_no_file_and_no_events(self) -> None:
        """Running should drain control mode stdout stream."""

        def readline_side_effect():
            self.assertIsNotNone(self.icon_list._watchdog_watch)
            raise KeyboardInterrupt()

        self.control_mode.readline = unittest.mock.MagicMock(
            side_effect=readline_side_effect
        )
        self.icon_list.run()
        self.assertIsNone(self.icon_list._watchdog_watch)


if __name__ == '__main__':
    unittest.main()
