# Standard libraries.
import collections
import collections.abc
import os
import signal
import socket as _socket
import typing as _typing

# Internal modules.
from . import _common

from ._common import (
    AIX as AIX,
    BSD as BSD,
    FREEBSD as FREEBSD,
    LINUX as LINUX,
    MACOS as MACOS,
    NETBSD as NETBSD,
    OPENBSD as OPENBSD,
    OSX as OSX,
    POSIX as POSIX,
    SUNOS as SUNOS,
    WINDOWS as WINDOWS,
)
from ._common import (
    CONN_CLOSE as CONN_CLOSE,
    CONN_CLOSE_WAIT as CONN_CLOSE_WAIT,
    CONN_CLOSING as CONN_CLOSING,
    CONN_ESTABLISHED as CONN_ESTABLISHED,
    CONN_FIN_WAIT1 as CONN_FIN_WAIT1,
    CONN_FIN_WAIT2 as CONN_FIN_WAIT2,
    CONN_LAST_ACK as CONN_LAST_ACK,
    CONN_LISTEN as CONN_LISTEN,
    CONN_NONE as CONN_NONE,
    CONN_SYN_RECV as CONN_SYN_RECV,
    CONN_SYN_SENT as CONN_SYN_SENT,
    CONN_TIME_WAIT as CONN_TIME_WAIT,
)
from ._common import (
    NIC_DUPLEX_FULL as NIC_DUPLEX_FULL,
    NIC_DUPLEX_HALF as NIC_DUPLEX_HALF,
    NIC_DUPLEX_UNKNOWN as NIC_DUPLEX_UNKNOWN,
)
from ._common import (
    STATUS_DEAD as STATUS_DEAD,
    STATUS_DISK_SLEEP as STATUS_DISK_SLEEP,
    STATUS_IDLE as STATUS_IDLE,
    STATUS_LOCKED as STATUS_LOCKED,
    STATUS_PARKED as STATUS_PARKED,
    STATUS_RUNNING as STATUS_RUNNING,
    STATUS_SLEEPING as STATUS_SLEEPING,
    STATUS_STOPPED as STATUS_STOPPED,
    # STATUS_SUSPENDED as STATUS_SUSPENDED,  # Missing from source.
    STATUS_TRACING_STOP as STATUS_TRACING_STOP,
    STATUS_WAITING as STATUS_WAITING,
    # STATUS_WAKE_KILL as STATUS_WAKE_KILL,  # Missing from source.
    STATUS_WAKING as STATUS_WAKING,
    STATUS_ZOMBIE as STATUS_ZOMBIE,
)
from ._common import (
    AccessDenied as AccessDenied,
    Error as Error,
    NoSuchProcess as NoSuchProcess,
    TimeoutExpired as TimeoutExpired,
    ZombieProcess as ZombieProcess,
)
from ._common import (
    POWER_TIME_UNKNOWN as POWER_TIME_UNKNOWN,
    POWER_TIME_UNLIMITED as POWER_TIME_UNLIMITED,
)

PROCFS_PATH: str
AF_LINK: _socket.AddressFamily
version_info: tuple[int, int, int]


class Process:

    def __init__(self, pid: _typing.Optional[int] = ...) -> None:
        ...

    def __eq__(self, other: object) -> bool:
        ...

    def __ne__(self, other: object) -> bool:
        ...

    def __hash__(self) -> int:
        ...

    @property
    def pid(self) -> int:
        ...

    def oneshot(self) -> None:
        ...

    def as_dict(
        self,
        attrs: _typing.Optional[collections.abc.Iterator[str]] = ...,
        ad_value: _typing.Optional[_typing.Any] = ...,
    ) -> dict[str, _typing.Any]:
        ...

    def parent(self) -> _typing.Optional['Process']:
        ...

    def parents(self) -> list['Process']:
        ...

    def is_running(self) -> bool:
        ...

    def ppid(self) -> int:
        ...

    def name(self) -> str:
        ...

    def exe(self) -> str:
        ...

    def cmdline(self) -> str:
        ...

    def status(self) -> str:
        ...

    def username(self) -> str:
        ...

    def create_time(self) -> float:
        ...

    def cwd(self) -> str:
        ...

    def nice(self, value: _typing.Optional[int] = ...) -> int:
        ...

    def num_ctx_switches(self) -> int:
        ...

    def num_threads(self) -> int:
        ...

    def children(self, recursive: bool = ...) -> list['Process']:
        ...

    def cpu_percent(
        self,
        interval: _typing.Optional[float] = ...,
    ) -> float:
        ...

    def cpu_times(self) -> _common.pcputimes:
        ...

    def memory_info(self) -> tuple[int, ...]:
        ...

    def memory_full_info(self) -> tuple[int, ...]:
        ...

    def memory_percent(self, memtype: str = ...) -> float:
        ...

    def open_files(self) -> list[_common.popenfile]:
        ...

    def connections(self, kind: str = ...) -> list[_common.pconn]:
        ...

    def send_signal(self, sig: signal.Signals) -> None:
        ...

    def suspend(self) -> None:
        ...

    def resume(self) -> None:
        ...

    def terminate(self) -> None:
        ...

    def kill(self) -> None:
        ...

    def wait(self, timeout: _typing.Optional[float] = ...) -> int:
        ...


