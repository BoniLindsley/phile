#!/usr/bin/env python3

# Standard libraries.
import asyncio
import logging
import json
import typing
import unittest

# External dependencies.
import watchdog.events

# Internal packages.
import phile.asyncio
import phile.configuration
import phile.launcher.defaults
import phile.tray
import phile.watchdog.asyncio
from test_phile.test_configuration.test_init import (
    PreparesEntries as PreparesConfiguration,
)
from test_phile.test_launcher.test_init import (
    UsesRegistry as UsesLauncherRegistry,
)
from test_phile.test_tmux.test_init import UsesRunningTmuxServer
from test_phile.test_watchdog.test_asyncio import UsesObserver


class TestAddConfiguration(
    UsesLauncherRegistry,
    PreparesConfiguration,
    unittest.IsolatedAsyncioTestCase,
):
    def test_add_launcher(self) -> None:
        phile.launcher.defaults.add_configuration(
            launcher_registry=self.launcher_registry
        )
        self.assertTrue(
            self.launcher_registry.contains("phile.configuration")
        )

    async def test_adds_capability(self) -> None:
        self.test_add_launcher()
        file_content: dict[str, str] = {"pid_path": ".pid_file"}
        self.configuration_path.write_text(json.dumps(file_content))
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                "phile.configuration",
            )
        )
        configuration = self.capability_registry[
            phile.configuration.Entries
        ]
        self.assertIsInstance(
            configuration,
            phile.configuration.Entries,
        )
        self.assertTrue(configuration.pid_path, ".pid_file")


class TestAddLogFile(
    UsesLauncherRegistry,
    PreparesConfiguration,
    unittest.IsolatedAsyncioTestCase,
):
    def test_add_launcher(self) -> None:
        phile.launcher.defaults.add_log_file(
            launcher_registry=self.launcher_registry
        )
        self.assertTrue(
            self.launcher_registry.contains("phile.log.file")
        )

    async def test_logs_to_file(self) -> None:
        file_content: dict[str, str] = {"log_file_path": "ph.log"}
        self.configuration_path.write_text(json.dumps(file_content))
        phile.launcher.defaults.add_configuration(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_log_file(
            launcher_registry=self.launcher_registry
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                "phile.log.file",
            )
        )
        logger = logging.getLogger("phile.log.file")
        logger.warning("Add this to log.")
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.stop(
                "phile.log.file",
            )
        )
        log_file_path = self.state_directory_path / "ph.log"
        self.assertTrue(log_file_path.is_file())
        self.assertRegex(
            log_file_path.read_text(),
            r"\[\d{4}(-\d\d){2} \d\d(:\d\d){2},\d{3}\] "
            r"\[030\] phile.log.file: "
            "Add this to log.\n",
        )

    async def test_filter_by_level(self) -> None:
        file_content: dict[str, str] = {"log_file_level": "20"}
        self.configuration_path.write_text(json.dumps(file_content))
        phile.launcher.defaults.add_configuration(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_log_file(
            launcher_registry=self.launcher_registry
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                "phile.log.file",
            )
        )
        logger = logging.getLogger("phile.log.phile")
        logger.debug("Do not add this.")
        logger.info("But add this.")
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.stop(
                "phile.log.file",
            )
        )
        log_file_path = self.state_directory_path / "phile.log"
        self.assertTrue(log_file_path.is_file())
        self.assertRegex(
            log_file_path.read_text(),
            r"\[\d{4}(-\d\d){2} \d\d(:\d\d){2},\d{3}\] "
            r"\[020\] phile.log.phile: "
            "But add this.\n",
        )


class TestAddKeyring(
    UsesLauncherRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    def test_keyring_added(self) -> None:
        phile.launcher.defaults.add_keyring(
            launcher_registry=self.launcher_registry
        )
        self.assertTrue(self.launcher_registry.contains("keyring"))


class TestAddNotify(
    UsesLauncherRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.launcher_name: str

    def setUp(self) -> None:
        super().setUp()
        self.launcher_name = "phile.notify"

    def test_add_launcher(self) -> None:
        phile.launcher.defaults.add_notify(
            launcher_registry=self.launcher_registry
        )
        self.assertTrue(
            self.launcher_registry.contains(self.launcher_name)
        )

    async def test_start_launcher(self) -> None:
        self.test_add_launcher()
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name
            )
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            self.launcher_registry.state_machine.stop(
                self.launcher_name
            ),
        )

    async def test_provides_notify_registry(self) -> None:
        await self.test_start_launcher()
        capability_type = phile.notify.Registry
        self.assertIsInstance(
            self.capability_registry.get(capability_type),
            capability_type,
        )


