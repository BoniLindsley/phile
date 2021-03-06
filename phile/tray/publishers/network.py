#!/usr/bin/env python3

# Standard library.
import asyncio
import contextlib
import datetime
import sys
import typing

# External dependencies.
import psutil  # type: ignore[import]

# Internal packages.
import phile
import phile.tray
from . import update

NetworkStatus: type[psutil._common.snetio] = psutil._common.snetio

default_network_status = NetworkStatus(
    bytes_sent=0,
    bytes_recv=0,
    packets_sent=0,
    packets_recv=0,
    errin=0,
    errout=0,
    dropin=0,
    dropout=0,
)


class NetworkFile(phile.tray.File):

    def __init__(
        self,
        *args: typing.Any,
        updated_at: datetime.datetime,
        network_status: psutil._common.snetio = default_network_status,
        **kwargs: typing.Any
    ) -> None:
        super().__init__(*args, **kwargs)
        self.network_status = network_status
        self.updated_at = updated_at

    def update(
        self, at: datetime.datetime,
        network_status: psutil._common.snetio
    ) -> None:
        interval = at - self.updated_at
        previous_status = self.network_status
        sent_diff = (
            network_status.bytes_sent - previous_status.bytes_sent
        )
        recv_diff = (
            network_status.bytes_recv - previous_status.bytes_recv
        )
        sent_rate = sent_diff / interval.total_seconds()
        recv_rate = recv_diff / interval.total_seconds()
        sent_kBps = sent_rate / 1000
        recv_kBps = recv_rate / 1000
        self.text_icon = f' W:{recv_kBps:_>4.0f}/{sent_kBps:_>4.0f}'
        self.network_status = network_status
        self.updated_at = at


default_refresh_interval = datetime.timedelta(seconds=5)


class TrayFilesUpdater(update.SelfTarget):

    def __init__(
        self,
        *args: typing.Any,
        capabilities: phile.Capabilities,
        prefix: str = '70-phile-tray-network-',
        refresh_interval: datetime.timedelta = default_refresh_interval,
        **kwargs: typing.Any,
    ):
        # See: https://github.com/python/mypy/issues/4001
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        configuration = capabilities[phile.Configuration]
        self.refresh_interval = refresh_interval
        now = datetime.datetime.now()
        network_status = psutil.net_io_counters()
        self.file = NetworkFile(
            path=configuration.tray_directory /
            (prefix + 'rate' + configuration.tray_suffix),
            updated_at=now,
            network_status=network_status
        )

    def on_exit(self) -> None:
        self.file.path.unlink(missing_ok=True)

    def __call__(self) -> datetime.timedelta:
        now = datetime.datetime.now()
        network_status = psutil.net_io_counters()
        file = self.file
        file.update(at=now, network_status=network_status)
        file.save()
        return self.refresh_interval


async def run(
    capabilities: phile.Capabilities
) -> int:  # pragma: no cover
    target = TrayFilesUpdater(capabilities=capabilities)
    await update.sleep_loop(target)
    return 0


async def async_main(argv: typing.List[str]) -> int:  # pragma: no cover
    capabilities = phile.Capabilities()
    capabilities.set(phile.Configuration())
    return await run(capabilities=capabilities)


def main(argv: typing.List[str] = sys.argv) -> int:  # pragma: no cover
    with contextlib.suppress(KeyboardInterrupt):
        return asyncio.run(async_main(argv))
    return 1


if __name__ == '__main__':  # pragma: no cover
    sys.exit(main())
