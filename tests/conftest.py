import pytest
import subprocess
import time
import requests
import os
import signal
import socket

def _is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

@pytest.fixture(scope="session")
def fastapi_server():
    """
    Start or wait for a FastAPI server for E2E tests and stop it after the session.

    Behavior:
    - If a server is already listening on host:port, the fixture waits for an HTTP response
      and yields without starting or stopping any process.
    - Otherwise the fixture starts uvicorn (preferred) or falls back to `python -m app.main`,
      waits for readiness, yields to tests, and then attempts a graceful shutdown of the
      process it started.
    """
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd()

    host = "127.0.0.1"
    port = 8000
    env["PORT"] = str(port)
    server_url = f"http://{host}:{port}/"

    started_proc = None

    # If there's already a server listening on the port, wait until it answers HTTP
    if _is_port_open(host, port):
        timeout = 30
        start = time.time()
        while True:
            try:
                resp = requests.get(server_url, timeout=1)
                if resp.status_code < 500:
                    break
            except requests.RequestException:
                pass
            if time.time() - start > timeout:
                raise RuntimeError(f"Port {port} is open but server did not respond within timeout.")
            time.sleep(0.5)
        yield
        return

    # Try to start uvicorn; fallback to python -m app.main
    cmd_uvicorn = ["uvicorn", "app.main:app", "--host", host, "--port", str(port)]
    try:
        proc = subprocess.Popen(cmd_uvicorn, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        cmd_used = cmd_uvicorn
    except FileNotFoundError:
        cmd_fallback = ["python", "-m", "app.main"]
        proc = subprocess.Popen(cmd_fallback, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        cmd_used = cmd_fallback

    started_proc = proc

    # Wait for server readiness
    timeout = 30
    start = time.time()
    while True:
        if proc.poll() is not None:
            stdout, stderr = proc.communicate(timeout=1)
            raise RuntimeError(
                "FastAPI process exited prematurely.\n"
                f"cmd: {' '.join(cmd_used)}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
        try:
            resp = requests.get(server_url, timeout=1)
            if resp.status_code < 500:
                break
        except requests.RequestException:
            pass
        if time.time() - start > timeout:
            try:
                stdout, stderr = proc.communicate(timeout=1)
            except Exception:
                stdout = stderr = "<unable to capture>"
            proc.terminate()
            raise RuntimeError(
                "Timed out waiting for FastAPI to start.\n"
                f"cmd: {' '.join(cmd_used)}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
        time.sleep(0.5)

    yield

    # Teardown: only stop the process we started
    if started_proc is not None:
        try:
            started_proc.send_signal(signal.SIGINT)
            started_proc.wait(timeout=5)
        except Exception:
            started_proc.terminate()
            started_proc.wait(timeout=5)
