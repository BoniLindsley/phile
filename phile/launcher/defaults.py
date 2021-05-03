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


def add_keyring(
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
    launcher_registry.database.add(
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


def add_configuration(
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
            with capability_registry.provide(phile.Configuration()):
                ready.set_result(True)
                await create_future()

        running_task = loop.create_task(run())
        await ready
        return running_task

    launcher_registry = capability_registry[phile.launcher.Registry]
    launcher_registry.database.add(
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


def add_tmux(capability_registry: phile.capability.Registry) -> None:

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
    launcher_registry.database.add(
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


def add_tray_battery(
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
    launcher_registry.database.add(
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


def add_tray_cpu(capability_registry: phile.capability.Registry) -> None:

    async def phile_tray_publishers_cpu(
        capability_registry: phile.capability.Registry,
    ) -> None:
        import phile.tray.publishers.cpu
        await phile.tray.publishers.cpu.run(
            capabilities=capability_registry
        )

    launcher_registry = capability_registry[phile.launcher.Registry]
    launcher_registry.database.add(
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


def add_tray_datetime(
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
    launcher_registry.database.add(
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


def add_tray_imap(
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
    launcher_registry.database.add(
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


def add_tray_memory(
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
    launcher_registry.database.add(
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


def add_tray_network(
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
    launcher_registry.database.add(
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


def add_tray_notify(
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
    launcher_registry.database.add(
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


def add_tray_tmux(
    capability_registry: phile.capability.Registry,
) -> None:

    async def phile_tray_tmux(
        capability_registry: phile.capability.Registry,
    ) -> None:
        import phile.tray.tmux
        await phile.tray.tmux.run(capabilities=capability_registry)

    launcher_registry = capability_registry[phile.launcher.Registry]
    launcher_registry.database.add(
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


def add_trigger(capability_registry: phile.capability.Registry) -> None:

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
    launcher_registry.database.add(
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


def add_trigger_launcher(
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
    launcher_registry.database.add(
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


def add_trigger_watchdog(
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
    launcher_registry.database.add(
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


def add_pyside2(
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
            provide = capability_registry.provide
            qt_app = PySide2.QtWidgets.QApplication.instance()
            with provide(qt_app,
                         PySide2.QtCore.QCoreApplication), provide(
                             qt_app, PySide2.QtGui.QGuiApplication
                         ), provide(qt_app):
                ready.set_result(True)
                try:
                    await create_future()
                finally:
                    launcher_registry = (
                        capability_registry[phile.launcher.Registry]
                    )
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
    launcher_registry.database.add(
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


def add_watchdog_observer(
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
    launcher_registry.database.add(
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


def add(capability_registry: phile.capability.Registry) -> None:
    add_keyring(capability_registry=capability_registry)
    add_configuration(capability_registry=capability_registry)
    add_tmux(capability_registry=capability_registry)
    add_tray_battery(capability_registry=capability_registry)
    add_tray_cpu(capability_registry=capability_registry)
    add_tray_datetime(capability_registry=capability_registry)
    #add_tray_imap(capability_registry=capability_registry)
    add_tray_memory(capability_registry=capability_registry)
    add_tray_network(capability_registry=capability_registry)
    add_tray_notify(capability_registry=capability_registry)
    add_tray_tmux(capability_registry=capability_registry)
    add_trigger(capability_registry=capability_registry)
    add_trigger_launcher(capability_registry=capability_registry)
    add_trigger_watchdog(capability_registry=capability_registry)
    add_pyside2(capability_registry=capability_registry)
    add_watchdog_observer(capability_registry=capability_registry)
