"""Checks that a memory follows the body skeleton in PROTOCOL.md.

They only report. A memory that breaks a rule is still worth keeping until
someone tidies it, so nothing is rejected.
"""

import re

DESCRIPTION_MAX = 150  # the index cuts longer descriptions (select.line)
BODY_MAX = 1500
NEEDS_REASON = ("feedback", "project")

_WHY = re.compile(r"\*\*\s*why\s*:?\s*\*\*", re.I)
_HOW = re.compile(r"\*\*\s*how to apply\s*:?\s*\*\*", re.I)
_WIKI = re.compile(r"\[\[([^\]]+)\]\]")
KINDS = {
    "long": "too long",
    "reason": "without Why or How to apply",
    "heading": "opening with a heading",
    "description": "with a description the index cuts",
    "links": "with broken links",
    "empty": "empty",
}


def check(m, body, names):
    """What is wrong with one memory, as (kind, message) pairs; empty when nothing is.

    m is a memory as store.load_all returns it; names holds every memory's name,
    for checking [[links]].
    """
    out = []
    desc = " ".join(m["description"].split())
    if len(desc) > DESCRIPTION_MAX:
        out.append(("description", f"description is {len(desc)} characters; the index shows {DESCRIPTION_MAX}"))
    text = body.strip()
    if not text:
        return out + [("empty", "body is empty")]
    if len(text) > BODY_MAX:
        out.append(("long", f"body is {len(text):,} characters; keep it under about {BODY_MAX:,}"))
    first = next(line for line in text.splitlines() if line.strip())
    if first.lstrip().startswith("#"):
        out.append(("heading", "opens with a heading instead of the fact"))
    if m["type"] in NEEDS_REASON:
        missing = [label for label, rx in (("**Why:**", _WHY), ("**How to apply:**", _HOW)) if not rx.search(body)]
        if missing:
            out.append(("reason", "no " + " or ".join(missing)))
    broken = sorted({n.strip() for n in _WIKI.findall(body)} - set(names))
    if broken:
        out.append(("links", "links to " + ", ".join(f"[[{n}]]" for n in broken) + ", which no memory is named"))
    return out
