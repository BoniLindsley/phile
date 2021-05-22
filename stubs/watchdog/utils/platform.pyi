PLATFORM_WINDOWS: str
PLATFORM_LINUX: str
PLATFORM_BSD: str
PLATFORM_DARWIN: str
PLATFORM_UNKNOWN: str


def get_platform_name() -> str:
    ...


__platform__: str


def is_linux() -> None:
    ...


def is_bsd() -> None:
    ...


def is_darwin() -> None:
    ...


def is_windows() -> None:
    ...
