# Standard libraries.
import enum
import socket
import threading
import typing as _typing

_T = _typing.TypeVar('_T')

# OS constants
AIX: bool
BSD: bool
FREEBSD: bool
LINUX: bool
MACOS: bool
NETBSD: bool
OPENBSD: bool
OSX: bool
POSIX: bool
SUNOS: bool
WINDOWS: bool

# Process status constants
STATUS_DEAD: str
STATUS_DISK_SLEEP: str
STATUS_IDLE: str
STATUS_LOCKED: str
STATUS_PARKED: str
STATUS_RUNNING: str
STATUS_SLEEPING: str
STATUS_STOPPED: str
STATUS_SUSPENDED: str
STATUS_TRACING_STOP: str
STATUS_WAITING: str
STATUS_WAKE_KILL: str
STATUS_WAKING: str
STATUS_ZOMBIE: str

# Connection constants
CONN_CLOSE: str
CONN_CLOSE_WAIT: str
CONN_CLOSING: str
CONN_ESTABLISHED: str
CONN_FIN_WAIT1: str
CONN_FIN_WAIT2: str
CONN_LAST_ACK: str
CONN_LISTEN: str
CONN_NONE: str
CONN_SYN_RECV: str
CONN_SYN_SENT: str
CONN_TIME_WAIT: str


# Net constants
class NicDuplex(enum.IntEnum):
    NIC_DUPLEX_FULL: int = ...
    NIC_DUPLEX_HALF: int = ...
    NIC_DUPLEX_UNKNOWN: int = ...


NIC_DUPLEX_FULL: int
NIC_DUPLEX_HALF: int
NIC_DUPLEX_UNKNOWN: int


# Sensor's battery
class BatteryTime(enum.IntEnum):
    POWER_TIME_UNKNOWN: int = ...
    POWER_TIME_UNLIMITED: int = ...


POWER_TIME_UNKNOWN: int
POWER_TIME_UNLIMITED: int

# Other constants
AF_INET6: _typing.Optional[socket.AddressFamily]
ENCODING: str
ENCODING_ERRS: str


# Named tuples
class sswap(_typing.NamedTuple):
    total: int
    used: int
    free: int
    percent: float
    sin: int
    sout: int


class sdiskusage(_typing.NamedTuple):
    total: int
    used: int
    free: int
    percent: float


class sdiskio(_typing.NamedTuple):
    read_count: int
    write_count: int
    read_bytes: int
    write_bytes: int
    read_time: int
    write_time: int


class sdiskpart(_typing.NamedTuple):
    device: str
    mountpoint: str
    fstype: str
    opts: str
    maxfile: int
    maxpath: int


class snetio(_typing.NamedTuple):
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    errin: int
    errout: int
    dropin: int
    dropout: int


class suser(_typing.NamedTuple):
    name: str
    terminal: _typing.Optional[str]
    host: str
    started: float
    pid: _typing.Optional[int]


class sconn(_typing.NamedTuple):
    fd: int
    family: socket.AddressFamily
    type: socket.SocketKind
    laddr: 'addr'
    raddr: 'addr'
    status: str
    pid: int


class snicaddr(_typing.NamedTuple):
    family: socket.AddressFamily
    address: str
    netmask: _typing.Optional[str]
    broadcast: _typing.Optional[str]
    ptp: _typing.Optional[str]


class snicstats(_typing.NamedTuple):
    isup: bool
    duplex: NicDuplex
    speed: int
    mtu: int


class scpustats(_typing.NamedTuple):
    ctx_switches: int
    interrupts: int
    soft_interrupts: int
    syscalls: int


class scpufreq(_typing.NamedTuple):
    current: int
    min: int
    max: int


class shwtemp(_typing.NamedTuple):
    label: str
    current: float
    high: float
    critical: float


class sbattery(_typing.NamedTuple):
    percent: float
    secsleft: _typing.Union[float, BatteryTime]
    power_plugged: _typing.Optional[bool]


class sfan(_typing.NamedTuple):
    label: str
    current: int


class pcputimes(_typing.NamedTuple):
    user: float
    system: float
    children_user: float
    children_system: float


class popenfile(_typing.NamedTuple):
    path: str
    fd: int


class pthread(_typing.NamedTuple):
    id: int
    user_time: float
    system_time: float


class puids(_typing.NamedTuple):
    real: int
    effective: int
    saved: int


class pgids(_typing.NamedTuple):
    real: int
    effective: int
    saved: int


class pio(_typing.NamedTuple):
    read_count: int
    write_count: int
    read_bytes: int
    write_bytes: int


class pionice(_typing.NamedTuple):
    ioclass: int
    value: int


class pctxsw(_typing.NamedTuple):
    voluntary: int
    involuntary: int


