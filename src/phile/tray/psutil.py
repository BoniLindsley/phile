#!/usr/bin/env python3

# Standard library.
import asyncio
import collections.abc
import dataclasses
import datetime
import typing

# External dependencies.
import psutil
from psutil import (
    _common as psutil_common,  # pylint: disable=protected-access
)

# Internal packages.
import phile.tray
import phile.tray.watchdog

default_refresh_interval = datetime.timedelta(seconds=5)


class VirtualMemory(typing.NamedTuple):
    """
    Fake return type of :func:`psutil.virtual_memory`
    for type hints only.
    """

    total: int
    available: int
    percent: float
    used: int
    free: int


@dataclasses.dataclass
class Snapshot:
    cpu_percentage: float
    datetime: datetime.datetime
    network_io_counters: psutil_common.snetio
    sensors_battery: typing.Optional[psutil_common.sbattery]
    virtual_memory: VirtualMemory

    @classmethod
    def create(cls) -> "Snapshot":
        return cls(
            cpu_percentage=psutil.cpu_percent(),
            datetime=datetime.datetime.now(),
            network_io_counters=psutil.net_io_counters(),
            sensors_battery=psutil.sensors_battery(),
            virtual_memory=psutil.virtual_memory(),
        )

    def to_string(self, previous_snapshot: "Snapshot") -> str:
        text_icon = ""
        text_icon += self.sensors_battery_to_string()
        text_icon += self.cpu_percent_to_string()
        text_icon += self.virtual_memory_to_string()
        text_icon += self.network_io_counters_to_string(
            previous_snapshot
        )
        return text_icon

    def cpu_percent_to_string(self) -> str:
        return " C{self.cpu_percentage:02.0f}".format(self=self)

    def network_io_counters_to_string(
        self, previous_snapshot: "Snapshot"
    ) -> str:
        interval = self.datetime - previous_snapshot.datetime
        counters = self.network_io_counters
        previous_counters = previous_snapshot.network_io_counters
        sent_diff = counters.bytes_sent - previous_counters.bytes_sent
        recv_diff = counters.bytes_recv - previous_counters.bytes_recv
        try:
            sent_rate = sent_diff / interval.total_seconds()
            recv_rate = recv_diff / interval.total_seconds()
            return " W:{recv_kBps:->4.0f}/{sent_kBps:->4.0f}".format(
                recv_kBps=recv_rate / 1000,
                sent_kBps=sent_rate / 1000,
            )
        except ZeroDivisionError:
            return " W:---?/---?"

    def sensors_battery_to_string(self) -> str:
        battery_state = self.sensors_battery
        percentage_text = "-?"
        remaining_text = ""
        if battery_state is not None:
            percentage_text = "{battery_state.percent:02.0f}".format(
                battery_state=battery_state,
            )
            if battery_state.secsleft >= 0:
                timedelta = datetime.timedelta
                time_remaining = timedelta(
                    seconds=battery_state.secsleft
                )
                hour, trailing = divmod(
                    time_remaining, timedelta(hours=1)
                )
                minute = trailing // timedelta(minutes=1)
                remaining_text = "={hour}h{minute:02}".format(
                    hour=hour,
                    minute=minute,
                )
        return " B:{percentage_text}%{remaining_text}".format(
            percentage_text=percentage_text,
            remaining_text=remaining_text,
        )

    def virtual_memory_to_string(self) -> str:
        return " M{memory_available_gB:.0f}".format(
            memory_available_gB=self.virtual_memory.available
            // 1000 ** 3,
        )


class NotEnoughData(Exception):
    pass


class History:
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        # TODO[mypy issue 4001]: Remove type ignore.
        super().__init__(*args, **kwargs)  # type: ignore[call-arg]
        self.snapshots: list[Snapshot] = []

    def create_snapshot(self) -> None:
        self.snapshots.append(Snapshot.create())

    def last_snapshot_to_string(self) -> str:
        snapshots = self.snapshots
        if len(snapshots) <= 1:
            raise NotEnoughData()
        last_snapshot = snapshots[-1]
        return last_snapshot.to_string(snapshots[-2])

    def to_strings(self) -> collections.abc.Iterator[str]:
        self.create_snapshot()
        yield " psutil..."
        while True:
            self.create_snapshot()
            yield self.last_snapshot_to_string()


async def run(
    *,
    refresh_interval: datetime.timedelta = default_refresh_interval,
    tray_name: str = "70-phile-tray-psutil",
    tray_target: phile.tray.watchdog.Target,
) -> None:
    tray_entry = phile.tray.Entry(name=tray_name)
    tray_target.set(entry=tray_entry)
    try:
        snapshot_strings = History().to_strings().__iter__()

        def update_file() -> None:
            tray_entry.text_icon = snapshot_strings.__next__()
            tray_target.set(entry=tray_entry)

        loop = asyncio.get_running_loop()
        wait_seconds = refresh_interval.total_seconds()
        while True:
            await loop.run_in_executor(None, update_file)
            await asyncio.sleep(wait_seconds)
    finally:
        tray_target.pop(name=tray_name)
