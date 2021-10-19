#!/usr/bin/env python3

# Standard libraries.
import setuptools  # type: ignore


setuptools.setup(
    name="phile",
    version="0.0.0.2",
    description="A file-based notification management",
    author="Boni Lindsley",
    author_email="boni.lindsley@gmail.com",
    package_dir={
        "": "src",
        "test_phile": "tests",
    },
    packages=setuptools.find_packages(where="src"),
    license="MIT",
    install_requires=[
        "appdirs >= 1.4.4",
        "IMAPClient >= 2.2.0",
        "keyring >= 23.2.1",
        "pathvalidate >= 2.5.0",
        "portalocker >= 2.3.2",
        "psutil >= 5.8.0",
        "pydantic >= 1.8.2",
        "pynput >= 1.7.4",
        "PySide2 >= 5.15.2",
        "watchdog >= 2.1.6",
    ],
    entry_points={
        "console_scripts": [
            "phile = phile.__main__:main",
            "phile-notify = phile.notify.__main__:main",
            "phile-tray-tmux = phile.tray.tmux:main",
        ],
        "gui_scripts": [
            "phile-notify-gui = phile.notify.gui:main",
            "phile-tray-gui = phile.tray.gui:main",
        ],
    },
    extras_require={
        "dev": [
            "black >= 21.9b0",
            "coverage[toml] >= 6.0.2",
            "mypy >= 0.910",
            "pytest >= 6.2.5",
            "recommonmark >= 0.7.1",
            "Sphinx >= 4.2.0",
            "tox >= 3.24.4",
            "types-pkg_resources >= 0.1.3",
            "types-six >= 1.16.2",
        ],
    },
    # Requires Python 3.6 because Python is dropping support
    # for version 3.5 after September 2020 (as for 2020-09-05).
    # Reference: https://www.python.org/dev/peps/pep-0478/
    python_requires=">= 3.9",
    package_data={
        "phile.tray": [
            "resources/icons/blank/64x64/status/phile-tray-empty.png",
            "resources/icons/blank/64x64/status/phile-tray-new.png",
            "resources/icons/blank/64x64/status/phile-tray-read.png",
            "resources/icons/blank/index.theme",
        ],
    },
)
