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
import phile.trigger.cli
from test_phile.test_init import UsesCapabilities
from test_phile.test_trigger.test_init import UsesRegistry


class TestPrompt(UsesRegistry, UsesCapabilities, unittest.TestCase):
    """Tests :func:`~phile.trigger.cli.Prompt`."""

    def setUp(self) -> None:
        super().setUp()
        self.stdout = io.StringIO()
        self.prompt = phile.trigger.cli.Prompt(
            capabilities=self.capabilities, stdout=self.stdout
        )
        self.prompt.use_rawinput = False
        self.set_up_triggers()

    def set_up_triggers(self) -> None:
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


if __name__ == '__main__':
    unittest.main()
