"""Phase 8 batch 5 — re-tune the deferred retrieval knobs against the scorecard.

    python -m eval.sweep_knobs            # sweep top_k, chunk size, embedding model (free, offline)
    python -m eval.sweep_knobs --k-values 3,5,8,10
    python -m eval.sweep_knobs --chunk-sizes 1800,2800,3600 --overlap 400
    python -m eval.sweep_knobs --embed-models BAAI/bge-small-en-v1.5,sentence-transformers/all-MiniLM-L6-v2

The embedding model, chunk size/overlap, and top_k were set by judgment in Phase 1/2. This script
*measures* them so the chosen values are evidence-backed (plan §8, build order step 5). It is a
free, deterministic measurement — no LLM, no API key.

Method: one factor at a time around the production baseline. Each non-baseline config is built into
an ISOLATED temporary Chroma index (production `.chroma` is never touched) with a chunk-aligned
lexical index, scored on both gold sets, then torn down. top_k is swept over a single index (cheap).
Scoring routes through the same `score_retrieval` / `score_query_retrieval` the main eval uses, so we
measure the production path. Two metrics per config:

  grounding  — mean recall@k over the 14-case scope/grounding gold set (eval/gold/cases.yaml)
  exact-term — mean recall@k over the 5-case exact-term/citation gold set (retrieval_cases.yaml)
"""

import argparse
import json
import logging
import shutil
import sys
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from eval.harness import Core
from eval.loader import load_gold, load_retrieval_gold
from eval.metrics import score_query_retrieval, score_retrieval
from patchwork_assurance.config import settings
from patchwork_assurance.core.corpus.chunk import _MAX_CHARS, _OVERLAP_CHARS
from patchwork_assurance.core.corpus.loader import load_corpus
from patchwork_assurance.core.embeddings import FastEmbedEmbedder
from patchwork_assurance.core.grounding import corpus_section_texts
from patchwork_assurance.core.lexical import build_lexical_index
from patchwork_assurance.core.retrieval import Retriever
from patchwork_assurance.core.scope import load_law_metadata
from patchwork_assurance.core.vectorstore import ChromaVectorStore

RESULTS_DIR = Path(__file__).parent / "results"
# Baseline = today's production defaults. Each sweep varies ONE of these and holds the rest here.
BASE_K = 8  # == MEMO_RETRIEVAL_K, the k the memo retrieves at
BASE_MODEL = "BAAI/bge-small-en-v1.5"
BASE_MAX_CHARS = _MAX_CHARS
BASE_OVERLAP = _OVERLAP_CHARS


@contextmanager
def isolated_core(corpus_path: Path, embed_model: str, max_chars: int, overlap_chars: int):
    """Build a throwaway Core (vector + lexical) in a temp Chroma dir, yield it, then delete the dir.

    The temp index keeps the production `.chroma` untouched and sidesteps the embedding-model stamp
    (a fresh collection takes the new model name cleanly). The lexical index uses the SAME chunk
    params so the two views stay aligned (rag.md). Embedder build may download a model on first use;
    callers handle that failure and skip the model."""
    tmp = Path(tempfile.mkdtemp(prefix="pw-knobsweep-"))
    try:
        embedder = FastEmbedEmbedder(model_name=embed_model)
        store = ChromaVectorStore(str(tmp / "chroma"), embedder.model_name)
        load_corpus(corpus_path, store, embedder, max_chars=max_chars, overlap_chars=overlap_chars)
        lexical = build_lexical_index(corpus_path, max_chars=max_chars, overlap_chars=overlap_chars)
        yield Core(
            retriever=Retriever(store, embedder, lexical),
            laws=load_law_metadata(corpus_path),
            section_texts=corpus_section_texts(corpus_path),
        )
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _score(core: Core, k: int, mode: str) -> tuple[float, float]:
    """(grounding recall@k, exact-term recall@k) for one Core — the same two metrics the eval prints."""
    g_cases = load_gold()
    # pin=False: the sweep compares the RAW semantic layer (embedding model / chunk size / top_k).
    # The production key-obligation pin backstops that layer but would mask config differences here.
    g = [score_retrieval(c, core, k, mode, pin=False) for c in g_cases]
    g = [o for o in g if o is not None]
    grounding = sum(o.recall for o in g) / len(g) if g else 0.0

    q_cases = load_retrieval_gold()
    q = [score_query_retrieval(c, core, k, mode) for c in q_cases]
    exact = sum(o.recall for o in q) / len(q) if q else 0.0
    return grounding, exact


def _row(label: str, grounding: float, exact: float, is_base: bool) -> str:
    mark = " (baseline)" if is_base else ""
    return f"    {label:<34} grounding {grounding:6.1%}   exact-term {exact:6.1%}{mark}"


