#!/usr/bin/env python3
"""
Shared helpers to run external recon tools gently:
  - every child runs under `nice` (default 19) so it never starves the server
  - hard timeout, and the whole process group is killed on timeout
  - StreamProc reads stdout line by line (no huge buffers in RAM)

Env vars:
    WATCH_NICE         nice level for children (default 19, 0 disables)
    WATCH_CMD_TIMEOUT  default timeout in seconds (default 7200)
"""
import os
import shutil
import signal
import subprocess
import threading

DEFAULT_TIMEOUT = int(os.environ.get("WATCH_CMD_TIMEOUT", "7200"))
NICE_LEVEL = os.environ.get("WATCH_NICE", "19")


def _wrap(command):
    argv = ["bash", "-c", command]
    if NICE_LEVEL and NICE_LEVEL != "0" and shutil.which("nice"):
        argv = ["nice", "-n", NICE_LEVEL] + argv
    return argv


def _kill(proc):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def missing_tools(names):
    """Return the tools from `names` that are not found in PATH."""
    return [n for n in names if shutil.which(n) is None]


def run_bash(command, timeout=None):
    """
    Run a shell command (niced, with timeout) and return a CompletedProcess.
    On timeout the process group is killed and returncode is 124.
    """
    timeout = timeout or DEFAULT_TIMEOUT
    proc = subprocess.Popen(
        _wrap(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill(proc)
        out, err = proc.communicate()
        return subprocess.CompletedProcess(proc.args, 124, out or "", f"timeout after {timeout}s")
    return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)


class StreamProc:
    """
    Iterate over stdout lines of a niced shell command without buffering
    the whole output. After iteration: .returncode, .timed_out and .ok are set.
    """

    def __init__(self, command, timeout=None):
        self.command = command
        self.timeout = timeout or DEFAULT_TIMEOUT
        self.returncode = None
        self.timed_out = False

    @property
    def ok(self):
        return (not self.timed_out) and self.returncode == 0

    def __iter__(self):
        proc = subprocess.Popen(
            _wrap(self.command),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            errors="replace",
            bufsize=1,
            start_new_session=True,
        )

        def on_timeout():
            self.timed_out = True
            _kill(proc)

        timer = threading.Timer(self.timeout, on_timeout)
        timer.daemon = True
        timer.start()
        try:
            for line in proc.stdout:
                line = line.strip()
                if line:
                    yield line
        finally:
            timer.cancel()
            if proc.poll() is None:
                _kill(proc)
            proc.wait()
            self.returncode = proc.returncode
