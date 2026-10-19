"""`mem ui`: the data behind the local page for searching, reading and editing memories.

Similar memories and search by meaning come from a local embedding model
(Qwen3-Embedding-0.6B, int8 ONNX, run in an isolated `uv` environment) when
it is present, and from keyword vectors (TF-IDF over English words,
identifiers and Chinese words) otherwise.
"""

import datetime as _dt
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np

from . import config, lint, store
from .util import HOME

WORKER = Path(__file__).with_name("embed_worker.py")

# The embedding model, pinned to one revision and checked by hash.
MODEL = {
    "name": "Qwen3-Embedding-0.6B (int8 ONNX)",
    "dir": "qwen3-embedding-0.6b-int8",
    "repo": "onnx-community/Qwen3-Embedding-0.6B-ONNX",
    "revision": "c25a394dd583836952667c12f008335071b3f43d",
    "files": {
        "onnx/model_quantized.onnx": "87cd124e0ef1fd1f223ebc283efccbaeac386d0b08344701c46975d0657b591f",
        "config.json": None,
        "tokenizer.json": None,
        "tokenizer_config.json": None,
        "special_tokens_map.json": None,
    },
    # Plain text, no instruction prefix: on known same-topic pairs (including Chinese/English
    # ones) this ranked partners closer than the topic or similarity instructions did.
    "instruction": "",
}
WORKER_DEPS = ["onnxruntime==1.31.0", "tokenizers==0.23.3", "numpy"]
EMBED_CHARS = 2000  # characters of each memory given to the model
TITLE_WEIGHT = 3  # description and name count this many times in keyword vectors
NEIGHBORS = 6  # similar memories listed for each memory
KEYWORDS = 4  # keywords shown for each memory
SEARCH_INSTRUCTION = "Instruct: Given a search query, retrieve memory notes about it\nQuery: "

_ASCII = re.compile(r"[A-Za-z][A-Za-z0-9_+#-]*[A-Za-z0-9+#]|[A-Za-z]")
_CJK = re.compile(r"[㐀-鿿]+")
_STOP = set(
    """
a about above after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing done down during each either else etc even
ever every few for from further get gets got had has have having he her here hers him his how i if
in into is it its itself just keep kept let like made make makes many may me might more most much
must my no nor not now of off often on once one only or other our out over own per put rather re
same see seen she should since so some such than that the their them then there these they this
those though through thus to too under until up upon us use used uses using very via was way we
well were what when where whether which while who whom whose why will with within without would
yes yet you your also first new next last still back via vs eg ie non
md json txt yaml yml py js ts html css sh com org www http https github io dev
task tasks memory memories user users agent agents codex claude session sessions file files
when what thing things work works working worked step steps run runs running ran note notes
group scope cwd thread_id updated_at rollout rollout_path rollout_summary
rollout_summary_files rollout_summaries applies_to reuse_rule keywords reusable knowledge failures
differently preferences apply how why outcome success partial history summary
asked plus real never check checks verify verified evidence explicit said complete final current
live state local source remote text path test symptom instead before after already actual ad-hoc
""".split()
)
# Paths, URLs, hashes and ids say where something lives, not what it is about.
_NOISE = re.compile(
    r"(?:https?://\S+|(?:~|/|\.\.?/)[\w.@%+-]+(?:/[\w.@%+-]*)+"
    r"|\b[\w.-]+\.(?:md|json|jsonl|py|ts|js|html|yaml|yml|toml|txt|sh)\b"
    r"|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b|\b[0-9a-f]{7,40}\b"
    r"|\b\d{4}-\d\d-\d\d(?:[T ][\d:.+-]+)?\b)"
)
CJK_MAX = 4
_STOP_CJK = set(
    """
的是 是的 一个 这个 那个 可以 需要 如果 因为 所以 但是 而且 或者 以及 我们 你们 他们 用户 时候 没有 不是 就是
已经 进行 通过 使用 这样 这些 那些 什么 怎么 为了 之后 之前 然后 还是 一下 一些 这里 那里 其中 以后 以前 不要
必须 应该 能够 只是 也是 都是 就会 会在 在这 这次 每次 一次 当前 目前 现在 之类 等等 方面 问题 内容 情况
相关 进行 这种 时候 需要 不能 不会 只有 直接 所有 其他 自己 一样 部分 以上 以下 下来 起来 出来 每个 各个 任何 一定 先给
""".split()
)
# Function characters that start no word: 的了和与… A string beginning with one is a fragment.
_CJK_BAD_START = set(
    "的了和与及或就都也把被让给并而时在是对向从个件等上不每一这那该各再又还才只很最更已将会能要可使于以之其此"
)
_CJK_KEEP = {"完成", "生成", "集成", "构成", "组成", "前后", "最后", "然后", "之后", "背后", "上一", "中文"}
# ...and characters that end no word: a string ending in one runs into the next word.
_CJK_BAD_END = set("的了着过是在和与及等上中里成到给把被让后不也都就又再才很一个这那各每将会能要可于以之其此任")


