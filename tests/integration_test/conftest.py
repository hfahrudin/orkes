import os
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

MOCK_SERVER = os.path.join(os.path.dirname(__file__), "..", "mock_servers", "mock_llm_server.py")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def mock_server():
    """Starts the mock LLM server on a free port and yields its base URL.

    A free port avoids clashing with anything already running locally (such as
    an Orkes Watcher backend on 8000).
    """
    port = _free_port()
    process = subprocess.Popen([sys.executable, MOCK_SERVER, str(port)])
    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    while True:
        try:
            urllib.request.urlopen(f"{url}/docs", timeout=1)
            break
        except OSError:
            if process.poll() is not None or time.time() > deadline:
                process.terminate()
                raise RuntimeError("mock LLM server didn't start")
            time.sleep(0.1)
    yield url
    process.terminate()
    process.wait()
