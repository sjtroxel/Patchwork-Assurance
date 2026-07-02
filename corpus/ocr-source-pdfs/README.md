# corpus/ocr-source-pdfs/

Official statute source **PDFs that are image scans** and required our own OCR pass (Tesseract at
400 DPI, per the Phase 1 method) before the text could be cleaned into a `corpus/<law_id>.md`.

This folder is **only** for OCR-requiring PDF sources. It is not a general source archive:

- Laws sourced from **clean, machine-readable HTML** (e.g. Illinois `ilga.gov`, NYC Legistar,
  Connecticut's CTDPA from `cga.ct.gov`) keep **no** raw source file here — the `source_url` in the
  law's `.meta.yaml` is the record of provenance.
- A law lands a file here **only** when its official source was a scanned PDF needing OCR.

The loader ignores this folder (it globs `corpus/*.md` + `*.meta.yaml`); nothing here is indexed.
