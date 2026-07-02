# Phase 1 — IMPLEMENTATION (as-built runbook)

*The executable steps for Phase 1, prepared 2026-06-17 as a head start (Phase 0 is complete and CI-green).
Companion to the design in [`phase-1-corpus.md`](phase-1-corpus.md); the canonical schema + the two
metadata records live in [`../SPEC_V1.md`](../SPEC_V1.md) §4–6. Written to teach (this is the builder's
first ingestion/embeddings/vector-store work). Unlike Phase 0, Phase 1 is **not one sitting** — the
statute-cleaning (Step 4) is genuinely hands-on and iterative.*

> **High-confidence vs verify-tomorrow.** The metadata model, the `.meta.yaml` records, and the chunker
> below are stable Python — copy them. The **Chroma** and **embedding** calls are version-sensitive
> (those libraries change across releases) — they're written correctly to the current API as I
> understand it, but **confirm them against the versions you actually install** before trusting them.

---

## 0. Before you start — two build-time decisions to confirm

**A) Embedding tool — a hardware-aware change from the plan.** The plan said
`sentence-transformers`, but that pulls **PyTorch (~2 GB+)** — heavy for your RTX 4050 / 16 GB box and
your ~$0 budget. The same model is available far lighter:

- **Recommended: `fastembed`** (Qdrant's ONNX embedder, **no PyTorch**, ~100 MB). Runs the same
  small MiniLM/BGE models on CPU, fast, and sits cleanly behind our `Embedder` interface (Seam 4) so the
  dimension-mismatch guard is still ours.
- *Alternatives:* Chroma's built-in `DefaultEmbeddingFunction` (ONNX too, but Chroma owns the embedding
  — less explicit control); or full `sentence-transformers` (the plan's choice — only if you want torch
  for other reasons).

**Confirm fastembed tomorrow.** It keeps the install light and the Seam-4 interface intact. The rest of
this doc assumes it.

**B) Corpus scope (already decided, SPEC §2):** Colorado is ingested in **full**; Connecticut is the
**employment subset (Sec. 7–12)** only. Clean accordingly in Step 4.

---

## Step 1 — dependencies

Add to `pyproject.toml` `dependencies` (Phase 1 additions):

```toml
    "chromadb",
    "fastembed",
    "pyyaml",
```

Then, with the venv active:

```bash
pip install -e ".[dev]"
pip freeze > requirements-lock.txt   # refresh the lock
```

> Heads-up: `chromadb` + `fastembed` pull `onnxruntime` and friends — a few hundred MB, a minute or two.
> Much lighter than torch, but not instant. Still no GPU needed (CPU ONNX is plenty for 2 statutes).

---

## Step 2 — the `LawMetadata` model (the contract, executable)

This makes SPEC §4 a real validator: a malformed `.meta.yaml` fails loudly at load time.

**`src/patchwork_assurance/core/corpus/__init__.py`** — empty package marker (a docstring is fine).

**`src/patchwork_assurance/core/corpus/metadata.py`:**

```python
from datetime import date
from typing import Literal

from pydantic import BaseModel

# Controlled vocabularies (SPEC §3). Literals make the YAML self-validating.
ScopeDomain = Literal[
    "education", "employment", "housing", "financial_lending", "insurance",
    "health_care", "government_services",
    # reserved for CT's non-employment parts (post-v1):
    "online_safety_minors", "ai_companion", "generative_ai_provenance", "frontier_models",
]
Status = Literal["enacted", "effective", "enjoined", "repealed"]
RegulatedRole = Literal["developer", "deployer"]


class EffectiveDate(BaseModel):
    date: date
    applies_to: str


class Obligation(BaseModel):
    section: str
    label: str


class LawMetadata(BaseModel):
    """Law-level metadata — the human-authored source of truth (SPEC §4).
    The loader flattens this into Chroma-safe chunk metadata (Step 6 / SPEC §6)."""

    law_id: str
    jurisdiction: str
    short_name: str
    law_name: str
    citation: str
    also_known_as: list[str] = []
    status: Status
    signed_date: date
    effective_dates: list[EffectiveDate]
    operative_standard: str
    regulated_tech_term: str
    regulated_roles: list[RegulatedRole]
    scope_domains: list[ScopeDomain]
    enforcement_authority: str
    enforcement_mechanism: str
    cure_period: str | None
    private_right_of_action: bool
    key_obligations: list[Obligation] = []
    source_url: str
    source_page: str | None = None
    retrieved_on: date
```