# ------------------------------------------------------------ keyword vectors


def clean(text):
    return _NOISE.sub(" ", text)


def chinese_words(texts):
    """Recurring Chinese words, found without a dictionary.

    Takes every 2-4 character string that appears in at least two texts, then
    drops fragments: a string that nearly always occurs inside one longer
    string (e.g. 京时 inside 北京时间) is part of that word, not a word.
    """
    df = Counter()
    for text in texts:
        grams = set()
        for run in _CJK.findall(text):
            for n in range(2, CJK_MAX + 1):
                grams.update(run[i : i + n] for i in range(len(run) - n + 1))
        df.update(grams)
    frequent = {g for g, d in df.items() if d >= 2}
    words = set()
    for g in frequent:
        longer = [h for h in frequent if len(h) == len(g) + 1 and g in h]
        if not any(df[h] >= 0.8 * df[g] for h in longer):
            words.add(g)
    return {
        w
        for w in words - _STOP_CJK
        if (w[0] not in _CJK_BAD_START or w == "时间") and (w[-1] not in _CJK_BAD_END or w in _CJK_KEEP)
    }


def tokens(text, words=frozenset()):
    """Lowercased English words and identifiers, plus Chinese words.

    Chinese runs are split by longest match against `words`; characters that
    start no known word are skipped.
    """
    text = clean(text)
    out = []
    for w in _ASCII.findall(text):
        low = w.lower().strip("-_")
        if len(low) < 2 or low in _STOP or low.isdigit():
            continue
        if len(low) == 2 and not w.isupper():  # keep acronyms like S3, UI
            continue
        out.append(low)
    for run in _CJK.findall(text):
        i = 0
        while i < len(run) - 1:
            for n in range(min(CJK_MAX, len(run) - i), 1, -1):
                if run[i : i + n] in words:
                    out.append(run[i : i + n])
                    i += n
                    break
            else:
                i += 1
    return out


def _display_forms(texts):
    """Most common original spelling of each token (GPU, not gpu), for showing keywords."""
    seen = {}
    for text in texts:
        for w in _ASCII.findall(text):
            seen.setdefault(w.lower().strip("-_"), Counter())[w] += 1
    return {k: c.most_common(1)[0][0] for k, c in seen.items()}


# Plain English words that score high in TF-IDF but say little about what a memory is about.
_GENERIC = set(
    """
actually specified large small nontrivial declaring declared truth human builds build built pin pinned
following follow follows needed need needs means mean simple simply clear clearly important exact exactly
whole entire full fully main mainly certain directly direct proper properly various several general
correct correctly wrong instead later earlier often usually rather quite really already able unable
item items part parts kind way ways case cases point points detail details thing result results
come comes edit edits edited anything something everything separate change changes changed
fail fails failed code example examples
""".split()
)


def _term_like(display):
    """Acronyms, identifiers and Chinese words make better keywords than plain English.

    A capital only at the start (Choose, Pack) is usually the start of a sentence, so it
    does not count; one further in (SigLIP, GPU, OpenReview) does.
    """
    return bool(re.search(r".[A-Z]|[0-9_.+#-]|[\u3400-\u9fff]", display))


def keyword_picks(x, vocab, forms, k=KEYWORDS):
    """Column indices of each memory's keywords, best first."""
    skip = _GENERIC | {w.lower() for w in config.load().get("keyword_stopwords", [])}
    weight = np.array([0 if t in skip else (1.6 if _term_like(forms.get(t, t)) else 1.0) for t in vocab])
    scored = x * weight
    return [[int(j) for j in np.argsort(-row)[:k] if row[j] > 0] for row in scored]