class pconn(_typing.NamedTuple):
    fd: int
    family: socket.AddressFamily
    type: socket.SocketKind
    laddr: 'addr'
    raddr: 'addr'
    status: str


class addr(_typing.NamedTuple):
    ip: str
    port: int


conn_tmap: (
    dict[str, tuple[list[socket.AddressFamily], list[socket.SocketKind]]]
)


# Exceptions
class Error(Exception):
    __module__: str = ...
    msg: str = ...

    def __init__(self, msg: str = ...) -> None:
        ...


class NoSuchProcess(Error):
    name: str = ...
    pid: int = ...

    def __init__(
        self,
        pid: int,
        name: _typing.Optional[str] = ...,
        msg: _typing.Optional[str] = ...,
    ) -> None:
        ...


class ZombieProcess(NoSuchProcess):
    ppid: int = ...

    def __init__(
        self,
        pid: int,
        name: _typing.Optional[str] = ...,
        ppid: _typing.Optional[int] = ...,
        msg: _typing.Optional[str] = ...,
    ) -> None:
        ...


class AccessDenied(Error):
    name: str = ...
    pid: int = ...

    def __init__(
        self,
        pid: _typing.Optional[int] = ...,
        name: _typing.Optional[str] = ...,
        msg: _typing.Optional[str] = ...,
    ) -> None:
        ...


class TimeoutExpired(Error):
    name: str = ...
    pid: int = ...
    seconds: float = ...

    def __init__(
        self,
        seconds: float,
        pid: _typing.Optional[int] = ...,
        name: _typing.Optional[str] = ...,
    ) -> None:
        ...


# Utility functions
def usage_percent(
    used: float,
    total: float,
    round_: _typing.Optional[int] = ...,
) -> float:
    ...


def memoize(fun: _T) -> _T:
    ...


def isfile_strict(path: str) -> bool:
    ...


def path_exists_strict(path: str) -> bool:
    ...


def supports_ipv6() -> bool:
    ...


def parse_environ_block(data: str) -> dict[str, str]:
    ...


def sockfam_to_enum(
    num: int
) -> _typing.Union[int, socket.AddressFamily]:
    ...


def socktype_to_enum(num: int) -> _typing.Union[int, socket.SocketKind]:
    ...


def conn_to_ntuple(
    fd: int,
    fam: socket.AddressFamily,
    type_: socket.SocketKind,
    laddr: _typing.Union[tuple[str, int], str],
    raddr: _typing.Union[tuple[str, int], str],
    status: str,
    status_map: dict[str, str],
    pid: _typing.Optional[int] = ...
) -> _typing.Union[pconn, sconn]:
    ...


def deprecated_method(replacement: _T) -> _T:
    ...


class _WrapNumbers:
    lock: threading.Lock = ...
    cache: dict[str, dict[str, tuple[int, ...]]] = ...
    reminders: dict[str, dict[str, int]] = ...
    reminder_keys: dict[str, dict[str, set[tuple[str, int]]]] = ...

    def __init__(self) -> None:
        ...

    def run(
        self,
        input_dict: dict[str, tuple[int, ...]],
        name: str,
    ) -> dict[str, tuple[int, ...]]:
        ...

    def cache_clear(self, name: _typing.Optional[str] = ...) -> None:
        ...

    def cache_info(
        self,
    ) -> tuple[dict[str, dict[str, tuple[int, ...]]],
               dict[str, dict[str, int]],
               dict[str, dict[str, set[tuple[str, int]]]],
               ]:
        ...


class _WrapNumbersFunction(_typing.Protocol):

    def __call__(
        self,
        input_dict: dict[str, tuple[int, ...]],
        name: str,
    ) -> dict[str, tuple[int, ...]]:
        ...

    def cache_clear(self, name: _typing.Optional[str] = ...) -> None:
        ...

    def cache_info(
        self,
    ) -> tuple[dict[str, dict[str, tuple[int, ...]]],
               dict[str, dict[str, int]],
               dict[str, dict[str, set[tuple[str, int]]]],
               ]:
        ...


wrap_numbers: _WrapNumbersFunction


def bytes2human(n: _typing.Union[float, str], format: str = ...) -> str:
    ...


# Shell utils
def term_supports_colors(file: _typing.IO[str] = ...) -> bool:
    ...


def hilite(
    s: object,
    color: _typing.Optional[str] = ...,
    bold: bool = ...,
) -> _typing.Union[object, str]:
    ...


class _PrintWriter(_typing.Protocol):

    def write(self, string: str) -> _typing.Any:
        ...


def print_color(
    s: object,
    color: _typing.Optional[str] = ...,
    bold: bool = ...,
    file: _PrintWriter = ...,
) -> None:
    ...


def debug(msg: object) -> None:
    ...