---

## Step 3 — the two `.meta.yaml` records

These are **already authored and verified** in SPEC §5 — copy them verbatim. They validate against the
model above.

**`corpus/co-sb26-189.meta.yaml`** — from SPEC §5.1 (CO: "materially influence", 7 domains, CCPA, 60-day
cure, no private right of action, effective Jan 1 2027).

**`corpus/ct-sb5-pa26-15.meta.yaml`** — from SPEC §5.2 (CT: "substantial factor", employment, CUTPA,
staggered dates, signed May 27 2026).

> Pull the exact YAML from `docs/SPEC_V1.md` §5.1 / §5.2 — don't retype from memory. Then validate each:
> ```bash
> python -c "import yaml; from patchwork_assurance.core.corpus.metadata import LawMetadata; \
> LawMetadata(**yaml.safe_load(open('corpus/co-sb26-189.meta.yaml'))); print('CO ok')"
> ```
> Repeat for CT. A validation error here means a field/typo to fix — exactly the loud-failure contract.

---

## Step 4 — clean the statutes → `corpus/*.md` (the hands-on integrity task)

**This is the one genuinely manual, iterative step**, and the integrity rule is absolute (Phase 1 §5):
the text comes from the **official PDFs** (`corpus/ocr-source-pdfs/`), cleaned — never LLM-authored.

**Define the cleaned-`.md` convention** (the chunker in Step 5 depends on it): each statute **section** is
a Markdown H2 whose heading starts with the section number, e.g.

```markdown
## 6-1-1704. Deployer disclosures - point-of-interaction notice
<the section's statutory text, line-number artifacts stripped>

## 6-1-1705. Consumer rights - correction - human review
...
```

For CT, use its section markers (`## Sec. 10. ...`) and include **only Sec. 7–12**.

**Workflow** (you extracted these same PDFs earlier this session with pypdf, so the tooling is known):

1. Extract raw text per PDF (a throwaway script):
   ```python
   import pypdf
   reader = pypdf.PdfReader("corpus/ocr-source-pdfs/co-sb26-189-signed-act.pdf")
   raw = "\n".join((p.extract_text() or "") for p in reader.pages)
   open("/tmp/co_raw.txt", "w").write(raw)
   ```
2. Clean by hand into `corpus/co-sb26-189.md`: strip page headers/footers, line numbers, and running
   marginalia; keep section numbering, headings, and citations intact; wrap each section under its `##`
   heading. An LLM may *assist the cleanup* (e.g. "strip the line-number column"), but the words are the
   statute's.
3. Spot-check against the official PDF that no text was altered — this is a compliance corpus.

> Honest note: budget real time here. It's the J.D.-edge task (reading statutes is the cheap part for
> you), and it's the one step that resists full automation. Do CO first, get the whole pipeline green on
> it, then do CT's subset.

---

## Step 5 — the custom chunker (structure-first, citation-preserving)

Decided in Phase 1 §6.1. Pure Python, stable — copy it.

**`src/patchwork_assurance/core/corpus/chunk.py`:**

```python
import re
from dataclasses import dataclass

# An H2 heading is one statute section. The leading token is the section number
# (e.g. "6-1-1704" for CO, "Sec. 10" for CT).
_HEADING = re.compile(r"^##\s+(.*\S)\s*$")
_SECTION_NUM = re.compile(r"^(\d+-\d+-\d+\w*|Sec\.\s*\d+\w*)")

# Char-based size bound (a simple ~4-chars/token proxy avoids a tokenizer dependency).
_MAX_CHARS = 2800   # ~700 tokens
_OVERLAP_CHARS = 400  # ~100 tokens


@dataclass
class Chunk:
    text: str
    section_number: str
    section_heading: str
    chunk_index: int


def chunk_markdown(text: str) -> list[Chunk]:
    """Split cleaned statute markdown into section-aware chunks that keep their citation."""
    sections: list[tuple[str, str, list[str]]] = []  # (section_number, heading, body lines)
    current: tuple[str, str, list[str]] | None = None

    for line in text.splitlines():
        m = _HEADING.match(line)
        if m:
            heading = m.group(1)
            num_match = _SECTION_NUM.match(heading)
            section_number = num_match.group(1) if num_match else heading
            current = (section_number, heading, [])
            sections.append(current)
        elif current is not None:
            current[2].append(line)

    chunks: list[Chunk] = []
    idx = 0
    for section_number, heading, body_lines in sections:
        body = f"## {heading}\n" + "\n".join(body_lines).strip()
        for piece in _split_by_size(body):
            chunks.append(Chunk(piece, section_number, heading, idx))
            idx += 1
    return chunks


def _split_by_size(body: str) -> list[str]:
    """One chunk per section, unless it exceeds the size bound — then split with overlap."""
    if len(body) <= _MAX_CHARS:
        return [body]
    pieces, start = [], 0
    while start < len(body):
        end = start + _MAX_CHARS
        pieces.append(body[start:end])
        start = end - _OVERLAP_CHARS
    return pieces
```

