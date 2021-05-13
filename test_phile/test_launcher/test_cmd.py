#!/usr/bin/env python3
"""
------------------------------
Test :mod:`phile.launcher.cmd`
------------------------------
"""

# Standard libraries.
import asyncio
import io
import typing
import unittest

# Internal packages.
import phile.asyncio
import phile.launcher
import phile.launcher.cmd
import phile.pubsub_event

StrSubscriber = phile.pubsub_event.Subscriber[str]


class TestCmd(unittest.IsolatedAsyncioTestCase):
    """Tests :func:`~phile.launcher.cmd.Cmd`."""

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.cmd: phile.launcher.cmd.Cmd
        self.database_add_events: StrSubscriber
        self.database_remove_events: StrSubscriber
        self.launcher_name_1: str
        self.launcher_name_2: str
        self.launcher_registry: phile.launcher.Registry
        self.state_machine_start_events: StrSubscriber
        self.state_machine_stop_events: StrSubscriber
        self.stdin: io.StringIO
        self.stdout: io.StringIO
        super().__init__(*args, **kwargs)

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.launcher_registry = launcher_registry = (
            phile.launcher.Registry()
        )
        self.stdin = io.StringIO()
        self.stdout = io.StringIO()
        self.cmd = phile.launcher.cmd.Cmd(
            stdin=self.stdin,
            stdout=self.stdout,
            launcher_registry=launcher_registry,
        )
        self.add_subscribers()
        await phile.asyncio.wait_for(self.add_launchers())

    def add_subscribers(self) -> None:
        self.database_add_events = StrSubscriber(
            publisher=(
                self.launcher_registry.database.event_publishers[
                    phile.launcher.Database.add]
            )
        )
        self.database_remove_events = StrSubscriber(
            publisher=(
                self.launcher_registry.database.event_publishers[
                    phile.launcher.Database.remove]
            )
        )
        self.state_machine_start_events = StrSubscriber(
            publisher=(
                self.launcher_registry.state_machine.event_publishers[
                    phile.launcher.StateMachine.start]
            )
        )
        self.state_machine_stop_events = StrSubscriber(
            publisher=(
                self.launcher_registry.state_machine.event_publishers[
                    phile.launcher.StateMachine.stop]
            )
        )

    async def add_launchers(self) -> None:

        async def add(launcher_name: str) -> None:
            await self.launcher_registry.database.add(
                entry_name=launcher_name,
                descriptor=phile.launcher.Descriptor(
                    exec_start=[asyncio.get_event_loop().create_future],
                )
            )

        self.launcher_name_1 = 'launcher_cmd_runner'
        await add(self.launcher_name_1)
        self.launcher_name_2 = 'launcher_cmd_tester'
        await add(self.launcher_name_2)

    def test_do_eof_stops_cmd(self) -> None:
        self.assertTrue(self.cmd.onecmd('EOF'))

    async def test_do_reset_reuses_id(self) -> None:
        self.test_do_list_sorts_output_of_new_launchers()
        await phile.asyncio.wait_for(
            self.launcher_registry.database.remove(self.launcher_name_1)
        )
        self.assertFalse(self.cmd.onecmd('reset'))
        self.assertEqual(
            self.stdout.getvalue(),
            'Listing IDs and states of 2 launchers.\n'
            '[stopped] 0: {launcher_name_1}\n'
            '[stopped] 1: {launcher_name_2}\n'
            'Listing IDs and states of 1 launchers.\n'
            '[stopped] 0: {launcher_name_2}\n'.format(
                launcher_name_1=self.launcher_name_1,
                launcher_name_2=self.launcher_name_2,
            )
        )

    async def test_do_start_starts_launcher(self) -> None:
        self.assertFalse(self.cmd.onecmd('list'))
        self.assertFalse(
            self.launcher_registry.state_machine.is_running(
                self.launcher_name_1
            )
        )
        self.assertFalse(self.cmd.onecmd('start 0'))

        async def wait_for_launcher_to_start(launcher_name: str) -> None:
            pull = self.state_machine_start_events.pull
            while launcher_name != await pull():
                pass

        await phile.asyncio.wait_for(
            wait_for_launcher_to_start(self.launcher_name_1)
        )
        self.assertTrue(
            self.launcher_registry.state_machine.is_running(
                self.launcher_name_1
            )
        )

    async def test_do_start_writes_to_stdout(self) -> None:
        self.assertFalse(self.cmd.onecmd('reset'))
        self.assertFalse(self.cmd.onecmd('start 1'))
        self.assertEqual(
            self.stdout.getvalue(),
            'Listing IDs and states of 2 launchers.\n'
            '[stopped] 0: {launcher_name_1}\n'
            '[stopped] 1: {launcher_name_2}\n'
            'Started 1 launchers.\n'.format(
                launcher_name_1=self.launcher_name_1,
                launcher_name_2=self.launcher_name_2,
            )
        )

    def test_do_start_warns_wrong_argument(self) -> None:
        self.assertFalse(self.cmd.onecmd('start a'))
        self.assertEqual(
            self.stdout.getvalue(), 'Unable to parse given launcher: a\n'
        )

    def test_do_start_informs_unknown_launchers(self) -> None:
        self.assertFalse(self.cmd.onecmd('start 0'))
        self.assertEqual(
            self.stdout.getvalue(), 'Unknown launcher ID 0.\n'
        )

    async def test_do_stop_stops_launcher(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name_1
            )
        )
        self.assertFalse(self.cmd.onecmd('list'))
        self.assertTrue(
            self.launcher_registry.state_machine.is_running(
                self.launcher_name_1
            )
        )
        self.assertFalse(self.cmd.onecmd('stop 0'))

        async def wait_for_launcher_to_stop(launcher_name: str) -> None:
            pull = self.state_machine_stop_events.pull
            while launcher_name != await pull():
                pass

        await phile.asyncio.wait_for(
            wait_for_launcher_to_stop(self.launcher_name_1)
        )
        self.assertFalse(
            self.launcher_registry.state_machine.is_running(
                self.launcher_name_1
            )
        )

    async def test_do_stop_writes_to_stdout(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name_1
            )
        )
        self.assertFalse(self.cmd.onecmd('list'))
        self.assertFalse(self.cmd.onecmd('stop 0'))
        self.assertEqual(
            self.stdout.getvalue(),
            'Listing IDs and states of 2 launchers.\n'
            '[running] 0: {launcher_name_1}\n'
            '[stopped] 1: {launcher_name_2}\n'
            'Stopped 1 launchers.\n'.format(
                launcher_name_1=self.launcher_name_1,
                launcher_name_2=self.launcher_name_2,
            )
        )

    def test_do_stop_warns_wrong_argument(self) -> None:
        self.assertFalse(self.cmd.onecmd('stop a'))
        self.assertEqual(
            self.stdout.getvalue(), 'Unable to parse given launcher: a\n'
        )

    def test_do_stop_informs_unknown_launchers(self) -> None:
        self.assertFalse(self.cmd.onecmd('stop 0'))
        self.assertEqual(
            self.stdout.getvalue(), 'Unknown launcher ID 0.\n'
        )

    def test_do_list_sorts_output_of_new_launchers(self) -> None:
        self.assertFalse(self.cmd.onecmd('list'))
        self.assertEqual(
            self.stdout.getvalue(),
            'Listing IDs and states of 2 launchers.\n'
            '[stopped] 0: {launcher_name_1}\n'
            '[stopped] 1: {launcher_name_2}\n'.format(
                launcher_name_1=self.launcher_name_1,
                launcher_name_2=self.launcher_name_2,
            )
        )

    async def test_do_list_prints_running_launchers(self) -> None:
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name_1
            )
        )
        self.assertFalse(self.cmd.onecmd('list'))
        self.assertEqual(
            self.stdout.getvalue(),
            'Listing IDs and states of 2 launchers.\n'
            '[running] 0: {launcher_name_1}\n'
            '[stopped] 1: {launcher_name_2}\n'.format(
                launcher_name_1=self.launcher_name_1,
                launcher_name_2=self.launcher_name_2,
            )
        )

    async def test_do_list_ignores_removed_launchers(self) -> None:
        self.assertFalse(self.cmd.onecmd('list'))
        await phile.asyncio.wait_for(
            self.launcher_registry.database.remove(self.launcher_name_1)
        )
        self.assertFalse(self.cmd.onecmd('list'))
        self.assertEqual(
            self.stdout.getvalue(),
            'Listing IDs and states of 2 launchers.\n'
            '[stopped] 0: {launcher_name_1}\n'
            '[stopped] 1: {launcher_name_2}\n'
            'Listing IDs and states of 1 launchers.\n'
            '[stopped] 1: {launcher_name_2}\n'.format(
                launcher_name_1=self.launcher_name_1,
                launcher_name_2=self.launcher_name_2,
            )
        )
