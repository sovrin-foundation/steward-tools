import json
import platform
import urllib.request

import asyncio
from ctypes import cdll
from pathlib import Path

from src.constants import *

PROTOCOL_VERSION = 2

LIBRARY = {"darwin": "libsovtoken.dylib", "linux": "libsovtoken.so", "win32": "sovtoken.dll", 'windows': 'sovtoken.dll'}
INITIAL_DIR = Path.home()

loop = asyncio.get_event_loop()


def load_config():
    return json.loads(read_remote_file(CONFIG_URL))


def read_remote_file(url: str) -> str:
    return urllib.request.urlopen(url).read().decode()


def download_remote_file(url: str) -> str:
    path, _ = urllib.request.urlretrieve(url)
    return path


def library():
    your_platform = platform.system().lower()
    return LIBRARY[your_platform] if (your_platform in LIBRARY) else 'libsovtoken.so'


def load_plugin():
    try:
        payment_plugin = cdll.LoadLibrary(library())
        payment_plugin.sovtoken_init()
    except Exception as e:
        raise Exception(e)


def run_coroutine(coroutine):
    return loop.run_until_complete(coroutine)
