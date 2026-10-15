"""Where a session is running: folder, host and git identity."""

import os
import re
import socket
import subprocess

_GIT_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}


def _git(cwd, *args):
    try:
        r = subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=3, env=_GIT_ENV)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def normalize_remote(url):
    """Reduce a git remote URL to host/owner/repo, dropping credentials."""
    url = (url or "").strip()
    if not url:
        return ""
    m = re.match(r"^[\w.-]+@([^:/]+):(.+)$", url)
    if not m:
        m = re.match(r"^[a-z][a-z0-9+.-]*://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$", url, re.I)
    if not m:
        return url.lower()
    host, path = m.groups()
    path = path.strip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return f"{host}/{path}".lower()


def hostname():
    h = socket.gethostname()
    return h[:-6] if h.endswith(".local") else h


def detect(cwd=None):
    cwd = os.path.realpath(os.path.expanduser(cwd or os.getcwd()))
    ctx = {"host": hostname(), "cwd": cwd}
    if not os.path.isdir(cwd):
        return ctx
    root = _git(cwd, "rev-parse", "--show-toplevel")
    if not root:
        return ctx
    ctx["git_root"] = os.path.realpath(root)
    remote = _git(cwd, "remote", "get-url", "origin")
    if not remote:
        names = _git(cwd, "remote").split()
        remote = _git(cwd, "remote", "get-url", names[0]) if names else ""
    if remote:
        ctx["git_remote"] = normalize_remote(remote)
    branch = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch != "HEAD":
        ctx["git_branch"] = branch
    commit = _git(cwd, "rev-parse", "--short", "HEAD")
    if commit:
        ctx["git_commit"] = commit
    return ctx


def describe(ctx):
    parts = [f"cwd={ctx.get('cwd', '?')}"]
    if ctx.get("git_remote"):
        parts.append(f"remote={ctx['git_remote']}")
    elif ctx.get("git_root"):
        parts.append(f"git_root={ctx['git_root']}")
    parts.append(f"host={ctx.get('host', '?')}")
    return ", ".join(parts)
