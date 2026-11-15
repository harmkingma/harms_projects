"""Test bootstrap.

Home Assistant core is POSIX-only. On Windows:
- homeassistant.runner imports fcntl and resource at module level for its
  single-instance lock file and file-descriptor limit, neither of which the
  tests use, so stubs are registered before the Home Assistant pytest plugin
  loads. pytest.ini disables the plugin's autoload so this file loads it in order.
- The plugin blocks sockets per test, but the Windows asyncio event loop needs a
  local socket pair to start. Socket blocking is turned off; these tests make no
  network calls.
"""

import sys
import types

if sys.platform == "win32":
    import pytest_socket

    if "fcntl" not in sys.modules:
        fcntl = types.ModuleType("fcntl")
        fcntl.LOCK_EX, fcntl.LOCK_NB, fcntl.LOCK_UN = 2, 4, 8
        fcntl.flock = lambda *_args, **_kwargs: None
        sys.modules["fcntl"] = fcntl
    if "resource" not in sys.modules:
        resource = types.ModuleType("resource")
        resource.RLIMIT_NOFILE = 7
        resource.getrlimit = lambda _limit: (8192, 8192)
        resource.setrlimit = lambda *_args, **_kwargs: None
        sys.modules["resource"] = resource

    pytest_socket.disable_socket = lambda *_args, **_kwargs: None
    pytest_socket.socket_allow_hosts = lambda *_args, **_kwargs: None

pytest_plugins = ["pytest_homeassistant_custom_component.plugins"]
