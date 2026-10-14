"""Git operations on the data repository, serialized by a file lock."""

import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

from .config import BIN
from .util import log

_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


class Lock:
    """Exclusive lock shared by every hook and CLI process on this machine."""

    def __init__(self, data_dir, timeout=10.0):
        self.path = Path(data_dir) / ".cache" / "lock"
        self.timeout = timeout
        self.fd = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT, 0o644)
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    os.close(self.fd)
                    self.fd = None
                    return False
                time.sleep(0.05)

    def __exit__(self, *exc):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None


def git(data_dir, *args, timeout=30):
    return subprocess.run(["git", "-C", str(data_dir), *args], capture_output=True,
                          text=True, timeout=timeout, env=_ENV)


def has_remote(data_dir):
    # A system gitconfig can declare remote.origin.* without a URL, so look for URLs.
    r = git(data_dir, "config", "--get-regexp", r"^remote\..*\.url$", timeout=5)
    return r.returncode == 0 and bool(r.stdout.strip())


def commit(data_dir, message):
    """Stage everything under memories/ and commit. Returns True if a commit was made."""
    git(data_dir, "add", "-A", "--", "memories")
    if git(data_dir, "diff", "--cached", "--quiet").returncode == 0:
        return False
    r = git(data_dir, "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m", message)
    if r.returncode != 0:
        log(data_dir, f"commit failed: {r.stderr.strip()}")
        return False
    return True


def sync(data_dir, push=True):
    """Pull (rebase) and optionally push. Caller must hold the lock."""
    if not has_remote(data_dir):
        return
    r = git(data_dir, "pull", "--rebase", "--autostash", "-q", timeout=60)
    if r.returncode != 0:
        log(data_dir, f"pull failed: {r.stderr.strip()}")
        if (Path(data_dir) / ".git" / "rebase-merge").exists() or \
                (Path(data_dir) / ".git" / "rebase-apply").exists():
            git(data_dir, "rebase", "--abort")
        return
    if push:
        ahead = git(data_dir, "rev-list", "--count", "@{u}..HEAD")
        if ahead.returncode != 0 or ahead.stdout.strip() != "0":
            r = git(data_dir, "push", "-q", timeout=60)
            if r.returncode != 0:
                log(data_dir, f"push failed: {r.stderr.strip()}")


def spawn_sync(data_dir, push):
    """Run `mem sync` detached so hooks return immediately."""
    args = [sys.executable, str(BIN), "sync", "--quiet"]
    if not push:
        args.append("--pull-only")
    log_path = Path(data_dir) / ".cache" / "sync.out"
    try:
        with open(log_path, "a") as out:
            subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                             start_new_session=True,
                             env={**os.environ, "AGENT_MEMORY_DATA": str(data_dir)})
    except OSError as e:
        log(data_dir, f"spawn sync failed: {e}")