> Tune `_HEADING`/`_SECTION_NUM` to match the exact `##` convention you settle on in Step 4 — they're
> coupled by design.

---

## Step 6 — the embedder interface + the Chroma vector store

**Seam 4 + the dimension-mismatch guard.** *Verify the `fastembed` and `chromadb` APIs against your
installed versions* — these are the churniest calls in the project.

**`src/patchwork_assurance/core/embeddings.py`:**

```python
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class FastEmbedEmbedder:
    """ONNX MiniLM/BGE embeddings, no PyTorch. Verify the fastembed API at build."""

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [list(vec) for vec in self._model.embed(texts)]
```

**`src/patchwork_assurance/core/vectorstore.py`:**

```python
from typing import Protocol

import chromadb

COLLECTION = "patchwork_corpus"


class VectorStore(Protocol):
    def add(self, ids, embeddings, documents, metadatas) -> None: ...
    def count(self) -> int: ...
    def embedding_model(self) -> str | None: ...


class ChromaVectorStore:
    """Persistent, idempotent Chroma collection. Verify the chromadb API at build."""

    def __init__(self, path: str, embedding_model_name: str) -> None:
        self._client = chromadb.PersistentClient(path=path)
        # Stamp the embedding model on the collection — the mismatch guard (SPEC §7):
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION,
            metadata={"embedding_model": embedding_model_name},
        )

    def add(self, ids, embeddings, documents, metadatas) -> None:
        # upsert (not add) so re-running the loader updates in place — idempotent.
        self._collection.upsert(
            ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
        )

    def count(self) -> int:
        return self._collection.count()

    def embedding_model(self) -> str | None:
        return (self._collection.metadata or {}).get("embedding_model")
```

---

## Step 7 — the loader (read → validate → chunk → embed → upsert)

**`src/patchwork_assurance/core/corpus/loader.py`:**

```python
from pathlib import Path

import yaml

from patchwork_assurance.core.corpus.chunk import Chunk, chunk_markdown
from patchwork_assurance.core.corpus.metadata import LawMetadata


def _flatten(meta: LawMetadata, chunk: Chunk) -> dict:
    """Law metadata + chunk -> Chroma-safe scalar metadata (SPEC §6).
    scope_domains becomes per-domain booleans so retrieval can filter by domain."""
    flat = {
        "law_id": meta.law_id,
        "jurisdiction": meta.jurisdiction,
        "short_name": meta.short_name,
        "citation": meta.citation,
        "section_number": chunk.section_number,
        "section_heading": chunk.section_heading,
        "effective_date_primary": meta.effective_dates[0].date.isoformat(),
        "source_url": meta.source_url,
        "chunk_index": chunk.chunk_index,
    }
    for domain in meta.scope_domains:
        flat[f"scope_{domain}"] = True
    return flat


def load_corpus(corpus_path: Path, store, embedder) -> int:
    """Ingest every <law_id>.meta.yaml + sibling <law_id>.md. Returns chunks indexed."""
    total = 0
    for meta_file in sorted(corpus_path.glob("*.meta.yaml")):
        meta = LawMetadata(**yaml.safe_load(meta_file.read_text()))
        md_file = corpus_path / f"{meta.law_id}.md"
        chunks = chunk_markdown(md_file.read_text())

        ids = [f"{meta.law_id}:{c.chunk_index}" for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [_flatten(meta, c) for c in chunks]
        embeddings = embedder.embed(documents)

        store.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        total += len(chunks)
    return total
```

A small runnable entry point (so `python -m patchwork_assurance.core.corpus.build` indexes everything):

**`src/patchwork_assurance/core/corpus/build.py`:**

