#!/usr/bin/env python3
"""
-----------------------------
Test :mod:`phile.trigger.cli`
-----------------------------
"""

# Standard library.
import io
import unittest
import unittest.mock

# Internal packages.
import phile
import phile.asyncio
import phile.trigger
import phile.trigger.cli
from test_phile.test_init import UsesCapabilities
from test_phile.test_trigger.test_init import UsesRegistry


class _UsesPrompt(UsesRegistry, UsesCapabilities, unittest.TestCase):
    """Tests :func:`~phile.trigger.cli.Prompt`."""

    def setUp(self) -> None:
        super().setUp()
        self.stdin = io.StringIO()
        self.stdout = io.StringIO()
        self.prompt = phile.trigger.cli.Prompt(
            capabilities=self.capabilities,
            stdin=self.stdin,
            stdout=self.stdout
        )


class TestPrompt(_UsesPrompt, unittest.TestCase):
    """Tests :func:`~phile.trigger.cli.Prompt`."""

    def setUp(self) -> None:
        super().setUp()
        self.run_mock = unittest.mock.Mock()
        self.trigger_registry.bind('run', self.run_mock)
        self.trigger_registry.show('run')
        self.clean_mock = unittest.mock.Mock()
        self.trigger_registry.bind('clean', self.clean_mock)
        self.trigger_registry.show('clean')

    def test_do_eof_stops_prompt(self) -> None:
        self.assertTrue(self.prompt.onecmd('EOF'))

    def test_do_reset_uses_id_from_one(self) -> None:
        self.test_do_list_sorts_output_of_new_triggers()
        self.trigger_registry.unbind('clean')
        self.assertFalse(self.prompt.onecmd('reset'))
        self.assertEqual(
            self.stdout.getvalue(),
            'Listing IDs of 2 available triggers.\n'
            'Trigger 0 is clean\n'
            'Trigger 1 is run\n'
            'Listing IDs of 1 available triggers.\n'
            'Trigger 0 is run\n'
        )

    def test_do_exe_activates_trigger(self) -> None:
        self.assertFalse(self.prompt.onecmd('reset'))
        self.assertFalse(self.prompt.onecmd('exe 1'))
        self.run_mock.assert_called_with()

    def test_do_execute_writes_to_stdout_on_trigger(self) -> None:
        self.assertFalse(self.prompt.onecmd('reset'))
        self.assertFalse(self.prompt.onecmd('exe 1 0'))
        self.run_mock.assert_called_with()
        self.assertEqual(
            self.stdout.getvalue(),
            'Listing IDs of 2 available triggers.\n'
            'Trigger 0 is clean\n'
            'Trigger 1 is run\n'
            'Activated 2 triggers.\n'
        )

    def test_do_execute_warns_wrong_argument(self) -> None:
        self.assertFalse(self.prompt.onecmd('exe a'))
        self.assertEqual(
            self.stdout.getvalue(), 'Unable to parse given trigger: a\n'
        )

    def test_do_execute_informs_unknown_triggers(self) -> None:
        self.assertFalse(self.prompt.onecmd('exe 0'))
        self.assertEqual(
            self.stdout.getvalue(), 'Unknown_trigger ID 0.\n'
        )

    def test_do_execute_informs_hidden_triggers(self) -> None:
        self.assertFalse(self.prompt.onecmd('reset'))
        self.trigger_registry.unbind('clean')
        self.assertFalse(self.prompt.onecmd('exe 0'))
        self.assertEqual(
            self.stdout.getvalue(),
            'Listing IDs of 2 available triggers.\n'
            'Trigger 0 is clean\n'
            'Trigger 1 is run\n'
            'Failed to activate trigger 0 clean\n'
            'Activated 0 triggers.\n'
        )

    def test_do_list_sorts_output_of_new_triggers(self) -> None:
        self.assertFalse(self.prompt.onecmd('list'))
        self.assertEqual(
            self.stdout.getvalue(),
            'Listing IDs of 2 available triggers.\n'
            'Trigger 0 is clean\n'
            'Trigger 1 is run\n'
        )

    def test_do_list_hides_known_hidden_triggers(self) -> None:
        self.assertFalse(self.prompt.onecmd('list'))
        self.trigger_registry.hide('clean')
        self.assertFalse(self.prompt.onecmd('list'))
        self.assertEqual(
            self.stdout.getvalue(),
            'Listing IDs of 2 available triggers.\n'
            'Trigger 0 is clean\n'
            'Trigger 1 is run\n'
            'Listing IDs of 1 available triggers.\n'
            'Trigger 1 is run\n'
        )


class TestProcessCommand(_UsesPrompt, unittest.TestCase):
    """Tests :func:`~phile.trigger.cli.process_command`."""

    def test_exits_without_command(self) -> None:
        self.assertTrue(
            phile.trigger.cli.process_command(self.prompt, '')
        )

    def test_exits_with_eof(self) -> None:
        self.assertTrue(
            phile.trigger.cli.process_command(self.prompt, 'EOF')
        )

    def test_run_precmd(self) -> None:
        with unittest.mock.patch.object(
            self.prompt, 'precmd', return_value='EOF'
        ) as precmd:
            phile.trigger.cli.process_command(self.prompt, 'EOF')
            precmd.assert_called_with('EOF')

    def test_run_postcmd(self) -> None:
        with unittest.mock.patch.object(
            self.prompt, 'postcmd', return_value=True
        ) as postcmd:
            phile.trigger.cli.process_command(self.prompt, 'EOF')
            postcmd.assert_called_with(True, 'EOF')


class TestAsyncCmdloopThreadedStdin(
    _UsesPrompt, unittest.IsolatedAsyncioTestCase
):
    """Tests :func:`~phile.trigger.cli.async_cmdloop_threaded_stdin`."""

    async def test_exits_with_eof(self) -> None:
        self.stdin.write('EOF\n')
        await phile.asyncio.wait_for(
            phile.trigger.cli.async_cmdloop_threaded_stdin(
                prompt=self.prompt,
            )
        )

    async def test_respects_intro(self) -> None:
        self.prompt.intro = 'Hello\n'
        self.stdin.write('EOF\n')
        await phile.asyncio.wait_for(
            phile.trigger.cli.async_cmdloop_threaded_stdin(
                prompt=self.prompt,
            )
        )
        self.assertEqual(self.stdout.getvalue(), 'Hello\n(Cmd) ')

    async def test_run_preloop(self) -> None:
        with unittest.mock.patch.object(
            self.prompt, 'preloop'
        ) as preloop:
            self.stdin.write('EOF\n')
            await phile.asyncio.wait_for(
                phile.trigger.cli.async_cmdloop_threaded_stdin(
                    prompt=self.prompt,
                )
            )
            preloop.assert_called_with()

    async def test_run_postloop(self) -> None:
        with unittest.mock.patch.object(
            self.prompt, 'postloop'
        ) as postloop:
            self.stdin.write('EOF\n')
            await phile.asyncio.wait_for(
                phile.trigger.cli.async_cmdloop_threaded_stdin(
                    prompt=self.prompt,
                )
            )
            postloop.assert_called_with()


if __name__ == '__main__':
    unittest.main()
