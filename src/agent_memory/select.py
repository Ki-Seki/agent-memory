"""Choosing which memories a session sees, and rendering the index."""

from .context import describe
from .util import is_under, parse_time, specific

TYPE_ORDER = {"user": 0, "feedback": 1, "reference": 2, "project": 3}

# Claude Code caps injected hook context at 10,000 characters.
DEFAULT_BUDGET = 9000
GLOBAL_SHARE = 0.5


def location_score(source, ctx):
    """How strongly a memory recorded at `source` belongs to the session at `ctx`.

    0 means unrelated. Higher is closer: same folder, same git checkout, same
    remote (another clone or worktree), then parent or child folders.
    """
    best = 0
    remote = source.get("git_remote")
    if remote and remote == ctx.get("git_remote"):
        best = max(best, 80)
    here, there = ctx.get("cwd"), source.get("cwd")
    if here and there:
        if here == there:
            best = max(best, 100)
        root = source.get("git_root")
        if root and root == ctx.get("git_root") and source.get("host") in (None, ctx.get("host")):
            best = max(best, 90)
        if is_under(here, there) and specific(there):
            best = max(best, 70)
        if is_under(there, here) and specific(here):
            best = max(best, 60)
    return best


def _recency(m):
    t = parse_time(m.get("updated")) or parse_time(m.get("created"))
    return t.timestamp() if t else 0.0


def visible(memories, ctx, include_all=False):
    """(global, here) lists visible from ctx, each sorted best-first."""
    globals_, here = [], []
    for m in memories:
        if m["scope"] == "global":
            globals_.append(m)
            continue
        score = location_score(m["source"], ctx)
        if score or include_all:
            here.append((score, m))
    globals_.sort(key=lambda m: (TYPE_ORDER.get(m["type"], 9), -_recency(m)))
    here.sort(key=lambda sm: (-sm[0], -_recency(sm[1])))
    return globals_, [m for _, m in here]


def line(m):
    desc = " ".join(m["description"].split())
    if len(desc) > 150:
        desc = desc[:149] + "…"
    return f"- [{m['type']}] {desc} → {m['rel']}"


def _take(items, budget):
    out, used = [], 0
    for m in items:
        text = line(m)
        if used + len(text) + 1 > budget:
            break
        out.append(text)
        used += len(text) + 1
    return out, used


THROWAWAY_NOTE = ("throwaway folder: `here` memories will be filed under the project "
                  "this session works in")


def render(memories, ctx, paths, budget=DEFAULT_BUDGET, throwaway=False):
    globals_, here = visible(memories, ctx)
    location = describe(ctx) + (f" ({THROWAWAY_NOTE})" if throwaway else "")
    header = [
        "# Shared memory index",
        f"memories: {paths['memories']}",
        f"staging (write new memories here): {paths['staging']}",
        f"mem: {paths['mem']}",
        f"location: {location}",
    ]
    budget -= sum(len(h) + 1 for h in header) + 400  # headings and overflow notes

    g_lines, g_used = _take(globals_, int(budget * GLOBAL_SHARE))
    h_lines, h_used = _take(here, budget - g_used)
    if len(g_lines) < len(globals_) and h_used < budget - g_used:
        g_lines, _ = _take(globals_, budget - h_used)

    out = list(header)
    out += ["", f"## Global ({len(globals_)})"]
    out += g_lines or ["(none)"]
    if len(g_lines) < len(globals_):
        out.append(f"({len(globals_) - len(g_lines)} more: `mem list --global`)")
    out += ["", f"## This location ({len(here)})"]
    out += h_lines or ["(none)"]
    if len(h_lines) < len(here):
        out.append(f"({len(here) - len(h_lines)} more: `mem list --here`)")
    return "\n".join(out) + "\n"