def vectorize(docs):
    """TF-IDF rows (L2-normalized) and the vocabulary.

    docs: list of (title, body). Title tokens count TITLE_WEIGHT times.
    Terms in one document only carry no similarity and are dropped, as are
    terms in more than half of the documents.
    """
    words = chinese_words(clean(t + " " + b) for t, b in docs)
    counts = [Counter(tokens(t, words) * TITLE_WEIGHT + tokens(b, words)) for t, b in docs]
    df = Counter(term for c in counts for term in c)
    n = len(docs)
    vocab = sorted(t for t, d in df.items() if 2 <= d <= max(2, n // 2))
    index = {t: i for i, t in enumerate(vocab)}
    x = np.zeros((n, len(vocab)))
    for row, c in enumerate(counts):
        for term, tf in c.items():
            j = index.get(term)
            if j is not None:
                x[row, j] = (1 + math.log(tf)) * math.log((1 + n) / (1 + df[term]))
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.where(norms == 0, 1, norms), vocab


# ------------------------------------------------------------ meaning vectors

_TEMPLATE_LINE = re.compile(r"^\s*(?:-\s*)?rollout_summaries/|^\s*#+\s*(?:rollout_summary_files|keywords)\s*$", re.I)


def prose(title, body):
    """What the model reads: the description and body without bookkeeping lines."""
    lines = [line for line in body.splitlines() if not _TEMPLATE_LINE.search(line)]
    text = clean(f"{title}\n" + "\n".join(lines))
    text = re.sub(r"[#*`>|]+", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()[:EMBED_CHARS]


def model_dir():
    custom = config.load().get("embed_model_dir")
    return Path(custom).expanduser() if custom else Path("~/.cache/agent-memory/models").expanduser() / MODEL["dir"]


def model_ready():
    d = model_dir()
    return (d / "model_quantized.onnx").exists() and (d / "tokenizer.json").exists() and bool(shutil.which("uv"))


def fetch_model():
    """Download the pinned model files (about 625 MB) and check the ONNX hash."""
    d = model_dir()
    d.mkdir(parents=True, exist_ok=True)
    base = f"https://huggingface.co/{MODEL['repo']}/resolve/{MODEL['revision']}"
    for rel, sha in MODEL["files"].items():
        target = d / Path(rel).name
        if target.exists() and (sha is None or _sha256(target) == sha):
            continue
        print(f"downloading {rel}…", flush=True)
        part = target.with_suffix(target.suffix + ".part")
        urllib.request.urlretrieve(f"{base}/{rel}", part)
        if sha and _sha256(part) != sha:
            part.unlink()
            raise SystemExit(f"{rel}: checksum mismatch, download discarded")
        part.replace(target)
    (d / "REVISION").write_text(MODEL["revision"] + "\n")
    print(f"model ready in {d}")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def embed(data_dir, texts):
    """Unit vectors for texts, reusing cached ones; None if the model is unavailable."""
    if not model_ready():
        return None
    cache_file = Path(data_dir) / ".cache" / "embeddings" / f"{MODEL['dir']}.npz"
    keys = [hashlib.sha1((MODEL["revision"] + MODEL["instruction"] + t).encode()).hexdigest() for t in texts]
    known = {}
    if cache_file.exists():
        with np.load(cache_file) as z:
            known = dict(zip(z["keys"].tolist(), z["vectors"]))
    todo = [i for i, k in enumerate(keys) if k not in known]
    if todo:
        out = cache_file.with_name("new-vectors.npy")
        out.parent.mkdir(parents=True, exist_ok=True)
        job = {
            "model_dir": str(model_dir()),
            "out": str(out),
            "max_tokens": 512,
            "texts": [MODEL["instruction"] + texts[i] for i in todo],
        }
        print(f"embedding {len(todo)} memories with {MODEL['name']}…", flush=True)
        cmd = (
            ["uv", "run", "--no-project", "--quiet"]
            + [a for dep in WORKER_DEPS for a in ("--with", dep)]
            + ["python", "-I", str(WORKER)]
        )
        r = subprocess.run(
            cmd, input=json.dumps(job), text=True, cwd=str(out.parent), env={**os.environ, "PYTHONWARNINGS": "ignore"}
        )
        if r.returncode != 0:
            print("embedding failed; falling back to keywords", file=sys.stderr)
            return None
        for i, vec in zip(todo, np.load(out)):
            known[keys[i]] = vec
        out.unlink()
        live = {k: known[k] for k in keys}  # drop vectors of edited or deleted memories
        np.savez(cache_file, keys=np.array(list(live)), vectors=np.array(list(live.values())))
    return np.array([known[k] for k in keys])


def closeness(vectors):
    """The cosine similarity of every pair of unit rows, as it is (below 0 reads as 0), and what a typical pair
    scores: the median over pairs of different memories. Pairs at or below it are not listed as similar.

    It is not rescaled: rescaling made the closest pair 100% however far apart it was.
    """
    sim = np.clip(vectors @ vectors.T, 0, 1)
    off = sim[~np.eye(len(sim), dtype=bool)]
    np.fill_diagonal(sim, 1)
    return sim, float(np.median(off)) if len(off) else 0.0


# ------------------------------------------------------------ page data


def _short(path):
    home = str(HOME)
    return "~" + path[len(home) :] if path and (path == home or path.startswith(home + "/")) else path or ""


def _place(src):
    if src.get("git_remote"):
        return src["git_remote"]
    return _short(src.get("git_root") or src.get("cwd") or "")


def build(data_dir, semantic=True, vectors_out=None):
    """Every memory with its whole file, and the ones most similar to it."""
    now = _dt.datetime.now().astimezone()
    mdir = store.memories_dir(data_dir)
    items, docs = [], []
    for m in store.load_all(data_dir):
        try:
            raw = (mdir / m["rel"]).read_text("utf-8", errors="replace")
        except OSError:
            continue
        meta, body = store.read(mdir / m["rel"])
        items.append((m, raw, meta, body))
        docs.append((f"{m['description']} {m['name'].replace('-', ' ')}", body))
    base = {"generated": now.isoformat(timespec="minutes"), "dataDir": _short(str(data_dir))}
    if not items:
        return {**base, "memories": [], "places": [], "method": "", "semantic": False}

    # keywords: the words that most set each memory apart (TF-IDF), shared with at least one other
    x, vocab = vectorize(docs)
    forms = _display_forms(clean(t + " " + b) for t, b in docs)
    vectors = embed(data_dir, [prose(t, b) for t, b in docs]) if semantic else None
    space = vectors if vectors is not None else x
    sim, typical = closeness(space)
    method = f"{MODEL['name']}, local" if vectors is not None else "keywords only (no local model)"
    if vectors_out is not None:
        vectors_out[:] = [space]

    picks = keyword_picks(x, vocab, forms)
    names = {m["name"] for m, _, _, _ in items if m["name"]}
    rows, places = [], {}
    for i, (m, raw, meta, body) in enumerate(items):
        order = [int(j) for j in np.argsort(-sim[i]) if j != i][:NEIGHBORS]
        src = m["source"]
        rows.append(
            {
                "id": m["id"],
                "rel": m["rel"],
                "path": str(mdir / m["rel"]),
                "hash": hashlib.sha1(raw.encode()).hexdigest()[:16],
                "raw": raw,
                "meta": json.loads(json.dumps(meta, default=str)),
                "body": body,
                "description": m["description"],
                "type": m["type"],
                "scope": m["scope"],
                "place": _place(src) if m["scope"] == "here" else "",
                "tool": src.get("tool") or "",
                "host": src.get("host") or "",
                "created": m["created"],
                "updated": m["updated"],
                "similar": [{"i": j, "s": round(float(sim[i, j]), 3)} for j in order if sim[i, j] > typical],
                "keywords": [{"k": vocab[j], "t": forms.get(vocab[j], vocab[j])} for j in picks[i]],
                "terms": [vocab[j] for j in np.flatnonzero(x[i])],
                "issues": [message for _, message in lint.check(m, body, names)],
            }
        )
        if m["scope"] == "here" and (src.get("git_remote") or src.get("cwd")):
            key = _place(src)
            places.setdefault(
                key,
                {
                    "key": key,
                    "count": 0,
                    "ctx": {k: src[k] for k in ("cwd", "git_root", "git_remote", "git_branch", "host") if src.get(k)},
                },
            )
            places[key]["count"] += 1
    return {
        **base,
        "memories": rows,
        "method": method,
        "semantic": vectors is not None,
        "places": sorted(places.values(), key=lambda p: (-p["count"], p["key"])),
    }


# ------------------------------------------------------------ query embedding


class QueryEncoder:
    """A long-lived embedding worker for search queries (model loads once)."""

    def __init__(self):
        self.proc = None
        self.lock = threading.Lock()

    def encode(self, text):
        if not model_ready():
            return None
        with self.lock:
            if self.proc is None or self.proc.poll() is not None:
                cmd = (
                    ["uv", "run", "--no-project", "--quiet"]
                    + [a for dep in WORKER_DEPS for a in ("--with", dep)]
                    + ["python", "-I", str(WORKER), "--serve", str(model_dir())]
                )
                self.proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                    cwd=str(model_dir()),
                )
            self.proc.stdin.write(json.dumps({"text": SEARCH_INSTRUCTION + text}) + "\n")
            self.proc.stdin.flush()
            line = self.proc.stdout.readline()
        if not line:
            return None
        return np.array(json.loads(line)["vector"], dtype=np.float32)

    def close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