class TestAddTray(
    UsesLauncherRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.launcher_name: str

    def setUp(self) -> None:
        super().setUp()
        self.launcher_name = "phile.tray"

    def test_add_launcher(self) -> None:
        phile.launcher.defaults.add_tray(
            launcher_registry=self.launcher_registry
        )
        self.assertTrue(
            self.launcher_registry.contains(self.launcher_name)
        )

    async def test_start_launcher(self) -> None:
        self.test_add_launcher()
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name
            )
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            self.launcher_registry.state_machine.stop(
                self.launcher_name
            ),
        )

    async def test_provides_tray_registry(self) -> None:
        await self.test_start_launcher()
        capability_type = phile.tray.Registry
        self.assertIsInstance(
            self.capability_registry.get(capability_type),
            capability_type,
        )


class TestAddTrayDatetime(
    UsesObserver,
    UsesLauncherRegistry,
    PreparesConfiguration,
    unittest.IsolatedAsyncioTestCase,
):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.launcher_name: str

    def setUp(self) -> None:
        super().setUp()
        self.launcher_name = "phile.tray.datetime"

    def test_add_launcher(self) -> None:
        phile.launcher.defaults.add_configuration(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_tray(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_tray_watchdog(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_watchdog_asyncio_observer(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_tray_datetime(
            launcher_registry=self.launcher_registry
        )
        self.assertTrue(
            self.launcher_registry.contains(self.launcher_name)
        )

    async def test_start_launcher(self) -> None:
        self.test_add_launcher()
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name
            )
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            self.launcher_registry.state_machine.stop(
                self.launcher_name
            ),
        )

    async def test_creates_tray_file(self) -> None:
        self.test_add_launcher()
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                "phile.configuration",
            )
        )
        configuration: phile.configuration.Entries = (
            self.capability_registry[phile.configuration.Entries]
        )
        # Monitor tray directory before starting launcher.
        tray_directory = (
            configuration.state_directory_path
            / configuration.tray_directory
        )
        tray_directory.mkdir(exist_ok=True)
        watchdog_view = await self.schedule_watchdog_observer(
            tray_directory
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name
            )
        )
        # Show a trigger and a corresponding file should be created.
        await self.assert_watchdog_emits(
            source_view=watchdog_view,
            expected_event=watchdog.events.FileModifiedEvent(
                str(
                    tray_directory
                    / (
                        "90-phile-tray-datetime"
                        + configuration.tray_suffix
                    )
                )
            ),
        )


class TestAddTrayPsutil(
    UsesObserver,
    UsesLauncherRegistry,
    PreparesConfiguration,
    unittest.IsolatedAsyncioTestCase,
):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.launcher_name: str

    def setUp(self) -> None:
        super().setUp()
        self.launcher_name = "phile.tray.psutil"

    def test_add_launcher(self) -> None:
        phile.launcher.defaults.add_configuration(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_tray(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_tray_watchdog(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_watchdog_asyncio_observer(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_tray_psutil(
            launcher_registry=self.launcher_registry
        )
        self.assertTrue(
            self.launcher_registry.contains(self.launcher_name)
        )

    async def test_start_launcher(self) -> None:
        self.test_add_launcher()
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name
            )
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            self.launcher_registry.state_machine.stop(
                self.launcher_name
            ),
        )

    async def test_creates_tray_file(self) -> None:
        self.test_add_launcher()
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                "phile.configuration",
            )
        )
        configuration: phile.configuration.Entries = (
            self.capability_registry[phile.configuration.Entries]
        )
        # Monitor tray directory before starting launcher.
        tray_directory = (
            configuration.state_directory_path
            / configuration.tray_directory
        )
        tray_directory.mkdir(exist_ok=True)
        watchdog_view = await self.schedule_watchdog_observer(
            tray_directory
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name
            )
        )
        # Show a trigger and a corresponding file should be created.
        await self.assert_watchdog_emits(
            source_view=watchdog_view,
            expected_event=watchdog.events.FileModifiedEvent(
                str(
                    tray_directory
                    / (
                        "70-phile-tray-psutil"
                        + configuration.tray_suffix
                    )
                )
            ),
        )


class TestAddTrayText(
    UsesLauncherRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.launcher_name: str

    def setUp(self) -> None:
        super().setUp()
        self.launcher_name = "phile.tray.text"

    def test_add_launcher(self) -> None:
        phile.launcher.defaults.add_tray_text(
            launcher_registry=self.launcher_registry
        )
        self.assertTrue(
            self.launcher_registry.contains(self.launcher_name)
        )

    async def test_start_launcher(self) -> None:
        self.test_add_launcher()
        phile.launcher.defaults.add_tray(
            launcher_registry=self.launcher_registry
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name
            )
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            self.launcher_registry.state_machine.stop(
                self.launcher_name
            ),
        )

    async def test_provides_tray_text_icons(self) -> None:
        await self.test_start_launcher()
        capability_type = phile.tray.TextIcons
        self.assertIsInstance(
            self.capability_registry.get(capability_type),
            capability_type,
        )


