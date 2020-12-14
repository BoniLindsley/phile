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
import signal
import subprocess
import tempfile
import threading
import unittest
import unittest.mock

# External dependencies.
import psutil  # type: ignore[import]
import watchdog.events  # type: ignore[import]

# Internal packages.
import phile.configuration
import phile.tray
from phile.tray.tmux import (
    CommandBuilder, ControlMode, get_server_pid, IconList, kill_server,
    timedelta_to_seconds
)
from phile.watchdog_extras import Observer
from test_phile.pyside2_test_tools import EnvironBackup
import test_phile.threaded_mock

_logger = logging.getLogger(
    __loader__.name  # type: ignore[name-defined]  # mypy issue #1422
)
"""Logger whose name is the module name."""

wait_time = datetime.timedelta(seconds=2)


class TestCommandBuilder(unittest.TestCase):
    """
    Tests :class:`~phile.tray.tmux.CommandBuilder`.

    Ensures the tmux command string returned from the class methods
    are as expected.
    """

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

    def test_unset_global_status_right(self) -> None:
        self.assertEqual(
            CommandBuilder.unset_global_status_right(),
            "set-option -gu status-right"
        )


class TestTimedeltaToSeconds(unittest.TestCase):
    """Tests :class:`~phile.tray.tmux.timedelta_to_seconds`."""

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
    Tests :class:`~phile.tray.tmux.ControlMode`.

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
        tmux_tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmux_tmpdir.cleanup)
        tmux_tmpdir_path = pathlib.Path(tmux_tmpdir.name)
        _logger.debug('Creating tmux.conf.')
        tmux_config_path = tmux_tmpdir_path / 'tmux.conf'
        tmux_config_path.touch()
        _logger.debug('Setting environment variables.')
        environ_backup = EnvironBackup()
        self.addCleanup(environ_backup.restore)
        environ_backup.backup_and_set(
            TMUX=None,
            TMUX_TMPDIR=str(tmux_tmpdir_path),
        )
        _logger.debug('Creating control mode.')
        self.control_mode = ControlMode(
            configuration_file_path=tmux_config_path,
            session_name=None,
            timeout=wait_time,
        )
        _logger.debug('Determining tmux server PID.')
        self.tmux_server_pid = get_server_pid()
        _logger.debug('Got tmux server PID as %s.', self.tmux_server_pid)

    def tearDown(self) -> None:
        """Shut down the tmux server after each method test."""
        _logger.debug('Shutting down control mode.')
        self.control_mode.__del__()
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


class CompletionCheckingThread(threading.Thread):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.daemon = True
        self.completed_event = threading.Event()

    def run(self):
        super().run()
        # If run raised an exception,
        # the event would not be set here.
        self.completed_event.set()