```python
from pathlib import Path

from patchwork_assurance.config import settings
from patchwork_assurance.core.embeddings import FastEmbedEmbedder
from patchwork_assurance.core.vectorstore import ChromaVectorStore


def main() -> None:
    embedder = FastEmbedEmbedder()
    store = ChromaVectorStore(path=settings.chroma_path, embedding_model_name=embedder.model_name)
    from patchwork_assurance.core.corpus.loader import load_corpus

    n = load_corpus(Path(settings.corpus_path), store, embedder)
    print(f"Indexed {n} chunks into {store.count()} total.")


if __name__ == "__main__":
    main()
```

Add the new config fields to `config.py`:

```python
    corpus_path: str = "corpus"
    chroma_path: str = ".chroma"
```

---

## Step 8 — wire the real `corpus_size` into `/health`

Update `core_status()` so `/health` reflects the indexed corpus (Phase 0 left it at 0):

```python
def core_status() -> dict:
    from patchwork_assurance.config import settings
    from patchwork_assurance.core.vectorstore import ChromaVectorStore

    try:
        store = ChromaVectorStore(path=settings.chroma_path, embedding_model_name="")
        corpus_size = store.count()
    except Exception:
        corpus_size = 0  # index not built yet
    return {"status": "ok", "layer": "core", "version": __version__, "corpus_size": corpus_size}
```

> This is a Phase-1 stopgap (opening the store per call). Phase 3 moves store construction into the
> FastAPI lifespan (load once) — don't optimize it now.

---

## Step 9 — tests (a tiny fixture corpus, no network)

Put a fake 2-section "statute" + meta under `tests/fixtures/` so tests never depend on the real bills.

- `test_metadata.py` — a malformed `.meta.yaml` raises a `ValidationError` (the loud-failure contract).
- `test_chunk.py` — the chunker splits the fixture into the expected sections and attaches the section
  number/heading; a long section sub-splits with overlap.
- `test_loader.py` — load the fixture; assert chunk count, that `scope_<domain>` booleans are derived,
  and that the collection count matches; **run it twice and assert the count is unchanged (idempotent)**.
- For tests, a **stub embedder** (returns fixed-length zero vectors) keeps them offline and fast — no
  model download in CI.

---

## Step 10 — run it for real + verify

```bash
python -m patchwork_assurance.core.corpus.build
# -> "Indexed N chunks into N total."
```

Then `make dev`, click **Check system status**, and `/health` should now report a **non-zero
`corpus_size`** — the Phase 0 stub turned real. (First run downloads the ONNX embedding model, ~100 MB,
once.)

---

## Definition of done

- [x] Two cleaned `corpus/*.md` (CO full; CT Sec. 1–2, 4–15 — expanded from original plan after PDF review), faithful to the official PDFs.
- [x] Two `corpus/*.meta.yaml`, each validating against `LawMetadata`.
- [x] The loader ingests the folder generically (no hardcoded filenames/jurisdictions); idempotent.
- [x] The embedding model is stamped on the Chroma collection (mismatch guard).
- [x] `/health` reports a real `corpus_size` (47 chunks on 2026-06-18).
- [x] Fixture tests pass (validation, chunking, count, idempotency); CI green.
- [x] SPEC §4 schema reflects the final `LawMetadata`.

---

## Learning recap (what Phase 1 teaches)

- **Ingestion pipeline:** read → validate → chunk → embed → upsert, as composable pure functions.
- **Embeddings & vector stores:** what an embedding is, why the *same* model must embed corpus and query
  (the mismatch guard), and why a local ONNX model beats a 2 GB torch install for this.
