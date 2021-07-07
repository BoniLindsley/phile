#!/usr/bin/env python3

from setuptools import setup  # type: ignore

setup(
    name='phile',
    version='0.0.0.2',
    description='A file-based notification management',
    author='Boni Lindsley',
    author_email='boni.lindsley@gmail.com',
    packages=[
        'phile',
        'phile.PySide2',
        'phile.asyncio',
        'phile.configuration',
        'phile.data',
        'phile.hotkey',
        'phile.launcher',
        'phile.notify',
        'phile.tmux',
        'phile.tray',
        'phile.trigger',
        'phile.watchdog',
    ],
    license='MIT',
    install_requires=[
        'IMAPClient',
        'keyring',
        'pathvalidate',
        'portalocker',
        'psutil',
        'pydantic',
        'pynput',
        'PySide2',
        'watchdog',
    ],
    entry_points={
        'console_scripts': [
            'phile = phile.__main__:main',
            'phile-notify = phile.notify.__main__:main',
            'phile-tray-tmux = phile.tray.tmux:main',
        ],
        'gui_scripts': [
            'phile-notify-gui = phile.notify.gui:main',
            'phile-tray-gui = phile.tray.gui:main',
        ],
    },
    extras_require={
        'dev': [
            'coverage',
            'mypy',
            'recommonmark',
            'sphinx',
            'tox',
            'types-pkg_resources',
            'types-six',
            'yapf',
        ],
    },
    # Requires Python 3.6 because Python is dropping support
    # for version 3.5 after September 2020 (as for 2020-09-05).
    # Reference: https://www.python.org/dev/peps/pep-0478/
    python_requires='>= 3.9',
    package_data={
        'phile.tray': [
            'resources/icons/blank/64x64/status/phile-tray-empty.png',
            'resources/icons/blank/64x64/status/phile-tray-new.png',
            'resources/icons/blank/64x64/status/phile-tray-read.png',
            'resources/icons/blank/index.theme',
        ],
    },
)
