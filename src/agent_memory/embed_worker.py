"""Embed texts with a local ONNX embedding model. Runs in its own environment.

`mem ui` starts this with `uv run --with onnxruntime --with tokenizers`, so
neither package has to be installed where the hooks run. It reads a JSON job
on stdin and writes an .npy matrix of L2-normalized vectors:

    {"model_dir": ..., "texts": [...], "out": "vectors.npy", "max_tokens": 512}

With `--serve MODEL_DIR` it stays up and answers one {"text": ...} per line
with {"vector": [...]}, for search queries.

The model directory holds model_quantized.onnx (or model.onnx) and a
Hugging Face tokenizer.json. Pooling follows the model family: last token for
decoder models such as Qwen3-Embedding, attention-masked mean otherwise.
"""

import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer


def load(model_dir):
    model_dir = Path(model_dir)
    onnx = next(p for p in (model_dir / "model_quantized.onnx", model_dir / "model.onnx") if p.exists())
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session = ort.InferenceSession(str(onnx), opts, providers=["CPUExecutionProvider"])
    tok = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
    config = json.loads((model_dir / "config.json").read_text())
    return session, tok, config


def embed_one(session, tok, config, text, max_tokens):
    ids = tok.encode(text).ids[: max_tokens - 1]
    decoder = config.get("model_type", "").startswith("qwen")
    eos = config.get("eos_token_id")
    if decoder and isinstance(eos, int) and (not ids or ids[-1] != eos):
        ids.append(eos)  # last-token pooling reads the end-of-text position
    n = len(ids)
    feed = {}
    for inp in session.get_inputs():
        name = inp.name
        if name == "input_ids":
            feed[name] = np.array([ids], dtype=np.int64)
        elif name == "attention_mask":
            feed[name] = np.ones((1, n), dtype=np.int64)
        elif name == "position_ids":
            feed[name] = np.arange(n, dtype=np.int64)[None, :]
        elif name == "token_type_ids":
            feed[name] = np.zeros((1, n), dtype=np.int64)
        elif name.startswith("past_key_values"):
            shape = [1 if d == "batch_size" else 0 if isinstance(d, str) else d for d in inp.shape]
            feed[name] = np.zeros(shape, dtype=np.float16 if "float16" in inp.type else np.float32)
        else:
            raise SystemExit(f"unsupported model input {name}")
    hidden = session.run(None, feed)[0][0]  # (tokens, dim)
    vec = hidden[-1] if decoder else hidden.mean(axis=0)
    return vec / (np.linalg.norm(vec) or 1.0)


def serve(model_dir):
    """One JSON request per line, {"text": ...} -> {"vector": [...]}, until stdin closes."""
    session, tok, config = load(model_dir)
    for line in sys.stdin:
        text = json.loads(line)["text"]
        vec = embed_one(session, tok, config, text, 256)
        sys.stdout.write(json.dumps({"vector": [round(float(v), 6) for v in vec]}) + "\n")
        sys.stdout.flush()


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--serve":
        return serve(sys.argv[2])
    job = json.load(sys.stdin)
    session, tok, config = load(job["model_dir"])
    texts = job["texts"]
    out = []
    for i, text in enumerate(texts, 1):
        out.append(embed_one(session, tok, config, text, job.get("max_tokens", 512)))
        if i % 10 == 0 or i == len(texts):
            print(f"embedded {i}/{len(texts)}", file=sys.stderr, flush=True)
    np.save(job["out"], np.array(out, dtype=np.float32))


if __name__ == "__main__":
    main()