class TestIconList(unittest.TestCase):
    """Tests :class:`~phile.tray.tmux.IconList`."""

    def set_up_configuration(self) -> None:
        """
        Use unique data directories to not interfere with other tests.
        """
        user_state_directory = tempfile.TemporaryDirectory()
        self.addCleanup(user_state_directory.cleanup)
        self.configuration = phile.configuration.Configuration(
            user_state_directory=pathlib.Path(user_state_directory.name)
        )
        self.trigger_directory = (
            self.configuration.trigger_root / 'phile-tray-gui'
        )

    def set_up_observer(self) -> None:
        """
        Use unique observers to ensure handlers do not linger.

        Start immediately to allow file changes propagate.
        The observer does not join, as that can take a long time.
        """
        self.observer = observer = watchdog.observers.Observer()
        observer.daemon = True
        observer.start()
        self.addCleanup(observer.stop)

    def set_up_control_mode(self) -> None:
        """Use unique control modes to not have commands linger."""
        control_mode_patch = unittest.mock.patch(
            'phile.tray.tmux.ControlMode'
        )
        self.ControlModeMock = control_mode_patch.start()
        self.addCleanup(control_mode_patch.stop)

    def set_up_icon_list(self) -> None:
        """
        Override ControlMode to not create a tmux session every test.

        Create the actual icon list to test.
        """
        self.icon_list = IconList(
            configuration=self.configuration,
            watching_observer=self.observer,
        )
        self.addCleanup(self.icon_list._entry_point.unbind)
        # For detecting commands sent to control mode.
        # Creating a new mock to make mypy happy,
        # since it detects `send_command` as a method,
        # and so assigning to it raises errors in mypy.
        self.control_mode = control_mode = unittest.mock.Mock()
        control_mode.send_command = (
            test_phile.threaded_mock.ThreadedMock()
        )
        self.icon_list._control_mode = control_mode
        self.trigger_directory = (
            self.icon_list._entry_point.trigger_directory
        )

    def setUp(self) -> None:
        self.set_up_configuration()
        self.set_up_observer()
        self.set_up_control_mode()
        self.set_up_icon_list()

    def test_initialisation_creates_triggers(self) -> None:
        """
        Initialising a :class:`~phile.tray.tmux.IconList`
        creates triggers.
        """
        icon_list = self.icon_list
        trigger_directory = self.trigger_directory
        trigger_suffix = self.configuration.trigger_suffix
        self.assertTrue(icon_list.is_hidden())
        self.assertTrue(
            (trigger_directory / ('close' + trigger_suffix)).is_file()
        )
        self.assertTrue(
            (trigger_directory / ('show' + trigger_suffix)).is_file()
        )

    def test_refresh_with_no_tray_files(self) -> None:
        """Change tmux status line to reflect currently tracked files."""
        self.icon_list.refresh()
        self.control_mode.send_command.assert_called_with_soon(
            CommandBuilder.set_global_status_right(''),
        )

    def test_show_with_existing_files(self) -> None:
        """
        Showing should display existing tray files.

        Directory changes should be ignored.
        Wrong suffix should be ignored.
        Moves are treated as delete and create.
        """
        _logger.debug('Adding a tray file.')
        year_tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='year'
        )
        year_tray_file.text_icon = '2345'
        year_tray_file.save()
        _logger.debug('Adding a second tray file.')
        month_tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='month'
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
        self.control_mode.send_command.assert_called_with_soon(
            CommandBuilder.set_global_status_right(
                month_tray_file.text_icon + year_tray_file.text_icon
            )
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
        self.assertTrue(not self.icon_list.is_hidden())
        self.control_mode.send_command.assert_called_with_soon(
            CommandBuilder.set_global_status_right('')
        )
        _logger.debug('Inserting event setter to monitor events.')
        _logger.debug('Adding a tray file.')
        year_tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='year'
        )
        year_tray_file.text_icon = '2345'
        year_tray_file.save()
        self.control_mode.send_command.assert_called_with_soon(
            CommandBuilder.set_global_status_right(
                year_tray_file.text_icon
            )
        )
        _logger.debug('Adding a second tray file.')
        month_tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='month'
        )
        month_tray_file.text_icon = '12/'
        month_tray_file.save()
        self.control_mode.send_command.assert_called_with_soon(
            CommandBuilder.set_global_status_right(
                month_tray_file.text_icon + year_tray_file.text_icon
            )
        )
        _logger.debug('Changing a tray file.')
        year_tray_file.text_icon = '1234'
        year_tray_file.save()
        self.control_mode.send_command.assert_called_with_soon(
            CommandBuilder.set_global_status_right(
                month_tray_file.text_icon + year_tray_file.text_icon
            )
        )
        _logger.debug('Moving a tray file.')
        new_year_tray_file = phile.tray.File.from_path_stem(
            configuration=self.configuration, path_stem='a_year'
        )
        year_tray_file.path.rename(new_year_tray_file.path)
        year_tray_file.path = new_year_tray_file.path
        self.control_mode.send_command.assert_called_with_soon(
            CommandBuilder.set_global_status_right(
                year_tray_file.text_icon + month_tray_file.text_icon
            )
        )
        _logger.debug('Removing a tray file.')
        year_tray_file.text_icon = ''
        year_tray_file.path.unlink(missing_ok=True)
        self.control_mode.send_command.assert_called_with_soon(
            CommandBuilder.set_global_status_right(
                month_tray_file.text_icon
            )
        )
        _logger.debug('Hiding system tray.')
        self.icon_list.hide()
        self.assertTrue(self.icon_list.is_hidden())
        self.control_mode.send_command.assert_called_with_soon(
            CommandBuilder.unset_global_status_right()
        )

    def test_hide_without_show(self) -> None:
        """Hiding without showing first does nothing."""
        _logger.debug('Hiding  empty tray.')
        self.icon_list.hide()
        self.assertTrue(self.icon_list.is_hidden())
        self.control_mode.send_command.assert_not_called()

    def test_double_show(self) -> None:
        """Double show does nothing."""
        _logger.debug('Hiding  empty tray.')
        self.icon_list.show()
        self.assertTrue(not self.icon_list.is_hidden())
        self.control_mode.send_command.assert_called_with_soon(
            CommandBuilder.set_global_status_right('')
        )
        self.control_mode.send_command.reset_mock()
        self.icon_list.show()
        self.assertTrue(not self.icon_list.is_hidden())
        self.control_mode.send_command.assert_not_called()

    def test_run_returning_on_exit_response(self) -> None:
        """Run should return when it receives an ``%exit`` response."""
        # Give an exit response to run.
        self.control_mode.readline.return_value = '%exit'
        # Running blocks, so do it in a separate thread.
        # Detect whether it returns normally.
        run_thread = CompletionCheckingThread(target=self.icon_list.run)
        run_thread.start()
        self.assertTrue(
            run_thread.completed_event.wait(
                timeout=wait_time.total_seconds()
            )
        )
        self.assertEqual(self.control_mode.readline.call_count, 1)

    def test_run_ignores_blocks(self) -> None:
        """
        Run ignore response blocks.

        In particular,
        if an exit response is wrapped inside a response block,
        it should be ignored as well.
        """
        # Give an exit response to run.
        self.control_mode.readline.side_effect = [
            '%begin ',
            '%exit',
            '%end ',
            '%exit',
        ]
        # Running blocks, so do it in a separate thread.
        # Detect whether it returns normally.
        run_thread = CompletionCheckingThread(target=self.icon_list.run)
        run_thread.start()
        self.assertTrue(
            run_thread.completed_event.wait(
                timeout=wait_time.total_seconds()
            )
        )
        self.assertEqual(self.control_mode.readline.call_count, 4)

    def test_close_sends_command(self) -> None:
        """Close sends an exit request to tmux."""
        self.icon_list.close()
        self.assertTrue(self.icon_list.is_hidden())
        self.control_mode.send_command.assert_called_with(
            CommandBuilder.exit_client()
        )

    def test_triggers(self) -> None:
        """Tray GUI has show, hide and close triggers."""
        icon_list = self.icon_list
        # Use a threaded mock to check when events are queued into Qt.
        trigger_directory = self.trigger_directory
        trigger_suffix = self.configuration.trigger_suffix
        trigger_path = trigger_directory / ('show' + trigger_suffix)
        # Respond to a show trigger.
        with unittest.mock.patch.object(
            icon_list,
            'show',
            new_callable=test_phile.threaded_mock.ThreadedMock,
            wraps=icon_list.show
        ) as show_mock:
            trigger_path.unlink()
            show_mock.assert_called_soon()
        # Respond to a hide trigger.
        trigger_path = trigger_directory / ('hide' + trigger_suffix)
        with unittest.mock.patch.object(
            icon_list,
            'hide',
            new_callable=test_phile.threaded_mock.ThreadedMock,
            wraps=icon_list.hide
        ) as hide_mock:
            trigger_path.unlink()
            hide_mock.assert_called_soon()
        # Respond to a close trigger.
        trigger_path = trigger_directory / ('close' + trigger_suffix)
        with unittest.mock.patch.object(
            icon_list,
            'close',
            new_callable=test_phile.threaded_mock.ThreadedMock,
            wraps=icon_list.close
        ) as close_mock:
            trigger_path.unlink()
            close_mock.assert_called_soon()


if __name__ == '__main__':
    unittest.main()