def sweep_top_k(corpus_path: Path, k_values: list[int], mode: str) -> list[dict]:
    """Cheapest knob: one baseline index, vary k. No re-ingest."""
    print(f"\n  top_k  (model={BASE_MODEL}, chunk={BASE_MAX_CHARS}/{BASE_OVERLAP}, mode={mode})")
    rows: list[dict] = []
    with isolated_core(corpus_path, BASE_MODEL, BASE_MAX_CHARS, BASE_OVERLAP) as core:
        for k in k_values:
            grounding, exact = _score(core, k, mode)
            print(_row(f"k={k}", grounding, exact, k == BASE_K))
            rows.append(
                {"k": k, "grounding": grounding, "exact_term": exact, "baseline": k == BASE_K}
            )
    return rows


def sweep_chunk_size(
    corpus_path: Path, sizes: list[int], overlap: int, k: int, mode: str
) -> list[dict]:
    """Re-chunk + re-embed per size into an isolated index. overlap held fixed across sizes."""
    print(f"\n  chunk size  (model={BASE_MODEL}, overlap={overlap}, k={k}, mode={mode})")
    rows: list[dict] = []
    for size in sizes:
        with isolated_core(corpus_path, BASE_MODEL, size, overlap) as core:
            grounding, exact = _score(core, k, mode)
        is_base = size == BASE_MAX_CHARS and overlap == BASE_OVERLAP
        print(_row(f"max_chars={size}", grounding, exact, is_base))
        rows.append(
            {
                "max_chars": size,
                "overlap": overlap,
                "grounding": grounding,
                "exact_term": exact,
                "baseline": is_base,
            }
        )
    return rows


def sweep_embed_model(corpus_path: Path, models: list[str], k: int, mode: str) -> list[dict]:
    """Re-embed the corpus under each model into an isolated index. A model that fails to load
    (offline / not in fastembed's catalog) is skipped with a note, not a crash."""
    print(f"\n  embedding model  (chunk={BASE_MAX_CHARS}/{BASE_OVERLAP}, k={k}, mode={mode})")
    rows: list[dict] = []
    for model in models:
        try:
            with isolated_core(corpus_path, model, BASE_MAX_CHARS, BASE_OVERLAP) as core:
                grounding, exact = _score(core, k, mode)
        except Exception as e:  # noqa: BLE001 — measurement script: report and continue
            print(f"    {model:<34} [skipped] {type(e).__name__}: {str(e)[:80]}")
            rows.append({"model": model, "skipped": str(e)[:160]})
            continue
        print(_row(model, grounding, exact, model == BASE_MODEL))
        rows.append(
            {
                "model": model,
                "grounding": grounding,
                "exact_term": exact,
                "baseline": model == BASE_MODEL,
            }
        )
    return rows


def _ints(csv: str) -> list[int]:
    return [int(x) for x in csv.split(",") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 8 knob sweep (free, offline)")
    parser.add_argument("--k-values", default="3,5,8,10", type=_ints)
    parser.add_argument("--chunk-sizes", default="1800,2800,3600", type=_ints)
    parser.add_argument("--overlap", default=BASE_OVERLAP, type=int)
    parser.add_argument(
        "--embed-models",
        default="BAAI/bge-small-en-v1.5,sentence-transformers/all-MiniLM-L6-v2",
        type=lambda s: [m.strip() for m in s.split(",") if m.strip()],
    )
    parser.add_argument(
        "--k", default=BASE_K, type=int, help="base top_k for the chunk/model sweeps"
    )
    parser.add_argument(
        "--mode",
        default=settings.retrieval_mode,
        help="retrieval mode to tune at (default: config)",
    )
    args = parser.parse_args()

    # The per-retrieve Phase 7 logs would bury the scorecard — quiet them for this run only (local to
    # the process; production logging config is untouched). Recall is the signal here, not latency.
    logging.getLogger("patchwork").setLevel(logging.WARNING)

    corpus_path = Path(settings.corpus_path)
    print("=" * 76)
    print("PATCHWORK KNOB SWEEP  —  Phase 8 batch 5 (free, offline, one factor at a time)")
    print("=" * 76)
    print(f"  baseline: model={BASE_MODEL}  chunk={BASE_MAX_CHARS}/{BASE_OVERLAP}  k={BASE_K}")

    results = {
        "mode": args.mode,
        "baseline": {
            "model": BASE_MODEL,
            "max_chars": BASE_MAX_CHARS,
            "overlap": BASE_OVERLAP,
            "k": BASE_K,
        },
        "top_k": sweep_top_k(corpus_path, args.k_values, args.mode),
        "chunk_size": sweep_chunk_size(
            corpus_path, args.chunk_sizes, args.overlap, args.k, args.mode
        ),
        "embed_model": sweep_embed_model(corpus_path, args.embed_models, args.k, args.mode),
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"knobs-{stamp}.json"
    out.write_text(json.dumps(results, indent=2))
    print(f"\n  wrote {out.relative_to(Path.cwd())}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
