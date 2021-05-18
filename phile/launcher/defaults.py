#!/usr/bin/env python3
# pylint: disable=import-outside-toplevel
# pylint: disable=redefined-outer-name

# Function scope imports are used
# to ensure imports occur only when necessary.
# For example, the function may determine a launcher to be unusable
# in a certain platform, and not import it.
# Standard library.
import asyncio
import functools
import typing

# Internal packages.
import phile.capability


async def add_configuration(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_configuration(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile
            import phile.configuration
            with capability_registry.provide(
                phile.Configuration()
            ), capability_registry.provide(
                await asyncio.to_thread(phile.configuration.load)
            ):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.configuration',
        phile.launcher.Descriptor(
            exec_start=[
                functools.partial(
                    phile_configuration,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_hotkey_gui(
    capability_registry: phile.capability.Registry,
) -> None:
    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.hotkey.gui',
        phile.launcher.Descriptor(
            after={'phile.hotkey.pynput', 'phile.hotkey.pyside2'},
            binds_to={'phile.hotkey.pynput', 'phile.hotkey.pyside2'},
            exec_start=[asyncio.get_running_loop().create_future],
        )
    )


async def add_hotkey_pynput(
    capability_registry: phile.capability.Registry,
) -> None:

    async def run_pynput() -> None:
        import phile.configuration
        import phile.hotkey.pynput
        import phile.trigger
        await phile.hotkey.pynput.run(
            configuration=(
                capability_registry[phile.configuration.Entries]
            ),
            trigger_registry=(
                capability_registry[phile.trigger.Registry]
            ),
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.hotkey.pynput',
        phile.launcher.Descriptor(
            after={
                'phile.configuration',
                'phile.launcher',
                'phile.trigger',
                'phile.trigger.launcher',
            },
            binds_to={
                'phile.configuration',
                'phile.launcher',
                'phile.trigger',
                'phile.trigger.launcher',
            },
            exec_start=[run_pynput],
        )
    )


async def add_hotkey_pyside2(
    capability_registry: phile.capability.Registry,
) -> None:

    async def run() -> None:
        import phile.configuration
        import phile.PySide2.QtCore
        import phile.hotkey.pyside2
        import phile.trigger
        configurations = (
            capability_registry[phile.configuration.Entries]
        )
        pyside2_executor = (
            capability_registry[phile.PySide2.QtCore.Executor]
        )
        trigger_registry = (capability_registry[phile.trigger.Registry])
        await phile.hotkey.pyside2.run(
            configurations=configurations,
            pyside2_executor=pyside2_executor,
            trigger_registry=trigger_registry,
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.hotkey.pyside2',
        phile.launcher.Descriptor(
            after={
                'phile.configuration',
                'phile.trigger',
                'phile.trigger.launcher',
                'pyside2',
            },
            binds_to={
                'phile.configuration',
                'phile.trigger',
                'phile.trigger.launcher',
                'pyside2',
            },
            exec_start=[run],
        )
    )


async def add_launcher_cmd(
    capability_registry: phile.capability.Registry,
) -> None:

    async def run() -> None:
        import phile.cmd
        import phile.launcher.cmd

        await phile.cmd.async_cmdloop_threaded_stdin(
            phile.launcher.cmd.Cmd(
                launcher_registry=launcher_registry,
            )
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.launcher.cmd',
        phile.launcher.Descriptor(
            after={'phile.launcher'},
            binds_to={'phile.launcher'},
            exec_start=[run],
        )
    )


async def add_log_file(
    capability_registry: phile.capability.Registry,
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import logging
            import phile.configuration
            configuration = (
                capability_registry[phile.configuration.Entries]
            )
            log_level = configuration.log_file_level
            log_path = (
                configuration.state_directory_path /
                configuration.log_file_path
            )
            handler = logging.FileHandler(str(log_path))
            try:
                formatter = logging.Formatter(
                    '[%(asctime)s] [%(levelno)03d] %(name)s:'
                    ' %(message)s',
                )
                handler.setFormatter(formatter)
                handler.setLevel(log_level)
                package_logger = logging.getLogger('phile')
                package_logger.addHandler(handler)
                package_logger.setLevel(1)
                try:
                    ready.set_result(True)
                    await create_future()
                finally:
                    package_logger.removeHandler(handler)
            finally:
                handler.close()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.log.file',
        phile.launcher.Descriptor(
            after={'phile.configuration'},
            binds_to={'phile.configuration'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_log_stderr(
    capability_registry: phile.capability.Registry,
) -> None:

    async def start() -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import logging
            import sys
            import phile.configuration
            configuration = (
                capability_registry[phile.configuration.Entries]
            )
            log_level = configuration.log_stderr_level
            handler = logging.StreamHandler(sys.stderr)
            try:
                formatter = logging.Formatter(
                    '[%(asctime)s] [%(levelno)03d] %(name)s:'
                    ' %(message)s',
                )
                handler.setFormatter(formatter)
                handler.setLevel(log_level)
                package_logger = logging.getLogger('phile')
                package_logger.addHandler(handler)
                package_logger.setLevel(1)
                try:
                    ready.set_result(True)
                    await create_future()
                finally:
                    package_logger.removeHandler(handler)
            finally:
                handler.close()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.log.stderr',
        phile.launcher.Descriptor(
            after={'phile.configuration'},
            binds_to={'phile.configuration'},
            exec_start=[start],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_keyring(
    capability_registry: phile.capability.Registry,
) -> None:

    async def keyring_backend(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import keyring
            default_keyring = await asyncio.to_thread(
                keyring.get_keyring
            )
            with capability_registry.provide(
                default_keyring, keyring.backend.KeyringBackend
            ):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'keyring',
        phile.launcher.Descriptor(
            exec_start=[
                functools.partial(
                    keyring_backend,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_tmux(
    capability_registry: phile.capability.Registry
) -> None:

    async def phile_tmux_control_mode(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.tmux.control_mode
            async with phile.tmux.control_mode.open(
                control_mode_arguments=(
                    phile.tmux.control_mode.Arguments()
                )
            ) as control_mode:
                with capability_registry.provide(
                    control_mode, phile.tmux.control_mode.Client
                ):
                    async with phile.asyncio.open_task(
                        control_mode.run()
                    ):
                        ready.set_result(True)
                        await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tmux.control_mode',
        phile.launcher.Descriptor(
            after={'phile.launcher'},
            binds_to={'phile.launcher'},
            exec_start=[
                functools.partial(
                    phile_tmux_control_mode,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_tray_battery(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_tray_publishers_battery(
        capability_registry: phile.capability.Registry,
    ) -> None:
        import phile.tray.publishers.battery
        await phile.tray.publishers.battery.run(
            capabilities=capability_registry
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray.publisher.battery',
        phile.launcher.Descriptor(
            after={'phile.configuration'},
            binds_to={'phile.configuration'},
            exec_start=[
                functools.partial(
                    phile_tray_publishers_battery,
                    capability_registry=capability_registry,
                ),
            ],
        )
    )


async def add_tray_cpu(
    capability_registry: phile.capability.Registry
) -> None:

    async def phile_tray_publishers_cpu(
        capability_registry: phile.capability.Registry,
    ) -> None:
        import phile.tray.publishers.cpu
        await phile.tray.publishers.cpu.run(
            capabilities=capability_registry
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray.publisher.cpu',
        phile.launcher.Descriptor(
            after={'phile.configuration'},
            binds_to={'phile.configuration'},
            exec_start=[
                functools.partial(
                    phile_tray_publishers_cpu,
                    capability_registry=capability_registry,
                ),
            ],
        )
    )


async def add_tray_datetime(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_tray_publishers_datetime(
        capability_registry: phile.capability.Registry,
    ) -> None:
        import phile.tray.publishers.datetime
        await phile.tray.publishers.datetime.run(
            capabilities=capability_registry
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray.publisher.datetime',
        phile.launcher.Descriptor(
            after={'phile.configuration'},
            binds_to={'phile.configuration'},
            exec_start=[
                functools.partial(
                    phile_tray_publishers_datetime,
                    capability_registry=capability_registry,
                ),
            ],
        )
    )


async def add_tray_imap(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_tray_publishers_imap_idle(
        capability_registry: phile.capability.Registry,
    ) -> None:
        import phile.tray.publishers.imap_idle
        await phile.tray.publishers.imap_idle.run(
            capabilities=capability_registry
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray.publisher.imap_idle',
        phile.launcher.Descriptor(
            after={'phile.configuration', 'keyring'},
            binds_to={'phile.configuration', 'keyring'},
            exec_start=[
                functools.partial(
                    phile_tray_publishers_imap_idle,
                    capability_registry=capability_registry,
                ),
            ],
        )
    )


async def add_tray_memory(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_tray_publishers_memory(
        capability_registry: phile.capability.Registry,
    ) -> None:
        import phile.tray.publishers.memory
        await phile.tray.publishers.memory.run(
            capabilities=capability_registry
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray.publisher.memory',
        phile.launcher.Descriptor(
            after={'phile.configuration'},
            binds_to={'phile.configuration'},
            exec_start=[
                functools.partial(
                    phile_tray_publishers_memory,
                    capability_registry=capability_registry,
                ),
            ],
        )
    )


async def add_tray_network(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_tray_publishers_network(
        capability_registry: phile.capability.Registry,
    ) -> None:
        import phile.tray.publishers.network
        await phile.tray.publishers.network.run(
            capabilities=capability_registry
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray.publisher.network',
        phile.launcher.Descriptor(
            after={'phile.configuration'},
            binds_to={'phile.configuration'},
            exec_start=[
                functools.partial(
                    phile_tray_publishers_network,
                    capability_registry=capability_registry,
                ),
            ],
        )
    )


async def add_tray_notify(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_tray_publishers_notify_monitor(
        capability_registry: phile.capability.Registry,
    ) -> None:
        import phile.tray.publishers.notify_monitor
        await phile.tray.publishers.notify_monitor.run(
            capabilities=capability_registry
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray.publisher.notify_monitor',
        phile.launcher.Descriptor(
            after={'phile.configuration', 'watchdog.observer'},
            binds_to={'phile.configuration', 'watchdog.observer'},
            exec_start=[
                functools.partial(
                    phile_tray_publishers_notify_monitor,
                    capability_registry=capability_registry,
                ),
            ],
        )
    )


async def add_tray_tmux(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_tray_tmux(
        capability_registry: phile.capability.Registry,
    ) -> None:
        import phile.tray.tmux
        await phile.tray.tmux.run(capabilities=capability_registry)

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.tray.tmux',
        phile.launcher.Descriptor(
            after={
                'phile.configuration',
                'phile.tmux.control_mode',
                'watchdog.observer',
            },
            binds_to={
                'phile.configuration',
                'phile.tmux.control_mode',
                'watchdog.observer',
            },
            exec_start=[
                functools.partial(
                    phile_tray_tmux,
                    capability_registry=capability_registry,
                ),
            ],
        )
    )


async def add_trigger(
    capability_registry: phile.capability.Registry
) -> None:

    async def phile_trigger_registry(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.trigger
            with capability_registry.provide(phile.trigger.Registry()):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.trigger',
        phile.launcher.Descriptor(
            exec_start=[
                functools.partial(
                    phile_trigger_registry,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_trigger_launcher(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_trigger_launcher_producer(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.launcher
            import phile.trigger
            import phile.trigger.launcher
            launcher_registry = (
                capability_registry[phile.launcher.Registry]
            )
            trigger_registry = (
                capability_registry[phile.trigger.Registry]
            )
            async with phile.trigger.launcher.Producer(
                launcher_registry=launcher_registry,
                trigger_registry=trigger_registry,
            ) as producer:
                with capability_registry.provide(producer):
                    ready.set_result(True)
                    await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.trigger.launcher',
        phile.launcher.Descriptor(
            after={'phile.launcher', 'phile.trigger'},
            binds_to={'phile.launcher', 'phile.trigger'},
            exec_start=[
                functools.partial(
                    phile_trigger_launcher_producer,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_trigger_watchdog(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_trigger_watchdog(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import phile.trigger.watchdog
            with phile.trigger.watchdog.View(
                capabilities=capability_registry
            ) as view, capability_registry.provide(view):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'phile.trigger.watchdog',
        phile.launcher.Descriptor(
            after={
                'phile.configuration',
                'phile.trigger',
                'watchdog.observer',
            },
            binds_to={
                'phile.configuration',
                'phile.trigger',
                'watchdog.observer',
            },
            exec_start=[
                functools.partial(
                    phile_trigger_watchdog,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_pyside2(
    capability_registry: phile.capability.Registry,
) -> None:

    async def pyside2(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        loop.stop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import PySide2.QtCore
            import PySide2.QtGui
            import PySide2.QtWidgets
            import phile.PySide2.QtCore
            import phile.launcher
            launcher_registry = (
                capability_registry[phile.launcher.Registry]
            )
            provide = capability_registry.provide
            qt_app = PySide2.QtWidgets.QApplication.instance()
            qt_app.setQuitLockEnabled(False)
            with provide(
                qt_app,
                PySide2.QtCore.QCoreApplication,
            ), provide(
                qt_app,
                PySide2.QtGui.QGuiApplication,
            ), provide(
                qt_app,
            ), phile.PySide2.QtCore.Executor(
            ) as pyside2_executor, provide(
                pyside2_executor,
            ):
                ready.set_result(True)
                try:
                    await create_future()
                finally:
                    launcher_registry.state_machine.stop_soon(
                        'phile.launcher'
                    )
                    phile.PySide2.QtCore.call_soon_threadsafe(
                        qt_app.quit
                    )

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'pyside2',
        phile.launcher.Descriptor(
            after={'phile.launcher'},
            binds_to={'phile.launcher'},
            exec_start=[
                functools.partial(
                    pyside2,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add_watchdog_observer(
    capability_registry: phile.capability.Registry,
) -> None:

    async def watchdog_observer(
        capability_registry: phile.capability.Registry,
    ) -> asyncio.Future[typing.Any]:
        loop = asyncio.get_running_loop()
        create_future = loop.create_future
        ready = create_future()

        async def run() -> None:
            import watchdog.observers
            import phile.trigger.watchdog
            async with phile.watchdog.observers.async_open() as observer:
                with capability_registry.provide(
                    observer,
                    watchdog.observers.api.BaseObserver,
                ):
                    ready.set_result(True)
                    await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    await launcher_registry.database.add(
        'watchdog.observer',
        phile.launcher.Descriptor(
            exec_start=[
                functools.partial(
                    watchdog_observer,
                    capability_registry=capability_registry,
                ),
            ],
            type=phile.launcher.Type.FORKING,
        )
    )


async def add(capability_registry: phile.capability.Registry) -> None:
    await add_configuration(capability_registry=capability_registry)
    await add_hotkey_gui(capability_registry=capability_registry)
    await add_hotkey_pynput(capability_registry=capability_registry)
    await add_hotkey_pyside2(capability_registry=capability_registry)
    await add_log_file(capability_registry=capability_registry)
    await add_log_stderr(capability_registry=capability_registry)
    await add_keyring(capability_registry=capability_registry)
    await add_launcher_cmd(capability_registry=capability_registry)
    await add_pyside2(capability_registry=capability_registry)
    await add_tmux(capability_registry=capability_registry)
    await add_tray_battery(capability_registry=capability_registry)
    await add_tray_cpu(capability_registry=capability_registry)
    await add_tray_datetime(capability_registry=capability_registry)
    await add_tray_imap(capability_registry=capability_registry)
    await add_tray_memory(capability_registry=capability_registry)
    await add_tray_network(capability_registry=capability_registry)
    await add_tray_notify(capability_registry=capability_registry)
    await add_tray_tmux(capability_registry=capability_registry)
    await add_trigger(capability_registry=capability_registry)
    await add_trigger_launcher(capability_registry=capability_registry)
    await add_trigger_watchdog(capability_registry=capability_registry)
    await add_watchdog_observer(capability_registry=capability_registry)