class TestAddTrayNotify(
    PreparesConfiguration,
    UsesLauncherRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.launcher_name: str

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.launcher_name = "phile.tray.notify"

    def test_add_launcher(self) -> None:
        phile.launcher.defaults.add_tray_notify(
            launcher_registry=self.launcher_registry
        )
        self.assertTrue(
            self.launcher_registry.contains(self.launcher_name)
        )

    async def test_start_launcher(self) -> None:
        self.test_add_launcher()
        phile.launcher.defaults.add_configuration(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_notify(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_tray(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_tray_watchdog(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_watchdog_asyncio_observer(
            launcher_registry=self.launcher_registry
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name
            )
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            self.launcher_registry.state_machine.stop(
                self.launcher_name
            ),
        )


class TestAddTrayTmux(
    UsesRunningTmuxServer,
    UsesLauncherRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    def setUp(self) -> None:
        super().setUp()
        self.launcher_name = "phile.tray.tmux"

    def test_add_launcher(self) -> None:
        phile.launcher.defaults.add_tray_tmux(
            launcher_registry=self.launcher_registry
        )
        self.assertTrue(
            self.launcher_registry.contains(self.launcher_name)
        )

    async def test_start_launcher(self) -> None:
        self.test_add_launcher()
        phile.launcher.defaults.add_tray(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_tray_text(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_tmux(
            launcher_registry=self.launcher_registry
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.state_machine.start(
                self.launcher_name
            )
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            self.launcher_registry.state_machine.stop(
                self.launcher_name
            ),
        )


class TestAddTriggerWatchdog(
    UsesObserver,
    UsesLauncherRegistry,
    PreparesConfiguration,
    unittest.IsolatedAsyncioTestCase,
):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        self.launcher_name: str

    def setUp(self) -> None:
        super().setUp()
        self.launcher_name = "phile.trigger.watchdog"

    def test_add_launcher(self) -> None:
        phile.launcher.defaults.add_configuration(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_watchdog_asyncio_observer(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_trigger(
            launcher_registry=self.launcher_registry
        )
        phile.launcher.defaults.add_trigger_watchdog(
            launcher_registry=self.launcher_registry
        )
        self.assertTrue(
            self.launcher_registry.contains(self.launcher_name)
        )

    async def test_start_launcher(self) -> None:
        self.test_add_launcher()
        await phile.asyncio.wait_for(
            self.launcher_registry.start(self.launcher_name)
        )
        self.addAsyncCleanup(
            phile.asyncio.wait_for,
            self.launcher_registry.state_machine.stop(
                self.launcher_name
            ),
        )

    async def test_showing_trigger_creates_file(self) -> None:
        self.test_add_launcher()
        await phile.asyncio.wait_for(
            self.launcher_registry.start("phile.configuration")
        )
        await phile.asyncio.wait_for(
            self.launcher_registry.start("phile.trigger")
        )
        # Get objects created by other launcher.
        configuration: phile.configuration.Entries = (
            self.capability_registry[phile.configuration.Entries]
        )
        trigger_registry: phile.trigger.Registry = (
            self.capability_registry[phile.trigger.Registry]
        )
        trigger_directory = (
            configuration.state_directory_path
            / configuration.trigger_directory
        )
        trigger_directory.mkdir()
        trigger_name = "something"
        # Monitor trigger directory before showing trigger.
        await phile.asyncio.wait_for(
            self.launcher_registry.start(self.launcher_name)
        )
        async with await self.schedule_watchdog_observer(
            trigger_directory
        ) as observer_view:
            # Show a trigger and a corresponding file should be created.
            trigger_registry.bind(trigger_name, lambda: None)
            trigger_registry.show(trigger_name)
            expected_event = watchdog.events.FileCreatedEvent(
                str(
                    trigger_directory
                    / (trigger_name + configuration.trigger_suffix)
                )
            )
            await self.assert_watchdog_emits(
                observer_view, expected_event
            )


class TestAdd(
    UsesLauncherRegistry,
    unittest.IsolatedAsyncioTestCase,
):
    def test_add_launchers(self) -> None:
        phile.launcher.defaults.add(
            launcher_registry=self.launcher_registry
        )
        self.assertEqual(
            set(self.launcher_registry.database.remover.keys()),
            {
                "keyring",
                "phile.configuration",
                "phile.hotkey.gui",
                "phile.hotkey.pynput",
                "phile.hotkey.pyside2",
                "phile.launcher.cmd",
                "phile.log.file",
                "phile.log.stderr",
                "phile.notify",
                "phile.notify.pyside2",
                "phile.notify.watchdog",
                "phile.tmux.control_mode",
                "phile.tray",
                "phile.tray.datetime",
                "phile.tray.imapclient",
                "phile.tray.notify",
                "phile.tray.psutil",
                "phile.tray.pyside2.window",
                "phile.tray.text",
                "phile.tray.tmux",
                "phile.tray.watchdog",
                "phile.trigger",
                "phile.trigger.launcher",
                "phile.trigger.watchdog",
                "phile_shutdown.target",
                "pyside2",
                "watchdog.asyncio.observer",
            },
        )
