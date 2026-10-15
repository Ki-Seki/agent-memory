"""Minimal YAML-subset frontmatter parser and serializer.

Memory files only need scalars, quoted strings, flow lists, block lists and
one level of nested mappings, so this avoids a PyYAML dependency.
"""

import json
import re

FENCE = "---"


def split(text):
    """Return (meta, body). A file without frontmatter yields ({}, text)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != FENCE:
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == FENCE:
            meta = parse("\n".join(lines[1:i]))
            body = "\n".join(lines[i + 1 :]).lstrip("\n")
            return meta, body
    return {}, text


def join(meta, body):
    return f"{FENCE}\n{dump(meta)}{FENCE}\n{body.rstrip()}\n"


def parse(block):
    lines = [line.rstrip() for line in block.split("\n") if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        return {}
    value, _ = _parse_map(lines, 0, _indent(lines[0]))
    return value


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _parse_map(lines, i, indent):
    out = {}
    while i < len(lines):
        line = lines[i]
        ind = _indent(line)
        if ind < indent:
            break
        stripped = line.strip()
        if ind > indent or stripped.startswith("- "):
            i += 1
            continue
        key, sep, rest = stripped.partition(":")
        i += 1
        if not sep:
            continue
        key, rest = key.strip(), rest.strip()
        if rest:
            out[key] = _scalar(rest)
        elif i < len(lines) and _indent(lines[i]) > indent:
            child = _indent(lines[i])
            if lines[i].strip().startswith("- "):
                out[key], i = _parse_list(lines, i, child)
            else:
                out[key], i = _parse_map(lines, i, child)
        else:
            out[key] = ""
    return out, i


def _parse_list(lines, i, indent):
    out = []
    while i < len(lines) and _indent(lines[i]) >= indent:
        stripped = lines[i].strip()
        if _indent(lines[i]) == indent and stripped.startswith("- "):
            out.append(_scalar(stripped[2:].strip()))
        i += 1
    return out, i


def _scalar(s):
    if s.startswith('"'):
        try:
            return json.loads(s)
        except ValueError:
            return s.strip('"')
    if s.startswith("'") and s.endswith("'") and len(s) >= 2:
        return s[1:-1].replace("''", "'")
    if s.startswith("[") and s.endswith("]"):
        try:
            value = json.loads(s)
            if isinstance(value, list):
                return value
        except ValueError:
            pass
        inner = s[1:-1].strip()
        return [_scalar(p.strip()) for p in inner.split(",") if p.strip()] if inner else []
    low = s.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    if low in ("null", "~"):
        return None
    return s


_RESERVED = {"true", "false", "null", "yes", "no", "on", "off", "~"}


def _needs_quote(s):
    if s == "" or s != s.strip() or "\n" in s:
        return True
    if s.lower() in _RESERVED:
        return True
    if s[0] in "-?:,[]{}#&*!|>'\"%@`":
        return True
    if ": " in s or " #" in s or s.endswith(":"):
        return True
    return bool(re.fullmatch(r"[-+]?\d+(\.\d+)?", s))


def _emit(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_emit(v) for v in value) + "]"
    s = str(value)
    return json.dumps(s, ensure_ascii=False) if _needs_quote(s) else s


def dump(meta):
    out = []
    for key, value in meta.items():
        if isinstance(value, dict):
            out.append(f"{key}:")
            for k, v in value.items():
                out.append(f"  {k}: {_emit(v)}")
        else:
            out.append(f"{key}: {_emit(value)}")
    return "\n".join(out) + "\n"