- **Structure-aware chunking:** why legal text is split by section (keeping each chunk's citation), not
  by blind fixed size.
- **Two metadata layers:** rich human YAML → flattened scalar chunk metadata, and why Chroma forces that.
- **Idempotent, deterministic IDs:** the property that lets the Phase 9 agent re-run the loader safely.

---

## As-built notes

- **Embedding tool: `fastembed` 0.8.0** (ONNX, no torch). `embed()` returns a generator of numpy
  arrays; `.tolist()` required to convert to pure Python floats — `list(vec)` leaves `np.float32`
  scalars which Chroma 1.5.9 rejects with a `ValueError`.
- **Chroma 1.5.9**: `PersistentClient` / `get_or_create_collection` / `upsert` all confirmed stable.
- **CT corpus scope expanded** from the plan's Sec. 7–12 to Sec. 1–2, 4–15 after PDF review.
  Sec. 3 (government sandbox directive) and Sec. 16+ (research/administrative) deliberately excluded.
  CT `.meta.yaml` `scope_domains` updated to `[employment, ai_companion, generative_ai_provenance, frontier_models]`.
- **`corpus_size` in `/health`** is a per-call stopgap; Phase 3's lifespan replaces it.

### Colorado text integrity — re-OCR remediation (2026-06-18, Opus review)

A critical-eye review found the first CO `co-sb26-189.md` was **not faithful to the statute**. Root
cause: the official signed-act PDF is a **scanned image with a corrupt embedded OCR text layer** (CO
sets new statutory material in an all-caps font that the state's OCR mishandled). Every text extractor
(pypdf, PyMuPDF) faithfully returned that corruption — 3 page headers embedded mid-statute, ~11
run-together words, dozens of split words (`FERP A`, `ST A TE`), and **corrupted subsection enumerators**
(`(II)`→`(11)`, `(III)`→`(111)`, `(IX)`→`(LX)`), which is a citation-integrity defect for a compliance
tool. CT (mixed-case PDF) was unaffected.

**Fix:** re-OCR the PDF's 400-DPI page images with Tesseract 5 (working from the clean *visual*
document, which is the official source — not the corrupt embedded layer). This eliminated all
systematic corruption. Tesseract then left a small, bounded residual: it systematically misreads
leading roman numerals as digits/letters (`(I)`→`(1)`, `(II)`→`(I)`, `(IX)`→`(LX)`). Because CO
statutory nesting is **strictly sequential** (`(1)`→`(a)`→`(I)`→`(A)`), every residual was identified
with certainty from sequence position and corrected: **18 enumerator fixes + 9 text-glyph fixes**, all
applied as unique, asserted, context-anchored replacements (each must match exactly once). These are
OCR *corrections* (faithful to the statute's own structure), **not** LLM authoring — auditable against
the page images at `corpus/ocr-source-pdfs/co-sb26-189-signed-act.pdf`. Post-fix verification: all enumerator
sequences valid, zero non-ASCII, all 11 section headings intact, key operative text spot-checked.

> Reproduction (throwaway scripts not retained): render each PDF page at 400 DPI via PyMuPDF
> (`page.get_pixmap(dpi=400)`), OCR with `pytesseract` (`--psm 3`), strip page headers/footnote/preamble,
> emit `## <section>` headings, then apply the 27-item correction map above. The committed
> `corpus/co-sb26-189.md` is the source of truth going forward.

### CT completeness — Sec. 17 added (2026-06-18)

The Opus review found one genuine dangling internal reference: included Sec. 1 and Sec. 4 reference
"artificial intelligence, as defined in **section 17** of this act," but Sec. 17 was excluded. (The
other cross-references — `section 31-51m`, `section 35-51`, `section 42-110b` — are external Connecticut
General Statutes citations, not internal, so they're correctly out of scope.) Full Sec. 17 added (the
"artificial intelligence" definition + the Connecticut AI Academy provisions; effective July 1, 2026).
CT `.meta.yaml` citation + `effective_dates` updated accordingly.

### CT text integrity — re-OCR'd to match the CO gold standard (2026-06-18)

The first CT `.md` (pypdf-extracted) had ~40 spurious mid-word space splits (`membersh ip`,
`consu mers`, `applicati on`, `occ upational`) — surfaced by diffing the pypdf words against a clean
re-OCR vocabulary. Rather than whack-a-mole, CT was **re-OCR'd wholesale** at 400 DPI (Tesseract 5),
same as CO. Mixed-case OCR preserved the enumerators cleanly (verified: `(A)/(B)`, `(i)/(ii)/(iii)`,
`(I)/(II)` sequences all intact). Residual: only **2 glyph fixes** (`(A)(i1)`→`(A)(ii)`, a cent-sign in
the CUTPA cite `42-110¢g`→`42-110g`) — far fewer than CO because mixed-case text doesn't trigger the
roman-numeral confusion. Sections kept: 1-2, 4-15, 17 (skip 3, 16, 18+). Final: zero non-ASCII, all
15 headings, AI definition (Sec. 17) intact.

- **Phase 1 complete — 2026-06-18.** 50 chunks indexed. Both statutes re-OCR'd from their official
  page images and integrity-verified (CO: 9 sections + 2 amendments, 18 enumerator + 9 glyph fixes;
  CT: 15 sections incl. Sec. 17, 2 glyph fixes). All gates green; the corpus is the trustworthy,
  citation-faithful foundation the rest of v1 builds on.