class Popen(Process):

    def __init__(
        self, *args: _typing.Any, **kwargs: _typing.Any
    ) -> None:
        ...

    def __dir__(self) -> list[str]:
        ...

    def __enter__(self) -> 'Popen':
        ...

    def __exit__(self, *args: _typing.Any,
                 **kwargs: _typing.Any) -> _typing.Optional[bool]:
        ...

    def __getattribute__(self, name: str) -> _typing.Any:
        ...

    def wait(self, timeout: _typing.Optional[float] = ...) -> int:
        ...


def pids() -> list[int]:
    ...


def pid_exists(pid: int) -> bool:
    ...


def process_iter(
    attrs: _typing.Optional[collections.abc.Iterator[str]] = ...,
    ad_value: _typing.Optional[_typing.Any] = ...,
) -> collections.abc.Iterator[Process]:
    ...


def wait_procs(
    procs: collections.abc.Iterable[Process],
    timeout: _typing.Optional[float] = ...,
    callback: (
        _typing.Optional[collections.abc.Callable[[Process],
                                                  _typing.Any]]
    ) = ...
) -> tuple[list[Process], list[Process]]:
    ...


def cpu_count(logical: bool = ...) -> int:
    ...


def cpu_times(percpu: bool = ...) -> _common.pcputimes:
    ...


@_typing.overload
def cpu_percent(
    interval: _typing.Optional[float] = ...,
    percpu: _typing.Literal[False] = ...,
) -> float:
    ...


@_typing.overload
def cpu_percent(*, percpu: _typing.Literal[True]) -> list[float]:
    ...


@_typing.overload
def cpu_percent(
    interval: _typing.Optional[float],
    percpu: _typing.Literal[True],
) -> list[float]:
    ...


@_typing.overload
def cpu_percent(
    interval: _typing.Optional[float],
    percpu: bool,
) -> _typing.Union[float, list[float]]:
    ...


@_typing.overload
def cpu_times_percent(
    interval: _typing.Optional[float] = ...,
    percpu: _typing.Literal[False] = ...,
) -> float:
    ...


@_typing.overload
def cpu_times_percent(*, percpu: _typing.Literal[True]) -> list[float]:
    ...


@_typing.overload
def cpu_times_percent(
    interval: _typing.Optional[float],
    percpu: _typing.Literal[True],
) -> list[float]:
    ...


@_typing.overload
def cpu_times_percent(
    interval: _typing.Optional[float],
    percpu: bool,
) -> _typing.Union[float, list[float]]:
    ...


def cpu_stats() -> _common.scpustats:
    ...


def virtual_memory() -> _typing.Any:
    ...


def swap_memory() -> _common.sswap:
    ...


def disk_usage(path: str) -> _common.sdiskusage:
    ...


def disk_partitions(all: bool = ...) -> list[_common.sdiskpart]:
    ...


@_typing.overload
def disk_io_counters(
    perdisk: _typing.Literal[False] = ...,
    nowrap: bool = ...,
) -> _common.sdiskio:
    ...


@_typing.overload
def disk_io_counters(
    perdisk: _typing.Literal[True],
    nowrap: bool = ...,
) -> _typing.Union[None, dict[str, _common.sdiskio]]:
    ...


@_typing.overload
def disk_io_counters(
    perdisk: bool,
    nowrap: bool = ...,
) -> _typing.Union[None, _common.sdiskio, dict[str, _common.sdiskio]]:
    ...


@_typing.overload
def net_io_counters(
    pernic: _typing.Literal[False] = ...,
    nowrap: bool = ...,
) -> _common.snetio:
    ...


@_typing.overload
def net_io_counters(
    pernic: _typing.Literal[True],
    nowrap: bool = ...,
) -> _typing.Union[None, dict[str, _common.snetio]]:
    ...


@_typing.overload
def net_io_counters(
    pernic: bool,
    nowrap: bool = ...,
) -> _typing.Union[None, _common.snetio, dict[str, _common.snetio]]:
    ...


def net_connections(kind: str = ...) -> _common.sconn:
    ...


def net_if_addrs() -> dict[str, list[_common.snicaddr]]:
    ...


def net_if_stats() -> dict[str, _common.snicstats]:
    ...


def sensors_temperatures(
    fahrenheit: bool = ...,
) -> dict[str, list[_common.shwtemp]]:
    ...


def sensors_fans() -> dict[str, list[_common.sfan]]:
    ...


def sensors_battery() -> _typing.Optional[_common.sbattery]:
    ...


def boot_time() -> float:
    ...


def users() -> list[_common.suser]:
    ...
